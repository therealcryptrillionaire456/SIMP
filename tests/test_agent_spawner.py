"""
Tests for AgentSpawner — step 5 self-cloning subsystem spawner.

Validates spawn lifecycle, pool management, TTL/expiry behaviour,
and graceful agent termination.  Uses only the methods that the
actual AgentSpawner class exposes; no stub or mock is needed since
spawn() does not fork processes — it creates lightweight in-memory
SpawnedAgent handles.
"""

from __future__ import annotations

import threading

import pytest

from simp.projectx.agent_spawner import (
    AgentSpawner,
    SpawnSpec,
    SpawnedAgent,
    get_agent_spawner,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_spec(role: str = "test_agent", **kwargs) -> SpawnSpec:
    defaults = dict(
        role=role,
        system_prompt="You are a test agent.",
        tags=["test"],
        ttl_seconds=3600,
        max_calls=1000,
    )
    defaults.update(kwargs)
    return SpawnSpec(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spawner() -> AgentSpawner:
    """Fresh spawner with a low cap for max-agent rejection tests."""
    sp = AgentSpawner(max_agents=5)
    yield sp
    # No shutdown() method exists — terminate any leftovers manually.
    for a in list(sp.list_agents()):
        sp.terminate(a["agent_id"])


@pytest.fixture
def spawner_unlimited() -> AgentSpawner:
    """Spawner with generous cap for multi-agent tests."""
    sp = AgentSpawner(max_agents=100)
    yield sp
    for a in list(sp.list_agents()):
        sp.terminate(a["agent_id"])


# ---------------------------------------------------------------------------
# Spawner initialisation
# ---------------------------------------------------------------------------

class TestSpawnerInitialization:
    def test_spawner_initialization(self):
        """AgentSpawner instantiates without error and starts its reaper thread."""
        sp = AgentSpawner()
        try:
            assert sp._max == 20                          # default cap
            assert isinstance(sp._pool, dict)
            assert isinstance(sp._lock, type(threading.Lock()))
            assert sp._reaper.daemon is True
            assert sp._reaper.is_alive()
        finally:
            pass   # reaper is daemon; will die with process

    def test_spawner_custom_max_agents(self):
        """Custom max_agents cap is stored and readable."""
        sp = AgentSpawner(max_agents=3)
        assert sp._max == 3


# ---------------------------------------------------------------------------
# register / spawn
# ---------------------------------------------------------------------------

class TestRegisterAgentType:
    def test_register_agent_type(self, spawner: AgentSpawner):
        """spawn() with a spec stores the agent in the pool."""
        spec = make_spec(role="trader", tags=["finance", "defi"])
        agent = spawner.spawn(spec)
        try:
            assert agent.role == "trader"
            # Spec tags are sanitised and stored
            assert "finance" in spec.tags
            assert "defi" in spec.tags
            # Agent is reachable via get_agent
            retrieved = spawner.get_agent(agent.agent_id)
            assert retrieved is not None
        finally:
            spawner.terminate(agent.agent_id)


class TestSpawnAgentReturnsHandle:
    def test_spawn_agent_returns_handle(self, spawner: AgentSpawner):
        """spawn() returns a SpawnedAgent handle with all expected fields."""
        spec = make_spec(role="analyzer")
        agent = spawner.spawn(spec)
        try:
            assert isinstance(agent, SpawnedAgent)

            # Identity
            assert isinstance(agent.agent_id, str)
            assert len(agent.agent_id) == 8

            # Role and channel
            assert agent.role == "analyzer"
            assert isinstance(agent.channel, str)
            assert agent.channel.startswith("projectx.agent.analyzer.")

            # Lifecycle
            assert agent.spawned_at > 0
            assert agent.ttl_seconds == 3600
            assert agent.alive is True
            assert agent.call_count == 0

            # Computed flags
            assert agent.expired is False
            assert agent.exhausted is False
        finally:
            spawner.terminate(agent.agent_id)


# ---------------------------------------------------------------------------
# Active-agent tracking
# ---------------------------------------------------------------------------

class TestSpawnerKeepsTrackOfActiveAgents:
    def test_spawner_keeps_track_of_active_agents(self, spawner_unlimited: AgentSpawner):
        """After spawning N agents, list_agents() returns N entries."""
        agents = []
        for i in range(3):
            agents.append(spawner_unlimited.spawn(make_spec(role=f"agent_{i}")))
        try:
            listed = spawner_unlimited.list_agents()
            assert len(listed) == 3
            assert all(a["alive"] for a in listed)
        finally:
            for a in agents:
                spawner_unlimited.terminate(a.agent_id)


class TestSpawnerIsolation:
    def test_spawner_isolation(self, spawner_unlimited: AgentSpawner):
        """Agents can be tracked and terminated independently."""
        a1 = spawner_unlimited.spawn(make_spec(role="alpha"))
        a2 = spawner_unlimited.spawn(make_spec(role="beta"))
        a3 = spawner_unlimited.spawn(make_spec(role="gamma"))

        # All three are independently reachable
        assert spawner_unlimited.get_agent(a1.agent_id).role == "alpha"
        assert spawner_unlimited.get_agent(a2.agent_id).role == "beta"
        assert spawner_unlimited.get_agent(a3.agent_id).role == "gamma"

        # Terminate middle one — others remain
        spawner_unlimited.terminate(a2.agent_id)
        assert spawner_unlimited.get_agent(a1.agent_id) is not None
        assert spawner_unlimited.get_agent(a2.agent_id) is None
        assert spawner_unlimited.get_agent(a3.agent_id) is not None

        # Clean up the rest
        spawner_unlimited.terminate(a1.agent_id)
        spawner_unlimited.terminate(a3.agent_id)
        assert len(spawner_unlimited.list_agents()) == 0


# ---------------------------------------------------------------------------
# terminate
# ---------------------------------------------------------------------------

class TestTerminateAgent:
    def test_terminate_agent(self, spawner: AgentSpawner):
        """terminate() removes the agent from the pool."""
        agent = spawner.spawn(make_spec(role="temp"))
        aid = agent.agent_id
        assert spawner.terminate(aid) is True
        assert spawner.get_agent(aid) is None
        assert len(spawner.list_agents()) == 0

    def test_terminate_nonexistent_returns_false(self, spawner: AgentSpawner):
        """Terminating an unknown ID returns False and does not raise."""
        assert spawner.terminate("no-such-id") is False


# ---------------------------------------------------------------------------
# max_agents enforcement
# ---------------------------------------------------------------------------

class TestSpawnerRespectsMaxAgents:
    def test_spawner_respects_max_agents(self, spawner: AgentSpawner):
        """Spawning beyond max_agents raises RuntimeError."""
        spawned = []
        for _ in range(spawner._max):
            spawned.append(spawner.spawn(make_spec(role="fill")))
        try:
            with pytest.raises(RuntimeError, match="pool full"):
                spawner.spawn(make_spec(role="overflow"))
        finally:
            for a in spawned:
                spawner.terminate(a.agent_id)

    def test_terminate_frees_slot_for_respawn(self, spawner: AgentSpawner):
        """Terminating an agent opens a slot for a new spawn."""
        a1 = spawner.spawn(make_spec(role="slot_test"))
        spawner.terminate(a1.agent_id)
        # Must not raise — slot is now available
        a2 = spawner.spawn(make_spec(role="slot_test_2"))
        spawner.terminate(a2.agent_id)


# ---------------------------------------------------------------------------
# SpawnedAgent handle properties
# ---------------------------------------------------------------------------

class TestAgentHandleProperties:
    def test_agent_handle_properties(self, spawner: AgentSpawner):
        """SpawnedAgent exposes all required properties and methods."""
        spec = make_spec(role="inspect_me", ttl_seconds=600, max_calls=50)
        agent = spawner.spawn(spec)
        try:
            # Identity
            assert isinstance(agent.agent_id, str)
            assert len(agent.agent_id) == 8

            # Role / channel
            assert agent.role == "inspect_me"
            assert isinstance(agent.channel, str)
            assert "inspect_me" in agent.channel

            # TTL / spawn time
            assert agent.spawned_at > 0
            assert agent.ttl_seconds == 600

            # Lifecycle flags
            assert agent.alive is True
            assert agent.expired is False
            assert agent.exhausted is False

            # Call counter starts at zero
            assert agent.call_count == 0

            # increment() bumps counter
            agent.increment()
            assert agent.call_count == 1

            # terminate() flips alive flag
            agent.terminate()
            assert agent.alive is False

            # to_dict() produces a serialisable dict
            d = agent.to_dict()
            assert d["agent_id"] == agent.agent_id
            assert d["role"] == "inspect_me"
            assert d["alive"] is False
            assert "expired" in d
        finally:
            spawner.terminate(agent.agent_id)

    def test_spawned_agent_ttl_clamped_above_zero(self, spawner: AgentSpawner):
        """TTL below MIN_TTL (60s) is raised to MIN_TTL."""
        spec = make_spec(role="short_ttl", ttl_seconds=0)
        agent = spawner.spawn(spec)
        try:
            assert agent.ttl_seconds >= 60   # MIN_TTL
        finally:
            spawner.terminate(agent.agent_id)


# ---------------------------------------------------------------------------
# graceful agent shutdown (via terminate)
# ---------------------------------------------------------------------------

class TestSpawnerGracefulShutdown:
    def test_spawner_graceful_shutdown(self, spawner_unlimited: AgentSpawner):
        """Terminating all agents clears the pool cleanly."""
        agents = []
        for i in range(3):
            agents.append(spawner_unlimited.spawn(make_spec(role=f"shutdown_test_{i}")))
        for a in agents:
            spawner_unlimited.terminate(a.agent_id)

        # Pool is empty
        assert len(spawner_unlimited.list_agents()) == 0

    def test_single_agent_termination_is_clean(self, spawner: AgentSpawner):
        """Terminating a single agent leaves pool in a consistent state."""
        agent = spawner.spawn(make_spec(role="single_shutdown"))
        spawner.terminate(agent.agent_id)
        # No agents left
        assert len(spawner.list_agents()) == 0
        # Re-spawning works without error
        new_agent = spawner.spawn(make_spec(role="single_shutdown_2"))
        spawner.terminate(new_agent.agent_id)


# ---------------------------------------------------------------------------
# TTL clamping and expiry
# ---------------------------------------------------------------------------

class TestTTLAndExpiry:
    def test_ttl_clamped_to_max(self, spawner: AgentSpawner):
        """TTL above MAX_TTL (86400s) is clamped down."""
        spec = make_spec(role="long_lived", ttl_seconds=999_999)
        agent = spawner.spawn(spec)
        try:
            assert agent.ttl_seconds <= 86400
        finally:
            spawner.terminate(agent.agent_id)

    def test_ttl_clamped_to_min(self, spawner: AgentSpawner):
        """TTL below MIN_TTL (60s) is clamped up."""
        spec = make_spec(role="short_ttl", ttl_seconds=1)
        agent = spawner.spawn(spec)
        try:
            assert agent.ttl_seconds >= 60
        finally:
            spawner.terminate(agent.agent_id)

    def test_exhausted_flag(self, spawner: AgentSpawner):
        """exhausted becomes True once call_count >= max_calls."""
        spec = make_spec(role="exhaust_test", max_calls=2)
        agent = spawner.spawn(spec)
        try:
            assert agent.exhausted is False
            agent.increment()
            assert agent.exhausted is False
            agent.increment()
            assert agent.exhausted is True
        finally:
            spawner.terminate(agent.agent_id)


# ---------------------------------------------------------------------------
# Tag sanitisation
# ---------------------------------------------------------------------------

class TestTagSanitisation:
    def test_tags_truncated_to_max_count(self, spawner: AgentSpawner):
        """Tags list is capped at MAX_TAGS (20)."""
        many_tags = [f"tag_{i}" for i in range(50)]
        spec = make_spec(role="tag_test", tags=many_tags)
        # Tags are sanitised in-place on spawn
        spawner.spawn(spec)
        assert len(spec.tags) <= 20

    def test_tags_truncated_to_max_length(self, spawner: AgentSpawner):
        """Individual tags longer than MAX_TAG_LEN (64) are truncated."""
        spec = make_spec(role="tag_len_test", tags=["x" * 200])
        spawner.spawn(spec)
        assert len(spec.tags[0]) <= 64


# ---------------------------------------------------------------------------
# route_task
# ---------------------------------------------------------------------------

class TestRouteTask:
    def test_route_task_returns_matching_agent(self, spawner: AgentSpawner):
        """route_task returns an alive agent whose role matches goal keywords."""
        spawner.spawn(make_spec(role="defi_analyst", tags=["finance"]))
        agent = spawner.route_task("I need a defi analyst")
        assert agent is not None
        assert "defi" in agent.role

    def test_route_task_returns_none_when_no_match(self, spawner: AgentSpawner):
        """route_task returns None when no agent role matches the goal."""
        spawner.spawn(make_spec(role="trader", tags=["trade"]))
        agent = spawner.route_task("xyz zz zz")
        # Returns None if best score is 0
        assert agent is None

    def test_route_task_ignores_dead_agent(self, spawner: AgentSpawner):
        """route_task does not return a terminated agent."""
        agent = spawner.spawn(make_spec(role="dead_one"))
        spawner.terminate(agent.agent_id)
        result = spawner.route_task("dead_one")
        if result is not None:
            assert result.agent_id != agent.agent_id


# ---------------------------------------------------------------------------
# list_agents and get_agent
# ---------------------------------------------------------------------------

class TestListAndGet:
    def test_list_agents_returns_dicts(self, spawner: AgentSpawner):
        """list_agents() returns serialisable dict objects."""
        agent = spawner.spawn(make_spec(role="lister"))
        try:
            listed = spawner.list_agents()
            assert isinstance(listed, list)
            assert all(isinstance(a, dict) for a in listed)
            assert all("agent_id" in a for a in listed)
            assert all("role" in a for a in listed)
        finally:
            spawner.terminate(agent.agent_id)

    def test_get_agent_returns_spawned_agent(self, spawner: AgentSpawner):
        """get_agent() returns the SpawnedAgent handle by ID."""
        agent = spawner.spawn(make_spec(role="getter"))
        try:
            retrieved = spawner.get_agent(agent.agent_id)
            assert isinstance(retrieved, SpawnedAgent)
            assert retrieved.agent_id == agent.agent_id
            assert retrieved.role == "getter"
        finally:
            spawner.terminate(agent.agent_id)

    def test_get_nonexistent_returns_none(self, spawner: AgentSpawner):
        """get_agent() with an unknown ID returns None."""
        assert spawner.get_agent("deadbeef") is None


# ---------------------------------------------------------------------------
# get_agent_spawner singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_agent_spawner_singleton(self):
        """get_agent_spawner() returns the same instance across calls."""
        sp1 = get_agent_spawner()
        sp2 = get_agent_spawner()
        assert sp1 is sp2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
