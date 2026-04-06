"""Tests for simp.compat.live_ledger — Sprint 44."""

import json
import pytest
from simp.compat.live_ledger import LiveSpendLedger, LiveSpendRecord


@pytest.fixture
def ledger(tmp_path):
    return LiveSpendLedger(ledger_path=str(tmp_path / "test_live.jsonl"))


# ---------------------------------------------------------------------------
# record_live_spend
# ---------------------------------------------------------------------------

class TestRecordLiveSpend:
    def test_basic_record(self, ledger):
        rec = ledger.record_live_spend(
            proposal_id="prop-1", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=9.99, reference_id="ref-001",
        )
        assert rec is not None
        assert rec.proposal_id == "prop-1"
        assert rec.status == "completed"
        assert rec.amount == 9.99

    def test_idempotency_guard(self, ledger):
        ledger.record_live_spend(
            proposal_id="prop-1", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=9.99, reference_id="ref-001",
        )
        dup = ledger.record_live_spend(
            proposal_id="prop-1", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=9.99, reference_id="ref-002",
        )
        assert dup is None  # Silently ignored

    def test_different_proposals_allowed(self, ledger):
        r1 = ledger.record_live_spend(
            proposal_id="prop-1", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=5.0, reference_id="ref-001",
        )
        r2 = ledger.record_live_spend(
            proposal_id="prop-2", connector_name="stripe_small_payments",
            vendor="aws", category="software_subscription",
            amount=8.0, reference_id="ref-002",
        )
        assert r1 is not None
        assert r2 is not None

    def test_persists_to_file(self, ledger, tmp_path):
        ledger.record_live_spend(
            proposal_id="prop-1", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=5.0, reference_id="ref-001",
        )
        path = tmp_path / "test_live.jsonl"
        content = path.read_text()
        assert "prop-1" in content
        data = json.loads(content.strip())
        assert data["status"] == "completed"


# ---------------------------------------------------------------------------
# record_failed_spend
# ---------------------------------------------------------------------------

class TestRecordFailedSpend:
    def test_basic_failure(self, ledger):
        rec = ledger.record_failed_spend(
            proposal_id="prop-fail", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=10.0, error="Connection timeout",
        )
        assert rec.status == "failed"
        assert rec.error == "Connection timeout"

    def test_failed_does_not_block_idempotency(self, ledger):
        """A failed record for a proposal should not block re-execution."""
        ledger.record_failed_spend(
            proposal_id="prop-retry", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=10.0, error="timeout",
        )
        # Failed spend does NOT add to _seen_proposals, so live spend still works
        rec = ledger.record_live_spend(
            proposal_id="prop-retry", connector_name="stripe_small_payments",
            vendor="github", category="software_subscription",
            amount=10.0, reference_id="ref-retry",
        )
        assert rec is not None


# ---------------------------------------------------------------------------
# record_refund
# ---------------------------------------------------------------------------

class TestRecordRefund:
    def test_basic_refund(self, ledger):
        rec = ledger.record_refund(
            proposal_id="prop-1", connector_name="stripe_small_payments",
            vendor="github", amount=5.0, reference_id="refund-ref-1",
            reason="Customer request",
        )
        assert rec.status == "refunded"
        assert rec.category == "refund"


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestLedgerSummary:
    def test_empty_summary(self, ledger):
        s = ledger.get_summary()
        assert s["total_records"] == 0
        assert s["total_spent"] == 0.0

    def test_summary_counts(self, ledger):
        ledger.record_live_spend("p1", "stripe_small_payments", "github", "sw", 10.0, "r1")
        ledger.record_live_spend("p2", "stripe_small_payments", "aws", "sw", 5.0, "r2")
        ledger.record_failed_spend("p3", "stripe_small_payments", "heroku", "sw", 8.0, "error")
        ledger.record_refund("p1", "stripe_small_payments", "github", 3.0, "refund-r1", "partial")
        s = ledger.get_summary()
        assert s["completed_count"] == 2
        assert s["failed_count"] == 1
        assert s["refunded_count"] == 1
        assert s["total_spent"] == 15.0
        assert s["total_refunded"] == 3.0
        assert s["net_spent"] == 12.0


# ---------------------------------------------------------------------------
# is_proposal_already_executed
# ---------------------------------------------------------------------------

class TestIdempotencyCheck:
    def test_not_executed(self, ledger):
        assert ledger.is_proposal_already_executed("nonexistent") is False

    def test_executed(self, ledger):
        ledger.record_live_spend("p1", "stripe_small_payments", "github", "sw", 5.0, "r1")
        assert ledger.is_proposal_already_executed("p1") is True


# ---------------------------------------------------------------------------
# export_jsonl
# ---------------------------------------------------------------------------

class TestExportJsonl:
    def test_empty_export(self, ledger):
        assert ledger.export_jsonl() == ""

    def test_export_content(self, ledger):
        ledger.record_live_spend("p1", "stripe_small_payments", "github", "sw", 5.0, "r1")
        raw = ledger.export_jsonl()
        assert "p1" in raw
        lines = [l for l in raw.strip().split("\n") if l]
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# LiveSpendRecord
# ---------------------------------------------------------------------------

class TestLiveSpendRecord:
    def test_to_dict(self):
        rec = LiveSpendRecord(
            record_id="r1", proposal_id="p1", connector_name="stripe",
            vendor="github", category="sw", amount=10.0, currency="USD",
            reference_id="ref-1", timestamp="2025-01-01T00:00:00Z",
            status="completed",
        )
        d = rec.to_dict()
        assert d["record_id"] == "r1"
        assert d["amount"] == 10.0
        assert d["status"] == "completed"

    def test_no_sensitive_fields(self):
        rec = LiveSpendRecord(
            record_id="r1", proposal_id="p1", connector_name="stripe",
            vendor="github", category="sw", amount=10.0, currency="USD",
            reference_id="ref-1", timestamp="2025-01-01T00:00:00Z",
            status="completed",
        )
        raw = json.dumps(rec.to_dict())
        # No PAN, card number, token, secret in output
        for sensitive in ['"pan"', '"card_number"', '"secret"', '"token"']:
            assert sensitive not in raw.lower()


# ---------------------------------------------------------------------------
# Reload from file (idempotency on restart)
# ---------------------------------------------------------------------------

class TestReloadIdempotency:
    def test_reload_preserves_seen_proposals(self, tmp_path):
        path = str(tmp_path / "reload_test.jsonl")
        ledger1 = LiveSpendLedger(ledger_path=path)
        ledger1.record_live_spend("p1", "stripe", "github", "sw", 5.0, "r1")

        # Create new ledger pointing at same file
        ledger2 = LiveSpendLedger(ledger_path=path)
        assert ledger2.is_proposal_already_executed("p1") is True
        dup = ledger2.record_live_spend("p1", "stripe", "github", "sw", 5.0, "r2")
        assert dup is None  # Idempotency preserved across restart
