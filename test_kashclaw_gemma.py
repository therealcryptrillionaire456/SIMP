#!/usr/bin/env python3
"""
Test communication with kashclaw_gemma agent via SIMP broker.
"""
import json
import requests
import sys

def test_ping_intent():
    """Test ping intent routing to kashclaw_gemma."""
    print("=== Testing Ping Intent ===")
    
    payload = {
        "source_agent": "integration_goose",
        "target_agent": "kashclaw_gemma",
        "intent_type": "ping",
        "params": {
            "message": "Hello from Integration Goose!",
            "timestamp": "2026-04-12T04:32:00Z"
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:5555/intents/route",
            json=payload,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result.get('success')}")
            print(f"Intent ID: {result.get('intent_id')}")
            print(f"Delivery Status: {result.get('delivery_status')}")
            
            # Check if we got a response from the agent
            if result.get("response"):
                print(f"Agent Response: {json.dumps(result['response'], indent=2)}")
            else:
                print("No response from agent yet (may be async)")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")
    
    print()

def test_capability_query():
    """Test capability query intent."""
    print("=== Testing Capability Query ===")
    
    payload = {
        "source_agent": "integration_goose",
        "target_agent": "kashclaw_gemma",
        "intent_type": "capability_query",
        "params": {
            "query": "What capabilities do you provide?",
            "detail_level": "full"
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:5555/intents/route",
            json=payload,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result.get('success')}")
            
            if result.get("response"):
                print(f"Agent Response: {json.dumps(result['response'], indent=2)}")
            else:
                print("No response from agent yet")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")
    
    print()

def test_research_intent():
    """Test research intent (main capability)."""
    print("=== Testing Research Intent ===")
    
    payload = {
        "source_agent": "integration_goose",
        "target_agent": "kashclaw_gemma",
        "intent_type": "research",
        "params": {
            "topic": "SIMP Agent Registration",
            "prompt": "Explain the enhanced agent registration system in SIMP and how it verifies agents before registration.",
            "max_tokens": 500
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:5555/intents/route",
            json=payload,
            timeout=30  # Longer timeout for research
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result.get('success')}")
            print(f"Intent ID: {result.get('intent_id')}")
            print(f"Delivery Status: {result.get('delivery_status')}")
            
            if result.get("response"):
                resp_data = result["response"]
                print(f"Research completed: {resp_data.get('completed', False)}")
                if resp_data.get("result"):
                    print(f"Result summary: {resp_data['result'][:200]}...")
                else:
                    print(f"Response: {json.dumps(resp_data, indent=2)}")
            else:
                print("No response from agent yet (may be async)")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")
    
    print()

def main():
    """Run all tests."""
    print("Testing kashclaw_gemma agent communication via SIMP broker")
    print("=" * 60)
    print()
    
    # Test 1: Ping
    test_ping_intent()
    
    # Test 2: Capability query
    test_capability_query()
    
    # Test 3: Research (main capability)
    test_research_intent()
    
    print("=" * 60)
    print("Tests completed!")

if __name__ == "__main__":
    main()