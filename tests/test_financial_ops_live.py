"""Tests for Sprint 44 — Live Ledger and Execution (all use stub connector, NO real API calls)."""

import json
import os
import pytest
from unittest.mock import patch

import simp.compat.approval_queue as aq_mod
import simp.compat.live_ledger as ll_mod
from simp.compat.live_ledger import (
    LivePaymentRecord,
    LiveSpendLedger,
    _abbreviate_reference,
)
from simp.compat.approval_queue import (
    ApprovalQueue,
    PaymentProposalStatus,
)
from simp.compat.financial_ops import execute_approved_payment


class TestLivePaymentRecord:
    def test_auto_id(self):
        r = LivePaymentRecord()
        assert len(r.record_id) > 0

    def test_auto_timestamp(self):
        r = LivePaymentRecord()
        assert r.attempted_at != ""

    def test_to_dict(self):
        r = LivePaymentRecord(vendor="Acme", amount=5.0)
        d = r.to_dict()
        assert d["vendor"] == "Acme"
        assert d["amount"] == 5.0


class TestAbbreviateReference:
    def test_short_ref(self):
        assert _abbreviate_reference("ab") == "ab"

    def test_long_ref(self):
        assert _abbreviate_reference("abcdefghij") == "...ghij"

    def test_empty(self):
        assert _abbreviate_reference("") == ""


