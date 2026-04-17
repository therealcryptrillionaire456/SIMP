#!/usr/bin/env python3
"""
Test capability advertisement flow.
"""

import time
import logging
from simp.mesh.intent_router import IntentMeshRouter, get_intent_router
from simp.mesh.enhanced_bus import get_enhanced_mesh_bus

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_capability_advertisements():
    """Test that capability advertisements are properly received."""
    print("Testing Capability Advertisement Flow")
    print("=" * 60)
    
    # Create shared mesh bus
    bus = get_enhanced_mesh_bus()
    
    # Create two agents
    print("\n1. Creating agents...")
    agent1 = get_intent_router("quantumarb", bus)
    agent2 = get_intent_router("kashclaw", bus)
    
    # Set capabilities
    agent1.set_capabilities(["risk_assessment", "arb_signals"], channel_capacity=500.0)
    agent2.set_capabilities(["trade_execution", "portfolio_management"], channel_capacity=1000.0)
    
    # Start agents
    print("\n2. Starting agents...")
    agent1.start()
    agent2.start()
    
    # Give time for advertisements
    print("\n3. Waiting for advertisements to propagate...")
    time.sleep(5)  # Give time for advertisements
    
    # Check capability tables
    print("\n4. Checking capability tables...")
    table1 = agent1.get_capability_table()
    table2 = agent2.get_capability_table()
    
    print(f"QuantumArb capability table:")
    for capability, ads in table1.items():
        print(f"  {capability}: {len(ads)} advertisements")
        for ad in ads:
            print(f"    - {ad['agent_id']} (capacity: {ad['channel_capacity']})")
    
    print(f"\nKashClaw capability table:")
    for capability, ads in table2.items():
        print(f"  {capability}: {len(ads)} advertisements")
        for ad in ads:
            print(f"    - {ad['agent_id']} (capacity: {ad['channel_capacity']})")
    
    # Test intent routing based on capabilities
    print("\n5. Testing capability-based routing...")
    
    # QuantumArb should find KashClaw for trade_execution
    trade_agent = agent1._find_agent_for_capability("trade_execution")
    print(f"  QuantumArb finds agent for 'trade_execution': {trade_agent}")
    
    # KashClaw should find QuantumArb for risk_assessment
    risk_agent = agent2._find_agent_for_capability("risk_assessment")
    print(f"  KashClaw finds agent for 'risk_assessment': {risk_agent}")
    
    # Test non-existent capability
    nonexistent = agent1._find_agent_for_capability("nonexistent_capability")
    print(f"  Agent for 'nonexistent_capability': {nonexistent}")
    
    # Stop agents
    print("\n6. Stopping agents...")
    agent1.stop()
    agent2.stop()
    
    print("\n" + "=" * 60)
    
    # Check results
    success = True
    
    if not table1:
        print("✗ QuantumArb didn't receive any capability advertisements")
        success = False
    else:
        print("✓ QuantumArb received capability advertisements")
    
    if not table2:
        print("✗ KashClaw didn't receive any capability advertisements")
        success = False
    else:
        print("✓ KashClaw received capability advertisements")
    
    if trade_agent != "kashclaw":
        print(f"✗ QuantumArb should find KashClaw for trade_execution, found: {trade_agent}")
        success = False
    else:
        print("✓ QuantumArb correctly found KashClaw for trade_execution")
    
    if risk_agent != "quantumarb":
        print(f"✗ KashClaw should find QuantumArb for risk_assessment, found: {risk_agent}")
        success = False
    else:
        print("✓ KashClaw correctly found QuantumArb for risk_assessment")
    
    if nonexistent is not None:
        print(f"✗ Should return None for nonexistent capability, got: {nonexistent}")
        success = False
    else:
        print("✓ Correctly returned None for nonexistent capability")
    
    print("\n" + "=" * 60)
    if success:
        print("✓ ALL TESTS PASSED - Capability advertisement system works!")
    else:
        print("✗ SOME TESTS FAILED")
    
    return success

if __name__ == "__main__":
    test_capability_advertisements()