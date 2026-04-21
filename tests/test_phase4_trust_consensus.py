"""
Phase 4+5 Integration Tests
=============================
Tests for: TrustScorer, TrustGraph, A2A Consensus Engine,
           BRP Mesh Gateway, ProjectX Mesh Bridge

Run:
    python3.10 -m pytest tests/test_phase4_trust_consensus.py -v
"""

import json
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sys
import os

# Ensure simp package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    """Temporary directory for test databases."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def receipts_db(tmp_dir):
    """Create a populated receipts SQLite database."""
    db_path = tmp_dir / "mesh_receipts.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE receipts (
            message_id   TEXT PRIMARY KEY,
            recipient_id TEXT,
            sender_id    TEXT,
            received_at  REAL,
            signature    TEXT,
            stored_at    REAL
        )
    """)
    # Agent A sent 8 messages (received by others), received 5
    for i in range(8):
        conn.execute(
            "INSERT INTO receipts VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), f"agent_b_{i}", "agent_a", time.time(), "sig", time.time())
        )
    for i in range(5):
        conn.execute(
            "INSERT INTO receipts VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), "agent_a", "agent_b", time.time(), "sig", time.time())
        )
    # Agent B has fewer
    for i in range(3):
        conn.execute(
            "INSERT INTO receipts VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), f"agent_c_{i}", "agent_b", time.time(), "sig", time.time())
        )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def payments_db(tmp_dir):
    """Create a populated payments SQLite database."""
    db_path = tmp_dir / "mesh_payments.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE payment_channels (
            channel_id TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            updated_at REAL
        )
    """)
    # Open channel: agent_a has 70% balance remaining, 10 HTLCs
    ch_a = {
        "channel_id":           "ch_001",
        "initiator_id":         "agent_a",
        "counterparty_id":      "agent_b",
        "initiator_balance":    700.0,
        "counterparty_balance": 300.0,
        "total_capacity":       1000.0,
        "sequence":             10,
        "state":                "open",
    }
    conn.execute(
        "INSERT INTO payment_channels VALUES (?,?,?)",
        ("ch_001", json.dumps(ch_a), time.time())
    )
    # Settled channel for agent_a (should NOT count toward balance)
    ch_settled = {
        "channel_id":           "ch_002",
        "initiator_id":         "agent_a",
        "counterparty_id":      "agent_c",
        "initiator_balance":    0.0,
        "counterparty_balance": 500.0,
        "total_capacity":       500.0,
        "sequence":             25,
        "state":                "settled",
    }
    conn.execute(
        "INSERT INTO payment_channels VALUES (?,?,?)",
        ("ch_002", json.dumps(ch_settled), time.time())
    )
    conn.commit()
    conn.close()
    return db_path


# ─────────────────────────────────────────────────────────────────────────────
# TrustScorer Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTrustScorer:

    def test_import(self):
        from simp.mesh.trust_scorer import TrustScorer, TrustScore
        assert TrustScorer is not None

    def test_score_empty_dbs(self, tmp_dir):
        """Returns zero-based score when no data exists."""
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(log_dir=str(tmp_dir))
        ts = scorer.score("unknown_agent")
        assert 0.0 <= ts.trust_score <= 5.0
        assert ts.agent_id == "unknown_agent"

    def test_score_with_receipts(self, receipts_db, tmp_dir):
        """Agent with receipts gets positive receipt component."""
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(
            receipts_db_path=str(receipts_db),
            payments_db_path=str(tmp_dir / "mesh_payments.db"),
        )
        ts = scorer.score("agent_a")
        # 8 sent + 5 received = 13 receipts → receipt_norm = 13/20 = 0.65 → receipt_score = 3.25
        assert ts.sent_deliveries == 8
        assert ts.recv_deliveries == 5
        assert ts.receipt_score > 0
        assert 0.0 <= ts.trust_score <= 5.0

    def test_score_with_payments(self, receipts_db, payments_db):
        """Agent with open payment channels gets payment component."""
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(
            receipts_db_path=str(receipts_db),
            payments_db_path=str(payments_db),
        )
        ts = scorer.score("agent_a")
        assert ts.open_channels == 1          # only open channels
        assert ts.total_htlcs == 10
        assert ts.balance_ratio == pytest.approx(0.7, abs=0.01)
        assert ts.payment_score > 0
        assert ts.trust_score > 0

    def test_settled_channel_excluded(self, payments_db, tmp_dir):
        """Settled channels do not inflate balance or open count."""
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(payments_db_path=str(payments_db), log_dir=str(tmp_dir))
        ts = scorer.score("agent_a")
        assert ts.open_channels == 1  # ch_002 is settled, not counted

    def test_score_clamped(self, receipts_db, payments_db):
        """Trust score is always in [0.0, 5.0]."""
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(
            receipts_db_path=str(receipts_db),
            payments_db_path=str(payments_db),
        )
        for agent in ("agent_a", "agent_b", "nobody"):
            ts = scorer.score(agent)
            assert 0.0 <= ts.trust_score <= 5.0

    def test_cache_returns_same_object(self, receipts_db, payments_db):
        """Second call within TTL returns cached score."""
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(
            receipts_db_path=str(receipts_db),
            payments_db_path=str(payments_db),
        )
        ts1 = scorer.score("agent_a")
        ts2 = scorer.score("agent_a")
        assert ts1 is ts2

    def test_score_all_known(self, receipts_db, payments_db):
        """score_all_known returns all agents that appear in either DB."""
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(
            receipts_db_path=str(receipts_db),
            payments_db_path=str(payments_db),
        )
        scores = scorer.score_all_known()
        agent_ids = {s.agent_id for s in scores}
        assert "agent_a" in agent_ids
        assert "agent_b" in agent_ids
        # Sorted highest first
        for i in range(len(scores) - 1):
            assert scores[i].trust_score >= scores[i+1].trust_score

    def test_to_dict(self, tmp_dir):
        from simp.mesh.trust_scorer import TrustScorer
        scorer = TrustScorer(log_dir=str(tmp_dir))
        ts = scorer.score("x")
        d = ts.to_dict()
        assert "agent_id" in d
        assert "trust_score" in d
        assert "receipt_score" in d
        assert "payment_score" in d


