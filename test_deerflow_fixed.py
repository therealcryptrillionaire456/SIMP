#!/usr/bin/env python3
"""
Test the fixed DeerFlow agent.
"""

import json
import requests
import sys
import time

def test_deerflow_agent():
    """Test the fixed DeerFlow agent."""
    deerflow_url = "http://127.0.0.1:8888"
    
    print("Testing fixed DeerFlow agent...")
    print("=" * 60)
    
    # 1. Health check
    print("1. Health check...")
    try:
        response = requests.get(f"{deerflow_url}/health")
        if response.status_code == 200:
            print(f"   ✅ Healthy: {response.json()}")
        else:
            print(f"   ❌ Unhealthy: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 2. Capabilities
    print("\n2. Capabilities...")
    try:
        response = requests.get(f"{deerflow_url}/capabilities")
        if response.status_code == 200:
            caps = response.json()
            print(f"   ✅ Capabilities: {caps.get('capabilities', [])}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Test deerflow_spawn intent
    print("\n3. Testing deerflow_spawn intent...")
    try:
        spawn_data = {
            "intent_type": "deerflow_spawn",
            "source_agent": "test_runner",
            "target_agent": "deerflow",
            "params": {
                "task": "Analyze current market conditions and generate trading signal",
                "skill_id": "trading_analysis"
            }
        }
        
        response = requests.post(f"{deerflow_url}/intent", json=spawn_data)
        result = response.json()
        
        print(f"   Status: {response.status_code}")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Message: {result.get('message', 'No message')}")
        
        if result.get('success'):
            print(f"   ✅ Spawn successful!")
            subagent_id = result.get('data', {}).get('subagent_id')
            print(f"   Subagent ID: {subagent_id}")
            
            # 4. Test deerflow_status intent
            print("\n4. Testing deerflow_status intent...")
            status_data = {
                "intent_type": "deerflow_status",
                "source_agent": "test_runner",
                "target_agent": "deerflow",
                "params": {
                    "agent_id": subagent_id
                }
            }
            
            response = requests.post(f"{deerflow_url}/intent", json=status_data)
            result = response.json()
            
            print(f"   Status: {response.status_code}")
            print(f"   Success: {result.get('success', False)}")
            print(f"   Message: {result.get('message', 'No message')}")
            
            if result.get('success'):
                print(f"   ✅ Status check successful!")
            else:
                print(f"   ❌ Status check failed")
        
        else:
            print(f"   ❌ Spawn failed: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Test health_check intent
    print("\n5. Testing health_check intent...")
    try:
        health_data = {
            "intent_type": "health_check",
            "source_agent": "test_runner",
            "target_agent": "deerflow"
        }
        
        response = requests.post(f"{deerflow_url}/intent", json=health_data)
        result = response.json()
        
        print(f"   Status: {response.status_code}")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Message: {result.get('message', 'No message')}")
        
        if result.get('success'):
            print(f"   ✅ Health check intent successful!")
        else:
            print(f"   ❌ Health check intent failed")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    return True

if __name__ == '__main__':
    # First check if DeerFlow agent is running
    try:
        response = requests.get("http://127.0.0.1:8888/health", timeout=5)
        if response.status_code == 200:
            print("DeerFlow agent is running. Starting tests...")
            test_deerflow_agent()
        else:
            print(f"DeerFlow agent not healthy: {response.status_code}")
            print("Please start the DeerFlow agent first.")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("DeerFlow agent is not running on port 8888.")
        print("Please start the DeerFlow agent first.")
        sys.exit(1)
    except Exception as e:
        print(f"Error checking DeerFlow agent: {e}")
        sys.exit(1)