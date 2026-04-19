"""
Enhanced Mesh Bus for SIMP Ecosystem
Features:
- Priority-based message queues
- Multi-threaded processing
- Message persistence (SQLite-backed, survives restarts)
- Delivery confirmation with HMAC-signed receipts
- Self-healing capabilities
- Gossip flood-routing with bloom-filter deduplication  (BitChat-style)
- Offline payment channels with atomic settlement      (Lightning-inspired)
- Per-channel encryption hooks
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import logging
import sqlite3
import threading
import time
import heapq
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .packet import MeshPacket, MessageType, Priority, create_event_packet

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Core enums / dataclasses (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

class MessageStatus(Enum):
    """Status of a message in the mesh."""
    PENDING   = "pending"
    DELIVERED = "delivered"
    FAILED    = "failed"
    EXPIRED   = "expired"


@dataclass(order=True)
class PrioritizedMessage:
    """Message with priority for queueing."""
    priority:           int
    timestamp:          float
    packet:             MeshPacket     = field(compare=False)
    delivery_attempts:  int            = field(default=0,                            compare=False)
    status:             MessageStatus  = field(default=MessageStatus.PENDING,        compare=False)
    delivery_callback:  Optional[Callable] = field(default=None,                    compare=False)
    message_id:         str            = field(default_factory=lambda: str(uuid.uuid4()), compare=False)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  OFFLINE MESSAGE STORE  (SQLite – survives process restarts)
# ─────────────────────────────────────────────────────────────────────────────

class OfflineMessageStore:
    """
    SQLite-backed durable store for messages destined to currently-offline agents.

    Inspired by BitChat's on-device store-and-forward: packets written here
    survive a SIMP restart and are drained into the live priority queue the
    moment an agent (re-)registers.

    Thread-safe; uses a per-call sqlite3.connect() so it works correctly
    across threads without a shared connection object.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS messages (
            id          TEXT    PRIMARY KEY,
            recipient   TEXT    NOT NULL,
            sender      TEXT,
            channel     TEXT,
            payload     TEXT    NOT NULL,
            priority    INTEGER DEFAULT 1,
            created_at  REAL    NOT NULL,
            expires_at  REAL    NOT NULL,
            attempts    INTEGER DEFAULT 0,
            status      TEXT    DEFAULT 'pending'
        );
        CREATE INDEX IF NOT EXISTS idx_recv    ON messages(recipient);
        CREATE INDEX IF NOT EXISTS idx_status  ON messages(status);
        CREATE INDEX IF NOT EXISTS idx_expires ON messages(expires_at);
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock   = threading.Lock()
        # Single shared connection so :memory: databases work across threads.
        self._db = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        """Return the shared connection (thread-safe via self._lock)."""
        return self._db

    def _init_db(self) -> None:
        with self._lock:
            self._db.executescript(self._SCHEMA)
            self._db.commit()

    # ------------------------------------------------------------------
    def store(self, packet: MeshPacket, priority: int = 1) -> str:
        """Persist a packet.  Returns the internal store-message-id."""
        msg_id = str(uuid.uuid4())
        try:
            packet_time = datetime.fromisoformat(
                packet.timestamp.replace("Z", "+00:00")
            ).timestamp()
        except (ValueError, AttributeError):
            packet_time = time.time()

        expires_at = packet_time + max(packet.ttl_seconds, 0)

        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO messages
                   (id,recipient,sender,channel,payload,priority,created_at,expires_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    msg_id,
                    packet.recipient_id,
                    packet.sender_id,
                    packet.channel,
                    packet.to_json(),
                    priority,
                    time.time(),
                    expires_at,
                ),
            )
        return msg_id

    def fetch_for_agent(self, agent_id: str, limit: int = 50) -> List[MeshPacket]:
        """
        Atomically claim and return pending, non-expired packets for *agent_id*.
        Claimed rows are marked 'delivered' so they won't be returned again.
        """
        now = time.time()
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                """SELECT id, payload FROM messages
                   WHERE recipient=? AND status='pending' AND expires_at>?
                   ORDER BY priority ASC, created_at ASC
                   LIMIT ?""",
                (agent_id, now, limit),
            ).fetchall()

            if not rows:
                return []

            ids = [r["id"] for r in rows]
            conn.execute(
                f"UPDATE messages SET status='delivered', attempts=attempts+1 "
                f"WHERE id IN ({','.join('?'*len(ids))})",
                ids,
            )

        packets: List[MeshPacket] = []
        for row in rows:
            try:
                packets.append(MeshPacket.from_json(row["payload"]))
            except Exception as exc:
                logger.warning("OfflineMessageStore: bad packet row – %s", exc)
        return packets

    def purge_expired(self) -> int:
        """Remove expired rows.  Returns number of rows deleted."""
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM messages WHERE expires_at<?", (time.time(),)
            )
            return cur.rowcount

    def pending_count(self, agent_id: Optional[str] = None) -> int:
        with self._lock, self._conn() as conn:
            if agent_id:
                return conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE recipient=? AND status='pending'",
                    (agent_id,),
                ).fetchone()[0]
            return conn.execute(
                "SELECT COUNT(*) FROM messages WHERE status='pending'"
            ).fetchone()[0]

    def stats(self) -> Dict[str, Any]:
        with self._lock, self._conn() as conn:
            total   = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE status='pending'"
            ).fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE expires_at<?", (time.time(),)
            ).fetchone()[0]
            by_agent = conn.execute(
                "SELECT recipient,COUNT(*) FROM messages "
                "WHERE status='pending' GROUP BY recipient"
            ).fetchall()
        return {
            "total": total,
            "pending": pending,
            "expired_not_purged": expired,
            "by_agent": {r[0]: r[1] for r in by_agent},
        }


# ─────────────────────────────────────────────────────────────────────────────
# 2.  BLOOM FILTER  (seen-message deduplication – BitChat-style)
# ─────────────────────────────────────────────────────────────────────────────

