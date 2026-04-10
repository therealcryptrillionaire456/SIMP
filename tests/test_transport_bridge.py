"""
Tests for SIMP Transport Bridge (Sprint 71)
"""

import json
import pytest

from simp.transport.bridge import (
    intent_to_packet,
    packet_to_intent,
    build_ack_packet,
    build_discovery_packet,
    select_transport,
)
from simp.transport.packet import (
    MessageType,
    PacketFlags,
    agent_id_to_peer_id,
    encode,
    decode,
)


class TestIntentToPacket:
    def test_basic_conversion(self):
        intent = {"intent_type": "test", "params": {"key": "value"}}
        pkt = intent_to_packet(intent)
        assert pkt.msg_type == MessageType.INTENT
        assert len(pkt.payload) > 0

    def test_with_source_and_target(self):
        intent = {"intent_type": "trade", "target_agent": "bob"}
        pkt = intent_to_packet(intent, source_agent_id="alice", target_agent_id="bob")
        assert pkt.sender_id == agent_id_to_peer_id("alice")
        assert pkt.recipient_id == agent_id_to_peer_id("bob")
        assert pkt.flags & PacketFlags.HAS_RECIPIENT

    def test_signature_flag(self):
        intent = {"intent_type": "test", "signature": "abc123"}
        pkt = intent_to_packet(intent)
        assert pkt.flags & PacketFlags.HAS_SIGNATURE

    def test_custom_ttl(self):
        intent = {"intent_type": "test"}
        pkt = intent_to_packet(intent, ttl=3)
        assert pkt.ttl == 3


class TestPacketToIntent:
    def test_roundtrip(self):
        original = {"intent_type": "test", "params": {"x": 42}}
        pkt = intent_to_packet(original)
        recovered = packet_to_intent(pkt)
        assert recovered["intent_type"] == "test"
        assert recovered["params"]["x"] == 42

    def test_full_encode_decode_roundtrip(self):
        original = {"id": "intent-123", "source_agent": "alice", "target_agent": "bob"}
        pkt = intent_to_packet(original, source_agent_id="alice", target_agent_id="bob")
        encoded = encode(pkt)
        decoded = decode(encoded)
        recovered = packet_to_intent(decoded)
        assert recovered["id"] == "intent-123"


class TestBuildAckPacket:
    def test_basic_ack(self):
        ack = build_ack_packet("intent-123")
        assert ack.msg_type == MessageType.ACK
        assert ack.ttl == 1

        payload = json.loads(ack.payload.decode())
        assert payload["intent_id"] == "intent-123"
        assert payload["status"] == "received"

    def test_ack_with_agent(self):
        ack = build_ack_packet("intent-456", responder_agent_id="bob")
        assert ack.sender_id == agent_id_to_peer_id("bob")


class TestBuildDiscoveryPacket:
    def test_basic_discovery(self):
        disc = build_discovery_packet("agent-1")
        assert disc.msg_type == MessageType.DISCOVERY
        assert disc.sender_id == agent_id_to_peer_id("agent-1")

        payload = json.loads(disc.payload.decode())
        assert payload["agent_id"] == "agent-1"

    def test_discovery_with_capabilities(self):
        disc = build_discovery_packet("agent-2", "trading", ["trade", "query"])
        payload = json.loads(disc.payload.decode())
        assert payload["agent_type"] == "trading"
        assert "trade" in payload["capabilities"]


class TestSelectTransport:
    def test_default_http(self):
        assert select_transport("any-agent") == "http"

    def test_all_available_prefers_http(self):
        available = {"http": True, "ble": True, "nostr": True}
        assert select_transport("agent", available) == "http"

    def test_no_http_uses_ble(self):
        available = {"http": False, "ble": True, "nostr": True}
        assert select_transport("agent", available) == "ble"

    def test_only_nostr(self):
        available = {"http": False, "ble": False, "nostr": True}
        assert select_transport("agent", available) == "nostr"

    def test_nothing_available_falls_back_http(self):
        available = {"http": False, "ble": False, "nostr": False}
        assert select_transport("agent", available) == "http"

    def test_peer_hint_overrides(self):
        available = {"http": True, "ble": True, "nostr": True}
        hints = {"bob": "nostr"}
        assert select_transport("bob", available, hints) == "nostr"

    def test_peer_hint_ignored_if_unavailable(self):
        available = {"http": True, "ble": False, "nostr": False}
        hints = {"bob": "ble"}
        assert select_transport("bob", available, hints) == "http"
