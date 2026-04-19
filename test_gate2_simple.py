#!/usr/bin/env python3.10
"""Simple test of Gate 2 agent."""

import sys
sys.path.insert(0, '.')

try:
    # Test basic imports
    from simp.agents.quantumarb_gate2_sol import QuantumArbGate2Agent, Gate2Config
    print("✅ Gate 2 agent imports successful")
    
    # Test class definitions
    from simp.agents.quantumarb_gate2_sol import ArbDecision, ArbitrageSignal, ArbitrageOpportunity
    print("✅ Arb classes defined")
    
    # Create test signal
    import json
    from datetime import datetime
    
    test_signal = ArbitrageSignal(
        signal_id="test_123",
        arb_type="cross_venue",
        symbol_a="SOL-USD",
        symbol_b="SOL-USD",
        venue_a="coinbase",
        venue_b="coinbase",
        spread_pct=0.15,
        expected_return_pct=0.12,
        confidence=0.85,
        timestamp=datetime.now().isoformat(),
        metadata={"test": True}
    )
    
    print(f"✅ Test signal created: {test_signal.symbol_a}, spread: {test_signal.spread_pct}%")
    
    # Create test opportunity
    test_opportunity = ArbitrageOpportunity(
        signal=test_signal,
        decision=ArbDecision.EXECUTE,
        decision_reason="Test approval",
        position_size_usd=0.05,
        expected_pnl_usd=0.00006,
        risk_score=0.65
    )
    
    print(f"✅ Test opportunity created: {test_opportunity.decision.value}")
    
    print("\n✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()