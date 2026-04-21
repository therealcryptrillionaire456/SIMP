"""Tests for Sprint 8: Memory layer activation."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.broker import SimpBroker, BrokerConfig
from simp.memory.hooks import MemoryHooks
from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.conversation_archive import ConversationArchive
from simp.memory.system_memory import SystemMemoryStore


class TestMemoryHooksWired:
    @pytest.fixture
    def broker_with_hooks(self):
        hooks = MemoryHooks()
        config = BrokerConfig(max_agents=10)
        broker = SimpBroker(config, hooks=hooks)
        broker.start()
        return broker

    def test_broker_has_hooks(self, broker_with_hooks):
        assert broker_with_hooks.hooks is not None

    def test_hooks_has_on_task_completed(self, broker_with_hooks):
        assert hasattr(broker_with_hooks.hooks, "on_task_completed")
        assert callable(broker_with_hooks.hooks.on_task_completed)

    def test_hooks_has_on_intent_routed(self, broker_with_hooks):
        assert hasattr(broker_with_hooks.hooks, "on_intent_routed")
        assert callable(broker_with_hooks.hooks.on_intent_routed)

    def test_on_intent_routed_no_crash(self, broker_with_hooks):
        """Calling on_intent_routed should not raise."""
        broker_with_hooks.hooks.on_intent_routed(
            {"intent_type": "test", "source_agent": "a", "target_agent": "b"},
            {"status": "success"},
        )

    def test_on_task_completed_no_crash(self, broker_with_hooks):
        """Calling on_task_completed should not raise."""
        broker_with_hooks.hooks.on_task_completed({
            "task_type": "test",
            "title": "Test task",
            "intent_id": "test-001",
        })


class TestMemoryComponents:
    def test_task_memory_importable(self):
        tm = TaskMemory()
        assert tm is not None

    def test_knowledge_index_importable(self):
        ki = KnowledgeIndex()
        assert ki is not None

    def test_conversation_archive_importable(self):
        ca = ConversationArchive()
        assert ca is not None

    def test_memory_hooks_persist_structured_episode(self, tmp_path):
        hooks = MemoryHooks(
            task_memory=TaskMemory(base_dir=str(tmp_path / "tasks")),
            knowledge_index=KnowledgeIndex(index_path=str(tmp_path / "index.json")),
            conversation_archive=ConversationArchive(base_dir=str(tmp_path / "conversations")),
            system_memory_store=SystemMemoryStore(db_path=str(tmp_path / "system_memory.sqlite3")),
        )

        hooks.on_intent_routed(
            {"intent_type": "trade_signal", "intent_id": "intent-123", "timestamp": "2026-04-21T17:00:00+00:00"},
            {"target_agent": "gate4_live", "delivery_status": "success", "timestamp": "2026-04-21T17:00:01+00:00"},
        )

        episodes = hooks.system_memory_store.list_episodes(limit=5)
        assert any(
            episode["episode_type"] == "intent_routed"
            and episode["entity"] == "intent-123"
            for episode in episodes
        )


class TestDatetimeDeprecation:
    def test_no_utcnow_in_memory_files(self):
        """Memory layer files should not use deprecated datetime.utcnow()."""
        memory_dir = os.path.join(os.path.dirname(__file__), "..", "simp", "memory")
        for fname in os.listdir(memory_dir):
            if fname.endswith(".py") and not fname.startswith("__"):
                path = os.path.join(memory_dir, fname)
                with open(path) as f:
                    content = f.read()
                assert "datetime.utcnow()" not in content, (
                    f"{fname} still uses deprecated datetime.utcnow()"
                )

    def test_no_utcnow_in_intent_py(self):
        path = os.path.join(os.path.dirname(__file__), "..", "simp", "intent.py")
        with open(path) as f:
            content = f.read()
        assert "datetime.utcnow()" not in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
