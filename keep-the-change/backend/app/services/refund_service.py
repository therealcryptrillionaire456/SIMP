"""
Refund processing service for KEEPTHECHANGE.com

This service handles refund requests, processing, tracking, and reconciliation.
"""

import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import json
from enum import Enum

logger = logging.getLogger(__name__)


class RefundStatus(str, Enum):
    """Refund status enumeration"""
    REQUESTED = "requested"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class RefundReason(str, Enum):
    """Refund reason enumeration"""
    DUPLICATE = "duplicate"
    FRAUDULENT = "fraudulent"
    REQUESTED_BY_CUSTOMER = "requested_by_customer"
    PRODUCT_UNSATISFACTORY = "product_unsatisfactory"
    SERVICE_UNSATISFACTORY = "service_unsatisfactory"
    PRICE_DISCREPANCY = "price_discrepancy"
    CANCELLED = "cancelled"
    OTHER = "other"


@dataclass
class RefundRequest:
    """Refund request definition"""
    refund_id: str
    receipt_id: str
    user_id: str
    amount: float
    currency: str = "USD"
    reason: RefundReason = RefundReason.REQUESTED_BY_CUSTOMER
    reason_details: str = ""
    status: RefundStatus = RefundStatus.REQUESTED
    requested_at: datetime = None
    processed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processor_id: Optional[str] = None
    transaction_id: Optional[str] = None
    refund_transaction_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.requested_at is None:
            self.requested_at = datetime.utcnow()
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "refund_id": self.refund_id,
            "receipt_id": self.receipt_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "reason": self.reason.value,
            "reason_details": self.reason_details,
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processor_id": self.processor_id,
            "transaction_id": self.transaction_id,
            "refund_transaction_id": self.refund_transaction_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class RefundPolicy:
    """Refund policy definition"""
    policy_id: str
    name: str
    description: str
    refund_period_days: int = 30
    partial_refunds_allowed: bool = True
    requires_approval: bool = False
    auto_approve_threshold: float = 50.0  # Auto-approve refunds under $50
    allowed_reasons: List[RefundReason] = None
    excluded_products: List[str] = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.allowed_reasons is None:
            self.allowed_reasons = [
                RefundReason.REQUESTED_BY_CUSTOMER,
                RefundReason.PRODUCT_UNSATISFACTORY,
                RefundReason.SERVICE_UNSATISFACTORY,
                RefundReason.PRICE_DISCREPANCY,
                RefundReason.DUPLICATE,
                RefundReason.FRAUDULENT,
                RefundReason.CANCELLED,
                RefundReason.OTHER
            ]
        if self.excluded_products is None:
            self.excluded_products = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "refund_period_days": self.refund_period_days,
            "partial_refunds_allowed": self.partial_refunds_allowed,
            "requires_approval": self.requires_approval,
            "auto_approve_threshold": self.auto_approve_threshold,
            "allowed_reasons": [reason.value for reason in self.allowed_reasons],
            "excluded_products": self.excluded_products,
            "is_active": self.is_active
        }
    
    def is_refund_allowed(
        self,
        purchase_date: datetime,
        amount: float,
        reason: RefundReason
    ) -> Tuple[bool, str]:
        """Check if refund is allowed based on policy"""
        now = datetime.utcnow()
        days_since_purchase = (now - purchase_date).days
        
        # Check refund period
        if days_since_purchase > self.refund_period_days:
            return False, f"Refund period expired ({days_since_purchase} days > {self.refund_period_days} days)"
        
        # Check allowed reasons
        if reason not in self.allowed_reasons:
            return False, f"Refund reason '{reason.value}' not allowed"
        
        # Check if approval is required
        if self.requires_approval and amount > self.auto_approve_threshold:
            return True, "Approval required"
        
        return True, "Refund allowed"


