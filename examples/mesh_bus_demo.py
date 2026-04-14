"""
SIMP Agent Mesh Bus - Demonstration Script

Shows real use cases for the Mesh Bus:
1. Safety alerts channel
2. Trade intent state updates
3. Agent-to-agent communication
"""

import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any

# Import mesh components
from simp.mesh import (
    MeshPacket,
    MessageType,
    Priority,
    create_event_packet,
    create_system_packet,
    create_heartbeat_packet,
    MeshBus,
)


def demo_safety_alerts():
    """Demonstrate safety alerts channel usage."""
    print("\n" + "="*60)
    print("DEMO 1: Safety Alerts Channel")
    print("="*60)
    
    # Create a mesh bus instance
    mesh_bus = MeshBus()
    
    # Register some agents
    agents = ["brp_monitor", "projectx", "dashboard", "watchtower", "quantumarb"]
    for agent in agents:
        mesh_bus.register_agent(agent)
        mesh_bus.subscribe(agent, "safety_alerts")
        print(f"✓ Registered agent: {agent}")
    
    # Simulate BRP monitor detecting a safety issue
    print("\n--- BRP Monitor detects safety issue ---")
    safety_alert = create_system_packet(
        sender_id="brp_monitor",
        recipient_id="*",  # Broadcast to all subscribers
        payload={
            "source": "BRP",
            "severity": "HIGH",
            "description": "Daily loss limit approaching 80%",
            "metric": "daily_loss_pct",
            "value": 78.5,
            "threshold": 80.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendation": "Pause trading until review",
        }
    )
    
    # Send the safety alert
    success = mesh_bus.send(safety_alert)
    if success:
        print(f"✓ Safety alert sent: {safety_alert.message_id[:8]}...")
        print(f"  Channel: safety_alerts")
        print(f"  Severity: HIGH")
        print(f"  Message: Daily loss limit approaching 80%")
    else:
        print("✗ Failed to send safety alert")
    
    # Simulate agents receiving alerts
    print("\n--- Agents receiving safety alerts ---")
    for agent in agents:
        if agent == "brp_monitor":
            continue  # Don't receive our own messages
        
        messages = mesh_bus.receive(agent, max_messages=5)
        for msg in messages:
            print(f"✓ {agent} received alert: {msg.payload.get('description', 'No description')}")
    
    # Show statistics
    stats = mesh_bus.get_statistics()
    print(f"\n--- Mesh Bus Statistics ---")
    print(f"Registered agents: {stats['registered_agents']}")
    print(f"Total queued messages: {stats['total_queued_messages']}")
    print(f"Safety alerts subscribers: {len(mesh_bus.get_channel_subscribers('safety_alerts'))}")
    
    return mesh_bus


def demo_trade_updates():
    """Demonstrate trade intent state updates."""
    print("\n" + "="*60)
    print("DEMO 2: Trade Intent State Updates")
    print("="*60)
    
    # Create a new mesh bus for this demo
    mesh_bus = MeshBus()
    
    # Register trading-related agents
    trading_agents = ["quantumarb", "kashclaw", "dashboard", "risk_monitor", "execution_engine"]
    for agent in trading_agents:
        mesh_bus.register_agent(agent)
        mesh_bus.subscribe(agent, "trade_updates")
        print(f"✓ Registered trading agent: {agent}")
    
    # Simulate QuantumArb detecting an arbitrage opportunity
    print("\n--- QuantumArb detects arbitrage opportunity ---")
    arb_opportunity = create_event_packet(
        sender_id="quantumarb",
        recipient_id="*",  # Broadcast to trade_updates channel
        channel="trade_updates",
        payload={
            "event_type": "arbitrage_opportunity",
            "opportunity_id": "arb_001",
            "assets": ["BTC", "ETH"],
            "exchanges": ["exchange_a", "exchange_b"],
            "estimated_profit_pct": 1.5,
            "confidence": 0.85,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "detected",
            "risk_score": 0.2,
        }
    )
    
    success = mesh_bus.send(arb_opportunity)
    if success:
        print(f"✓ Arbitrage opportunity broadcast: {arb_opportunity.message_id[:8]}...")
        print(f"  Estimated profit: 1.5%")
        print(f"  Confidence: 85%")
    
    # Simulate execution engine accepting the trade
    print("\n--- Execution engine accepts trade ---")
    trade_accepted = create_event_packet(
        sender_id="execution_engine",
        recipient_id="quantumarb",  # Direct reply to QuantumArb
        channel="trade_updates",
        payload={
            "event_type": "trade_accepted",
            "opportunity_id": "arb_001",
            "accepted_by": "execution_engine",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_plan": {
                "exchange_a": {"action": "buy", "amount": 0.1},
                "exchange_b": {"action": "sell", "amount": 0.1},
            },
            "estimated_execution_time": "2s",
        }
    )
    
    success = mesh_bus.send(trade_accepted)
    if success:
        print(f"✓ Trade acceptance sent to QuantumArb")
    
    # Simulate trade execution
    print("\n--- Trade execution in progress ---")
    trade_executing = create_event_packet(
        sender_id="execution_engine",
        recipient_id="*",  # Broadcast update
        channel="trade_updates",
        payload={
            "event_type": "trade_executing",
            "opportunity_id": "arb_001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "progress": 0.5,
            "status": "executing",
            "current_step": "exchange_a_buy",
        }
    )
    
    success = mesh_bus.send(trade_executing)
    if success:
        print(f"✓ Trade execution update broadcast")
    
    # Check what messages agents have received
    print("\n--- Message queues for agents ---")
    for agent in trading_agents:
        messages = mesh_bus.peek(agent, max_messages=5)
        if messages:
            print(f"{agent}: {len(messages)} messages in queue")
            for msg in messages[:2]:  # Show first 2 messages
                event_type = msg.payload.get('event_type', 'unknown')
                print(f"  - {event_type} ({msg.message_id[:8]}...)")
    
    return mesh_bus


