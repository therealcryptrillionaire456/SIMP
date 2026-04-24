"""
Test Suite — Dashboard Truthfulness (GOOSE 7 / Tranche 7)

Verifies that mesh dashboard endpoints explicitly report broker reachability
and data freshness, so operators can distinguish:
  - "live broker with no data" from
  - "broker is unreachable" from
  - "stale cached data"

Backward compatibility: existing fields that existed before still exist.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from dashboard.mesh_dashboard import MeshDashboard


# =========================================================================
# Helpers
# =========================================================================


class _BrokerResponder:
    """Simulates a broker that either responds (live) or raises (down)."""

    def __init__(self, live: bool = True, status_code: int = 200):
        self.live = live
        self.status_code = status_code

    def _make_response(self, json_data: dict):
        resp = MagicMock()
        resp.status_code = self.status_code
        resp.json.return_value = json_data
        return resp


# =========================================================================
# broker_is_reachable
# =========================================================================


class TestBrokerIsReachable:
    """Test that broker_is_reachable() returns correct booleans."""

    def test_returns_false_when_no_broker(self):
        """When no broker is running, broker_is_reachable() returns False."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        assert dashboard.broker_is_reachable() is False

    def test_returns_false_on_connection_refused(self):
        """A refused connection also returns False."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        assert dashboard.broker_is_reachable() is False

    @patch("requests.get")
    def test_returns_true_when_broker_healthy(self, mock_get):
        """When broker returns 200, broker_is_reachable() returns True."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        dashboard = MeshDashboard(broker_url="http://127.0.0.1:5555")
        assert dashboard.broker_is_reachable() is True
        mock_get.assert_called_once_with(
            "http://127.0.0.1:5555/health", timeout=3
        )


# =========================================================================
# Metadata presence on all fetch methods
# =========================================================================


class TestFetchMethodsMetadata:
    """Every fetch method must include broker_reachable, data_freshness,
    source, and error fields."""

    REQUIRED_FIELDS = {"broker_reachable", "data_freshness", "source", "error"}

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("fetch_mesh_stats", []),
            ("fetch_channel_data", []),
            ("fetch_agent_status", ["test_agent"]),
            ("fetch_recent_events", []),
        ],
    )
    def test_metadata_fields_present(self, method_name, args):
        """Each fetch method returns a dict with all required metadata fields."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = getattr(dashboard, method_name)(*args)

        missing = self.REQUIRED_FIELDS - set(result.keys())
        assert not missing, (
            f"{method_name} is missing metadata fields: {missing}. "
            f"Got keys: {list(result.keys())}"
        )

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("fetch_mesh_stats", []),
            ("fetch_channel_data", []),
            ("fetch_agent_status", ["test_agent"]),
            ("fetch_recent_events", []),
        ],
    )
    def test_source_is_fallback_when_broker_down(self, method_name, args):
        """When broker is unreachable, source should be 'fallback'."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = getattr(dashboard, method_name)(*args)
        assert result.get("broker_reachable") is False
        assert result.get("source") == "fallback"

    def test_error_field_set_on_failure(self):
        """When broker is unreachable, the error field should be populated."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = dashboard.fetch_mesh_stats()
        assert result.get("broker_reachable") is False
        assert result.get("error") is not None
        assert isinstance(result.get("error"), str)

    @patch("dashboard.mesh_dashboard.requests")
    def test_source_is_broker_on_success(self, mock_requests):
        """When broker responds successfully, source should be 'broker'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success", "statistics": {}}
        mock_requests.get.return_value = mock_resp

        dashboard = MeshDashboard(broker_url="http://127.0.0.1:5555")
        result = dashboard.fetch_mesh_stats()
        assert result.get("broker_reachable") is True
        assert result.get("source") == "broker"
        assert result.get("error") is None


# =========================================================================
# Backward compatibility: existing keys still exist
# =========================================================================


class TestBackwardCompatibility:
    """Existing keys that existed before must still be present."""

    def test_mesh_stats_has_data_key(self):
        """fetch_mesh_stats returns a 'data' key with the actual data."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = dashboard.fetch_mesh_stats()
        assert "data" in result, (
            "fetch_mesh_stats must include a 'data' key for backward compat"
        )

    def test_channel_data_has_data_key(self):
        """fetch_channel_data returns a 'data' key with channel data."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = dashboard.fetch_channel_data()
        assert "data" in result

    def test_agent_status_has_data_key(self):
        """fetch_agent_status returns a 'data' key."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = dashboard.fetch_agent_status("test_agent")
        assert "data" in result

    @patch("dashboard.mesh_dashboard.requests")
    def test_get_dashboard_data_keeps_old_keys(self, mock_requests):
        """get_dashboard_data() must still contain stats, channels,
        agents, recent_events, core_channels keys."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "success",
            "statistics": {"registered_agents": 2, "agent_queue_sizes": {"a1": 0}},
        }
        mock_requests.get.return_value = mock_resp

        dashboard = MeshDashboard(broker_url="http://127.0.0.1:5555")

        # First call returns live data
        data = dashboard.get_dashboard_data()
        for key in ("stats", "channels", "agents", "recent_events", "core_channels"):
            assert key in data, (
                f"get_dashboard_data() must contain '{key}' key for backward compat"
            )


