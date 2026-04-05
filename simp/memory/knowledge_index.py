"""
SIMP Knowledge Index

Central index mapping topics to conversations, task files, code locations,
and decisions. Also stores agent profiles.
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class KnowledgeIndex:
    """Manages the memory/index.json knowledge index."""

    def __init__(self, index_path: str = "memory/index.json"):
        self.index_path = Path(index_path)
        self._lock = threading.RLock()
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load index from disk."""
        if self.index_path.exists():
            try:
                return json.loads(self.index_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"topics": {}, "agent_profiles": {}}

    def _save(self) -> None:
        """Persist index to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(self._data, indent=2, default=str))

    def update_topic(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Update or create a topic entry.

        data can contain:
            conversations (list[str]): Conversation IDs
            task_files (list[str]): Task memory slugs
            code_locations (list[str]): File paths / module references
            decisions (list[str]): Key decisions
            tags (list[str]): Searchable tags
        """
        with self._lock:
            existing = self._data.setdefault("topics", {}).get(topic, {})
            # Merge lists rather than overwrite
            for key in ("conversations", "task_files", "code_locations", "decisions", "tags"):
                if key in data:
                    existing_list = existing.get(key, [])
                    for item in data[key]:
                        if item not in existing_list:
                            existing_list.append(item)
                    existing[key] = existing_list
            # Overwrite scalar fields
            for key in data:
                if key not in ("conversations", "task_files", "code_locations", "decisions", "tags"):
                    existing[key] = data[key]
            self._data["topics"][topic] = existing
            self._save()

    def search_topics(self, query: str) -> List[Dict[str, Any]]:
        """Search topics by keyword."""
        query_lower = query.lower()
        results = []
        with self._lock:
            for topic_name, topic_data in self._data.get("topics", {}).items():
                searchable = " ".join([
                    topic_name,
                    " ".join(topic_data.get("tags", [])),
                    " ".join(topic_data.get("decisions", [])),
                ]).lower()
                if query_lower in searchable:
                    results.append({"topic": topic_name, **topic_data})
        return results

    def get_topic(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get a single topic entry."""
        with self._lock:
            data = self._data.get("topics", {}).get(topic)
            if data:
                return {"topic": topic, **data}
            return None

    def get_all_topics(self) -> Dict[str, Any]:
        """Return the full topics index."""
        with self._lock:
            return dict(self._data.get("topics", {}))

    def get_agent_profile(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get an agent's profile."""
        with self._lock:
            return self._data.get("agent_profiles", {}).get(agent_id)

    def update_agent_profile(self, agent_id: str, profile: Dict[str, Any]) -> None:
        """
        Update or create an agent profile.

        profile can contain:
            role (str): Agent's role description
            strengths (list[str]): What this agent is good at
            limitations (list[str]): Known limitations
            notes (str): Freeform notes
        """
        with self._lock:
            self._data.setdefault("agent_profiles", {})[agent_id] = profile
            self._save()

    def get_all_agent_profiles(self) -> Dict[str, Any]:
        """Return all agent profiles."""
        with self._lock:
            return dict(self._data.get("agent_profiles", {}))

    def get_full_index(self) -> Dict[str, Any]:
        """Return the complete index."""
        with self._lock:
            return dict(self._data)
