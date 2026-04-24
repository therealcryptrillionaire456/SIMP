#!/usr/bin/env python3
"""
Fix Coinbase PEM file formatting
"""

import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Get the current key
current_key = os.getenv("COINBASE_API_PRIVATE_KEY", "")

print(f"Current key length: {len(current_key)} chars")
print(f"First 100 chars: {current_key[:100]}")
print(f"Last 100 chars: {current_key[-100:]}")

# Check if it has proper PEM format
if "-----BEGIN EC PRIVATE KEY-----" in current_key and "-----END EC PRIVATE KEY-----" in current_key:
    print("✅ Key already has PEM headers")
    
    # Check line breaks
    lines = current_key.split('\n')
    print(f"Number of lines: {len(lines)}")
    
    if len(lines) < 3:
        print("⚠️  Key may be missing line breaks")
        # Try to reformat
        parts = current_key.split('-----')
        if len(parts) >= 3:
            key_content = parts[2].strip()
            # Reformat with proper line breaks
            formatted_key = f"-----BEGIN EC PRIVATE KEY-----\n{key_content}\n-----END EC PRIVATE KEY-----"
            print(f"Reformatted key:\n{formatted_key}")
else:
    print("❌ Key missing PEM headers")
    
    # Try to extract the key content
    # Look for base64-like content
    import re
    
    # Try to find base64 content
    b64_match = re.search(r'[A-Za-z0-9+/=]{40,}', current_key)
    if b64_match:
        key_content = b64_match.group(0)
        formatted_key = f"-----BEGIN EC PRIVATE KEY-----\n{key_content}\n-----END EC PRIVATE KEY-----"
        print(f"Extracted and reformatted key:\n{formatted_key}")
    else:
        print("Could not extract key content")
