"""
A2A Consensus Engine — SIMP Layer 5 (Distributed Agent-to-Agent Consensus)
===========================================================================
Architecture: "any node can propose, any node can aggregate"

  ConsensusProposal   — broadcast on 'consensus' mesh channel
  ConsensusVote       — broadcast back by each participating agent
  QuorumEngine        — aggregates votes, determines outcomes
  MeshConsensusNode   — high-level API for a participating mesh node

Trust-weighted voting
─────────────────────
Votes are weighted by the voter's L4 trust score (0.0–5.0).
A 5.0-trust voter has 5× the influence of a 1.0-trust voter.
This means the financial equilibrium (who stays solvent) DIRECTLY
determines which proposals pass — no separate governance token needed.

Quorum formula
──────────────
weighted_approve = Σ trust_score(voter) for APPROVE votes
weighted_total   = Σ trust_score(voter) for all non-ABSTAIN votes
quorum_reached   = weighted_approve / weighted_total >= required_quorum (default 0.67)

AND total participating weight >= min_participation_weight (default 5.0)
   (prevents 1-agent quorum with high trust score)

Channels
────────
  consensus_proposals  — proposals (broadcast)
  consensus_votes      — votes (broadcast, any node aggregates)
  consensus_results    — final results (broadcast by aggregator)
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tuning ────────────────────────────────────────────────────────────────────
DEFAULT_QUORUM           = 0.67    # 2/3 weighted approval
DEFAULT_PROPOSAL_TTL     = 300.0   # seconds
MIN_PARTICIPATION_WEIGHT = 5.0     # sum of trust scores of non-abstaining voters
NEUTRAL_TRUST_SCORE      = 1.0     # fallback if trust graph unavailable


class VoteChoice(Enum):
    APPROVE  = "approve"
    REJECT   = "reject"
    ABSTAIN  = "abstain"


class ConsensusState(Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED  = "expired"
    TIED     = "tied"


@dataclass
class ConsensusProposal:
    """A proposal broadcast to the mesh for voting."""
    proposal_id:      str
    topic:            str
    payload:          Dict
    proposer_id:      str
    required_quorum:  float              = DEFAULT_QUORUM
    proposal_ttl:     float              = DEFAULT_PROPOSAL_TTL
    created_at:       float              = field(default_factory=time.time)
    metadata:         Dict               = field(default_factory=dict)

    @property
    def expires_at(self) -> float:
        return self.created_at + self.proposal_ttl

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def canonical_hash(self) -> str:
        """Deterministic content hash for signature verification."""
        data = json.dumps({
            "proposal_id":     self.proposal_id,
            "topic":           self.topic,
            "payload":         self.payload,
            "proposer_id":     self.proposer_id,
            "required_quorum": self.required_quorum,
            "created_at":      self.created_at,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "proposal_id":     self.proposal_id,
            "topic":           self.topic,
            "payload":         self.payload,
            "proposer_id":     self.proposer_id,
            "required_quorum": self.required_quorum,
            "proposal_ttl":    self.proposal_ttl,
            "created_at":      self.created_at,
            "expires_at":      self.expires_at,
            "metadata":        self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> ConsensusProposal:
        return cls(
            proposal_id     = d["proposal_id"],
            topic           = d["topic"],
            payload         = d.get("payload", {}),
            proposer_id     = d["proposer_id"],
            required_quorum = d.get("required_quorum", DEFAULT_QUORUM),
            proposal_ttl    = d.get("proposal_ttl", DEFAULT_PROPOSAL_TTL),
            created_at      = d.get("created_at", time.time()),
            metadata        = d.get("metadata", {}),
        )


@dataclass
class ConsensusVote:
    """A single agent's vote on a proposal."""
    vote_id:      str
    proposal_id:  str
    voter_id:     str
    choice:       VoteChoice
    trust_score:  float               # L4 score at time of voting [0.0–5.0]
    rationale:    str                 = ""
    voted_at:     float               = field(default_factory=time.time)
    signature:    str                 = ""  # optional HMAC

    def to_dict(self) -> Dict:
        return {
            "vote_id":     self.vote_id,
            "proposal_id": self.proposal_id,
            "voter_id":    self.voter_id,
            "choice":      self.choice.value,
            "trust_score": self.trust_score,
            "rationale":   self.rationale,
            "voted_at":    self.voted_at,
            "signature":   self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> ConsensusVote:
        return cls(
            vote_id     = d["vote_id"],
            proposal_id = d["proposal_id"],
            voter_id    = d["voter_id"],
            choice      = VoteChoice(d["choice"]),
            trust_score = d.get("trust_score", NEUTRAL_TRUST_SCORE),
            rationale   = d.get("rationale", ""),
            voted_at    = d.get("voted_at", time.time()),
            signature   = d.get("signature", ""),
        )


@dataclass
class ConsensusResult:
    """Final aggregated result of a proposal."""
    proposal_id:          str
    state:                ConsensusState
    weighted_approve:     float
    weighted_reject:      float
    weighted_total:       float
    participation_weight: float
    vote_count:           int
    votes:                List[ConsensusVote]
    aggregator_id:        str
    decided_at:           float = field(default_factory=time.time)
    required_quorum:      float = DEFAULT_QUORUM

    @property
    def approval_ratio(self) -> float:
        if self.weighted_total <= 0:
            return 0.0
        return self.weighted_approve / self.weighted_total

    def to_dict(self) -> Dict:
        return {
            "proposal_id":          self.proposal_id,
            "state":                self.state.value,
            "approval_ratio":       round(self.approval_ratio, 4),
            "weighted_approve":     round(self.weighted_approve, 4),
            "weighted_reject":      round(self.weighted_reject, 4),
            "weighted_total":       round(self.weighted_total, 4),
            "participation_weight": round(self.participation_weight, 4),
            "required_quorum":      self.required_quorum,
            "vote_count":           self.vote_count,
            "aggregator_id":        self.aggregator_id,
            "decided_at":           self.decided_at,
            "votes":                [v.to_dict() for v in self.votes],
        }


class QuorumEngine:
    """
    Stateless aggregation logic.

    Takes a list of ConsensusVote objects and a ConsensusProposal,
    returns a ConsensusResult.  Designed to be deterministic — any
    node running aggregate() with the same inputs gets the same output.
    """

    @staticmethod
    def aggregate(
        proposal:     ConsensusProposal,
        votes:        List[ConsensusVote],
        aggregator_id: str = "unknown",
    ) -> ConsensusResult:
        """
        Compute consensus result from votes.
        One vote per voter (latest vote wins if duplicates exist).
        """
        # Deduplicate: keep latest vote per voter
        by_voter: Dict[str, ConsensusVote] = {}
        for vote in sorted(votes, key=lambda v: v.voted_at):
            if vote.proposal_id == proposal.proposal_id:
                by_voter[vote.voter_id] = vote

        unique_votes = list(by_voter.values())

        # Trust-weighted tally
        weighted_approve = 0.0
        weighted_reject  = 0.0
        weighted_total   = 0.0
        part_weight      = 0.0

        for vote in unique_votes:
            w = max(vote.trust_score, 0.01)  # floor at 0.01 so every vote counts
            part_weight += w

            if vote.choice == VoteChoice.APPROVE:
                weighted_approve += w
                weighted_total   += w
            elif vote.choice == VoteChoice.REJECT:
                weighted_reject  += w
                weighted_total   += w
            # ABSTAIN counts toward participation but not toward total

        # Determine state
        if proposal.is_expired:
            state = ConsensusState.EXPIRED
        elif len(unique_votes) == 0:
            state = ConsensusState.PENDING
        elif part_weight < MIN_PARTICIPATION_WEIGHT and weighted_total < 1.0:
            # Insufficient participation
            state = ConsensusState.PENDING
        else:
            ratio = weighted_approve / weighted_total if weighted_total > 0 else 0.0

            if ratio >= proposal.required_quorum:
                state = ConsensusState.APPROVED
            elif (1 - ratio) >= proposal.required_quorum:
                state = ConsensusState.REJECTED
            else:
                state = ConsensusState.TIED

        return ConsensusResult(
            proposal_id          = proposal.proposal_id,
            state                = state,
            weighted_approve     = weighted_approve,
            weighted_reject      = weighted_reject,
            weighted_total       = weighted_total,
            participation_weight = part_weight,
            vote_count           = len(unique_votes),
            votes                = unique_votes,
            aggregator_id        = aggregator_id,
            required_quorum      = proposal.required_quorum,
        )


class MeshConsensusNode:
    """
    High-level API for a mesh agent participating in the consensus layer.

    Usage:
        node = MeshConsensusNode(agent_id="quantumarb_mesh")
        node.start()

        # Propose something
        proposal = node.propose(
            topic="reduce_risk_exposure",
            payload={"max_position_usd": 50},
            required_quorum=0.6,
        )

        # Vote on proposals you receive
        node.vote(proposal_id, VoteChoice.APPROVE, rationale="risk params look safe")

        # Get results
        result = node.get_result(proposal_id)
    """

    PROPOSAL_CHANNEL = "consensus_proposals"
    VOTE_CHANNEL     = "consensus_votes"
    RESULT_CHANNEL   = "consensus_results"

    def __init__(
        self,
        agent_id:       str,
        trust_graph=None,
        auto_aggregate: bool  = True,
    ):
        """
        Parameters
        ----------
        agent_id:
            This node's mesh agent ID.
        trust_graph:
            TrustGraph instance for live trust scores.  If None, uses
            NEUTRAL_TRUST_SCORE for all votes (unweighted).
        auto_aggregate:
            If True, automatically re-aggregate and broadcast results when
            enough votes accumulate.
        """
        self.agent_id       = agent_id
        self._trust_graph   = trust_graph
        self._auto_aggregate = auto_aggregate

        self._proposals:    Dict[str, ConsensusProposal]   = {}
        self._votes:        Dict[str, List[ConsensusVote]] = {}   # proposal_id → [votes]
        self._results:      Dict[str, ConsensusResult]     = {}
        self._my_votes:     Dict[str, ConsensusVote]       = {}   # proposal_id → my vote
        self._result_callbacks = []  # callable(ConsensusResult)

        self._lock     = threading.RLock()
        self._running  = False
        self._thread:   Optional[threading.Thread] = None

        logger.info("[ConsensusNode] initialized: %s", agent_id)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Subscribe to consensus channels and start processing."""
        with self._lock:
            if self._running:
                return
            self._running = True

        self._setup_mesh_subscriptions()

        self._thread = threading.Thread(
            target=self._process_loop,
            daemon=True,
            name=f"Consensus-{self.agent_id}",
        )
        self._thread.start()
        logger.info("[ConsensusNode] started: %s", self.agent_id)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[ConsensusNode] stopped: %s", self.agent_id)

    def on_result(self, callback) -> None:
        """Register a callback invoked whenever a consensus result is decided."""
        self._result_callbacks.append(callback)

    # ── Proposal API ──────────────────────────────────────────────────────────

    def propose(
        self,
        topic:           str,
        payload:         Dict,
        required_quorum: float = DEFAULT_QUORUM,
        ttl:             float = DEFAULT_PROPOSAL_TTL,
        metadata:        Optional[Dict] = None,
    ) -> ConsensusProposal:
        """
        Create and broadcast a new proposal.
        Returns the ConsensusProposal object.
        """
        proposal = ConsensusProposal(
            proposal_id     = str(uuid.uuid4()),
            topic           = topic,
            payload         = payload,
            proposer_id     = self.agent_id,
            required_quorum = required_quorum,
            proposal_ttl    = ttl,
            metadata        = metadata or {},
        )

        with self._lock:
            self._proposals[proposal.proposal_id] = proposal
            self._votes[proposal.proposal_id]     = []

        self._broadcast_proposal(proposal)
        logger.info(
            "[ConsensusNode] proposed %s topic=%s quorum=%.0f%%",
            proposal.proposal_id[:8], topic, required_quorum * 100,
        )
        return proposal

    # ── Voting API ────────────────────────────────────────────────────────────

    def vote(
        self,
        proposal_id: str,
        choice:      VoteChoice,
        rationale:   str = "",
    ) -> Optional[ConsensusVote]:
        """
        Cast a vote on *proposal_id*.
        Returns the ConsensusVote or None if proposal unknown/expired.
        """
        with self._lock:
            proposal = self._proposals.get(proposal_id)

        if proposal is None:
            logger.warning("[ConsensusNode] unknown proposal: %s", proposal_id)
            return None

        if proposal.is_expired:
            logger.warning("[ConsensusNode] proposal expired: %s", proposal_id)
            return None

        # Get own trust score
        trust = NEUTRAL_TRUST_SCORE
        if self._trust_graph is not None:
            try:
                trust = self._trust_graph.get_effective_score(self.agent_id)
            except Exception:
                pass

        vote = ConsensusVote(
            vote_id     = str(uuid.uuid4()),
            proposal_id = proposal_id,
            voter_id    = self.agent_id,
            choice      = choice,
            trust_score = trust,
            rationale   = rationale,
        )

        with self._lock:
            self._my_votes[proposal_id] = vote
            self._votes.setdefault(proposal_id, []).append(vote)

        self._broadcast_vote(vote)

        if self._auto_aggregate:
            self._try_aggregate(proposal_id)

        logger.info(
            "[ConsensusNode] voted %s on %s (trust=%.2f)",
            choice.value, proposal_id[:8], trust,
        )
        return vote

    # ── Aggregation ───────────────────────────────────────────────────────────

    def aggregate_now(self, proposal_id: str) -> Optional[ConsensusResult]:
        """
        Manually trigger aggregation for *proposal_id*.
        Broadcasts result if state is final (APPROVED/REJECTED/EXPIRED).
        """
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            votes    = list(self._votes.get(proposal_id, []))

        if proposal is None:
            return None

        result = QuorumEngine.aggregate(proposal, votes, aggregator_id=self.agent_id)

        with self._lock:
            self._results[proposal_id] = result

        if result.state in (ConsensusState.APPROVED, ConsensusState.REJECTED, ConsensusState.EXPIRED):
            self._broadcast_result(result)
            for cb in self._result_callbacks:
                try:
                    cb(result)
                except Exception as exc:
                    logger.error("[ConsensusNode] result callback error: %s", exc)

        return result

    def get_result(self, proposal_id: str) -> Optional[ConsensusResult]:
        """Return cached result, or aggregate on demand."""
        with self._lock:
            result = self._results.get(proposal_id)
        if result:
            return result
        return self.aggregate_now(proposal_id)

    # ── Mesh integration ──────────────────────────────────────────────────────

    def _setup_mesh_subscriptions(self) -> None:
        try:
            from .enhanced_bus import get_enhanced_mesh_bus
            bus = get_enhanced_mesh_bus()
            for ch in (self.PROPOSAL_CHANNEL, self.VOTE_CHANNEL, self.RESULT_CHANNEL):
                bus.subscribe(self.agent_id, ch)
            logger.debug("[ConsensusNode] subscribed to consensus channels")
        except Exception as exc:
            logger.warning("[ConsensusNode] could not subscribe to mesh: %s", exc)

    def _process_loop(self) -> None:
        """Pull consensus messages from mesh bus."""
        while self._running:
            try:
                self._process_mesh_messages()
                self._expire_old_proposals()
                time.sleep(2)
            except Exception as exc:
                logger.error("[ConsensusNode] process loop error: %s", exc)
                time.sleep(5)

    def _process_mesh_messages(self) -> None:
        try:
            from .enhanced_bus import get_enhanced_mesh_bus
            bus     = get_enhanced_mesh_bus()
            packets = bus.receive(self.agent_id, max_messages=20)

            for pkt in packets:
                channel = pkt.channel
                payload = pkt.payload

                if channel == self.PROPOSAL_CHANNEL:
                    self._handle_incoming_proposal(payload)
                elif channel == self.VOTE_CHANNEL:
                    self._handle_incoming_vote(payload)
                elif channel == self.RESULT_CHANNEL:
                    self._handle_incoming_result(payload)

        except Exception as exc:
            logger.debug("[ConsensusNode] mesh receive error: %s", exc)

    def _handle_incoming_proposal(self, payload: Dict) -> None:
        try:
            proposal = ConsensusProposal.from_dict(payload)
            with self._lock:
                if proposal.proposal_id not in self._proposals:
                    self._proposals[proposal.proposal_id] = proposal
                    self._votes[proposal.proposal_id] = []
                    logger.info(
                        "[ConsensusNode] received proposal %s topic=%s from %s",
                        proposal.proposal_id[:8], proposal.topic, proposal.proposer_id,
                    )
        except Exception as exc:
            logger.warning("[ConsensusNode] bad proposal payload: %s", exc)

    def _handle_incoming_vote(self, payload: Dict) -> None:
        try:
            vote = ConsensusVote.from_dict(payload)
            with self._lock:
                if vote.proposal_id in self._proposals:
                    existing = self._votes.setdefault(vote.proposal_id, [])
                    # Deduplicate by voter
                    existing = [v for v in existing if v.voter_id != vote.voter_id]
                    existing.append(vote)
                    self._votes[vote.proposal_id] = existing

            if self._auto_aggregate:
                self._try_aggregate(vote.proposal_id)

        except Exception as exc:
            logger.warning("[ConsensusNode] bad vote payload: %s", exc)

    def _handle_incoming_result(self, payload: Dict) -> None:
        # Just log — we don't override our own aggregation with remote results
        try:
            pid = payload.get("proposal_id", "?")
            state = payload.get("state", "?")
            agg   = payload.get("aggregator_id", "?")
            logger.info(
                "[ConsensusNode] remote result: %s state=%s aggregator=%s",
                pid[:8], state, agg,
            )
        except Exception:
            pass

    def _try_aggregate(self, proposal_id: str) -> None:
        """Aggregate if we haven't already decided."""
        with self._lock:
            if proposal_id in self._results:
                existing = self._results[proposal_id]
                if existing.state in (ConsensusState.APPROVED, ConsensusState.REJECTED):
                    return
        self.aggregate_now(proposal_id)

    def _expire_old_proposals(self) -> None:
        with self._lock:
            for pid, proposal in list(self._proposals.items()):
                if proposal.is_expired and pid not in self._results:
                    pass  # aggregate_now will mark EXPIRED
            # Cleanup results older than 1 hour
            cutoff = time.time() - 3600
            self._results = {
                pid: r for pid, r in self._results.items()
                if r.decided_at > cutoff
            }

    # ── Broadcast helpers ─────────────────────────────────────────────────────

    def _broadcast_proposal(self, proposal: ConsensusProposal) -> None:
        self._send_to_channel(self.PROPOSAL_CHANNEL, proposal.to_dict(), priority="high")

    def _broadcast_vote(self, vote: ConsensusVote) -> None:
        self._send_to_channel(self.VOTE_CHANNEL, vote.to_dict(), priority="normal")

    def _broadcast_result(self, result: ConsensusResult) -> None:
        self._send_to_channel(self.RESULT_CHANNEL, result.to_dict(), priority="high")
        logger.info(
            "[ConsensusNode] broadcast result %s state=%s approval=%.1f%% votes=%d",
            result.proposal_id[:8], result.state.value,
            result.approval_ratio * 100, result.vote_count,
        )

    def _send_to_channel(self, channel: str, payload: Dict, priority: str = "normal") -> None:
        try:
            from .enhanced_bus import get_enhanced_mesh_bus
            from .packet import create_event_packet, Priority

            pmap = {"high": Priority.HIGH, "normal": Priority.NORMAL, "low": Priority.LOW}
            bus  = get_enhanced_mesh_bus()
            pkt  = create_event_packet(
                sender_id    = self.agent_id,
                recipient_id = "*",
                channel      = channel,
                payload      = payload,
                ttl_seconds  = 300,
            )
            pkt.priority = pmap.get(priority, Priority.NORMAL)
            bus.send(pkt)
        except Exception as exc:
            logger.debug("[ConsensusNode] send_to_channel failed: %s", exc)

    # ── Introspection ─────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        with self._lock:
            return {
                "agent_id":        self.agent_id,
                "running":         self._running,
                "proposals":       len(self._proposals),
                "votes_cast":      len(self._my_votes),
                "results_decided": len(self._results),
                "open_proposals":  [
                    {
                        "proposal_id":  pid,
                        "topic":        p.topic,
                        "expires_in":   round(p.expires_at - time.time(), 1),
                        "vote_count":   len(self._votes.get(pid, [])),
                    }
                    for pid, p in self._proposals.items()
                    if not p.is_expired and pid not in self._results
                ],
            }
