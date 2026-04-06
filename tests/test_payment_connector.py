"""Tests for simp.compat.payment_connector — Sprint 41."""

import os
import pytest
from simp.compat.payment_connector import (
    PaymentConnectorConfig,
    PaymentResult,
    StubPaymentConnector,
    ConnectorHealthTracker,
    ALLOWED_CONNECTORS,
    ALLOWED_VENDOR_CATEGORIES,
    DISALLOWED_PAYMENT_TYPES,
    build_connector,
    validate_payment_request,
)


# ---------------------------------------------------------------------------
# PaymentConnectorConfig
# ---------------------------------------------------------------------------

class TestPaymentConnectorConfig:
    def test_defaults(self):
        cfg = PaymentConnectorConfig()
        assert cfg.connector_name == "stub"
        assert cfg.dry_run is True
        assert cfg.live_enabled is False
        assert cfg.currency == "USD"
        assert cfg.max_amount == 20.00

    def test_custom_values(self):
        cfg = PaymentConnectorConfig(connector_name="test", max_amount=50.0)
        assert cfg.connector_name == "test"
        assert cfg.max_amount == 50.0


# ---------------------------------------------------------------------------
# StubPaymentConnector
# ---------------------------------------------------------------------------

class TestStubPaymentConnector:
    def _make_connector(self, **overrides):
        cfg = PaymentConnectorConfig(**overrides)
        return StubPaymentConnector(cfg)

    def test_health_check(self):
        c = self._make_connector()
        h = c.health_check()
        assert h["status"] == "ok"
        assert h["connector"] == "stub"
        assert h["mode"] == "dry_run"
        assert "timestamp" in h

    def test_health_check_live_mode(self):
        c = self._make_connector(dry_run=False)
        h = c.health_check()
        assert h["mode"] == "live"

    def test_authorize_approved_vendor(self):
        c = self._make_connector()
        r = c.authorize("github", 5.00, "software_subscription", "key-1")
        assert r.success is True
        assert r.mode == "dry_run"
        assert r.vendor == "github"
        assert r.amount == 5.00

    def test_authorize_unknown_vendor(self):
        c = self._make_connector()
        r = c.authorize("unknown_vendor", 5.00, "software_subscription", "key-2")
        assert r.success is False
        assert "not in approved list" in r.dry_run_note

    def test_authorize_exceeds_max(self):
        c = self._make_connector()
        r = c.authorize("github", 25.00, "software_subscription", "key-3")
        assert r.success is False
        assert "exceeds max" in r.dry_run_note.lower()

    def test_authorize_all_approved_vendors(self):
        c = self._make_connector()
        for vendor in ["github", "aws", "digitalocean", "heroku", "vercel", "netlify", "stripe", "sendgrid"]:
            r = c.authorize(vendor, 1.00, "test", "key-" + vendor)
            assert r.success is True, f"Expected {vendor} to be approved"

    def test_execute_raises_when_dry_run(self):
        c = self._make_connector()
        with pytest.raises(RuntimeError, match="Live payments not enabled"):
            c.execute_small_payment("github", 5.00, "test", "key-4", "prop-1")

    def test_execute_live(self):
        c = self._make_connector(dry_run=False, live_enabled=True)
        r = c.execute_small_payment("github", 5.00, "test", "key-5", "prop-1")
        assert r.success is True
        assert r.mode == "live"
        assert "stub-live-" in r.reference_id

    def test_refund_raises_when_dry_run(self):
        c = self._make_connector()
        with pytest.raises(RuntimeError):
            c.refund("ref-1", 5.00, "test refund")

    def test_refund_live(self):
        c = self._make_connector(dry_run=False, live_enabled=True)
        r = c.refund("ref-1", 5.00, "test refund")
        assert r.success is True
        assert "refund-ref-1" in r.reference_id


# ---------------------------------------------------------------------------
# Allowlists
# ---------------------------------------------------------------------------

