"""
SIMP Agent Mesh Bus - Packet Model

MeshPacket: JSON-serializable message struct for agent-to-agent communication
via the MeshBus store-and-forward router.

Inspired by BitChat-style messaging with TTL, priority, and routing history.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List


class MessageType(str, Enum):
    """Mesh message types"""
    EVENT = "event"
    COMMAND = "command"
    REPLY = "reply"
    HEARTBEAT = "heartbeat"
    SYSTEM = "system"


class Priority(str, Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class MeshPacket:
    """
    MeshPacket - JSON-serializable message for agent mesh communication.
    
    Fields:
      version: Protocol version (1 for MVP)
      msg_type: MessageType enum value
      message_id: Unique UUID for this message
      correlation_id: Optional UUID for linking replies to requests
      sender_id: Source agent ID
      recipient_id: Target agent ID, '*' for broadcast, or channel name
      channel: Channel name for pub/sub
      timestamp: ISO 8601 UTC timestamp
      ttl_hops: Maximum number of routing hops before dropping
      ttl_seconds: Maximum age in seconds before dropping
      priority: Priority level
      payload: JSON-serializable message content
      meta: Additional metadata (trace_id, labels, etc.)
      routing_history: List of node IDs that have handled this packet
    """
    
    # Required fields
    version: int = 1
    msg_type: str = MessageType.EVENT
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    sender_id: str = ""
    recipient_id: str = ""
    channel: str = ""
    
    # Timestamp and TTL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_hops: int = 10
    ttl_seconds: int = 3600  # 1 hour default
    
    # Message properties
    priority: str = Priority.NORMAL
    
    # Content
    payload: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    
    # Routing
    routing_history: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert MeshPacket to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeshPacket":
        """Create MeshPacket from dictionary."""
        # Handle optional fields with defaults
        if "routing_history" not in data:
            data["routing_history"] = []
        if "meta" not in data:
            data["meta"] = {}
        
        return cls(**data)
    
    def touch_hop(self, node_id: str) -> None:
        """
        Record a routing hop and decrement TTL.
        
        Args:
            node_id: ID of the node that handled this packet
        """
        self.routing_history.append(node_id)
        self.ttl_hops -= 1
    
    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """
        Check if packet has expired based on TTL.
        
        Args:
            now: Current datetime (defaults to UTC now)
            
        Returns:
            True if packet has expired (TTL hops <= 0 or age > ttl_seconds)
        """
        if self.ttl_hops <= 0:
            return True
        
        if now is None:
            now = datetime.now(timezone.utc)
        
        try:
            packet_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
            age_seconds = (now - packet_time).total_seconds()
            return age_seconds > self.ttl_seconds
        except (ValueError, TypeError):
            # If timestamp parsing fails, assume expired for safety
            return True
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), separators=(',', ':'))
    
    @classmethod
    def from_json(cls, json_str: str) -> "MeshPacket":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return (f"MeshPacket({self.message_id[:8]}... "
                f"from:{self.sender_id} to:{self.recipient_id} "
                f"type:{self.msg_type} channel:{self.channel})")


# Helper functions for common packet types
def create_event_packet(
    sender_id: str,
    recipient_id: str,
    channel: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
    priority: str = Priority.NORMAL,
    ttl_seconds: int = 3600,
    meta: Optional[Dict[str, Any]] = None
) -> MeshPacket:
    """Create a standard event packet."""
    return MeshPacket(
        msg_type=MessageType.EVENT,
        sender_id=sender_id,
        recipient_id=recipient_id,
        channel=channel,
        payload=payload,
        correlation_id=correlation_id,
        priority=priority,
        ttl_seconds=ttl_seconds,
        meta=meta or {}
    )


def create_system_packet(
    sender_id: str,
    recipient_id: str,
    payload: Dict[str, Any],
    priority: str = Priority.HIGH,
    ttl_seconds: int = 300  # 5 minutes for system messages
) -> MeshPacket:
    """Create a system packet (high priority, short TTL)."""
    return MeshPacket(
        msg_type=MessageType.SYSTEM,
        sender_id=sender_id,
        recipient_id=recipient_id,
        channel="system",
        payload=payload,
        priority=priority,
        ttl_seconds=ttl_seconds
    )


def create_heartbeat_packet(agent_id: str) -> MeshPacket:
    """Create a heartbeat packet for agent liveness."""
    return MeshPacket(
        msg_type=MessageType.HEARTBEAT,
        sender_id=agent_id,
        recipient_id="*",  # Broadcast to all
        channel="heartbeats",
        payload={"agent_id": agent_id, "timestamp": datetime.now(timezone.utc).isoformat()},
        priority=Priority.LOW,
        ttl_seconds=60  # Short TTL for heartbeats
    )