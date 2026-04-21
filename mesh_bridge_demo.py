#!/usr/bin/env python3
"""
Demo of SIMP Broker-Mesh Bridge
Shows how the broker can connect to the mesh network
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

try:
    from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
    from simp.mesh.packet import MeshPacket, MessageType, Priority
    MESH_AVAILABLE = True
except ImportError:
    print("⚠️ Mesh components not available. Running in simulation mode.")
    MESH_AVAILABLE = False

@dataclass
class SimulatedIntent:
    """Simulated broker intent for demo purposes"""
    intent_type: str
    source_agent: str
    target_agent: str
    payload: Dict[str, Any]
    intent_id: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.intent_id:
            import uuid
            self.intent_id = str(uuid.uuid4())
        if not self.timestamp:
            from datetime import datetime, timezone
            self.timestamp = datetime.now(timezone.utc).isoformat()

class MeshBridge:
    """Bridge between SIMP broker and mesh network"""
    
    def __init__(self, broker_url: str = "http://127.0.0.1:5555"):
        self.broker_url = broker_url
        self.mesh_bus = None
        self.agent_map = {}  # Maps broker agent_id to mesh agent_id
        self.running = False
        self.message_queue = []
        self.queue_lock = threading.Lock()
        
        if MESH_AVAILABLE:
            self._init_mesh()
        else:
            print("🔶 Running in simulation mode (no actual mesh connection)")
    
    def _init_mesh(self):
        """Initialize mesh connection"""
        try:
            self.mesh_bus = get_enhanced_mesh_bus()
            print("✅ Mesh bus initialized")
            
            # Register bridge as a mesh agent
            self.mesh_bus.register_agent("simp_bridge")
            print("✅ Bridge registered as mesh agent")
            
        except Exception as e:
            print(f"❌ Failed to initialize mesh: {e}")
            self.mesh_bus = None
    
    def register_agent(self, broker_agent_id: str, mesh_agent_id: Optional[str] = None):
        """Register an agent for mesh communication"""
        if not mesh_agent_id:
            mesh_agent_id = f"mesh_{broker_agent_id}"
        
        self.agent_map[broker_agent_id] = mesh_agent_id
        
        if self.mesh_bus:
            try:
                self.mesh_bus.register_agent(mesh_agent_id)
                print(f"✅ Registered agent: {broker_agent_id} -> {mesh_agent_id}")
            except Exception as e:
                print(f"❌ Failed to register mesh agent {mesh_agent_id}: {e}")
        else:
            print(f"🔶 Simulated agent registration: {broker_agent_id} -> {mesh_agent_id}")
        
        return mesh_agent_id
    
    def forward_to_mesh(self, intent: SimulatedIntent) -> bool:
        """Forward a broker intent to the mesh network"""
        print(f"📤 Forwarding to mesh: {intent.intent_type} from {intent.source_agent}")
        
        if not self.mesh_bus:
            # Simulation mode
            print(f"   🔶 Simulated mesh send: {intent.intent_id}")
            with self.queue_lock:
                self.message_queue.append(("to_mesh", intent))
            return True
        
        # Convert intent to mesh packet
        mesh_packet = self._intent_to_mesh_packet(intent)
        
        try:
            # Send via mesh
            message_id = self.mesh_bus.send(mesh_packet)
            print(f"   ✅ Sent via mesh: {message_id}")
            return True
        except Exception as e:
            print(f"   ❌ Failed to send via mesh: {e}")
            return False
    
    def forward_to_broker(self, mesh_packet: MeshPacket) -> bool:
        """Forward a mesh message to the broker"""
        print(f"📥 Forwarding to broker: {mesh_packet.msg_type} from {mesh_packet.sender_id}")
        
        # Convert mesh packet to intent
        intent = self._mesh_packet_to_intent(mesh_packet)
        
        # In real implementation, this would make HTTP request to broker
        print(f"   🔶 Simulated broker send: {intent.intent_id}")
        with self.queue_lock:
            self.message_queue.append(("to_broker", intent))
        
        return True
    
    def _intent_to_mesh_packet(self, intent: SimulatedIntent) -> MeshPacket:
        """Convert broker intent to mesh packet"""
        # Determine target mesh agent ID
        target_mesh_id = self.agent_map.get(intent.target_agent, intent.target_agent)
        
        # Set priority based on intent type
        from simp.mesh.packet import Priority
        priority = Priority.HIGH if intent.intent_type == "urgent" else Priority.NORMAL
        
        # Create mesh packet
        return MeshPacket(
            msg_type=MessageType.EVENT,
            sender_id=self.agent_map.get(intent.source_agent, intent.source_agent),
            recipient_id=target_mesh_id,
            payload={
                "intent_type": intent.intent_type,
                "original_payload": intent.payload,
                "broker_intent_id": intent.intent_id,
                "timestamp": intent.timestamp
            },
            message_id=f"mesh_{intent.intent_id}",
            correlation_id=intent.intent_id,
            priority=priority,
            meta={
                "source": "simp_broker",
                "original_source": intent.source_agent,
                "bridge_version": "1.0.0"
            }
        )
    
    def _mesh_packet_to_intent(self, mesh_packet: MeshPacket) -> SimulatedIntent:
        """Convert mesh packet to broker intent"""
        # Extract original broker agent IDs
        payload = mesh_packet.payload
        
        # Find broker agent ID from mesh agent ID (reverse lookup)
        source_broker_id = None
        target_broker_id = None
        
        for broker_id, mesh_id in self.agent_map.items():
            if mesh_id == mesh_packet.sender_id:
                source_broker_id = broker_id
            if mesh_id == mesh_packet.recipient_id:
                target_broker_id = broker_id
        
        # If not found, use mesh IDs directly
        if not source_broker_id:
            source_broker_id = mesh_packet.sender_id.replace("mesh_", "")
        if not target_broker_id:
            target_broker_id = mesh_packet.recipient_id.replace("mesh_", "")
        
        return SimulatedIntent(
            intent_type=payload.get("intent_type", "mesh_message"),
            source_agent=source_broker_id,
            target_agent=target_broker_id,
            payload=payload.get("original_payload", {}),
            intent_id=payload.get("broker_intent_id", mesh_packet.message_id),
            timestamp=payload.get("timestamp", mesh_packet.timestamp)
        )
    
    def start(self):
        """Start the bridge"""
        self.running = True
        print("🚀 Mesh bridge started")
        
        # In real implementation, this would:
        # 1. Listen for broker webhook events
        # 2. Listen for mesh messages
        # 3. Process message queue
        
        # For demo, just simulate some activity
        if not MESH_AVAILABLE:
            self._simulate_activity()
    
    def stop(self):
        """Stop the bridge"""
        self.running = False
        print("🛑 Mesh bridge stopped")
    
    def _simulate_activity(self):
        """Simulate bridge activity for demo"""
        def simulation_loop():
            while self.running:
                time.sleep(2)
                # Simulate receiving a mesh message
                if self.message_queue:
                    with self.queue_lock:
                        direction, item = self.message_queue.pop(0)
                        if direction == "to_mesh":
                            print(f"🔁 Simulating mesh processing: {item.intent_id}")
                            # Simulate mesh response
                            response_intent = SimulatedIntent(
                                intent_type="response",
                                source_agent=item.target_agent,
                                target_agent=item.source_agent,
                                payload={"status": "processed", "original_id": item.intent_id}
                            )
                            self.forward_to_broker_response(response_intent)
        
        thread = threading.Thread(target=simulation_loop, daemon=True)
        thread.start()
    
    def forward_to_broker_response(self, intent: SimulatedIntent):
        """Simulate forwarding a response back to broker"""
        print(f"📨 Simulated mesh response: {intent.intent_type} to {intent.target_agent}")
        with self.queue_lock:
            self.message_queue.append(("to_broker", intent))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics"""
        return {
            "running": self.running,
            "agents_registered": len(self.agent_map),
            "queue_size": len(self.message_queue),
            "mesh_available": MESH_AVAILABLE,
            "mesh_bus_ready": self.mesh_bus is not None
        }

