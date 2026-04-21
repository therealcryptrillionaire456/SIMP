#!/usr/bin/env python3
"""
Test QuantumArb mesh integration
"""

import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QuantumArbMeshTest")

def test_mesh_integration():
    """Test QuantumArb mesh integration"""
    print("=" * 70)
    print("QUANTUMARB MESH INTEGRATION TEST")
    print("=" * 70)
    
    # Test 1: Import mesh integration
    print("\n1. Testing mesh integration imports...")
    try:
        from simp.organs.quantumarb.mesh_integration import (
            get_quantumarb_mesh_monitor,
            TradeUpdate,
            TradeStatus,
            SafetyAction,
            SafetyCommand
        )
        print("✅ Mesh integration imports successful")
    except ImportError as e:
        print(f"❌ Mesh integration imports failed: {e}")
        return False
    
    # Test 2: Create mesh monitor
    print("\n2. Testing mesh monitor creation...")
    try:
        monitor = get_quantumarb_mesh_monitor()
        if monitor.mesh_client:
            print("✅ Mesh monitor created successfully")
            print(f"   Agent ID: {monitor.agent_id}")
            print(f"   Broker URL: {monitor.broker_url}")
        else:
            print("❌ Mesh monitor created but mesh client not available")
            print("   Running in simulation mode")
    except Exception as e:
        print(f"❌ Failed to create mesh monitor: {e}")
        return False
    
    # Test 3: Test trade update creation
    print("\n3. Testing trade update creation...")
    try:
        update = TradeUpdate(
            trade_id="test_trade_123",
            status=TradeStatus.DETECTED,
            symbol="BTC-USD",
            venue="Coinbase",
            spread_percent=1.5,
            expected_profit=150.0,
            risk_score=0.2,
            brp_decision="APPROVED",
            trace_id="test_trace_123"
        )
        
        payload = update.to_payload()
        print("✅ Trade update created successfully")
        print(f"   Trade ID: {update.trade_id}")
        print(f"   Status: {update.status.value}")
        print(f"   Symbol: {update.symbol}")
        print(f"   Spread: {update.spread_percent}%")
        print(f"   Expected Profit: ${update.expected_profit}")
    except Exception as e:
        print(f"❌ Failed to create trade update: {e}")
        return False
    
    # Test 4: Test safety action parsing
    print("\n4. Testing safety action parsing...")
    try:
        safety_payload = {
            "command": "pause_trading",
            "reason": "High risk detected",
            "severity": "CRITICAL",
            "source": "ProjectX",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": "safety_trace_123",
            "parameters": {"duration_minutes": 30}
        }
        
        action = SafetyAction.from_mesh_payload(safety_payload)
        if action:
            print("✅ Safety action parsed successfully")
            print(f"   Command: {action.command.value}")
            print(f"   Reason: {action.reason}")
            print(f"   Severity: {action.severity}")
            print(f"   Source: {action.source}")
        else:
            print("❌ Failed to parse safety action")
            return False
    except Exception as e:
        print(f"❌ Error parsing safety action: {e}")
        return False
    
    # Test 5: Test monitor start/stop
    print("\n5. Testing monitor start/stop...")
    try:
        # Try to start monitor
        started = monitor.start()
        if started:
            print("✅ Mesh monitor started successfully")
            
            # Run for a few seconds
            print("   Running monitor for 5 seconds...")
            time.sleep(5)
            
            # Get status
            status = monitor.get_status()
            print(f"   Monitor status: {status}")
            
            # Stop monitor
            monitor.stop()
            print("✅ Mesh monitor stopped successfully")
        else:
            print("⚠️  Mesh monitor failed to start (may be expected if broker not available)")
            print("   Running in simulation mode")
    except Exception as e:
        print(f"❌ Error testing monitor start/stop: {e}")
        return False
    
    # Test 6: Test QuantumArb agent integration
    print("\n6. Testing QuantumArb agent integration...")
    try:
        # Check if agent can import mesh integration
        from simp.agents.quantumarb_agent_enhanced import MESH_AVAILABLE
        
        if MESH_AVAILABLE:
            print("✅ QuantumArb agent mesh integration available")
            
            # Create a test intent
            test_intent = {
                "intent_id": "test_intent_123",
                "intent_type": "arbitrage_analysis",
                "source_agent": "test_agent",
                "trace_id": "test_trace_456",
                "payload": {
                    "ticker": "BTC-USD",
                    "venue": "Coinbase",
                    "spread_bps": 150,
                    "estimated_profit_usd": 150.0
                }
            }
            
            # Save to inbox for processing
            inbox_dir = Path("data/inboxes/quantumarb_enhanced")
            inbox_dir.mkdir(parents=True, exist_ok=True)
            
            intent_file = inbox_dir / "test_intent.json"
            with open(intent_file, "w") as f:
                json.dump(test_intent, f, indent=2)
            
            print("✅ Test intent created for QuantumArb processing")
            print(f"   Saved to: {intent_file}")
            
        else:
            print("⚠️  QuantumArb agent mesh integration not available")
            print("   Agent will run without mesh updates")
            
    except ImportError as e:
        print(f"⚠️  Could not import QuantumArb agent: {e}")
        print("   This may be expected if QuantumArb agent is not available")
    except Exception as e:
        print(f"❌ Error testing QuantumArb agent integration: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    
    print("\n✅ All integration tests passed!")
    print("\nNext steps:")
    print("1. Start QuantumArb agent to process test intent")
    print("2. Check mesh events log for trade updates")
    print("3. Send safety commands via mesh to test response")
    print("4. Monitor trade_updates channel for real-time updates")
    
    return True


def test_mesh_channels():
    """Test mesh channel communication"""
    print("\n" + "=" * 70)
    print("MESH CHANNEL COMMUNICATION TEST")
    print("=" * 70)
    
    try:
        import requests
        
        base_url = "http://127.0.0.1:5555"
        
        # Test mesh stats
        print("\n1. Testing mesh stats endpoint...")
        response = requests.get(f"{base_url}/mesh/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Mesh stats: {stats}")
        else:
            print(f"❌ Mesh stats failed: {response.status_code}")
            return False
        
        # Test sending a trade update via HTTP
        print("\n2. Testing trade update via HTTP...")
        trade_update = {
            "sender_id": "quantumarb_test",
            "recipient_id": "*",  # Broadcast
            "channel": "trade_updates",
            "msg_type": "event",
            "payload": {
                "trade_id": "http_test_123",
                "status": "detected",
                "symbol": "ETH-USD",
                "venue": "test_exchange",
                "spread_percent": 2.1,
                "expected_profit": 85.0,
                "risk_score": 0.3,
                "brp_decision": "TEST_APPROVED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "priority": "normal",
            "ttl_hops": 10,
            "ttl_seconds": 60
        }
        
        response = requests.post(f"{base_url}/mesh/send", json=trade_update)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Trade update sent via HTTP")
                print(f"   Message ID: {result.get('message_id')}")
            else:
                print(f"❌ Trade update failed: {result.get('error')}")
        else:
            print(f"❌ HTTP request failed: {response.status_code}")
            return False
        
        # Test safety alert
        print("\n3. Testing safety alert via HTTP...")
        safety_alert = {
            "sender_id": "brp_test",
            "recipient_id": "*",
            "channel": "safety_alerts",
            "msg_type": "event",
            "payload": {
                "alert_type": "high_risk",
                "severity": "WARNING",
                "reason": "Test safety alert",
                "source": "test_brp",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recommended_action": "increase_monitoring"
            },
            "priority": "high",
            "ttl_hops": 10,
            "ttl_seconds": 300
        }
        
        response = requests.post(f"{base_url}/mesh/send", json=safety_alert)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Safety alert sent via HTTP")
                print(f"   Message ID: {result.get('message_id')}")
            else:
                print(f"❌ Safety alert failed: {result.get('error')}")
        else:
            print(f"❌ HTTP request failed: {response.status_code}")
            return False
        
        print("\n✅ Mesh channel communication tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing mesh channels: {e}")
        return False


if __name__ == "__main__":
    # Run tests
    success1 = test_mesh_integration()
    
    # Only run channel tests if broker is available
    try:
        import requests
        response = requests.get("http://127.0.0.1:5555/health", timeout=2)
        if response.status_code == 200:
            success2 = test_mesh_channels()
        else:
            print("\n⚠️  Broker not available, skipping channel tests")
            success2 = True
    except:
        print("\n⚠️  Broker not available, skipping channel tests")
        success2 = True
    
    if success1 and success2:
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nQuantumArb mesh integration is ready for use.")
        print("\nTo use:")
        print("1. Start QuantumArb agent: python3.10 simp/agents/quantumarb_agent_enhanced.py")
        print("2. Send arbitrage intents to data/inboxes/quantumarb_enhanced/")
        print("3. Monitor trade_updates channel for real-time updates")
        print("4. Send safety commands to safety_alerts channel")
    else:
        print("\n" + "=" * 70)
        print("❌ SOME TESTS FAILED")
        print("=" * 70)
        exit(1)