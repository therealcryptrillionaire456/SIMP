"""
SIMP Payment Connector -- Sprint 41 (Sprint 41)

Payment connector abstraction with stub implementations.
ALL connectors default to DRY RUN. No real payments unless FINANCIAL_OPS_LIVE_ENABLED=true.
"""

import os
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("SIMP.PaymentConnector")

# ---------------------------------------------------------------------------
# Config & Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PaymentConnectorConfig:
    """Configuration for a payment connector."""
    name: str = ""
    connector_type: str = "stub"
    dry_run: bool = True
    max_amount: float = 20.00
    currency: str = "USD"
    # NEVER store credentials here

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PaymentResult:
    """Result from a payment operation."""
    success: bool = False
    reference_id: str = ""
    connector_name: str = ""
    amount: float = 0.0
    currency: str = "USD"
    dry_run: bool = True
    message: str = ""
    timestamp: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        if not self.reference_id:
            self.reference_id = f"dry-{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class PaymentConnector(ABC):
    """Abstract payment connector interface."""

    def __init__(self, config: PaymentConnectorConfig):
        self.config = config

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return health status of this connector."""
        ...

    @abstractmethod
    def authorize(self, amount: float, vendor: str, description: str) -> PaymentResult:
        """Authorize (but not capture) a payment."""
        ...

    @abstractmethod
    def execute_small_payment(self, amount: float, vendor: str, description: str, idempotency_key: str = "") -> PaymentResult:
        """Execute a small payment."""
        ...

    @abstractmethod
    def refund(self, reference_id: str, amount: float) -> PaymentResult:
        """Refund a previous payment."""
        ...


# ---------------------------------------------------------------------------
# Stub connector (dry-run only)
# ---------------------------------------------------------------------------

class StubPaymentConnector(PaymentConnector):
    """
    Stub connector that simulates payment operations.

    Always returns realistic simulated responses (dry_run=True in result).
    When config.dry_run=False and explicitly called outside execute flow,
    raises RuntimeError to prevent accidental misuse.
    The execute flow (execute_approved_payment) catches exceptions,
    so the stub always indicates it is simulated.
    """

    def __init__(self, config: Optional[PaymentConnectorConfig] = None):
        if config is None:
            config = PaymentConnectorConfig(name="stub", connector_type="stub", dry_run=True)
        super().__init__(config)
        self._health_ok = True

    def health_check(self) -> Dict[str, Any]:
        return {
            "connector": self.config.name,
            "status": "ok" if self._health_ok else "degraded",
            "dry_run": self.config.dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def authorize(self, amount: float, vendor: str, description: str) -> PaymentResult:
        logger.info("STUB authorize: $%.2f to %s (dry_run=%s)", amount, vendor, self.config.dry_run)
        return PaymentResult(
            success=True,
            connector_name=self.config.name,
            amount=amount,
            currency=self.config.currency,
            dry_run=True,
            message=f"STUB: authorized ${amount:.2f} to {vendor}",
        )

    def execute_small_payment(self, amount: float, vendor: str, description: str, idempotency_key: str = "") -> PaymentResult:
        if amount > self.config.max_amount:
            return PaymentResult(
                success=False,
                connector_name=self.config.name,
                amount=amount,
                dry_run=True,
                error=f"Amount ${amount:.2f} exceeds max ${self.config.max_amount:.2f}",
                message="Payment rejected: exceeds limit",
            )
        logger.info("STUB payment: $%.2f to %s (dry_run=%s)", amount, vendor, self.config.dry_run)
        return PaymentResult(
            success=True,
            connector_name=self.config.name,
            amount=amount,
            currency=self.config.currency,
            dry_run=True,
            message=f"STUB: paid ${amount:.2f} to {vendor}",
        )

    def refund(self, reference_id: str, amount: float) -> PaymentResult:
        logger.info("STUB refund: $%.2f for ref %s (dry_run=%s)", amount, reference_id, self.config.dry_run)
        return PaymentResult(
            success=True,
            connector_name=self.config.name,
            amount=amount,
            currency=self.config.currency,
            dry_run=True,
            message=f"STUB: refunded ${amount:.2f} for {reference_id}",
        )


# ---------------------------------------------------------------------------
# Allowed connectors registry
# ---------------------------------------------------------------------------

ALLOWED_CONNECTORS: Dict[str, type] = {
    "stripe_small_payments": StubPaymentConnector,
    "internal_corp_card_proxy": StubPaymentConnector,
}

# ---------------------------------------------------------------------------
# Vendor & payment-type guardrails
# ---------------------------------------------------------------------------

ALLOWED_VENDOR_CATEGORIES: frozenset = frozenset({
    "cloud_infrastructure",
    "developer_tools",
    "saas_subscription",
    "office_supplies",
    "software_license",
})

DISALLOWED_PAYMENT_TYPES: frozenset = frozenset({
    "cryptocurrency",
    "gambling",
    "cash_advance",
    "wire_transfer",
    "gift_card",
    "personal_expense",
})


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_connector(name: str) -> PaymentConnector:
    """
    Build a payment connector by name.

    Reads FINANCIAL_OPS_LIVE_ENABLED env var to decide dry_run mode.
    If the env var is not set or is not "true", dry_run defaults to True.
    """
    if name not in ALLOWED_CONNECTORS:
        raise ValueError(f"Unknown connector: {name!r}. Allowed: {sorted(ALLOWED_CONNECTORS)}")

    live_enabled = os.environ.get("FINANCIAL_OPS_LIVE_ENABLED", "").lower() == "true"

    config = PaymentConnectorConfig(
        name=name,
        connector_type="stub",
        dry_run=not live_enabled,
    )

    cls = ALLOWED_CONNECTORS[name]
    return cls(config)


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------

def validate_payment_request(
    vendor: str,
    category: str,
    amount: float,
    connector_name: str,
) -> Tuple[bool, Optional[str]]:
    """
    Validate a payment request against policy guardrails.

    Returns (True, None) if valid, (False, reason) if rejected.
    """
    if not vendor or not vendor.strip():
        return False, "Vendor name is required"

    if category not in ALLOWED_VENDOR_CATEGORIES:
        return False, f"Vendor category {category!r} is not in allowed list: {sorted(ALLOWED_VENDOR_CATEGORIES)}"

    if amount <= 0:
        return False, "Amount must be positive"

    if amount > 20.00:
        return False, f"Amount ${amount:.2f} exceeds per-transaction limit of $20.00"

    if connector_name not in ALLOWED_CONNECTORS:
        return False, f"Connector {connector_name!r} is not allowed"

    # Check for disallowed payment types embedded in vendor name
    vendor_lower = vendor.lower()
    for disallowed in DISALLOWED_PAYMENT_TYPES:
        if disallowed.replace("_", " ") in vendor_lower or disallowed in vendor_lower:
            return False, f"Payment type {disallowed!r} is not allowed"

    return True, None


# ---------------------------------------------------------------------------
# Connector Health Tracker — Sprint 42
# ---------------------------------------------------------------------------

class ConnectorHealthTracker:
    """
    Tracks health check results for payment connectors.
    Records consecutive OK days and determines gate-1 readiness.
    """

    def __init__(self) -> None:
        import threading
        self._lock = threading.Lock()
        self._checks: list = []  # list of {connector, status, timestamp}
        self._consecutive_ok: Dict[str, int] = {}

    def record_check(self, connector_name: str, status: str) -> None:
        """Record a health check result."""
        from datetime import datetime, timezone
        entry = {
            "connector": connector_name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._checks.append(entry)
            if status == "ok":
                self._consecutive_ok[connector_name] = self._consecutive_ok.get(connector_name, 0) + 1
            else:
                self._consecutive_ok[connector_name] = 0

    def consecutive_ok_days(self, connector_name: str) -> int:
        """Return the number of consecutive OK checks for a connector."""
        with self._lock:
            return self._consecutive_ok.get(connector_name, 0)

    def is_gate1_ready(self, connector_name: str, required_days: int = 3) -> bool:
        """Check if a connector has passed gate-1 (N consecutive OK days)."""
        return self.consecutive_ok_days(connector_name) >= required_days

    def get_status(self) -> Dict[str, Any]:
        """Return health tracker status (safe for public endpoints)."""
        with self._lock:
            return {
                "total_checks": len(self._checks),
                "connectors": {
                    name: {
                        "consecutive_ok": count,
                        "gate1_ready": count >= 3,
                    }
                    for name, count in self._consecutive_ok.items()
                },
                "last_check": self._checks[-1] if self._checks else None,
            }


# Module-level singleton
HEALTH_TRACKER = ConnectorHealthTracker()
