#!/usr/bin/env python3
"""
Fix Coinbase private key formatting in .env file
"""

import os
import re
from pathlib import Path

def fix_coinbase_key():
    """Fix the Coinbase private key formatting"""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ .env file not found")
        return False
    
    # Read current content
    with open(env_path, 'r') as f:
        content = f.read()
    
    # Find the Coinbase private key
    pattern = r'COINBASE_API_PRIVATE_KEY=(.*?)(?=\n[A-Z_]|$)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("❌ Coinbase private key not found in .env")
        return False
    
    current_key = match.group(1).strip()
    
    # Check if it's already properly formatted
    if "-----BEGIN EC PRIVATE KEY-----" in current_key and "-----END EC PRIVATE KEY-----" in current_key:
        print("✅ Coinbase private key is already properly formatted")
        return True
    
    # The key should be the one from your message
    fixed_key = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIPBKmQijcoLG3GPZ7ii9Plh+c0t6CVp/hH6UzJhwZeYSoAoGCCqGSM49
AwEHoUQDQgAE5iNjj5QApwg1n8c9JjSkFAgroZBOn2cg5Rg8ICIlsg2bpO+s71PP
dhU+KtB5qBmXayI05PrQ/zafNPOlMIwZNA==
-----END EC PRIVATE KEY-----"""
    
    # Replace the key
    new_content = content.replace(current_key, fixed_key)
    
    # Write back
    with open(env_path, 'w') as f:
        f.write(new_content)
    
    print("✅ Coinbase private key fixed")
    print(f"Old key length: {len(current_key)} chars")
    print(f"New key length: {len(fixed_key)} chars")
    print(f"New key starts with: {fixed_key[:50]}...")
    
    return True

if __name__ == "__main__":
    fix_coinbase_key()
