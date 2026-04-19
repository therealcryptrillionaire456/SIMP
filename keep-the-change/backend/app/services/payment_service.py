"""
Payment processing service for KEEPTHECHANGE.com

This service handles payment processing, subscription billing, and financial operations.
"""

import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import json
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class PaymentResult:
    """Result of a payment operation"""
    success: bool
    transaction_id: Optional[str]
    amount: float
    currency: str
    status: str  # pending, processing, completed, failed, refunded
    provider: str  # stripe, paypal, etc.
    provider_response: Dict[str, Any]
    error_message: Optional[str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "provider": self.provider,
            "provider_response": self.provider_response,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class SubscriptionPlan:
    """Subscription plan definition"""
    plan_id: str
    name: str
    description: str
    price_monthly: float
    price_yearly: Optional[float]
    currency: str
    features: List[str]
    trial_days: int
    is_active: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "price_monthly": self.price_monthly,
            "price_yearly": self.price_yearly,
            "currency": self.currency,
            "features": self.features,
            "trial_days": self.trial_days,
            "is_active": self.is_active
        }


@dataclass
class CustomerInfo:
    """Customer information for payment processing"""
    customer_id: str
    email: str
    name: Optional[str]
    phone: Optional[str]
    billing_address: Optional[Dict[str, Any]]
    shipping_address: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "customer_id": self.customer_id,
            "email": self.email,
            "name": self.name,
            "phone": self.phone,
            "billing_address": self.billing_address,
            "shipping_address": self.shipping_address,
            "metadata": self.metadata
        }


class PaymentProvider(ABC):
    """Abstract base class for payment providers"""
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.provider_name = self.__class__.__name__.replace("Provider", "").lower()
        self.is_authenticated = False
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with payment provider"""
        pass
    
    @abstractmethod
    async def create_customer(self, customer_info: CustomerInfo) -> Tuple[bool, Optional[str], str]:
        """Create customer in payment provider system"""
        pass
    
    @abstractmethod
    async def create_payment_method(
        self,
        customer_id: str,
        payment_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], str]:
        """Create payment method for customer"""
        pass
    
    @abstractmethod
    async def process_payment(
        self,
        customer_id: str,
        payment_method_id: str,
        amount: float,
        currency: str,
        description: str,
        metadata: Dict[str, Any]
    ) -> PaymentResult:
        """Process a payment"""
        pass
    
    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        trial_days: int = 0
    ) -> Tuple[bool, Optional[str], str]:
        """Create subscription for customer"""
        pass
    
    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> Tuple[bool, str]:
        """Cancel subscription"""
        pass
    
    @abstractmethod
    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Refund a payment"""
        pass
    
    @abstractmethod
    async def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get payment status"""
        pass
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information"""
        return {
            "name": self.provider_name,
            "requires_auth": self.api_key is not None,
            "is_authenticated": self.is_authenticated,
            "supports_subscriptions": True,
            "supports_refunds": True
        }


