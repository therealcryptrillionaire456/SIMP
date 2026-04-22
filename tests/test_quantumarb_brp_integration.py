import json
from unittest.mock import patch

import pytest

from simp.agents.quantumarb_agent import _emit_brp_shadow_observation
from simp.organs.quantumarb.brp_integration import (
    QuantumArbBRPIntegrator,
    TradeAction,
    TradeContext,
)
from simp.security.brp_models import BRPDecision, BRPMode, BRPResponse


class _StubBridge:
    def __init__(self, response):
        self.response = response
        self.events = []
        self.observations = []

    def evaluate_event(self, event):
        self.events.append(event)
        return self.response

    def ingest_observation(self, observation):
        self.observations.append(observation)


def test_quantumarb_integrator_treats_deny_as_block():
    integrator = QuantumArbBRPIntegrator(mode=BRPMode.ENFORCED)
    integrator._bridge = _StubBridge(
        BRPResponse(
            decision=BRPDecision.DENY.value,
            severity="critical",
            summary="blocked",
        )
    )

    allowed, response = integrator.evaluate_trade_action(
        TradeContext(
            market="SOL/USDC",
            action=TradeAction.TRADE_EXECUTE,
            quantity=1.0,
            price=100.0,
            side="buy",
        )
    )

    assert allowed is False
    assert response.decision == BRPDecision.DENY.value
    assert integrator.stats["blocks"] == 1
    assert len(integrator.bridge.observations) == 1


def test_quantumarb_integrator_treats_elevate_as_warning():
    integrator = QuantumArbBRPIntegrator(mode=BRPMode.ADVISORY)
    integrator._bridge = _StubBridge(
        BRPResponse(
            decision=BRPDecision.ELEVATE.value,
            severity="high",
            summary="manual review required",
        )
    )

    allowed, response = integrator.evaluate_trade_action(
        TradeContext(
            market="BTC/USDC",
            action=TradeAction.ARB_EVALUATE,
            spread_bps=12.5,
            side="long",
        )
    )

    assert allowed is True
    assert response.decision == BRPDecision.ELEVATE.value
    assert integrator.stats["warnings"] == 1
    assert len(integrator.bridge.observations) == 1


def test_quantumarb_integrator_reuses_last_event_id_for_outcomes(tmp_path):
    integrator = QuantumArbBRPIntegrator(mode=BRPMode.ADVISORY)
    integrator._log_dir = tmp_path / "brp"
    integrator._log_dir.mkdir(parents=True, exist_ok=True)
    integrator._bridge = _StubBridge(
        BRPResponse(
            decision=BRPDecision.ALLOW.value,
            severity="info",
            summary="allowed",
        )
    )

    allowed, response = integrator.evaluate_trade_action(
        TradeContext(
            market="ETH/USDC",
            action=TradeAction.TRADE_EXECUTE,
            quantity=2.0,
            price=2500.0,
            side="buy",
        )
    )

    assert allowed is True
    event_id = integrator.bridge.events[0].event_id
    assert response.event_id == event_id
    assert "integrator_runtime" in response.metadata

    integrator.record_trade_outcome(
        market="ETH/USDC",
        action=TradeAction.TRADE_EXECUTE,
        success=True,
        outcome_data={"filled_qty": 2.0},
    )

    assert integrator.bridge.observations[-1].event_id == event_id
    records = (integrator._log_dir / "trade_outcomes.jsonl").read_text().splitlines()
    assert json.loads(records[-1])["event_id"] == event_id


def test_quantumarb_shadow_observation_reuses_supplied_event_id():
    bridge = _StubBridge(
        BRPResponse(
            decision=BRPDecision.SHADOW_ALLOW.value,
            severity="info",
            summary="shadow ok",
        )
    )

    with patch("simp.agents.quantumarb_agent._get_brp_bridge", return_value=bridge):
        _emit_brp_shadow_observation(
            action="arb_evaluate",
            outcome="dry_run",
            result_data={"ticker": "SOL/USDC"},
            event_id="evt-123",
            tags=["quantumarb", "shadow"],
        )

    assert bridge.events == []
    assert bridge.observations[0].event_id == "evt-123"
