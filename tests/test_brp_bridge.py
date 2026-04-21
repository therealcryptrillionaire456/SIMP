"""
Unit tests for BRP bridge: schema validation, scoring, JSONL persistence,
restricted action escalation, and shadow allow behaviour.
"""

import json
import os
import tempfile

import pytest

from simp.security.brp_models import (
    BRPDecision,
    BRPEvent,
    BRPEventType,
    BRPMode,
    BRPObservation,
    BRPPlan,
    BRPResponse,
    BRPSeverity,
    RESTRICTED_ACTIONS,
)
from simp.security.brp_bridge import BRPBridge


@pytest.fixture
def tmp_data_dir(tmp_path):
    return str(tmp_path / "brp")


@pytest.fixture
def bridge(tmp_data_dir):
    return BRPBridge(data_dir=tmp_data_dir)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestBRPSchemas:
    def test_brp_event_defaults(self):
        event = BRPEvent()
        assert event.schema_version == "brp.event.v1"
        assert event.event_id  # non-empty uuid
        assert event.mode == BRPMode.SHADOW.value
        d = event.to_dict()
        assert "event_id" in d
        assert d["schema_version"] == "brp.event.v1"

    def test_brp_plan_defaults(self):
        plan = BRPPlan(steps=[{"action": "trade_buy"}])
        assert plan.schema_version == "brp.plan.v1"
        assert len(plan.steps) == 1
        d = plan.to_dict()
        assert d["steps"] == [{"action": "trade_buy"}]

    def test_brp_observation_defaults(self):
        obs = BRPObservation(event_id="evt-1", outcome="success")
        assert obs.schema_version == "brp.observation.v1"
        assert obs.event_id == "evt-1"

    def test_brp_response_defaults(self):
        resp = BRPResponse()
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value
        assert resp.threat_score == 0.0
        assert resp.confidence == 1.0

    def test_brp_event_custom_fields(self):
        event = BRPEvent(
            source_agent="kashclaw:agent",
            event_type=BRPEventType.TRADE_EXECUTION.value,
            action="trade_buy",
            params={"quantity": 10},
            tags=["test"],
        )
        d = event.to_dict()
        assert d["source_agent"] == "kashclaw:agent"
        assert d["tags"] == ["test"]


# ---------------------------------------------------------------------------
# Bridge scoring defaults
# ---------------------------------------------------------------------------

class TestBridgeScoring:
    def test_safe_action_low_threat(self, bridge):
        event = BRPEvent(action="trade_buy", params={"quantity": 5})
        resp = bridge.evaluate_event(event)
        assert resp.threat_score < 0.2
        assert resp.severity == BRPSeverity.INFO.value

    def test_high_value_elevated_threat(self, bridge):
        event = BRPEvent(action="trade_buy", params={"quantity": 200_000})
        resp = bridge.evaluate_event(event)
        assert resp.threat_score >= 0.6
        assert "high_value" in resp.threat_tags

    def test_plan_with_safe_steps(self, bridge):
        plan = BRPPlan(steps=[
            {"action": "trade_buy", "quantity": 10},
            {"action": "trade_sell", "quantity": 10},
        ])
        resp = bridge.evaluate_plan(plan)
        assert resp.threat_score < 0.2
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value


# ---------------------------------------------------------------------------
# JSONL persistence
# ---------------------------------------------------------------------------

