"""Tests for simp.compat.approval_queue — Sprint 43."""

import json
import os
import tempfile
import pytest
from simp.compat.approval_queue import (
    ApprovalQueue,
    PaymentProposal,
    PaymentProposalStatus,
    PolicyChangeQueue,
    PolicyChangeRecord,
)


@pytest.fixture
def tmp_ledger(tmp_path):
    return str(tmp_path / "test_proposals.jsonl")


@pytest.fixture
def queue(tmp_ledger):
    return ApprovalQueue(ledger_path=tmp_ledger)


@pytest.fixture
def policy_queue(tmp_path):
    return PolicyChangeQueue(ledger_path=str(tmp_path / "test_policy.jsonl"))


# ---------------------------------------------------------------------------
# ApprovalQueue — submit
# ---------------------------------------------------------------------------

class TestApprovalQueueSubmit:
    def test_submit_creates_pending(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 10.0, "Test", "stripe_small_payments")
        assert p.status == PaymentProposalStatus.PENDING
        assert p.vendor == "github"
        assert p.would_spend == 10.0
        assert p.proposal_id

    def test_submit_risk_flags_high_value(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 12.0, "Test", "stripe_small_payments")
        assert "high_value" in p.risk_flags

    def test_submit_risk_flags_near_limit(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 18.0, "Test", "stripe_small_payments")
        assert "near_daily_limit" in p.risk_flags

    def test_submit_risk_flags_new_vendor(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        assert "new_vendor" in p.risk_flags
        # Second submission with same vendor: no new_vendor flag
        p2 = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test2", "stripe_small_payments")
        assert "new_vendor" not in p2.risk_flags

    def test_submit_sets_expires_at(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        assert p.expires_at is not None

    def test_submit_persists_to_jsonl(self, queue, tmp_ledger):
        queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        with open(tmp_ledger) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "proposal_created"


# ---------------------------------------------------------------------------
# ApprovalQueue — approve / reject
# ---------------------------------------------------------------------------

class TestApprovalQueueApproveReject:
    def test_approve_pending(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        ok, err = queue.approve_proposal(p.proposal_id, "operator-1")
        assert ok is True
        assert err is None

    def test_approve_sets_status(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        queue.approve_proposal(p.proposal_id, "operator-1")
        fetched = queue.get_proposal(p.proposal_id)
        assert fetched.status == PaymentProposalStatus.APPROVED
        assert fetched.approved_by == "operator-1"

    def test_approve_nonexistent(self, queue):
        ok, err = queue.approve_proposal("no-such-id", "operator-1")
        assert ok is False
        assert "not found" in err

    def test_approve_already_approved(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        queue.approve_proposal(p.proposal_id, "operator-1")
        ok, err = queue.approve_proposal(p.proposal_id, "operator-2")
        assert ok is False
        assert "already" in err.lower()

    def test_reject_pending(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        ok, err = queue.reject_proposal(p.proposal_id, "operator-1", "Too expensive")
        assert ok is True

    def test_reject_sets_status(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        queue.reject_proposal(p.proposal_id, "operator-1", "Too expensive")
        fetched = queue.get_proposal(p.proposal_id)
        assert fetched.status == PaymentProposalStatus.REJECTED
        assert fetched.rejected_by == "operator-1"
        assert fetched.rejection_reason == "Too expensive"

    def test_reject_nonexistent(self, queue):
        ok, err = queue.reject_proposal("no-such-id", "operator-1", "reason")
        assert ok is False

    def test_cannot_reject_approved(self, queue):
        p = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test", "stripe_small_payments")
        queue.approve_proposal(p.proposal_id, "operator-1")
        ok, err = queue.reject_proposal(p.proposal_id, "operator-2", "Changed mind")
        assert ok is False


# ---------------------------------------------------------------------------
# ApprovalQueue — listing
# ---------------------------------------------------------------------------

class TestApprovalQueueListing:
    def test_get_pending(self, queue):
        p1 = queue.submit_proposal("agent-1", "github", "software_subscription", 5.0, "Test1", "stripe_small_payments")
        p2 = queue.submit_proposal("agent-1", "aws", "software_subscription", 8.0, "Test2", "stripe_small_payments")
        queue.approve_proposal(p1.proposal_id, "operator-1")
        pending = queue.get_pending_proposals()
        assert len(pending) == 1
        assert pending[0].proposal_id == p2.proposal_id

    def test_get_all(self, queue):
        for i in range(5):
            queue.submit_proposal("agent-1", f"vendor-{i}", "software_subscription", 5.0, f"Test{i}", "stripe_small_payments")
        all_p = queue.get_all_proposals()
        assert len(all_p) == 5

    def test_get_all_respects_limit(self, queue):
        for i in range(10):
            queue.submit_proposal("agent-1", f"vendor-{i}", "software_subscription", 5.0, f"Test{i}", "stripe_small_payments")
        all_p = queue.get_all_proposals(limit=3)
        assert len(all_p) == 3


# ---------------------------------------------------------------------------
# PolicyChangeQueue
# ---------------------------------------------------------------------------

class TestPolicyChangeQueue:
    def test_submit(self, policy_queue):
        r = policy_queue.submit_policy_change("Raise limit to $50", "admin-1")
        assert r.change_id
        assert r.status == "pending"
        assert r.requested_by == "admin-1"

    def test_first_approval(self, policy_queue):
        r = policy_queue.submit_policy_change("Raise limit", "admin-1")
        ok, msg = policy_queue.approve_policy_change(r.change_id, "approver-1")
        assert ok is True
        assert "First approval" in msg

    def test_second_approval_different_operator(self, policy_queue):
        r = policy_queue.submit_policy_change("Raise limit", "admin-1")
        policy_queue.approve_policy_change(r.change_id, "approver-1")
        ok, msg = policy_queue.approve_policy_change(r.change_id, "approver-2")
        assert ok is True
        assert "Second approval" in msg

    def test_same_operator_cannot_approve_twice(self, policy_queue):
        r = policy_queue.submit_policy_change("Raise limit", "admin-1")
        policy_queue.approve_policy_change(r.change_id, "approver-1")
        ok, msg = policy_queue.approve_policy_change(r.change_id, "approver-1")
        assert ok is False
        assert "Same operator" in msg

    def test_get_record(self, policy_queue):
        r = policy_queue.submit_policy_change("Test change", "admin-1")
        policy_queue.approve_policy_change(r.change_id, "approver-1")
        fetched = policy_queue.get_record(r.change_id)
        assert fetched.status == "partially_approved"
        assert fetched.first_approval_by == "approver-1"

    def test_fully_approved_status(self, policy_queue):
        r = policy_queue.submit_policy_change("Test change", "admin-1")
        policy_queue.approve_policy_change(r.change_id, "approver-1")
        policy_queue.approve_policy_change(r.change_id, "approver-2")
        fetched = policy_queue.get_record(r.change_id)
        assert fetched.status == "approved"

    def test_nonexistent_change(self, policy_queue):
        ok, msg = policy_queue.approve_policy_change("no-such-id", "approver-1")
        assert ok is False
        assert "not found" in msg.lower()
