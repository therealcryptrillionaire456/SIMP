"""Tests for Sprint 47 — Graduation Gate Manager."""

import os
import pytest

from simp.compat.gate_manager import (
    GateStatus,
    GateCondition,
    GateCheckResult,
    GateManager,
    GATE_MANAGER,
)


class TestGateStatus:
    def test_values(self):
        assert GateStatus.NOT_STARTED.value == "not_started"
        assert GateStatus.IN_PROGRESS.value == "in_progress"
        assert GateStatus.SIGNED_OFF.value == "signed_off"
        assert GateStatus.PROMOTED.value == "promoted"


class TestGateCondition:
    def test_default_values(self):
        c = GateCondition(name="test", description="desc")
        assert c.automated is True
        assert c.met is False

    def test_to_dict(self):
        c = GateCondition(name="test", description="desc", met=True)
        d = c.to_dict()
        assert d["name"] == "test"
        assert d["met"] is True


class TestGateCheckResult:
    def test_auto_timestamp(self):
        r = GateCheckResult(gate=1, status="not_started")
        assert r.timestamp != ""

    def test_to_dict(self):
        r = GateCheckResult(gate=1, status="not_started")
        d = r.to_dict()
        assert d["gate"] == 1


class TestGateManager:
    @pytest.fixture
    def manager(self, tmp_path):
        filepath = str(tmp_path / "gates.jsonl")
        return GateManager(filepath=filepath)

    def test_initial_gate1_not_started(self, manager):
        result = manager.check_gate1()
        assert result.status == GateStatus.NOT_STARTED.value
        assert result.signed_off is False

    def test_initial_gate2_not_started(self, manager):
        result = manager.check_gate2()
        assert result.status == GateStatus.NOT_STARTED.value

    def test_gate1_has_4_conditions(self, manager):
        result = manager.check_gate1()
        assert len(result.conditions) == 4

    def test_gate2_has_7_conditions(self, manager):
        result = manager.check_gate2()
        assert len(result.conditions) == 7

    def test_sign_off_manual_condition(self, manager):
        cond = manager.sign_off_condition(1, "ops_policy_reviewed", "admin@test.com")
        assert cond.met is True
        assert cond.signed_off_by == "admin@test.com"

    def test_sign_off_automated_condition_raises(self, manager):
        with pytest.raises(ValueError, match="automated"):
            manager.sign_off_condition(1, "connector_health_7_days", "admin")

    def test_sign_off_unknown_condition_raises(self, manager):
        with pytest.raises(ValueError, match="Unknown condition"):
            manager.sign_off_condition(1, "nonexistent", "admin")

    def test_mark_automated_condition_met(self, manager):
        cond = manager.mark_condition_met(1, "connector_health_7_days")
        assert cond.met is True

    def test_sign_off_gate_requires_all_automated(self, manager):
        """Cannot sign off gate if automated conditions are not met."""
        # Sign off manual condition
        manager.sign_off_condition(1, "ops_policy_reviewed", "admin")
        # Try to sign off gate — automated conditions not met
        with pytest.raises(ValueError, match="automated conditions not met"):
            manager.sign_off_gate(1, "admin")

    def test_sign_off_gate1_succeeds(self, manager):
        # Meet all conditions
        manager.mark_condition_met(1, "connector_health_7_days")
        manager.mark_condition_met(1, "simulated_payments_20")
        manager.mark_condition_met(1, "no_connector_errors")
        manager.sign_off_condition(1, "ops_policy_reviewed", "admin")
        # Sign off gate
        result = manager.sign_off_gate(1, "admin")
        assert result.signed_off is True
        assert result.status == GateStatus.SIGNED_OFF.value

    def test_gate1_signoff_sets_gate2_condition(self, manager):
        """Gate 1 sign-off should auto-mark gate2.gate1_signed_off."""
        manager.mark_condition_met(1, "connector_health_7_days")
        manager.mark_condition_met(1, "simulated_payments_20")
        manager.mark_condition_met(1, "no_connector_errors")
        manager.sign_off_condition(1, "ops_policy_reviewed", "admin")
        manager.sign_off_gate(1, "admin")

        result = manager.check_gate2()
        gate1_cond = next(c for c in result.conditions if c["name"] == "gate1_signed_off")
        assert gate1_cond["met"] is True

    def test_promote_gate_requires_signoff(self, manager):
        with pytest.raises(ValueError, match="signed off"):
            manager.promote_gate(1, "admin")

    def test_promote_gate1(self, manager):
        manager.mark_condition_met(1, "connector_health_7_days")
        manager.mark_condition_met(1, "simulated_payments_20")
        manager.mark_condition_met(1, "no_connector_errors")
        manager.sign_off_condition(1, "ops_policy_reviewed", "admin")
        manager.sign_off_gate(1, "admin")
        result = manager.promote_gate(1, "admin")
        assert result.status == GateStatus.PROMOTED.value

    def test_get_current_gate_status(self, manager):
        status = manager.get_current_gate_status()
        assert "gate1" in status
        assert "gate2" in status

    def test_jsonl_persistence(self, tmp_path):
        filepath = str(tmp_path / "gates.jsonl")
        m1 = GateManager(filepath=filepath)
        m1.mark_condition_met(1, "connector_health_7_days")
        m1.sign_off_condition(1, "ops_policy_reviewed", "admin")

        m2 = GateManager(filepath=filepath)
        result = m2.check_gate1()
        health_cond = next(c for c in result.conditions if c["name"] == "connector_health_7_days")
        assert health_cond["met"] is True


class TestGateRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_gates_status_route(self, client):
        resp = client.get("/gates")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "gate1" in data
        assert "gate2" in data

    def test_gate1_route(self, client):
        resp = client.get("/gates/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["gate"] == 1

    def test_gate2_route(self, client):
        resp = client.get("/gates/2")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["gate"] == 2


class TestSingleton:
    def test_gate_manager_singleton_exists(self):
        assert GATE_MANAGER is not None
