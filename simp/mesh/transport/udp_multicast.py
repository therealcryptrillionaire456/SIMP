"""
UDP Multicast Transport for SIMP Mesh.
Provides same-LAN communication without internet access.
"""

import socket
import threading
import json
import logging
import time
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Multicast configuration
MULTICAST_GROUP = "239.0.0.1"
MULTICAST_PORT = 5007
BUFFER_SIZE = 65507  # Maximum UDP packet size

class UdpMessageType(Enum):
    """Types of UDP multicast messages."""
    DISCOVERY = "discovery"
    MESH_PACKET = "mesh_packet"
    HEARTBEAT = "heartbeat"
    CAPABILITY_ADVERTISEMENT = "capability_ad"

@dataclass
class UdpMessage:
    """UDP multicast message structure."""
    type: UdpMessageType
    sender_id: str
    payload: Dict[str, Any]
    timestamp: float
    ttl: int = 5  # Time-to-live in hops
    
    def to_json(self) -> str:
        """Serialize message to JSON."""
        return json.dumps({
            "type": self.type.value,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "ttl": self.ttl
        })
    
    @classmethod
    def from_json(cls, data: str) -> 'UdpMessage':
        """Deserialize message from JSON."""
        obj = json.loads(data)
        return cls(
            type=UdpMessageType(obj["type"]),
            sender_id=obj["sender_id"],
            payload=obj["payload"],
            timestamp=obj["timestamp"],
            ttl=obj.get("ttl", 5)
        )

