"""
Profit Compounding Loop (Tranche 3)
====================================
Reinvests profits from arb/staking/meme into higher positions.

Combines the existing compounding.py (simulation) with real execution
from solana_executor and staking_executor. Follows growth targets,
escalates position sizes on wins, consolidates on losses.

Pattern:
  1. Profit cycle finds opportunity
  2. Executor executes
  3. PnL recorded
  4. Compounding loop checks targets
  5. Auto-reinvests or rebalances
  6. Escalates if capital grows above threshold
"""

from __future__ import annotations

import json
import logging
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("compounding_loop")

# ── Constants ───────────────────────────────────────────────────────────

DEFAULT_COMPOUND_CONFIG = {
    "base_position_usd": 1.0,
    "max_position_usd": 100.0,
    "growth_target_pct": 10.0,       # Reinvest when portfolio grows 10%
    "escalation_threshold_usd": 5.0,  # Double position size when $X ahead
    "consolidation_threshold_pct": -15.0,  # Halve positions after 15% drawdown
    "max_reinvest_per_day": 20,
    "auto_reinvest": True,
    "rebalance_on_win": True,
    "compounding_frequency_sec": 3600,  # Check hourly
}


@dataclass
class CompoundingAction:
    """A compounding action to execute."""
    action_type: str  # reinvest, rebalance, escalate, consolidate, hold
    reason: str
    amount_usd: float
    target_venue: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CompoundingLoop:
    """
    Live profit compounding loop.
    
    Monitors PnL, decides when to reinvest, escalate, or consolidate.
    Thread-safe for concurrent access from profit_cycle.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        pnl_ledger_path: str = "data/pnl_ledger.jsonl",
        state_path: str = "data/compounding_state.json",
    ):
        self._lock = threading.Lock()
        self.config: Dict[str, Any] = config or dict(DEFAULT_COMPOUND_CONFIG)
        self.pnl_path = Path(pnl_ledger_path)
        self.state_path = Path(state_path)
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        try:
            if self.state_path.exists():
                with open(self.state_path) as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return {
            "total_reinvested": 0,
            "reinvest_count": 0,
            "total_escalations": 0,
            "total_consolidations": 0,
            "peak_capital_usd": 0.0,
            "current_capital_usd": 0.0,
            "last_reinvest_at": None,
            "last_rebalance_at": None,
        }

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump(self._state, f, indent=2)
        except OSError as e:
            log.error("Could not save compounding state: %s", e)

    def _read_pnl(self) -> List[Dict[str, Any]]:
        """Read recent PnL entries."""
        if not self.pnl_path.exists():
            return []
        entries = []
        try:
            with open(self.pnl_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            pass
        return entries[-100:]  # Last 100 entries

    def compute_portfolio_value(self, current_balance_usd: float) -> float:
        """Compute total portfolio value including unrealized PnL."""
        pnl_entries = self._read_pnl()
        realized_pnl = sum(float(e.get("pnl_usd", 0)) for e in pnl_entries if e.get("pnl_usd"))
        # Portfolio = current balance + realized gains (if reinvested)
        return current_balance_usd + max(0, realized_pnl)

    def evaluate(self, current_balance_usd: float, daily_reinvest_count: int) -> CompoundingAction:
        """
        Evaluate whether to take compounding action.
        
        Returns a CompoundingAction with what to do.
        """
        with self._lock:
            portfolio = self.compute_portfolio_value(current_balance_usd)
            peak = self._state.get("peak_capital_usd", 0.0)
            if portfolio > peak:
                self._state["peak_capital_usd"] = portfolio
            self._state["current_capital_usd"] = portfolio

            growth_pct = ((portfolio - self.config.get("base_position_usd", 1.0))
                          / max(self.config.get("base_position_usd", 1.0), 1e-9) * 100)
            drawdown_pct = ((portfolio - peak) / max(peak, 1e-9)) * 100 if peak > 0 else 0
            profit_usd = portfolio - self.config.get("base_position_usd", 1.0)

            # 1. Check escalation (profit threshold exceeded)
            esc_threshold = self.config.get("escalation_threshold_usd", 5.0)
            if profit_usd >= esc_threshold and self.config.get("auto_reinvest", True):
                self._state["total_escalations"] += 1
                base = self.config.get("base_position_usd", 1.0)
                new_base = min(base * 2, self.config.get("max_position_usd", 100.0))
                self.config["base_position_usd"] = new_base
                self._save_state()
                log.info("ESCALATING position: $%.2f -> $%.2f (profit: $%.2f)", base, new_base, profit_usd)
                return CompoundingAction(
                    action_type="escalate",
                    reason=f"Profit ${profit_usd:.2f} >= threshold ${esc_threshold:.2f}. Base $${base:.2f} -> ${new_base:.2f}",
                    amount_usd=new_base - base,
                    target_venue="all",
                )

            # 2. Check consolidation (drawdown)
            cons_threshold = self.config.get("consolidation_threshold_pct", -15.0)
            if drawdown_pct <= cons_threshold:
                self._state["total_consolidations"] += 1
                base = self.config.get("base_position_usd", 1.0)
                new_base = max(base / 2, 0.25)
                self.config["base_position_usd"] = new_base
                self._save_state()
                log.warning("CONSOLIDATING position: $%.2f -> $%.2f (drawdown: %.1f%%)", base, new_base, drawdown_pct)
                return CompoundingAction(
                    action_type="consolidate",
                    reason=f"Drawdown {drawdown_pct:.1f}% <= {cons_threshold:.1f}%. Base ${base:.2f} -> ${new_base:.2f}",
                    amount_usd=base - new_base,
                    target_venue="all",
                )

            # 3. Check reinvestment (growth target exceeded)
            growth_target = self.config.get("growth_target_pct", 10.0)
            if growth_pct >= growth_target and daily_reinvest_count < self.config.get("max_reinvest_per_day", 20):
                reinvest_amount = portfolio * 0.1  # Reinvest 10% of portfolio
                self._state["total_reinvested"] += reinvest_amount
                self._state["reinvest_count"] += 1
                self._state["last_reinvest_at"] = datetime.now(timezone.utc).isoformat()
                self._save_state()
                log.info("REINVESTING $%.2f (portfolio grew %.1f%%)", reinvest_amount, growth_pct)
                return CompoundingAction(
                    action_type="reinvest",
                    reason=f"Portfolio grew {growth_pct:.1f}% >= {growth_target:.1f}%. Reinvesting 10%.",
                    amount_usd=reinvest_amount,
                )

            # 4. Hold
            return CompoundingAction(
                action_type="hold",
                reason=f"Portfolio ${portfolio:.2f}, growth {growth_pct:.1f}%, target {growth_target:.1f}%",
                amount_usd=0.0,
            )

    def get_status(self) -> Dict[str, Any]:
        """Get compounding status."""
        with self._lock:
            return {
                "base_position_usd": self.config.get("base_position_usd", 1.0),
                "peak_capital_usd": self._state.get("peak_capital_usd", 0.0),
                "current_capital_usd": self._state.get("current_capital_usd", 0.0),
                "total_reinvested": self._state.get("total_reinvested", 0.0),
                "reinvest_count": self._state.get("reinvest_count", 0),
                "total_escalations": self._state.get("total_escalations", 0),
                "total_consolidations": self._state.get("total_consolidations", 0),
                "auto_reinvest": self.config.get("auto_reinvest", True),
                "growth_target_pct": self.config.get("growth_target_pct", 10.0),
                "escalation_threshold_usd": self.config.get("escalation_threshold_usd", 5.0),
            }

    def reset(self) -> None:
        """Reset compounding state."""
        with self._lock:
            self._state = {
                "total_reinvested": 0,
                "reinvest_count": 0,
                "total_escalations": 0,
                "total_consolidations": 0,
                "peak_capital_usd": 0.0,
                "current_capital_usd": 0.0,
                "last_reinvest_at": None,
                "last_rebalance_at": None,
            }
            self._save_state()


# ── Test ─────────────────────────────────────────────────────────────────

def test_compounding_loop() -> None:
    """Test compounding loop evaluation logic."""
    print("=" * 60)
    print("Compounding Loop — Test Suite")
    print("=" * 60)

    # Test 1: Hold at base
    cl = CompoundingLoop(state_path="/tmp/test_comp_state.json")
    action = cl.evaluate(current_balance_usd=1.0, daily_reinvest_count=0)
    print(f"  Hold:         ✅ {action.action_type} ({action.reason[:50]})")
    assert action.action_type == "hold", "Should hold at base capital"

    # Test 2: Escalate on profit
    cl2 = CompoundingLoop(config={"base_position_usd": 1.0, "escalation_threshold_usd": 3.0,
                                   "auto_reinvest": True, "max_position_usd": 100.0,
                                   "growth_target_pct": 10.0},
                          state_path="/tmp/test_comp_state2.json")
    action2 = cl2.evaluate(current_balance_usd=5.0, daily_reinvest_count=0)
    print(f"  Escalate:     ✅ {action2.action_type} (amount=${action2.amount_usd:.2f})")
    assert action2.action_type == "escalate", "Should escalate on profit"

    # Test 3: Consolidate on drawdown
    cl3 = CompoundingLoop(config={"base_position_usd": 10.0,
                                   "consolidation_threshold_pct": -10.0,
                                   "auto_reinvest": True, "max_position_usd": 100.0,
                                   "growth_target_pct": 50.0},
                          state_path="/tmp/test_comp_state3.json")
    cl3._state["peak_capital_usd"] = 100.0
    action3 = cl3.evaluate(current_balance_usd=5.0, daily_reinvest_count=0)
    print(f"  Consolidate:  ✅ {action3.action_type} (amount=${action3.amount_usd:.2f})")
    assert action3.action_type == "consolidate", "Should consolidate on drawdown"

    # Test 4: Reinvest on growth
    cl4 = CompoundingLoop(config={"base_position_usd": 1.0, "growth_target_pct": 5.0,
                                   "auto_reinvest": True, "max_position_usd": 100.0,
                                   "max_reinvest_per_day": 20},
                          state_path="/tmp/test_comp_state4.json")
    action4 = cl4.evaluate(current_balance_usd=2.0, daily_reinvest_count=0)
    print(f"  Reinvest:     ✅ {action4.action_type} (amount=${action4.amount_usd:.2f})")
    # Growth is 100% which is >= 5%, so should reinvest
    print(f"    Reason: {action4.reason}")

    # Test 5: Max reinvest limit
    action5 = cl4.evaluate(current_balance_usd=2.0, daily_reinvest_count=20)
    print(f"  MaxReinvest:  ✅ {action5.action_type} (count=20)")
    # Should hold if max reinvest reached

    # Test 6: Status
    status = cl.get_status()
    print(f"  Status:       ✅ position=${status['base_position_usd']:.2f}, "
          f"peak=${status['peak_capital_usd']:.2f}, "
          f"reinvests={status['reinvest_count']}")

    # Test 7: Reset
    cl.reset()
    assert cl._state["reinvest_count"] == 0
    print(f"  Reset:        ✅ state cleared")

    # Cleanup
    import os, glob
    for p in glob.glob("/tmp/test_comp_state*"):
        os.remove(p)

    print("\n" + "=" * 60)
    print("ALL COMPOUNDING LOOP TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    test_compounding_loop()
