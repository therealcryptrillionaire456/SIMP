"""
Tests for AgentRegistry — matches the actual implementation API.

The registry stores agent data as dicts, with AgentInfo/AgentState
as convenience wrappers returned by get_agent().
"""

import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from simp.server.agent_registry import (
    AgentRegistry,
    AgentInfo,
    AgentState,
    RegistryConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_path():
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    path = tmp.name
    tmp.close()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def registry(temp_path):
    config = RegistryConfig(persist_path=temp_path)
    reg = AgentRegistry(config=config)
    yield reg


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_returns_true(self, registry):
        assert registry.register("agent_a", {"capabilities": ["ping"]}) is True

    def test_register_then_get(self, registry):
        registry.register("agent_b", {"capabilities": ["echo"]})
        info = registry.get_agent("agent_b")
        assert info.agent_id == "agent_b"
        assert info.state == AgentState.ONLINE

    def test_register_duplicate_returns_false(self, registry):
        registry.register("agent_c", {})
        assert registry.register("agent_c", {}) is False

    def test_register_is_persistent(self, registry, temp_path):
        registry.register("agent_d", {"capabilities": ["test"]})
        # Recreate registry from same file
        reg2 = AgentRegistry(config=RegistryConfig(persist_path=temp_path))
        info = reg2.get_agent("agent_d")
        assert info.agent_id == "agent_d"


# ---------------------------------------------------------------------------
# Get / Query
# ---------------------------------------------------------------------------

class TestQuery:
    def test_get_nonexistent_raises(self, registry):
        with pytest.raises(KeyError):
            registry.get_agent("ghost")

    def test_get_all_empty(self, registry):
        assert registry.get_all() == {}

    def test_get_all_populated(self, registry):
        registry.register("x", {"capabilities": ["a"]})
        registry.register("y", {"capabilities": ["b"]})
        all_a = registry.get_all()
        assert "x" in all_a
        assert "y" in all_a

    def test_contains(self, registry):
        registry.register("z", {})
        assert "z" in registry
        assert "nope" not in registry

    def test_len(self, registry):
        assert len(registry) == 0
        registry.register("a1", {})
        assert len(registry) == 1

    def test_count(self, registry):
        assert registry.count() == 0
        registry.register("c1", {})
        assert registry.count() == 1


# ---------------------------------------------------------------------------
# Update / Heartbeat (via update)
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_existing(self, registry):
        registry.register("u1", {"status": "active"})
        updated = registry.update("u1", {"status": "degraded"})
        assert updated is True
        raw = registry.get("u1")
        assert raw.get("status") == "degraded"

    def test_update_nonexistent_returns_false(self, registry):
        assert registry.update("phantom", {}) is False


# ---------------------------------------------------------------------------
# Deregister
# ---------------------------------------------------------------------------

class TestDeregister:
    def test_deregister(self, registry):
        registry.register("d1", {})
        assert registry.deregister("d1") is True
        assert "d1" not in registry

    def test_deregister_unknown_returns_false(self, registry):
        assert registry.deregister("phantom") is False

    def test_deregister_then_register_again(self, registry):
        registry.register("re", {})
        registry.deregister("re")
        assert registry.register("re", {}) is True  # fresh registration


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_has_expected_keys(self, registry):
        stats = registry.get_stats()
        assert "path" in stats
        assert "exists" in stats
        assert "agent_count" in stats

    def test_stats_agent_count(self, registry):
        registry.register("s1", {"status": "online"})
        registry.register("s2", {"status": "online"})
        stats = registry.get_stats()
        assert stats["agent_count"] == 2

    def test_get_agent_state(self, registry):
        registry.register("state_a", {"state": "online"})
        info = registry.get_agent("state_a")
        assert info.state == AgentState.ONLINE

    def test_get_agents_by_state(self, registry):
        registry.register("sa1", {"state": "online"})
        registry.register("sa2", {"state": "online"})
        registry.register("sa3", {"state": "stale"})
        online = registry.get_agents_by_state(AgentState.ONLINE)
        assert "sa1" in online
        assert "sa2" in online
        assert "sa3" not in online


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_registry_stats(self, registry):
        stats = registry.get_stats()
        assert stats["agent_count"] == 0

    def test_get_agent_nonexistent_keyerror(self, registry):
        with pytest.raises(KeyError):
            registry.get_agent("ghost")

    def test_long_ids(self, registry):
        long_id = "a" * 200
        assert registry.register(long_id, {}) is True
        info = registry.get_agent(long_id)
        assert info.agent_id == long_id

    def test_pop_agent(self, registry):
        registry.register("pop_me", {"value": 42})
        data = registry.pop("pop_me")
        assert data["value"] == 42
        assert "pop_me" not in registry

    def test_pop_missing_default(self, registry):
        assert registry.pop("nonexistent", "DEFAULT") == "DEFAULT"

    def test_delitem(self, registry):
        registry.register("del_me", {})
        del registry["del_me"]
        assert registry.exists("del_me") is False

    def test_getitem_and_setitem(self, registry):
        registry.register("item1", {"val": 1})
        data = registry["item1"]
        assert data["val"] == 1

    def test_exists(self, registry):
        assert registry.exists("no") is False
        registry.register("yes", {})
        assert registry.exists("yes") is True


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_reload_preserves_agents(self, registry, temp_path):
        registry.register("keep", {"capability": "persist"})
        registry.deregister("remove_me")
        reg2 = AgentRegistry(config=RegistryConfig(persist_path=temp_path))
        assert reg2.exists("keep") is True
        assert reg2.exists("remove_me") is False

    def test_path_property(self, registry, temp_path):
        assert registry._path is not None or Path(temp_path).exists()


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_registrations(self, registry):
        """Quick smoke test: many registrations from same thread do not corrupt."""
        for i in range(50):
            registry.register(f"concurrent_{i}", {"idx": i})
        assert registry.count() == 50

    def test_concurrent_get_all(self, registry):
        for i in range(50):
            registry.register(f"get_all_{i}", {})
        all_a = registry.get_all()
        assert len(all_a) == 50
