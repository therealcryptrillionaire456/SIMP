"""
ProjectX Agent Spawner — Step 5

Self-cloning: dynamically creates and registers specialized agents on both
the SIMP mesh broker and the SubsystemRegistry.

Design:
  - SpawnSpec  — intent-driven spec describing what agent to create
  - AgentSpawner.spawn() — instantiates subsystem config + mesh registration
  - SpawnedAgent — handle with heartbeat + self-termination
  - Pool management: max concurrent agents, TTL-based reaping

Spawned agents are isolated subsystem variants that can be sent tasks
via the mesh bus and respond on a dedicated reply channel.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_AGENTS = 20
_DEFAULT_TTL = 3600   # seconds
_MAX_TTL = 86400      # 24h hard ceiling
_MIN_TTL = 60         # 1 minute floor
_MAX_CALLS_CAP = 100_000
_MAX_TAGS = 20
_MAX_TAG_LEN = 64


@dataclass
class SpawnSpec:
    """Declarative spec for an agent to spawn."""
    role:           str                      # e.g. "defi_analyst"
    system_prompt:  str
    tags:           List[str] = field(default_factory=list)
    ttl_seconds:    int = _DEFAULT_TTL
    max_calls:      int = 1000
    metadata:       Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpawnedAgent:
    """Live agent handle returned by AgentSpawner.spawn()."""
    agent_id:       str
    role:           str
    channel:        str                      # mesh reply channel
    spawned_at:     float
    ttl_seconds:    int
    call_count:     int = 0
    max_calls:      int = 1000
    alive:          bool = True
    _lock:          threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def expired(self) -> bool:
        return (time.time() - self.spawned_at) > self.ttl_seconds

    @property
    def exhausted(self) -> bool:
        return self.call_count >= self.max_calls

    def increment(self) -> None:
        with self._lock:
            self.call_count += 1

    def terminate(self) -> None:
        with self._lock:
            self.alive = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "channel": self.channel,
            "spawned_at": self.spawned_at,
            "ttl_seconds": self.ttl_seconds,
            "call_count": self.call_count,
            "alive": self.alive,
            "expired": self.expired,
        }


class AgentSpawner:
    """
    Dynamically creates specialized agents registered on the mesh + SubsystemRegistry.

    Usage::

        spawner = AgentSpawner()
        spec = SpawnSpec(
            role="defi_analyst",
            system_prompt="You are a DeFi expert specializing in liquidity analysis.",
            tags=["defi", "finance"],
            ttl_seconds=1800,
        )
        agent = spawner.spawn(spec)
        # agent.channel can now receive tasks via the mesh bus
    """

    def __init__(self, max_agents: int = _MAX_AGENTS) -> None:
        self._max = max_agents
        self._pool: Dict[str, SpawnedAgent] = {}
        self._lock = threading.Lock()
        self._reaper = threading.Thread(target=self._reap_loop, daemon=True, name="spawner-reaper")
        self._reaper.start()

    # ── Public API ────────────────────────────────────────────────────────

    def spawn(self, spec: SpawnSpec) -> SpawnedAgent:
        """Create a new specialized agent from the given SpawnSpec."""
        # Validate inputs before touching shared state
        try:
            from simp.projectx.hardening import InputGuard
            spec.role = InputGuard.check_string(spec.role, "role", max_len=64)
            spec.system_prompt = InputGuard.check_string(
                spec.system_prompt, "system_prompt", max_len=InputGuard.MAX_PROMPT_BYTES
            )
        except Exception as exc:
            raise ValueError(f"SpawnSpec validation failed: {exc}") from exc

        # Clamp TTL and call-count to safe ranges
        spec.ttl_seconds = max(_MIN_TTL, min(int(spec.ttl_seconds), _MAX_TTL))
        spec.max_calls = max(1, min(int(spec.max_calls), _MAX_CALLS_CAP))

        # Sanitize tags list (cap count + length)
        spec.tags = [str(t)[:_MAX_TAG_LEN] for t in spec.tags[:_MAX_TAGS]]

        # Sanitize role for use in channel name (alphanumeric + underscore only)
        import re as _re
        safe_role = _re.sub(r"[^a-zA-Z0-9_]", "_", spec.role)[:48]

        self._reap_expired()

        with self._lock:
            if len(self._pool) >= self._max:
                raise RuntimeError(
                    f"Agent pool full ({self._max} max). Terminate an agent first."
                )

        agent_id = uuid.uuid4().hex[:8]
        channel = f"projectx.agent.{safe_role}.{agent_id}"

        # Register subsystem
        self._register_subsystem(agent_id, spec)

        # Register on mesh
        self._register_mesh(agent_id, spec, channel)

        agent = SpawnedAgent(
            agent_id=agent_id,
            role=spec.role,
            channel=channel,
            spawned_at=time.time(),
            ttl_seconds=spec.ttl_seconds,
            max_calls=spec.max_calls,
        )

        with self._lock:
            self._pool[agent_id] = agent

        logger.info("Spawned agent %s role=%s channel=%s", agent_id, spec.role, channel)
        return agent

    def spawn_from_domain(self, domain: str, subsystem: str = "analysis") -> Optional[SpawnedAgent]:
        """
        Convenience: spawn an agent tuned for a domain using previously adapted prompts.
        Loads from domain adapter store if available.
        """
        import re as _re
        # Validate domain and subsystem to prevent path traversal in domain store
        if not domain or not _re.fullmatch(r"[a-zA-Z0-9_\-]{1,64}", domain):
            raise ValueError(f"domain must be alphanumeric/underscore/hyphen (1-64 chars), got {domain!r}")
        if not subsystem or not _re.fullmatch(r"[a-zA-Z0-9_]{1,64}", subsystem):
            raise ValueError(f"subsystem must be alphanumeric (1-64 chars), got {subsystem!r}")
        try:
            from simp.projectx.domain_adapter import DomainAdapter
            adapter = DomainAdapter()
            data = adapter.load_domain(domain)
            if not data:
                logger.warning("No domain data for '%s'", domain)
                return None
            for res in data.get("results", []):
                if res.get("subsystem") == subsystem and res.get("improvement", 0) > 0:
                    spec = SpawnSpec(
                        role=f"{subsystem}_{domain}",
                        system_prompt=res.get("adapted_prompt", ""),
                        tags=[domain, subsystem],
                        ttl_seconds=_DEFAULT_TTL,
                    )
                    return self.spawn(spec)
        except Exception as exc:
            logger.warning("spawn_from_domain failed: %s", exc)
        return None

    def terminate(self, agent_id: str) -> bool:
        """Terminate and deregister an agent."""
        with self._lock:
            agent = self._pool.pop(agent_id, None)
        if not agent:
            return False
        agent.terminate()
        self._deregister_mesh(agent_id, agent.channel)
        self._deregister_subsystem(agent_id, agent.role)
        logger.info("Terminated agent %s", agent_id)
        return True

    def list_agents(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in self._pool.values()]

    def get_agent(self, agent_id: str) -> Optional[SpawnedAgent]:
        with self._lock:
            return self._pool.get(agent_id)

    def route_task(self, goal: str) -> Optional[SpawnedAgent]:
        """Return the best alive agent for a given goal (keyword match on role/tags)."""
        goal_lower = goal.lower()
        with self._lock:
            candidates = [a for a in self._pool.values() if a.alive and not a.expired and not a.exhausted]
        if not candidates:
            return None
        scored = []
        for agent in candidates:
            score = sum(1 for w in agent.role.split("_") if w in goal_lower)
            scored.append((score, agent))
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]
        return best if best_score > 0 else None

    # ── Registration helpers ──────────────────────────────────────────────

    def _register_subsystem(self, agent_id: str, spec: SpawnSpec) -> None:
        try:
            from simp.projectx.subsystems import get_subsystem_registry, SubsystemConfig
            config = SubsystemConfig(
                name=f"{spec.role}_{agent_id}",
                role=spec.role,
                system_prompt=spec.system_prompt,
                tags=spec.tags,
            )
            get_subsystem_registry().register(config)
        except Exception as exc:
            logger.debug("Subsystem register skipped: %s", exc)

    def _deregister_subsystem(self, agent_id: str, role: str) -> None:
        try:
            from simp.projectx.subsystems import get_subsystem_registry
            registry = get_subsystem_registry()
            name = f"{role}_{agent_id}"
            registry._handles.pop(name, None)
        except Exception as exc:
            logger.debug("Subsystem deregister skipped: %s", exc)

    def _register_mesh(self, agent_id: str, spec: SpawnSpec, channel: str) -> None:
        try:
            from simp.mesh.enhanced_bus import get_enhanced_bus
            bus = get_enhanced_bus()
            bus.subscribe(channel, self._make_handler(agent_id))
        except Exception as exc:
            logger.debug("Mesh register skipped: %s", exc)

    def _deregister_mesh(self, agent_id: str, channel: str) -> None:
        try:
            from simp.mesh.enhanced_bus import get_enhanced_bus
            bus = get_enhanced_bus()
            bus.unsubscribe(channel)
        except Exception as exc:
            logger.debug("Mesh deregister skipped: %s", exc)

    def _make_handler(self, agent_id: str) -> Callable:
        def _handle(msg: Dict) -> None:
            agent = self.get_agent(agent_id)
            if agent:
                agent.increment()
                if agent.exhausted:
                    logger.info("Agent %s exhausted, terminating", agent_id)
                    self.terminate(agent_id)
        return _handle

    # ── Reaper ────────────────────────────────────────────────────────────

    def _reap_expired(self) -> None:
        with self._lock:
            expired = [aid for aid, a in self._pool.items() if a.expired or not a.alive]
        for aid in expired:
            self.terminate(aid)

    def _reap_loop(self) -> None:
        while True:
            time.sleep(60)
            try:
                self._reap_expired()
            except Exception as exc:
                logger.debug("Reaper error: %s", exc)


# Module-level singleton
_spawner: Optional[AgentSpawner] = None


def get_agent_spawner() -> AgentSpawner:
    global _spawner
    if _spawner is None:
        _spawner = AgentSpawner()
    return _spawner
