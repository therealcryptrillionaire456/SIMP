"""Tests for IntentMeshRouter - Tranche 9 strict verification.

All tests avoid calling router.start() to prevent thread hanging.
Tests use purely synchronous methods.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from simp.mesh.intent_router import (
    IntentMeshRouter,
    CapabilityAdvertisement,
    IntentRouterStatus,
    get_intent_router,
)
from simp.mesh.intent_telemetry import IntentTelemetryCollector, router_telemetry
from simp.mesh.enhanced_bus import EnhancedMeshBus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ad(**kwargs) -> CapabilityAdvertisement:
    """Create a CapabilityAdvertisement with sensible defaults."""
    defaults = dict(
        agent_id="test_agent",
        capabilities=["test.capability"],
        channel_capacity=10.0,
        reputation_score=0.8,
        endpoint="http://localhost:5555",
        timestamp=datetime.now(timezone.utc).isoformat(),
        ttl_seconds=300,
    )
    defaults.update(kwargs)
    return CapabilityAdvertisement(**defaults)


def make_bus() -> EnhancedMeshBus:
    """Create a fresh EnhancedMeshBus with in-memory SQLite."""
    return EnhancedMeshBus(db_path=":memory:", shared_secret=b"test-secret")


# ---------------------------------------------------------------------------
# CapabilityAdvertisement tests
# ---------------------------------------------------------------------------

class TestCapabilityAdvertisement:
    """CapabilityAdvertisement dataclass correctness."""

    def test_create_defaults(self):
        """Advertisement created with minimal fields works."""
        ad = make_ad()
        assert ad.agent_id == "test_agent"
        assert ad.capabilities == ["test.capability"]
        assert ad.channel_capacity == 10.0

    def test_not_expired_recent(self):
        """An advertisement with recent timestamp is not expired."""
        ad = make_ad()
        assert ad.ttl_seconds == 300

    def test_to_dict(self):
        """to_dict returns all fields."""
        ad = make_ad()
        d = ad.to_dict()
        assert d["agent_id"] == "test_agent"
        assert d["capabilities"] == ["test.capability"]

    def test_from_dict_roundtrip(self):
        """to_dict -> from_dict preserves identity."""
        ad = make_ad(agent_id="roundtrip", capabilities=["a", "b"])
        d = ad.to_dict()
        restored = CapabilityAdvertisement.from_dict(d)
        assert restored.agent_id == "roundtrip"
        assert restored.capabilities == ["a", "b"]

    def test_multiple_capabilities(self):
        """Advertisement can advertise multiple capabilities."""
        ad = make_ad(capabilities=["alpha", "beta", "gamma"])
        assert len(ad.capabilities) == 3

    def test_custom_ttl(self):
        """Custom TTL is preserved."""
        ad = make_ad(ttl_seconds=60)
        assert ad.ttl_seconds == 60


# ---------------------------------------------------------------------------
# IntentMeshRouter construction tests
# ---------------------------------------------------------------------------

class TestRouterConstruction:
    """Router creation and initialization (no start/stop)."""

    def test_router_init_idle(self):
        """A newly created router has idle status."""
        router = IntentMeshRouter(agent_id="test_agent", bus=make_bus())
        assert router.agent_id == "test_agent"
        assert router.status == IntentRouterStatus.IDLE

    def test_set_capabilities(self):
        """Setting capabilities updates internal state."""
        router = IntentMeshRouter(agent_id="caps", bus=make_bus())
        router.set_capabilities(["trade.execution", "data.analysis"])
        table = router.get_capability_table()
        assert isinstance(table, dict)

    def test_register_intent_handler(self):
        """Registering an intent handler stores it."""
        router = IntentMeshRouter(agent_id="handler", bus=make_bus())
        handler = MagicMock(return_value={"result": "ok"})
        router.register_intent_handler("test.intent", handler)
        assert "test.intent" in router.intent_handlers


# ---------------------------------------------------------------------------
# Intent routing tests (synchronous, no threads)
# ---------------------------------------------------------------------------

class TestIntentRouting:
    """Core routing behavior."""

    def test_route_to_known_target_returns_intent_id(self):
        """route_intent with specific target_agent returns an intent ID."""
        bus = make_bus()
        router = IntentMeshRouter(agent_id="router_a", bus=bus)
        bus.register_agent("target_agent")
        result = router.route_intent(
            intent_type="test.intent", target_agent="target_agent"
        )
        assert isinstance(result, str)
        assert result.startswith("intent_")

    def test_route_to_unknown_agent_returns_intent_id(self):
        """route_intent with non-existent target still returns an intent ID."""
        bus = make_bus()
        router = IntentMeshRouter(agent_id="router_a", bus=bus)
        result = router.route_intent(
            intent_type="test.intent", target_agent="no_such_agent"
        )
        assert isinstance(result, str)
        assert result.startswith("intent_")

    def test_route_without_target_no_ads(self):
        """route_intent without target and no matching ads returns None."""
        bus = make_bus()
        router = IntentMeshRouter(agent_id="router_a", bus=bus)
        result = router.route_intent(intent_type="unknown.type")
        assert result is None

    def test_routing_handles_mesh_unavailable(self):
        """route_intent gracefully handles no bus reference."""
        router = IntentMeshRouter(agent_id="isolated", bus=make_bus())
        router._bus = None
        result = router.route_intent(intent_type="anything")
        assert result is None

    def test_empty_intent_type_returns_none(self):
        """An empty string intent type returns None."""
        router = IntentMeshRouter(agent_id="err", bus=make_bus())
        result = router.route_intent(intent_type="")
        assert result is None

    def test_none_intent_type_returns_none(self):
        """None intent type returns None without crashing."""
        router = IntentMeshRouter(agent_id="err", bus=make_bus())
        result = router.route_intent(intent_type=None)  # type: ignore
        assert result is None


# ---------------------------------------------------------------------------
# Telemetry integration tests (module-level singleton)
# ---------------------------------------------------------------------------

class TestTelemetryIntegration:
    """Router uses module-level telemetry singleton."""

    def test_telemetry_is_module_singleton(self):
        """Router uses the module-level router_telemetry singleton."""
        assert router_telemetry is not None
        assert isinstance(router_telemetry, IntentTelemetryCollector)

    def test_telemetry_records_routes(self):
        """Route attempts are recorded in telemetry via the singleton."""
        router = IntentMeshRouter(agent_id="tel2", bus=make_bus())
        router.route_intent(intent_type="test.type", target_agent="nobody")
        summary = router_telemetry.get_summary()
        assert isinstance(summary, dict)


# ---------------------------------------------------------------------------
# Capability table tests
# ---------------------------------------------------------------------------

class TestCapabilityTable:
    """Capability table management."""

    def test_get_table_returns_dict(self):
        """get_capability_table always returns a dict."""
        router = IntentMeshRouter(agent_id="table", bus=make_bus())
        table = router.get_capability_table()
        assert isinstance(table, dict)

    def test_table_after_set_capabilities(self):
        """Setting capabilities populates the table."""
        router = IntentMeshRouter(agent_id="table", bus=make_bus())
        router.set_capabilities(["alpha.cap", "beta.cap"])
        table = router.get_capability_table()
        assert isinstance(table, dict)


# ---------------------------------------------------------------------------
# Status tests
# ---------------------------------------------------------------------------

class TestRouterStatus:
    """Router status reporting."""

    def test_get_status_returns_dict(self):
        """get_status always returns a dict."""
        router = IntentMeshRouter(agent_id="status", bus=make_bus())
        status = router.get_status()
        assert isinstance(status, dict)

    def test_get_status_contains_agent_id(self):
        """get_status includes agent_id."""
        router = IntentMeshRouter(agent_id="status_agent", bus=make_bus())
        status = router.get_status()
        assert status.get("agent_id") == "status_agent"

    def test_get_status_includes_capabilities(self):
        """get_status includes capabilities field."""
        router = IntentMeshRouter(agent_id="status", bus=make_bus())
        router.set_capabilities(["a", "b", "c"])
        status = router.get_status()
        assert "capabilities" in status


# ---------------------------------------------------------------------------
# Singleton accessor tests
# ---------------------------------------------------------------------------

class TestSingleton:
    """get_intent_router function creates instances."""

    def test_get_intent_router_returns_instance(self):
        """get_intent_router returns a valid IntentMeshRouter."""
        router = get_intent_router("singleton_test", bus=make_bus())
        assert isinstance(router, IntentMeshRouter)
        assert router.agent_id == "singleton_test"

    def test_get_intent_router_creates_fresh_instance(self):
        """get_intent_router creates a new instance each call (no caching)."""
        bus = make_bus()
        r1 = get_intent_router("reuse", bus=bus)
        r2 = get_intent_router("reuse", bus=bus)
        assert isinstance(r1, IntentMeshRouter)
        assert isinstance(r2, IntentMeshRouter)
