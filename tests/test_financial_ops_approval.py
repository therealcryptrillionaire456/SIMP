"""Tests for Sprint 43 — Approval Queue."""

import json
import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta

from simp.compat.approval_queue import (
    PaymentProposalStatus,
    PaymentProposal,
    ApprovalQueue,
    PolicyChangeQueue,
    PolicyChangeProposal,
)


class TestPaymentProposalStatus:
    def test_constants(self):
        assert PaymentProposalStatus.PENDING == "pending"
        assert PaymentProposalStatus.APPROVED == "approved"
        assert PaymentProposalStatus.REJECTED == "rejected"
        assert PaymentProposalStatus.EXPIRED == "expired"


class TestPaymentProposal:
    def test_auto_id(self):
        p = PaymentProposal()
        assert len(p.proposal_id) > 0

    def test_auto_timestamp(self):
        p = PaymentProposal()
        assert p.submitted_at != ""

    def test_auto_expiry(self):
        p = PaymentProposal()
        assert p.expires_at != ""

    def test_not_expired(self):
        p = PaymentProposal()
        assert p.is_expired() is False

    def test_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        p = PaymentProposal(expires_at=past)
        assert p.is_expired() is True

    def test_to_dict(self):
        p = PaymentProposal(vendor="Acme", amount=10.0)
        d = p.to_dict()
        assert d["vendor"] == "Acme"
        assert d["amount"] == 10.0


class TestApprovalQueue:
    @pytest.fixture
    def queue(self, tmp_path):
        filepath = str(tmp_path / "proposals.jsonl")
        return ApprovalQueue(filepath=filepath)

    def test_submit_proposal(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 10.0, "stripe_small_payments")
        assert p.status == PaymentProposalStatus.PENDING
        assert p.vendor == "Acme"

    def test_risk_flags_high_amount(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 18.0, "stripe_small_payments")
        assert "high_amount" in p.risk_flags

    def test_risk_flags_missing_category(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "", 5.0, "stripe_small_payments")
        assert "missing_category" in p.risk_flags

    def test_approve_proposal(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        approved = queue.approve_proposal(p.proposal_id, "operator@example.com")
        assert approved.status == PaymentProposalStatus.APPROVED
        assert approved.approved_by == "operator@example.com"

    def test_reject_proposal(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        rejected = queue.reject_proposal(p.proposal_id, "op@example.com", "too risky")
        assert rejected.status == PaymentProposalStatus.REJECTED
        assert rejected.rejection_reason == "too risky"

    def test_approve_nonexistent_raises(self, queue):
        with pytest.raises(ValueError, match="not found"):
            queue.approve_proposal("nonexistent-id", "op@example.com")

    def test_approve_already_approved_raises(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        queue.approve_proposal(p.proposal_id, "op1@example.com")
        with pytest.raises(ValueError, match="not pending"):
            queue.approve_proposal(p.proposal_id, "op2@example.com")

    def test_reject_already_rejected_raises(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        queue.reject_proposal(p.proposal_id, "op1@example.com", "no")
        with pytest.raises(ValueError, match="not pending"):
            queue.reject_proposal(p.proposal_id, "op2@example.com", "also no")

    def test_approve_expired_raises(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        # Force expiry
        p.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with pytest.raises(ValueError, match="expired"):
            queue.approve_proposal(p.proposal_id, "op@example.com")

    def test_get_proposal(self, queue):
        p = queue.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        fetched = queue.get_proposal(p.proposal_id)
        assert fetched is not None
        assert fetched.proposal_id == p.proposal_id

    def test_get_pending_proposals(self, queue):
        queue.submit_proposal("small_purchase", "A", "cloud_infrastructure", 5.0, "stripe_small_payments")
        queue.submit_proposal("small_purchase", "B", "cloud_infrastructure", 5.0, "stripe_small_payments")
        pending = queue.get_pending_proposals()
        assert len(pending) == 2

    def test_get_all_proposals(self, queue):
        p1 = queue.submit_proposal("small_purchase", "A", "cloud_infrastructure", 5.0, "stripe_small_payments")
        p2 = queue.submit_proposal("small_purchase", "B", "cloud_infrastructure", 5.0, "stripe_small_payments")
        queue.approve_proposal(p1.proposal_id, "op@example.com")
        all_p = queue.get_all_proposals()
        assert len(all_p) == 2

    def test_jsonl_persistence(self, tmp_path):
        filepath = str(tmp_path / "proposals.jsonl")
        q1 = ApprovalQueue(filepath=filepath)
        p = q1.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        q1.approve_proposal(p.proposal_id, "op@example.com")

        # Create new queue from same file (event replay)
        q2 = ApprovalQueue(filepath=filepath)
        fetched = q2.get_proposal(p.proposal_id)
        assert fetched is not None
        assert fetched.status == PaymentProposalStatus.APPROVED


class TestPolicyChangeQueue:
    @pytest.fixture
    def queue(self, tmp_path):
        filepath = str(tmp_path / "policy_changes.jsonl")
        return PolicyChangeQueue(filepath=filepath)

    def test_submit_change(self, queue):
        c = queue.submit_change("enable_live", "Enable live payments", "admin@example.com")
        assert c.status == PaymentProposalStatus.PENDING

    def test_dual_control_requires_two_approvers(self, queue):
        c = queue.submit_change("enable_live", "Enable live payments", "admin@example.com")
        # First approver (not the proposer)
        c = queue.approve_change(c.change_id, "approver1@example.com")
        assert c.status == PaymentProposalStatus.PENDING
        assert c.first_approver == "approver1@example.com"

        # Second approver (different from first)
        c = queue.approve_change(c.change_id, "approver2@example.com")
        assert c.status == PaymentProposalStatus.APPROVED
        assert c.second_approver == "approver2@example.com"

    def test_same_operator_cannot_approve_twice(self, queue):
        c = queue.submit_change("enable_live", "Enable live", "admin@example.com")
        queue.approve_change(c.change_id, "approver1@example.com")
        with pytest.raises(ValueError, match="Same operator"):
            queue.approve_change(c.change_id, "approver1@example.com")

    def test_proposer_cannot_be_first_approver(self, queue):
        c = queue.submit_change("enable_live", "Enable live", "admin@example.com")
        with pytest.raises(ValueError, match="Proposer cannot"):
            queue.approve_change(c.change_id, "admin@example.com")

    def test_nonexistent_change_raises(self, queue):
        with pytest.raises(ValueError, match="not found"):
            queue.approve_change("nonexistent", "op@example.com")

    def test_jsonl_persistence(self, tmp_path):
        filepath = str(tmp_path / "policy_changes.jsonl")
        q1 = PolicyChangeQueue(filepath=filepath)
        c = q1.submit_change("enable_live", "Enable live", "admin@example.com")
        q1.approve_change(c.change_id, "approver1@example.com")

        q2 = PolicyChangeQueue(filepath=filepath)
        fetched = q2.get_change(c.change_id)
        assert fetched is not None
        assert fetched.first_approver == "approver1@example.com"


class TestProposalRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_submit_proposal_route(self, client):
        resp = client.post(
            "/a2a/agents/financial-ops/proposals",
            data=json.dumps({
                "op_type": "small_purchase",
                "vendor": "Acme",
                "category": "cloud_infrastructure",
                "amount": 10.0,
                "connector_name": "stripe_small_payments",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data["status"] == "pending"

    def test_list_proposals_route(self, client):
        resp = client.get("/a2a/agents/financial-ops/proposals")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "proposals" in data
