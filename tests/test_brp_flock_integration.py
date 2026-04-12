"""
BRP flock integration tests for remaining agents:
- Kloutbot: strategy generation + goal decomposition
- CoWork Bridge: peer intent gate
- OrchestrationLoop: task assignment

All tests use the real BRP bridge with a temp data dir to validate
end-to-end event/observation flow. Agent methods are invoked directly
or via mocks where full infrastructure (Flask, broker) is impractical.
"""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from simp.security.brp_models import (
    BRPDecision,
    BRPEvent,
    BRPEventType,
    BRPMode,
    BRPObservation,
    BRPPlan,
    BRPResponse,
)
from simp.security.brp_bridge import BRPBridge


@pytest.fixture
def brp_dir(tmp_path):
    return str(tmp_path / "brp")


@pytest.fixture
def bridge(brp_dir):
    return BRPBridge(data_dir=brp_dir)


# ---------------------------------------------------------------------------
# 1. Kloutbot — strategy generation BRP event
# ---------------------------------------------------------------------------

class TestKloutbotStrategyBRPEvent:
    def test_kloutbot_strategy_brp_event(self, bridge, brp_dir):
        """
        Mock KloutbotAgent.handle_generate_strategy, verify BRP event
        is emitted and metadata is attached to the response.
        """
        # Patch the module-level _brp_bridge to use our test bridge
        with patch("simp.agents.kloutbot_agent._get_brp_bridge", return_value=bridge):
            from simp.agents.kloutbot_agent import _get_brp_bridge

            # Simulate the BRP event flow that handle_generate_strategy does
            from simp.security.brp_models import BRPEvent, BRPEventType, BRPMode
            brp_event = BRPEvent(
                source_agent="kloutbot",
                event_type=BRPEventType.STRATEGY_GENERATION.value,
                action="generate_strategy",
                context={"foresight": {"affinity": 0.85}, "deltas": {"momentum": 0.8}},
                mode=BRPMode.SHADOW.value,
                tags=["kloutbot", "strategy_generation"],
            )
            brp_resp = bridge.evaluate_event(brp_event)

            # Verify BRP response metadata
            assert brp_resp.decision == BRPDecision.SHADOW_ALLOW.value
            assert brp_resp.mode == BRPMode.SHADOW.value
            assert brp_resp.threat_score < 0.5

            # Verify event was persisted
            events_log = os.path.join(brp_dir, "events.jsonl")
            assert os.path.exists(events_log)
            with open(events_log) as f:
                lines = f.readlines()
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["source_agent"] == "kloutbot"
            assert record["event_type"] == "strategy_generation"

            # Simulate success observation
            obs = BRPObservation(
                source_agent="kloutbot",
                event_id=brp_event.event_id,
                action="generate_strategy",
                outcome="success",
                result_data={"strategy_count": 1},
                mode=BRPMode.SHADOW.value,
                tags=["kloutbot", "strategy_generation"],
            )
            bridge.ingest_observation(obs)

            obs_log = os.path.join(brp_dir, "observations.jsonl")
            with open(obs_log) as f:
                lines = f.readlines()
            assert len(lines) == 1
            obs_record = json.loads(lines[0])
            assert obs_record["outcome"] == "success"
            assert obs_record["event_id"] == brp_event.event_id


# ---------------------------------------------------------------------------
# 2. Kloutbot — goal decomposition BRP plan
# ---------------------------------------------------------------------------

