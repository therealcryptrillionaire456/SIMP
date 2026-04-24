"""
ProjectX Mesh Intelligence — Step 10

Real-time mesh activity model: agent load tracking, bottleneck detection,
opportunity routing, and automatic rebalancing recommendations.

Features:
  - Subscribes to mesh bus events and builds a live agent load map
  - Detects bottlenecks: agents at >80% capacity, stalled queues
  - Opportunity routing: finds underutilised agents for new tasks
  - Emits rebalancing recommendations to the orchestrator
  - Exports mesh topology snapshot for telemetry dashboard
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_STALL_THRESHOLD_S = 30    # seconds with no activity = stalled
_HIGH_LOAD_RATIO = 0.80    # call_count / max_calls above this = high load
_SNAPSHOT_INTERVAL = 15    # seconds between topology snapshots


@dataclass
class AgentLoad:
    """Live load data for one agent on the mesh."""
    agent_id:       str
    role:           str
    channel:        str
    call_count:     int = 0
    max_calls:      int = 1000
    last_active:    float = field(default_factory=time.time)
    error_count:    int = 0
    avg_latency_ms: float = 0.0
    _latency_samples: List[float] = field(default_factory=list, repr=False)

    @property
    def load_ratio(self) -> float:
        return self.call_count / max(1, self.max_calls)

    @property
    def high_load(self) -> bool:
        return self.load_ratio >= _HIGH_LOAD_RATIO

    @property
    def stalled(self) -> bool:
        return (time.time() - self.last_active) > _STALL_THRESHOLD_S and self.call_count > 0

    def record_call(self, latency_ms: float = 0.0, error: bool = False) -> None:
        self.call_count += 1
        self.last_active = time.time()
        if error:
            self.error_count += 1
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 50:
            self._latency_samples = self._latency_samples[-50:]
        self.avg_latency_ms = sum(self._latency_samples) / len(self._latency_samples)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "channel": self.channel,
            "call_count": self.call_count,
            "max_calls": self.max_calls,
            "load_ratio": round(self.load_ratio, 3),
            "high_load": self.high_load,
            "stalled": self.stalled,
            "error_count": self.error_count,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }


@dataclass
class BottleneckReport:
    bottleneck_agents:  List[str]       # agent_ids at high load
    stalled_agents:     List[str]       # agent_ids with no recent activity
    recommended_roles:  List[str]       # roles that need new agents spawned
    topology_snapshot:  Dict[str, Any]  = field(default_factory=dict)
    timestamp:          float           = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "bottleneck_agents": self.bottleneck_agents,
            "stalled_agents": self.stalled_agents,
            "recommended_roles": self.recommended_roles,
            "topology": self.topology_snapshot,
        }


class MeshIntelligence:
    """
    Real-time mesh load monitor with bottleneck detection and opportunity routing.

    Usage::

        intel = MeshIntelligence()
        intel.start()

        report = intel.analyse()
        best = intel.route("defi analysis task")
        intel.recommend_rebalance()
    """

    _TOPOLOGY_CACHE_TTL = 5.0   # seconds before topology snapshot is rebuilt

    def __init__(self, snapshot_interval: int = _SNAPSHOT_INTERVAL) -> None:
        self._snapshot_interval = max(5, min(snapshot_interval, 3600))
        self._agents: Dict[str, AgentLoad] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._history: List[BottleneckReport] = []
        self._topology_cache: Optional[Dict] = None
        self._topology_cache_ts: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._sync_from_spawner()
        self._subscribe_mesh()
        self._thread = threading.Thread(
            target=self._snapshot_loop, daemon=True, name="mesh-intelligence"
        )
        self._thread.start()
        logger.info("MeshIntelligence started")

    def stop(self) -> None:
        self._running = False

    _MAX_AGENTS_TRACKED = 500  # cap tracked agents to prevent unbounded growth

    def record_call(
        self,
        agent_id: str,
        latency_ms: float = 0.0,
        error: bool = False,
    ) -> None:
        if not agent_id or len(agent_id) > 64:
            return
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].record_call(latency_ms, error)

    def route(self, goal: str) -> Optional[str]:
        """
        Return the agent_id of the best available (low-load) agent for the goal.
        Returns None if no suitable agent found.
        """
        if not goal or not isinstance(goal, str):
            return None
        goal_lower = goal[:512].lower()  # cap to prevent slow split on huge inputs
        with self._lock:
            candidates = [
                a for a in self._agents.values()
                if not a.high_load and not a.stalled
            ]
        if not candidates:
            return None
        scored = []
        for a in candidates:
            role_words = set(a.role.lower().split("_"))
            goal_words = set(goal_lower.split())
            score = len(role_words & goal_words) - a.load_ratio * 2
            scored.append((score, a))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1].agent_id if scored else None

    def analyse(self) -> BottleneckReport:
        """Produce a bottleneck report from current load data."""
        with self._lock:
            agents = list(self._agents.values())

        bottlenecks = [a.agent_id for a in agents if a.high_load]
        stalled = [a.agent_id for a in agents if a.stalled]

        # Recommend spawning more agents for high-load roles
        role_load: Dict[str, float] = {}
        for a in agents:
            role_load[a.role] = max(role_load.get(a.role, 0.0), a.load_ratio)
        recommended = [role for role, ratio in role_load.items() if ratio >= _HIGH_LOAD_RATIO]

        topology = {
            "total_agents": len(agents),
            "high_load_count": len(bottlenecks),
            "stalled_count": len(stalled),
            "agents": [a.to_dict() for a in agents],
        }

        report = BottleneckReport(
            bottleneck_agents=bottlenecks,
            stalled_agents=stalled,
            recommended_roles=recommended,
            topology_snapshot=topology,
        )
        with self._lock:
            self._history.append(report)
            if len(self._history) > 100:
                self._history = self._history[-50:]
        return report

    def recommend_rebalance(self) -> List[Dict[str, Any]]:
        """
        Return a list of rebalancing actions for the orchestrator.
        E.g. spawn additional agents for bottlenecked roles,
        terminate stalled agents.
        """
        report = self.analyse()
        actions: List[Dict[str, Any]] = []

        for role in report.recommended_roles:
            actions.append({"action": "spawn", "role": role, "reason": "high_load"})

        for agent_id in report.stalled_agents:
            actions.append({"action": "terminate", "agent_id": agent_id, "reason": "stalled"})

        if actions:
            logger.info(
                "MeshIntelligence recommends %d rebalancing actions: %s",
                len(actions),
                [a["action"] + ":" + a.get("role", a.get("agent_id", "")) for a in actions],
            )
            self._broadcast_recommendations(actions)
        return actions

    def topology(self) -> Dict[str, Any]:
        """Export current mesh topology as a dict (cached for TTL seconds)."""
        now = time.time()
        if self._topology_cache and (now - self._topology_cache_ts) < self._TOPOLOGY_CACHE_TTL:
            return self._topology_cache
        report = self.analyse()
        self._topology_cache = report.topology_snapshot
        self._topology_cache_ts = now
        return self._topology_cache

    def load_map(self) -> Dict[str, float]:
        """Return {agent_id: load_ratio} for all tracked agents."""
        with self._lock:
            return {aid: a.load_ratio for aid, a in self._agents.items()}

    # ── Internal ──────────────────────────────────────────────────────────

    def _sync_from_spawner(self) -> None:
        """Pull current agent pool from AgentSpawner."""
        try:
            from simp.projectx.agent_spawner import get_agent_spawner
            spawner = get_agent_spawner()
            with self._lock:
                for entry in spawner.list_agents():
                    aid = entry["agent_id"]
                    if aid not in self._agents:
                        self._agents[aid] = AgentLoad(
                            agent_id=aid,
                            role=entry.get("role", "unknown"),
                            channel=entry.get("channel", ""),
                            max_calls=entry.get("max_calls", 1000),
                        )
        except Exception as exc:
            logger.debug("sync_from_spawner: %s", exc)

    def _subscribe_mesh(self) -> None:
        try:
            from simp.mesh.enhanced_bus import get_enhanced_bus
            bus = get_enhanced_bus()
            bus.subscribe("projectx.agent.*", self._handle_mesh_event)
        except Exception as exc:
            logger.debug("mesh subscribe: %s", exc)

    def _handle_mesh_event(self, msg: Dict) -> None:
        if not isinstance(msg, dict):
            return
        agent_id = str(msg.get("agent_id", ""))[:64]
        latency = float(msg.get("latency_ms", 0) or 0)
        error = bool(msg.get("error"))
        if agent_id:
            with self._lock:
                if len(self._agents) >= self._MAX_AGENTS_TRACKED and agent_id not in self._agents:
                    return  # drop new agents when at cap
                if agent_id not in self._agents:
                    self._agents[agent_id] = AgentLoad(
                        agent_id=agent_id,
                        role=str(msg.get("role", "unknown"))[:64],
                        channel=str(msg.get("channel", ""))[:128],
                    )
            self.record_call(agent_id, latency, error)

    def _broadcast_recommendations(self, actions: List[Dict]) -> None:
        try:
            from simp.mesh.enhanced_bus import get_enhanced_bus
            bus = get_enhanced_bus()
            bus.publish("projectx.intelligence.rebalance", {
                "source": "mesh_intelligence",
                "actions": actions,
                "timestamp": time.time(),
            })
        except Exception as exc:
            logger.debug("broadcast: %s", exc)

    def _snapshot_loop(self) -> None:
        while self._running:
            time.sleep(self._snapshot_interval)
            try:
                self._sync_from_spawner()
                report = self.analyse()
                self._persist_snapshot(report)
                # Auto-recommend if bottlenecks detected
                if report.bottleneck_agents or report.stalled_agents:
                    self.recommend_rebalance()
            except Exception as exc:
                logger.debug("MeshIntelligence snapshot error: %s", exc)

    def _persist_snapshot(self, report: BottleneckReport) -> None:
        try:
            from simp.projectx.hardening import AtomicWriter
            path = "projectx_logs/mesh_topology.json"
            AtomicWriter.write_json(path, report.to_dict())
        except Exception as exc:
            logger.debug("persist snapshot: %s", exc)


# Module-level singleton
_intel: Optional[MeshIntelligence] = None
_intel_lock = threading.Lock()


def get_mesh_intelligence(auto_start: bool = True) -> MeshIntelligence:
    global _intel
    if _intel is None:
        with _intel_lock:
            if _intel is None:
                _intel = MeshIntelligence()
                if auto_start:
                    _intel.start()
    return _intel
