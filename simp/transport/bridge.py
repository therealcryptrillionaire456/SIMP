"""
SIMP Transport Bridge

Converts between SIMP Intent JSON and binary SimpPacket format.
Provides transport selection logic.
"""

import json
import time
import logging
from typing import Dict, Any, Optional

from simp.transport.packet import (
    SimpPacket,
    MessageType,
    PacketFlags,
    agent_id_to_peer_id,
    encode,
    decode,
    PACKET_VERSION,
    DEFAULT_TTL,
)

logger = logging.getLogger("SIMP.Transport.Bridge")


def intent_to_packet(
    intent_dict: Dict[str, Any],
    source_agent_id: str = "",
    target_agent_id: str = "",
    ttl: int = DEFAULT_TTL,
) -> SimpPacket:
    """
    Convert a SIMP intent dict to a binary SimpPacket.

    Args:
        intent_dict: SIMP intent in dict form
        source_agent_id: Source agent identifier
        target_agent_id: Target agent identifier
        ttl: Time-to-live hop count

    Returns:
        SimpPacket ready for encoding
    """
    payload = json.dumps(intent_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")

    flags = PacketFlags.NONE
    sender_id = b"\x00" * 8
    recipient_id = b"\x00" * 8

    if source_agent_id:
        sender_id = agent_id_to_peer_id(source_agent_id)

    if target_agent_id:
        recipient_id = agent_id_to_peer_id(target_agent_id)
        flags |= PacketFlags.HAS_RECIPIENT

    if intent_dict.get("signature"):
        flags |= PacketFlags.HAS_SIGNATURE

    return SimpPacket(
        version=PACKET_VERSION,
        msg_type=MessageType.INTENT,
        ttl=ttl,
        timestamp=int(time.time()),
        flags=flags,
        payload=payload,
        sender_id=sender_id,
        recipient_id=recipient_id,
    )


def packet_to_intent(packet: SimpPacket) -> Dict[str, Any]:
    """
    Convert a SimpPacket back to a SIMP intent dict.

    Args:
        packet: Decoded SimpPacket

    Returns:
        Intent dict parsed from packet payload
    """
    return json.loads(packet.payload.decode("utf-8"))


def build_ack_packet(
    intent_id: str,
    responder_agent_id: str = "",
    status: str = "received",
) -> SimpPacket:
    """
    Build an ACK packet for a received intent.

    Args:
        intent_id: ID of the intent being acknowledged
        responder_agent_id: Agent sending the ACK
        status: ACK status string

    Returns:
        SimpPacket with ACK payload
    """
    payload = json.dumps({
        "intent_id": intent_id,
        "status": status,
        "timestamp": time.time(),
    }, separators=(",", ":")).encode("utf-8")

    sender_id = b"\x00" * 8
    if responder_agent_id:
        sender_id = agent_id_to_peer_id(responder_agent_id)

    return SimpPacket(
        version=PACKET_VERSION,
        msg_type=MessageType.ACK,
        ttl=1,
        timestamp=int(time.time()),
        flags=PacketFlags.NONE,
        payload=payload,
        sender_id=sender_id,
    )


def build_discovery_packet(
    agent_id: str,
    agent_type: str = "",
    capabilities: Optional[list] = None,
) -> SimpPacket:
    """
    Build a discovery/announcement packet.

    Args:
        agent_id: Agent announcing itself
        agent_type: Type of agent
        capabilities: List of capabilities

    Returns:
        SimpPacket for broadcasting
    """
    payload = json.dumps({
        "agent_id": agent_id,
        "agent_type": agent_type,
        "capabilities": capabilities or [],
        "timestamp": time.time(),
    }, separators=(",", ":")).encode("utf-8")

    return SimpPacket(
        version=PACKET_VERSION,
        msg_type=MessageType.DISCOVERY,
        ttl=DEFAULT_TTL,
        timestamp=int(time.time()),
        flags=PacketFlags.NONE,
        payload=payload,
        sender_id=agent_id_to_peer_id(agent_id),
    )


def select_transport(
    target_agent_id: str,
    available_transports: Optional[Dict[str, bool]] = None,
    peer_transport_hints: Optional[Dict[str, str]] = None,
) -> str:
    """
    Select the best transport for delivering to a target agent.

    Priority: HTTP -> BLE -> Nostr -> HTTP fallback

    Args:
        target_agent_id: Target agent to deliver to
        available_transports: Dict of transport_name -> is_available
        peer_transport_hints: Dict of agent_id -> preferred_transport

    Returns:
        Transport name string: "http", "ble", or "nostr"
    """
    if available_transports is None:
        available_transports = {"http": True, "ble": False, "nostr": False}

    if peer_transport_hints is None:
        peer_transport_hints = {}

    # Check if we have a hint for this specific peer
    hint = peer_transport_hints.get(target_agent_id)
    if hint and available_transports.get(hint, False):
        return hint

    # Default priority chain: HTTP -> BLE -> Nostr -> HTTP fallback
    if available_transports.get("http", False):
        return "http"

    if available_transports.get("ble", False):
        return "ble"

    if available_transports.get("nostr", False):
        return "nostr"

    # Fallback to HTTP even if not explicitly available
    return "http"
