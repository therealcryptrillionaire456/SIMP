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