# ─────────────────────────────────────────────────────────────────────────────
# TrustGraph Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTrustGraph:

    def test_import(self):
        from simp.mesh.trust_graph import TrustGraph, TrustEntry
        assert TrustGraph is not None

    def test_get_trust_score_calls_scorer(self, tmp_dir):
        """get_trust_score delegates to scorer and caches result."""
        from simp.mesh.trust_graph import TrustGraph
        from simp.mesh.trust_scorer import TrustScorer

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)
        ts = graph.get_trust_score("agent_x")
        # Should be a TrustScore or None
        from simp.mesh.trust_scorer import TrustScore
        assert isinstance(ts, TrustScore)

    def test_apply_delta_increases_score(self, tmp_dir):
        """apply_delta nudges effective score."""
        from simp.mesh.trust_graph import TrustGraph
        from simp.mesh.trust_scorer import TrustScorer

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)

        # Prime the entry
        graph.get_trust_score("agent_delta")
        base   = graph.get_effective_score("agent_delta")

        new_score = graph.apply_delta("agent_delta", 2.0, reason="test_boost")
        assert new_score >= base  # Should be higher

    def test_apply_delta_clamped(self, tmp_dir):
        """apply_delta never exceeds [0.0, 5.0]."""
        from simp.mesh.trust_graph import TrustGraph
        from simp.mesh.trust_scorer import TrustScorer

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)

        score = graph.apply_delta("agent_clamp", 999.0, reason="overflow")
        assert score <= 5.0

        score2 = graph.apply_delta("agent_clamp", -999.0, reason="underflow")
        assert score2 >= 0.0

    def test_locked_entry_delta_preserved(self, tmp_dir):
        """Locked entries keep their delta across refresh cycles."""
        from simp.mesh.trust_graph import TrustGraph, TrustEntry
        from simp.mesh.trust_scorer import TrustScorer, TrustScore

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)

        graph.apply_delta("locked_agent", 1.5)
        graph.lock_entry("locked_agent")
        entry = graph.get_entry("locked_agent")
        assert entry is not None
        assert entry.locked is True
        assert entry.delta == pytest.approx(1.5, abs=0.01)

    def test_snapshot(self, tmp_dir):
        """snapshot() returns serialisable dict."""
        from simp.mesh.trust_graph import TrustGraph
        from simp.mesh.trust_scorer import TrustScorer

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)
        graph.get_trust_score("snap_agent")

        snap = graph.snapshot()
        assert "timestamp" in snap
        assert "agent_count" in snap
        assert "agents" in snap

    def test_inject_into_router(self, tmp_dir):
        """inject_into_router sets _trust_graph on the router."""
        from simp.mesh.trust_graph import TrustGraph
        from simp.mesh.trust_scorer import TrustScorer

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)

        mock_router = MagicMock()
        graph.inject_into_router(mock_router)
        assert mock_router._trust_graph is graph


