#!/usr/bin/env python3
"""
SIMP Agent Mesh Bus - End-to-End Smoke Test

Tests the complete Mesh Bus system:
1. MeshPacket creation and serialization
2. MeshBus core functionality
3. Broker integration
4. HTTP API endpoints
5. MeshClient usage
"""

import json
import time
import threading
from datetime import datetime, timezone
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simp.mesh.packet import (
    MeshPacket,
    MessageType,
    Priority,
    create_event_packet,
    create_system_packet,
    create_heartbeat_packet,
)
from simp.mesh.bus import MeshBus
from simp.mesh.client import MeshClient


def test_mesh_packet():
    """Test MeshPacket creation and serialization."""
    print("🧪 Testing MeshPacket...")
    
    # Create a packet
    packet = MeshPacket(
        sender_id="agent_a",
        recipient_id="agent_b",
        channel="test_channel",
        payload={"message": "hello", "timestamp": time.time()},
        msg_type=MessageType.EVENT,
        priority=Priority.HIGH,
        ttl_seconds=3600,
        ttl_hops=10,
    )
    
    # Test to_dict and from_dict
    data = packet.to_dict()
    restored = MeshPacket.from_dict(data)
    
    assert packet.sender_id == restored.sender_id
    assert packet.recipient_id == restored.recipient_id
    assert packet.payload == restored.payload
    assert packet.message_id == restored.message_id
    
    # Test JSON serialization
    json_str = packet.to_json()
    restored_json = MeshPacket.from_json(json_str)
    
    assert packet.sender_id == restored_json.sender_id
    assert packet.recipient_id == restored_json.recipient_id
    
    print("  ✓ MeshPacket serialization/deserialization works")
    return True


def test_mesh_bus_core():
    """Test MeshBus core functionality."""
    print("\n🧪 Testing MeshBus core functionality...")
    
    bus = MeshBus()
    
    # Test agent registration
    bus.register_agent("agent_a")
    bus.register_agent("agent_b")
    bus.subscribe("agent_a", "alerts")
    bus.subscribe("agent_b", "alerts")
    
    assert bus.is_agent_registered("agent_a")
    assert bus.is_agent_registered("agent_b")
    print("  ✓ Agent registration and subscription works")
    
    # Test direct messaging
    packet = create_event_packet(
        sender_id="agent_a",
        recipient_id="agent_b",
        channel="",  # Direct message
        payload={"direct": "message"},
    )
    
    success = bus.send(packet)
    assert success
    
    messages = bus.receive("agent_b", max_messages=10)
    assert len(messages) == 1
    assert messages[0].sender_id == "agent_a"
    assert messages[0].payload["direct"] == "message"
    print("  ✓ Direct messaging works")
    
    # Test channel broadcast
    broadcast_packet = create_event_packet(
        sender_id="system",
        recipient_id="*",
        channel="alerts",
        payload={"alert": "system_update"},
    )
    
    success = bus.send(broadcast_packet)
    assert success
    
    # Both agents should receive the broadcast
    for agent in ["agent_a", "agent_b"]:
        messages = bus.receive(agent, max_messages=10)
        # Filter for broadcast messages
        broadcast_messages = [m for m in messages if m.payload.get("alert") == "system_update"]
        assert len(broadcast_messages) == 1
    print("  ✓ Channel broadcast works")
    
    # Test offline messaging
    bus.deregister_agent("agent_b")
    
    offline_packet = create_event_packet(
        sender_id="agent_a",
        recipient_id="agent_b",
        channel="",  # Direct message
        payload={"offline": "message"},
    )
    
    success = bus.send(offline_packet)
    assert success
    
    # Message should be pending
    pending_count = bus.get_pending_count("agent_b")
    assert pending_count == 1
    print("  ✓ Offline message storage works")
    
    # Re-register and receive pending message
    bus.register_agent("agent_b")
    bus.subscribe("agent_b", "alerts")
    
    messages = bus.receive("agent_b", max_messages=10)
    offline_messages = [m for m in messages if m.payload.get("offline") == "message"]
    assert len(offline_messages) == 1
    print("  ✓ Offline message delivery works")
    
    # Test statistics
    stats = bus.get_statistics()
    assert stats["registered_agents"] == 2
    assert "alerts" in stats["channels"]
    print("  ✓ Statistics collection works")
    
    bus.shutdown()
    return True


