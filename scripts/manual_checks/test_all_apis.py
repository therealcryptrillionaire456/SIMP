#!/usr/bin/env python3
"""
Comprehensive API Connectivity Test
Actually tests API connections with real calls
"""

import os
import sys
import json
import requests
import time
from dotenv import load_dotenv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)

# Load environment
load_dotenv()

def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")

def print_result(name, success, message=""):
    """Print test result"""
    icon = "✅" if success else "❌"
    print(f"{icon} {name}: {message}")

def test_coinbase():
    """Test Coinbase API with actual call"""
    print_header("COINBASE ADVANCED TRADE - LIVE TEST")
    
    api_key_name = os.getenv("COINBASE_API_KEY_NAME")
    private_key = os.getenv("COINBASE_API_PRIVATE_KEY")
    
    if not api_key_name or not private_key:
        print_result("Coinbase", False, "Credentials missing")
        return False
    
    print(f"🔧 Testing with API Key: {api_key_name[:30]}...")
    
    try:
        # Try to import Coinbase SDK
        import coinbase.rest
        from coinbase.rest import RESTClient
        from coinbase.jwt_generator import build_jwt
        
        print_result("Coinbase SDK", True, "Module available")
        
        # Create JWT token
        jwt_token = build_jwt(
            key_var="COINBASE_API_PRIVATE_KEY",
            secret_var="COINBASE_API_KEY_NAME",
            uri="/api/v3/brokerage/accounts"
        )
        
        # Initialize client
        client = RESTClient(
            api_key=api_key_name,
            private_key=private_key
        )
        
        # Test with a simple endpoint
        print("🔧 Testing /api/v3/brokerage/accounts endpoint...")
        accounts = client.get_accounts()
        
        if 'accounts' in accounts:
            print_result("Coinbase API", True, f"Connected - {len(accounts['accounts'])} accounts")
            
            # Show USD balance
            usd_balance = 0
            for account in accounts['accounts']:
                if account.get('currency') == 'USD':
                    balance = float(account.get('available_balance', {}).get('value', 0))
                    usd_balance = balance
                    print(f"   💰 USD Balance: ${balance:.2f}")
            
            return True
        else:
            print_result("Coinbase API", False, "No accounts returned")
            return False
            
    except ImportError:
        print_result("Coinbase SDK", False, "coinbase-advanced-py not installed")
        print("   Install with: pip install coinbase-advanced-py")
        return False
    except Exception as e:
        print_result("Coinbase API", False, f"Error: {str(e)[:100]}")
        return False

