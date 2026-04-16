"""
Enhanced Mesh Bus for SIMP Ecosystem
Features:
- Priority-based message queues
- Multi-threaded processing
- Message persistence
- Delivery confirmation
- Self-healing capabilities
"""

import json
import logging
import threading
import time
import heapq
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .packet import MeshPacket, MessageType, Priority, create_event_packet

logger = logging.getLogger(__name__)


class MessageStatus(Enum):
    """Status of a message in the mesh."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(order=True)
class PrioritizedMessage:
    """Message with priority for queueing."""
    priority: int
    timestamp: float
    packet: MeshPacket = field(compare=False)
    delivery_attempts: int = field(default=0, compare=False)
    status: MessageStatus = field(default=MessageStatus.PENDING, compare=False)
    delivery_callback: Optional[callable] = field(default=None, compare=False)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)


class EnhancedMeshBus:
    """
    Enhanced mesh bus with priority queues, persistence, and delivery confirmation.
    """
    
    def __init__(self, log_dir: Optional[str] = None, max_queue_size: int = 10000):
        """
        Initialize enhanced mesh bus.
        
        Args:
            log_dir: Directory for message persistence logs
            max_queue_size: Maximum number of messages in queue per agent
        """
        self._agent_queues: Dict[str, List[PrioritizedMessage]] = {}
        self._channel_subscribers: Dict[str, Set[str]] = {
            "system": set(),
            "safety_alerts": set(),
            "heartbeats": set(),
            "trade_updates": set(),
            "mesh_control": set(),
        }
        self._registered_agents: Set[str] = set()
        self._pending_offline: Dict[str, List[PrioritizedMessage]] = {}
        
        # Enhanced features
        self._message_store: Dict[str, PrioritizedMessage] = {}  # message_id -> message
        self._delivery_confirmation: Dict[str, bool] = {}  # message_id -> delivered
        self._agent_last_seen: Dict[str, float] = {}  # agent_id -> timestamp
        self._channel_stats: Dict[str, Dict[str, int]] = {}  # channel -> stats
        
        # Thread safety
        self._lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_running = False
        
        # Configuration
        self.max_queue_size = max_queue_size
        self.message_ttl = 3600  # 1 hour
        self.max_delivery_attempts = 3
        self.retry_delay = 5.0  # seconds
        
        # Persistence
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs" / "mesh"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self._stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "messages_expired": 0,
            "queue_overflows": 0,
            "avg_delivery_time": 0.0,
            "active_agents": 0,
            "active_channels": 0,
        }
        
        logger.info(f"Enhanced Mesh Bus initialized with max_queue_size={max_queue_size}")
    
    def _log_event(self, event_type: str, agent_id: str = "", channel: str = "", 
                   message: str = "", data: Optional[Dict] = None):
        """Log mesh event for auditing."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "agent_id": agent_id,
            "channel": channel,
            "message": message,
            "data": data or {},
        }
        
        log_file = self.log_dir / f"mesh_events_{datetime.utcnow().date()}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    
    def register_agent(self, agent_id: str) -> bool:
        """Register an agent with the mesh bus."""
        with self._lock:
            if agent_id in self._registered_agents:
                logger.warning(f"Agent {agent_id} already registered")
                return False
            
            self._registered_agents.add(agent_id)
            self._agent_queues[agent_id] = []
            self._agent_last_seen[agent_id] = time.time()
            
            # Auto-subscribe to system channel
            self._channel_subscribers["system"].add(agent_id)
            
            # Initialize channel stats
            for channel in self._channel_subscribers:
                if channel not in self._channel_stats:
                    self._channel_stats[channel] = {"messages": 0, "subscribers": 0}
                self._channel_stats[channel]["subscribers"] = len(self._channel_subscribers[channel])
            
            self._stats["active_agents"] = len(self._registered_agents)
            
            self._log_event("agent_registered", agent_id, "system", f"Agent {agent_id} registered")
            logger.info(f"Agent {agent_id} registered with mesh bus")
            return True
    
    def deregister_agent(self, agent_id: str) -> bool:
        """Deregister an agent from the mesh bus."""
        with self._lock:
            if agent_id not in self._registered_agents:
                logger.warning(f"Agent {agent_id} not registered")
                return False
            
            # Remove from all channels
            for channel, subscribers in self._channel_subscribers.items():
                subscribers.discard(agent_id)
                if channel in self._channel_stats:
                    self._channel_stats[channel]["subscribers"] = len(subscribers)
            
            # Clear agent queue
            if agent_id in self._agent_queues:
                # Mark all pending messages as failed
                for msg in self._agent_queues[agent_id]:
                    msg.status = MessageStatus.FAILED
                    self._stats["messages_failed"] += 1
                del self._agent_queues[agent_id]
            
            # Remove from registered agents
            self._registered_agents.discard(agent_id)
            if agent_id in self._agent_last_seen:
                del self._agent_last_seen[agent_id]
            
            self._stats["active_agents"] = len(self._registered_agents)
            
            self._log_event("agent_deregistered", agent_id, "system", f"Agent {agent_id} deregistered")
            logger.info(f"Agent {agent_id} deregistered from mesh bus")
            return True
    
    def is_agent_registered(self, agent_id: str) -> bool:
        """Check if an agent is registered."""
        with self._lock:
            return agent_id in self._registered_agents
    
    def update_agent_heartbeat(self, agent_id: str) -> bool:
        """Update agent heartbeat timestamp."""
        with self._lock:
            if agent_id not in self._registered_agents:
                return False
            
            self._agent_last_seen[agent_id] = time.time()
            return True
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of an agent."""
        with self._lock:
            if agent_id not in self._registered_agents:
                return None
            
            queue_size = len(self._agent_queues.get(agent_id, []))
            last_seen = self._agent_last_seen.get(agent_id, 0)
            
            return {
                "agent_id": agent_id,
                "registered": True,
                "queue_size": queue_size,
                "last_seen": datetime.fromtimestamp(last_seen).isoformat(),
                "seconds_since_seen": time.time() - last_seen,
                "channels": [ch for ch, subs in self._channel_subscribers.items() 
                            if agent_id in subs],
            }
    
    def subscribe(self, agent_id: str, channel: str) -> bool:
        """Subscribe agent to a channel."""
        with self._lock:
            if agent_id not in self._registered_agents:
                logger.warning(f"Cannot subscribe unregistered agent {agent_id}")
                return False
            
            if channel not in self._channel_subscribers:
                self._channel_subscribers[channel] = set()
                self._channel_stats[channel] = {"messages": 0, "subscribers": 0}
            
            self._channel_subscribers[channel].add(agent_id)
            self._channel_stats[channel]["subscribers"] = len(self._channel_subscribers[channel])
            
            self._log_event("channel_subscribed", agent_id, channel, 
                          f"Agent {agent_id} subscribed to {channel}")
            logger.info(f"Agent {agent_id} subscribed to channel {channel}")
            return True
    
    def unsubscribe(self, agent_id: str, channel: str) -> bool:
        """Unsubscribe agent from a channel."""
        with self._lock:
            if agent_id not in self._registered_agents:
                return False
            
            if channel in self._channel_subscribers:
                self._channel_subscribers[channel].discard(agent_id)
                if channel in self._channel_stats:
                    self._channel_stats[channel]["subscribers"] = len(self._channel_subscribers[channel])
                
                self._log_event("channel_unsubscribed", agent_id, channel,
                              f"Agent {agent_id} unsubscribed from {channel}")
                logger.info(f"Agent {agent_id} unsubscribed from channel {channel}")
                return True
            
            return False
    
    def get_channel_subscribers(self, channel: str) -> List[str]:
        """Get all subscribers to a channel."""
        with self._lock:
            return list(self._channel_subscribers.get(channel, set()))
    
    def send(self, packet: MeshPacket, delivery_callback: Optional[callable] = None) -> str:
        """
        Send a message with delivery confirmation.
        
        Returns:
            Message ID for tracking delivery status
        """
        with self._lock:
            # Create prioritized message
            priority_value = self._get_priority_value(packet.priority)
            prioritized_msg = PrioritizedMessage(
                priority=priority_value,
                timestamp=time.time(),
                packet=packet,
                delivery_callback=delivery_callback,
            )
            
            # Store message
            self._message_store[prioritized_msg.message_id] = prioritized_msg
            
            # Route message based on type
            if packet.recipient_id and packet.recipient_id != "*":
                success = self._send_to_agent(prioritized_msg)
            elif packet.channel:
                success = self._broadcast_to_channel(prioritized_msg)
            else:
                success = self._broadcast_to_all(prioritized_msg)
            
            if success:
                self._stats["messages_sent"] += 1
                self._log_event("message_sent", packet.sender_id, 
                              packet.channel or "broadcast",
                              f"Message {prioritized_msg.message_id} sent")
            else:
                prioritized_msg.status = MessageStatus.FAILED
                self._stats["messages_failed"] += 1
            
            return prioritized_msg.message_id
    
    def _get_priority_value(self, priority: Priority) -> int:
        """Convert Priority enum to integer value for queue ordering."""
        priority_map = {
            Priority.HIGH: 0,
            Priority.NORMAL: 1,
            Priority.LOW: 2,
        }
        return priority_map.get(priority, 1)
    
    def _send_to_agent(self, prioritized_msg: PrioritizedMessage) -> bool:
        """Send message to specific agent."""
        packet = prioritized_msg.packet
        agent_id = packet.recipient_id
        
        if agent_id not in self._registered_agents:
            logger.warning(f"Cannot send to unregistered agent {agent_id}")
            
            # Store for offline delivery
            if agent_id not in self._pending_offline:
                self._pending_offline[agent_id] = []
            self._pending_offline[agent_id].append(prioritized_msg)
            return True  # Message stored for later delivery
        
        # Add to agent's priority queue
        if agent_id not in self._agent_queues:
            self._agent_queues[agent_id] = []
        
        queue = self._agent_queues[agent_id]
        if len(queue) >= self.max_queue_size:
            logger.warning(f"Queue overflow for agent {agent_id}")
            self._stats["queue_overflows"] += 1
            # Remove lowest priority message
            if queue:
                removed = heapq.heappop(queue)
                removed.status = MessageStatus.FAILED
                self._stats["messages_failed"] += 1
        
        heapq.heappush(queue, prioritized_msg)
        logger.debug(f"Message queued for agent {agent_id}, priority {prioritized_msg.priority}")
        return True
    
    def _broadcast_to_channel(self, prioritized_msg: PrioritizedMessage) -> bool:
        """Broadcast message to all subscribers of a channel."""
        packet = prioritized_msg.packet
        channel = packet.channel
        
        if channel not in self._channel_subscribers:
            logger.warning(f"Channel {channel} does not exist")
            return False
        
        subscribers = self._channel_subscribers[channel]
        success_count = 0
        
        for agent_id in subscribers:
            # Create copy of packet for each subscriber
            packet_copy = MeshPacket(
                version=packet.version,
                msg_type=packet.msg_type,
                message_id=str(uuid.uuid4()),
                correlation_id=packet.correlation_id,
                sender_id=packet.sender_id,
                recipient_id=agent_id,
                channel=channel,
                timestamp=packet.timestamp,
                ttl_hops=packet.ttl_hops,
                ttl_seconds=packet.ttl_seconds,
                priority=packet.priority,
                payload=packet.payload,
                routing_history=packet.routing_history.copy() if packet.routing_history else [],
            )
            
            # Create new prioritized message for each subscriber
            subscriber_msg = PrioritizedMessage(
                priority=prioritized_msg.priority,
                timestamp=time.time(),
                packet=packet_copy,
                delivery_callback=None,  # No callback for broadcasts
            )
            
            self._message_store[subscriber_msg.message_id] = subscriber_msg
            if self._send_to_agent(subscriber_msg):
                success_count += 1
        
        # Update channel stats
        if channel in self._channel_stats:
            self._channel_stats[channel]["messages"] += success_count
        
        logger.debug(f"Broadcast to channel {channel}: {success_count}/{len(subscribers)} successful")
        return success_count > 0
    
    def _broadcast_to_all(self, prioritized_msg: PrioritizedMessage) -> bool:
        """Broadcast message to all registered agents."""
        packet = prioritized_msg.packet
        
        # Create system channel broadcast
        packet_copy = MeshPacket(
            version=packet.version,
            msg_type=packet.msg_type,
            message_id=str(uuid.uuid4()),
            correlation_id=packet.correlation_id,
            sender_id=packet.sender_id,
            recipient_id="*",  # Broadcast
            channel="system",
            timestamp=packet.timestamp,
            ttl_hops=packet.ttl_hops,
            ttl_seconds=packet.ttl_seconds,
            priority=packet.priority,
            payload=packet.payload,
            routing_history=packet.routing_history.copy() if packet.routing_history else [],
        )
        
        broadcast_msg = PrioritizedMessage(
            priority=prioritized_msg.priority,
            timestamp=time.time(),
            packet=packet_copy,
            delivery_callback=None,
        )
        
        return self._broadcast_to_channel(broadcast_msg)
    
    def receive(self, agent_id: str, max_messages: int = 1) -> List[MeshPacket]:
        """Receive messages for an agent."""
        with self._lock:
            if agent_id not in self._registered_agents:
                logger.warning(f"Agent {agent_id} not registered")
                return []
            
            queue = self._agent_queues.get(agent_id, [])
            if not queue:
                return []
            
            messages = []
            messages_to_remove = []
            
            # Update agent heartbeat
            self._agent_last_seen[agent_id] = time.time()
            
            # Process messages in priority order
            for _ in range(min(max_messages, len(queue))):
                if not queue:
                    break
                
                prioritized_msg = heapq.heappop(queue)
                packet = prioritized_msg.packet
                
                # Check if message expired
                # Convert ISO timestamp to datetime
                from datetime import datetime
                packet_time = datetime.fromisoformat(packet.timestamp.replace('Z', '+00:00')).timestamp()
                if time.time() > packet_time + packet.ttl_seconds:
                    prioritized_msg.status = MessageStatus.EXPIRED
                    self._stats["messages_expired"] += 1
                    self._log_event("message_expired", agent_id, packet.channel,
                                  f"Message {prioritized_msg.message_id} expired")
                    continue
                
                # Mark as delivered
                prioritized_msg.status = MessageStatus.DELIVERED
                self._delivery_confirmation[prioritized_msg.message_id] = True
                self._stats["messages_delivered"] += 1
                
                # Calculate delivery time
                delivery_time = time.time() - prioritized_msg.timestamp
                self._stats["avg_delivery_time"] = (
                    self._stats["avg_delivery_time"] * 0.9 + delivery_time * 0.1
                )
                
                # Call delivery callback if exists
                if prioritized_msg.delivery_callback:
                    try:
                        prioritized_msg.delivery_callback(prioritized_msg.message_id, True)
                    except Exception as e:
                        logger.error(f"Delivery callback failed: {e}")
                
                messages.append(packet)
                messages_to_remove.append(prioritized_msg.message_id)
            
            # Clean up delivered messages from store
            for msg_id in messages_to_remove:
                if msg_id in self._message_store:
                    del self._message_store[msg_id]
            
            # Deliver any pending offline messages
            self._deliver_offline(agent_id)
            
            return messages
    
    def _deliver_offline(self, agent_id: str):
        """Deliver messages that were pending while agent was offline."""
        if agent_id in self._pending_offline and self._pending_offline[agent_id]:
            pending_messages = self._pending_offline.pop(agent_id)
            queue = self._agent_queues.get(agent_id, [])
            
            for msg in pending_messages:
                # Check if message expired
                from datetime import datetime
                packet_time = datetime.fromisoformat(msg.packet.timestamp.replace('Z', '+00:00')).timestamp()
                if time.time() > packet_time + msg.packet.ttl_seconds:
                    msg.status = MessageStatus.EXPIRED
                    self._stats["messages_expired"] += 1
                    continue
                
                heapq.heappush(queue, msg)
                logger.info(f"Delivered {len(pending_messages)} pending messages to {agent_id}")
    
    def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific message."""
        with self._lock:
            if message_id not in self._message_store:
                return None
            
            msg = self._message_store[message_id]
            packet = msg.packet
            
            return {
                "message_id": message_id,
                "status": msg.status.value,
                "source_agent": packet.sender_id,
                "target_agent": packet.recipient_id,
                "target_channel": packet.channel,
                "priority": packet.priority.value,
                "delivery_attempts": msg.delivery_attempts,
                "created_at": datetime.fromtimestamp(msg.timestamp).isoformat(),
                "age_seconds": time.time() - msg.timestamp,
                "ttl_seconds": packet.ttl_seconds,
                "ttl_hops": packet.ttl_hops,
                "expires_at": datetime.fromtimestamp(
                    datetime.fromisoformat(packet.timestamp.replace('Z', '+00:00')).timestamp() + packet.ttl_seconds
                ).isoformat(),
            }
    
    def confirm_delivery(self, message_id: str) -> bool:
        """Confirm delivery of a message (called by receiving agent)."""
        with self._lock:
            if message_id not in self._message_store:
                return False
            
            msg = self._message_store[message_id]
            msg.status = MessageStatus.DELIVERED
            self._delivery_confirmation[message_id] = True
            
            # Call delivery callback
            if msg.delivery_callback:
                try:
                    msg.delivery_callback(message_id, True)
                except Exception as e:
                    logger.error(f"Delivery confirmation callback failed: {e}")
            
            self._log_event("delivery_confirmed", msg.packet.recipient_id, 
                          msg.packet.channel, f"Message {message_id} delivered")
            return True
    
    def retry_failed_messages(self) -> int:
        """Retry failed messages (for recovery scenarios)."""
        with self._lock:
            retry_count = 0
            
            for msg_id, msg in list(self._message_store.items()):
                if msg.status == MessageStatus.FAILED and msg.delivery_attempts < self.max_delivery_attempts:
                    # Reset status and retry
                    msg.status = MessageStatus.PENDING
                    msg.delivery_attempts += 1
                    
                    # Re-queue the message
                    if msg.packet.recipient_id and msg.packet.recipient_id != "*":
                        self._send_to_agent(msg)
                    
                    retry_count += 1
            
            if retry_count > 0:
                logger.info(f"Retried {retry_count} failed messages")
            
            return retry_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive mesh statistics."""
        with self._lock:
            stats = self._stats.copy()
            
            # Add current state
            stats.update({
                "total_messages_stored": len(self._message_store),
                "total_agents_registered": len(self._registered_agents),
                "total_channels": len(self._channel_subscribers),
                "pending_offline_messages": sum(len(msgs) for msgs in self._pending_offline.values()),
                "channel_stats": self._channel_stats.copy(),
                "uptime_seconds": getattr(self, "_start_time", time.time()) - time.time(),
            })
            
            # Add queue sizes
            queue_sizes = {}
            for agent_id, queue in self._agent_queues.items():
                queue_sizes[agent_id] = len(queue)
            stats["queue_sizes"] = queue_sizes
            
            return stats
    
    def _cleanup_expired(self):
        """Clean up expired messages and stale agents."""
        with self._lock:
            current_time = time.time()
            expired_count = 0
            stale_agent_count = 0
            
            # Clean expired messages
            messages_to_remove = []
            for msg_id, msg in self._message_store.items():
                packet = msg.packet
                packet_time = datetime.fromisoformat(packet.timestamp.replace('Z', '+00:00')).timestamp()
                if current_time > packet_time + packet.ttl_seconds:
                    msg.status = MessageStatus.EXPIRED
                    messages_to_remove.append(msg_id)
                    expired_count += 1
            
            for msg_id in messages_to_remove:
                del self._message_store[msg_id]
            
            # Clean stale agents (not seen for 5 minutes)
            agents_to_remove = []
            for agent_id, last_seen in self._agent_last_seen.items():
                if current_time - last_seen > 300:  # 5 minutes
                    agents_to_remove.append(agent_id)
                    stale_agent_count += 1
            
            for agent_id in agents_to_remove:
                self.deregister_agent(agent_id)
            
            if expired_count > 0 or stale_agent_count > 0:
                logger.debug(f"Cleanup: {expired_count} expired messages, {stale_agent_count} stale agents")
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while self._cleanup_running:
            time.sleep(60)  # Run every minute
            try:
                self._cleanup_expired()
                self.retry_failed_messages()
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    def start_cleanup(self):
        """Start background cleanup thread."""
        with self._lock:
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                return
            
            self._cleanup_running = True
            self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self._cleanup_thread.start()
            self._start_time = time.time()
            logger.info("Mesh bus cleanup thread started")
    
    def stop_cleanup(self):
        """Stop background cleanup thread."""
        with self._lock:
            self._cleanup_running = False
            if self._cleanup_thread:
                self._cleanup_thread.join(timeout=5)
                self._cleanup_thread = None
            logger.info("Mesh bus cleanup thread stopped")
    
    def shutdown(self):
        """Shutdown mesh bus cleanly."""
        self.stop_cleanup()
        
        with self._lock:
            # Save pending messages to disk
            if self._message_store:
                save_file = self.log_dir / f"mesh_state_{int(time.time())}.json"
                state = {
                    "timestamp": time.time(),
                    "messages": [
                        {
                            "message_id": msg_id,
                            "packet": msg.packet.to_dict(),
                            "status": msg.status.value,
                            "timestamp": msg.timestamp,
                        }
                        for msg_id, msg in self._message_store.items()
                        if msg.status == MessageStatus.PENDING
                    ]
                }
                
                with open(save_file, "w") as f:
                    json.dump(state, f, indent=2)
                
                logger.info(f"Saved {len(state['messages'])} pending messages to {save_file}")
            
            # Clear all data
            self._agent_queues.clear()
            self._channel_subscribers.clear()
            self._registered_agents.clear()
            self._pending_offline.clear()
            self._message_store.clear()
            self._delivery_confirmation.clear()
            self._agent_last_seen.clear()
            self._channel_stats.clear()
            
            logger.info("Enhanced Mesh Bus shutdown complete")


def get_enhanced_mesh_bus(log_dir: Optional[str] = None) -> EnhancedMeshBus:
    """
    Get or create enhanced mesh bus singleton.
    
    Args:
        log_dir: Directory for mesh logs
        
    Returns:
        EnhancedMeshBus instance
    """
    if not hasattr(get_enhanced_mesh_bus, "_instance"):
        get_enhanced_mesh_bus._instance = EnhancedMeshBus(log_dir=log_dir)
        get_enhanced_mesh_bus._instance.start_cleanup()
    
    return get_enhanced_mesh_bus._instance