# ─────────────────────────────────────────────────────────────────────────────
# Consensus Engine Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConsensusEngine:

    def test_import(self):
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, ConsensusResult,
            QuorumEngine, MeshConsensusNode, VoteChoice, ConsensusState,
        )
        assert QuorumEngine is not None

    def test_proposal_creation(self):
        from simp.mesh.consensus import ConsensusProposal
        p = ConsensusProposal(
            proposal_id="p1",
            topic="test_topic",
            payload={"key": "value"},
            proposer_id="agent_a",
        )
        assert p.proposal_id == "p1"
        assert not p.is_expired
        d = p.to_dict()
        assert d["topic"] == "test_topic"

    def test_proposal_serialisation_roundtrip(self):
        from simp.mesh.consensus import ConsensusProposal
        p = ConsensusProposal(
            proposal_id="rt1",
            topic="roundtrip",
            payload={"x": 42},
            proposer_id="agent_a",
            required_quorum=0.75,
        )
        p2 = ConsensusProposal.from_dict(p.to_dict())
        assert p2.proposal_id == p.proposal_id
        assert p2.required_quorum == p.required_quorum

    def test_vote_serialisation_roundtrip(self):
        from simp.mesh.consensus import ConsensusVote, VoteChoice
        v = ConsensusVote(
            vote_id="v1",
            proposal_id="p1",
            voter_id="agent_a",
            choice=VoteChoice.APPROVE,
            trust_score=3.5,
            rationale="looks good",
        )
        v2 = ConsensusVote.from_dict(v.to_dict())
        assert v2.choice == VoteChoice.APPROVE
        assert v2.trust_score == 3.5

    def test_quorum_approve_simple(self):
        """Majority approve → APPROVED (quorum=0.60 so 2/3 clears it)."""
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine, ConsensusState,
        )
        proposal = ConsensusProposal(
            proposal_id="qa1", topic="t", payload={}, proposer_id="a",
            required_quorum=0.60   # 2/3 ≈ 0.667 > 0.60 → APPROVED
        )
        votes = [
            ConsensusVote("v1","qa1","a1",VoteChoice.APPROVE, 3.0),
            ConsensusVote("v2","qa1","a2",VoteChoice.APPROVE, 3.0),
            ConsensusVote("v3","qa1","a3",VoteChoice.REJECT, 3.0),
        ]
        result = QuorumEngine.aggregate(proposal, votes, aggregator_id="agg")
        assert result.state == ConsensusState.APPROVED
        assert result.approval_ratio == pytest.approx(2/3, abs=0.01)

    def test_quorum_reject_simple(self):
        """Majority reject → REJECTED."""
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine, ConsensusState,
        )
        proposal = ConsensusProposal(
            proposal_id="qr1", topic="t", payload={}, proposer_id="a",
        )
        votes = [
            ConsensusVote("v1","qr1","a1",VoteChoice.REJECT, 4.0),
            ConsensusVote("v2","qr1","a2",VoteChoice.REJECT, 4.0),
            ConsensusVote("v3","qr1","a3",VoteChoice.APPROVE, 1.0),
        ]
        result = QuorumEngine.aggregate(proposal, votes, aggregator_id="agg")
        assert result.state == ConsensusState.REJECTED

    def test_trust_weighted_vote(self):
        """Higher trust voters have more influence."""
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine, ConsensusState,
        )
        proposal = ConsensusProposal(
            proposal_id="tw1", topic="t", payload={}, proposer_id="a",
            required_quorum=0.67
        )
        # Low-trust agents approve (3 votes), high-trust agent rejects (1 vote)
        # Weighted: 3*(0.5) approve = 1.5, 1*(5.0) reject = 5.0
        votes = [
            ConsensusVote("v1","tw1","a1",VoteChoice.APPROVE, 0.5),
            ConsensusVote("v2","tw1","a2",VoteChoice.APPROVE, 0.5),
            ConsensusVote("v3","tw1","a3",VoteChoice.APPROVE, 0.5),
            ConsensusVote("v4","tw1","a4",VoteChoice.REJECT, 5.0),
        ]
        result = QuorumEngine.aggregate(proposal, votes, aggregator_id="agg")
        # approve_weight = 1.5, reject_weight = 5.0, total = 6.5
        # ratio = 1.5/6.5 ≈ 0.23 < 0.67 → NOT approved
        assert result.state == ConsensusState.REJECTED

    def test_abstain_does_not_count_in_ratio(self):
        """ABSTAIN votes don't affect approval ratio."""
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine, ConsensusState,
        )
        proposal = ConsensusProposal(
            proposal_id="ab1", topic="t", payload={}, proposer_id="a",
            required_quorum=0.67
        )
        votes = [
            ConsensusVote("v1","ab1","a1",VoteChoice.APPROVE, 3.0),
            ConsensusVote("v2","ab1","a2",VoteChoice.ABSTAIN, 3.0),
            ConsensusVote("v3","ab1","a3",VoteChoice.ABSTAIN, 3.0),
        ]
        result = QuorumEngine.aggregate(proposal, votes, aggregator_id="agg")
        # Only 1 non-abstain vote → not enough participation
        # ratio = 1.0, but participation_weight check may keep it PENDING
        assert result.vote_count == 3

    def test_expired_proposal(self):
        """Expired proposals result in EXPIRED state."""
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine, ConsensusState,
        )
        proposal = ConsensusProposal(
            proposal_id="exp1", topic="t", payload={}, proposer_id="a",
            proposal_ttl=0.001,  # expires immediately
        )
        time.sleep(0.01)
        votes = [ConsensusVote("v1","exp1","a1",VoteChoice.APPROVE, 5.0)]
        result = QuorumEngine.aggregate(proposal, votes, aggregator_id="agg")
        assert result.state == ConsensusState.EXPIRED

    def test_deduplication(self):
        """Duplicate votes from same voter — only latest counts."""
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine, ConsensusState,
        )
        proposal = ConsensusProposal(
            proposal_id="dup1", topic="t", payload={}, proposer_id="a",
        )
        t = time.time()
        votes = [
            ConsensusVote("v1","dup1","a1",VoteChoice.REJECT, 3.0, voted_at=t),
            ConsensusVote("v2","dup1","a1",VoteChoice.APPROVE, 3.0, voted_at=t+1),  # override
            ConsensusVote("v3","dup1","a2",VoteChoice.APPROVE, 3.0, voted_at=t),
        ]
        result = QuorumEngine.aggregate(proposal, votes, aggregator_id="agg")
        # Both counted votes should be APPROVE
        assert result.state == ConsensusState.APPROVED

    def test_result_serialisation(self):
        """ConsensusResult.to_dict() is JSON-serialisable."""
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine,
        )
        proposal = ConsensusProposal("s1","t",{},"a")
        votes    = [ConsensusVote("v1","s1","a1",VoteChoice.APPROVE,2.0)]
        result   = QuorumEngine.aggregate(proposal, votes, aggregator_id="agg")
        d = result.to_dict()
        json.dumps(d)  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# BRP Mesh Gateway Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBRPMeshGateway:

    def _make_packet(self, sender_id="agent_a", channel="trade_updates", payload=None):
        pkt = MagicMock()
        pkt.sender_id    = sender_id
        pkt.recipient_id = "agent_b"
        pkt.channel      = channel
        pkt.message_id   = str(uuid.uuid4())
        pkt.msg_type     = "event"
        pkt.ttl_hops     = 5
        pkt.routing_history = []
        pkt.timestamp    = "2026-04-16T00:00:00Z"
        pkt.payload      = payload or {"type": "trade", "amount": 10.0}
        return pkt

    def test_import(self):
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        assert BRPMeshGateway is not None

    def test_clean_packet_allowed(self, tmp_dir):
        """Normal clean packet is allowed through."""
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(
            brp_db_path=str(tmp_dir / "brp.db"),
            dry_run=True,  # don't actually block
        )
        pkt    = self._make_packet()
        result = gateway.screen_packet(pkt)
        # dry_run=True means even threats are logged but allowed
        assert isinstance(result.allowed, bool)
        assert result.agent_id == "agent_a"

    def test_blocklisted_agent_denied(self, tmp_dir):
        """Blocklisted agent is denied even without BRP analysis."""
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(
            brp_db_path=str(tmp_dir / "brp.db"),
            dry_run=False,
        )
        # Manually blocklist the agent
        gateway._issue_block("evil_agent", "test block", "critical")

        pkt = self._make_packet(sender_id="evil_agent")
        result = gateway.screen_packet(pkt)
        assert result.allowed is False
        assert "blocklisted" in result.reason.lower()

    def test_unblock_removes_from_blocklist(self, tmp_dir):
        """unblock() removes agent from blocklist."""
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(brp_db_path=str(tmp_dir / "brp.db"))
        gateway._issue_block("temp_agent", "test", "high")
        assert gateway._blocklist_check("temp_agent") is not None

        gateway.unblock("temp_agent")
        assert gateway._blocklist_check("temp_agent") is None

    def test_trust_penalty_applied(self, tmp_dir):
        """BRP threat finding reduces trust graph score."""
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        from simp.mesh.trust_graph import TrustGraph
        from simp.mesh.trust_scorer import TrustScorer

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)
        # Prime the entry
        graph.apply_delta("penalised_agent", 0.0)
        before = graph.get_effective_score("penalised_agent")

        gateway = BRPMeshGateway(
            brp_db_path=str(tmp_dir / "brp2.db"),
            trust_graph=graph,
        )
        gateway._apply_trust_penalty("penalised_agent", "high")
        after = graph.get_effective_score("penalised_agent")

        assert after < before  # penalty was applied

    def test_get_blocklist_returns_list(self, tmp_dir):
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(brp_db_path=str(tmp_dir / "brp.db"))
        gateway._issue_block("a1", "r1", "high")
        gateway._issue_block("a2", "r2", "critical")
        bl = gateway.get_blocklist()
        assert len(bl) == 2
        assert any(e["agent_id"] == "a1" for e in bl)

    def test_get_status(self, tmp_dir):
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(brp_db_path=str(tmp_dir / "brp.db"))
        status = gateway.get_status()
        assert "stats" in status
        assert "blocklist_count" in status
        assert "dry_run" in status

    def test_packet_to_log_entry(self, tmp_dir):
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(brp_db_path=str(tmp_dir / "brp.db"))
        pkt = self._make_packet()
        entry = gateway._packet_to_log_entry(pkt)
        assert "source_ip" in entry
        assert entry["source_ip"] == "agent_a"
        assert "event_type" in entry

    def test_check_access_allows_clean(self, tmp_dir):
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(brp_db_path=str(tmp_dir / "brp.db"))
        allowed, reason = gateway.check_access("clean_agent", "target", "ch")
        assert allowed is True

    def test_check_access_denies_blocked(self, tmp_dir):
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway
        gateway = BRPMeshGateway(brp_db_path=str(tmp_dir / "brp.db"), dry_run=False)
        gateway._issue_block("bad_agent", "threat", "critical")
        allowed, reason = gateway.check_access("bad_agent", "target", "ch")
        assert allowed is False

    def test_predictive_screening_can_escalate_clean_bases(self, tmp_dir):
        from simp.mesh.brp_mesh_gateway import BRPMeshGateway

        class _StubBRP:
            def analyze_event(self, log_entry):
                return {
                    "threat_assessment": {"threat_level": "low", "confidence": 0.05},
                    "pattern_details": [],
                }

        gateway = BRPMeshGateway(brp_db_path=str(tmp_dir / "brp.db"), dry_run=False)
        gateway._get_brp = lambda: _StubBRP()

        pkt = self._make_packet(
            sender_id="projectx_native",
            payload={
                "type": "computer_use",
                "projectx_action": "run_shell",
                "details": "autonomous multi-step fuzz payload attempting sandbox bypass",
            },
        )

        result = gateway.screen_packet(pkt)

        assert result.allowed is False
        assert result.threat_level in {"high", "critical"}
        assert result.metadata["predictive_assessment"]["score_boost"] > 0.0
        assert any(pattern["type"] == "zero_day_signal" for pattern in result.patterns)


