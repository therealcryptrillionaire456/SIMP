#!/usr/bin/env python3.10
"""
Test monitoring system integration with QuantumArb agent.
"""

import json
import time
import os
import sys
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.getcwd())

def test_monitoring_import():
    """Test that monitoring system can be imported."""
    print("Testing monitoring system import...")
    try:
        from monitoring_alerting_system import MonitoringSystem, AlertSeverity, AlertType
        print("✅ Monitoring system imports successfully")
        
        # Test creating monitoring system
        monitoring = MonitoringSystem()
        print("✅ Monitoring system created successfully")
        
        # Test recording an intent
        test_intent = {
            "intent_id": "test_intent_001",
            "intent_type": "arbitrage_opportunity",
            "source_agent": "test_agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "symbol": "BTC-USD",
                "exchange_a": "coinbase",
                "exchange_b": "binance",
                "spread_percent": 1.5,
                "volume": 0.1
            }
        }
        
        trade_id = monitoring.record_intent(
            intent_id=test_intent["intent_id"],
            intent_data=test_intent
        )
        print(f"✅ Intent recorded successfully, trade_id: {trade_id}")
        
        # Test recording BRP decision
        brp_data = {
            "decision": "execute",
            "risk_allowed": True,
            "risk_reason": "Within risk limits",
            "position_size": 1000.0,
            "estimated_profit": 15.0,
            "estimated_spread": 150.0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        monitoring.record_brp_decision(
            trade_id=test_intent["intent_id"],
            brp_data=brp_data
        )
        print("✅ BRP decision recorded successfully")
        
        # Test getting system metrics
        metrics = monitoring.get_system_metrics()
        print(f"✅ System metrics retrieved: {len(metrics.get('recent_trades', []))} trades")
        
        return True
        
    except Exception as e:
        print(f"❌ Monitoring system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_quantumarb_monitoring_integration():
    """Test QuantumArb agent with monitoring integration."""
    print("\nTesting QuantumArb agent monitoring integration...")
    
    try:
        # Import the agent
        from simp.agents.quantumarb_risk_simple import QuantumArbAgentWithRiskSimple
        
        # Create agent with monitoring
        agent = QuantumArbAgentWithRiskSimple(
            poll_interval=1.0,
            risk_config="risk_config_conservative.json"
        )
        
        print(f"✅ Agent created successfully")
        print(f"✅ Monitoring enabled: {agent.monitoring_enabled}")
        
        # Test agent directories
        inbox_dir = Path("data/inboxes/quantumarb_risk_simple")
        if inbox_dir.exists():
            print("✅ Inbox directory exists")
        else:
            print("⚠️ Inbox directory doesn't exist (will be created)")
            
        return True
        
    except Exception as e:
        print(f"❌ QuantumArb agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_intent_processing():
    """Test that intents are processed correctly."""
    print("\nTesting intent processing...")
    
    try:
        # Create a test intent file
        inbox_dir = Path("data/inboxes/quantumarb_risk_simple")
        inbox_dir.mkdir(parents=True, exist_ok=True)
        
        test_intent = {
            "intent_id": "test_processing_001",
            "intent_type": "arbitrage_opportunity",
            "source_agent": "test_runner",
            "target_agent": "quantumarb_risk_simple",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "symbol": "ETH-USD",
                "exchange_a": "kraken",
                "exchange_b": "gemini",
                "price_a": 3500.50,
                "price_b": 3495.25,
                "spread_percent": 0.15,
                "volume": 0.5,
                "estimated_profit": 2.63,
                "confidence": 0.85,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "test_mode": "normal"
            }
        }
        
        intent_file = inbox_dir / "test_intent_001.json"
        with open(intent_file, "w") as f:
            json.dump(test_intent, f, indent=2)
            
        print(f"✅ Test intent written to: {intent_file}")
        
        # Check that the intent can be parsed
        from simp.agents.quantumarb_risk_simple import ArbitrageSignal
        
        signal = ArbitrageSignal.from_intent(test_intent)
        print(f"✅ Intent parsed successfully:")
        print(f"   Ticker: {signal.ticker}")
        print(f"   Exchange A: {signal.exchange_a}")
        print(f"   Exchange B: {signal.exchange_b}")
        print(f"   Spread: {signal.spread_percent}%")
        print(f"   Volume: {signal.volume}")
        
        # Clean up
        intent_file.unlink()
        print("✅ Test intent cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Intent processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("MONITORING SYSTEM INTEGRATION TEST")
    print("=" * 60)
    
    # Run tests
    test1 = test_monitoring_import()
    test2 = test_quantumarb_monitoring_integration()
    test3 = test_intent_processing()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Monitoring system import: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"QuantumArb agent integration: {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"Intent processing: {'✅ PASS' if test3 else '❌ FAIL'}")
    
    overall = test1 and test2 and test3
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if overall else '❌ SOME TESTS FAILED'}")
    
    return 0 if overall else 1

if __name__ == "__main__":
    sys.exit(main())