class MockStripeProvider(PaymentProvider):
    """Mock Stripe provider for testing"""
    
    def __init__(self, api_key: str = "sk_test_mock"):
        super().__init__(api_key)
        self._customers: Dict[str, Dict[str, Any]] = {}
        self._payment_methods: Dict[str, Dict[str, Any]] = {}
        self._transactions: Dict[str, Dict[str, Any]] = {}
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        
        # Mock subscription plans
        self._plans = {
            "free": SubscriptionPlan(
                plan_id="free",
                name="Free",
                description="Basic features",
                price_monthly=0.0,
                price_yearly=0.0,
                currency="USD",
                features=["basic_price_comparison", "manual_purchasing"],
                trial_days=0,
                is_active=True
            ),
            "basic": SubscriptionPlan(
                plan_id="basic",
                name="Basic",
                description="Advanced features",
                price_monthly=4.99,
                price_yearly=49.99,
                currency="USD",
                features=["advanced_price_comparison", "auto_purchasing", "basic_support"],
                trial_days=7,
                is_active=True
            ),
            "pro": SubscriptionPlan(
                plan_id="pro",
                name="Pro",
                description="Premium features",
                price_monthly=14.99,
                price_yearly=149.99,
                currency="USD",
                features=["premium_price_comparison", "priority_support", "advanced_analytics"],
                trial_days=14,
                is_active=True
            ),
            "elite": SubscriptionPlan(
                plan_id="elite",
                name="Elite",
                description="Enterprise features",
                price_monthly=49.99,
                price_yearly=499.99,
                currency="USD",
                features=["custom_strategies", "24/7_support", "enterprise_features"],
                trial_days=30,
                is_active=True
            )
        }
    
    async def authenticate(self) -> bool:
        """Mock authentication"""
        await asyncio.sleep(0.1)
        self.is_authenticated = True
        logger.info(f"Mock Stripe provider authenticated")
        return True
    
    async def create_customer(self, customer_info: CustomerInfo) -> Tuple[bool, Optional[str], str]:
        """Create mock customer"""
        await asyncio.sleep(0.1)
        
        customer_id = f"cus_{uuid.uuid4().hex[:24]}"
        
        self._customers[customer_id] = {
            "id": customer_id,
            "email": customer_info.email,
            "name": customer_info.name,
            "phone": customer_info.phone,
            "billing_address": customer_info.billing_address,
            "shipping_address": customer_info.shipping_address,
            "metadata": customer_info.metadata,
            "created": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Created mock customer {customer_id} for {customer_info.email}")
        return True, customer_id, "Customer created successfully"
    
    async def create_payment_method(
        self,
        customer_id: str,
        payment_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], str]:
        """Create mock payment method"""
        await asyncio.sleep(0.1)
        
        if customer_id not in self._customers:
            return False, None, "Customer not found"
        
        payment_method_id = f"pm_{uuid.uuid4().hex[:24]}"
        
        self._payment_methods[payment_method_id] = {
            "id": payment_method_id,
            "customer_id": customer_id,
            "type": payment_data.get("type", "card"),
            "card_brand": payment_data.get("card_brand", "visa"),
            "card_last4": payment_data.get("card_last4", "4242"),
            "card_exp_month": payment_data.get("card_exp_month", 12),
            "card_exp_year": payment_data.get("card_exp_year", 2026),
            "billing_address": payment_data.get("billing_address"),
            "created": datetime.utcnow().isoformat(),
            "is_default": payment_data.get("is_default", False)
        }
        
        logger.info(f"Created mock payment method {payment_method_id} for customer {customer_id}")
        return True, payment_method_id, "Payment method created successfully"
    
    async def process_payment(
        self,
        customer_id: str,
        payment_method_id: str,
        amount: float,
        currency: str,
        description: str,
        metadata: Dict[str, Any]
    ) -> PaymentResult:
        """Process mock payment"""
        await asyncio.sleep(0.2)
        
        if customer_id not in self._customers:
            return PaymentResult(
                success=False,
                transaction_id=None,
                amount=amount,
                currency=currency,
                status="failed",
                provider=self.provider_name,
                provider_response={"error": "Customer not found"},
                error_message="Customer not found",
                timestamp=datetime.utcnow()
            )
        
        if payment_method_id not in self._payment_methods:
            return PaymentResult(
                success=False,
                transaction_id=None,
                amount=amount,
                currency=currency,
                status="failed",
                provider=self.provider_name,
                provider_response={"error": "Payment method not found"},
                error_message="Payment method not found",
                timestamp=datetime.utcnow()
            )
        
        # Validate amount
        if amount <= 0:
            return PaymentResult(
                success=False,
                transaction_id=None,
                amount=amount,
                currency=currency,
                status="failed",
                provider=self.provider_name,
                provider_response={"error": "Amount must be positive"},
                error_message="Amount must be positive",
                timestamp=datetime.utcnow()
            )
        
        # Simulate occasional payment failures (10% failure rate)
        # Disabled for deterministic testing
        # import random
        # if random.random() < 0.1:
        #     return PaymentResult(
        #         success=False,
        #         transaction_id=None,
        #         amount=amount,
        #         currency=currency,
        #         status="failed",
        #         provider=self.provider_name,
        #         provider_response={"error": "Insufficient funds"},
        #         error_message="Payment declined: Insufficient funds",
        #         timestamp=datetime.utcnow()
        #     )
        
        transaction_id = f"pi_{uuid.uuid4().hex[:24]}"
        
        self._transactions[transaction_id] = {
            "id": transaction_id,
            "customer_id": customer_id,
            "payment_method_id": payment_method_id,
            "amount": amount,
            "currency": currency,
            "description": description,
            "metadata": metadata,
            "status": "succeeded",
            "created": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Processed mock payment {transaction_id} for ${amount} {currency}")
        
        return PaymentResult(
            success=True,
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            status="completed",
            provider=self.provider_name,
            provider_response={
                "id": transaction_id,
                "status": "succeeded",
                "amount": amount,
                "currency": currency,
                "description": description
            },
            error_message=None,
            timestamp=datetime.utcnow()
        )
    
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        trial_days: int = 0
    ) -> Tuple[bool, Optional[str], str]:
        """Create mock subscription"""
        await asyncio.sleep(0.2)
        
        if customer_id not in self._customers:
            return False, None, "Customer not found"
        
        if plan_id not in self._plans:
            return False, None, f"Plan {plan_id} not found"
        
        if payment_method_id not in self._payment_methods:
            return False, None, "Payment method not found"
        
        subscription_id = f"sub_{uuid.uuid4().hex[:24]}"
        plan = self._plans[plan_id]
        
        # Calculate trial end date
        trial_end = None
        if trial_days > 0:
            trial_end = datetime.utcnow() + timedelta(days=trial_days)
        
        self._subscriptions[subscription_id] = {
            "id": subscription_id,
            "customer_id": customer_id,
            "plan_id": plan_id,
            "payment_method_id": payment_method_id,
            "status": "active",
            "current_period_start": datetime.utcnow().isoformat(),
            "current_period_end": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "trial_end": trial_end.isoformat() if trial_end else None,
            "cancel_at_period_end": False,
            "created": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Created mock subscription {subscription_id} for plan {plan_id}")
        return True, subscription_id, "Subscription created successfully"
    
    async def cancel_subscription(self, subscription_id: str) -> Tuple[bool, str]:
        """Cancel mock subscription"""
        await asyncio.sleep(0.1)
        
        if subscription_id not in self._subscriptions:
            return False, "Subscription not found"
        
        subscription = self._subscriptions[subscription_id]
        subscription["status"] = "canceled"
        subscription["canceled_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Canceled mock subscription {subscription_id}")
        return True, "Subscription canceled successfully"
    
    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Process mock refund"""
        await asyncio.sleep(0.2)
        
        if transaction_id not in self._transactions:
            return False, None, "Transaction not found"
        
        transaction = self._transactions[transaction_id]
        
        if transaction["status"] != "succeeded":
            return False, None, "Cannot refund failed transaction"
        
        refund_amount = amount or transaction["amount"]
        
        if refund_amount > transaction["amount"]:
            return False, None, f"Refund amount ${refund_amount} exceeds transaction amount ${transaction['amount']}"
        
        refund_id = f"re_{uuid.uuid4().hex[:24]}"
        
        # Update transaction
        transaction["refunded_amount"] = refund_amount
        transaction["refund_reason"] = reason
        transaction["refund_id"] = refund_id
        
        logger.info(f"Processed mock refund {refund_id} for ${refund_amount}")
        return True, refund_id, "Refund processed successfully"
    
    async def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get mock payment status"""
        await asyncio.sleep(0.05)
        
        if transaction_id not in self._transactions:
            return None
        
        return self._transactions[transaction_id]
    
    def get_plans(self) -> Dict[str, SubscriptionPlan]:
        """Get available subscription plans"""
        return self._plans
    
    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer information"""
        return self._customers.get(customer_id)
    
    def get_payment_method(self, payment_method_id: str) -> Optional[Dict[str, Any]]:
        """Get payment method information"""
        return self._payment_methods.get(payment_method_id)
    
    def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription information"""
        return self._subscriptions.get(subscription_id)


class PaymentService:
    """Main payment service orchestrator"""
    
    def __init__(self, providers: List[PaymentProvider]):
        self.providers = providers
        self._provider_map = {provider.provider_name: provider for provider in providers}
        self.default_provider = "stripe" if "stripe" in self._provider_map else list(self._provider_map.keys())[0]
        self.is_initialized = False
        
        # Idempotency tracking (in production, use Redis or database)
        self._processed_idempotency_keys: Dict[str, Dict[str, Any]] = {}
        self._idempotency_lock = asyncio.Lock()
        
        logger.info(f"Payment service initialized with providers: {list(self._provider_map.keys())}")
    
    async def initialize(self) -> bool:
        """Initialize payment service"""
        try:
            logger.info("Initializing payment service...")
            
            # Authenticate with all providers
            auth_results = {}
            for provider in self.providers:
                try:
                    auth_results[provider.provider_name] = await provider.authenticate()
                    logger.info(f"Authenticated with {provider.provider_name}: {auth_results[provider.provider_name]}")
                except Exception as e:
                    logger.error(f"Failed to authenticate with {provider.provider_name}: {e}")
                    auth_results[provider.provider_name] = False
            
            # Check if we have at least one working provider
            working_providers = [
                name for name, status in auth_results.items()
                if status
            ]
            
            if not working_providers:
                logger.warning("No payment providers are currently available")
                self.is_initialized = False
                return False
            
            logger.info(f"Connected to {len(working_providers)} payment providers: {', '.join(working_providers)}")
            self.is_initialized = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize payment service: {e}")
            self.is_initialized = False
            return False
    
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        billing_address: Optional[Dict[str, Any]] = None,
        shipping_address: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Create customer with payment provider"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            return False, None, f"Payment provider '{provider_name}' not found"
        
        customer_info = CustomerInfo(
            customer_id="",  # Will be generated by provider
            email=email,
            name=name,
            phone=phone,
            billing_address=billing_address,
            shipping_address=shipping_address,
            metadata=metadata or {}
        )
        
        return await payment_provider.create_customer(customer_info)
    
    async def add_payment_method(
        self,
        customer_id: str,
        payment_data: Dict[str, Any],
        provider: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Add payment method for customer"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            return False, None, f"Payment provider '{provider_name}' not found"
        
        return await payment_provider.create_payment_method(customer_id, payment_data)
    
    async def process_payment(
        self,
        customer_id: str,
        payment_method_id: str,
        amount: float,
        currency: str = "USD",
        description: str = "KEEPTHECHANGE.com Purchase",
        metadata: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> PaymentResult:
        """Process a payment with validation"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        # Validate request using Pydantic model
        try:
            from app.schemas.service_validation import PaymentRequest
            from pydantic import ValidationError
            # Create validation model (will raise ValidationError if invalid)
            payment_request = PaymentRequest(
                customer_id=customer_id,
                payment_method_id=payment_method_id,
                amount=amount,
                currency=currency,
                description=description,
                metadata=metadata or {}
            )
            # Use validated values
            customer_id = payment_request.customer_id
            payment_method_id = payment_request.payment_method_id
            amount = payment_request.amount
            currency = payment_request.currency
            description = payment_request.description
            metadata = payment_request.metadata
        except (ImportError, ValidationError) as e:
            # Fallback validation if schemas not available or validation fails
            if isinstance(e, ValidationError):
                error_msg = str(e.errors()[0].get('msg', 'Validation failed'))
                return PaymentResult(
                    success=False,
                    transaction_id=None,
                    amount=amount,
                    currency=currency,
                    status="failed",
                    provider=provider or self.default_provider,
                    provider_response={"error": error_msg},
                    error_message=error_msg,
                    timestamp=datetime.utcnow()
                )
            
            # ImportError fallback
            if amount <= 0:
                return PaymentResult(
                    success=False,
                    transaction_id=None,
                    amount=amount,
                    currency=currency,
                    status="failed",
                    provider=provider or self.default_provider,
                    provider_response={"error": "Amount must be positive"},
                    error_message="Amount must be positive",
                    timestamp=datetime.utcnow()
                )
            if currency not in {"USD", "EUR", "GBP", "CAD", "AUD", "JPY"}:
                return PaymentResult(
                    success=False,
                    transaction_id=None,
                    amount=amount,
                    currency=currency,
                    status="failed",
                    provider=provider or self.default_provider,
                    provider_response={"error": f"Unsupported currency: {currency}"},
                    error_message=f"Unsupported currency: {currency}",
                    timestamp=datetime.utcnow()
                )
        
        # Check idempotency key
        if idempotency_key:
            async with self._idempotency_lock:
                if idempotency_key in self._processed_idempotency_keys:
                    # Return cached result
                    cached_result = self._processed_idempotency_keys[idempotency_key]
                    logger.info(f"Returning cached result for idempotency key: {idempotency_key}")
                    return cached_result["result"]
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            result = PaymentResult(
                success=False,
                transaction_id=None,
                amount=amount,
                currency=currency,
                status="failed",
                provider=provider_name or "unknown",
                provider_response={"error": f"Provider '{provider_name}' not found"},
                error_message=f"Payment provider '{provider_name}' not found",
                timestamp=datetime.utcnow()
            )
        else:
            # Process payment
            result = await payment_provider.process_payment(
                customer_id=customer_id,
                payment_method_id=payment_method_id,
                amount=amount,
                currency=currency,
                description=description,
                metadata=metadata or {}
            )
        
        # Cache result if idempotency key provided
        if idempotency_key and result.transaction_id:
            async with self._idempotency_lock:
                self._processed_idempotency_keys[idempotency_key] = {
                    "result": result,
                    "timestamp": datetime.utcnow(),
                    "operation": "process_payment",
                    "customer_id": customer_id,
                    "amount": amount,
                    "currency": currency
                }
                # Simple cleanup: remove entries older than 24 hours
                # In production, use TTL or scheduled cleanup
                current_time = datetime.utcnow()
                keys_to_remove = []
                for key, data in self._processed_idempotency_keys.items():
                    if (current_time - data["timestamp"]).total_seconds() > 86400:  # 24 hours
                        keys_to_remove.append(key)
                for key in keys_to_remove:
                    del self._processed_idempotency_keys[key]
        
        return result
    
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        trial_days: int = 0,
        provider: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Create subscription for customer"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            return False, None, f"Payment provider '{provider_name}' not found"
        
        return await payment_provider.create_subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            payment_method_id=payment_method_id,
            trial_days=trial_days
        )
    
    async def cancel_subscription(
        self,
        subscription_id: str,
        provider: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Cancel subscription"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            return False, f"Payment provider '{provider_name}' not found"
        
        return await payment_provider.cancel_subscription(subscription_id)
    
    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Refund a payment"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            return False, None, f"Payment provider '{provider_name}' not found"
        
        return await payment_provider.refund_payment(transaction_id, amount, reason)
    
    async def process_refund(
        self,
        receipt_id: str,
        amount: float,
        currency: str,
        reason: str
    ) -> PaymentResult:
        """Process a refund (called by RefundService)"""
        # In a real implementation, we would:
        # 1. Look up the receipt to get transaction_id
        # 2. Call refund_payment with transaction_id
        # For mock implementation, we need to find a transaction to refund
        
        # Try to find a transaction that matches the receipt
        # Since we don't have access to billing service, we'll use a heuristic
        # Look for any transaction in the first provider's transaction store
        transaction_id = None
        if self.providers and hasattr(self.providers[0], '_transactions'):
            # Get the first provider
            provider = self.providers[0]
            # Look for a transaction that hasn't been refunded yet
            for tx_id, tx_data in provider._transactions.items():
                if tx_data.get('status') == 'succeeded' and 'refunded_amount' not in tx_data:
                    transaction_id = tx_id
                    break
        
        if not transaction_id:
            # No transaction found, simulate one for testing
            transaction_id = f"tx_{receipt_id.replace('rcpt_', '')[:16]}"
        
        # Process refund
        success, refund_id, message = await self.refund_payment(
            transaction_id=transaction_id,
            amount=amount,
            reason=reason
        )
        
        if success:
            return PaymentResult(
                success=True,
                transaction_id=refund_id,
                amount=amount,
                currency=currency,
                status="completed",
                provider=self.default_provider,
                provider_response={
                    "id": refund_id,
                    "status": "succeeded",
                    "amount": amount,
                    "currency": currency,
                    "reason": reason
                },
                error_message=None,
                timestamp=datetime.utcnow()
            )
        else:
            return PaymentResult(
                success=False,
                transaction_id=None,
                amount=amount,
                currency=currency,
                status="failed",
                provider=self.default_provider,
                provider_response={"error": message},
                error_message=message,
                timestamp=datetime.utcnow()
            )
    
    async def get_payment_status(
        self,
        transaction_id: str,
        provider: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get payment status"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            return None
        
        return await payment_provider.get_payment_status(transaction_id)
    
    async def get_subscription_plans(
        self,
        provider: Optional[str] = None
    ) -> Dict[str, SubscriptionPlan]:
        """Get available subscription plans"""
        if not self.is_initialized:
            raise RuntimeError("Payment service not initialized")
        
        provider_name = provider or self.default_provider
        payment_provider = self._provider_map.get(provider_name)
        
        if not payment_provider:
            return {}
        
        # Check if provider has get_plans method
        if hasattr(payment_provider, 'get_plans'):
            return payment_provider.get_plans()
        
        return {}
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get payment service status"""
        provider_status = {}
        
        for provider_name, provider in self._provider_map.items():
            provider_status[provider_name] = provider.get_provider_info()
        
        return {
            "initialized": self.is_initialized,
            "default_provider": self.default_provider,
            "providers": provider_status,
            "available_providers": list(self._provider_map.keys())
        }
    
    async def validate_payment_method(
        self,
        payment_method_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate payment method data"""
        errors = []
        
        # Validate required fields
        required_fields = ["type", "card_brand", "card_last4", "card_exp_month", "card_exp_year"]
        
        for field in required_fields:
            if field not in payment_method_data or not payment_method_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate card number (last 4 digits)
        if "card_last4" in payment_method_data:
            last4 = payment_method_data["card_last4"]
            if not (last4.isdigit() and len(last4) == 4):
                errors.append("Card last 4 digits must be 4 digits")
        
        # Validate expiration
        if "card_exp_month" in payment_method_data:
            month = payment_method_data["card_exp_month"]
            if not (1 <= month <= 12):
                errors.append("Card expiration month must be between 1 and 12")
        
        if "card_exp_year" in payment_method_data:
            year = payment_method_data["card_exp_year"]
            current_year = datetime.utcnow().year
            if year < current_year:
                errors.append("Card expiration year cannot be in the past")
            if year > current_year + 20:
                errors.append("Card expiration year is too far in the future")
        
        # Validate billing address if provided
        if "billing_address" in payment_method_data:
            address = payment_method_data["billing_address"]
            required_address_fields = ["street", "city", "state", "zip_code", "country"]
            
            for field in required_address_fields:
                if field not in address or not address[field]:
                    errors.append(f"Missing required billing address field: {field}")
        
        return len(errors) == 0, errors
    
    async def calculate_savings_investment(
        self,
        purchase_amount: float,
        savings_amount: float,
        user_tier: str = "free"
    ) -> Dict[str, Any]:
        """Calculate how much savings to invest based on user tier"""
        tier_settings = {
            "free": {
                "user_share": 0.00,  # 0% of savings
                "platform_fee": 0.20,  # 20% platform fee
                "min_savings": 0.01  # $0.01 minimum
            },
            "basic": {
                "user_share": 0.10,  # 10% of savings
                "platform_fee": 0.10,  # 10% platform fee
                "min_savings": 0.01
            },
            "pro": {
                "user_share": 0.25,  # 25% of savings
                "platform_fee": 0.00,  # 0% platform fee
                "min_savings": 0.01
            },
            "elite": {
                "user_share": 0.50,  # 50% of savings
                "platform_fee": 0.00,  # 0% platform fee
                "min_savings": 0.01
            }
        }
        
        settings = tier_settings.get(user_tier, tier_settings["free"])
        
        # Calculate investment amounts
        if savings_amount < settings["min_savings"]:
            return {
                "savings_amount": savings_amount,
                "user_share_percentage": settings["user_share"] * 100,
                "platform_fee_percentage": settings["platform_fee"] * 100,
                "user_investment": 0.0,
                "platform_investment": 0.0,
                "total_investment": 0.0,
                "investable": False,
                "reason": f"Savings ${savings_amount:.2f} below minimum ${settings['min_savings']:.2f}"
            }
        
        user_investment = savings_amount * settings["user_share"]
        platform_investment = savings_amount * settings["platform_fee"]
        total_investment = user_investment + platform_investment
        
        return {
            "savings_amount": savings_amount,
            "user_share_percentage": settings["user_share"] * 100,
            "platform_fee_percentage": settings["platform_fee"] * 100,
            "user_investment": user_investment,
            "platform_investment": platform_investment,
            "total_investment": total_investment,
            "investable": total_investment >= settings["min_savings"],
            "reason": "Ready for investment" if total_investment >= settings["min_savings"] else "Below minimum threshold"
        }
    
    async def process_savings_investment(
        self,
        purchase_id: str,
        savings_amount: float,
        user_id: str,
        user_tier: str
    ) -> Dict[str, Any]:
        """Process savings investment after purchase"""
        # Calculate investment amounts
        investment_calc = await self.calculate_savings_investment(
            purchase_amount=0,  # Not needed for calculation
            savings_amount=savings_amount,
            user_tier=user_tier
        )
        
        if not investment_calc["investable"]:
            return {
                "success": False,
                "investment_calculation": investment_calc,
                "message": investment_calc["reason"],
                "purchase_id": purchase_id,
                "user_id": user_id
            }
        
        # In a real implementation, this would:
        # 1. Create investment record in database
        # 2. Initiate crypto purchase via exchange API
        # 3. Update user's investment portfolio
        # 4. Send notification to user
        
        investment_id = f"inv_{uuid.uuid4().hex[:16]}"
        
        return {
            "success": True,
            "investment_id": investment_id,
            "investment_calculation": investment_calc,
            "purchase_id": purchase_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Investment of ${investment_calc['total_investment']:.2f} initiated (${investment_calc['user_investment']:.2f} user + ${investment_calc['platform_investment']:.2f} platform)"
        }


def create_mock_payment_service() -> PaymentService:
    """Create payment service with mock providers for testing"""
    mock_providers = [
        MockStripeProvider()
    ]
    
    return PaymentService(mock_providers)