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
from .bus import MeshBus
from .commitment_market import CommitmentMarket, Commitment, Settlement, get_commitment_market
from .enhanced_bus import (
    EnhancedMeshBus,
    get_enhanced_mesh_bus,
    OfflineMessageStore,
    BloomFilter,
    DeliveryReceipt,
    DeliveryReceiptManager,
    PaymentChannel,
    PaymentSettler,
    GossipRouter,
    ChannelState,
    MessageStatus,
)

# Alias: anything that calls get_mesh_bus() transparently gets the enhanced bus
get_mesh_bus = get_enhanced_mesh_bus

__all__ = [
    "MeshPacket",
    "MessageType",
    "Priority",
    "create_event_packet",
    "create_system_packet",
    "create_heartbeat_packet",
    "MeshBus",
    "CommitmentMarket",
    "Commitment",
    "Settlement",
    "get_commitment_market",
    "EnhancedMeshBus",
    "get_mesh_bus",
    "get_enhanced_mesh_bus",
    "OfflineMessageStore",
    "BloomFilter",
    "DeliveryReceipt",
    "DeliveryReceiptManager",
    "PaymentChannel",
    "PaymentSettler",
    "GossipRouter",
    "ChannelState",
    "MessageStatus",
]

__version__ = "0.2.0"
