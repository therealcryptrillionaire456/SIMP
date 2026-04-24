"""
Tests for SIMP Route Contract — Tranche 17

Verifies RouteEnvelope default creation, status serialization,
stream availability values, to_dict() key coverage, unique intent_id
generation, correlation_id round-trip, error states, and stream_url.
"""

import json
import uuid

from simp.server.route_contract import (
    RouteEnvelope,
    RouteStatus,
    StreamAvailability,
)


# ---------------------------------------------------------------------------
# Test: RouteEnvelope default creation
# ---------------------------------------------------------------------------

def test_default_creation():
    """RouteEnvelope creates with sensible defaults."""
    env = RouteEnvelope()
    assert env.intent_id.startswith("intent_")
    assert len(env.trace_id) == 32  # uuid4 hex
    assert env.correlation_id == ""
    assert env.status == RouteStatus.ACCEPTED
    assert env.stream_availability == StreamAvailability.STREAM_UNAVAILABLE
    assert env.stream_url == ""
    assert env.invocation_mode == "native"
    assert env.bridge_mode == "none"
    assert env.delivery_status == "pending"
    assert env.delivery_method == "direct"
    assert env.delivery_latency_ms == 0.0
    assert env.error_code == ""
    assert env.error_message == ""
    assert env.result is None
    assert env.created_at.endswith("Z") or "+" in env.created_at  # ISO8601


# ---------------------------------------------------------------------------
# Test: All RouteStatus values serialize correctly
# ---------------------------------------------------------------------------

def test_route_status_values():
    """All five RouteStatus enum members have expected string values."""
    assert RouteStatus.ACCEPTED.value == "accepted"
    assert RouteStatus.QUEUED.value == "queued"
    assert RouteStatus.IMMEDIATE.value == "immediate"
    assert RouteStatus.FAILED.value == "failed"
    assert RouteStatus.INVALID_SIGNATURE.value == "invalid_signature"


def test_route_status_serialization():
    """Each RouteStatus serializes via to_dict() correctly."""
    for status in RouteStatus:
        env = RouteEnvelope(status=status)
        d = env.to_dict()
        assert d["status"] == status.value


def test_route_status_json_serializable():
    """RouteStatus values round-trip through JSON."""
    for status in RouteStatus:
        env = RouteEnvelope(status=status)
        raw = json.dumps(env.to_dict())
        restored = json.loads(raw)
        assert restored["status"] == status.value


# ---------------------------------------------------------------------------
# Test: All StreamAvailability values serialize correctly
# ---------------------------------------------------------------------------

def test_stream_availability_values():
    """All three StreamAvailability enum members have expected string values."""
    assert StreamAvailability.STREAM_AVAILABLE.value == "stream_available"
    assert StreamAvailability.STREAM_UNAVAILABLE.value == "stream_unavailable"
    assert StreamAvailability.NON_STREAM_FALLBACK.value == "non_stream_fallback"


def test_stream_availability_serialization():
    """Each StreamAvailability serializes via to_dict() correctly."""
    for sa in StreamAvailability:
        env = RouteEnvelope(stream_availability=sa)
        d = env.to_dict()
        assert d["stream_availability"] == sa.value


# ---------------------------------------------------------------------------
# Test: to_dict() includes all expected keys
# ---------------------------------------------------------------------------

def test_to_dict_keys():
    """to_dict() returns exactly the 15 expected keys."""
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
    assert set(d.keys()) == expected_keys, (
        f"Expected keys {expected_keys}, got {set(d.keys())}"
    )


# ---------------------------------------------------------------------------
# Test: intent_id generates on each creation
# ---------------------------------------------------------------------------

def test_intent_id_unique():
    """Each RouteEnvelope gets a unique intent_id."""
    ids = {RouteEnvelope().intent_id for _ in range(100)}
    assert len(ids) == 100, "intent_id collision detected"


def test_intent_id_format():
    """intent_id follows the 'intent_<hex>' pattern."""
    env = RouteEnvelope()
    assert env.intent_id.startswith("intent_")
    hex_part = env.intent_id[len("intent_"):]
    assert len(hex_part) == 12
    int(hex_part, 16)  # raises ValueError if not valid hex


