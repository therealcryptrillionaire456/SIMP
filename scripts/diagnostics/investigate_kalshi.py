#!/usr/bin/env python3
"""
Kalshi API Investigation - Comprehensive connection test
"""

import os
import sys
import json
import requests
import time
import hmac
import hashlib
from pathlib import Path

# Read .env file directly
def load_env_file():
    """Load environment variables from .env"""
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found")
        return {}
    
    env_vars = {}
    current_key = None
    current_value = []
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                if current_key:
                    env_vars[current_key] = '\n'.join(current_value)
                key, value = line.split('=', 1)
                current_key = key.strip()
                current_value = [value.strip()]
            elif current_key:
                current_value.append(line)
    
    if current_key:
        env_vars[current_key] = '\n'.join(current_value)
    
    return env_vars

env = load_env_file()

def print_header(text):
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")

def print_result(name, success, message=""):
    icon = "✅" if success else "❌"
    print(f"{icon} {name}: {message}")

# Step 1: Check Kalshi Credentials
print_header("STEP 1: KALSHI CREDENTIALS CHECK")

kalshi_api_key_id = env.get("KALSHI_API_KEY_ID", "")
kalshi_prod_key = env.get("KALSHI_PRODUCTION_API_KEY", "")
kalshi_prod_secret = env.get("KALSHI_PRODUCTION_API_SECRET", "")

print(f"📋 KALSHI_API_KEY_ID: {kalshi_api_key_id}")
print(f"📋 KALSHI_PRODUCTION_API_KEY: {'Configured' if kalshi_prod_key else 'NOT SET'}")
print(f"📋 KALSHI_PRODUCTION_API_SECRET: {'Configured' if kalshi_prod_secret else 'NOT SET'}")
print(f"📋 KALSHI_SANDBOX_API_KEY: {'Configured' if env.get('KALSHI_SANDBOX_API_KEY') else 'NOT SET'}")
print(f"📋 KALSHI_SANDBOX_API_SECRET: {'Configured' if env.get('KALSHI_SANDBOX_API_SECRET') else 'NOT SET'}")

if not kalshi_prod_key or not kalshi_prod_secret:
    print("\n⚠️  Kalshi production keys are NOT configured.")
    print("   The system has KALSHI_API_KEY_ID but is missing:")
    print("   - KALSHI_PRODUCTION_API_KEY")
    print("   - KALSHI_PRODUCTION_API_SECRET")
    print("\n   The KALSHI_API_KEY_ID alone is NOT sufficient for trading.")
    print("   You need to generate API keys from the Kalshi dashboard.")
    
    # Check if there are any Kalshi-related files
    print("\n🔍 Searching for Kalshi-related files...")
    kalshi_files = list(Path('.').rglob('*kalshi*'))
    if kalshi_files:
        print(f"   Found {len(kalshi_files)} Kalshi files:")
        for f in kalshi_files[:5]:
            print(f"      • {f}")
    else:
        print("   No Kalshi files found")
    
    print("\n❌ KALSHI TRADING NOT POSSIBLE - Missing credentials")
    sys.exit(1)

# Step 2: Test Kalshi API Connection
print_header("STEP 2: KALSHI API CONNECTION TEST")

# Kalshi endpoints
KALSHI_API_BASE = "https://trading-api.kalshi.com/trade-api/v2"
KALSHI_REST_ENDPOINT = "https://api.kalshi.com"

print(f"🔧 Testing Kalshi API endpoints...")

# Test 1: Basic connectivity to rest endpoint
try:
    response = requests.get(f"{KALSHI_REST_ENDPOINT}/health", timeout=10)
    print(f"   GET /health -> HTTP {response.status_code}")
    if response.status_code == 200:
        print_result("Kalshi REST Health", True, "Server reachable")
    else:
        print_result("Kalshi REST Health", True, f"Server responded ({response.status_code})")
except Exception as e:
    print_result("Kalshi REST Health", False, f"Connection error: {str(e)[:50]}")

# Test 2: Check trade-api endpoint
try:
    response = requests.get(f"{KALSHI_API_BASE}", timeout=10)
    print(f"   GET /trade-api/v2 -> HTTP {response.status_code}")
except Exception as e:
    print(f"   GET /trade-api/v2 -> Error: {str(e)[:50]}")

