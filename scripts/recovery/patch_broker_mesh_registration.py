#!/usr/bin/env python3
"""
Patch broker to ensure mesh bus registration works for QIP.
This script adds retry logic and better error handling for mesh bus registration.
"""
import os
import re

BROKER_FILE = "simp/server/broker.py"

print("=== PATCHING BROKER MESH REGISTRATION ===")

# Read the current file
with open(BROKER_FILE, 'r') as f:
    content = f.read()

# Find the mesh bus registration section in register_agent method
pattern = r'# Register agent with MeshBus\s+try:\s+self\.mesh_bus\.register_agent\(agent_id\)\s+# Auto-subscribe to safety alerts channel for all agents\s+self\.mesh_bus\.subscribe\(agent_id,\s*"safety_alerts"\)\s+self\.logger\.debug\(f"Agent \{agent_id\} registered with MeshBus"\)\s+except Exception as e:\s+self\.logger\.warning\(f"Failed to register agent \{agent_id\} with MeshBus: \{e\}"\)'
match = re.search(pattern, content, re.DOTALL)

if not match:
    print("✗ Could not find mesh bus registration section")
    # Try a different pattern
    pattern = r'self\.mesh_bus\.register_agent\(agent_id\)'
    match = re.search(pattern, content)
    if not match:
        print("✗ Could not find mesh bus registration at all")
        exit(1)

print(f"\nFound mesh bus registration at position {match.start()}")

# Create enhanced mesh bus registration with retry logic
enhanced_registration = '''            # Register agent with MeshBus (with retry logic)
            max_retries = 3
            registered_with_mesh = False
            for attempt in range(max_retries):
                try:
                    self.mesh_bus.register_agent(agent_id)
                    # Auto-subscribe to safety alerts channel for all agents
                    self.mesh_bus.subscribe(agent_id, "safety_alerts")
                    self.logger.debug(f"Agent {agent_id} registered with MeshBus (attempt {attempt + 1})")
                    registered_with_mesh = True
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        self.logger.warning(f"Failed to register agent {agent_id} with MeshBus after {max_retries} attempts: {e}")
                        # Log more details for debugging
                        self.logger.debug(f"Mesh bus state: registered_agents={list(self.mesh_bus._registered_agents)}")
                    else:
                        self.logger.debug(f"Mesh bus registration attempt {attempt + 1} failed for {agent_id}: {e}")
                        import time
                        time.sleep(0.1 * (attempt + 1))  # Small backoff
            
            # If registration failed, log it prominently for QIP
            if not registered_with_mesh and agent_id == "quantum_intelligence_prime":
                self.logger.error(f"CRITICAL: QIP agent {agent_id} failed mesh bus registration!")
                self.logger.error(f"This will prevent quantum operations. Mesh bus state: {self.mesh_bus.get_statistics() if hasattr(self.mesh_bus, 'get_statistics') else 'unknown'}")'''

# Replace the section
if match:
    # Find the exact bounds of the try-except block
    start = match.start()
    # Find the end of the except block (look for next line at same indentation level)
    lines = content[start:].split('\n')
    indent_level = 0
    end_pos = start
    for i, line in enumerate(lines):
        end_pos += len(line) + 1  # +1 for newline
        # Check if we've reached the next major section (less indented)
        if i > 0 and line.strip() and not line.startswith(' ' * 12):  # 12 spaces = 3 tabs
            # Check if this is the start of the next section
            if 'Register agent mesh capabilities' in line or 'if self.mesh_routing:' in line:
                break
    
    # Replace the section
    new_content = content[:start] + enhanced_registration + content[end_pos:]
    
    # Write back to file
    with open(BROKER_FILE, 'w') as f:
        f.write(new_content)
    
    print(f"\n✓ Patched {BROKER_FILE}")
    print("\nEnhanced mesh bus registration now includes:")
    print("1. Retry logic (3 attempts)")
    print("2. Backoff between attempts")
    print("3. Better error logging")
    print("4. Critical error logging for QIP")
    print("5. Mesh bus state debugging")

print("\n=== PATCH COMPLETE ===")
print("\nNote: Broker needs to be restarted for changes to take effect.")
