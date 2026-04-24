#!/usr/bin/env python3
"""
Force QIP mesh registration by directly accessing the broker's mesh bus.
This works by attaching to the running broker process.
"""
import sys
import os
import time

sys.path.insert(0, os.getcwd())

print("=== FORCING QIP MESH REGISTRATION ===")

# Try to get the broker instance
try:
    # First, let's see if we can import the running broker
    import requests
    import json
    
    broker_url = "http://127.0.0.1:5555"
    agent_id = "quantum_intelligence_prime"
    
    print(f"\n1. Checking current state via API...")
    
    # Get broker health
    resp = requests.get(f"{broker_url}/health")
    if resp.status_code == 200:
        print(f"   ✓ Broker is healthy")
    else:
        print(f"   ✗ Broker health check failed: {resp.status_code}")
    
    # Get agents
    resp = requests.get(f"{broker_url}/agents")
    agents = resp.json().get('agents', {})
    if agent_id in agents:
        print(f"   ✓ {agent_id} is registered with broker")
    else:
        print(f"   ✗ {agent_id} is NOT registered with broker")
    
    print(f"\n2. Attempting to trigger mesh registration...")
    
    # Method 1: Re-register agent (might trigger mesh registration)
    print("   Method 1: Re-registering agent...")
    
    # Get agent data
    agent_data = agents.get(agent_id, {})
    metadata = agent_data.get('metadata', {})
    
    # Try to re-register
    resp = requests.post(f"{broker_url}/agents/register", json={
        "agent_id": agent_id,
        "agent_type": agent_data.get('agent_type', 'quantum'),
        "endpoint": agent_data.get('endpoint', ''),
        "metadata": metadata
    })
    
    if resp.status_code == 200:
        print(f"   ✓ Re-registration successful")
        result = resp.json()
        print(f"   Result: {result.get('message', 'unknown')}")
    else:
        print(f"   ✗ Re-registration failed: {resp.status_code}")
        print(f"   Error: {resp.text}")
    
    print(f"\n3. Testing mesh subscription after re-registration...")
    time.sleep(1)  # Give it a moment
    
    for channel in ["quantum", "intent_requests"]:
        resp = requests.post(f"{broker_url}/mesh/subscribe", json={
            "agent_id": agent_id,
            "channel": channel
        })
        
        if resp.status_code == 200:
            print(f"   ✓ Subscribed to {channel}")
        else:
            print(f"   ✗ Failed to subscribe to {channel}: {resp.status_code}")
            print(f"   Error: {resp.text}")
    
    print(f"\n4. Sending test message...")
    
    test_payload = {
        "intent": "health_check",
        "test": "force_registration_test",
        "timestamp": time.time(),
        "request_id": "force_test_001"
    }
    
    resp = requests.post(f"{broker_url}/mesh/send", json={
        "channel": "quantum",
        "sender_id": "force_registration_script",
        "recipient_id": agent_id,
        "payload": test_payload,
        "ttl_seconds": 30
    })
    
    if resp.status_code == 200:
        print(f"   ✓ Test message sent")
        message_id = resp.json().get('message_id')
        print(f"   Message ID: {message_id}")
        
        # Check if QIP receives it
        print(f"   Waiting 2 seconds...")
        time.sleep(2)
        
        resp = requests.get(f"{broker_url}/mesh/poll?agent_id={agent_id}&channel=quantum&max_messages=10")
        if resp.status_code == 200:
            messages = resp.json().get('messages', [])
            print(f"   Messages in queue: {len(messages)}")
            if messages:
                print(f"   ✓ SUCCESS! QIP can receive messages!")
                print(f"   First message ID: {messages[0].get('message_id', 'unknown')}")
            else:
                print(f"   ✗ No messages in queue")
        else:
            print(f"   ✗ Failed to poll: {resp.status_code}")
    else:
        print(f"   ✗ Failed to send test message: {resp.status_code}")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n=== FORCE REGISTRATION COMPLETE ===")