class RefundService:
    """Refund processing service"""
    
    def __init__(self, payment_service=None, billing_service=None):
        self.payment_service = payment_service
        self.billing_service = billing_service
        self.refund_requests: Dict[str, RefundRequest] = {}
        self.refund_policies: Dict[str, RefundPolicy] = {}
        self._initialize_default_policies()
    
    def _initialize_default_policies(self):
        """Initialize default refund policies"""
        self.refund_policies = {
            "standard": RefundPolicy(
                policy_id="standard",
                name="Standard Refund Policy",
                description="Standard 30-day refund policy for most purchases",
                refund_period_days=30,
                partial_refunds_allowed=True,
                requires_approval=False,
                auto_approve_threshold=100.0
            ),
            "subscription": RefundPolicy(
                policy_id="subscription",
                name="Subscription Refund Policy",
                description="Refund policy for subscription purchases",
                refund_period_days=14,
                partial_refunds_allowed=False,
                requires_approval=True,
                auto_approve_threshold=50.0
            ),
            "digital": RefundPolicy(
                policy_id="digital",
                name="Digital Product Refund Policy",
                description="Refund policy for digital products and services",
                refund_period_days=7,
                partial_refunds_allowed=False,
                requires_approval=True,
                auto_approve_threshold=25.0
            )
        }
    
    async def request_refund(
        self,
        receipt_id: str,
        user_id: str,
        amount: float,
        reason: RefundReason,
        reason_details: str = "",
        policy_id: str = "standard"
    ) -> Tuple[bool, Optional[RefundRequest], str]:
        """Request a refund"""
        try:
            # Get refund policy
            policy = self.refund_policies.get(policy_id)
            if not policy:
                return False, None, f"Refund policy {policy_id} not found"
            
            # In a real implementation, we would fetch the receipt from billing service
            # For now, simulate receipt lookup
            receipt = await self._get_receipt_simulated(receipt_id)
            if not receipt:
                return False, None, f"Receipt {receipt_id} not found"
            
            # Check if user owns the receipt
            if receipt["user_id"] != user_id:
                return False, None, "User does not own this receipt"
            
            # Check if amount is valid
            if amount <= 0:
                return False, None, "Refund amount must be positive"
            
            if amount > receipt["total_amount"]:
                return False, None, f"Refund amount exceeds purchase amount ({receipt['total_amount']})"
            
            # Check refund policy
            purchase_date = datetime.fromisoformat(receipt["paid_at"])
            allowed, message = policy.is_refund_allowed(purchase_date, amount, reason)
            
            if not allowed:
                return False, None, f"Refund not allowed: {message}"
            
            # Generate refund ID
            refund_id = f"ref_{uuid.uuid4().hex[:16]}"
            
            # Create refund request
            refund_request = RefundRequest(
                refund_id=refund_id,
                receipt_id=receipt_id,
                user_id=user_id,
                amount=amount,
                currency=receipt["currency"],
                reason=reason,
                reason_details=reason_details,
                status=RefundStatus.REQUESTED,
                metadata={
                    "policy_id": policy_id,
                    "original_amount": receipt["total_amount"],
                    "purchase_date": receipt["paid_at"],
                    "requires_approval": message == "Approval required"
                }
            )
            
            # Store refund request
            self.refund_requests[refund_id] = refund_request
            
            # Auto-approve if allowed by policy
            if not policy.requires_approval or amount <= policy.auto_approve_threshold:
                await self.approve_refund(refund_id, "system", "Auto-approved per policy")
            
            logger.info(f"Refund requested: {refund_id} for receipt {receipt_id}, amount {amount}")
            return True, refund_request, "Refund requested successfully"
            
        except Exception as e:
            logger.error(f"Error requesting refund: {str(e)}")
            return False, None, f"Error requesting refund: {str(e)}"
    
    async def approve_refund(
        self,
        refund_id: str,
        processor_id: str,
        notes: str = ""
    ) -> Tuple[bool, Optional[RefundRequest], str]:
        """Approve a refund request"""
        try:
            refund_request = await self.get_refund_request(refund_id)
            if not refund_request:
                return False, None, f"Refund request {refund_id} not found"
            
            if refund_request.status != RefundStatus.REQUESTED:
                return False, None, f"Refund request is not in requested state: {refund_request.status}"
            
            # Update status
            refund_request.status = RefundStatus.PENDING
            refund_request.processor_id = processor_id
            refund_request.processed_at = datetime.utcnow()
            refund_request.updated_at = datetime.utcnow()
            
            if notes:
                refund_request.metadata["approval_notes"] = notes
            
            logger.info(f"Refund approved: {refund_id} by {processor_id}")
            return True, refund_request, "Refund approved successfully"
            
        except Exception as e:
            logger.error(f"Error approving refund: {str(e)}")
            return False, None, f"Error approving refund: {str(e)}"
    
    async def process_refund(
        self,
        refund_id: str,
        processor_id: str
    ) -> Tuple[bool, Optional[RefundRequest], str]:
        """Process a refund (execute the payment reversal)"""
        try:
            refund_request = await self.get_refund_request(refund_id)
            if not refund_request:
                return False, None, f"Refund request {refund_id} not found"
            
            if refund_request.status != RefundStatus.PENDING:
                return False, None, f"Refund request cannot be processed in state: {refund_request.status}"
            
            # Update status
            refund_request.status = RefundStatus.PROCESSING
            refund_request.processor_id = processor_id
            refund_request.updated_at = datetime.utcnow()
            
            # Process refund through payment service
            if self.payment_service:
                # Try to get transaction_id from receipt
                transaction_id = None
                
                if self.billing_service:
                    # Get receipt from billing service
                    receipt = await self.billing_service.get_receipt(refund_request.receipt_id)
                    if receipt and hasattr(receipt, 'transaction_id'):
                        transaction_id = receipt.transaction_id
                
                if not transaction_id:
                    # Fallback: try to use process_refund if available
                    if hasattr(self.payment_service, 'process_refund'):
                        # Use the old process_refund method
                        payment_result = await self.payment_service.process_refund(
                            receipt_id=refund_request.receipt_id,
                            amount=refund_request.amount,
                            currency=refund_request.currency,
                            reason=refund_request.reason.value
                        )
                        
                        if payment_result.success:
                            # Update refund request with transaction details
                            refund_request.status = RefundStatus.COMPLETED
                            refund_request.completed_at = datetime.utcnow()
                            refund_request.refund_transaction_id = payment_result.transaction_id
                            refund_request.metadata["payment_result"] = payment_result.to_dict()
                            
                            logger.info(f"Refund processed successfully: {refund_id}, transaction {payment_result.transaction_id}")
                            return True, refund_request, "Refund processed successfully"
                        else:
                            # Refund failed
                            refund_request.status = RefundStatus.FAILED
                            refund_request.metadata["payment_error"] = payment_result.error_message
                            
                            logger.error(f"Refund processing failed: {refund_id}, error: {payment_result.error_message}")
                            return False, refund_request, f"Refund processing failed: {payment_result.error_message}"
                    else:
                        # No way to get transaction_id, simulate refund
                        refund_request.status = RefundStatus.COMPLETED
                        refund_request.completed_at = datetime.utcnow()
                        refund_request.refund_transaction_id = f"ref_tx_{uuid.uuid4().hex[:16]}"
                        refund_request.metadata["payment_result"] = {"simulated": True}
                        
                        logger.info(f"Refund processed (simulated, no transaction_id): {refund_id}")
                        return True, refund_request, "Refund processed successfully (simulated)"
                
                # We have transaction_id, process refund
                success, refund_transaction_id, message = await self.payment_service.refund_payment(
                    transaction_id=transaction_id,
                    amount=refund_request.amount,
                    reason=refund_request.reason.value
                )
                
                if success:
                    # Update refund request with transaction details
                    refund_request.status = RefundStatus.COMPLETED
                    refund_request.completed_at = datetime.utcnow()
                    refund_request.refund_transaction_id = refund_transaction_id
                    refund_request.metadata["payment_result"] = {
                        "success": True,
                        "transaction_id": refund_transaction_id,
                        "message": message
                    }
                    
                    logger.info(f"Refund processed successfully: {refund_id}, transaction {refund_transaction_id}")
                    return True, refund_request, "Refund processed successfully"
                else:
                    # Refund failed
                    refund_request.status = RefundStatus.FAILED
                    refund_request.metadata["payment_error"] = message
                    
                    logger.error(f"Refund processing failed: {refund_id}, error: {message}")
                    return False, refund_request, f"Refund processing failed: {message}"
            else:
                # No payment service, simulate success
                refund_request.status = RefundStatus.COMPLETED
                refund_request.completed_at = datetime.utcnow()
                refund_request.refund_transaction_id = f"ref_tx_{uuid.uuid4().hex[:16]}"
                
                logger.info(f"Refund processed (simulated): {refund_id}")
                return True, refund_request, "Refund processed successfully (simulated)"
            
        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            
            # Update refund request status
            if refund_request:
                refund_request.status = RefundStatus.FAILED
                refund_request.metadata["processing_error"] = str(e)
            
            return False, None, f"Error processing refund: {str(e)}"
    
    async def reject_refund(
        self,
        refund_id: str,
        processor_id: str,
        reason: str
    ) -> Tuple[bool, Optional[RefundRequest], str]:
        """Reject a refund request"""
        try:
            refund_request = await self.get_refund_request(refund_id)
            if not refund_request:
                return False, None, f"Refund request {refund_id} not found"
            
            if refund_request.status != RefundStatus.REQUESTED:
                return False, None, f"Refund request cannot be rejected in state: {refund_request.status}"
            
            # Update status
            refund_request.status = RefundStatus.REJECTED
            refund_request.processor_id = processor_id
            refund_request.processed_at = datetime.utcnow()
            refund_request.updated_at = datetime.utcnow()
            refund_request.metadata["rejection_reason"] = reason
            
            logger.info(f"Refund rejected: {refund_id} by {processor_id}, reason: {reason}")
            return True, refund_request, "Refund rejected successfully"
            
        except Exception as e:
            logger.error(f"Error rejecting refund: {str(e)}")
            return False, None, f"Error rejecting refund: {str(e)}"
    
    async def cancel_refund(
        self,
        refund_id: str,
        user_id: str
    ) -> Tuple[bool, Optional[RefundRequest], str]:
        """Cancel a refund request (by user)"""
        try:
            refund_request = await self.get_refund_request(refund_id)
            if not refund_request:
                return False, None, f"Refund request {refund_id} not found"
            
            if refund_request.user_id != user_id:
                return False, None, "User does not own this refund request"
            
            if refund_request.status not in [RefundStatus.REQUESTED, RefundStatus.PENDING]:
                return False, None, f"Refund request cannot be cancelled in state: {refund_request.status}"
            
            # Update status
            refund_request.status = RefundStatus.CANCELLED
            refund_request.updated_at = datetime.utcnow()
            refund_request.metadata["cancelled_by_user"] = user_id
            refund_request.metadata["cancelled_at"] = datetime.utcnow().isoformat()
            
            logger.info(f"Refund cancelled: {refund_id} by user {user_id}")
            return True, refund_request, "Refund cancelled successfully"
            
        except Exception as e:
            logger.error(f"Error cancelling refund: {str(e)}")
            return False, None, f"Error cancelling refund: {str(e)}"
    
    async def get_refund_request(self, refund_id: str) -> Optional[RefundRequest]:
        """Get refund request by ID"""
        return self.refund_requests.get(refund_id)
    
    async def get_user_refund_requests(
        self,
        user_id: str,
        status: Optional[RefundStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[RefundRequest]:
        """Get refund requests for a user"""
        user_refunds = [
            refund for refund in self.refund_requests.values()
            if refund.user_id == user_id
        ]
        
        if status:
            user_refunds = [refund for refund in user_refunds if refund.status == status]
        
        # Sort by requested_at descending
        user_refunds.sort(key=lambda x: x.requested_at, reverse=True)
        
        return user_refunds[offset:offset + limit]
    
    async def get_pending_refunds(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[RefundRequest]:
        """Get pending refund requests (for admin/processor review)"""
        pending_refunds = [
            refund for refund in self.refund_requests.values()
            if refund.status in [RefundStatus.REQUESTED, RefundStatus.PENDING]
        ]
        
        # Sort by requested_at ascending (oldest first)
        pending_refunds.sort(key=lambda x: x.requested_at)
        
        return pending_refunds[offset:offset + limit]
    
    async def get_refund_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get refund analytics"""
        try:
            all_refunds = list(self.refund_requests.values())
            
            # Filter by date range
            if start_date:
                all_refunds = [refund for refund in all_refunds if refund.requested_at >= start_date]
            if end_date:
                all_refunds = [refund for refund in all_refunds if refund.requested_at <= end_date]
            
            # Calculate statistics
            total_refunds = len(all_refunds)
            total_amount = sum(refund.amount for refund in all_refunds)
            completed_refunds = [refund for refund in all_refunds if refund.status == RefundStatus.COMPLETED]
            pending_refunds = [refund for refund in all_refunds if refund.status in [RefundStatus.REQUESTED, RefundStatus.PENDING, RefundStatus.PROCESSING]]
            
            # Group by reason
            reasons = {}
            for refund in all_refunds:
                reason = refund.reason.value
                if reason not in reasons:
                    reasons[reason] = {"count": 0, "amount": 0.0}
                reasons[reason]["count"] += 1
                reasons[reason]["amount"] += refund.amount
            
            # Group by status
            statuses = {}
            for refund in all_refunds:
                status = refund.status.value
                if status not in statuses:
                    statuses[status] = {"count": 0, "amount": 0.0}
                statuses[status]["count"] += 1
                statuses[status]["amount"] += refund.amount
            
            # Calculate approval rate (if we have processed refunds)
            processed_refunds = [refund for refund in all_refunds if refund.status in [RefundStatus.COMPLETED, RefundStatus.REJECTED]]
            if processed_refunds:
                approved_count = len([refund for refund in processed_refunds if refund.status == RefundStatus.COMPLETED])
                approval_rate = approved_count / len(processed_refunds)
            else:
                approval_rate = 0.0
            
            # Calculate average processing time for completed refunds
            processing_times = []
            for refund in completed_refunds:
                if refund.requested_at and refund.completed_at:
                    processing_time = (refund.completed_at - refund.requested_at).total_seconds() / 3600  # hours
                    processing_times.append(processing_time)
            
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            return {
                "period": {
                    "start": start_date.isoformat() if start_date else "all",
                    "end": end_date.isoformat() if end_date else "all"
                },
                "summary": {
                    "total_refunds": total_refunds,
                    "total_amount": total_amount,
                    "completed_refunds": len(completed_refunds),
                    "pending_refunds": len(pending_refunds),
                    "approval_rate": approval_rate,
                    "average_processing_time_hours": avg_processing_time
                },
                "by_reason": reasons,
                "by_status": statuses,
                "recent_refunds": [
                    {
                        "refund_id": refund.refund_id,
                        "receipt_id": refund.receipt_id,
                        "amount": refund.amount,
                        "status": refund.status.value,
                        "reason": refund.reason.value,
                        "requested_at": refund.requested_at.isoformat(),
                        "completed_at": refund.completed_at.isoformat() if refund.completed_at else None
                    }
                    for refund in sorted(all_refunds, key=lambda x: x.requested_at, reverse=True)[:10]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting refund analytics: {str(e)}")
            return {
                "error": str(e),
                "summary": {
                    "total_refunds": 0,
                    "total_amount": 0,
                    "completed_refunds": 0,
                    "pending_refunds": 0,
                    "approval_rate": 0,
                    "average_processing_time_hours": 0
                },
                "by_reason": {},
                "by_status": {},
                "recent_refunds": []
            }
    
    async def _get_receipt_simulated(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        """Simulate receipt lookup (would use billing service in production)"""
        # In a real implementation, this would call billing_service.get_receipt()
        # For now, return simulated data
        return {
            "receipt_id": receipt_id,
            "user_id": "user_123",
            "amount": 49.99,
            "total_amount": 53.99,  # including tax
            "currency": "USD",
            "paid_at": (datetime.utcnow() - timedelta(days=5)).isoformat(),
            "payment_method": "credit_card",
            "transaction_id": f"tx_{uuid.uuid4().hex[:16]}",
            "items": [
                {
                    "description": "Monthly Subscription",
                    "quantity": 1,
                    "unit_price": 49.99,
                    "amount": 49.99
                }
            ]
        }


# Singleton instance
refund_service = RefundService()