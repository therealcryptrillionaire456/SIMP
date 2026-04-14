"""
SIMP Agent Mesh Bus Module

Provides store-and-forward messaging for agent-to-agent communication.
"""

from .packet import (
    MeshPacket,
    MessageType,
    Priority,
    create_event_packet,
    create_system_packet,
    create_heartbeat_packet,
)
from .bus import MeshBus, get_mesh_bus

__all__ = [
    "MeshPacket",
    "MessageType",
    "Priority",
    "create_event_packet",
    "create_system_packet",
    "create_heartbeat_packet",
    "MeshBus",
    "get_mesh_bus",
]

__version__ = "0.1.0"