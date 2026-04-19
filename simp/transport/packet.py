"""
SIMP Transport Packet Format

Binary packet format for multi-transport delivery (BLE mesh, Nostr relay, HTTP).
13-byte header + variable payload with PKCS#7 padding to block boundaries.
"""

import hashlib
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import Optional


class MessageType(IntEnum):
    """SIMP transport message types"""
    INTENT = 0x01
    ACK = 0x02
    HANDSHAKE_INIT = 0x10
    HANDSHAKE_RESP = 0x11
    HANDSHAKE_FIN = 0x12
    HEARTBEAT = 0x20
    DISCOVERY = 0x30
    FRAGMENT_START = 0x40
    FRAGMENT_CONT = 0x41
    FRAGMENT_END = 0x42


class PacketFlags(IntFlag):
    """Packet flag bits"""
    NONE = 0x00
    HAS_RECIPIENT = 0x01
    HAS_SIGNATURE = 0x02
    IS_COMPRESSED = 0x04


# Header format: version(1) + type(1) + ttl(1) + timestamp(4) + flags(1) + reserved(1) + payload_len(4) = 13 bytes
HEADER_FORMAT = ">BBBIBBB I"  # Note: struct packing
HEADER_SIZE = 13
HEADER_STRUCT = struct.Struct(">BBB I B B H")
# version(1) + type(1) + ttl(1) + timestamp(4) + flags(1) + reserved(1) + payload_len(2) = 11
# Actually let's use a clean 13-byte header:
# version(1) + msg_type(1) + ttl(1) + timestamp(4) + flags(1) + payload_len(4) + reserved(1) = 13

PACKET_VERSION = 1
DEFAULT_TTL = 7
BLOCK_SIZES = [256, 512, 1024, 2048]


@dataclass
class SimpPacket:
    """Binary packet for SIMP multi-transport delivery"""
    version: int = PACKET_VERSION
    msg_type: int = MessageType.INTENT
    ttl: int = DEFAULT_TTL
    timestamp: int = field(default_factory=lambda: int(time.time()))
    flags: int = PacketFlags.NONE
    payload: bytes = b""
    sender_id: bytes = b"\x00" * 8
    recipient_id: bytes = b"\x00" * 8

    @property
    def payload_len(self) -> int:
        return len(self.payload)


def agent_id_to_peer_id(agent_id: str) -> bytes:
    """Convert agent ID string to 8-byte peer ID via SHA256 truncation."""
    return hashlib.sha256(agent_id.encode("utf-8")).digest()[:8]


def _select_block_size(data_len: int) -> int:
    """Select smallest block size that fits the data."""
    for bs in BLOCK_SIZES:
        if data_len <= bs:
            return bs
    return BLOCK_SIZES[-1]


def _pkcs7_pad(data: bytes, block_size: int) -> bytes:
    """Apply PKCS#7 padding to reach block_size boundary."""
    if len(data) == 0:
        # For empty data, fill the entire block with padding
        return bytes([block_size & 0xFF]) * block_size
    if len(data) >= block_size:
        target = ((len(data) // block_size) + 1) * block_size
    else:
        target = block_size
    pad_len = target - len(data)
    if pad_len == 0:
        pad_len = block_size
    if pad_len > 255:
        pad_len = 255
    return data + bytes([pad_len]) * pad_len


def _pkcs7_unpad(data: bytes) -> bytes:
    """Remove PKCS#7 padding."""
    if not data:
        return data
    pad_byte = data[-1]
    if pad_byte == 0 or pad_byte > len(data):
        return data
    # Verify all padding bytes match
    for i in range(pad_byte):
        if data[-(i + 1)] != pad_byte:
            return data
    return data[:-pad_byte]


def encode(packet: SimpPacket) -> bytes:
    """
    Encode a SimpPacket to bytes.

    Header (13 bytes):
      version(1) + msg_type(1) + ttl(1) + timestamp(4) + flags(1) + payload_len(4) + reserved(1)

    Followed by sender_id(8) + recipient_id(8) + payload.
    Padded with PKCS#7 to block boundary.
    """
    payload_len = len(packet.payload)
    header = struct.pack(
        ">BBB I B I B",
        packet.version,
        packet.msg_type,
        packet.ttl,
        packet.timestamp & 0xFFFFFFFF,
        packet.flags & 0xFF,
        payload_len & 0xFFFFFFFF,
        0,  # reserved
    )
    assert len(header) == HEADER_SIZE, f"Header size mismatch: {len(header)}"

    body = header + packet.sender_id[:8].ljust(8, b"\x00") + packet.recipient_id[:8].ljust(8, b"\x00") + packet.payload
    block_size = _select_block_size(len(body))
    return _pkcs7_pad(body, block_size)


def decode(data: bytes) -> SimpPacket:
    """
    Decode bytes to a SimpPacket, stripping PKCS#7 padding.
    """
    raw = _pkcs7_unpad(data)
    if len(raw) < HEADER_SIZE + 16:
        raise ValueError(f"Packet too short: {len(raw)} bytes (need at least {HEADER_SIZE + 16})")

    version, msg_type, ttl, timestamp, flags, payload_len, _reserved = struct.unpack(
        ">BBB I B I B", raw[:HEADER_SIZE]
    )

    sender_id = raw[HEADER_SIZE:HEADER_SIZE + 8]
    recipient_id = raw[HEADER_SIZE + 8:HEADER_SIZE + 16]
    payload = raw[HEADER_SIZE + 16:HEADER_SIZE + 16 + payload_len]

    return SimpPacket(
        version=version,
        msg_type=msg_type,
        ttl=ttl,
        timestamp=timestamp,
        flags=flags,
        payload=payload,
        sender_id=sender_id,
        recipient_id=recipient_id,
    )


class IntentBloomFilter:
    """
    Simple Bloom filter for intent deduplication.
    1024-byte bit array with 3 hash functions.
    """

    def __init__(self, size: int = 1024):
        self.size = size
        self.num_bits = size * 8
        self.bit_array = bytearray(size)
        self.count = 0

    def _hashes(self, item: bytes) -> list:
        """Generate 3 hash positions for an item."""
        if isinstance(item, str):
            item = item.encode("utf-8")
        h1 = int(hashlib.md5(item).hexdigest(), 16) % self.num_bits
        h2 = int(hashlib.sha1(item).hexdigest(), 16) % self.num_bits
        h3 = int(hashlib.sha256(item).hexdigest(), 16) % self.num_bits
        return [h1, h2, h3]

    def add(self, item) -> None:
        """Add an item to the Bloom filter."""
        if isinstance(item, str):
            item = item.encode("utf-8")
        for pos in self._hashes(item):
            byte_idx = pos // 8
            bit_idx = pos % 8
            self.bit_array[byte_idx] |= (1 << bit_idx)
        self.count += 1

    def might_contain(self, item) -> bool:
        """Check if an item might be in the filter (may have false positives)."""
        if isinstance(item, str):
            item = item.encode("utf-8")
        for pos in self._hashes(item):
            byte_idx = pos // 8
            bit_idx = pos % 8
            if not (self.bit_array[byte_idx] & (1 << bit_idx)):
                return False
        return True

    def clear(self) -> None:
        """Reset the Bloom filter."""
        self.bit_array = bytearray(self.size)
        self.count = 0
