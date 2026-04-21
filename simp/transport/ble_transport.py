"""
SIMP BLE Transport

Bluetooth Low Energy transport for SIMP mesh networking.
Uses the bleak library for BLE scanning and GATT communication.

IMPORTANT: bleak is OPTIONAL. All code works without it installed.
When bleak is not available, operations return graceful stubs with warnings.
"""

import logging
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from simp.transport.packet import (
    SimpPacket,
    encode,
    decode,
    agent_id_to_peer_id,
    PACKET_VERSION,
    MessageType,
    PacketFlags,
    DEFAULT_TTL,
)

logger = logging.getLogger("SIMP.Transport.BLE")

# BLE service and characteristic UUIDs for SIMP
SIMP_SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
SIMP_CHAR_UUID = "12345678-1234-5678-1234-56789abcdef1"

# BLE MTU limit (typical)
BLE_MTU = 512
# Fragment overhead: 1 byte sequence + 1 byte total_fragments
FRAGMENT_OVERHEAD = 2
MAX_FRAGMENT_PAYLOAD = BLE_MTU - FRAGMENT_OVERHEAD

# Try to import bleak
_bleak_available = False
try:
    import bleak
    _bleak_available = True
except ImportError:
    pass


def is_ble_available() -> bool:
    """Check if BLE support is available (bleak installed)."""
    return _bleak_available


@dataclass
class BleDevice:
    """A discovered BLE device running SIMP."""
    address: str = ""
    name: str = ""
    rssi: int = 0
    peer_id: bytes = b"\x00" * 8
    agent_id: str = ""
    last_seen: float = 0.0


class BleTransport:
    """
    BLE transport for SIMP protocol.

    Handles BLE scanning, packet fragmentation/reassembly, and delivery.
    All operations gracefully degrade when bleak is not installed.
    """

    def __init__(self, local_agent_id: str = ""):
        self.local_agent_id = local_agent_id
        self.local_peer_id = agent_id_to_peer_id(local_agent_id) if local_agent_id else b"\x00" * 8
        self.discovered_devices: Dict[str, BleDevice] = {}
        self._fragment_buffers: Dict[str, List[Optional[bytes]]] = {}

        self.stats = {
            "scans_completed": 0,
            "packets_sent": 0,
            "packets_received": 0,
            "fragments_sent": 0,
            "fragments_received": 0,
            "devices_discovered": 0,
        }

        if not _bleak_available:
            warnings.warn(
                "bleak is not installed. BLE transport will operate in stub mode. "
                "Install bleak for BLE support: pip install bleak",
                stacklevel=2,
            )

    @property
    def available(self) -> bool:
        return _bleak_available

    async def scan_for_peers(self, timeout: float = 5.0) -> List[BleDevice]:
        """
        Scan for nearby SIMP BLE peers.

        Returns list of discovered BLE devices.
        When bleak is not installed, returns empty list with warning.
        """
        if not _bleak_available:
            logger.warning("BLE scan requested but bleak is not installed")
            return []

        try:
            scanner = bleak.BleakScanner()
            devices = await scanner.discover(timeout=timeout)
            result = []
            for d in devices:
                dev = BleDevice(
                    address=d.address,
                    name=d.name or "",
                    rssi=d.rssi if hasattr(d, 'rssi') else 0,
                )
                self.discovered_devices[d.address] = dev
                result.append(dev)
            self.stats["scans_completed"] += 1
            self.stats["devices_discovered"] = len(self.discovered_devices)
            return result
        except Exception as e:
            logger.error(f"BLE scan failed: {e}")
            return []

    async def send_packet(self, packet: SimpPacket, device_address: str) -> bool:
        """
        Send a packet to a BLE device.

        Fragments the packet if needed, sends via GATT write.
        Returns False with warning when bleak is not installed.
        """
        if not _bleak_available:
            logger.warning("BLE send requested but bleak is not installed")
            return False

        encoded = encode(packet)
        fragments = self._fragment(encoded)

        try:
            async with bleak.BleakClient(device_address) as client:
                for frag in fragments:
                    await client.write_gatt_char(SIMP_CHAR_UUID, frag)
                    self.stats["fragments_sent"] += 1
            self.stats["packets_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"BLE send failed: {e}")
            return False

    def _fragment(self, data: bytes) -> List[bytes]:
        """
        Fragment data into BLE-MTU-sized chunks.

        Each fragment: [sequence_number(1)] [total_fragments(1)] [payload]
        """
        if len(data) <= MAX_FRAGMENT_PAYLOAD:
            return [bytes([0, 1]) + data]

        fragments = []
        offset = 0
        total = (len(data) + MAX_FRAGMENT_PAYLOAD - 1) // MAX_FRAGMENT_PAYLOAD
        seq = 0
        while offset < len(data):
            chunk = data[offset:offset + MAX_FRAGMENT_PAYLOAD]
            fragments.append(bytes([seq, total]) + chunk)
            offset += MAX_FRAGMENT_PAYLOAD
            seq += 1
        return fragments

    def _reassemble(self, fragments: List[bytes]) -> Optional[bytes]:
        """
        Reassemble fragments into a complete packet.

        Each fragment: [sequence_number(1)] [total_fragments(1)] [payload]
        Returns None if fragments are incomplete.
        """
        if not fragments:
            return None

        # Parse first fragment to get total
        total = fragments[0][1]
        if len(fragments) < total:
            return None

        # Sort by sequence number
        sorted_frags = sorted(fragments, key=lambda f: f[0])
        data = b""
        for frag in sorted_frags:
            data += frag[FRAGMENT_OVERHEAD:]
        return data

    def receive_fragment(self, source_address: str, fragment: bytes) -> Optional[SimpPacket]:
        """
        Process an incoming BLE fragment.

        Returns a complete SimpPacket when all fragments are received,
        None otherwise.
        """
        self.stats["fragments_received"] += 1

        if len(fragment) < FRAGMENT_OVERHEAD:
            return None

        seq = fragment[0]
        total = fragment[1]

        if source_address not in self._fragment_buffers:
            self._fragment_buffers[source_address] = [None] * total

        buf = self._fragment_buffers[source_address]
        if seq < len(buf):
            buf[seq] = fragment

        # Check if complete
        if all(f is not None for f in buf):
            data = self._reassemble(buf)
            del self._fragment_buffers[source_address]
            if data:
                self.stats["packets_received"] += 1
                return decode(data)
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get BLE transport status."""
        return {
            "available": _bleak_available,
            "mode": "active" if _bleak_available else "stub",
            "devices_discovered": len(self.discovered_devices),
            "pending_reassembly": len(self._fragment_buffers),
            "stats": dict(self.stats),
        }
