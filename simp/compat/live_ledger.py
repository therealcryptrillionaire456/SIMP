"""
SIMP Live Spend Ledger — Sprint 44

Append-only, JSONL-backed ledger that records actual (live) payment executions.
Separated from the simulated spend ledger in ops_policy.py so the two streams
never mix.

Design rules:
- Append-only: records are never deleted.
- Thread-safe via threading.Lock.
- Idempotent: repeated writes with the same proposal_id are silently ignored.
- Feature-flagged: callers must check FINANCIAL_OPS_LIVE_ENABLED before writing.
"""

import json
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LiveSpendRecord:
    record_id: str
    proposal_id: str
    connector_name: str
    vendor: str
    category: str
    amount: float
    currency: str
    reference_id: str
    timestamp: str
    status: str  # "completed" | "failed" | "refunded"
    operator_subject: str = ""
    error: Optional[str] = None
    provider_response: Optional[Dict] = None
    idempotency_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveSpendLedger:
    """Append-only JSONL-backed ledger for live payment executions."""

    def __init__(self, ledger_path: Optional[str] = None):
        self._ledger_path = Path(ledger_path or "data/financial_ops_live_spend.jsonl")
        self._lock = threading.Lock()
        self._seen_proposals: set = set()
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_seen_proposals()

    def _load_seen_proposals(self) -> None:
        """Load already-recorded proposal IDs to enforce idempotency."""
        if self._ledger_path.exists():
            with open(self._ledger_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            pid = record.get("proposal_id")
                            if pid:
                                self._seen_proposals.add(pid)
                        except json.JSONDecodeError:
                            continue

    def _append_record(self, record: Dict) -> None:
        with open(self._ledger_path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def record_live_spend(
        self,
        proposal_id: str,
        connector_name: str,
        vendor: str,
        category: str,
        amount: float,
        reference_id: str,
        operator_subject: str = "",
        provider_response: Optional[Dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[LiveSpendRecord]:
        """
        Record a completed live payment.

        Returns None if the proposal_id was already recorded (idempotency guard).
        """
        with self._lock:
            if proposal_id in self._seen_proposals:
                return None  # Idempotent — already recorded

            record = LiveSpendRecord(
                record_id=str(uuid.uuid4()),
                proposal_id=proposal_id,
                connector_name=connector_name,
                vendor=vendor,
                category=category,
                amount=amount,
                currency="USD",
                reference_id=reference_id,
                timestamp=_now_iso(),
                status="completed",
                operator_subject=operator_subject,
                provider_response=provider_response,
                idempotency_key=idempotency_key or proposal_id,
            )
            self._append_record(record.to_dict())
            self._seen_proposals.add(proposal_id)
            return record

    def record_failed_spend(
        self,
        proposal_id: str,
        connector_name: str,
        vendor: str,
        category: str,
        amount: float,
        error: str,
        idempotency_key: Optional[str] = None,
    ) -> LiveSpendRecord:
        """Record a failed payment attempt."""
        with self._lock:
            record = LiveSpendRecord(
                record_id=str(uuid.uuid4()),
                proposal_id=proposal_id,
                connector_name=connector_name,
                vendor=vendor,
                category=category,
                amount=amount,
                currency="USD",
                reference_id="",
                timestamp=_now_iso(),
                status="failed",
                error=error,
                idempotency_key=idempotency_key or proposal_id,
            )
            self._append_record(record.to_dict())
            return record

    def record_refund(
        self,
        proposal_id: str,
        connector_name: str,
        vendor: str,
        amount: float,
        reference_id: str,
        reason: str,
    ) -> LiveSpendRecord:
        """Record a refund."""
        with self._lock:
            record = LiveSpendRecord(
                record_id=str(uuid.uuid4()),
                proposal_id=proposal_id,
                connector_name=connector_name,
                vendor=vendor,
                category="refund",
                amount=amount,
                currency="USD",
                reference_id=reference_id,
                timestamp=_now_iso(),
                status="refunded",
                error=reason,
            )
            self._append_record(record.to_dict())
            return record

    def get_all_records(self, limit: int = 100) -> List[LiveSpendRecord]:
        """Return all records, most recent first."""
        with self._lock:
            records = []
            if self._ledger_path.exists():
                with open(self._ledger_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                d = json.loads(line)
                                records.append(LiveSpendRecord(**{
                                    k: d.get(k, v.default if hasattr(v, 'default') else None)
                                    for k, v in LiveSpendRecord.__dataclass_fields__.items()
                                    if k in d
                                }))
                            except (json.JSONDecodeError, TypeError):
                                continue
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records[:limit]

    def get_records_raw(self, limit: int = 100) -> List[Dict]:
        """Return raw dicts from the ledger."""
        with self._lock:
            records = []
            if self._ledger_path.exists():
                with open(self._ledger_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                records.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
            return records[:limit]

    def get_summary(self) -> Dict[str, Any]:
        """Return summary stats for the live ledger."""
        with self._lock:
            records = []
            if self._ledger_path.exists():
                with open(self._ledger_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                records.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue

            completed = [r for r in records if r.get("status") == "completed"]
            failed = [r for r in records if r.get("status") == "failed"]
            refunded = [r for r in records if r.get("status") == "refunded"]

            total_spent = sum(r.get("amount", 0) for r in completed)
            total_refunded = sum(r.get("amount", 0) for r in refunded)

            return {
                "total_records": len(records),
                "completed_count": len(completed),
                "failed_count": len(failed),
                "refunded_count": len(refunded),
                "total_spent": round(total_spent, 2),
                "total_refunded": round(total_refunded, 2),
                "net_spent": round(total_spent - total_refunded, 2),
                "currency": "USD",
            }

    def is_proposal_already_executed(self, proposal_id: str) -> bool:
        """Check if a proposal has already been executed (idempotency check)."""
        with self._lock:
            return proposal_id in self._seen_proposals

    def export_jsonl(self) -> str:
        """Return the raw JSONL content for export/backup."""
        with self._lock:
            if self._ledger_path.exists():
                return self._ledger_path.read_text()
            return ""


LIVE_SPEND_LEDGER = LiveSpendLedger()
