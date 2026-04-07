"""Tests for Sprint 50 — Contract & Invariant Tests.

Verifies system-wide invariants:
- Ledger append-only
- No secrets in agent cards
- Idempotency
- Rollback
- Gate conditions
- A2A card shape
"""

import json
import os
import pytest
from unittest.mock import patch

from simp.compat.live_ledger import LiveSpendLedger, LivePaymentRecord
from simp.compat.approval_queue import ApprovalQueue, PaymentProposalStatus
from simp.compat.rollback import RollbackManager, RollbackState, LedgerFrozenError
from simp.compat.gate_manager import GateManager, GateStatus
from simp.compat.budget_monitor import BudgetMonitor, AlertSeverity
from simp.compat.financial_ops import build_financial_ops_card
from simp.compat.payment_connector import StubPaymentConnector


class TestLedgerAppendOnly:
    """Verify ledger is append-only — no delete, no overwrite."""

    def test_live_ledger_append_only(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        ledger = LiveSpendLedger(filepath=filepath)
        ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_attempt("p2", "k2", "stripe", "Acme", "cloud", 20.0)

        # File should have exactly 2 lines
        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2

        # Each line is valid JSON
        for line in lines:
            data = json.loads(line)
            assert "type" in data

    def test_live_ledger_outcome_appends(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        ledger = LiveSpendLedger(filepath=filepath)
        rec = ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)
        ledger.record_outcome(rec.record_id, "succeeded", "ref123")

        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["type"] == "payment_attempt"
        assert json.loads(lines[1])["type"] == "payment_outcome"

    def test_approval_queue_append_only(self, tmp_path):
        filepath = str(tmp_path / "proposals.jsonl")
        q = ApprovalQueue(filepath=filepath)
        q.submit_proposal("small_purchase", "Acme", "cloud_infrastructure", 5.0, "stripe_small_payments")
        q.submit_proposal("small_purchase", "Beta", "developer_tools", 3.0, "stripe_small_payments")

        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2

    def test_rollback_log_append_only(self, tmp_path):
        filepath = str(tmp_path / "rollback.jsonl")
        mgr = RollbackManager(filepath=filepath)
        mgr.trigger_rollback("admin", "test1")
        mgr.trigger_rollback("admin", "test2")

        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2

    def test_gate_log_append_only(self, tmp_path):
        filepath = str(tmp_path / "gates.jsonl")
        mgr = GateManager(filepath=filepath)
        mgr.mark_condition_met(1, "connector_health_7_days")
        mgr.sign_off_condition(1, "ops_policy_reviewed", "admin")

        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2


class TestNoSecretsInCards:
    """Verify no credentials, API keys, or secrets appear in agent cards."""

    def test_financial_ops_card_no_secrets(self, monkeypatch):
        monkeypatch.delenv("STRIPE_TEST_SECRET_KEY", raising=False)
        card = build_financial_ops_card()
        card_str = json.dumps(card)
        assert "sk_test_" not in card_str
        assert "sk_live_" not in card_str
        assert "password" not in card_str.lower()
        # "noCredentialStorage" is a policy key, not a leaked credential
        # Check that no actual secret values appear
        assert "api_key_value" not in card_str.lower()
        assert "bearer_token" not in card_str.lower()

    def test_financial_ops_card_has_required_fields(self):
        card = build_financial_ops_card()
        assert "name" in card
        assert "description" in card
        assert "version" in card
        assert "url" in card
        assert "capabilities" in card
        assert "skills" in card
        assert "x-simp" in card

    def test_card_does_not_contain_env_vars(self, monkeypatch):
        monkeypatch.setenv("STRIPE_TEST_SECRET_KEY", "sk_test_shouldnotappear")
        card = build_financial_ops_card()
        card_str = json.dumps(card)
        assert "shouldnotappear" not in card_str


class TestIdempotency:
    """Verify idempotency guards work correctly."""

    def test_live_ledger_idempotency(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        ledger = LiveSpendLedger(filepath=filepath)
        ledger.record_attempt("p1", "idem-key-1", "stripe", "Acme", "cloud", 10.0)
        assert ledger.is_already_executed("idem-key-1") is True
        assert ledger.is_already_executed("idem-key-2") is False

    def test_idempotency_survives_reload(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        l1 = LiveSpendLedger(filepath=filepath)
        l1.record_attempt("p1", "idem-key-1", "stripe", "Acme", "cloud", 10.0)

        l2 = LiveSpendLedger(filepath=filepath)
        assert l2.is_already_executed("idem-key-1") is True

    def test_stub_connector_is_idempotent(self):
        conn = StubPaymentConnector()
        r1 = conn.execute_small_payment(5.0, "Acme", "test", "idem-1")
        r2 = conn.execute_small_payment(5.0, "Acme", "test", "idem-1")
        assert r1.success == r2.success
        assert r1.dry_run is True


class TestRollbackContracts:
    """Verify rollback invariants."""

    def test_rollback_active_when_env_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        filepath = str(tmp_path / "rb.jsonl")
        mgr = RollbackManager(filepath=filepath)
        mgr.deactivate_rollback("admin", "was live")
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "false")
        assert mgr.get_state() == RollbackState.ACTIVE

    def test_frozen_ledger_blocks_writes(self, tmp_path):
        filepath = str(tmp_path / "live.jsonl")
        ledger = LiveSpendLedger(filepath=filepath)
        ledger.freeze()
        with pytest.raises(LedgerFrozenError):
            ledger.record_attempt("p1", "k1", "stripe", "Acme", "cloud", 10.0)

    def test_rollback_history_is_ordered(self, tmp_path):
        filepath = str(tmp_path / "rb.jsonl")
        mgr = RollbackManager(filepath=filepath)
        mgr.trigger_rollback("admin", "first")
        mgr.trigger_rollback("admin", "second")
        history = mgr.get_rollback_history()
        assert history[0]["reason"] == "second"
        assert history[1]["reason"] == "first"

    def test_rollback_never_live_without_history(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FINANCIAL_OPS_LIVE_ENABLED", raising=False)
        filepath = str(tmp_path / "rb.jsonl")
        mgr = RollbackManager(filepath=filepath)
        assert mgr.get_state() == RollbackState.NEVER_LIVE


class TestGateContracts:
    """Verify gate invariants."""

    def test_gate_signoff_requires_all_automated(self, tmp_path):
        filepath = str(tmp_path / "gates.jsonl")
        mgr = GateManager(filepath=filepath)
        mgr.sign_off_condition(1, "ops_policy_reviewed", "admin")
        with pytest.raises(ValueError, match="automated conditions not met"):
            mgr.sign_off_gate(1, "admin")

    def test_gate2_requires_gate1(self, tmp_path):
        filepath = str(tmp_path / "gates.jsonl")
        mgr = GateManager(filepath=filepath)
        # Gate 2 condition gate1_signed_off is automated
        result = mgr.check_gate2()
        gate1_cond = next(c for c in result.conditions if c["name"] == "gate1_signed_off")
        assert gate1_cond["met"] is False

    def test_promote_requires_signoff(self, tmp_path):
        filepath = str(tmp_path / "gates.jsonl")
        mgr = GateManager(filepath=filepath)
        with pytest.raises(ValueError, match="signed off"):
            mgr.promote_gate(1, "admin")

    def test_invalid_gate_raises(self, tmp_path):
        filepath = str(tmp_path / "gates.jsonl")
        mgr = GateManager(filepath=filepath)
        with pytest.raises(ValueError, match="Invalid gate"):
            mgr._get_conditions(3)


class TestA2ACardShape:
    """Verify A2A card has correct shape for interoperability."""

    def test_card_has_url(self):
        card = build_financial_ops_card()
        assert card["url"].startswith("http")

    def test_card_capabilities_structure(self):
        card = build_financial_ops_card()
        caps = card["capabilities"]
        assert "streaming" in caps
        assert "pushNotifications" in caps

    def test_card_skills_are_list(self):
        card = build_financial_ops_card()
        assert isinstance(card["skills"], list)
        for skill in card["skills"]:
            assert "id" in skill
            assert "name" in skill

    def test_card_security_schemes(self):
        card = build_financial_ops_card()
        assert "securitySchemes" in card
        assert "security" in card

    def test_card_safety_policies(self):
        card = build_financial_ops_card()
        assert "safetyPolicies" in card
        policies = card["safetyPolicies"]
        assert policies["noCredentialStorage"] is True

    def test_card_x_simp_namespace(self):
        card = build_financial_ops_card()
        xs = card["x-simp"]
        assert xs["agent_type"] == "financial_ops"
        assert "protocol" in xs


class TestBudgetContracts:
    """Verify budget monitor invariants."""

    def test_warning_threshold_at_75(self):
        m = BudgetMonitor(max_per_day=100.0)
        alerts = m.check_daily_budget(74.99)
        assert len(alerts) == 0
        alerts = m.check_daily_budget(75.0)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING.value

    def test_critical_threshold_at_100(self):
        m = BudgetMonitor(max_per_day=100.0)
        alerts = m.check_daily_budget(99.99)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING.value
        alerts2 = m.check_daily_budget(100.0)
        assert alerts2[0].severity == AlertSeverity.CRITICAL.value

    def test_acknowledged_alert_not_critical(self):
        m = BudgetMonitor(max_per_day=50.0)
        m.check_daily_budget(50.0)
        alerts = m.get_alerts()
        m.acknowledge_alert(alerts[0]["alert_id"], "admin")
        assert m.has_critical_alert() is False