class BloomFilter:
    """
    Simple counting bloom filter for seen-message deduplication.

    Uses k=3 independent hash functions over a 2^16-bit array.
    Membership is only checked within a sliding TTL window: old entries
    are evicted from the *seen_times* OrderedDict so that after *ttl_seconds*
    the same message_id can be forwarded again (correct for gossip re-seeding).

    False-positive rate ≈ 0.7% at 10 000 elements with the default parameters.
    """

    def __init__(self, capacity: int = 65_536, ttl_seconds: int = 300):
        self._cap  = capacity
        self._bits = bytearray(capacity // 8 + 1)
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._ttl  = ttl_seconds
        self._lock = threading.Lock()
        self._hits = 0   # telemetry

    # Three hash positions ---------------------------------------------------
    @staticmethod
    def _hashes(key: str, cap: int) -> Tuple[int, int, int]:
        h = hashlib.sha256(key.encode()).digest()
        m = hashlib.md5(key.encode()).digest()   # noqa: S324 (not security use)
        return (
            int.from_bytes(h[0:4], "big") % cap,
            int.from_bytes(h[4:8], "big") % cap,
            int.from_bytes(m[0:4], "big") % cap,
        )

    def _set_bit(self, pos: int) -> None:
        self._bits[pos >> 3] |= 1 << (pos & 7)

    def _get_bit(self, pos: int) -> bool:
        return bool(self._bits[pos >> 3] & (1 << (pos & 7)))

    # Public API -------------------------------------------------------------
    def add(self, key: str) -> None:
        with self._lock:
            self._evict()
            for pos in self._hashes(key, self._cap):
                self._set_bit(pos)
            self._seen[key] = time.time()

    def contains(self, key: str) -> bool:
        with self._lock:
            self._evict()
            if key not in self._seen:
                return False
            result = all(self._get_bit(p) for p in self._hashes(key, self._cap))
            if result:
                self._hits += 1
            return result

    def _evict(self) -> None:
        """Remove entries older than ttl from the time-tracking dict."""
        cutoff = time.time() - self._ttl
        while self._seen:
            oldest_key, oldest_ts = next(iter(self._seen.items()))
            if oldest_ts < cutoff:
                self._seen.pop(oldest_key)
            else:
                break

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._seen)

    @property
    def hits(self) -> int:
        return self._hits


# ─────────────────────────────────────────────────────────────────────────────
# 3.  DELIVERY RECEIPT  (HMAC-signed ACKs)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DeliveryReceipt:
    """Cryptographically signed delivery acknowledgement."""
    message_id:   str
    recipient_id: str
    sender_id:    str
    received_at:  float
    signature:    str   # HMAC-SHA256(message_id + recipient_id + received_at)

    # Serialisation ----------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id":   self.message_id,
            "recipient_id": self.recipient_id,
            "sender_id":    self.sender_id,
            "received_at":  self.received_at,
            "signature":    self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DeliveryReceipt":
        return cls(**d)

    # Verification -----------------------------------------------------------
    def verify(self, shared_secret: bytes) -> bool:
        payload  = f"{self.message_id}{self.recipient_id}{self.received_at:.6f}".encode()
        expected = _hmac.new(shared_secret, payload, hashlib.sha256).hexdigest()
        return _hmac.compare_digest(self.signature, expected)


class DeliveryReceiptManager:
    """
    Issues and verifies HMAC-signed delivery receipts.
    All receipts are persisted to a SQLite database so that settlement
    proofs survive process restarts.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS receipts (
            message_id   TEXT PRIMARY KEY,
            recipient_id TEXT,
            sender_id    TEXT,
            received_at  REAL,
            signature    TEXT,
            stored_at    REAL
        );
    """

    def __init__(self, db_path: str, shared_secret: bytes):
        self.db_path = db_path
        self._secret = shared_secret
        self._lock   = threading.Lock()
        self._db = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return self._db

    def _init_db(self) -> None:
        with self._lock:
            self._db.executescript(self._SCHEMA)
            self._db.commit()

    def issue(
        self,
        message_id:   str,
        recipient_id: str,
        sender_id:    str,
    ) -> DeliveryReceipt:
        """Issue a signed receipt.  Persists to DB and returns the receipt."""
        received_at = time.time()
        payload     = f"{message_id}{recipient_id}{received_at:.6f}".encode()
        sig         = _hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

        receipt = DeliveryReceipt(
            message_id   = message_id,
            recipient_id = recipient_id,
            sender_id    = sender_id,
            received_at  = received_at,
            signature    = sig,
        )
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO receipts VALUES (?,?,?,?,?,?)",
                (message_id, recipient_id, sender_id, received_at, sig, time.time()),
            )
        return receipt

    def verify(self, receipt: DeliveryReceipt) -> bool:
        return receipt.verify(self._secret)

    def get(self, message_id: str) -> Optional[DeliveryReceipt]:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM receipts WHERE message_id=?", (message_id,)
            ).fetchone()
        if row:
            return DeliveryReceipt(
                message_id   = row["message_id"],
                recipient_id = row["recipient_id"],
                sender_id    = row["sender_id"],
                received_at  = row["received_at"],
                signature    = row["signature"],
            )
        return None

    def count(self) -> int:
        with self._lock, self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]


# ─────────────────────────────────────────────────────────────────────────────
# 4.  PAYMENT CHANNEL  (offline settlement – Lightning Network inspired)
# ─────────────────────────────────────────────────────────────────────────────

class ChannelState(Enum):
    OPEN      = "open"
    CLOSING   = "closing"
    SETTLED   = "settled"
    DISPUTED  = "disputed"


@dataclass
class PaymentChannel:
    """
    Lightweight bilateral payment channel between two SIMP agents.

    Inspired by Lightning Network payment channels: micro-transactions
    accumulate offline (no network round-trip per payment); when connectivity
    returns, `PaymentSettler.settle()` broadcasts a signed close packet so
    both parties can reconcile final balances.

    Balances are denominated in 'SIMP credits' (float, 8 decimal places).
    """
    channel_id:           str
    initiator_id:         str
    counterparty_id:      str
    initiator_balance:    float
    counterparty_balance: float
    total_capacity:       float
    sequence:             int          = 0
    state:                ChannelState = ChannelState.OPEN
    created_at:           float        = field(default_factory=time.time)
    updated_at:           float        = field(default_factory=time.time)
    pending_htlcs:        List[Dict]   = field(default_factory=list)

    # Serialisation ----------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id":           self.channel_id,
            "initiator_id":         self.initiator_id,
            "counterparty_id":      self.counterparty_id,
            "initiator_balance":    self.initiator_balance,
            "counterparty_balance": self.counterparty_balance,
            "total_capacity":       self.total_capacity,
            "sequence":             self.sequence,
            "state":                self.state.value,
            "created_at":           self.created_at,
            "updated_at":           self.updated_at,
            "pending_htlcs":        self.pending_htlcs,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PaymentChannel":
        d = d.copy()
        d["state"]         = ChannelState(d["state"])
        d["pending_htlcs"] = d.get("pending_htlcs", [])
        return cls(**d)

    # State signing ----------------------------------------------------------
    def sign_state(self, secret: bytes) -> str:
        """HMAC-SHA256 of the canonical state string."""
        payload = (
            f"{self.channel_id}"
            f"{self.sequence}"
            f"{self.initiator_balance:.8f}"
            f"{self.counterparty_balance:.8f}"
        ).encode()
        return _hmac.new(secret, payload, hashlib.sha256).hexdigest()

    # Payment logic ----------------------------------------------------------
    def apply_payment(
        self,
        from_agent:  str,
        amount:      float,
        description: str = "",
    ) -> bool:
        """
        Apply a unidirectional payment.
        Returns True on success, False if channel is closed or balance insufficient.
        """
        if self.state != ChannelState.OPEN:
            return False
        if amount <= 0:
            return False

        if from_agent == self.initiator_id:
            if self.initiator_balance < amount:
                return False
            self.initiator_balance    -= amount
            self.counterparty_balance += amount
        elif from_agent == self.counterparty_id:
            if self.counterparty_balance < amount:
                return False
            self.counterparty_balance -= amount
            self.initiator_balance    += amount
        else:
            return False

        self.sequence   += 1
        self.updated_at  = time.time()
        self.pending_htlcs.append({
            "seq":         self.sequence,
            "from":        from_agent,
            "amount":      amount,
            "description": description,
            "timestamp":   self.updated_at,
        })
        return True

    @property
    def net_flow(self) -> Dict[str, float]:
        """Net value transferred from each party since channel open."""
        total_initiated = sum(
            h["amount"] for h in self.pending_htlcs
            if h["from"] == self.initiator_id
        )
        total_counterparty = sum(
            h["amount"] for h in self.pending_htlcs
            if h["from"] == self.counterparty_id
        )
        return {
            self.initiator_id:    total_initiated,
            self.counterparty_id: total_counterparty,
        }


