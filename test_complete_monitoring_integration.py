#!/usr/bin/env python3.10
"""
COMPLETE MONITORING SYSTEM INTEGRATION TEST
Tests the full monitoring system integration with QuantumArb agent.
"""

import json
import time
import os
import sys
import requests
from datetime import datetime
from pathlib import Path
import subprocess
import signal

# Add current directory to path
sys.path.insert(0, os.getcwd())

def check_broker_health():
    """Check if SIMP broker is healthy."""
    print("1. Checking broker health...")
    try:
        response = requests.get("http://127.0.0.1:5555/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Broker healthy: {data.get('status', 'unknown')}")
            print(f"   ✅ Uptime: {data.get('uptime_seconds', 0):.0f}s")
            print(f"   ✅ Agents: {data.get('registered_agents', 0)}")
            return True
        else:
            print(f"   ❌ Broker unhealthy: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Broker not reachable: {e}")
        return False

def check_agents():
    """Check registered agents."""
    print("\n2. Checking registered agents...")
    try:
        response = requests.get("http://127.0.0.1:5555/agents", timeout=5)
        if response.status_code == 200:
            agents = response.json().get("agents", [])
            print(f"   ✅ Found {len(agents)} agents:")
            for agent in agents:
                status = "🟢 ONLINE" if agent.get("status") == "online" else "🔴 OFFLINE"
                print(f"      {status} {agent.get('agent_id')} - {agent.get('capabilities', [])}")
            
            # Check for quantumarb_risk_simple
            quantumarb_agents = [a for a in agents if "quantumarb" in a.get("agent_id", "")]
            if quantumarb_agents:
                print(f"   ✅ QuantumArb agents found: {len(quantumarb_agents)}")
                return True
            else:
                print("   ❌ No QuantumArb agents found")
                return False
        else:
            print(f"   ❌ Failed to get agents: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error checking agents: {e}")
        return False