class UdpMulticastTransport:
    """
    UDP multicast transport for mesh communication.
    
    Features:
    - Same-LAN communication without internet
    - Sub-millisecond latency
    - Automatic peer discovery
    - TTL-based message propagation
    """
    
    def __init__(
        self,
        agent_id: str,
        multicast_group: str = MULTICAST_GROUP,
        multicast_port: int = MULTICAST_PORT,
        enable_listener: bool = True
    ):
        """
        Initialize UDP multicast transport.
        
        Args:
            agent_id: Unique agent identifier
            multicast_group: Multicast IP address (239.0.0.1)
            multicast_port: Multicast port (5007)
            enable_listener: Whether to start listening thread
        """
        self.agent_id = agent_id
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.enable_listener = enable_listener
        
        # Socket for sending/receiving
        self._socket: Optional[socket.socket] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Callback for received messages
        self._message_callback: Optional[Callable[[UdpMessage], None]] = None
        
        # Statistics
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
        }
        
        # Seen message IDs to prevent loops
        self._seen_messages: Dict[str, float] = {}
        self._seen_lock = threading.Lock()
        
        logger.info(f"UDP multicast transport initialized for agent {agent_id}")
    
    def start(self) -> bool:
        """Start the UDP multicast transport."""
        try:
            # Create socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to all interfaces
            self._socket.bind(('', self.multicast_port))
            
            # Join multicast group
            group = socket.inet_aton(self.multicast_group)
            mreq = group + socket.inet_aton('0.0.0.0')
            self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # Set socket timeout for non-blocking operations
            self._socket.settimeout(0.1)
            
            # Start listener thread if enabled
            if self.enable_listener:
                self._running = True
                self._listener_thread = threading.Thread(
                    target=self._listener_loop,
                    daemon=True,
                    name=f"UDP-Listener-{self.agent_id}"
                )
                self._listener_thread.start()
                logger.info(f"UDP multicast listener started on {self.multicast_group}:{self.multicast_port}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start UDP multicast transport: {e}")
            self._socket = None
            return False
    
    def stop(self) -> None:
        """Stop the UDP multicast transport."""
        self._running = False
        
        if self._listener_thread:
            self._listener_thread.join(timeout=2)
            self._listener_thread = None
        
        if self._socket:
            try:
                # Leave multicast group
                group = socket.inet_aton(self.multicast_group)
                mreq = group + socket.inet_aton('0.0.0.0')
                self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
                self._socket.close()
            except:
                pass
            finally:
                self._socket = None
        
        logger.info("UDP multicast transport stopped")
    
    def set_message_callback(self, callback: Callable[[UdpMessage], None]) -> None:
        """Set callback for received messages."""
        self._message_callback = callback
    
    def send_message(self, message: UdpMessage) -> bool:
        """
        Send a UDP multicast message.
        
        Args:
            message: UDP message to send
            
        Returns:
            True if sent successfully
        """
        if not self._socket:
            logger.warning("UDP socket not initialized")
            return False
        
        try:
            # Serialize message
            data = message.to_json().encode('utf-8')
            
            # Send to multicast group
            self._socket.sendto(data, (self.multicast_group, self.multicast_port))
            
            # Update statistics
            self._stats["messages_sent"] += 1
            self._stats["bytes_sent"] += len(data)
            
            logger.debug(f"Sent UDP message type={message.type} from {self.agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send UDP message: {e}")
            self._stats["errors"] += 1
            return False
    
    def broadcast_discovery(self, endpoint: str, capabilities: List[str]) -> bool:
        """
        Broadcast discovery message to announce presence.
        
        Args:
            endpoint: Agent endpoint (e.g., "http://localhost:8765")
            capabilities: List of agent capabilities
            
        Returns:
            True if broadcast successful
        """
        message = UdpMessage(
            type=UdpMessageType.DISCOVERY,
            sender_id=self.agent_id,
            payload={
                "endpoint": endpoint,
                "capabilities": capabilities,
                "timestamp": time.time()
            },
            timestamp=time.time(),
            ttl=5
        )
        
        return self.send_message(message)
    
    def broadcast_mesh_packet(self, packet_data: Dict[str, Any]) -> bool:
        """
        Broadcast a mesh packet via UDP multicast.
        
        Args:
            packet_data: Mesh packet data (from MeshPacket.to_dict())
            
        Returns:
            True if broadcast successful
        """
        message = UdpMessage(
            type=UdpMessageType.MESH_PACKET,
            sender_id=self.agent_id,
            payload=packet_data,
            timestamp=time.time(),
            ttl=5
        )
        
        return self.send_message(message)
    
    def _listener_loop(self) -> None:
        """Background listener loop for receiving UDP messages."""
        logger.info("UDP listener loop started")
        
        while self._running and self._socket:
            try:
                # Receive data
                data, address = self._socket.recvfrom(BUFFER_SIZE)
                
                # Update statistics
                self._stats["bytes_received"] += len(data)
                
                # Parse message
                try:
                    message = UdpMessage.from_json(data.decode('utf-8'))
                    self._stats["messages_received"] += 1
                    
                    # Skip our own messages
                    if message.sender_id == self.agent_id:
                        continue
                    
                    # Check TTL
                    if message.ttl <= 0:
                        continue
                    
                    # Check if we've seen this message recently
                    message_id = f"{message.sender_id}:{message.timestamp}:{message.type}"
                    with self._seen_lock:
                        if message_id in self._seen_messages:
                            # Skip duplicate
                            continue
                        self._seen_messages[message_id] = time.time()
                    
                    # Clean old seen messages
                    self._clean_seen_messages()
                    
                    # Decrement TTL for forwarding
                    message.ttl -= 1
                    
                    # Call callback if set
                    if self._message_callback:
                        try:
                            self._message_callback(message)
                        except Exception as e:
                            logger.error(f"Message callback error: {e}")
                    
                    # Log received message
                    logger.debug(f"Received UDP message type={message.type} from {message.sender_id}@{address}")
                    
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to parse UDP message: {e}")
                    self._stats["errors"] += 1
                
            except socket.timeout:
                # Expected timeout for non-blocking socket
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"UDP listener error: {e}")
                    self._stats["errors"] += 1
                # Brief pause on error
                time.sleep(0.1)
        
        logger.info("UDP listener loop stopped")
    
    def _clean_seen_messages(self) -> None:
        """Clean old entries from seen messages cache."""
        with self._seen_lock:
            current_time = time.time()
            to_remove = []
            
            for msg_id, timestamp in self._seen_messages.items():
                if current_time - timestamp > 300:  # 5 minutes
                    to_remove.append(msg_id)
            
            for msg_id in to_remove:
                del self._seen_messages[msg_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get transport statistics."""
        return self._stats.copy()
    
    def is_running(self) -> bool:
        """Check if transport is running."""
        return self._running and self._socket is not None


# Factory function for easy creation
def create_udp_multicast_transport(
    agent_id: str,
    multicast_group: str = MULTICAST_GROUP,
    multicast_port: int = MULTICAST_PORT,
    enable_listener: bool = True
) -> UdpMulticastTransport:
    """
    Create and start a UDP multicast transport.
    
    Args:
        agent_id: Unique agent identifier
        multicast_group: Multicast IP address
        multicast_port: Multicast port
        enable_listener: Whether to start listening
        
    Returns:
        UdpMulticastTransport instance
    """
    transport = UdpMulticastTransport(
        agent_id=agent_id,
        multicast_group=multicast_group,
        multicast_port=multicast_port,
        enable_listener=enable_listener
    )
    
    if enable_listener:
        transport.start()
    
    return transport