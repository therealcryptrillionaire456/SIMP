"""
SIMP Builder Pool — Manages builder agent assignments based on capacity and capability.

Reads the static routing policy from routing_policy.json and dynamically tracks
agent availability. Thread-safe for use with the multi-threaded broker.

Sprint 22: Dynamic hot-reload, weighted round-robin selection, task-load tracking.
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_POLICY_PATH = Path(__file__).parent / "routing_policy.json"


def _load_policy() -> Dict[str, Any]:
    """Load the routing policy JSON from disk."""
    with open(_POLICY_PATH, "r") as f:
        return json.load(f)


class BuilderPool:
    """Manages builder agent assignments based on capacity and capability."""

    def __init__(self, policy_path: Optional[str] = None):
        self._policy_path = Path(policy_path) if policy_path else _POLICY_PATH
        self._policy_mtime: float = 0
        self._lock = threading.RLock()

        # Capacity tracking: agent_id -> {"status": "available"|"busy"|"offline", "updated_at": iso}
        self._capacity: Dict[str, Dict[str, Any]] = {}

        # Sprint 22: Active task count and round-robin tracking
        self._active_task_count: Dict[str, int] = {}
        self._rr_counter: Dict[str, int] = {}

        # Load initial policy
        self._policy: Dict[str, Any] = {}
        self._primary: str = ""
        self._secondary: str = ""
        self._support: List[str] = []
        self._task_routing: Dict[str, List[str]] = {}
        self._fallback_rules: Dict[str, str] = {}
        self._load_policy()

    def _load_policy(self) -> None:
        """Load routing policy from JSON file."""
        try:
            mtime = os.path.getmtime(self._policy_path)
            if mtime == self._policy_mtime:
                return  # No change
            self._policy_mtime = mtime
            with open(self._policy_path, "r") as f:
                self._policy = json.load(f)

            pool = self._policy.get("builder_pool", {})
            self._primary = pool.get("primary", "")
            self._secondary = pool.get("secondary", "")
            self._support = pool.get("support", [])
            self._task_routing = self._policy.get("task_routing", {})
            self._fallback_rules = self._policy.get("fallback_rules", {})
        except Exception:
            pass

    def check_reload(self) -> bool:
        """Check if policy file changed and reload if so."""
        try:
            mtime = os.path.getmtime(self._policy_path)
            if mtime != self._policy_mtime:
                self._load_policy()
                return True
        except Exception:
            pass
        return False

    @property
    def policy(self) -> Dict[str, Any]:
        """Return the full routing policy (read-only copy)."""
        return dict(self._policy)

    def get_builder(self, task_type: str, exclude: Optional[set] = None) -> Optional[str]:
        """
        Select best agent for task_type using weighted selection.

        Sprint 22: Replaces first-available with scored round-robin.
        """
        exclude = exclude or set()
        # Normalize exclude to set for O(1) lookups
        if isinstance(exclude, list):
            exclude = set(exclude)

        # Try task-specific routing first
        candidates = self._task_routing.get(task_type, [])
        candidates = [c for c in candidates if c not in exclude]

        if not candidates:
            # Fallback through pool tiers
            for agent_id in [self._primary, self._secondary] + self._support:
                if agent_id and agent_id not in exclude and self.is_available(agent_id):
                    return agent_id
            return None

        # Score each candidate
        scored = []
        for agent_id in candidates:
            if not self.is_available(agent_id):
                continue
            score = self._compute_agent_score(agent_id)
            scored.append((agent_id, score))

        if not scored:
            # Fallback through pool tiers
            for agent_id in [self._primary, self._secondary] + self._support:
                if agent_id and agent_id not in exclude and self.is_available(agent_id):
                    return agent_id
            return None

        # Sort by score descending, pick best
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _compute_agent_score(self, agent_id: str) -> float:
        """Compute routing score for an agent. Higher = better."""
        score = 1.0

        # Health factor
        with self._lock:
            cap = self._capacity.get(agent_id)
        if cap is not None:
            status = cap.get("status", "available")
            if status == "available":
                score *= 1.0
            elif status == "busy":
                score *= 0.5
            elif status == "offline":
                return 0.0

        # Task load factor (fewer tasks = higher score)
        active_tasks = self._active_task_count.get(agent_id, 0)
        score *= max(0.1, 1.0 - (active_tasks * 0.1))

        # Round-robin tiebreaker
        self._rr_counter[agent_id] = self._rr_counter.get(agent_id, 0) + 1
        # Slight penalty for recently selected agents
        score -= (self._rr_counter[agent_id] % 10) * 0.01

        return score

    def report_task_assigned(self, agent_id: str) -> None:
        """Increment active task count for an agent."""
        self._active_task_count[agent_id] = self._active_task_count.get(agent_id, 0) + 1

    def report_task_completed(self, agent_id: str) -> None:
        """Decrement active task count for an agent."""
        self._active_task_count[agent_id] = max(0, self._active_task_count.get(agent_id, 0) - 1)

    def report_capacity(self, agent_id: str, status: str) -> None:
        """
        Update an agent's capacity state.

        Args:
            agent_id: The agent to update.
            status: One of "available", "busy", "offline".
        """
        with self._lock:
            self._capacity[agent_id] = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

    def is_available(self, agent_id: str) -> bool:
        """Check if an agent is healthy and under quota."""
        with self._lock:
            cap = self._capacity.get(agent_id)
        if cap is None:
            # Unknown agents are assumed available (they may just not have reported yet)
            return True
        return cap.get("status") == "available"

    def get_pool_status(self) -> Dict[str, Any]:
        """Return current pool status for monitoring."""
        with self._lock:
            capacity_snapshot = dict(self._capacity)
        return {
            "primary": self._primary,
            "secondary": self._secondary,
            "support": list(self._support),
            "capacity": capacity_snapshot,
            "active_task_counts": dict(self._active_task_count),
        }

    def get_fallback_rule(self, failure_class: str) -> str:
        """Return the fallback rule name for a failure class."""
        return self._fallback_rules.get(failure_class, "fail_immediately")
