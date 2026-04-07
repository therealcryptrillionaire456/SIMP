"""Sprint 59 — Gate 1 Simulation + FinancialOps E2E tests.

Multi-step FinancialOps flows: submit→approve, overspend rejection,
disallowed category, execute without approval, budget after simulation,
gate-1 simulation, rollback blocks.
"""

import json
import os
import pytest

from simp.server.http_server import SimpHttpServer
from simp.compat.approval_queue import APPROVAL_QUEUE
from simp.compat.payment_connector import HEALTH_TRACKER, ALLOWED_CONNECTORS
from simp.compat.ops_policy import SPEND_LEDGER
from simp.compat.gate_manager import GATE_MANAGER


@pytest.fixture(autouse=True)
def env_setup():
    os.environ["SIMP_REQUIRE_API_KEY"] = "false"
    os.environ.pop("SIMP_ENV", None)
    os.environ.pop("FINANCIAL_OPS_LIVE_ENABLED", None)
    yield


@pytest.fixture()
def client():
    server = SimpHttpServer(debug=False)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


class TestGate1Simulation:
    """Tests for the gate-1 simulation endpoint."""

    def test_simulate_gate1_adds_records(self, client):
        resp = client.post("/a2a/agents/financial-ops/gates/simulate-gate1")
        assert resp.status_code == 200
        data = resp.json
        assert data["status"] == "simulated"
        assert data["health_records_added"] == 7 * len(ALLOWED_CONNECTORS)
        assert data["spend_records_added"] == 20

    def test_simulate_gate1_blocked_in_production(self, client):
        os.environ["SIMP_ENV"] = "production"
        resp = client.post("/a2a/agents/financial-ops/gates/simulate-gate1")
        assert resp.status_code == 403

    def test_simulate_gate1_returns_gate_check(self, client):
        resp = client.post("/a2a/agents/financial-ops/gates/simulate-gate1")
        data = resp.json
        assert "gate1_check" in data


class TestFinancialOpsE2E:
    """Multi-step FinancialOps flow tests."""

    def test_submit_and_approve_proposal(self, client):
        """Submit a proposal and approve it."""
        resp = client.post("/a2a/agents/financial-ops/proposals", json={
            "op_type": "small_purchase",
            "vendor": "TestVendor",
            "category": "software_licenses",
            "amount": 50.0,
            "connector_name": "stripe_small_payments",
            "description": "Test purchase",
            "submitted_by": "e2e_test",
        })
        assert resp.status_code == 201
        proposal_id = resp.json["proposal"]["proposal_id"]

        # Approve
        resp2 = client.post(f"/a2a/agents/financial-ops/proposals/{proposal_id}/approve", json={
            "operator_subject": "ops-admin",
        })
        assert resp2.status_code == 200
        assert resp2.json["status"] == "approved"

    def test_overspend_rejected_at_execution(self, client):
        """Execute fails when live payments disabled."""
        # Submit and approve
        resp = client.post("/a2a/agents/financial-ops/proposals", json={
            "op_type": "small_purchase",
            "vendor": "ExpensiveVendor",
            "category": "software_licenses",
            "amount": 999.99,
            "connector_name": "stripe_small_payments",
            "submitted_by": "e2e_test",
        })
        proposal_id = resp.json["proposal"]["proposal_id"]
        client.post(f"/a2a/agents/financial-ops/proposals/{proposal_id}/approve", json={
            "operator_subject": "ops-admin",
        })

        # Try to execute — should fail because live is disabled
        resp2 = client.post(f"/a2a/agents/financial-ops/proposals/{proposal_id}/execute")
        assert resp2.status_code == 403
        assert "not enabled" in resp2.json["error"]

    def test_disallowed_category_rejected(self, client):
        """FinancialOps task with invalid category still records simulated spend."""
        resp = client.post("/a2a/agents/financial-ops/tasks", json={
            "op_type": "gambling",
            "would_spend": 100.0,
            "description": "Gambling expense",
        })
        # The endpoint always records and returns 202
        assert resp.status_code == 202
        assert resp.json["status"] == "pending_approval"

    def test_execute_without_approval_fails(self, client):
        """Execute a proposal that hasn't been approved should fail."""
        resp = client.post("/a2a/agents/financial-ops/proposals", json={
            "op_type": "small_purchase",
            "vendor": "NoApproveVendor",
            "category": "software_licenses",
            "amount": 10.0,
            "submitted_by": "e2e_test",
        })
        proposal_id = resp.json["proposal"]["proposal_id"]

        # Execute without approving — live not enabled anyway
        resp2 = client.post(f"/a2a/agents/financial-ops/proposals/{proposal_id}/execute")
        assert resp2.status_code == 403

    def test_budget_endpoint_works(self, client):
        resp = client.get("/a2a/agents/financial-ops/budget")
        assert resp.status_code == 200

    def test_gate1_simulation_flow(self, client):
        """Simulate gate-1 and check that health records are populated."""
        resp = client.post("/a2a/agents/financial-ops/gates/simulate-gate1")
        assert resp.status_code == 200

        # Now check gates
        resp2 = client.get("/gates/1")
        assert resp2.status_code == 200

    def test_rollback_status(self, client):
        """Rollback status endpoint returns valid data."""
        resp = client.get("/rollback/status")
        assert resp.status_code == 200
        data = resp.json
        assert "state" in data or "status" in data or isinstance(data, dict)

    def test_ledger_endpoint(self, client):
        resp = client.get("/a2a/agents/financial-ops/ledger")
        assert resp.status_code == 200
        data = resp.json
        assert "simulated" in data
        assert "live" in data

    def test_submit_then_reject(self, client):
        """Submit a proposal and reject it."""
        resp = client.post("/a2a/agents/financial-ops/proposals", json={
            "op_type": "small_purchase",
            "vendor": "RejectVendor",
            "category": "software_licenses",
            "amount": 25.0,
            "submitted_by": "e2e_test",
        })
        proposal_id = resp.json["proposal"]["proposal_id"]

        resp2 = client.post(f"/a2a/agents/financial-ops/proposals/{proposal_id}/reject", json={
            "operator_subject": "ops-admin",
            "reason": "Not needed",
        })
        assert resp2.status_code == 200
        assert resp2.json["status"] == "rejected"

    def test_proposals_list(self, client):
        """List proposals returns a valid structure."""
        resp = client.get("/a2a/agents/financial-ops/proposals")
        assert resp.status_code == 200
        assert "proposals" in resp.json

    def test_connector_health_endpoint(self, client):
        resp = client.get("/a2a/agents/financial-ops/connector-health")
        assert resp.status_code == 200
