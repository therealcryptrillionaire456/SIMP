"""
SIMP FinancialOps Approval Queue — Sprint 43

Stores proposed payments in an append-only, durable JSONL ledger
pending manual approval or rejection.

Design rules:
- Append-only: records are never deleted. Rejections add a rejection record.
- Dual control: policy changes require two distinct operator identities.
- Proposal state machine: pending -> approved | rejected (one-way transitions).
- No real payment execution in this module.
"""

import json
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaymentProposalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class PaymentProposal:
    proposal_id: str
    created_at: str
    requester_agent_id: str
    vendor: str
    category: str
    would_spend: float
    currency: str
    description: str
    connector_name: str
    status: str
    risk_flags: List[str] = field(default_factory=list)
    dry_run_result: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    expires_at: Optional[str] = None


class ApprovalQueue:
    """Append-only JSONL-backed approval queue for payment proposals."""

    def __init__(self, ledger_path: Optional[str] = None):
        self._ledger_path = Path(ledger_path or "data/financial_ops_proposals.jsonl")
        self._lock = threading.Lock()
        self._seen_vendors: set = set()
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def _append_event(self, event: Dict) -> None:
        with open(self._ledger_path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def _load_events(self) -> List[Dict]:
        events = []
        if self._ledger_path.exists():
            with open(self._ledger_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        return events

    def submit_proposal(self, requester_agent_id: str, vendor: str, category: str,
                        would_spend: float, description: str, connector_name: str,
                        dry_run_result: Optional[str] = None) -> PaymentProposal:
        with self._lock:
            proposal_id = str(uuid.uuid4())
            now = _now_iso()
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            risk_flags = []
            if would_spend > 15.00:
                risk_flags.append("near_daily_limit")
            if would_spend > 10.00:
                risk_flags.append("high_value")
            if vendor.lower() not in self._seen_vendors:
                risk_flags.append("new_vendor")
            self._seen_vendors.add(vendor.lower())

            proposal = PaymentProposal(
                proposal_id=proposal_id, created_at=now,
                requester_agent_id=requester_agent_id, vendor=vendor,
                category=category, would_spend=would_spend, currency="USD",
                description=description, connector_name=connector_name,
                status=PaymentProposalStatus.PENDING, risk_flags=risk_flags,
                dry_run_result=dry_run_result, expires_at=expires_at,
            )
            self._append_event({"type": "proposal_created", **asdict(proposal)})
            return proposal

    def approve_proposal(self, proposal_id: str, operator_subject: str) -> Tuple[bool, Optional[str]]:
        with self._lock:
            proposal = self._get_proposal_unlocked(proposal_id)
            if proposal is None:
                return (False, f"Proposal '{proposal_id}' not found.")
            if proposal.status != PaymentProposalStatus.PENDING:
                return (False, f"Proposal is already '{proposal.status}', cannot approve.")
            if proposal.expires_at:
                try:
                    if datetime.now(timezone.utc) > datetime.fromisoformat(proposal.expires_at):
                        return (False, "Proposal has expired.")
                except (ValueError, TypeError):
                    pass
            self._append_event({"type": "proposal_approved", "proposal_id": proposal_id, "operator_subject": operator_subject, "timestamp": _now_iso()})
            return (True, None)

    def reject_proposal(self, proposal_id: str, operator_subject: str, reason: str) -> Tuple[bool, Optional[str]]:
        with self._lock:
            proposal = self._get_proposal_unlocked(proposal_id)
            if proposal is None:
                return (False, f"Proposal '{proposal_id}' not found.")
            if proposal.status != PaymentProposalStatus.PENDING:
                return (False, f"Proposal is already '{proposal.status}', cannot reject.")
            self._append_event({"type": "proposal_rejected", "proposal_id": proposal_id, "operator_subject": operator_subject, "reason": reason, "timestamp": _now_iso()})
            return (True, None)

    def get_proposal(self, proposal_id: str) -> Optional[PaymentProposal]:
        with self._lock:
            return self._get_proposal_unlocked(proposal_id)

    def _get_proposal_unlocked(self, proposal_id: str) -> Optional[PaymentProposal]:
        events = [e for e in self._load_events() if e.get("proposal_id") == proposal_id]
        return self._compute_current_state(events) if events else None

    def get_pending_proposals(self) -> List[PaymentProposal]:
        with self._lock:
            now = datetime.now(timezone.utc)
            result = []
            for p in self._get_all_proposals_unlocked():
                if p.status != PaymentProposalStatus.PENDING:
                    continue
                if p.expires_at:
                    try:
                        if now > datetime.fromisoformat(p.expires_at):
                            continue
                    except (ValueError, TypeError):
                        pass
                result.append(p)
            return result

    def get_all_proposals(self, limit: int = 50) -> List[PaymentProposal]:
        with self._lock:
            all_p = self._get_all_proposals_unlocked()
            all_p.sort(key=lambda p: p.created_at, reverse=True)
            return all_p[:limit]

    def _get_all_proposals_unlocked(self) -> List[PaymentProposal]:
        events = self._load_events()
        grouped: Dict[str, List[Dict]] = {}
        for e in events:
            pid = e.get("proposal_id")
            if pid:
                grouped.setdefault(pid, []).append(e)
        return [p for pid, pevts in grouped.items() if (p := self._compute_current_state(pevts)) is not None]

    def _compute_current_state(self, events: List[Dict]) -> Optional[PaymentProposal]:
        proposal = None
        for event in events:
            etype = event.get("type")
            if etype == "proposal_created":
                proposal = PaymentProposal(
                    proposal_id=event["proposal_id"], created_at=event.get("created_at", ""),
                    requester_agent_id=event.get("requester_agent_id", ""), vendor=event.get("vendor", ""),
                    category=event.get("category", ""), would_spend=event.get("would_spend", 0.0),
                    currency=event.get("currency", "USD"), description=event.get("description", ""),
                    connector_name=event.get("connector_name", ""), status=event.get("status", "pending"),
                    risk_flags=event.get("risk_flags", []), dry_run_result=event.get("dry_run_result"),
                    expires_at=event.get("expires_at"),
                )
            elif etype == "proposal_approved" and proposal:
                proposal.status = PaymentProposalStatus.APPROVED
                proposal.approved_by = event.get("operator_subject")
                proposal.approved_at = event.get("timestamp")
            elif etype == "proposal_rejected" and proposal:
                proposal.status = PaymentProposalStatus.REJECTED
                proposal.rejected_by = event.get("operator_subject")
                proposal.rejected_at = event.get("timestamp")
                proposal.rejection_reason = event.get("reason")
        return proposal


@dataclass
class PolicyChangeRecord:
    change_id: str
    description: str
    requested_by: str
    requested_at: str
    first_approval_by: Optional[str] = None
    first_approval_at: Optional[str] = None
    second_approval_by: Optional[str] = None
    second_approval_at: Optional[str] = None
    status: str = "pending"


class PolicyChangeQueue:
    """Dual-control queue for policy changes. Two distinct approvers required."""

    def __init__(self, ledger_path: Optional[str] = None):
        self._ledger_path = Path(ledger_path or "data/financial_ops_policy_changes.jsonl")
        self._lock = threading.Lock()
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def _append_event(self, event: Dict) -> None:
        with open(self._ledger_path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def _load_events(self) -> List[Dict]:
        events = []
        if self._ledger_path.exists():
            with open(self._ledger_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        return events

    def submit_policy_change(self, description: str, requested_by: str) -> PolicyChangeRecord:
        with self._lock:
            change_id = str(uuid.uuid4())
            record = PolicyChangeRecord(change_id=change_id, description=description, requested_by=requested_by, requested_at=_now_iso())
            self._append_event({"type": "policy_change_requested", "change_id": change_id, "description": description, "requested_by": requested_by, "timestamp": _now_iso()})
            return record

    def approve_policy_change(self, change_id: str, operator_subject: str) -> Tuple[bool, str]:
        with self._lock:
            record = self._get_record_unlocked(change_id)
            if record is None:
                return (False, f"Policy change '{change_id}' not found.")
            if record.status == "approved":
                return (False, "Policy change already fully approved.")
            if record.first_approval_by is None:
                self._append_event({"type": "policy_change_first_approval", "change_id": change_id, "operator_subject": operator_subject, "timestamp": _now_iso()})
                return (True, "First approval recorded. Awaiting second approver.")
            elif record.first_approval_by == operator_subject:
                return (False, "Same operator cannot approve twice.")
            else:
                self._append_event({"type": "policy_change_second_approval", "change_id": change_id, "operator_subject": operator_subject, "timestamp": _now_iso()})
                return (True, "Second approval recorded. Policy change approved.")

    def get_record(self, change_id: str) -> Optional[PolicyChangeRecord]:
        with self._lock:
            return self._get_record_unlocked(change_id)

    def _get_record_unlocked(self, change_id: str) -> Optional[PolicyChangeRecord]:
        events = [e for e in self._load_events() if e.get("change_id") == change_id]
        if not events:
            return None
        record = None
        for event in events:
            etype = event.get("type")
            if etype == "policy_change_requested":
                record = PolicyChangeRecord(change_id=event["change_id"], description=event.get("description", ""), requested_by=event.get("requested_by", ""), requested_at=event.get("timestamp", ""))
            elif etype == "policy_change_first_approval" and record:
                record.first_approval_by = event.get("operator_subject")
                record.first_approval_at = event.get("timestamp")
                record.status = "partially_approved"
            elif etype == "policy_change_second_approval" and record:
                record.second_approval_by = event.get("operator_subject")
                record.second_approval_at = event.get("timestamp")
                record.status = "approved"
        return record


APPROVAL_QUEUE = ApprovalQueue()
POLICY_CHANGE_QUEUE = PolicyChangeQueue()
