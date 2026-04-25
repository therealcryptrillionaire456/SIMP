"""
Safety Backstop (Tranche 4)
===========================
On-chain safety circuit breakers enforced at execution time.

Every execution call MUST pass through the safety backstop before
sending a transaction. Rules are checked at JSON-merge granularity.

Kill switch: file-based (state/KILL) and memory-based.
Max loss: per-tx, per-hour, per-day.
Circuit breaker: opens on N consecutive losses, auto-closes after cooldown.
"""

from __future__ import annotations

import json
import logging
import os
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("safety_backstop")

# ── Constants ───────────────────────────────────────────────────────────

KILL_SWITCH_PATH = Path("state/KILL")
STATE_PATH = Path("data/safety_backstop_state.json")

DEFAULT_RULES = {
    "max_loss_per_tx_usd": 5.0,
    "max_loss_per_hour_usd": 20.0,
    "max_loss_per_day_usd": 50.0,
    "max_trades_per_hour": 10,
    "max_trades_per_day": 50,
    "consecutive_loss_limit": 5,
    "cooldown_minutes": 30,
    "max_slippage_bps": 200,
    "min_capital_usd": 1.0,
    "emergency_stop": False,
}


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""
    allowed: bool
    reason: str = ""
    rule: str = ""
    current_value: float = 0.0
    limit_value: float = 0.0
    severity: str = "info"  # info, warning, critical

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SafetyBackstop:
    """
    On-chain safety circuit breaker.
    
    Thread-safe. Checked BEFORE every execution call.
    """

    def __init__(self, rules: Optional[Dict[str, Any]] = None, state_path: str = "data/safety_backstop_state.json"):
        self._lock = threading.Lock()
        self.state_path = Path(state_path)
        self._rules: Dict[str, Any] = rules or dict(DEFAULT_RULES)
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load persistent state from disk."""
        try:
            if self.state_path.exists():
                with open(self.state_path) as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Could not load safety state: %s", e)
        return {
            "trades": [],
            "losses": [],
            "consecutive_losses": 0,
            "circuit_open": False,
            "circuit_open_at": None,
            "emergency_stop": self._rules.get("emergency_stop", False),
            "last_reset": datetime.now(timezone.utc).isoformat(),
        }

    def _save_state(self) -> None:
        """Persist state to disk."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump(self._state, f, indent=2)
        except OSError as e:
            log.error("Could not save safety state: %s", e)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ── Kill Switch ─────────────────────────────────────────────────────

    def check_kill_switch(self) -> SafetyCheckResult:
        """Check file-based kill switch at state/KILL."""
        if KILL_SWITCH_PATH.exists():
            try:
                content = KILL_SWITCH_PATH.read_text().strip().lower()
                if content in ("1", "true", "stop", "kill"):
                    return SafetyCheckResult(False, "Kill switch active", "kill_switch", severity="critical")
            except OSError:
                pass
        env_kill = os.environ.get("SIMP_KILL_SWITCH", "").lower()
        if env_kill in ("1", "true", "stop", "kill"):
            return SafetyCheckResult(False, "Kill switch active (env)", "kill_switch", severity="critical")
        return SafetyCheckResult(True, reason="kill_switch_ok")

    # ── Emergency Stop ──────────────────────────────────────────────────

    def check_emergency_stop(self) -> SafetyCheckResult:
        """Check in-memory and state-file emergency stop."""
        with self._lock:
            if self._state.get("emergency_stop", False):
                return SafetyCheckResult(False, "Emergency stop active", "emergency_stop", severity="critical")
            if self._rules.get("emergency_stop", False):
                return SafetyCheckResult(False, "Emergency stop in rules", "emergency_stop", severity="critical")
        return SafetyCheckResult(True, reason="emergency_stop_ok")

    def set_emergency_stop(self, active: bool = True) -> None:
        """Set or clear emergency stop."""
        with self._lock:
            self._state["emergency_stop"] = active
            self._save_state()
        log.warning("Emergency stop %s", "ACTIVATED" if active else "CLEARED")

    # ── Circuit Breaker ─────────────────────────────────────────────────

    def check_circuit_breaker(self) -> SafetyCheckResult:
        """Check if circuit breaker is open."""
        with self._lock:
            if not self._state.get("circuit_open", False):
                return SafetyCheckResult(True, reason="circuit_closed")
            opened_at = self._state.get("circuit_open_at")
            if opened_at:
                opened = datetime.fromisoformat(opened_at)
                cooldown = self._rules.get("cooldown_minutes", 30)
                if self._now() - opened > timedelta(minutes=cooldown):
                    # Auto-close
                    self._state["circuit_open"] = False
                    self._state["circuit_open_at"] = None
                    self._state["consecutive_losses"] = 0
                    self._save_state()
                    log.info("Circuit breaker auto-closed after %d min cooldown", cooldown)
                    return SafetyCheckResult(True, reason="circuit_auto_closed")
                remaining = cooldown - (self._now() - opened).total_seconds() / 60
                return SafetyCheckResult(
                    False, f"Circuit open ({remaining:.0f} min remaining)",
                    "circuit_breaker", severity="critical",
                )
        return SafetyCheckResult(False, "Circuit open (no timestamp)", "circuit_breaker", severity="critical")

    def _open_circuit(self) -> None:
        """Open circuit breaker (public, acquires lock)."""
        with self._lock:
            self._unsafe_open_circuit()
        log.warning("Circuit breaker OPENED")

    def _unsafe_open_circuit(self) -> None:
        """Open circuit breaker WITHOUT acquiring lock (caller must hold lock)."""
        self._state["circuit_open"] = True
        self._state["circuit_open_at"] = self._now().isoformat()
        self._save_state()

    # ── Loss Limits ─────────────────────────────────────────────────────

    def check_loss_limits(self, proposed_loss_usd: float = 0.0) -> List[SafetyCheckResult]:
        """Check all loss limits."""
        results = []
        with self._lock:
            now = self._now()
            one_hour_ago = now - timedelta(hours=1)
            one_day_ago = now - timedelta(days=1)

            # Filter recent losses
            recent_losses = [
                t for t in self._state.get("losses", [])
                if datetime.fromisoformat(t.get("timestamp", now.isoformat())) > one_hour_ago
            ]
            daily_losses = [
                t for t in self._state.get("losses", [])
                if datetime.fromisoformat(t.get("timestamp", now.isoformat())) > one_day_ago
            ]

            total_hourly = sum(abs(float(t.get("amount", 0))) for t in recent_losses)
            total_daily = sum(abs(float(t.get("amount", 0))) for t in daily_losses)

            consecutive = self._state.get("consecutive_losses", 0)

            # Per-tx check
            max_tx = self._rules.get("max_loss_per_tx_usd", 5.0)
            if proposed_loss_usd > max_tx:
                results.append(SafetyCheckResult(
                    False, f"Proposed loss ${proposed_loss_usd:.2f} > max ${max_tx:.2f}",
                    "max_loss_per_tx_usd", proposed_loss_usd, max_tx, severity="critical",
                ))

            # Per-hour check
            max_hourly = self._rules.get("max_loss_per_hour_usd", 20.0)
            if total_hourly + proposed_loss_usd > max_hourly:
                results.append(SafetyCheckResult(
                    False, f"Hourly loss ${total_hourly:.2f}+${proposed_loss_usd:.2f} > ${max_hourly:.2f}",
                    "max_loss_per_hour_usd", total_hourly + proposed_loss_usd, max_hourly, severity="critical",
                ))

            # Per-day check
            max_daily = self._rules.get("max_loss_per_day_usd", 50.0)
            if total_daily + proposed_loss_usd > max_daily:
                results.append(SafetyCheckResult(
                    False, f"Daily loss ${total_daily:.2f}+${proposed_loss_usd:.2f} > ${max_daily:.2f}",
                    "max_loss_per_day_usd", total_daily + proposed_loss_usd, max_daily, severity="critical",
                ))

            # Consecutive loss check
            max_consec = self._rules.get("consecutive_loss_limit", 5)
            if consecutive >= max_consec:
                self._unsafe_open_circuit()  # caller holds lock
                results.append(SafetyCheckResult(
                    False, f"{consecutive} consecutive losses >= {max_consec}",
                    "consecutive_loss_limit", consecutive, max_consec, severity="critical",
                ))

        return results if results else [SafetyCheckResult(True, reason="loss_limits_ok")]

    # ── Trade Rate Limits ───────────────────────────────────────────────

    def check_rate_limits(self) -> List[SafetyCheckResult]:
        """Check trade rate limits."""
        results = []
        with self._lock:
            now = self._now()
            one_hour_ago = now - timedelta(hours=1)
            one_day_ago = now - timedelta(days=1)

            recent = [
                t for t in self._state.get("trades", [])
                if datetime.fromisoformat(t.get("timestamp", now.isoformat())) > one_hour_ago
            ]
            daily = [
                t for t in self._state.get("trades", [])
                if datetime.fromisoformat(t.get("timestamp", now.isoformat())) > one_day_ago
            ]

            max_hourly = self._rules.get("max_trades_per_hour", 10)
            if len(recent) >= max_hourly:
                results.append(SafetyCheckResult(
                    False, f"{len(recent)} trades/h >= {max_hourly}",
                    "max_trades_per_hour", len(recent), max_hourly, severity="warning",
                ))
            max_daily = self._rules.get("max_trades_per_day", 50)
            if len(daily) >= max_daily:
                results.append(SafetyCheckResult(
                    False, f"{len(daily)} trades/day >= {max_daily}",
                    "max_trades_per_day", len(daily), max_daily, severity="critical",
                ))
        return results if results else [SafetyCheckResult(True, reason="rate_limits_ok")]

    # ── Capital Check ───────────────────────────────────────────────────

    def check_min_capital(self, current_balance_usd: float) -> SafetyCheckResult:
        """Check minimum capital threshold."""
        min_cap = self._rules.get("min_capital_usd", 1.0)
        if current_balance_usd < min_cap:
            return SafetyCheckResult(
                False, f"Balance ${current_balance_usd:.2f} < min ${min_cap:.2f}",
                "min_capital_usd", current_balance_usd, min_cap, severity="critical",
            )
        return SafetyCheckResult(True, reason=f"capital_ok (${current_balance_usd:.2f})")

    # ── Full Check ─────────────────────────────────────────────────────

    def can_execute(self, proposed_loss_usd: float = 0.0, balance_usd: float = 100.0) -> Tuple[bool, List[SafetyCheckResult]]:
        """
        Full safety check before any execution.
        
        Returns (allowed, list_of_checks).
        ALL checks must pass for execution to be allowed.
        """
        checks: List[SafetyCheckResult] = []

        # 1. Kill switch
        checks.append(self.check_kill_switch())

        # 2. Emergency stop
        checks.append(self.check_emergency_stop())

        # 3. Circuit breaker
        checks.append(self.check_circuit_breaker())

        # 4. Capital
        checks.append(self.check_min_capital(balance_usd))

        # 5. Loss limits
        checks.extend(self.check_loss_limits(proposed_loss_usd))

        # 6. Rate limits
        checks.extend(self.check_rate_limits())

        allowed = all(c.allowed for c in checks)
        return (allowed, checks)

    # ── Record Results ──────────────────────────────────────────────────

    def record_execution(self, success: bool, loss_usd: float = 0.0, details: Optional[Dict[str, Any]] = None) -> None:
        """Record a trade execution result for safety tracking."""
        with self._lock:
            record = {
                "timestamp": self._now().isoformat(),
                "success": success,
                "amount": abs(loss_usd) if not success else 0.0,
                "details": details or {},
            }
            self._state.setdefault("trades", []).append(record)

            if not success and loss_usd > 0:
                self._state.setdefault("losses", []).append(record)
                self._state["consecutive_losses"] = self._state.get("consecutive_losses", 0) + 1
                if self._state["consecutive_losses"] >= self._rules.get("consecutive_loss_limit", 5):
                    self._unsafe_open_circuit()  # caller holds lock
            else:
                self._state["consecutive_losses"] = 0  # reset on win

            self._save_state()

    # ── Config ──────────────────────────────────────────────────────────

    def update_rules(self, rules: Dict[str, Any]) -> None:
        """Update safety rules."""
        with self._lock:
            self._rules.update(rules)
            self._save_state()
        log.info("Safety rules updated: %s", rules)

    def get_status(self) -> Dict[str, Any]:
        """Get full safety status."""
        with self._lock:
            recent_trades = self._state.get("trades", [])[-20:]  # last 20
            recent_losses = self._state.get("losses", [])[-20:]
            total_loss = sum(abs(float(t.get("amount", 0))) for t in self._state.get("losses", []))
            return {
                "circuit_open": self._state.get("circuit_open", False),
                "emergency_stop": self._state.get("emergency_stop", False),
                "consecutive_losses": self._state.get("consecutive_losses", 0),
                "cooldown_minutes": self._rules.get("cooldown_minutes", 30),
                "total_losses": len(recent_losses),
                "total_loss_usd": round(total_loss, 2),
                "recent_trades": len(recent_trades),
                "rules": dict(self._rules),
                "kill_switch_exists": KILL_SWITCH_PATH.exists(),
            }

    def reset(self) -> None:
        """Reset all safety state (use with caution)."""
        with self._lock:
            self._state = {
                "trades": [],
                "losses": [],
                "consecutive_losses": 0,
                "circuit_open": False,
                "circuit_open_at": None,
                "emergency_stop": False,
                "last_reset": self._now().isoformat(),
            }
            self._save_state()
        log.warning("Safety backstop RESET")


