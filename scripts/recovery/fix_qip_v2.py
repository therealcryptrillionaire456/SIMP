#!/usr/bin/env python3
"""
Fix QIP polling to use correct endpoint and parameters.
"""
import os
import re

def fix_polling_endpoint():
    """Revert to GET /mesh/poll but with correct parameters"""
    with open('quantum_mesh_consumer.py', 'r') as f:
        content = f.read()
    
    # Find and fix the poll_messages function
    # Look for the current broken version
    broken_pattern = r'def poll_messages\(broker: str, channel: str\) -> list:.*?return \[\]'
    
    # Replace with working version
    fixed_poll = '''def poll_messages(broker: str, channel: str) -> list:
    """Poll for messages on a channel. Returns list of message dicts."""
    result = _get(f"{broker}/mesh/subscribe/{channel}" + f"?agent_id={AGENT_ID}")
    if result and result.get("status") == "success":
        return result.get("messages", [])
    return []'''
    
    # Use regex to replace
    import re
    content = re.sub(broken_pattern, fixed_poll, content, flags=re.DOTALL)
    
    # Also fix the _http_subscribe_fallback function
    content = content.replace(
        'result = _post(f"{broker}/mesh/subscribe", {',
        'result = _post(f"{broker}/mesh/subscribe", {\n        "simp_versions": ["1.0"],'
    )
    
    with open('quantum_mesh_consumer.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed polling with correct parameters")

if __name__ == "__main__":
    print("Fixing QIP polling endpoint...")
    fix_polling_endpoint()
    print("✅ Fix applied. Restart QIP to test.")
