"""
SIMP Session Bootstrap

Generates compact context packs (<10KB) for new agent sessions.
Pulls from task memory, conversation archive, knowledge index, and task ledger.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from simp.memory.conversation_archive import ConversationArchive
from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex


class SessionBootstrap:
    """Generates and manages context packs for agent sessions."""

    MAX_PACK_SIZE = 10 * 1024  # 10KB target

    def __init__(
        self,
        task_memory: Optional[TaskMemory] = None,
        conversation_archive: Optional[ConversationArchive] = None,
        knowledge_index: Optional[KnowledgeIndex] = None,
        task_ledger: Optional[Any] = None,
        packs_dir: str = "memory/context_packs",
    ):
        self.task_memory = task_memory or TaskMemory()
        self.conversation_archive = conversation_archive or ConversationArchive()
        self.knowledge_index = knowledge_index or KnowledgeIndex()
        self.task_ledger = task_ledger
        self.packs_dir = Path(packs_dir)
        self.packs_dir.mkdir(parents=True, exist_ok=True)

    def generate_context_pack(
        self,
        task_id: Optional[str] = None,
        topic: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a compact context pack.

        At least one of task_id, topic, or agent_id should be provided.
        The pack is kept under MAX_PACK_SIZE bytes.
        """
        pack: Dict[str, Any] = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "params": {
                "task_id": task_id,
                "topic": topic,
                "agent_id": agent_id,
            },
        }

        # Task memory context
        if task_id:
            task_data = self.task_memory.get_task(task_id)
            if task_data:
                # Strip raw content to save space
                task_data.pop("raw", None)
                pack["task"] = task_data

        # Topic context from knowledge index
        if topic:
            topic_data = self.knowledge_index.get_topic(topic)
            if topic_data:
                pack["topic"] = topic_data

            # Recent conversations on this topic
            convos = self.conversation_archive.list_conversations(topic=topic)
            if convos:
                # Include only the 5 most recent, summarized
                recent = convos[-5:]
                pack["recent_conversations"] = [
                    {
                        "id": c.get("id"),
                        "topic": c.get("topic"),
                        "summary": c.get("summary", "")[:200],
                        "decisions": c.get("decisions", [])[:5],
                        "created_at": c.get("created_at"),
                    }
                    for c in recent
                ]

        # Agent profile
        if agent_id:
            profile = self.knowledge_index.get_agent_profile(agent_id)
            if profile:
                pack["agent_profile"] = profile

        # Active tasks summary (always included, compact)
        all_tasks = self.task_memory.list_tasks()
        active_tasks = [t for t in all_tasks if t.get("status") == "active"]
        if active_tasks:
            pack["active_tasks"] = active_tasks

        # Task ledger summary if available
        if self.task_ledger:
            try:
                ledger_tasks = self.task_ledger.list_tasks(status="in_progress")
                if ledger_tasks:
                    pack["in_progress_ledger_tasks"] = [
                        {
                            "task_id": t.get("task_id"),
                            "title": t.get("title"),
                            "assigned_agent": t.get("assigned_agent") or t.get("claimed_by"),
                        }
                        for t in ledger_tasks[:10]
                    ]
            except Exception:
                pass

        # Truncate if too large
        pack_json = json.dumps(pack, default=str)
        if len(pack_json) > self.MAX_PACK_SIZE:
            # Remove least critical sections
            for key in ("recent_conversations", "in_progress_ledger_tasks", "active_tasks"):
                if key in pack:
                    del pack[key]
                    pack_json = json.dumps(pack, default=str)
                    if len(pack_json) <= self.MAX_PACK_SIZE:
                        break

        return pack

    def save_context_pack(self, pack: Dict[str, Any], pack_id: Optional[str] = None) -> str:
        """Save a context pack to disk. Returns the pack ID."""
        if not pack_id:
            pack_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            params = pack.get("params", {})
            suffix = params.get("task_id") or params.get("topic") or params.get("agent_id") or "general"
            pack_id = f"{pack_id}_{suffix}"

        path = self.packs_dir / f"{pack_id}.json"
        path.write_text(json.dumps(pack, indent=2, default=str))
        return pack_id

    def load_context_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        """Load a context pack from disk."""
        path = self.packs_dir / f"{pack_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
