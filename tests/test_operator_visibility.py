"""
Test operator visibility — path_telemetry section in /api/stats.

Verifies that:
1. The /api/stats endpoint includes a ``path_telemetry`` block with the
   expected fields when telemetry is available.
2. The endpoint gracefully degrades when the telemetry module cannot be
   imported or raises an exception.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# path  &  imports
# ---------------------------------------------------------------------------

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient

# We import the app module (which may register routes on import) and keep a
# reference to the original ``server`` module so we can restore it.
import dashboard.server as ds
from dashboard.server import app


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Test client for the dashboard FastAPI app."""
    return TestClient(app)


def _broker_snapshot_down():
    """Return a snapshot that looks like broker is unreachable."""
    return {"dashboard": None, "health": None}


@pytest.fixture(autouse=True)
def patch_broker_snapshot():
    """Provide a healthy broker snapshot so /api/stats returns real data."""
    original = ds._broker_snapshot

    async def healthy_snapshot(*, force_refresh: bool = False):
        return {
            "dashboard": {
                "broker": {
                    "status": "running",
                    "agents_online": 5,
                    "total_intents": 100,
                    "routed": 90,
                    "failed": 2,
                    "agent_queues": {},
                },
            },
            "health": {"healthy": True},
        }

    ds._broker_snapshot = healthy_snapshot
    yield
    ds._broker_snapshot = original


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

FAKE_TELEMETRY_BLOCK = {
    "native_count": 14,
    "bridged_count": 6,
    "aggregate_latency_ms": 352.1,
    "count_by_agent": {
        "quantumarb": 8,
        "kashclaw": 7,
        "gemma4": 5,
    },
    "count_by_mode": {
        "native": 14,
        "bridged": 6,
    },
}


@pytest.fixture
def patch_telemetry_available():
    """Make PATH_TELEMETRY_AVAILABLE = True and patch make_telemetry_block."""
    original_available = ds.PATH_TELEMETRY_AVAILABLE
    original_fn = ds.make_telemetry_block

    ds.PATH_TELEMETRY_AVAILABLE = True
    ds.make_telemetry_block = lambda: FAKE_TELEMETRY_BLOCK  # type: ignore[assignment]

    yield

    ds.PATH_TELEMETRY_AVAILABLE = original_available
    ds.make_telemetry_block = original_fn


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestOperatorVisibility:
    """Tests for the path_telemetry block in /api/stats."""

    def test_path_telemetry_present(self, client, patch_telemetry_available):
        """When telemetry is available, /api/stats includes a
        ``path_telemetry`` key with the expected structure."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200, resp.text

        payload = resp.json()
        assert "path_telemetry" in payload, (
            f"Expected 'path_telemetry' in response keys: {list(payload.keys())}"
        )

        pt = payload["path_telemetry"]
        assert pt["native_count"] == 14
        assert pt["bridged_count"] == 6
        assert pt["aggregate_latency_ms"] == 352.1
        assert pt["count_by_agent"] == {"quantumarb": 8, "kashclaw": 7, "gemma4": 5}
        assert pt["count_by_mode"] == {"native": 14, "bridged": 6}

    def test_path_telemetry_fields_present(self, client, patch_telemetry_available):
        """Ensure all five mandatory keys exist in the telemetry block."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200

        pt = resp.json()["path_telemetry"]
        expected_keys = {
            "native_count",
            "bridged_count",
            "aggregate_latency_ms",
            "count_by_agent",
            "count_by_mode",
        }
        assert expected_keys.issubset(pt.keys()), (
            f"Missing keys: {expected_keys - set(pt.keys())}"
        )

    def test_path_telemetry_types(self, client, patch_telemetry_available):
        """Verify the types of each telemetry field."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200

        pt = resp.json()["path_telemetry"]
        assert isinstance(pt["native_count"], int)
        assert isinstance(pt["bridged_count"], int)
        assert isinstance(pt["aggregate_latency_ms"], (int, float))
        assert isinstance(pt["count_by_agent"], dict)
        assert isinstance(pt["count_by_mode"], dict)

    def test_path_telemetry_zeros_when_unavailable(self, client):
        """When PATH_TELEMETRY_AVAILABLE is False, the block is present with
        all-zero / empty values."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200

        pt = resp.json().get("path_telemetry")
        assert pt is not None, "path_telemetry should still appear when unavailable"
        assert pt["native_count"] == 0
        assert pt["bridged_count"] == 0
        assert pt["aggregate_latency_ms"] == 0.0
        assert pt["count_by_agent"] == {}
        assert pt["count_by_mode"] == {}

    def test_path_telemetry_import_error_graceful(self, client):
        """Simulate an ImportError by toggling the flag — the endpoint must
        not crash and still return valid JSON with the fallback block."""
        original_available = ds.PATH_TELEMETRY_AVAILABLE
        ds.PATH_TELEMETRY_AVAILABLE = False
        try:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            payload = resp.json()
            assert "path_telemetry" in payload
            assert payload["path_telemetry"]["native_count"] == 0
            assert payload["path_telemetry"]["count_by_agent"] == {}
        finally:
            ds.PATH_TELEMETRY_AVAILABLE = original_available

    def test_path_telemetry_exception_in_block_graceful(self, client):
        """If make_telemetry_block() raises, the endpoint should still return
        200 with the fallback zero block."""
        original_available = ds.PATH_TELEMETRY_AVAILABLE
        original_fn = ds.make_telemetry_block

        ds.PATH_TELEMETRY_AVAILABLE = True

        def _broken_block():
            raise RuntimeError("telemetry module broken")

        ds.make_telemetry_block = _broken_block  # type: ignore[assignment]

        try:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            payload = resp.json()
            assert "path_telemetry" in payload
            pt = payload["path_telemetry"]
            assert pt["native_count"] == 0
            assert pt["bridged_count"] == 0
            assert pt["count_by_agent"] == {}
        finally:
            ds.PATH_TELEMETRY_AVAILABLE = original_available
            ds.make_telemetry_block = original_fn

    def test_other_stats_structure_preserved(self, client, patch_telemetry_available):
        """Adding path_telemetry should not break the existing broker stats."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        payload = resp.json()

        # core broker stats should still be present
        assert "broker" in payload
        broker = payload["broker"]
        assert "state" in broker
        assert "stats" in broker
        assert "dashboard_started_at" in payload

    def test_path_telemetry_zeros_from_get_summary(self, client):
        """When the collector exists but has no records, the block still
        reflects zero counts."""
        # Use the real module singleton (which starts empty)
        from simp.telemetry.path_telemetry import path_telemetry as collector
        collector.clear()

        original_available = ds.PATH_TELEMETRY_AVAILABLE
        original_fn = ds.make_telemetry_block
        ds.PATH_TELEMETRY_AVAILABLE = True
        ds.make_telemetry_block = lambda: {  # type: ignore[assignment]
            "native_count": 0,
            "bridged_count": 0,
            "aggregate_latency_ms": 0.0,
            "count_by_agent": {},
            "count_by_mode": {},
        }

        try:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            pt = resp.json()["path_telemetry"]
            assert pt["native_count"] == 0
            assert pt["aggregate_latency_ms"] == 0.0
            assert pt["count_by_agent"] == {}
        finally:
            ds.PATH_TELEMETRY_AVAILABLE = original_available
            ds.make_telemetry_block = original_fn
