"""
Integration tests for FinancialOps Graduation (Sprints 41-45).

Tests the extended ops_policy, financial_ops, event_stream, and HTTP routes.
"""

import json
import os
import pytest
from dataclasses import asdict
from simp.compat.ops_policy import (
    OpsPolicy, get_policy_dict, get_live_policy_dict, SpendRecord, SPEND_LEDGER,
)
from simp.compat.financial_ops import (
    build_financial_ops_card, validate_financial_op, record_would_spend,
    execute_approved_payment,
)
from simp.compat.event_stream import (
    build_payment_event, PAYMENT_EVENT_KINDS, build_a2a_event, build_a2a_events_list,
)
from simp.compat.approval_queue import APPROVAL_QUEUE, ApprovalQueue
from simp.compat.payment_connector import (
    ALLOWED_CONNECTORS, ALLOWED_VENDOR_CATEGORIES, DISALLOWED_PAYMENT_TYPES,
    validate_payment_request,
)
from simp.compat.live_ledger import LiveSpendLedger


# ---------------------------------------------------------------------------
# OpsPolicy extensions
# ---------------------------------------------------------------------------

class TestOpsPolicyExtensions:
    def test_live_payment_fields_exist(self):
        policy = OpsPolicy()
        assert policy.live_payments_allowed is False
        assert "stripe_small_payments" in policy.live_payment_connectors
        assert "software_subscription" in policy.allowed_vendor_categories
        assert "wire_transfers" in policy.disallowed_payment_types
        assert policy.pilot_max_spend_per_month == 100.00
        assert policy.pilot_max_payments_per_month == 20

    def test_get_live_policy_dict(self):
        d = get_live_policy_dict()
        assert d["live_payments_allowed"] is False
        assert "stripe_small_payments" in d["live_payment_connectors"]
        assert d["spend_mode"] == "simulation"
        assert d["approval_required"] is True

    def test_get_policy_dict_unchanged(self):
        d = get_policy_dict()
        assert "log_destination" not in d
        assert "version" in d

    def test_spend_record_dry_run_fields(self):
        rec = SpendRecord(
            record_id="r1", timestamp="t", op_type="simulated_spend",
            agent_id="a1", description="test", would_spend=5.0,
            dry_run_result="Would charge $5.00",
            connector_used="stripe_small_payments",
            dry_run_reference_id="ref-1",
        )
        d = rec.to_dict()
        assert d["dry_run_result"] == "Would charge $5.00"
        assert d["connector_used"] == "stripe_small_payments"
        assert d["dry_run_reference_id"] == "ref-1"


class TestSimulatedSpendLedgerExtensions:
    @pytest.fixture(autouse=True)
    def clear_ledger(self):
        SPEND_LEDGER._records.clear()
        yield
        SPEND_LEDGER._records.clear()

    def test_record_with_dry_run(self):
        rec = SPEND_LEDGER.record_with_dry_run(
            agent_id="agent-1",
            description="Test dry run",
            would_spend=5.0,
            dry_run_result="Would charge $5.00",
            connector_used="stripe_small_payments",
            dry_run_reference_id="ref-dr-1",
        )
        assert rec.dry_run_result == "Would charge $5.00"
        assert rec.connector_used == "stripe_small_payments"
        assert rec.status == "simulated"
        assert rec.approved is False

    def test_record_with_dry_run_in_ledger(self):
        SPEND_LEDGER.record_with_dry_run(
            agent_id="agent-1", description="Test", would_spend=5.0,
            dry_run_result="ok", connector_used="stripe", dry_run_reference_id="ref",
        )
        assert len(SPEND_LEDGER.get_ledger()) == 1
        s = SPEND_LEDGER.get_ledger_summary()
        assert s["total_would_spend"] == 5.0


# ---------------------------------------------------------------------------
# Financial ops card
# ---------------------------------------------------------------------------

