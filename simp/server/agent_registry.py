"""
SIMP Agent Registry — Session 2

Persistent registry for agent state with disk persistence.
Loads agent state on startup, saves on registration/deregistration.
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SIMP.AgentRegistry")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)


@dataclass
class AgentRegistryConfig:
    """Tuning knobs for the agent registry."""
    path: str = os.path.join(_REPO_ROOT, "data", "agent_registry.jsonl")
    max_size_mb: float = 10.0  # Smaller than intent ledger since fewer records


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