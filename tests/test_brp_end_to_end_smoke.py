"""
End-to-end smoke tests for BRP integration.

Validates:
1. Mother Goose (broker) -> plan review -> BRP response
2. KashClaw goose -> BRP event -> trade -> BRP observation
3. QuantumArb goose -> BRP shadow observation
4. Restricted action escalation through full stack

NOTE: These tests use the BRP bridge and models directly, without
requiring the full broker infrastructure (SimpConfig, etc.) since the
broker's external dependencies make isolated unit testing impractical.
The broker integration is validated via py_compile and the evaluate_plan
method is tested via the BRP bridge directly.
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
)
from simp.security.brp_bridge import BRPBridge


@pytest.fixture
def brp_dir(tmp_path):
    return str(tmp_path / "brp")


@pytest.fixture
def bridge(brp_dir):
    return BRPBridge(data_dir=brp_dir)


# ---------------------------------------------------------------------------
# Scenario 1: mother_goose_plan_review
# ---------------------------------------------------------------------------

class TestMotherGoosePlanReview:
    def test_plan_review_returns_brp_response(self, bridge):
        """A multi-step plan is evaluated by BRP."""
        plan = BRPPlan(
            source_agent="mother_goose",
            steps=[
                {"action": "trade_buy", "asset_pair": "SOL/USDC", "quantity": 10},
                {"action": "trade_sell", "asset_pair": "SOL/USDC", "quantity": 10},
            ],
        )
        response = bridge.evaluate_plan(plan)
        assert response.decision == BRPDecision.SHADOW_ALLOW.value
        assert response.threat_score < 0.2

    def test_plan_with_restricted_step(self, bridge):
        """Plan containing a restricted action gets elevated threat."""
        plan = BRPPlan(
            source_agent="mother_goose",
            steps=[
                {"action": "trade_buy"},
                {"action": "withdrawal"},
            ],
        )
        response = bridge.evaluate_plan(plan)
        assert response.threat_score >= 0.8
        # shadow mode defaults - still allows
        assert response.decision == BRPDecision.SHADOW_ALLOW.value

    def test_plan_result_persisted(self, bridge, brp_dir):
        """Plan and response are persisted to JSONL."""
        plan = BRPPlan(
            source_agent="mother_goose",
            steps=[{"action": "trade_buy"}],
        )
        bridge.evaluate_plan(plan)

        plans_log = os.path.join(brp_dir, "plans.jsonl")
        assert os.path.exists(plans_log)
        with open(plans_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["source_agent"] == "mother_goose"


# ---------------------------------------------------------------------------
# Scenario 2: kashclaw_trade_shadow_gate
# ---------------------------------------------------------------------------

class TestKashClawTradeShadowGate:
    def test_trade_event_evaluation(self, bridge):
        """A trade event gets evaluated and returns BRP metadata."""
        event = BRPEvent(
            source_agent="kashclaw:agent",
            event_type=BRPEventType.TRADE_EXECUTION.value,
            action="trade_buy",
            params={"asset_pair": "SOL/USDC", "quantity": 10},
            mode=BRPMode.SHADOW.value,
            tags=["kashclaw", "SOL/USDC"],
        )
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value
        assert "threat_score" in resp.to_dict()

    def test_post_trade_observation_persisted(self, bridge, brp_dir):
        """Post-trade observation is persisted."""
        event = BRPEvent(
            source_agent="kashclaw:agent",
            event_type=BRPEventType.TRADE_EXECUTION.value,
            action="trade_buy",
        )
        bridge.evaluate_event(event)

        obs = BRPObservation(
            source_agent="kashclaw:agent",
            event_id=event.event_id,
            action="trade_buy",
            outcome="completed",
            result_data={"total_pnl": 0.5},
            mode=BRPMode.SHADOW.value,
            tags=["kashclaw"],
        )
        bridge.ingest_observation(obs)

        obs_log = os.path.join(brp_dir, "observations.jsonl")
        assert os.path.exists(obs_log)
        with open(obs_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["source_agent"] == "kashclaw:agent"
        assert record["event_id"] == event.event_id


# ---------------------------------------------------------------------------
# Scenario 3: quantumarb_shadow_observation
# ---------------------------------------------------------------------------

class TestQuantumArbShadowObservation:
    def test_arb_shadow_event_and_observation(self, bridge, brp_dir):
        """QuantumArb emits BRP event + observation in shadow mode."""
        event = BRPEvent(
            source_agent="quantumarb",
            event_type=BRPEventType.ARBITRAGE.value,
            action="arb_evaluate",
            params={"ticker": "SOL/USDC", "direction": "BULL"},
            mode=BRPMode.SHADOW.value,
            tags=["quantumarb", "shadow", "SOL/USDC"],
        )
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value

        obs = BRPObservation(
            source_agent="quantumarb",
            event_id=event.event_id,
            action="arb_evaluate",
            outcome="NO_OPPORTUNITY",
            result_data={"spread_bps": 5.2, "dry_run": True},
            mode=BRPMode.SHADOW.value,
            tags=["quantumarb", "shadow"],
        )
        bridge.ingest_observation(obs)

        obs_log = os.path.join(brp_dir, "observations.jsonl")
        with open(obs_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["source_agent"] == "quantumarb"
        assert "shadow" in record["tags"]


# ---------------------------------------------------------------------------
# Scenario 4: restricted_action_escalation
# ---------------------------------------------------------------------------

class TestRestrictedActionEscalation:
    def test_enforced_withdrawal_denied(self, bridge):
        """Enforced mode: withdrawal is DENY."""
        event = BRPEvent(action="withdrawal", mode=BRPMode.ENFORCED.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.DENY.value

    def test_shadow_withdrawal_shadow_allow(self, bridge):
        """Shadow mode: restricted action still gets SHADOW_ALLOW."""
        event = BRPEvent(action="withdrawal", mode=BRPMode.SHADOW.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.SHADOW_ALLOW.value
        assert resp.threat_score >= 0.8

    def test_advisory_elevates_high_threat(self, bridge):
        """Advisory mode: restricted action gets ELEVATE."""
        event = BRPEvent(action="fund_transfer", mode=BRPMode.ADVISORY.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.ELEVATE.value


# ---------------------------------------------------------------------------
# Feature flag checks
# ---------------------------------------------------------------------------

class TestFeatureFlags:
    def test_default_mode_is_shadow(self):
        """BRP defaults to shadow mode."""
        bridge = BRPBridge(data_dir=tempfile.mkdtemp())
        assert bridge.default_mode == BRPMode.SHADOW.value

    def test_disabled_mode_log_only(self, bridge):
        """Disabled mode returns LOG_ONLY."""
        event = BRPEvent(action="trade_buy", mode=BRPMode.DISABLED.value)
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.LOG_ONLY.value

    def test_advisory_enriches_without_blocking(self, bridge):
        """Advisory mode never blocks normal actions."""
        event = BRPEvent(
            action="trade_buy",
            params={"quantity": 5},
            mode=BRPMode.ADVISORY.value,
        )
        resp = bridge.evaluate_event(event)
        assert resp.decision == BRPDecision.ALLOW.value
