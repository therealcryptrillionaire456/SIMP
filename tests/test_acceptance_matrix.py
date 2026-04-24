"""
SIMP Tranche 20 — Acceptance Matrix & Migration Readiness

Verifies:
  A) Route Contract Surface — if simp/server/route_contract.py exists
  B) Error Taxonomy — if simp/server/error_taxonomy.py exists
  C) Path Telemetry Shape — if simp/telemetry/path_telemetry.py exists
  D) Compatibility Perimeter Doc exists
  E) Operator Visibility — if dashboard/server.py and path_telemetry exist
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


# ======================================================================
# A) Route Contract Surface
# ======================================================================

try:
    from simp.server.route_contract import (
        RouteEnvelope,
        RouteStatus,
        StreamAvailability,
    )
    ROUTE_CONTRACT_AVAILABLE = True
except ImportError:
    ROUTE_CONTRACT_AVAILABLE = False


@pytest.mark.skipif(not ROUTE_CONTRACT_AVAILABLE, reason="route_contract.py not available")
class TestRouteContractSurface:
    """A) Route Contract Surface — envelope, status, availability, to_dict()."""

    def test_default_creation_has_expected_fields(self):
        """RouteEnvelope default has intent_id, trace_id, status."""
        env = RouteEnvelope()
        assert env.intent_id.startswith("intent_")
        assert len(env.trace_id) == 32
        assert env.status == RouteStatus.ACCEPTED

    def test_all_route_status_variants(self):
        """All RouteStatus variants exist with correct values."""
        expected = {
            "ACCEPTED": "accepted",
            "QUEUED": "queued",
            "IMMEDIATE": "immediate",
            "FAILED": "failed",
            "INVALID_SIGNATURE": "invalid_signature",
        }
        for name, val in expected.items():
            member = getattr(RouteStatus, name)
            assert member.value == val

    def test_all_stream_availability_variants(self):
        """All StreamAvailability variants exist with correct values."""
        expected = {
            "STREAM_AVAILABLE": "stream_available",
            "STREAM_UNAVAILABLE": "stream_unavailable",
            "NON_STREAM_FALLBACK": "non_stream_fallback",
        }
        for name, val in expected.items():
            member = getattr(StreamAvailability, name)
            assert member.value == val

    def test_to_dict_has_all_expected_keys(self):
        """to_dict() returns all 15 expected keys."""
        env = RouteEnvelope()
        d = env.to_dict()
        expected_keys = {
            "intent_id", "trace_id", "correlation_id",
            "status", "stream_availability", "stream_url",
            "invocation_mode", "bridge_mode",
            "delivery_status", "delivery_method", "delivery_latency_ms",
            "error_code", "error_message",
            "result", "created_at",
        }
        assert set(d.keys()) == expected_keys


# ======================================================================
# B) Error Taxonomy
# ======================================================================

try:
    from simp.server.error_taxonomy import (
        SimpErrorCode,
        SimpError,
        ERROR_HTTP_MAP,
    )
    ERROR_TAXONOMY_AVAILABLE = True
except ImportError:
    ERROR_TAXONOMY_AVAILABLE = False


@pytest.mark.skipif(not ERROR_TAXONOMY_AVAILABLE, reason="error_taxonomy.py not available")
class TestErrorTaxonomy:
    """B) Error Taxonomy — codes, SimpError, HTTP map."""

    def test_all_11_codes_exist(self):
        """SimpErrorCode has exactly 11 members."""
        codes = list(SimpErrorCode)
        assert len(codes) == 11

    def test_simperror_to_dict_has_all_keys(self):
        """SimpError.to_dict() returns error_id, code, message, detail, http_status."""
        err = SimpError(code=SimpErrorCode.NOT_FOUND, message="not found")
        d = err.to_dict()
        assert set(d.keys()) == {"error_id", "code", "message", "detail", "http_status"}

    def test_to_response_has_success_false_and_error_key(self):
        """SimpError.to_response() returns success: False and error key."""
        err = SimpError(code=SimpErrorCode.UNAUTHORIZED, message="bad key")
        resp = err.to_response()
        assert resp["success"] is False
        assert "error" in resp

    def test_error_http_map_has_all_codes(self):
        """ERROR_HTTP_MAP has entries for all 11 SimpErrorCode members."""
        for code in SimpErrorCode:
            assert code in ERROR_HTTP_MAP, f"{code.value} missing from ERROR_HTTP_MAP"

    def test_http_status_401_for_invalid_signature(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.INVALID_SIGNATURE] == 401

    def test_http_status_403_for_unauthorized(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.UNAUTHORIZED] == 403

    def test_http_status_404_for_not_found(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.NOT_FOUND] == 404

    def test_http_status_400_for_invalid_request(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.INVALID_REQUEST] == 400

    def test_http_status_429_for_rate_limited(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.RATE_LIMITED] == 429

    def test_http_status_500_for_internal_error(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.INTERNAL_ERROR] == 500

    def test_http_status_504_for_timeout(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.TIMEOUT] == 504


# ======================================================================
# C) Path Telemetry Shape
# ======================================================================

try:
    from simp.telemetry.path_telemetry import make_telemetry_block
    PATH_TELEMETRY_AVAILABLE = True
except ImportError:
    PATH_TELEMETRY_AVAILABLE = False


@pytest.mark.skipif(not PATH_TELEMETRY_AVAILABLE, reason="path_telemetry.py not available")
class TestPathTelemetryShape:
    """C) Path Telemetry Shape — make_telemetry_block output structure."""

    def test_make_telemetry_block_has_all_keys(self):
        """make_telemetry_block returns invocation_mode, bridge_mode, source,
        latency_ms, delivery_latency_ms."""
        block = make_telemetry_block("native", 10.0, "broker", "quantumarb")
        expected_keys = {
            "invocation_mode", "bridge_mode", "source", "agent_id",
            "latency_ms", "delivery_latency_ms", "timestamp",
        }
        assert set(block.keys()) == expected_keys

    def test_native_mode_bridge_mode_none(self):
        """Native mode gets bridge_mode 'none'."""
        block = make_telemetry_block("native", 5.0, "test", "agent_a")
        assert block["bridge_mode"] == "none"

    def test_mcp_bridge_mode_bridge_mode_mcp_compat(self):
        """mcp_bridge mode gets bridge_mode 'mcp_compat'."""
        block = make_telemetry_block("mcp_bridge", 5.0, "test", "agent_b")
        assert block["bridge_mode"] == "mcp_compat"


# ======================================================================
# D) Compatibility Perimeter Doc Exists
# ======================================================================

class TestCompatibilityPerimeterDoc:
    """D) COMPATIBILITY_PERIMETER.md exists and references migration/native."""

    DOC_PATH = _PROJECT_ROOT / "docs" / "COMPATIBILITY_PERIMETER.md"

    def test_compatibility_perimeter_doc_exists(self):
        """COMPATIBILITY_PERIMETER.md exists on disk."""
        assert os.path.exists(str(self.DOC_PATH)), (
            f"Expected {self.DOC_PATH} to exist"
        )

    def test_doc_mentions_migration_or_native(self):
        """The doc mentions 'migration' or 'native'."""
        assert os.path.exists(str(self.DOC_PATH))
        content = self.DOC_PATH.read_text(encoding="utf-8")
        assert "migration" in content or "native" in content, (
            "COMPATIBILITY_PERIMETER.md should mention 'migration' or 'native'"
        )


# ======================================================================
# E) Operator Visibility
# ======================================================================

try:
    from fastapi.testclient import TestClient
    from dashboard.server import app
    import dashboard.server as ds
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False


@pytest.mark.skipif(not DASHBOARD_AVAILABLE, reason="dashboard/server.py not importable")
@pytest.mark.skipif(not PATH_TELEMETRY_AVAILABLE, reason="path_telemetry.py not available")
class TestOperatorVisibility:
    """E) Operator Visibility — /api/stats returns 200 with path_telemetry."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def patch_broker_for_stats(self, monkeypatch):
        """Provide a healthy broker snapshot so the endpoint doesn't
        try to contact a real broker."""
        async def fake_broker_snapshot(*, force_refresh=False):
            return {
                "dashboard": {
                    "broker": {
                        "status": "running",
                        "agents_online": 3,
                        "total_intents": 50,
                        "routed": 45,
                        "failed": 2,
                        "agent_queues": {},
                    },
                },
                "health": {"healthy": True},
            }
        monkeypatch.setattr(ds, "_broker_snapshot", fake_broker_snapshot)

    @pytest.fixture(autouse=True)
    def patch_make_telemetry_block(self, monkeypatch):
        """Ensure PATH_TELEMETRY_AVAILABLE and a working block."""
        monkeypatch.setattr(ds, "PATH_TELEMETRY_AVAILABLE", True)

        def fake_block():
            return {
                "native_count": 10,
                "bridged_count": 3,
                "aggregate_latency_ms": 45.2,
                "count_by_agent": {"quantumarb": 5, "kashclaw": 8},
                "count_by_mode": {"native": 10, "mcp_bridge": 3},
            }
        monkeypatch.setattr(ds, "make_telemetry_block", fake_block)

    def test_api_stats_returns_200(self, client):
        """Test /api/stats returns 200."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200, resp.text

    def test_path_telemetry_present_in_response(self, client):
        """path_telemetry section present in /api/stats response."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        payload = resp.json()
        assert "path_telemetry" in payload, (
            f"Expected 'path_telemetry' in response keys: {list(payload.keys())}"
        )
        pt = payload["path_telemetry"]
        assert pt["native_count"] == 10
        assert pt["bridged_count"] == 3
        assert pt["aggregate_latency_ms"] == 45.2
        assert pt["count_by_agent"] == {"quantumarb": 5, "kashclaw": 8}
        assert pt["count_by_mode"] == {"native": 10, "mcp_bridge": 3}
