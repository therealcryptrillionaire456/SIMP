"""
SIMP Agent Mesh Bus - In-memory Store-and-Forward Router

MeshBus: Central message router for agent-to-agent communication with
store-and-forward semantics, channel subscriptions, and TTL-based expiration.
"""

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional, Deque, Any
from dataclasses import asdict

from .packet import MeshPacket, MessageType, Priority


logger = logging.getLogger("SIMP.MeshBus")


class MeshBus:
    """
    In-memory mesh message router with store-and-forward semantics.
    
    Responsibilities:
      - Maintain per-agent message queues
      - Handle channel subscriptions (pub/sub)
      - Store messages for offline agents
      - Expire messages based on TTL
      - Log mesh events for observability
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """
        Initialize MeshBus.
        
        Args:
            log_dir: Directory for mesh event logs (defaults to data/)
        """
        self._lock = threading.RLock()
        
        # Core data structures
        self._agent_queues: Dict[str, Deque[MeshPacket]] = {}
        self._channel_subscribers: Dict[str, Set[str]] = {}
        self._pending_offline: Dict[str, List[MeshPacket]] = {}
        self._registered_agents: Set[str] = set()
        
        # Default channels
        self._channel_subscribers["system"] = set()
        self._channel_subscribers["safety_alerts"] = set()
        self._channel_subscribers["heartbeats"] = set()
        
        # Logging setup
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "data"
        else:
            log_dir = Path(log_dir)
        
        log_dir.mkdir(exist_ok=True)
        self._log_path = log_dir / "mesh_events.jsonl"
        self._event_log_lock = threading.Lock()
        
        # Cleanup thread
        self._cleanup_interval = 60.0  # seconds
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        logger.info(f"MeshBus initialized with log path: {self._log_path}")
    
    def _log_event(self, event_type: str, packet: MeshPacket, 
                   status: str = "success", error_code: Optional[str] = None,
                   trace_id: Optional[str] = None) -> None:
        """
        Log mesh event to JSONL file.
        
        Args:
            event_type: Type of event (MESSAGE_SENT, MESSAGE_DELIVERED, etc.)
            packet: The MeshPacket involved
            status: Event status (success, error, dropped)
            error_code: Optional error code if status is error
            trace_id: Optional trace ID for correlation
        """
        event = {
            "event_id": str(time.time_ns()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message_id": packet.message_id,
            "sender_id": packet.sender_id,
            "recipient_id": packet.recipient_id,
            "channel": packet.channel,
            "msg_type": packet.msg_type,
            "status": status,
            "error_code": error_code,
            "trace_id": trace_id or packet.meta.get("trace_id"),
            "ttl_hops_remaining": packet.ttl_hops,
            "priority": packet.priority,
        }
        
        with self._event_log_lock:
            try:
                with open(self._log_path, "a") as f:
                    f.write(json.dumps(event) + "\n")
            except (IOError, OSError) as e:
                logger.error(f"Failed to write mesh event log: {e}")
    
    # ----------------------------------------------------------------------
    # Agent Management
    # ----------------------------------------------------------------------
    
    def register_agent(self, agent_id: str) -> None:
        """
        Register an agent with the mesh bus.
        
        Args:
            agent_id: Unique agent identifier
        """
        with self._lock:
            if agent_id in self._registered_agents:
                logger.debug(f"Agent {agent_id} already registered")
                return
            
            self._registered_agents.add(agent_id)
            self._agent_queues[agent_id] = deque()
            
            # Auto-subscribe to system channel
            self.subscribe(agent_id, "system")
            
            # Deliver any pending offline messages
            self._deliver_offline(agent_id)
            
            logger.info(f"Agent {agent_id} registered with MeshBus")
    
    def deregister_agent(self, agent_id: str) -> None:
        """
        Deregister an agent from the mesh bus.
        
        Args:
            agent_id: Agent identifier to deregister
        """
        with self._lock:
            if agent_id not in self._registered_agents:
                return
            
            # Remove from all channel subscriptions
            for channel in list(self._channel_subscribers.keys()):
                self._channel_subscribers[channel].discard(agent_id)
            
            # Clear agent queue
            if agent_id in self._agent_queues:
                del self._agent_queues[agent_id]
            
            self._registered_agents.discard(agent_id)
            logger.info(f"Agent {agent_id} deregistered from MeshBus")
    
    def is_agent_registered(self, agent_id: str) -> bool:
        """Check if an agent is currently registered."""
        with self._lock:
            return agent_id in self._registered_agents
    
    # ----------------------------------------------------------------------
    # Channel Management
    # ----------------------------------------------------------------------
    
    def subscribe(self, agent_id: str, channel: str) -> bool:
        """
        Subscribe an agent to a channel.
        
        Args:
            agent_id: Agent identifier
            channel: Channel name
            
        Returns:
            True if subscription successful, False otherwise
        """
        with self._lock:
            if agent_id not in self._registered_agents:
                # Auto-attach agent to the in-memory mesh bus. The persistent
                # AgentRegistry survives broker restarts but the mesh bus does
                # not — so an agent that registered before the last restart
                # can still be "known" while absent from _registered_agents.
                # Rather than refuse the subscribe (which breaks bridges that
                # already hold a valid session), lazily register the agent
                # here and proceed.
                logger.info(
                    f"Auto-registering {agent_id} on mesh bus before subscribe "
                    f"to {channel}"
                )
                self._registered_agents.add(agent_id)
                if agent_id not in self._agent_queues:
                    self._agent_queues[agent_id] = deque()

            if channel not in self._channel_subscribers:
                self._channel_subscribers[channel] = set()

            self._channel_subscribers[channel].add(agent_id)
            logger.debug(f"Agent {agent_id} subscribed to channel {channel}")
            return True
    
    def unsubscribe(self, agent_id: str, channel: str) -> bool:
        """
        Unsubscribe an agent from a channel.
        
        Args:
            agent_id: Agent identifier
            channel: Channel name
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        with self._lock:
            if channel in self._channel_subscribers:
                self._channel_subscribers[channel].discard(agent_id)
                logger.debug(f"Agent {agent_id} unsubscribed from channel {channel}")
                return True
            return False
    
    def get_channel_subscribers(self, channel: str) -> List[str]:
        """
        Get list of agents subscribed to a channel.
        
        Args:
            channel: Channel name
            
        Returns:
            List of agent IDs subscribed to the channel
        """
        with self._lock:
            subscribers = self._channel_subscribers.get(channel, set())
            return list(subscribers)

    def get_all_subscriptions(self) -> Dict[str, List[str]]:
        """Return channel -> sorted subscribers mapping."""
        with self._lock:
            return {
                channel: sorted(subscribers)
                for channel, subscribers in self._channel_subscribers.items()
            }

    def get_agent_channels(self, agent_id: str) -> List[str]:
        """Return sorted list of channels an agent is subscribed to."""
        with self._lock:
            return sorted(
                channel
                for channel, subscribers in self._channel_subscribers.items()
                if agent_id in subscribers
            )

    def get_registered_agents(self) -> List[str]:
        """Return sorted list of registered mesh agents."""
        with self._lock:
            return sorted(self._registered_agents)
    
    # ----------------------------------------------------------------------
    # Message Sending
    # ----------------------------------------------------------------------
    
    def send(self, packet: MeshPacket) -> bool:
        """
        Send a mesh packet.
        
        Handles:
          - Direct agent-to-agent delivery
          - Channel broadcasts
          - Store-and-forward for offline agents
        
        Args:
            packet: MeshPacket to send
            
        Returns:
            True if packet was accepted, False if invalid or expired
        """
        # Validate packet
        if packet.is_expired():
            self._log_event("MESSAGE_DROPPED", packet, "error", "TTL_EXPIRED")
            logger.warning(f"Packet {packet.message_id} expired, dropping")
            return False
        
        if not packet.sender_id:
            self._log_event("MESSAGE_DROPPED", packet, "error", "NO_SENDER")
            logger.warning(f"Packet {packet.message_id} has no sender, dropping")
            return False
        
        # Record routing hop
        packet.touch_hop("mesh_bus")
        
        with self._lock:
            # Direct delivery to specific agent
            if packet.recipient_id != "*" and not packet.channel:
                return self._send_to_agent(packet)
            
            # Channel broadcast
            if packet.channel:
                return self._broadcast_to_channel(packet)
            
            # Wildcard broadcast (to all registered agents)
            return self._broadcast_to_all(packet)
    
    def _send_to_agent(self, packet: MeshPacket) -> bool:
        """Send packet directly to a specific agent."""
        recipient_id = packet.recipient_id
        
        if recipient_id in self._registered_agents:
            # Agent is online - deliver immediately
            self._agent_queues[recipient_id].append(packet)
            self._log_event("MESSAGE_DELIVERED", packet, "success")
            logger.debug(f"Packet {packet.message_id} delivered to agent {recipient_id}")
            return True
        else:
            # Agent is offline - store for later
            if recipient_id not in self._pending_offline:
                self._pending_offline[recipient_id] = []
            self._pending_offline[recipient_id].append(packet)
            self._log_event("MESSAGE_STORED", packet, "success", trace_id=f"offline:{recipient_id}")
            logger.debug(f"Packet {packet.message_id} stored for offline agent {recipient_id}")
            return True
    
    def _broadcast_to_channel(self, packet: MeshPacket) -> bool:
        """Broadcast packet to all subscribers of a channel."""
        channel = packet.channel
        subscribers = self._channel_subscribers.get(channel, set())
        
        if not subscribers:
            self._log_event("MESSAGE_DROPPED", packet, "error", "NO_SUBSCRIBERS")
            logger.warning(f"Packet {packet.message_id} broadcast to empty channel {channel}")
            return False
        
        delivered = False
        for agent_id in subscribers:
            if agent_id == packet.sender_id:
                continue  # Don't deliver to sender
            
            packet_copy = MeshPacket.from_dict(packet.to_dict())
            packet_copy.recipient_id = agent_id
            
            if agent_id in self._registered_agents:
                self._agent_queues[agent_id].append(packet_copy)
                delivered = True
                self._log_event("MESSAGE_DELIVERED", packet_copy, "success")
            else:
                # Store for offline subscribers
                if agent_id not in self._pending_offline:
                    self._pending_offline[agent_id] = []
                self._pending_offline[agent_id].append(packet_copy)
                self._log_event("MESSAGE_STORED", packet_copy, "success", trace_id=f"offline:{agent_id}")
        
        if delivered:
            logger.debug(f"Packet {packet.message_id} broadcast to channel {channel} ({len(subscribers)} subscribers)")
        return delivered
    
    def _broadcast_to_all(self, packet: MeshPacket) -> bool:
        """Broadcast packet to all registered agents."""
        delivered = False
        for agent_id in self._registered_agents:
            if agent_id == packet.sender_id:
                continue  # Don't deliver to sender
            
            packet_copy = MeshPacket.from_dict(packet.to_dict())
            packet_copy.recipient_id = agent_id
            
            self._agent_queues[agent_id].append(packet_copy)
            delivered = True
            self._log_event("MESSAGE_DELIVERED", packet_copy, "success")
        
        if delivered:
            logger.debug(f"Packet {packet.message_id} broadcast to all agents ({len(self._registered_agents)} agents)")
        return delivered
    
    # ----------------------------------------------------------------------
    # Message Receiving
    # ----------------------------------------------------------------------
    
    def receive(self, agent_id: str, max_messages: int = 1) -> List[MeshPacket]:
        """
        Receive messages for an agent.
        
        Args:
            agent_id: Agent identifier
            max_messages: Maximum number of messages to return
            
        Returns:
            List of MeshPackets (may be empty)
        """
        with self._lock:
            if agent_id not in self._agent_queues:
                return []
            
            queue = self._agent_queues[agent_id]
            messages = []
            
            # Filter out expired messages
            valid_messages = []
            expired_count = 0
            
            while queue:
                packet = queue.popleft()
                if packet.is_expired():
                    self._log_event("MESSAGE_DROPPED", packet, "error", "TTL_EXPIRED")
                    expired_count += 1
                else:
                    valid_messages.append(packet)
            
            # Put valid messages back in queue
            for packet in valid_messages:
                queue.append(packet)
            
            if expired_count > 0:
                logger.debug(f"Dropped {expired_count} expired messages for agent {agent_id}")
            
            # Return requested number of messages
            for _ in range(min(max_messages, len(queue))):
                if queue:
                    packet = queue.popleft()
                    messages.append(packet)
                    self._log_event("MESSAGE_RECEIVED", packet, "success")
            
            return messages
    
    def peek(self, agent_id: str, max_messages: int = 1) -> List[MeshPacket]:
        """
        Peek at messages for an agent without removing them.
        
        Args:
            agent_id: Agent identifier
            max_messages: Maximum number of messages to peek at
            
        Returns:
            List of MeshPackets (may be empty)
        """
        with self._lock:
            if agent_id not in self._agent_queues:
                return []
            
            queue = self._agent_queues[agent_id]
            messages = []
            
            # Filter expired messages during peek
            now = datetime.now(timezone.utc)
            for packet in list(queue):  # Create copy to avoid modification during iteration
                if not packet.is_expired(now):
                    messages.append(packet)
                    if len(messages) >= max_messages:
                        break
            
            return messages[:max_messages]
    
    # ----------------------------------------------------------------------
    # Offline Message Handling
    # ----------------------------------------------------------------------
    
    def _deliver_offline(self, agent_id: str) -> None:
        """Deliver pending offline messages to a newly registered agent."""
        with self._lock:
            if agent_id in self._pending_offline and self._pending_offline[agent_id]:
                pending = self._pending_offline.pop(agent_id)
                delivered = 0
                expired = 0
                
                for packet in pending:
                    if packet.is_expired():
                        self._log_event("MESSAGE_DROPPED", packet, "error", "TTL_EXPIRED")
                        expired += 1
                    else:
                        self._agent_queues[agent_id].append(packet)
                        delivered += 1
                        self._log_event("MESSAGE_DELIVERED", packet, "success", trace_id="offline_delivery")
                
                if delivered > 0 or expired > 0:
                    logger.info(f"Delivered {delivered} pending messages to agent {agent_id} (dropped {expired} expired)")
    
    def get_pending_count(self, agent_id: str) -> int:
        """Get number of pending offline messages for an agent."""
        with self._lock:
            pending = self._pending_offline.get(agent_id, [])
            # Filter expired messages
            now = datetime.now(timezone.utc)
            valid_count = sum(1 for packet in pending if not packet.is_expired(now))
            return valid_count
    
    # ----------------------------------------------------------------------
    # Cleanup and Maintenance
    # ----------------------------------------------------------------------
    
    def _cleanup_expired(self) -> None:
        """Clean up expired messages from all queues."""
        with self._lock:
            now = datetime.now(timezone.utc)
            total_expired = 0
            
            # Clean agent queues
            for agent_id, queue in list(self._agent_queues.items()):
                valid_messages = []
                for packet in queue:
                    if packet.is_expired(now):
                        self._log_event("MESSAGE_DROPPED", packet, "error", "TTL_EXPIRED")
                        total_expired += 1
                    else:
                        valid_messages.append(packet)
                
                # Replace queue with valid messages only
                self._agent_queues[agent_id] = deque(valid_messages)
            
            # Clean pending offline messages
            for agent_id, pending in list(self._pending_offline.items()):
                valid_messages = []
                for packet in pending:
                    if packet.is_expired(now):
                        self._log_event("MESSAGE_DROPPED", packet, "error", "TTL_EXPIRED")
                        total_expired += 1
                    else:
                        valid_messages.append(packet)
                
                if valid_messages:
                    self._pending_offline[agent_id] = valid_messages
                else:
                    del self._pending_offline[agent_id]
            
            if total_expired > 0:
                logger.debug(f"Cleaned up {total_expired} expired messages")
    
    def _cleanup_loop(self) -> None:
        """Background thread for periodic cleanup."""
        while not self._shutdown_event.wait(self._cleanup_interval):
            try:
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Error in mesh bus cleanup: {e}")
    
    def start_cleanup(self) -> None:
        """Start background cleanup thread."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._shutdown_event.clear()
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                name="MeshBusCleanup",
                daemon=True
            )
            self._cleanup_thread.start()
            logger.info("MeshBus cleanup thread started")
    
    def stop_cleanup(self) -> None:
        """Stop background cleanup thread."""
        self._shutdown_event.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
            logger.info("MeshBus cleanup thread stopped")
    
    # ----------------------------------------------------------------------
    # Statistics and Diagnostics
    # ----------------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get mesh bus statistics."""
        with self._lock:
            stats = {
                "registered_agents": len(self._registered_agents),
                "total_queued_messages": sum(len(q) for q in self._agent_queues.values()),
                "total_pending_offline": sum(len(p) for p in self._pending_offline.values()),
                "channels": {
                    channel: len(subscribers)
                    for channel, subscribers in self._channel_subscribers.items()
                    if subscribers  # Only include non-empty channels
                },
                "agent_queue_sizes": {
                    agent_id: len(queue)
                    for agent_id, queue in self._agent_queues.items()
                }
            }
            return stats
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status information for a specific agent."""
        with self._lock:
            if agent_id not in self._registered_agents:
                return None
            
            status = {
                "registered": True,
                "queue_size": len(self._agent_queues.get(agent_id, [])),
                "pending_offline": len(self._pending_offline.get(agent_id, [])),
                "subscribed_channels": [
                    channel for channel, subscribers in self._channel_subscribers.items()
                    if agent_id in subscribers
                ]
            }
            return status
    
    # ----------------------------------------------------------------------
    # Lifecycle Management
    # ----------------------------------------------------------------------
    
    def shutdown(self) -> None:
        """Shutdown mesh bus and cleanup resources."""
        self.stop_cleanup()
        with self._lock:
            self._agent_queues.clear()
            self._channel_subscribers.clear()
            self._pending_offline.clear()
            self._registered_agents.clear()
        logger.info("MeshBus shutdown complete")


# Singleton instance for easy access
_mesh_bus_instance: Optional[MeshBus] = None


def get_mesh_bus() -> MeshBus:
    """Get or create singleton MeshBus instance."""
    global _mesh_bus_instance
    if _mesh_bus_instance is None:
        _mesh_bus_instance = MeshBus()
        _mesh_bus_instance.start_cleanup()
    return _mesh_bus_instance
