"""
SIMP Approval Queue — Sprint 43 (Sprint 43)

JSONL-backed, append-only approval queue for payment proposals.
Supports dual-control policy changes (two distinct operators required).
"""

import json
import os
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SIMP.ApprovalQueue")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class PaymentProposalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

PROPOSAL_EXPIRY_HOURS = 24

# ---------------------------------------------------------------------------
# Data dir
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _ensure_data_dir() -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    return _DATA_DIR


# ---------------------------------------------------------------------------
# PaymentProposal
# ---------------------------------------------------------------------------

@dataclass
class PaymentProposal:
    proposal_id: str = ""
    op_type: str = ""
    vendor: str = ""
    category: str = ""
    amount: float = 0.0
    currency: str = "USD"
    connector_name: str = ""
    description: str = ""
    submitted_by: str = ""
    submitted_at: str = ""
    status: str = PaymentProposalStatus.PENDING
    risk_flags: List[str] = field(default_factory=list)
    expires_at: str = ""
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None

    def __post_init__(self):
        if not self.proposal_id:
            self.proposal_id = str(uuid.uuid4())
        if not self.submitted_at:
            self.submitted_at = datetime.now(timezone.utc).isoformat()
        if not self.expires_at:
            expiry = datetime.now(timezone.utc) + timedelta(hours=PROPOSAL_EXPIRY_HOURS)
            self.expires_at = expiry.isoformat()

    def is_expired(self) -> bool:
        try:
            exp = datetime.fromisoformat(self.expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) > exp
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Risk flag computation
# ---------------------------------------------------------------------------

def _compute_risk_flags(proposal: PaymentProposal) -> List[str]:
    flags = []
    if proposal.amount > 15.0:
        flags.append("high_amount")
    if proposal.amount > 10.0:
        flags.append("above_half_limit")
    if proposal.vendor and len(proposal.vendor) < 3:
        flags.append("short_vendor_name")
    if not proposal.category:
        flags.append("missing_category")
    return flags


# ---------------------------------------------------------------------------
# ApprovalQueue — JSONL-backed, append-only
# ---------------------------------------------------------------------------