def demo():
    """Run a demonstration of the mesh bridge"""
    print("=" * 60)
    print("🚀 SIMP Broker-Mesh Bridge Demo")
    print("=" * 60)
    
    # Create bridge
    bridge = MeshBridge()
    
    # Register some agents
    print("\n👥 Registering agents...")
    bridge.register_agent("quantumarb")
    bridge.register_agent("kashclaw_gemma")
    bridge.register_agent("bullbear_predictor")
    bridge.register_agent("kloutbot")
    
    # Start bridge
    bridge.start()
    
    # Simulate some intents
    print("\n📨 Simulating message flow...")
    
    # Intent 1: QuantumArb to KashClaw Gemma
    intent1 = SimulatedIntent(
        intent_type="analysis_request",
        source_agent="quantumarb",
        target_agent="kashclaw_gemma",
        payload={
            "market": "BTC-USD",
            "action": "analyze_arbitrage",
            "parameters": {"timeframe": "5m", "exchanges": ["binance", "coinbase"]}
        }
    )
    bridge.forward_to_mesh(intent1)
    
    time.sleep(1)
    
    # Intent 2: BullBear to KloutBot
    intent2 = SimulatedIntent(
        intent_type="prediction_update",
        source_agent="bullbear_predictor",
        target_agent="kloutbot",
        payload={
            "prediction_id": "pred_001",
            "confidence": 0.85,
            "timestamp": "2026-04-16T07:00:00Z",
            "assets": ["SPY", "QQQ", "BTC"]
        }
    )
    bridge.forward_to_mesh(intent2)
    
    time.sleep(1)
    
    # Intent 3: Urgent message
    intent3 = SimulatedIntent(
        intent_type="urgent",
        source_agent="quantumarb",
        target_agent="kloutbot",
        payload={
            "alert": "high_volatility",
            "severity": "critical",
            "message": "Market volatility exceeding thresholds"
        }
    )
    bridge.forward_to_mesh(intent3)
    
    # Show stats
    time.sleep(2)
    print("\n📊 Bridge Statistics:")
    stats = bridge.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Show message queue
    print(f"\n📭 Message queue size: {len(bridge.message_queue)}")
    if bridge.message_queue:
        print("   Recent messages:")
        for i, (direction, intent) in enumerate(bridge.message_queue[-3:]):
            print(f"   {i+1}. {direction}: {intent.intent_type} ({intent.intent_id[:8]}...)")
    
    # Stop bridge
    time.sleep(1)
    bridge.stop()
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("\nNext steps for real implementation:")
    print("1. Fix UDP multicast port conflicts")
    print("2. Implement actual HTTP broker integration")
    print("3. Add mesh message listeners")
    print("4. Set up proper error handling and retries")
    print("=" * 60)

if __name__ == "__main__":
    demo()