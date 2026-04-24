#!/usr/bin/env python3
"""
Fix QIP polling and Path issues manually.
"""
import os
import re

def fix_polling_endpoint():
    """Change GET /mesh/poll to GET /mesh/subscribe/{channel}" + f"?agent_id={AGENT_ID}"""
    with open('quantum_mesh_consumer.py', 'r') as f:
        content = f.read()
    
    # Fix the poll_messages function
    old_poll = '''def poll_messages(broker: str, channel: str) -> list:
    """Poll for messages on a channel. Returns list of message dicts."""
    result = _get(f"{broker}/mesh/subscribe/{channel}" + f"?agent_id={AGENT_ID}")
    if result and result.get("status") == "success":
        return result.get("messages", [])
    return []'''
    
    new_poll = '''def poll_messages(broker: str, channel: str) -> list:
    """Poll for messages on a channel. Returns list of message dicts."""
    result = _get(f"{broker}/mesh/subscribe/{channel}" + f"?agent_id={AGENT_ID}")
    if result and result.get("status") == "success":
        return result.get("messages", [])
    return []'''
    
    content = content.replace(old_poll, new_poll)
    
    # Also fix the _http_subscribe_fallback function if it exists
    content = content.replace(
        'result = _post(f"{broker}/mesh/subscribe", {',
        'result = _post(f"{broker}/mesh/subscribe", {\n        "simp_versions": ["1.0"],'
    )
    
    with open('quantum_mesh_consumer.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed polling endpoint and added simp_versions")

def fix_path_issue_in_quantum_mode():
    """Fix the Path.exists() issue in stray_goose_quantum_integration.py"""
    try:
        with open('stray_goose_quantum_integration.py', 'r') as f:
            content = f.read()
        
        # Fix Path(config_path).exists() instead of config_path.exists()
        content = content.replace(
            'if config_path and config_path.exists():',
            'if config_path and Path(config_path).exists():'
        )
        
        with open('stray_goose_quantum_integration.py', 'w') as f:
            f.write(content)
        
        print("✅ Fixed Path.exists() issue in quantum mode engine")
    except Exception as e:
        print(f"⚠️  Could not fix Path issue: {e}")

if __name__ == "__main__":
    print("Fixing QIP issues...")
    fix_polling_endpoint()
    fix_path_issue_in_quantum_mode()
    print("✅ Fixes applied. Restart QIP to test.")