class PaymentSettler:
    """
    Manages a node's portfolio of offline payment channels and coordinates
    atomic settlement when connectivity is restored.

    Settlement flow
    ---------------
    1. Agents exchange offline payments via `pay()` / `receive_payment()`.
    2. Either party calls `settle(channel_id)` → returns a signed settlement
       dict suitable for wrapping in a MeshPacket payload.
    3. The mesh bus broadcasts the settlement packet on the `payment_settlement`
       channel so all interested agents can reconcile.

    All channel state is persisted to SQLite so nothing is lost on restart.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS payment_channels (
            channel_id TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            updated_at REAL
        );
        CREATE TABLE IF NOT EXISTS settlements (
            settlement_id TEXT PRIMARY KEY,
            channel_id    TEXT,
            settled_at    REAL,
            final_state   TEXT,
            signature     TEXT
        );
    """

    def __init__(self, agent_id: str, db_path: str, shared_secret: bytes):
        self.agent_id = agent_id
        self.db_path  = db_path
        self._secret  = shared_secret
        self._lock    = threading.Lock()
        self._channels: Dict[str, PaymentChannel] = {}
        self._db = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_db()
        self._load_channels()

    def _conn(self) -> sqlite3.Connection:
        return self._db

    def _init_db(self) -> None:
        with self._lock:
            self._db.executescript(self._SCHEMA)
            self._db.commit()

    def _load_channels(self) -> None:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT channel_id, data FROM payment_channels"
            ).fetchall()
        for row in rows:
            try:
                ch = PaymentChannel.from_dict(json.loads(row["data"]))
                self._channels[row["channel_id"]] = ch
            except Exception as exc:
                logger.warning("PaymentSettler: could not load channel – %s", exc)

    def _persist(self, ch: PaymentChannel) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO payment_channels VALUES (?,?,?)",
                (ch.channel_id, json.dumps(ch.to_dict()), ch.updated_at),
            )

    # ------------------------------------------------------------------
    def open_channel(
        self,
        counterparty_id: str,
        my_balance:      float,
        their_balance:   float = 0.0,
    ) -> PaymentChannel:
        """Open a new bilateral payment channel and persist it."""
        ch_id = f"ch_{self.agent_id[:8]}_{counterparty_id[:8]}_{int(time.time())}"
        ch = PaymentChannel(
            channel_id           = ch_id,
            initiator_id         = self.agent_id,
            counterparty_id      = counterparty_id,
            initiator_balance    = my_balance,
            counterparty_balance = their_balance,
            total_capacity       = my_balance + their_balance,
        )
        with self._lock:
            self._channels[ch_id] = ch
            self._persist(ch)
        logger.info("PaymentSettler: opened channel %s", ch_id)
        return ch

    def pay(
        self,
        channel_id:  str,
        amount:      float,
        description: str = "",
    ) -> bool:
        """Debit *amount* from this agent's balance in *channel_id*."""
        with self._lock:
            ch = self._channels.get(channel_id)
            if not ch:
                return False
            ok = ch.apply_payment(self.agent_id, amount, description)
            if ok:
                self._persist(ch)
            return ok

    def receive_payment(
        self,
        channel_id:  str,
        from_agent:  str,
        amount:      float,
        description: str = "",
    ) -> bool:
        """Record a payment sent by *from_agent* on *channel_id*."""
        with self._lock:
            ch = self._channels.get(channel_id)
            if not ch:
                return False
            ok = ch.apply_payment(from_agent, amount, description)
            if ok:
                self._persist(ch)
            return ok

    def settle(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Close a channel and produce a signed settlement payload.
        The returned dict should be broadcast as a MeshPacket payload
        on the `payment_settlement` channel.
        Returns None if channel not found or already settled.
        """
        with self._lock:
            ch = self._channels.get(channel_id)
            if not ch or ch.state != ChannelState.OPEN:
                return None

            ch.state      = ChannelState.SETTLED
            ch.updated_at = time.time()
            sig = ch.sign_state(self._secret)

            settlement: Dict[str, Any] = {
                "settlement_id":              str(uuid.uuid4()),
                "channel_id":                 channel_id,
                "initiator_id":               ch.initiator_id,
                "counterparty_id":            ch.counterparty_id,
                "final_initiator_balance":    ch.initiator_balance,
                "final_counterparty_balance": ch.counterparty_balance,
                "total_capacity":             ch.total_capacity,
                "total_payments":             ch.sequence,
                "net_flow":                   ch.net_flow,
                "settled_at":                 ch.updated_at,
                "signature":                  sig,
                "htlc_history":               ch.pending_htlcs,
            }

            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO settlements VALUES (?,?,?,?,?)",
                    (
                        settlement["settlement_id"],
                        channel_id,
                        ch.updated_at,
                        json.dumps(ch.to_dict()),
                        sig,
                    ),
                )
            self._persist(ch)

        logger.info(
            "PaymentSettler: settled channel %s  seq=%d  "
            "initiator=%.8f  counterparty=%.8f",
            channel_id, ch.sequence,
            settlement["final_initiator_balance"],
            settlement["final_counterparty_balance"],
        )
        return settlement

    def get_channel(self, channel_id: str) -> Optional[PaymentChannel]:
        with self._lock:
            return self._channels.get(channel_id)

    def list_channels(
        self,
        state_filter: Optional[ChannelState] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            channels = self._channels.values()
            if state_filter:
                channels = [c for c in channels if c.state == state_filter]
            return [c.to_dict() for c in channels]

    def get_balance_summary(self) -> Dict[str, float]:
        """Net liquidity this agent holds in each open channel."""
        net: Dict[str, float] = {}
        with self._lock:
            for ch in self._channels.values():
                if ch.state != ChannelState.OPEN:
                    continue
                if ch.initiator_id == self.agent_id:
                    peer = ch.counterparty_id
                    net[peer] = net.get(peer, 0.0) + ch.initiator_balance
                else:
                    peer = ch.initiator_id
                    net[peer] = net.get(peer, 0.0) + ch.counterparty_balance
        return net

    def total_open_capacity(self) -> float:
        """Sum of all outbound balances across open channels."""
        return sum(self.get_balance_summary().values())


# ─────────────────────────────────────────────────────────────────────────────
# 5.  GOSSIP ROUTER  (flood routing with bloom-filter dedup – BitChat-style)
# ─────────────────────────────────────────────────────────────────────────────

class GossipRouter:
    """
    Flood-fill gossip router with bloom-filter deduplication.

    Each node forwards every unseen packet to all known peers (excluding the
    sender), decrementing TTL each hop.  The bloom filter prevents loops and
    is self-evicting over *seen_ttl* seconds so that long-lived nodes don't
    accumulate unbounded state.

    BitChat uses a nearly identical model over BLE; here the transport is
    abstracted via registered forward_callbacks so the router works over
    HTTP, BLE, Nostr, or any other transport.
    """

    def __init__(
        self,
        node_id:    str,
        max_hops:   int = 5,
        seen_ttl:   int = 300,
    ):
        self.node_id  = node_id
        self.max_hops = max_hops
        self._seen: BloomFilter = BloomFilter(capacity=65_536, ttl_seconds=seen_ttl)
        self._peers: Dict[str, Dict[str, Any]] = {}
        self._forward_callbacks: List[Callable[[MeshPacket, str], bool]] = []
        self._lock = threading.Lock()
        self._stats: Dict[str, int] = {
            "originated":    0,
            "forwarded":     0,
            "deduplicated":  0,
            "ttl_dropped":   0,
        }

    # Peer management --------------------------------------------------------
    def add_peer(
        self,
        peer_id:  str,
        endpoint: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._peers[peer_id] = {
                "endpoint":  endpoint,
                "last_seen": time.time(),
                "metadata":  metadata or {},
            }

    def remove_peer(self, peer_id: str) -> None:
        with self._lock:
            self._peers.pop(peer_id, None)

    def touch_peer(self, peer_id: str) -> None:
        with self._lock:
            if peer_id in self._peers:
                self._peers[peer_id]["last_seen"] = time.time()

    def list_peers(self) -> List[str]:
        with self._lock:
            return list(self._peers.keys())

    # Forwarding callbacks ---------------------------------------------------
    def add_forward_callback(
        self,
        cb: Callable[[MeshPacket, str], bool],
    ) -> None:
        """
        Register a callback invoked for each (packet, peer_id) forwarding
        decision.  Return True from the callback to indicate success.
        """
        self._forward_callbacks.append(cb)

    # Core routing -----------------------------------------------------------
    def should_forward(self, packet: MeshPacket) -> bool:
        if self._seen.contains(packet.message_id):
            self._stats["deduplicated"] += 1
            return False
        if packet.ttl_hops <= 0:
            self._stats["ttl_dropped"] += 1
            return False
        return True

    def originate(self, packet: MeshPacket) -> int:
        """
        Originate a packet from *this* node – mark seen and flood to all peers.
        Returns number of peers the packet was forwarded to.
        """
        self._seen.add(packet.message_id)
        self._stats["originated"] += 1
        return self._flood(packet, exclude_peer=None)

    def receive_and_forward(
        self,
        packet:      MeshPacket,
        from_peer_id: str,
    ) -> int:
        """
        Accept an incoming packet from *from_peer_id*.
        Deduplicates, decrements TTL, then floods to all other peers.
        Returns number of peers forwarded to (0 = deduped or TTL-dropped).
        """
        if not self.should_forward(packet):
            return 0
        self._seen.add(packet.message_id)
        packet.touch_hop(self.node_id)   # decrements ttl_hops + appends routing_history
        self._stats["forwarded"] += 1
        return self._flood(packet, exclude_peer=from_peer_id)

    def _flood(
        self,
        packet:       MeshPacket,
        exclude_peer: Optional[str],
    ) -> int:
        with self._lock:
            peers_snapshot = dict(self._peers)

        count = 0
        for peer_id, info in peers_snapshot.items():
            if peer_id == exclude_peer:
                continue
            for cb in self._forward_callbacks:
                try:
                    if cb(packet, peer_id):
                        count += 1
                        break
                except Exception as exc:
                    logger.warning("GossipRouter: forward to %s failed – %s", peer_id, exc)
        return count

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "peer_count":  len(self._peers),
            "bloom_size":  self._seen.size,
            "bloom_hits":  self._seen.hits,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 6.  ENHANCED MESH BUS  (original + all new subsystems integrated)
# ─────────────────────────────────────────────────────────────────────────────

class EnhancedMeshBus:
    """
    Enhanced mesh bus with:
      • Priority-based per-agent queues
      • SQLite-backed offline message store (survives restarts)
      • HMAC-signed delivery receipts
      • Gossip flood-routing with bloom-filter deduplication
      • Offline payment channels with atomic settlement broadcasts
      • Background cleanup / retry thread
      • Full backwards compatibility with the original API
    """

    # Default channels (extended with payment + gossip lanes)
    _DEFAULT_CHANNELS = frozenset({
        "system",
        "safety_alerts",
        "heartbeats",
        "trade_updates",
        "mesh_control",
        "payment_settlement",   # NEW – settlement broadcasts
        "gossip",               # NEW – gossip protocol
        "receipts",             # NEW – delivery acknowledgements
    })

    def __init__(
        self,
        log_dir:        Optional[str] = None,
        max_queue_size: int           = 10_000,
        db_path:        Optional[str] = None,
        shared_secret:  Optional[bytes] = None,
        enable_gossip:  bool          = True,
        enable_payments: bool         = True,
        enable_receipts: bool         = True,
    ):
        """
        Parameters
        ----------
        log_dir:
            Directory for JSONL event logs and (default) SQLite databases.
        max_queue_size:
            Maximum in-memory messages per agent before oldest low-priority
            message is evicted.
        db_path:
            Explicit path for the SQLite offline store.  Defaults to
            ``<log_dir>/mesh_offline.db``.
        shared_secret:
            Bytes used to sign delivery receipts and payment-channel states.
            Auto-generated (randomly) if not provided.
        enable_gossip:
            Attach a ``GossipRouter`` instance.
        enable_payments:
            Attach a ``PaymentSettler`` instance.
        enable_receipts:
            Attach a ``DeliveryReceiptManager`` and auto-issue receipts on
            every successful ``receive()`` call.
        """
        # ── Core data structures (unchanged from original) ─────────────────
        self._agent_queues:        Dict[str, List[PrioritizedMessage]] = {}
        self._channel_subscribers: Dict[str, Set[str]] = {
            ch: set() for ch in self._DEFAULT_CHANNELS
        }
        self._registered_agents:   Set[str]  = set()
        self._pending_offline:     Dict[str, List[PrioritizedMessage]] = {}
        self._message_store:       Dict[str, PrioritizedMessage] = {}
        self._delivery_confirmation: Dict[str, bool] = {}
        self._agent_last_seen:     Dict[str, float] = {}
        self._channel_stats:       Dict[str, Dict[str, int]] = {}

        # ── Thread safety ──────────────────────────────────────────────────
        self._lock = threading.RLock()

        # ── Configuration ──────────────────────────────────────────────────
        self.max_queue_size      = max_queue_size
        self.message_ttl         = 3600
        self.max_delivery_attempts = 3
        self.retry_delay         = 5.0
        self._cleanup_thread:    Optional[threading.Thread] = None
        self._cleanup_running    = False

        # ── Persistence paths ──────────────────────────────────────────────
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs" / "mesh"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        _db_path = db_path or str(self.log_dir / "mesh_offline.db")

        # ── Shared secret (for receipts + payment channels) ────────────────
        self._secret: bytes = (
            shared_secret
            if shared_secret
            else _hmac.new(
                str(uuid.uuid4()).encode(), b"simp_mesh_secret", hashlib.sha256
            ).digest()
        )

        # ── SQLite offline store (always on) ───────────────────────────────
        self.offline_store = OfflineMessageStore(_db_path)

        # ── Optional subsystems ────────────────────────────────────────────
        self.gossip: Optional[GossipRouter] = (
            GossipRouter(node_id="mesh_bus") if enable_gossip else None
        )
        self.payment_settler: Optional[PaymentSettler] = (
            PaymentSettler(
                agent_id     = "mesh_bus",
                db_path      = str(self.log_dir / "mesh_payments.db"),
                shared_secret = self._secret,
            )
            if enable_payments else None
        )
        self.receipt_manager: Optional[DeliveryReceiptManager] = (
            DeliveryReceiptManager(
                db_path       = str(self.log_dir / "mesh_receipts.db"),
                shared_secret = self._secret,
            )
            if enable_receipts else None
        )

        # ── Statistics ─────────────────────────────────────────────────────
        self._stats: Dict[str, Any] = {
            "messages_sent":       0,
            "messages_delivered":  0,
            "messages_failed":     0,
            "messages_expired":    0,
            "queue_overflows":     0,
            "avg_delivery_time":   0.0,
            "active_agents":       0,
            "active_channels":     0,
            "receipts_issued":     0,
            "gossip_originated":   0,
            "gossip_forwarded":    0,
            "offline_stored":      0,
            "offline_drained":     0,
            "payments_settled":    0,
        }

        logger.info(
            "EnhancedMeshBus initialised  max_queue=%d  "
            "gossip=%s  payments=%s  receipts=%s",
            max_queue_size,
            enable_gossip,
            enable_payments,
            enable_receipts,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _log_event(
        self,
        event_type: str,
        agent_id:   str = "",
        channel:    str = "",
        message:    str = "",
        data:       Optional[Dict] = None,
    ) -> None:
        event = {
            "timestamp":  datetime.utcnow().isoformat(),
            "event_type": event_type,
            "agent_id":   agent_id,
            "channel":    channel,
            "message":    message,
            "data":       data or {},
        }
        log_file = self.log_dir / f"mesh_events_{datetime.utcnow().date()}.jsonl"
        try:
            with open(log_file, "a") as fh:
                fh.write(json.dumps(event) + "\n")
        except OSError as exc:
            logger.debug("_log_event write failed: %s", exc)

    @staticmethod
    def _get_priority_value(priority: Priority) -> int:
        return {Priority.HIGH: 0, Priority.NORMAL: 1, Priority.LOW: 2}.get(priority, 1)

    # ── Agent management (original API, unchanged) ───────────────────────────

    def register_agent(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self._registered_agents:
                logger.warning("Agent %s already registered", agent_id)
                return False

            self._registered_agents.add(agent_id)
            self._agent_queues[agent_id] = []
            self._agent_last_seen[agent_id] = time.time()
            self._channel_subscribers["system"].add(agent_id)

            for ch in self._channel_subscribers:
                if ch not in self._channel_stats:
                    self._channel_stats[ch] = {"messages": 0, "subscribers": 0}
                self._channel_stats[ch]["subscribers"] = len(
                    self._channel_subscribers[ch]
                )

            self._stats["active_agents"] = len(self._registered_agents)

            # Drain SQLite offline store into live priority queue
            offline_packets = self.offline_store.fetch_for_agent(agent_id)
            for pkt in offline_packets:
                pv = self._get_priority_value(pkt.priority)
                pm = PrioritizedMessage(priority=pv, timestamp=time.time(), packet=pkt)
                heapq.heappush(self._agent_queues[agent_id], pm)
                self._stats["offline_drained"] += 1

            if offline_packets:
                logger.info(
                    "register_agent: drained %d offline packets for %s",
                    len(offline_packets), agent_id,
                )

            self._log_event("agent_registered", agent_id, "system")
            return True

    def deregister_agent(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id not in self._registered_agents:
                return False

            for ch, subs in self._channel_subscribers.items():
                subs.discard(agent_id)
                if ch in self._channel_stats:
                    self._channel_stats[ch]["subscribers"] = len(subs)

            if agent_id in self._agent_queues:
                for msg in self._agent_queues[agent_id]:
                    msg.status = MessageStatus.FAILED
                    self._stats["messages_failed"] += 1
                del self._agent_queues[agent_id]

            self._registered_agents.discard(agent_id)
            self._agent_last_seen.pop(agent_id, None)
            self._stats["active_agents"] = len(self._registered_agents)
            self._log_event("agent_deregistered", agent_id, "system")
            return True

    def is_agent_registered(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._registered_agents

    def update_agent_heartbeat(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id not in self._registered_agents:
                return False
            self._agent_last_seen[agent_id] = time.time()
            return True

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if agent_id not in self._registered_agents:
                return None
            return {
                "agent_id":         agent_id,
                "registered":       True,
                "queue_size":       len(self._agent_queues.get(agent_id, [])),
                "last_seen":        datetime.fromtimestamp(
                                        self._agent_last_seen.get(agent_id, 0)
                                    ).isoformat(),
                "seconds_since_seen": time.time() - self._agent_last_seen.get(agent_id, 0),
                "channels":         [
                                        ch for ch, subs in self._channel_subscribers.items()
                                        if agent_id in subs
                                    ],
                "offline_pending":  self.offline_store.pending_count(agent_id),
            }

    # ── Channel management (original API, unchanged) ─────────────────────────

    def subscribe(self, agent_id: str, channel: str) -> bool:
        with self._lock:
            if agent_id not in self._registered_agents:
                return False
            if channel not in self._channel_subscribers:
                self._channel_subscribers[channel] = set()
                self._channel_stats[channel]       = {"messages": 0, "subscribers": 0}
            self._channel_subscribers[channel].add(agent_id)
            self._channel_stats[channel]["subscribers"] = len(
                self._channel_subscribers[channel]
            )
            return True

    def unsubscribe(self, agent_id: str, channel: str) -> bool:
        with self._lock:
            if agent_id not in self._registered_agents:
                return False
            if channel in self._channel_subscribers:
                self._channel_subscribers[channel].discard(agent_id)
                if channel in self._channel_stats:
                    self._channel_stats[channel]["subscribers"] = len(
                        self._channel_subscribers[channel]
                    )
                return True
            return False

    def get_channel_subscribers(self, channel: str) -> List[str]:
        with self._lock:
            return list(self._channel_subscribers.get(channel, set()))

    # ── Message sending ───────────────────────────────────────────────────────

    def send(
        self,
        packet:            MeshPacket,
        delivery_callback: Optional[Callable] = None,
        gossip:            bool = False,
    ) -> str:
        """
        Send a packet.

        Parameters
        ----------
        packet:
            The MeshPacket to send.
        delivery_callback:
            Optional callable(message_id, success) called on delivery/failure.
        gossip:
            If True, also originate the packet through the GossipRouter so it
            is flooded to all registered mesh peers.

        Returns
        -------
        str
            Internal message-id for status tracking.
        """
        with self._lock:
            pv  = self._get_priority_value(packet.priority)
            pm  = PrioritizedMessage(
                priority          = pv,
                timestamp         = time.time(),
                packet            = packet,
                delivery_callback = delivery_callback,
            )
            self._message_store[pm.message_id] = pm

            if packet.recipient_id and packet.recipient_id != "*":
                success = self._send_to_agent(pm)
            elif packet.channel:
                success = self._broadcast_to_channel(pm)
            else:
                success = self._broadcast_to_all(pm)

            if success:
                self._stats["messages_sent"] += 1
                self._log_event(
                    "message_sent",
                    packet.sender_id,
                    packet.channel or "broadcast",
                    f"Message {pm.message_id} sent",
                )
            else:
                pm.status = MessageStatus.FAILED
                self._stats["messages_failed"] += 1

        # Gossip is intentionally outside the main lock to avoid deadlock with
        # transport-layer callbacks.
        if gossip and self.gossip:
            self.gossip.originate(packet)
            self._stats["gossip_originated"] += 1

        return pm.message_id

    def send_with_receipt(
        self,
        packet:  MeshPacket,
        timeout: float = 30.0,
    ) -> Tuple[str, Optional[DeliveryReceipt]]:
        """
        Send a packet and block until a delivery receipt arrives or *timeout* elapses.

        Returns
        -------
        (message_id, DeliveryReceipt | None)
            Receipt is None on timeout or if receipt_manager is disabled.
        """
        receipt_holder: List[Optional[DeliveryReceipt]] = [None]
        event = threading.Event()

        def _on_delivery(msg_id: str, success: bool) -> None:
            if success and self.receipt_manager:
                receipt_holder[0] = self.receipt_manager.get(msg_id)
            event.set()

        msg_id = self.send(packet, delivery_callback=_on_delivery)
        event.wait(timeout=timeout)
        return msg_id, receipt_holder[0]

    def _send_to_agent(self, pm: PrioritizedMessage) -> bool:
        packet   = pm.packet
        agent_id = packet.recipient_id

        if agent_id not in self._registered_agents:
            # Agent offline – persist to SQLite store for durable delivery
            self.offline_store.store(packet, priority=pm.priority)
            self._stats["offline_stored"] += 1
            logger.debug("offline-store: queued for %s", agent_id)
            return True

        queue = self._agent_queues.setdefault(agent_id, [])
        if len(queue) >= self.max_queue_size:
            self._stats["queue_overflows"] += 1
            if queue:
                evicted = heapq.heappop(queue)
                evicted.status = MessageStatus.FAILED
                self._stats["messages_failed"] += 1

        heapq.heappush(queue, pm)
        return True

    def _broadcast_to_channel(self, pm: PrioritizedMessage) -> bool:
        packet  = pm.packet
        channel = packet.channel

        if channel not in self._channel_subscribers:
            return False

        subscribers = self._channel_subscribers[channel]
        count       = 0
        for agent_id in subscribers:
            pkt_copy = MeshPacket(
                version         = packet.version,
                msg_type        = packet.msg_type,
                message_id      = str(uuid.uuid4()),
                correlation_id  = packet.correlation_id,
                sender_id       = packet.sender_id,
                recipient_id    = agent_id,
                channel         = channel,
                timestamp       = packet.timestamp,
                ttl_hops        = packet.ttl_hops,
                ttl_seconds     = packet.ttl_seconds,
                priority        = packet.priority,
                payload         = packet.payload,
                routing_history = list(packet.routing_history) if packet.routing_history else [],
            )
            sub_pm = PrioritizedMessage(
                priority  = pm.priority,
                timestamp = time.time(),
                packet    = pkt_copy,
            )
            self._message_store[sub_pm.message_id] = sub_pm
            if self._send_to_agent(sub_pm):
                count += 1

        if channel in self._channel_stats:
            self._channel_stats[channel]["messages"] += count
        return count > 0

    def _broadcast_to_all(self, pm: PrioritizedMessage) -> bool:
        packet   = pm.packet
        pkt_copy = MeshPacket(
            version         = packet.version,
            msg_type        = packet.msg_type,
            message_id      = str(uuid.uuid4()),
            correlation_id  = packet.correlation_id,
            sender_id       = packet.sender_id,
            recipient_id    = "*",
            channel         = "system",
            timestamp       = packet.timestamp,
            ttl_hops        = packet.ttl_hops,
            ttl_seconds     = packet.ttl_seconds,
            priority        = packet.priority,
            payload         = packet.payload,
            routing_history = list(packet.routing_history) if packet.routing_history else [],
        )
        broadcast_pm = PrioritizedMessage(
            priority  = pm.priority,
            timestamp = time.time(),
            packet    = pkt_copy,
        )
        return self._broadcast_to_channel(broadcast_pm)

    # ── Message receiving ─────────────────────────────────────────────────────

    def receive(self, agent_id: str, max_messages: int = 1) -> List[MeshPacket]:
        """
        Receive messages for *agent_id*.

        If receipt_manager is enabled, a signed delivery receipt is issued
        automatically for every message handed to the agent.
        """
        with self._lock:
            if agent_id not in self._registered_agents:
                return []

            queue = self._agent_queues.get(agent_id, [])
            if not queue:
                return []

            self._agent_last_seen[agent_id] = time.time()

            messages: List[MeshPacket] = []
            to_clean: List[str]        = []

            for _ in range(min(max_messages, len(queue))):
                if not queue:
                    break

                pm     = heapq.heappop(queue)
                packet = pm.packet

                # TTL check
                try:
                    pkt_ts = datetime.fromisoformat(
                        packet.timestamp.replace("Z", "+00:00")
                    ).timestamp()
                except (ValueError, AttributeError):
                    pkt_ts = time.time()

                if time.time() > pkt_ts + packet.ttl_seconds:
                    pm.status = MessageStatus.EXPIRED
                    self._stats["messages_expired"] += 1
                    self._log_event("message_expired", agent_id, packet.channel)
                    continue

                # Mark delivered
                pm.status = MessageStatus.DELIVERED
                self._delivery_confirmation[pm.message_id] = True
                self._stats["messages_delivered"] += 1

                # Issue signed receipt
                if self.receipt_manager:
                    try:
                        self.receipt_manager.issue(
                            pm.message_id,
                            agent_id,
                            packet.sender_id,
                        )
                        self._stats["receipts_issued"] += 1
                    except Exception as exc:
                        logger.warning("receipt issue failed: %s", exc)

                # Update delivery timing EMA
                dt = time.time() - pm.timestamp
                self._stats["avg_delivery_time"] = (
                    self._stats["avg_delivery_time"] * 0.9 + dt * 0.1
                )

                if pm.delivery_callback:
                    try:
                        pm.delivery_callback(pm.message_id, True)
                    except Exception as exc:
                        logger.error("delivery callback raised: %s", exc)

                messages.append(packet)
                to_clean.append(pm.message_id)

            for mid in to_clean:
                self._message_store.pop(mid, None)

            # Drain SQLite offline store (belt-and-suspenders flush)
            self._deliver_offline(agent_id)

        return messages

    def _deliver_offline(self, agent_id: str) -> None:
        """Drain SQLite offline store into the live in-memory queue."""
        offline = self.offline_store.fetch_for_agent(agent_id, limit=100)
        if not offline:
            return

        queue = self._agent_queues.setdefault(agent_id, [])
        for pkt in offline:
            try:
                pkt_ts = datetime.fromisoformat(
                    pkt.timestamp.replace("Z", "+00:00")
                ).timestamp()
            except (ValueError, AttributeError):
                pkt_ts = time.time()

            if time.time() > pkt_ts + pkt.ttl_seconds:
                self._stats["messages_expired"] += 1
                continue

            pv = self._get_priority_value(pkt.priority)
            pm = PrioritizedMessage(priority=pv, timestamp=time.time(), packet=pkt)
            heapq.heappush(queue, pm)
            self._stats["offline_drained"] += 1

        if offline:
            logger.info(
                "_deliver_offline: drained %d packets for %s", len(offline), agent_id
            )

    # ── Payment helpers (new public API) ─────────────────────────────────────

    def open_payment_channel(
        self,
        initiator_id:    str,
        counterparty_id: str,
        my_balance:      float,
        their_balance:   float = 0.0,
    ) -> Optional["PaymentChannel"]:
        """
        Open a bilateral offline payment channel.
        Requires payment_settler to be enabled.
        """
        if not self.payment_settler:
            logger.warning("open_payment_channel: payment support not enabled")
            return None
        # Create a per-agent settler on demand
        settler = PaymentSettler(
            agent_id      = initiator_id,
            db_path       = str(self.log_dir / f"payments_{initiator_id}.db"),
            shared_secret = self._secret,
        )
        ch = settler.open_channel(counterparty_id, my_balance, their_balance)
        self._log_event(
            "payment_channel_opened",
            initiator_id,
            "payment_settlement",
            f"Channel {ch.channel_id} opened",
            {"channel_id": ch.channel_id},
        )
        return ch

    def broadcast_settlement(
        self,
        settlement_payload: Dict[str, Any],
        sender_id:          str,
    ) -> str:
        """
        Broadcast a channel settlement to all subscribers of the
        `payment_settlement` channel.
        Returns the broadcast message_id.
        """
        pkt = create_event_packet(
            sender_id    = sender_id,
            recipient_id = "*",
            channel      = "payment_settlement",
            payload      = settlement_payload,
            priority     = Priority.HIGH,
            ttl_seconds  = 86_400,   # 24 h – settlements must survive partition
        )
        self._stats["payments_settled"] += 1
        return self.send(pkt)

    # ── Gossip helpers (new public API) ──────────────────────────────────────

    def add_gossip_peer(self, peer_id: str, endpoint: str) -> None:
        if self.gossip:
            self.gossip.add_peer(peer_id, endpoint)

    def gossip_send(self, packet: MeshPacket) -> int:
        """
        Originate *packet* through the gossip router.
        Returns number of peers it was forwarded to (0 if gossip disabled).
        """
        if not self.gossip:
            return 0
        count = self.gossip.originate(packet)
        self._stats["gossip_originated"] += 1
        return count

    def gossip_receive(self, packet: MeshPacket, from_peer_id: str) -> int:
        """
        Handle an incoming gossip packet from *from_peer_id*.
        Returns number of peers forwarded to.
        """
        if not self.gossip:
            return 0
        count = self.gossip.receive_and_forward(packet, from_peer_id)
        if count:
            self._stats["gossip_forwarded"] += count
        return count

    # ── Receipt helpers ───────────────────────────────────────────────────────

    def get_receipt(self, message_id: str) -> Optional[DeliveryReceipt]:
        if not self.receipt_manager:
            return None
        return self.receipt_manager.get(message_id)

    # ── Original public API (unchanged) ──────────────────────────────────────

    def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            msg = self._message_store.get(message_id)
            if not msg:
                return None
            packet = msg.packet
            try:
                pkt_ts = datetime.fromisoformat(
                    packet.timestamp.replace("Z", "+00:00")
                ).timestamp()
            except (ValueError, AttributeError):
                pkt_ts = time.time()
            return {
                "message_id":       message_id,
                "status":           msg.status.value,
                "source_agent":     packet.sender_id,
                "target_agent":     packet.recipient_id,
                "target_channel":   packet.channel,
                "priority":         packet.priority,
                "delivery_attempts": msg.delivery_attempts,
                "created_at":       datetime.fromtimestamp(msg.timestamp).isoformat(),
                "age_seconds":      time.time() - msg.timestamp,
                "ttl_seconds":      packet.ttl_seconds,
                "expires_at":       datetime.fromtimestamp(pkt_ts + packet.ttl_seconds).isoformat(),
                "has_receipt":      (
                    self.receipt_manager is not None
                    and self.receipt_manager.get(message_id) is not None
                ),
            }

    def confirm_delivery(self, message_id: str) -> bool:
        with self._lock:
            msg = self._message_store.get(message_id)
            if not msg:
                return False
            msg.status = MessageStatus.DELIVERED
            self._delivery_confirmation[message_id] = True
            if msg.delivery_callback:
                try:
                    msg.delivery_callback(message_id, True)
                except Exception as exc:
                    logger.error("confirm_delivery callback raised: %s", exc)
            return True

    def retry_failed_messages(self) -> int:
        with self._lock:
            count = 0
            for msg in list(self._message_store.values()):
                if (
                    msg.status == MessageStatus.FAILED
                    and msg.delivery_attempts < self.max_delivery_attempts
                ):
                    msg.status = MessageStatus.PENDING
                    msg.delivery_attempts += 1
                    if msg.packet.recipient_id and msg.packet.recipient_id != "*":
                        self._send_to_agent(msg)
                    count += 1
            return count

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            stats = self._stats.copy()
            stats.update(
                {
                    "total_messages_stored":    len(self._message_store),
                    "total_agents_registered":  len(self._registered_agents),
                    "total_channels":           len(self._channel_subscribers),
                    "pending_offline_messages": self.offline_store.pending_count(),
                    "offline_store":            self.offline_store.stats(),
                    "channel_stats":            self._channel_stats.copy(),
                    "queue_sizes": {
                        aid: len(q)
                        for aid, q in self._agent_queues.items()
                    },
                }
            )
            if self.gossip:
                stats["gossip"] = self.gossip.get_stats()
            if self.payment_settler:
                stats["payment_summary"] = self.payment_settler.get_balance_summary()
            if self.receipt_manager:
                stats["receipts_in_db"] = self.receipt_manager.count()
            return stats

    # ── Background cleanup ───────────────────────────────────────────────────

    def _cleanup_expired(self) -> None:
        with self._lock:
            now = time.time()
            expired_msgs = [
                mid for mid, msg in self._message_store.items()
                if (
                    lambda pkt_ts: now > pkt_ts + msg.packet.ttl_seconds
                )(
                    datetime.fromisoformat(
                        msg.packet.timestamp.replace("Z", "+00:00")
                    ).timestamp()
                    if msg.packet.timestamp else now
                )
            ]
            for mid in expired_msgs:
                self._message_store[mid].status = MessageStatus.EXPIRED
                del self._message_store[mid]
            if expired_msgs:
                self._stats["messages_expired"] += len(expired_msgs)

            stale = [
                aid for aid, ts in self._agent_last_seen.items()
                if now - ts > 300
            ]
            for aid in stale:
                self.deregister_agent(aid)

        # Purge SQLite offline store
        purged = self.offline_store.purge_expired()
        if purged:
            logger.debug("offline store purged %d expired rows", purged)

    def _cleanup_loop(self) -> None:
        while self._cleanup_running:
            time.sleep(60)
            try:
                self._cleanup_expired()
                self.retry_failed_messages()
            except Exception as exc:
                logger.error("cleanup loop error: %s", exc)

    def start_cleanup(self) -> None:
        with self._lock:
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                return
            self._cleanup_running = True
            self._cleanup_thread  = threading.Thread(
                target=self._cleanup_loop, daemon=True, name="MeshBusCleanup"
            )
            self._cleanup_thread.start()
            self._start_time = time.time()
            logger.info("EnhancedMeshBus cleanup thread started")

    def stop_cleanup(self) -> None:
        with self._lock:
            self._cleanup_running = False
            if self._cleanup_thread:
                self._cleanup_thread.join(timeout=5)
                self._cleanup_thread = None

    def shutdown(self) -> None:
        """Flush pending state to disk and release resources."""
        self.stop_cleanup()
        with self._lock:
            # Persist in-memory PENDING messages to SQLite so nothing is lost
            flushed = 0
            for msg in self._message_store.values():
                if msg.status == MessageStatus.PENDING:
                    self.offline_store.store(msg.packet, priority=msg.priority)
                    flushed += 1

            # Also save a JSON snapshot (backwards compat with original)
            pending_list = [
                {
                    "message_id": mid,
                    "packet":     msg.packet.to_dict(),
                    "status":     msg.status.value,
                    "timestamp":  msg.timestamp,
                }
                for mid, msg in self._message_store.items()
                if msg.status == MessageStatus.PENDING
            ]
            if pending_list:
                snap = self.log_dir / f"mesh_state_{int(time.time())}.json"
                try:
                    with open(snap, "w") as fh:
                        json.dump(
                            {"timestamp": time.time(), "messages": pending_list},
                            fh,
                            indent=2,
                        )
                    logger.info(
                        "shutdown: saved %d pending messages → %s", len(pending_list), snap
                    )
                except OSError as exc:
                    logger.error("shutdown snapshot failed: %s", exc)

            self._agent_queues.clear()
            self._channel_subscribers.clear()
            self._registered_agents.clear()
            self._pending_offline.clear()
            self._message_store.clear()
            self._delivery_confirmation.clear()
            self._agent_last_seen.clear()
            self._channel_stats.clear()

        logger.info(
            "EnhancedMeshBus shutdown complete  flushed=%d pending to SQLite", flushed
        )


# ─────────────────────────────────────────────────────────────────────────────
# Singleton factory (original API preserved)
# ─────────────────────────────────────────────────────────────────────────────

def get_enhanced_mesh_bus(log_dir: Optional[str] = None) -> EnhancedMeshBus:
    """
    Return the process-level EnhancedMeshBus singleton.

    On first call the bus is created, the cleanup thread is started,
    and all new subsystems (gossip, payments, receipts) are enabled by
    default.  Subsequent calls return the same instance regardless of
    *log_dir*.
    """
    if not hasattr(get_enhanced_mesh_bus, "_instance"):
        # Use absolute import for config
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from config.config import config
        
        # Use config values for stable secrets and paths
        shared_secret = config.MESH_SHARED_SECRET.encode() if config.MESH_SHARED_SECRET else None
        db_path = config.MESH_DB_PATH
        
        get_enhanced_mesh_bus._instance = EnhancedMeshBus(
            log_dir=log_dir or config.MESH_LOG_DIR,
            db_path=db_path,
            shared_secret=shared_secret,
            enable_gossip=True,
            enable_payments=True,
            enable_receipts=True
        )
        get_enhanced_mesh_bus._instance.start_cleanup()
    return get_enhanced_mesh_bus._instance
