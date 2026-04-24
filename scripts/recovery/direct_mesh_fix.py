#!/usr/bin/env python3
"""
Direct mesh fix - registers QIP with mesh bus directly.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import mesh bus directly
from simp.mesh.bus import get_mesh_bus

print("=== DIRECT MESH BUS FIX ===")

agent_id = "quantum_intelligence_prime"
mesh_bus = get_mesh_bus()

print(f"\n1. Current mesh bus state:")
print(f"   Registered agents: {list(mesh_bus._registered_agents)}")
print(f"   Channels: {list(mesh_bus._channel_subscribers.keys())}")

print(f"\n2. Registering {agent_id}...")
try:
    # Register agent
    mesh_bus.register_agent(agent_id)
    print(f"   ✓ Registered {agent_id} with mesh bus")
    
    # Subscribe to channels
    channels = ["quantum", "intent_requests", "safety_alerts"]
    for channel in channels:
        success = mesh_bus.subscribe(agent_id, channel)
        print(f"   ✓ Subscribed to {channel}: {success}")
    
except Exception as e:
    print(f"   ✗ Error: {e}")

print(f"\n3. Updated mesh bus state:")
print(f"   Registered agents: {list(mesh_bus._registered_agents)}")
for channel, subscribers in mesh_bus._channel_subscribers.items():
    print(f"   {channel}: {subscribers}")

print(f"\n4. Testing message delivery...")
# Send a test message
test_msg = {
    "channel": "quantum",
    "sender_id": "direct_fix",
    "recipient_id": agent_id,
    "payload": {"test": "direct_mesh_fix", "timestamp": time.time()},
    "ttl_seconds": 30
}

try:
    # Use mesh bus directly
    message_id = mesh_bus.send_message(
        test_msg["channel"],
        test_msg["sender_id"],
        test_msg["recipient_id"],
        test_msg["payload"],
        test_msg["ttl_seconds"]
    )
    print(f"   ✓ Test message sent: {message_id}")
    
    # Check if message is in queue
    messages = mesh_bus.get_messages(agent_id, "quantum", max_messages=10)
    print(f"   ✓ Messages in queue for {agent_id}: {len(messages)}")
    
except Exception as e:
    print(f"   ✗ Error sending test message: {e}")
    # Check if methods exist
    print(f"   Available methods: {[m for m in dir(mesh_bus) if not m.startswith('_')]}")

print("\n=== FIX COMPLETE ===")
print("\nNote: This fix modifies the mesh bus singleton directly.")
print("The quantum_mesh_consumer should now be able to receive messages.")
