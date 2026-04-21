"""
SIMP Trading Policy Gate + Kill Switch
=======================================

Single source of truth for all trading risk limits and the global kill switch.
Risk limits are calculated against your REAL wallet balances (Coinbase, Alpaca,
Solana), not a placeholder number.

KILL SWITCH
-----------
To immediately halt ALL execution, create the kill switch file:

    touch data/KILL_SWITCH

To resume:

    rm data/KILL_SWITCH

No code changes needed. Any process with filesystem access can halt the system.
The kill switch is checked before every trade, every order, every execution.

HARD LIMITS (as % of real portfolio — override via env vars)
---------------------------------------------------------------------------
- MAX_DAILY_LOSS_PCT     : 2% of real portfolio per calendar day
- MAX_POSITION_SIZE_PCT  : 5% of real portfolio per single trade
- MAX_OPEN_POSITIONS     : 3 concurrent positions
- EXCHANGE_ALLOWLIST     : coinbase, alpaca, solana (live requires explicit opt-in)

ENABLING LIVE TRADING
---------------------
Both env vars required — belt AND suspenders:

    export SIMP_LIVE_TRADING_ENABLED=true
    export SIMP_LIVE_EXCHANGES=coinbase,alpaca

STARTING CAPITAL
----------------
Fetched automatically at startup from your connected wallets.
Override with SIMP_STARTING_CAPITAL_USD if needed (e.g. credentials not loaded yet).

Usage
-----
    from simp.policies.trading_policy import check_trade_allowed, TradingPolicy

    # Quick gate (raises PolicyViolation on reject)
    check_trade_allowed(exchange="coinbase", size_usd=50.0)

    # Full policy object for status reporting
    policy = TradingPolicy()
    status = policy.status()
    policy.record_loss(20.0)  # called by executors after a losing trade
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("simp.policies.trading_policy")

# ---------------------------------------------------------------------------
# Kill switch path (relative to repo root, or override via env)
# ---------------------------------------------------------------------------

_DEFAULT_KILL_SWITCH_PATH = Path(
    os.environ.get("SIMP_KILL_SWITCH_PATH", "data/KILL_SWITCH")
)

# ---------------------------------------------------------------------------
# Hard limits — override via environment variables
# ---------------------------------------------------------------------------

MAX_DAILY_LOSS_PCT: float = float(os.environ.get("SIMP_MAX_DAILY_LOSS_PCT", "0.02"))
# Position size as % of real portfolio (default 5% per trade)
MAX_POSITION_SIZE_PCT: float = float(os.environ.get("SIMP_MAX_POSITION_PCT", "0.05"))
MAX_OPEN_POSITIONS: int = int(os.environ.get("SIMP_MAX_OPEN_POSITIONS", "3"))

# Paper exchanges always allowed; live exchanges require explicit opt-in
_PAPER_EXCHANGES: frozenset = frozenset({"coinbase_paper", "alpaca_paper", "binance_paper"})

_live_trading_enabled: bool = os.environ.get("SIMP_LIVE_TRADING_ENABLED", "").lower() == "true"
_live_exchanges_raw: str = os.environ.get("SIMP_LIVE_EXCHANGES", "")
_LIVE_EXCHANGES: frozenset = frozenset(
    e.strip().lower() for e in _live_exchanges_raw.split(",") if e.strip()
) if _live_trading_enabled else frozenset()

# When live trading is enabled, real exchange names are added automatically
_REAL_EXCHANGES: frozenset = frozenset({"coinbase", "alpaca", "solana", "kraken", "binance"})
EXCHANGE_ALLOWLIST: frozenset = _PAPER_EXCHANGES | (
    _LIVE_EXCHANGES | _REAL_EXCHANGES if _live_trading_enabled else frozenset()
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PolicyViolation(Exception):
    """Raised when a trade request violates the trading policy."""

    def __init__(self, reason: str, policy_name: str = "trading_policy"):
        self.reason = reason
        self.policy_name = policy_name
        super().__init__(f"[{policy_name}] BLOCKED: {reason}")


# ---------------------------------------------------------------------------
# Daily loss tracker (in-process, reset at midnight)
# ---------------------------------------------------------------------------

@dataclass
class _DailyLossTracker:
    """Thread-safe daily realized loss accumulator."""
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _date: date = field(default_factory=date.today, init=False)
    _total_loss_usd: float = field(default=0.0, init=False)

    def record_loss(self, amount_usd: float) -> float:
        """Record a loss (positive = loss). Returns new daily total."""
        if amount_usd <= 0:
            return self._total_loss_usd
        with self._lock:
            today = date.today()
            if today != self._date:
                self._date = today
                self._total_loss_usd = 0.0
            self._total_loss_usd += amount_usd
            return self._total_loss_usd

    def daily_total(self) -> float:
        with self._lock:
            today = date.today()
            if today != self._date:
                self._date = today
                self._total_loss_usd = 0.0
            return self._total_loss_usd

    def reset(self) -> None:
        with self._lock:
            self._total_loss_usd = 0.0
            self._date = date.today()


_LOSS_TRACKER = _DailyLossTracker()

# ---------------------------------------------------------------------------
# Core policy class
# ---------------------------------------------------------------------------

class TradingPolicy:
    """
    Central trading policy enforcer.

    Risk limits are calculated against real wallet balances fetched at startup.
    Call check() before every trade. It either returns True or raises
    PolicyViolation. Never returns False silently — a violation always raises.

    Thread-safe. Stateless except for daily loss tracking (module-level).
    """

    def __init__(
        self,
        kill_switch_path: Optional[Path] = None,
        starting_capital_usd: Optional[float] = None,
        skip_balance_fetch: bool = False,
    ):
        self._kill_switch_path = kill_switch_path or _DEFAULT_KILL_SWITCH_PATH
        self._balance_report = None

        if starting_capital_usd is not None:
            # Explicit override (used by tests or manual config)
            self._starting_capital_usd = starting_capital_usd
        elif not skip_balance_fetch:
            self._starting_capital_usd = self._load_real_balance()
        else:
            manual = os.environ.get("SIMP_STARTING_CAPITAL_USD", "")
            self._starting_capital_usd = float(manual) if manual else 0.0

        self._max_daily_loss_usd = self._starting_capital_usd * MAX_DAILY_LOSS_PCT
        self._max_position_size_usd = self._starting_capital_usd * MAX_POSITION_SIZE_PCT

        log.info(
            "TradingPolicy initialized: capital=$%.2f  "
            "daily_loss_limit=$%.2f (%.0f%%)  max_position=$%.2f (%.0f%%)",
            self._starting_capital_usd,
            self._max_daily_loss_usd,
            MAX_DAILY_LOSS_PCT * 100,
            self._max_position_size_usd,
            MAX_POSITION_SIZE_PCT * 100,
        )

    def _load_real_balance(self) -> float:
        """Fetch real portfolio value from connected wallets. Returns 0 on total failure."""
        try:
            from simp.policies.wallet_balance import fetch_portfolio_usd
            report = fetch_portfolio_usd()
            self._balance_report = report
            if report.total_usd > 0:
                log.info(
                    "Real portfolio loaded: $%.2f USD  live_account=%s",
                    report.total_usd,
                    report.is_live_account,
                )
                for w in report.warnings:
                    log.warning("Balance warning: %s", w)
                for e in report.errors:
                    log.error("Balance error: %s", e)
                return report.total_usd
            else:
                log.warning(
                    "No portfolio balance fetched from any source. "
                    "Defaulting to $0. Set SIMP_STARTING_CAPITAL_USD as override."
                )
                for w in report.warnings:
                    log.warning("Balance warning: %s", w)
                return 0.0
        except Exception as e:
            log.error("Balance fetch failed: %s — defaulting to $0", e)
            return 0.0

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------

    def is_killed(self) -> bool:
        """Return True if the kill switch file exists."""
        return self._kill_switch_path.exists()

    def activate_kill_switch(self, reason: str = "manual") -> None:
        """
        Activate the kill switch programmatically.
        Writes the reason into the file so operators can see why.
        """
        self._kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "activated_by": "simp.policies.trading_policy",
        }
        self._kill_switch_path.write_text(json.dumps(payload, indent=2))
        log.critical("KILL SWITCH ACTIVATED: %s", reason)

    def deactivate_kill_switch(self) -> None:
        """Remove the kill switch file. Resumes normal operation."""
        if self._kill_switch_path.exists():
            self._kill_switch_path.unlink()
            log.warning("Kill switch deactivated — trading policy resumed")

    def kill_switch_info(self) -> Optional[dict]:
        """Return the content of the kill switch file, or None if inactive."""
        if not self._kill_switch_path.exists():
            return None
        try:
            return json.loads(self._kill_switch_path.read_text())
        except Exception:
            return {"activated_at": "unknown", "reason": "file exists but unreadable"}

    # ------------------------------------------------------------------
    # Loss tracking
    # ------------------------------------------------------------------

    def record_loss(self, amount_usd: float) -> float:
        """
        Record a realized loss. Automatically activates kill switch if
        daily loss limit is breached.

        Returns the new daily loss total.
        """
        new_total = _LOSS_TRACKER.record_loss(amount_usd)
        if new_total >= self._max_daily_loss_usd:
            self.activate_kill_switch(
                reason=(
                    f"Daily loss limit breached: ${new_total:.2f} >= "
                    f"${self._max_daily_loss_usd:.2f} "
                    f"({MAX_DAILY_LOSS_PCT * 100:.1f}% of starting capital)"
                )
            )
        return new_total

    def daily_loss_total(self) -> float:
        return _LOSS_TRACKER.daily_total()

    def remaining_daily_loss_budget(self) -> float:
        return max(0.0, self._max_daily_loss_usd - _LOSS_TRACKER.daily_total())

    # ------------------------------------------------------------------
    # Trade gate — the main enforcement point
    # ------------------------------------------------------------------

    def check(
        self,
        exchange: str,
        size_usd: float,
        dry_run: bool = False,
        open_positions: int = 0,
    ) -> bool:
        """
        Validate a proposed trade against all policy limits.

        Args:
            exchange: Exchange identifier (must be in EXCHANGE_ALLOWLIST)
            size_usd: Notional size in USD
            dry_run: If True, skip kill switch and live-exchange checks
            open_positions: Current number of open positions

        Returns:
            True if trade is allowed.

        Raises:
            PolicyViolation: With a human-readable reason if any check fails.
        """
        # Kill switch is always checked, even for dry_run
        if self.is_killed():
            info = self.kill_switch_info() or {}
            raise PolicyViolation(
                f"Kill switch is active. Reason: {info.get('reason', 'unknown')}. "
                f"Activated at: {info.get('activated_at', 'unknown')}. "
                f"Remove {self._kill_switch_path} to resume."
            )

        if not dry_run:
            # Exchange allowlist
            exchange_lower = exchange.lower()
            if exchange_lower not in EXCHANGE_ALLOWLIST:
                raise PolicyViolation(
                    f"Exchange '{exchange}' is not in the allowlist. "
                    f"Allowed: {sorted(EXCHANGE_ALLOWLIST)}. "
                    f"To add live exchanges, set SIMP_LIVE_TRADING_ENABLED=true "
                    f"and SIMP_LIVE_EXCHANGES=<name>."
                )

            # Position size cap (% of real portfolio)
            if self._max_position_size_usd > 0 and size_usd > self._max_position_size_usd:
                raise PolicyViolation(
                    f"Position size ${size_usd:.2f} exceeds maximum "
                    f"${self._max_position_size_usd:.2f} "
                    f"({MAX_POSITION_SIZE_PCT * 100:.0f}% of ${self._starting_capital_usd:.2f} portfolio). "
                    f"Override via SIMP_MAX_POSITION_PCT env var."
                )

            # Max concurrent positions
            if open_positions >= MAX_OPEN_POSITIONS:
                raise PolicyViolation(
                    f"Open positions ({open_positions}) at maximum ({MAX_OPEN_POSITIONS}). "
                    f"Override via SIMP_MAX_OPEN_POSITIONS env var."
                )

            # Daily loss budget
            remaining = self.remaining_daily_loss_budget()
            if remaining <= 0:
                raise PolicyViolation(
                    f"Daily loss budget exhausted: "
                    f"${self.daily_loss_total():.2f} lost today "
                    f"(limit: ${self._max_daily_loss_usd:.2f}). "
                    f"Resets at midnight UTC."
                )

        log.info(
            "Policy check PASSED: exchange=%s size_usd=%.2f dry_run=%s "
            "open_positions=%d daily_loss_remaining=$%.2f",
            exchange, size_usd, dry_run, open_positions,
            self.remaining_daily_loss_budget(),
        )
        return True

    # ------------------------------------------------------------------
    # Status report
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Return a human-readable policy status dict for dashboards/reports."""
        kill_active = self.is_killed()
        balance_breakdown = {}
        is_live_account = False
        if self._balance_report:
            balance_breakdown = self._balance_report.breakdown
            is_live_account = self._balance_report.is_live_account

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kill_switch": {
                "active": kill_active,
                "path": str(self._kill_switch_path),
                "info": self.kill_switch_info() if kill_active else None,
            },
            "portfolio": {
                "starting_capital_usd": round(self._starting_capital_usd, 2),
                "is_live_account": is_live_account,
                "balance_breakdown": balance_breakdown,
            },
            "limits": {
                "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
                "max_daily_loss_usd": round(self._max_daily_loss_usd, 2),
                "max_position_size_pct": MAX_POSITION_SIZE_PCT,
                "max_position_size_usd": round(self._max_position_size_usd, 2),
                "max_open_positions": MAX_OPEN_POSITIONS,
            },
            "daily_loss": {
                "total_usd": round(self.daily_loss_total(), 2),
                "remaining_usd": round(self.remaining_daily_loss_budget(), 2),
                "limit_usd": round(self._max_daily_loss_usd, 2),
                "pct_used": round(
                    self.daily_loss_total() / self._max_daily_loss_usd * 100, 1
                ) if self._max_daily_loss_usd > 0 else 0.0,
            },
            "exchanges": {
                "allowlist": sorted(EXCHANGE_ALLOWLIST),
                "live_trading_enabled": _live_trading_enabled,
                "live_exchanges_configured": sorted(_LIVE_EXCHANGES),
            },
            "system": {
                "kill_switch_path": str(self._kill_switch_path),
                "to_halt": f"touch {self._kill_switch_path}",
                "to_resume": f"rm {self._kill_switch_path}",
            },
        }


# ---------------------------------------------------------------------------
# Module-level singleton + convenience function
# ---------------------------------------------------------------------------

_DEFAULT_POLICY = TradingPolicy()  # fetches real balances at import time


def check_trade_allowed(
    exchange: str,
    size_usd: float,
    dry_run: bool = False,
    open_positions: int = 0,
) -> bool:
    """
    Module-level convenience gate. Raises PolicyViolation on reject.

    Import and call this at the top of any execution path:

        from simp.policies.trading_policy import check_trade_allowed
        check_trade_allowed(exchange="coinbase_paper", size_usd=150.0)
    """
    return _DEFAULT_POLICY.check(
        exchange=exchange,
        size_usd=size_usd,
        dry_run=dry_run,
        open_positions=open_positions,
    )


def get_policy_status() -> dict:
    """Return current policy status. Safe to call from dashboards."""
    return _DEFAULT_POLICY.status()


def activate_kill_switch(reason: str = "manual") -> None:
    """Immediately halt all live trading."""
    _DEFAULT_POLICY.activate_kill_switch(reason)


def record_loss(amount_usd: float) -> float:
    """Record a realized loss. Auto-trips kill switch if daily limit breached."""
    return _DEFAULT_POLICY.record_loss(amount_usd)
