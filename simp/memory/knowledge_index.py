"""
SIMP Knowledge Index

Central index mapping topics to conversations, task files, code locations,
and decisions. Also stores agent profiles and category-based entries for
self-improvement persistence (improvement history, mutation memory).
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class KnowledgeIndex:
    """Manages the memory/index.json knowledge index."""

    def __init__(self, base_dir: Optional[str] = None, index_path: Optional[str] = None):
        if base_dir is not None:
            self._base_dir = base_dir
            self.index_path = Path(os.path.join(base_dir, "index.json"))
        elif index_path is not None:
            self._base_dir = str(Path(index_path).parent)
            self.index_path = Path(index_path)
        else:
            self._base_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "memory"
            )
            self.index_path = Path(os.path.join(self._base_dir, "index.json"))
        self._lock = threading.RLock()
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load index from disk."""
        if self.index_path.exists():
            try:
                return json.loads(self.index_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"topics": {}, "agent_profiles": {}, "categories": {}}

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

    # ── Category-based storage for self-improvement persistence ──────

    def add_entry(self, category: str, data: Any) -> None:
        """Add an entry to a category (used by improvement history, mutation memory)."""
        with self._lock:
            cats = self._data.setdefault("categories", {})
            if category not in cats:
                cats[category] = []
            cats[category].append(data)
            # Cap at 1000 entries per category
            if len(cats[category]) > 1000:
                cats[category] = cats[category][-1000:]
            self._save()

    def search(self, category: str, query: Optional[str] = None) -> List[Any]:
        """Get entries from a category, optionally filtered by query string."""
        with self._lock:
            entries = self._data.get("categories", {}).get(category, [])
            if query and isinstance(query, str):
                entries = [
                    e for e in entries
                    if query.lower() in json.dumps(e, default=str).lower()
                ]
            return list(entries)

    def get_categories(self) -> List[str]:
        """List all categories."""
        with self._lock:
            return list(self._data.get("categories", {}).keys())