class TestLiveSpendLedger:
    @pytest.fixture
    def ledger(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        return LiveSpendLedger(filepath=filepath)

    def test_record_attempt(self, ledger):
        rec = ledger.record_attempt("p1", "key1", "stripe_small_payments", "Acme", "cloud", 10.0)
        assert rec.status == "pending"
        assert rec.proposal_id == "p1"

    def test_record_outcome_succeeded(self, ledger):
        rec = ledger.record_attempt("p1", "key1", "stripe", "Acme", "cloud", 10.0)
        updated = ledger.record_outcome(rec.record_id, "succeeded", "ref-long-string-here")
        assert updated.status == "succeeded"
        assert updated.provider_reference == "...here"

    def test_record_outcome_failed(self, ledger):
        rec = ledger.record_attempt("p1", "key1", "stripe", "Acme", "cloud", 10.0)
        updated = ledger.record_outcome(rec.record_id, "failed", error="timeout")
        assert updated.status == "failed"
        assert updated.error == "timeout"

    def test_idempotency_check(self, ledger):
        assert ledger.is_already_executed("key1") is False
        ledger.record_attempt("p1", "key1", "stripe", "Acme", "cloud", 10.0)
        assert ledger.is_already_executed("key1") is True

    def test_idempotency_prevents_duplicate(self, ledger):
        ledger.record_attempt("p1", "key1", "stripe", "Acme", "cloud", 10.0)
        assert ledger.is_already_executed("key1") is True

    def test_get_summary(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "succeeded", "ref123")
        s = ledger.get_summary()
        assert s["total_live_spend"] == 10.0
        assert s["succeeded"] == 1

    def test_get_summary_empty(self, ledger):
        s = ledger.get_summary()
        assert s["total_live_spend"] == 0.0
        assert s["attempted"] == 0

    def test_get_all_records(self, ledger):
        ledger.record_attempt("p1", "k1", "s", "V", "c", 5.0)
        ledger.record_attempt("p2", "k2", "s", "V", "c", 7.0)
        assert len(ledger.get_all_records()) == 2

    def test_jsonl_persistence(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        l1 = LiveSpendLedger(filepath=filepath)
        rec = l1.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        l1.record_outcome(rec.record_id, "succeeded", "ref-abc")

        l2 = LiveSpendLedger(filepath=filepath)
        assert l2.is_already_executed("k1") is True
        s = l2.get_summary()
        assert s["succeeded"] == 1

    def test_record_outcome_nonexistent_raises(self, ledger):
        with pytest.raises(ValueError, match="not found"):
            ledger.record_outcome("nonexistent", "succeeded")


class TestExecuteApprovedPayment:
    @pytest.fixture
    def setup_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        # Use temp files for queues and ledgers
        proposals_file = str(tmp_path / "proposals.jsonl")
        live_file = str(tmp_path / "live.jsonl")
        return proposals_file, live_file

    def test_live_not_enabled_raises(self, monkeypatch):
        monkeypatch.delenv("FINANCIAL_OPS_LIVE_ENABLED", raising=False)
        with pytest.raises(RuntimeError, match="not enabled"):
            execute_approved_payment("some-id")

    def test_nonexistent_proposal_raises(self, setup_env, monkeypatch):
        from simp.compat.approval_queue import ApprovalQueue
        q = ApprovalQueue(filepath=setup_env[0])
        with patch.object(aq_mod, "APPROVAL_QUEUE", q):
            with pytest.raises(ValueError, match="not found"):
                execute_approved_payment("nonexistent")

    def test_unapproved_proposal_raises(self, setup_env, monkeypatch):
        from simp.compat.approval_queue import ApprovalQueue
        from simp.compat.live_ledger import LiveSpendLedger
        q = ApprovalQueue(filepath=setup_env[0])
        p = q.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        # Proposal is pending, not approved
        with patch.object(aq_mod, "APPROVAL_QUEUE", q):
            with pytest.raises(ValueError, match="not approved"):
                execute_approved_payment(p.proposal_id)

    def test_execute_succeeds_with_stub(self, setup_env, monkeypatch):
        from simp.compat.approval_queue import ApprovalQueue
        from simp.compat.live_ledger import LiveSpendLedger
        q = ApprovalQueue(filepath=setup_env[0])
        ll = LiveSpendLedger(filepath=setup_env[1])
        p = q.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        q.approve_proposal(p.proposal_id, "operator@example.com")

        with patch.object(aq_mod, "APPROVAL_QUEUE", q), \
             patch.object(ll_mod, "LIVE_LEDGER", ll):
            result = execute_approved_payment(p.proposal_id)
            assert result["status"] == "succeeded"
            assert result["proposal_id"] == p.proposal_id

    def test_idempotency_guard(self, setup_env, monkeypatch):
        from simp.compat.approval_queue import ApprovalQueue
        from simp.compat.live_ledger import LiveSpendLedger
        q = ApprovalQueue(filepath=setup_env[0])
        ll = LiveSpendLedger(filepath=setup_env[1])
        p = q.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        q.approve_proposal(p.proposal_id, "operator@example.com")

        with patch.object(aq_mod, "APPROVAL_QUEUE", q), \
             patch.object(ll_mod, "LIVE_LEDGER", ll):
            result1 = execute_approved_payment(p.proposal_id)
            assert result1["status"] == "succeeded"

            # Second call should be idempotent
            result2 = execute_approved_payment(p.proposal_id)
            assert result2["status"] == "already_executed"

    def test_no_double_charge(self, setup_env, monkeypatch):
        from simp.compat.approval_queue import ApprovalQueue
        from simp.compat.live_ledger import LiveSpendLedger
        q = ApprovalQueue(filepath=setup_env[0])
        ll = LiveSpendLedger(filepath=setup_env[1])
        p = q.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        q.approve_proposal(p.proposal_id, "operator@example.com")

        with patch.object(aq_mod, "APPROVAL_QUEUE", q), \
             patch.object(ll_mod, "LIVE_LEDGER", ll):
            execute_approved_payment(p.proposal_id)
            execute_approved_payment(p.proposal_id)
            s = ll.get_summary()
            # Only one attempt should succeed
            assert s["succeeded"] == 1


class TestExecuteRoute:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_execute_returns_403_when_disabled(self, client, monkeypatch):
        monkeypatch.delenv("FINANCIAL_OPS_LIVE_ENABLED", raising=False)
        resp = client.post("/a2a/agents/financial-ops/proposals/test-id/execute")
        assert resp.status_code == 403

    def test_execute_returns_400_for_bad_proposal(self, client, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        resp = client.post("/a2a/agents/financial-ops/proposals/nonexistent/execute")
        assert resp.status_code == 400


class TestNoRealApiCalls:
    def test_stub_never_calls_external(self):
        """Verify StubPaymentConnector doesn't make real API calls."""
        from simp.compat.payment_connector import StubPaymentConnector
        conn = StubPaymentConnector()
        result = conn.execute_small_payment(5.0, "Test", "test")
        assert result.dry_run is True
        assert "STUB" in result.message

    def test_no_credentials_in_code(self):
        """Verify no credentials in source."""
        import simp.compat.payment_connector as mod
        source = open(mod.__file__).read()
        assert "sk-" not in source
        assert "sk_live" not in source
        assert "credit_card" not in source
