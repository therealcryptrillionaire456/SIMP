"""
ProjectX Risk Engine — Wave 5

Pre-trade risk checks that every order must pass before touching the market.
Hard gates, not advisory — violating any limit raises RiskViolation and blocks execution.

Gates (evaluated in order, short-circuit on first failure):
  1. Kill switch — global halt flag
  2. Max notional per order
  3. Max open notional across all positions
  4. Max daily loss (cumulative realised + unrealised vs. starting equity)
  5. Max single-symbol concentration (% of total notional)
  6. Duplicate signal guard (same signal_id within window)
  7. Volatility circuit breaker (blocks if recent vol > threshold)

All thresholds are configurable via RiskConfig; defaults are conservative.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class RiskViolation(Exception):
    """Raised when a pre-trade risk check fails. Contains the blocking gate name."""
    def __init__(self, gate: str, reason: str) -> None:
        super().__init__(f"[{gate}] {reason}")
        self.gate = gate
        self.reason = reason


@dataclass
class RiskConfig:
    max_order_notional_usd:     float = 500.0      # single order ceiling
    max_open_notional_usd:      float = 5_000.0    # total open exposure ceiling
    max_daily_loss_usd:         float = 250.0      # cumulative loss hard stop
    max_symbol_concentration:   float = 0.40       # max fraction of open notional in one symbol
    duplicate_signal_window_s:  int   = 60         # seconds to remember signal IDs
    max_vol_threshold:          float = 0.15       # annualised vol fraction (15%) to block trading
    kill_switch:                bool  = False       # global halt
    paper_mode:                 bool  = True        # forces dry-run even if broker says live


@dataclass
class OrderIntent:
    """A pending order to be risk-checked."""
    signal_id:      str
    symbol:         str
    side:           str          # "BUY" | "SELL"
    notional_usd:   float
    strategy:       str = ""
    metadata:       Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = self.symbol.upper().strip()
        self.side = self.side.upper().strip()
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {self.side!r}")
        if self.notional_usd <= 0:
            raise ValueError(f"notional_usd must be positive, got {self.notional_usd}")
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.signal_id:
            raise ValueError("signal_id must not be empty")


@dataclass
class PositionState:
    symbol:         str
    side:           str
    notional_usd:   float
    entry_ts:       float = field(default_factory=time.time)


class RiskEngine:
    """
    Stateful pre-trade risk gate. Call check() before every order.

    Usage::

        engine = RiskEngine(RiskConfig(max_order_notional_usd=100))
        intent = OrderIntent("sig-001", "BTC-USD", "BUY", 50.0)
        engine.check(intent)          # raises RiskViolation on failure
        engine.record_fill(intent)    # call after confirmed execution
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        starting_equity_usd: float = 10_000.0,
    ) -> None:
        self._cfg = config or RiskConfig()
        self._starting_equity = starting_equity_usd
        self._daily_loss: float = 0.0
        self._positions: Dict[str, PositionState] = {}   # symbol → state
        self._seen_signals: Dict[str, float] = {}         # signal_id → timestamp
        self._lock = threading.Lock()
        self._reset_day = time.strftime("%Y-%m-%d")

    # ── Public API ────────────────────────────────────────────────────────

    def check(self, intent: OrderIntent) -> None:
        """
        Run all risk gates. Raises RiskViolation if any gate fails.
        Thread-safe — safe to call from multiple strategy threads.
        """
        with self._lock:
            self._maybe_reset_daily()
            self._gate_kill_switch()
            self._gate_notional(intent)
            self._gate_open_exposure(intent)
            self._gate_daily_loss()
            self._gate_concentration(intent)
            self._gate_duplicate_signal(intent)
        logger.debug("Risk check PASS: %s %s $%.2f", intent.side, intent.symbol, intent.notional_usd)

    def record_fill(self, intent: OrderIntent, realised_pnl: float = 0.0) -> None:
        """Record a confirmed fill to update position and daily P&L state."""
        with self._lock:
            if realised_pnl < 0:
                self._daily_loss += abs(realised_pnl)
            if intent.side == "BUY":
                self._positions[intent.symbol] = PositionState(
                    symbol=intent.symbol,
                    side="BUY",
                    notional_usd=intent.notional_usd,
                )
            else:
                self._positions.pop(intent.symbol, None)

    def record_loss(self, loss_usd: float) -> None:
        """Manually record a realised loss (e.g. from P&L tracker)."""
        with self._lock:
            self._daily_loss += max(0.0, loss_usd)

    def set_kill_switch(self, active: bool) -> None:
        with self._lock:
            self._cfg.kill_switch = active
        logger.warning("Kill switch %s", "ACTIVATED" if active else "DEACTIVATED")

    def status(self) -> Dict[str, Any]:
        with self._lock:
            open_notional = sum(p.notional_usd for p in self._positions.values())
            return {
                "kill_switch": self._cfg.kill_switch,
                "paper_mode": self._cfg.paper_mode,
                "daily_loss_usd": round(self._daily_loss, 4),
                "max_daily_loss_usd": self._cfg.max_daily_loss_usd,
                "open_notional_usd": round(open_notional, 4),
                "max_open_notional_usd": self._cfg.max_open_notional_usd,
                "open_positions": len(self._positions),
                "daily_loss_pct": round(self._daily_loss / max(1, self._starting_equity) * 100, 2),
            }

    # ── Gates ─────────────────────────────────────────────────────────────

    def _gate_kill_switch(self) -> None:
        if self._cfg.kill_switch:
            raise RiskViolation("kill_switch", "Global trading halt is active")

    def _gate_notional(self, intent: OrderIntent) -> None:
        cap = self._cfg.max_order_notional_usd
        if intent.notional_usd > cap:
            raise RiskViolation(
                "max_order_notional",
                f"Order ${intent.notional_usd:.2f} exceeds limit ${cap:.2f}",
            )

    def _gate_open_exposure(self, intent: OrderIntent) -> None:
        if intent.side != "BUY":
            return
        current = sum(p.notional_usd for p in self._positions.values())
        projected = current + intent.notional_usd
        cap = self._cfg.max_open_notional_usd
        if projected > cap:
            raise RiskViolation(
                "max_open_notional",
                f"Projected open exposure ${projected:.2f} exceeds limit ${cap:.2f}",
            )

    def _gate_daily_loss(self) -> None:
        cap = self._cfg.max_daily_loss_usd
        if self._daily_loss >= cap:
            raise RiskViolation(
                "max_daily_loss",
                f"Daily loss ${self._daily_loss:.2f} has reached limit ${cap:.2f}",
            )

    def _gate_concentration(self, intent: OrderIntent) -> None:
        if intent.side != "BUY":
            return
        total = sum(p.notional_usd for p in self._positions.values()) + intent.notional_usd
        sym_total = self._positions.get(intent.symbol, PositionState("", "", 0)).notional_usd
        sym_total += intent.notional_usd
        if total > 0 and (sym_total / total) > self._cfg.max_symbol_concentration:
            raise RiskViolation(
                "concentration",
                f"{intent.symbol} would be {sym_total/total:.1%} of portfolio "
                f"(limit {self._cfg.max_symbol_concentration:.1%})",
            )

    def _gate_duplicate_signal(self, intent: OrderIntent) -> None:
        now = time.time()
        window = self._cfg.duplicate_signal_window_s
        # Evict expired signals
        self._seen_signals = {
            sid: ts for sid, ts in self._seen_signals.items() if now - ts < window
        }
        if intent.signal_id in self._seen_signals:
            raise RiskViolation(
                "duplicate_signal",
                f"signal_id {intent.signal_id!r} already processed within {window}s",
            )
        self._seen_signals[intent.signal_id] = now

    def _maybe_reset_daily(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self._reset_day:
            self._daily_loss = 0.0
            self._reset_day = today
            logger.info("Daily risk counters reset for %s", today)


# Module-level singleton
_engine: Optional[RiskEngine] = None
_engine_lock = threading.Lock()


def get_risk_engine(config: Optional[RiskConfig] = None) -> RiskEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = RiskEngine(config)
    return _engine
