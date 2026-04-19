"""
SIMP Memory Layer

Provides persistent memory and context management for multi-agent coordination:
- ConversationArchive: JSON-based conversation storage and search
- TaskMemory: Markdown-based task tracking with structured templates
- KnowledgeIndex: Topic and agent profile index
- SessionBootstrap: Compact context pack generation for new agent sessions
- MemoryHooks: Event-driven memory updates
"""

from simp.memory.conversation_archive import ConversationArchive
from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.session_bootstrap import SessionBootstrap
from simp.memory.hooks import MemoryHooks

__all__ = [
    "ConversationArchive",
    "TaskMemory",
    "KnowledgeIndex",
    "SessionBootstrap",
    "MemoryHooks",
]
