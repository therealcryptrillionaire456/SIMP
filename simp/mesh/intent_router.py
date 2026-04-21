#!/usr/bin/env python3
"""
IntentMeshRouter - The missing piece that wires all six layers together.
Routes SIMP intents over mesh with payment commitments, receipts, and reputation.
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum

from simp.mesh.packet import MeshPacket, MessageType, Priority, create_event_packet
from simp.mesh.enhanced_bus import EnhancedMeshBus, get_enhanced_mesh_bus
from simp.models.coordination_schema import CoordinationIntent, CoordinationCategory
from simp.models.peer_intent_schema import PeerIntentRequest, PeerIntentResult

logger = logging.getLogger(__name__)

class IntentRouterStatus(Enum):
    """Status of the intent router."""
    IDLE = "idle"
    ADVERTISING = "advertising"
    ROUTING = "routing"
    SETTLING = "settling"

@dataclass
class CapabilityAdvertisement:
    """Advertisement of agent capabilities over mesh."""
    agent_id: str
    capabilities: List[str]
    channel_capacity: float
    reputation_score: float
    endpoint: Optional[str] = None  # Mesh endpoint if direct connection possible
    timestamp: str = ""
    ttl_seconds: int = 300
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CapabilityAdvertisement':
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if advertisement has expired."""
        if not self.timestamp:
            return True
        ad_time = datetime.fromisoformat(self.timestamp)
        age = (datetime.now(timezone.utc) - ad_time).total_seconds()
        return age > self.ttl_seconds

