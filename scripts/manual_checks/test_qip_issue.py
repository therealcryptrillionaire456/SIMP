#!/usr/bin/env python3.10
"""
Test to diagnose QIP issue:
1. Check if QIP is running
2. Check if messages can be sent to QIP
3. Check if QIP can receive messages
4. Check if QIP can process messages
"""

import os
import json
import requests
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)

BROKER = "http://127.0.0.1:5555"

def test_qip():
    print("=== Testing QIP Issue ===")
    
    # 1. Check QIP status
    print("\n1. Checking QIP agent status...")
    resp = requests.get(f"{BROKER}/agents/quantum_intelligence_prime")
    if resp.status_code == 200:
        data = resp.json()
        agent = data.get("agent", {})
        print(f"   Status: {agent.get('status', 'unknown')}")
        print(f"   Heartbeats: {agent.get('heartbeat_count', 0)}")
        print(f"   Intents received: {agent.get('intents_received', 0)}")
        print(f"   Intents completed: {agent.get('intents_completed', 0)}")
        print(f"   Transport: {agent.get('metadata', {}).get('transport', 'unknown')}")
        print(f"   Mesh native: {agent.get('metadata', {}).get('mesh_native', False)}")
    else:
        print(f"   ❌ Failed to get agent status: {resp.status_code}")
        return
    
    # 2. Send test message
    print("\n2. Sending test message to QIP...")
    message = {
        "type": "health_check",
        "payload": {"test": "diagnostic"},
        "sender_id": "test_diagnostic",
        "recipient_id": "quantum_intelligence_prime",
        "channel": "intent_requests",
        "ttl": 60
    }
    
    resp = requests.post(f"{BROKER}/mesh/send", json=message)
    if resp.status_code == 200:
        result = resp.json()
        print(f"   ✅ Message sent: {result.get('message_id', 'unknown')}")
        print(f"   Status: {result.get('status', 'unknown')}")
    else:
        print(f"   ❌ Failed to send message: {resp.status_code}")
        print(f"   Response: {resp.text}")
        return
    
    # 3. Check if message appears in mesh events
    print("\n3. Checking mesh events...")
    time.sleep(2)
    # Try to read mesh events file
    try:
        with open("data/logs/mesh_events.jsonl", "r") as f:
            lines = f.readlines()
            recent = lines[-5:] if len(lines) > 5 else lines
            print(f"   Recent mesh events (last {len(recent)}):")
            for line in recent:
                try:
                    event = json.loads(line.strip())
                    if "quantum_intelligence_prime" in str(event):
                        print(f"   - {json.dumps(event, indent=4)}")
                except:
                    pass
    except FileNotFoundError:
        print("   ❌ Mesh events file not found")
    
    # 4. Check if QIP can poll for the message
    print("\n4. Checking if QIP can poll for message...")
    resp = requests.get(f"{BROKER}/mesh/poll", params={
        "agent_id": "quantum_intelligence_prime",
        "channel": "intent_requests",
        "max_messages": 10
    })
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Poll status: {data.get('status', 'unknown')}")
        print(f"   Messages count: {data.get('count', 0)}")
        if data.get('count', 0) > 0:
            print(f"   ✅ QIP can receive messages via polling!")
        else:
            print(f"   ❌ No messages for QIP via polling")
    else:
        print(f"   ❌ Poll failed: {resp.status_code}")
    
    print("\n=== Diagnosis Summary ===")
    print("If QIP is mesh_native=true but trying to poll via HTTP,")
    print("messages won't be delivered. QIP needs to:")
    print("1. Use mesh bus callbacks (not HTTP polling)")
    print("2. OR switch to HTTP transport (not mesh_native)")
    print("3. OR fix message routing between mesh bus and HTTP")

if __name__ == "__main__":
    test_qip()
