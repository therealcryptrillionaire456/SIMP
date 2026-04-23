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
        assert "quantum_defense_assessment" in resp.metadata

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
        persisted = BRPBridge.read_operator_adaptive_rules(data_dir=tmp_data_dir, limit=20)
        assert any(rule["key"] == "action:run_shell" for rule in persisted)

    def test_multimodal_event_analysis_enriches_bridge_metadata(self, bridge):
        event = BRPEvent(
            source_agent="projectx_native",
            action="run_shell",
            params={"code": "eval(user_input)"},
            context={
                "projectx_action": "run_shell",
                "description": "transfer funds without approval",
                "pattern": "rapid_file_access_sequence",
                "risk_level": "high",
                "network_flow": {
                    "source": "192.168.1.10",
                    "destination": "10.0.0.2",
                    "protocol": "HTTP",
                    "bytes": 1500000,
                    "suspicious": False,
                },
                "memory_id": "MEM-001",
                "content": "sensitive financial data",
                "access_agent": "projectx_native",
                "correlation_score": 0.96,
            },
            tags=["projectx", "network"],
        )

        resp = bridge.evaluate_event(event)

        multimodal = resp.metadata["multimodal_assessment"]
        assert multimodal["summary"]["total_detections"] >= 4
        assert "multimodal_text_threat" in resp.threat_tags
        assert "multimodal_code_risk" in resp.threat_tags
        assert "multimodal_behavior_risk" in resp.threat_tags
        assert "multimodal_network_risk" in resp.threat_tags
        assert "multimodal_memory_risk" in resp.threat_tags
        assert multimodal["score_boost"] > 0.0

    def test_multimodal_plan_analysis_marks_risky_steps(self, bridge):
        plan = BRPPlan(
            source_agent="mother_goose",
            mode=BRPMode.ADVISORY.value,
            context={"description": "transfer funds without approval"},
            tags=["projectx"],
            steps=[
                {"action": "review"},
                {"action": "run_shell", "code": "os.system('rm -rf /')"},
            ],
        )

        resp = bridge.evaluate_plan(plan)

        multimodal_steps = resp.metadata["multimodal_steps"]
        assert any(step["summary"]["total_detections"] > 0 for step in multimodal_steps)
        assert "multimodal_code_risk" in resp.threat_tags