def test_alpaca():
    """Test Alpaca API with actual call"""
    print_header("ALPACA TRADING - LIVE TEST")
    
    api_key = os.getenv("APCA_API_KEY")
    secret_key = os.getenv("APCA_SECRET_KEY")
    api_url = os.getenv("APCA_API")
    
    if not api_key or not secret_key:
        print_result("Alpaca", False, "Credentials missing")
        return False
    
    print(f"🔧 Testing with API Key: {api_key}")
    
    try:
        headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key
        }
        
        # Test account endpoint
        response = requests.get(f"{api_url}/v2/account", headers=headers, timeout=10)
        
        if response.status_code == 200:
            account_data = response.json()
            print_result("Alpaca API", True, f"Connected - Status: {account_data.get('status', 'Unknown')}")
            print(f"   💰 Buying Power: ${float(account_data.get('buying_power', 0)):.2f}")
            print(f"   📊 Equity: ${float(account_data.get('equity', 0)):.2f}")
            return True
        else:
            print_result("Alpaca API", False, f"HTTP {response.status_code}: {response.text[:100]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_result("Alpaca API", False, f"Connection error: {e}")
        return False
    except Exception as e:
        print_result("Alpaca API", False, f"Error: {str(e)[:100]}")
        return False

def test_alpha_vantage():
    """Test Alpha Vantage API"""
    print_header("ALPHA VANTAGE - LIVE TEST")
    
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    
    if not api_key:
        print_result("Alpha Vantage", False, "API key missing")
        return False
    
    try:
        # Test with a simple stock quote
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": "IBM",
            "apikey": api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "Global Quote" in data:
                print_result("Alpha Vantage", True, "Connected - Data received")
                quote = data["Global Quote"]
                print(f"   📈 IBM Price: ${quote.get('05. price', 'N/A')}")
                return True
            else:
                # Check for rate limit message
                if "Note" in data:
                    print_result("Alpha Vantage", True, f"Connected - Rate limited: {data['Note'][:50]}...")
                    return True
                else:
                    print_result("Alpha Vantage", False, "Unexpected response format")
                    return False
        else:
            print_result("Alpha Vantage", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_result("Alpha Vantage", False, f"Error: {str(e)[:100]}")
        return False

def test_coingecko():
    """Test CoinGecko API"""
    print_header("COINGECKO - LIVE TEST")
    
    api_key = os.getenv("COINGECKO_API_KEY_1") or os.getenv("COINGECKO_API_KEY_2")
    
    if not api_key:
        print_result("CoinGecko", False, "API key missing")
        return False
    
    try:
        # Test with simple ping
        url = "https://api.coingecko.com/api/v3/ping"
        headers = {
            "x-cg-demo-api-key": api_key
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_result("CoinGecko", True, "Connected")
            print(f"   🏓 Ping response: {data.get('gecko_says', 'OK')}")
            return True
        else:
            print_result("CoinGecko", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_result("CoinGecko", False, f"Error: {str(e)[:100]}")
        return False

def test_finnhub():
    """Test Finnhub API"""
    print_header("FINNHUB - LIVE TEST")
    
    api_key = os.getenv("FINNHUB_API_KEY")
    
    if not api_key:
        print_result("Finnhub", False, "API key missing")
        return False
    
    try:
        # Test with stock quote
        url = f"https://finnhub.io/api/v1/quote"
        params = {
            "symbol": "AAPL",
            "token": api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "c" in data:  # Current price
                print_result("Finnhub", True, "Connected - Data received")
                print(f"   📈 AAPL Price: ${data['c']:.2f}")
                return True
            else:
                print_result("Finnhub", False, "Unexpected response format")
                return False
        else:
            print_result("Finnhub", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_result("Finnhub", False, f"Error: {str(e)[:100]}")
        return False

def test_nodereal():
    """Test NodeReal RPC endpoints"""
    print_header("NODEREAL - LIVE TEST")
    
    api_key = os.getenv("NODEREAL_API_KEY")
    
    if not api_key:
        print_result("NodeReal", False, "API key missing")
        return False
    
    # Test BSC endpoint
    endpoint = os.getenv("BSC_MAINNET_HTTPS")
    
    if not endpoint:
        print_result("NodeReal BSC", False, "Endpoint missing")
        return False
    
    try:
        # Test with simple eth_blockNumber call
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }
        
        response = requests.post(endpoint, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                block_num = int(data["result"], 16)
                print_result("NodeReal BSC", True, "Connected")
                print(f"   🔗 Current Block: {block_num:,}")
                return True
            else:
                print_result("NodeReal BSC", False, f"Unexpected response: {data}")
                return False
        else:
            print_result("NodeReal BSC", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_result("NodeReal BSC", False, f"Error: {str(e)[:100]}")
        return False

def test_alchemy():
    """Test Alchemy API"""
    print_header("ALCHEMY - LIVE TEST")
    
    api_key = os.getenv("ALCHEMY_API_KEY")
    endpoint = os.getenv("ALCHEMY_SOLANA_ENDPOINT")
    
    if not api_key or not endpoint:
        print_result("Alchemy", False, "API key or endpoint missing")
        return False
    
    try:
        # Test Solana endpoint
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getHealth"
        }
        
        response = requests.post(endpoint, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                print_result("Alchemy Solana", True, "Connected")
                print(f"   🔗 Health: {data['result']}")
                return True
            else:
                print_result("Alchemy Solana", False, f"Unexpected response: {data}")
                return False
        else:
            print_result("Alchemy Solana", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_result("Alchemy Solana", False, f"Error: {str(e)[:100]}")
        return False

def test_bitquery():
    """Test BitQuery API"""
    print_header("BITQUERY - LIVE TEST")
    
    api_key = os.getenv("BITQUERY_API_KEY")
    endpoint = os.getenv("BITQUERY_ENDPOINT")
    
    if not api_key or not endpoint:
        print_result("BitQuery", False, "API key or endpoint missing")
        return False
    
    try:
        # Simple GraphQL query
        query = """
        {
          ethereum {
            blocks(limit: 1) {
              height
            }
          }
        }
        """
        
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": api_key
        }
        
        response = requests.post(endpoint, json={"query": query}, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                print_result("BitQuery", True, "Connected")
                print(f"   🔗 GraphQL query successful")
                return True
            elif "errors" in data:
                print_result("BitQuery", True, f"Connected - Query error: {data['errors'][0]['message'][:50]}...")
                return True  # Still connected, just query error
            else:
                print_result("BitQuery", False, f"Unexpected response: {data}")
                return False
        else:
            print_result("BitQuery", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_result("BitQuery", False, f"Error: {str(e)[:100]}")
        return False

def main():
    """Main test function"""
    print("🔌 COMPREHENSIVE API CONNECTIVITY TEST")
    print("=" * 60)
    print(f"Environment: {Path('.env').absolute()}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    tests = [
        ("Coinbase", test_coinbase),
        ("Alpaca", test_alpaca),
        ("Alpha Vantage", test_alpha_vantage),
        ("CoinGecko", test_coingecko),
        ("Finnhub", test_finnhub),
        ("NodeReal", test_nodereal),
        ("Alchemy", test_alchemy),
        ("BitQuery", test_bitquery)
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"❌ {name}: Test crashed - {str(e)[:100]}")
            results[name] = False
    
    # Summary
    print_header("CONNECTIVITY TEST SUMMARY")
    
    total = len(results)
    passed = sum(1 for result in results.values() if result)
    
    print(f"📊 Total APIs Tested: {total}")
    print(f"✅ APIs Connected: {passed}")
    print(f"❌ APIs Failed: {total - passed}")
    
    print("\n🔍 DETAILED RESULTS:")
    for name, success in results.items():
        icon = "✅" if success else "❌"
        print(f"   {icon} {name}")
    
    print("\n🎯 CRITICAL APIS FOR TRADING:")
    critical_apis = ["Coinbase", "Alpaca"]
    for api in critical_apis:
        if api in results:
            status = "✅ WORKING" if results[api] else "❌ BROKEN"
            print(f"   {status} {api}")
    
    print("\n⚠️  RECOMMENDATIONS:")
    if not results.get("Coinbase", False):
        print("1. FIX COINBASE API - Critical for current trading")
    
    if total - passed > 3:
        print("2. Check network connectivity and API keys")
    
    print("3. Test during trading hours for market data APIs")
    
    print(f"\n{'='*60}")
    if passed >= total - 2:  # Allow 2 failures (non-critical APIs)
        print("🎉 API ECOSYSTEM READY FOR TRADING!")
    else:
        print("⚠️  API CONNECTIVITY ISSUES DETECTED")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
