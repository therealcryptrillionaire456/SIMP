#!/usr/bin/env python3
"""
Fix QIP mesh registration - ensures quantum_intelligence_prime is properly
registered with the mesh bus and subscribed to channels.
"""
import sys
import os
import time
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_qip_registration():
    """Fix QIP mesh registration issues."""
    broker_url = "http://127.0.0.1:5555"
    agent_id = "quantum_intelligence_prime"
    
    print("=== FIXING QIP MESH REGISTRATION ===")
    
    # 1. Check if QIP is registered with broker
    print(f"\n1. Checking broker registration for {agent_id}...")
    resp = requests.get(f"{broker_url}/agents")
    agents = resp.json().get('agents', {})
    
    if agent_id in agents:
        print(f"   ✓ {agent_id} is registered with broker")
        qip_data = agents[agent_id]
        print(f"   Status: {qip_data.get('status')}")
        print(f"   Last heartbeat: {qip_data.get('last_heartbeat')}")
    else:
        print(f"   ✗ {agent_id} is NOT registered with broker")
        print("   Cannot fix mesh registration without broker registration")
        return False
    
    # 2. Try to register with mesh bus via direct API if available
    print(f"\n2. Attempting mesh bus registration...")
    
    # First, try the mesh subscribe endpoint (which should trigger registration)
    print("   Testing mesh subscription...")
    for channel in ["quantum", "intent_requests"]:
        resp = requests.post(f"{broker_url}/mesh/subscribe", json={
            "agent_id": agent_id,
            "channel": channel
        })
        
        if resp.status_code == 200:
            print(f"   ✓ Successfully subscribed to {channel}")
        else:
            print(f"   ✗ Failed to subscribe to {channel}: {resp.status_code}")
            print(f"   Error: {resp.text}")
    
    # 3. Check mesh routing status
    print(f"\n3. Checking mesh routing status...")
    resp = requests.get(f"{broker_url}/mesh/routing/status")
    if resp.status_code == 200:
        status = resp.json()
        mesh_routing = status.get('mesh_routing', {})
        print(f"   Mesh enabled: {mesh_routing.get('mesh_enabled', False)}")
        print(f"   Mesh agents count: {mesh_routing.get('mesh_agents_count', 0)}")
        print(f"   Fallback mode: {mesh_routing.get('fallback_mode', False)}")
    else:
        print(f"   ✗ Failed to get mesh status: {resp.status_code}")
    
    # 4. Send a test message to verify
    print(f"\n4. Sending test message to verify...")
    test_payload = {
        "intent": "health_check",
        "test": "registration_fix_test",
        "timestamp": time.time(),
        "request_id": "fix_test_001"
    }
    
    resp = requests.post(f"{broker_url}/mesh/send", json={
        "channel": "quantum",
        "sender_id": "goose_orchestrator",
        "recipient_id": agent_id,
        "payload": test_payload,
        "ttl_seconds": 30
    })
    
    if resp.status_code == 200:
        print(f"   ✓ Test message sent successfully")
        message_id = resp.json().get('message_id')
        print(f"   Message ID: {message_id}")
        
        # Wait and check if QIP receives it
        print(f"   Waiting 3 seconds for QIP to poll...")
        time.sleep(3)
        
        # Check if message was delivered
        resp = requests.get(f"{broker_url}/mesh/poll?agent_id={agent_id}&channel=quantum&max_messages=10")
        if resp.status_code == 200:
            messages = resp.json().get('messages', [])
            print(f"   Messages in queue: {len(messages)}")
            if messages:
                print(f"   ✓ QIP can receive messages!")
            else:
                print(f"   ✗ No messages in queue (QIP might have processed it or not subscribed)")
        else:
            print(f"   ✗ Failed to poll messages: {resp.status_code}")
    else:
        print(f"   ✗ Failed to send test message: {resp.status_code}")
        print(f"   Error: {resp.text}")
    
    print(f"\n=== FIX COMPLETE ===")
    return True

if __name__ == "__main__":
    fix_qip_registration()
