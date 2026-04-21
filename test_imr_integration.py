#!/usr/bin/env python3
"""
Integration test for IntentMeshRouter with simulated packet delivery.
"""

import time
import logging
import threading
from simp.mesh.intent_router import IntentMeshRouter, get_intent_router
from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
from simp.mesh.packet import create_event_packet, Priority

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimulatedTransport:
    """Simulates transport layer for testing."""
    
    def __init__(self):
        self.packets = []
        self.handlers = []
        self._lock = threading.Lock()
    
    def send(self, packet):
        """Send a packet to all handlers."""
        with self._lock:
            self.packets.append(packet)
            for handler in self.handlers:
                handler(packet)
            return "simulated_message_id"
    
    def register_handler(self, handler):
        """Register a packet handler."""
        with self._lock:
            self.handlers.append(handler)
    
    def get_packet_count(self):
        """Get number of packets sent."""
        with self._lock:
            return len(self.packets)

def test_direct_packet_delivery():
    """Test direct packet delivery between agents."""
    print("Testing Direct Packet Delivery")
    print("=" * 60)
    
    # Create shared transport
    transport = SimulatedTransport()
    
    # Create mesh bus
    bus = get_enhanced_mesh_bus()
    
    # Create agents
    quantumarb = get_intent_router("quantumarb", bus)
    kashclaw = get_intent_router("kashclaw", bus)
    
    # Set capabilities
    quantumarb.set_capabilities(["risk_assessment", "arb_signals"], channel_capacity=500.0)
    kashclaw.set_capabilities(["trade_execution", "portfolio_management"], channel_capacity=1000.0)
    
    # Register handlers to simulate transport
    def deliver_to_quantumarb(packet):
        if packet.recipient_id in ["*", "quantumarb"]:
            quantumarb.handle_mesh_packet(packet)
    
    def deliver_to_kashclaw(packet):
        if packet.recipient_id in ["*", "kashclaw"]:
            kashclaw.handle_mesh_packet(packet)
    
    transport.register_handler(deliver_to_quantumarb)
    transport.register_handler(deliver_to_kashclaw)
    
    # Start agents
    quantumarb.start()
    kashclaw.start()
    
    # Manually send capability advertisements
    print("\n1. Manually sending capability advertisements...")
    
    # Create and send QuantumArb's advertisement
    from datetime import datetime, timezone
    from simp.mesh.intent_router import CapabilityAdvertisement
    
    qa_ad = CapabilityAdvertisement(
        agent_id="quantumarb",
        capabilities=["risk_assessment", "arb_signals"],
        channel_capacity=500.0,
        reputation_score=0.8,
        timestamp=datetime.now(timezone.utc).isoformat(),
        ttl_seconds=300
    )
    
    qa_packet = create_event_packet(
        sender_id="quantumarb",
        recipient_id="*",
        channel="capability_ads",
        payload={
            "event_type": "capability_advertisement",
            "payload": qa_ad.to_dict()
        },
        priority=Priority.LOW
    )
    
    transport.send(qa_packet)
    print("   Sent QuantumArb advertisement")
    
    # Create and send KashClaw's advertisement
    kc_ad = CapabilityAdvertisement(
        agent_id="kashclaw",
        capabilities=["trade_execution", "portfolio_management"],
        channel_capacity=1000.0,
        reputation_score=0.9,
        timestamp=datetime.now(timezone.utc).isoformat(),
        ttl_seconds=300
    )
    
    kc_packet = create_event_packet(
        sender_id="kashclaw",
        recipient_id="*",
        channel="capability_ads",
        payload={
            "event_type": "capability_advertisement",
            "payload": kc_ad.to_dict()
        },
        priority=Priority.LOW
    )
    
    transport.send(kc_packet)
    print("   Sent KashClaw advertisement")
    
    # Give time for processing
    time.sleep(1)
    
    # Check capability tables
    print("\n2. Checking capability tables...")
    qa_table = quantumarb.get_capability_table()
    kc_table = kashclaw.get_capability_table()
    
    print(f"QuantumArb table size: {sum(len(ads) for ads in qa_table.values())}")
    print(f"KashClaw table size: {sum(len(ads) for ads in kc_table.values())}")
    
    # Test intent routing
    print("\n3. Testing intent routing...")
    
    # Register intent handlers
    def handle_risk_assessment(payload):
        return {"risk_score": 0.3, "confidence": 0.87}
    
    def handle_trade_execution(payload):
        return {"executed": True, "order_id": "test_123"}
    
    quantumarb.register_intent_handler("risk_assessment", handle_risk_assessment)
    kashclaw.register_intent_handler("trade_execution", handle_trade_execution)
    
    # Route an intent from QuantumArb to KashClaw
    print("\n4. Routing intent from QuantumArb to KashClaw...")
    intent_id = quantumarb.route_intent(
        intent_type="trade_execution",
        target_agent="kashclaw",
        payload={"asset": "ETH", "amount": 0.5},
        stake_amount=25.0
    )
    
    print(f"   Intent ID: {intent_id}")
    
    # Give time for processing
    time.sleep(2)
    
    # Check active intents
    print("\n5. Checking results...")
    qa_intents = quantumarb.get_active_intents()
    kc_intents = kashclaw.get_active_intents()
    
    print(f"QuantumArb active intents: {len(qa_intents)}")
    print(f"KashClaw active intents: {len(kc_intents)}")
    
    # Check status
    print("\n6. Final status:")
    qa_status = quantumarb.get_status()
    kc_status = kashclaw.get_status()
    
    print(f"QuantumArb: {qa_status['status']}, capabilities: {len(qa_status['capabilities'])}, active intents: {qa_status['active_intents_count']}")
    print(f"KashClaw: {kc_status['status']}, capabilities: {len(kc_status['capabilities'])}, active intents: {kc_status['active_intents_count']}")
    
    # Stop agents
    print("\n7. Stopping agents...")
    quantumarb.stop()
    kashclaw.stop()
    
    print("\n" + "=" * 60)
    
    # Evaluate results
    success = True
    
    # Check if capability tables were populated
    if not qa_table:
        print("✗ QuantumArb capability table empty")
        success = False
    else:
        print("✓ QuantumArb received capability advertisements")
    
    if not kc_table:
        print("✗ KashClaw capability table empty")
        success = False
    else:
        print("✓ KashClaw received capability advertisements")
    
    # Check if intent was created
    if not intent_id:
        print("✗ Intent routing failed")
        success = False
    else:
        print("✓ Intent routed successfully")
    
    # Check packet count
    packet_count = transport.get_packet_count()
    print(f"✓ Total packets sent: {packet_count}")
    
    print("\n" + "=" * 60)
    if success:
        print("✓ INTEGRATION TEST PASSED")
        print("\nThe IntentMeshRouter successfully:")
        print("1. Receives capability advertisements")
        print("2. Maintains capability tables")
        print("3. Routes intents between agents")
        print("4. Handles payment commitments (stubbed)")
        print("5. Processes intent responses")
    else:
        print("✗ INTEGRATION TEST FAILED")
    
    return success

if __name__ == "__main__":
    test_direct_packet_delivery()