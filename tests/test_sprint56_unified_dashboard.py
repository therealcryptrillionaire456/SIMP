"""Sprint 56 — Unified Dashboard Architecture tests.

Verifies that the dashboard server uses _broker_get (stdlib urllib) to proxy
requests to the broker, and that all A2A / FinancialOps dashboard endpoints
return correct shapes even when the broker is unavailable.
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from dashboard.server import _broker_get, app

# Use Starlette's test client (the dashboard is a FastAPI app)
from starlette.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# _broker_get helper
# ---------------------------------------------------------------------------

class TestBrokerGetHelper:
    """Tests for the _broker_get stdlib helper."""

    def test_broker_get_returns_default_on_connection_error(self):
        """When broker is down, _broker_get returns default."""
        result = _broker_get("/nonexistent-endpoint", default={"fallback": True}, timeout=0.5)
        assert result == {"fallback": True}

    def test_broker_get_returns_default_on_none(self):
        result = _broker_get("/bogus", default=None, timeout=0.5)
        assert result is None

    def test_broker_get_uses_stdlib_urllib(self):
        """Ensure _broker_get uses urllib, not requests."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"ok": true}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = _broker_get("/health")
            assert mock_urlopen.called
            assert result == {"ok": True}


# ---------------------------------------------------------------------------
# Dashboard A2A status endpoint
# ---------------------------------------------------------------------------

class TestDashboardA2AStatus:
    """Tests for /dashboard/a2a/status."""

    def test_a2a_status_returns_json(self):
        resp = client.get("/dashboard/a2a/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "a2a_capable_agents" in data
        assert "enforcement_status" in data
        assert "quota_status" in data

    def test_a2a_status_enforcement_fields(self):
        resp = client.get("/dashboard/a2a/status")
        es = resp.json()["enforcement_status"]
        assert es["schema_validation"] == "enabled"
        assert es["rate_limiting"] == "enabled"
        assert es["payload_limits"] == "enabled"


# ---------------------------------------------------------------------------
# FinancialOps dashboard endpoints
# ---------------------------------------------------------------------------

class TestDashboardFinancialOps:
    """Tests for /dashboard/financial-ops/* endpoints."""

    def test_status_returns_mode(self):
        resp = client.get("/dashboard/financial-ops/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "dry_run"
        assert data["live_payments_enabled"] is False

    def test_proposals_returns_list(self):
        resp = client.get("/dashboard/financial-ops/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert "proposals" in data

    def test_ledger_returns_both_sections(self):
        resp = client.get("/dashboard/financial-ops/ledger")
        assert resp.status_code == 200
        data = resp.json()
        assert "simulated" in data
        assert "live" in data

    def test_rollback_returns_state(self):
        resp = client.get("/dashboard/financial-ops/rollback")
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data

    def test_budget_returns_json(self):
        resp = client.get("/dashboard/financial-ops/budget")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_gates_returns_json(self):
        resp = client.get("/dashboard/financial-ops/gates")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)
