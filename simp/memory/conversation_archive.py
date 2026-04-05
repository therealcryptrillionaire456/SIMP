"""
SIMP Conversation Archive

Saves and retrieves conversation records as JSON files.
Thread-safe for concurrent broker access.
"""

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:80]


class ConversationArchive:
    """Manages conversation records stored as JSON files."""

    def __init__(self, base_dir: str = "memory/conversations"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save_conversation(self, record: Dict[str, Any]) -> str:
        """
        Save a conversation record to disk.

        Required fields in record:
            topic (str): Conversation topic
            summary (str): Brief summary
            participants (list[str]): Agent IDs involved
            decisions (list[str]): Key decisions made
            tags (list[str]): Searchable tags

        Returns:
            The conversation ID (filename stem).
        """
        with self._lock:
            topic = record.get("topic", "untitled")
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            slug = _slugify(topic)
            conv_id = f"{date_str}_{slug}"
            filename = f"{conv_id}.json"

            record.setdefault("id", conv_id)
            record.setdefault("created_at", datetime.now(timezone.utc).isoformat() + "Z")
            record.setdefault("participants", [])
            record.setdefault("decisions", [])
            record.setdefault("tags", [])

            path = self.base_dir / filename
            path.write_text(json.dumps(record, indent=2, default=str))
            return conv_id

    def list_conversations(
        self,
        topic: Optional[str] = None,
        tag: Optional[str] = None,
        participant: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List conversations with optional filters."""
        results = []
        with self._lock:
            for path in sorted(self.base_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text())
                except (json.JSONDecodeError, OSError):
                    continue

                if topic and topic.lower() not in data.get("topic", "").lower():
                    continue
                if tag and tag not in data.get("tags", []):
                    continue
                if participant and participant not in data.get("participants", []):
                    continue

                results.append(data)
        return results

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Get a single conversation by ID."""
        with self._lock:
            path = self.base_dir / f"{conv_id}.json"
            if not path.exists():
                # Try partial match
                for candidate in self.base_dir.glob(f"*{conv_id}*.json"):
                    path = candidate
                    break
                else:
                    return None
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                return None

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Full-text search across summaries and decisions."""
        query_lower = query.lower()
        results = []
        with self._lock:
            for path in sorted(self.base_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text())
                except (json.JSONDecodeError, OSError):
                    continue

                searchable = " ".join([
                    data.get("summary", ""),
                    data.get("topic", ""),
                    " ".join(data.get("decisions", [])),
                    " ".join(data.get("tags", [])),
                ]).lower()

                if query_lower in searchable:
                    results.append(data)
        return results
