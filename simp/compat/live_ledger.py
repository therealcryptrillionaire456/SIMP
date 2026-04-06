"""
SIMP Live Ledger — Sprint 44 (Sprint 44)

JSONL-backed, append-only live payment ledger.
Records real payment attempts and outcomes (when live mode is enabled).
Provider references are abbreviated for security.
"""

import json
import os
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SIMP.LiveLedger")

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _ensure_data_dir() -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    return _DATA_DIR


def _abbreviate_reference(ref: str) -> str:
    """Abbreviate a provider reference for security — only show last 4 chars."""
    if not ref or len(ref) <= 4:
        return ref
    return "..." + ref[-4:]


# ---------------------------------------------------------------------------
# LivePaymentRecord
# ---------------------------------------------------------------------------

@dataclass
class LivePaymentRecord:
    record_id: str = ""
    proposal_id: str = ""
    idempotency_key: str = ""
    connector_name: str = ""
    vendor: str = ""
    category: str = ""
    amount: float = 0.0
    currency: str = "USD"
    status: str = "pending"  # pending, succeeded, failed
    provider_reference: str = ""  # abbreviated only
    error: Optional[str] = None
    attempted_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self):
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.attempted_at:
            self.attempted_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# LiveSpendLedger — JSONL-backed, append-only
# ---------------------------------------------------------------------------

class LiveSpendLedger:
    """
    Append-only live spend ledger backed by JSONL file.
    Records payment attempts and outcomes.
    """

    def __init__(self, filepath: Optional[str] = None):
        _ensure_data_dir()
        self._filepath = filepath or os.path.join(_DATA_DIR, "live_spend_ledger.jsonl")
        self._lock = threading.Lock()
        self._records: Dict[str, LivePaymentRecord] = {}
        self._idempotency_keys: set = set()
        self._rebuild_from_events()

    def _rebuild_from_events(self) -> None:
        if not os.path.exists(self._filepath):
            return
        with open(self._filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    self._apply_event(event)
                except (json.JSONDecodeError, KeyError):
                    continue

    def _apply_event(self, event: Dict[str, Any]) -> None:
        etype = event.get("type", "")
        rid = event.get("record_id", "")

        if etype == "payment_attempt":
            rec = LivePaymentRecord(
                record_id=rid,
                proposal_id=event.get("proposal_id", ""),
                idempotency_key=event.get("idempotency_key", ""),
                connector_name=event.get("connector_name", ""),
                vendor=event.get("vendor", ""),
                category=event.get("category", ""),
                amount=event.get("amount", 0.0),
                currency=event.get("currency", "USD"),
                status="pending",
                attempted_at=event.get("timestamp", ""),
            )
            self._records[rid] = rec
            if rec.idempotency_key:
                self._idempotency_keys.add(rec.idempotency_key)

        elif etype == "payment_outcome":
            if rid in self._records:
                self._records[rid].status = event.get("status", "failed")
                ref = event.get("provider_reference", "")
                self._records[rid].provider_reference = _abbreviate_reference(ref)
                self._records[rid].error = event.get("error")
                self._records[rid].completed_at = event.get("timestamp", "")

    def _append_event(self, event: Dict[str, Any]) -> None:
        with open(self._filepath, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def record_attempt(
        self,
        proposal_id: str,
        idempotency_key: str,
        connector_name: str,
        vendor: str,
        category: str,
        amount: float,
    ) -> LivePaymentRecord:
        """Record a payment attempt (before execution)."""
        rec = LivePaymentRecord(
            proposal_id=proposal_id,
            idempotency_key=idempotency_key,
            connector_name=connector_name,
            vendor=vendor,
            category=category,
            amount=amount,
        )
        event = {
            "type": "payment_attempt",
            "record_id": rec.record_id,
            "proposal_id": proposal_id,
            "idempotency_key": idempotency_key,
            "connector_name": connector_name,
            "vendor": vendor,
            "category": category,
            "amount": amount,
            "currency": "USD",
            "timestamp": rec.attempted_at,
        }
        with self._lock:
            self._append_event(event)
            self._records[rec.record_id] = rec
            if idempotency_key:
                self._idempotency_keys.add(idempotency_key)

        logger.info("Payment attempt recorded: %s ($%.2f to %s)", rec.record_id, amount, vendor)
        return rec

    def record_outcome(
        self,
        record_id: str,
        status: str,
        provider_reference: str = "",
        error: Optional[str] = None,
    ) -> LivePaymentRecord:
        """Record the outcome of a payment attempt."""
        with self._lock:
            rec = self._records.get(record_id)
            if rec is None:
                raise ValueError(f"Record {record_id!r} not found")

            now = datetime.now(timezone.utc).isoformat()
            event = {
                "type": "payment_outcome",
                "record_id": record_id,
                "status": status,
                "provider_reference": provider_reference,
                "error": error,
                "timestamp": now,
            }
            self._append_event(event)
            rec.status = status
            rec.provider_reference = _abbreviate_reference(provider_reference)
            rec.error = error
            rec.completed_at = now

        logger.info("Payment outcome: %s -> %s", record_id, status)
        return rec

    def is_already_executed(self, idempotency_key: str) -> bool:
        """Check if a payment with this idempotency key has already been attempted."""
        with self._lock:
            return idempotency_key in self._idempotency_keys

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the live ledger."""
        with self._lock:
            total = sum(r.amount for r in self._records.values() if r.status == "succeeded")
            attempted = len(self._records)
            succeeded = sum(1 for r in self._records.values() if r.status == "succeeded")
            failed = sum(1 for r in self._records.values() if r.status == "failed")
            pending = sum(1 for r in self._records.values() if r.status == "pending")
            return {
                "total_live_spend": round(total, 2),
                "attempted": attempted,
                "succeeded": succeeded,
                "failed": failed,
                "pending": pending,
                "currency": "USD",
            }

    def get_all_records(self) -> List[LivePaymentRecord]:
        """Get all records."""
        with self._lock:
            return list(self._records.values())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

LIVE_LEDGER = LiveSpendLedger()
