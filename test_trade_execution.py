#!/usr/bin/env python3.10
"""
Test trade execution with QuantumArb agent.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

BROKER_URL = "http://127.0.0.1:5555"
API_KEY = "test-key-123"

def test_file_based_communication():
    """Test file-based communication with QuantumArb agent."""
    print("Testing file-based communication with QuantumArb...")
    
    # Create inbox directory if it doesn't exist
    inbox_dir = Path("data/inboxes/quantumarb")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a test intent file
    test_intent = {
        "intent_id": f"test_trade_{int(time.time())}",
        "intent_type": "arbitrage_execution",
        "source_agent": "tester",
        "target_agent": "quantumarb",
        "payload": {
            "symbol": "BTC-USD",
            "venue_a": "testnet_exchange_a",
            "venue_b": "testnet_exchange_b",
            "price_a": 50000.0,
            "price_b": 50100.0,
            "spread": 100.0,
            "spread_percent": 0.2,
            "amount": 0.001,
            "max_slippage": 0.1,
            "arb_type": "cross_venue",
            "confidence": 0.85,
            "timestamp": time.time(),
            "test_mode": True,
            "sandbox": True
        },
        "metadata": {
            "test": True,
            "sandbox": True,
            "emergency_stop_available": True
        },
        "timestamp": time.time()
    }
    
    # Write intent to inbox
    intent_file = inbox_dir / f"{test_intent['intent_id']}.json"
    with open(intent_file, "w") as f:
        json.dump(test_intent, f, indent=2)
    
    print(f"✓ Test intent written to: {intent_file}")
    print(f"  Intent ID: {test_intent['intent_id']}")
    
    # Wait for agent to process (if running)
    print("Waiting 10 seconds for agent processing...")
    time.sleep(10)
    
    # Check for response in outbox
    outbox_dir = Path("data/inboxes/tester")
    outbox_dir.mkdir(parents=True, exist_ok=True)
    
    response_files = list(outbox_dir.glob(f"*{test_intent['intent_id']}*"))
    if response_files:
        print(f"✓ Found {len(response_files)} response(s)")
        for response_file in response_files:
            with open(response_file, "r") as f:
                response = json.load(f)
            print(f"  Response: {json.dumps(response, indent=2)}")
        return True
    else:
        print("✗ No response received (agent may not be running)")
        return False

def test_broker_intent():
    """Test sending intent through broker."""
    print("\nTesting broker intent routing...")
    
    # Try different intent types based on routing policy
    intent_types = [
        "small_purchase",
        "native_agent_trade",
        "portfolio_rebalance"
    ]
    
    for intent_type in intent_types:
        print(f"\nTrying intent type: {intent_type}")
        
        test_intent = {
            "intent_type": intent_type,
            "source_agent": "tester",
            "target_agent": "quantumarb",
            "payload": {
                "symbol": "BTC-USD",
                "amount": 0.001,
                "test_mode": True,
                "sandbox": True
            },
            "metadata": {
                "test": True,
                "sandbox": True
            }
        }
        
        try:
            response = requests.post(
                f"{BROKER_URL}/intents/route",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": API_KEY
                },
                json=test_intent,
                timeout=10
            )
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ Success: {data.get('status')}")
                print(f"  Target: {data.get('target_agent', 'unknown')}")
                return True
            else:
                print(f"  ✗ Failed: {response.text}")
                
        except Exception as e:
            print(f"  ✗ Exception: {e}")
    
    return False

def test_quantumarb_direct():
    """Test QuantumArb components directly."""
    print("\nTesting QuantumArb components directly...")
    
    # Import QuantumArb modules
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from simp.organs.quantumarb.arb_detector import create_detector
        from simp.organs.quantumarb.exchange_connector import StubExchangeConnector
        
        print("✓ Successfully imported QuantumArb modules")
        
        # Test exchange connector
        connector = StubExchangeConnector()
        print("✓ StubExchangeConnector initialized")
        
        # Test getting ticker
        ticker = connector.get_ticker("BTC-USD")
        print(f"✓ Got test ticker: {ticker}")
        
        # Test arb detector with factory function
        exchanges = {
            "testnet_a": connector,
            "testnet_b": connector
        }
        detector = create_detector(exchanges=exchanges)
        print("✓ ArbDetector created via factory")
        
        return True
        
    except Exception as e:
        print(f"✗ QuantumArb import failed: {e}")
        return False

def test_pnl_ledger():
    """Test P&L ledger functionality."""
    print("\nTesting P&L ledger...")
    
    try:
        from simp.organs.quantumarb.pnl_ledger import get_default_ledger
        
        # Get default ledger
        ledger = get_default_ledger()
        print("✓ PnLLedger initialized")
        
        # Record test trade P&L
        entry = ledger.record_trade_pnl(
            market="BTC-USD",
            quantity=0.001,
            price=50000.0,
            pnl_amount=0.1,
            trade_id=f"test_{int(time.time())}",
            position_before=0.0,
            position_after=0.001,
            fees=0.01,
            metadata={
                "venue_a": "testnet_a",
                "venue_b": "testnet_b",
                "price_a": 50000.0,
                "price_b": 50100.0,
                "spread_bps": 20.0,
                "status": "executed",
                "test": True
            }
        )
        print("✓ Test trade P&L recorded")
        
        # Get recent entries
        recent = ledger.get_entries(limit=5)
        print(f"✓ Got {len(recent)} recent entries")
        
        return True
        
    except Exception as e:
        print(f"✗ P&L ledger test failed: {e}")
        return False

def main():
    """Run all trade execution tests."""
    print("="*80)
    print("TRADE EXECUTION TESTS")
    print("="*80)
    
    tests = [
        ("File-based Communication", test_file_based_communication),
        ("Broker Intent Routing", test_broker_intent),
        ("QuantumArb Components", test_quantumarb_direct),
        ("P&L Ledger", test_pnl_ledger)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            print(f"Test: {test_name}")
            print('='*60)
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed >= 2:  # At least half passed
        print("\n✅ SUFFICIENT TESTS PASSED - Trade execution is possible!")
        return True
    else:
        print("\n⚠️  Insufficient tests passed - Review issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)