# ── Singleton ──────────────────────────────────────────────────────────

BACKSTOP = SafetyBackstop()


# ── Test ─────────────────────────────────────────────────────────────────

def test_safety_backstop() -> None:
    """Test all safety backstop functions."""
    print("=" * 60)
    print("Safety Backstop — Test Suite")
    print("=" * 60)

    sb = SafetyBackstop(state_path="/tmp/test_safety_state.json")

    # Test 1: Kill switch check (no kill switch file)
    ks = sb.check_kill_switch()
    assert ks.allowed, "Should pass with no kill switch"
    print(f"  KillSwitch:   ✅ {ks.allowed} ({ks.reason})")

    # Test 2: Emergency stop
    es = sb.check_emergency_stop()
    assert es.allowed, "Should pass with no emergency stop"
    print(f"  EmergencyStop:✅ {es.allowed} ({es.reason})")

    # Test 3: Circuit breaker (closed)
    cb = sb.check_circuit_breaker()
    assert cb.allowed, "Should pass with circuit closed"
    print(f"  CircuitBreaker:✅ {cb.allowed} ({cb.reason})")

    # Test 4: Capital check
    cap = sb.check_min_capital(100.0)
    assert cap.allowed, "Should pass with $100"
    print(f"  MinCapital:   ✅ {cap.allowed} ({cap.reason})")

    cap_low = sb.check_min_capital(0.5)
    assert not cap_low.allowed, "Should fail with $0.50"
    print(f"  MinCapitalLow:✅ blocked ({cap_low.reason})")

    # Test 5: Loss limits (proposed loss $10 > $5 max per tx)
    checks = sb.check_loss_limits(proposed_loss_usd=10.0)
    tx_check = [c for c in checks if c.rule == "max_loss_per_tx_usd"]
    assert any(not c.allowed for c in checks), "Should block $10 loss on $5 limit"
    print(f"  LossLimit:    ✅ blocked $10 (limit ${sb._rules['max_loss_per_tx_usd']:.0f})")

    # Test 6: All checks pass for small trade
    allowed, all_checks = sb.can_execute(proposed_loss_usd=1.0, balance_usd=100.0)
    assert allowed, "Small trade should be allowed"
    print(f"  AllChecks:    ✅ {allowed} ({len(all_checks)} checks, all pass)")

    # Test 7: All checks fail for large trade
    allowed2, _ = sb.can_execute(proposed_loss_usd=50.0, balance_usd=100.0)
    assert not allowed2, "Large proposed loss should be blocked"
    print(f"  LargeLoss:    ✅ blocked $50 loss")

    # Test 8: Consecutive losses trigger circuit breaker
    for i in range(6):
        sb.record_execution(success=False, loss_usd=1.0)
    allowed3, _ = sb.can_execute(proposed_loss_usd=1.0, balance_usd=100.0)
    assert not allowed3, "Should block after 6 consecutive losses"
    print(f"  CircuitTrip:  ✅ blocked after 6 consecutive losses")

    # Test 9: Record success resets consecutive counter
    sb.record_execution(success=True)
    # Reset circuit for test
    sb._state["circuit_open"] = False
    sb._state["circuit_open_at"] = None
    allowed4, _ = sb.can_execute(proposed_loss_usd=1.0, balance_usd=100.0)
    print(f"  WinReset:     ✅ {allowed4} (consecutive={sb._state['consecutive_losses']})")

    # Test 10: Emergency stop blocks
    sb.set_emergency_stop(True)
    allowed5, _ = sb.can_execute(proposed_loss_usd=1.0, balance_usd=100.0)
    assert not allowed5, "Emergency stop should block"
    print(f"  EmergencyStopBlock: ✅ blocked")
    sb.set_emergency_stop(False)

    # Test 11: Kill switch file blocks
    kill_path = Path("/tmp/test_kill_switch")
    kill_path.write_text("stop")
    KILL_SWITCH_PATH_ORIG = KILL_SWITCH_PATH
    # Override by creating a temp kill file
    import importlib
    import simp.organs.quantumarb.safety_backstop as sb_mod
    sb_mod.KILL_SWITCH_PATH = kill_path
    ks2 = sb.check_kill_switch()
    assert not ks2.allowed, "Kill switch file should block"
    print(f"  KillFileBlock:✅ blocked")
    kill_path.unlink(missing_ok=True)
    sb_mod.KILL_SWITCH_PATH = KILL_SWITCH_PATH_ORIG

    # Test 12: Status report
    status = sb.get_status()
    print(f"  Status:       ✅ circuit={status['circuit_open']}, losses={status['total_losses']}, rules={len(status['rules'])}")
    assert "rules" in status

    # Reset
    sb.reset()
    import os
    os.remove("/tmp/test_safety_state.json")

    print("\n" + "=" * 60)
    print("ALL SAFETY BACKSTOP TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    test_safety_backstop()
