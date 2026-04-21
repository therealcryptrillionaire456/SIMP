"""
TrustGraph — SIMP Layer 4 (Reputation/Trust Graph)
===================================================
Wraps TrustScorer into a live, self-refreshing trust graph that:

  1. Maintains cached [0.0–5.0] scores for all known agents
  2. Runs a background refresh thread (default: every 60 s)
  3. Broadcasts trust score updates to the mesh on channel 'trust_updates'
  4. Provides a drop-in injection point for SimpleIntentMeshRouter:
       score = trust_graph.get_trust_score(agent_id)
  5. Exposes delta-update API: apply_delta(agent_id, delta) lets BRP and
     other systems nudge scores without a full DB read.

Wire-up in SimpleIntentMeshRouter._find_agent_for_intent_type():
    from .trust_graph import get_trust_graph
    ts = get_trust_graph().get_trust_score(agent_id)
    score = ts.trust_score if ts else ad.reputation_score
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .trust_scorer import TrustScore, TrustScorer, get_trust_scorer

logger = logging.getLogger(__name__)

# How often the background thread refreshes all scores (seconds)
DEFAULT_REFRESH_INTERVAL = 60.0

# Absolute floor/ceiling for delta-nudged scores
SCORE_MIN = 0.0
SCORE_MAX = 5.0


@dataclass
class TrustEntry:
    """
    Live trust entry combining the DB-sourced TrustScore with any
    runtime delta adjustments (e.g. from BRP threat analysis).
    """
    base:          TrustScore          # last computed from DB
    delta:         float = 0.0        # cumulative runtime adjustment
    locked:        bool  = False       # if True, delta cannot be cleared on refresh
    updated_at:    float = field(default_factory=time.time)

    @property
    def effective_score(self) -> float:
        """Clamped combined score."""
        return min(max(self.base.trust_score + self.delta, SCORE_MIN), SCORE_MAX)

    def apply_delta(self, d: float) -> None:
        self.delta = min(max(self.delta + d, -SCORE_MAX), SCORE_MAX)
        self.updated_at = time.time()

    def to_dict(self) -> Dict:
        d = self.base.to_dict()
        d["delta"]           = round(self.delta, 4)
        d["effective_score"] = round(self.effective_score, 4)
        d["locked"]          = self.locked
        d["entry_updated"]   = self.updated_at
        return d


class TrustGraph:
    """
    Live trust graph for the SIMP mesh.

    All public methods are thread-safe.
    """

    def __init__(
        self,
        scorer:           Optional[TrustScorer] = None,
        refresh_interval: float = DEFAULT_REFRESH_INTERVAL,
        broadcast:        bool  = True,
    ):
        """
        Parameters
        ----------
        scorer:
            TrustScorer instance.  Defaults to the process singleton.
        refresh_interval:
            Seconds between background score refreshes.
        broadcast:
            If True, push trust_update packets to the mesh bus on each refresh.
        """
        self._scorer           = scorer or get_trust_scorer()
        self._refresh_interval = refresh_interval
        self._broadcast        = broadcast
        self._entries:         Dict[str, TrustEntry] = {}
        self._lock             = threading.RLock()
        self._refresh_thread:  Optional[threading.Thread] = None
        self._running          = False

        logger.info("[TrustGraph] initialized (refresh=%.0fs broadcast=%s)", refresh_interval, broadcast)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background refresh loop."""
        with self._lock:
            if self._running:
                return
            self._running = True

        # Seed with an immediate full refresh
        self._refresh_all()

        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            daemon=True,
            name="TrustGraphRefresh",
        )
        self._refresh_thread.start()
        logger.info("[TrustGraph] refresh thread started")

    def stop(self) -> None:
        """Stop background refresh loop."""
        with self._lock:
            self._running = False

        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
            self._refresh_thread = None

        logger.info("[TrustGraph] stopped")

    # ── Public read API ───────────────────────────────────────────────────────

    def get_trust_score(self, agent_id: str) -> Optional[TrustScore]:
        """
        Return the latest TrustScore for *agent_id*, triggering a fresh
        computation if the cached value is stale.

        Returns None only if the agent is entirely unknown (no receipts, no
        payment channels) and the databases are unreachable.
        """
        with self._lock:
            entry = self._entries.get(agent_id)

        # Cache miss or stale base — recompute
        if entry is None or entry.base.is_stale():
            fresh = self._scorer.score(agent_id)
            with self._lock:
                if agent_id in self._entries:
                    self._entries[agent_id].base = fresh
                    self._entries[agent_id].updated_at = time.time()
                else:
                    self._entries[agent_id] = TrustEntry(base=fresh)
            return fresh

        return entry.base

    def get_effective_score(self, agent_id: str) -> float:
        """
        Return the *effective* trust score including any runtime deltas.
        Returns 1.0 (neutral) for unknown agents.
        """
        with self._lock:
            entry = self._entries.get(agent_id)
        if entry is None:
            # Try to compute
            fresh = self._scorer.score(agent_id)
            with self._lock:
                self._entries[agent_id] = TrustEntry(base=fresh)
            return fresh.trust_score
        return entry.effective_score

    def get_entry(self, agent_id: str) -> Optional[TrustEntry]:
        with self._lock:
            return self._entries.get(agent_id)

    def all_entries(self) -> List[TrustEntry]:
        with self._lock:
            return list(self._entries.values())

    # ── Delta (runtime adjustments) ───────────────────────────────────────────

    def apply_delta(self, agent_id: str, delta: float, reason: str = "") -> float:
        """
        Nudge *agent_id*'s effective trust score by *delta*.
        Called by BRP gateway, consensus engine, etc.

        Returns the new effective score.
        """
        with self._lock:
            if agent_id not in self._entries:
                # Create a placeholder entry with score=1.0 (neutral)
                placeholder = TrustScore(
                    agent_id      = agent_id,
                    trust_score   = 1.0,
                    receipt_score = 0.0,
                    payment_score = 0.0,
                    sent_deliveries = 0,
                    recv_deliveries = 0,
                    open_channels   = 0,
                    total_htlcs     = 0,
                    balance_ratio   = 0.0,
                )
                self._entries[agent_id] = TrustEntry(base=placeholder)

            entry = self._entries[agent_id]
            entry.apply_delta(delta)
            new_score = entry.effective_score

        logger.debug(
            "[TrustGraph] delta %.3f applied to %s (reason=%s) → effective=%.3f",
            delta, agent_id, reason, new_score,
        )
        return new_score

    def lock_entry(self, agent_id: str) -> None:
        """Lock an entry so refresh won't clear runtime deltas."""
        with self._lock:
            if agent_id in self._entries:
                self._entries[agent_id].locked = True

    def unlock_entry(self, agent_id: str) -> None:
        with self._lock:
            if agent_id in self._entries:
                self._entries[agent_id].locked = False

    def inject_into_router(self, router) -> None:
        """
        Attach this TrustGraph to a SimpleIntentMeshRouter so that
        _find_agent_for_intent_type() uses live trust scores.

        router._trust_graph is set; the router checks it if present.
        """
        router._trust_graph = self
        logger.info("[TrustGraph] injected into router %s", getattr(router, 'local_agent_id', '?'))

    # ── Serialisation ─────────────────────────────────────────────────────────

    def snapshot(self) -> Dict:
        """Return a full serialisable snapshot of the trust graph."""
        with self._lock:
            entries = {aid: e.to_dict() for aid, e in self._entries.items()}
        return {
            "timestamp":     time.time(),
            "agent_count":   len(entries),
            "refresh_interval": self._refresh_interval,
            "agents":        entries,
        }

    # ── Background refresh ────────────────────────────────────────────────────

    def _refresh_loop(self) -> None:
        while self._running:
            time.sleep(self._refresh_interval)
            if not self._running:
                break
            try:
                self._refresh_all()
            except Exception as exc:
                logger.error("[TrustGraph] refresh loop error: %s", exc)

    def _refresh_all(self) -> None:
        """Recompute scores for all known agents."""
        try:
            fresh_scores = self._scorer.score_all_known()
        except Exception as exc:
            logger.warning("[TrustGraph] score_all_known failed: %s", exc)
            return

        broadcast_updates = []

        with self._lock:
            for ts in fresh_scores:
                existing = self._entries.get(ts.agent_id)
                if existing:
                    existing.base = ts
                    existing.updated_at = time.time()
                    # Clear runtime delta only if not locked
                    if not existing.locked:
                        existing.delta = 0.0
                else:
                    self._entries[ts.agent_id] = TrustEntry(base=ts)

                if self._broadcast:
                    broadcast_updates.append(ts.to_dict())

        if broadcast_updates:
            self._broadcast_updates(broadcast_updates)

        logger.debug("[TrustGraph] refreshed %d agent scores", len(fresh_scores))

    def _broadcast_updates(self, updates: list) -> None:
        """Send trust_updates to the mesh bus."""
        try:
            from .enhanced_bus import get_enhanced_mesh_bus
            from .packet import create_event_packet, Priority

            bus = get_enhanced_mesh_bus()
            pkt = create_event_packet(
                sender_id    = "trust_graph",
                recipient_id = "*",
                channel      = "trust_updates",
                payload      = {"trust_scores": updates, "timestamp": time.time()},
                ttl_seconds  = 120,
            )
            bus.send(pkt)
        except Exception as exc:
            logger.debug("[TrustGraph] broadcast failed (bus may not be ready): %s", exc)


