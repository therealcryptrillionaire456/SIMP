"""Tests for Sprint 42 — Connector Health Tracking and Dry-Run Ledger."""

import json
import os
import pytest

from simp.compat.payment_connector import (
    ConnectorHealthTracker,
    StubPaymentConnector,
    PaymentConnectorConfig,
    build_connector,
    HEALTH_TRACKER,
)
from simp.compat.ops_policy import (
    SpendRecord,
    SimulatedSpendLedger,
    SPEND_LEDGER,
)


class TestConnectorHealthTracking:
    def test_new_tracker_empty(self):
        t = ConnectorHealthTracker()
        s = t.get_status()
        assert s["total_checks"] == 0

    def test_record_multiple_ok(self):
        t = ConnectorHealthTracker()
        t.record_check("stripe_small_payments", "ok")
        t.record_check("stripe_small_payments", "ok")
        assert t.consecutive_ok_days("stripe_small_payments") == 2

    def test_failure_resets_count(self):
        t = ConnectorHealthTracker()
        t.record_check("c1", "ok")
        t.record_check("c1", "ok")
        t.record_check("c1", "degraded")
        assert t.consecutive_ok_days("c1") == 0

    def test_gate1_requires_3(self):
        t = ConnectorHealthTracker()
        t.record_check("c1", "ok")
        t.record_check("c1", "ok")
        assert t.is_gate1_ready("c1") is False
        t.record_check("c1", "ok")
        assert t.is_gate1_ready("c1") is True

    def test_multiple_connectors_independent(self):
        t = ConnectorHealthTracker()
        t.record_check("a", "ok")
        t.record_check("b", "degraded")
        assert t.consecutive_ok_days("a") == 1
        assert t.consecutive_ok_days("b") == 0

    def test_status_has_last_check(self):
        t = ConnectorHealthTracker()
        t.record_check("x", "ok")
        s = t.get_status()
        assert s["last_check"]["connector"] == "x"
        assert s["last_check"]["status"] == "ok"


class TestSpendRecordDryRunFields:
    def test_dry_run_fields_default_none(self):
        r = SpendRecord()
        assert r.dry_run_result is None
        assert r.connector_used is None
        assert r.dry_run_reference_id is None

    def test_to_dict_includes_dry_run_fields(self):
        r = SpendRecord(dry_run_result="success", connector_used="stripe_small_payments")
        d = r.to_dict()
        assert d["dry_run_result"] == "success"
        assert d["connector_used"] == "stripe_small_payments"


class TestSimulatedSpendLedgerDryRun:
    def test_record_with_dry_run(self):
        ledger = SimulatedSpendLedger()
        rec = ledger.record_with_dry_run(
            agent_id="test",
            description="test buy",
            would_spend=5.0,
            connector_name="stripe_small_payments",
            dry_run_result="success",
            dry_run_reference_id="dry-abc123",
        )
        assert rec.connector_used == "stripe_small_payments"
        assert rec.dry_run_result == "success"
        assert rec.dry_run_reference_id == "dry-abc123"
        assert rec.status == "simulated"

    def test_record_appears_in_ledger(self):
        ledger = SimulatedSpendLedger()
        ledger.record_with_dry_run(
            agent_id="test", description="buy", would_spend=10.0,
            connector_name="c1", dry_run_result="ok", dry_run_reference_id="ref-1",
        )
        records = ledger.get_ledger()
        assert len(records) == 1
        assert records[0].would_spend == 10.0

    def test_ledger_summary_counts_dry_run(self):
        ledger = SimulatedSpendLedger()
        ledger.record_with_dry_run("a", "d", 3.0, "c", "ok", "r1")
        ledger.record_with_dry_run("a", "d", 7.0, "c", "ok", "r2")
        s = ledger.get_ledger_summary()
        assert s["total_would_spend"] == 10.0
        assert s["count"] == 2


class TestHealthCheckRoute:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_connector_health_endpoint(self, client):
        resp = client.get("/a2a/agents/financial-ops/connector-health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "total_checks" in data


class TestStubConnectorHealthIntegration:
    def test_stub_health_check_ok(self):
        conn = StubPaymentConnector()
        h = conn.health_check()
        assert h["status"] == "ok"

    def test_dry_run_payment_and_record(self):
        ledger = SimulatedSpendLedger()
        conn = StubPaymentConnector()
        result = conn.execute_small_payment(8.0, "Acme", "test")
        rec = ledger.record_with_dry_run(
            agent_id="test",
            description="Acme purchase",
            would_spend=8.0,
            connector_name=conn.config.name,
            dry_run_result="success" if result.success else "failed",
            dry_run_reference_id=result.reference_id,
        )
        assert rec.dry_run_result == "success"
        assert rec.dry_run_reference_id.startswith("dry-")
