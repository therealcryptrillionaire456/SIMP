"""
SIMP Memory Layer

Provides persistent memory and context management for multi-agent coordination:
- ConversationArchive: JSON-based conversation storage and search
- TaskMemory: Markdown-based task tracking with structured templates
- KnowledgeIndex: Topic and agent profile index
- SessionBootstrap: Compact context pack generation for new agent sessions
- MemoryHooks: Event-driven memory updates
- SystemMemoryStore: Structured SQLite store for episodes, lessons, policies
- TradeLearningEngine: Promotion of trade artifacts into lessons/policy candidates
"""

from simp.memory.conversation_archive import ConversationArchive
from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.session_bootstrap import SessionBootstrap
from simp.memory.hooks import MemoryHooks
from simp.memory.system_memory import SystemMemoryStore, Episode, Lesson, PolicyCandidate
from simp.memory.trade_learning import TradeLearningEngine, TradeLearningReport
from simp.memory.system_reflection import SystemLearningEngine, SystemLearningReport

__all__ = [
    "ConversationArchive",
    "TaskMemory",
    "KnowledgeIndex",
    "SessionBootstrap",
    "MemoryHooks",
    "SystemMemoryStore",
    "Episode",
    "Lesson",
    "PolicyCandidate",
    "TradeLearningEngine",
    "TradeLearningReport",
    "SystemLearningEngine",
    "SystemLearningReport",
]
