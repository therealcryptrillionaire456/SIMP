"""
Tests for SIMP Transport Packet (Sprint 71)
"""

import struct
import time
import pytest

from simp.transport.packet import (
    SimpPacket,
    MessageType,
    PacketFlags,
    encode,
    decode,
    agent_id_to_peer_id,
    IntentBloomFilter,
    HEADER_SIZE,
    PACKET_VERSION,
    DEFAULT_TTL,
    BLOCK_SIZES,
    _pkcs7_pad,
    _pkcs7_unpad,
    _select_block_size,
)


class TestMessageType:
    def test_intent_value(self):
        assert MessageType.INTENT == 0x01

    def test_ack_value(self):
        assert MessageType.ACK == 0x02

    def test_handshake_values(self):
        assert MessageType.HANDSHAKE_INIT == 0x10
        assert MessageType.HANDSHAKE_RESP == 0x11
        assert MessageType.HANDSHAKE_FIN == 0x12

    def test_heartbeat_value(self):
        assert MessageType.HEARTBEAT == 0x20

    def test_discovery_value(self):
        assert MessageType.DISCOVERY == 0x30

    def test_fragment_values(self):
        assert MessageType.FRAGMENT_START == 0x40
        assert MessageType.FRAGMENT_CONT == 0x41
        assert MessageType.FRAGMENT_END == 0x42


class TestPacketFlags:
    def test_none_flag(self):
        assert PacketFlags.NONE == 0

    def test_has_recipient(self):
        assert PacketFlags.HAS_RECIPIENT == 0x01

    def test_has_signature(self):
        assert PacketFlags.HAS_SIGNATURE == 0x02

    def test_is_compressed(self):
        assert PacketFlags.IS_COMPRESSED == 0x04

    def test_flag_combination(self):
        flags = PacketFlags.HAS_RECIPIENT | PacketFlags.HAS_SIGNATURE
        assert flags & PacketFlags.HAS_RECIPIENT
        assert flags & PacketFlags.HAS_SIGNATURE
        assert not (flags & PacketFlags.IS_COMPRESSED)


class TestSimpPacket:
    def test_default_values(self):
        pkt = SimpPacket()
        assert pkt.version == PACKET_VERSION
        assert pkt.msg_type == MessageType.INTENT
        assert pkt.ttl == DEFAULT_TTL
        assert pkt.flags == PacketFlags.NONE
        assert pkt.payload == b""
        assert pkt.sender_id == b"\x00" * 8
        assert pkt.recipient_id == b"\x00" * 8

    def test_payload_len_property(self):
        pkt = SimpPacket(payload=b"hello world")
        assert pkt.payload_len == 11

    def test_custom_values(self):
        pkt = SimpPacket(
            version=1,
            msg_type=MessageType.DISCOVERY,
            ttl=5,
            flags=PacketFlags.HAS_RECIPIENT,
            payload=b"test",
        )
        assert pkt.msg_type == MessageType.DISCOVERY
        assert pkt.ttl == 5
        assert pkt.flags == PacketFlags.HAS_RECIPIENT


class TestAgentIdToPeerId:
    def test_returns_8_bytes(self):
        result = agent_id_to_peer_id("agent-1")
        assert isinstance(result, bytes)
        assert len(result) == 8

    def test_deterministic(self):
        a = agent_id_to_peer_id("test-agent")
        b = agent_id_to_peer_id("test-agent")
        assert a == b

    def test_different_ids_different_peers(self):
        a = agent_id_to_peer_id("agent-a")
        b = agent_id_to_peer_id("agent-b")
        assert a != b


class TestPKCS7Padding:
    def test_pad_short_data(self):
        padded = _pkcs7_pad(b"hi", 256)
        assert len(padded) == 256
        assert padded[-1] == 254  # 256 - 2 = 254

    def test_unpad_recovers_original(self):
        original = b"hello world test data"
        padded = _pkcs7_pad(original, 256)
        recovered = _pkcs7_unpad(padded)
        assert recovered == original

    def test_pad_empty(self):
        padded = _pkcs7_pad(b"", 256)
        assert len(padded) == 256

    def test_block_size_selection(self):
        assert _select_block_size(100) == 256
        assert _select_block_size(300) == 512
        assert _select_block_size(600) == 1024
        assert _select_block_size(1500) == 2048


class TestEncodeDecodeRoundTrip:
    def test_basic_roundtrip(self):
        original = SimpPacket(
            msg_type=MessageType.INTENT,
            ttl=5,
            payload=b'{"type":"test"}',
            sender_id=agent_id_to_peer_id("alice"),
            recipient_id=agent_id_to_peer_id("bob"),
            flags=PacketFlags.HAS_RECIPIENT,
        )
        encoded = encode(original)
        decoded = decode(encoded)

        assert decoded.version == original.version
        assert decoded.msg_type == original.msg_type
        assert decoded.ttl == original.ttl
        assert decoded.flags == original.flags
        assert decoded.payload == original.payload
        assert decoded.sender_id == original.sender_id
        assert decoded.recipient_id == original.recipient_id

    def test_encode_produces_block_aligned(self):
        pkt = SimpPacket(payload=b"short")
        encoded = encode(pkt)
        assert len(encoded) in BLOCK_SIZES or len(encoded) % BLOCK_SIZES[-1] == 0

    def test_empty_payload_roundtrip(self):
        original = SimpPacket(msg_type=MessageType.HEARTBEAT, payload=b"")
        encoded = encode(original)
        decoded = decode(encoded)
        assert decoded.msg_type == MessageType.HEARTBEAT
        assert decoded.payload == b""

    def test_large_payload_roundtrip(self):
        payload = b"x" * 1500
        original = SimpPacket(payload=payload)
        encoded = encode(original)
        decoded = decode(encoded)
        assert decoded.payload == payload

    def test_decode_too_short_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode(b"\x00" * 5)

    def test_header_size_is_13(self):
        assert HEADER_SIZE == 13


class TestIntentBloomFilter:
    def test_add_and_check(self):
        bf = IntentBloomFilter()
        bf.add(b"test-intent-1")
        assert bf.might_contain(b"test-intent-1")
        assert bf.count == 1

    def test_not_contain(self):
        bf = IntentBloomFilter()
        bf.add(b"item-a")
        assert not bf.might_contain(b"item-b-definitely-not-there")

    def test_string_input(self):
        bf = IntentBloomFilter()
        bf.add("string-item")
        assert bf.might_contain("string-item")

    def test_clear(self):
        bf = IntentBloomFilter()
        bf.add(b"data")
        bf.clear()
        assert bf.count == 0
        # After clear, the item should not be found (with high probability)
        assert not bf.might_contain(b"data")

    def test_multiple_items(self):
        bf = IntentBloomFilter()
        items = [f"intent-{i}".encode() for i in range(50)]
        for item in items:
            bf.add(item)
        for item in items:
            assert bf.might_contain(item)
        assert bf.count == 50

    def test_custom_size(self):
        bf = IntentBloomFilter(size=512)
        assert bf.size == 512
        assert bf.num_bits == 512 * 8