class TestOperatorReadHelpers:
    def test_operator_status_and_evaluations(self, bridge, tmp_data_dir):
        event = BRPEvent(
            source_agent="projectx_native",
            action="run_shell",
            context={"projectx_action": "run_shell", "details": "autonomous fuzz bypass"},
            tags=["projectx", "network"],
        )
        plan = BRPPlan(
            source_agent="mother_goose",
            mode=BRPMode.ADVISORY.value,
            steps=[{"action": "withdrawal"}],
        )
        bridge.evaluate_event(event)
        bridge.evaluate_plan(plan)
        bridge.ingest_observation(
            BRPObservation(
                source_agent="projectx_native",
                action="run_shell",
                event_id=event.event_id,
                outcome="failure",
            )
        )

        status = BRPBridge.read_operator_status(data_dir=tmp_data_dir, recent_limit=10)
        evaluations = BRPBridge.read_operator_evaluations(data_dir=tmp_data_dir, limit=10)
        rules = BRPBridge.read_operator_adaptive_rules(data_dir=tmp_data_dir, limit=10)

        assert status["status"] == "success"
        assert status["counts"]["responses"] == 2
        assert status["counts"]["observations"] == 1
        assert status["recent"]["decision_counts"]
        assert "quantum_defense" in status
        assert evaluations[0]["record_type"] in {"event", "plan"}
        assert any(item["event_id"] == event.event_id for item in evaluations)
        assert isinstance(rules, list)

    def test_operator_evaluation_filters_and_detail(self, bridge, tmp_data_dir):
        event = BRPEvent(
            source_agent="projectx_native",
            action="run_shell",
            context={"projectx_action": "run_shell", "details": "autonomous fuzz bypass"},
            tags=["projectx", "network"],
        )
        response = bridge.evaluate_event(event)
        bridge.ingest_observation(
            BRPObservation(
                source_agent="projectx_native",
                action="run_shell",
                event_id=event.event_id,
                outcome="failure",
            )
        )

        filtered = BRPBridge.read_operator_evaluations(
            data_dir=tmp_data_dir,
            limit=10,
            decision=response.decision,
            query="projectx_native",
        )
        detail = BRPBridge.read_operator_evaluation_detail(
            event_id=event.event_id,
            data_dir=tmp_data_dir,
        )

        assert len(filtered) == 1
        assert filtered[0]["event_id"] == event.event_id
        assert detail is not None
        assert detail["evaluation"]["event_id"] == event.event_id
        assert len(detail["related_observations"]) == 1
        assert detail["evaluation"]["controller_rounds"] >= 0
        assert detail["alert"] is not None
        assert detail["incident"] is not None
        assert "history" in detail["incident"]
        assert detail["playbook"] is not None

    def test_operator_incidents_playbooks_and_acknowledgements(self, bridge, tmp_data_dir):
        event = BRPEvent(
            source_agent="projectx_native",
            action="withdrawal",
            mode=BRPMode.ADVISORY.value,
        )
        bridge.evaluate_event(event)

        incidents = BRPBridge.read_operator_incidents(data_dir=tmp_data_dir, limit=10)
        assert incidents["count"] >= 1
        assert incidents["open_alerts"] >= 1
        assert incidents["state_counts"]["open"] >= 1
        assert incidents["incidents"][0]["incident_state"] == "open"

        playbooks = BRPBridge.read_operator_playbooks(data_dir=tmp_data_dir, limit=10)
        assert playbooks
        assert playbooks[0]["alert_id"].startswith("brp-alert::")
        assert playbooks[0]["actions"]
        assert playbooks[0]["automation"]["job"]
        assert playbooks[0]["evidence"]["incident_state"] in {"open", "acknowledged", "reopened", "remediated"}
        assert playbooks[0]["guardrails"]

        alert_id = incidents["alerts"][0]["alert_id"]
        acknowledged = BRPBridge.acknowledge_operator_alert(
            alert_id,
            actor="test_operator",
            note="triaged",
            data_dir=tmp_data_dir,
        )
        assert acknowledged is not None
        assert acknowledged["acknowledged"] is True
        assert acknowledged["acknowledged_by"] == "test_operator"
        assert acknowledged["incident_state"] == "acknowledged"

        refreshed = BRPBridge.read_operator_incidents(data_dir=tmp_data_dir, limit=10)
        assert refreshed["acknowledged_alerts"] >= 1
        assert refreshed["incidents"][0]["history"]

    def test_operator_incident_counts_use_canonical_state_not_page_limit(self, bridge, tmp_data_dir):
        for idx in range(3):
            bridge.evaluate_event(
                BRPEvent(
                    source_agent=f"agent_{idx}",
                    action="withdrawal",
                    mode=BRPMode.ADVISORY.value,
                )
            )

        incidents = BRPBridge.read_operator_incidents(data_dir=tmp_data_dir, limit=1)

        assert incidents["count"] == 3
        assert incidents["open_alerts"] == 3
        assert len(incidents["alerts"]) == 1
        assert len(incidents["incidents"]) == 1

    def test_operator_remediations_are_persisted_and_linked(self, bridge, tmp_data_dir):
        event = BRPEvent(
            source_agent="projectx_native",
            action="run_shell",
            context={"projectx_action": "run_shell", "details": "autonomous fuzz bypass"},
            tags=["projectx", "network"],
        )
        bridge.evaluate_event(event)

        playbook = BRPBridge.read_operator_playbooks(data_dir=tmp_data_dir, limit=10)[0]
        remediation = BRPBridge.record_operator_remediation(
            alert_id=playbook["alert_id"],
            playbook_id=playbook["playbook_id"],
            actor="test_operator",
            job=playbook["automation"]["job"],
            result={
                "status": "success",
                "routing_mode": "broker",
                "broker_intent_id": "intent-123",
                "delivery_status": "delivered",
                "response": {"status": "ok"},
            },
            data_dir=tmp_data_dir,
        )

        assert remediation is not None
        assert remediation["status"] == "completed"
        assert remediation["incident_state"] == "remediated"
        remediations = BRPBridge.read_operator_remediations(data_dir=tmp_data_dir, limit=10)
        assert remediations
        assert remediations[0]["playbook_id"] == playbook["playbook_id"]

        detail = BRPBridge.read_operator_evaluation_detail(event_id=event.event_id, data_dir=tmp_data_dir)
        assert detail is not None
        assert detail["remediations"]
        assert detail["playbook"]["last_remediation"]["status"] == "completed"
        assert detail["incident"]["incident_state"] == "remediated"

    def test_failed_remediation_feeds_back_into_predictive_learning(self, bridge, tmp_data_dir):
        event = BRPEvent(
            source_agent="projectx_native",
            action="run_shell",
            context={"projectx_action": "run_shell", "details": "autonomous fuzz bypass"},
            tags=["projectx", "network"],
        )
        bridge.evaluate_event(event)

        playbook = BRPBridge.read_operator_playbooks(data_dir=tmp_data_dir, limit=10)[0]
        remediation = BRPBridge.record_operator_remediation(
            alert_id=playbook["alert_id"],
            playbook_id=playbook["playbook_id"],
            actor="test_operator",
            job=playbook["automation"]["job"],
            result={
                "status": "error",
                "routing_mode": "broker",
                "broker_intent_id": "intent-456",
                "delivery_status": "delivered",
                "response": {"status": "error"},
            },
            data_dir=tmp_data_dir,
        )

        assert remediation is not None
        assert remediation["incident_state"] == "reopened"
        observations_path = os.path.join(tmp_data_dir, "observations.jsonl")
        with open(observations_path, "r", encoding="utf-8") as handle:
            observations = [json.loads(line) for line in handle if line.strip()]
        assert observations[-1]["event_id"] == event.event_id
        assert observations[-1]["outcome"] == "error"
        assert "remediation_feedback" in observations[-1]["tags"]

        refreshed_bridge = BRPBridge(data_dir=tmp_data_dir)
        follow_up = refreshed_bridge.evaluate_event(
            BRPEvent(
                source_agent="projectx_native",
                action="run_shell",
                context={"projectx_action": "run_shell"},
                tags=["projectx"],
            )
        )

        predictive = follow_up.metadata["predictive_assessment"]
        assert "adaptive_rule_match" in follow_up.threat_tags
        assert predictive["near_miss_count"] >= 1
        assert predictive["adaptive_rule_matches"]
        incidents = BRPBridge.read_operator_incidents(data_dir=tmp_data_dir, limit=10)
        assert incidents["state_counts"]["reopened"] >= 1

    def test_operator_report_includes_incident_state(self, bridge, tmp_data_dir):
        bridge.evaluate_event(
            BRPEvent(
                source_agent="mother_goose",
                action="withdrawal",
                mode=BRPMode.ADVISORY.value,
            )
        )

        report = BRPBridge.read_operator_report(data_dir=tmp_data_dir, limit=10)

        assert report["status"] == "success"
        assert "incidents" in report
        assert "playbooks" in report
        assert "remediations" in report
        assert report["incidents"]["count"] >= 1
        assert report["playbooks"]
        assert "runtime_context" in report
        assert "runtime_cache" in report["runtime_context"]
        assert "quantum_defense" in report["runtime_context"]