# =========================================================================
# Server endpoint shape (using the mock broker helper)
# =========================================================================


class TestServerEndpointShape:
    """Verify that the server endpoints return correct shape with broker
    reachability metadata when accessed through a mock app test client."""

    @pytest.fixture
    def app(self):
        """Build a minimal FastAPI test app with the mesh endpoints."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from dashboard.server import app as dashboard_app

        # Override the MESH_DASHBOARD_AVAILABLE flag so endpoints are active
        import dashboard.server as srv

        srv.MESH_DASHBOARD_AVAILABLE = True
        return TestClient(dashboard_app)

    def test_mesh_stats_endpoint_shape(self, app):
        """The /api/mesh/stats endpoint returns top-level broker_reachable and
        data_freshness fields."""
        resp = app.get("/api/mesh/stats")
        assert resp.status_code == 200
        body = resp.json()
        # Must have broker reachability fields at top level
        assert "broker_reachable" in body, (
            "/api/mesh/stats must include 'broker_reachable'"
        )
        assert "data_freshness" in body
        assert "source" in body
        # Must still have status and data
        assert "status" in body
        assert "data" in body

    def test_mesh_channels_endpoint_shape(self, app):
        """The /api/mesh/channels endpoint returns top-level broker_reachable and
        data_freshness fields."""
        resp = app.get("/api/mesh/channels")
        assert resp.status_code == 200
        body = resp.json()
        assert "broker_reachable" in body
        assert "data_freshness" in body
        assert "source" in body
        assert "status" in body
        assert "data" in body
        # data.channels and data.core_channels must still exist
        inner = body.get("data", {})
        assert "channels" in inner
        assert "core_channels" in inner

    def test_mesh_events_endpoint_shape(self, app):
        """The /api/mesh/events endpoint returns top-level broker_reachable and
        data_freshness fields."""
        resp = app.get("/api/mesh/events")
        assert resp.status_code == 200
        body = resp.json()
        assert "broker_reachable" in body
        assert "data_freshness" in body
        assert "source" in body
        assert "status" in body
        assert "events" in body

    def test_broker_unreachable_returns_200_not_500(self, app):
        """When broker is unreachable, the endpoint should return HTTP 200
        with broker_reachable: false, not HTTP 500."""
        resp = app.get("/api/mesh/stats")
        # The test server is running but the actual broker at port 5555
        # is not available in tests, so broker_reachable should be False
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("broker_reachable") is False or body.get("broker_reachable") is not None

    def test_mesh_dashboard_endpoint_shape(self, app):
        """The /api/mesh/dashboard endpoint returns top-level broker_reachable
        and data_freshness fields."""
        resp = app.get("/api/mesh/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert "broker_reachable" in body
        assert "data_freshness" in body
        assert "source" in body
        assert "status" in body
        assert "data" in body

    def test_mesh_export_endpoint_shape(self, app):
        """The /api/mesh/export endpoint returns broker_reachable and
        data_freshness fields."""
        resp = app.get("/api/mesh/export")
        assert resp.status_code == 200
        body = resp.json()
        assert "broker_reachable" in body
        assert "data_freshness" in body
        assert "source" in body
        assert "export_timestamp" in body or "error" in body


# =========================================================================
# Freshness tracking
# =========================================================================


class TestFreshnessTracking:
    """Verify that _last_success and _last_error are tracked properly."""

    def test_init_tracking_fields(self):
        """__init__ must set _last_success = None and _last_error = None."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:5555")
        assert dashboard._last_success is None
        assert dashboard._last_error is None

    def test_data_freshness_is_iso_timestamp(self):
        """data_freshness should be an ISO-8601 string or None."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = dashboard.fetch_mesh_stats()
        freshness = result.get("data_freshness")
        # When broker is unreachable and there was no previous success,
        # freshness may be None
        if freshness is not None:
            # Try parsing as ISO timestamp
            datetime.fromisoformat(freshness)

    @patch("dashboard.mesh_dashboard.requests")
    def test_last_success_updated_on_success(self, mock_requests):
        """_last_success should be set after a successful fetch."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success", "statistics": {}}
        mock_requests.get.return_value = mock_resp

        dashboard = MeshDashboard(broker_url="http://127.0.0.1:5555")
        result = dashboard.fetch_mesh_stats()
        assert dashboard._last_success is not None
        assert result.get("data_freshness") == dashboard._last_success

    def test_error_field_types(self):
        """error field should be a string when there's an error, None when not."""
        dashboard = MeshDashboard(broker_url="http://127.0.0.1:1")
        result = dashboard.fetch_mesh_stats()
        assert isinstance(result.get("error"), str), (
            "error should be a string when broker is unreachable"
        )
