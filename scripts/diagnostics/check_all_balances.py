#!/usr/bin/env python3
"""
Comprehensive wallet balance checker for all external systems:
1. Coinbase Advanced Trade
2. Kalshi Prediction Markets
3. Solana Wallets
4. Other configured exchanges
"""

import os
import sys
import json
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv()

def check_coinbase_balance():
    """Check Coinbase Advanced Trade balance"""
    print("\n=== COINBASE ADVANCED TRADE ===")
    
    api_key_name = os.getenv("COINBASE_API_KEY_NAME")
    private_key = os.getenv("COINBASE_API_PRIVATE_KEY")
    
    if not api_key_name or not private_key:
        print("❌ Coinbase credentials not configured")
        return None
    
    print(f"✅ API Key Name: {api_key_name}")
    print(f"✅ Private Key: {'Configured' if private_key else 'Missing'}")
    
    # Try to import Coinbase module
    try:
        import coinbase.rest
        from coinbase.rest import RESTClient
        from coinbase.jwt_generator import build_jwt
        
        print("✅ Coinbase module available")
        
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
        
        # Get accounts
        accounts = client.get_accounts()
        print(f"✅ Accounts retrieved: {len(accounts.get('accounts', []))}")
        
        # Calculate total balance
        total_usd = 0
        for account in accounts.get('accounts', []):
            currency = account.get('currency', '')
            balance = float(account.get('available_balance', {}).get('value', 0))
            if currency == 'USD':
                total_usd += balance
            elif currency in ['BTC', 'ETH', 'SOL']:
                # For crypto, we'd need current prices
                print(f"   {currency}: {balance}")
        
        print(f"💰 Total USD Balance: ${total_usd:.2f}")
        return total_usd
        
    except ImportError:
        print("❌ Coinbase Python SDK not installed")
        print("   Install with: pip install coinbase-advanced-py")
    except Exception as e:
        print(f"❌ Coinbase API error: {e}")
    
    return None

def check_kalshi_balance():
    """Check Kalshi prediction markets balance"""
    print("\n=== KALSHI PREDICTION MARKETS ===")
    
    api_key = os.getenv("KALSHI_PRODUCTION_API_KEY")
    api_secret = os.getenv("KALSHI_PRODUCTION_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Kalshi credentials not configured")
        return None
    
    print(f"✅ API Key: {'Configured' if api_key else 'Missing'}")
    print(f"✅ API Secret: {'Configured' if api_secret else 'Missing'}")
    
    # Note: Kalshi API would require actual implementation
    print("⚠️ Kalshi balance check requires API implementation")
    
    return None

def check_solana_balance():
    """Check Solana wallet balance"""
    print("\n=== SOLANA WALLET ===")
    
    wallet_address = os.getenv("SOLANA_WALLET_ADDRESS")
    private_key = os.getenv("SOLANA_PRIVATE_KEY")
    
    if not wallet_address:
        print("❌ Solana wallet address not configured")
        return None
    
    print(f"✅ Wallet Address: {wallet_address}")
    print(f"✅ Private Key: {'Configured' if private_key else 'Missing'}")
    
    # Note: Solana balance check would require web3.py or similar
    print("⚠️ Solana balance check requires web3.py implementation")
    
    return None

def check_system_wallets():
    """Check for any system wallet files"""
    print("\n=== SYSTEM WALLET FILES ===")
    
    repo_path = Path(__file__).parent
    wallet_files = []
    
    # Search for wallet-related files
    for pattern in ["*.json", "*.env*", "*.txt", "*.pem", "*.key"]:
        for file in repo_path.rglob(pattern):
            if file.is_file():
                try:
                    content = file.read_text()
                    if any(keyword in content.lower() for keyword in 
                          ["wallet", "private", "secret", "0x", "key-----"]):
                        wallet_files.append(str(file.relative_to(repo_path)))
                except:
                    pass
    
    if wallet_files:
        print(f"✅ Found {len(wallet_files)} wallet-related files:")
        for file in wallet_files[:10]:  # Show first 10
            print(f"   • {file}")
        if len(wallet_files) > 10:
            print(f"   ... and {len(wallet_files) - 10} more")
    else:
        print("❌ No wallet files found")
    
    return wallet_files

def main():
    """Main balance checking function"""
    print("🔍 COMPREHENSIVE WALLET BALANCE CHECK")
    print("=" * 50)
    
    # Check current environment
    print("\n=== ENVIRONMENT CHECK ===")
    env_vars = [
        "COINBASE_API_KEY_NAME",
        "COINBASE_API_PRIVATE_KEY", 
        "KALSHI_PRODUCTION_API_KEY",
        "KALSHI_PRODUCTION_API_SECRET",
        "SOLANA_WALLET_ADDRESS",
        "SOLANA_PRIVATE_KEY"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value and len(value) > 10:
            print(f"✅ {var}: Configured")
        elif value:
            print(f"⚠️  {var}: Set but short ({len(value)} chars)")
        else:
            print(f"❌ {var}: Not set")
    
    # Check balances
    coinbase_balance = check_coinbase_balance()
    kalshi_balance = check_kalshi_balance()
    solana_balance = check_solana_balance()
    wallet_files = check_system_wallets()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 BALANCE CHECK SUMMARY")
    print("=" * 50)
    
    if coinbase_balance is not None:
        print(f"💰 Coinbase: ${coinbase_balance:.2f}")
    else:
        print("💰 Coinbase: Not available")
    
    print("💰 Kalshi: Not configured")
    print("💰 Solana: Not configured")
    
    print(f"\n📁 Wallet files found: {len(wallet_files)}")
    
    print("\n⚠️  RECOMMENDATIONS:")
    print("1. Configure Kalshi API keys in .env file")
    print("2. Add Solana wallet address and private key")
    print("3. Test Coinbase API connectivity")
    print("4. Secure all private keys and wallet files")

if __name__ == "__main__":
    main()
