"""
SIMP PaymentConnector — Sprint 41-42

Defines the minimal, explicit interface for payment connector implementations.
No real payment API calls occur until Gate 2 is passed and
FINANCIAL_OPS_LIVE_ENABLED is explicitly set to 'true'.

Design rules:
- Connectors load credentials from environment variables ONLY.
- Connector names are declared in ALLOWED_CONNECTORS allowlist.
- Dry-run mode is always available; live mode requires explicit opt-in.
"""

import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaymentConnectorConfig:
    connector_name: str = "stub"
    dry_run: bool = True
    live_enabled: bool = False
    timeout_seconds: int = 10
    max_retries: int = 2
    currency: str = "USD"
    max_amount: float = 20.00


@dataclass
class PaymentResult:
    success: bool
    connector: str
    mode: str  # "dry_run" | "live"
    amount: float
    currency: str
    vendor: str
    category: str
    reference_id: str
    timestamp: str
    dry_run_note: str = ""
    error: Optional[str] = None
    provider_response: Optional[Dict] = None


class PaymentConnector(ABC):
    def __init__(self, config: PaymentConnectorConfig):
        self.config = config

    @abstractmethod
    def health_check(self) -> Dict:
        """Return {status, connector, mode, timestamp}. Never reveal secrets."""

    @abstractmethod
    def authorize(self, vendor: str, amount: float, category: str, idempotency_key: str) -> PaymentResult:
        """Dry-run authorization check. No money moves."""

    @abstractmethod
    def execute_small_payment(self, vendor: str, amount: float, category: str, idempotency_key: str, proposal_id: str) -> PaymentResult:
        """Live execution. Only callable when live_enabled=True."""

    @abstractmethod
    def refund(self, reference_id: str, amount: float, reason: str) -> PaymentResult:
        """Refund a completed payment. Only callable when live_enabled=True."""


class StubPaymentConnector(PaymentConnector):
    """Stub connector for development and testing. No real API calls."""

    _APPROVED_VENDORS = frozenset({
        "github", "aws", "digitalocean", "heroku",
        "vercel", "netlify", "stripe", "sendgrid",
    })

    def health_check(self) -> Dict:
        return {
            "status": "ok",
            "connector": self.config.connector_name,
            "mode": "dry_run" if self.config.dry_run else "live",
            "reachable": True,
            "auth_status": "stubbed",
            "timestamp": _now_iso(),
            "note": "Stub connector — no real API calls.",
        }

    def authorize(self, vendor: str, amount: float, category: str, idempotency_key: str) -> PaymentResult:
        if vendor.lower() not in self._APPROVED_VENDORS:
            return PaymentResult(
                success=False, connector=self.config.connector_name, mode="dry_run",
                amount=amount, currency=self.config.currency, vendor=vendor,
                category=category, reference_id=idempotency_key, timestamp=_now_iso(),
                dry_run_note=f"Vendor '{vendor}' not in approved list.",
                error=f"Unknown vendor: {vendor}",
            )
        if amount > self.config.max_amount:
            return PaymentResult(
                success=False, connector=self.config.connector_name, mode="dry_run",
                amount=amount, currency=self.config.currency, vendor=vendor,
                category=category, reference_id=idempotency_key, timestamp=_now_iso(),
                dry_run_note=f"Amount ${amount:.2f} exceeds max ${self.config.max_amount:.2f}.",
                error=f"Amount exceeds limit: {amount} > {self.config.max_amount}",
            )
        return PaymentResult(
            success=True, connector=self.config.connector_name, mode="dry_run",
            amount=amount, currency=self.config.currency, vendor=vendor,
            category=category, reference_id=idempotency_key, timestamp=_now_iso(),
            dry_run_note=f"Would charge ${amount:.2f} to {vendor} — dry run only.",
        )

    def execute_small_payment(self, vendor: str, amount: float, category: str, idempotency_key: str, proposal_id: str) -> PaymentResult:
        if self.config.dry_run or not self.config.live_enabled:
            raise RuntimeError("Live payments not enabled. Set FINANCIAL_OPS_LIVE_ENABLED=true to enable.")
        return PaymentResult(
            success=True, connector=self.config.connector_name, mode="live",
            amount=amount, currency=self.config.currency, vendor=vendor,
            category=category, reference_id=f"stub-live-{idempotency_key}",
            timestamp=_now_iso(),
            provider_response={"stub": True, "proposal_id": proposal_id},
        )

    def refund(self, reference_id: str, amount: float, reason: str) -> PaymentResult:
        if self.config.dry_run or not self.config.live_enabled:
            raise RuntimeError("Live payments not enabled.")
        return PaymentResult(
            success=True, connector=self.config.connector_name, mode="live",
            amount=amount, currency=self.config.currency, vendor="refund",
            category="refund", reference_id=f"refund-{reference_id}",
            timestamp=_now_iso(),
        )


