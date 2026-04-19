"""Tests for Sprint 24: Recursive self-improvement engine."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestKnowledgeIndexPersistence:
    def test_knowledge_index_importable(self):
        from simp.memory.knowledge_index import KnowledgeIndex
        ki = KnowledgeIndex()
        assert ki is not None

    def test_add_and_search(self, tmp_path):
        from simp.memory.knowledge_index import KnowledgeIndex
        ki = KnowledgeIndex(base_dir=str(tmp_path))
        ki.add_entry("test_category", {"value": 42, "label": "test"})
        results = ki.search("test_category")
        assert len(results) == 1
        assert results[0]["value"] == 42

    def test_persistence_round_trip(self, tmp_path):
        from simp.memory.knowledge_index import KnowledgeIndex
        ki1 = KnowledgeIndex(base_dir=str(tmp_path))
        ki1.add_entry("persist_test", {"data": "hello"})
        # Create new instance — should load persisted data
        ki2 = KnowledgeIndex(base_dir=str(tmp_path))
        results = ki2.search("persist_test")
        assert len(results) == 1

    def test_category_cap(self, tmp_path):
        from simp.memory.knowledge_index import KnowledgeIndex
        ki = KnowledgeIndex(base_dir=str(tmp_path))
        for i in range(1050):
            ki.add_entry("big_category", {"i": i})
        results = ki.search("big_category")
        assert len(results) <= 1000


class TestProjectXKnowledgeSync:
    def test_sync_knowledge(self, tmp_path):
        from simp.projectx.computer import ProjectXComputer
        pc = ProjectXComputer(log_dir=str(tmp_path / "logs"))
        knowledge = pc.sync_knowledge()
        assert "sources" in knowledge
        assert "timestamp" in knowledge

    def test_check_protocol_health(self, tmp_path):
        from simp.projectx.computer import ProjectXComputer
        pc = ProjectXComputer(log_dir=str(tmp_path / "logs"))
        health = pc.check_protocol_health()
        assert "checks" in health
        assert "healthy" in health
        assert isinstance(health["checks"], list)

    def test_update_knowledge_detects_changes(self, tmp_path):
        from simp.projectx.computer import ProjectXComputer
        pc = ProjectXComputer(log_dir=str(tmp_path / "logs"))
        k1 = pc.sync_knowledge()
        k2 = pc.update_knowledge()
        assert "changes_detected" in k2

    def test_knowledge_actions_in_tiers(self):
        from simp.projectx.computer import ACTION_TIERS
        assert "sync_knowledge" in ACTION_TIERS
        assert "check_protocol_health" in ACTION_TIERS
        assert ACTION_TIERS["sync_knowledge"] == 0  # Read-only = tier 0


class TestDirectedMutations:
    def test_q_intent_compiler_importable(self):
        from simp.agents.q_intent_compiler import StrategicOptimizer
        assert StrategicOptimizer is not None

    def test_kloutbot_mutation_memory_importable(self):
        from simp.agents.kloutbot_agent import KloutbotAgent
        assert KloutbotAgent is not None


class TestModulesCompile:
    def test_knowledge_index_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "memory", "knowledge_index.py"),
            doraise=True
        )

    def test_projectx_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "projectx", "computer.py"),
            doraise=True
        )

    def test_q_intent_compiler_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "agents", "q_intent_compiler.py"),
            doraise=True
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
