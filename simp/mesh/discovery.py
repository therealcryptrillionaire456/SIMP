"""
Mesh Discovery Service for SIMP Ecosystem
Features:
- Automatic peer discovery via multicast/broadcast
- Dynamic routing table management
- Network topology mapping
- Peer health monitoring
- Self-healing network
"""

import json
import logging
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import struct

from .packet import MeshPacket, MessageType, Priority, create_event_packet
from .enhanced_bus import get_enhanced_mesh_bus

logger = logging.getLogger(__name__)


class DiscoveryMethod(Enum):
    """Methods for discovering peers."""
    MULTICAST = "multicast"
    BROADCAST = "broadcast"
    MANUAL = "manual"
    BROKER = "broker"


class PeerStatus(Enum):
    """Status of a discovered peer."""
    ONLINE = "online"
    OFFLINE = "offline"
    UNREACHABLE = "unreachable"
    STALE = "stale"


@dataclass
class MeshPeer:
    """Information about a mesh peer."""
    agent_id: str
    endpoint: str  # e.g., "http://192.168.1.100:8765"
    transport: str = "http"
    discovered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    status: PeerStatus = PeerStatus.ONLINE
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    priority: int = 0  # Lower number = higher priority
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "endpoint": self.endpoint,
            "transport": self.transport,
            "discovered_at": datetime.fromtimestamp(self.discovered_at).isoformat(),
            "last_seen": datetime.fromtimestamp(self.last_seen).isoformat(),
            "status": self.status.value,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "failure_count": self.failure_count,
            "avg_latency_ms": self.avg_latency_ms,
            "priority": self.priority,
            "age_seconds": time.time() - self.discovered_at,
            "seconds_since_seen": time.time() - self.last_seen,
        }
    
    def is_stale(self, timeout_seconds: int = 300) -> bool:
        """Check if peer is stale (not seen for timeout)."""
        return time.time() - self.last_seen > timeout_seconds
    
    def update_heartbeat(self, latency_ms: Optional[float] = None):
        """Update peer heartbeat with optional latency measurement."""
        self.last_seen = time.time()
        self.status = PeerStatus.ONLINE
        self.failure_count = 0
        
        if latency_ms is not None:
            # Exponential moving average for latency
            if self.avg_latency_ms == 0:
                self.avg_latency_ms = latency_ms
            else:
                self.avg_latency_ms = self.avg_latency_ms * 0.7 + latency_ms * 0.3
    
    def mark_failure(self):
        """Mark peer as failed."""
        self.failure_count += 1
        if self.failure_count >= 3:
            self.status = PeerStatus.UNREACHABLE
        else:
            self.status = PeerStatus.OFFLINE