class TestFinancialOpsCardExtensions:
    def test_card_has_live_policy(self):
        card = build_financial_ops_card("http://localhost:5555")
        x_simp = card.get("x-simp", {})
        assert "livePaymentPolicy" in x_simp
        lp = x_simp["livePaymentPolicy"]
        assert lp["live_payments_allowed"] is False
        assert lp["approval_required"] is True

    def test_card_no_credentials(self):
        card = build_financial_ops_card("http://localhost:5555")
        raw = json.dumps(card)
        # Check that no actual credential values are present.
        # "noCredentialStorage" is a policy field name, not a credential.
        for s in ['"api_key":', '"secret_key":', '"password":', '"private_key":']:
            assert s not in raw.lower()

    def test_card_safety_policies(self):
        card = build_financial_ops_card("http://localhost:5555")
        sp = card["safetyPolicies"]
        assert sp["requiresManualApproval"] is True
        assert sp["noCredentialStorage"] is True

    def test_card_skills(self):
        card = build_financial_ops_card("http://localhost:5555")
        skills = card["skills"]
        assert len(skills) > 0
        assert all("Simulated" in s["name"] for s in skills)


# ---------------------------------------------------------------------------
# validate_financial_op
# ---------------------------------------------------------------------------

class TestValidateFinancialOp:
    def test_valid_op_requires_approval(self):
        ok, msg = validate_financial_op("small_purchase", 10.0)
        assert ok is False
        assert "manual approval" in msg.lower()

    def test_unknown_op(self):
        ok, msg = validate_financial_op("wire_transfer", 10.0)
        assert ok is False
        assert "Unknown" in msg

    def test_exceeds_limit(self):
        ok, msg = validate_financial_op("small_purchase", 25.0)
        assert ok is False
        assert "exceeds" in msg.lower()


# ---------------------------------------------------------------------------
# record_would_spend
# ---------------------------------------------------------------------------

class TestRecordWouldSpend:
    @pytest.fixture(autouse=True)
    def clear_ledger(self):
        SPEND_LEDGER._records.clear()
        yield
        SPEND_LEDGER._records.clear()

    def test_returns_dict(self):
        d = record_would_spend("agent-1", "small_purchase", 5.0, "test desc")
        assert "record_id" in d
        assert d["would_spend"] == 5.0
        assert d["status"] == "simulated"
        assert d["approved"] is False


# ---------------------------------------------------------------------------
# Payment events
# ---------------------------------------------------------------------------

class TestPaymentEvents:
    def test_payment_event_kinds_nonempty(self):
        assert len(PAYMENT_EVENT_KINDS) >= 10

    def test_build_payment_event_basic(self):
        evt = build_payment_event("payment.proposal_created", "prop-1", vendor="github", amount=10.0)
        assert evt["taskId"] == "prop-1"
        assert evt["eventKind"] == "payment.proposal_created"
        assert evt["x-simp"]["proposal_id"] == "prop-1"
        assert "vendor" in evt["x-simp"]

    def test_terminal_events(self):
        for kind in ["payment.execution_completed", "payment.execution_failed",
                      "payment.proposal_rejected", "payment.proposal_expired"]:
            evt = build_payment_event(kind, "p1")
            assert evt["terminal"] is True

    def test_non_terminal_events(self):
        for kind in ["payment.proposal_created", "payment.execution_started",
                      "payment.policy_change_requested"]:
            evt = build_payment_event(kind, "p1")
            assert evt["terminal"] is False

    def test_unknown_event_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            build_payment_event("payment.invalid_kind", "p1")

    def test_error_in_event(self):
        evt = build_payment_event("payment.execution_failed", "p1", error="Connection refused")
        assert evt["error"] == "Connection refused"

    def test_error_truncation(self):
        long_error = "x" * 300
        evt = build_payment_event("payment.execution_failed", "p1", error=long_error)
        assert len(evt["error"]) <= 204  # 200 + "..."

    def test_existing_event_functions_unchanged(self):
        """Existing build_a2a_event and build_a2a_events_list still work."""
        record = {"intent_id": "int-1", "status": "completed", "timestamp": "2025-01-01T00:00:00Z"}
        evt = build_a2a_event(record)
        assert evt["taskId"] == "int-1"
        assert evt["state"] == "completed"

        result = build_a2a_events_list([record])
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# execute_approved_payment (feature-flagged)
# ---------------------------------------------------------------------------

