"""Tests for Sprint 45 — Reconciliation, Payment Events, and Observability."""

import json
import os
import pytest
from unittest.mock import patch

from simp.compat.reconciliation import (
    ReconciliationResult,
    run_reconciliation,
)
from simp.compat.live_ledger import LiveSpendLedger, LivePaymentRecord
from simp.compat.event_stream import (
    build_payment_event,
    PAYMENT_EVENT_KINDS,
)


class TestReconciliationResult:
    def test_auto_id(self):
        r = ReconciliationResult()
        assert len(r.run_id) > 0

    def test_auto_timestamp(self):
        r = ReconciliationResult()
        assert r.run_at != ""

    def test_to_dict(self):
        r = ReconciliationResult(status="matched", live_ledger_total=100.0)
        d = r.to_dict()
        assert d["status"] == "matched"
        assert d["live_ledger_total"] == 100.0


class TestRunReconciliation:
    @pytest.fixture
    def ledger(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        return LiveSpendLedger(filepath=filepath)

    def test_no_reference_total(self, ledger):
        with patch("simp.compat.reconciliation.LIVE_LEDGER", ledger):
            result = run_reconciliation("2000-01-01", "2099-12-31")
            assert result.status == "reference_unavailable"
            assert result.live_ledger_total == 0.0

    def test_matched(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "succeeded", "ref123")
        with patch("simp.compat.reconciliation.LIVE_LEDGER", ledger):
            result = run_reconciliation("2000-01-01", "2099-12-31", reference_total=10.0)
            assert result.status == "matched"
            assert abs(result.discrepancy) <= 0.01

    def test_discrepancy(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "succeeded", "ref123")
        with patch("simp.compat.reconciliation.LIVE_LEDGER", ledger):
            result = run_reconciliation("2000-01-01", "2099-12-31", reference_total=15.0)
            assert result.status == "discrepancy"
            assert result.discrepancy == -5.0

    def test_flags_failed_payments(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "failed", error="timeout")
        with patch("simp.compat.reconciliation.LIVE_LEDGER", ledger):
            result = run_reconciliation("2000-01-01", "2099-12-31")
            assert len(result.flagged_records) == 1
            assert "failed_payment" in result.flagged_records[0]["flags"]

    def test_flags_pending_payments(self, ledger):
        ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        # No outcome recorded — still pending
        with patch("simp.compat.reconciliation.LIVE_LEDGER", ledger):
            result = run_reconciliation("2000-01-01", "2099-12-31")
            assert len(result.flagged_records) == 1
            assert "still_pending" in result.flagged_records[0]["flags"]

    def test_never_modifies_ledger(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "succeeded", "ref")
        count_before = len(ledger.get_all_records())
        with patch("simp.compat.reconciliation.LIVE_LEDGER", ledger):
            run_reconciliation("2000-01-01", "2099-12-31", reference_total=10.0)
        count_after = len(ledger.get_all_records())
        assert count_before == count_after

    def test_period_filtering(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "succeeded", "ref")
        with patch("simp.compat.reconciliation.LIVE_LEDGER", ledger):
            result = run_reconciliation("3000-01-01", "3099-12-31", reference_total=0.0)
            assert result.live_ledger_total == 0.0
            assert result.status == "matched"


class TestPaymentEventKinds:
    def test_all_kinds_present(self):
        expected = {"proposal_created", "approval_granted", "execution_started", "execution_succeeded", "execution_failed"}
        assert PAYMENT_EVENT_KINDS == expected


class TestBuildPaymentEvent:
    def test_proposal_created(self):
        e = build_payment_event("proposal_created", "p1", amount=10.0, vendor="Acme")
        assert e["eventKind"] == "proposal_created"
        assert e["x-simp"]["proposal_id"] == "p1"
        assert e["x-simp"]["amount"] == 10.0

    def test_execution_succeeded(self):
        e = build_payment_event("execution_succeeded", "p1", amount=5.0, status="succeeded")
        assert e["eventKind"] == "execution_succeeded"

    def test_execution_failed_with_error(self):
        e = build_payment_event("execution_failed", "p1", error="connection timeout")
        assert "error" in e
        assert e["error"] == "connection timeout"

    def test_error_truncated(self):
        long_error = "x" * 300
        e = build_payment_event("execution_failed", "p1", error=long_error)
        assert len(e["error"]) <= 204  # 200 + "..."

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            build_payment_event("unknown_kind", "p1")

    def test_no_pan_in_event(self):
        e = build_payment_event("execution_succeeded", "p1", vendor="Acme")
        raw = str(e)
        assert "4111" not in raw
        assert "credit_card" not in raw

    def test_timestamp_present(self):
        e = build_payment_event("proposal_created", "p1")
        assert "timestamp" in e


class TestObservabilityRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_ledger_route(self, client):
        resp = client.get("/a2a/agents/financial-ops/ledger")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "simulated" in data
        assert "live" in data

    def test_reconciliation_route(self, client):
        resp = client.post(
            "/a2a/agents/financial-ops/reconciliation",
            data=json.dumps({"period_start": "2000-01-01", "period_end": "2099-12-31"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] in ("matched", "discrepancy", "reference_unavailable")

    def test_export_route(self, client):
        resp = client.get("/a2a/agents/financial-ops/export")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "records" in data
        assert "count" in data

    def test_export_safe_fields_only(self, client):
        resp = client.get("/a2a/agents/financial-ops/export")
        data = json.loads(resp.data)
        # Each record should only have safe fields
        for r in data.get("records", []):
            allowed = {"proposal_id", "vendor", "category", "amount", "status", "submitted_at"}
            assert set(r.keys()).issubset(allowed)
