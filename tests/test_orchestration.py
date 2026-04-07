"""
Tests for Sprint 54 — Orchestration Manager

Multi-step plan creation, execution, templates, and logging.
"""

import json
import os
import tempfile
import unittest

from simp.orchestration.orchestration_manager import (
    OrchestrationManager,
    OrchestrationPlan,
    OrchestrationStep,
    OrchestrationStepStatus,
)


class TestOrchestrationStepStatus(unittest.TestCase):

    def test_enum_values(self):
        assert OrchestrationStepStatus.PENDING.value == "pending"
        assert OrchestrationStepStatus.RUNNING.value == "running"
        assert OrchestrationStepStatus.COMPLETED.value == "completed"
        assert OrchestrationStepStatus.FAILED.value == "failed"
        assert OrchestrationStepStatus.SKIPPED.value == "skipped"


class TestOrchestrationStep(unittest.TestCase):

    def test_to_dict(self):
        step = OrchestrationStep(step_id="s1", name="Test Step", intent_type="ping")
        d = step.to_dict()
        assert d["step_id"] == "s1"
        assert d["name"] == "Test Step"
        assert d["status"] == "pending"


class TestOrchestrationPlan(unittest.TestCase):

    def test_to_dict(self):
        plan = OrchestrationPlan(plan_id="p1", name="Test Plan")
        plan.steps.append(OrchestrationStep(step_id="s1", name="Step 1"))
        d = plan.to_dict()
        assert d["plan_id"] == "p1"
        assert len(d["steps"]) == 1


class TestCreatePlan(unittest.TestCase):

    def test_create_plan_basic(self):
        mgr = OrchestrationManager()
        plan = mgr.create_plan("Test", "A test plan", [
            {"name": "Step A", "intent_type": "ping"},
            {"name": "Step B", "intent_type": "research"},
        ])
        assert plan.name == "Test"
        assert len(plan.steps) == 2
        assert plan.status == "pending"
        assert plan.plan_id  # UUID assigned

    def test_create_plan_assigns_step_ids(self):
        mgr = OrchestrationManager()
        plan = mgr.create_plan("Test", "", [
            {"name": "Step A"},
            {"name": "Step B"},
        ])
        assert plan.steps[0].step_id == "step-0"
        assert plan.steps[1].step_id == "step-1"

    def test_create_plan_custom_step_ids(self):
        mgr = OrchestrationManager()
        plan = mgr.create_plan("Test", "", [
            {"step_id": "custom-1", "name": "Step A"},
        ])
        assert plan.steps[0].step_id == "custom-1"


class TestExecutePlan(unittest.TestCase):
    """Execute without broker — simulated success."""

    def test_execute_all_steps_succeed(self):
        mgr = OrchestrationManager(broker=None)
        plan = mgr.create_plan("Test", "desc", [
            {"name": "Step A", "intent_type": "ping"},
            {"name": "Step B", "intent_type": "analysis"},
        ])
        result = mgr.execute_plan(plan.plan_id)
        assert result.status == "completed"
        for step in result.steps:
            assert step.status == "completed"
            assert step.result is not None

    def test_execute_records_timestamps(self):
        mgr = OrchestrationManager(broker=None)
        plan = mgr.create_plan("Test", "", [{"name": "S1"}])
        result = mgr.execute_plan(plan.plan_id)
        assert result.completed_at != ""
        assert result.steps[0].started_at != ""
        assert result.steps[0].completed_at != ""

    def test_execute_nonexistent_plan_raises(self):
        mgr = OrchestrationManager()
        with self.assertRaises(KeyError):
            mgr.execute_plan("nonexistent-id")


class TestGetAndListPlans(unittest.TestCase):

    def test_get_plan(self):
        mgr = OrchestrationManager()
        plan = mgr.create_plan("Test", "", [{"name": "S1"}])
        found = mgr.get_plan(plan.plan_id)
        assert found is not None
        assert found.plan_id == plan.plan_id

    def test_get_plan_not_found(self):
        mgr = OrchestrationManager()
        assert mgr.get_plan("bad-id") is None

    def test_list_plans(self):
        mgr = OrchestrationManager()
        mgr.create_plan("Plan A", "", [{"name": "S1"}])
        mgr.create_plan("Plan B", "", [{"name": "S1"}])
        plans = mgr.list_plans()
        assert len(plans) == 2
        assert plans[0]["name"] == "Plan A"


class TestPlanTemplates(unittest.TestCase):

    def test_maintenance_plan(self):
        mgr = OrchestrationManager()
        plan = mgr.make_maintenance_plan()
        assert plan.name == "System Maintenance"
        assert len(plan.steps) >= 3

    def test_analysis_plan(self):
        mgr = OrchestrationManager()
        plan = mgr.make_analysis_plan()
        assert plan.name == "Market Analysis"
        assert len(plan.steps) >= 4

    def test_demo_plan(self):
        mgr = OrchestrationManager()
        plan = mgr.make_full_demo_plan()
        assert plan.name == "Full Demo"
        assert len(plan.steps) >= 5


class TestOrchestrationLogging(unittest.TestCase):
    """Execution writes to orchestration_log.jsonl."""

    def test_log_written_on_execute(self):
        log_path = "data/orchestration_log.jsonl"
        # Clear if exists
        if os.path.exists(log_path):
            os.remove(log_path)

        mgr = OrchestrationManager(broker=None)
        plan = mgr.create_plan("Log Test", "", [{"name": "S1"}])
        mgr.execute_plan(plan.plan_id)

        assert os.path.exists(log_path)
        with open(log_path, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        # Should have at minimum: plan_started, step_started, step_completed, plan_completed
        assert len(lines) >= 4
        events = [json.loads(l) for l in lines]
        kinds = [e["event_kind"] for e in events]
        assert "plan_started" in kinds
        assert "plan_completed" in kinds


if __name__ == "__main__":
    unittest.main()
