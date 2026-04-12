#!/usr/bin/env python3
"""
Script to register kashclaw_gemma agent with SIMP broker using enhanced registration system.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simp.agent_registration import AgentRegistrar

def main():
    """Register kashclaw_gemma agent with verification."""
    
    # Create registrar instance
    registrar = AgentRegistrar(broker_url="http://localhost:5555")
    
    print("=== Kashclaw Gemma Agent Registration ===")
    print(f"Broker URL: http://localhost:5555")
    print(f"Agent endpoint: http://localhost:8780")
    print()
    
    # Step 1: Verify agent
    print("1. Verifying agent health...")
    verification = registrar.verify_agent(
        agent_id="kashclaw_gemma",
        endpoint="http://localhost:8780",
        timeout=10
    )
    
    print(f"   Reachable: {verification.reachable}")
    print(f"   Response time: {verification.response_time_ms:.1f} ms")
    print(f"   Health status: {verification.health_status.get('status', 'unknown') if verification.health_status else 'N/A'}")
    print(f"   Capabilities: {verification.capabilities}")
    
    if verification.errors:
        print(f"   Errors: {verification.errors}")
    
    if not verification.passed:
        print("❌ Agent verification failed!")
        return 1
    
    print("✅ Agent verification passed!")
    print()
    
    # Step 2: Register agent using specialized method
    print("2. Registering agent with broker...")
    result = registrar.register_kashclaw_gemma(port=8780, verify=False)  # Already verified
    
    if result.get("success"):
        print("✅ Agent registration successful!")
        print(f"   Agent ID: {result.get('agent_id')}")
        print(f"   Endpoint: {result.get('endpoint')}")
        print(f"   Capabilities: {result.get('capabilities')}")
    else:
        print(f"❌ Agent registration failed: {result.get('error')}")
        return 1
    
    print()
    
    # Step 3: List all registered agents
    print("3. Listing all registered agents...")
    agents_result = registrar.list_agents()
    
    if agents_result.get("success"):
        agents = agents_result.get("agents", [])
        print(f"   Total agents registered: {len(agents)}")
        for agent in agents:
            if agent.get("agent_id") == "kashclaw_gemma":
                print(f"   ✓ kashclaw_gemma: {agent.get('endpoint')} - {agent.get('capabilities')}")
            else:
                print(f"   • {agent.get('agent_id')}: {agent.get('endpoint')}")
    else:
        print(f"   Failed to list agents: {agents_result.get('error')}")
    
    print()
    print("=== Registration Complete ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())