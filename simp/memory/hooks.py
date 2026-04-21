"""
SIMP Memory Hooks

Event-driven hooks that automatically update task memory and knowledge index
when significant events occur in the broker lifecycle.
"""

import logging
from typing import Any, Dict, Optional

from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.conversation_archive import ConversationArchive


logger = logging.getLogger("SIMP.MemoryHooks")


class MemoryHooks:
    """Event hooks that update memory stores on broker events."""

    def __init__(
        self,
        task_memory: Optional[TaskMemory] = None,
        knowledge_index: Optional[KnowledgeIndex] = None,
        conversation_archive: Optional[ConversationArchive] = None,
    ):
        self.task_memory = task_memory or TaskMemory()
        self.knowledge_index = knowledge_index or KnowledgeIndex()
        self.conversation_archive = conversation_archive or ConversationArchive()

    def on_task_completed(self, task_data: Dict[str, Any]) -> None:
        """
        Called when a task completes in the broker.
        Updates knowledge index with task outcome.
        """
        try:
            task_type = task_data.get("task_type", "unknown")
            title = task_data.get("title", "")
            agent = task_data.get("assigned_agent") or task_data.get("claimed_by", "unknown")

            self.knowledge_index.update_topic(task_type, {
                "decisions": [f"Task '{title}' completed by {agent}"],
                "tags": [task_type, "completed"],
            })
            logger.info(f"Memory updated for completed task: {title}")
        except Exception as exc:
            logger.warning(f"Failed to update memory on task completion: {exc}")

    def on_intent_routed(self, intent_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Called after an intent is routed by the broker.
        Updates knowledge index with routing information.
        """
        try:
            intent_type = intent_data.get("intent_type", "unknown")
            target_agent = result.get("target_agent", "unknown")
            delivery_status = result.get("delivery_status", "unknown")

            self.knowledge_index.update_topic(intent_type, {
                "tags": [intent_type, "routed"],
            })

            # Track agent activity in profiles
            profile = self.knowledge_index.get_agent_profile(target_agent) or {}
            notes = profile.get("notes", "")
            profile["notes"] = notes  # preserve existing notes
            self.knowledge_index.update_agent_profile(target_agent, profile)

            logger.debug(
                f"Memory updated for routed intent: {intent_type} -> {target_agent} "
                f"({delivery_status})"
            )
        except Exception as exc:
            logger.warning(f"Failed to update memory on intent routed: {exc}")

    def on_conversation_end(
        self, topic: str, summary: str, participants: list, decisions: list, tags: list
    ) -> str:
        """
        Called when a multi-agent conversation concludes.
        Saves the conversation and updates the knowledge index.

        Returns:
            The conversation ID.
        """
        try:
            conv_id = self.conversation_archive.save_conversation({
                "topic": topic,
                "summary": summary,
                "participants": participants,
                "decisions": decisions,
                "tags": tags,
            })

            self.knowledge_index.update_topic(topic, {
                "conversations": [conv_id],
                "decisions": decisions,
                "tags": tags,
            })

            logger.info(f"Conversation archived: {conv_id}")
            return conv_id
        except Exception as exc:
            logger.warning(f"Failed to archive conversation: {exc}")
            return ""

    def on_session_start(self, agent_id: str, task_id: Optional[str] = None) -> None:
        """
        Called when a new agent session starts.
        Logs the session start in knowledge index.
        """
        try:
            profile = self.knowledge_index.get_agent_profile(agent_id) or {}
            profile.setdefault("role", "unknown")
            self.knowledge_index.update_agent_profile(agent_id, profile)

            if task_id:
                self.task_memory.add_history_entry(
                    task_id, f"Session started by {agent_id}"
                )

            logger.info(f"Session start recorded: {agent_id}")
        except Exception as exc:
            logger.warning(f"Failed to record session start: {exc}")
