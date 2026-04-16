"""
Simple Intent Mesh Router that works with actual PeerIntentRequest schema.
"""

import json
import logging
import threading
import time
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

from ..models.peer_intent_schema import (
    PeerIntentRequest,
    PeerIntentResult,
    validate_request,
    validate_result
)
from .packet import MeshPacket, MessageType, Priority, create_event_packet
from .enhanced_bus import get_enhanced_mesh_bus

logger = logging.getLogger(__name__)

@dataclass
class CapabilityAdvertisement:
    """Advertisement of agent capabilities."""
    agent_id: str
    endpoint: str
    capabilities: List[str]  # List of intent_types this agent can handle
    channel_capacity: float = 0.0
    last_seen: float = field(default_factory=time.time)
    reputation_score: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "endpoint": self.endpoint,
            "capabilities": self.capabilities,
            "channel_capacity": self.channel_capacity,
            "last_seen": self.last_seen,
            "reputation_score": self.reputation_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CapabilityAdvertisement':
        """Create from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            endpoint=data["endpoint"],
            capabilities=data["capabilities"],
            channel_capacity=data.get("channel_capacity", 0.0),
            last_seen=data.get("last_seen", time.time()),
            reputation_score=data.get("reputation_score", 1.0)
        )

class SimpleIntentMeshRouter:
    """
    Simple intent router that works with actual PeerIntentRequest schema.
    """
    
    def __init__(self, local_agent_id: str, local_endpoint: str):
        """
        Initialize simple intent router.
        
        Args:
            local_agent_id: ID of local agent
            local_endpoint: Endpoint where this agent can be reached
        """
        self.local_agent_id = local_agent_id
        self.local_endpoint = local_endpoint
        
        # Get enhanced mesh bus
        self.mesh_bus = get_enhanced_mesh_bus()
        
        # Register with mesh bus
        self.mesh_bus.register_agent(local_agent_id)
        
        # Capability registry
        self._capabilities: Dict[str, CapabilityAdvertisement] = {}
        self._capabilities_lock = threading.RLock()
        
        # Local capabilities
        self._local_capabilities: Set[str] = set()
        
        # Callback for received intents
        self._intent_callback: Optional[Callable[[PeerIntentRequest], PeerIntentResult]] = None
        
        # Start capability advertisement
        self._advertise_capabilities()
        
        # Subscribe to mesh channels
        self._setup_subscriptions()
        
        logger.info(f"Simple intent router initialized for {local_agent_id}")
    
    def _advertise_capabilities(self) -> None:
        """Advertise local capabilities to mesh."""
        # Convert local capabilities to list
        capabilities = list(self._local_capabilities)
        
        if not capabilities:
            capabilities = ["mesh_relay"]  # Default capability
        
        advertisement = CapabilityAdvertisement(
            agent_id=self.local_agent_id,
            endpoint=self.local_endpoint,
            capabilities=capabilities,
            channel_capacity=1000.0,
            reputation_score=1.0
        )
        
        # Broadcast capability advertisement
        self._broadcast_capability_ad(advertisement)
        
        logger.info(f"Advertised capabilities: {capabilities}")
    
    def _broadcast_capability_ad(self, ad: CapabilityAdvertisement) -> None:
        """Broadcast capability advertisement to mesh."""
        packet = create_event_packet(
            sender_id=self.local_agent_id,
            recipient_id="*",  # Broadcast
            channel="capability_ads",
            payload=ad.to_dict()
        )
        
        self.mesh_bus.send(packet)
    
    def _setup_subscriptions(self) -> None:
        """Subscribe to mesh channels."""
        # Subscribe to capability advertisements
        self.mesh_bus.subscribe(
            agent_id=self.local_agent_id,
            channel="capability_ads"
        )
        
        # Subscribe to intent requests
        self.mesh_bus.subscribe(
            agent_id=self.local_agent_id,
            channel="intent_requests"
        )
        
        # Subscribe to intent responses
        self.mesh_bus.subscribe(
            agent_id=self.local_agent_id,
            channel="intent_responses"
        )
        
        logger.info("Subscribed to mesh channels")
    
    def add_capability(self, intent_type: str) -> None:
        """Add a local capability."""
        self._local_capabilities.add(intent_type)
        self._advertise_capabilities()
        logger.info(f"Added capability: {intent_type}")
    
    def set_intent_callback(self, callback: Callable[[PeerIntentRequest], PeerIntentResult]) -> None:
        """Set callback for processing received intents."""
        self._intent_callback = callback
        logger.info("Intent callback set")
    
    def process_messages(self) -> None:
        """Process incoming mesh messages."""
        try:
            # Get messages for this agent
            packets = self.mesh_bus.receive(self.local_agent_id, max_messages=10)
            
            for packet in packets:
                self._handle_packet(packet)
                
        except Exception as e:
            logger.error(f"Error processing messages: {e}")
    
    def _handle_packet(self, packet: MeshPacket) -> None:
        """Handle incoming mesh packet."""
        try:
            if packet.channel == "capability_ads":
                self._handle_capability_ad(packet)
            elif packet.channel == "intent_requests":
                self._handle_intent_request(packet)
            elif packet.channel == "intent_responses":
                self._handle_intent_response(packet)
                
        except Exception as e:
            logger.error(f"Error handling packet: {e}")
    
    def _handle_capability_ad(self, packet: MeshPacket) -> None:
        """Handle capability advertisement."""
        try:
            if packet.sender_id == self.local_agent_id:
                return  # Skip our own ads
            
            ad_data = packet.payload
            ad = CapabilityAdvertisement.from_dict(ad_data)
            
            with self._capabilities_lock:
                self._capabilities[ad.agent_id] = ad
            
            logger.debug(f"Updated capabilities for {ad.agent_id}: {ad.capabilities}")
            
        except Exception as e:
            logger.error(f"Failed to handle capability ad: {e}")
    
    def _handle_intent_request(self, packet: MeshPacket) -> None:
        """Handle intent request."""
        try:
            # Check if this intent is for us
            if packet.recipient_id not in [self.local_agent_id, "*"]:
                return  # Not for us
            
            request_data = packet.payload
            
            # Validate request
            validate_request(request_data)
            
            # Create request object
            request = PeerIntentRequest(
                intent_type=request_data["intent_type"],
                source_agent=request_data["source_agent"],
                target_agent=request_data["target_agent"],
                task_id=request_data["task_id"],
                topic=request_data["topic"],
                prompt=request_data["prompt"],
                intent_id=request_data.get("intent_id", str(uuid.uuid4())),
                timestamp=request_data.get("timestamp"),
                schema_version=request_data.get("schema_version"),
                context=request_data.get("context", {}),
                priority=request_data.get("priority", "normal"),
                requires_response=request_data.get("requires_response", True),
                timeout_seconds=request_data.get("timeout_seconds", 300),
                dry_run=request_data.get("dry_run", True)
            )
            
            # Check if we can handle this intent type
            if request.intent_type not in self._local_capabilities:
                logger.debug(f"Cannot handle intent type: {request.intent_type}")
                return
            
            # Process intent if we have a callback
            if self._intent_callback:
                logger.info(f"Processing intent {request.intent_id} ({request.intent_type})")
                
                try:
                    result = self._intent_callback(request)
                    
                    # Send response back
                    self._send_intent_response(result, packet.sender_id)
                    
                except Exception as e:
                    logger.error(f"Intent processing failed: {e}")
                    # Send error response
                    error_result = PeerIntentResult.error(
                        intent_type=request.intent_type,
                        source_agent=request.source_agent,
                        target_agent=request.target_agent,
                        task_id=request.task_id,
                        error_message=str(e),
                        error_code="PROCESSING_ERROR"
                    )
                    self._send_intent_response(error_result, packet.sender_id)
            
        except Exception as e:
            logger.error(f"Failed to handle intent request: {e}")
    
    def _handle_intent_response(self, packet: MeshPacket) -> None:
        """Handle intent response."""
        try:
            response_data = packet.payload
            
            # Validate response
            validate_result(response_data)
            
            # Log the response
            logger.info(f"Received intent response: {response_data.get('task_id')}")
            
        except Exception as e:
            logger.error(f"Failed to handle intent response: {e}")
    
    def _send_intent_response(self, result: PeerIntentResult, recipient_id: str) -> None:
        """Send intent response through mesh."""
        packet = create_event_packet(
            sender_id=self.local_agent_id,
            recipient_id=recipient_id,
            channel="intent_responses",
            payload=result.to_dict()
        )
        
        self.mesh_bus.send(packet)
        logger.debug(f"Sent intent response to {recipient_id}")
    
    def route_intent(self, request: PeerIntentRequest) -> bool:
        """
        Route an intent through the mesh.
        
        Args:
            request: Intent request to route
            
        Returns:
            True if sent successfully
        """
        # Find suitable agent for this intent type
        target_agent = self._find_agent_for_intent_type(request.intent_type)
        
        if not target_agent:
            logger.warning(f"No agent found for intent type {request.intent_type}")
            return False
        
        # Update target agent
        request.target_agent = target_agent
        
        # Send intent through mesh
        packet = create_event_packet(
            sender_id=self.local_agent_id,
            recipient_id=target_agent,
            channel="intent_requests",
            payload=request.to_dict(),
            priority=Priority.HIGH
        )
        
        if self.mesh_bus.send(packet):
            logger.info(f"Routed intent {request.intent_id} to {target_agent}")
            return True
        else:
            logger.error(f"Failed to send intent {request.intent_id}")
            return False
    
    def _find_agent_for_intent_type(self, intent_type: str) -> Optional[str]:
        """
        Find best agent for an intent type.
        """
        with self._capabilities_lock:
            suitable_agents = []
            
            for agent_id, ad in self._capabilities.items():
                if intent_type in ad.capabilities:
                    # Calculate score based on reputation and recency
                    score = ad.reputation_score
                    
                    # Penalize for being offline too long
                    offline_time = time.time() - ad.last_seen
                    if offline_time > 300:  # 5 minutes
                        score *= 0.5
                    
                    suitable_agents.append((score, offline_time, agent_id))
            
            if not suitable_agents:
                return None
            
            # Sort by score (highest first), then by recency
            suitable_agents.sort(key=lambda x: (-x[0], x[1]))
            
            return suitable_agents[0][2]
    
    def get_capabilities(self) -> List[CapabilityAdvertisement]:
        """Get all known capability advertisements."""
        with self._capabilities_lock:
            return list(self._capabilities.values())
    
    def update_reputation(self, agent_id: str, delta: float) -> None:
        """Update reputation score for an agent."""
        with self._capabilities_lock:
            if agent_id in self._capabilities:
                ad = self._capabilities[agent_id]
                ad.reputation_score = max(0.0, min(5.0, ad.reputation_score + delta))
                logger.debug(f"Updated reputation for {agent_id}: {ad.reputation_score}")


# Factory function
def create_simple_intent_router(local_agent_id: str, local_endpoint: str) -> SimpleIntentMeshRouter:
    """
    Create a simple intent mesh router.
    """
    return SimpleIntentMeshRouter(local_agent_id, local_endpoint)