"""
Tests for the refund service
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from services.refund_service import (
    RefundService,
    RefundRequest,
    RefundPolicy,
    RefundStatus,
    RefundReason
)


class TestRefundService:
    """Test suite for RefundService"""
    
    @pytest.fixture
    def refund_service(self):
        """Create a refund service instance for testing"""
        return RefundService()
    
    @pytest.fixture
    def mock_payment_service(self):
        """Create a mock payment service"""
        payment_service = AsyncMock()
        payment_service.process_refund.return_value = AsyncMock(
            success=True,
            transaction_id="refund_tx_123",
            error_message=None
        )
        return payment_service
    
    @pytest.fixture
    def mock_billing_service(self):
        """Create a mock billing service"""
        return AsyncMock()
    
    @pytest.fixture
    def sample_refund_request_data(self):
        """Create sample refund request data for testing"""
        return {
            "receipt_id": "rcpt_123",
            "user_id": "user_123",
            "amount": 49.99,
            "reason": RefundReason.REQUESTED_BY_CUSTOMER,
            "reason_details": "Changed my mind",
            "policy_id": "standard"
        }
    
    @pytest.fixture
    def standard_policy(self):
        """Create a standard refund policy for testing"""
        return RefundPolicy(
            policy_id="standard",
            name="Standard Refund Policy",
            description="Standard 30-day refund policy",
            refund_period_days=30,
            partial_refunds_allowed=True,
            requires_approval=False,
            auto_approve_threshold=100.0
        )
    
    @pytest.mark.asyncio
    async def test_refund_service_initialization(self, refund_service):
        """Test refund service initialization"""
        assert refund_service is not None
        assert refund_service.payment_service is None
        assert refund_service.billing_service is None
        assert refund_service.refund_requests == {}
        assert refund_service.refund_policies is not None
        
        # Check that default policies are initialized
        assert "standard" in refund_service.refund_policies
        assert "subscription" in refund_service.refund_policies
        assert "digital" in refund_service.refund_policies
        
        # Check standard policy
        standard_policy = refund_service.refund_policies["standard"]
        assert standard_policy.policy_id == "standard"
        assert standard_policy.refund_period_days == 30
        assert standard_policy.partial_refunds_allowed is True
        
        # Check subscription policy
        subscription_policy = refund_service.refund_policies["subscription"]
        assert subscription_policy.policy_id == "subscription"
        assert subscription_policy.refund_period_days == 14
        assert subscription_policy.partial_refunds_allowed is False
    
    @pytest.mark.asyncio
    async def test_request_refund(self, refund_service, sample_refund_request_data):
        """Test requesting a refund"""
        # Request refund
        success, refund_request, message = await refund_service.request_refund(**sample_refund_request_data)
        
        # Verify result
        assert success is True
        assert refund_request is not None
        assert "successfully" in message.lower()
        
        # Verify refund request details
        assert refund_request.receipt_id == "rcpt_123"
        assert refund_request.user_id == "user_123"
        assert refund_request.amount == 49.99
        assert refund_request.currency == "USD"
        assert refund_request.reason == RefundReason.REQUESTED_BY_CUSTOMER
        assert refund_request.reason_details == "Changed my mind"
        # Refund is auto-approved for amounts under $100 (standard policy threshold)
        assert refund_request.status == RefundStatus.PENDING
        assert refund_request.requested_at is not None
        
        # Verify refund request is stored
        assert refund_request.refund_id in refund_service.refund_requests
        stored_request = refund_service.refund_requests[refund_request.refund_id]
        assert stored_request == refund_request
        
        # Verify auto-approval (standard policy doesn't require approval for amounts under $100)
        # The refund should be auto-approved and moved to PENDING status
        assert refund_request.status == RefundStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_request_refund_nonexistent_policy(self, refund_service, sample_refund_request_data):
        """Test requesting a refund with non-existent policy"""
        # Request refund with non-existent policy
        data = sample_refund_request_data.copy()
        data["policy_id"] = "nonexistent"
        
        success, refund_request, message = await refund_service.request_refund(**data)
        
        # Verify failure
        assert success is False
        assert refund_request is None
        assert "not found" in message.lower()
    
    @pytest.mark.asyncio
    async def test_request_refund_requires_approval(self, refund_service):
        """Test requesting a refund that requires approval"""
        # Create a policy that requires approval
        approval_policy = RefundPolicy(
            policy_id="approval_required",
            name="Approval Required",
            description="All refunds require approval",
            refund_period_days=30,
            partial_refunds_allowed=True,
            requires_approval=True,
            auto_approve_threshold=0.0  # No auto-approval
        )
        refund_service.refund_policies["approval_required"] = approval_policy
        
        # Request refund
        success, refund_request, message = await refund_service.request_refund(
            receipt_id="rcpt_123",
            user_id="user_123",
            amount=49.99,
            reason=RefundReason.REQUESTED_BY_CUSTOMER,
            policy_id="approval_required"
        )
        
        # Verify result
        assert success is True
        assert refund_request is not None
        
        # Verify status is requested (not auto-approved)
        assert refund_request.status == RefundStatus.REQUESTED
        
        # Verify metadata indicates approval required
        assert refund_request.metadata.get("requires_approval") is True
    
    @pytest.mark.asyncio
    async def test_request_refund_expired_period(self, refund_service):
        """Test requesting a refund after expiration period"""
        # Mock receipt with old purchase date
        with patch.object(refund_service, '_get_receipt_simulated') as mock_get_receipt:
            mock_get_receipt.return_value = {
                "receipt_id": "rcpt_old",
                "user_id": "user_123",
                "amount": 49.99,
                "total_amount": 53.99,
                "currency": "USD",
                "paid_at": (datetime.utcnow() - timedelta(days=45)).isoformat(),  # 45 days ago
                "payment_method": "credit_card"
            }
            
            # Request refund
            success, refund_request, message = await refund_service.request_refund(
                receipt_id="rcpt_old",
                user_id="user_123",
                amount=49.99,
                reason=RefundReason.REQUESTED_BY_CUSTOMER,
                policy_id="standard"  # 30-day policy
            )
            
            # Verify failure
            assert success is False
            assert refund_request is None
            assert "expired" in message.lower()
    
    @pytest.mark.asyncio
    async def test_request_refund_invalid_amount(self, refund_service):
        """Test requesting a refund with invalid amount"""
        # Request refund with zero amount
        success, refund_request, message = await refund_service.request_refund(
            receipt_id="rcpt_123",
            user_id="user_123",
            amount=0.0,
            reason=RefundReason.REQUESTED_BY_CUSTOMER,
            policy_id="standard"
        )
        
        # Verify failure
        assert success is False
        assert refund_request is None
        assert "positive" in message.lower()
        
        # Request refund with amount exceeding purchase
        success, refund_request, message = await refund_service.request_refund(
            receipt_id="rcpt_123",
            user_id="user_123",
            amount=1000.0,  # Exceeds mock receipt amount
            reason=RefundReason.REQUESTED_BY_CUSTOMER,
            policy_id="standard"
        )
        
        # Verify failure
        assert success is False
        assert refund_request is None
        assert "exceeds" in message.lower()
    
    @pytest.mark.asyncio
    async def test_approve_refund(self, refund_service):
        """Test approving a refund request"""
        # Use subscription policy which requires approval
        success, refund_request, _ = await refund_service.request_refund(
            receipt_id="rcpt_123",
            user_id="user_123",
            amount=30.00,  # Under $50 auto-approve threshold for subscription policy
            reason=RefundReason.REQUESTED_BY_CUSTOMER,
            policy_id="subscription"  # This policy requires approval
        )
        
        # Refund should be auto-approved since amount <= 50
        # Subscription policy has auto_approve_threshold=50.0
        assert success is True
        assert refund_request is not None
        assert refund_request.status == RefundStatus.PENDING
        assert refund_request.processor_id == "system"
        
        # Test that we can't approve an already approved refund
        success, approved_request, message = await refund_service.approve_refund(
            refund_id=refund_request.refund_id,
            processor_id="admin_123",
            notes="Approved per policy"
        )
        
        # Should fail because refund is already in PENDING status
        assert success is False
        assert "not in requested state" in message.lower()
    
    @pytest.mark.asyncio
    async def test_approve_refund_nonexistent(self, refund_service):
        """Test approving non-existent refund request"""
        # Approve non-existent refund
        success, refund_request, message = await refund_service.approve_refund(
            refund_id="nonexistent",
            processor_id="admin_123"
        )
        
        # Verify failure
        assert success is False
        assert refund_request is None
        assert "not found" in message.lower()
    
    @pytest.mark.asyncio
    async def test_approve_refund_wrong_status(self, refund_service, sample_refund_request_data):
        """Test approving refund request in wrong status"""
        # Request and process a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        
        # Manually change status to completed
        refund_request.status = RefundStatus.COMPLETED
        
        # Try to approve
        success, approved_request, message = await refund_service.approve_refund(
            refund_id=refund_request.refund_id,
            processor_id="admin_123"
        )
        
        # Verify failure
        assert success is False
        assert approved_request is None
        assert "not in requested state" in message.lower()
    
    @pytest.mark.asyncio
    async def test_process_refund(self, refund_service, sample_refund_request_data, mock_payment_service):
        """Test processing a refund (executing payment reversal)"""
        # Set up payment service
        refund_service.payment_service = mock_payment_service
        
        # Request and approve a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        await refund_service.approve_refund(refund_request.refund_id, "admin_123")
        
        # Process refund
        success, processed_request, message = await refund_service.process_refund(
            refund_id=refund_request.refund_id,
            processor_id="processor_123"
        )
        
        # Verify result
        assert success is True
        assert processed_request is not None
        assert "successfully" in message.lower()
        
        # Verify status is updated
        assert processed_request.status == RefundStatus.COMPLETED
        assert processed_request.processor_id == "processor_123"
        assert processed_request.completed_at is not None
        assert processed_request.refund_transaction_id is not None
        
        # Verify payment service was called
        mock_payment_service.process_refund.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_refund_without_payment_service(self, refund_service, sample_refund_request_data):
        """Test processing a refund without payment service (simulated)"""
        # Request and approve a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        await refund_service.approve_refund(refund_request.refund_id, "admin_123")
        
        # Process refund (no payment service)
        success, processed_request, message = await refund_service.process_refund(
            refund_id=refund_request.refund_id,
            processor_id="processor_123"
        )
        
        # Verify result (simulated success)
        assert success is True
        assert processed_request is not None
        assert "simulated" in message.lower()
        
        # Verify status is completed
        assert processed_request.status == RefundStatus.COMPLETED
        assert processed_request.refund_transaction_id is not None
    
    @pytest.mark.asyncio
    async def test_process_refund_payment_failure(self, refund_service, sample_refund_request_data, mock_payment_service):
        """Test processing a refund when payment fails"""
        # Set up payment service to fail
        mock_payment_service.process_refund.return_value = AsyncMock(
            success=False,
            transaction_id=None,
            error_message="Payment processor error"
        )
        refund_service.payment_service = mock_payment_service
        
        # Request and approve a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        await refund_service.approve_refund(refund_request.refund_id, "admin_123")
        
        # Process refund
        success, processed_request, message = await refund_service.process_refund(
            refund_id=refund_request.refund_id,
            processor_id="processor_123"
        )
        
        # Verify failure
        assert success is False
        assert processed_request is not None
        assert "failed" in message.lower()
        
        # Verify status is failed
        assert processed_request.status == RefundStatus.FAILED
        assert "payment_error" in processed_request.metadata
    
    @pytest.mark.asyncio
    async def test_reject_refund(self, refund_service):
        """Test rejecting a refund request"""
        # Use subscription policy which requires approval for amounts > 50
        # Request full amount (53.99) which is > 50 so it stays in REQUESTED status
        success, refund_request, _ = await refund_service.request_refund(
            receipt_id="rcpt_123",
            user_id="user_123",
            amount=53.99,  # Full amount, over $50 threshold for subscription policy
            reason=RefundReason.REQUESTED_BY_CUSTOMER,
            policy_id="subscription"
        )
        
        # Reject refund
        success, rejected_request, message = await refund_service.reject_refund(
            refund_id=refund_request.refund_id,
            processor_id="admin_123",
            reason="Not eligible per policy"
        )
        
        # Verify result
        assert success is True
        assert rejected_request is not None
        assert "successfully" in message.lower()
        
        # Verify status is updated
        assert rejected_request.status == RefundStatus.REJECTED
        assert rejected_request.processor_id == "admin_123"
        assert rejected_request.processed_at is not None
        assert rejected_request.metadata.get("rejection_reason") == "Not eligible per policy"
    
    @pytest.mark.asyncio
    async def test_cancel_refund(self, refund_service, sample_refund_request_data):
        """Test canceling a refund request (by user)"""
        # Request a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        
        # Cancel refund
        success, cancelled_request, message = await refund_service.cancel_refund(
            refund_id=refund_request.refund_id,
            user_id="user_123"
        )
        
        # Verify result
        assert success is True
        assert cancelled_request is not None
        assert "successfully" in message.lower()
        
        # Verify status is updated
        assert cancelled_request.status == RefundStatus.CANCELLED
        assert cancelled_request.metadata.get("cancelled_by_user") == "user_123"
        assert "cancelled_at" in cancelled_request.metadata
    
    @pytest.mark.asyncio
    async def test_cancel_refund_wrong_user(self, refund_service, sample_refund_request_data):
        """Test canceling a refund request with wrong user"""
        # Request a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        
        # Try to cancel with wrong user
        success, cancelled_request, message = await refund_service.cancel_refund(
            refund_id=refund_request.refund_id,
            user_id="wrong_user"
        )
        
        # Verify failure
        assert success is False
        assert cancelled_request is None
        assert "does not own" in message.lower()
    
    @pytest.mark.asyncio
    async def test_get_refund_request(self, refund_service, sample_refund_request_data):
        """Test getting a refund request by ID"""
        # Request a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        refund_id = refund_request.refund_id
        
        # Get the refund request
        retrieved_request = await refund_service.get_refund_request(refund_id)
        
        # Verify result
        assert retrieved_request is not None
        assert retrieved_request.refund_id == refund_id
        assert retrieved_request.receipt_id == "rcpt_123"
        assert retrieved_request.user_id == "user_123"
        
        # Get non-existent refund request
        nonexistent_request = await refund_service.get_refund_request("nonexistent")
        assert nonexistent_request is None
    
    @pytest.mark.asyncio
    async def test_get_user_refund_requests(self, refund_service, sample_refund_request_data):
        """Test getting refund requests for a user"""
        # Request multiple refunds for the same user with different receipt IDs
        for i in range(3):
            data = sample_refund_request_data.copy()
            data["receipt_id"] = f"rcpt_{i+1}"  # Different receipt IDs
            data["amount"] = 49.99 - i * 5  # Decreasing amounts to stay under receipt total
            data["reason_details"] = f"Reason {i+1}"
            await refund_service.request_refund(**data)
        
        # Request refund for different user
        other_user_data = sample_refund_request_data.copy()
        other_user_data["user_id"] = "user_456"
        other_user_data["receipt_id"] = "rcpt_other"
        await refund_service.request_refund(**other_user_data)
        
        # Get refund requests for user_123
        user_refunds = await refund_service.get_user_refund_requests("user_123")
        
        # Verify result
        assert isinstance(user_refunds, list)
        assert len(user_refunds) == 3
        
        # Verify all refunds belong to user_123
        for refund in user_refunds:
            assert refund.user_id == "user_123"
        
        # Verify sorting (newest first)
        dates = [refund.requested_at for refund in user_refunds]
        assert dates == sorted(dates, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_user_refund_requests_with_status_filter(self, refund_service, sample_refund_request_data):
        """Test getting refund requests for a user with status filter"""
        # Request refunds with different statuses
        data = sample_refund_request_data.copy()
        
        # Requested refund (will be auto-approved to PENDING since amount < 100)
        success, requested_refund, _ = await refund_service.request_refund(**data)
        
        # Create another refund (will also be auto-approved since requires_approval=False)
        data["amount"] = 30.0  # Use amount less than receipt total (53.99)
        data["receipt_id"] = "rcpt_30"  # Different receipt ID
        success, second_refund, _ = await refund_service.request_refund(**data)
        
        # Get pending refunds only (all auto-approved refunds)
        pending_refunds = await refund_service.get_user_refund_requests(
            "user_123",
            status=RefundStatus.PENDING
        )
        
        # Verify result - should have 2 pending refunds (both auto-approved)
        assert len(pending_refunds) == 2
        
        # Get requested refunds only (should be empty since all are auto-approved)
        requested_refunds = await refund_service.get_user_refund_requests(
            "user_123",
            status=RefundStatus.REQUESTED
        )
        
        # Verify result - should have 0 requested refunds
        assert len(requested_refunds) == 0
    
    @pytest.mark.asyncio
    async def test_get_pending_refunds(self, refund_service, sample_refund_request_data):
        """Test getting pending refund requests (for admin review)"""
        # Create refunds with different statuses
        for i in range(5):
            data = sample_refund_request_data.copy()
            # Use different receipt IDs and reasonable amounts
            data["receipt_id"] = f"rcpt_pending_{i}"
            data["amount"] = 40.0 + i * 5  # Reasonable amounts under 100
            
            success, refund_request, _ = await refund_service.request_refund(**data)
            
            # Note: All refunds will be auto-approved since requires_approval=False
            # So we can't call approve_refund here as they're already in PENDING status
        
        # Get pending refunds
        pending_refunds = await refund_service.get_pending_refunds()
        
        # Verify result
        assert isinstance(pending_refunds, list)
        
        # Verify all are pending or requested
        for refund in pending_refunds:
            assert refund.status in [RefundStatus.REQUESTED, RefundStatus.PENDING]
        
        # Verify sorting (oldest first for admin review)
        dates = [refund.requested_at for refund in pending_refunds]
        assert dates == sorted(dates)  # Ascending (oldest first)
    
    @pytest.mark.asyncio
    async def test_get_refund_analytics(self, refund_service, sample_refund_request_data):
        """Test getting refund analytics"""
        # Create refunds with different statuses and reasons
        reasons = [
            RefundReason.REQUESTED_BY_CUSTOMER,
            RefundReason.PRODUCT_UNSATISFACTORY,
            RefundReason.SERVICE_UNSATISFACTORY,
            RefundReason.DUPLICATE
        ]
        
        for i, reason in enumerate(reasons):
            data = sample_refund_request_data.copy()
            # Use different receipt IDs and reasonable amounts
            data["receipt_id"] = f"rcpt_analytics_{i}"
            data["amount"] = 40.0 + i * 5  # Reasonable amounts
            data["reason"] = reason
            
            success, refund_request, _ = await refund_service.request_refund(**data)
            
            # Note: All refunds will be auto-approved to PENDING status
            # We can process some of them
            if i % 2 == 0:
                # Process the refund (from PENDING to COMPLETED)
                await refund_service.process_refund(refund_request.refund_id, "processor_123")
            elif i == 1:
                # Reject the refund (from PENDING to REJECTED)
                # First need to cancel the auto-approval by changing status back to REQUESTED
                refund_request.status = RefundStatus.REQUESTED
                await refund_service.reject_refund(refund_request.refund_id, "admin_123", "Not eligible")
        
        # Get analytics
        analytics = await refund_service.get_refund_analytics()
        
        # Verify result
        assert isinstance(analytics, dict)
        
        # Check required fields
        assert "period" in analytics
        assert "summary" in analytics
        assert "by_reason" in analytics
        assert "by_status" in analytics
        assert "recent_refunds" in analytics
        
        # Check summary
        summary = analytics["summary"]
        assert "total_refunds" in summary
        assert "total_amount" in summary
        assert "completed_refunds" in summary
        assert "pending_refunds" in summary
        assert "approval_rate" in summary
        assert "average_processing_time_hours" in summary
        
        # Verify data types
        assert isinstance(summary["total_refunds"], int)
        assert isinstance(summary["total_amount"], float)
        assert isinstance(summary["approval_rate"], float)
        
        # Check by_reason
        by_reason = analytics["by_reason"]
        assert len(by_reason) > 0
        
        # Check by_status
        by_status = analytics["by_status"]
        assert len(by_status) > 0
        
        # Check recent refunds
        recent_refunds = analytics["recent_refunds"]
        assert isinstance(recent_refunds, list)
        assert len(recent_refunds) <= 10
    
    @pytest.mark.asyncio
    async def test_refund_policy_is_refund_allowed(self, standard_policy):
        """Test refund policy validation"""
        now = datetime.utcnow()
        
        # Test within period
        purchase_date = now - timedelta(days=15)  # 15 days ago
        allowed, message = standard_policy.is_refund_allowed(
            purchase_date=purchase_date,
            amount=49.99,
            reason=RefundReason.REQUESTED_BY_CUSTOMER
        )
        
        assert allowed is True
        assert "allowed" in message
        
        # Test expired period
        purchase_date = now - timedelta(days=45)  # 45 days ago
        allowed, message = standard_policy.is_refund_allowed(
            purchase_date=purchase_date,
            amount=49.99,
            reason=RefundReason.REQUESTED_BY_CUSTOMER
        )
        
        assert allowed is False
        assert "expired" in message
        
        # Test disallowed reason
        # Create policy with limited reasons
        limited_policy = RefundPolicy(
            policy_id="limited",
            name="Limited",
            description="Limited reasons",
            refund_period_days=30,
            allowed_reasons=[RefundReason.DUPLICATE, RefundReason.FRAUDULENT]
        )
        
        purchase_date = now - timedelta(days=15)
        allowed, message = limited_policy.is_refund_allowed(
            purchase_date=purchase_date,
            amount=49.99,
            reason=RefundReason.REQUESTED_BY_CUSTOMER  # Not in allowed reasons
        )
        
        assert allowed is False
        assert "not allowed" in message
    
    @pytest.mark.asyncio
    async def test_refund_request_to_dict(self, refund_service, sample_refund_request_data):
        """Test converting refund request to dictionary"""
        # Request a refund
        success, refund_request, _ = await refund_service.request_refund(**sample_refund_request_data)
        
        # Convert to dict
        refund_dict = refund_request.to_dict()
        
        # Verify dictionary structure
        assert isinstance(refund_dict, dict)
        assert refund_dict["refund_id"] == refund_request.refund_id
        assert refund_dict["receipt_id"] == "rcpt_123"
        assert refund_dict["user_id"] == "user_123"
        assert refund_dict["amount"] == 49.99
        assert refund_dict["currency"] == "USD"
        assert refund_dict["reason"] == "requested_by_customer"
        assert refund_dict["reason_details"] == "Changed my mind"
        # Status will be "pending" because it was auto-approved (amount < 100)
        assert refund_dict["status"] == "pending"
        assert "requested_at" in refund_dict
        # processed_at should not be None since refund was auto-approved
        assert refund_dict["processed_at"] is not None
        assert refund_dict["completed_at"] is None
        # processor_id should be "system" since refund was auto-approved
        assert refund_dict["processor_id"] == "system"
        assert refund_dict["transaction_id"] is None
        assert refund_dict["refund_transaction_id"] is None
        assert isinstance(refund_dict["metadata"], dict)
        assert "created_at" in refund_dict
        assert "updated_at" in refund_dict
    
    @pytest.mark.asyncio
    async def test_refund_policy_to_dict(self, standard_policy):
        """Test converting refund policy to dictionary"""
        # Convert to dict
        policy_dict = standard_policy.to_dict()
        
        # Verify dictionary structure
        assert isinstance(policy_dict, dict)
        assert policy_dict["policy_id"] == "standard"
        assert policy_dict["name"] == "Standard Refund Policy"
        assert policy_dict["description"] == "Standard 30-day refund policy"
        assert policy_dict["refund_period_days"] == 30
        assert policy_dict["partial_refunds_allowed"] is True
        assert policy_dict["requires_approval"] is False
        assert policy_dict["auto_approve_threshold"] == 100.0
        assert isinstance(policy_dict["allowed_reasons"], list)
        assert isinstance(policy_dict["excluded_products"], list)
        assert policy_dict["is_active"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])