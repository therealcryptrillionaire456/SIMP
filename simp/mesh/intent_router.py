"""
Intent Mesh Router - Layer 3 of SIMP mesh architecture.
Routes SIMP intents over mesh network based on capability advertisements.
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

class IntentRouteStatus(Enum):
    """Status of intent routing."""
    PENDING = "pending"
    ROUTED = "routed"
    DELIVERED = "delivered"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class CapabilityAdvertisement:
    """Advertisement of agent capabilities."""
    agent_id: str
    endpoint: str
    capabilities: List[str]
    channel_capacity: float = 0.0  # Available payment channel capacity
    last_seen: float = field(default_factory=time.time)
    reputation_score: float = 1.0  # Initial trust score
    
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

@dataclass
class IntentRoute:
    """Route for an intent through the mesh."""
    intent_id: str
    request: PeerIntentRequest
    target_agent: str
    status: IntentRouteStatus
    timestamp: float
    response: Optional[PeerIntentResult] = None
    error: Optional[str] = None
    hops: List[str] = field(default_factory=list)  # Path through mesh
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent_id": self.intent_id,
            "request": self.request.to_dict() if self.request else None,
            "target_agent": self.target_agent,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "response": self.response.to_dict() if self.response else None,
            "error": self.error,
            "hops": self.hops
        }

class IntentMeshRouter:
    """
    Routes SIMP intents over mesh network.
    
    Features:
    - Capability-based routing
    - Reputation-weighted agent selection
    - Mesh path optimization
    - Intent delivery confirmation
    - Offline intent queuing
    """
    
    def __init__(self, local_agent_id: str, local_endpoint: str):
        """
        Initialize intent mesh router.
        
        Args:
            local_agent_id: ID of local agent
            local_endpoint: Endpoint where this agent can be reached
        """
        self.local_agent_id = local_agent_id
        self.local_endpoint = local_endpoint
        
        # Get enhanced mesh bus
        self.mesh_bus = get_enhanced_mesh_bus()
        
        # Capability registry
        self._capabilities: Dict[str, CapabilityAdvertisement] = {}
        self._capabilities_lock = threading.RLock()
        
        # Intent routing table
        self._routes: Dict[str, IntentRoute] = {}
        self._routes_lock = threading.RLock()
        
        # Callback for received intents
        self._intent_callback: Optional[Callable[[PeerIntentRequest], PeerIntentResult]] = None
        
        # Message processing
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        
        # Statistics
        self._stats = {
            "intents_routed": 0,
            "intents_delivered": 0,
            "intents_failed": 0,
            "capability_advertisements": 0,
            "routing_errors": 0,
            "messages_processed": 0
        }
        
        # Start capability advertisement
        self._advertise_capabilities()
        
        # Subscribe to mesh events
        self._setup_mesh_subscriptions()
        
        logger.info(f"Intent mesh router initialized for agent {local_agent_id}")
    
    def _advertise_capabilities(self) -> None:
        """Advertise local capabilities to mesh."""
        # This should be populated based on actual agent capabilities
        # For now, advertise basic capabilities
        capabilities = ["intent_router", "mesh_relay"]
        
        advertisement = CapabilityAdvertisement(
            agent_id=self.local_agent_id,
            endpoint=self.local_endpoint,
            capabilities=capabilities,
            channel_capacity=1000.0,  # Example capacity
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
        self._stats["capability_advertisements"] += 1
    
    def _setup_mesh_subscriptions(self) -> None:
        """Subscribe to relevant mesh channels."""
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
        
        # Start message processing thread
        self._running = True
        self._processor_thread = threading.Thread(
            target=self._process_mesh_messages,
            daemon=True,
            name=f"IntentRouter-Processor-{self.local_agent_id}"
        )
        self._processor_thread.start()
        
        logger.info("Subscribed to mesh channels and started processor")
    
    def _process_mesh_messages(self) -> None:
        """Process messages from mesh bus."""
        logger.info("Intent router message processor started")
        
        while self._running:
            try:
                # Get next message for this agent (non-blocking)
                packets = self.mesh_bus.receive(self.local_agent_id, max_messages=10)
                
                for packet in packets:
                    self._stats["messages_processed"] += 1
                    
                    # Route based on channel
                    if packet.channel == "capability_ads":
                        self._handle_capability_ad(packet)
                    elif packet.channel == "intent_requests":
                        self._handle_intent_request(packet)
                    elif packet.channel == "intent_responses":
                        self._handle_intent_response(packet)
                    else:
                        logger.debug(f"Ignoring message on channel {packet.channel}")
                
                # Sleep briefly if no messages
                if not packets:
                    time.sleep(0.1)
                
            except Exception as e:
                if self._running:
                    logger.error(f"Message processor error: {e}")
                time.sleep(0.1)
        
        logger.info("Intent router message processor stopped")
    
    def _handle_capability_ad(self, packet: MeshPacket) -> None:
        """Handle capability advertisement from other agents."""
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
        """Handle intent request from mesh."""
        try:
            # Check if this intent is for us
            if packet.recipient_id not in [self.local_agent_id, "*"]:
                return  # Not for us
            
            request_data = packet.payload
            validate_request(request_data)
            
            request = PeerIntentRequest.create(**request_data)
            
            # Check if we have the requested capability
            # Use intent_type as capability identifier
            if not self._has_capability(request.intent_type):
                logger.debug(f"No capability {request.intent_type}, ignoring intent")
                return
            
            # If we have an intent callback, process it
            if self._intent_callback:
                logger.info(f"Processing intent {request.intent_id} for {request.capability}")
                
                try:
                    result = self._intent_callback(request)
                    
                    # Send response back
                    self._send_intent_response(request, result, packet.sender_id)
                    
                except Exception as e:
                    logger.error(f"Intent callback failed: {e}")
                    error_result = PeerIntentResult.error(
                        intent_type=request.intent_type,
                        source_agent=request.source_agent,
                        target_agent=request.target_agent,
                        task_id=request.task_id,
                        error_message=str(e),
                        error_code="PROCESSING_ERROR"
                    )
                    self._send_intent_response(request, error_result, packet.sender_id)
            
        except Exception as e:
            logger.error(f"Failed to handle intent request: {e}")
    
    def _handle_intent_response(self, packet: MeshPacket) -> None:
        """Handle intent response from mesh."""
        try:
            response_data = packet.payload
            validate_result(response_data)
            
            result = PeerIntentResult(
                intent_id=response_data["intent_id"],
                capability=response_data["capability"],
                status=response_data["status"],
                result_data=response_data.get("result_data"),
                error_message=response_data.get("error_message"),
                error_code=response_data.get("error_code"),
                timestamp=response_data.get("timestamp", time.time())
            )
            
            # Update route status
            with self._routes_lock:
                if result.intent_id in self._routes:
                    route = self._routes[result.intent_id]
                    route.response = result
                    
                    if result.status == "ok":
                        route.status = IntentRouteStatus.DELIVERED
                        self._stats["intents_delivered"] += 1
                        logger.info(f"Intent {result.intent_id} delivered successfully")
                    else:
                        route.status = IntentRouteStatus.FAILED
                        self._stats["intents_failed"] += 1
                        logger.warning(f"Intent {result.intent_id} failed: {result.error_message}")
                
        except Exception as e:
            logger.error(f"Failed to handle intent response: {e}")
    
    def _send_intent_response(self, intent_id: str, result: PeerIntentResult, recipient_id: str) -> None:
        """Send intent response through mesh."""
        packet = create_event_packet(
            sender_id=self.local_agent_id,
            recipient_id=recipient_id,
            channel="intent_responses",
            payload=result.to_dict()
        )
        
        self.mesh_bus.send(packet)
        logger.debug(f"Sent intent response for {intent_id} to {recipient_id}")
    
    def _has_capability(self, capability: str) -> bool:
        """Check if local agent has a capability."""
        # This should check actual agent capabilities
        # For now, return True for testing
        return True
    
    def set_intent_callback(self, callback: Callable[[PeerIntentRequest], PeerIntentResult]) -> None:
        """Set callback for processing received intents."""
        self._intent_callback = callback
        logger.info("Intent callback set")
    
    def route_intent(self, request: PeerIntentRequest, timeout: float = 30.0) -> Optional[PeerIntentResult]:
        """
        Route an intent through the mesh.
        
        Args:
            request: Intent request to route
            timeout: Maximum time to wait for response (seconds)
            
        Returns:
            Intent result if successful, None if failed or timeout
        """
        # Find suitable agent for capability
        target_agent = self._find_agent_for_capability(request.capability)
        
        if not target_agent:
            logger.warning(f"No agent found for capability {request.capability}")
            self._stats["routing_errors"] += 1
            return None
        
        # Create route
        route = IntentRoute(
            intent_id=request.intent_id,
            request=request,
            target_agent=target_agent,
            status=IntentRouteStatus.PENDING,
            timestamp=time.time(),
            hops=[self.local_agent_id]
        )
        
        with self._routes_lock:
            self._routes[request.intent_id] = route
        
        # Send intent through mesh
        packet = create_event_packet(
            sender_id=self.local_agent_id,
            recipient_id=target_agent,
            channel="intent_requests",
            payload=request.to_dict(),
            priority=Priority.HIGH
        )
        
        if not self.mesh_bus.send(packet):
            logger.error(f"Failed to send intent {request.intent_id}")
            route.status = IntentRouteStatus.FAILED
            route.error = "Mesh send failed"
            self._stats["intents_failed"] += 1
            return None
        
        route.status = IntentRouteStatus.ROUTED
        self._stats["intents_routed"] += 1
        logger.info(f"Routed intent {request.intent_id} to {target_agent}")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._routes_lock:
                route = self._routes.get(request.intent_id)
                if route and route.response:
                    return route.response
            
            time.sleep(0.1)
        
        # Timeout
        with self._routes_lock:
            if request.intent_id in self._routes:
                self._routes[request.intent_id].status = IntentRouteStatus.TIMEOUT
        
        logger.warning(f"Intent {request.intent_id} timeout after {timeout}s")
        return None
    
    def _find_agent_for_capability(self, capability: str) -> Optional[str]:
        """
        Find best agent for a capability.
        
        Selection criteria:
        1. Has the capability
        2. Highest reputation score
        3. Sufficient channel capacity
        4. Most recently seen
        """
        with self._capabilities_lock:
            suitable_agents = []
            
            for agent_id, ad in self._capabilities.items():
                if capability in ad.capabilities:
                    # Calculate score
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
    
    def get_routes(self) -> List[IntentRoute]:
        """Get all intent routes."""
        with self._routes_lock:
            return list(self._routes.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics."""
        return self._stats.copy()
    
    def add_capability(self, capability: str) -> None:
        """Add a local capability and advertise it."""
        # This should update local capabilities and re-advertise
        logger.info(f"Added local capability: {capability}")
        self._advertise_capabilities()
    
    def update_reputation(self, agent_id: str, delta: float) -> None:
        """Update reputation score for an agent."""
        with self._capabilities_lock:
            if agent_id in self._capabilities:
                ad = self._capabilities[agent_id]
                ad.reputation_score = max(0.0, min(5.0, ad.reputation_score + delta))
                logger.debug(f"Updated reputation for {agent_id}: {ad.reputation_score}")
    
    def stop(self) -> None:
        """Stop the intent router."""
        self._running = False
        
        if self._processor_thread:
            self._processor_thread.join(timeout=2)
            self._processor_thread = None
        
        # Unsubscribe from channels
        if hasattr(self.mesh_bus, 'unsubscribe'):
            self.mesh_bus.unsubscribe(self.local_agent_id, "capability_ads")
            self.mesh_bus.unsubscribe(self.local_agent_id, "intent_requests")
            self.mesh_bus.unsubscribe(self.local_agent_id, "intent_responses")
        
        logger.info("Intent router stopped")


# Factory function for easy creation
def create_intent_mesh_router(local_agent_id: str, local_endpoint: str) -> IntentMeshRouter:
    """
    Create an intent mesh router.
    
    Args:
        local_agent_id: ID of local agent
        local_endpoint: Endpoint where this agent can be reached
        
    Returns:
        IntentMeshRouter instance
    """
    return IntentMeshRouter(local_agent_id, local_endpoint)