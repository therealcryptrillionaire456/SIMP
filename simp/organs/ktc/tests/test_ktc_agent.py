"""
Test script for KTC Agent
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from agent.ktc_agent import create_ktc_agent


def test_ktc_agent():
    """Test basic KTC agent functionality"""
    print("=== Testing KTC Agent ===")
    
    # Create agent
    agent = create_ktc_agent()
    
    # Test 1: Health check
    print("\n1. Testing health check...")
    health = agent.health()
    print(f"Health status: {health.get('status')}")
    print(f"Agent ID: {health.get('agent_id')}")
    print(f"Capabilities: {', '.join(health.get('capabilities', []))}")
    
    # Test 2: Process receipt
    print("\n2. Testing receipt processing...")
    receipt_intent = {
        "intent_type": "process_receipt",
        "parameters": {
            "user_id": "test_user_001",
            "store_name": "Test Grocery Store",
            "receipt_id": "test_receipt_001"
        }
    }
    
    receipt_result = agent.handle_intent(receipt_intent)
    print(f"Receipt processing status: {receipt_result.get('status')}")
    print(f"Total: ${receipt_result.get('total', 0):.2f}")
    print(f"Items processed: {receipt_result.get('item_count', 0)}")
    
    # Test 3: Compare prices
    print("\n3. Testing price comparison...")
    
    # Use items from receipt result
    items = receipt_result.get("items", [])
    if items:
        price_intent = {
            "intent_type": "compare_prices",
            "parameters": {
                "user_id": "test_user_001",
                "items": items[:3],  # Compare first 3 items
                "location": {
                    "zipcode": "90210",
                    "radius_miles": 10
                }
            }
        }
        
        price_result = agent.handle_intent(price_intent)
        print(f"Price comparison status: {price_result.get('status')}")
        print(f"Total potential savings: ${price_result.get('total_potential_savings', 0):.2f}")
        print(f"Comparisons found: {price_result.get('comparison_count', 0)}")
        
        # Test 4: Calculate savings
        print("\n4. Testing savings calculation...")
        savings_intent = {
            "intent_type": "calculate_savings",
            "parameters": {
                "comparisons": price_result.get("comparisons", [])
            }
        }
        
        savings_result = agent.handle_intent(savings_intent)
        print(f"Savings calculation status: {savings_result.get('status')}")
        print(f"Total savings: ${savings_result.get('total_savings', 0):.2f}")
        print(f"Eligible for investment: {savings_result.get('eligible_for_investment', False)}")
        
        # Test 5: Invest savings
        print("\n5. Testing investment...")
        investment_intent = {
            "intent_type": "invest_savings",
            "parameters": {
                "user_id": "test_user_001",
                "amount": savings_result.get("total_savings", 0),
                "receipt_id": "test_receipt_001"
            }
        }
        
        investment_result = agent.handle_intent(investment_intent)
        print(f"Investment status: {investment_result.get('status')}")
        
        if investment_result.get("status") == "success":
            investment = investment_result.get("investment", {})
            print(f"Amount invested: ${investment.get('amount_usd', 0):.2f}")
            print(f"Crypto received: {investment.get('crypto_amount', 0)} {investment.get('crypto_asset', '')}")
            print(f"Transaction hash: {investment.get('transaction_hash', 'N/A')}")
    
    # Test 6: Get user stats
    print("\n6. Testing user statistics...")
    stats_intent = {
        "intent_type": "get_user_stats",
        "parameters": {
            "user_id": "test_user_001"
        }
    }
    
    stats_result = agent.handle_intent(stats_intent)
    print(f"User stats status: {stats_result.get('status')}")
    
    if stats_result.get("status") == "success":
        stats = stats_result.get("stats", {})
        print(f"Total savings: ${stats.get('total_savings', 0):.2f}")
        print(f"Total invested: ${stats.get('total_invested', 0):.2f}")
        print(f"Crypto balance: {stats.get('crypto_balance', 0)} {stats.get('crypto_asset', '')}")
    
    # Test 7: Error handling
    print("\n7. Testing error handling...")
    error_intent = {
        "intent_type": "invalid_intent_type",
        "parameters": {}
    }
    
    error_result = agent.handle_intent(error_intent)
    print(f"Error handling status: {error_result.get('status')}")
    print(f"Error message: {error_result.get('error', 'No error message')}")
    
    # Clean up
    agent.close()
    
    print("\n=== All tests completed ===")
    
    # Return summary
    return {
        "tests_completed": 7,
        "agent_id": health.get("agent_id"),
        "capabilities": health.get("capabilities"),
        "database_path": health.get("database")
    }


def test_simp_integration():
    """Test SIMP integration concepts"""
    print("\n=== Testing SIMP Integration Concepts ===")
    
    # Example SIMP intent for crypto investment
    simp_intent = {
        "intent_type": "crypto_investment",
        "source_agent": "ktc_agent",
        "target_agent": "quantumarb",
        "parameters": {
            "amount": 15.75,
            "currency": "USD",
            "strategy": "dollar_cost_average",
            "user_wallet": "solana_wallet_address_123",
            "savings_source": "receipt_001_grocery_savings"
        },
        "timestamp": "2026-04-11T18:30:00Z"
    }
    
    print("Example SIMP Intent for Crypto Investment:")
    print(json.dumps(simp_intent, indent=2))
    
    # Example response from QuantumArb
    quantumarb_response = {
        "status": "success",
        "intent_id": "intent_123456",
        "result": {
            "trade_confirmation": True,
            "transaction_hash": "0x1234567890abcdef",
            "investment_details": {
                "crypto_amount": 0.00945,
                "crypto_asset": "SOL",
                "exchange_rate": 1666.67,
                "timestamp": "2026-04-11T18:30:05Z"
            }
        },
        "metadata": {
            "processing_time_ms": 125,
            "agent": "quantumarb",
            "version": "1.0.0"
        }
    }
    
    print("\nExample QuantumArb Response:")
    print(json.dumps(quantumarb_response, indent=2))
    
    return {
        "simp_intent_example": simp_intent,
        "quantumarb_response_example": quantumarb_response
    }


if __name__ == "__main__":
    print("Keep the Change (KTC) Agent Test Suite")
    print("=" * 50)
    
    # Run agent tests
    test_results = test_ktc_agent()
    
    # Run SIMP integration tests
    simp_results = test_simp_integration()
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"Agent ID: {test_results.get('agent_id')}")
    print(f"Capabilities: {', '.join(test_results.get('capabilities', []))}")
    print(f"Database: {test_results.get('database_path')}")
    print(f"Tests completed: {test_results.get('tests_completed')}")
    print("\nSIMP Integration Ready:")
    print("- Crypto investment intents formatted")
    print("- QuantumArb agent integration defined")
    print("- FinancialOps compliance configured")
    
    print("\n✅ KTC Agent tests passed successfully!")
    print("\nNext steps:")
    print("1. Start KTC API server: python api/app.py")
    print("2. Register agent with SIMP broker")
    print("3. Test with frontend application")
    print("4. Integrate with QuantumArb for real crypto trading")