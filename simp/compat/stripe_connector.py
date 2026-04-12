"""
SIMP Stripe Test Connector — Sprint 48

StripeTestConnector using ONLY stdlib urllib (no requests/stripe SDK).
Enforces sk_test_ key prefix — production keys are REJECTED.
NEVER logs the full API key — only last 4 characters.
"""

import json
import logging
import os
import urllib.request
import urllib.error
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from simp.compat.payment_connector import (
    PaymentConnector,
    PaymentConnectorConfig,
    PaymentResult,
)

logger = logging.getLogger("SIMP.StripeConnector")


class StripeTestConnector(PaymentConnector):
    """
    Stripe test-mode connector using stdlib urllib only.
    - Key MUST start with "sk_test_" — raises ValueError otherwise.
    - NEVER logs or stores the full key.
    - dry_run=True: authorize() works (payment_intents with confirm=false).
    - dry_run=True: execute_small_payment() and refund() raise RuntimeError.
    """

    def __init__(self, config: Optional[PaymentConnectorConfig] = None, api_key: Optional[str] = None):
        if config is None:
            config = PaymentConnectorConfig(
                name="stripe_test",
                connector_type="stripe_test",
                dry_run=True,
            )
        super().__init__(config)

        self._api_key = api_key or os.environ.get("STRIPE_TEST_SECRET_KEY", "")
        if self._api_key and not self._api_key.startswith("sk_test_"):
            raise ValueError(
                "Stripe key must start with 'sk_test_' — production keys are not allowed. "
                f"Key ending: ...{self._api_key[-4:]}"
            )

        self._base_url = "https://api.stripe.com"

    def _key_suffix(self) -> str:
        """Return last 4 chars of key for logging (NEVER full key)."""
        if not self._api_key:
            return "(none)"
        return "..." + self._api_key[-4:]

    def _make_request(self, method: str, path: str, data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Make an HTTP request to Stripe API using stdlib urllib.
        NEVER logs the full API key.
        """
        url = self._base_url + path
        encoded_data = None
        if data:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        req = urllib.request.Request(url, data=encoded_data, method=method)
        req.add_header("Authorization", f"Bearer {self._api_key}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        logger.info("Stripe API %s %s (key=%s)", method, path, self._key_suffix())

        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            logger.error("Stripe API error %d on %s (key=%s): %s", e.code, path, self._key_suffix(), body[:200])
            raise
        except urllib.error.URLError as e:
            logger.error("Stripe connection error on %s (key=%s): %s", path, self._key_suffix(), e.reason)
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        GET /v1/account — check Stripe connectivity.
        NEVER logs the full key.
        """
        if not self._api_key:
            return {
                "connector": self.config.name,
                "status": "not_configured",
                "dry_run": self.config.dry_run,
                "message": "STRIPE_TEST_SECRET_KEY not set",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            result = self._make_request("GET", "/v1/account")
            return {
                "connector": self.config.name,
                "status": "ok",
                "dry_run": self.config.dry_run,
                "account_id": result.get("id", ""),
                "key_suffix": self._key_suffix(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "connector": self.config.name,
                "status": "error",
                "dry_run": self.config.dry_run,
                "error": str(exc)[:200],
                "key_suffix": self._key_suffix(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def authorize(self, amount: float, vendor: str, description: str) -> PaymentResult:
        """
        POST /v1/payment_intents with confirm=false (dry-run authorization only).
        """
        if not self._api_key:
            return PaymentResult(
                success=False,
                connector_name=self.config.name,
                amount=amount,
                dry_run=True,
                error="STRIPE_TEST_SECRET_KEY not set",
                message="Cannot authorize without API key",
            )

        try:
            amount_cents = int(amount * 100)
            data = {
                "amount": str(amount_cents),
                "currency": self.config.currency.lower(),
                "confirm": "false",
                "description": description,
                "metadata[vendor]": vendor,
                "metadata[source]": "simp_financial_ops",
            }
            result = self._make_request("POST", "/v1/payment_intents", data)
            return PaymentResult(
                success=True,
                reference_id=result.get("id", ""),
                connector_name=self.config.name,
                amount=amount,
                currency=self.config.currency,
                dry_run=True,  # Always dry-run for authorize
                message=f"Authorized ${amount:.2f} (intent={result.get('id', 'unknown')})",
            )
        except Exception as exc:
            return PaymentResult(
                success=False,
                connector_name=self.config.name,
                amount=amount,
                dry_run=True,
                error=str(exc)[:200],
                message="Authorization failed",
            )

    def execute_small_payment(self, amount: float, vendor: str, description: str, idempotency_key: str = "") -> PaymentResult:
        """
        Execute a small payment. Raises RuntimeError when dry_run=True.
        """
        if self.config.dry_run:
            raise RuntimeError(
                "StripeTestConnector: execute_small_payment is blocked in dry_run mode. "
                "Live execution requires dry_run=False and explicit go-live approval."
            )
        # If dry_run were ever False, this would execute — but by design it shouldn't reach here
        # in test/pilot mode.
        raise RuntimeError("StripeTestConnector: live execution not implemented in pilot phase")

    def refund(self, reference_id: str, amount: float) -> PaymentResult:
        """
        Refund a payment. Raises RuntimeError when dry_run=True.
        """
        if self.config.dry_run:
            raise RuntimeError(
                "StripeTestConnector: refund is blocked in dry_run mode. "
                "Live refunds require dry_run=False and explicit go-live approval."
            )
        raise RuntimeError("StripeTestConnector: live refund not implemented in pilot phase")