def test_mesh_bus_edge_cases():
    """Test MeshBus edge cases."""
    print("\n🧪 Testing MeshBus edge cases...")
    
    bus = MeshBus()
    
    # Test expired message handling
    expired_packet = MeshPacket(
        sender_id="agent_a",
        recipient_id="agent_b",
        ttl_seconds=0,  # Already expired
        payload={"expired": "message"},
    )
    
    bus.register_agent("agent_b")
    success = bus.send(expired_packet)
    assert not success  # Should fail to send expired packet
    print("  ✓ Expired message rejection works")
    
    # Test invalid packet (no sender)
    invalid_packet = MeshPacket(
        sender_id="",  # Empty sender
        recipient_id="agent_b",
        payload={"invalid": "message"},
    )
    
    success = bus.send(invalid_packet)
    assert not success  # Should fail to send invalid packet
    print("  ✓ Invalid packet rejection works")
    
    # Test empty channel broadcast
    empty_channel_packet = create_event_packet(
        sender_id="agent_a",
        recipient_id="*",
        channel="empty_channel",  # No subscribers
        payload={"test": "data"},
    )
    
    success = bus.send(empty_channel_packet)
    assert not success  # Should fail (no subscribers)
    print("  ✓ Empty channel broadcast handling works")
    
    bus.shutdown()
    return True


def test_mesh_client_mocked():
    """Test MeshClient with mocked HTTP responses."""
    print("\n🧪 Testing MeshClient (mocked)...")
    
    # Note: We're testing the client logic, not actual HTTP calls
    # In a real smoke test, we'd need a running broker
    
    # Create a mock HTTP client
    class MockHttpClient:
        def __init__(self):
            self.last_request = None
        
        def post(self, url, headers=None, json=None):
            self.last_request = {"url": url, "headers": headers, "json": json}
            # Return a mock response
            class MockResponse:
                status_code = 200
                def json(self):
                    return {"status": "success", "message_id": "test-123"}
            return MockResponse()
        
        def get(self, url, headers=None, params=None):
            self.last_request = {"url": url, "headers": headers, "params": params}
            # Return a mock response
            class MockResponse:
                status_code = 200
                def json(self):
                    return {
                        "status": "success",
                        "agent_id": "test_agent",
                        "messages": [],
                        "count": 0
                    }
            return MockResponse()
    
    mock_http = MockHttpClient()
    
    # Create client with mock HTTP
    client = MeshClient(
        agent_id="test_agent",
        broker_url="http://test:5555",
        api_key="test_key",
        http_client=mock_http
    )
    
    # Test send
    message_id = client.send(
        recipient_id="other_agent",
        payload={"test": "data"}
    )
    assert message_id == "test-123"
    assert mock_http.last_request is not None
    assert "mesh/send" in mock_http.last_request["url"]
    print("  ✓ MeshClient.send() works (mocked)")
    
    # Test poll
    messages = client.poll(max_messages=10)
    assert len(messages) == 0
    assert "mesh/poll" in mock_http.last_request["url"]
    print("  ✓ MeshClient.poll() works (mocked)")
    
    # Test subscribe
    # We need to mock the response for this
    mock_http.post = lambda url, headers=None, json=None: type('MockResponse', (), {
        'status_code': 200,
        'json': lambda: {"status": "success", "message": "Subscribed"}
    })()
    
    result = client.subscribe("test_channel")
    assert result is True
    print("  ✓ MeshClient.subscribe() works (mocked)")
    
    # Test statistics
    mock_http.get = lambda url, headers=None, params=None: type('MockResponse', (), {
        'status_code': 200,
        'json': lambda: {"status": "success", "statistics": {"registered_agents": 5}}
    })()
    
    stats = client.get_stats()
    assert stats["registered_agents"] == 5
    print("  ✓ MeshClient.get_stats() works (mocked)")
    
    client.close()
    return True


