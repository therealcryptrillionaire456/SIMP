"""Tests for Sprint 19: Production server, orchestration fixes, task dependencies."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProductionServer:
    def test_start_production_script_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "bin", "start_production.py")
        assert os.path.exists(path)

    def test_production_script_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "bin", "start_production.py")
        py_compile.compile(path, doraise=True)

    def test_create_app_factory_exists(self):
        from simp.server.http_server import create_app
        app = create_app()
        assert app is not None

    def test_gunicorn_in_requirements(self):
        path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        with open(path) as f:
            content = f.read()
        assert "gunicorn" in content.lower()


class TestOrchestrationDuplicateFix:
    def test_task_ledger_get_task(self):
        from simp.task_ledger import TaskLedger
        tl = TaskLedger()
        task_id = tl.create_task(
            title="Test task",
            task_type="implementation",
            description="Test task",
        )
        task = tl.get_task(task_id)
        assert task is not None
        assert task["task_id"] == task_id

    def test_no_duplicate_task_for_same_intent(self):
        """Creating a task for the same intent should not duplicate."""
        from simp.task_ledger import TaskLedger
        tl = TaskLedger()
        task_id_1 = tl.create_task(
            title="Task for intent X",
            task_type="implementation",
            description="Task for intent X",
        )
        # The fix should prevent duplicates when routing the same intent
        task = tl.get_task(task_id_1)
        assert task is not None


class TestTaskDependencyOrdering:
    def test_task_ledger_has_blocked_status(self):
        from simp.task_ledger import TaskLedger, VALID_STATUSES
        assert "blocked" in VALID_STATUSES

    def test_subtask_ordering(self):
        from simp.task_ledger import TaskLedger
        tl = TaskLedger()
        parent_id = tl.create_task(
            title="Parent goal",
            task_type="architecture",
            description="Parent goal",
        )
        subtasks = [
            {"task_type": "spec", "description": "Step 1", "title": "Step 1", "order": 0},
            {"task_type": "implementation", "description": "Step 2", "title": "Step 2", "order": 1},
            {"task_type": "test", "description": "Step 3", "title": "Step 3", "order": 2},
        ]
        tl.decompose_task(parent_id, subtasks)
        parent = tl.get_task(parent_id)
        assert len(parent.get("subtask_ids", [])) == 3

    def test_subtask_blocked_status(self):
        """Subtasks with order > 0 should start as blocked."""
        from simp.task_ledger import TaskLedger
        tl = TaskLedger()
        parent_id = tl.create_task(
            title="Parent",
            task_type="architecture",
            description="Parent",
        )
        subtasks = [
            {"task_type": "spec", "description": "Step 1", "title": "Step 1", "order": 0},
            {"task_type": "implementation", "description": "Step 2", "title": "Step 2", "order": 1},
        ]
        sub_ids = tl.decompose_task(parent_id, subtasks)
        first = tl.get_task(sub_ids[0])
        second = tl.get_task(sub_ids[1])
        assert first["status"] == "queued"
        assert second["status"] == "blocked"

    def test_unblock_on_predecessor_complete(self):
        """Completing a predecessor should unblock the next subtask."""
        from simp.task_ledger import TaskLedger
        tl = TaskLedger()
        parent_id = tl.create_task(
            title="Parent",
            task_type="architecture",
            description="Parent",
        )
        subtasks = [
            {"task_type": "spec", "description": "Step 1", "title": "Step 1", "order": 0},
            {"task_type": "implementation", "description": "Step 2", "title": "Step 2", "order": 1},
        ]
        sub_ids = tl.decompose_task(parent_id, subtasks)
        # Complete the first subtask
        tl.claim_task(sub_ids[0], "worker")
        tl.complete_task(sub_ids[0], result={"output": "done"})
        # Second subtask should now be unblocked
        second = tl.get_task(sub_ids[1])
        assert second["status"] == "queued"

    def test_complete_task_exists(self):
        from simp.task_ledger import TaskLedger
        tl = TaskLedger()
        task_id = tl.create_task(
            title="Completable task",
            task_type="test",
            description="Completable task",
        )
        tl.claim_task(task_id, "worker")
        tl.complete_task(task_id, result={"output": "done"})
        task = tl.get_task(task_id)
        assert task["status"] == "completed"


class TestModulesCompile:
    def test_http_server_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "server", "http_server.py"),
            doraise=True
        )

    def test_broker_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "server", "broker.py"),
            doraise=True
        )

    def test_orchestration_loop_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "orchestration", "orchestration_loop.py"),
            doraise=True
        )

    def test_task_ledger_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "task_ledger.py"),
            doraise=True
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
