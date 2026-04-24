#!/usr/bin/env python3
"""
Test QIP message reception.
"""
import sys
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

from simp.mesh.bus import get_mesh_bus

print('=== TESTING QIP MESSAGE RECEPTION ===')

# Get mesh bus instance
mesh_bus = get_mesh_bus()
agent_id = 'quantum_intelligence_prime'

print(f'\n1. Checking mesh bus state...')
print(f'   Agent registered: {agent_id in mesh_bus._registered_agents}')
print(f'   Agent queue exists: {agent_id in mesh_bus._agent_queues}')

print(f'\n2. Sending test message...')
from simp.mesh import MeshPacket
import uuid

packet = MeshPacket(
    message_id=str(uuid.uuid4()),
    sender_id='test_sender',
    recipient_id=agent_id,
    channel='quantum',
    payload={'test': 'direct_mesh_bus_test'},
    ttl_seconds=30
)

success = mesh_bus.send(packet)
print(f'   Send success: {success}')

print(f'\n3. Checking for messages...')
messages = mesh_bus.receive(agent_id, max_messages=10)
print(f'   Messages received: {len(messages)}')
for msg in messages:
    print(f'   - {msg.message_id}: {msg.payload}')

print(f'\n=== TEST COMPLETE ===')