class TestAllowlists:
    def test_allowed_connectors(self):
        assert "stripe_small_payments" in ALLOWED_CONNECTORS
        assert "internal_corp_card_proxy" in ALLOWED_CONNECTORS

    def test_allowed_vendor_categories(self):
        assert "software_subscription" in ALLOWED_VENDOR_CATEGORIES
        assert "developer_tool_license" in ALLOWED_VENDOR_CATEGORIES
        assert "small_cloud_addon" in ALLOWED_VENDOR_CATEGORIES

    def test_disallowed_payment_types(self):
        for pt in ["wire_transfers", "crypto_payments", "peer_to_peer", "payroll"]:
            assert pt in DISALLOWED_PAYMENT_TYPES


# ---------------------------------------------------------------------------
# build_connector
# ---------------------------------------------------------------------------

class TestBuildConnector:
    def test_build_known_connector(self):
        c = build_connector("stripe_small_payments")
        assert c.config.connector_name == "stripe_small_payments"
        assert c.config.dry_run is True  # default: live not enabled

    def test_build_unknown_raises(self):
        with pytest.raises(ValueError, match="not in ALLOWED_CONNECTORS"):
            build_connector("unknown_connector")

    def test_build_connector_live_flag(self, monkeypatch):
        monkeypatch.setenv("FINANCIAL_OPS_LIVE_ENABLED", "true")
        c = build_connector("stripe_small_payments")
        assert c.config.live_enabled is True
        assert c.config.dry_run is False


# ---------------------------------------------------------------------------
# validate_payment_request
# ---------------------------------------------------------------------------

class TestValidatePaymentRequest:
    def test_valid_request(self):
        ok, err = validate_payment_request("github", "software_subscription", 10.0, "stripe_small_payments")
        assert ok is True
        assert err is None

    def test_empty_vendor(self):
        ok, err = validate_payment_request("", "software_subscription", 10.0, "stripe_small_payments")
        assert ok is False
        assert "Vendor" in err

    def test_bad_category(self):
        ok, err = validate_payment_request("github", "invalid_cat", 10.0, "stripe_small_payments")
        assert ok is False
        assert "not in allowed categories" in err

    def test_amount_exceeds_limit(self):
        ok, err = validate_payment_request("github", "software_subscription", 25.0, "stripe_small_payments")
        assert ok is False
        assert "exceeds" in err.lower()

    def test_negative_amount(self):
        ok, err = validate_payment_request("github", "software_subscription", -1.0, "stripe_small_payments")
        assert ok is False
        assert "positive" in err.lower()

    def test_bad_connector(self):
        ok, err = validate_payment_request("github", "software_subscription", 10.0, "bad_connector")
        assert ok is False
        assert "not in allowed connectors" in err.lower()


# ---------------------------------------------------------------------------
# ConnectorHealthTracker
# ---------------------------------------------------------------------------

class TestConnectorHealthTracker:
    def test_unknown_connector_status(self):
        tracker = ConnectorHealthTracker()
        s = tracker.get_status("nonexistent")
        assert s["status"] == "unknown"
        assert s["consecutive_ok_days"] == 0

    def test_record_and_get(self):
        tracker = ConnectorHealthTracker()
        tracker.record_check("test", {"status": "ok", "timestamp": "2025-01-01T00:00:00+00:00"})
        s = tracker.get_status("test")
        assert s["status"] == "ok"
        assert s["check_count"] == 1

    def test_gate1_not_ready_initially(self):
        tracker = ConnectorHealthTracker()
        tracker.record_check("test", {"status": "ok"})
        assert tracker.is_gate1_ready("test") is False

    def test_history_cap_at_100(self):
        tracker = ConnectorHealthTracker()
        for i in range(110):
            tracker.record_check("test", {"status": "ok"})
        s = tracker.get_status("test")
        assert s["check_count"] == 100

    def test_error_resets_consecutive(self):
        tracker = ConnectorHealthTracker()
        tracker.record_check("test", {"status": "ok"})
        tracker.record_check("test", {"status": "error", "note": "timeout"})
        s = tracker.get_status("test")
        assert s["consecutive_ok_days"] == 0
        assert s["last_error"] == "timeout"
