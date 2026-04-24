#!/usr/bin/env python3
"""
Patch QIP mesh consumer to ensure proper mesh registration.
This script modifies quantum_mesh_consumer.py to:
1. Check if agent is registered with mesh bus before subscribing
2. If not registered, register first
3. Retry subscription on failure
"""
import os
import re

QIP_FILE = "quantum_mesh_consumer.py"

print("=== PATCHING QIP MESH CONSUMER ===")

# Read the current file
with open(QIP_FILE, 'r') as f:
    content = f.read()

# Find the subscribe function
subscribe_pattern = r'def subscribe\(broker: str\) -> bool:'
subscribe_match = re.search(subscribe_pattern, content)

if not subscribe_match:
    print("✗ Could not find subscribe function")
    exit(1)

subscribe_start = subscribe_match.start()

# Find the end of the subscribe function (next function definition)
next_func_pattern = r'\ndef [a-zA-Z_]+\(|^class [a-zA-Z_]+:'
next_func_match = re.search(next_func_pattern, content[subscribe_start + 1:])

if next_func_match:
    subscribe_end = subscribe_start + next_func_match.start()
    subscribe_func = content[subscribe_start:subscribe_end]
else:
    # If no next function, take to end of file
    subscribe_func = content[subscribe_start:]

print(f"\nCurrent subscribe function:")
print("-" * 50)
print(subscribe_func)
print("-" * 50)

# Create enhanced subscribe function
enhanced_subscribe = '''def subscribe(broker: str) -> bool:
    """Subscribe to all quantum channels with registration fallback."""
    ok = True
    for channel in SUBSCRIBE_CHANNELS:
        # First try normal subscription
        result = _post(f"{broker}/mesh/subscribe", {
            "agent_id": AGENT_ID,
            "channel": channel,
        })
        
        if result and result.get("status") == "success":
            logger.info(f"Subscribed to channel '{channel}' ✅")
            continue
            
        # If subscription failed, try to register agent first
        logger.warning(f"Subscribe to '{channel}' failed, attempting registration...")
        
        # Try to register agent with mesh bus
        register_result = _post(f"{broker}/mesh/register", {
            "agent_id": AGENT_ID,
        })
        
        if register_result and register_result.get("status") == "success":
            logger.info(f"Registered {AGENT_ID} with mesh bus ✅")
            # Retry subscription
            result = _post(f"{broker}/mesh/subscribe", {
                "agent_id": AGENT_ID,
                "channel": channel,
            })
            if result and result.get("status") == "success":
                logger.info(f"Subscribed to channel '{channel}' ✅")
                continue
        
        # If still failing, log error
        logger.warning(f"Subscribe to '{channel}' failed after registration attempt: {result}")
        ok = False
    
    return ok
'''

# Replace the subscribe function
new_content = content[:subscribe_start] + enhanced_subscribe + content[subscribe_end:]

# Write back to file
with open(QIP_FILE, 'w') as f:
    f.write(new_content)

print(f"\n✓ Patched {QIP_FILE}")
print("\nEnhanced subscribe function now includes:")
print("1. Normal subscription attempt")
print("2. Registration fallback if subscription fails")
print("3. Retry subscription after registration")
print("4. Better error logging")

# Also need to check if /mesh/register endpoint exists
print("\n⚠️  Note: This patch assumes /mesh/register endpoint exists.")
print("If it doesn't, we may need to create it or use a different approach.")

print("\n=== PATCH COMPLETE ===")
