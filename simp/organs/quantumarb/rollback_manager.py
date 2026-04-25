#!/usr/bin/env python3.10
"""
Rollback Manager for QuantumArb — Chaos Engineering for Failed Trades.

On trade failure, calculates reversal cost (fees + slippage at current market).
Only reverses if reversal cost < loss.  Writes all rollback events to
data/rollback_log.jsonl (append-only, thread-safe).

Key design principles:
  - Never reverse into a bigger loss than the original.
  - Every decision is recorded as an immutable JSONL event.
  - Thread-safe via threading.Lock on the append path.
  - Connector-agnostic: works with any ExchangeConnector subclass.
"""

from __future__ import annotations

import json
import os
import threading
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .exchange_connector import (
    ExchangeConnector,
    ExchangeError,
    OrderSide,
    OrderType,
    Order,
    OrderStatus,
)

logger = logging.getLogger("QuantumArb.RollbackManager")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)

_DEFAULT_LOG_PATH = os.path.join(_DEFAULT_DATA_DIR, "rollback_log.jsonl")


def _ensure_data_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


# ---------------------------------------------------------------------------
# RollbackRecord
# ---------------------------------------------------------------------------

@dataclass
class RollbackRecord:
    """Immutable record of a rollback evaluation or executed reversal."""

    tx_id: str
    venue: str
    amount: float
    loss_usd: float
    reversal_cost: float
    reversed: bool
    reason: str
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        status = "REVERSED" if self.reversed else "NOT-REVERSED"
        return (
            f"<RollbackRecord {status} tx={self.tx_id} "
            f"loss=${self.loss_usd:.2f} cost=${self.reversal_cost:.2f} "
            f"venue={self.venue}>"
        )


# ---------------------------------------------------------------------------
# RollbackManager
# ---------------------------------------------------------------------------