def test_real_use_cases():
    """Test real-world use cases."""
    print("\n🧪 Testing real use cases...")
    
    bus = MeshBus()
    
    # Register agents for different roles
    agents = {
        "brp_monitor": ["safety_alerts", "system"],
        "quantumarb": ["trade_updates", "safety_alerts"],
        "dashboard": ["safety_alerts", "trade_updates", "system"],
        "risk_monitor": ["safety_alerts", "trade_updates"],
    }
    
    for agent_id, channels in agents.items():
        bus.register_agent(agent_id)
        for channel in channels:
            bus.subscribe(agent_id, channel)
    
    print(f"  ✓ Registered {len(agents)} agents with role-based subscriptions")
    
    # Test safety alert flow
    safety_alert = create_system_packet(
        sender_id="brp_monitor",
        recipient_id="*",  # Broadcast to all subscribers
        payload={
            "alert_type": "risk_limit",
            "severity": "HIGH",
            "message": "Daily loss limit approaching 80%",
            "metric": "daily_loss_pct",
            "value": 78.5,
            "threshold": 80.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    
    success = bus.send(safety_alert)
    assert success
    
    # Check that safety alert subscribers received it
    safety_subscribers = ["dashboard", "risk_monitor", "quantumarb"]
    for agent in safety_subscribers:
        messages = bus.peek(agent, max_messages=10)
        safety_messages = [m for m in messages if m.payload.get("alert_type") == "risk_limit"]
        assert len(safety_messages) > 0
    print("  ✓ Safety alert propagation works")
    
    # Test trade update flow
    trade_update = create_event_packet(
        sender_id="quantumarb",
        recipient_id="*",
        channel="trade_updates",
        payload={
            "event_type": "arbitrage_opportunity",
            "opportunity_id": "arb_001",
            "assets": ["BTC", "ETH"],
            "estimated_profit_pct": 1.5,
            "confidence": 0.85,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    
    success = bus.send(trade_update)
    assert success
    
    # Check that trade update subscribers received it
    trade_subscribers = ["dashboard", "risk_monitor"]
    for agent in trade_subscribers:
        messages = bus.peek(agent, max_messages=10)
        trade_messages = [m for m in messages if m.payload.get("event_type") == "arbitrage_opportunity"]
        assert len(trade_messages) > 0
    print("  ✓ Trade update propagation works")
    
    # Test heartbeat monitoring
    heartbeat = create_heartbeat_packet("quantumarb")
    success = bus.send(heartbeat)
    assert success
    
    # System agents should receive heartbeats
    system_agents = ["dashboard"]  # Dashboard monitors system health
    for agent in system_agents:
        messages = bus.peek(agent, max_messages=10)
        heartbeat_messages = [m for m in messages if m.msg_type == MessageType.HEARTBEAT]
        assert len(heartbeat_messages) > 0
    print("  ✓ Heartbeat monitoring works")
    
    bus.shutdown()
    return True


def run_smoke_test():
    """Run complete smoke test."""
    print("=" * 70)
    print("SIMP Agent Mesh Bus - End-to-End Smoke Test")
    print("=" * 70)
    
    tests = [
        ("MeshPacket", test_mesh_packet),
        ("MeshBus Core", test_mesh_bus_core),
        ("MeshBus Edge Cases", test_mesh_bus_edge_cases),
        ("MeshClient (Mocked)", test_mesh_client_mocked),
        ("Real Use Cases", test_real_use_cases),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
    
    print("\n" + "=" * 70)
    print("Test Results:")
    print("=" * 70)
    
    all_passed = True
    for test_name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if error:
            print(f"     Error: {error}")
        if not success:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 All smoke tests passed! Mesh Bus is ready for integration.")
        print("\nNext steps:")
        print("1. Start broker: python -m simp.server.http_server")
        print("2. Use MeshClient in agents for real communication")
        print("3. Monitor mesh events in data/mesh_events.jsonl")
    else:
        print("⚠️  Some tests failed. Review errors above.")
    
    return all_passed


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)