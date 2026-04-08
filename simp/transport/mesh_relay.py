"""
SIMP Mesh Relay Router

Manages mesh peers and relay logic for multi-hop intent delivery.
Uses Bloom filter for deduplication and TTL for loop prevention.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set

from simp.transport.packet import (
    SimpPacket,
    MessageType,
    PacketFlags,
    IntentBloomFilter,
    agent_id_to_peer_id,
    decode,
    encode,
)

logger = logging.getLogger("SIMP.Transport.MeshRelay")


@dataclass
class MeshPeer:
    """A peer in the mesh network."""
    peer_id: bytes = b"\x00" * 8
    agent_id: str = ""
    transport: str = "http"  # "http", "ble", "nostr"
    last_seen: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)
    noise_session: Any = None  # Optional NoiseSession
    endpoint: str = ""
    is_direct: bool = True  # Direct or relay peer

    @property
    def is_stale(self) -> bool:
        """Peer is stale if not seen in 5 minutes."""
        return (time.time() - self.last_seen) > 300


class MeshRouter:
    """
    Mesh network router for SIMP transport layer.

    Manages peers, deduplication via Bloom filter, TTL enforcement,
    and relay target selection.
    """

    def __init__(self, local_agent_id: str = "", max_peers: int = 256):
        self.local_agent_id = local_agent_id
        self.local_peer_id = agent_id_to_peer_id(local_agent_id) if local_agent_id else b"\x00" * 8
        self.max_peers = max_peers

        self.peers: Dict[bytes, MeshPeer] = {}
        self.seen_filter = IntentBloomFilter(size=1024)

        # Stats
        self.stats = {
            "packets_received": 0,
            "packets_relayed": 0,
            "packets_delivered": 0,
            "packets_dropped": 0,
            "duplicates_filtered": 0,
        }

    def add_peer(self, peer: MeshPeer) -> bool:
        """Add or update a peer in the routing table."""
        if len(self.peers) >= self.max_peers and peer.peer_id not in self.peers:
            logger.warning("Max peers reached, dropping add request")
            return False

        self.peers[peer.peer_id] = peer
        logger.debug(f"Peer added/updated: {peer.agent_id} via {peer.transport}")
        return True

    def remove_peer(self, peer_id: bytes) -> bool:
        """Remove a peer from the routing table."""
        if peer_id in self.peers:
            del self.peers[peer_id]
            return True
        return False

    def get_peer(self, peer_id: bytes) -> Optional[MeshPeer]:
        """Get a peer by peer_id."""
        return self.peers.get(peer_id)

    def get_peer_by_agent_id(self, agent_id: str) -> Optional[MeshPeer]:
        """Get a peer by agent_id."""
        pid = agent_id_to_peer_id(agent_id)
        return self.peers.get(pid)

    def list_peers(self) -> List[MeshPeer]:
        """List all known peers."""
        return list(self.peers.values())

    def prune_stale_peers(self) -> int:
        """Remove peers not seen recently. Returns count removed."""
        stale = [pid for pid, p in self.peers.items() if p.is_stale]
        for pid in stale:
            del self.peers[pid]
        return len(stale)

    def should_relay(self, packet: SimpPacket) -> bool:
        """
        Determine if a packet should be relayed.

        Returns False if:
        - Already seen (Bloom filter)
        - TTL exhausted
        - Packet is from ourselves
        - Packet is addressed to us
        """
        # Create a dedup key from sender + timestamp + first 8 bytes of payload
        dedup_key = packet.sender_id + packet.timestamp.to_bytes(4, "big") + packet.payload[:8]

        # Check Bloom filter for duplicates
        if self.seen_filter.might_contain(dedup_key):
            self.stats["duplicates_filtered"] += 1
            return False

        # TTL check
        if packet.ttl <= 1:
            return False

        # Don't relay our own packets
        if packet.sender_id == self.local_peer_id:
            return False

        # Don't relay packets addressed specifically to us
        if (packet.flags & PacketFlags.HAS_RECIPIENT) and packet.recipient_id == self.local_peer_id:
            return False

        return True

    def process_incoming(self, packet: SimpPacket) -> Dict[str, Any]:
        """
        Process an incoming packet.

        Returns a dict describing what to do:
        {
            "action": "deliver" | "relay" | "drop",
            "packet": SimpPacket (possibly modified),
            "relay_targets": [MeshPeer, ...],
            "reason": str,
        }
        """
        self.stats["packets_received"] += 1

        # Create dedup key and mark as seen
        dedup_key = packet.sender_id + packet.timestamp.to_bytes(4, "big") + packet.payload[:8]

        # Check for duplicate
        if self.seen_filter.might_contain(dedup_key):
            self.stats["duplicates_filtered"] += 1
            self.stats["packets_dropped"] += 1
            return {
                "action": "drop",
                "packet": packet,
                "relay_targets": [],
                "reason": "duplicate",
            }

        # Mark as seen
        self.seen_filter.add(dedup_key)

        # Is this addressed to us?
        is_for_us = False
        if packet.flags & PacketFlags.HAS_RECIPIENT:
            if packet.recipient_id == self.local_peer_id:
                is_for_us = True

        if is_for_us:
            self.stats["packets_delivered"] += 1
            return {
                "action": "deliver",
                "packet": packet,
                "relay_targets": [],
                "reason": "addressed_to_us",
            }

        # Check if we should relay
        if packet.ttl <= 1:
            self.stats["packets_dropped"] += 1
            return {
                "action": "drop",
                "packet": packet,
                "relay_targets": [],
                "reason": "ttl_expired",
            }

        if packet.sender_id == self.local_peer_id:
            self.stats["packets_dropped"] += 1
            return {
                "action": "drop",
                "packet": packet,
                "relay_targets": [],
                "reason": "own_packet",
            }

        # Decrement TTL and relay
        relayed = SimpPacket(
            version=packet.version,
            msg_type=packet.msg_type,
            ttl=packet.ttl - 1,
            timestamp=packet.timestamp,
            flags=packet.flags,
            payload=packet.payload,
            sender_id=packet.sender_id,
            recipient_id=packet.recipient_id,
        )

        # Determine relay targets (all peers except sender)
        relay_targets = [
            p for p in self.peers.values()
            if p.peer_id != packet.sender_id and not p.is_stale
        ]

        # If packet has a specific recipient, try to narrow targets
        if packet.flags & PacketFlags.HAS_RECIPIENT:
            specific = self.peers.get(packet.recipient_id)
            if specific and not specific.is_stale:
                relay_targets = [specific]

        self.stats["packets_relayed"] += 1
        return {
            "action": "relay",
            "packet": relayed,
            "relay_targets": relay_targets,
            "reason": "forwarding",
        }

    def get_relay_stats(self) -> Dict[str, Any]:
        """Get relay statistics."""
        active_peers = sum(1 for p in self.peers.values() if not p.is_stale)
        return {
            **self.stats,
            "total_peers": len(self.peers),
            "active_peers": active_peers,
            "stale_peers": len(self.peers) - active_peers,
            "bloom_filter_count": self.seen_filter.count,
        }