# ---------------------------------------------------------------------------
# Test: correlation_id round-trip
# ---------------------------------------------------------------------------

def test_correlation_id_round_trip():
    """correlation_id set during construction appears in to_dict()."""
    corr_id = "corr_" + uuid.uuid4().hex[:8]
    env = RouteEnvelope(correlation_id=corr_id)
    assert env.correlation_id == corr_id
    d = env.to_dict()
    assert d["correlation_id"] == corr_id


def test_correlation_id_json_round_trip():
    """correlation_id round-trips through JSON."""
    corr_id = "test-correlation-001"
    env = RouteEnvelope(correlation_id=corr_id)
    raw = json.dumps(env.to_dict())
    restored = json.loads(raw)
    assert restored["correlation_id"] == corr_id


# ---------------------------------------------------------------------------
# Test: error state serialization
# ---------------------------------------------------------------------------

def test_error_state_serialization():
    """Error code and message appear correctly in to_dict()."""
    env = RouteEnvelope(
        status=RouteStatus.FAILED,
        error_code="ROUTE_FAILED",
        error_message="No matching agent for intent type",
    )
    d = env.to_dict()
    assert d["status"] == "failed"
    assert d["error_code"] == "ROUTE_FAILED"
    assert d["error_message"] == "No matching agent for intent type"


def test_invalid_signature_error():
    """INVALID_SIGNATURE status with error details serializes correctly."""
    env = RouteEnvelope(
        status=RouteStatus.INVALID_SIGNATURE,
        error_code="SIG_MISMATCH",
        error_message="HMAC signature does not match",
    )
    d = env.to_dict()
    assert d["status"] == "invalid_signature"
    assert d["error_code"] == "SIG_MISMATCH"


# ---------------------------------------------------------------------------
# Test: stream_availability with url
# ---------------------------------------------------------------------------

def test_stream_available_with_url():
    """STREAM_AVAILABLE status with stream_url serializes correctly."""
    env = RouteEnvelope(
        stream_availability=StreamAvailability.STREAM_AVAILABLE,
        stream_url="/agentic/events/stream/intent_abc123",
    )
    d = env.to_dict()
    assert d["stream_availability"] == "stream_available"
    assert d["stream_url"] == "/agentic/events/stream/intent_abc123"


def test_non_stream_fallback():
    """NON_STREAM_FALLBACK status serializes correctly."""
    env = RouteEnvelope(
        stream_availability=StreamAvailability.NON_STREAM_FALLBACK,
    )
    d = env.to_dict()
    assert d["stream_availability"] == "non_stream_fallback"
    assert d["stream_url"] == ""  # no url expected


# ---------------------------------------------------------------------------
# Test: to_dict() result field
# ---------------------------------------------------------------------------

def test_result_dict_in_to_dict():
    """result dict appears in to_dict() output."""
    result_data = {"matched_agent": "quantumarb", "confidence": 0.95}
    env = RouteEnvelope(result=result_data)
    d = env.to_dict()
    assert d["result"] == result_data


def test_result_none_in_to_dict():
    """result is None when not provided."""
    env = RouteEnvelope()
    d = env.to_dict()
    assert d["result"] is None


# ---------------------------------------------------------------------------
# Test: delivery fields
# ---------------------------------------------------------------------------

def test_delivery_fields_custom():
    """Delivery-related fields serialize correctly when customized."""
    env = RouteEnvelope(
        delivery_status="delivered",
        delivery_method="http_post",
        delivery_latency_ms=12.5,
    )
    d = env.to_dict()
    assert d["delivery_status"] == "delivered"
    assert d["delivery_method"] == "http_post"
    assert d["delivery_latency_ms"] == 12.5


# ---------------------------------------------------------------------------
# Test: invocation and bridge modes
# ---------------------------------------------------------------------------

def test_invocation_mode():
    """invocation_mode and bridge_mode serialize correctly."""
    env = RouteEnvelope(invocation_mode="a2a", bridge_mode="projectx")
    d = env.to_dict()
    assert d["invocation_mode"] == "a2a"
    assert d["bridge_mode"] == "projectx"
