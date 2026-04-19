#!/usr/bin/env python3
"""
Test production quantum agent.
"""

import os
import sys
import time

# Set token
os.environ['IBM_QUANTUM_TOKEN'] = 'J8_u7OEompECV6_7iZrqKHMk4wtetxvbESILLCJNPlya'
# Force simulator mode for testing
os.environ['SIMP_USE_REAL_HARDWARE'] = '0'

print("=" * 60)
print("PRODUCTION QUANTUM AGENT TEST")
print("=" * 60)

try:
    # Import production agent
    from simp.organs.quantum_intelligence.production_agent import ProductionQuantumAgent
    
    print("✅ ProductionQuantumAgent imported")
    
    # Create agent
    agent = ProductionQuantumAgent(
        agent_id="test_production_quantum",
        initial_level="quantum_aware",
        enable_monitoring=False  # Disable monitoring for faster test
    )
    
    print("✅ Agent created")
    
    # Run a simple test
    print("\n🧪 Running production quantum test (simulator only)...")
    start_time = time.time()
    
    result = agent.solve_quantum_problem_with_rollout(
        problem_description="Test portfolio optimization",
        problem_type="optimization",
        qubits=2,
        request_id="production_test_001",
        metadata={"use_real_hardware": False}
    )
    
    elapsed = time.time() - start_time
    
    print(f"✅ Test completed in {elapsed:.2f} seconds")
    print(f"Status: {result.get('status', 'unknown')}")
    print(f"Backend: {result.get('backend_id', 'unknown')}")
    
    if "quantum_advantage" in result:
        print(f"Quantum advantage: {result['quantum_advantage']}")
    
    print("\n🎉 PRODUCTION QUANTUM TEST PASSED!")
    
except Exception as e:
    import traceback
    print(f"\n❌ Test failed: {e}")
    print("\nTraceback:")
    print(traceback.format_exc())
    
print("\n" + "=" * 60)