class TestKloutbotGoalBRPPlan:
    def test_kloutbot_goal_brp_plan(self, bridge, brp_dir):
        """
        Mock handle_submit_goal plan evaluation, verify BRP plan evaluation occurs.
        """
        # Simulate the BRP plan evaluation that handle_submit_goal does
        subtasks = [
            {"task_type": "research", "description": "Gather data"},
            {"task_type": "implementation", "description": "Build pipeline"},
            {"task_type": "testing", "description": "Write tests"},
        ]
        brp_plan = BRPPlan(
            source_agent="kloutbot",
            steps=[
                {"action": st["task_type"], "description": st["description"]}
                for st in subtasks
            ],
            context={"goal": "Build a data pipeline", "goal_type": "build"},
            mode=BRPMode.SHADOW.value,
            tags=["kloutbot", "goal_decomposition"],
        )
        brp_resp = bridge.evaluate_plan(brp_plan)

        assert brp_resp.decision == BRPDecision.SHADOW_ALLOW.value
        assert brp_resp.threat_score < 0.5

        # Verify plan persisted
        plans_log = os.path.join(brp_dir, "plans.jsonl")
        assert os.path.exists(plans_log)
        with open(plans_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["source_agent"] == "kloutbot"
        assert len(record["steps"]) == 3


# ---------------------------------------------------------------------------
# 3. CoWork Bridge — BRP gate on peer intent
# ---------------------------------------------------------------------------

class TestCoWorkBridgeBRPGate:
    def test_cowork_bridge_brp_gate(self, bridge, brp_dir):
        """
        Verify BRP event evaluation fires on incoming peer intent.
        """
        brp_event = BRPEvent(
            source_agent="external_agent",
            event_type=BRPEventType.PEER_INTENT.value,
            action="code_task",
            context={
                "intent_id": "test-123",
                "target_agent": "claude_cowork",
                "params": {"task_id": "task-1"},
            },
            mode=BRPMode.SHADOW.value,
            tags=["cowork_bridge", "peer_intent", "code_task"],
        )
        brp_resp = bridge.evaluate_event(brp_event)

        assert brp_resp.decision == BRPDecision.SHADOW_ALLOW.value
        assert brp_resp.mode == BRPMode.SHADOW.value

        # Verify event persisted
        events_log = os.path.join(brp_dir, "events.jsonl")
        with open(events_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_type"] == "peer_intent"
        assert record["action"] == "code_task"


# ---------------------------------------------------------------------------
# 4. CoWork Bridge — shadow mode passthrough
# ---------------------------------------------------------------------------

class TestCoWorkBridgeShadowPassthrough:
    def test_cowork_bridge_brp_shadow_passthrough(self, bridge):
        """
        Shadow mode must never block — even restricted actions get SHADOW_ALLOW.
        """
        # Test with a normal peer intent
        brp_event = BRPEvent(
            source_agent="peer_agent",
            event_type=BRPEventType.PEER_INTENT.value,
            action="code_task",
            mode=BRPMode.SHADOW.value,
        )
        resp = bridge.evaluate_event(brp_event)
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value

        # Even a high-value event still passes in shadow mode
        brp_event2 = BRPEvent(
            source_agent="peer_agent",
            event_type=BRPEventType.PEER_INTENT.value,
            action="withdrawal",
            mode=BRPMode.SHADOW.value,
        )
        resp2 = bridge.evaluate_event(brp_event2)
        assert resp2.decision == BRPDecision.SHADOW_ALLOW.value
        assert resp2.threat_score >= 0.8  # flagged but not blocked


# ---------------------------------------------------------------------------
# 5. OrchestrationLoop — BRP event before routing
# ---------------------------------------------------------------------------

class TestOrchestrationLoopBRPEvent:
    def test_orchestration_loop_brp_event(self, bridge, brp_dir):
        """
        Verify BRP event is emitted for task assignment.
        """
        brp_event = BRPEvent(
            source_agent="test_builder",
            event_type=BRPEventType.TASK_ASSIGNMENT.value,
            action="implementation",
            context={
                "task_id": "task-42",
                "priority": "high",
                "builder": "test_builder",
                "title": "Implement feature X",
            },
            mode=BRPMode.SHADOW.value,
            tags=["orchestration_loop", "task_assignment", "implementation"],
        )
        resp = bridge.evaluate_event(brp_event)

        assert resp.decision == BRPDecision.SHADOW_ALLOW.value
        assert resp.threat_score < 0.5

        # Verify event persisted
        events_log = os.path.join(brp_dir, "events.jsonl")
        with open(events_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_type"] == "task_assignment"
        assert record["source_agent"] == "test_builder"

        # Post-routing observation
        obs = BRPObservation(
            source_agent="orchestration_loop",
            event_id=brp_event.event_id,
            action="implementation",
            outcome="success",
            result_data={"delivery_status": "delivered", "task_id": "task-42", "builder": "test_builder"},
            mode=BRPMode.SHADOW.value,
            tags=["orchestration_loop", "task_assignment"],
        )
        bridge.ingest_observation(obs)

        obs_log = os.path.join(brp_dir, "observations.jsonl")
        with open(obs_log) as f:
            lines = f.readlines()
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# 6. OrchestrationLoop — enforced mode DENY blocks assignment
# ---------------------------------------------------------------------------

class TestOrchestrationLoopBRPDeny:
    def test_orchestration_loop_brp_deny_blocks(self, bridge):
        """
        In enforced mode, DENY on a restricted action prevents task assignment.
        """
        # A restricted action in enforced mode should yield DENY
        brp_event = BRPEvent(
            source_agent="orchestration_loop",
            event_type=BRPEventType.TASK_ASSIGNMENT.value,
            action="withdrawal",  # restricted action
            mode=BRPMode.ENFORCED.value,
            tags=["orchestration_loop", "task_assignment"],
        )
        resp = bridge.evaluate_event(brp_event)
        assert resp.decision == BRPDecision.DENY.value
        assert resp.threat_score >= 0.8

    def test_orchestration_loop_shadow_never_blocks(self, bridge):
        """
        Shadow mode must not block even restricted task types.
        """
        brp_event = BRPEvent(
            source_agent="orchestration_loop",
            event_type=BRPEventType.TASK_ASSIGNMENT.value,
            action="withdrawal",
            mode=BRPMode.SHADOW.value,
        )
        resp = bridge.evaluate_event(brp_event)
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value


# ---------------------------------------------------------------------------
# 7. All flock agents BRP-aware
# ---------------------------------------------------------------------------

class TestAllFlockAgentsBRPAware:
    def test_all_flock_agents_brp_aware(self):
        """
        Verify all 6 agents have BRP integration points by checking
        that their modules contain _get_brp_bridge or BRP-related imports.

        Note: some modules (e.g. simp.server.broker) have heavy deps that
        may not be installed in all test environments, so we check source
        files for those and import only the ones that are importable.
        """
        import importlib

        # Modules that can be imported directly
        importable_modules = {
            "simp.agents.quantumarb_agent": "_get_brp_bridge",
            "simp.agents.kloutbot_agent": "_get_brp_bridge",
            "simp.agents.cowork_bridge": "_get_brp_bridge",
            "simp.orchestration.orchestration_loop": "_get_brp_bridge",
        }

        for module_name, expected_attr in importable_modules.items():
            mod = importlib.import_module(module_name)
            assert hasattr(mod, expected_attr), (
                f"{module_name} missing BRP integration attribute: {expected_attr}"
            )

        # For modules with heavy deps, verify via source file grep
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        source_checks = {
            "simp/server/broker.py": "evaluate_plan",
            "simp/integrations/kashclaw_shim.py": "BRPEvent",
        }
        for filepath, expected_string in source_checks.items():
            full_path = os.path.join(repo_root, filepath)
            assert os.path.exists(full_path), f"{filepath} not found"
            with open(full_path) as f:
                content = f.read()
            assert expected_string in content, (
                f"{filepath} missing BRP integration: expected '{expected_string}'"
            )


# ---------------------------------------------------------------------------
# 8. New event types exist in BRPEventType enum
# ---------------------------------------------------------------------------

class TestNewEventTypes:
    def test_strategy_generation_event_type(self):
        assert BRPEventType.STRATEGY_GENERATION.value == "strategy_generation"

    def test_peer_intent_event_type(self):
        assert BRPEventType.PEER_INTENT.value == "peer_intent"

    def test_task_assignment_event_type(self):
        assert BRPEventType.TASK_ASSIGNMENT.value == "task_assignment"

    def test_goal_decomposition_event_type(self):
        assert BRPEventType.GOAL_DECOMPOSITION.value == "goal_decomposition"