def test_monitoring_system():
    """Test monitoring system directly."""
    print("\n3. Testing monitoring system...")
    try:
        from monitoring_alerting_system import MonitoringSystem, AlertSeverity, AlertType
        
        # Create monitoring system
        monitoring = MonitoringSystem()
        print("   ✅ Monitoring system created")
        
        # Test recording intent
        test_intent = {
            "intent_id": "integration_test_001",
            "intent_type": "arbitrage_opportunity",
            "source_agent": "integration_tester",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "symbol": "BTC-USD",
                "exchange_a": "coinbase",
                "exchange_b": "binance",
                "spread_percent": 1.2,
                "volume": 0.05,
                "price_a": 65000.50,
                "price_b": 64923.75
            }
        }
        
        trade_id = monitoring.record_intent(
            intent_id=test_intent["intent_id"],
            intent_data=test_intent
        )
        print(f"   ✅ Intent recorded: {trade_id}")
        
        # Test recording BRP decision
        brp_data = {
            "decision": "execute",
            "risk_allowed": True,
            "risk_reason": "Within conservative risk limits",
            "position_size": 500.0,
            "estimated_profit": 6.0,
            "estimated_spread": 120.0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        monitoring.record_brp_decision(
            trade_id=test_intent["intent_id"],
            brp_data=brp_data
        )
        print("   ✅ BRP decision recorded")
        
        # Test creating alert (using internal method)
        alert_id = monitoring._create_alert(
            alert_type=AlertType.BRP_BLOCK,
            severity=AlertSeverity.WARNING,
            message="Test BRP block alert",
            details={"symbol": "BTC-USD", "reason": "Risk limit exceeded"}
        )
        print(f"   ✅ Alert created: {alert_id}")
        
        # Test getting metrics
        metrics = monitoring.get_system_metrics()
        print(f"   ✅ System metrics: {metrics.get('trades', {}).get('total', 0)} trades, {metrics.get('alerts', {}).get('total', 0)} alerts")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Monitoring system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_quantumarb_agent():
    """Test QuantumArb agent with monitoring integration."""
    print("\n4. Testing QuantumArb agent...")
    try:
        from simp.agents.quantumarb_risk_simple import QuantumArbAgentWithRiskSimple
        
        # Create agent
        agent = QuantumArbAgentWithRiskSimple(
            poll_interval=1.0,
            risk_config="risk_config_conservative.json"
        )
        
        print(f"   ✅ Agent created successfully")
        print(f"   ✅ Monitoring enabled: {agent.monitoring_enabled}")
        
        # Test agent directories
        inbox_dir = Path("data/inboxes/quantumarb_risk_simple")
        if inbox_dir.exists():
            print("   ✅ Inbox directory exists")
        else:
            print("   ⚠️ Inbox directory doesn't exist (will be created)")
            
        # Test intent parsing
        test_intent = {
            "intent_id": "agent_test_001",
            "intent_type": "arbitrage_opportunity",
            "source_agent": "agent_tester",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "symbol": "ETH-USD",
                "exchange_a": "kraken",
                "exchange_b": "gemini",
                "spread_percent": 0.8,
                "volume": 2.5,
                "price_a": 3500.50,
                "price_b": 3495.25
            }
        }
        
        from simp.agents.quantumarb_risk_simple import ArbitrageSignal
        signal = ArbitrageSignal.from_intent(test_intent)
        
        print(f"   ✅ Intent parsing successful:")
        print(f"      Symbol: {signal.ticker}")
        print(f"      Exchange A: {signal.exchange_a}")
        print(f"      Exchange B: {signal.exchange_b}")
        print(f"      Spread: {signal.spread_percent}%")
        print(f"      Volume: {signal.volume}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ QuantumArb agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_intent_routing():
    """Test sending arbitrage intent through broker."""
    print("\n5. Testing intent routing...")
    
    # Check routing policy
    try:
        response = requests.get("http://127.0.0.1:5555/routing-policy", timeout=5)
        if response.status_code == 200:
            policy = response.json()
            arb_policy = policy.get("arbitrage_opportunity", {})
            print(f"   ✅ Routing policy found for arbitrage_opportunity")
            print(f"      Primary: {arb_policy.get('primary_agent', 'none')}")
            print(f"      Fallback: {arb_policy.get('fallback_chain', [])}")
        else:
            print(f"   ⚠️ Could not get routing policy: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Error checking routing policy: {e}")
    
    # Send test intent
    test_intent = {
        "intent_id": f"routing_test_{int(time.time())}",
        "intent_type": "arbitrage_opportunity",
        "source_agent": "integration_tester",
        "target_agent": "auto",  # Let broker route it
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "symbol": "SOL-USD",
            "exchange_a": "ftx",
            "exchange_b": "kucoin",
            "price_a": 150.75,
            "price_b": 149.50,
            "spread_percent": 0.83,
            "volume": 10.0,
            "estimated_profit": 12.50,
            "confidence": 0.72,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "test_mode": "normal"
        }
    }
    
    try:
        # Get API key from environment
        api_key = os.environ.get("SIMP_API_KEY", "781002cryptrillionaire456")
        
        response = requests.post(
            "http://127.0.0.1:5555/intents/route",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            json=test_intent,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Intent routed successfully")
            print(f"      Status: {result.get('status', 'unknown')}")
            print(f"      Message: {result.get('message', '')}")
            print(f"      Target agent: {result.get('target_agent', 'unknown')}")
            
            # Check if intent was written to inbox
            time.sleep(1)  # Give broker time to write file
            inbox_dir = Path("data/inboxes/quantumarb_risk_simple")
            if inbox_dir.exists():
                intent_files = list(inbox_dir.glob("*.json"))
                print(f"   ✅ Inbox has {len(intent_files)} intent files")
                return True
            else:
                print("   ⚠️ Inbox directory doesn't exist yet")
                return False
        else:
            print(f"   ❌ Intent routing failed: HTTP {response.status_code}")
            print(f"      Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error routing intent: {e}")
        return False

def test_trade_reconstruction():
    """Test trade reconstruction from monitoring logs."""
    print("\n6. Testing trade reconstruction...")
    
    try:
        from monitoring_alerting_system import MonitoringSystem
        
        monitoring = MonitoringSystem()
        
        # Create a complete trade record
        test_trade_id = f"reconstruction_test_{int(time.time())}"
        
        # Record intent
        test_intent = {
            "intent_id": test_trade_id,
            "intent_type": "arbitrage_opportunity",
            "source_agent": "reconstruction_tester",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "symbol": "ADA-USD",
                "exchange_a": "binance",
                "exchange_b": "coinbase",
                "spread_percent": 1.5,
                "volume": 1000.0,
                "price_a": 0.45,
                "price_b": 0.44325
            }
        }
        
        monitoring.record_intent(test_trade_id, test_intent)
        
        # Record BRP decision
        brp_data = {
            "decision": "execute",
            "risk_allowed": True,
            "risk_reason": "Within moderate risk limits",
            "position_size": 450.0,
            "estimated_profit": 6.75,
            "estimated_spread": 150.0,
            "timestamp": datetime.utcnow().isoformat()
        }
        monitoring.record_brp_decision(test_trade_id, brp_data)
        
        # Record order execution (simulated)
        order_data = {
            "order_id": f"order_{test_trade_id}",
            "status": "filled",
            "exchange": "binance",
            "symbol": "ADA-USD",
            "side": "buy",
            "quantity": 1000.0,
            "price": 0.449,
            "timestamp": datetime.utcnow().isoformat(),
            "slippage_bps": 2.2
        }
        monitoring.record_order_execution(test_trade_id, order_data)
        
        # Record P&L
        pnl_data = {
            "realized_pnl": 4.50,
            "fees": 0.90,
            "net_pnl": 3.60,
            "slippage_impact": -0.45,
            "timestamp": datetime.utcnow().isoformat()
        }
        monitoring.record_pnl(test_trade_id, pnl_data)
        
        # Test reconstruction
        trade_record = monitoring.get_trade_reconstruction(test_trade_id)
        if trade_record:
            print(f"   ✅ Trade reconstruction successful")
            print(f"      Symbol: {trade_record.symbol}")
            print(f"      BRP decision: {trade_record.brp_decision}")
            print(f"      Order status: {trade_record.order_status}")
            print(f"      P&L: ${trade_record.pnl:.2f}")
            print(f"      Log entries: {len(trade_record.logs)}")
            return True
        else:
            print("   ❌ Trade reconstruction failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Trade reconstruction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run complete monitoring integration test."""
    print("=" * 80)
    print("COMPLETE MONITORING SYSTEM INTEGRATION TEST")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run all tests
    tests = [
        ("Broker Health", check_broker_health),
        ("Registered Agents", check_agents),
        ("Monitoring System", test_monitoring_system),
        ("QuantumArb Agent", test_quantumarb_agent),
        ("Intent Routing", test_intent_routing),
        ("Trade Reconstruction", test_trade_reconstruction)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"{'='*60}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"   ❌ Test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:30} {status}")
        if success:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed ({passed/len(results)*100:.0f}%)")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED - MONITORING SYSTEM INTEGRATION COMPLETE")
        print("\nPhase 3 Status: ✅ COMPLETE")
        print("System ready for Phase 4: First Real-Money Experiment")
    else:
        print(f"\n⚠️ {len(results)-passed} tests failed")
        print("Review logs above and fix issues before proceeding to Phase 4")
    
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())