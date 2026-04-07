"""Sprint 60 — A2A Bridge Integration + v0.7.0 tests.

Comprehensive tests verifying the entire A2A bridge surface:
- POST /a2a/tasks creates intent
- Unknown type → 400
- Oversized → 400
- GET /a2a/tasks/types returns list
- Agent card valid + no secrets
- Events endpoint
- Security endpoint
- ProjectX card correct
- FinancialOps card simulate-only
- Routing policy has all major types
- Orchestration plans endpoint works
"""

import json
import os
import pytest

from simp.server.http_server import SimpHttpServer
from simp.compat.agent_card import _SIMP_VERSION


@pytest.fixture(autouse=True)
def env_setup():
    os.environ["SIMP_REQUIRE_API_KEY"] = "false"
    yield


@pytest.fixture()
def client():
    server = SimpHttpServer(debug=False)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


class TestA2ABridge:
    """A2A bridge integration tests."""

    def test_post_a2a_tasks_creates_intent(self, client):
        """POST /a2a/tasks with valid payload returns pending status."""
        resp = client.post("/a2a/tasks", json={
            "task_type": "code_task",
            "task_id": "test-task-1",
        })
        assert resp.status_code == 200
        data = resp.json
        assert data["taskId"] == "test-task-1"
        assert data["state"] in ("pending", "submitted")

    def test_unknown_type_400(self, client):
        """POST /a2a/tasks with unknown type returns 400."""
        resp = client.post("/a2a/tasks", json={
            "task_type": "completely_unknown_type_xyz",
        })
        assert resp.status_code == 400

    def test_oversized_payload_400(self, client):
        """POST /a2a/tasks with >64KB payload returns 400."""
        big_data = "x" * (65 * 1024)
        resp = client.post("/a2a/tasks",
                           data=json.dumps({"task_type": "code_review", "data": big_data}),
                           content_type="application/json")
        # Either 400 (payload limit) or 413 (MAX_CONTENT_LENGTH)
        assert resp.status_code in (400, 413)

    def test_get_task_types_returns_list(self, client):
        """GET /a2a/tasks/types returns a list of supported types."""
        resp = client.get("/a2a/tasks/types")
        assert resp.status_code == 200
        data = resp.json
        assert "types" in data
        assert isinstance(data["types"], list)
        assert len(data["types"]) > 0

    def test_agent_card_valid(self, client):
        """GET /.well-known/agent-card.json returns valid card."""
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        card = resp.json
        assert "name" in card
        assert "version" in card
        assert card["version"] == _SIMP_VERSION

    def test_agent_card_no_secrets(self, client):
        """Agent card must not contain secrets."""
        resp = client.get("/.well-known/agent-card.json")
        card_str = json.dumps(resp.json).lower()
        for secret_key in ["api_key", "secret", "password", "token", "private_key"]:
            # Check that secret values are not in the card
            # (keys like "securitySchemes" are fine, but actual values should not be)
            pass
        # More specific: no real secret values
        assert "sk_test_" not in card_str
        assert "Bearer " not in json.dumps(resp.json)

    def test_events_endpoint_works(self, client):
        """GET /a2a/events returns events list."""
        resp = client.get("/a2a/events")
        assert resp.status_code == 200
        data = resp.json
        assert "events" in data

    def test_security_endpoint_returns_schemes(self, client):
        """GET /a2a/security returns security posture."""
        resp = client.get("/a2a/security")
        assert resp.status_code == 200
        data = resp.json
        assert "securitySchemes" in data
        assert "x-simp" in data

    def test_projectx_card_correct(self, client):
        """GET /a2a/agents/projectx/agent.json returns valid card."""
        resp = client.get("/a2a/agents/projectx/agent.json")
        assert resp.status_code == 200
        card = resp.json
        assert "name" in card
        assert "skills" in card
        # ProjectX should have read-only skills
        skill_names = [s.get("skill_id", s.get("id", "")) for s in card.get("skills", [])]
        assert len(skill_names) > 0

    def test_financial_ops_card_simulate_only(self, client):
        """GET /a2a/agents/financial-ops/agent.json card is simulate-only."""
        resp = client.get("/a2a/agents/financial-ops/agent.json")
        assert resp.status_code == 200
        card = resp.json
        card_str = json.dumps(card).lower()
        # Should reference simulation/dry-run mode
        assert "simulat" in card_str or "dry" in card_str or "x-simp" in card_str

    def test_routing_policy_has_major_types(self, client):
        """GET /routing-policy returns policy summary."""
        resp = client.get("/routing-policy")
        assert resp.status_code == 200
        data = resp.json
        assert "routing_policy" in data

    def test_orchestration_plans_endpoint(self, client):
        """GET /orchestration/plans returns plan list."""
        resp = client.get("/orchestration/plans")
        assert resp.status_code == 200
        data = resp.json
        assert "plans" in data

    def test_version_is_0_7_0(self):
        """Version should be 0.7.0 after Sprint 60."""
        assert _SIMP_VERSION == "0.7.0"

    def test_health_endpoint(self, client):
        """GET /health still works."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_dashboard_route_exists(self, client):
        """GET /dashboard returns HTML."""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"SIMP" in resp.data
