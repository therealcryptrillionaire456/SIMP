"""
T41: Multi-Signature Approval for Large Moves
============================================
Large moves (>10% of portfolio) require multiple approvals.

This module implements a multi-sig approval workflow:
1. Large moves are flagged and pending approval
2. Required approvers must approve within timeout
3. All approvers must approve for execution to proceed
4. Any approver can reject and block the move

Usage:
    approver = MultiSigApprover(required_signatures=2)
    pending = approver.request_approval("buy", 10000.0, "BTC-USD", reason="arb_opportunity")
    if pending.approved:
        executor.execute(pending)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger("multisig_approver")

# ── Constants ───────────────────────────────────────────────────────────

APPROVAL_TIMEOUT_SECONDS = 300  # 5 minutes to approve
STATE_PATH = Path("data/multisig_approvals.json")
LARGE_MOVE_THRESHOLD_PCT = 0.10  # 10% of portfolio

# Default approvers (in production, these would be real people/Slack IDs)
DEFAULT_APPROVERS = ["admin", "trader_ops", "risk_manager"]


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MoveType(Enum):
    BUY = "buy"
    SELL = "sell"
    TRANSFER = "transfer"
    WITHDRAW = "withdraw"


@dataclass
class ApprovalRequest:
    """A request for multi-sig approval."""
    request_id: str
    move_type: str  # buy, sell, transfer, withdraw
    amount_usd: float
    symbol: str
    reason: str
    requested_by: str
    requested_at: str
    expires_at: str
    status: str
    approvals: Dict[str, str] = field(default_factory=dict)  # approver_id -> timestamp
    rejections: List[str] = field(default_factory=list)
    required_signatures: int = 2

    def is_approved(self) -> bool:
        return len(self.approvals) >= self.required_signatures and self.status == ApprovalStatus.APPROVED.value

    def is_rejected(self) -> bool:
        return len(self.rejections) > 0 or self.status == ApprovalStatus.REJECTED.value

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > datetime.fromisoformat(self.expires_at)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiSigApprover:
    """
    Multi-signature approval system for large moves.
    
    Thread-safe. Requires multiple approvals before large moves execute.
    """

    def __init__(
        self,
        required_signatures: int = 2,
        approvers: Optional[List[str]] = None,
        state_path: str = str(STATE_PATH),
        timeout_seconds: int = APPROVAL_TIMEOUT_SECONDS,
        large_move_threshold_pct: float = LARGE_MOVE_THRESHOLD_PCT,
    ):
        self._lock = threading.Lock()
        self.required_signatures = required_signatures
        self.approvers: Set[str] = set(approvers or DEFAULT_APPROVERS)
        self.state_path = Path(state_path)
        self.timeout_seconds = timeout_seconds
        self.large_move_threshold_pct = large_move_threshold_pct
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._approval_history: List[ApprovalRequest] = []
        self._load_state()

    def _load_state(self) -> None:
        """Load pending requests from disk."""
        try:
            if self.state_path.exists():
                with open(self.state_path) as f:
                    data = json.load(f)
                    self._pending_requests = {
                        k: ApprovalRequest(**v) 
                        for k, v in data.get("pending", {}).items()
                    }
                    self._approval_history = [
                        ApprovalRequest(**r) for r in data.get("history", [])
                    ]
                    log.info(f"Loaded {len(self._pending_requests)} pending requests")
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"Failed to load state: {e}")

    def _save_state(self) -> None:
        """Persist pending requests to disk."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump({
                    "pending": {k: v.to_dict() for k, v in self._pending_requests.items()},
                    "history": [r.to_dict() for r in self._approval_history[-100:]],  # Keep last 100
                }, f, indent=2)
        except OSError as e:
            log.error(f"Failed to save state: {e}")

    def requires_approval(self, amount_usd: float, portfolio_value_usd: float) -> bool:
        """Check if a move requires multi-sig approval."""
        if portfolio_value_usd <= 0:
            return amount_usd >= 1000  # Default to $1000 minimum
        return (amount_usd / portfolio_value_usd) >= self.large_move_threshold_pct

    def request_approval(
        self,
        move_type: str,
        amount_usd: float,
        symbol: str,
        reason: str = "",
        requested_by: str = "system",
        portfolio_value_usd: float = 0.0,
    ) -> ApprovalRequest:
        """
        Request multi-sig approval for a large move.
        
        Args:
            move_type: buy, sell, transfer, withdraw
            amount_usd: USD value of the move
            symbol: Trading pair or asset
            reason: Human-readable reason for the move
            requested_by: Who is requesting (system, trader, bot)
            portfolio_value_usd: Total portfolio value to check threshold
            
        Returns:
            ApprovalRequest with pending status
        """
        with self._lock:
            # Check if approval is required
            if not self.requires_approval(amount_usd, portfolio_value_usd):
                # Auto-approve small moves
                request = ApprovalRequest(
                    request_id=uuid.uuid4().hex[:12],
                    move_type=move_type,
                    amount_usd=amount_usd,
                    symbol=symbol,
                    reason=reason,
                    requested_by=requested_by,
                    requested_at=datetime.now(timezone.utc).isoformat(),
                    expires_at=(datetime.now(timezone.utc) + timedelta(seconds=self.timeout_seconds)).isoformat(),
                    status=ApprovalStatus.APPROVED.value,
                    required_signatures=0,  # Auto-approved
                )
                log.info(f"Auto-approved small move: {move_type} ${amount_usd} {symbol}")
                return request

            # Create pending request
            request = ApprovalRequest(
                request_id=uuid.uuid4().hex[:12],
                move_type=move_type,
                amount_usd=amount_usd,
                symbol=symbol,
                reason=reason,
                requested_by=requested_by,
                requested_at=datetime.now(timezone.utc).isoformat(),
                expires_at=(datetime.now(timezone.utc) + timedelta(seconds=self.timeout_seconds)).isoformat(),
                status=ApprovalStatus.PENDING.value,
                required_signatures=self.required_signatures,
            )
            self._pending_requests[request.request_id] = request
            self._save_state()
            
            log.info(f"Approval requested: {request.request_id} - {move_type} ${amount_usd} {symbol}")
            log.info(f"Required signatures: {self.required_signatures}/{len(self.approvers)}")
            
            return request

    def approve(self, request_id: str, approver_id: str) -> ApprovalRequest:
        """
        Approve a pending request.
        
        Args:
            request_id: The approval request ID
            approver_id: Who is approving
            
        Returns:
            Updated ApprovalRequest
        """
        with self._lock:
            if request_id not in self._pending_requests:
                raise ValueError(f"Request {request_id} not found")
            
            request = self._pending_requests[request_id]
            
            if request.is_expired():
                request.status = ApprovalStatus.EXPIRED.value
                self._move_to_history(request)
                raise ValueError(f"Request {request_id} has expired")
            
            if request.is_rejected():
                raise ValueError(f"Request {request_id} was rejected")
            
            if approver_id not in self.approvers:
                raise ValueError(f"Approver {approver_id} not authorized")
            
            if approver_id in request.approvals:
                raise ValueError(f"Approver {approver_id} already approved")
            
            # Record approval
            request.approvals[approver_id] = datetime.now(timezone.utc).isoformat()
            log.info(f"Approved: {request_id} by {approver_id} ({len(request.approvals)}/{request.required_signatures})")
            
            # Check if fully approved
            if len(request.approvals) >= request.required_signatures:
                request.status = ApprovalStatus.APPROVED.value
                self._move_to_history(request)
                log.info(f"Request {request_id} fully approved!")
            
            self._save_state()
            return request

    def reject(self, request_id: str, rejector_id: str, reason: str = "") -> ApprovalRequest:
        """
        Reject a pending request.
        
        Args:
            request_id: The approval request ID
            rejector_id: Who is rejecting
            reason: Why it's being rejected
            
        Returns:
            Updated ApprovalRequest (rejected)
        """
        with self._lock:
            if request_id not in self._pending_requests:
                raise ValueError(f"Request {request_id} not found")
            
            request = self._pending_requests[request_id]
            request.rejections.append(rejector_id)
            request.status = ApprovalStatus.REJECTED.value
            
            log.warning(f"Rejected: {request_id} by {rejector_id} - {reason}")
            self._move_to_history(request)
            self._save_state()
            
            return request

    def cancel(self, request_id: str) -> ApprovalRequest:
        """Cancel a pending request."""
        with self._lock:
            if request_id not in self._pending_requests:
                raise ValueError(f"Request {request_id} not found")
            
            request = self._pending_requests[request_id]
            request.status = ApprovalStatus.CANCELLED.value
            self._move_to_history(request)
            self._save_state()
            
            log.info(f"Cancelled: {request_id}")
            return request

    def get_pending(self) -> List[ApprovalRequest]:
        """Get all pending requests."""
        with self._lock:
            # Check for expired requests
            expired = []
            for req_id, request in self._pending_requests.items():
                if request.is_expired():
                    request.status = ApprovalStatus.EXPIRED.value
                    expired.append(req_id)
            
            for req_id in expired:
                self._move_to_history(self._pending_requests.pop(req_id))
            
            if expired:
                self._save_state()
            
            return list(self._pending_requests.values())

    def get_history(self, limit: int = 50) -> List[ApprovalRequest]:
        """Get approval history."""
        with self._lock:
            return self._approval_history[-limit:]

    def _move_to_history(self, request: ApprovalRequest) -> None:
        """Move a request from pending to history."""
        if request.request_id in self._pending_requests:
            del self._pending_requests[request.request_id]
        self._approval_history.append(request)
        # Keep only last 100 in memory
        if len(self._approval_history) > 100:
            self._approval_history = self._approval_history[-100:]