class ApprovalQueue:
    """
    Append-only approval queue backed by JSONL file.
    Records are event-sourced: each action appends a new event line.
    """

    def __init__(self, filepath: Optional[str] = None):
        _ensure_data_dir()
        self._filepath = filepath or os.path.join(_DATA_DIR, "financial_ops_proposals.jsonl")
        self._lock = threading.Lock()
        # In-memory cache rebuilt from events
        self._proposals: Dict[str, PaymentProposal] = {}
        self._rebuild_from_events()

    def _rebuild_from_events(self) -> None:
        """Replay events from JSONL to rebuild state."""
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
        """Apply a single event to in-memory state."""
        etype = event.get("type", "")
        pid = event.get("proposal_id", "")

        if etype == "proposal_created":
            p = PaymentProposal(
                proposal_id=pid,
                op_type=event.get("op_type", ""),
                vendor=event.get("vendor", ""),
                category=event.get("category", ""),
                amount=event.get("amount", 0.0),
                currency=event.get("currency", "USD"),
                connector_name=event.get("connector_name", ""),
                description=event.get("description", ""),
                submitted_by=event.get("submitted_by", ""),
                submitted_at=event.get("timestamp", ""),
                status=PaymentProposalStatus.PENDING,
                risk_flags=event.get("risk_flags", []),
                expires_at=event.get("expires_at", ""),
            )
            self._proposals[pid] = p

        elif etype == "proposal_approved":
            if pid in self._proposals:
                self._proposals[pid].status = PaymentProposalStatus.APPROVED
                self._proposals[pid].approved_by = event.get("operator_subject", "")
                self._proposals[pid].approved_at = event.get("timestamp", "")

        elif etype == "proposal_rejected":
            if pid in self._proposals:
                self._proposals[pid].status = PaymentProposalStatus.REJECTED
                self._proposals[pid].rejected_by = event.get("operator_subject", "")
                self._proposals[pid].rejected_at = event.get("timestamp", "")
                self._proposals[pid].rejection_reason = event.get("reason", "")

    def _append_event(self, event: Dict[str, Any]) -> None:
        """Append an event to the JSONL file (append-only, never delete)."""
        with open(self._filepath, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def submit_proposal(
        self,
        op_type: str,
        vendor: str,
        category: str,
        amount: float,
        connector_name: str,
        description: str = "",
        submitted_by: str = "system",
    ) -> PaymentProposal:
        """Submit a new payment proposal."""
        proposal = PaymentProposal(
            op_type=op_type,
            vendor=vendor,
            category=category,
            amount=amount,
            connector_name=connector_name,
            description=description,
            submitted_by=submitted_by,
        )
        proposal.risk_flags = _compute_risk_flags(proposal)

        event = {
            "type": "proposal_created",
            "proposal_id": proposal.proposal_id,
            "op_type": op_type,
            "vendor": vendor,
            "category": category,
            "amount": amount,
            "currency": proposal.currency,
            "connector_name": connector_name,
            "description": description,
            "submitted_by": submitted_by,
            "risk_flags": proposal.risk_flags,
            "expires_at": proposal.expires_at,
            "timestamp": proposal.submitted_at,
        }

        with self._lock:
            self._append_event(event)
            self._proposals[proposal.proposal_id] = proposal

        logger.info("Proposal %s submitted: $%.2f to %s", proposal.proposal_id, amount, vendor)
        return proposal

    def approve_proposal(self, proposal_id: str, operator_subject: str) -> PaymentProposal:
        """Approve a pending, non-expired proposal."""
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None:
                raise ValueError(f"Proposal {proposal_id!r} not found")

            if proposal.is_expired():
                proposal.status = PaymentProposalStatus.EXPIRED
                raise ValueError(f"Proposal {proposal_id!r} has expired")

            if proposal.status != PaymentProposalStatus.PENDING:
                raise ValueError(
                    f"Proposal {proposal_id!r} is {proposal.status}, not pending"
                )

            now = datetime.now(timezone.utc).isoformat()
            event = {
                "type": "proposal_approved",
                "proposal_id": proposal_id,
                "operator_subject": operator_subject,
                "timestamp": now,
            }
            self._append_event(event)
            proposal.status = PaymentProposalStatus.APPROVED
            proposal.approved_by = operator_subject
            proposal.approved_at = now

        logger.info("Proposal %s approved by %s", proposal_id, operator_subject)
        return proposal

    def reject_proposal(
        self, proposal_id: str, operator_subject: str, reason: str = ""
    ) -> PaymentProposal:
        """Reject a pending proposal."""
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None:
                raise ValueError(f"Proposal {proposal_id!r} not found")

            if proposal.status != PaymentProposalStatus.PENDING:
                raise ValueError(
                    f"Proposal {proposal_id!r} is {proposal.status}, not pending"
                )

            now = datetime.now(timezone.utc).isoformat()
            event = {
                "type": "proposal_rejected",
                "proposal_id": proposal_id,
                "operator_subject": operator_subject,
                "reason": reason,
                "timestamp": now,
            }
            self._append_event(event)
            proposal.status = PaymentProposalStatus.REJECTED
            proposal.rejected_by = operator_subject
            proposal.rejected_at = now
            proposal.rejection_reason = reason

        logger.info("Proposal %s rejected by %s: %s", proposal_id, operator_subject, reason)
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[PaymentProposal]:
        """Get a proposal by ID (event-replayed state)."""
        with self._lock:
            p = self._proposals.get(proposal_id)
            if p and p.status == PaymentProposalStatus.PENDING and p.is_expired():
                p.status = PaymentProposalStatus.EXPIRED
            return p

    def get_pending_proposals(self) -> List[PaymentProposal]:
        """Get all pending (non-expired) proposals."""
        with self._lock:
            result = []
            for p in self._proposals.values():
                if p.status == PaymentProposalStatus.PENDING:
                    if p.is_expired():
                        p.status = PaymentProposalStatus.EXPIRED
                    else:
                        result.append(p)
            return result

    def get_all_proposals(self) -> List[PaymentProposal]:
        """Get all proposals."""
        with self._lock:
            # Update expired statuses
            for p in self._proposals.values():
                if p.status == PaymentProposalStatus.PENDING and p.is_expired():
                    p.status = PaymentProposalStatus.EXPIRED
            return list(self._proposals.values())


# ---------------------------------------------------------------------------
# PolicyChangeQueue — dual control (two distinct operators required)
# ---------------------------------------------------------------------------

@dataclass
class PolicyChangeProposal:
    change_id: str = ""
    change_type: str = ""
    description: str = ""
    proposed_by: str = ""
    proposed_at: str = ""
    status: str = PaymentProposalStatus.PENDING
    first_approver: Optional[str] = None
    first_approved_at: Optional[str] = None
    second_approver: Optional[str] = None
    second_approved_at: Optional[str] = None

    def __post_init__(self):
        if not self.change_id:
            self.change_id = str(uuid.uuid4())
        if not self.proposed_at:
            self.proposed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolicyChangeQueue:
    """
    Dual-control policy change queue.
    Requires two distinct operators to approve a policy change.
    JSONL-backed, append-only.
    """

    def __init__(self, filepath: Optional[str] = None):
        _ensure_data_dir()
        self._filepath = filepath or os.path.join(_DATA_DIR, "financial_ops_policy_changes.jsonl")
        self._lock = threading.Lock()
        self._changes: Dict[str, PolicyChangeProposal] = {}
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
        cid = event.get("change_id", "")

        if etype == "policy_change_proposed":
            self._changes[cid] = PolicyChangeProposal(
                change_id=cid,
                change_type=event.get("change_type", ""),
                description=event.get("description", ""),
                proposed_by=event.get("proposed_by", ""),
                proposed_at=event.get("timestamp", ""),
            )
        elif etype == "policy_change_approved":
            if cid in self._changes:
                change = self._changes[cid]
                operator = event.get("operator_subject", "")
                ts = event.get("timestamp", "")
                if change.first_approver is None:
                    change.first_approver = operator
                    change.first_approved_at = ts
                elif change.second_approver is None and operator != change.first_approver:
                    change.second_approver = operator
                    change.second_approved_at = ts
                    change.status = PaymentProposalStatus.APPROVED

    def _append_event(self, event: Dict[str, Any]) -> None:
        with open(self._filepath, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def submit_change(
        self, change_type: str, description: str, proposed_by: str
    ) -> PolicyChangeProposal:
        change = PolicyChangeProposal(
            change_type=change_type,
            description=description,
            proposed_by=proposed_by,
        )
        event = {
            "type": "policy_change_proposed",
            "change_id": change.change_id,
            "change_type": change_type,
            "description": description,
            "proposed_by": proposed_by,
            "timestamp": change.proposed_at,
        }
        with self._lock:
            self._append_event(event)
            self._changes[change.change_id] = change
        return change

    def approve_change(self, change_id: str, operator_subject: str) -> PolicyChangeProposal:
        with self._lock:
            change = self._changes.get(change_id)
            if change is None:
                raise ValueError(f"Policy change {change_id!r} not found")

            if change.status != PaymentProposalStatus.PENDING:
                raise ValueError(f"Policy change {change_id!r} is {change.status}")

            # Dual control: proposer cannot be approver
            if operator_subject == change.proposed_by and change.first_approver is None:
                raise ValueError("Proposer cannot be the first approver (dual control)")

            # Same operator cannot approve twice
            if change.first_approver == operator_subject:
                raise ValueError("Same operator cannot approve twice (dual control)")

            now = datetime.now(timezone.utc).isoformat()
            event = {
                "type": "policy_change_approved",
                "change_id": change_id,
                "operator_subject": operator_subject,
                "timestamp": now,
            }
            self._append_event(event)

            if change.first_approver is None:
                change.first_approver = operator_subject
                change.first_approved_at = now
            elif operator_subject != change.first_approver:
                change.second_approver = operator_subject
                change.second_approved_at = now
                change.status = PaymentProposalStatus.APPROVED

        return change

    def get_change(self, change_id: str) -> Optional[PolicyChangeProposal]:
        with self._lock:
            return self._changes.get(change_id)

    def get_all_changes(self) -> List[PolicyChangeProposal]:
        with self._lock:
            return list(self._changes.values())


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

APPROVAL_QUEUE = ApprovalQueue()
POLICY_CHANGE_QUEUE = PolicyChangeQueue()
