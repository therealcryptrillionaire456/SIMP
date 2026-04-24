#!/usr/bin/env python3
"""
Workaround for QIP mesh registration.
This modifies quantum_mesh_consumer.py to directly use mesh bus singleton
instead of relying on HTTP endpoints for subscription.
"""
import os
import re

QIP_FILE = "quantum_mesh_consumer.py"

print("=== WORKAROUND FOR QIP MESH REGISTRATION ===")

# Read the current file
with open(QIP_FILE, 'r') as f:
    content = f.read()

# Add import for mesh bus at the top
import_pattern = r'import sys\nimport os\nimport time\nimport json\nimport logging\nimport argparse\nimport signal\nimport threading\nfrom datetime import datetime, timezone\nfrom typing import Optional, Dict, Any\n\nimport requests'
import_replacement = '''import sys
import os
import time
import json
import logging
import argparse
import signal
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests

# Direct mesh bus access for workaround
from simp.mesh.bus import get_mesh_bus'''

if import_replacement not in content:
    content = content.replace(import_pattern, import_replacement)
    print("✓ Added mesh bus import")

# Find the subscribe function and replace it with direct mesh bus version
subscribe_pattern = r'def subscribe\(broker: str\) -> bool:.*?return ok'
subscribe_replacement = '''def subscribe(broker: str) -> bool:
    """Subscribe to all quantum channels using direct mesh bus access."""
    ok = True
    
    # Get mesh bus singleton
    mesh_bus = get_mesh_bus()
    agent_id = AGENT_ID
    
    for channel in SUBSCRIBE_CHANNELS:
        # Check if already registered
        if agent_id not in mesh_bus._registered_agents:
            try:
                mesh_bus.register_agent(agent_id)
                logger.info(f"Directly registered {agent_id} with mesh bus ✅")
            except Exception as e:
                logger.warning(f"Failed to register {agent_id} with mesh bus: {e}")
                ok = False
                continue
        
        # Subscribe to channel
        try:
            success = mesh_bus.subscribe(agent_id, channel)
            if success:
                logger.info(f"Directly subscribed to channel '{channel}' ✅")
            else:
                logger.warning(f"Failed to subscribe to '{channel}' via mesh bus")
                ok = False
        except Exception as e:
            logger.warning(f"Error subscribing to '{channel}': {e}")
            ok = False
    
    # Also try HTTP subscription as fallback
    if not ok:
        logger.info("Falling back to HTTP subscription...")
        ok = _http_subscribe_fallback(broker)
    
    return ok


def _http_subscribe_fallback(broker: str) -> bool:
    """Fallback HTTP subscription."""
    ok = True
    for channel in SUBSCRIBE_CHANNELS:
        result = _post(f"{broker}/mesh/subscribe", {
            "agent_id": AGENT_ID,
            "channel": channel,
        })
        if result and result.get("status") == "success":
            logger.info(f"HTTP subscribed to channel '{channel}' ✅")
        else:
            logger.warning(f"HTTP subscribe to '{channel}' failed: {result}")
            ok = False
    return ok'''

# Use regex with DOTALL to match across multiple lines
subscribe_regex = re.compile(r'def subscribe\(broker: str\) -> bool:.*?return ok', re.DOTALL)
if subscribe_regex.search(content):
    content = subscribe_regex.sub(subscribe_replacement, content)
    print("✓ Replaced subscribe function with direct mesh bus version")
else:
    print("✗ Could not find subscribe function to replace")

# Also update the QuantumMeshConsumer.start() method to ensure registration
# Find the start method
start_method_pattern = r'def start\(self\):.*?while self\._running:'
start_method_replacement = '''def start(self):
        logger.info(f"Quantum mesh consumer starting — broker={self.broker}")
        self._engine = _load_engine()
        self._integration = _load_integration()

        # Ensure mesh bus registration before HTTP registration
        mesh_bus = get_mesh_bus()
        if AGENT_ID not in mesh_bus._registered_agents:
            try:
                mesh_bus.register_agent(AGENT_ID)
                logger.info(f"Pre-registered {AGENT_ID} with mesh bus ✅")
                # Pre-subscribe to channels
                for channel in SUBSCRIBE_CHANNELS:
                    mesh_bus.subscribe(AGENT_ID, channel)
                    logger.info(f"Pre-subscribed to {channel} ✅")
            except Exception as e:
                logger.warning(f"Pre-registration failed: {e}")

        register(self.broker)
        subscribe(self.broker)

        self._running = True
        last_heartbeat = 0.0

        logger.info("Polling mesh for quantum intents... (Ctrl+C to stop)")

        while self._running:'''

start_method_regex = re.compile(r'def start\(self\):.*?while self\._running:', re.DOTALL)
if start_method_regex.search(content):
    content = start_method_regex.sub(start_method_replacement, content)
    print("✓ Updated start method with pre-registration")
else:
    print("✗ Could not find start method to update")

# Write back to file
with open(QIP_FILE, 'w') as f:
    f.write(content)

print(f"\n✓ Workaround applied to {QIP_FILE}")
print("\nChanges made:")
print("1. Added direct mesh bus import")
print("2. Replaced subscribe() with direct mesh bus access")
print("3. Added HTTP subscription fallback")
print("4. Added pre-registration in start() method")
print("\nThe QIP agent will now:")
print("- Directly register with mesh bus singleton")
print("- Directly subscribe to channels")
print("- Fall back to HTTP if direct access fails")
print("- Pre-register before attempting HTTP registration")

print("\n=== WORKAROUND COMPLETE ===")
print("\nNote: The quantum_mesh_consumer process needs to be restarted.")
print("Current PID: $(ps aux | grep '[q]uantum_mesh_consumer' | awk '{print $2}')")