class MeshDiscoveryService:
    """
    Service for discovering and managing mesh peers.
    """
    
    # Multicast configuration
    MULTICAST_GROUP = "239.255.255.250"
    MULTICAST_PORT = 1900
    DISCOVERY_INTERVAL = 30  # seconds
    
    def __init__(
        self,
        local_agent_id: str,
        local_endpoint: str,
        broker_url: str = "http://localhost:5555",
        enable_multicast: bool = True,
        enable_broadcast: bool = True,
        peer_timeout: int = 300,  # 5 minutes
        max_peers: int = 100,
    ):
        """
        Initialize mesh discovery service.
        
        Args:
            local_agent_id: ID of local agent
            local_endpoint: Endpoint where this agent can be reached
            broker_url: SIMP broker URL for broker-based discovery
            enable_multicast: Whether to use multicast discovery
            enable_broadcast: Whether to use broadcast discovery
            peer_timeout: Timeout for stale peers (seconds)
            max_peers: Maximum number of peers to track
        """
        self.local_agent_id = local_agent_id
        self.local_endpoint = local_endpoint
        self.broker_url = broker_url
        self.peer_timeout = peer_timeout
        self.max_peers = max_peers
        
        # Peer management
        self.peers: Dict[str, MeshPeer] = {}  # agent_id -> MeshPeer
        self._peer_lock = threading.RLock()
        
        # Discovery methods
        self.enable_multicast = enable_multicast
        self.enable_broadcast = enable_broadcast
        
        # Multicast socket
        self._multicast_socket: Optional[socket.socket] = None
        self._multicast_running = False
        self._multicast_thread: Optional[threading.Thread] = None
        
        # Discovery thread
        self._discovery_running = False
        self._discovery_thread: Optional[threading.Thread] = None
        
        # Mesh bus connection
        self._mesh_bus = get_enhanced_mesh_bus()
        
        # Statistics
        self._stats = {
            "peers_discovered": 0,
            "peers_active": 0,
            "discovery_cycles": 0,
            "multicast_messages_sent": 0,
            "multicast_messages_received": 0,
            "broker_discoveries": 0,
            "manual_discoveries": 0,
        }
        
        # Start discovery
        self.start()
        
        logger.info(f"Mesh Discovery Service initialized for {local_agent_id}")
    
    def _create_multicast_socket(self) -> Optional[socket.socket]:
        """Create and configure multicast socket."""
        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to all interfaces
            sock.bind(('', self.MULTICAST_PORT))
            
            # Join multicast group
            group = socket.inet_aton(self.MULTICAST_GROUP)
            mreq = struct.pack('4sL', group, socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # Set timeout for non-blocking receive
            sock.settimeout(1.0)
            
            return sock
            
        except Exception as e:
            logger.error(f"Failed to create multicast socket: {e}")
            return None
    
    def _send_multicast_announcement(self):
        """Send multicast announcement of this agent."""
        if not self._multicast_socket:
            return
        
        announcement = {
            "agent_id": self.local_agent_id,
            "endpoint": self.local_endpoint,
            "timestamp": time.time(),
            "message_type": "mesh_announcement",
            "version": "1.0",
        }
        
        try:
            message = json.dumps(announcement).encode('utf-8')
            self._multicast_socket.sendto(
                message,
                (self.MULTICAST_GROUP, self.MULTICAST_PORT)
            )
            self._stats["multicast_messages_sent"] += 1
            logger.debug(f"Sent multicast announcement from {self.local_agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to send multicast announcement: {e}")
    
    def _handle_multicast_message(self, data: bytes, address: Tuple[str, int]):
        """Handle incoming multicast message."""
        try:
            message = json.loads(data.decode('utf-8'))
            agent_id = message.get("agent_id")
            endpoint = message.get("endpoint")
            message_type = message.get("message_type")
            
            if not agent_id or not endpoint:
                logger.warning(f"Invalid multicast message from {address}")
                return
            
            if agent_id == self.local_agent_id:
                # Ignore our own messages
                return
            
            if message_type == "mesh_announcement":
                self._stats["multicast_messages_received"] += 1
                self.add_peer(
                    agent_id=agent_id,
                    endpoint=endpoint,
                    method=DiscoveryMethod.MULTICAST,
                    metadata={"discovery_address": address[0]},
                )
                logger.debug(f"Discovered peer via multicast: {agent_id} at {endpoint}")
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in multicast message from {address}")
        except Exception as e:
            logger.error(f"Error handling multicast message: {e}")
    
    def _multicast_listener(self):
        """Listen for multicast announcements."""
        logger.info("Multicast listener started")
        
        while self._multicast_running:
            try:
                if self._multicast_socket:
                    data, address = self._multicast_socket.recvfrom(1024)
                    self._handle_multicast_message(data, address)
            except socket.timeout:
                continue  # Expected, allows checking running flag
            except Exception as e:
                logger.error(f"Multicast listener error: {e}")
                time.sleep(1)
        
        logger.info("Multicast listener stopped")
    
    def _discover_via_broker(self):
        """Discover peers via SIMP broker."""
        try:
            import httpx
            
            client = httpx.Client(timeout=10.0)
            response = client.get(f"{self.broker_url}/agents")
            
            if response.status_code == 200:
                agents = response.json().get("agents", {})
                
                for agent_id, agent_info in agents.items():
                    if agent_id == self.local_agent_id:
                        continue
                    
                    # Extract endpoint from agent info
                    endpoint = agent_info.get("endpoint")
                    if endpoint and endpoint != "(file-based)":
                        self.add_peer(
                            agent_id=agent_id,
                            endpoint=endpoint,
                            method=DiscoveryMethod.BROKER,
                            metadata=agent_info,
                        )
                        self._stats["broker_discoveries"] += 1
                        logger.debug(f"Discovered peer via broker: {agent_id} at {endpoint}")
            
        except Exception as e:
            logger.error(f"Broker discovery failed: {e}")
    
    def _discover_via_broadcast(self):
        """Discover peers via local network broadcast."""
        # TODO: Implement UDP broadcast discovery
        pass
    
    def _discovery_cycle(self):
        """Run a single discovery cycle."""
        logger.debug("Running discovery cycle")
        
        # Send our own announcement
        if self.enable_multicast:
            self._send_multicast_announcement()
        
        # Discover via broker
        self._discover_via_broker()
        
        # Discover via broadcast
        if self.enable_broadcast:
            self._discover_via_broadcast()
        
        # Clean up stale peers
        self._cleanup_stale_peers()
        
        # Update mesh bus with discovered peers
        self._update_mesh_bus_routing()
        
        self._stats["discovery_cycles"] += 1
        logger.debug(f"Discovery cycle complete: {len(self.peers)} peers known")
    
    def _discovery_loop(self):
        """Background discovery loop."""
        logger.info("Discovery loop started")
        
        while self._discovery_running:
            try:
                self._discovery_cycle()
            except Exception as e:
                logger.error(f"Discovery cycle error: {e}")
            
            # Wait for next cycle
            time.sleep(self.DISCOVERY_INTERVAL)
        
        logger.info("Discovery loop stopped")
    
    def add_peer(
        self,
        agent_id: str,
        endpoint: str,
        method: DiscoveryMethod = DiscoveryMethod.MANUAL,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add or update a peer.
        
        Args:
            agent_id: Peer agent ID
            endpoint: Peer endpoint URL
            method: Discovery method
            capabilities: Peer capabilities
            metadata: Additional metadata
            
        Returns:
            True if peer was added/updated, False otherwise
        """
        with self._peer_lock:
            # Check if we've reached max peers
            if len(self.peers) >= self.max_peers:
                # Remove lowest priority stale peer
                stale_peers = [
                    (agent_id, peer) for agent_id, peer in self.peers.items()
                    if peer.is_stale(self.peer_timeout)
                ]
                
                if stale_peers:
                    # Remove oldest stale peer
                    stale_peers.sort(key=lambda x: x[1].last_seen)
                    removed_id, _ = stale_peers[0]
                    del self.peers[removed_id]
                    logger.debug(f"Removed stale peer {removed_id} to make room")
                else:
                    logger.warning(f"Cannot add peer {agent_id}: max peers reached")
                    return False
            
            # Check if peer already exists
            if agent_id in self.peers:
                peer = self.peers[agent_id]
                peer.endpoint = endpoint
                peer.update_heartbeat()
                
                if capabilities:
                    peer.capabilities = capabilities
                if metadata:
                    peer.metadata.update(metadata)
                
                logger.debug(f"Updated peer {agent_id}")
                return True
            
            # Create new peer
            peer = MeshPeer(
                agent_id=agent_id,
                endpoint=endpoint,
                capabilities=capabilities or [],
                metadata=metadata or {},
            )
            
            self.peers[agent_id] = peer
            self._stats["peers_discovered"] += 1
            
            logger.info(f"Added new peer {agent_id} via {method.value} at {endpoint}")
            return True
    
    def remove_peer(self, agent_id: str) -> bool:
        """Remove a peer."""
        with self._peer_lock:
            if agent_id in self.peers:
                del self.peers[agent_id]
                logger.info(f"Removed peer {agent_id}")
                return True
            return False
    
    def get_peer(self, agent_id: str) -> Optional[MeshPeer]:
        """Get peer by agent ID."""
        with self._peer_lock:
            return self.peers.get(agent_id)
    
    def get_peers(
        self,
        status: Optional[PeerStatus] = None,
        min_priority: Optional[int] = None,
        max_failures: Optional[int] = None,
    ) -> List[MeshPeer]:
        """Get filtered list of peers."""
        with self._peer_lock:
            filtered = list(self.peers.values())
            
            if status:
                filtered = [p for p in filtered if p.status == status]
            
            if min_priority is not None:
                filtered = [p for p in filtered if p.priority <= min_priority]
            
            if max_failures is not None:
                filtered = [p for p in filtered if p.failure_count <= max_failures]
            
            return filtered
    
    def update_peer_heartbeat(
        self,
        agent_id: str,
        latency_ms: Optional[float] = None,
    ) -> bool:
        """Update peer heartbeat."""
        with self._peer_lock:
            if agent_id in self.peers:
                self.peers[agent_id].update_heartbeat(latency_ms)
                return True
            return False
    
    def mark_peer_failure(self, agent_id: str) -> bool:
        """Mark peer as failed."""
        with self._peer_lock:
            if agent_id in self.peers:
                self.peers[agent_id].mark_failure()
                logger.warning(f"Marked peer {agent_id} as failed")
                return True
            return False
    
    def _cleanup_stale_peers(self):
        """Remove stale peers."""
        with self._peer_lock:
            to_remove = []
            
            for agent_id, peer in self.peers.items():
                if peer.is_stale(self.peer_timeout):
                    peer.status = PeerStatus.STALE
                    to_remove.append(agent_id)
            
            for agent_id in to_remove:
                del self.peers[agent_id]
                logger.info(f"Removed stale peer {agent_id}")
    
    def _update_mesh_bus_routing(self):
        """Update mesh bus with discovered peers for routing."""
        if not self._mesh_bus:
            return
        
        # Get online peers
        online_peers = self.get_peers(status=PeerStatus.ONLINE)
        
        # Add peers to gossip router
        for peer in online_peers:
            if peer.agent_id != self.local_agent_id:  # Don't add ourselves
                # Check if peer has an endpoint
                if peer.endpoint:
                    try:
                        self._mesh_bus.add_gossip_peer(peer.agent_id, peer.endpoint)
                        logger.debug(f"Added peer {peer.agent_id} to gossip router")
                    except Exception as e:
                        logger.warning(f"Failed to add peer {peer.agent_id} to gossip router: {e}")
        
        if online_peers:
            logger.debug(f"Mesh bus routing: {len(online_peers)} online peers available")
    
    def get_network_topology(self) -> Dict[str, Any]:
        """Get current network topology."""
        with self._peer_lock:
            topology = {
                "local_agent": {
                    "agent_id": self.local_agent_id,
                    "endpoint": self.local_endpoint,
                },
                "peers": {},
                "statistics": {
                    "total_peers": len(self.peers),
                    "online_peers": len(self.get_peers(status=PeerStatus.ONLINE)),
                    "offline_peers": len(self.get_peers(status=PeerStatus.OFFLINE)),
                    "unreachable_peers": len(self.get_peers(status=PeerStatus.UNREACHABLE)),
                    "stale_peers": len(self.get_peers(status=PeerStatus.STALE)),
                },
                "discovery_methods": {
                    "multicast": self.enable_multicast,
                    "broadcast": self.enable_broadcast,
                    "broker": True,  # Always enabled
                },
            }
            
            for agent_id, peer in self.peers.items():
                topology["peers"][agent_id] = peer.to_dict()
            
            return topology
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get discovery service statistics."""
        stats = self._stats.copy()
        
        with self._peer_lock:
            stats.update({
                "current_peers": len(self.peers),
                "online_peers": len([p for p in self.peers.values() if p.status == PeerStatus.ONLINE]),
                "service_running": self._discovery_running,
                "multicast_running": self._multicast_running,
                "uptime_seconds": getattr(self, "_start_time", time.time()) - time.time(),
            })
        
        return stats
    
    def start(self):
        """Start discovery service."""
        if self._discovery_running:
            logger.warning("Discovery service already running")
            return
        
        # Start multicast listener if enabled
        if self.enable_multicast:
            self._multicast_socket = self._create_multicast_socket()
            if self._multicast_socket:
                self._multicast_running = True
                self._multicast_thread = threading.Thread(
                    target=self._multicast_listener,
                    daemon=True,
                    name="MeshMulticastListener",
                )
                self._multicast_thread.start()
                logger.info("Multicast listener started")
            else:
                logger.warning("Multicast disabled due to socket creation failure")
                self.enable_multicast = False
        
        # Start discovery loop
        self._discovery_running = True
        self._discovery_thread = threading.Thread(
            target=self._discovery_loop,
            daemon=True,
            name="MeshDiscoveryLoop",
        )
        self._discovery_thread.start()
        self._start_time = time.time()
        
        logger.info("Mesh Discovery Service started")
    
    def stop(self):
        """Stop discovery service."""
        self._discovery_running = False
        
        # Stop multicast
        self._multicast_running = False
        if self._multicast_socket:
            self._multicast_socket.close()
            self._multicast_socket = None
        
        # Wait for threads to stop
        if self._discovery_thread:
            self._discovery_thread.join(timeout=5)
            self._discovery_thread = None
        
        if self._multicast_thread:
            self._multicast_thread.join(timeout=5)
            self._multicast_thread = None
        
        logger.info("Mesh Discovery Service stopped")


def get_mesh_discovery_service(
    local_agent_id: str,
    local_endpoint: str,
    broker_url: str = "http://localhost:5555",
) -> MeshDiscoveryService:
    """
    Get or create mesh discovery service singleton.
    
    Args:
        local_agent_id: ID of local agent
        local_endpoint: Endpoint where this agent can be reached
        broker_url: SIMP broker URL
        
    Returns:
        MeshDiscoveryService instance
    """
    # Use agent_id as key for singleton
    key = f"{local_agent_id}_{broker_url}"
    
    if not hasattr(get_mesh_discovery_service, "_instances"):
        get_mesh_discovery_service._instances = {}
    
    if key not in get_mesh_discovery_service._instances:
        get_mesh_discovery_service._instances[key] = MeshDiscoveryService(
            local_agent_id=local_agent_id,
            local_endpoint=local_endpoint,
            broker_url=broker_url,
        )
    
    return get_mesh_discovery_service._instances[key]