"""
SIMP Transport Manager

Orchestrates multi-transport delivery: HTTP (default) -> BLE -> Nostr fallback chain.
Integrates with the existing SimpBroker for HTTP delivery.
"""

import logging
import time
from typing import Dict, Any, Optional, List

from simp.transport.packet import (
    SimpPacket,
    MessageType,
    agent_id_to_peer_id,
    encode,
    decode,
)
from simp.transport.bridge import (
    intent_to_packet,
    packet_to_intent,
    build_ack_packet,
    build_discovery_packet,
    select_transport,
)
from simp.transport.mesh_relay import MeshRouter, MeshPeer
from simp.transport.ble_transport import BleTransport, is_ble_available
from simp.transport.nostr_transport import NostrTransport

logger = logging.getLogger("SIMP.Transport.Manager")


class TransportManager:
    """
    Manages multi-transport delivery for SIMP protocol.

    Delivery chain: HTTP -> BLE -> Nostr -> HTTP fallback.
    HTTP uses the existing IntentDeliveryEngine (SimpBroker).
    BLE and Nostr are optional additive transports.
    """

    def __init__(
        self,
        agent_id: str = "",
        broker=None,
        enable_ble: bool = True,
        enable_nostr: bool = True,
        nostr_relays: Optional[List[str]] = None,
    ):
        self.agent_id = agent_id
        self.broker = broker  # Existing SimpBroker instance

        # Mesh router
        self.mesh = MeshRouter(local_agent_id=agent_id)

        # BLE transport (optional)
        self.ble: Optional[BleTransport] = None
        if enable_ble:
            self.ble = BleTransport(local_agent_id=agent_id)

        # Nostr transport (optional)
        self.nostr: Optional[NostrTransport] = None
        if enable_nostr:
            self.nostr = NostrTransport(agent_id=agent_id, relays=nostr_relays)

        self.stats = {
            "deliveries_attempted": 0,
            "deliveries_http": 0,
            "deliveries_ble": 0,
            "deliveries_nostr": 0,
            "deliveries_failed": 0,
        }

        logger.info(
            f"TransportManager initialized: agent={agent_id}, "
            f"ble={'active' if self.ble and self.ble.available else 'stub'}, "
            f"nostr={'active' if self.nostr else 'disabled'}"
        )

    def deliver(
        self,
        intent_data: Dict[str, Any],
        target_agent_id: str = "",
        preferred_transport: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deliver an intent using the best available transport.

        Priority: preferred_transport -> HTTP -> BLE -> Nostr -> HTTP fallback

        Returns delivery result dict.
        """
        self.stats["deliveries_attempted"] += 1

        if not target_agent_id:
            target_agent_id = intent_data.get("target_agent", "")

        # Build available transports map
        available = {
            "http": self.broker is not None,
            "ble": self.ble is not None and self.ble.available,
            "nostr": self.nostr is not None,
        }

        # Determine transport to use
        if preferred_transport and available.get(preferred_transport, False):
            transport = preferred_transport
        else:
            peer_hints = {}
            peer = self.mesh.get_peer_by_agent_id(target_agent_id)
            if peer:
                peer_hints[target_agent_id] = peer.transport
            transport = select_transport(target_agent_id, available, peer_hints)

        # Attempt delivery
        if transport == "http":
            return self._deliver_http(intent_data)
        elif transport == "ble":
            result = self._deliver_ble(intent_data, target_agent_id)
            if result.get("status") == "error":
                # Fallback to HTTP
                logger.info("BLE delivery failed, falling back to HTTP")
                return self._deliver_http(intent_data)
            return result
        elif transport == "nostr":
            result = self._deliver_nostr(intent_data, target_agent_id)
            if result.get("status") == "error":
                # Fallback to HTTP
                logger.info("Nostr delivery failed, falling back to HTTP")
                return self._deliver_http(intent_data)
            return result
        else:
            return self._deliver_http(intent_data)

    def _deliver_http(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver via HTTP using existing SimpBroker."""
        if self.broker is None:
            self.stats["deliveries_failed"] += 1
            return {
                "status": "error",
                "transport": "http",
                "error": "No broker configured",
            }

        try:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(self.broker.route_intent(intent_data))
            finally:
                loop.close()

            self.stats["deliveries_http"] += 1
            result["transport"] = "http"
            return result
        except Exception as e:
            self.stats["deliveries_failed"] += 1
            return {
                "status": "error",
                "transport": "http",
                "error": str(e),
            }

    def _deliver_ble(self, intent_data: Dict[str, Any], target_agent_id: str) -> Dict[str, Any]:
        """Deliver via BLE transport."""
        if not self.ble or not self.ble.available:
            self.stats["deliveries_failed"] += 1
            return {
                "status": "error",
                "transport": "ble",
                "error": "BLE transport not available",
            }

        # Build packet
        packet = intent_to_packet(intent_data, self.agent_id, target_agent_id)

        # Look up peer for BLE address
        peer = self.mesh.get_peer_by_agent_id(target_agent_id)
        if not peer or not peer.endpoint:
            self.stats["deliveries_failed"] += 1
            return {
                "status": "error",
                "transport": "ble",
                "error": f"No BLE address for agent {target_agent_id}",
            }

        self.stats["deliveries_ble"] += 1
        return {
            "status": "queued",
            "transport": "ble",
            "target": target_agent_id,
            "device": peer.endpoint,
        }

    def _deliver_nostr(self, intent_data: Dict[str, Any], target_agent_id: str) -> Dict[str, Any]:
        """Deliver via Nostr relay."""
        if not self.nostr:
            self.stats["deliveries_failed"] += 1
            return {
                "status": "error",
                "transport": "nostr",
                "error": "Nostr transport not configured",
            }

        try:
            event = self.nostr.build_intent_event(intent_data)
            self.stats["deliveries_nostr"] += 1
            return {
                "status": "published",
                "transport": "nostr",
                "event_id": event.id,
                "relays": self.nostr.relays,
            }
        except Exception as e:
            self.stats["deliveries_failed"] += 1
            return {
                "status": "error",
                "transport": "nostr",
                "error": str(e),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get status of all transport layers."""
        status = {
            "agent_id": self.agent_id,
            "transports": {
                "http": {
                    "available": self.broker is not None,
                    "status": "active" if self.broker else "unconfigured",
                },
                "ble": self.ble.get_status() if self.ble else {"available": False, "status": "disabled"},
                "nostr": self.nostr.get_status() if self.nostr else {"available": False, "status": "disabled"},
            },
            "mesh": self.mesh.get_relay_stats(),
            "delivery_stats": dict(self.stats),
        }
        return status

    def get_peers(self) -> List[Dict[str, Any]]:
        """Get list of known mesh peers."""
        peers = []
        for p in self.mesh.list_peers():
            peers.append({
                "peer_id": p.peer_id.hex(),
                "agent_id": p.agent_id,
                "transport": p.transport,
                "last_seen": p.last_seen,
                "capabilities": p.capabilities,
                "is_stale": p.is_stale,
                "endpoint": p.endpoint,
            })
        return peers

    def discover(self, agent_type: str = "", capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
        """Broadcast a discovery packet on all available transports."""
        results = {}

        # Build discovery packet
        packet = build_discovery_packet(self.agent_id, agent_type, capabilities)

        # Nostr discovery
        if self.nostr:
            try:
                event = self.nostr.build_discovery_event(agent_type, capabilities)
                results["nostr"] = {
                    "status": "published",
                    "event_id": event.id,
                }
            except Exception as e:
                results["nostr"] = {"status": "error", "error": str(e)}

        # BLE discovery (if available)
        if self.ble and self.ble.available:
            results["ble"] = {"status": "queued"}
        elif self.ble:
            results["ble"] = {"status": "unavailable", "reason": "bleak not installed"}

        results["mesh_packet"] = {
            "msg_type": "DISCOVERY",
            "ttl": packet.ttl,
        }

        return results