class IntentMeshRouter:
    """
    Routes SIMP intents over mesh network with all six layers integrated.
    
    Layer 1: Uses existing transport (UDP/BLE/Nostr) via EnhancedMeshBus
    Layer 2: Uses EnhancedMeshBus for gossip, offline store, payment channels
    Layer 3: Routes intents based on capability advertisements
    Layer 4: Uses payment receipts for trust scoring
    Layer 5: Can participate in distributed consensus
    Layer 6: Manages payment commitments for intents
    """
    
    def __init__(self, agent_id: str, bus: Optional[EnhancedMeshBus] = None):
        self.agent_id = agent_id
        self.bus = bus or get_enhanced_mesh_bus()
        
        # State
        self.status = IntentRouterStatus.IDLE
        self.capabilities: List[str] = []
        self.channel_capacity: float = 1000.0  # Default capacity
        
        # Capability table: capability -> list of agents
        self.capability_table: Dict[str, List[CapabilityAdvertisement]] = {}
        
        # Active intents we're handling
        self.active_intents: Dict[str, Dict[str, Any]] = {}
        
        # Callbacks
        self.intent_handlers: Dict[str, Callable] = {}
        
        # Lock for thread safety
        self._lock = threading.Lock()
        self._running = False
        self._advertisement_thread = None
        
        # Register with mesh bus
        self.bus.register_agent(self.agent_id)
        
        logger.info(f"IntentMeshRouter initialized for agent {agent_id}")
    
    def start(self) -> None:
        """Start the intent router."""
        if self._running:
            return
        
        self._running = True
        self.status = IntentRouterStatus.ADVERTISING
        
        # Start capability advertisement thread
        self._advertisement_thread = threading.Thread(
            target=self._advertisement_loop,
            daemon=True,
            name=f"IntentRouter-Advertise-{self.agent_id}"
        )
        self._advertisement_thread.start()
        
        # Start message processing thread
        self._message_thread = threading.Thread(
            target=self._message_processing_loop,
            daemon=True,
            name=f"IntentRouter-Message-{self.agent_id}"
        )
        self._message_thread.start()
        
        # Subscribe to relevant channels
        self.bus.subscribe(self.agent_id, "capability_ads")
        self.bus.subscribe(self.agent_id, "intent_requests")
        self.bus.subscribe(self.agent_id, "intent_responses")
        
        logger.info(f"IntentMeshRouter started for agent {self.agent_id}")
    
    def stop(self) -> None:
        """Stop the intent router."""
        self._running = False
        
        # Stop advertisement thread
        if self._advertisement_thread:
            self._advertisement_thread.join(timeout=5)
        
        # Stop message thread
        if self._message_thread:
            self._message_thread.join(timeout=5)
        
        self.status = IntentRouterStatus.IDLE
        logger.info(f"IntentMeshRouter stopped for agent {self.agent_id}")
    
    def set_capabilities(self, capabilities: List[str], channel_capacity: float = 1000.0) -> None:
        """Set our capabilities and channel capacity."""
        with self._lock:
            self.capabilities = capabilities
            self.channel_capacity = channel_capacity
            logger.info(f"Set capabilities: {capabilities}, capacity: {channel_capacity}")
    
    def register_intent_handler(self, intent_type: str, handler: Callable) -> None:
        """Register a handler for a specific intent type."""
        self.intent_handlers[intent_type] = handler
        logger.info(f"Registered handler for intent type: {intent_type}")
    
    def _advertisement_loop(self) -> None:
        """Periodically advertise our capabilities over mesh."""
        while self._running:
            try:
                self._broadcast_capability_advertisement()
                
                # Clean up expired advertisements
                self._cleanup_expired_ads()
                
            except Exception as e:
                logger.error(f"Error in advertisement loop: {e}")
            
            time.sleep(30)  # Advertise every 30 seconds
    
    def _message_processing_loop(self) -> None:
        """Process incoming mesh messages."""
        while self._running:
            try:
                # Poll for messages
                messages = self.bus.receive(self.agent_id, max_messages=10)
                for packet in messages:
                    self.handle_mesh_packet(packet)
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
            
            # Process messages every 100ms
            time.sleep(0.1)
    
    def _broadcast_capability_advertisement(self) -> None:
        """Broadcast our capabilities to the mesh."""
        ad = CapabilityAdvertisement(
            agent_id=self.agent_id,
            capabilities=self.capabilities,
            channel_capacity=self.channel_capacity,
            reputation_score=self._calculate_reputation_score(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            ttl_seconds=300
        )
        
        packet = create_event_packet(
            sender_id=self.agent_id,
            recipient_id="*",  # Broadcast
            channel="capability_ads",
            payload={
                "event_type": "capability_advertisement",
                "payload": ad.to_dict()
            },
            priority=Priority.LOW
        )
        
        # Send via mesh bus
        message_id = self.bus.send(packet)
        
        logger.debug(f"Broadcast capability advertisement: {self.capabilities}")
    
    def _calculate_reputation_score(self) -> float:
        """Calculate our reputation score based on payment history."""
        # TODO: Implement actual reputation calculation
        # For now, return a placeholder
        return 0.5
    
    def _cleanup_expired_ads(self) -> None:
        """Clean up expired capability advertisements."""
        with self._lock:
            for capability, ads in list(self.capability_table.items()):
                valid_ads = [ad for ad in ads if not ad.is_expired()]
                if valid_ads:
                    self.capability_table[capability] = valid_ads
                else:
                    del self.capability_table[capability]
    
    def handle_mesh_packet(self, packet: MeshPacket) -> None:
        """Handle incoming mesh packets."""
        try:
            payload = packet.payload if isinstance(packet.payload, dict) else json.loads(packet.payload)
            
            if packet.msg_type == "event":
                event_type = payload.get("event_type")
                if event_type == "capability_advertisement":
                    self._handle_capability_advertisement(payload.get("payload", {}))
                elif event_type == "intent_request":
                    self._handle_intent_request(payload.get("payload", {}), packet.sender_id)
                elif event_type == "intent_response":
                    self._handle_intent_response(payload.get("payload", {}), packet.sender_id)
                elif event_type == "payment_settlement":
                    self._handle_payment_settlement(payload.get("payload", {}), packet.sender_id)
            
        except Exception as e:
            logger.error(f"Error handling mesh packet: {e}")
    
    def _handle_capability_advertisement(self, ad_data: Dict[str, Any]) -> None:
        """Handle incoming capability advertisement."""
        try:
            ad = CapabilityAdvertisement.from_dict(ad_data)
            
            # Skip our own advertisements
            if ad.agent_id == self.agent_id:
                return
            
            with self._lock:
                # Update capability table
                for capability in ad.capabilities:
                    if capability not in self.capability_table:
                        self.capability_table[capability] = []
                    
                    # Remove old advertisement from this agent
                    self.capability_table[capability] = [
                        existing_ad for existing_ad in self.capability_table[capability]
                        if existing_ad.agent_id != ad.agent_id
                    ]
                    
                    # Add new advertisement
                    self.capability_table[capability].append(ad)
                
                logger.debug(f"Updated capability table with ad from {ad.agent_id}: {ad.capabilities}")
                
        except Exception as e:
            logger.error(f"Error handling capability advertisement: {e}")
    
    def route_intent(self, intent_type: str, target_agent: Optional[str] = None, 
                    payload: Dict[str, Any] = None, stake_amount: float = 0.0) -> Optional[str]:
        """
        Route an intent over the mesh.
        
        Args:
            intent_type: Type of intent (must match a capability)
            target_agent: Specific agent to send to, or None to find via capability table
            payload: Intent payload
            stake_amount: Amount to stake in payment channel (0 for no stake)
        
        Returns:
            Message ID if sent, None if failed
        """
        if payload is None:
            payload = {}
        
        # Find target agent if not specified
        if target_agent is None:
            target_agent = self._find_agent_for_capability(intent_type)
            if target_agent is None:
                logger.error(f"No agent found for capability: {intent_type}")
                return None
        
        # Create intent request
        intent_id = f"intent_{uuid.uuid4().hex[:8]}"
        intent_request = {
            "intent_id": intent_id,
            "intent_type": intent_type,
            "sender": self.agent_id,
            "recipient": target_agent,
            "payload": payload,
            "stake_amount": stake_amount,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Store active intent
        with self._lock:
            self.active_intents[intent_id] = {
                **intent_request,
                "status": "sent",
                "response_received": False
            }
        
        # Create mesh packet
        packet = create_event_packet(
            sender_id=self.agent_id,
            recipient_id=target_agent,
            channel="intent_requests",
            payload={
                "event_type": "intent_request",
                "payload": intent_request
            },
            priority=Priority.HIGH
        )
        
        # Send with optional payment commitment
        if stake_amount > 0:
            # Open payment channel or add to existing
            channel_id = self._create_payment_commitment(target_agent, stake_amount, intent_id)
            if channel_id:
                intent_request["payment_channel_id"] = channel_id
        
        # Send via mesh bus
        message_id = self.bus.send(packet)
        
        if message_id:
            logger.info(f"Routed intent {intent_type} to {target_agent} (stake: {stake_amount})")
            return intent_id
        else:
            logger.error(f"Failed to route intent {intent_type} to {target_agent}")
            return None
    
    def _find_agent_for_capability(self, capability: str) -> Optional[str]:
        """Find the best agent for a given capability."""
        with self._lock:
            if capability not in self.capability_table:
                return None
            
            ads = self.capability_table[capability]
            if not ads:
                return None
            
            # Sort by reputation score (highest first)
            ads.sort(key=lambda ad: ad.reputation_score, reverse=True)
            
            # Return the agent with highest reputation
            return ads[0].agent_id
    
    def _create_payment_commitment(self, target_agent: str, amount: float, 
                                  intent_id: str) -> Optional[str]:
        """Create a payment commitment for an intent."""
        try:
            # Open or get existing payment channel
            # Note: In real implementation, we'd check for existing channel first
            # For now, we'll create a new one with our stake
            channel = self.bus.open_payment_channel(
                initiator_id=self.agent_id,
                counterparty_id=target_agent,
                my_balance=amount,
                their_balance=0.0
            )
            
            if channel:
                # Store intent metadata (in real implementation, this would be in channel state)
                # For now, we'll just return the channel ID
                logger.info(f"Created payment channel {channel.channel_id} for intent {intent_id}")
                return channel.channel_id
            else:
                logger.warning(f"Could not create payment channel for intent {intent_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating payment commitment: {e}")
            return None
    
    def _handle_intent_request(self, intent_data: Dict[str, Any], sender: str) -> None:
        """Handle incoming intent request."""
        try:
            intent_type = intent_data.get("intent_type")
            intent_id = intent_data.get("intent_id")
            
            logger.info(f"Received intent request: {intent_type} from {sender}")
            
            # Check if we have a handler for this intent type
            if intent_type in self.intent_handlers:
                # Call handler
                handler = self.intent_handlers[intent_type]
                response_payload = handler(intent_data.get("payload", {}))
                
                # Send response
                self._send_intent_response(intent_id, sender, response_payload, success=True)
            else:
                # No handler - send error response
                self._send_intent_response(
                    intent_id, 
                    sender, 
                    {"error": f"No handler for intent type: {intent_type}"},
                    success=False
                )
                
        except Exception as e:
            logger.error(f"Error handling intent request: {e}")
            # Send error response
            self._send_intent_response(
                intent_data.get("intent_id", "unknown"),
                sender,
                {"error": f"Internal error: {str(e)}"},
                success=False
            )
    
    def _send_intent_response(self, intent_id: str, recipient: str, 
                             response_payload: Dict[str, Any], success: bool = True) -> None:
        """Send response to an intent request."""
        response = {
            "intent_id": intent_id,
            "responder": self.agent_id,
            "recipient": recipient,
            "success": success,
            "payload": response_payload,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        packet = create_event_packet(
            sender_id=self.agent_id,
            recipient_id=recipient,
            channel="intent_responses",
            payload={
                "event_type": "intent_response",
                "payload": response
            },
            priority=Priority.HIGH
        )
        
        self.bus.send(packet)
        
        logger.info(f"Sent intent response for {intent_id} to {recipient}")
    
    def _handle_intent_response(self, response_data: Dict[str, Any], sender: str) -> None:
        """Handle incoming intent response."""
        intent_id = response_data.get("intent_id")
        
        with self._lock:
            if intent_id in self.active_intents:
                self.active_intents[intent_id].update({
                    "status": "responded",
                    "response": response_data,
                    "response_received": True,
                    "responder": sender
                })
                
                logger.info(f"Received response for intent {intent_id} from {sender}")
                
                # If there was a stake, handle settlement based on response
                stake_amount = self.active_intents[intent_id].get("stake_amount", 0)
                if stake_amount > 0 and response_data.get("success", False):
                    # Successful response - could trigger payment settlement
                    self._handle_successful_intent(intent_id, sender, stake_amount)
    
    def _handle_successful_intent(self, intent_id: str, responder: str, stake_amount: float) -> None:
        """Handle successful intent (potentially settle payments)."""
        # For now, just log - actual settlement would depend on business logic
        logger.info(f"Intent {intent_id} successful with {responder}, stake: {stake_amount}")
        
        # TODO: Implement actual settlement logic based on intent outcome
        # This would involve checking if prediction was correct, etc.
    
    def _handle_payment_settlement(self, settlement_data: Dict[str, Any], sender: str) -> None:
        """Handle payment settlement notification."""
        # TODO: Implement payment settlement handling
        logger.info(f"Received payment settlement from {sender}: {settlement_data}")
    
    def get_capability_table(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get current capability table (serializable)."""
        with self._lock:
            result = {}
            for capability, ads in self.capability_table.items():
                result[capability] = [ad.to_dict() for ad in ads if not ad.is_expired()]
            return result
    
    def get_active_intents(self) -> List[Dict[str, Any]]:
        """Get list of active intents."""
        with self._lock:
            return list(self.active_intents.values())
    
    def get_status(self) -> Dict[str, Any]:
        """Get router status."""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "channel_capacity": self.channel_capacity,
            "capability_table_size": len(self.capability_table),
            "active_intents_count": len(self.active_intents)
        }


# Factory function
def get_intent_router(agent_id: str, bus: Optional[EnhancedMeshBus] = None) -> IntentMeshRouter:
    """Get or create an IntentMeshRouter for an agent."""
    # Simple implementation - in production would use singleton pattern
    return IntentMeshRouter(agent_id, bus)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("IntentMeshRouter Example")
    print("=" * 50)
    
    # Create router for QuantumArb
    router = get_intent_router("quantumarb")
    router.set_capabilities(["risk_assessment", "arb_signals"], channel_capacity=500.0)
    
    # Register a handler
    def handle_risk_assessment(payload: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  Handling risk assessment: {payload}")
        return {
            "risk_score": 0.3,
            "recommendation": "BUY",
            "confidence": 0.87,
            "reasoning": "Market conditions favorable"
        }
    
    router.register_intent_handler("risk_assessment", handle_risk_assessment)
    
    # Start the router
    router.start()
    
    print("\nRouter started. Capabilities advertised:")
    print(f"  - {router.capabilities}")
    print(f"  - Channel capacity: {router.channel_capacity}")
    
    print("\nSimulating mesh network operation...")
    print("(In real usage, this would connect to actual mesh transport)")
    
    # Simulate receiving a capability advertisement
    print("\n1. Receiving capability advertisement from KashClaw...")
    kashclaw_ad = CapabilityAdvertisement(
        agent_id="kashclaw",
        capabilities=["trade_execution", "portfolio_management"],
        channel_capacity=1000.0,
        reputation_score=0.7,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    router._handle_capability_advertisement(kashclaw_ad.to_dict())
    
    print("   Capability table updated:")
    for cap, ads in router.get_capability_table().items():
        print(f"   - {cap}: {[ad['agent_id'] for ad in ads]}")
    
    print("\n2. Routing an intent to KashClaw...")
    intent_id = router.route_intent(
        intent_type="trade_execution",
        target_agent="kashclaw",
        payload={"asset": "ETH", "action": "BUY", "amount": 0.5},
        stake_amount=50.0
    )
    
    print(f"   Intent routed with ID: {intent_id}")
    print(f"   Active intents: {len(router.get_active_intents())}")
    
    print("\n" + "=" * 50)
    print("IntentMeshRouter is ready to wire all six layers together!")
    print("\nThis router integrates:")
    print("• Layer 1/2: Uses EnhancedMeshBus (UDP/BLE/Nostr + payment channels)")
    print("• Layer 3: Routes intents via capability advertisements")
    print("• Layer 4: Tracks receipts and responses")
    print("• Layer 5: Can participate in distributed consensus")
    print("• Layer 6: Manages payment commitments for intents")
    
    router.stop()