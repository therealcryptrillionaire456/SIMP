"""
Tranche 12 — Confidence Calibration & Learning from Decisions
SIMP QuantumArb system.

Tracks prediction accuracy per signal type, computes calibration error,
and auto-adjusts confidence thresholds based on historical performance.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────
MAX_ENTRIES: int = 200
DEFAULT_LOG_PATH: str = "data/calibration_log.jsonl"
VALID_SIGNAL_TYPES: tuple = (
    "cross_exchange",
    "triangular",
    "Solana_dex",
    "staking",
    "meme",
)


# ── Data Classes ───────────────────────────────────────────────────────

@dataclass
class CalibrationEntry:
    """A single calibration data point — a prediction vs. actual outcome."""

    signal_id: str
    signal_type: str  # one of VALID_SIGNAL_TYPES
    predicted_confidence: float  # 0.0 – 1.0
    actual_pnl_usd: float
    outcome_binary: bool  # True if pnl > 0
    expected_return_pct: float
    timestamp: str  # ISO8601 UTC


# ── Calibrator ─────────────────────────────────────────────────────────

class ConfidenceCalibrator:
    """Tracks prediction accuracy per signal type and adjusts thresholds.

    Thread-safe via ``self._lock``.  Data is persisted to an append-only
    JSONL ledger at ``log_path``.  The last *MAX_ENTRIES* records are kept
    in memory for fast calibration computation.
    """

    def __init__(self, log_path: str = DEFAULT_LOG_PATH) -> None:
        self._lock = threading.Lock()
        self.log_path = Path(log_path)
        self._entries: List[CalibrationEntry] = []

        # Ensure parent directory exists.
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Replay existing ledger into memory on startup.
        self._replay_ledger()

    # ── Public API ─────────────────────────────────────────────────────

    def record_outcome(
        self,
        signal_id: str,
        signal_type: str,
        predicted_confidence: float,
        actual_pnl_usd: float,
        expected_return_pct: float = 0.0,
    ) -> None:
        """Record a prediction vs. actual outcome.

        Parameters
        ----------
        signal_id : str
            Unique identifier for the signal / trade.
        signal_type : str
            Must be one of ``VALID_SIGNAL_TYPES``.
        predicted_confidence : float
            Confidence at decision time, in [0.0, 1.0].
        actual_pnl_usd : float
            Realised PnL in USD (positive = win).
        expected_return_pct : float
            Expected return percentage at decision time.
        """
        if signal_type not in VALID_SIGNAL_TYPES:
            logger.warning(
                "Unknown signal_type %r; valid types are %s",
                signal_type,
                VALID_SIGNAL_TYPES,
            )

        predicted_confidence = max(0.0, min(1.0, predicted_confidence))
        outcome_binary = actual_pnl_usd > 0.0

        entry = CalibrationEntry(
            signal_id=signal_id,
            signal_type=signal_type,
            predicted_confidence=predicted_confidence,
            actual_pnl_usd=actual_pnl_usd,
            outcome_binary=outcome_binary,
            expected_return_pct=expected_return_pct,
            timestamp=_now_iso(),
        )

        with self._lock:
            self._append_log(entry)
            self._entries.append(entry)
            # Keep only the last N entries.
            if len(self._entries) > MAX_ENTRIES:
                self._entries = self._entries[-MAX_ENTRIES:]

    def get_calibration(self, signal_type: str) -> Dict:
        """Get calibration statistics for a given signal type.

        Returns a dictionary with keys:
            total, wins, win_rate, avg_confidence, calibration_error, avg_pnl
        """
        with self._lock:
            filtered = [e for e in self._entries if e.signal_type == signal_type]

        total = len(filtered)
        if total == 0:
            return {
                "signal_type": signal_type,
                "total": 0,
                "wins": 0,
                "win_rate": 0.0,
                "avg_confidence": 0.0,
                "calibration_error": 0.0,
                "avg_pnl": 0.0,
            }

        wins = sum(1 for e in filtered if e.outcome_binary)
        win_rate = wins / total
        avg_conf = statistics.mean(e.predicted_confidence for e in filtered)
        avg_pnl = statistics.mean(e.actual_pnl_usd for e in filtered)

        return {
            "signal_type": signal_type,
            "total": total,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "avg_confidence": round(avg_conf, 4),
            "calibration_error": round(abs(win_rate - avg_conf), 4),
            "avg_pnl": round(avg_pnl, 4),
        }

    def compute_calibration_error(self, signal_type: str) -> float:
        """|win_rate - avg_confidence| — values closer to 0 are better."""
        stats = self.get_calibration(signal_type)
        return stats["calibration_error"]

    def get_adjusted_confidence(
        self, raw_confidence: float, signal_type: str
    ) -> float:
        """Apply calibration adjustment to a raw confidence score.

        If the system has been *overconfident* (avg_confidence > win_rate),
        the adjustment reduces the score.  If *underconfident* it boosts it.

        The adjustment is proportional to the calibration error but capped at
        ±20 % points.
        """
        raw_confidence = max(0.0, min(1.0, raw_confidence))
        stats = self.get_calibration(signal_type)

        if stats["total"] < 3:
            return raw_confidence  # not enough data to calibrate

        avg_conf = stats["avg_confidence"]
        win_rate = stats["win_rate"]
        error = abs(win_rate - avg_conf)

        # Limit the adjustment magnitude.
        adjustment = min(error, 0.20)
        if avg_conf > win_rate:
            adjusted = raw_confidence - adjustment
        else:
            adjusted = raw_confidence + adjustment

        return max(0.0, min(1.0, round(adjusted, 4)))

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get calibration statistics for every encountered signal type."""
        with self._lock:
            types_seen = set(e.signal_type for e in self._entries)

        result: Dict[str, Dict] = {}
        for st in sorted(types_seen):
            result[st] = self.get_calibration(st)
        return result

    def get_recommended_threshold(self, signal_type: str) -> float:
        """Auto-recommend a minimum-confidence threshold based on calibration.

        Heuristic
        ---------
        If calibration_error > 0.10, adjust default (0.5) by 5 %-points in the
        direction that would improve conservatism (raise if overconfident,
        lower if underconfident).  Result is clamped to [0.1, 0.9].
        """
        stats = self.get_calibration(signal_type)

        if stats["total"] < 5:
            return 0.5  # default / not enough data

        base = 0.5
        error = stats["calibration_error"]

        if error <= 0.10:
            return base

        avg_conf = stats["avg_confidence"]
        win_rate = stats["win_rate"]

        # Overconfident: raise the threshold to be more selective.
        if avg_conf > win_rate:
            base += 0.05
        else:
            base -= 0.05

        return max(0.1, min(0.9, round(base, 2)))

    def reset(self) -> None:
        """Clear all in-memory calibration data.

        .. warning::
            This does **not** delete the append-only ledger on disk.
            The next ``__init__`` or replay would re-load old entries.
        """
        with self._lock:
            self._entries.clear()
        logger.info("ConfidenceCalibrator reset (in-memory entries cleared).")

    # ── Internal Helpers ──────────────────────────────────────────────

    def _append_log(self, entry: CalibrationEntry) -> None:
        """Append one entry to the JSONL ledger (no lock — caller holds it)."""
        with open(self.log_path, "a") as f:
            f.write(json.dumps(asdict(entry), sort_keys=True) + "\n")

    def _replay_ledger(self) -> None:
        """Replay the last *MAX_ENTRIES* from the existing JSONL file."""
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "r") as f:
                lines = f.readlines()
            for line in lines[-MAX_ENTRIES:]:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                self._entries.append(CalibrationEntry(**data))
        except Exception as exc:
            logger.warning("Failed to replay calibration ledger: %s", exc)


# ── Helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Standalone Test ────────────────────────────────────────────────────

def test_confidence_calibrator() -> None:
    """Exercise every public method of ``ConfidenceCalibrator``."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = str(Path(tmpdir) / "calibration_log.jsonl")
        cal = ConfidenceCalibrator(log_path)

        # 1. record_outcome — basic recording
        cal.record_outcome("sig-001", "cross_exchange", 0.85, 120.0, 2.5)
        cal.record_outcome("sig-002", "cross_exchange", 0.92, -30.0, 3.0)
        cal.record_outcome("sig-003", "triangular", 0.65, 50.0, 1.2)
        cal.record_outcome("sig-004", "cross_exchange", 0.78, 200.0, 1.8)
        cal.record_outcome("sig-005", "cross_exchange", 0.88, -10.0, 2.0)
        cal.record_outcome("sig-006", "Solana_dex", 0.55, 15.0, 0.9)

        # 2. get_calibration
        stats = cal.get_calibration("cross_exchange")
        assert stats["total"] == 4, f"Expected 4, got {stats['total']}"
        assert stats["wins"] == 2, f"Expected 2 wins, got {stats['wins']}"
        assert stats["win_rate"] == 0.5, f"Expected 0.5, got {stats['win_rate']}"
        expected_avg_conf = round((0.85 + 0.92 + 0.78 + 0.88) / 4, 4)
        assert stats["avg_confidence"] == expected_avg_conf, (
            f"Expected {expected_avg_conf}, got {stats['avg_confidence']}"
        )
        expected_cal_err = round(abs(0.5 - expected_avg_conf), 4)
        assert stats["calibration_error"] == expected_cal_err, (
            f"Expected {expected_cal_err}, got {stats['calibration_error']}"
        )

        # 3. compute_calibration_error
        err = cal.compute_calibration_error("cross_exchange")
        assert err == expected_cal_err

        # 4. get_adjusted_confidence
        adj = cal.get_adjusted_confidence(0.90, "cross_exchange")
        # avg_conf (0.8575) > win_rate (0.5) => overconfident => reduce
        assert adj < 0.90, f"Expected adjusted < 0.90, got {adj}"
        assert 0.0 <= adj <= 1.0

        # Not enough data for Solana_dex (< 3) => raw returned.
        adj_low = cal.get_adjusted_confidence(0.70, "Solana_dex")
        assert adj_low == 0.70, f"Expected 0.70 (raw), got {adj_low}"

        # 5. get_all_stats
        all_stats = cal.get_all_stats()
        assert "cross_exchange" in all_stats
        assert "triangular" in all_stats
        assert "Solana_dex" in all_stats
        assert "meme" not in all_stats  # no entries recorded

        # 6. get_recommended_threshold
        # Only 4 entries of cross_exchange => total < 5 => returns default 0.5
        thresh = cal.get_recommended_threshold("cross_exchange")
        assert thresh == 0.5, f"Expected 0.5 (<5 entries), got {thresh}"

        # Add a 5th entry so calibration kicks in.
        cal.record_outcome("sig-006b", "cross_exchange", 0.72, 60.0, 1.5)
        thresh = cal.get_recommended_threshold("cross_exchange")
        # error = 0.3575 > 0.10, overconfident => base + 0.05 = 0.55
        expected_thresh = 0.55
        assert thresh == expected_thresh, f"Expected {expected_thresh}, got {thresh}"

        thresh_low = cal.get_recommended_threshold("Solana_dex")
        # only 1 entry => total < 5 => default 0.5
        assert thresh_low == 0.5

        thresh_default = cal.get_recommended_threshold("meme")
        assert thresh_default == 0.5

        # 7. reset
        cal.reset()
        assert len(cal._entries) == 0
        assert cal.get_calibration("cross_exchange")["total"] == 0

        # 8. Edge cases — boundary values
        cal.record_outcome("sig-007", "cross_exchange", 1.0, 100.0, 5.0)
        cal.record_outcome("sig-008", "cross_exchange", 1.5, -50.0, 3.0)  # clamped
        assert cal._entries[-1].predicted_confidence == 1.0

        cal.record_outcome("sig-009", "cross_exchange", -0.3, 75.0, 2.0)  # clamped
        assert cal._entries[-1].predicted_confidence == 0.0

        # 9. Unknown signal type — warning only, allowed.
        cal.record_outcome("sig-010", "unknown_type", 0.5, 10.0, 0.5)
        stats_unknown = cal.get_calibration("unknown_type")
        assert stats_unknown["total"] == 1

        print("All test_confidence_calibrator assertions passed ✓")


# ── Main (execute test when run directly) ──────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_confidence_calibrator()
    print("confidence_calibrator.py — all tests passed.")
