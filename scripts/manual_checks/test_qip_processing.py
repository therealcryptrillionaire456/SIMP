#!/usr/bin/env python3
"""
Test QIP message processing via HTTP mesh endpoints.
"""
import os
import requests
import json
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)

broker_url = 'http://127.0.0.1:5555'
agent_id = 'quantum_intelligence_prime'

print('=== TESTING QIP MESSAGE PROCESSING ===')

# First, check current state
print(f'\n1. Checking agent status...')
resp = requests.get(f'{broker_url}/agents/{agent_id}')
if resp.status_code == 200:
    agent_info = resp.json()
    print(f'   ✓ Agent registered: {agent_info.get("agent_id")}')
    print(f'   Status: {agent_info.get("status")}')
    print(f'   Last heartbeat: {agent_info.get("last_heartbeat")}')
    print(f'   Mesh native: {agent_info.get("mesh_native", False)}')
else:
    print(f'   ✗ Agent not found: {resp.status_code}')

# Send a health check message
print(f'\n2. Sending health check to QIP...')
resp = requests.post(f'{broker_url}/mesh/send', json={
    'channel': 'quantum',
    'sender_id': 'test_runner',
    'recipient_id': agent_id,
    'payload': {
        'intent': 'health_check',
        'request_id': f'test_{int(time.time())}',
        'timestamp': time.time()
    },
    'ttl_seconds': 30
})

if resp.status_code == 200:
    result = resp.json()
    print(f'   ✓ Message sent: {result.get("message_id")}')
    
    # Wait for processing
    print(f'\n3. Waiting 3 seconds for QIP to process...')
    time.sleep(3)
    
    # Check QIP logs for processing
    print(f'\n4. Checking QIP logs...')
    import subprocess
    result = subprocess.run(['tail', '-10', 'logs/quantum/qip.log'], 
                          capture_output=True, text=True)
    print(f'   Recent logs:')
    for line in result.stdout.strip().split('\n'):
        if 'health_check' in line or 'Processing' in line or 'Response' in line:
            print(f'   - {line}')
    
    # Check if response was sent back
    print(f'\n5. Checking for response from QIP...')
    resp = requests.get(f"{broker_url}/mesh/subscribe/{channel}" + f"?agent_id={AGENT_ID}")
    
    if resp.status_code == 200:
        result = resp.json()
        messages = result.get('messages', [])
        print(f'   ✓ Poll response: {len(messages)} messages')
        for msg in messages:
            sender = msg.get('sender_id', 'unknown')
            if sender == agent_id:
                print(f'   ✓ SUCCESS! QIP responded!')
                print(f'   Response: {json.dumps(msg.get("payload", {}), indent=2)}')
                break
        else:
            print(f'   ✗ No response from QIP yet')
    else:
        print(f'   ✗ Poll failed: {resp.text}')
else:
    print(f'   ✗ Send failed: {resp.status_code}: {resp.text}')

print(f'\n=== TEST COMPLETE ===')
