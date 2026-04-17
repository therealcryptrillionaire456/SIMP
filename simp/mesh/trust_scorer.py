"""
TrustScorer — SIMP Layer 4 (Reputation/Trust Graph)
====================================================
Reads from two live SQLite databases:

  1. DeliveryReceiptManager  (logs/mesh/mesh_receipts.db)
     Table: receipts(message_id, recipient_id, sender_id, received_at, signature, stored_at)

  2. PaymentSettler          (logs/mesh/mesh_payments.db)
     Table: payment_channels(channel_id, data TEXT JSON, updated_at)
     Table: settlements(settlement_id, channel_id, settled_at, final_state TEXT, signature)

Score formula per agent  →  [0.0 – 5.0]
────────────────────────────────────────
receipt_score  (weight 0.6)
  = clamp( (sent_deliveries + received_deliveries) / RECEIPT_CEILING, 0, 1 ) * 5.0
  RECEIPT_CEILING = 20  (20+ total receipts = full score)

payment_score  (weight 0.4)
  = (balance_ratio * 0.5 + activity_norm * 0.5) * 5.0
  balance_ratio   = remaining_balance / total_capacity  (0 if no channels)
  activity_norm   = clamp(total_htlc_count / HTLC_CEILING, 0, 1)
  HTLC_CEILING    = 50  (50+ HTLCs across channels = full payment score)

final_trust = receipt_score * 0.6 + payment_score * 0.4
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tuning constants ─────────────────────────────────────────────────────────
RECEIPT_CEILING  = 20     # receipts for max receipt score
HTLC_CEILING     = 50     # HTLC ops across channels for max payment score
SCORE_MAX        = 5.0
RECEIPT_WEIGHT   = 0.6
PAYMENT_WEIGHT   = 0.4
STALE_SECONDS    = 300    # score older than this triggers background refresh


@dataclass
class TrustScore:
    """Immutable trust score snapshot for a single agent."""
    agent_id:         str
    trust_score:      float          # [0.0 – 5.0]
    receipt_score:    float          # receipt component [0.0 – 5.0]
    payment_score:    float          # payment component [0.0 – 5.0]
    sent_deliveries:  int            # receipts where sender_id = agent
    recv_deliveries:  int            # receipts where recipient_id = agent
    open_channels:    int
    total_htlcs:      int
    balance_ratio:    float          # remaining / capacity, [0.0 – 1.0]
    computed_at:      float = field(default_factory=time.time)

    def is_stale(self, ttl: float = STALE_SECONDS) -> bool:
        return (time.time() - self.computed_at) > ttl

    def to_dict(self) -> Dict:
        return {
            "agent_id":        self.agent_id,
            "trust_score":     round(self.trust_score, 4),
            "receipt_score":   round(self.receipt_score, 4),
            "payment_score":   round(self.payment_score, 4),
            "sent_deliveries": self.sent_deliveries,
            "recv_deliveries": self.recv_deliveries,
            "open_channels":   self.open_channels,
            "total_htlcs":     self.total_htlcs,
            "balance_ratio":   round(self.balance_ratio, 4),
            "computed_at":     self.computed_at,
        }


class TrustScorer:
    """
    Reads DeliveryReceiptManager and PaymentSettler SQLite databases,
    computes a [0.0–5.0] trust score per agent.

    Thread-safe.  All reads are read-only (no writes to either DB).
    """

    def __init__(
        self,
        receipts_db_path: Optional[str] = None,
        payments_db_path: Optional[str] = None,
        log_dir: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        receipts_db_path:
            Path to mesh_receipts.db.  Defaults to <log_dir>/mesh_receipts.db.
        payments_db_path:
            Path to mesh_payments.db.  Defaults to <log_dir>/mesh_payments.db.
        log_dir:
            Base log directory.  Defaults to logs/mesh/ relative to cwd.
        """
        base = Path(log_dir) if log_dir else Path.cwd() / "logs" / "mesh"
        self._receipts_path = Path(receipts_db_path) if receipts_db_path else (base / "mesh_receipts.db")
        self._payments_path = Path(payments_db_path) if payments_db_path else (base / "mesh_payments.db")
        self._lock = threading.Lock()
        self._cache: Dict[str, TrustScore] = {}

        logger.info(
            "[TrustScorer] init  receipts=%s  payments=%s",
            self._receipts_path, self._payments_path,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def score(self, agent_id: str) -> TrustScore:
        """
        Compute and cache trust score for *agent_id*.
        Returns cached value if fresh, recomputes otherwise.
        """
        with self._lock:
            cached = self._cache.get(agent_id)
            if cached and not cached.is_stale():
                return cached

        ts = self._compute(agent_id)

        with self._lock:
            self._cache[agent_id] = ts

        return ts

    def score_all_known(self) -> List[TrustScore]:
        """
        Score every agent that appears in either database.
        Returns sorted list (highest trust_score first).
        """
        agents = self._all_known_agents()
        scores = [self.score(aid) for aid in agents]
        scores.sort(key=lambda s: s.trust_score, reverse=True)
        return scores

    def invalidate(self, agent_id: str) -> None:
        """Force cache eviction for *agent_id* (next call recomputes)."""
        with self._lock:
            self._cache.pop(agent_id, None)

    def get_cached(self, agent_id: str) -> Optional[TrustScore]:
        """Return cached score without recomputing (may be None or stale)."""
        with self._lock:
            return self._cache.get(agent_id)

    def summary(self) -> Dict:
        """Return a summary of all cached scores."""
        with self._lock:
            entries = list(self._cache.values())
        return {
            "agent_count": len(entries),
            "avg_trust":   round(sum(e.trust_score for e in entries) / max(len(entries), 1), 4),
            "max_trust":   max((e.trust_score for e in entries), default=0.0),
            "min_trust":   min((e.trust_score for e in entries), default=0.0),
            "agents":      [e.to_dict() for e in sorted(entries, key=lambda x: x.trust_score, reverse=True)],
        }

    # ── Internal computation ──────────────────────────────────────────────────

    def _compute(self, agent_id: str) -> TrustScore:
        """Full score computation — reads both DBs."""
        sent, recv    = self._query_receipts(agent_id)
        open_ch, htlcs, bal_ratio = self._query_payments(agent_id)

        # Receipt component
        total_receipts = sent + recv
        receipt_norm   = min(total_receipts / RECEIPT_CEILING, 1.0)
        receipt_score  = receipt_norm * SCORE_MAX

        # Payment component
        activity_norm  = min(htlcs / HTLC_CEILING, 1.0)
        payment_score  = (bal_ratio * 0.5 + activity_norm * 0.5) * SCORE_MAX

        # Weighted combination
        trust_score = receipt_score * RECEIPT_WEIGHT + payment_score * PAYMENT_WEIGHT
        trust_score = round(min(max(trust_score, 0.0), SCORE_MAX), 4)

        logger.debug(
            "[TrustScorer] %s  trust=%.3f  receipt=%.3f (s=%d r=%d)  "
            "payment=%.3f (ch=%d htlc=%d bal=%.2f)",
            agent_id, trust_score, receipt_score, sent, recv,
            payment_score, open_ch, htlcs, bal_ratio,
        )

        return TrustScore(
            agent_id       = agent_id,
            trust_score    = trust_score,
            receipt_score  = round(receipt_score, 4),
            payment_score  = round(payment_score, 4),
            sent_deliveries= sent,
            recv_deliveries= recv,
            open_channels  = open_ch,
            total_htlcs    = htlcs,
            balance_ratio  = round(bal_ratio, 4),
        )

    # ── Receipt DB queries ────────────────────────────────────────────────────

    def _query_receipts(self, agent_id: str) -> tuple[int, int]:
        """Return (sent_deliveries, recv_deliveries) for agent_id."""
        if not self._receipts_path.exists():
            logger.debug("[TrustScorer] receipts DB not found: %s", self._receipts_path)
            return 0, 0

        try:
            conn = sqlite3.connect(str(self._receipts_path), timeout=5)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute(
                "SELECT COUNT(*) FROM receipts WHERE sender_id = ?", (agent_id,)
            )
            sent = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM receipts WHERE recipient_id = ?", (agent_id,)
            )
            recv = cur.fetchone()[0]

            conn.close()
            return int(sent), int(recv)

        except Exception as exc:
            logger.warning("[TrustScorer] receipt query failed for %s: %s", agent_id, exc)
            return 0, 0

    # ── Payment DB queries ────────────────────────────────────────────────────

    def _query_payments(self, agent_id: str) -> tuple[int, int, float]:
        """Return (open_channels, total_htlcs, balance_ratio) for agent_id."""
        if not self._payments_path.exists():
            logger.debug("[TrustScorer] payments DB not found: %s", self._payments_path)
            return 0, 0, 0.0

        try:
            conn = sqlite3.connect(str(self._payments_path), timeout=5)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute(
                "SELECT data FROM payment_channels "
                "WHERE json_extract(data,'$.state') = 'open'"
            )
            rows = cur.fetchall()
            conn.close()

            open_channels  = 0
            total_htlcs    = 0
            total_capacity = 0.0
            my_balance     = 0.0

            for row in rows:
                try:
                    ch = json.loads(row["data"])
                    initiator  = ch.get("initiator_id", "")
                    counterparty = ch.get("counterparty_id", "")

                    if agent_id not in (initiator, counterparty):
                        continue

                    open_channels  += 1
                    total_htlcs    += ch.get("sequence", 0)
                    cap             = ch.get("total_capacity", 0.0)
                    total_capacity += cap

                    if agent_id == initiator:
                        my_balance += ch.get("initiator_balance", 0.0)
                    else:
                        my_balance += ch.get("counterparty_balance", 0.0)

                except (json.JSONDecodeError, KeyError):
                    continue

            balance_ratio = (my_balance / total_capacity) if total_capacity > 0 else 0.0
            balance_ratio = min(max(balance_ratio, 0.0), 1.0)

            return open_channels, total_htlcs, balance_ratio

        except Exception as exc:
            logger.warning("[TrustScorer] payment query failed for %s: %s", agent_id, exc)
            return 0, 0, 0.0

    # ── Helper: all known agents across both DBs ──────────────────────────────

    def _all_known_agents(self) -> List[str]:
        """Return all agent IDs that appear in either database."""
        agents: set = set()

        if self._receipts_path.exists():
            try:
                conn = sqlite3.connect(str(self._receipts_path), timeout=5)
                cur  = conn.cursor()
                for col in ("sender_id", "recipient_id"):
                    cur.execute(f"SELECT DISTINCT {col} FROM receipts WHERE {col} IS NOT NULL")
                    agents.update(r[0] for r in cur.fetchall())
                conn.close()
            except Exception as exc:
                logger.warning("[TrustScorer] receipts agents scan failed: %s", exc)

        if self._payments_path.exists():
            try:
                conn = sqlite3.connect(str(self._payments_path), timeout=5)
                cur  = conn.cursor()
                cur.execute("SELECT data FROM payment_channels")
                for row in cur.fetchall():
                    try:
                        ch = json.loads(row[0])
                        for field in ("initiator_id", "counterparty_id"):
                            if ch.get(field):
                                agents.add(ch[field])
                    except Exception:
                        pass
                conn.close()
            except Exception as exc:
                logger.warning("[TrustScorer] payments agents scan failed: %s", exc)

        return list(agents)


# ── Singleton factory ─────────────────────────────────────────────────────────

def get_trust_scorer(
    receipts_db_path: Optional[str] = None,
    payments_db_path: Optional[str] = None,
    log_dir: Optional[str] = None,
) -> TrustScorer:
    """
    Return the process-level TrustScorer singleton.
    Paths are resolved against the EnhancedMeshBus log directory by default.
    """
    if not hasattr(get_trust_scorer, "_instance"):
        # Try to inherit log_dir from the live mesh bus if available
        if log_dir is None:
            try:
                from .enhanced_bus import get_enhanced_mesh_bus
                bus = get_enhanced_mesh_bus()
                log_dir = str(bus.log_dir)
            except Exception:
                pass

        get_trust_scorer._instance = TrustScorer(
            receipts_db_path = receipts_db_path,
            payments_db_path = payments_db_path,
            log_dir          = log_dir,
        )

    return get_trust_scorer._instance
