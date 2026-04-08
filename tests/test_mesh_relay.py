"""
Tests for SIMP Mesh Relay Router (Sprint 73)
"""

import time
import pytest

from simp.transport.mesh_relay import MeshRouter, MeshPeer
from simp.transport.packet import (
    SimpPacket,
    MessageType,
    PacketFlags,
    agent_id_to_peer_id,
    IntentBloomFilter,
    DEFAULT_TTL,
)


class TestMeshPeer:
    def test_default_values(self):
        peer = MeshPeer()
        assert peer.transport == "http"
        assert peer.is_direct is True

    def test_is_stale(self):
        peer = MeshPeer(last_seen=time.time() - 600)
        assert peer.is_stale

    def test_not_stale(self):
        peer = MeshPeer(last_seen=time.time())
        assert not peer.is_stale

    def test_custom_peer(self):
        peer = MeshPeer(
            peer_id=agent_id_to_peer_id("bob"),
            agent_id="bob",
            transport="ble",
            capabilities=["trade"],
        )
        assert peer.agent_id == "bob"
        assert peer.transport == "ble"
        assert "trade" in peer.capabilities


class TestMeshRouter:
    def test_init(self):
        router = MeshRouter(local_agent_id="test")
        assert router.local_agent_id == "test"
        assert len(router.peers) == 0

    def test_add_peer(self):
        router = MeshRouter(local_agent_id="test")
        peer = MeshPeer(peer_id=b"\x01" * 8, agent_id="peer-1")
        assert router.add_peer(peer)
        assert len(router.peers) == 1

    def test_remove_peer(self):
        router = MeshRouter(local_agent_id="test")
        pid = b"\x01" * 8
        peer = MeshPeer(peer_id=pid, agent_id="peer-1")
        router.add_peer(peer)
        assert router.remove_peer(pid)
        assert len(router.peers) == 0

    def test_remove_nonexistent(self):
        router = MeshRouter()
        assert not router.remove_peer(b"\xff" * 8)

    def test_get_peer(self):
        router = MeshRouter()
        pid = b"\x02" * 8
        peer = MeshPeer(peer_id=pid, agent_id="p2")
        router.add_peer(peer)
        found = router.get_peer(pid)
        assert found is not None
        assert found.agent_id == "p2"

    def test_get_peer_by_agent_id(self):
        router = MeshRouter()
        peer = MeshPeer(
            peer_id=agent_id_to_peer_id("alice"),
            agent_id="alice",
        )
        router.add_peer(peer)
        found = router.get_peer_by_agent_id("alice")
        assert found is not None
        assert found.agent_id == "alice"

    def test_max_peers(self):
        router = MeshRouter(max_peers=2)
        router.add_peer(MeshPeer(peer_id=b"\x01" * 8))
        router.add_peer(MeshPeer(peer_id=b"\x02" * 8))
        assert not router.add_peer(MeshPeer(peer_id=b"\x03" * 8))

    def test_list_peers(self):
        router = MeshRouter()
        router.add_peer(MeshPeer(peer_id=b"\x01" * 8, agent_id="a"))
        router.add_peer(MeshPeer(peer_id=b"\x02" * 8, agent_id="b"))
        peers = router.list_peers()
        assert len(peers) == 2

    def test_prune_stale_peers(self):
        router = MeshRouter()
        router.add_peer(MeshPeer(peer_id=b"\x01" * 8, last_seen=time.time() - 600))
        router.add_peer(MeshPeer(peer_id=b"\x02" * 8, last_seen=time.time()))
        removed = router.prune_stale_peers()
        assert removed == 1
        assert len(router.peers) == 1


class TestShouldRelay:
    def test_duplicate_not_relayed(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(
            ttl=5,
            sender_id=b"\x01" * 8,
            payload=b"test-payload",
            timestamp=12345,
        )
        # Add to filter first
        dedup_key = pkt.sender_id + pkt.timestamp.to_bytes(4, "big") + pkt.payload[:8]
        router.seen_filter.add(dedup_key)
        assert not router.should_relay(pkt)

    def test_ttl_expired_not_relayed(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(ttl=1, sender_id=b"\x01" * 8)
        assert not router.should_relay(pkt)

    def test_own_packet_not_relayed(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(
            ttl=5,
            sender_id=router.local_peer_id,
        )
        assert not router.should_relay(pkt)

    def test_addressed_to_us_not_relayed(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(
            ttl=5,
            sender_id=b"\x01" * 8,
            recipient_id=router.local_peer_id,
            flags=PacketFlags.HAS_RECIPIENT,
        )
        assert not router.should_relay(pkt)

    def test_valid_relay(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(
            ttl=5,
            sender_id=b"\x99" * 8,
            payload=b"unique-payload-data",
            timestamp=99999,
        )
        assert router.should_relay(pkt)


class TestProcessIncoming:
    def test_deliver_to_us(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(
            ttl=5,
            sender_id=b"\x01" * 8,
            recipient_id=router.local_peer_id,
            flags=PacketFlags.HAS_RECIPIENT,
            payload=b"for-me-payload",
            timestamp=11111,
        )
        result = router.process_incoming(pkt)
        assert result["action"] == "deliver"

    def test_relay_to_others(self):
        router = MeshRouter(local_agent_id="me")
        # Add a peer to relay to
        router.add_peer(MeshPeer(peer_id=b"\x03" * 8, agent_id="charlie"))

        pkt = SimpPacket(
            ttl=5,
            sender_id=b"\x01" * 8,
            payload=b"relay-this-data",
            timestamp=22222,
        )
        result = router.process_incoming(pkt)
        assert result["action"] == "relay"
        assert result["packet"].ttl == 4  # Decremented
        assert len(result["relay_targets"]) > 0

    def test_drop_duplicate(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(
            ttl=5,
            sender_id=b"\x01" * 8,
            payload=b"dup-payload",
            timestamp=33333,
        )
        # Process twice
        router.process_incoming(pkt)
        result = router.process_incoming(pkt)
        assert result["action"] == "drop"
        assert result["reason"] == "duplicate"

    def test_drop_ttl_expired(self):
        router = MeshRouter(local_agent_id="me")
        pkt = SimpPacket(
            ttl=1,
            sender_id=b"\x01" * 8,
            payload=b"ttl-expired-payload",
            timestamp=44444,
        )
        result = router.process_incoming(pkt)
        assert result["action"] == "drop"
        assert result["reason"] == "ttl_expired"

    def test_relay_stats(self):
        router = MeshRouter(local_agent_id="me")
        stats = router.get_relay_stats()
        assert "packets_received" in stats
        assert "total_peers" in stats
        assert "active_peers" in stats
        assert "bloom_filter_count" in stats
