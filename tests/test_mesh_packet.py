"""
Tests for SIMP Mesh Packet model.
"""

import json
import time
from datetime import datetime, timezone, timedelta
import pytest

from simp.mesh.packet import (
    MeshPacket,
    MessageType,
    Priority,
    create_event_packet,
    create_system_packet,
    create_heartbeat_packet,
)


class TestMeshPacket:
    """Test MeshPacket dataclass and utilities."""
    
    def test_packet_creation(self):
        """Test basic packet creation."""
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            channel="test_channel",
            payload={"test": "data"},
        )
        
        assert packet.sender_id == "agent_a"
        assert packet.recipient_id == "agent_b"
        assert packet.channel == "test_channel"
        assert packet.payload == {"test": "data"}
        assert packet.version == 1
        assert packet.msg_type == MessageType.EVENT
        assert packet.priority == Priority.NORMAL
        assert packet.ttl_hops == 10
        assert packet.ttl_seconds == 3600
        assert packet.message_id is not None
        assert packet.timestamp is not None
        assert packet.routing_history == []
    
    def test_packet_to_dict(self):
        """Test packet serialization to dictionary."""
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            payload={"key": "value"},
        )
        
        data = packet.to_dict()
        
        assert data["sender_id"] == "agent_a"
        assert data["recipient_id"] == "agent_b"
        assert data["payload"] == {"key": "value"}
        assert data["version"] == 1
        assert data["message_id"] == packet.message_id
        assert data["timestamp"] == packet.timestamp
    
    def test_packet_from_dict(self):
        """Test packet deserialization from dictionary."""
        original = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            payload={"test": "data"},
            meta={"trace_id": "123"},
            routing_history=["node1", "node2"],
        )
        
        data = original.to_dict()
        restored = MeshPacket.from_dict(data)
        
        assert restored.sender_id == original.sender_id
        assert restored.recipient_id == original.recipient_id
        assert restored.payload == original.payload
        assert restored.meta == original.meta
        assert restored.routing_history == original.routing_history
        assert restored.message_id == original.message_id
        assert restored.timestamp == original.timestamp
    
    def test_packet_json_serialization(self):
        """Test JSON serialization/deserialization."""
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            payload={"nested": {"key": "value"}},
        )
        
        # Serialize to JSON
        json_str = packet.to_json()
        assert isinstance(json_str, str)
        
        # Deserialize from JSON
        restored = MeshPacket.from_json(json_str)
        
        assert restored.sender_id == packet.sender_id
        assert restored.recipient_id == packet.recipient_id
        assert restored.payload == packet.payload
    
    def test_touch_hop(self):
        """Test recording routing hops."""
        packet = MeshPacket(sender_id="agent_a", recipient_id="agent_b")
        initial_hops = packet.ttl_hops
        
        packet.touch_hop("node1")
        
        assert packet.routing_history == ["node1"]
        assert packet.ttl_hops == initial_hops - 1
        
        packet.touch_hop("node2")
        
        assert packet.routing_history == ["node1", "node2"]
        assert packet.ttl_hops == initial_hops - 2
    
    def test_is_expired_hops(self):
        """Test expiration based on TTL hops."""
        packet = MeshPacket(sender_id="agent_a", recipient_id="agent_b", ttl_hops=2)
        
        # Not expired yet
        assert not packet.is_expired()
        
        # Use all hops
        packet.touch_hop("node1")
        packet.touch_hop("node2")
        
        # Should be expired (0 hops left)
        assert packet.is_expired()
    
    def test_is_expired_time(self):
        """Test expiration based on TTL seconds."""
        # Create packet with very short TTL
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            ttl_seconds=1,  # 1 second TTL
        )
        
        # Not expired immediately
        assert not packet.is_expired()
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        assert packet.is_expired()
    
    def test_is_expired_with_custom_time(self):
        """Test expiration check with custom datetime."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(seconds=10)
        past = now - timedelta(seconds=10)
        
        # Packet created now with 5 second TTL
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            ttl_seconds=5,
        )
        
        # With future time (packet should be expired)
        assert packet.is_expired(future)
        
        # With past time (packet should not be expired)
        assert not packet.is_expired(past)
    
    def test_invalid_timestamp_expiration(self):
        """Test expiration with invalid timestamp."""
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            timestamp="invalid-timestamp",  # Invalid format
        )
        
        # Should treat invalid timestamp as expired for safety
        assert packet.is_expired()
    
    def test_packet_str_representation(self):
        """Test string representation."""
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            channel="test_channel",
            msg_type=MessageType.EVENT,
        )
        
        str_repr = str(packet)
        
        assert "MeshPacket" in str_repr
        assert packet.message_id[:8] in str_repr
        assert "agent_a" in str_repr
        assert "agent_b" in str_repr
        assert "test_channel" in str_repr
        assert "event" in str_repr.lower()


class TestPacketHelpers:
    """Test packet helper functions."""
    
    def test_create_event_packet(self):
        """Test create_event_packet helper."""
        packet = create_event_packet(
            sender_id="agent_a",
            recipient_id="agent_b",
            channel="test_channel",
            payload={"event": "test"},
            correlation_id="corr_123",
            priority=Priority.HIGH,
            ttl_seconds=1800,
            meta={"trace_id": "456"},
        )
        
        assert packet.sender_id == "agent_a"
        assert packet.recipient_id == "agent_b"
        assert packet.channel == "test_channel"
        assert packet.payload == {"event": "test"}
        assert packet.msg_type == MessageType.EVENT
        assert packet.correlation_id == "corr_123"
        assert packet.priority == Priority.HIGH
        assert packet.ttl_seconds == 1800
        assert packet.meta == {"trace_id": "456"}
    
    def test_create_system_packet(self):
        """Test create_system_packet helper."""
        packet = create_system_packet(
            sender_id="system_monitor",
            recipient_id="*",
            payload={"alert": "high_cpu"},
            priority=Priority.HIGH,
            ttl_seconds=300,
        )
        
        assert packet.sender_id == "system_monitor"
        assert packet.recipient_id == "*"
        assert packet.channel == "system"
        assert packet.payload == {"alert": "high_cpu"}
        assert packet.msg_type == MessageType.SYSTEM
        assert packet.priority == Priority.HIGH
        assert packet.ttl_seconds == 300
    
    def test_create_heartbeat_packet(self):
        """Test create_heartbeat_packet helper."""
        packet = create_heartbeat_packet("agent_a")
        
        assert packet.sender_id == "agent_a"
        assert packet.recipient_id == "*"
        assert packet.channel == "heartbeats"
        assert packet.msg_type == MessageType.HEARTBEAT
        assert packet.priority == Priority.LOW
        assert packet.ttl_seconds == 60
        assert "agent_id" in packet.payload
        assert "timestamp" in packet.payload
        assert packet.payload["agent_id"] == "agent_a"
    
    def test_message_type_enum(self):
        """Test MessageType enum values."""
        assert MessageType.EVENT.value == "event"
        assert MessageType.COMMAND.value == "command"
        assert MessageType.REPLY.value == "reply"
        assert MessageType.HEARTBEAT.value == "heartbeat"
        assert MessageType.SYSTEM.value == "system"
        
        # Test string representation
        assert str(MessageType.EVENT.value) == "event"
    
    def test_priority_enum(self):
        """Test Priority enum values."""
        assert Priority.LOW.value == "low"
        assert Priority.NORMAL.value == "normal"
        assert Priority.HIGH.value == "high"
        
        # Test string representation
        assert str(Priority.NORMAL.value) == "normal"


class TestPacketEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_packet(self):
        """Test packet with minimal fields."""
        packet = MeshPacket()
        
        assert packet.sender_id == ""
        assert packet.recipient_id == ""
        assert packet.channel == ""
        assert packet.payload == {}
        assert packet.meta == {}
        assert packet.routing_history == []
        assert packet.message_id is not None
        assert packet.timestamp is not None
    
    def test_packet_with_special_characters(self):
        """Test packet with special characters in fields."""
        packet = MeshPacket(
            sender_id="agent-123@domain",
            recipient_id="agent_456#test",
            channel="channel/with/slashes",
            payload={"key": "value with spaces", "number": 123.45},
            meta={"special": "chars: !@#$%^&*()"},
        )
        
        # Should serialize/deserialize correctly
        data = packet.to_dict()
        restored = MeshPacket.from_dict(data)
        
        assert restored.sender_id == packet.sender_id
        assert restored.recipient_id == packet.recipient_id
        assert restored.channel == packet.channel
        assert restored.payload == packet.payload
        assert restored.meta == packet.meta
    
    def test_large_payload(self):
        """Test packet with large payload."""
        large_payload = {
            "array": list(range(1000)),
            "nested": {
                "deep": {
                    "deeper": {
                        "value": "very deep"
                    }
                }
            },
            "text": "x" * 1000,  # 1000 character string
        }
        
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            payload=large_payload,
        )
        
        # Should serialize/deserialize correctly
        json_str = packet.to_json()
        restored = MeshPacket.from_json(json_str)
        
        assert restored.payload["array"] == large_payload["array"]
        assert restored.payload["nested"]["deep"]["deeper"]["value"] == "very deep"
        assert len(restored.payload["text"]) == 1000
    
    def test_correlation_id_persistence(self):
        """Test that correlation_id is preserved through serialization."""
        correlation_id = "test-correlation-123"
        
        packet = MeshPacket(
            sender_id="agent_a",
            recipient_id="agent_b",
            correlation_id=correlation_id,
        )
        
        # Through dict
        data = packet.to_dict()
        assert data["correlation_id"] == correlation_id
        
        restored = MeshPacket.from_dict(data)
        assert restored.correlation_id == correlation_id
        
        # Through JSON
        json_str = packet.to_json()
        restored_json = MeshPacket.from_json(json_str)
        assert restored_json.correlation_id == correlation_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])