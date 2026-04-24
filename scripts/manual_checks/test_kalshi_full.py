#!/usr/bin/env python3
"""
Kalshi Full Connection Test
Testing with API Key ID + RSA Private Key
"""

import os
import sys
import json
import requests
import time
import base64
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)

# Load env
def load_env():
    """Load env vars handling multi-line values"""
    env = {}
    current_key = None
    current_val = []
    
    with open('.env') as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith('#'):
                if current_key:
                    env[current_key] = '\n'.join(current_val)
                    current_key = None
                    current_val = []
                continue
            if '=' in line and not current_key:
                key, val = line.split('=', 1)
                current_key = key.strip()
                if not val.strip():
                    current_val = []
                else:
                    current_val = [val.strip()]
            elif current_key:
                current_val.append(line)
            else:
                if current_key:
                    env[current_key] = '\n'.join(current_val)
                    current_key = None
                    current_val = []
    
    if current_key:
        env[current_key] = '\n'.join(current_val)
    
    return env

env = load_env()

print("=" * 60)
print("KALSHI FULL CONNECTION TEST")
print("=" * 60)

# Get credentials
api_key_id = env.get("KALSHI_API_KEY_ID", "")
private_key_pem = env.get("KALSHI_PRIVATE_KEY", "")
prod_key = env.get("KALSHI_PRODUCTION_API_KEY", "")
prod_secret = env.get("KALSHI_PRODUCTION_API_SECRET", "")

print(f"\n📋 KALSHI_API_KEY_ID: {api_key_id}")
print(f"📋 KALSHI_PRIVATE_KEY: {'✅ Present (' + str(len(private_key_pem)) + ' chars)' if private_key_pem else '❌ Missing'}")
print(f"📋 KALSHI_PRODUCTION_API_KEY: {'✅ Configured' if prod_key else '❌ Missing'}")
print(f"📋 KALSHI_PRODUCTION_API_SECRET: {'✅ Configured' if prod_secret else '❌ Missing'}")

# Test 1: Basic API connectivity
print("\n" + "=" * 60)
print("TEST 1: BASIC API CONNECTIVITY")
print("=" * 60)

# Kalshi API endpoints
KALSHI_BASE = "https://api.kalshi.com"
KALSHI_TRADE = f"{KALSHI_BASE}/trade-api/v2"

print(f"\n🔧 Testing {KALSHI_BASE}...")

# Test health endpoint
try:
    r = requests.get(f"{KALSHI_BASE}/health", timeout=10)
    print(f"   GET /health -> {r.status_code}")
    if r.status_code == 200:
        print("   ✅ Kalshi server reachable")
except Exception as e:
    print(f"   ❌ {str(e)[:50]}")

# Test exchange status
try:
    r = requests.get(f"{KALSHI_TRADE}/exchange/status", timeout=10)
    print(f"   GET /exchange/status -> {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ Exchange status: {json.dumps(data, indent=2)[:200]}")
except Exception as e:
    print(f"   ❌ {str(e)[:50]}")

