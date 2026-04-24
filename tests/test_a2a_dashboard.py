"""
SIMP A2A Dashboard — Sprint S8 (Sprint 38) tests.
"""

import json
import os
import pytest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestDashboardA2AStatus:
    @pytest.fixture
    def client(self):
        from dashboard.server import app, set_broker
        mock_broker = MagicMock()
        mock_broker.agents = {
            "px:001": {
                "agent_id": "px:001",
                "agent_type": "projectx_native",
                "status": "online",
            },
        }
        mock_broker.intent_records = {}
        # Provide list_agents for the endpoint to call
        mock_broker.list_agents.return_value = list(mock_broker.agents.values())
        set_broker(mock_broker)
        return TestClient(app)

    def test_status_returns_json(self, client):
        resp = client.get("/dashboard/a2a/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "a2a_capable_agents" in data
        assert "enforcement_status" in data
        assert "quota_status" in data

    def test_enforcement_status(self, client):
        data = client.get("/dashboard/a2a/status").json()
        es = data["enforcement_status"]
        assert es["schema_validation"] == "enabled"
        assert es["replay_protection"] == "planned"

    def test_no_api_keys_in_response(self, client):
        data = client.get("/dashboard/a2a/status").json()
        raw = str(data)
        assert "sk-" not in raw

    def test_agents_listed(self, client):
        data = client.get("/dashboard/a2a/status").json()
        agents = data["a2a_capable_agents"]
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "px:001"


class TestDashboardHTML:
    def test_index_html_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
        assert os.path.exists(path)

    def test_index_html_has_a2a_panel(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
        with open(path) as f:
            content = f.read()
        assert "A2A Compatibility" in content

    def test_index_html_references_status_endpoint(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
        with open(path) as f:
            content = f.read()
        assert "/dashboard/a2a/status" in content