class TestExecuteApprovedPayment:
    def test_blocked_when_not_enabled(self):
        result = execute_approved_payment("prop-nonexistent")
        assert result["success"] is False
        assert "not enabled" in result["error"].lower()

    def test_proposal_not_found(self, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        result = execute_approved_payment("no-such-proposal")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_idempotent_execution(self, monkeypatch, tmp_path):
        """If proposal is already in live ledger, return success without double-charging."""
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        # Pre-load into live ledger
        from simp.compat.live_ledger import LIVE_SPEND_LEDGER
        LIVE_SPEND_LEDGER._seen_proposals.add("prop-already-done")
        try:
            result = execute_approved_payment("prop-already-done")
            assert result["success"] is True
            assert "idempotent" in result["message"].lower()
        finally:
            LIVE_SPEND_LEDGER._seen_proposals.discard("prop-already-done")


# ---------------------------------------------------------------------------
# HTTP routes smoke tests (via Flask test client)
# ---------------------------------------------------------------------------

class TestFinancialOpsHTTPRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        server = SimpHttpServer(debug=True)
        server.app.config["TESTING"] = True
        return server.app.test_client()

    def test_connector_health(self, client):
        resp = client.get("/a2a/financial-ops/connectors/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "connectors" in data
        assert "x-simp" in data

    def test_submit_proposal(self, client):
        resp = client.post("/a2a/financial-ops/proposals", json={
            "vendor": "github", "category": "software_subscription",
            "would_spend": 5.0, "connector_name": "stripe_small_payments",
            "description": "Test proposal",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "pending_approval"
        assert "proposal" in data

    def test_submit_proposal_bad_vendor(self, client):
        resp = client.post("/a2a/financial-ops/proposals", json={
            "vendor": "", "category": "software_subscription",
            "would_spend": 5.0, "connector_name": "stripe_small_payments",
        })
        assert resp.status_code == 400

    def test_list_proposals(self, client):
        resp = client.get("/a2a/financial-ops/proposals")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "proposals" in data
        assert "count" in data

    def test_approve_missing_operator(self, client):
        resp = client.post("/a2a/financial-ops/proposals/fake-id/approve", json={})
        assert resp.status_code == 400

    def test_reject_missing_operator(self, client):
        resp = client.post("/a2a/financial-ops/proposals/fake-id/reject", json={})
        assert resp.status_code == 400

    def test_execute_not_enabled(self, client):
        resp = client.post("/a2a/financial-ops/proposals/fake-id/execute", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "not enabled" in data.get("error", "").lower()

    def test_ledger(self, client):
        resp = client.get("/a2a/financial-ops/ledger")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "records" in data
        assert "summary" in data

    def test_ledger_export(self, client):
        resp = client.get("/a2a/financial-ops/ledger/export")
        assert resp.status_code == 200
        assert resp.content_type.startswith("application/x-ndjson")

    def test_reconciliation(self, client):
        resp = client.post("/a2a/financial-ops/reconciliation", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reconciliation" in data

    def test_submit_policy_change(self, client):
        resp = client.post("/a2a/financial-ops/policy-changes", json={
            "description": "Raise limit to $50",
            "requested_by": "admin-1",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "pending"

    def test_submit_policy_change_missing_fields(self, client):
        resp = client.post("/a2a/financial-ops/policy-changes", json={})
        assert resp.status_code == 400

    def test_financial_ops_card_has_live_policy(self, client):
        resp = client.get("/a2a/agents/financial-ops/agent.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "livePaymentPolicy" in data.get("x-simp", {})
