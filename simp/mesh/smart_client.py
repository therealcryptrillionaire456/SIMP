"""
Smart Mesh Client for SIMP Ecosystem
Features:
- Automatic transport selection (HTTP → BLE → Nostr)
- Connection pooling and reuse
- Exponential backoff for retries
- Health checking and failover
- Delivery confirmation
"""

import json
import logging
import time
import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import random

import httpx
from .packet import MeshPacket, MessageType, Priority, create_event_packet
from .enhanced_bus import get_enhanced_mesh_bus, MessageStatus

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Available transport types."""
    HTTP = "http"
    BLE = "ble"
    NOSTR = "nostr"
    DIRECT = "direct"  # Direct mesh bus connection


@dataclass
class TransportHealth:
    """Health status of a transport."""
    transport: TransportType
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    failure_count: int = 0
    avg_latency: float = 0.0
    available: bool = True
    priority: int = 0  # Lower number = higher priority


class SmartMeshClient:
    """
    Smart mesh client with automatic transport selection and failover.
    """
    
    def __init__(
        self,
        agent_id: str,
        broker_url: str = "http://localhost:5555",
        mesh_bus_url: str = "http://localhost:8765",
        enable_direct_mesh: bool = True,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        health_check_interval: float = 30.0,
    ):
        """
        Initialize smart mesh client.
        
        Args:
            agent_id: Unique agent identifier
            broker_url: SIMP broker URL
            mesh_bus_url: Mesh bus HTTP endpoint
            enable_direct_mesh: Whether to use direct mesh bus connection
            max_retries: Maximum retry attempts for failed messages
            retry_base_delay: Base delay for exponential backoff (seconds)
            health_check_interval: Health check interval (seconds)
        """
        self.agent_id = agent_id
        self.broker_url = broker_url.rstrip("/")
        self.mesh_bus_url = mesh_bus_url.rstrip("/")
        self.enable_direct_mesh = enable_direct_mesh
        
        # Retry configuration
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        
        # Transport management
        self.transports: Dict[TransportType, TransportHealth] = {}
        self._init_transports()
        
        # Connection pooling
        self._http_client: Optional[httpx.Client] = None
        self._http_async_client: Optional[httpx.AsyncClient] = None
        
        # Message tracking
        self._pending_messages: Dict[str, Dict] = {}  # message_id -> message info
        self._delivery_callbacks: Dict[str, Callable] = {}  # message_id -> callback
        
        # Direct mesh bus connection
        self._mesh_bus = None
        if enable_direct_mesh:
            try:
                self._mesh_bus = get_enhanced_mesh_bus()
                self._mesh_bus.register_agent(agent_id)
                logger.info(f"Connected to direct mesh bus as {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to connect to direct mesh bus: {e}")
        
        # Health monitoring
        self._health_check_thread: Optional[threading.Thread] = None
        self._health_check_running = False
        self.health_check_interval = health_check_interval
        
        # Statistics
        self._stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "total_retries": 0,
            "transport_failovers": 0,
            "avg_latency_ms": 0.0,
            "uptime_seconds": 0,
        }
        
        self._start_time = time.time()
        
        # Start health monitoring
        self.start_health_monitoring()
        
        logger.info(f"Smart Mesh Client initialized for agent {agent_id}")
    
    def _init_transports(self):
        """Initialize available transports with priorities."""
        # Priority order: DIRECT (if enabled) → HTTP → BLE → NOSTR
        priorities = {
            TransportType.DIRECT: 0,
            TransportType.HTTP: 1,
            TransportType.BLE: 2,
            TransportType.NOSTR: 3,
        }
        
        for transport_type in TransportType:
            self.transports[transport_type] = TransportHealth(
                transport=transport_type,
                priority=priorities.get(transport_type, 99),
            )
        
        # Disable transports that aren't available
        if not self.enable_direct_mesh:
            self.transports[TransportType.DIRECT].available = False
    
    def _get_http_client(self) -> httpx.Client:
        """Get or create HTTP client with connection pooling."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                transport=httpx.HTTPTransport(retries=2),
            )
        return self._http_client
    
    def _get_async_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_async_client is None:
            self._http_async_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._http_async_client
    
    def _select_transport(self, priority: Priority = Priority.NORMAL) -> Optional[TransportType]:
        """
        Select the best available transport based on health and priority.
        
        Args:
            priority: Message priority (higher priority may use more reliable transport)
            
        Returns:
            Selected transport type or None if no transports available
        """
        available_transports = [
            th for th in self.transports.values() 
            if th.available and (th.last_failure is None or time.time() - th.last_failure > 60)
        ]
        
        if not available_transports:
            logger.warning("No available transports")
            return None
        
        # Sort by priority and health
        available_transports.sort(key=lambda th: (
            th.priority,
            th.failure_count,
            -th.avg_latency if th.avg_latency > 0 else float('inf'),
        ))
        
        # For critical messages, prefer more reliable transports
        if priority == Priority.CRITICAL:
            # Filter to only reliable transports for critical messages
            reliable_transports = [t for t in available_transports if t.failure_count == 0]
            if reliable_transports:
                available_transports = reliable_transports
        
        return available_transports[0].transport
    
    def _update_transport_health(
        self, 
        transport: TransportType, 
        success: bool, 
        latency: Optional[float] = None
    ):
        """Update transport health statistics."""
        if transport not in self.transports:
            return
        
        health = self.transports[transport]
        
        if success:
            health.last_success = time.time()
            health.failure_count = max(0, health.failure_count - 1)
            if latency is not None:
                # Exponential moving average for latency
                if health.avg_latency == 0:
                    health.avg_latency = latency
                else:
                    health.avg_latency = health.avg_latency * 0.7 + latency * 0.3
        else:
            health.last_failure = time.time()
            health.failure_count += 1
            
            # Mark as unavailable if too many failures
            if health.failure_count >= 5:
                health.available = False
                logger.warning(f"Transport {transport.value} marked as unavailable")
    
    def _send_via_direct_mesh(self, packet: MeshPacket) -> Optional[str]:
        """Send message via direct mesh bus connection."""
        if not self._mesh_bus:
            return None
        
        try:
            # Register callback for delivery confirmation
            def delivery_callback(msg_id: str, delivered: bool):
                if delivered:
                    self._handle_delivery_confirmation(msg_id)
                else:
                    self._handle_delivery_failure(msg_id)
            
            message_id = self._mesh_bus.send(packet, delivery_callback)
            
            # Track pending message
            self._pending_messages[message_id] = {
                "packet": packet,
                "transport": TransportType.DIRECT,
                "sent_time": time.time(),
                "retry_count": 0,
                "status": "pending",
            }
            
            self._update_transport_health(TransportType.DIRECT, True)
            return message_id
            
        except Exception as e:
            logger.error(f"Direct mesh send failed: {e}")
            self._update_transport_health(TransportType.DIRECT, False)
            return None
    
    def _send_via_http(self, packet: MeshPacket) -> Optional[str]:
        """Send message via HTTP transport."""
        try:
            client = self._get_http_client()
            start_time = time.time()
            
            # Convert packet to dict
            packet_dict = packet.to_dict()
            packet_dict["source_agent"] = self.agent_id
            
            # Send to mesh bus HTTP endpoint
            response = client.post(
                f"{self.mesh_bus_url}/send",
                json=packet_dict,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            message_id = result.get("message_id")
            latency = (time.time() - start_time) * 1000  # ms
            
            if message_id:
                # Track pending message
                self._pending_messages[message_id] = {
                    "packet": packet,
                    "transport": TransportType.HTTP,
                    "sent_time": time.time(),
                    "retry_count": 0,
                    "status": "pending",
                }
                
                self._update_transport_health(TransportType.HTTP, True, latency)
                return message_id
            else:
                raise ValueError("No message_id in response")
                
        except Exception as e:
            logger.error(f"HTTP send failed: {e}")
            self._update_transport_health(TransportType.HTTP, False)
            return None
    
    def _send_via_ble(self, packet: MeshPacket) -> Optional[str]:
        """Send message via BLE transport (stub implementation)."""
        # TODO: Implement actual BLE transport
        logger.warning("BLE transport not implemented")
        self._update_transport_health(TransportType.BLE, False)
        return None
    
    def _send_via_nostr(self, packet: MeshPacket) -> Optional[str]:
        """Send message via Nostr transport (stub implementation)."""
        # TODO: Implement actual Nostr transport
        logger.warning("Nostr transport not implemented")
        self._update_transport_health(TransportType.NOSTR, False)
        return None
    
    def send(
        self,
        target_agent: Optional[str] = None,
        target_channel: Optional[str] = None,
        message_type: MessageType = MessageType.EVENT,
        priority: Priority = Priority.NORMAL,
        payload: Optional[Dict] = None,
        ttl: int = 3600,
        delivery_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """
        Send a message with automatic transport selection and retry.
        
        Args:
            target_agent: Target agent ID (optional for broadcasts)
            target_channel: Target channel (optional for agent-specific)
            message_type: Type of message
            priority: Message priority
            payload: Message payload
            ttl: Time to live in seconds
            delivery_callback: Callback for delivery confirmation
            
        Returns:
            Message ID or None if failed
        """
        # Create packet
        packet = MeshPacket(
            message_id=str(uuid.uuid4()),
            source_agent=self.agent_id,
            target_agent=target_agent,
            target_channel=target_channel,
            message_type=message_type,
            priority=priority,
            payload=payload or {},
            timestamp=time.time(),
            ttl=ttl,
        )
        
        # Store delivery callback
        if delivery_callback:
            self._delivery_callbacks[packet.message_id] = delivery_callback
        
        # Try to send with retries
        message_id = None
        for attempt in range(self.max_retries + 1):
            # Select transport for this attempt
            transport = self._select_transport(priority)
            if not transport:
                logger.error("No available transports after all attempts")
                break
            
            # Send via selected transport
            if transport == TransportType.DIRECT:
                message_id = self._send_via_direct_mesh(packet)
            elif transport == TransportType.HTTP:
                message_id = self._send_via_http(packet)
            elif transport == TransportType.BLE:
                message_id = self._send_via_ble(packet)
            elif transport == TransportType.NOSTR:
                message_id = self._send_via_nostr(packet)
            
            if message_id:
                self._stats["messages_sent"] += 1
                if attempt > 0:
                    self._stats["total_retries"] += attempt
                    self._stats["transport_failovers"] += 1
                
                logger.debug(f"Message {message_id} sent via {transport.value} (attempt {attempt + 1})")
                break
            else:
                # Transport failed, mark it as unhealthy
                self._update_transport_health(transport, False)
                
                if attempt < self.max_retries:
                    # Exponential backoff before retry
                    delay = self.retry_base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    logger.debug(f"Send failed, retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Failed to send message after {self.max_retries + 1} attempts")
                    self._stats["messages_failed"] += 1
        
        return message_id
    
    async def send_async(
        self,
        target_agent: Optional[str] = None,
        target_channel: Optional[str] = None,
        message_type: MessageType = MessageType.EVENT,
        priority: Priority = Priority.NORMAL,
        payload: Optional[Dict] = None,
        ttl: int = 3600,
        delivery_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Async version of send method."""
        # For now, use sync version (can be enhanced for true async)
        return self.send(
            target_agent=target_agent,
            target_channel=target_channel,
            message_type=message_type,
            priority=priority,
            payload=payload,
            ttl=ttl,
            delivery_callback=delivery_callback,
        )
    
    def send_to_agent(
        self,
        target_agent: str,
        message_type: MessageType = MessageType.EVENT,
        priority: Priority = Priority.NORMAL,
        payload: Optional[Dict] = None,
        ttl: int = 3600,
        delivery_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Convenience method to send to specific agent."""
        return self.send(
            target_agent=target_agent,
            message_type=message_type,
            priority=priority,
            payload=payload,
            ttl=ttl,
            delivery_callback=delivery_callback,
        )
    
    def broadcast_to_channel(
        self,
        channel: str,
        message_type: MessageType = MessageType.EVENT,
        priority: Priority = Priority.NORMAL,
        payload: Optional[Dict] = None,
        ttl: int = 3600,
        delivery_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Convenience method to broadcast to channel."""
        return self.send(
            target_channel=channel,
            message_type=message_type,
            priority=priority,
            payload=payload,
            ttl=ttl,
            delivery_callback=delivery_callback,
        )
    
    def _handle_delivery_confirmation(self, message_id: str):
        """Handle delivery confirmation from mesh bus."""
        if message_id in self._pending_messages:
            msg_info = self._pending_messages[message_id]
            msg_info["status"] = "delivered"
            msg_info["delivered_time"] = time.time()
            
            # Calculate latency
            latency = (msg_info["delivered_time"] - msg_info["sent_time"]) * 1000
            self._stats["avg_latency_ms"] = (
                self._stats["avg_latency_ms"] * 0.9 + latency * 0.1
            )
            self._stats["messages_delivered"] += 1
            
            # Call delivery callback
            if message_id in self._delivery_callbacks:
                try:
                    self._delivery_callbacks[message_id](message_id, True)
                except Exception as e:
                    logger.error(f"Delivery callback failed: {e}")
                finally:
                    del self._delivery_callbacks[message_id]
            
            # Clean up after successful delivery
            del self._pending_messages[message_id]
            
            logger.debug(f"Message {message_id} delivered")
    
    def _handle_delivery_failure(self, message_id: str):
        """Handle delivery failure from mesh bus."""
        if message_id in self._pending_messages:
            msg_info = self._pending_messages[message_id]
            msg_info["status"] = "failed"
            msg_info["retry_count"] += 1
            
            # Retry if under max retries
            if msg_info["retry_count"] <= self.max_retries:
                logger.debug(f"Message {message_id} failed, retrying ({msg_info['retry_count']}/{self.max_retries})")
                
                # Exponential backoff
                delay = self.retry_base_delay * (2 ** msg_info["retry_count"])
                time.sleep(delay)
                
                # Retry with same parameters
                packet = msg_info["packet"]
                self.send(
                    target_agent=packet.target_agent,
                    target_channel=packet.target_channel,
                    message_type=packet.message_type,
                    priority=packet.priority,
                    payload=packet.payload,
                    ttl=packet.ttl - (time.time() - packet.timestamp),
                    delivery_callback=self._delivery_callbacks.get(message_id),
                )
            else:
                # Final failure
                self._stats["messages_failed"] += 1
                
                # Call delivery callback
                if message_id in self._delivery_callbacks:
                    try:
                        self._delivery_callbacks[message_id](message_id, False)
                    except Exception as e:
                        logger.error(f"Failure callback failed: {e}")
                    finally:
                        del self._delivery_callbacks[message_id]
                
                # Clean up
                del self._pending_messages[message_id]
                
                logger.error(f"Message {message_id} failed after {self.max_retries} retries")
    
    def receive(self, max_messages: int = 10, timeout: Optional[float] = None) -> List[MeshPacket]:
        """
        Receive messages for this agent.
        
        Args:
            max_messages: Maximum number of messages to receive
            timeout: Maximum time to wait (None = non-blocking)
            
        Returns:
            List of received messages
        """
        if self._mesh_bus:
            # Update heartbeat
            self._mesh_bus.update_agent_heartbeat(self.agent_id)
            
            # Receive from direct mesh bus
            messages = self._mesh_bus.receive(self.agent_id, max_messages)
            
            # Confirm delivery for each message
            for msg in messages:
                if self._mesh_bus:
                    self._mesh_bus.confirm_delivery(msg.message_id)
            
            return messages
        else:
            # TODO: Implement HTTP polling for mesh bus
            logger.warning("Direct mesh bus not available, HTTP polling not implemented")
            return []
    
    async def receive_async(self, max_messages: int = 10) -> List[MeshPacket]:
        """Async version of receive method."""
        # For now, use sync version
        return self.receive(max_messages)
    
    def subscribe(self, channel: str) -> bool:
        """Subscribe to a channel."""
        if self._mesh_bus:
            return self._mesh_bus.subscribe(self.agent_id, channel)
        
        # TODO: Implement HTTP subscription
        logger.warning("Direct mesh bus not available for subscription")
        return False
    
    def unsubscribe(self, channel: str) -> bool:
        """Unsubscribe from a channel."""
        if self._mesh_bus:
            return self._mesh_bus.unsubscribe(self.agent_id, channel)
        
        # TODO: Implement HTTP unsubscription
        logger.warning("Direct mesh bus not available for unsubscription")
        return False
    
    def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific message."""
        if message_id in self._pending_messages:
            msg_info = self._pending_messages[message_id]
            packet = msg_info["packet"]
            
            return {
                "message_id": message_id,
                "status": msg_info["status"],
                "target_agent": packet.target_agent,
                "target_channel": packet.target_channel,
                "priority": packet.priority.value,
                "retry_count": msg_info["retry_count"],
                "sent_time": datetime.fromtimestamp(msg_info["sent_time"]).isoformat(),
                "age_seconds": time.time() - msg_info["sent_time"],
                "transport": msg_info["transport"].value,
            }
        
        if self._mesh_bus:
            return self._mesh_bus.get_message_status(message_id)
        
        return None
    
    def _health_check(self):
        """Perform health check on all transports."""
        logger.debug("Performing transport health check")
        
        # Check direct mesh bus
        if self._mesh_bus:
            try:
                status = self._mesh_bus.get_agent_status(self.agent_id)
                if status and status.get("registered"):
                    self._update_transport_health(TransportType.DIRECT, True)
                else:
                    self._update_transport_health(TransportType.DIRECT, False)
            except Exception as e:
                logger.error(f"Direct mesh health check failed: {e}")
                self._update_transport_health(TransportType.DIRECT, False)
        
        # Check HTTP transport
        try:
            client = self._get_http_client()
            start_time = time.time()
            response = client.get(f"{self.mesh_bus_url}/health", timeout=5.0)
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                self._update_transport_health(TransportType.HTTP, True, latency)
            else:
                self._update_transport_health(TransportType.HTTP, False)
        except Exception as e:
            logger.error(f"HTTP health check failed: {e}")
            self._update_transport_health(TransportType.HTTP, False)
        
        # Try to revive unavailable transports after some time
        for transport, health in self.transports.items():
            if not health.available and health.last_failure:
                # Try to revive after 5 minutes
                if time.time() - health.last_failure > 300:
                    health.available = True
                    health.failure_count = 0
                    logger.info(f"Transport {transport.value} revived")
    
    def _health_check_loop(self):
        """Background health check loop."""
        while self._health_check_running:
            time.sleep(self.health_check_interval)
            try:
                self._health_check()
                self._stats["uptime_seconds"] = time.time() - self._start_time
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    def start_health_monitoring(self):
        """Start background health monitoring."""
        if self._health_check_thread and self._health_check_thread.is_alive():
            return
        
        self._health_check_running = True
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name=f"MeshHealth-{self.agent_id}",
        )
        self._health_check_thread.start()
        logger.info("Health monitoring started")
    
    def stop_health_monitoring(self):
        """Stop background health monitoring."""
        self._health_check_running = False
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
            self._health_check_thread = None
        logger.info("Health monitoring stopped")
    
    def get_transport_health(self) -> Dict[str, Any]:
        """Get health status of all transports."""
        health_info = {}
        
        for transport, health in self.transports.items():
            health_info[transport.value] = {
                "available": health.available,
                "priority": health.priority,
                "failure_count": health.failure_count,
                "avg_latency_ms": health.avg_latency,
                "last_success": (
                    datetime.fromtimestamp(health.last_success).isoformat()
                    if health.last_success else None
                ),
                "last_failure": (
                    datetime.fromtimestamp(health.last_failure).isoformat()
                    if health.last_failure else None
                ),
            }
        
        return health_info
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics."""
        stats = self._stats.copy()
        
        stats.update({
            "agent_id": self.agent_id,
            "pending_messages": len(self._pending_messages),
            "pending_callbacks": len(self._delivery_callbacks),
            "transport_health": self.get_transport_health(),
            "direct_mesh_available": self._mesh_bus is not None,
        })
        
        return stats
    
    def close(self):
        """Close client and release resources."""
        self.stop_health_monitoring()
        
        if self._http_client:
            self._http_client.close()
            self._http_client = None
        
        if self._http_async_client:
            # Note: Async client should be closed in async context
            pass
        
        if self._mesh_bus:
            self._mesh_bus.deregister_agent(self.agent_id)
        
        logger.info(f"Smart Mesh Client for {self.agent_id} closed")


def create_smart_mesh_client(
    agent_id: str,
    broker_url: str = "http://localhost:5555",
    mesh_bus_url: str = "http://localhost:8765",
    enable_direct_mesh: bool = True,
) -> SmartMeshClient:
    """
    Create a smart mesh client.
    
    Args:
        agent_id: Unique agent identifier
        broker_url: SIMP broker URL
        mesh_bus_url: Mesh bus HTTP endpoint
        enable_direct_mesh: Whether to use direct mesh bus connection
        
    Returns:
        SmartMeshClient instance
    """
    return SmartMeshClient(
        agent_id=agent_id,
        broker_url=broker_url,
        mesh_bus_url=mesh_bus_url,
        enable_direct_mesh=enable_direct_mesh,
    )