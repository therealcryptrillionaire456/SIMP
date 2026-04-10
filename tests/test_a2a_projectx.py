"""
SIMP A2A ProjectX — Sprint S2 (Sprint 32) tests.
"""

import json
import os
import pytest

from simp.compat.projectx_card import (
    build_projectx_a2a_card,
    validate_projectx_task,
    ALLOWED_SKILL_IDS,
)


class TestProjectXCard:
    def test_valid_card(self):
        card = build_projectx_a2a_card("http://test:5555")
        assert card["name"] == "SIMP ProjectX Native Agent"
        assert card["version"] == "1.0"
        assert "url" in card

    def test_four_maintenance_skills(self):
        card = build_projectx_a2a_card()
        ids = {s["id"] for s in card["skills"]}
        assert "maintenance.health_check" in ids
        assert "maintenance.audit" in ids
        assert "maintenance.security_audit" in ids
        assert "maintenance.repo_scan" in ids
        assert len(ids) == 4

    def test_safety_policies(self):
        card = build_projectx_a2a_card()
        assert card["safetyPolicies"]["readOnlyByDefault"] is True

    def test_resource_limits(self):
        card = build_projectx_a2a_card()
        assert "maxConcurrentJobs" in card["resourceLimits"]

    def test_no_file_paths(self):
        card = build_projectx_a2a_card()
        raw = str(card)
        assert "/Users/" not in raw
        assert "boundedScanRoots" not in raw

    def test_security_schemes_present(self):
        card = build_projectx_a2a_card()
        assert "securitySchemes" in card
        assert len(card["securitySchemes"]) > 0

    def test_security_requirements(self):
        card = build_projectx_a2a_card()
        assert "security" in card
        assert len(card["security"]) > 0


class TestProjectXTaskValidation:
    def test_valid_health_check(self):
        ok, skill, intent = validate_projectx_task({"skill_id": "maintenance.health_check"})
        assert ok is True
        assert intent == "native_agent_health_check"

    def test_write_skill_rejected(self):
        ok, err, _ = validate_projectx_task({"skill_id": "maintenance.code_maintenance"})
        assert ok is False
        assert "not allowed" in err

    def test_unknown_skill_rejected(self):
        ok, err, _ = validate_projectx_task({"skill_id": "unknown.skill"})
        assert ok is False


class TestProjectXRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_get_card_no_auth(self, client):
        resp = client.get("/a2a/agents/projectx/agent.json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["name"] == "SIMP ProjectX Native Agent"

    def test_post_valid_task(self, client):
        resp = client.post(
            "/a2a/agents/projectx/tasks",
            data=json.dumps({"skill_id": "maintenance.health_check"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "taskId" in data

    def test_post_write_task_rejected(self, client):
        resp = client.post(
            "/a2a/agents/projectx/tasks",
            data=json.dumps({"skill_id": "maintenance.code_maintenance"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
