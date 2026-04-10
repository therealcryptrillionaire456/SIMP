"""
Tests for SIMP BLE Transport (Sprint 74)

All tests work without bleak installed.
"""

import pytest

from simp.transport.ble_transport import (
    BleTransport,
    BleDevice,
    is_ble_available,
    SIMP_SERVICE_UUID,
    SIMP_CHAR_UUID,
    BLE_MTU,
    FRAGMENT_OVERHEAD,
    MAX_FRAGMENT_PAYLOAD,
)
from simp.transport.packet import (
    SimpPacket,
    MessageType,
    encode,
    decode,
    agent_id_to_peer_id,
)


class TestBleConstants:
    def test_service_uuid(self):
        assert SIMP_SERVICE_UUID is not None
        assert len(SIMP_SERVICE_UUID) > 0

    def test_char_uuid(self):
        assert SIMP_CHAR_UUID is not None
        assert SIMP_CHAR_UUID != SIMP_SERVICE_UUID

    def test_mtu(self):
        assert BLE_MTU == 512

    def test_fragment_overhead(self):
        assert FRAGMENT_OVERHEAD == 2

    def test_max_fragment_payload(self):
        assert MAX_FRAGMENT_PAYLOAD == BLE_MTU - FRAGMENT_OVERHEAD


class TestBleTransport:
    def test_init(self):
        bt = BleTransport(local_agent_id="test-agent")
        assert bt.local_agent_id == "test-agent"
        assert bt.local_peer_id == agent_id_to_peer_id("test-agent")

    def test_available_property(self):
        bt = BleTransport()
        # bleak is not installed in test env, so should be False
        assert bt.available == is_ble_available()

    def test_get_status(self):
        bt = BleTransport(local_agent_id="status-test")
        status = bt.get_status()
        assert "available" in status
        assert "mode" in status
        assert "stats" in status
        assert status["mode"] in ("active", "stub")


class TestFragmentation:
    def test_small_data_single_fragment(self):
        bt = BleTransport()
        data = b"small data"
        fragments = bt._fragment(data)
        assert len(fragments) == 1
        # Header: seq=0, total=1
        assert fragments[0][0] == 0
        assert fragments[0][1] == 1
        assert fragments[0][2:] == data

    def test_large_data_multiple_fragments(self):
        bt = BleTransport()
        data = b"x" * (MAX_FRAGMENT_PAYLOAD * 3)
        fragments = bt._fragment(data)
        assert len(fragments) == 3
        for i, frag in enumerate(fragments):
            assert frag[0] == i  # sequence number
            assert frag[1] == 3  # total fragments

    def test_reassemble_complete(self):
        bt = BleTransport()
        data = b"reassemble this data which is long " * 20
        fragments = bt._fragment(data)
        reassembled = bt._reassemble(fragments)
        assert reassembled == data

    def test_reassemble_incomplete_returns_none(self):
        bt = BleTransport()
        data = b"x" * (MAX_FRAGMENT_PAYLOAD * 2)
        fragments = bt._fragment(data)
        # Only pass first fragment
        result = bt._reassemble(fragments[:1])
        assert result is None

    def test_reassemble_empty_returns_none(self):
        bt = BleTransport()
        assert bt._reassemble([]) is None

    def test_fragment_roundtrip_with_packet(self):
        bt = BleTransport()
        pkt = SimpPacket(
            msg_type=MessageType.INTENT,
            payload=b'{"intent": "test", "data": "value"}',
            sender_id=agent_id_to_peer_id("alice"),
        )
        encoded = encode(pkt)
        fragments = bt._fragment(encoded)
        reassembled = bt._reassemble(fragments)
        decoded = decode(reassembled)
        assert decoded.payload == pkt.payload


class TestReceiveFragment:
    def test_single_fragment_packet(self):
        bt = BleTransport()
        pkt = SimpPacket(payload=b"test")
        encoded = encode(pkt)
        fragments = bt._fragment(encoded)
        result = bt.receive_fragment("AA:BB:CC:DD:EE:FF", fragments[0])
        assert result is not None
        assert result.payload == b"test"

    def test_multi_fragment_packet(self):
        bt = BleTransport()
        pkt = SimpPacket(payload=b"x" * 1000)
        encoded = encode(pkt)
        fragments = bt._fragment(encoded)

        result = None
        for frag in fragments:
            result = bt.receive_fragment("AA:BB:CC:DD:EE:FF", frag)

        assert result is not None
        assert result.payload == b"x" * 1000

    def test_too_short_fragment(self):
        bt = BleTransport()
        result = bt.receive_fragment("addr", b"\x00")
        assert result is None


class TestBleScanStub:
    @pytest.mark.asyncio
    async def test_scan_without_bleak(self):
        bt = BleTransport()
        if not bt.available:
            result = await bt.scan_for_peers()
            assert result == []

    @pytest.mark.asyncio
    async def test_send_without_bleak(self):
        bt = BleTransport()
        if not bt.available:
            pkt = SimpPacket(payload=b"test")
            result = await bt.send_packet(pkt, "AA:BB:CC:DD:EE:FF")
            assert result is False
