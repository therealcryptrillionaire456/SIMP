"""
SIMP Builder Pool — Manages builder agent assignments based on capacity and capability.

Reads the static routing policy from routing_policy.json and dynamically tracks
agent availability. Thread-safe for use with the multi-threaded broker.
"""

import json
import threading
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
        path = Path(policy_path) if policy_path else _POLICY_PATH
        with open(path, "r") as f:
            self._policy: Dict[str, Any] = json.load(f)

        self._lock = threading.RLock()

        # Capacity tracking: agent_id -> {"status": "available"|"busy"|"offline", "updated_at": iso}
        self._capacity: Dict[str, Dict[str, Any]] = {}

        pool = self._policy.get("builder_pool", {})
        self._primary: str = pool.get("primary", "")
        self._secondary: str = pool.get("secondary", "")
        self._support: List[str] = pool.get("support", [])
        self._task_routing: Dict[str, List[str]] = self._policy.get("task_routing", {})
        self._fallback_rules: Dict[str, str] = self._policy.get("fallback_rules", {})

    @property
    def policy(self) -> Dict[str, Any]:
        """Return the full routing policy (read-only copy)."""
        return dict(self._policy)

    def get_builder(self, task_type: str, exclude: Optional[List[str]] = None) -> Optional[str]:
        """
        Return the best available builder for a task type.

        Checks the task_routing table first, then falls back to
        primary -> secondary -> support order.
        """
        exclude = exclude or []

        # Try task-specific routing first
        candidates = self._task_routing.get(task_type, [])
        for agent_id in candidates:
            if agent_id not in exclude and self.is_available(agent_id):
                return agent_id

        # Fall back to pool order: primary -> secondary -> support
        for agent_id in [self._primary, self._secondary] + self._support:
            if agent_id not in exclude and self.is_available(agent_id):
                return agent_id

        return None

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
        }

    def get_fallback_rule(self, failure_class: str) -> str:
        """Return the fallback rule name for a failure class."""
        return self._fallback_rules.get(failure_class, "fail_immediately")
