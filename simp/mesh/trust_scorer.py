#!/usr/bin/env python3
"""
simp/mesh/trust_scorer.py  —  Phase 4: L4 Trust Graph / TrustScorer

Reads DeliveryReceiptManager SQLite + PaymentSettler DB.
Outputs a score [0.0–5.0] per agent.
Wires into SimpleIntentMeshRouter._find_agent_for_intent_type() weighting.

DROP INTO: simp/mesh/trust_scorer.py
RUN STANDALONE: python3.10 simp/mesh/trust_scorer.py
"""

import sqlite3
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("simp.mesh.trust_scorer")

# ─── Scoring weights ──────────────────────────────────────────────────────────
WEIGHT_DELIVERY_RATE   = 0.40   # % of messages successfully delivered
WEIGHT_RESPONSE_TIME   = 0.25   # inverse of avg delivery latency
WEIGHT_PAYMENT_HISTORY = 0.20   # payment settlement success rate
WEIGHT_RECENCY         = 0.15   # bias toward recently-active agents

MAX_SCORE = 5.0
RECENCY_WINDOW_HOURS = 48       # only count receipts in last 48h for recency

# Known DB paths — tries each in order
RECEIPT_DB_CANDIDATES = [
    "logs/mesh/mesh_receipts.db",
    "logs/mesh_receipts.db",
    "data/mesh_receipts.db",
    "data/enhanced_mesh.db",
    "data/simp.db",
    "data/mesh.db",
]
PAYMENT_DB_CANDIDATES = [
    "logs/mesh/mesh_payments.db",
    "logs/mesh_payments.db",
    "data/payments.db",
    "data/payment_settler.db",
    "data/simp.db",
]


@dataclass
class AgentTrustProfile:
    agent_id: str
    sent_deliveries: int = 0
    recv_deliveries: int = 0
    total_receipts: int = 0
    delivered: int = 0
    failed: int = 0
    avg_latency_ms: float = 0.0
    payments_attempted: int = 0
    payments_settled: int = 0
    open_channels: int = 0
    total_htlcs: int = 0
    balance_ratio: float = 0.0
    last_seen_ts: Optional[float] = None
    raw_score: float = 0.0
    receipt_score: float = 0.0
    payment_score: float = 0.0
    score: float = 0.0          # final [0.0–5.0]
    breakdown: Dict = field(default_factory=dict)


@dataclass
class TrustScore:
    """Compatibility class for trust_graph.py"""
    agent_id: str
    trust_score: float = 1.0
    receipt_score: float = 0.0
    payment_score: float = 0.0
    sent_deliveries: int = 0
    recv_deliveries: int = 0
    open_channels: int = 0
    total_htlcs: int = 0
    balance_ratio: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

    def is_stale(self) -> bool:
        return False


