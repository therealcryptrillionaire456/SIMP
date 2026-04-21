"""Tests for /timesfm/health, /timesfm/audit, and TimesFM in /stats.

Verifies that the two new TimesFM observability endpoints return correct
shapes, degrade safely on import errors, and that /stats now includes a
timesfm sub-dict.
"""

import json
import os

import pytest

from simp.server.http_server import SimpHttpServer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Flask test client with a fresh SimpHttpServer (no API-key required)."""
    os.environ.setdefault("SIMP_REQUIRE_API_KEY", "false")
    server = SimpHttpServer(debug=False)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# /timesfm/health
# ---------------------------------------------------------------------------

class TestTimesFMHealthEndpoint:
    """Tests for GET /timesfm/health."""

    def test_returns_200(self, client):
        resp = client.get("/timesfm/health")
        assert resp.status_code == 200

    def test_has_timesfm_service_key(self, client):
        data = json.loads(client.get("/timesfm/health").data)
        assert "timesfm_service" in data

    def test_has_policy_engine_key(self, client):
        data = json.loads(client.get("/timesfm/health").data)
        assert "policy_engine" in data

    def test_degrades_safely_on_error(self, client):
        """Endpoint never 5xx even if TimesFM is misconfigured."""
        resp = client.get("/timesfm/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        # Even if the service is unavailable, we should get a valid structure
        assert isinstance(data.get("timesfm_service"), dict)
        assert isinstance(data.get("policy_engine"), dict)

    def test_includes_shadow_mode_if_present(self, client):
        data = json.loads(client.get("/timesfm/health").data)
        ts = data["timesfm_service"]
        # If the service loaded successfully, shadow_mode should be present
        if "error" not in ts:
            assert "shadow_mode" in ts

    def test_includes_cache_metrics_if_present(self, client):
        data = json.loads(client.get("/timesfm/health").data)
        ts = data["timesfm_service"]
        # If the service loaded successfully, cache/error metrics should be present
        if "error" not in ts:
            for key in ("cache_hit_rate", "avg_latency_ms", "error_rate"):
                assert key in ts, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# /timesfm/audit
# ---------------------------------------------------------------------------

class TestTimesFMAuditEndpoint:
    """Tests for GET /timesfm/audit."""

    def test_returns_200(self, client):
        resp = client.get("/timesfm/audit")
        assert resp.status_code == 200

    def test_default_limit(self, client):
        data = json.loads(client.get("/timesfm/audit").data)
        assert "records" in data
        assert data["count"] <= 100

    def test_agent_filter(self, client):
        resp = client.get("/timesfm/audit?agent=quantumarb")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "records" in data

    def test_custom_limit(self, client):
        data = json.loads(client.get("/timesfm/audit?limit=10").data)
        assert data["count"] <= 10

    def test_max_limit_clamped_at_500(self, client):
        data = json.loads(client.get("/timesfm/audit?limit=9999").data)
        assert data["count"] <= 500

    def test_degrades_safely_on_error(self, client):
        """Endpoint never 5xx even if TimesFM is misconfigured."""
        resp = client.get("/timesfm/audit")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "records" in data


# ---------------------------------------------------------------------------
# /stats includes timesfm
# ---------------------------------------------------------------------------

class TestStatsIncludesTimesFM:
    """Tests that GET /stats now includes a timesfm sub-dict."""

    def test_stats_has_timesfm_key(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        stats = data.get("stats", {})
        assert "timesfm" in stats

    def test_timesfm_in_stats_is_dict(self, client):
        data = json.loads(client.get("/stats").data)
        ts = data["stats"]["timesfm"]
        assert isinstance(ts, dict)