# Test events
try:
    r = requests.get(f"{KALSHI_TRADE}/events", params={"limit": 2}, timeout=10)
    print(f"   GET /events -> {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        events = data.get('events', [])
        print(f"   ✅ Public events accessible ({len(events)} returned)")
        if events:
            for e in events[:2]:
                print(f"      📊 {e.get('title', 'N/A')} - {e.get('status', 'N/A')}")
except Exception as e:
    print(f"   ❌ {str(e)[:50]}")

# Test 2: Authentication with RSA key
print("\n" + "=" * 60)
print("TEST 2: RSA KEY AUTHENTICATION")
print("=" * 60)

if private_key_pem and api_key_id:
    try:
        # Load RSA key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        print("   ✅ RSA key loaded successfully")
        
        # Generate timestamp
        timestamp = int(time.time() * 1000)
        method = "GET"
        path = "/trade-api/v2/portfolio/balance"
        
        # Create message to sign
        message = f"{timestamp}{method}{path}"
        
        # Sign with RSA
        signature = private_key.sign(
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        # Base64 encode signature
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        auth_headers = {
            "Content-Type": "application/json",
            "User-Agent": "KLOUTBOT/1.0",
            "KALSHI-API-KEY": api_key_id,
            "KALSHI-API-SIGNATURE": signature_b64,
            "KALSHI-API-TIMESTAMP": str(timestamp)
        }
        
        print(f"   🔧 Testing GET /portfolio/balance with RSA auth...")
        print(f"      API Key: {api_key_id[:20]}...")
        print(f"      Timestamp: {timestamp}")
        print(f"      Signature: {signature_b64[:30]}...")
        
        r = requests.get(f"{KALSHI_TRADE}/portfolio/balance", 
                        headers=auth_headers, timeout=15)
        
        print(f"      Response HTTP {r.status_code}")
        print(f"      Response: {r.text[:300]}")
        
        if r.status_code == 200:
            data = r.json()
            print("\n   ✅ Kalshi AUTHENTICATION SUCCESSFUL!")
            if 'balance' in data:
                print(f"      💰 Balance: ${data['balance']:.2f}")
            if 'available_balance' in data:
                print(f"      💰 Available: ${data['available_balance']:.2f}")
        elif r.status_code == 401:
            print("   ❌ Authentication failed (HTTP 401)")
        else:
            print(f"   ⚠️  Unexpected response: HTTP {r.status_code}")
            
    except ImportError:
        print("   ⚠️  cryptography library needed for RSA auth")
        print("      Install: pip install cryptography")
    except Exception as e:
        print(f"   ❌ RSA auth error: {str(e)[:100]}")
else:
    print("   ❌ Missing RSA key or API key ID")

# Test 3: Alternative auth methods
print("\n" + "=" * 60)
print("TEST 3: ALTERNATIVE AUTH METHODS")
print("=" * 60)

if prod_key and prod_secret:
    # Test with production key/secret directly
    print(f"\n🔧 Testing with production credentials...")
    try:
        # Try direct POST login
        login_data = {"api_key": prod_key, "api_secret": prod_secret}
        r = requests.post(f"{KALSHI_TRADE}/login", json=login_data, timeout=10)
        print(f"   POST /login -> HTTP {r.status_code}")
        print(f"   Response: {r.text[:200]}")
        if r.status_code == 200:
            token = r.json().get('token', '')
            if token:
                print("   ✅ Login successful! Got auth token")
    except Exception as e:
        print(f"   ❌ Login error: {str(e)[:50]}")
else:
    print("\n   ⚠️  No production API key/secret to test")

# Summary
print("\n" + "=" * 60)
print("KALSHI CONNECTION SUMMARY")
print("=" * 60)

print(f"\n📊 Credentials Status:")
print(f"   ✅ API Key ID: {api_key_id}")
print(f"   ✅ RSA Private Key: {'Configured' if private_key_pem else 'Missing'}")
print(f"   ❌ Production Key: {'Configured' if prod_key else 'Missing'}")
print(f"   ❌ Production Secret: {'Configured' if prod_secret else 'Missing'}")

print(f"\n📊 Kalshi Trading Capability:")
has_rsa = bool(private_key_pem and api_key_id)
has_prod = bool(prod_key and prod_secret)

if has_rsa or has_prod:
    print(f"   ✅ Authentication credentials configured")
else:
    print(f"   ❌ No working authentication method")

print(f"\n🎯 Recommendations:")
if not has_rsa and not has_prod:
    print(f"   1. Generate Kalshi API keys at https://kalshi.com/account/api-keys")
    print(f"   2. Add KALSHI_PRODUCTION_API_KEY and KALSHI_PRODUCTION_API_SECRET")
    print(f"   3. Or: Use the existing RSA key with KALSHI_API_KEY_ID")
elif has_rsa:
    print(f"   1. ✅ RSA key configured - test authentication")
    print(f"   2. Install: pip install cryptography")
    print(f"   3. Run the trader with RSA auth")
elif has_prod:
    print(f"   1. ✅ Production keys configured")
    print(f"   2. Test login endpoint")
    print(f"   3. Check account balances")

print(f"\n🔗 Kalshi API Documentation:")
print(f"   https://trading-api.kalshi.com/trade-api/v2/docs")
print(f"   https://docs.kalshi.com/")