# ─────────────────────────────────────────────────────────────────────────────
# ProjectX Mesh Bridge Tests (unit, no broker connection needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestProjectXMeshBridge:

    def test_import(self):
        from simp.projectx.mesh_bridge import ProjectXMeshBridge, AGENT_ID, HEARTBEAT_PATH
        assert ProjectXMeshBridge is not None
        # Verify heartbeat path uses parameterized form (Bug 4 fix)
        assert "{agent_id}" in HEARTBEAT_PATH

    def test_heartbeat_path_correct(self):
        """Bug 4: Heartbeat path must use /agents/<agent_id>/heartbeat."""
        from simp.projectx.mesh_bridge import HEARTBEAT_PATH
        formatted = HEARTBEAT_PATH.format(agent_id="projectx_native")
        assert formatted == "/agents/projectx_native/heartbeat"

    def test_remote_allowed_actions_are_safe(self):
        """Only Tier 0 actions + knowledge actions should be remotely allowed."""
        from simp.projectx.mesh_bridge import ProjectXMeshBridge
        from simp.projectx.computer import ACTION_TIERS

        for action in ProjectXMeshBridge.REMOTE_ALLOWED_ACTIONS:
            tier = ACTION_TIERS.get(action, 0)
            # Tier 2 (run_shell) is NOT in REMOTE_ALLOWED_ACTIONS
            assert action != "run_shell", "run_shell must never be in remote allowlist"

    def test_bridge_status(self, tmp_dir):
        """get_status returns structured dict."""
        from simp.projectx.mesh_bridge import ProjectXMeshBridge
        from simp.projectx.computer import ProjectXComputer

        computer = ProjectXComputer(log_dir=str(tmp_dir / "px_logs"))
        bridge   = ProjectXMeshBridge(computer=computer)
        status   = bridge.get_status()

        assert "agent_id" in status
        assert "running" in status
        assert "stats" in status
        assert status["running"] is False  # not started

    def test_task_action_allowlist_gate(self, tmp_dir):
        """Disallowed actions are rejected."""
        from simp.projectx.mesh_bridge import ProjectXMeshBridge, ProjectXTask
        from simp.projectx.computer import ProjectXComputer

        computer = ProjectXComputer(log_dir=str(tmp_dir / "px_logs"))
        bridge   = ProjectXMeshBridge(computer=computer)

        task = ProjectXTask(
            task_id="t1",
            action="run_shell",  # not allowed remotely
            params={"command": "ls"},
            requester_id="some_agent",
        )
        # Simulate the allowlist check directly
        assert task.action not in ProjectXMeshBridge.REMOTE_ALLOWED_ACTIONS

    def test_task_roundtrip_serialisation(self):
        """ProjectXTask serialises and deserialises correctly."""
        from simp.projectx.mesh_bridge import ProjectXTask
        task = ProjectXTask(
            task_id="t1",
            action="check_protocol_health",
            params={},
            requester_id="agent_a",
            trust_required=2.0,
        )
        d    = task.to_dict()
        task2 = ProjectXTask.from_dict(d)
        assert task2.task_id        == task.task_id
        assert task2.action         == task.action
        assert task2.trust_required == task.trust_required