class TrustScorer:
    """
    Computes trust scores from mesh receipts and payment history.

    Usage:
        scorer = TrustScorer()
        scores = scorer.get_scores()          # {agent_id: 0.0-5.0}
        profile = scorer.get_profile("gate4_real")
    """

    def __init__(
        self,
        receipt_db: Optional[str] = None,
        payment_db: Optional[str] = None,
        base_dir: str = ".",
        receipts_db_path: Optional[str] = None,
        payments_db_path: Optional[str] = None,
        log_dir: Optional[str] = None,
    ):
        if receipts_db_path and not receipt_db:
            receipt_db = receipts_db_path
        if payments_db_path and not payment_db:
            payment_db = payments_db_path
        if log_dir and base_dir == ".":
            base_dir = log_dir

        self.base_dir = Path(base_dir)
        self.receipt_db = self._resolve(receipt_db, RECEIPT_DB_CANDIDATES)
        self.payment_db = self._resolve(payment_db, PAYMENT_DB_CANDIDATES)
        self._profiles: Dict[str, AgentTrustProfile] = {}
        self._score_cache: Dict[str, TrustScore] = {}
        self._computed_at: Optional[float] = None
        self._ttl = 60.0   # re-compute at most once per minute

    def _resolve(self, explicit: Optional[str], candidates: List[str]) -> Optional[Path]:
        if explicit:
            p = Path(explicit)
            return p if p.exists() else None
        for c in candidates:
            p = self.base_dir / c
            if p.exists():
                logger.info(f"Found DB: {p}")
                return p
        logger.warning(f"No DB found among {candidates}")
        return None

    # ─── DB introspection ─────────────────────────────────────────────────────

    def _tables(self, db: Path) -> List[str]:
        try:
            conn = sqlite3.connect(str(db))
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
            return tables
        except Exception as e:
            logger.error(f"_tables({db}): {e}")
            return []

    def _columns(self, db: Path, table: str) -> List[str]:
        try:
            conn = sqlite3.connect(str(db))
            cur = conn.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cur.fetchall()]
            conn.close()
            return cols
        except Exception:
            return []

    def _pick_col(self, candidates: List[str], available: List[str]) -> Optional[str]:
        for c in candidates:
            if c in available:
                return c
        return None

    # ─── Receipt parsing ──────────────────────────────────────────────────────

    def _load_receipts(self) -> Dict[str, AgentTrustProfile]:
        profiles: Dict[str, AgentTrustProfile] = {}
        if not self.receipt_db:
            return profiles

        tables = self._tables(self.receipt_db)
        logger.info(f"Receipt DB tables: {tables}")

        # Find the right table
        receipt_table = None
        for candidate in ["delivery_receipts", "receipts", "mesh_receipts", "messages"]:
            if candidate in tables:
                receipt_table = candidate
                break
        if not receipt_table and tables:
            receipt_table = tables[0]
        if not receipt_table:
            logger.warning("No receipt table found")
            return profiles

        cols = self._columns(self.receipt_db, receipt_table)
        logger.info(f"Receipt table '{receipt_table}' columns: {cols}")

        # Map column names flexibly
        sender_col   = self._pick_col(["sender_id","source_agent","from_agent","agent_id"], cols)
        receiver_col = self._pick_col(["recipient_id","target_agent","to_agent","receiver_id"], cols)
        status_col   = self._pick_col(["status","delivery_status","state"], cols)
        latency_col  = self._pick_col(["latency_ms","delivery_time_ms","duration_ms","elapsed_ms"], cols)
        ts_col       = self._pick_col(["timestamp","created_at","sent_at","ts"], cols)

        if not sender_col:
            logger.warning("Cannot identify sender column in receipt table")
            return profiles

        select_cols = [sender_col]
        if receiver_col: select_cols.append(receiver_col)
        if status_col:   select_cols.append(status_col)
        if latency_col:  select_cols.append(latency_col)
        if ts_col:       select_cols.append(ts_col)

        try:
            conn = sqlite3.connect(str(self.receipt_db))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT {', '.join(select_cols)} FROM {receipt_table} LIMIT 50000"
            ).fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"Receipt query failed: {e}")
            return profiles

        now = time.time()
        recency_cutoff = now - (RECENCY_WINDOW_HOURS * 3600)

        for row in rows:
            agent_id = str(row[sender_col])
            if not agent_id or agent_id in ("", "None", "null"):
                continue

            if agent_id not in profiles:
                profiles[agent_id] = AgentTrustProfile(agent_id=agent_id)
            p = profiles[agent_id]
            p.sent_deliveries += 1
            p.total_receipts += 1

            # Delivery status
            if status_col:
                status = str(row[status_col]).lower()
                if any(x in status for x in ("delivered", "success", "ok", "completed")):
                    p.delivered += 1
                elif any(x in status for x in ("failed", "error", "timeout", "drop")):
                    p.failed += 1
                else:
                    p.delivered += 1   # treat unknown as delivered

            # Latency
            if latency_col and row[latency_col] is not None:
                try:
                    lat = float(row[latency_col])
                    if lat > 0:
                        p.avg_latency_ms = (
                            (p.avg_latency_ms * (p.total_receipts - 1) + lat)
                            / p.total_receipts
                        )
                except (ValueError, TypeError):
                    pass

            # Recency
            if ts_col and row[ts_col] is not None:
                try:
                    ts_val = row[ts_col]
                    if isinstance(ts_val, str):
                        ts = datetime.fromisoformat(ts_val.replace("Z", "+00:00")).timestamp()
                    else:
                        ts = float(ts_val)
                    if p.last_seen_ts is None or ts > p.last_seen_ts:
                        p.last_seen_ts = ts
                except Exception:
                    pass

        # Also count receiver participation (being a receiver builds trust too)
        if receiver_col:
            try:
                conn = sqlite3.connect(str(self.receipt_db))
                rows2 = conn.execute(
                    f"SELECT {receiver_col}, COUNT(*) as cnt "
                    f"FROM {receipt_table} WHERE {receiver_col} IS NOT NULL "
                    f"GROUP BY {receiver_col}"
                ).fetchall()
                conn.close()
                for row in rows2:
                    rid = str(row[0])
                    if rid and rid not in ("None", "null", ""):
                        if rid not in profiles:
                            profiles[rid] = AgentTrustProfile(agent_id=rid)
                        received = int(row[1])
                        profiles[rid].recv_deliveries += received
                        profiles[rid].delivered += received
                        profiles[rid].total_receipts += received
            except Exception:
                pass

        return profiles

    # ─── Payment parsing ──────────────────────────────────────────────────────

    def _load_payments(self, profiles: Dict[str, AgentTrustProfile]):
        if not self.payment_db:
            return

        tables = self._tables(self.payment_db)
        if "payment_channels" in tables:
            return self._load_payment_channels(profiles)

        payment_table = None
        for candidate in ["payments", "settlements", "payment_records", "transactions"]:
            if candidate in tables:
                payment_table = candidate
                break
        if not payment_table:
            return

        cols = self._columns(self.payment_db, payment_table)
        agent_col  = self._pick_col(["agent_id","sender_id","from_agent","payer"], cols)
        status_col = self._pick_col(["status","settlement_status","state"], cols)
        if not agent_col:
            return

        select = [agent_col]
        if status_col:
            select.append(status_col)

        try:
            conn = sqlite3.connect(str(self.payment_db))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT {', '.join(select)} FROM {payment_table} LIMIT 10000"
            ).fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"Payment query failed: {e}")
            return

        for row in rows:
            aid = str(row[agent_col])
            if not aid or aid in ("None", "null", ""):
                continue
            if aid not in profiles:
                profiles[aid] = AgentTrustProfile(agent_id=aid)
            p = profiles[aid]
            p.payments_attempted += 1
            if status_col:
                status = str(row[status_col]).lower()
                if any(x in status for x in ("settled", "success", "completed", "paid")):
                    p.payments_settled += 1
            else:
                p.payments_settled += 1   # no status col → assume settled

    def _load_payment_channels(self, profiles: Dict[str, AgentTrustProfile]):
        try:
            conn = sqlite3.connect(str(self.payment_db))
            rows = conn.execute("SELECT data FROM payment_channels").fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"Payment channel query failed: {e}")
            return

        import json

        for (raw_data,) in rows:
            try:
                data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            except Exception:
                continue

            state = str(data.get("state", "")).lower()
            initiator_id = data.get("initiator_id")
            counterparty_id = data.get("counterparty_id")
            total_capacity = float(data.get("total_capacity") or 0.0)
            initiator_balance = float(data.get("initiator_balance") or 0.0)
            counterparty_balance = float(data.get("counterparty_balance") or 0.0)
            sequence = int(data.get("sequence") or 0)

            for agent_id, balance in (
                (initiator_id, initiator_balance),
                (counterparty_id, counterparty_balance),
            ):
                if not agent_id:
                    continue
                if agent_id not in profiles:
                    profiles[agent_id] = AgentTrustProfile(agent_id=agent_id)
                profile = profiles[agent_id]
                profile.payments_attempted += 1
                if state == "open":
                    profile.payments_settled += 1
                    profile.open_channels += 1
                    profile.total_htlcs += sequence
                    ratio = (balance / total_capacity) if total_capacity > 0 else 0.0
                    profile.balance_ratio = max(profile.balance_ratio, ratio)

    # ─── Scoring ──────────────────────────────────────────────────────────────

    def _score_profile(self, p: AgentTrustProfile) -> float:
        now = time.time()
        p.total_receipts = p.sent_deliveries + p.recv_deliveries

        receipt_norm = min(p.total_receipts / 20.0, 1.0)
        p.receipt_score = round(receipt_norm * MAX_SCORE, 3)

        if p.open_channels > 0:
            channel_norm = min(p.open_channels / 2.0, 1.0)
            htlc_norm = min(p.total_htlcs / 20.0, 1.0)
            balance_norm = min(max(p.balance_ratio, 0.0), 1.0)
            payment_norm = min((0.45 * channel_norm) + (0.30 * htlc_norm) + (0.25 * balance_norm), 1.0)
        elif p.payments_attempted > 0:
            payment_norm = p.payments_settled / max(p.payments_attempted, 1)
        else:
            payment_norm = 0.0
        p.payment_score = round(payment_norm * MAX_SCORE, 3)

        if p.avg_latency_ms > 0:
            s_response = max(0.0, min(1.0, 1000.0 / max(p.avg_latency_ms, 1.0)))
        else:
            s_response = 0.5

        if p.last_seen_ts:
            age_hours = (now - p.last_seen_ts) / 3600
            s_recency = max(0.0, 1.0 - (age_hours / RECENCY_WINDOW_HOURS))
        else:
            s_recency = 0.0

        raw = (
            (p.receipt_score / MAX_SCORE) * 0.65 +
            (p.payment_score / MAX_SCORE) * 0.25 +
            s_response * 0.05 +
            s_recency * 0.05
        )

        p.raw_score = raw
        p.score = round(min(max(raw * MAX_SCORE, 0.0), MAX_SCORE), 3)
        p.breakdown = {
            "receipt_score": p.receipt_score,
            "payment_score": p.payment_score,
            "response_time": round(s_response, 3),
            "recency": round(s_recency, 3),
            "total_receipts": p.total_receipts,
            "sent_deliveries": p.sent_deliveries,
            "recv_deliveries": p.recv_deliveries,
            "open_channels": p.open_channels,
            "total_htlcs": p.total_htlcs,
            "balance_ratio": round(p.balance_ratio, 3),
            "avg_latency_ms": round(p.avg_latency_ms, 1),
        }
        return p.score

    # ─── Public API ───────────────────────────────────────────────────────────

    def compute(self) -> Dict[str, AgentTrustProfile]:
        """Recompute all trust profiles from DB."""
        profiles = self._load_receipts()
        self._load_payments(profiles)
        for p in profiles.values():
            self._score_profile(p)
        self._profiles = profiles
        self._score_cache = {}
        self._computed_at = time.time()
        return profiles

    def get_scores(self, recompute: bool = False) -> Dict[str, float]:
        """Return {agent_id: score} dict. Recomputes if stale."""
        if recompute or not self._profiles or (
            self._computed_at and time.time() - self._computed_at > self._ttl
        ):
            self.compute()
        return {aid: p.score for aid, p in self._profiles.items()}

    def get_profile(self, agent_id: str) -> Optional[AgentTrustProfile]:
        if not self._profiles:
            self.compute()
        return self._profiles.get(agent_id)

    def top_agents(self, n: int = 5) -> List[Tuple[str, float]]:
        scores = self.get_scores()
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]

    def score_for(self, agent_id: str) -> float:
        """Fast lookup — returns 2.5 (neutral) if agent unknown."""
        if not self._profiles:
            self.compute()
        p = self._profiles.get(agent_id)
        return p.score if p else 2.5

    def _profile_to_trust_score(self, profile: AgentTrustProfile) -> TrustScore:
        return TrustScore(
            agent_id=profile.agent_id,
            trust_score=profile.score,
            receipt_score=profile.receipt_score,
            payment_score=profile.payment_score,
            sent_deliveries=profile.sent_deliveries,
            recv_deliveries=profile.recv_deliveries,
            open_channels=profile.open_channels,
            total_htlcs=profile.total_htlcs,
            balance_ratio=profile.balance_ratio,
        )

    def score(self, agent_id: str) -> TrustScore:
        if not self._profiles:
            self.compute()
        elif self._computed_at and time.time() - self._computed_at > self._ttl:
            self.compute()

        cached = self._score_cache.get(agent_id)
        if cached is not None:
            return cached

        profile = self._profiles.get(agent_id)
        score = self._profile_to_trust_score(profile) if profile is not None else TrustScore(agent_id=agent_id, trust_score=1.0)
        self._score_cache[agent_id] = score
        return score

    def score_all_known(self) -> List[TrustScore]:
        """Return TrustScore objects for all known agents. Compatibility method for TrustGraph."""
        if not self._profiles:
            self.compute()
        elif self._computed_at and time.time() - self._computed_at > self._ttl:
            self.compute()
        scores = [self.score(profile.agent_id) for profile in self._profiles.values()]
        return sorted(scores, key=lambda score: score.trust_score, reverse=True)


