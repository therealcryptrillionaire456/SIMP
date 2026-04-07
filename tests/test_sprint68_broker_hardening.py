"""
Sprint 68 — Broker Hardening Tests

Tests for:
- OrderedDict intent_records with LRU eviction
- max_intent_records config
- _add_intent_record eviction behavior
- Agent client length-prefixed framing (_recv_exact, send/receive)
"""

import pytest
import asyncio
import struct
import json
import socket
import threading
from collections import OrderedDict

from simp.server.broker import SimpBroker, BrokerConfig, IntentRecord
from simp.server.agent_client import SimpAgentClient, _HEADER_FORMAT, _HEADER_SIZE, _MAX_MESSAGE_SIZE


class TestBrokerIntentRecordEviction:
    """Test LRU eviction for intent records."""

    def test_intent_records_is_ordered_dict(self):
        broker = SimpBroker()
        assert isinstance(broker.intent_records, OrderedDict)

    def test_default_max_intent_records(self):
        broker = SimpBroker()
        assert broker._max_intent_records == 10000

    def test_custom_max_intent_records(self):
        config = BrokerConfig(max_intent_records=50)
        broker = SimpBroker(config)
        assert broker._max_intent_records == 50

    def test_eviction_at_capacity(self):
        config = BrokerConfig(max_intent_records=5)
        broker = SimpBroker(config)
        broker.start()

        # Add 5 records
        for i in range(5):
            record = IntentRecord(
                intent_id=f"intent:{i}",
                source_agent="src",
                target_agent="tgt",
                intent_type="test",
                timestamp="2024-01-01",
                status="pending",
            )
            broker._add_intent_record(f"intent:{i}", record)

        assert len(broker.intent_records) == 5
        assert "intent:0" in broker.intent_records

        # Add 6th — should evict intent:0 (oldest)
        record = IntentRecord(
            intent_id="intent:5",
            source_agent="src",
            target_agent="tgt",
            intent_type="test",
            timestamp="2024-01-01",
            status="pending",
        )
        broker._add_intent_record("intent:5", record)

        assert len(broker.intent_records) == 5
        assert "intent:0" not in broker.intent_records
        assert "intent:5" in broker.intent_records

    def test_update_existing_moves_to_end(self):
        config = BrokerConfig(max_intent_records=5)
        broker = SimpBroker(config)
        broker.start()

        for i in range(5):
            record = IntentRecord(
                intent_id=f"intent:{i}",
                source_agent="src",
                target_agent="tgt",
                intent_type="test",
                timestamp="2024-01-01",
                status="pending",
            )
            broker._add_intent_record(f"intent:{i}", record)

        # Update intent:0 — should move to end
        updated = IntentRecord(
            intent_id="intent:0",
            source_agent="src",
            target_agent="tgt",
            intent_type="test",
            timestamp="2024-01-01",
            status="completed",
        )
        broker._add_intent_record("intent:0", updated)
        assert len(broker.intent_records) == 5

        # Now adding a new one should evict intent:1, not intent:0
        record = IntentRecord(
            intent_id="intent:5",
            source_agent="src",
            target_agent="tgt",
            intent_type="test",
            timestamp="2024-01-01",
            status="pending",
        )
        broker._add_intent_record("intent:5", record)
        assert "intent:0" in broker.intent_records
        assert "intent:1" not in broker.intent_records

    @pytest.mark.asyncio
    async def test_route_intent_uses_bounded_records(self):
        config = BrokerConfig(max_intent_records=3, max_agents=10)
        broker = SimpBroker(config)
        broker.start()
        broker.register_agent("agent:001", "test", "localhost:5001")

        for i in range(5):
            await broker.route_intent({
                "intent_id": f"intent:{i}",
                "source_agent": "client",
                "target_agent": "agent:001",
                "intent_type": "test",
                "params": {},
            })

        # Should only have 3 records
        assert len(broker.intent_records) <= 3


class TestAgentClientFraming:
    """Test length-prefixed framing in agent client."""

    def test_header_format(self):
        assert _HEADER_SIZE == 4
        # Encode and decode a length
        packed = struct.pack(_HEADER_FORMAT, 42)
        assert len(packed) == 4
        assert struct.unpack(_HEADER_FORMAT, packed)[0] == 42

    def test_recv_exact_basic(self):
        """Test _recv_exact with a mock socket-like pair."""
        server_sock, client_sock = socket.socketpair()
        try:
            data = b"hello world"
            server_sock.sendall(data)
            result = SimpAgentClient._recv_exact(client_sock, len(data))
            assert result == data
        finally:
            server_sock.close()
            client_sock.close()

    def test_send_and_receive_roundtrip(self):
        """Test that send/receive use length-prefix framing."""
        server_sock, client_sock = socket.socketpair()
        try:
            # Create a client that uses the server_sock as its connection
            client = SimpAgentClient("test", "test", 5001)
            client.socket = server_sock
            client.connected = True

            msg = {"type": "test", "data": "hello"}
            client._send_message(msg)

            # Read from the other end manually
            header = SimpAgentClient._recv_exact(client_sock, _HEADER_SIZE)
            msg_len = struct.unpack(_HEADER_FORMAT, header)[0]
            payload = SimpAgentClient._recv_exact(client_sock, msg_len)
            decoded = json.loads(payload)
            assert decoded == msg
        finally:
            server_sock.close()
            client_sock.close()
