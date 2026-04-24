#!/usr/bin/env python3
"""
Test QIP live message processing.
"""
import os
import requests
import json
import time
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)

broker_url = 'http://127.0.0.1:5555'
agent_id = 'quantum_intelligence_prime'
test_agent = 'test_runner_' + str(int(time.time()))

print('=== TESTING QIP LIVE PROCESSING ===')

# Register test agent first
print(f'\n1. Registering test agent: {test_agent}')
resp = requests.post(f'{broker_url}/agents/register', json={
    'agent_id': test_agent,
    'endpoint': '(file-based)',
    'capabilities': ['test']
})
print(f'   Status: {resp.status_code}')

# Send health check to QIP
print(f'\n2. Sending health check to QIP...')
resp = requests.post(f'{broker_url}/mesh/send', json={
    'channel': 'quantum',
    'sender_id': test_agent,
    'recipient_id': agent_id,
    'payload': {
        'intent': 'health_check',
        'request_id': f'test_{int(time.time())}',
        'timestamp': time.time(),
        'test': 'live_processing'
    },
    'ttl_seconds': 30
})

if resp.status_code == 200:
    result = resp.json()
    msg_id = result.get('message_id')
    print(f'   ✓ Message sent: {msg_id}')
    
    # Wait for QIP to process (polling every 2 seconds)
    print(f'\n3. Waiting for QIP to process (max 10 seconds)...')
    for i in range(5):
        print(f'   Checking... ({i*2 + 2}s)')
        time.sleep(2)
        
        # Check for response
        resp = requests.get(f"{broker_url}/mesh/subscribe/{channel}" + f"?agent_id={AGENT_ID}")
        
        if resp.status_code == 200:
            result = resp.json()
            messages = result.get('messages', [])
            for msg in messages:
                if msg.get('sender_id') == agent_id:
                    print(f'\n   ✓ SUCCESS! QIP responded!')
                    print(f'   Response ID: {msg.get("message_id")}')
                    payload = msg.get('payload', {})
                    print(f'   Status: {payload.get("status", "unknown")}')
                    print(f'   Capabilities: {payload.get("capabilities", [])}')
                    print(f'   Timestamp: {payload.get("timestamp")}')
                    sys.exit(0)
    
    print(f'\n   ✗ No response from QIP after 10 seconds')
    
    # Check QIP logs
    print(f'\n4. Checking QIP logs...')
    import subprocess
    result = subprocess.run(['tail', '-5', 'logs/quantum/qip_current.log'], 
                          capture_output=True, text=True)
    print(f'   Recent QIP logs:')
    for line in result.stdout.strip().split('\n'):
        print(f'   - {line}')
        
else:
    print(f'   ✗ Send failed: {resp.status_code}: {resp.text}')

print(f'\n=== TEST COMPLETE ===')
