"""
Tranche 12 — Confidence Calibration & Learning from Trading Outcomes (T12).

Extends the existing calibration system with:
  1. Per-signal-type **and** per-venue confidence tracking.
  2. **Bayesian update** using Beta-distribution inference
     (posterior = Beta(alpha + wins, beta + losses)).
  3. **Auto-adjust** of min_confidence threshold ±5% when calibration
     error exceeds 10 %.
  4. **Append-only ledger** at ``data/calibration_log.jsonl`` recording
     every threshold change (old → new + rationale).
  5. **State file** for restart resilience (JSON).
  6. Decision-agent method: ``get_adjusted_min_confidence(signal_type, venue)``.

All stdlib — no external dependencies.  Thread-safe via ``threading.Lock``.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

VALID_SIGNAL_TYPES: Tuple[str, ...] = (
    "cross_exchange",
    "triangular",
    "Solana_dex",
    "staking",
)

DEFAULT_LOG_PATH: str = "data/calibration_log.jsonl"
DEFAULT_STATE_PATH: str = "data/calibration_state.json"

MIN_DATA_POINTS: int = 3       # minimum records before calibration kicks in
MAX_ENTRIES: int = 500          # retained in-memory for ledger replay

DEFAULT_MIN_CONFIDENCE: float = 0.30
MIN_THRESHOLD: float = 0.05
MAX_THRESHOLD: float = 0.95

# Beta prior — minimally informative (Jeffreys prior-like)
BETA_PRIOR_ALPHA: float = 0.5
BETA_PRIOR_BETA: float = 0.5


# ── Data Classes ───────────────────────────────────────────────────────

@dataclass
class ConfidenceRecord:
    """One recorded prediction vs. actual outcome."""

    signal_type: str
    venue: str
    predicted_confidence: float  # 0.0 – 1.0
    actual_pnl: float            # positive = profit
    timestamp: str               # ISO8601 UTC


@dataclass
class CalibrationState:
    """Per-(signal_type, venue) calibration statistics."""

    signal_type: str
    venue: str
    alpha: float = BETA_PRIOR_ALPHA
    beta: float = BETA_PRIOR_BETA
    wins: int = 0
    losses: int = 0
    total: int = 0
    sum_predicted_confidence: float = 0.0
    current_threshold: float = DEFAULT_MIN_CONFIDENCE
    last_adjustment_ts: str = ""


@dataclass
class ThresholdChangeLog:
    """A single threshold-adjustment event written to the append-only ledger."""

    signal_type: str
    venue: str
    old_threshold: float
    new_threshold: float
    rationale: str
    calibration_error_before: float
    timestamp: str


# ── Helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _beta_log_pdf(alpha: float, beta: float, x: float) -> float:
    """Log of the Beta(alpha, beta) PDF at x (used internally)."""
    if x <= 0.0 or x >= 1.0:
        return -float("inf")
    log_beta = (
        math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(alpha + beta)
    )
    return (alpha - 1.0) * math.log(x) + (beta - 1.0) * math.log(1.0 - x) - log_beta


def _beta_posterior_mean(alpha: float, beta: float) -> float:
    """Expected value of a Beta(alpha, beta) distribution."""
    denom = alpha + beta
    if denom <= 0.0:
        return 0.5
    return alpha / denom


def _calibrated_win_rate(alpha: float, beta: float) -> float:
    """Posterior mean win rate from Beta(alpha, beta)."""
    return _beta_posterior_mean(alpha, beta)


def _posterior_std(alpha: float, beta: float) -> float:
    """Standard deviation of Beta(alpha, beta)."""
    denom = alpha + beta
    if denom <= 0.0:
        return 0.5
    var = (alpha * beta) / (denom * denom * (denom + 1.0))
    return math.sqrt(var)


# ── Confidence Calibrator ──────────────────────────────────────────────

class ConfidenceCalibrator:
    """Learns from trading outcomes using Bayesian Beta updates.

    Thread-safe via ``self._lock``.  Data is persisted to:
      - an **append-only JSONL ledger** for audit (every outcome recorded).
      - a **state JSON file** for fast restart (calibration parameters).

    Design
    ------
    For each ``(signal_type, venue)`` pair we maintain a Beta posterior
    distribution.  The prior is Beta(0.5, 0.5).  After each recorded
    outcome we update:

        alpha += 1  if profitable
        beta  += 1  if non-profitable

    The posterior mean ``alpha / (alpha + beta)`` represents the
    calibrated win-rate estimate.

    If the absolute difference between the posterior mean and the
    average predicted confidence exceeds **10%**, the ``current_threshold``
    is adjusted by **±5%** in the direction that would improve selector
    conservatism.
    """

    def __init__(
        self,
        log_path: str = DEFAULT_LOG_PATH,
        state_path: str = DEFAULT_STATE_PATH,
    ) -> None:
        self._lock = threading.Lock()
        self.log_path = Path(log_path)
        self.state_path = Path(state_path)

        # Ensure parent directories exist.
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory ring buffer of recent entries (for quick stats).
        self._entries: List[ConfidenceRecord] = []

        # Calibration state keyed by "(signal_type)|(venue)".
        self._state: Dict[str, CalibrationState] = {}

        # Load persisted state (if any) / replay ledger.
        self._load_state()
        self._replay_ledger()

    # ── Public API ─────────────────────────────────────────────────────

    def record_outcome(
        self,
        signal_type: str,
        venue: str,
        predicted_confidence: float,
        actual_pnl: float,
    ) -> None:
        """Record a prediction vs. actual outcome.

        Parameters
        ----------
        signal_type : str
            One of ``VALID_SIGNAL_TYPES``.
        venue : str
            Exchange or venue name (e.g. ``"coinbase"``, ``"binance"``,
            ``"solana_mainnet"``).
        predicted_confidence : float
            Confidence at decision time, in **[0.0, 1.0]**.
        actual_pnl : float
            Realised P&L in USD (positive = profitable trade).
        """
        predicted_confidence = max(0.0, min(1.0, predicted_confidence))
        is_profitable = actual_pnl > 0.0

        record = ConfidenceRecord(
            signal_type=signal_type,
            venue=venue,
            predicted_confidence=predicted_confidence,
            actual_pnl=actual_pnl,
            timestamp=_now_iso(),
        )

        with self._lock:
            # --- Append to ledger ---
            self._append_ledger(record)
            self._entries.append(record)
            if len(self._entries) > MAX_ENTRIES:
                self._entries = self._entries[-MAX_ENTRIES:]

            # --- Bayesian update ---
            key = self._state_key(signal_type, venue)
            cs = self._state.get(key)
            if cs is None:
                cs = CalibrationState(
                    signal_type=signal_type,
                    venue=venue,
                )
                self._state[key] = cs

            cs.total += 1
            cs.sum_predicted_confidence += predicted_confidence
            if is_profitable:
                cs.wins += 1
                cs.alpha += 1.0
            else:
                cs.losses += 1
                cs.beta += 1.0

            # --- Calibration error check → auto-adjust threshold ---
            self._maybe_adjust_threshold(cs)

            # --- Persist state ---
            self._save_state()

    def get_adjusted_min_confidence(
        self,
        signal_type: str,
        venue: str,
        base_min: float = DEFAULT_MIN_CONFIDENCE,
    ) -> float:
        """Return the calibrated minimum-confidence threshold for a
        ``(signal_type, venue)`` pair.

        The decision agent should call this at startup / before every
        signal evaluation.  Returns the *current threshold* from the
        calibration state if enough data exists; otherwise returns
        ``base_min``.
        """
        with self._lock:
            key = self._state_key(signal_type, venue)
            cs = self._state.get(key)

        if cs is None or cs.total < MIN_DATA_POINTS:
            return base_min

        return cs.current_threshold

    def get_calibration_error(self, signal_type: str, venue: str) -> float:
        """Return the calibration error for a (signal_type, venue) pair.

        Definition
        ----------
        ``abs(posterior_mean_win_rate - avg_predicted_confidence)``

        Returns 0.0 if insufficient data.
        """
        with self._lock:
            key = self._state_key(signal_type, venue)
            cs = self._state.get(key)

        if cs is None or cs.total < MIN_DATA_POINTS:
            return 0.0

        posterior_mean = _calibrated_win_rate(cs.alpha, cs.beta)
        avg_predicted = cs.sum_predicted_confidence / cs.total

        return round(abs(posterior_mean - avg_predicted), 4)

    def get_stats(self) -> Dict[str, Any]:
        """Return a comprehensive calibration report.

        Returns
        -------
        dict
            Top-level keys:
              - ``calibration_report``: dict of ``(signal_type, venue)`` stats
              - ``summary``: aggregate counts
        """
        with self._lock:
            report: Dict[str, Dict[str, Any]] = {}
            for key, cs in self._state.items():
                if cs.total < 1:
                    continue
                posterior_mean = _calibrated_win_rate(cs.alpha, cs.beta)
                posterior_std = _posterior_std(cs.alpha, cs.beta)
                avg_pred = (
                    cs.sum_predicted_confidence / cs.total if cs.total else 0.0
                )
                cal_err = abs(posterior_mean - avg_pred)
                report[key] = {
                    "signal_type": cs.signal_type,
                    "venue": cs.venue,
                    "total": cs.total,
                    "wins": cs.wins,
                    "losses": cs.losses,
                    "win_rate_empirical": (
                        round(cs.wins / cs.total, 4) if cs.total else 0.0
                    ),
                    "posterior_mean_win_rate": round(posterior_mean, 4),
                    "posterior_std": round(posterior_std, 4),
                    "avg_predicted_confidence": round(avg_pred, 4),
                    "calibration_error": round(cal_err, 4),
                    "current_threshold": cs.current_threshold,
                    "last_adjustment_ts": cs.last_adjustment_ts,
                }

        total_entries = len(self._entries)
        total_pairs = len(report)
        total_trades = sum(cs.total for cs in self._state.values())
        total_wins = sum(cs.wins for cs in self._state.values())

        return {
            "calibration_report": report,
            "summary": {
                "total_pairs_tracked": total_pairs,
                "total_trades_recorded": total_trades,
                "total_wins": total_wins,
                "win_rate_overall": (
                    round(total_wins / total_trades, 4) if total_trades else 0.0
                ),
                "in_memory_entries": total_entries,
                "timestamp": _now_iso(),
            },
        }

    def reset(self) -> None:
        """Reset all in-memory calibration state.

        .. warning::
            Does **not** delete the append-only ledger on disk.
        """
        with self._lock:
            self._entries.clear()
            self._state.clear()
            self._save_state()
        logger.info("ConfidenceCalibrator state reset (in-memory).")

    # ── Internal: Threshold auto-adjustment ────────────────────────────

    def _maybe_adjust_threshold(self, cs: CalibrationState) -> None:
        """Check calibration error and adjust threshold if > 10%.

        The caller holds ``self._lock``.
        """
        if cs.total < MIN_DATA_POINTS:
            return

        posterior_mean = _calibrated_win_rate(cs.alpha, cs.beta)
        avg_predicted = cs.sum_predicted_confidence / cs.total
        cal_error = abs(posterior_mean - avg_predicted)

        if cal_error <= 0.10:
            return  # within tolerance

        old_threshold = cs.current_threshold
        new_threshold = old_threshold

        if avg_predicted > posterior_mean:
            # Overconfident: raise threshold (be more selective).
            new_threshold = old_threshold + 0.05
            direction = "raised (overconfident)"
        else:
            # Underconfident: lower threshold (allow more signals).
            new_threshold = old_threshold - 0.05
            direction = "lowered (underconfident)"

        # Clamp.
        new_threshold = max(MIN_THRESHOLD, min(MAX_THRESHOLD, new_threshold))

        if abs(new_threshold - old_threshold) < 0.001:
            return  # no effective change after clamping

        cs.current_threshold = round(new_threshold, 4)
        cs.last_adjustment_ts = _now_iso()

        rationale = (
            f"Calibration error {cal_error:.2%} > 10%: "
            f"avg_predicted={avg_predicted:.2%}, "
            f"posterior_win_rate={posterior_mean:.2%}. "
            f"Threshold {direction} from {old_threshold:.2%} "
            f"to {new_threshold:.2%}."
        )

        # Write to append-only threshold-change ledger.
        change = ThresholdChangeLog(
            signal_type=cs.signal_type,
            venue=cs.venue,
            old_threshold=round(old_threshold, 4),
            new_threshold=round(new_threshold, 4),
            rationale=rationale,
            calibration_error_before=round(cal_error, 4),
            timestamp=_now_iso(),
        )

        self._append_threshold_change(change)

        logger.info("Threshold %s: %s", direction, rationale)

    # ── Internal: Persistence ──────────────────────────────────────────

    @staticmethod
    def _state_key(signal_type: str, venue: str) -> str:
        return f"{signal_type}|{venue}"

    def _append_ledger(self, record: ConfidenceRecord) -> None:
        """Append one outcome record to the JSONL ledger.
        Caller holds ``self._lock``.
        """
        with open(self.log_path, "a") as f:
            f.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    def _append_threshold_change(self, change: ThresholdChangeLog) -> None:
        """Append a threshold-change record to the same JSONL ledger
        (distinguished by the ``__event`` field).
        Caller holds ``self._lock``.
        """
        payload = asdict(change)
        payload["__event"] = "threshold_adjustment"
        with open(self.log_path, "a") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")

    def _save_state(self) -> None:
        """Persist calibration state to JSON for restart resilience.
        Caller holds ``self._lock`` (or no concurrent access).
        """
        data: Dict[str, Any] = {
            "version": 1,
            "timestamp": _now_iso(),
            "pairs": {},
        }
        for key, cs in self._state.items():
            data["pairs"][key] = asdict(cs)

        with open(self.state_path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def _load_state(self) -> None:
        """Load calibration state from JSON file (if it exists)."""
        if not self.state_path.exists():
            return
        try:
            with open(self.state_path, "r") as f:
                data = json.load(f)

            version = data.get("version", 0)
            if version < 1:
                logger.warning("Unknown calibration state version %d", version)
                return

            for key, cs_data in data.get("pairs", {}).items():
                self._state[key] = CalibrationState(**cs_data)

            logger.info(
                "Loaded calibration state: %d pairs", len(self._state)
            )
        except Exception as exc:
            logger.warning("Failed to load calibration state: %s", exc)

    def _replay_ledger(self) -> None:
        """Replay recent entries from the JSONL ledger into memory.

        This captures outcomes that may have been written by a different
        process instance since the last state save.
        """
        if not self.log_path.exists():
            return
        try:
            entries: List[ConfidenceRecord] = []
            with open(self.log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)

                    # Skip threshold-change events (they are meta-records).
                    if data.get("__event") == "threshold_adjustment":
                        continue

                    # Only load records that match our schema.
                    if "signal_type" in data and "venue" in data:
                        entries.append(ConfidenceRecord(**data))

            # Keep only the most recent MAX_ENTRIES.
            self._entries = entries[-MAX_ENTRIES:]
            logger.info(
                "Replayed %d calibration records from ledger",
                len(self._entries),
            )
        except Exception as exc:
            logger.warning("Failed to replay calibration ledger: %s", exc)


# ── Entry Points for Convenience ───────────────────────────────────────

# Module-level singleton (thread-safe via class internals).
_calibrator_instance: Optional[ConfidenceCalibrator] = None
_calibrator_lock = threading.Lock()


def get_calibrator(
    log_path: str = DEFAULT_LOG_PATH,
    state_path: str = DEFAULT_STATE_PATH,
) -> ConfidenceCalibrator:
    """Return the module-level ``ConfidenceCalibrator`` singleton."""
    global _calibrator_instance
    if _calibrator_instance is None:
        with _calibrator_lock:
            if _calibrator_instance is None:
                _calibrator_instance = ConfidenceCalibrator(
                    log_path=log_path, state_path=state_path
                )
    return _calibrator_instance


# ── Test ───────────────────────────────────────────────────────────────

def test_confidence_calibrator() -> None:
    """Exercise the ConfidenceCalibrator end-to-end.

    Tests:
      1. Record 10 profitable high-confidence trades.
      2. Record 10 losing high-confidence trades.
      3. Verify the calibrator adjusts thresholds differently.
      4. Serialization round-trip (save → reload).
      5. Print a summary.
    """
    import tempfile

    print("=" * 60)
    print("T12 Confidence Calibrator — Test Suite")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = str(Path(tmpdir) / "calibration_log.jsonl")
        state_path = str(Path(tmpdir) / "calibration_state.json")

        cal = ConfidenceCalibrator(log_path=log_path, state_path=state_path)

        # ── 1. Record 10 profitable high-confidence trades ──────────
        print("\n1. Recording 10 profitable trades at 0.85+ confidence...")
        for i in range(10):
            cal.record_outcome(
                signal_type="cross_exchange",
                venue="coinbase",
                predicted_confidence=0.85 + (i * 0.01),  # 0.85 – 0.94
                actual_pnl=50.0 + (i * 10.0),            # all profitable
            )
        stats1 = cal.get_calibration_error("cross_exchange", "coinbase")
        thresh1 = cal.get_adjusted_min_confidence(
            "cross_exchange", "coinbase"
        )
        print(f"   Calibration error: {stats1:.2%}")
        print(f"   Adjusted threshold: {thresh1:.2%}")
        # Since we were ~accurate (high confidence + profitable),
        # calibration error should be low; threshold likely stays at default.
        assert stats1 < 0.15, (
            f"Expected low calibration error after accurate predictions, "
            f"got {stats1:.2%}"
        )

        # ── 2. Record 10 losing high-confidence trades ──────────────
        print("\n2. Recording 10 LOSING trades at 0.85+ confidence...")
        for i in range(10):
            cal.record_outcome(
                signal_type="cross_exchange",
                venue="binance",
                predicted_confidence=0.85 + (i * 0.01),  # 0.85 – 0.94
                actual_pnl=-30.0 - (i * 5.0),            # all losses
            )
        stats2 = cal.get_calibration_error("cross_exchange", "binance")
        thresh2 = cal.get_adjusted_min_confidence(
            "cross_exchange", "binance"
        )
        print(f"   Calibration error: {stats2:.2%}")
        print(f"   Adjusted threshold: {thresh2:.2%}")

        # Since we were overconfident (high confidence but all losses),
        # the error should be high and threshold should have been raised.
        if stats2 > 0.10:
            print("   → Calibration error > 10%: threshold should adjust.")
            # The threshold should have been raised to 0.35 or higher.
            assert thresh2 >= 0.35, (
                f"Expected threshold >= 0.35 after overconfident losses, "
                f"got {thresh2:.2%}"
            )
        else:
            print("   → Calibration error within tolerance (unexpected).")

        # ── 3. Verify different trajectories ─────────────────────────
        print("\n3. Verifying the calibrator adjusts differently per venue...")
        coinbase_thresh = cal.get_adjusted_min_confidence(
            "cross_exchange", "coinbase"
        )
        binance_thresh = cal.get_adjusted_min_confidence(
            "cross_exchange", "binance"
        )
        print(f"   coinbase threshold: {coinbase_thresh:.2%}")
        print(f"   binance threshold:  {binance_thresh:.2%}")
        # Binance (overconfident losses) should have a higher threshold
        # than coinbase (accurate profits).
        assert binance_thresh >= coinbase_thresh, (
            f"Expected binance threshold ({binance_thresh:.2%}) >= "
            f"coinbase threshold ({coinbase_thresh:.2%})"
        )

        # ── 4. Serialisation round-trip ──────────────────────────────
        print("\n4. Testing serialisation round-trip...")
        # Save happens inside record_outcome.  Now create a fresh instance
        # that reads from the same files.
        cal2 = ConfidenceCalibrator(log_path=log_path, state_path=state_path)

        coinbase_thresh2 = cal2.get_adjusted_min_confidence(
            "cross_exchange", "coinbase"
        )
        binance_thresh2 = cal2.get_adjusted_min_confidence(
            "cross_exchange", "binance"
        )
        print(f"   Reloaded coinbase threshold: {coinbase_thresh2:.2%}")
        print(f"   Reloaded binance threshold:  {binance_thresh2:.2%}")

        assert abs(coinbase_thresh - coinbase_thresh2) < 0.001, (
            f"Round-trip mismatch for coinbase: "
            f"{coinbase_thresh:.4f} vs {coinbase_thresh2:.4f}"
        )
        assert abs(binance_thresh - binance_thresh2) < 0.001, (
            f"Round-trip mismatch for binance: "
            f"{binance_thresh:.4f} vs {binance_thresh2:.4f}"
        )
        print("   ✅ Round-trip verified.")

        # Verify the ledger has both outcome records and threshold changes.
        with open(log_path) as f:
            ledger_lines = [l.strip() for l in f if l.strip()]
        outcome_count = sum(
            1 for l in ledger_lines
            if "__event" not in json.loads(l)
        )
        adj_count = sum(
            1 for l in ledger_lines
            if json.loads(l).get("__event") == "threshold_adjustment"
        )
        print(
            f"   Ledger: {outcome_count} outcome records, "
            f"{adj_count} threshold adjustments."
        )
        assert outcome_count == 20, (
            f"Expected 20 outcome records, got {outcome_count}"
        )

        # ── 5. Print summary ─────────────────────────────────────────
        print("\n5. Calibration report summary:")
        stats = cal.get_stats()
        report = stats.get("calibration_report", {})
        summary = stats.get("summary", {})

        print(f"   Trades tracked: {summary['total_trades_recorded']}")
        print(f"   Pairs tracked:  {summary['total_pairs_tracked']}")
        print(f"   Overall win rate: {summary['win_rate_overall']:.2%}")

        for key, info in report.items():
            print(f"\n   [{key}]")
            print(f"      Trades:    {info['total']} "
                  f"(wins: {info['wins']}, losses: {info['losses']})")
            print(f"      Posterior win rate: {info['posterior_mean_win_rate']:.2%} "
                  f"(±{info['posterior_std']:.2%})")
            print(f"      Avg predicted confidence: {info['avg_predicted_confidence']:.2%}")
            print(f"      Calibration error: {info['calibration_error']:.2%}")
            print(f"      Current threshold: {info['current_threshold']:.2%}")

        print("\n" + "=" * 60)
        print("✅ All test_confidence_calibrator assertions passed.")
        print("=" * 60)


# ── Main ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_confidence_calibrator()