# ─── Singleton factory ──────────────────────────────────────────────────────

def get_trust_scorer() -> TrustScorer:
    """Return the process-level TrustScorer singleton."""
    if not hasattr(get_trust_scorer, "_instance"):
        get_trust_scorer._instance = TrustScorer()
    return get_trust_scorer._instance


# ─── Router integration patch ────────────────────────────────────────────────
# Call this once after importing SimpleIntentMeshRouter to wire trust weighting.

def patch_router_with_trust(router, scorer: Optional[TrustScorer] = None):
    """
    Monkey-patch SimpleIntentMeshRouter to weight agent selection by trust score.

    Usage (in broker startup):
        from simp.mesh.trust_scorer import TrustScorer, patch_router_with_trust
        scorer = TrustScorer()
        patch_router_with_trust(broker.mesh_routing.mesh_router, scorer)
    """
    if scorer is None:
        scorer = TrustScorer()

    original_find = router._find_agent_for_intent_type

    def trust_weighted_find(intent_type: str, exclude: list = None):
        candidates = original_find(intent_type, exclude)
        if not candidates:
            return candidates
        # Sort by trust score descending
        scores = scorer.get_scores()
        candidates.sort(key=lambda aid: scores.get(aid, 2.5), reverse=True)
        return candidates

    router._find_agent_for_intent_type = trust_weighted_find
    logger.info("Router patched with trust-weighted agent selection")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

    scorer = TrustScorer()
    profiles = scorer.compute()

    print(f"\n{'='*60}")
    print(f"  SIMP TRUST SCORES — {len(profiles)} agents")
    print(f"{'='*60}")

    for aid, p in sorted(profiles.items(), key=lambda x: x[1].score, reverse=True):
        bar = "█" * int(p.score) + "░" * (5 - int(p.score))
        print(f"  {aid:<35} [{bar}] {p.score:.2f}/5.0")
        print(f"    receipts={p.total_receipts}  "
              f"delivery={p.breakdown.get('delivery_rate',0):.0%}  "
              f"latency={p.breakdown.get('avg_latency_ms',0):.0f}ms  "
              f"payments={p.payments_settled}/{p.payments_attempted}")

    print(f"\n  Top 3: {scorer.top_agents(3)}")
