#!/usr/bin/env python3
"""Test script to enable and test TimesFM integration."""

import os
import asyncio
import sys

# Enable TimesFM with shadow mode for safety
os.environ['SIMP_TIMESFM_ENABLED'] = 'true'
os.environ['SIMP_TIMESFM_SHADOW_MODE'] = 'true'

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simp.integrations.timesfm_service import get_timesfm_service, ForecastRequest
from simp.integrations.timesfm_policy_engine import make_agent_context_for, PolicyEngine


async def test_timesfm_integration():
    """Test TimesFM integration with QuantumArb pattern."""
    print("=== Testing TimesFM Integration ===")
    
    # 1. Test policy engine for quantumarb
    print("\n1. Testing Policy Engine for quantumarb...")
    context = make_agent_context_for(
        agent_id="quantumarb",
        series_id="btc:usd:coinbase_vs_binance:spread_bps",
        series_length=100,
        requesting_handler="handle_trade",
    )
    
    engine = PolicyEngine()
    policy_decision = engine.evaluate(context)
    
    print(f"   Policy decision: approved={policy_decision.approved}")
    print(f"   Reason: {policy_decision.reason}")
    print(f"   Violations: {policy_decision.violations}")
    
    # 2. Test TimesFM service
    print("\n2. Testing TimesFM Service...")
    service = await get_timesfm_service()
    
    print(f"   Service enabled: {service._enabled}")
    print(f"   Service shadow mode: {service._shadow_mode}")
    print(f"   Model loaded: {service._model is not None}")
    
    if service._enabled:
        # Create a simple forecast request
        request = ForecastRequest(
            series_id="test_series",
            values=[0.1, 0.2, 0.15, 0.18, 0.22, 0.19, 0.21, 0.23],
            requesting_agent="quantumarb",
            horizon=5,
        )
        
        try:
            response = await service.forecast(request)
            print(f"   Forecast available: {response.available}")
            print(f"   In shadow mode: {response.shadow_mode}")
            if response.available and not response.shadow_mode:
                print(f"   Point forecast: {response.point_forecast}")
        except Exception as e:
            print(f"   Forecast error: {e}")
    
    # 3. Test QuantumArb data structure integration
    print("\n3. Testing QuantumArb TimesFM data structure...")
    from simp.organs.quantumarb import QuantumArbDecisionSummary
    
    # Create a QuantumArb decision with TimesFM usage
    qa_decision = QuantumArbDecisionSummary(
        timestamp="2024-04-09T12:34:56.789Z",
        intent_id="test-intent-timesfm",
        source_agent="quantumarb",
        asset_pair="BTC-USD",
        side="BULL",
        decision="BUY",
        arb_type="cross_exchange",
        dry_run=True,  # Always dry-run when testing
        confidence=0.85,
        timesfm_used=True,
        timesfm_rationale="Volatility forecast indicates mean reversion likely",
        rationale_preview="Arbitrage with TimesFM forecast",
        venue_a="coinbase",
        venue_b="kraken",
        estimated_spread_bps=18.2,
    )
    
    print(f"   QuantumArb decision created with timesfm_used={qa_decision.timesfm_used}")
    print(f"   TimesFM rationale: {qa_decision.timesfm_rationale}")
    print(f"   Confidence: {qa_decision.confidence}")
    
    # Test the integration contract
    from simp.organs.quantumarb import QuantumArbIntegrationContract
    contract = QuantumArbIntegrationContract()
    agent_decision = contract.map_to_agent_decision_summary(qa_decision)
    
    print(f"   Mapped to agent decision with volatility_posture: {agent_decision.get('volatility_posture', 'N/A')}")
    print(f"   TimesFM used in mapping: {agent_decision.get('timesfm_used', False)}")
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_timesfm_integration())