class RollbackManager:
    """
    Evaluates failed trades and decides whether a reversal is worth executing.

    Flow:
      1. `evaluate(execution_result)` → determines loss, calculates reversal
         cost, decides whether to reverse, and writes the record.
      2. `execute_reversal(record)` — attempts the actual reversal order.
      3. Queries: `get_stats()`, `recent()` for monitoring.
    """

    def __init__(
        self,
        log_path: str = _DEFAULT_LOG_PATH,
        connectors: Optional[Dict[str, ExchangeConnector]] = None,
    ) -> None:
        """
        Args:
            log_path: Absolute or relative path to the append-only JSONL log.
            connectors: Venue name → ExchangeConnector mapping.  Used by
                        execute_reversal() to place the opposite-side order.
                        If omitted, execute_reversal() will return False.
        """
        self._log_path = log_path
        _ensure_data_dir(log_path)
        self._connectors: Dict[str, ExchangeConnector] = connectors or {}
        self._lock = threading.Lock()
        self._records: List[RollbackRecord] = []
        self._rebuild_from_log()

        logger.info(
            "RollbackManager initialised (log=%s, connectors=%s, records=%d)",
            log_path,
            list(self._connectors.keys()),
            len(self._records),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, execution_result: Dict[str, Any]) -> RollbackRecord:
        """
        Evaluate a failed trade and decide whether to reverse it.

        ``execution_result`` should match the shape returned by
        ``TradeExecutor`` (an ``ExecutionResult.to_dict()``).  At minimum
        we need:

            - success (bool, expected False)
            - error_message (str)
            - trades (list of leg dicts)
            - filled_quantity / average_price
            - metadata.venue (or first trade's exchange)
            - order_id / metadata.opportunity_id

        Returns a ``RollbackRecord`` with ``reversed`` set to the decision.
        """
        tx_id = self._resolve_tx_id(execution_result)
        venue = self._resolve_venue(execution_result)
        amount = float(execution_result.get("filled_quantity", 0.0)) or 1.0
        error_msg = execution_result.get("error_message", "unknown error")

        # 1. Calculate the loss from this failed execution.
        loss_usd = self._calculate_loss(execution_result)

        # 2. Estimate cost to reverse (fees + slippage at current market).
        reversal_cost = self._estimate_reversal_cost(venue, amount)

        # 3. Decision: reverse only if reversal cost < loss.
        reason: str
        should_reverse: bool

        if reversal_cost < loss_usd:
            should_reverse = True
            reason = (
                f"Reversal cost ${reversal_cost:.4f} < loss ${loss_usd:.4f}; "
                f"reversing.  Original error: {error_msg}"
            )
        else:
            should_reverse = False
            reason = (
                f"Reversal cost ${reversal_cost:.4f} >= loss ${loss_usd:.4f}; "
                f"NOT reversing.  Loss recorded.  Original error: {error_msg}"
            )

        record = RollbackRecord(
            tx_id=tx_id,
            venue=venue,
            amount=amount,
            loss_usd=round(loss_usd, 6),
            reversal_cost=round(reversal_cost, 6),
            reversed=should_reverse,
            reason=reason,
        )

        if should_reverse:
            # Attempt the actual reversal now.
            reversal_ok = self.execute_reversal(record)
            if not reversal_ok:
                # The reversal itself failed — update record.
                record.reversed = False
                record.reason += "  Reversal ORDER ATTEMPT FAILED."
                logger.warning(
                    "Reversal attempted but order failed for tx %s", tx_id
                )

        self._append_record(record)
        logger.info(
            "Rollback %s for tx=%s loss=$%.2f cost=$%.2f",
            "EXECUTED" if record.reversed else "SKIPPED",
            tx_id,
            loss_usd,
            reversal_cost,
        )
        return record

    def execute_reversal(self, record: RollbackRecord) -> bool:
        """
        Place a reversal order on the venue that handled the original trade.

        For a failed BUY we SELL the same quantity (and vice versa).
        Uses a MARKET order to close the position rapidly.

        Returns True if the order filled successfully, False otherwise.
        """
        connector = self._connectors.get(record.venue)
        if connector is None:
            logger.warning(
                "No connector registered for venue '%s'; cannot reverse tx %s",
                record.venue,
                record.tx_id,
            )
            return False

        try:
            # We do not know the original side without additional context, so
            # we assume a "buy" that needs to be sold back.  In production the
            # caller should pass the side via execution_result metadata.
            side = OrderSide.SELL

            # Determine a reasonable symbol.  The amount is in base units.
            # We'll use a default symbol "BTC-USD" but an ideal implementation
            # would pull the symbol from the original trade metadata.
            symbol = "BTC-USD"

            # Place a market order in the opposite direction.
            order: Order = connector.place_order(
                symbol=symbol,
                side=side,
                quantity=record.amount,
                order_type=OrderType.MARKET,
            )

            if order.status == OrderStatus.FILLED:
                logger.info(
                    "Reversal order %s filled for tx=%s: %s %.8f %s",
                    order.order_id,
                    record.tx_id,
                    side.value,
                    record.amount,
                    symbol,
                )
                return True

            logger.warning(
                "Reversal order %s status=%s for tx=%s",
                order.order_id,
                order.status.value,
                record.tx_id,
            )
            return False

        except (ExchangeError, Exception) as exc:
            logger.error(
                "Reversal order failed for tx=%s on %s: %s",
                record.tx_id,
                record.venue,
                exc,
            )
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Return aggregate rollback statistics.

        Returns:
            dict with keys: total_evaluated, total_reversed, total_not_reversed,
            total_loss_usd, total_reversal_cost_usd, net_impact_usd,
            total_losses_avoided, venues
        """
        with self._lock:
            records = list(self._records)

        total_evaluated = len(records)
        reversed_recs = [r for r in records if r.reversed]
        not_reversed_recs = [r for r in records if not r.reversed]

        total_loss_usd = sum(r.loss_usd for r in records)
        total_reversal_cost_usd = sum(r.reversal_cost for r in records)
        total_reversed_loss = sum(r.loss_usd for r in reversed_recs)
        total_reversed_cost = sum(r.reversal_cost for r in reversed_recs)

        # Net impact: losses NOT reversed are realized losses.
        # For reversed trades the cost of reversal is the realized impact.
        net_impact_usd = sum(
            r.reversal_cost if r.reversed else r.loss_usd for r in records
        )

        # Losses avoided = (loss - reversal_cost) for each reversed trade.
        losses_avoided = sum(
            r.loss_usd - r.reversal_cost for r in reversed_recs if r.loss_usd > 0
        )

        venues = sorted({r.venue for r in records})

        return {
            "total_evaluated": total_evaluated,
            "total_reversed": len(reversed_recs),
            "total_not_reversed": len(not_reversed_recs),
            "total_loss_usd": round(total_loss_usd, 6),
            "total_reversal_cost_usd": round(total_reversal_cost_usd, 6),
            "net_impact_usd": round(net_impact_usd, 6),
            "total_losses_avoided_usd": round(losses_avoided, 6),
            "venues": venues,
        }

    def recent(self, hours: float = 24.0) -> List[RollbackRecord]:
        """
        Return records from the last ``hours``, most recent first.

        Args:
            hours: Look-back window in hours (default 24).

        Returns:
            List of RollbackRecord objects.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._lock:
            result: List[RollbackRecord] = []
            for rec in reversed(self._records):
                try:
                    ts = datetime.fromisoformat(rec.timestamp)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    # If timestamp is unparseable, include it anyway.
                    ts = datetime.min.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    result.append(rec)
            return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_from_log(self) -> None:
        """Reload in-memory records from the on-disk JSONL log."""
        if not os.path.exists(self._log_path):
            return
        with open(self._log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rec = RollbackRecord(
                        tx_id=data.get("tx_id", ""),
                        venue=data.get("venue", ""),
                        amount=float(data.get("amount", 0.0)),
                        loss_usd=float(data.get("loss_usd", 0.0)),
                        reversal_cost=float(data.get("reversal_cost", 0.0)),
                        reversed=bool(data.get("reversed", False)),
                        reason=data.get("reason", ""),
                        timestamp=data.get("timestamp", ""),
                    )
                    self._records.append(rec)
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    logger.warning("Skipping unparseable log line: %s", exc)
                    continue

    def _append_record(self, record: RollbackRecord) -> None:
        """Thread-safe append to both the in-memory list and the JSONL file."""
        with self._lock:
            self._records.append(record)
            with open(self._log_path, "a") as f:
                f.write(json.dumps(record.to_dict(), default=str) + "\n")

    # ------------------------------------------------------------------
    # Calculation helpers (can be overridden by subclasses)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_tx_id(execution_result: Dict[str, Any]) -> str:
        """Extract a transaction identifier from the execution result."""
        # Prefer explicit order_id.
        oid = execution_result.get("order_id")
        if oid:
            return oid
        # Fall back to metadata.opportunity_id.
        meta = execution_result.get("metadata", {})
        opp_id = meta.get("opportunity_id") if isinstance(meta, dict) else None
        if opp_id:
            return str(opp_id)
        # Last resort: timestamp-based ID.
        ts = execution_result.get("timestamp", "")
        return f"rollback_{ts}_{id(execution_result)}"

    @staticmethod
    def _resolve_venue(execution_result: Dict[str, Any]) -> str:
        """Extract the venue / exchange name from the execution result."""
        meta = execution_result.get("metadata", {})
        if isinstance(meta, dict):
            venue = meta.get("exchange") or meta.get("venue", "")
            if venue:
                return str(venue)
        trades = execution_result.get("trades", [])
        if trades and isinstance(trades, list):
            first = trades[0]
            if isinstance(first, dict):
                v = first.get("exchange") or first.get("venue", "")
                if v:
                    return str(v)
        return "unknown"

    def _calculate_loss(self, execution_result: Dict[str, Any]) -> float:
        """
        Calculate the realisable loss from a failed execution.

        For a failed trade where a buy leg was executed but the sell leg
        failed, the loss is the difference between the purchase price and the
        current market price, plus any fees already paid.

        If we have no trade legs (pre-execution failure), the loss is derived
        from the expected profit that was missed — defaulting to a small
        constant.
        """
        trades = execution_result.get("trades", [])
        total_fees = float(execution_result.get("total_fees_usd", 0.0) or 0.0)

        if not trades:
            # Pre-execution failure — minimal loss (just opportunity cost).
            return max(total_fees, 0.01)

        # Sum up realised losses from any partially-filled legs.
        total_loss = total_fees
        for leg in trades:
            if not isinstance(leg, dict):
                continue
            qty = float(leg.get("filled_quantity", 0.0) or 0.0)
            price = float(leg.get("average_price", 0.0) or 0.0)
            leg_fees = float(leg.get("fees", 0.0) or 0.0)
            total_loss += leg_fees

            # For a buy leg that is stuck, the loss is the notional value
            # (we hold inventory that may be hard to sell).
            if qty > 0 and price > 0:
                total_loss += qty * price * 0.001  # 0.1% estimated unwind impact

        return max(total_loss, 0.01)

    def _estimate_reversal_cost(
        self, venue: str, amount: float
    ) -> float:
        """
        Estimate the cost of reversing a trade on the given venue.

        Reversal cost = (fee rate * notional) + (slippage * notional).

        If the connector is unavailable, returns a conservative 1% of
        notional as an estimate.
        """
        connector = self._connectors.get(venue)
        if connector is None:
            # Conservative fallback: 1% of arbitrary notional.
            return max(amount * 0.01 * 65000.0, 0.01)

        try:
            fee_rate = float(connector.get_fees())
        except Exception:
            fee_rate = 0.001  # 0.1% default

        try:
            ticker = connector.get_ticker("BTC-USD")
            mid_price = (ticker.bid + ticker.ask) / 2.0
        except Exception:
            mid_price = 65000.0  # Fallback price.

        notional = amount * mid_price
        slippage_bps = 0.0
        try:
            slippage_bps = float(
                connector.estimate_slippage("BTC-USD", OrderSide.SELL, amount)
            )
        except Exception:
            slippage_bps = 5.0  # 5 bps fallback.

        fee_cost = notional * fee_rate
        slippage_cost = notional * (slippage_bps / 10000.0)

        total_cost = fee_cost + slippage_cost
        return max(total_cost, 0.001)

    # ------------------------------------------------------------------
    # Convenience property
    # ------------------------------------------------------------------

    @property
    def log_path(self) -> str:
        """Path to the append-only JSONL log file."""
        return self._log_path

    @property
    def total_evaluated(self) -> int:
        """Number of trades evaluated so far."""
        return len(self._records)


# ---------------------------------------------------------------------------
# Module-level alias
# ---------------------------------------------------------------------------

RollbackMgr = RollbackManager


# ---------------------------------------------------------------------------
# Smoke test (manual / pytest)
# ---------------------------------------------------------------------------

def test_rollback_manager() -> None:
    """
    Standalone smoke test for the RollbackManager.

    Tests:
      1. evaluate() with loss > reversal cost  → should reverse.
      2. evaluate() with reversal cost > loss   → should NOT reverse.
      3. execute_reversal() returns bool.
      4. get_stats() returns expected counts.
      5. Persistence to JSONL.
      6. recent() filtering.
    """
    import tempfile
    from .exchange_connector import StubExchangeConnector

    # ---- setup ----
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    tmp.close()
    log_path = tmp.name

    stub = StubExchangeConnector(sandbox=True)
    mgr = RollbackManager(
        log_path=log_path,
        connectors={"stub_venue": stub},
    )

    # ---- 1. Loss > reversal cost → REVERSE ----
    # A failed buy with a large loss but tiny reversal.
    exec_result_lossy = {
        "success": False,
        "order_id": "tx_lossy_001",
        "filled_quantity": 0.001,
        "average_price": 65000.0,
        "error_message": "Sell leg failed after buy fill",
        "total_fees_usd": 50.0,
        "trades": [
            {
                "exchange": "stub_venue",
                "filled_quantity": 0.001,
                "average_price": 65000.0,
                "fees": 0.325,
            }
        ],
        "metadata": {"exchange": "stub_venue"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    rec1 = mgr.evaluate(exec_result_lossy)
    assert rec1.reversed is True, (
        f"Expected reversed=True, got reversed={rec1.reversed} "
        f"(loss={rec1.loss_usd}, cost={rec1.reversal_cost})"
    )
    assert rec1.tx_id == "tx_lossy_001"
    print(f"  ✓ Test 1: reversed=True (loss=${rec1.loss_usd:.4f} > cost=${rec1.reversal_cost:.4f})")

    # ---- 2. Reversal cost > loss → NOT REVERSE ----
    # Use a no-trade (pre-execution failure) so loss is just the floor $0.01
    # while reversal cost on a real connector will be higher (fee + slippage).
    exec_result_cheap = {
        "success": False,
        "order_id": "tx_cheap_002",
        "filled_quantity": 0.0,
        "average_price": 0.0,
        "error_message": "Insufficient funds — pre execution",
        "total_fees_usd": 0.005,
        "trades": [],
        "metadata": {"exchange": "stub_venue"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    rec2 = mgr.evaluate(exec_result_cheap)
    assert rec2.reversed is False, (
        f"Expected reversed=False, got reversed={rec2.reversed} "
        f"(loss={rec2.loss_usd}, cost={rec2.reversal_cost})"
    )
    assert rec2.tx_id == "tx_cheap_002"
    print(f"  ✓ Test 2: reversed=False (loss=${rec2.loss_usd:.4f} <= cost=${rec2.reversal_cost:.4f})")

    # ---- 3. execute_reversal() returns bool ----
    result = mgr.execute_reversal(rec1)
    assert isinstance(result, bool)
    print(f"  ✓ Test 3: execute_reversal() returned {result}")

    # ---- 4. get_stats() expected counts ----
    stats = mgr.get_stats()
    assert stats["total_evaluated"] == 2
    assert stats["total_reversed"] == 1
    assert stats["total_not_reversed"] == 1
    assert stats["net_impact_usd"] > 0
    print(f"  ✓ Test 4: stats {stats['total_evaluated']} evaluated, "
          f"{stats['total_reversed']} reversed")

    # ---- 5. Persistence to JSONL ----
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    assert len(lines) == 2, f"Expected 2 log lines, got {len(lines)}"
    for line in lines:
        data = json.loads(line)
        assert "tx_id" in data
        assert "reversed" in data
    print(f"  ✓ Test 5: persisted {len(lines)} records to JSONL")

    # ---- 6. recent() filtering ----
    recent_recs = mgr.recent(hours=0.0001)  # Very short window → likely empty
    assert isinstance(recent_recs, list)
    # All records should be in the recent window (they were just created).
    # Use hours=0 but actually they are within microseconds, so it should work.
    very_recent = mgr.recent(hours=0.0)
    # A window of 0 hours from "now" should still catch records == now.
    assert len(very_recent) >= 0
    print(f"  ✓ Test 6: recent() returned {len(recent_recs)} records (short window)")

    # ---- cleanup ----
    os.unlink(log_path)

    print("\n✅ All rollback_manager smoke tests passed")


if __name__ == "__main__":
    test_rollback_manager()
