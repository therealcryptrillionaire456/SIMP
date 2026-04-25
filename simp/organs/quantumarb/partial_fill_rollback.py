"""
Partial-Fill Rollback Logic — T22
==================================
Not all legs fill atomically. This module adds a dead-man-switch for
incomplete fills with automatic retry or unwind.

When a multi-leg transaction is interrupted (partial fill of some legs),
the PartialFillRollbackHandler:
  1. Detects stuck/unfilled legs via timeout
  2. Attempts retry (up to N attempts)
  3. On max retries exceeded, executes unwind of filled legs
  4. Logs all events to append-only JSONL for audit

Integrates with:
  - TransactionCoordinator: detects partial fills
  - RollbackManager: executes reversals
  - LatencyProfiler: logs timing
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("partial_fill_rollback")


class PartialFillAction(str, Enum):
    """Action taken for a partial fill."""
    RETRYING = "retrying"
    UNWINDING = "unwinding"
    ACCEPTED = "accepted"       # Partial fill accepted (close enough to target)
    TIMEOUT = "timeout"          # No fill progress after timeout
    FAILED = "failed"


@dataclass
class PartialFillEvent:
    """Record of a partial fill event."""
    tx_id: str
    leg_index: int
    venue: str
    symbol: str
    side: str
    target_qty: float
    filled_qty: float
    fill_ratio: float
    action: str                # PartialFillAction value
    retry_attempt: int = 0
    duration_ms: float = 0.0
    error: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PartialFillConfig:
    """Configuration for partial fill handling."""
    min_acceptable_fill_ratio: float = 0.95   # Above this = accepted
    max_retries: int = 3                       # Max retry attempts
    retry_delay_seconds: float = 1.0           # Delay between retries
    leg_timeout_seconds: float = 60.0          # Max time for a leg
    unwind_threshold_ratio: float = 0.10       # Below this → unwind everything


class PartialFillRollbackHandler:
    """
    Handles partial fills with retry/unwind logic.

    Flow per leg:
      1. Wait for fill with timeout
      2. Check fill ratio:
         - >= min_acceptable_fill_ratio → ACCEPTED
         - > 0 but below threshold → retry (up to max_retries)
         - = 0 after timeout → TIMEOUT → unwind
      3. After retries exhausted and still partial → UNWIND completed legs
    """

    def __init__(
        self,
        config: Optional[PartialFillConfig] = None,
        log_dir: str = "data/partial_fill",
        rollback_manager: Optional[Any] = None,
        executor: Optional[Any] = None,
    ):
        self.config = config or PartialFillConfig()
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._events: List[PartialFillEvent] = []
        self._lock = threading.Lock()
        self._rollback_manager = rollback_manager
        self._executor = executor

        # Load existing events
        self._load_events()

        log.info(
            "PartialFillRollbackHandler initialized (min_fill=%.0f%%, max_retries=%d, timeout=%.0fs)",
            self.config.min_acceptable_fill_ratio * 100,
            self.config.max_retries,
            self.config.leg_timeout_seconds,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def handle_partial_fill(
        self,
        tx_id: str,
        leg_index: int,
        venue: str,
        symbol: str,
        side: str,
        target_qty: float,
        filled_qty: float,
        executor_callable: Optional[Any] = None,
    ) -> PartialFillEvent:
        """
        Handle a partial fill with retry/unwind logic.

        Args:
            tx_id: Transaction ID
            leg_index: Index of the leg within the transaction
            venue: Exchange name
            symbol: Trading pair
            side: "buy" or "sell"
            target_qty: Expected quantity
            filled_qty: Currently filled quantity
            executor_callable: Callable that returns (success, filled_qty)

        Returns:
            PartialFillEvent with the action taken
        """
        fill_ratio = filled_qty / target_qty if target_qty > 0 else 0.0
        start_time = time.time()

        # Case 1: Already acceptable
        if fill_ratio >= self.config.min_acceptable_fill_ratio:
            event = PartialFillEvent(
                tx_id=tx_id,
                leg_index=leg_index,
                venue=venue,
                symbol=symbol,
                side=side,
                target_qty=target_qty,
                filled_qty=filled_qty,
                fill_ratio=round(fill_ratio, 4),
                action=PartialFillAction.ACCEPTED.value,
                duration_ms=0.0,
            )
            self._record_event(event)
            return event

        # Case 2: Zero fill → timeout → unwind
        if filled_qty <= 0:
            event = self._handle_timeout(
                tx_id, leg_index, venue, symbol, side, target_qty, filled_qty, fill_ratio,
            )
            return event

        # Case 3: Partial fill below threshold — retry
        current_qty = filled_qty
        for attempt in range(1, self.config.max_retries + 1):
            log.info(
                "Retry %d/%d for leg %d of tx %s (filled %.6f/%.6f, ratio=%.1f%%)",
                attempt, self.config.max_retries, leg_index, tx_id,
                current_qty, target_qty, fill_ratio * 100,
            )

            time.sleep(self.config.retry_delay_seconds)

            if executor_callable:
                try:
                    retry_success, retry_qty = executor_callable(current_qty)
                    if retry_success and retry_qty > current_qty:
                        current_qty = retry_qty
                        fill_ratio = current_qty / target_qty if target_qty > 0 else 0.0
                except Exception as e:
                    log.warning("Retry %d failed for leg %d: %s", attempt, leg_index, e)

            # Check if acceptable now
            if fill_ratio >= self.config.min_acceptable_fill_ratio:
                elapsed = (time.time() - start_time) * 1000
                event = PartialFillEvent(
                    tx_id=tx_id,
                    leg_index=leg_index,
                    venue=venue,
                    symbol=symbol,
                    side=side,
                    target_qty=target_qty,
                    filled_qty=current_qty,
                    fill_ratio=round(fill_ratio, 4),
                    action=PartialFillAction.ACCEPTED.value,
                    retry_attempt=attempt,
                    duration_ms=round(elapsed, 2),
                )
                self._record_event(event)
                return event

        # Retries exhausted — still partial — unwind
        elapsed = (time.time() - start_time) * 1000
        event = PartialFillEvent(
            tx_id=tx_id,
            leg_index=leg_index,
            venue=venue,
            symbol=symbol,
            side=side,
            target_qty=target_qty,
            filled_qty=current_qty,
            fill_ratio=round(fill_ratio, 4),
            action=PartialFillAction.UNWINDING.value,
            retry_attempt=self.config.max_retries,
            duration_ms=round(elapsed, 2),
        )
        self._record_event(event)

        # Execute unwind
        self._execute_unwind(tx_id, venue, symbol, side, current_qty)
        return event

    def recover_stuck_transactions(
        self, active_legs: List[Dict[str, Any]]
    ) -> List[PartialFillEvent]:
        """
        Dead-man-switch recovery: check if any active legs have timed out
        and handle them.

        Args:
            active_legs: List of leg dicts with tx_id, leg_index, venue,
                         symbol, side, target_qty, filled_qty, timestamp

        Returns:
            List of PartialFillEvents for stuck/handled legs
        """
        events = []
        now = time.time()
        for leg in active_legs:
            leg_ts = leg.get("timestamp", "")
            try:
                leg_time = datetime.fromisoformat(leg_ts).timestamp() if leg_ts else now
            except (ValueError, TypeError):
                leg_time = now

            if now - leg_time > self.config.leg_timeout_seconds:
                event = self._handle_timeout(
                    tx_id=leg.get("tx_id", "unknown"),
                    leg_index=leg.get("leg_index", 0),
                    venue=leg.get("venue", "unknown"),
                    symbol=leg.get("symbol", "unknown"),
                    side=leg.get("side", "unknown"),
                    target_qty=float(leg.get("target_qty", 0)),
                    filled_qty=float(leg.get("filled_qty", 0)),
                    fill_ratio=float(leg.get("filled_qty", 0)) / max(float(leg.get("target_qty", 1)), 1),
                )
                events.append(event)
        return events

    # ── Internal Helpers ────────────────────────────────────────────────

    def _handle_timeout(
        self, tx_id: str, leg_index: int, venue: str, symbol: str,
        side: str, target_qty: float, filled_qty: float, fill_ratio: float,
    ) -> PartialFillEvent:
        """Handle a timeout — no fill progress."""
        event = PartialFillEvent(
            tx_id=tx_id,
            leg_index=leg_index,
            venue=venue,
            symbol=symbol,
            side=side,
            target_qty=target_qty,
            filled_qty=filled_qty,
            fill_ratio=round(fill_ratio, 4),
            action=PartialFillAction.TIMEOUT.value,
            error="Leg timed out with no fill progress",
        )
        self._record_event(event)
        # Unwind if anything was filled
        if filled_qty > 0:
            self._execute_unwind(tx_id, venue, symbol, side, filled_qty)
        return event

    def _execute_unwind(
        self, tx_id: str, venue: str, symbol: str,
        side: str, filled_qty: float,
    ) -> bool:
        """Execute reversal/unwind of a partially filled leg."""
        log.warning(
            "UNWIND: tx=%s venue=%s symbol=%s side=%s qty=%.6f",
            tx_id, venue, symbol, side, filled_qty,
        )

        if self._rollback_manager:
            try:
                exec_result = {
                    "success": False,
                    "order_id": f"unwind_{tx_id}",
                    "filled_quantity": filled_qty,
                    "average_price": 0.0,
                    "error_message": "Partial fill unwind",
                    "metadata": {"exchange": venue, "tx_id": tx_id},
                }
                record = self._rollback_manager.evaluate(exec_result)
                return record.reversed
            except Exception as e:
                log.error("Unwind via rollback_manager failed: %s", e)

        if self._executor:
            try:
                from .exchange_connector import OrderSide
                opp_side = OrderSide.SELL if side == "buy" else OrderSide.BUY
                result = self._executor.execute_trade(
                    symbol=symbol,
                    side=opp_side,
                    quantity=filled_qty,
                    trade_id=f"unwind_{tx_id}",
                    exchange_name=venue,
                )
                return result.success
            except Exception as e:
                log.error("Unwind via executor failed: %s", e)
                return False

        log.warning("No rollback_manager or executor available for unwind")
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics for partial fill events."""
        with self._lock:
            events = list(self._events)

        total = len(events)
        by_action: Dict[str, int] = {}
        for e in events:
            by_action[e.action] = by_action.get(e.action, 0) + 1

        # Average fill ratio for unwound events
        unwound = [e for e in events if e.action == PartialFillAction.UNWINDING.value]
        avg_unwind_fill_ratio = (
            sum(e.fill_ratio for e in unwound) / len(unwound) if unwound else 0.0
        )

        return {
            "total_events": total,
            "by_action": by_action,
            "accepted": by_action.get(PartialFillAction.ACCEPTED.value, 0),
            "retried": by_action.get(PartialFillAction.RETRYING.value, 0),
            "unwound": by_action.get(PartialFillAction.UNWINDING.value, 0),
            "timeouts": by_action.get(PartialFillAction.TIMEOUT.value, 0),
            "avg_unwind_fill_ratio": round(avg_unwind_fill_ratio, 4),
            "total_unwound_qty_unwind": len(unwound),
        }

    def recent_events(self, limit: int = 20) -> List[PartialFillEvent]:
        """Return most recent events."""
        with self._lock:
            return list(reversed(self._events[-limit:]))

    # ── Persistence ─────────────────────────────────────────────────────

    def _record_event(self, event: PartialFillEvent) -> None:
        """Thread-safe append to in-memory list and JSONL file."""
        with self._lock:
            self._events.append(event)
            log_path = self._log_dir / "partial_fill_events.jsonl"
            with open(log_path, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")

    def _load_events(self) -> None:
        """Load events from disk on init."""
        log_path = self._log_dir / "partial_fill_events.jsonl"
        if not log_path.exists():
            return
        try:
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    event = PartialFillEvent(**json.loads(line))
                    self._events.append(event)
        except Exception as e:
            log.warning("Failed to load partial fill events: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

PARTIAL_FILL_HANDLER = PartialFillRollbackHandler()
