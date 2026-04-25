"""
Tests for QuantumArb RollbackManager — T20 Chaos Engineering.

Tests cover:
  1. evaluate() with loss > reversal cost → reversed=True
  2. evaluate() with reversal cost > loss → reversed=False
  3. execute_reversal() returns bool
  4. get_stats() expected counts
  5. Persistence to JSONL (append-only)
  6. recent() time-based filtering
"""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from simp.organs.quantumarb.rollback_manager import (
    RollbackManager,
    RollbackRecord,
)
from simp.organs.quantumarb.exchange_connector import StubExchangeConnector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_log() -> str:
    """Yield a temporary JSONL file path that is cleaned up after the test."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    tmp.close()
    yield tmp.name
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


@pytest.fixture
def stub_connector() -> StubExchangeConnector:
    """Return a fresh StubExchangeConnector in sandbox mode."""
    return StubExchangeConnector(sandbox=True, simulated_latency_ms=0)


@pytest.fixture
def mgr(temp_log: str, stub_connector: StubExchangeConnector) -> RollbackManager:
    """Return a RollbackManager wired to a temp log and stub connector."""
    return RollbackManager(
        log_path=temp_log,
        connectors={"stub_venue": stub_connector},
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _lossy_result(order_id: str, venue: str = "stub_venue") -> dict:
    """Build an execution result where the buy leg filled but sell leg failed."""
    return {
        "success": False,
        "order_id": order_id,
        "filled_quantity": 0.001,
        "average_price": 65000.0,
        "error_message": "Sell leg failed after buy fill",
        "total_fees_usd": 50.0,
        "trades": [
            {
                "exchange": venue,
                "filled_quantity": 0.001,
                "average_price": 65000.0,
                "fees": 0.325,
            }
        ],
        "metadata": {"exchange": venue},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _cheap_result(order_id: str, venue: str = "stub_venue") -> dict:
    """Build an execution result that failed pre-execution (no trades)."""
    return {
        "success": False,
        "order_id": order_id,
        "filled_quantity": 0.0,
        "average_price": 0.0,
        "error_message": "Insufficient funds — pre execution",
        "total_fees_usd": 0.005,
        "trades": [],
        "metadata": {"exchange": venue},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRollbackManager:
    """Test suite for RollbackManager."""

    def test_evaluate_reverses_when_loss_exceeds_cost(
        self, mgr: RollbackManager
    ) -> None:
        """Test 1: loss > reversal cost → reversed=True."""
        rec = mgr.evaluate(_lossy_result("tx_a"))
        assert rec.reversed is True, (
            f"Expected reversal (loss=${rec.loss_usd:.4f} > "
            f"cost=${rec.reversal_cost:.4f})"
        )
        assert rec.tx_id == "tx_a"
        assert rec.venue == "stub_venue"
        assert rec.loss_usd > rec.reversal_cost
        # Reversal cost should be positive and sane
        assert rec.reversal_cost > 0

    def test_evaluate_skips_when_cost_exceeds_loss(
        self, mgr: RollbackManager
    ) -> None:
        """Test 2: reversal cost > loss → reversed=False."""
        rec = mgr.evaluate(_cheap_result("tx_b"))
        assert rec.reversed is False, (
            f"Expected no reversal (loss=${rec.loss_usd:.4f} <= "
            f"cost=${rec.reversal_cost:.4f})"
        )
        assert rec.tx_id == "tx_b"
        assert rec.reversal_cost > rec.loss_usd

    def test_execute_reversal_returns_bool(
        self, mgr: RollbackManager
    ) -> None:
        """Test 3: execute_reversal() returns a bool."""
        rec = mgr.evaluate(_lossy_result("tx_c"))
        result = mgr.execute_reversal(rec)
        assert isinstance(result, bool)

    def test_get_stats_expected_counts(
        self, mgr: RollbackManager
    ) -> None:
        """Test 4: get_stats() returns correct counts after multiple evals."""
        mgr.evaluate(_lossy_result("tx_d1"))
        mgr.evaluate(_lossy_result("tx_d2"))
        mgr.evaluate(_cheap_result("tx_d3"))

        stats = mgr.get_stats()
        assert stats["total_evaluated"] == 3
        assert stats["total_reversed"] == 2  # two lossy results
        assert stats["total_not_reversed"] == 1  # one cheap
        assert stats["net_impact_usd"] > 0
        assert "stub_venue" in stats["venues"]

    def test_persistence_to_jsonl(
        self, temp_log: str, stub_connector: StubExchangeConnector
    ) -> None:
        """Test 5: records are persisted to the JSONL file (append-only)."""
        mgr1 = RollbackManager(
            log_path=temp_log,
            connectors={"stub_venue": stub_connector},
        )
        mgr1.evaluate(_lossy_result("tx_e1"))
        mgr1.evaluate(_cheap_result("tx_e2"))
        assert mgr1.total_evaluated == 2

        # Reopen with a fresh instance — should rehydrate from JSONL
        mgr2 = RollbackManager(
            log_path=temp_log,
            connectors={"stub_venue": stub_connector},
        )
        assert mgr2.total_evaluated == 2

        # Append a third record
        mgr2.evaluate(_lossy_result("tx_e3"))
        assert mgr2.total_evaluated == 3

        # Verify file content
        with open(temp_log, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 3

        # Confirm tx_ids round-trip
        tx_ids = {json.loads(line)["tx_id"] for line in lines}
        assert tx_ids == {"tx_e1", "tx_e2", "tx_e3"}

    def test_recent_filtering(
        self, mgr: RollbackManager
    ) -> None:
        """Test 6: recent() returns only records within the time window."""
        mgr.evaluate(_lossy_result("tx_f1"))
        mgr.evaluate(_cheap_result("tx_f2"))

        # All records were just created — should appear in a wide window.
        wide = mgr.recent(hours=24)
        assert len(wide) == 2
        assert all(isinstance(r, RollbackRecord) for r in wide)

        # Use the timestamp of the most recent record to construct
        # a cutoff that is definitely before it (microsecond offset).
        most_recent_ts = wide[0].timestamp
        recent_dt = datetime.fromisoformat(most_recent_ts)
        age_hours = (datetime.now(timezone.utc) - recent_dt).total_seconds() / 3600
        # A window slightly wider than the age should include it.
        just_wide_enough = mgr.recent(hours=age_hours + 0.1)
        assert len(just_wide_enough) >= 1

        # A window of 0 hours will only include records with timestamps
        # exactly equal to 'now', which is improbable for already-created records.
        zero_window = mgr.recent(hours=0)
        assert len(zero_window) == 0

        # Negative window (effectively no records in the future).
        negative_window = mgr.recent(hours=-1)
        assert len(negative_window) == 0

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_stats(self, temp_log: str) -> None:
        """A fresh manager returns zeroed stats."""
        mgr = RollbackManager(log_path=temp_log)
        stats = mgr.get_stats()
        assert stats["total_evaluated"] == 0
        assert stats["total_reversed"] == 0
        assert stats["total_not_reversed"] == 0
        assert stats["net_impact_usd"] == 0.0

    def test_execute_reversal_no_connector(
        self, temp_log: str
    ) -> None:
        """execute_reversal returns False when no connector is registered."""
        mgr = RollbackManager(log_path=temp_log)
        rec = RollbackRecord(
            tx_id="orphan",
            venue="nonexistent",
            amount=1.0,
            loss_usd=10.0,
            reversal_cost=1.0,
            reversed=True,
            reason="test",
        )
        result = mgr.execute_reversal(rec)
        assert result is False

    def test_record_via_execute_reversal_remains_persistent(
        self, mgr: RollbackManager, temp_log: str
    ) -> None:
        """Even if execute_reversal fails, the rollback record stays in log."""
        # Evaluate — this automatically tries reversal and persists.
        mgr.evaluate(_lossy_result("tx_g"))
        with open(temp_log, "r") as f:
            content = f.read()
        assert "tx_g" in content

    def test_record_fields_present(
        self, mgr: RollbackManager
    ) -> None:
        """RollbackRecord has all expected fields."""
        rec = mgr.evaluate(_lossy_result("tx_h"))
        assert rec.tx_id == "tx_h"
        assert isinstance(rec.venue, str) and rec.venue
        assert isinstance(rec.amount, float) and rec.amount > 0
        assert isinstance(rec.loss_usd, float) and rec.loss_usd > 0
        assert isinstance(rec.reversal_cost, float) and rec.reversal_cost > 0
        assert isinstance(rec.reversed, bool)
        assert isinstance(rec.reason, str) and rec.reason
        assert isinstance(rec.timestamp, str) and rec.timestamp

    def test_multiple_venues(
        self, temp_log: str
    ) -> None:
        """Manager handles multiple venues in stats."""
        stub_a = StubExchangeConnector(sandbox=True, simulated_latency_ms=0)
        stub_b = StubExchangeConnector(sandbox=True, simulated_latency_ms=0)
        mgr = RollbackManager(
            log_path=temp_log,
            connectors={"venue_a": stub_a, "venue_b": stub_b},
        )
        mgr.evaluate(_lossy_result("tx_i1", venue="venue_a"))
        mgr.evaluate(_cheap_result("tx_i2", venue="venue_b"))

        stats = mgr.get_stats()
        assert set(stats["venues"]) == {"venue_a", "venue_b"}
        assert stats["total_evaluated"] == 2
