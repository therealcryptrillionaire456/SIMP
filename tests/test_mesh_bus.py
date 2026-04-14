"""
Tests for SIMP Mesh Bus router.
"""

import json
import tempfile
import time
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

from simp.mesh.bus import MeshBus
from simp.mesh.packet import MeshPacket, MessageType, Priority, create_event_packet


class TestMeshBusBasics:
    """Test basic MeshBus functionality."""
    
    def test_bus_initialization(self):
        """Test MeshBus initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = MeshBus(log_dir=tmpdir)
            
            assert bus is not None
            assert hasattr(bus, "_agent_queues")
            assert hasattr(bus, "_channel_subscribers")
            assert hasattr(bus, "_pending_offline")
            assert hasattr(bus, "_registered_agents")
            
            # Check default channels exist
            assert "system" in bus._channel_subscribers
            assert "safety_alerts" in bus._channel_subscribers
            assert "heartbeats" in bus._channel_subscribers
            
            bus.shutdown()
    
    def test_agent_registration(self):
        """Test agent registration."""
        bus = MeshBus()
        
        # Register agent
        bus.register_agent("agent_a")
        
        assert "agent_a" in bus._registered_agents
        assert "agent_a" in bus._agent_queues
        assert bus.is_agent_registered("agent_a")
        
        # Should auto-subscribe to system channel
        assert "agent_a" in bus._channel_subscribers["system"]
        
        bus.shutdown()
    
    def test_agent_deregistration(self):
        """Test agent deregistration."""
        bus = MeshBus()
        
        bus.register_agent("agent_a")
        bus.subscribe("agent_a", "test_channel")
        
        assert bus.is_agent_registered("agent_a")
        assert "agent_a" in bus._channel_subscribers["test_channel"]
        
        # Deregister
        bus.deregister_agent("agent_a")
        
        assert not bus.is_agent_registered("agent_a")
        assert "agent_a" not in bus._agent_queues
        assert "agent_a" not in bus._channel_subscribers["test_channel"]
        assert "agent_a" not in bus._channel_subscribers["system"]
        
        bus.shutdown()
    
    def test_channel_subscription(self):
        """Test channel subscription management."""
        bus = MeshBus()
        
        bus.register_agent("agent_a")
        bus.register_agent("agent_b")
        
        # Subscribe agents to channel
        assert bus.subscribe("agent_a", "test_channel")
        assert bus.subscribe("agent_b", "test_channel")
        
        # Get subscribers
        subscribers = bus.get_channel_subscribers("test_channel")
        assert "agent_a" in subscribers
        assert "agent_b" in subscribers
        assert len(subscribers) == 2
        
        # Unsubscribe
        assert bus.unsubscribe("agent_a", "test_channel")
        subscribers = bus.get_channel_subscribers("test_channel")
        assert "agent_a" not in subscribers
        assert "agent_b" in subscribers
        
        # Try to subscribe unregistered agent
        assert not bus.subscribe("unregistered_agent", "test_channel")
        
        bus.shutdown()
    
    def test_send_to_agent_direct(self):
        """Test direct agent-to-agent messaging."""
        bus = MeshBus()
        
        bus.register_agent("sender")
        bus.register_agent("receiver")
        
        # Create and send packet
        packet = create_event_packet(
            sender_id="sender",
            recipient_id="receiver",
            channel="",  # Empty for direct message
            payload={"message": "hello"},
        )
        
        assert bus.send(packet)
        
        # Receiver should have message
        messages = bus.receive("receiver", max_messages=10)
        assert len(messages) == 1
        assert messages[0].sender_id == "sender"
        assert messages[0].payload["message"] == "hello"
        
        bus.shutdown()
    
    def test_send_to_nonexistent_agent(self):
        """Test sending to non-existent agent (store for offline)."""
        bus = MeshBus()
        
        bus.register_agent("sender")
        
        # Send to non-existent agent
        packet = create_event_packet(
            sender_id="sender",
            recipient_id="offline_agent",
            channel="",  # Empty channel for direct message
            payload={"message": "hello"},
        )
        
        assert bus.send(packet)
        
        # Message should be in pending offline storage
        pending_count = bus.get_pending_count("offline_agent")
        assert pending_count == 1
        
        bus.shutdown()
    
    def test_broadcast_to_channel(self):
        """Test channel broadcast messaging."""
        bus = MeshBus()
        
        # Register and subscribe agents
        agents = ["agent_a", "agent_b", "agent_c"]
        for agent in agents:
            bus.register_agent(agent)
            bus.subscribe(agent, "broadcast_channel")
        
        # Send broadcast
        packet = create_event_packet(
            sender_id="broadcaster",
            recipient_id="*",  # Wildcard for broadcast
            channel="broadcast_channel",
            payload={"announcement": "system_update"},
        )
        
        assert bus.send(packet)
        
        # All subscribers should receive message (except sender, who isn't registered)
        for agent in agents:
            messages = bus.receive(agent, max_messages=10)
            assert len(messages) == 1
            assert messages[0].payload["announcement"] == "system_update"
        
        bus.shutdown()
    
    def test_broadcast_to_all(self):
        """Test broadcast to all registered agents."""
        bus = MeshBus()
        
        # Register agents
        agents = ["agent_a", "agent_b", "agent_c"]
        for agent in agents:
            bus.register_agent(agent)
        
        # Send broadcast to all
        packet = create_event_packet(
            sender_id="system",
            recipient_id="*",  # Wildcard
            channel="",  # Empty channel for broadcast to all
            payload={"system": "reboot"},
        )
        
        assert bus.send(packet)
        
        # All agents should receive message
        for agent in agents:
            messages = bus.receive(agent, max_messages=10)
            assert len(messages) == 1
            assert messages[0].payload["system"] == "reboot"
        
        bus.shutdown()


class TestMeshBusMessageHandling:
    """Test message handling and queue management."""
    
    def test_message_priority(self):
        """Test that messages are delivered in order."""
        bus = MeshBus()
        bus.register_agent("receiver")
        
        # Send multiple messages
        messages_to_send = []
        for i in range(5):
            packet = create_event_packet(
                sender_id="sender",
                recipient_id="receiver",
                channel="",  # Empty channel for direct message
                payload={"index": i},
            )
            messages_to_send.append(packet.message_id)
            bus.send(packet)
        
        # Receive messages
        received = bus.receive("receiver", max_messages=10)
        
        # Should receive all messages in order
        assert len(received) == 5
        for i, msg in enumerate(received):
            assert msg.payload["index"] == i
        
        bus.shutdown()
    
    def test_max_messages_receive(self):
        """Test max_messages parameter in receive."""
        bus = MeshBus()
        bus.register_agent("receiver")
        
        # Send 10 messages
        for i in range(10):
            packet = create_event_packet(
                sender_id="sender",
                recipient_id="receiver",
                channel="",  # Empty channel for direct message
                payload={"index": i},
            )
            bus.send(packet)
        
        # Receive only 3 messages
        received = bus.receive("receiver", max_messages=3)
        assert len(received) == 3
        
        # Receive remaining 7
        received = bus.receive("receiver", max_messages=10)
        assert len(received) == 7
        
        bus.shutdown()
    
    def test_peek_messages(self):
        """Test peeking at messages without removing them."""
        bus = MeshBus()
        bus.register_agent("receiver")
        
        # Send message
        packet = create_event_packet(
            sender_id="sender",
            recipient_id="receiver",
            channel="",  # Empty channel for direct message
            payload={"test": "data"},
        )
        bus.send(packet)
        
        # Peek multiple times
        for _ in range(3):
            peeked = bus.peek("receiver", max_messages=10)
            assert len(peeked) == 1
            assert peeked[0].payload["test"] == "data"
        
        # Actually receive it
        received = bus.receive("receiver", max_messages=10)
        assert len(received) == 1
        
        # Queue should now be empty
        peeked = bus.peek("receiver", max_messages=10)
        assert len(peeked) == 0
        
        bus.shutdown()
    
    def test_expired_message_filtering(self):
        """Test that expired messages are filtered out."""
        bus = MeshBus()
        bus.register_agent("receiver")
        
        # Create expired packet (0 TTL seconds)
        expired_packet = MeshPacket(
            sender_id="sender",
            recipient_id="receiver",
            ttl_seconds=0,  # Already expired
            payload={"status": "expired"},
        )
        
        # Create valid packet
        valid_packet = create_event_packet(
            sender_id="sender",
            recipient_id="receiver",
            channel="",  # Empty channel for direct message
            payload={"status": "valid"},
        )
        
        # Send both
        bus.send(expired_packet)
        bus.send(valid_packet)
        
        # Should only receive valid message
        received = bus.receive("receiver", max_messages=10)
        assert len(received) == 1
        assert received[0].payload["status"] == "valid"
        
        bus.shutdown()
    
    def test_offline_message_delivery(self):
        """Test store-and-forward for offline agents."""
        bus = MeshBus()
        
        bus.register_agent("sender")
        
        # Send message to offline agent
        packet = create_event_packet(
            sender_id="sender",
            recipient_id="offline_agent",
            channel="",  # Empty channel for direct message
            payload={"message": "hello"},
        )
        
        assert bus.send(packet)
        
        # Message should be pending
        pending_count = bus.get_pending_count("offline_agent")
        assert pending_count == 1
        
        # Register offline agent
        bus.register_agent("offline_agent")
        
        # Should receive pending message
        messages = bus.receive("offline_agent", max_messages=10)
        assert len(messages) == 1
        assert messages[0].payload["message"] == "hello"
        
        # Pending count should be 0
        pending_count = bus.get_pending_count("offline_agent")
        assert pending_count == 0
        
        bus.shutdown()
    
    def test_expired_offline_messages(self):
        """Test that expired offline messages are not delivered."""
        bus = MeshBus()
        
        bus.register_agent("sender")
        
        # Create expired packet for offline agent
        expired_packet = MeshPacket(
            sender_id="sender",
            recipient_id="offline_agent",
            ttl_seconds=0,  # Already expired
            payload={"status": "expired"},
        )
        
        # Create valid packet
        valid_packet = create_event_packet(
            sender_id="sender",
            recipient_id="offline_agent",
            channel="",  # Empty channel for direct message
            payload={"status": "valid"},
        )
        
        # Send both
        bus.send(expired_packet)
        bus.send(valid_packet)
        
        # Register offline agent
        bus.register_agent("offline_agent")
        
        # Should only receive valid message
        messages = bus.receive("offline_agent", max_messages=10)
        assert len(messages) == 1
        assert messages[0].payload["status"] == "valid"
        
        bus.shutdown()


class TestMeshBusThreadSafety:
    """Test thread safety of MeshBus operations."""
    
    def test_concurrent_registration(self):
        """Test concurrent agent registration."""
        bus = MeshBus()
        
        def register_agent(agent_id):
            bus.register_agent(agent_id)
            bus.subscribe(agent_id, "test_channel")
        
        # Register agents concurrently
        threads = []
        for i in range(10):
            t = threading.Thread(target=register_agent, args=(f"agent_{i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All agents should be registered
        for i in range(10):
            assert bus.is_agent_registered(f"agent_{i}")
            assert f"agent_{i}" in bus._channel_subscribers["test_channel"]
        
        bus.shutdown()
    
    def test_concurrent_send_receive(self):
        """Test concurrent send and receive operations."""
        bus = MeshBus()
        bus.register_agent("receiver")
        
        sent_count = 0
        received_count = 0
        lock = threading.Lock()
        
        def send_messages():
            nonlocal sent_count
            for i in range(50):
                packet = MeshPacket(
                    msg_type=MessageType.COMMAND,
                    sender_id=f"sender_{threading.current_thread().name}",
                    recipient_id="receiver",
                    payload={"index": i},
                )
                if bus.send(packet):
                    with lock:
                        sent_count += 1
        
        def receive_messages():
            nonlocal received_count
            for _ in range(50):
                messages = bus.receive("receiver", max_messages=5)
                with lock:
                    received_count += len(messages)
                time.sleep(0.001)  # Small delay
        
        # Create sender and receiver threads
        senders = [threading.Thread(target=send_messages) for _ in range(5)]
        receivers = [threading.Thread(target=receive_messages) for _ in range(3)]
        
        # Start all threads
        for t in senders + receivers:
            t.start()
        
        # Wait for completion
        for t in senders + receivers:
            t.join()
        
        # Verify counts
        assert sent_count == 250  # 5 senders * 50 messages each
        assert received_count == sent_count  # All messages should be received
        
        bus.shutdown()


class TestMeshBusStatistics:
    """Test statistics and monitoring functions."""
    
    def test_get_statistics(self):
        """Test get_statistics method."""
        bus = MeshBus()
        
        # Register agents and send messages
        bus.register_agent("agent_a")
        bus.register_agent("agent_b")
        bus.subscribe("agent_a", "channel_1")
        bus.subscribe("agent_b", "channel_1")
        bus.subscribe("agent_a", "channel_2")
        
        # Send some messages
        for i in range(3):
            packet = create_event_packet(
                sender_id="sender",
                recipient_id="agent_a",
                channel="",  # Empty channel for direct message
                payload={"index": i},
            )
            bus.send(packet)
        
        # Send to offline agent
        offline_packet = create_event_packet(
            sender_id="sender",
            recipient_id="offline_agent",
            channel="",  # Empty channel for direct message
            payload={"test": "offline"},
        )
        bus.send(offline_packet)
        
        # Get statistics
        stats = bus.get_statistics()
        
        assert stats["registered_agents"] == 2
        assert stats["total_queued_messages"] == 3  # Only for registered agents
        assert stats["total_pending_offline"] == 1
        
        # Check channel statistics
        assert "channel_1" in stats["channels"]
        assert stats["channels"]["channel_1"] == 2
        assert stats["channels"]["channel_2"] == 1
        
        # Check agent queue sizes
        assert "agent_a" in stats["agent_queue_sizes"]
        assert stats["agent_queue_sizes"]["agent_a"] == 3
        assert "agent_b" in stats["agent_queue_sizes"]
        assert stats["agent_queue_sizes"]["agent_b"] == 0
        
        bus.shutdown()
    
    def test_get_agent_status(self):
        """Test get_agent_status method."""
        bus = MeshBus()
        
        bus.register_agent("agent_a")
        bus.subscribe("agent_a", "channel_1")
        bus.subscribe("agent_a", "channel_2")
        
        # Send message
        packet = create_event_packet(
            sender_id="sender",
            recipient_id="agent_a",
            channel="",  # Empty channel for direct message
            payload={"test": "data"},
        )
        bus.send(packet)
        
        # Send to offline (pending)
        offline_packet = create_event_packet(
            sender_id="sender",
            recipient_id="agent_a",
            channel="",  # Empty channel for direct message
            payload={"test": "offline"},
        )
        # Temporarily deregister to simulate offline
        bus.deregister_agent("agent_a")
        bus.send(offline_packet)
        bus.register_agent("agent_a")  # Re-register
        
        # Get status
        status = bus.get_agent_status("agent_a")
        
        assert status is not None
        assert status["registered"] is True
        assert status["queue_size"] == 1  # One message in queue (delivered offline message)
        assert status["pending_offline"] == 0  # Pending message was delivered
        # Note: When agent is deregistered, subscriptions are lost
        # So we need to re-subscribe
        bus.subscribe("agent_a", "channel_1")
        bus.subscribe("agent_a", "channel_2")
        status = bus.get_agent_status("agent_a")  # Get updated status
        assert "channel_1" in status["subscribed_channels"]
        assert "channel_2" in status["subscribed_channels"]
        
        # Test non-existent agent
        status = bus.get_agent_status("non_existent")
        assert status is None
        
        bus.shutdown()


class TestMeshBusLogging:
    """Test event logging functionality."""
    
    def test_event_log_creation(self):
        """Test that event log is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = MeshBus(log_dir=tmpdir)
            
            log_path = Path(tmpdir) / "mesh_events.jsonl"
            assert log_path.exists() or not log_path.exists()  # May be created on first write
            
            bus.register_agent("test_agent")
            
            # Send a message to trigger logging
            packet = create_event_packet(
                sender_id="sender",
                recipient_id="test_agent",
                channel="",  # Empty channel for direct message
                payload={"test": "data"},
            )
            bus.send(packet)
            
            # Log file should exist now
            assert log_path.exists()
            
            bus.shutdown()
    
    def test_event_log_content(self):
        """Test that events are logged correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = MeshBus(log_dir=tmpdir)
            
            log_path = Path(tmpdir) / "mesh_events.jsonl"
            
            bus.register_agent("receiver")
            bus.subscribe("receiver", "test_channel")  # Subscribe to channel first
            
            # Send a message
            packet = create_event_packet(
                sender_id="sender",
                recipient_id="receiver",
                channel="test_channel",
                payload={"test": "data"},
            )
            bus.send(packet)
            
            # Read log file
            with open(log_path, "r") as f:
                lines = f.readlines()
            
            # Should have at least one event
            assert len(lines) >= 1
            
            # Parse first event
            event = json.loads(lines[0])
            
            assert event["event_type"] in ["MESSAGE_SENT", "MESSAGE_DELIVERED", "MESSAGE_STORED", "MESSAGE_DROPPED"]
            assert event["message_id"] == packet.message_id
            assert event["sender_id"] == "sender"
            assert event["recipient_id"] == "receiver"
            assert event["channel"] == "test_channel"
            assert event["msg_type"] == "event"
            assert event["status"] == "success"
            
            bus.shutdown()


class TestMeshBusCleanup:
    """Test cleanup and maintenance functions."""
    
    def test_cleanup_expired(self):
        """Test cleanup of expired messages."""
        bus = MeshBus()
        
        bus.register_agent("receiver")
        
        # Create expired message
        expired_packet = MeshPacket(
            sender_id="sender",
            recipient_id="receiver",
            ttl_seconds=0,  # Already expired
            payload={"status": "expired"},
        )
        
        # Create valid message
        valid_packet = create_event_packet(
            sender_id="sender",
            recipient_id="receiver",
            channel="",  # Empty channel for direct message
            payload={"status": "valid"},
        )
        
        # Send both
        bus.send(expired_packet)
        bus.send(valid_packet)
        
        # Manually trigger cleanup
        bus._cleanup_expired()
        
        # Should only have valid message
        messages = bus.peek("receiver", max_messages=10)
        assert len(messages) == 1
        assert messages[0].payload["status"] == "valid"
        
        bus.shutdown()
    
    def test_cleanup_thread(self):
        """Test background cleanup thread."""
        bus = MeshBus()
        
        # Start cleanup thread
        bus.start_cleanup()
        
        # Give it a moment to start
        time.sleep(0.1)
        
        # Verify thread is running
        assert bus._cleanup_thread is not None
        assert bus._cleanup_thread.is_alive()
        
        # Stop cleanup thread
        bus.stop_cleanup()
        
        # Give it a moment to stop
        time.sleep(0.1)
        
        # Thread should not be alive
        assert not bus._cleanup_thread.is_alive()
        
        bus.shutdown()


class TestMeshBusEdgeCases:
    """Test edge cases and error handling."""
    
    def test_send_invalid_packet(self):
        """Test sending invalid packet."""
        bus = MeshBus()
        
        # Packet with no sender
        invalid_packet = MeshPacket(
            sender_id="",  # Empty sender
            recipient_id="receiver",
            payload={"test": "data"},
        )
        
        # Should fail
        assert not bus.send(invalid_packet)
        
        bus.shutdown()
    
    def test_send_expired_packet(self):
        """Test sending already expired packet."""
        bus = MeshBus()
        
        bus.register_agent("receiver")
        
        # Create expired packet
        expired_packet = MeshPacket(
            sender_id="sender",
            recipient_id="receiver",
            ttl_seconds=0,  # Already expired
            payload={"test": "data"},
        )
        
        # Should fail
        assert not bus.send(expired_packet)
        
        # Receiver should have no messages
        messages = bus.receive("receiver", max_messages=10)
        assert len(messages) == 0
        
        bus.shutdown()
    
    def test_empty_channel_broadcast(self):
        """Test broadcast to empty channel."""
        bus = MeshBus()
        
        # Create channel with no subscribers
        packet = create_event_packet(
            sender_id="sender",
            recipient_id="*",
            channel="empty_channel",
            payload={"test": "data"},
        )
        
        # Should fail (no subscribers)
        assert not bus.send(packet)
        
        bus.shutdown()
    
    def test_duplicate_agent_registration(self):
        """Test duplicate agent registration."""
        bus = MeshBus()
        
        # Register same agent twice
        bus.register_agent("agent_a")
        bus.register_agent("agent_a")  # Should be idempotent (no error)
        
        # Agent should still be registered
        assert bus.is_agent_registered("agent_a")
        
        bus.shutdown()
    
    def test_unsubscribe_nonexistent(self):
        """Test unsubscribing from non-existent channel."""
        bus = MeshBus()
        
        bus.register_agent("agent_a")
        
        # Unsubscribe from non-existent channel
        assert not bus.unsubscribe("agent_a", "non_existent_channel")
        
        bus.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])