class TestJSONLPersistence:
    def test_event_persisted(self, bridge, tmp_data_dir):
        event = BRPEvent(action="trade_buy")
        bridge.evaluate_event(event)

        events_log = os.path.join(tmp_data_dir, "events.jsonl")
        assert os.path.exists(events_log)
        with open(events_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_id"] == event.event_id

    def test_response_persisted(self, bridge, tmp_data_dir):
        event = BRPEvent(action="trade_buy")
        bridge.evaluate_event(event)

        resp_log = os.path.join(tmp_data_dir, "responses.jsonl")
        with open(resp_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_id"] == event.event_id

    def test_plan_persisted(self, bridge, tmp_data_dir):
        plan = BRPPlan(steps=[{"action": "trade_buy"}])
        bridge.evaluate_plan(plan)

        plans_log = os.path.join(tmp_data_dir, "plans.jsonl")
        with open(plans_log) as f:
            lines = f.readlines()
        assert len(lines) == 1

    def test_observation_persisted(self, bridge, tmp_data_dir):
        obs = BRPObservation(event_id="evt-1", outcome="success")
        bridge.ingest_observation(obs)

        obs_log = os.path.join(tmp_data_dir, "observations.jsonl")
        with open(obs_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_id"] == "evt-1"

    def test_multiple_events_appended(self, bridge, tmp_data_dir):
        for i in range(5):
            bridge.evaluate_event(BRPEvent(action=f"action_{i}"))
        events_log = os.path.join(tmp_data_dir, "events.jsonl")
        with open(events_log) as f:
            lines = f.readlines()
        assert len(lines) == 5


# ---------------------------------------------------------------------------
# Restricted action escalation
# ---------------------------------------------------------------------------

class TestRestrictedActions:
    def test_withdrawal_shadow_mode(self, bridge):
        """In shadow mode, restricted actions still get SHADOW_ALLOW."""
        event = BRPEvent(action="withdrawal", mode=BRPMode.SHADOW.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value
        assert resp.threat_score >= 0.8
        assert "restricted_action" in resp.threat_tags

    def test_withdrawal_enforced_mode(self, bridge):
        """In enforced mode, restricted actions get DENY."""
        event = BRPEvent(action="withdrawal", mode=BRPMode.ENFORCED.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.DENY.value
        assert resp.severity == BRPSeverity.CRITICAL.value

    def test_admin_delete_enforced(self, bridge):
        event = BRPEvent(action="admin_delete", mode=BRPMode.ENFORCED.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.DENY.value

    def test_fund_transfer_advisory(self, bridge):
        """Advisory mode: restricted high-threat => ELEVATE, not DENY."""
        event = BRPEvent(action="fund_transfer", mode=BRPMode.ADVISORY.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.ELEVATE.value

    def test_plan_with_restricted_step_enforced(self, bridge):
        plan = BRPPlan(
            steps=[
                {"action": "trade_buy"},
                {"action": "withdrawal"},
            ],
            mode=BRPMode.ENFORCED.value,
        )
        resp = bridge.evaluate_plan(plan)
        assert resp.threat_score >= 0.8
        assert resp.decision in (BRPDecision.ELEVATE.value, BRPDecision.DENY.value)

    def test_all_restricted_actions_flagged(self, bridge):
        """Every action in RESTRICTED_ACTIONS should produce threat >= 0.8."""
        for action in RESTRICTED_ACTIONS:
            event = BRPEvent(action=action)
            resp = bridge.evaluate_event(event)
            assert resp.threat_score >= 0.8, f"{action} not flagged"
            assert "restricted_action" in resp.threat_tags


# ---------------------------------------------------------------------------
# Shadow allow behaviour
# ---------------------------------------------------------------------------

class TestShadowAllow:
    def test_shadow_mode_always_shadow_allow(self, bridge):
        """Shadow mode must never return DENY regardless of threat."""
        event = BRPEvent(action="withdrawal", mode=BRPMode.SHADOW.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value

    def test_disabled_mode_log_only(self, bridge):
        event = BRPEvent(action="trade_buy", mode=BRPMode.DISABLED.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.LOG_ONLY.value

    def test_default_mode_is_shadow(self):
        bridge = BRPBridge(data_dir=tempfile.mkdtemp())
        assert bridge.default_mode == BRPMode.SHADOW.value


class TestPredictiveSafety:
    def test_predictive_keywords_raise_threat_and_metadata(self, bridge):
        event = BRPEvent(
            source_agent="projectx_native",
            action="run_shell",
            context={
                "projectx_action": "run_shell",
                "details": "autonomous multi-step fuzz payload trying sandbox bypass",
            },
            tags=["projectx", "mesh", "network"],
        )

        resp = bridge.evaluate_event(event)

        assert resp.threat_score >= 0.45
        assert "zero_day_signal" in resp.threat_tags
        assert "autonomous_signal" in resp.threat_tags
        predictive = resp.metadata["predictive_assessment"]
        assert predictive["domains"]
        assert predictive["score_boost"] > 0.0

    def test_negative_observations_create_adaptive_rules(self, bridge, tmp_data_dir):
        for _ in range(2):
            bridge.ingest_observation(
                BRPObservation(
                    source_agent="projectx_native",
                    action="run_shell",
                    outcome="failure",
                    tags=["projectx", "maintenance"],
                )
            )

        event = BRPEvent(
            source_agent="projectx_native",
            action="run_shell",
            context={"projectx_action": "run_shell"},
            tags=["projectx"],
        )
        resp = bridge.evaluate_event(event)

        assert "adaptive_rule_match" in resp.threat_tags
        predictive = resp.metadata["predictive_assessment"]
        assert predictive["near_miss_count"] >= 2
        assert predictive["adaptive_rule_matches"]

        adaptive_rules = os.path.join(tmp_data_dir, "adaptive_rules.json")
        with open(adaptive_rules, "r", encoding="utf-8") as handle:
            persisted = json.load(handle)
        assert "action:run_shell" in persisted
