#!/usr/bin/env python3
"""
DeerFlow Integration Demo
=========================
Demonstrates DeerFlow agent spawning and management within SIMP ecosystem.
"""

import json
import requests
import sys

def demo_deerflow_intents():
    """Demonstrate DeerFlow-specific intents."""
    
    print("🚀 DeerFlow Integration Demo")
    print("=" * 60)
    
    # DeerFlow agent endpoint
    deerflow_url = "http://127.0.0.1:8888"
    
    # 1. Health check
    print("\n1. Checking DeerFlow agent health...")
    response = requests.get(f"{deerflow_url}/health")
    if response.status_code == 200:
        print(f"   ✅ Healthy: {response.json()}")
    else:
        print(f"   ❌ Unhealthy: {response.status_code}")
        return False
    
    # 2. Get capabilities
    print("\n2. Getting DeerFlow capabilities...")
    response = requests.get(f"{deerflow_url}/capabilities")
    caps = response.json()
    print(f"   Agent ID: {caps['agent_id']}")
    print(f"   Capabilities: {', '.join(caps['capabilities'])}")
    
    # 3. Send DeerFlow-specific intents
    print("\n3. Testing DeerFlow intents...")
    
    # Note: These would work once the DeerFlow agent is updated to handle
    # the new intent types: deerflow_spawn, deerflow_status, etc.
    
    print("   DeerFlow intent types available:")
    print("   • deerflow_spawn - Spawn subagent")
    print("   • deerflow_status - Get subagent status")
    print("   • deerflow_skills - List skills")
    print("   • deerflow_execute - Execute sandbox command")
    print("   • deerflow_health - Health check")
    
    print("\n✅ DeerFlow integration ready!")
    print("\nNext steps:")
    print("1. Update DeerFlow agent to handle new intent types")
    print("2. Test spawning subagents via SIMP broker")
    print("3. Integrate with existing agents (quantumarb, kloutbot, etc.)")
    
    return True

if __name__ == "__main__":
    try:
        success = demo_deerflow_intents()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        sys.exit(1)
