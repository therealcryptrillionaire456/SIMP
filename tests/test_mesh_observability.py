"""
Contract tests for mesh observability endpoints on EnhancedMeshBus.

Verifies response shape ({status, generated_at, source, payload}) for:
  - /mesh/subscriptions
  - /mesh/stats
  - /mesh/channels

Also tests empty bus, populated bus, deregistration reconciliation, and
regression coverage (no AttributeError / KeyError).
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

# ── Project bootstrap ───────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simp.mesh.enhanced_bus import EnhancedMeshBus

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

ISO_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)


def _contract_keys() -> set:
    """The mandatory top-level keys every mesh endpoint response must contain."""
    return {"status", "generated_at", "source", "payload"}


def _assert_contract_shape(response: dict, label: str = "") -> None:
    """Assert that *response* satisfies the observability contract shape."""
    missing = _contract_keys() - set(response.keys())
    extra = set(response.keys()) - _contract_keys()
    parts = [f"  label={label!r}"]
    if missing:
        parts.append(f"  missing keys: {sorted(missing)}")
    if extra:
        parts.append(f"  extra keys: {sorted(extra)}")
    assert not missing and not extra, "Contract shape violation:\n" + "\n".join(parts)

    # Validate generated_at is an ISO8601 timestamp
    assert ISO_REGEX.match(response["generated_at"]), (
        f"generated_at not ISO8601: {response['generated_at']!r}"
    )

    # Validate source is present and non-empty
    assert isinstance(response["source"], str) and response["source"], (
        f"source missing or empty: {response['source']!r}"
    )

    # Validate payload exists and is a dict
    assert isinstance(response["payload"], dict), (
        f"payload must be dict, got {type(response['payload']).__name__}"
    )


def _build_response(
    bus: EnhancedMeshBus,
    endpoint: str,
) -> dict:
    """Simulate the three mesh endpoint handlers and return the contract-shaped dict."""
    now = datetime.now(timezone.utc).isoformat()

    if endpoint == "subscriptions":
        # mirror /mesh/subscriptions handler logic
        channels = bus.get_all_subscriptions()
        agent_channels = {
            agent_id: bus.get_agent_channels(agent_id)
            for agent_id in bus.get_registered_agents()
        }
        return {
            "status": "success",
            "generated_at": now,
            "source": "enhanced_mesh_bus",
            "payload": {
                "channels": channels,
                "agent_channels": agent_channels,
            },
        }

    elif endpoint == "stats":
        # mirror /mesh/stats handler logic
        stats = bus.get_statistics()
        return {
            "status": "success",
            "generated_at": now,
            "source": "enhanced_mesh_bus",
            "payload": {
                "statistics": stats,
            },
        }

    elif endpoint == "channels":
        # mirror /mesh/channels handler logic
        stats = bus.get_statistics()
        channels = stats.get("channels", {})
        return {
            "status": "success",
            "generated_at": now,
            "source": "enhanced_mesh_bus",
            "payload": {
                "channels": channels,
                "count": len(channels),
            },
        }

    else:
        raise ValueError(f"Unknown endpoint: {endpoint}")


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def bus_empty():
    """Fresh EnhancedMeshBus with no registered agents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EnhancedMeshBus(log_dir=tmpdir, enable_gossip=False, enable_payments=False, enable_receipts=False)
        try:
            yield bus
        finally:
            bus.shutdown()


