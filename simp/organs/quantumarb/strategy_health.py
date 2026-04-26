"""
Strategy Health Scorecard — T31.3
====================================
Composite health score per strategy combining:
  - Sharpe ratio (30d trailing)
  - Win rate (30d trailing)
  - Max drawdown (30d)
  - Signal freshness
  - Trade frequency vs target
  - Slippage efficiency (expected vs realized spread)

Produces a 0.0–1.0 score per strategy and an overall system health score.
Updates every 30s via the dashboard polling loop.

Connects to:
  - PNLLedger for P&L data
  - LatencyProfiler for signal freshness
  - RiskReporter for drawdown/Sharpe
  - StrategySwitcher for current strategy mode
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

log = logging.getLogger("strategy_health")

# Type flag for deferred imports
PNL_LEDGER_AVAILABLE: bool = True
RISK_REPORTER_AVAILABLE: bool = True
STRATEGY_SWITCHER_AVAILABLE: bool = True
ALERTER_AVAILABLE: bool = True


@dataclass
class HealthScore:
    """Health score for a single strategy."""
    strategy_name: str
    sharpe_score: float           # 0.0–1.0 based on Sharpe ratio
    win_rate_score: float         # 0.0–1.0 based on win rate
    drawdown_score: float         # 0.0–1.0 based on max drawdown
    signal_freshness_score: float # 0.0–1.0 based on signal age
    frequency_score: float        # 0.0–1.0 based on trade cadence
    slippage_score: float         # 0.0–1.0 based on slippage efficiency
    composite_score: float        # Weighted average (0.0–1.0)
    status: str                   # "healthy", "degraded", "critical"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemHealthSummary:
    """Overall system health summary."""
    overall_score: float
    strategy_scores: Dict[str, HealthScore]
    healthy_count: int
    degraded_count: int
    critical_count: int
    total_strategies: int
    current_mode: str
    timestamp: str
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 4),
            "strategy_scores": {
                k: v.to_dict() for k, v in self.strategy_scores.items()
            },
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "critical_count": self.critical_count,
            "total_strategies": self.total_strategies,
            "current_mode": self.current_mode,
            "timestamp": self.timestamp,
            "alerts": self.alerts,
        }


class StrategyHealthMonitor:
    """
    Computes and caches strategy health scores.

    Thread-safe. Produces a composite score per strategy every evaluation
    cycle. Caches the last report for dashboard polling.

    Default weights for composite score:
      - Sharpe:         0.25
      - Win rate:       0.20
      - Drawdown:       0.20
      - Freshness:      0.15
      - Frequency:      0.10
      - Slippage:       0.10
    """

    WEIGHTS: Dict[str, float] = {
        "sharpe": 0.25,
        "win_rate": 0.20,
        "drawdown": 0.20,
        "freshness": 0.15,
        "frequency": 0.10,
        "slippage": 0.10,
    }

    # Score thresholds
    SHARPE_TARGET = 2.0          # Sharpe ≥ 2.0 → score=1.0; ≤ 0 → score=0.0
    WIN_RATE_TARGET = 0.65       # Win rate ≥ 65% → score=1.0
    DRAWDOWN_MAX = 0.15          # Drawdown ≤ 5% → score=1.0; ≥ 15% → score=0.0
    SIGNAL_MAX_AGE_S = 60.0      # Signal ≤ 10s → score=1.0; ≥ 60s → score=0.0
    SLIPPAGE_TOLERANCE = 2.0     # Slippage ≤ 0.5× target → score=1.0; ≥ 2× → score=0.0

    def __init__(
        self,
        pnl_ledger=None,
        risk_reporter=None,
        latency_profiler=None,
        strategy_switcher=None,
        cache_ttl: float = 10.0,
    ):
        self._pnl_ledger = pnl_ledger
        self._risk_reporter = risk_reporter
        self._latency_profiler = latency_profiler
        self._strategy_switcher = strategy_switcher

        self._lock = threading.Lock()
        self._cache_ttl = cache_ttl
        self._cached_summary: Optional[SystemHealthSummary] = None
        self._last_evaluation: float = 0.0
        self._evaluation_count: int = 0

        # Lazy-load dependencies if not provided
        self._init_dependencies()

        log.info("StrategyHealthMonitor initialized (cache_ttl=%.1fs)", cache_ttl)

    def _init_dependencies(self) -> None:
        """Lazy-import dependencies if not provided."""
        global PNL_LEDGER_AVAILABLE, RISK_REPORTER_AVAILABLE, STRATEGY_SWITCHER_AVAILABLE, ALERTER_AVAILABLE
        
        # T31.3/E2: Alerter import
        try:
            from .alerter import Alerter as _Alerter
            ALERTER_AVAILABLE = True
        except ImportError:
            ALERTER_AVAILABLE = False
        if self._pnl_ledger is None:
            try:
                from .pnl_ledger import PNLLedger
                self._pnl_ledger = PNLLedger()
                PNL_LEDGER_AVAILABLE = True
            except Exception as e:
                log.warning("PNLLedger not available: %s", e)
                PNL_LEDGER_AVAILABLE = False

        if self._risk_reporter is None:
            try:
                from .risk_reporter import RiskReporter
                self._risk_reporter = RiskReporter()
                RISK_REPORTER_AVAILABLE = True
            except Exception as e:
                log.warning("RiskReporter not available: %s", e)
                RISK_REPORTER_AVAILABLE = False

        if self._latency_profiler is None:
            try:
                from .latency_profiler import PROFILER
                self._latency_profiler = PROFILER
            except Exception:
                log.warning("LatencyProfiler not available")
        if self._strategy_switcher is None:
            try:
                from .strategy_switcher import get_strategy_switcher
                self._strategy_switcher = get_strategy_switcher()
                STRATEGY_SWITCHER_AVAILABLE = True
            except Exception as e:
                log.warning("StrategySwitcher not available: %s", e)
                STRATEGY_SWITCHER_AVAILABLE = False

    # ── Public API ──────────────────────────────────────────────────────

    def evaluate(self, force: bool = False) -> SystemHealthSummary:
        """
        Evaluate strategy health, using cache if TTL not expired.

        Args:
            force: If True, bypass cache and re-evaluate.

        Returns:
            SystemHealthSummary with per-strategy scores.
        """
        now = time.time()
        with self._lock:
            if (
                not force
                and self._cached_summary is not None
                and (now - self._last_evaluation) < self._cache_ttl
            ):
                return self._cached_summary

        # Perform evaluation
        summary = self._evaluate()
        self._evaluation_count += 1

        with self._lock:
            self._cached_summary = summary
            self._last_evaluation = now

        log.info(
            "Health evaluation #%d: overall=%.3f, healthy=%d, degraded=%d, critical=%d",
            self._evaluation_count,
            summary.overall_score,
            summary.healthy_count,
            summary.degraded_count,
            summary.critical_count,
        )
        return summary

    def get_cached_summary(self) -> Optional[SystemHealthSummary]:
        """Get the cached summary without triggering evaluation."""
        with self._lock:
            return self._cached_summary

    def get_evaluation_count(self) -> int:
        """Get total evaluations performed."""
        with self._lock:
            return self._evaluation_count

    # ── Core Evaluation ─────────────────────────────────────────────────

    def _evaluate(self) -> SystemHealthSummary:
        """Perform a full health evaluation."""
        strategies = self._collect_strategy_names()
        alerts: List[str] = []
        scores: Dict[str, HealthScore] = {}

        for strategy in strategies:
            score = self._score_strategy(strategy)
            scores[strategy] = score
            if score.status == "critical":
                alerts.append(
                    f"[CRITICAL] {strategy}: composite={score.composite_score:.3f} "
                    f"(Sharpe={score.sharpe_score:.2f}, drawdown={score.drawdown_score:.2f})"
                )
            elif score.status == "degraded":
                alerts.append(
                    f"[DEGRADED] {strategy}: composite={score.composite_score:.3f}"
                )

        healthy = sum(1 for s in scores.values() if s.status == "healthy")
        degraded = sum(1 for s in scores.values() if s.status == "degraded")
        critical = sum(1 for s in scores.values() if s.status == "critical")

        overall = (
            sum(s.composite_score for s in scores.values()) / len(scores)
            if scores else 0.0
        )

        current_mode = "unknown"
        if self._strategy_switcher is not None:
            try:
                status = self._strategy_switcher.get_status()
                current_mode = status.get("current_mode", "unknown")
            except Exception:
                pass

        # T31.3/E2: Dispatch alerts for critical/degraded strategies
        if ALERTER_AVAILABLE:
            try:
                from .alerter import Alerter
                alerter = Alerter()
                for strat_name, score in scores.items():
                    if score.status == "critical":
                        alerter.send_alert(
                            "strategy_health_critical",
                            "CRITICAL",
                            f"Strategy {strat_name} critical",
                            f"Composite={score.composite_score:.2f}",
                        )
                    elif score.status == "degraded":
                        alerter.send_alert(
                            "strategy_health_degraded",
                            "WARN",
                            f"Strategy {strat_name} degraded",
                            f"Composite={score.composite_score:.2f}",
                        )
            except Exception as e:
                log.warning("Failed to dispatch health alerts: %s", e)

        return SystemHealthSummary(
            overall_score=round(overall, 4),
            strategy_scores=scores,
            healthy_count=healthy,
            degraded_count=degraded,
            critical_count=critical,
            total_strategies=len(strategies),
            current_mode=current_mode,
            timestamp=datetime.now(timezone.utc).isoformat(),
            alerts=alerts,
        )

    def _collect_strategy_names(self) -> List[str]:
        """Collect all known strategy names."""
        strategies = []

        # From strategy switcher
        if self._strategy_switcher is not None:
            try:
                all_strategies = self._strategy_switcher.get_strategies()
                strategies.extend(list(all_strategies.keys()))
            except Exception:
                pass

        # Deduplicate
        seen: set = set()
        deduped = []
        for s in strategies:
            if s not in seen:
                seen.add(s)
                deduped.append(s)

        # Add generic fallback strategies if we have data
        if self._pnl_ledger is not None:
            try:
                trades = self._pnl_ledger.get_trade_history(limit=1)
                if trades:
                    # Extract unique symbols as pseudo-strategies
                    symbols = set()
                    if self._pnl_ledger.records:
                        for r in self._pnl_ledger.records[-100:]:
                            symbols.add(getattr(r, "symbol", "unknown"))
                    for s in symbols:
                        if s not in seen:
                            seen.add(s)
                            deduped.append(f"arb_{s}")
            except Exception:
                pass

        if not deduped:
            deduped = ["quantumarb_generic"]

        return deduped

    def _score_strategy(self, strategy_name: str) -> HealthScore:
        """Compute a composite health score for a single strategy."""
        # Gather raw metrics — each returns 0.0–1.0
        sharpe_score = self._score_sharpe(strategy_name)
        win_rate_score = self._score_win_rate(strategy_name)
        drawdown_score = self._score_drawdown(strategy_name)
        freshness_score = self._score_signal_freshness(strategy_name)
        frequency_score = self._score_trade_frequency(strategy_name)
        slippage_score = self._score_slippage(strategy_name)

        # Weighted composite
        composite = (
            self.WEIGHTS["sharpe"] * sharpe_score
            + self.WEIGHTS["win_rate"] * win_rate_score
            + self.WEIGHTS["drawdown"] * drawdown_score
            + self.WEIGHTS["freshness"] * freshness_score
            + self.WEIGHTS["frequency"] * frequency_score
            + self.WEIGHTS["slippage"] * slippage_score
        )

        # Determine status
        if composite >= 0.7:
            status = "healthy"
        elif composite >= 0.4:
            status = "degraded"
        else:
            status = "critical"

        details = {
            "raw_sharpe": self._get_raw_sharpe(strategy_name),
            "raw_win_rate": self._get_raw_win_rate(strategy_name),
            "raw_drawdown": self._get_raw_drawdown(strategy_name),
            "signal_freshness_s": self._get_signal_age(strategy_name),
            "trade_count_30d": self._get_trade_count_30d(strategy_name),
            "avg_slippage_bps": self._get_avg_slippage_bps(strategy_name),
        }

        return HealthScore(
            strategy_name=strategy_name,
            sharpe_score=round(sharpe_score, 4),
            win_rate_score=round(win_rate_score, 4),
            drawdown_score=round(drawdown_score, 4),
            signal_freshness_score=round(freshness_score, 4),
            frequency_score=round(frequency_score, 4),
            slippage_score=round(slippage_score, 4),
            composite_score=round(composite, 4),
            status=status,
            details=details,
        )

    # ── Individual Scoring Functions ────────────────────────────────────

    def _score_sharpe(self, _strategy: str) -> float:
        """Score Sharpe ratio: ≥ target → 1.0, ≤ 0 → 0.0, linear between."""
        sharpe = self._get_raw_sharpe(_strategy)
        if sharpe >= self.SHARPE_TARGET:
            return 1.0
        if sharpe <= 0:
            return 0.0
        return sharpe / self.SHARPE_TARGET

    def _score_win_rate(self, _strategy: str) -> float:
        """Score win rate: ≥ target → 1.0, ≤ 0 → 0.0, linear between."""
        wr = self._get_raw_win_rate(_strategy)
        if wr >= self.WIN_RATE_TARGET:
            return 1.0
        if wr <= 0:
            return 0.0
        return wr / self.WIN_RATE_TARGET

    def _score_drawdown(self, _strategy: str) -> float:
        """Score drawdown: ≤ 5% → 1.0, ≥ 15% → 0.0, linear between."""
        dd = self._get_raw_drawdown(_strategy)
        if dd <= 0.05:
            return 1.0
        if dd >= self.DRAWDOWN_MAX:
            return 0.0
        return 1.0 - (dd - 0.05) / (self.DRAWDOWN_MAX - 0.05)

    def _score_signal_freshness(self, _strategy: str) -> float:
        """Score signal freshness: ≤ 10s → 1.0, ≥ 60s → 0.0, linear between."""
        age = self._get_signal_age(_strategy)
        if age <= 10.0:
            return 1.0
        if age >= self.SIGNAL_MAX_AGE_S:
            return 0.0
        return 1.0 - (age - 10.0) / (self.SIGNAL_MAX_AGE_S - 10.0)

    def _score_trade_frequency(self, _strategy: str) -> float:
        """Score trade frequency relative to target for the current mode."""
        count_30d = self._get_trade_count_30d(_strategy)
        # Expect at least some trading activity
        if count_30d >= 30:
            return 1.0
        if count_30d <= 0:
            return 0.0
        return count_30d / 30.0

    def _score_slippage(self, _strategy: str) -> float:
        """Score slippage efficiency: ≤ 0.5× target → 1.0, ≥ 2× → 0.0."""
        avg_slip = self._get_avg_slippage_bps(_strategy)
        if avg_slip <= 0:
            return 1.0  # No data or perfect execution
        # Assume target slippage of 10bps for scoring
        target = 10.0
        ratio = avg_slip / target
        if ratio <= 0.5:
            return 1.0
        if ratio >= self.SLIPPAGE_TOLERANCE:
            return 0.0
        return 1.0 - (ratio - 0.5) / (self.SLIPPAGE_TOLERANCE - 0.5)

    # ── Raw Data Accessors ──────────────────────────────────────────────

    def _get_raw_sharpe(self, _strategy: str) -> float:
        """Get raw Sharpe ratio from risk reporter."""
        if self._risk_reporter is None:
            return 0.0
        try:
            report = self._risk_reporter.compute()
            return report.sharpe_ratio
        except Exception:
            return 0.0

    def _get_raw_win_rate(self, _strategy: str) -> float:
        """Get raw win rate from risk reporter."""
        if self._risk_reporter is None:
            return 0.0
        try:
            report = self._risk_reporter.compute()
            return report.win_rate_30d
        except Exception:
            return 0.0

    def _get_raw_drawdown(self, _strategy: str) -> float:
        """Get raw max drawdown from risk reporter."""
        if self._risk_reporter is None:
            return 0.0
        try:
            report = self._risk_reporter.compute()
            return report.max_drawdown
        except Exception:
            return 0.0

    def _get_signal_age(self, _strategy: str) -> float:
        """Get the age of the latest signal in seconds."""
        if self._latency_profiler is None:
            return 999.0
        try:
            stats = self._latency_profiler.get_stats(path_filter="signal")
            if not stats:
                return 999.0
            # Use the most recent span's timestamp
            return 0.0  # FIXME: track last signal timestamp
        except Exception:
            return 999.0

    def _get_trade_count_30d(self, _strategy: str) -> int:
        """Get trade count in last 30 days from PnL ledger."""
        if self._pnl_ledger is None:
            return 0
        try:
            stats = self._pnl_ledger.get_statistics(days=30)
            return stats.get("total_trades", 0)
        except Exception:
            return 0

    def _get_avg_slippage_bps(self, _strategy: str) -> float:
        """Get average slippage from PnL ledger."""
        if self._pnl_ledger is None:
            return 0.0
        try:
            stats = self._pnl_ledger.get_statistics(days=30)
            return stats.get("average_slippage_bps", 0.0)
        except Exception:
            return 0.0


# ── Module-level singleton ──────────────────────────────────────────────

MONITOR: Optional[StrategyHealthMonitor] = None


def get_health_monitor(**kwargs) -> StrategyHealthMonitor:
    """Get or create the global StrategyHealthMonitor singleton."""
    global MONITOR
    if MONITOR is None:
        MONITOR = StrategyHealthMonitor(**kwargs)
    return MONITOR


def health_check() -> SystemHealthSummary:
    """Quick convenience: evaluate health and return summary."""
    monitor = get_health_monitor()
    return monitor.evaluate()


# ── Test / Demo ─────────────────────────────────────────────────────────

def demo_health_scorecard():
    """Demonstrate the strategy health scorecard with synthetic data."""
    import sys

    print("=" * 60)
    print("T31.3 — Strategy Health Scorecard Demo")
    print("=" * 60)

    monitor = get_health_monitor()

    # Run evaluation
    print("\n[1] Running initial health evaluation...")
    summary = monitor.evaluate(force=True)
    print(f"    Overall score:  {summary.overall_score:.4f}")
    print(f"    Strategies:     {summary.total_strategies}")
    print(f"    Healthy:        {summary.healthy_count}")
    print(f"    Degraded:       {summary.degraded_count}")
    print(f"    Critical:       {summary.critical_count}")
    print(f"    Current mode:   {summary.current_mode}")

    # Per-strategy breakdown
    print("\n[2] Per-strategy breakdown:")
    for name, score in summary.strategy_scores.items():
        print(f"    {name:25s} composite={score.composite_score:.3f} "
              f"(status={score.status:10s}, "
              f"Sharpe={score.sharpe_score:.2f}, "
              f"WR={score.win_rate_score:.2f}, "
              f"DD={score.drawdown_score:.2f})")

    # Alerts
    print("\n[3] Alerts:")
    if summary.alerts:
        for alert in summary.alerts:
            print(f"    ⚠ {alert}")
    else:
        print("    ✅ No active alerts")

    # Cache test
    print("\n[4] Cache test (second call should be instant):")
    t0 = time.time()
    cached = monitor.evaluate(force=False)
    t1 = time.time()
    assert cached.overall_score == summary.overall_score
    print(f"    Cache hit: retrieved in {(t1-t0)*1000:.1f}ms  ✅")

    print("\n" + "=" * 60)
    print("✅ Strategy Health Scorecard ready")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo_health_scorecard()


    ALERTER_AVAILABLE = False
