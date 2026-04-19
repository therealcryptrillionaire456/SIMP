"""
SIMP A2A Ops Policy — Sprint S4 (Sprint 34) tests.
"""

import pytest
from simp.compat.ops_policy import (
    OpsPolicy,
    AutonomousOpType,
    validate_op_request,
    get_policy_dict,
    SpendRecord,
    SimulatedSpendLedger,
    SPEND_LEDGER,
)


class TestOpsPolicy:
    def test_default_values(self):
        p = OpsPolicy()
        assert p.version == "0.1.0"
        assert p.default_mode == "recommendation_only"
        assert p.spend_mode == "simulation"
        assert p.global_max_spend_per_task == 20.00
        assert p.global_max_spend_per_day == 50.00
        assert p.global_max_spend_per_month == 200.00
        assert p.currency == "USD"
        assert p.approval_required is True

    def test_validate_allowed_op_always_needs_approval(self):
        ok, reason = validate_op_request("maintenance")
        assert ok is False
        assert "manual approval" in reason

    def test_validate_disallowed_op(self):
        ok, reason = validate_op_request("dangerous_hack")
        assert ok is False
        assert "not allowed" in reason

    def test_validate_overspend(self):
        ok, reason = validate_op_request("simulated_spend", spend_amount=999.0)
        assert ok is False
        assert "exceeds" in reason

    def test_get_policy_dict_serializable(self):
        d = get_policy_dict()
        assert isinstance(d, dict)
        assert "version" in d
        assert "log_destination" not in d  # redacted

    def test_spend_mode_always_simulation(self):
        p = OpsPolicy()
        assert p.spend_mode == "simulation"


class TestSpendRecord:
    def test_fields(self):
        r = SpendRecord(
            record_id="r1",
            op_type="simulated_spend",
            agent_id="test",
            description="test spend",
            would_spend=5.0,
        )
        assert r.status == "simulated"
        assert r.approved is False
        assert r.currency == "USD"

    def test_to_dict(self):
        r = SpendRecord(record_id="r1", would_spend=5.0)
        d = r.to_dict()
        assert d["record_id"] == "r1"


class TestSimulatedSpendLedger:
    def test_record_spend(self):
        ledger = SimulatedSpendLedger()
        rec = ledger.record_simulated_spend("agent1", "test buy", 10.0)
        assert rec.status == "simulated"
        assert rec.approved is False
        assert rec.would_spend == 10.0

    def test_get_ledger(self):
        ledger = SimulatedSpendLedger()
        ledger.record_simulated_spend("a1", "buy", 5.0)
        ledger.record_simulated_spend("a1", "buy2", 3.0)
        assert len(ledger.get_ledger()) == 2

    def test_get_ledger_summary(self):
        ledger = SimulatedSpendLedger()
        ledger.record_simulated_spend("a1", "buy", 5.0)
        ledger.record_simulated_spend("a1", "buy2", 3.0)
        s = ledger.get_ledger_summary()
        assert s["total_would_spend"] == 8.0
        assert s["count"] == 2
        assert len(s["last_10"]) == 2

    def test_module_singleton(self):
        initial = SPEND_LEDGER.get_ledger_summary()["count"]
        SPEND_LEDGER.record_simulated_spend("test", "singleton test", 1.0)
        assert SPEND_LEDGER.get_ledger_summary()["count"] == initial + 1