# Test 3: Try to get exchange status (public endpoint)
try:
    response = requests.get(f"{KALSHI_API_BASE}/exchange/status", timeout=10)
    print(f"   GET /exchange/status -> HTTP {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"      Status: {json.dumps(data, indent=2)[:200]}")
        print_result("Kalshi Exchange Status", True, "Public endpoint reachable")
except Exception as e:
    print_result("Kalshi Exchange Status", False, f"Error: {str(e)[:50]}")

# Test 4: Try to get events (public endpoint)
try:
    response = requests.get(f"{KALSHI_API_BASE}/events", params={"limit": 1}, timeout=10)
    print(f"   GET /events -> HTTP {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if 'events' in data:
            total_events = len(data['events'])
            status = data.get('status', '')
            print(f"      Events: {total_events} in response")
            print_result("Kalshi Events API", True, "Public events available")
except Exception as e:
    print_result("Kalshi Events API", False, f"Error: {str(e)[:50]}")

# Step 3: Test Kalshi Authentication
print_header("STEP 3: KALSHI AUTHENTICATION TEST")

print(f"🔧 Using API Key: {kalshi_prod_key[:10]}...{kalshi_prod_key[-5:]}")
print(f"🔧 Using Secret: {'*' * 10}...{'*' * 5}")

# Generate Kalshi auth headers
timestamp = int(time.time() * 1000)
method = "GET"
path = "/trade-api/v2/portfolio/balance"

# Create signature
message = f"{timestamp}{method}{path}"
signature = hmac.new(
    kalshi_prod_secret.encode('utf-8'),
    message.encode('utf-8'),
    hashlib.sha256
).hexdigest()

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "KLOUTBOT/1.0"
}

# Try different auth methods

# Method 1: API Key + Signature
print("\n🔄 Testing Method 1: API Key + Signature headers...")
try:
    auth_headers = {
        **headers,
        "KALSHI-API-KEY": kalshi_prod_key,
        "KALSHI-API-SIGNATURE": signature,
        "KALSHI-API-TIMESTAMP": str(timestamp)
    }
    
    response = requests.get(f"{KALSHI_API_BASE}/portfolio/balance", 
                          headers=auth_headers, timeout=10)
    print(f"   GET /portfolio/balance -> HTTP {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    if response.status_code == 200:
        data = response.json()
        print_result("Kalshi Auth Method 1", True, "Authenticated!")
        if 'balance' in data:
            print(f"   💰 Balance: ${data['balance']:.2f}")
        if 'available_balance' in data:
            print(f"   💰 Available: ${data['available_balance']:.2f}")
    elif response.status_code == 401:
        print_result("Kalshi Auth Method 1", False, "Authentication failed")
    else:
        print_result("Kalshi Auth Method 1", False, f"HTTP {response.status_code}")
except Exception as e:
    print_result("Kalshi Auth Method 1", False, f"Error: {str(e)[:50]}")

# Method 2: Basic Auth with key:secret
print("\n🔄 Testing Method 2: Basic Auth...")
try:
    basic_headers = {
        **headers,
        "Authorization": f"Basic {base64.b64encode(f'{kalshi_prod_key}:{kalshi_prod_secret}'.encode()).decode()}"
    }
    
    # Import base64 if not available
    import base64
    
    response = requests.get(f"{KALSHI_API_BASE}/portfolio/balance", 
                          headers=basic_headers, timeout=10)
    print(f"   GET /portfolio/balance -> HTTP {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    if response.status_code == 200:
        print_result("Kalshi Auth Method 2", True, "Authenticated via Basic Auth!")
    else:
        print_result("Kalshi Auth Method 2", False, f"HTTP {response.status_code}")
except Exception as e:
    import traceback
    print_result("Kalshi Auth Method 2", False, f"Error: {str(e)[:50]}")

# Method 3: Try the login endpoint
print("\n🔄 Testing Method 3: Login endpoint...")
try:
    login_data = {
        "api_key": kalshi_prod_key,
        "api_secret": kalshi_prod_secret
    }
    
    response = requests.post(f"{KALSHI_API_BASE}/login", 
                           json=login_data, headers=headers, timeout=10)
    print(f"   POST /login -> HTTP {response.status_code}")
    print(f"   Response: {response.text[:300]}")
    
    if response.status_code == 200:
        data = response.json()
        if 'token' in data:
            print_result("Kalshi Auth Method 3", True, "Got auth token!")
            print(f"      Token: {data['token'][:30]}...")
    else:
        print_result("Kalshi Auth Method 3", False, f"HTTP {response.status_code}")
except Exception as e:
    print_result("Kalshi Auth Method 3", False, f"Error: {str(e)[:50]}")

# Method 4: Try bearer token from the key itself
print("\n🔄 Testing Method 4: Bearer token...")
try:
    bearer_headers = {
        **headers,
        "Authorization": f"Bearer {kalshi_prod_key}"
    }
    
    response = requests.get(f"{KALSHI_API_BASE}/portfolio/balance", 
                          headers=bearer_headers, timeout=10)
    print(f"   GET /portfolio/balance -> HTTP {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    if response.status_code == 200:
        print_result("Kalshi Auth Method 4", True, "Authenticated via Bearer token!")
    else:
        print_result("Kalshi Auth Method 4", False, f"HTTP {response.status_code}")
except Exception as e:
    print_result("Kalshi Auth Method 4", False, f"Error: {str(e)[:50]}")

# Step 4: Summary and Recommendations
print_header("STEP 4: KALSHI SUMMARY")

if kalshi_prod_key and kalshi_prod_secret:
    print("✅ Kalshi production keys ARE configured")
    print("⚠️  But authentication method varies")
    print("💡 Check Kalshi documentation for exact auth method")
    print("   https://trading-api.kalshi.com/trade-api/v2")
else:
    print("❌ Kalshi production keys ARE NOT configured")
    print(f"   KALSHI_API_KEY_ID: {kalshi_api_key_id} (exists but NOT used for auth)")
    
print("\n📋 WHAT YOU NEED TO DO:")
print("1. Go to https://kalshi.com/account/api-keys")
print("2. Generate a new API key with trading permissions")
print("3. Add these to your .env file:")
print("   KALSHI_PRODUCTION_API_KEY=your_new_api_key")
print("   KALSHI_PRODUCTION_API_SECRET=your_new_api_secret")
print("\n4. Use the KALSHI_API_KEY_ID for identification")
print("5. The production keys for authentication")

print("\n🔍 Kalshi API Documentation:")
print("   https://trading-api.kalshi.com/trade-api/v2/docs")
print("   https://kalshi.com/docs/api")

print("\n💡 TIP: The Kalshi API typically uses:")
print("   - API Key ID for identification")
print("   - RSA or HMAC signature for authentication")
print("   - Or: Basic Auth with key:secret")