ALLOWED_CONNECTORS: Dict[str, type] = {
    "stripe_small_payments": StubPaymentConnector,
    "internal_corp_card_proxy": StubPaymentConnector,
}

ALLOWED_VENDOR_CATEGORIES = frozenset([
    "software_subscription", "developer_tool_license", "small_cloud_addon",
])

DISALLOWED_PAYMENT_TYPES = frozenset([
    "wire_transfers", "crypto_payments", "peer_to_peer", "payroll",
])


def build_connector(name: str) -> PaymentConnector:
    """Build a configured connector instance by name."""
    if name not in ALLOWED_CONNECTORS:
        raise ValueError(f"Connector '{name}' not in ALLOWED_CONNECTORS: {list(ALLOWED_CONNECTORS.keys())}")
    live_enabled = os.getenv("FINANCIAL_OPS_LIVE_ENABLED", "false").lower() == "true"
    config = PaymentConnectorConfig(
        connector_name=name, dry_run=not live_enabled, live_enabled=live_enabled,
    )
    return ALLOWED_CONNECTORS[name](config)


def validate_payment_request(vendor: str, category: str, amount: float, connector_name: str) -> Tuple[bool, Optional[str]]:
    """Validate a payment request against policy rules."""
    if not vendor or not vendor.strip():
        return (False, "Vendor must not be empty.")
    if category not in ALLOWED_VENDOR_CATEGORIES:
        return (False, f"Category '{category}' not in allowed categories: {sorted(ALLOWED_VENDOR_CATEGORIES)}")
    if amount > 20.00:
        return (False, f"Amount ${amount:.2f} exceeds per-task limit of $20.00.")
    if amount <= 0:
        return (False, "Amount must be positive.")
    if connector_name not in ALLOWED_CONNECTORS:
        return (False, f"Connector '{connector_name}' not in allowed connectors.")
    return (True, None)


# ---------------------------------------------------------------------------
# Connector Health Tracking (Sprint 42)
# ---------------------------------------------------------------------------

@dataclass
class ConnectorHealthRecord:
    connector_name: str
    status: str
    checked_at: str
    mode: str
    consecutive_ok_days: int = 0
    last_error: Optional[str] = None


class ConnectorHealthTracker:
    """Thread-safe health history tracker for payment connectors."""

    def __init__(self):
        self._lock = threading.Lock()
        self._history: Dict[str, List[Dict]] = {}
        self._first_ok: Dict[str, Optional[str]] = {}

    def record_check(self, connector_name: str, result_dict: Dict) -> None:
        with self._lock:
            if connector_name not in self._history:
                self._history[connector_name] = []
            self._history[connector_name].append(result_dict)
            if len(self._history[connector_name]) > 100:
                self._history[connector_name] = self._history[connector_name][-100:]
            if result_dict.get("status") == "ok":
                if connector_name not in self._first_ok or self._first_ok[connector_name] is None:
                    self._first_ok[connector_name] = result_dict.get("timestamp", _now_iso())
            else:
                self._first_ok[connector_name] = None

    def get_status(self, connector_name: str) -> Dict:
        with self._lock:
            history = self._history.get(connector_name, [])
            if not history:
                return {"connector_name": connector_name, "status": "unknown", "consecutive_ok_days": 0, "last_error": None, "check_count": 0}
            latest = history[-1]
            consecutive_ok_days = self._compute_consecutive_ok_days(connector_name)
            last_error = None
            for check in reversed(history):
                if check.get("status") != "ok":
                    last_error = check.get("note", check.get("error", "Unknown error"))
                    break
            return {"connector_name": connector_name, "status": latest.get("status", "unknown"), "consecutive_ok_days": consecutive_ok_days, "last_error": last_error, "check_count": len(history)}

    def _compute_consecutive_ok_days(self, connector_name: str) -> int:
        first_ok = self._first_ok.get(connector_name)
        if first_ok is None:
            return 0
        try:
            first_dt = datetime.fromisoformat(first_ok)
            delta = datetime.now(timezone.utc) - first_dt
            return max(0, delta.days)
        except (ValueError, TypeError):
            return 0

    def is_gate1_ready(self, connector_name: str) -> bool:
        return self.get_status(connector_name)["consecutive_ok_days"] >= 7


HEALTH_TRACKER = ConnectorHealthTracker()