# ── SimpleIntentMeshRouter patch ──────────────────────────────────────────────

def patch_router_with_trust_graph(router, trust_graph: Optional[TrustGraph] = None) -> None:
    """
    Monkey-patch SimpleIntentMeshRouter._find_agent_for_intent_type to
    use live trust scores from the TrustGraph.

    Call this once after creating the router:
        router = SimpleIntentMeshRouter(...)
        patch_router_with_trust_graph(router)
    """
    graph = trust_graph or get_trust_graph()
    graph.inject_into_router(router)

    import time as _time

    def _patched_find(self, intent_type: str):
        with self._capabilities_lock:
            suitable_agents = []

            for agent_id, ad in self._capabilities.items():
                if intent_type not in ad.capabilities:
                    continue

                # L4: prefer live trust score over static reputation_score
                tg = getattr(self, '_trust_graph', None)
                if tg is not None:
                    score = tg.get_effective_score(agent_id)
                else:
                    score = ad.reputation_score

                # Penalise stale agents
                offline_time = _time.time() - ad.last_seen
                if offline_time > 300:
                    score *= 0.5

                suitable_agents.append((score, offline_time, agent_id))

            if not suitable_agents:
                return None

            suitable_agents.sort(key=lambda x: (-x[0], x[1]))
            return suitable_agents[0][2]

    import types
    router._find_agent_for_intent_type = types.MethodType(_patched_find, router)
    logger.info("[TrustGraph] patched _find_agent_for_intent_type on router")


# ── Singleton factory ─────────────────────────────────────────────────────────

_trust_graph_instance: Optional[TrustGraph] = None
_tg_lock = threading.Lock()


def get_trust_graph(
    scorer:           Optional[TrustScorer] = None,
    refresh_interval: float = DEFAULT_REFRESH_INTERVAL,
    broadcast:        bool  = True,
    autostart:        bool  = True,
) -> TrustGraph:
    """
    Return the process-level TrustGraph singleton.
    Creates and starts it on first call.
    """
    global _trust_graph_instance

    with _tg_lock:
        if _trust_graph_instance is None:
            _trust_graph_instance = TrustGraph(
                scorer           = scorer,
                refresh_interval = refresh_interval,
                broadcast        = broadcast,
            )
            if autostart:
                _trust_graph_instance.start()

    return _trust_graph_instance
