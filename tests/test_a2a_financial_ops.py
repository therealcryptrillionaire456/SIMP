"""
SIMP A2A Financial Ops — Sprint S7 (Sprint 37) tests.
"""

import json
import os
import pytest

from simp.compat.financial_ops import (
    build_financial_ops_card,
    validate_financial_op,
    record_would_spend,
    FINANCIAL_OPS_CAPABILITIES,
    FINANCIAL_OPS_LIMITS,
)
from simp.compat.ops_policy import SimulatedSpendLedger


class TestFinancialOpsCard:
    def test_valid_card(self):
        card = build_financial_ops_card("http://test:5555")
        assert card["name"] == "SIMP FinancialOps Agent"
        assert "version" in card
        assert "url" in card

    def test_three_capabilities(self):
        card = build_financial_ops_card()
        assert len(card["skills"]) == 3

    def test_safety_policies(self):
        card = build_financial_ops_card()
        assert card["safetyPolicies"]["requiresManualApproval"] is True
        assert card["safetyPolicies"]["noCredentialStorage"] is True
        assert card["safetyPolicies"]["sandboxMode"] is True

    def test_resource_limits(self):
        card = build_financial_ops_card()
        assert card["resourceLimits"]["maxSpendPerTask"] == 20.00
        assert card["resourceLimits"]["mode"] == "simulate_only"

    def test_planned_status(self):
        card = build_financial_ops_card()
        assert card["x-simp"]["status"] == "planned"
        assert card["x-simp"]["mode"] == "simulate_only"

    def test_no_payment_credentials(self):
        card = build_financial_ops_card()
        raw = str(card)
        assert "sk-" not in raw
        assert "credit_card" not in raw
        assert "bank_account" not in raw


class TestValidateFinancialOp:
    def test_always_returns_pending(self):
        state, reason = validate_financial_op("small_purchase", 5.0)
        assert state == "pending_approval"
        assert "manual approval" in reason.lower()

    def test_invalid_op_type(self):
        state, reason = validate_financial_op("hack_the_planet", 5.0)
        assert state == "rejected"
        assert "Unknown" in reason

    def test_overspend(self):
        state, reason = validate_financial_op("small_purchase", 999.0)
        assert state == "rejected"
        assert "exceeds" in reason


class TestRecordWouldSpend:
    def test_creates_record(self):
        rec = record_would_spend("test_agent", "small_purchase", 5.0, "test buy")
        assert rec["status"] == "simulated"
        assert rec["approved"] is False
        assert rec["would_spend"] == 5.0


class TestFinancialOpsRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_get_card(self, client):
        resp = client.get("/a2a/agents/financial-ops/agent.json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["name"] == "SIMP FinancialOps Agent"

    def test_post_task_returns_202(self, client):
        resp = client.post(
            "/a2a/agents/financial-ops/tasks",
            data=json.dumps({
                "op_type": "small_purchase",
                "would_spend": 5.0,
                "description": "test",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = json.loads(resp.data)
        assert data["status"] == "pending_approval"
        assert data["x-simp"]["approved"] is False

    def test_post_never_routes_real_payment(self, client):
        resp = client.post(
            "/a2a/agents/financial-ops/tasks",
            data=json.dumps({"op_type": "small_purchase", "would_spend": 5.0}),
            content_type="application/json",
        )
        data = json.loads(resp.data)
        assert data["x-simp"]["mode"] == "simulate_only"
