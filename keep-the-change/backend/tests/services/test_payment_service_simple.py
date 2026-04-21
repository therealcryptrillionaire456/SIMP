"""
Simple tests for the payment service
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from services.payment_service import (
    PaymentService,
    PaymentResult,
    CustomerInfo,
    SubscriptionPlan,
    PaymentProvider,
    MockStripeProvider
)


class TestPaymentServiceSimple:
    """Simple test suite for PaymentService"""
    
    @pytest.fixture
    def mock_provider(self):
        """Create a mock payment provider"""
        provider = AsyncMock(spec=PaymentProvider)
        provider.provider_name = "mock"
        provider.is_authenticated = True
        
        # Mock methods
        provider.authenticate.return_value = True
        provider.create_customer.return_value = (True, "cust_123", "Customer created")
        provider.create_payment_method.return_value = (True, "pm_123", "Payment method added")
        provider.process_payment.return_value = PaymentResult(
            success=True,
            transaction_id="tx_123",
            amount=49.99,
            currency="USD",
            status="completed",
            provider="mock",
            provider_response={"id": "ch_123", "status": "succeeded"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        provider.create_subscription.return_value = (True, "sub_123", "Subscription created")
        provider.cancel_subscription.return_value = (True, "Subscription cancelled")
        provider.refund_payment.return_value = (True, "ref_123", "Refund processed")
        provider.get_payment_status.return_value = {"status": "completed", "amount": 49.99}
        provider.get_provider_info.return_value = {
            "name": "mock",
            "requires_auth": True,
            "is_authenticated": True,
            "supports_subscriptions": True,
            "supports_refunds": True
        }
        
        return provider
    
    @pytest.fixture
    def payment_service(self, mock_provider):
        """Create a payment service instance for testing"""
        return PaymentService(providers=[mock_provider])
    
    @pytest.mark.asyncio
    async def test_payment_service_initialization(self, payment_service, mock_provider):
        """Test payment service initialization"""
        # Initialize service
        success = await payment_service.initialize()
        
        # Verify result
        assert success is True
        assert payment_service.is_initialized is True
        
        # Verify provider was authenticated
        mock_provider.authenticate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_customer(self, payment_service, mock_provider):
        """Test creating a customer"""
        # Initialize service first
        await payment_service.initialize()
        
        # Create customer
        success, customer_id, message = await payment_service.create_customer(
            email="test@example.com",
            name="Test User",
            phone="+1234567890"
        )
        
        # Verify result
        assert success is True
        assert customer_id == "cust_123"
        assert "created" in message.lower()
        
        # Verify provider was called
        mock_provider.create_customer.assert_called_once()
        call_args = mock_provider.create_customer.call_args
        customer_info = call_args[0][0]
        assert isinstance(customer_info, CustomerInfo)
        assert customer_info.email == "test@example.com"
        assert customer_info.name == "Test User"
        assert customer_info.phone == "+1234567890"
    
    @pytest.mark.asyncio
    async def test_add_payment_method(self, payment_service, mock_provider):
        """Test adding a payment method"""
        # Initialize service first
        await payment_service.initialize()
        
        # Add payment method
        payment_data = {
            "type": "credit_card",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2025,
            "cvc": "123"
        }
        
        success, payment_method_id, message = await payment_service.add_payment_method(
            customer_id="cust_123",
            payment_data=payment_data
        )
        
        # Verify result
        assert success is True
        assert payment_method_id == "pm_123"
        assert "added" in message.lower()
        
        # Verify provider was called
        mock_provider.create_payment_method.assert_called_once_with("cust_123", payment_data)
    
    @pytest.mark.asyncio
    async def test_process_payment(self, payment_service, mock_provider):
        """Test processing a payment"""
        # Initialize service first
        await payment_service.initialize()
        
        # Process payment
        result = await payment_service.process_payment(
            customer_id="cust_123",
            payment_method_id="pm_123",
            amount=49.99,
            currency="USD",
            description="Test payment"
        )
        
        # Verify result
        assert result.success is True
        assert result.transaction_id == "tx_123"
        assert result.amount == 49.99
        assert result.currency == "USD"
        assert result.status == "completed"
        assert result.provider == "mock"
        
        # Verify provider was called
        mock_provider.process_payment.assert_called_once()
        call_kwargs = mock_provider.process_payment.call_args.kwargs
        assert call_kwargs["customer_id"] == "cust_123"
        assert call_kwargs["payment_method_id"] == "pm_123"
        assert call_kwargs["amount"] == 49.99
        assert call_kwargs["currency"] == "USD"
        assert call_kwargs["description"] == "Test payment"
    
    @pytest.mark.asyncio
    async def test_create_subscription(self, payment_service, mock_provider):
        """Test creating a subscription"""
        # Initialize service first
        await payment_service.initialize()
        
        # Create subscription
        success, subscription_id, message = await payment_service.create_subscription(
            customer_id="cust_123",
            plan_id="pro",
            payment_method_id="pm_123",
            trial_days=14
        )
        
        # Verify result
        assert success is True
        assert subscription_id == "sub_123"
        assert "created" in message.lower()
        
        # Verify provider was called
        mock_provider.create_subscription.assert_called_once_with(
            customer_id="cust_123", plan_id="pro", payment_method_id="pm_123", trial_days=14
        )
    
    @pytest.mark.asyncio
    async def test_cancel_subscription(self, payment_service, mock_provider):
        """Test canceling a subscription"""
        # Initialize service first
        await payment_service.initialize()
        
        # Cancel subscription
        success, message = await payment_service.cancel_subscription("sub_123")
        
        # Verify result
        assert success is True
        assert "cancelled" in message.lower()
        
        # Verify provider was called
        mock_provider.cancel_subscription.assert_called_once_with("sub_123")
    
    @pytest.mark.asyncio
    async def test_refund_payment(self, payment_service, mock_provider):
        """Test refunding a payment"""
        # Initialize service first
        await payment_service.initialize()
        
        # Refund payment
        success, refund_id, message = await payment_service.refund_payment(
            transaction_id="tx_123",
            amount=49.99,
            reason="requested_by_customer"
        )
        
        # Verify result
        assert success is True
        assert refund_id == "ref_123"
        assert "processed" in message.lower()
        
        # Verify provider was called
        mock_provider.refund_payment.assert_called_once_with(
            "tx_123", 49.99, "requested_by_customer"
        )
    
    @pytest.mark.asyncio
    async def test_get_payment_status(self, payment_service, mock_provider):
        """Test getting payment status"""
        # Initialize service first
        await payment_service.initialize()
        
        # Get payment status
        status = await payment_service.get_payment_status("tx_123")
        
        # Verify result
        assert status is not None
        assert status["status"] == "completed"
        assert status["amount"] == 49.99
        
        # Verify provider was called
        mock_provider.get_payment_status.assert_called_once_with("tx_123")
    
    @pytest.mark.asyncio
    async def test_get_provider_info(self, payment_service, mock_provider):
        """Test getting provider information"""
        # Initialize service first
        await payment_service.initialize()
        
        # Get provider info directly from provider
        info = mock_provider.get_provider_info()
        
        # Verify result
        assert info is not None
        assert info["name"] == "mock"
        assert info["requires_auth"] is True
        assert info["is_authenticated"] is True
        
        # Verify provider was called
        mock_provider.get_provider_info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_service_not_initialized_error(self, payment_service):
        """Test error when service is not initialized"""
        # Try to create customer without initialization
        with pytest.raises(RuntimeError, match="Payment service not initialized"):
            await payment_service.create_customer(email="test@example.com")
    
    @pytest.mark.asyncio
    async def test_provider_not_found_error(self, payment_service, mock_provider):
        """Test error when provider is not found"""
        # Initialize service first
        await payment_service.initialize()
        
        # Try to use non-existent provider
        success, customer_id, message = await payment_service.create_customer(
            email="test@example.com",
            provider="nonexistent"
        )
        
        # Verify failure
        assert success is False
        assert customer_id is None
        assert "not found" in message.lower()
    
    @pytest.mark.asyncio
    async def test_mock_stripe_provider(self):
        """Test MockStripeProvider functionality"""
        # Create mock provider
        provider = MockStripeProvider(api_key="sk_test_mock")
        
        # Test authentication
        auth_result = await provider.authenticate()
        assert auth_result is True
        
        # Test create customer
        customer_info = CustomerInfo(
            customer_id="",
            email="test@example.com",
            name="Test User",
            phone=None,
            billing_address=None,
            shipping_address=None,
            metadata={}
        )
        
        success, customer_id, message = await provider.create_customer(customer_info)
        assert success is True
        assert customer_id is not None
        assert "created" in message.lower()
        
        # Test create payment method
        payment_data = {
            "type": "credit_card",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2025,
            "cvc": "123"
        }
        
        success, payment_method_id, message = await provider.create_payment_method(
            customer_id, payment_data
        )
        assert success is True
        assert payment_method_id is not None
        
        # Test process payment
        result = await provider.process_payment(
            customer_id=customer_id,
            payment_method_id=payment_method_id,
            amount=49.99,
            currency="USD",
            description="Test payment",
            metadata={}
        )
        
        assert result.success is True
        assert result.transaction_id is not None
        assert result.amount == 49.99
        assert result.currency == "USD"
        
        # Test get provider info
        info = provider.get_provider_info()
        assert info["name"] == "mockstripe"
        assert info["requires_auth"] is True
        assert info["is_authenticated"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])