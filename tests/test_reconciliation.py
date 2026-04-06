"""Tests for simp.compat.reconciliation — Sprint 45."""

import pytest
from simp.compat.reconciliation import (
    reconcile,
    ReconciliationResult,
    VendorReconciliation,
)
from simp.compat.live_ledger import LiveSpendLedger
from simp.compat.ops_policy import SPEND_LEDGER


@pytest.fixture
def live_ledger(tmp_path):
    return LiveSpendLedger(ledger_path=str(tmp_path / "reconcile_live.jsonl"))


@pytest.fixture(autouse=True)
def clear_simulated_ledger():
    """Clear the global simulated ledger before each test."""
    SPEND_LEDGER._records.clear()
    yield
    SPEND_LEDGER._records.clear()


# ---------------------------------------------------------------------------
# Basic reconciliation
# ---------------------------------------------------------------------------

class TestReconcileBasic:
    def test_empty_ledgers(self, live_ledger):
        result = reconcile(live_ledger=live_ledger)
        assert isinstance(result, ReconciliationResult)
        assert result.live_total == 0.0
        assert result.simulated_total == 0.0
        assert result.status == "ok"

    def test_with_reference_total_match(self, live_ledger):
        live_ledger.record_live_spend("p1", "stripe", "github", "sw", 10.0, "r1")
        result = reconcile(reference_total=10.0, live_ledger=live_ledger)
        assert result.status == "ok"
        assert result.live_total == 10.0

    def test_with_reference_total_mismatch(self, live_ledger):
        live_ledger.record_live_spend("p1", "stripe", "github", "sw", 10.0, "r1")
        result = reconcile(reference_total=15.0, live_ledger=live_ledger)
        assert result.status == "discrepancy_found"
        assert result.discrepancy == 5.0
        assert len(result.notes) > 0

    def test_result_has_id_and_timestamp(self, live_ledger):
        result = reconcile(live_ledger=live_ledger)
        assert result.reconciliation_id
        assert result.timestamp


# ---------------------------------------------------------------------------
# Refund handling
# ---------------------------------------------------------------------------

class TestReconcileRefunds:
    def test_refund_reduces_net(self, live_ledger):
        live_ledger.record_live_spend("p1", "stripe", "github", "sw", 10.0, "r1")
        live_ledger.record_refund("p1", "stripe", "github", 3.0, "refund-r1", "partial")
        result = reconcile(live_ledger=live_ledger)
        assert result.live_total == 7.0  # net = 10 - 3

    def test_refund_noted(self, live_ledger):
        live_ledger.record_live_spend("p1", "stripe", "github", "sw", 10.0, "r1")
        live_ledger.record_refund("p1", "stripe", "github", 10.0, "refund-r1", "full")
        result = reconcile(live_ledger=live_ledger)
        assert any("Refund" in n for n in result.notes)


# ---------------------------------------------------------------------------
# Vendor details
# ---------------------------------------------------------------------------

class TestReconcileVendors:
    def test_vendor_breakdown(self, live_ledger):
        live_ledger.record_live_spend("p1", "stripe", "github", "sw", 10.0, "r1")
        live_ledger.record_live_spend("p2", "stripe", "aws", "sw", 5.0, "r2")
        result = reconcile(live_ledger=live_ledger)
        vendors = {v.vendor for v in result.vendor_details}
        assert "github" in vendors
        assert "aws" in vendors

    def test_vendor_live_only(self, live_ledger):
        live_ledger.record_live_spend("p1", "stripe", "github", "sw", 10.0, "r1")
        result = reconcile(live_ledger=live_ledger)
        github_detail = [v for v in result.vendor_details if v.vendor == "github"]
        assert len(github_detail) == 1
        assert github_detail[0].status == "live_only"


# ---------------------------------------------------------------------------
# ReconciliationResult serialization
# ---------------------------------------------------------------------------

class TestReconciliationResultSerialization:
    def test_to_dict(self, live_ledger):
        result = reconcile(live_ledger=live_ledger)
        d = result.to_dict()
        assert "reconciliation_id" in d
        assert "timestamp" in d
        assert "vendor_details" in d
        assert isinstance(d["vendor_details"], list)

    def test_no_sensitive_data(self, live_ledger):
        """Reconciliation results should not contain PAN, card numbers, tokens."""
        import json
        live_ledger.record_live_spend("p1", "stripe", "github", "sw", 10.0, "r1")
        result = reconcile(live_ledger=live_ledger)
        raw = json.dumps(result.to_dict())
        for sensitive in ['"pan"', '"card_number"', '"secret"', '"token"', '"api_key"']:
            assert sensitive not in raw.lower()