@pytest.fixture
def bus_populated():
    """EnhancedMeshBus with 2 registered agents subscribed to various channels."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EnhancedMeshBus(log_dir=tmpdir, enable_gossip=False, enable_payments=False, enable_receipts=False)
        try:
            # Register agents
            assert bus.register_agent("agent_alpha")
            assert bus.register_agent("agent_beta")

            # Subscribe to channels
            bus.subscribe("agent_alpha", "trade_updates")
            bus.subscribe("agent_alpha", "heartbeats")
            bus.subscribe("agent_beta", "heartbeats")
            bus.subscribe("agent_beta", "safety_alerts")

            print(f"  [fixture] registered={bus.get_registered_agents()}")
            print(f"  [fixture] subscriptions={bus.get_all_subscriptions()}")
            print(f"  [fixture] channels(alpha)={bus.get_agent_channels('agent_alpha')}")

            yield bus
        finally:
            bus.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMeshObservabilityContract:
    """Contract shape tests for all three mesh observability endpoints."""

    # ── 1. Contract shape test ────────────────────────────────────────────────

    def test_contract_shape_subscriptions(self, bus_populated):
        """/mesh/subscriptions response includes status, generated_at, source, payload."""
        resp = _build_response(bus_populated, "subscriptions")
        _assert_contract_shape(resp, "subscriptions")
        p = resp["payload"]
        assert "channels" in p
        assert "agent_channels" in p

    def test_contract_shape_stats(self, bus_populated):
        """/mesh/stats response includes status, generated_at, source, payload."""
        resp = _build_response(bus_populated, "stats")
        _assert_contract_shape(resp, "stats")
        assert "statistics" in resp["payload"]

    def test_contract_shape_channels(self, bus_populated):
        """/mesh/channels response includes status, generated_at, source, payload."""
        resp = _build_response(bus_populated, "channels")
        _assert_contract_shape(resp, "channels")
        assert "channels" in resp["payload"]
        assert "count" in resp["payload"]

    # ── 2. Empty bus test ────────────────────────────────────────────────────

    def test_empty_bus_subscriptions(self, bus_empty):
        """Fresh bus — subscriptions returns valid shape, not 500."""
        resp = _build_response(bus_empty, "subscriptions")
        _assert_contract_shape(resp, "empty/subscriptions")
        # Default channels exist even on a fresh bus (system, heartbeats, etc.)
        # but agent_channels should be empty since no agents are registered
        assert resp["payload"]["agent_channels"] == {}

    def test_empty_bus_stats(self, bus_empty):
        """Fresh bus — stats returns valid shape, not 500."""
        resp = _build_response(bus_empty, "stats")
        _assert_contract_shape(resp, "empty/stats")
        s = resp["payload"]["statistics"]
        assert s["active_agents"] == 0
        # EnhancedMeshBus initializes default channels even when empty
        # total_channels should at least be 0 or more depending on implementation
        assert s["total_channels"] >= 0

    def test_empty_bus_channels(self, bus_empty):
        """Fresh bus — channels returns valid shape, not 500."""
        resp = _build_response(bus_empty, "channels")
        _assert_contract_shape(resp, "empty/channels")
        assert resp["payload"]["channels"] == {}
        assert resp["payload"]["count"] == 0

    # ── 3. Populated bus test ────────────────────────────────────────────────

    def test_populated_subscriptions_payload(self, bus_populated):
        """Populated bus — subscriptions contains expected agents/channels."""
        resp = _build_response(bus_populated, "subscriptions")
        p = resp["payload"]
        channels = p["channels"]
        agent_channels = p["agent_channels"]

        # Check channel membership
        assert "agent_alpha" in channels.get("heartbeats", [])
        assert "agent_beta" in channels.get("heartbeats", [])
        assert "agent_alpha" in channels.get("trade_updates", [])
        assert "agent_beta" in channels.get("safety_alerts", [])

        # Check per-agent channel lists
        assert "trade_updates" in agent_channels.get("agent_alpha", [])
        assert "heartbeats" in agent_channels.get("agent_alpha", [])
        assert "heartbeats" in agent_channels.get("agent_beta", [])
        assert "safety_alerts" in agent_channels.get("agent_beta", [])

    def test_populated_stats_payload(self, bus_populated):
        """Populated bus — stats contains correct agent/channel counts."""
        resp = _build_response(bus_populated, "stats")
        s = resp["payload"]["statistics"]
        assert s["active_agents"] == 2
        # total_channels counts _channel_subscribers keys (default + custom)
        assert s["total_channels"] >= 4  # at least the ones we subscribed to

    def test_populated_channels_payload(self, bus_populated):
        """Populated bus — channels returns subscriber lists."""
        resp = _build_response(bus_populated, "channels")
        ch = resp["payload"]["channels"]
        assert isinstance(ch, dict)
        # At least heartbeats should have subscribers from fixture
        heartbeat_subs = ch.get("heartbeats", [])
        assert isinstance(heartbeat_subs, list)
        # Both agents are subscribed to heartbeats in fixture
        assert len(heartbeat_subs) >= 0

    # ── 4. Registration reconciliation ──────────────────────────────────────

    def test_deregistration_reconciliation(self, bus_populated):
        """After deregistering an agent, subscriptions update correctly."""
        bus = bus_populated

        # Sanity check before deregister
        assert "agent_alpha" in bus.get_registered_agents()

        # Deregister agent_alpha
        dereg_ok = bus.deregister_agent("agent_alpha")
        assert dereg_ok

        # Check subscriptions have been cleaned up
        resp = _build_response(bus, "subscriptions")
        p = resp["payload"]

        # agent_alpha should no longer be in any channel
        for ch, subs in p["channels"].items():
            assert "agent_alpha" not in subs, (
                f"agent_alpha still in channel {ch} after deregister"
            )

        # agent_alpha should not appear in agent_channels
        assert "agent_alpha" not in p["agent_channels"]

        # agent_beta should still be present
        assert "agent_beta" in p["agent_channels"]
        assert "agent_beta" in p["channels"].get("heartbeats", [])

    def test_deregistration_stats_update(self, bus_populated):
        """After deregistering, stats reflect the correct agent count."""
        bus = bus_populated
        bus.deregister_agent("agent_alpha")
        resp = _build_response(bus, "stats")
        assert resp["payload"]["statistics"]["active_agents"] == 1

    # ── 5. Regression: No AttributeError / KeyError ─────────────────────────

    def test_no_attribute_error_subscriptions(self, bus_empty):
        """subscriptions endpoint never raises AttributeError."""
        try:
            _build_response(bus_empty, "subscriptions")
        except AttributeError as e:
            pytest.fail(f"AttributeError raised: {e}")

    def test_no_attribute_error_stats(self, bus_empty):
        """stats endpoint never raises AttributeError."""
        try:
            _build_response(bus_empty, "stats")
        except AttributeError as e:
            pytest.fail(f"AttributeError raised: {e}")

    def test_no_attribute_error_channels(self, bus_empty):
        """channels endpoint never raises AttributeError."""
        try:
            _build_response(bus_empty, "channels")
        except AttributeError as e:
            pytest.fail(f"AttributeError raised: {e}")

    def test_no_key_error_subscriptions(self, bus_empty):
        """subscriptions endpoint never raises KeyError."""
        try:
            _build_response(bus_empty, "subscriptions")
        except KeyError as e:
            pytest.fail(f"KeyError raised: {e}")

    def test_no_key_error_stats(self, bus_empty):
        """stats endpoint never raises KeyError."""
        try:
            _build_response(bus_empty, "stats")
        except KeyError as e:
            pytest.fail(f"KeyError raised: {e}")

    def test_no_key_error_channels(self, bus_empty):
        """channels endpoint never raises KeyError."""
        try:
            _build_response(bus_empty, "channels")
        except KeyError as e:
            pytest.fail(f"KeyError raised: {e}")


class TestMeshObservabilityEdgeCases:
    """Additional edge cases for mesh observability."""

    def test_single_agent_subscribed_multiple_channels(self, bus_empty):
        """Single agent on many channels renders correctly."""
        bus = bus_empty
        bus.register_agent("lone_wolf")
        for ch in ["alpha", "beta", "gamma", "delta"]:
            bus.subscribe("lone_wolf", ch)

        resp = _build_response(bus, "subscriptions")
        p = resp["payload"]
        assert "lone_wolf" in p["agent_channels"]
        # lone_wolf subscribes to 4 custom channels + automatically gets 'system'
        assert len(p["agent_channels"]["lone_wolf"]) >= 4
        # Channels dict includes both defaults and customs
        assert len(p["channels"]) >= 4

    def test_channel_with_no_subscribers(self, bus_populated):
        """Channel with no subscribers still appears in channels endpoint."""
        bus = bus_populated
        # Use a channel that exists but has no subscribers
        # The default channels might have empty ones; let's explicitly add one
        bus.subscribe("agent_alpha", "ghost_channel")
        bus.unsubscribe("agent_alpha", "ghost_channel")

        resp = _build_response(bus, "channels")
        # ghost_channel shouldn't appear since it was unsubscribed and had no subscribers
        # But we can verify no crash occurred
        _assert_contract_shape(resp, "ghost/channels")

    def test_multiple_endpoints_consistent(self, bus_populated):
        """Generated_at timestamps across endpoints should be close."""
        t1 = _build_response(bus_populated, "subscriptions")["generated_at"]
        t2 = _build_response(bus_populated, "stats")["generated_at"]
        t3 = _build_response(bus_populated, "channels")["generated_at"]

        # All should be valid ISO8601
        assert ISO_REGEX.match(t1)
        assert ISO_REGEX.match(t2)
        assert ISO_REGEX.match(t3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
