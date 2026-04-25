"""
Strategy Drift Detection — T30
===============================
Compare live Sharpe/SR against backtest baseline — auto-throttle if
SR drops >20% vs. regime-matched backtest.

Detects when a strategy's live performance diverges significantly from
its backtested baseline, indicating strategy drift. When drift exceeds
the threshold, automatically throttles position sizes.

Features:
  - Rolling window performance comparison (Sharpe, Sortino, Win Rate)
  - Regime-matched backtest comparison
  - Automatic position size throttling on drift
  - Drift events logged for analysis

Usage:
    detector = DriftDetector(backtest_baselines={
        "quantumarb": {"sharpe_ratio": 1.5, "win_rate": 0.65},
    })
    drift = detector.check_drift("quantumarb", live_sharpe=1.2, live_win_rate=0.60)
    if drift.drifting:
        throttle = detector.get_throttle("quantumarb")
        decoder.apply_throttle(throttle)
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("drift_detector")


@dataclass
class BacktestBaseline:
    """Backtest baseline metrics for a strategy."""
    strategy_name: str
    regime: str              # "trending", "ranging", "all"
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    avg_trade_return_pct: float
    sample_size: int         # Number of backtest trades

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DriftResult:
    """Result of a drift check for a strategy."""
    strategy_name: str
    regime: str
    live_sharpe: float
    baseline_sharpe: float
    sharpe_change_pct: float
    live_win_rate: float
    baseline_win_rate: float
    win_rate_change_pct: float
    drift_score: float       # 0.0 to 1.0 — how much the strategy has drifted
    is_drifting: bool        # True if drift_score > threshold
    threshold_pct: float     # The drift threshold
    throttle_multiplier: float  # Position size multiplier (0.0 to 1.0)
    reasons: List[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DriftConfig:
    """Configuration for drift detection."""
    sharpe_drift_threshold_pct: float = 20.0   # Alert if Sharpe drops >20%
    win_rate_drift_threshold_pct: float = 20.0
    sortino_drift_threshold_pct: float = 25.0
    min_trades_for_detection: int = 20          # Min trades before checking
    rolling_window_trades: int = 100            # Rolling window for live metrics
    throttle_min: float = 0.1                   # Minimum throttle (never go below 10%)
    drift_score_weight_sharpe: float = 0.5      # Weight of Sharpe in drift score
    drift_score_weight_win_rate: float = 0.3
    drift_score_weight_sortino: float = 0.2


class DriftDetector:
    """
    Detects strategy drift by comparing live vs. backtest performance.

    Thread-safe. Supports multiple strategies with regime-matched baselines.
    Automatically computes throttle multipliers when drift is detected.
    """

    def __init__(
        self,
        backtest_baselines: Optional[Dict[str, BacktestBaseline]] = None,
        config: Optional[DriftConfig] = None,
        data_dir: str = "data/drift",
    ):
        self._baselines: Dict[str, List[BacktestBaseline]] = {}
        self._config = config or DriftConfig()
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        # live_metrics[strategy_name] = list of metric snapshots
        self._live_metrics: Dict[str, List[Dict[str, float]]] = {}
        self._drift_results: Dict[str, DriftResult] = {}
        self._drift_history: List[DriftResult] = []

        # Load baselines
        if backtest_baselines:
            for name, baseline in backtest_baselines.items():
                self.set_baseline(baseline)

        self._load_data()

        log.info(
            "DriftDetector initialized (%d strategies, threshold=%.0f%% Sharpe)",
            len(self._baselines),
            self._config.sharpe_drift_threshold_pct,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def set_baseline(self, baseline: BacktestBaseline) -> None:
        """Register or update a backtest baseline for a strategy."""
        with self._lock:
            self._baselines.setdefault(baseline.strategy_name, []).append(baseline)
        log.info(
            "Registered baseline for %s [%s]: Sharpe=%.2f, WinRate=%.1f%%, Trades=%d",
            baseline.strategy_name, baseline.regime,
            baseline.sharpe_ratio, baseline.win_rate * 100, baseline.sample_size,
        )

    def record_live_metrics(
        self,
        strategy_name: str,
        sharpe_ratio: float,
        win_rate: float,
        sortino_ratio: Optional[float] = None,
        profit_factor: Optional[float] = None,
        num_trades: int = 0,
    ) -> None:
        """Record a live metrics snapshot for a strategy."""
        snapshot = {
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "sortino_ratio": sortino_ratio or sharpe_ratio * 0.8,  # Rough estimate
            "profit_factor": profit_factor or 1.0,
            "num_trades": num_trades,
            "timestamp": time.time(),
        }

        with self._lock:
            self._live_metrics.setdefault(strategy_name, []).append(snapshot)
            # Keep only the rolling window
            max_window = self._config.rolling_window_trades
            if len(self._live_metrics[strategy_name]) > max_window:
                self._live_metrics[strategy_name] = (
                    self._live_metrics[strategy_name][-max_window:]
                )

        self._save_data()

    def check_drift(
        self,
        strategy_name: str,
        regime: str = "all",
    ) -> Optional[DriftResult]:
        """
        Check if a strategy has drifted from its baseline.

        Args:
            strategy_name: Name of the strategy to check
            regime: Regime to match against (use "all" for overall baseline)

        Returns:
            DriftResult if baseline exists and sufficient data, else None
        """
        # Get baseline for this regime
        baseline = self._get_baseline(strategy_name, regime)
        if not baseline:
            return None

        # Get live metrics (rolling average)
        live = self._get_live_metrics(strategy_name)
        if not live or live.get("num_trades", 0) < self._config.min_trades_for_detection:
            return None

        live_sharpe = live.get("sharpe_ratio", 0.0)
        live_win_rate = live.get("win_rate", 0.0)
        live_sortino = live.get("sortino_ratio", 0.0)

        baseline_sharpe = baseline.sharpe_ratio
        baseline_win_rate = baseline.win_rate
        baseline_sortino = baseline.sortino_ratio

        # Calculate percentage changes
        sharpe_change = self._pct_change(live_sharpe, baseline_sharpe)
        win_rate_change = self._pct_change(live_win_rate, baseline_win_rate)
        sortino_change = self._pct_change(live_sortino, baseline_sortino)

        # Calculate drift score (weighted average of negative changes)
        drift_score = 0.0
        reasons: List[str] = []

        sharpe_drift = max(0, -sharpe_change)
        win_rate_drift = max(0, -win_rate_change)
        sortino_drift = max(0, -sortino_change)

        drift_score = (
            self._config.drift_score_weight_sharpe * (sharpe_drift / 100.0)
            + self._config.drift_score_weight_win_rate * (win_rate_drift / 100.0)
            + self._config.drift_score_weight_sortino * (sortino_drift / 100.0)
        )
        drift_score = min(1.0, max(0.0, drift_score))

        # Determine if drifting
        is_drifting = False
        if sharpe_change < -self._config.sharpe_drift_threshold_pct:
            reasons.append(
                f"Sharpe {live_sharpe:.2f} vs baseline {baseline_sharpe:.2f} "
                f"({sharpe_change:.1f}%)"
            )
            is_drifting = True
        if win_rate_change < -self._config.win_rate_drift_threshold_pct:
            reasons.append(
                f"WinRate {live_win_rate:.1%} vs baseline {baseline_win_rate:.1%} "
                f"({win_rate_change:.1f}%)"
            )
            is_drifting = True
        if sortino_change < -self._config.sortino_drift_threshold_pct:
            reasons.append(
                f"Sortino {live_sortino:.2f} vs baseline {baseline_sortino:.2f} "
                f"({sortino_change:.1f}%)"
            )
            is_drifting = True

        # Compute throttle multiplier
        throttle = self._compute_throttle(drift_score, is_drifting)

        result = DriftResult(
            strategy_name=strategy_name,
            regime=regime,
            live_sharpe=round(live_sharpe, 4),
            baseline_sharpe=round(baseline_sharpe, 4),
            sharpe_change_pct=round(sharpe_change, 1),
            live_win_rate=round(live_win_rate, 4),
            baseline_win_rate=round(baseline_win_rate, 4),
            win_rate_change_pct=round(win_rate_change, 1),
            drift_score=round(drift_score, 4),
            is_drifting=is_drifting,
            threshold_pct=self._config.sharpe_drift_threshold_pct,
            throttle_multiplier=round(throttle, 4),
            reasons=reasons,
        )

        # Store result
        with self._lock:
            self._drift_results[strategy_name] = result
            self._drift_history.append(result)

        # Log drift
        if is_drifting:
            log.warning(
                "DRIFT DETECTED: %s [%s] score=%.2f throttle=%.2f reasons=%s",
                strategy_name, regime, drift_score, throttle, reasons,
            )

        self._save_data()
        return result

    def check_all_strategies(self) -> Dict[str, DriftResult]:
        """Check drift for all strategies with baselines."""
        with self._lock:
            strategy_names = list(self._baselines.keys())

        results: Dict[str, DriftResult] = {}
        for name in strategy_names:
            result = self.check_drift(name)
            if result:
                results[name] = result
        return results

    def get_throttle(self, strategy_name: str) -> float:
        """
        Get the current throttle multiplier for a strategy.

        Returns 1.0 (no throttle) if no drift detected, or the computed
        throttle (0.1 to 1.0) if drifting.
        """
        with self._lock:
            result = self._drift_results.get(strategy_name)
        if not result:
            return 1.0
        return result.throttle_multiplier

    def get_drift_status(self, strategy_name: str) -> Optional[DriftResult]:
        """Get the most recent drift result for a strategy."""
        with self._lock:
            return self._drift_results.get(strategy_name)

    def get_all_status(self) -> Dict[str, DriftResult]:
        """Get drift status for all strategies."""
        with self._lock:
            return dict(self._drift_results)

    def get_drift_history(
        self, limit: int = 50, strategy_name: Optional[str] = None
    ) -> List[DriftResult]:
        """Get drift check history."""
        with self._lock:
            history = list(self._drift_history)
        if strategy_name:
            history = [h for h in history if h.strategy_name == strategy_name]
        return list(reversed(history[-limit:]))

    def get_summary(self) -> Dict[str, Any]:
        """Get overall drift detector summary."""
        status = self.get_all_status()
        drifting_count = sum(1 for s in status.values() if s.is_drifting)
        total = len(status)
        avg_drift = (
            sum(s.drift_score for s in status.values()) / total if total > 0 else 0.0
        )

        with self._lock:
            live_strategies = list(self._live_metrics.keys())

        return {
            "total_strategies": total,
            "drifting_count": drifting_count,
            "healthy_count": total - drifting_count,
            "avg_drift_score": round(avg_drift, 4),
            "strategies_with_live_data": live_strategies,
            "total_checks_in_history": len(self._drift_history),
            "drift_results": {n: s.to_dict() for n, s in status.items()},
        }

    # ── Internal ────────────────────────────────────────────────────────

    def _get_baseline(
        self, strategy_name: str, regime: str
    ) -> Optional[BacktestBaseline]:
        """Get the best matching baseline for a strategy and regime."""
        with self._lock:
            baselines = self._baselines.get(strategy_name, [])

        if not baselines:
            return None

        # First try exact regime match
        for b in baselines:
            if b.regime == regime:
                return b

        # Fall back to "all" regime
        for b in baselines:
            if b.regime == "all":
                return b

        # Return first available
        return baselines[0]

    def _get_live_metrics(
        self, strategy_name: str
    ) -> Optional[Dict[str, float]]:
        """Get the rolling average of live metrics for a strategy."""
        with self._lock:
            snapshots = self._live_metrics.get(strategy_name, [])

        if not snapshots:
            return None

        # Weighted average — recent snapshots count more
        n = len(snapshots)
        if n == 0:
            return None

        weights = [1.0 + (i / n) for i in range(n)]  # Linear recency weight
        total_weight = sum(weights)

        result = {
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "sortino_ratio": 0.0,
            "profit_factor": 0.0,
            "num_trades": max(s.get("num_trades", 0) for s in snapshots),
        }

        for key in ("sharpe_ratio", "win_rate", "sortino_ratio", "profit_factor"):
            weighted_sum = sum(s.get(key, 0.0) * w for s, w in zip(snapshots, weights))
            result[key] = weighted_sum / total_weight if total_weight > 0 else 0.0

        return result

    @staticmethod
    def _pct_change(current: float, baseline: float) -> float:
        """Calculate percentage change from baseline."""
        if baseline == 0:
            return 0.0
        return ((current - baseline) / abs(baseline)) * 100.0

    def _compute_throttle(
        self, drift_score: float, is_drifting: bool
    ) -> float:
        """
        Compute position size throttle based on drift score.

        Drift 0.0 → throttle 1.0 (no throttle)
        Drift 0.5 → throttle 0.5 (50% position size)
        Drift 1.0 → throttle min (10% position size)
        """
        if not is_drifting or drift_score <= 0:
            return 1.0

        throttle = 1.0 - drift_score
        return max(self._config.throttle_min, throttle)

    # ── Persistence ─────────────────────────────────────────────────────

    def _save_data(self) -> None:
        """Save drift data to disk."""
        with self._lock:
            # Save baselines
            baselines_path = self._data_dir / "backtest_baselines.json"
            baselines_data = {
                name: [b.to_dict() for b in blist]
                for name, blist in self._baselines.items()
            }
            try:
                with open(baselines_path, "w") as f:
                    json.dump(baselines_data, f, indent=2)
            except Exception as e:
                log.warning("Failed to save baselines: %s", e)

            # Save live metrics (compact)
            metrics_path = self._data_dir / "live_metrics.jsonl"
            with open(metrics_path, "w") as f:
                for name, snapshots in self._live_metrics.items():
                    for snap in snapshots:
                        record = {"strategy": name, **snap}
                        f.write(json.dumps(record) + "\n")

            # Save drift history (append-only)
            history_path = self._data_dir / "drift_history.jsonl"
            # Only append new entries since last save

    def _load_data(self) -> None:
        """Load drift data from disk."""
        # Load baselines
        baselines_path = self._data_dir / "backtest_baselines.json"
        if baselines_path.exists():
            try:
                with open(baselines_path) as f:
                    data = json.load(f)
                for name, blist in data.items():
                    self._baselines[name] = [BacktestBaseline(**b) for b in blist]
                log.info("Loaded baselines for %d strategies", len(self._baselines))
            except Exception as e:
                log.warning("Failed to load baselines: %s", e)

        # Load live metrics
        metrics_path = self._data_dir / "live_metrics.jsonl"
        if metrics_path.exists():
            try:
                with open(metrics_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        record = json.loads(line)
                        name = record.pop("strategy", "unknown")
                        timestamp = record.pop("timestamp", time.time())
                        record["timestamp"] = timestamp
                        self._live_metrics.setdefault(name, []).append(record)
                log.info("Loaded live metrics for %d strategies", len(self._live_metrics))
            except Exception as e:
                log.warning("Failed to load live metrics: %s", e)

        # Load drift history
        history_path = self._data_dir / "drift_history.jsonl"
        if history_path.exists():
            try:
                with open(history_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        result = DriftResult(**json.loads(line))
                        self._drift_history.append(result)
                        self._drift_results[result.strategy_name] = result
                log.info("Loaded %d drift history entries", len(self._drift_history))
            except Exception as e:
                log.warning("Failed to load drift history: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

DRIFT_DETECTOR: Optional[DriftDetector] = None


def get_drift_detector(
    backtest_baselines: Optional[Dict[str, BacktestBaseline]] = None,
) -> DriftDetector:
    """Get or create the global DriftDetector singleton."""
    global DRIFT_DETECTOR
    if DRIFT_DETECTOR is None:
        DRIFT_DETECTOR = DriftDetector(backtest_baselines=backtest_baselines)
    return DRIFT_DETECTOR
