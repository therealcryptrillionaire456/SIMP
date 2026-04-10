"""Tests for Sprint 46 — Rollback System."""

import json
import os
import pytest
from unittest.mock import patch

from simp.compat.rollback import (
    RollbackState,
    RollbackRecord,
    RollbackManager,
    LedgerFrozenError,
    ROLLBACK_MANAGER,
)
from simp.compat.live_ledger import LiveSpendLedger


class TestRollbackState:
    def test_active_value(self):
        assert RollbackState.ACTIVE.value == "active"

    def test_inactive_value(self):
        assert RollbackState.INACTIVE.value == "inactive"

    def test_never_live_value(self):
        assert RollbackState.NEVER_LIVE.value == "never_live"


class TestRollbackRecord:
    def test_auto_id(self):
        r = RollbackRecord()
        assert len(r.record_id) > 0

    def test_auto_timestamp(self):
        r = RollbackRecord()
        assert r.timestamp != ""

    def test_to_dict(self):
        r = RollbackRecord(state="active", triggered_by="operator", reason="test")
        d = r.to_dict()
        assert d["state"] == "active"
        assert d["triggered_by"] == "operator"
        assert d["reason"] == "test"


class TestRollbackManager:
    @pytest.fixture
    def manager(self, tmp_path):
        filepath = str(tmp_path / "rollback.jsonl")
        return RollbackManager(filepath=filepath)

    def test_initial_state_never_live(self, manager, monkeypatch):
        monkeypatch.delenv("FINANCIAL_OPS_LIVE_ENABLED", raising=False)
        assert manager.get_state() == RollbackState.NEVER_LIVE

    def test_trigger_rollback(self, manager, monkeypatch):
        monkeypatch.delenv("FINANCIAL_OPS_LIVE_ENABLED", raising=False)
        record = manager.trigger_rollback("admin@test.com", "Emergency rollback")
        assert record.state == RollbackState.ACTIVE.value
        assert record.triggered_by == "admin@test.com"
        assert manager.get_state() == RollbackState.ACTIVE

    def test_deactivate_rollback(self, manager, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        manager.trigger_rollback("admin", "test")
        manager.deactivate_rollback("admin", "resolved")
        assert manager.get_state() == RollbackState.INACTIVE

    def test_state_active_when_live_disabled(self, manager, monkeypatch):
        """When live is disabled and we were previously inactive, state should be ACTIVE."""
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        manager.deactivate_rollback("admin", "was live")
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "false")
        assert manager.get_state() == RollbackState.ACTIVE

    def test_get_rollback_status(self, manager, monkeypatch):
        monkeypatch.delenv("FINANCIAL_OPS_LIVE_ENABLED", raising=False)
        status = manager.get_rollback_status()
        assert "state" in status
        assert "live_enabled" in status
        assert status["live_enabled"] is False

    def test_get_rollback_history_empty(self, manager):
        history = manager.get_rollback_history()
        assert history == []

    def test_get_rollback_history_after_trigger(self, manager):
        manager.trigger_rollback("admin", "test1")
        manager.trigger_rollback("admin", "test2")
        history = manager.get_rollback_history()
        assert len(history) == 2
        # Most recent first
        assert history[0]["reason"] == "test2"

    def test_jsonl_persistence(self, tmp_path):
        filepath = str(tmp_path / "rollback.jsonl")
        m1 = RollbackManager(filepath=filepath)
        m1.trigger_rollback("admin", "persist test")

        m2 = RollbackManager(filepath=filepath)
        history = m2.get_rollback_history()
        assert len(history) == 1
        assert history[0]["reason"] == "persist test"

    def test_rollback_count_in_status(self, manager, monkeypatch):
        monkeypatch.delenv("FINANCIAL_OPS_LIVE_ENABLED", raising=False)
        manager.trigger_rollback("admin", "first")
        manager.trigger_rollback("admin", "second")
        status = manager.get_rollback_status()
        assert status["rollback_count"] == 2


class TestLedgerFreezeUnfreeze:
    @pytest.fixture
    def ledger(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        return LiveSpendLedger(filepath=filepath)

    def test_freeze_blocks_record_attempt(self, ledger):
        ledger.freeze()
        assert ledger.is_frozen() is True
        with pytest.raises(LedgerFrozenError, match="frozen"):
            ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)

    def test_freeze_blocks_record_outcome(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.freeze()
        with pytest.raises(LedgerFrozenError, match="frozen"):
            ledger.record_outcome(rec.record_id, "succeeded")

    def test_unfreeze_allows_writes(self, ledger):
        ledger.freeze()
        ledger.unfreeze()
        assert ledger.is_frozen() is False
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        assert rec.status == "pending"

    def test_initial_not_frozen(self, ledger):
        assert ledger.is_frozen() is False

    def test_freeze_does_not_affect_reads(self, ledger):
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "succeeded")
        ledger.freeze()
        # Reads still work
        summary = ledger.get_summary()
        assert summary["succeeded"] == 1
        records = ledger.get_all_records()
        assert len(records) == 1


class TestExecuteApprovedPaymentRollbackCheck:
    def test_rollback_active_blocks_execution(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        from simp.compat.rollback import RollbackManager
        import simp.compat.rollback as rb_mod
        mgr = RollbackManager(filepath=str(tmp_path / "rb.jsonl"))
        mgr.trigger_rollback("admin", "block test")
        with patch.object(rb_mod, "ROLLBACK_MANAGER", mgr):
            from simp.compat.financial_ops import execute_approved_payment
            with pytest.raises(RuntimeError, match="Rollback is ACTIVE"):
                execute_approved_payment("some-proposal-id")


class TestRollbackRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_rollback_status_route(self, client):
        resp = client.get("/rollback/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "state" in data

    def test_rollback_history_route(self, client):
        resp = client.get("/rollback/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "history" in data

    def test_trigger_rollback_route(self, client):
        resp = client.post("/a2a/agents/financial-ops/rollback",
                          json={"triggered_by": "test", "reason": "test rollback"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "rollback_active"


class TestSingleton:
    def test_rollback_manager_singleton_exists(self):
        assert ROLLBACK_MANAGER is not None
