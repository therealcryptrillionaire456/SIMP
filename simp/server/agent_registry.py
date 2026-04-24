"""
SIMP Agent Registry — Persistent registry for agent state with disk persistence.
Loads agent state on startup, saves on registration/deregistration.
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SIMP.AgentRegistry")


# ---------------------------------------------------------------------------
# Enums and Data Classes
# ---------------------------------------------------------------------------

class AgentState(Enum):
    """Operator-grade agent lifecycle states."""
    ONLINE = "online"
    STALE = "stale"
    UNREACHABLE = "unreachable"
    DEREGISTERED = "deregistered"


@dataclass
class AgentInfo:
    """Structured view of a registered agent."""
    agent_id: str
    state: AgentState
    last_seen: str  # ISO8601 UTC
    capabilities: List[str] = field(default_factory=list)
    endpoint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "last_seen": self.last_seen,
            "capabilities": self.capabilities,
            "endpoint": self.endpoint,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        return cls(
            agent_id=data["agent_id"],
            state=AgentState(data.get("state", "stale")),
            last_seen=data.get("last_seen", ""),
            capabilities=data.get("capabilities", []),
            endpoint=data.get("endpoint", ""),
            metadata=data.get("metadata", {}),
        )


AgentRecord = AgentInfo
"""Alias for backward compatibility."""

logger = logging.getLogger("SIMP.AgentRegistry")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)


@dataclass
class AgentRegistryConfig:
    """Tuning knobs for the agent registry."""
    path: str = os.path.join(_REPO_ROOT, "data", "agent_registry.jsonl")
    persist_path: Optional[str] = None
    max_size_mb: float = 10.0
    stale_after_seconds: int = 120
    unreachable_after_seconds: int = 300
    prune_after_seconds: int = 86400

    def __post_init__(self) -> None:
        if self.persist_path:
            self.path = self.persist_path


RegistryConfig = AgentRegistryConfig
"""Alias for backward compatibility — test imports RegistryConfig."""


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """
    Persistent registry for agent state with disk persistence.
    
    Rules:
    - Loads all agents from disk on initialization
    - Saves agent state on registration, update, and deregistration
    - Thread-safe with file locking
    - JSONL format for append-only durability
    """
    
    def __init__(self, config: Optional[AgentRegistryConfig] = None):
        self.config = config or AgentRegistryConfig()
        self._path = Path(self.config.path)
        self._lock = threading.Lock()
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._ensure_dir()
        self._load_all()
    
    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    
    def _ensure_dir(self) -> None:
        """Ensure the directory for the registry file exists."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    
    def _load_all(self) -> None:
        """Load all agents from disk by replaying events."""
        if not self._path.exists():
            logger.info("Agent registry file not found: %s", self._path)
            return
        
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("AgentRegistry: skipping corrupt line")
                        continue
                    
                    event_type = record.get("event")
                    agent_id = record.get("agent_id")
                    
                    if not agent_id:
                        continue
                    
                    # Replay events to reconstruct current state
                    if event_type == "registered":
                        # Store agent data from registration
                        agent_data = record.get("agent_data", {})
                        self._agents[agent_id] = agent_data
                    elif event_type == "updated":
                        # Apply updates to existing agent
                        updates = record.get("updates", {})
                        if agent_id in self._agents:
                            self._agents[agent_id].update(updates)
                    elif event_type == "deregistered":
                        # Remove agent
                        self._agents.pop(agent_id, None)
            
            logger.info("Loaded %d agents from %s", len(self._agents), self._path)
        except Exception as exc:
            logger.error("AgentRegistry.load_all failed: %s", exc)
    
    def _append_record(self, record: Dict[str, Any]) -> None:
        """
        Append one JSON line to the registry.
        Thread-safe with file locking.
        """
        try:
            enriched = dict(record)
            if "registry_ts" not in enriched:
                enriched["registry_ts"] = datetime.now(timezone.utc).isoformat()
            line = json.dumps(enriched, default=str) + "\n"
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(line)
                    fh.flush()
        except Exception as exc:
            logger.error("AgentRegistry._append_record failed: %s", exc)
    
    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    
    def register(self, agent_id: str, agent_data: Dict[str, Any]) -> bool:
        """
        Register an agent and persist to disk.
        Returns True if registered, False if already exists.
        """
        if agent_id in self._agents:
            return False
        
        # Add metadata
        enriched_data = dict(agent_data)
        enriched_data.setdefault("state", "online")
        enriched_data["agent_id"] = agent_id
        enriched_data["registered_at"] = datetime.now(timezone.utc).isoformat()
        enriched_data["last_updated"] = enriched_data["registered_at"]
        
        # Store in memory
        self._agents[agent_id] = enriched_data
        
        # Persist to disk
        self._append_record({
            "event": "registered",
            "agent_id": agent_id,
            "agent_data": enriched_data,
            "timestamp": enriched_data["registered_at"],
        })
        
        logger.info("Registered agent %s and persisted to disk", agent_id)
        return True
    
    def update(self, agent_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an agent's data and persist to disk.
        Returns True if updated, False if agent not found.
        """
        if agent_id not in self._agents:
            return False
        
        # Update in memory
        self._agents[agent_id].update(updates)
        self._agents[agent_id]["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Persist update to disk
        self._append_record({
            "event": "updated",
            "agent_id": agent_id,
            "updates": updates,
            "timestamp": self._agents[agent_id]["last_updated"],
        })
        
        logger.debug("Updated agent %s and persisted to disk", agent_id)
        return True
    
    def deregister(self, agent_id: str) -> bool:
        """
        Deregister an agent and persist to disk.
        Returns True if deregistered, False if agent not found.
        """
        if agent_id not in self._agents:
            return False
        
        # Get agent data before removing
        agent_data = self._agents[agent_id]
        
        # Remove from memory
        del self._agents[agent_id]
        
        # Persist deregistration to disk
        self._append_record({
            "event": "deregistered",
            "agent_id": agent_id,
            "agent_data": agent_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        logger.info("Deregistered agent %s and persisted to disk", agent_id)
        return True
    
    def pop(self, agent_id: str, default: Any = None) -> Any:
        """
        Remove agent and return its data, like dict.pop().
        """
        if agent_id not in self._agents:
            return default
        
        agent_data = self._agents[agent_id]
        self.deregister(agent_id)
        return agent_data
    
    def get(self, agent_id: str, default: Any = None) -> Optional[Dict[str, Any]]:
        """Get agent data by ID with optional default value."""
        return self._agents.get(agent_id, default)
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered agents."""
        return dict(self._agents)
    
    # Dictionary-like interface for backward compatibility
    def items(self):
        """Return items like a dictionary."""
        return self._agents.items()
    
    def values(self):
        """Return values like a dictionary."""
        return self._agents.values()
    
    def keys(self):
        """Return keys like a dictionary."""
        return self._agents.keys()
    
    def __contains__(self, agent_id: str) -> bool:
        """Check if agent exists using 'in' operator."""
        return agent_id in self._agents
    
    def __len__(self) -> int:
        """Get count of registered agents using len()."""
        return len(self._agents)
    
    def __getitem__(self, agent_id: str) -> Dict[str, Any]:
        """Get agent data using subscript notation."""
        return self._agents[agent_id]
    
    def __delitem__(self, agent_id: str) -> None:
        """Delete agent using del operator."""
        self.deregister(agent_id)
    
    def count(self) -> int:
        """Get count of registered agents."""
        return len(self._agents)
    
    def exists(self, agent_id: str) -> bool:
        """Check if agent exists."""
        return agent_id in self._agents
    
    def get_agent(self, agent_id: str) -> AgentInfo:
        """
        Return an AgentInfo view of an agent.

        Raises KeyError if agent not found.
        """
        raw = self._agents[agent_id]  # let KeyError propagate
        # Infer state from the raw dict's "state" or "status" field
        state_val = raw.get("state") or raw.get("status", "stale")
        if isinstance(state_val, AgentState):
            state = state_val
        else:
            try:
                state = AgentState(state_val.lower())
            except ValueError:
                state = AgentState.STALE  # safe fallback

        return AgentInfo(
            agent_id=agent_id,
            state=state,
            last_seen=raw.get("last_seen") or raw.get("last_updated", ""),
            capabilities=raw.get("capabilities", []),
            endpoint=raw.get("endpoint", ""),
            metadata=raw.get("metadata", {}),
        )

    def get_agents_by_state(self, target: AgentState) -> List[str]:
        """Return agent IDs whose state matches *target*."""
        result: List[str] = []
        for aid in self._agents:
            try:
                info = self.get_agent(aid)
                if info.state == target:
                    result.append(aid)
            except KeyError:
                continue
        return result

    # ------------------------------------------------------------------
    # stats and maintenance
    # ------------------------------------------------------------------
    
    def get_stats(self) -> Dict[str, Any]:
        """Return summary stats."""
        exists = self._path.exists()
        size = self._path.stat().st_size if exists else 0
        
        # Count by status
        status_counts = {}
        for agent in self._agents.values():
            status = agent.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "path": str(self._path),
            "exists": exists,
            "size_bytes": size,
            "agent_count": len(self._agents),
            "status_counts": status_counts,
        }


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

AGENT_REGISTRY = AgentRegistry()
