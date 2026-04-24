#!/usr/bin/env python3.10
"""
Simple fix: Comment out mesh bus code and use HTTP only
"""

import re

with open("quantum_mesh_consumer.py", "r") as f:
    content = f.read()

# Comment out mesh bus import
content = re.sub(r'^from simp\.mesh\.bus import get_mesh_bus$', 
                 '# from simp.mesh.bus import get_mesh_bus  # DISABLED: Using HTTP only', 
                 content, flags=re.MULTILINE)

# Comment out mesh bus usage in _register_with_mesh_bus
mesh_bus_pattern = r'(\s+)# Try mesh bus first\n\s+mesh_bus = get_mesh_bus\(\)\n\s+if agent_id not in mesh_bus\._registered_agents:\n\s+try:\n\s+mesh_bus\.register_agent\(agent_id\)\n\s+logger\.info\(f"Registered \{agent_id\} with MeshBus"\)\n\s+except Exception as e:\n\s+logger\.error\(f"MeshBus registration failed: \{e\}"\)\n\s+return False'
mesh_bus_replacement = r'\1# DISABLED: Mesh bus code removed - using HTTP only\n\1return _http_register_fallback(agent_id, broker, logger)'

content = re.sub(mesh_bus_pattern, mesh_bus_replacement, content, flags=re.MULTILINE)

# Comment out mesh bus subscription
subscribe_pattern = r'(\s+)# Subscribe via mesh bus\n\s+try:\n\s+success = mesh_bus\.subscribe\(agent_id, channel\)\n\s+if success:\n\s+logger\.info\(f"Directly subscribed to channel \'\{\{channel\}\}' ✅"\)\n\s+return True\n\s+else:\n\s+logger\.warning\(f"MeshBus subscription failed for \{\{channel\}\}"\)\n\s+except Exception as e:\n\s+logger\.error\(f"MeshBus subscription error: \{e\}"\)'
subscribe_replacement = r'\1# DISABLED: Mesh bus subscription removed\n\1return _http_subscribe_fallback(agent_id, channel, broker, logger)'

content = re.sub(subscribe_pattern, subscribe_replacement, content, flags=re.MULTILINE)

# Comment out main mesh bus registration
main_mesh_pattern = r'(\s+)# Register with mesh bus\n\s+mesh_bus = get_mesh_bus\(\)\n\s+if AGENT_ID not in mesh_bus\._registered_agents:\n\s+try:\n\s+mesh_bus\.register_agent\(AGENT_ID\)\n\s+logger\.info\(f"Pre-registered \{AGENT_ID\} with mesh bus ✅"\)\n\s+except Exception as e:\n\s+logger\.error\(f"MeshBus pre-registration failed: \{e\}"\)\n\n\s+# Pre-subscribe to channels\n\s+for channel in \["quantum", "intent_requests"\]:\n\s+try:\n\s+mesh_bus\.subscribe\(AGENT_ID, channel\)\n\s+logger\.info\(f"Pre-subscribed to \{channel\} ✅"\)\n\s+except Exception as e:\n\s+logger\.error\(f"MeshBus pre-subscription to \{channel\} failed: \{e\}"\)'
main_mesh_replacement = r'\1# DISABLED: Mesh bus registration removed\n\1# Using HTTP registration and subscription only\n\1_http_register_fallback(AGENT_ID, BROKER, logger)\n\1for channel in ["quantum", "intent_requests"]:\n\1    _http_subscribe_fallback(AGENT_ID, channel, BROKER, logger)'

content = re.sub(main_mesh_pattern, main_mesh_replacement, content, flags=re.MULTILINE)

with open("quantum_mesh_consumer.py", "w") as f:
    f.write(content)

print("✅ Applied simple fix: Commented out mesh bus code")