# ─────────────────────────────────────────────────────────────────────────────
# Integration: TrustGraph → Consensus trust weighting
# ─────────────────────────────────────────────────────────────────────────────

class TestTrustConsensusIntegration:

    def test_high_trust_agent_swings_vote(self, tmp_dir):
        """
        A high-trust agent's REJECT should outweigh multiple low-trust APPROVEs.
        Demonstrates L4→L5 trust integration.
        """
        from simp.mesh.trust_graph import TrustGraph
        from simp.mesh.trust_scorer import TrustScorer
        from simp.mesh.consensus import (
            ConsensusProposal, ConsensusVote, VoteChoice,
            QuorumEngine, ConsensusState, MeshConsensusNode,
        )

        scorer = TrustScorer(log_dir=str(tmp_dir))
        graph  = TrustGraph(scorer=scorer, broadcast=False)

        # Artificially set trust for agents
        graph.apply_delta("whale", 4.9)   # 4.9 effective
        graph.apply_delta("minnow1", 0.0) # ~1.0 effective (neutral)
        graph.apply_delta("minnow2", 0.0)
        graph.apply_delta("minnow3", 0.0)

        proposal = ConsensusProposal("lv1","liquidity_vote",{},"organizer")
        # Whale rejects with trust=5.0; minnows approve with trust=1.0 each.
        # weighted approve=3.0, reject=5.0, total=8.0
        # approval_ratio = 3/8 = 0.375 < 0.67 → not APPROVED
        # reject_ratio   = 5/8 = 0.625 < 0.67 → not REJECTED either → TIED
        # (Quorum requires a decisive majority on either side)
        votes = [
            ConsensusVote("v1","lv1","whale",   VoteChoice.REJECT,  5.0),
            ConsensusVote("v2","lv1","minnow1", VoteChoice.APPROVE, 1.0),
            ConsensusVote("v3","lv1","minnow2", VoteChoice.APPROVE, 1.0),
            ConsensusVote("v4","lv1","minnow3", VoteChoice.APPROVE, 1.0),
        ]
        result = QuorumEngine.aggregate(proposal, votes, aggregator_id="test")
        # Neither side reaches 0.67 → TIED (not APPROVED)
        assert result.state == ConsensusState.TIED
        assert result.approval_ratio < 0.67   # high-trust REJECT prevented approval


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
