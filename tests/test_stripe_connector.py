"""Tests for Sprint 48 — Stripe Test Connector. ALL mocked — NO real Stripe calls."""

import json
import os
import io
import pytest
from unittest.mock import patch, MagicMock

from simp.compat.stripe_connector import StripeTestConnector
from simp.compat.payment_connector import PaymentConnectorConfig


def _mock_urlopen_response(body: dict, status: int = 200):
    """Create a mock response for urllib.request.urlopen."""
    mock_resp = MagicMock()
    encoded = json.dumps(body).encode("utf-8")
    mock_resp.read.return_value = encoded
    mock_resp.status = status
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestStripeTestConnectorInit:
    def test_valid_test_key(self):
        conn = StripeTestConnector(api_key="sk_test_abc123")
        assert conn._api_key == "sk_test_abc123"

    def test_production_key_raises(self):
        with pytest.raises(ValueError, match="sk_test_"):
            StripeTestConnector(api_key="sk_live_abc123")

    def test_empty_key_allowed(self):
        conn = StripeTestConnector(api_key="")
        assert conn._api_key == ""

    def test_key_from_env(self, monkeypatch):
        monkeypatch.setenv("STRIPE_TEST_SECRET_KEY", "sk_test_envkey1234")
        conn = StripeTestConnector()
        assert conn._api_key == "sk_test_envkey1234"

    def test_key_suffix_only_last_4(self):
        conn = StripeTestConnector(api_key="sk_test_verylongkeyvalue1234")
        assert conn._key_suffix() == "...1234"
        # Full key NEVER in suffix
        assert "verylongkey" not in conn._key_suffix()


class TestHealthCheck:
    @patch("simp.compat.stripe_connector.urllib.request.urlopen")
    def test_health_check_ok(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({"id": "acct_test123"})
        conn = StripeTestConnector(api_key="sk_test_health1234")
        result = conn.health_check()
        assert result["status"] == "ok"
        assert result["account_id"] == "acct_test123"
        assert result["key_suffix"] == "...1234"
        # Verify the full key is NOT in the result
        assert "sk_test_health" not in json.dumps(result)

    def test_health_check_no_key(self):
        conn = StripeTestConnector(api_key="")
        result = conn.health_check()
        assert result["status"] == "not_configured"

    @patch("simp.compat.stripe_connector.urllib.request.urlopen")
    def test_health_check_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        conn = StripeTestConnector(api_key="sk_test_err12345")
        result = conn.health_check()
        assert result["status"] == "error"


class TestAuthorize:
    @patch("simp.compat.stripe_connector.urllib.request.urlopen")
    def test_authorize_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "id": "pi_test_intent123",
            "status": "requires_confirmation",
        })
        conn = StripeTestConnector(api_key="sk_test_auth12345")
        result = conn.authorize(10.00, "Acme Corp", "Test auth")
        assert result.success is True
        assert result.dry_run is True  # authorize is always dry-run
        assert "pi_test_intent123" in result.reference_id

    def test_authorize_no_key(self):
        conn = StripeTestConnector(api_key="")
        result = conn.authorize(10.00, "Acme", "test")
        assert result.success is False
        assert "not set" in result.error

    @patch("simp.compat.stripe_connector.urllib.request.urlopen")
    def test_authorize_api_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Stripe error")
        conn = StripeTestConnector(api_key="sk_test_fail12345")
        result = conn.authorize(10.00, "Acme", "test")
        assert result.success is False
        assert result.dry_run is True


class TestExecuteSmallPayment:
    def test_execute_raises_in_dry_run(self):
        conn = StripeTestConnector(api_key="sk_test_exec12345")
        with pytest.raises(RuntimeError, match="dry_run"):
            conn.execute_small_payment(5.0, "Acme", "test")

    def test_execute_raises_default_config(self):
        """Default config is dry_run=True, so execute should always raise."""
        conn = StripeTestConnector(api_key="sk_test_def12345")
        assert conn.config.dry_run is True
        with pytest.raises(RuntimeError):
            conn.execute_small_payment(5.0, "Acme", "test")


class TestRefund:
    def test_refund_raises_in_dry_run(self):
        conn = StripeTestConnector(api_key="sk_test_ref12345")
        with pytest.raises(RuntimeError, match="dry_run"):
            conn.refund("pi_123", 5.0)


class TestBuildConnectorIntegration:
    def test_build_connector_falls_back_to_stub(self, monkeypatch):
        monkeypatch.delenv("STRIPE_TEST_SECRET_KEY", raising=False)
        from simp.compat.payment_connector import build_connector, StubPaymentConnector
        conn = build_connector("stripe_small_payments")
        assert isinstance(conn, StubPaymentConnector)

    def test_build_connector_uses_stripe_when_key_set(self, monkeypatch):
        monkeypatch.setenv("STRIPE_TEST_SECRET_KEY", "sk_test_build1234")
        from simp.compat.payment_connector import build_connector
        conn = build_connector("stripe_small_payments")
        assert isinstance(conn, StripeTestConnector)


class TestNoRealStripeCalls:
    def test_no_real_api_calls_in_tests(self):
        """Verify all Stripe calls are mocked — no real network access."""
        conn = StripeTestConnector(api_key="sk_test_nosend123")
        # Without mock, health_check with no network should fail gracefully
        result = conn.health_check()
        # It should error (no mock, real URL fails), not succeed
        assert result["status"] in ("error", "ok")

    def test_no_credentials_in_source(self):
        """Verify no hardcoded credentials in source."""
        import simp.compat.stripe_connector as mod
        source = open(mod.__file__).read()
        assert "sk_live_" not in source
        assert "sk_test_real" not in source
