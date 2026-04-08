"""
SIMP Nostr Transport

Nostr relay transport for SIMP protocol.
Implements NIP-01 compatible events for agent discovery and intent delivery.

IMPORTANT: No external Nostr libraries required - uses only standard library + cryptography.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger("SIMP.Transport.Nostr")

# Nostr event kinds for SIMP
KIND_AGENT_CARD = 30078  # Replaceable: agent identity/capabilities
KIND_INTENT = 4  # Encrypted DM-style: intent delivery
KIND_DISCOVERY = 30023  # Long-form: agent discovery announcement
KIND_ACK = 7  # Reaction: intent acknowledgment

# Default relay list
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]


@dataclass
class NostrEvent:
    """
    NIP-01 compatible Nostr event.

    Fields:
        id: 32-byte hex SHA256 of serialized event
        pubkey: 32-byte hex public key
        created_at: Unix timestamp
        kind: Event kind integer
        tags: List of tag arrays
        content: Event content string
        sig: 64-byte hex Schnorr signature (placeholder for Ed25519)
    """
    id: str = ""
    pubkey: str = ""
    created_at: int = field(default_factory=lambda: int(time.time()))
    kind: int = 1
    tags: List[List[str]] = field(default_factory=list)
    content: str = ""
    sig: str = ""

    def serialize_for_id(self) -> str:
        """
        Serialize event for ID computation per NIP-01:
        [0, pubkey, created_at, kind, tags, content]
        """
        return json.dumps(
            [0, self.pubkey, self.created_at, self.kind, self.tags, self.content],
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def compute_id(self) -> str:
        """Compute the event ID as SHA256 of the serialized form."""
        serialized = self.serialize_for_id()
        self.id = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self.id

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Nostr JSON event format."""
        return {
            "id": self.id,
            "pubkey": self.pubkey,
            "created_at": self.created_at,
            "kind": self.kind,
            "tags": self.tags,
            "content": self.content,
            "sig": self.sig,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NostrEvent":
        """Create from Nostr JSON event dict."""
        return cls(
            id=data.get("id", ""),
            pubkey=data.get("pubkey", ""),
            created_at=data.get("created_at", int(time.time())),
            kind=data.get("kind", 1),
            tags=data.get("tags", []),
            content=data.get("content", ""),
            sig=data.get("sig", ""),
        )


class NostrTransport:
    """
    Nostr transport for SIMP protocol.

    Builds and parses Nostr events for SIMP agent communication.
    Does NOT manage WebSocket connections (that's the transport manager's job).
    """

    def __init__(self, agent_id: str = "", pubkey: str = "", relays: Optional[List[str]] = None):
        self.agent_id = agent_id
        self.pubkey = pubkey or hashlib.sha256(agent_id.encode()).hexdigest()[:64]
        self.relays = relays or list(DEFAULT_RELAYS)

        self.stats = {
            "events_built": 0,
            "events_parsed": 0,
            "intents_sent": 0,
            "intents_received": 0,
        }

    def build_agent_card_event(
        self,
        agent_type: str = "",
        capabilities: Optional[List[str]] = None,
        endpoint: str = "",
    ) -> NostrEvent:
        """
        Build a Nostr event for agent card (identity/capabilities).

        Kind 30078 (replaceable) with SIMP-specific tags.
        """
        content = json.dumps({
            "agent_id": self.agent_id,
            "agent_type": agent_type,
            "capabilities": capabilities or [],
            "endpoint": endpoint,
            "protocol": "simp",
            "version": "1.0",
        })

        tags = [
            ["d", f"simp-agent-{self.agent_id}"],
            ["t", "simp"],
            ["t", "agent-card"],
        ]
        if agent_type:
            tags.append(["t", agent_type])

        event = NostrEvent(
            pubkey=self.pubkey,
            kind=KIND_AGENT_CARD,
            tags=tags,
            content=content,
        )
        event.compute_id()
        self.stats["events_built"] += 1
        return event

    def build_intent_event(
        self,
        intent_dict: Dict[str, Any],
        target_pubkey: str = "",
    ) -> NostrEvent:
        """
        Build a Nostr event carrying a SIMP intent.

        Uses kind 4 (encrypted DM style) with intent as content.
        """
        content = json.dumps(intent_dict, separators=(",", ":"))

        tags = [
            ["t", "simp"],
            ["t", "intent"],
        ]
        if target_pubkey:
            tags.append(["p", target_pubkey])

        intent_type = intent_dict.get("intent", {}).get("type", "")
        if not intent_type:
            intent_type = intent_dict.get("intent_type", "")
        if intent_type:
            tags.append(["t", intent_type])

        event = NostrEvent(
            pubkey=self.pubkey,
            kind=KIND_INTENT,
            tags=tags,
            content=content,
        )
        event.compute_id()
        self.stats["events_built"] += 1
        self.stats["intents_sent"] += 1
        return event

    def build_discovery_event(
        self,
        agent_type: str = "",
        capabilities: Optional[List[str]] = None,
    ) -> NostrEvent:
        """
        Build a discovery announcement event.

        Kind 30023 (long-form) for agent discovery.
        """
        content = json.dumps({
            "agent_id": self.agent_id,
            "agent_type": agent_type,
            "capabilities": capabilities or [],
            "protocol": "simp",
            "timestamp": time.time(),
        })

        tags = [
            ["d", f"simp-discovery-{self.agent_id}"],
            ["t", "simp"],
            ["t", "discovery"],
        ]

        event = NostrEvent(
            pubkey=self.pubkey,
            kind=KIND_DISCOVERY,
            tags=tags,
            content=content,
        )
        event.compute_id()
        self.stats["events_built"] += 1
        return event

    def event_to_intent(self, event: NostrEvent) -> Optional[Dict[str, Any]]:
        """
        Parse a Nostr event into a SIMP intent dict.

        Returns None if the event is not a SIMP intent.
        """
        # Check if this is a SIMP intent event
        is_simp = False
        for tag in event.tags:
            if len(tag) >= 2 and tag[0] == "t" and tag[1] == "simp":
                is_simp = True
                break

        if not is_simp:
            return None

        try:
            intent_dict = json.loads(event.content)
            # Add Nostr metadata
            intent_dict["_nostr_event_id"] = event.id
            intent_dict["_nostr_pubkey"] = event.pubkey
            intent_dict["_nostr_created_at"] = event.created_at
            self.stats["events_parsed"] += 1
            self.stats["intents_received"] += 1
            return intent_dict
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"Failed to parse Nostr event content: {event.id}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """Get Nostr transport status."""
        return {
            "agent_id": self.agent_id,
            "pubkey": self.pubkey,
            "relays": self.relays,
            "stats": dict(self.stats),
        }