# ── Module-level singleton ──────────────────────────────────────────────

_approver: Optional[MultiSigApprover] = None


def get_multisig_approver(**kwargs) -> MultiSigApprover:
    """Get or create the global MultiSigApprover singleton."""
    global _approver
    if _approver is None:
        _approver = MultiSigApprover(**kwargs)
    return _approver


# ── Demo / Test ─────────────────────────────────────────────────────────

def demo_multisig():
    """Demonstrate the multi-sig approval workflow."""
    print("=" * 60)
    print("T41 — Multi-Sig Approval Demo")
    print("=" * 60)

    approver = MultiSigApprover(required_signatures=2)
    portfolio = 50000.0  # $50k portfolio

    # Small move - auto-approved
    print("\n[1] Small move (auto-approved):")
    small_request = approver.request_approval("buy", 100.0, "BTC-USD", "test", portfolio_value_usd=portfolio)
    print(f"    {small_request.request_id}: {small_request.status} (no approval needed)")

    # Large move - requires approval
    print("\n[2] Large move (requires multi-sig):")
    large_request = approver.request_approval("buy", 10000.0, "BTC-USD", "arb_opportunity", portfolio_value_usd=portfolio)
    print(f"    {large_request.request_id}: {large_request.status}")
    print(f"    Amount: ${large_request.amount_usd} ({large_request.amount_usd/portfolio*100:.1f}% of portfolio)")
    print(f"    Required: {large_request.required_signatures} approvals")

    # Approve from first approver
    print("\n[3] First approval (admin):")
    request = approver.approve(large_request.request_id, "admin")
    print(f"    Status: {request.status}, Approvals: {len(request.approvals)}/{request.required_signatures}")

    # Try to approve again
    print("\n[4] Second approval (trader_ops):")
    request = approver.approve(large_request.request_id, "trader_ops")
    print(f"    Status: {request.status}, Approvals: {len(request.approvals)}/{request.required_signatures}")

    # Check history
    print("\n[5] Approval history:")
    history = approver.get_history()
    for r in history[-3:]:
        print(f"    {r.request_id}: {r.move_type} ${r.amount_usd} {r.symbol} - {r.status}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_multisig()
