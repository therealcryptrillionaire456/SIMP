"""Tests for Sprint 41 — Payment Connector."""

import os
import pytest

from simp.compat.payment_connector import (
    PaymentConnectorConfig,
    PaymentResult,
    StubPaymentConnector,
    ALLOWED_CONNECTORS,
    ALLOWED_VENDOR_CATEGORIES,
    DISALLOWED_PAYMENT_TYPES,
    build_connector,
    validate_payment_request,
    ConnectorHealthTracker,
    HEALTH_TRACKER,
)
from simp.compat.ops_policy import OpsPolicy


class TestPaymentConnectorConfig:
    def test_defaults(self):
        c = PaymentConnectorConfig()
        assert c.dry_run is True
        assert c.max_amount == 20.00
        assert c.currency == "USD"

    def test_to_dict(self):
        c = PaymentConnectorConfig(name="test")
        d = c.to_dict()
        assert d["name"] == "test"
        assert "dry_run" in d


class TestPaymentResult:
    def test_defaults(self):
        r = PaymentResult()
        assert r.success is False
        assert r.dry_run is True
        assert r.reference_id.startswith("dry-")

    def test_to_dict(self):
        r = PaymentResult(success=True, amount=5.0)
        d = r.to_dict()
        assert d["success"] is True
        assert d["amount"] == 5.0


class TestStubPaymentConnector:
    def test_health_check(self):
        conn = StubPaymentConnector()
        h = conn.health_check()
        assert h["status"] == "ok"
        assert h["dry_run"] is True

    def test_authorize_dry_run(self):
        conn = StubPaymentConnector()
        result = conn.authorize(10.0, "Acme Corp", "test auth")
        assert result.success is True
        assert result.dry_run is True
        assert "STUB" in result.message

    def test_execute_small_payment_dry_run(self):
        conn = StubPaymentConnector()
        result = conn.execute_small_payment(15.0, "Acme Corp", "test pay")
        assert result.success is True
        assert result.dry_run is True

    def test_execute_exceeds_max(self):
        conn = StubPaymentConnector()
        result = conn.execute_small_payment(25.0, "Acme Corp", "too much")
        assert result.success is False
        assert "exceeds" in result.error

    def test_refund_dry_run(self):
        conn = StubPaymentConnector()
        result = conn.refund("ref-123", 5.0)
        assert result.success is True
        assert "refund" in result.message.lower()

    def test_live_mode_still_returns_stub(self):
        """Stub connector works in live mode but still marks result as dry_run=True."""
        config = PaymentConnectorConfig(name="test", dry_run=False)
        conn = StubPaymentConnector(config)
        result = conn.authorize(10.0, "Acme", "test")
        assert result.success is True
        assert result.dry_run is True  # stub always reports dry_run

    def test_live_execute_still_stub(self):
        config = PaymentConnectorConfig(name="test", dry_run=False)
        conn = StubPaymentConnector(config)
        result = conn.execute_small_payment(5.0, "Acme", "test")
        assert result.success is True
        assert result.dry_run is True

    def test_live_refund_still_stub(self):
        config = PaymentConnectorConfig(name="test", dry_run=False)
        conn = StubPaymentConnector(config)
        result = conn.refund("ref-1", 5.0)
        assert result.success is True
        assert result.dry_run is True


class TestAllowedConnectors:
    def test_stripe_in_allowed(self):
        assert "stripe_small_payments" in ALLOWED_CONNECTORS

    def test_corp_card_in_allowed(self):
        assert "internal_corp_card_proxy" in ALLOWED_CONNECTORS

    def test_all_are_stub(self):
        for name, cls in ALLOWED_CONNECTORS.items():
            assert cls is StubPaymentConnector


class TestBuildConnector:
    def test_build_stripe(self):
        conn = build_connector("stripe_small_payments")
        assert conn.config.name == "stripe_small_payments"
        assert conn.config.dry_run is True

    def test_build_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown connector"):
            build_connector("paypal")

    def test_env_var_controls_dry_run(self, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        conn = build_connector("stripe_small_payments")
        assert conn.config.dry_run is False


class TestValidatePaymentRequest:
    def test_valid_request(self):
        ok, err = validate_payment_request("Acme Corp", "cloud_infrastructure", 10.0, "stripe_small_payments")
        assert ok is True
        assert err is None

    def test_empty_vendor(self):
        ok, err = validate_payment_request("", "cloud_infrastructure", 10.0, "stripe_small_payments")
        assert ok is False
        assert "Vendor" in err

    def test_bad_category(self):
        ok, err = validate_payment_request("Acme", "weapons", 10.0, "stripe_small_payments")
        assert ok is False

    def test_negative_amount(self):
        ok, err = validate_payment_request("Acme", "cloud_infrastructure", -5.0, "stripe_small_payments")
        assert ok is False

    def test_over_limit(self):
        ok, err = validate_payment_request("Acme", "cloud_infrastructure", 25.0, "stripe_small_payments")
        assert ok is False
        assert "exceeds" in err

    def test_bad_connector(self):
        ok, err = validate_payment_request("Acme", "cloud_infrastructure", 5.0, "paypal")
        assert ok is False

    def test_disallowed_type_in_vendor(self):
        ok, err = validate_payment_request("Cryptocurrency Exchange", "cloud_infrastructure", 5.0, "stripe_small_payments")
        assert ok is False


class TestOpsPolicy:
    def test_live_payments_allowed_default(self):
        p = OpsPolicy()
        assert p.live_payments_allowed is False

    def test_vendor_categories(self):
        p = OpsPolicy()
        assert "cloud_infrastructure" in p.allowed_vendor_categories

    def test_disallowed_payment_types(self):
        p = OpsPolicy()
        assert "gambling" in p.disallowed_payment_types

    def test_pilot_limits(self):
        p = OpsPolicy()
        assert p.pilot_max_per_transaction == 20.00


class TestConnectorHealthTracker:
    def test_initial_state(self):
        tracker = ConnectorHealthTracker()
        assert tracker.consecutive_ok_days("test") == 0

    def test_record_ok(self):
        tracker = ConnectorHealthTracker()
        tracker.record_check("test", "ok")
        assert tracker.consecutive_ok_days("test") == 1

    def test_gate1_not_ready(self):
        tracker = ConnectorHealthTracker()
        tracker.record_check("test", "ok")
        assert tracker.is_gate1_ready("test") is False

    def test_gate1_ready(self):
        tracker = ConnectorHealthTracker()
        for _ in range(3):
            tracker.record_check("test", "ok")
        assert tracker.is_gate1_ready("test") is True

    def test_reset_on_failure(self):
        tracker = ConnectorHealthTracker()
        tracker.record_check("test", "ok")
        tracker.record_check("test", "ok")
        tracker.record_check("test", "degraded")
        assert tracker.consecutive_ok_days("test") == 0

    def test_get_status(self):
        tracker = ConnectorHealthTracker()
        tracker.record_check("conn1", "ok")
        s = tracker.get_status()
        assert s["total_checks"] == 1
        assert "conn1" in s["connectors"]
