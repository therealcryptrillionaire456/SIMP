"""
Sprint 68 — Broker Hardening Tests

Tests for:
- OrderedDict intent_records with LRU eviction
- max_intent_records config
- _add_intent_record eviction behavior
- Agent client length-prefixed framing (_recv_exact, send/receive)
"""

import pytest
import struct
import json
import socket
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

    def test_has_add_intent_record_method(self):
        broker = SimpBroker()
        assert hasattr(broker, '_add_intent_record')
        assert callable(broker._add_intent_record)


class TestAgentClientFraming:
    """Test length-prefixed framing in agent client."""

    def test_header_format(self):
        assert _HEADER_SIZE == 4
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

    def test_max_message_size(self):
        assert _MAX_MESSAGE_SIZE == 16 * 1024 * 1024