def demo_offline_agents():
    """Demonstrate store-and-forward for offline agents."""
    print("\n" + "="*60)
    print("DEMO 3: Store-and-Forward for Offline Agents")
    print("="*60)
    
    mesh_bus = MeshBus()
    
    # Register some agents
    mesh_bus.register_agent("agent_a")
    mesh_bus.register_agent("agent_b")
    mesh_bus.subscribe("agent_a", "important_updates")
    mesh_bus.subscribe("agent_b", "important_updates")
    
    print("✓ Registered agents: agent_a, agent_b")
    
    # Send message while agent_b is offline (simulated by deregistering)
    mesh_bus.deregister_agent("agent_b")
    print("✗ Deregistered agent_b (simulating offline)")
    
    # Send important update
    important_msg = create_event_packet(
        sender_id="agent_a",
        recipient_id="agent_b",  # Direct to offline agent
        payload={
            "message": "Urgent: System maintenance scheduled",
            "scheduled_time": "2024-01-15T14:00:00Z",
            "duration": "30 minutes",
            "impact": "Trading will be paused",
        },
        priority=Priority.HIGH,
        ttl_seconds=86400,  # 24 hours
    )
    
    success = mesh_bus.send(important_msg)
    if success:
        print(f"✓ Message stored for offline agent_b: {important_msg.message_id[:8]}...")
    
    # Check pending messages
    pending = mesh_bus.get_pending_count("agent_b")
    print(f"Pending messages for agent_b: {pending}")
    
    # Agent_b comes back online
    print("\n--- Agent_b comes back online ---")
    mesh_bus.register_agent("agent_b")
    mesh_bus.subscribe("agent_b", "important_updates")
    print("✓ Agent_b registered and subscribed")
    
    # Agent_b should receive the stored message
    messages = mesh_bus.receive("agent_b", max_messages=5)
    if messages:
        print(f"✓ Agent_b received {len(messages)} stored message(s)")
        for msg in messages:
            print(f"  - {msg.payload.get('message', 'No message')}")
    else:
        print("✗ Agent_b did not receive any messages")
    
    return mesh_bus


def demo_mesh_client():
    """Demonstrate using the MeshClient API."""
    print("\n" + "="*60)
    print("DEMO 4: MeshClient API Usage")
    print("="*60)
    
    # Note: This demo assumes a running SIMP broker
    print("This demo requires a running SIMP broker on http://127.0.0.1:5555")
    print("\nExample usage:")
    
    example_code = '''
from simp.mesh.client import MeshClient

# Create a client
client = MeshClient(
    agent_id="my_agent",
    broker_url="http://127.0.0.1:5555",
    api_key="your_api_key"  # Optional if no auth required
)

# Subscribe to channels
client.subscribe("safety_alerts")
client.subscribe("trade_updates")

# Send a message
message_id = client.send_to_agent(
    recipient_id="quantumarb",
    payload={"query": "current_opportunities", "timestamp": "2024-01-01T12:00:00Z"}
)

# Poll for messages
messages = client.poll(max_messages=10)
for msg in messages:
    print(f"Received from {msg.sender_id}: {msg.payload}")

# Send a system alert
client.send_system_alert(
    recipient_id="*",  # Broadcast to all
    alert_type="performance",
    severity="warning",
    message="High latency detected in exchange API",
    details={"exchange": "exchange_a", "latency_ms": 1200}
)

# Get statistics
stats = client.get_stats()
print(f"Mesh stats: {stats}")

client.close()
'''
    
    print(example_code)
    print("\nNote: Run the broker first with: python -m simp.server.http_server")


def main():
    """Run all demos."""
    print("SIMP Agent Mesh Bus - Demonstration")
    print("="*60)
    
    try:
        # Demo 1: Safety alerts
        mesh1 = demo_safety_alerts()
        
        # Demo 2: Trade updates
        mesh2 = demo_trade_updates()
        
        # Demo 3: Offline agents
        mesh3 = demo_offline_agents()
        
        # Demo 4: MeshClient API
        demo_mesh_client()
        
        # Cleanup
        mesh1.shutdown()
        mesh2.shutdown()
        mesh3.shutdown()
        
        print("\n" + "="*60)
        print("All demonstrations completed successfully!")
        print("="*60)
        print("\nNext steps:")
        print("1. Run tests: python3.10 -m pytest tests/test_mesh_*.py -v")
        print("2. Start broker: python -m simp.server.http_server")
        print("3. Use MeshClient in your agents for real communication")
        
    except Exception as e:
        print(f"\n✗ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()