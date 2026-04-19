"""
Tests for the payment service
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


class TestPaymentService:
    """Test suite for PaymentService"""
    
    @pytest.fixture
    def payment_service(self):
        """Create a payment service instance for testing"""
        # Create mock provider for testing
        mock_provider = AsyncMock(spec=PaymentProvider)
        mock_provider.provider_name = "mock"
        mock_provider.authenticate.return_value = True
        mock_provider.is_authenticated = True
        
        return PaymentService(providers=[mock_provider])
    
    @pytest.fixture
    def mock_stripe_connector(self):
        """Create a mock Stripe connector"""
        connector = AsyncMock(spec=MockStripeProvider)
        connector.provider_name = "stripe"
        connector.process_payment.return_value = PaymentResult(
            success=True,
            transaction_id="stripe_tx_123",
            amount=49.99,
            currency="USD",
            status="completed",
            provider="stripe",
            provider_response={"id": "ch_123", "status": "succeeded"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        connector.process_refund.return_value = PaymentResult(
            success=True,
            transaction_id="stripe_refund_123",
            amount=49.99,
            currency="USD",
            status="completed",
            provider="stripe",
            provider_response={"id": "re_123", "status": "succeeded"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        return connector
    
    @pytest.fixture
    def mock_paypal_connector(self):
        """Create a mock PayPal connector"""
        connector = AsyncMock(spec=PayPalPaymentConnector)
        connector.process_payment.return_value = PaymentResult(
            success=True,
            transaction_id="paypal_tx_123",
            amount=49.99,
            currency="USD",
            status="completed",
            provider="paypal",
            provider_response={"id": "PAY-123", "state": "approved"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        return connector
    
    @pytest.fixture
    def mock_bank_connector(self):
        """Create a mock bank transfer connector"""
        connector = AsyncMock(spec=BankTransferConnector)
        connector.process_payment.return_value = PaymentResult(
            success=True,
            transaction_id="bank_tx_123",
            amount=49.99,
            currency="USD",
            status="pending",
            provider="bank_transfer",
            provider_response={"reference": "BANK-123", "status": "pending"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        return connector
    
    @pytest.mark.asyncio
    async def test_payment_service_initialization(self, payment_service):
        """Test payment service initialization"""
        assert payment_service is not None
        assert payment_service.connectors == {}
        assert payment_service.default_currency == "USD"
        assert payment_service.supported_currencies == ["USD", "EUR", "GBP", "CAD", "AUD"]
    
    @pytest.mark.asyncio
    async def test_register_connector(self, payment_service, mock_stripe_connector):
        """Test registering a payment connector"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Verify connector is registered
        assert "stripe" in payment_service.connectors
        assert payment_service.connectors["stripe"] == mock_stripe_connector
        
        # Test getting connector
        connector = payment_service.get_connector("stripe")
        assert connector == mock_stripe_connector
        
        # Test getting non-existent connector
        connector = payment_service.get_connector("nonexistent")
        assert connector is None
    
    @pytest.mark.asyncio
    async def test_process_payment_stripe(self, payment_service, mock_stripe_connector):
        """Test processing payment with Stripe"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Process payment
        result = await payment_service.process_payment(
            user_id="user_123",
            amount=49.99,
            currency="USD",
            payment_method=PaymentMethod(
                method_id="pm_123",
                type="credit_card",
                provider="stripe",
                details={"last4": "4242", "brand": "visa"}
            ),
            description="Test payment"
        )
        
        # Verify result
        assert result.success is True
        assert result.transaction_id == "stripe_tx_123"
        assert result.amount == 49.99
        assert result.currency == "USD"
        assert result.status == "completed"
        assert result.provider == "stripe"
        
        # Verify connector was called
        mock_stripe_connector.process_payment.assert_called_once()
        call_args = mock_stripe_connector.process_payment.call_args
        assert call_args[0][0] == "user_123"  # user_id
        assert call_args[0][1] == 49.99  # amount
        assert call_args[0][2] == "USD"  # currency
    
    @pytest.mark.asyncio
    async def test_process_payment_paypal(self, payment_service, mock_paypal_connector):
        """Test processing payment with PayPal"""
        # Register connector
        payment_service.register_connector("paypal", mock_paypal_connector)
        
        # Process payment
        result = await payment_service.process_payment(
            user_id="user_456",
            amount=29.99,
            currency="USD",
            payment_method=PaymentMethod(
                method_id="paypal_123",
                type="paypal",
                provider="paypal",
                details={"email": "test@example.com"}
            ),
            description="PayPal test payment"
        )
        
        # Verify result
        assert result.success is True
        assert result.transaction_id == "paypal_tx_123"
        assert result.amount == 29.99
        assert result.provider == "paypal"
        
        # Verify connector was called
        mock_paypal_connector.process_payment.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_payment_unsupported_currency(self, payment_service, mock_stripe_connector):
        """Test processing payment with unsupported currency"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Process payment with unsupported currency
        result = await payment_service.process_payment(
            user_id="user_123",
            amount=100.00,
            currency="JPY",  # Not in supported currencies
            payment_method=PaymentMethod(
                method_id="pm_123",
                type="credit_card",
                provider="stripe",
                details={"last4": "4242"}
            ),
            description="Test with JPY"
        )
        
        # Verify failure
        assert result.success is False
        assert "Unsupported currency" in result.error_message
        assert result.transaction_id is None
        
        # Verify connector was NOT called
        mock_stripe_connector.process_payment.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_payment_no_connector(self, payment_service):
        """Test processing payment without registered connector"""
        # Process payment without registering connector
        result = await payment_service.process_payment(
            user_id="user_123",
            amount=49.99,
            currency="USD",
            payment_method=PaymentMethod(
                method_id="pm_123",
                type="credit_card",
                provider="stripe",
                details={"last4": "4242"}
            ),
            description="Test no connector"
        )
        
        # Verify failure
        assert result.success is False
        assert "No payment connector" in result.error_message
    
    @pytest.mark.asyncio
    async def test_process_refund(self, payment_service, mock_stripe_connector):
        """Test processing refund"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Process refund
        result = await payment_service.process_refund(
            receipt_id="rcpt_123",
            amount=49.99,
            currency="USD",
            reason="requested_by_customer"
        )
        
        # Verify result
        assert result.success is True
        assert result.transaction_id == "stripe_refund_123"
        assert result.amount == 49.99
        assert result.currency == "USD"
        assert result.status == "completed"
        assert result.provider == "stripe"
        
        # Verify connector was called
        mock_stripe_connector.process_refund.assert_called_once()
        call_args = mock_stripe_connector.process_refund.call_args
        assert call_args[0][0] == "rcpt_123"  # receipt_id
        assert call_args[0][1] == 49.99  # amount
        assert call_args[0][2] == "USD"  # currency
    
    @pytest.mark.asyncio
    async def test_get_supported_payment_methods(self, payment_service, mock_stripe_connector, mock_paypal_connector):
        """Test getting supported payment methods"""
        # Register connectors
        payment_service.register_connector("stripe", mock_stripe_connector)
        payment_service.register_connector("paypal", mock_paypal_connector)
        
        # Mock connector responses
        mock_stripe_connector.get_supported_methods.return_value = [
            PaymentMethod(
                method_id="card",
                type="credit_card",
                provider="stripe",
                details={"supported_cards": ["visa", "mastercard", "amex"]}
            ),
            PaymentMethod(
                method_id="bank",
                type="bank_account",
                provider="stripe",
                details={"supported_banks": ["chase", "wells_fargo"]}
            )
        ]
        
        mock_paypal_connector.get_supported_methods.return_value = [
            PaymentMethod(
                method_id="paypal",
                type="paypal",
                provider="paypal",
                details={}
            )
        ]
        
        # Get supported methods
        methods = await payment_service.get_supported_payment_methods()
        
        # Verify result
        assert len(methods) == 3
        
        # Check Stripe methods
        stripe_methods = [m for m in methods if m.provider == "stripe"]
        assert len(stripe_methods) == 2
        
        # Check PayPal methods
        paypal_methods = [m for m in methods if m.provider == "paypal"]
        assert len(paypal_methods) == 1
        assert paypal_methods[0].type == "paypal"
        
        # Verify connectors were called
        mock_stripe_connector.get_supported_methods.assert_called_once()
        mock_paypal_connector.get_supported_methods.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_subscription(self, payment_service, mock_stripe_connector):
        """Test creating a subscription"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Mock subscription creation
        mock_stripe_connector.create_subscription.return_value = PaymentResult(
            success=True,
            transaction_id="sub_123",
            amount=9.99,
            currency="USD",
            status="active",
            provider="stripe",
            provider_response={"id": "sub_123", "status": "active"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        
        # Create subscription
        result = await payment_service.create_subscription(
            user_id="user_123",
            plan_id="pro",
            amount=9.99,
            currency="USD",
            payment_method_id="pm_123",
            interval="monthly"
        )
        
        # Verify result
        assert result.success is True
        assert result.transaction_id == "sub_123"
        assert result.amount == 9.99
        assert result.status == "active"
        
        # Verify connector was called
        mock_stripe_connector.create_subscription.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cancel_subscription(self, payment_service, mock_stripe_connector):
        """Test canceling a subscription"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Mock subscription cancellation
        mock_stripe_connector.cancel_subscription.return_value = PaymentResult(
            success=True,
            transaction_id="sub_123",
            amount=0.0,
            currency="USD",
            status="cancelled",
            provider="stripe",
            provider_response={"id": "sub_123", "status": "cancelled"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        
        # Cancel subscription
        result = await payment_service.cancel_subscription("sub_123")
        
        # Verify result
        assert result.success is True
        assert result.status == "cancelled"
        
        # Verify connector was called
        mock_stripe_connector.cancel_subscription.assert_called_once_with("sub_123")
    
    @pytest.mark.asyncio
    async def test_get_payment_status(self, payment_service, mock_stripe_connector):
        """Test getting payment status"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Mock status check
        mock_stripe_connector.get_payment_status.return_value = PaymentResult(
            success=True,
            transaction_id="tx_123",
            amount=49.99,
            currency="USD",
            status="completed",
            provider="stripe",
            provider_response={"id": "ch_123", "status": "succeeded"},
            error_message=None,
            timestamp=datetime.utcnow()
        )
        
        # Get payment status
        result = await payment_service.get_payment_status("tx_123", "stripe")
        
        # Verify result
        assert result.success is True
        assert result.transaction_id == "tx_123"
        assert result.status == "completed"
        
        # Verify connector was called
        mock_stripe_connector.get_payment_status.assert_called_once_with("tx_123")
    
    @pytest.mark.asyncio
    async def test_validate_payment_method(self, payment_service, mock_stripe_connector):
        """Test validating a payment method"""
        # Register connector
        payment_service.register_connector("stripe", mock_stripe_connector)
        
        # Mock validation
        mock_stripe_connector.validate_payment_method.return_value = True
        
        # Validate payment method
        payment_method = PaymentMethod(
            method_id="pm_123",
            type="credit_card",
            provider="stripe",
            details={"last4": "4242", "exp_month": 12, "exp_year": 2025}
        )
        
        is_valid = await payment_service.validate_payment_method(payment_method)
        
        # Verify result
        assert is_valid is True
        
        # Verify connector was called
        mock_stripe_connector.validate_payment_method.assert_called_once_with(payment_method)
    
    @pytest.mark.asyncio
    async def test_get_payment_analytics(self, payment_service, mock_stripe_connector, mock_paypal_connector):
        """Test getting payment analytics"""
        # Register connectors
        payment_service.register_connector("stripe", mock_stripe_connector)
        payment_service.register_connector("paypal", mock_paypal_connector)
        
        # Mock analytics
        mock_stripe_connector.get_analytics.return_value = {
            "total_volume": 1000.00,
            "transaction_count": 50,
            "success_rate": 0.98,
            "average_transaction": 20.00
        }
        
        mock_paypal_connector.get_analytics.return_value = {
            "total_volume": 500.00,
            "transaction_count": 25,
            "success_rate": 0.95,
            "average_transaction": 20.00
        }
        
        # Get analytics
        analytics = await payment_service.get_payment_analytics()
        
        # Verify result
        assert "stripe" in analytics
        assert "paypal" in analytics
        assert analytics["stripe"]["total_volume"] == 1000.00
        assert analytics["paypal"]["total_volume"] == 500.00
        assert analytics["stripe"]["transaction_count"] == 50
        assert analytics["paypal"]["transaction_count"] == 25
        
        # Verify connectors were called
        mock_stripe_connector.get_analytics.assert_called_once()
        mock_paypal_connector.get_analytics.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])