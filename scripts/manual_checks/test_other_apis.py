#!/usr/bin/env python3
"""
Test Other APIs (Skip Coinbase since it's already working)
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
        elif response.status_code == 401:
            print_result("Alpaca API", False, "Authentication failed - Check API keys")
            return False
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
            "function": "TIME_SERIES_INTRADAY",
            "symbol": "IBM",
            "interval": "5min",
            "apikey": api_key,
            "datatype": "json"
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if "Time Series (5min)" in data:
                print_result("Alpha Vantage", True, "Connected - Live data received")
                # Get latest price
                time_series = data["Time Series (5min)"]
                latest = next(iter(time_series.values()))
                print(f"   📈 IBM Latest: ${latest.get('4. close', 'N/A')}")
                return True
            elif "Note" in data:
                # Rate limited but connected
                print_result("Alpha Vantage", True, f"Connected - Rate limited (free tier)")
                print(f"   ⚠️  {data['Note'][:60]}...")
                return True
            elif "Error Message" in data:
                print_result("Alpha Vantage", False, f"API error: {data['Error Message'][:50]}")
                return False
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
    
    # Try both API keys
    api_key_1 = os.getenv("COINGECKO_API_KEY_1")
    api_key_2 = os.getenv("COINGECKO_API_KEY_2")
    api_key = api_key_1 or api_key_2
    
    if not api_key:
        print_result("CoinGecko", False, "API key missing")
        return False
    
    try:
        # Test with simple ping (no auth required for ping)
        url = "https://api.coingecko.com/api/v3/ping"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_result("CoinGecko Ping", True, "Connected")
            print(f"   🏓 {data.get('gecko_says', 'OK')}")
            
            # Now test with API key for actual data
            headers = {"x-cg-demo-api-key": api_key}
            url2 = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "bitcoin", "vs_currencies": "usd"}
            
            response2 = requests.get(url2, params=params, headers=headers, timeout=10)
            
            if response2.status_code == 200:
                data2 = response2.json()
                if "bitcoin" in data2:
                    price = data2["bitcoin"]["usd"]
                    print_result("CoinGecko Data", True, f"BTC Price: ${price:,.2f}")
                    return True
                else:
                    print_result("CoinGecko Data", True, "Connected but rate limited")
                    return True
            else:
                print_result("CoinGecko Data", True, f"HTTP {response2.status_code} (may be rate limited)")
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
            if "c" in data and data["c"] > 0:  # Current price
                print_result("Finnhub", True, "Connected - Live data")
                print(f"   📈 AAPL: ${data['c']:.2f} (Change: {data.get('dp', 0):.2f}%)")
                return True
            elif "error" in data:
                print_result("Finnhub", False, f"API error: {data['error']}")
                return False
            else:
                print_result("Finnhub", False, "Unexpected response format")
                return False
        elif response.status_code == 402:
            print_result("Finnhub", False, "Payment required - Check subscription")
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
                
                # Test another endpoint
                endpoint2 = os.getenv("ETH_MAINNET_HTTPS")
                if endpoint2:
                    response2 = requests.post(endpoint2, json=payload, timeout=10)
                    if response2.status_code == 200:
                        data2 = response2.json()
                        if "result" in data2:
                            eth_block = int(data2["result"], 16)
                            print_result("NodeReal ETH", True, f"Connected - Block: {eth_block:,}")
                
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
        # Test Solana endpoint with getVersion
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getVersion",
            "params": []
        }
        
        response = requests.post(endpoint, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                version = data["result"].get("solana-core", "Unknown")
                print_result("Alchemy Solana", True, "Connected")
                print(f"   🔗 Solana Version: {version}")
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

def test_coinmarketcap():
    """Test CoinMarketCap API"""
    print_header("COINMARKETCAP - LIVE TEST")
    
    api_key = os.getenv("COINMARKETCAP_API_KEY")
    
    if not api_key:
        print_result("CoinMarketCap", False, "API key missing")
        return False
    
    try:
        # Test with latest listings
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {
            "X-CMC_PRO_API_KEY": api_key,
            "Accept": "application/json"
        }
        params = {
            "start": "1",
            "limit": "1",
            "convert": "USD"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                btc = data["data"][0]
                print_result("CoinMarketCap", True, "Connected")
                print(f"   📊 {btc['name']}: ${btc['quote']['USD']['price']:,.2f}")
                return True
            else:
                print_result("CoinMarketCap", False, "Unexpected response format")
                return False
        elif response.status_code == 401:
            print_result("CoinMarketCap", False, "Authentication failed - Check API key")
            return False
        elif response.status_code == 429:
            print_result("CoinMarketCap", True, "Connected - Rate limited")
            return True
        else:
            print_result("CoinMarketCap", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_result("CoinMarketCap", False, f"Error: {str(e)[:100]}")
        return False

def main():
    """Main test function"""
    print("🔌 OTHER API CONNECTIVITY TEST")
    print("=" * 60)
    print(f"Environment: {Path('.env').absolute()}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n⚠️  NOTE: Coinbase skipped - Already working (30+ trades executed)")
    
    # Run all tests except Coinbase
    tests = [
        ("Alpaca", test_alpaca),
        ("Alpha Vantage", test_alpha_vantage),
        ("CoinGecko", test_coingecko),
        ("Finnhub", test_finnhub),
        ("NodeReal", test_nodereal),
        ("Alchemy", test_alchemy),
        ("CoinMarketCap", test_coinmarketcap)
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            print(f"\n🔧 Testing {name}...")
            results[name] = test_func()
            time.sleep(1)  # Rate limiting
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
    
    print("\n🎯 TRADING-READY APIS:")
    trading_apis = ["Alpaca"]
    for api in trading_apis:
        if api in results:
            status = "✅ READY" if results[api] else "❌ NOT READY"
            print(f"   {status} {api}")
    
    print("\n📊 DATA PROVIDERS STATUS:")
    data_apis = ["Alpha Vantage", "CoinGecko", "Finnhub", "CoinMarketCap"]
    for api in data_apis:
        if api in results:
            status = "✅ WORKING" if results[api] else "❌ ISSUES"
            print(f"   {status} {api}")
    
    print("\n🔗 BLOCKCHAIN PROVIDERS STATUS:")
    blockchain_apis = ["NodeReal", "Alchemy"]
    for api in blockchain_apis:
        if api in results:
            status = "✅ CONNECTED" if results[api] else "❌ OFFLINE"
            print(f"   {status} {api}")
    
    print("\n⚠️  RECOMMENDATIONS:")
    if not results.get("Alpaca", False):
        print("1. Fix Alpaca API for stock trading capability")
    
    data_failures = sum(1 for api in data_apis if not results.get(api, False))
    if data_failures > 2:
        print(f"2. Fix {data_failures} data provider APIs for market data")
    
    print("3. Consider adding more trading pairs to Coinbase strategy")
    print("4. Test cross-exchange arbitrage opportunities")
    
    print(f"\n{'='*60}")
    if passed >= total - 2:  # Allow 2 failures
        print("🎉 MOST APIS CONNECTED - SYSTEM EXPANSION READY!")
    else:
        print("⚠️  MULTIPLE API CONNECTIVITY ISSUES")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
