import json
import os

import pytest

from simp.compat.brp_card import (
    ALLOWED_BRP_SKILL_IDS,
    build_brp_a2a_card,
    validate_brp_task,
)


class TestBRPCard:
    def test_valid_card(self):
        card = build_brp_a2a_card("http://test:5555")
        assert card["name"] == "SIMP Bill Russell Protocol"
        assert card["version"] == "1.0"
        assert "url" in card

    def test_defensive_skills_present(self):
        card = build_brp_a2a_card()
        ids = {item["id"] for item in card["skills"]}
        assert "defense.health_check" in ids
        assert "defense.threat_analysis" in ids
        assert "defense.security_audit" in ids
        assert "defense.pattern_detection" in ids
        assert "defense.quantum_posture" in ids
        assert ids == ALLOWED_BRP_SKILL_IDS

    def test_card_is_read_only(self):
        card = build_brp_a2a_card()
        assert card["safetyPolicies"]["readOnlyByDefault"] is True
        assert card["safetyPolicies"]["autonomousWritesAllowed"] is False


class TestBRPTaskValidation:
    def test_valid_health_check(self):
        ok, skill, intent = validate_brp_task({"skill_id": "defense.health_check"})
        assert ok is True
        assert intent == "ping"

    def test_unsafe_skill_rejected(self):
        ok, err, _ = validate_brp_task({"skill_id": "defense.self_modify"})
        assert ok is False
        assert "not allowed" in err.lower()

    def test_unknown_skill_rejected(self):
        ok, err, _ = validate_brp_task({"skill_id": "defense.unknown"})
        assert ok is False


class TestBRPRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer

        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_get_card_no_auth(self, client):
        resp = client.get("/a2a/agents/brp/agent.json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["name"] == "SIMP Bill Russell Protocol"

    def test_post_valid_task(self, client):
        resp = client.post(
            "/a2a/agents/brp/tasks",
            data=json.dumps({"skill_id": "defense.security_audit"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "taskId" in data

    def test_post_unsafe_task_rejected(self, client):
        resp = client.post(
            "/a2a/agents/brp/tasks",
            data=json.dumps({"skill_id": "defense.internet_full_access"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_health_route_exposes_quantum_defense(self, client):
        resp = client.get("/a2a/agents/brp/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "success"
        assert "quantum_defense" in data
        assert "backend_summary" in data["quantum_defense"]
