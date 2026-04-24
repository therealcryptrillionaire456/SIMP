"""
Profit Seeker Core — Compounding Growth Engine

The exponential heartbeat of the QuantumArb bot.

Implements the 2ⁿ daily doubling curve from the PDF vision:
  Day 1:       $1  → $2
  Day 2:       $2  → $4
  Day 10:    $512  → $1,024
  Day 20:  $524K  → $1M

This is NOT a literal profit target (the PDF knows 90-day doubling
is unachievable in real markets). It is a *benchmark curve* that drives
escalation and consolidation:

  - progress < 0.7  → ESCALATE (wider scans, higher risk, quantum opt-in)
  - progress > 1.3  → CONSOLIDATE (tighten thresholds, reduce exposure)

The curve is parameterised so it can be tuned to *any* growth rate.
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

log = logging.getLogger("compounding")

try:
    from simp.integrations.market_news import MLTradeLogicAdjuster, StrategyAdjustment

    NEWS_ADJUSTER_AVAILABLE = True
except ImportError:
    MLTradeLogicAdjuster = Any  # type: ignore[assignment]
    StrategyAdjustment = Any  # type: ignore[assignment]
    NEWS_ADJUSTER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ESCAPE_HATCH_DAYS = 90          # max lookahead
DEFAULT_BASE_CURRENCY = 1.0     # $1 starting point
DEFAULT_DAILY_MULTIPLIER = 2.0  # double every day


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CompoundingSnapshot:
    """Point-in-time snapshot of compounding state."""
    day: int
    target_balance: float
    actual_balance: float
    progress_ratio: float                    # actual / target
    regime: str                              # "CONSOLIDATE" | "TRACKING" | "ESCALATE" | "CRISIS"
    daily_growth_needed_pct: float           # % growth needed today to stay on curve
    consecutive_days_behind: int
    timestamp: str


@dataclass
class CompoundingConfig:
    """Tunable parameters for the growth curve."""
    base_currency: str = "USD"
    initial_capital: float = 1.0
    daily_multiplier: float = 2.0
    escalation_threshold: float = 0.7        # progress below → ESCALATE
    consolidation_threshold: float = 1.3     # progress above → CONSOLIDATE
    crisis_threshold: float = 0.3            # progress below → CRISIS (stop trading)
    max_escalation_days: int = 5             # max days before forced consolidation
    max_risk_per_trade_pct: float = 2.0      # max % of capital per trade in escalation
    base_risk_per_trade_pct: float = 0.5    # base % in tracking mode
    min_risk_per_trade_pct: float = 0.1     # min % in consolidation mode

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# CompoundingTarget — the 2ⁿ curve
# ---------------------------------------------------------------------------

class CompoundingTarget:
    """
    The 2ⁿ daily growth target.

    ``target(day) = initial_capital * (daily_multiplier ** day)``

    The curve is always computed from ``start_date``, so the bot can be
    paused, restarted, and the target still makes sense.
    """

    def __init__(
        self,
        start_date: Optional[str] = None,      # ISO date, default = now
        config: Optional[CompoundingConfig] = None,
    ):
        self.config = config or CompoundingConfig()
        self.start_date = start_date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._start_dt = datetime.fromisoformat(self.start_date.replace("Z", "+00:00"))

    # ------------------------------------------------------------------
    # core calculation
    # ------------------------------------------------------------------

    def target(self, day: int) -> float:
        """Return target balance for a given day (0-indexed)."""
        if day < 0:
            return 0.0
        return self.config.initial_capital * (self.config.daily_multiplier ** day)

    def target_at_date(self, dt: Optional[datetime] = None) -> Tuple[int, float]:
        """
        Return (day_number, target_balance) for a given datetime.

        Day 0 = midnight of start_date.  So if the bot started at noon,
        day 0 is the first 12-hour window.
        """
        now = dt or datetime.now(timezone.utc)
        elapsed = (now - self._start_dt).total_seconds()
        day = max(0, int(elapsed // 86400))
        return day, self.target(day)

    def progress(self, actual_balance: float, dt: Optional[datetime] = None) -> float:
        """
        Return progress ratio for a given balance.

        ``progress = actual / target``

        - 1.0  = on track
        - <0.7 = behind → escalation zone
        - >1.3 = ahead → consolidation zone
        - <0.3 = crisis → stop trading
        """
        _, tgt = self.target_at_date(dt)
        if tgt <= 0:
            return 1.0
        return actual_balance / tgt

    def regime(self, actual_balance: float, dt: Optional[datetime] = None) -> str:
        """
        Classify the current operating regime.
        """
        p = self.progress(actual_balance, dt)
        if p < self.config.crisis_threshold:
            return "CRISIS"
        if p < self.config.escalation_threshold:
            return "ESCALATE"
        if p > self.config.consolidation_threshold:
            return "CONSOLIDATE"
        return "TRACKING"

    def growth_needed_today(self, actual_balance: float, dt: Optional[datetime] = None) -> float:
        """
        Return the % growth needed *today* to stay on the 2ⁿ curve.

        If actual = 100 and target = 200, daily_growth_needed = 100%.
        If actual = 200 and target = 200, daily_growth_needed = 0%.
        """
        _, tgt = self.target_at_date(dt)
        if actual_balance <= 0:
            return float("inf")
        return ((tgt / actual_balance) - 1.0) * 100.0

    # ------------------------------------------------------------------
    # serialisation
    # ------------------------------------------------------------------

    def snapshot(self, actual_balance: float, consecutive_days_behind: int = 0) -> CompoundingSnapshot:
        day, tgt = self.target_at_date()
        p = self.progress(actual_balance)
        r = self.regime(actual_balance)
        growth = self.growth_needed_today(actual_balance)
        return CompoundingSnapshot(
            day=day,
            target_balance=tgt,
            actual_balance=actual_balance,
            progress_ratio=round(p, 4),
            regime=r,
            daily_growth_needed_pct=round(growth, 2),
            consecutive_days_behind=consecutive_days_behind,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date,
            "config": self.config.to_dict(),
        }


# ---------------------------------------------------------------------------
# GrowthScheduler — maps regime → trade parameters
# ---------------------------------------------------------------------------

class GrowthScheduler:
    """
    Translates compounding regime into concrete trading parameters.

    Each regime gets a different risk profile, min spread threshold,
    and position size multiplier.
    """

    def __init__(
        self,
        target: CompoundingTarget,
        pnl_ledger_ref: Any = None,
        news_adjuster: Optional[Any] = None,
    ):
        self._target = target
        self._ledger = pnl_ledger_ref
        self._news_adjuster = news_adjuster
        self._lock = threading.Lock()
        self._consecutive_days_behind: int = 0
        self._last_day_checked: int = -1

    # ------------------------------------------------------------------
    # regime-based parameters
    # ------------------------------------------------------------------

    def trading_parameters(self, actual_balance: float) -> Dict[str, Any]:
        """
        Compute trading parameters based on current regime.

        Returns:
            risk_per_trade_pct:   % of capital to risk per trade
            min_spread_bps:       minimum arb spread to consider
            max_position_pct:     % of capital per single position
            quantum_opt_in:       whether to use quantum optimisation
            aggressive_scan:      whether to scan more pairs/exchanges
            emergency_stop:       whether to halt all trading
        """
        regime = self._target.regime(actual_balance)
        config = self._target.config

        # Default: tracking
        params: Dict[str, Any] = {
            "risk_per_trade_pct": config.base_risk_per_trade_pct,
            "min_spread_bps": 10.0,
            "max_position_pct": 10.0,
            "quantum_opt_in": False,
            "aggressive_scan": False,
            "emergency_stop": False,
            "regime": regime,
        }

        if regime == "CONSOLIDATE":
            # Ahead of curve — tighten up, protect gains
            params["risk_per_trade_pct"] = config.min_risk_per_trade_pct
            params["min_spread_bps"] = 20.0     # only take high-quality arb
            params["max_position_pct"] = 5.0
            params["quantum_opt_in"] = False

        elif regime == "ESCALATE":
            # Behind curve — widen search, accept more risk
            params["risk_per_trade_pct"] = min(
                config.max_risk_per_trade_pct,
                config.base_risk_per_trade_pct * (1.5 ** self._consecutive_days_behind),
            )
            params["min_spread_bps"] = 5.0      # lower threshold
            params["max_position_pct"] = 15.0   # bigger positions
            params["quantum_opt_in"] = True      # use quantum optimisation
            params["aggressive_scan"] = True      # scan wider

        elif regime == "CRISIS":
            # Far behind — stop everything
            params["emergency_stop"] = True
            params["risk_per_trade_pct"] = 0.0
            params["aggressive_scan"] = False

        return params

    # ------------------------------------------------------------------
    # news-aware trading parameters
    # ------------------------------------------------------------------

    def trading_params_with_news(
        self,
        actual_balance: float,
        adjustments: Optional[Dict[str, Any]] = None,
        target_pair: str = "default",
    ) -> Dict[str, Any]:
        """
        Like trading_parameters() but applies MLTradeLogicAdjuster
        adjustments if a news_adjuster is attached.

        Args:
            actual_balance: Current portfolio balance.
            adjustments: Pre-computed adjustments dict from
                MLTradeLogicAdjuster.adjust_for_news().
            target_pair: Trading pair key for adjustment lookup.

        Returns:
            Trading params with sentiment-based overrides applied.
        """
        params = self.trading_parameters(actual_balance)

        if (
            self._news_adjuster is not None
            and NEWS_ADJUSTER_AVAILABLE
            and adjustments
        ):
            try:
                params = self._news_adjuster.apply_to_params(
                    params=params,
                    pair=target_pair,
                    adjustments=adjustments,
                )
                log.info(
                    "News-adjusted params for %s: risk=%.2f%%, spread=%.1fbps, "
                    "position=%.2f%%",
                    target_pair,
                    params.get("risk_per_trade_pct", 0),
                    params.get("min_spread_bps", 10),
                    params.get("max_position_pct", 10),
                )
            except Exception as exc:
                log.warning("News adjustment failed for %s: %s", target_pair, exc)

        return params

    # ------------------------------------------------------------------
    # day tracking
    # ------------------------------------------------------------------

    def update_day_tracking(self, actual_balance: float) -> None:
        """
        Call once per day (e.g. at market close) to update consecutive-day counter.
        """
        day, tgt = self._target.target_at_date()
        with self._lock:
            if day != self._last_day_checked:
                self._last_day_checked = day
                if actual_balance < tgt:
                    self._consecutive_days_behind += 1
                else:
                    self._consecutive_days_behind = 0

    def consecutive_days_behind(self) -> int:
        with self._lock:
            return self._consecutive_days_behind

    # ------------------------------------------------------------------
    # higher-level
    # ------------------------------------------------------------------

    def evaluate(self, actual_balance: float) -> CompoundingSnapshot:
        """Produce a full snapshot + update day tracking in one call."""
        self.update_day_tracking(actual_balance)
        return self._target.snapshot(actual_balance, self._consecutive_days_behind)


# ---------------------------------------------------------------------------
# EscalationManager — quantum escalation triggers
# ---------------------------------------------------------------------------

class EscalationManager:
    """
    When the bot falls behind the 2ⁿ curve, this manager triggers
    escalation actions: wider market scans, quantum optimisation,
    higher risk tolerance.
    """

    def __init__(self, scheduler: GrowthScheduler):
        self._scheduler = scheduler
        self._escalation_log: List[Dict[str, Any]] = []

    def check_and_escalate(self, actual_balance: float) -> Dict[str, Any]:
        """
        Check if escalation is needed and produce action instructions.

        Returns an action dict that other components (ArbDetector,
        TradeExecutor, QuantumArbOptimizer) can consume.
        """
        snapshot = self._scheduler.evaluate(actual_balance)
        params = self._scheduler.trading_parameters(actual_balance)

        action: Dict[str, Any] = {
            "timestamp": snapshot.timestamp,
            "regime": snapshot.regime,
            "progress": snapshot.progress_ratio,
            "action_required": snapshot.regime in ("ESCALATE", "CRISIS"),
            "params": params,
        }

        if snapshot.regime == "ESCALATE":
            # How many days behind?  Escalate harder each day
            days = snapshot.consecutive_days_behind
            action["escalation_level"] = min(days, 5)
            action["widen_scan_pairs"] = True
            action["widen_scan_exchanges"] = days >= 2
            action["enable_quantum_optimisation"] = days >= 1
            action["triangular_arb_enabled"] = days >= 3
            action["cross_exchange_triangular_enabled"] = days >= 4

        elif snapshot.regime == "CRISIS":
            action["action_required"] = True
            action["halt_trading"] = True
            action["reason"] = (
                f"Progress {snapshot.progress_ratio:.1%} below crisis "
                f"threshold {self._scheduler._target.config.crisis_threshold:.0%}"
            )

        self._escalation_log.append(action)
        log.info(
            "Escalation check: regime=%s progress=%.2f action=%s",
            snapshot.regime, snapshot.progress_ratio, action["action_required"],
        )
        return action

    def get_escalation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._escalation_log[-limit:]


# ---------------------------------------------------------------------------
# ConsolidationManager — profit protection
# ---------------------------------------------------------------------------

class ConsolidationManager:
    """
    When the bot is ahead of the 2ⁿ curve, this manager locks in gains
    by tightening thresholds and reducing exposure.
    """

    def __init__(self, scheduler: GrowthScheduler):
        self._scheduler = scheduler
        self._consolidation_log: List[Dict[str, Any]] = []

    def check_and_consolidate(self, actual_balance: float) -> Dict[str, Any]:
        """
        Check if consolidation is appropriate.

        Returns an action dict.
        """
        snapshot = self._scheduler.evaluate(actual_balance)
        params = self._scheduler.trading_parameters(actual_balance)

        action: Dict[str, Any] = {
            "timestamp": snapshot.timestamp,
            "regime": snapshot.regime,
            "progress": snapshot.progress_ratio,
            "consolidate": snapshot.regime == "CONSOLIDATE",
            "params": params,
        }

        if snapshot.regime == "CONSOLIDATE":
            excess_pct = (snapshot.progress_ratio - 1.0) * 100.0
            action["excess_pct"] = round(excess_pct, 2)
            action["profit_share_to_reserve"] = min(excess_pct, 50.0)  # move % to reserve
            action["tighten_spread"] = True
            action["reduce_position_size"] = True

        self._consolidation_log.append(action)
        return action

    def get_consolidation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._consolidation_log[-limit:]


# ---------------------------------------------------------------------------
# CompoundEngine — ties everything together
# ---------------------------------------------------------------------------

class CompoundEngine:
    """
    Top-level engine that combines the target curve, scheduler, escalation,
    and consolidation into a single interface.

    Usage::

        engine = CompoundEngine(start_date="2025-01-01", initial_capital=1.0)
        snapshot = engine.evaluate(actual_balance=500.0)
        params   = engine.trading_params()
        action   = engine.escalation_check()
    """

    def __init__(
        self,
        start_date: Optional[str] = None,
        initial_capital: float = 1.0,
        daily_multiplier: float = 2.0,
        config: Optional[CompoundingConfig] = None,
        ledger: Any = None,
        news_adjuster: Optional[Any] = None,
    ):
        if config is None:
            config = CompoundingConfig(
                initial_capital=initial_capital,
                daily_multiplier=daily_multiplier,
            )
        self.target = CompoundingTarget(start_date=start_date, config=config)
        self.scheduler = GrowthScheduler(
            self.target,
            pnl_ledger_ref=ledger,
            news_adjuster=news_adjuster,
        )
        self.escalation = EscalationManager(self.scheduler)
        self.consolidation = ConsolidationManager(self.scheduler)
        self._ledger = ledger

    # ------------------------------------------------------------------
    # single-call API
    # ------------------------------------------------------------------

    def evaluate(self, actual_balance: float) -> CompoundingSnapshot:
        """Evaluate current position against the 2ⁿ curve."""
        return self.scheduler.evaluate(actual_balance)

    def trading_params(self, actual_balance: float) -> Dict[str, Any]:
        """Get trading parameters for the current regime."""
        return self.scheduler.trading_parameters(actual_balance)

    def trading_params_with_news(
        self,
        actual_balance: float,
        adjustments: Optional[Dict[str, Any]] = None,
        target_pair: str = "default",
    ) -> Dict[str, Any]:
        """Get trading parameters adjusted by news sentiment."""
        return self.scheduler.trading_params_with_news(
            actual_balance, adjustments, target_pair
        )

    def escalation_check(self, actual_balance: float) -> Dict[str, Any]:
        """Check and trigger escalation if behind curve."""
        return self.escalation.check_and_escalate(actual_balance)

    def consolidation_check(self, actual_balance: float) -> Dict[str, Any]:
        """Check and trigger consolidation if ahead of curve."""
        return self.consolidation.check_and_consolidate(actual_balance)

    def full_report(self, actual_balance: float) -> Dict[str, Any]:
        """Produce a full status report combining everything."""
        snapshot = self.evaluate(actual_balance)
        params = self.trading_params(actual_balance)
        escalation = self.escalation_check(actual_balance)
        consolidation = self.consolidation_check(actual_balance)

        return {
            "snapshot": asdict(snapshot),
            "trading_params": params,
            "escalation": escalation,
            "consolidation": consolidation,
            "target_curve": {
                "start_date": self.target.start_date,
                "initial_capital": self.target.config.initial_capital,
                "daily_multiplier": self.target.config.daily_multiplier,
                "current_day": snapshot.day,
                "next_target": self.target.target(snapshot.day + 1),
            },
        }

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "scheduler": {
                "consecutive_days_behind": self.scheduler.consecutive_days_behind(),
                "last_day": self.scheduler._last_day_checked,
            },
        }


# ======================================================================
# Quick test
# ======================================================================

if __name__ == "__main__":
    engine = CompoundEngine(start_date="2025-01-01", initial_capital=100.0)

    # Day 0: exactly on target
    print(engine.full_report(100.0))

    # Day 5 simulation: behind curve
    import time
    print("\n--- Behind curve simulation ---")
    print(engine.full_report(50.0))
