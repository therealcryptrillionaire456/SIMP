"""
Pydantic models for service layer request validation.
These models validate input before passing to business logic services.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator, constr
import re


class PaymentRequest(BaseModel):
    """Validation model for payment processing requests"""
    customer_id: str = Field(..., min_length=1, description="Customer identifier")
    payment_method_id: str = Field(..., min_length=1, description="Payment method identifier")
    amount: float = Field(..., gt=0, le=1000000, description="Payment amount (must be positive, max $1,000,000)")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$", description="3-letter currency code")
    description: str = Field(..., min_length=1, max_length=500, description="Payment description")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('amount')
    def validate_amount(cls, v):
        """Validate amount is reasonable"""
        if v <= 0:
            raise ValueError('Amount must be positive')
        if v > 1000000:  # $1M limit
            raise ValueError('Amount exceeds maximum limit of $1,000,000')
        # Round to 2 decimal places for currency
        return round(v, 2)
    
    @validator('currency')
    def validate_currency(cls, v):
        """Validate currency code"""
        supported_currencies = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY"}
        if v not in supported_currencies:
            raise ValueError(f'Unsupported currency. Supported: {", ".join(sorted(supported_currencies))}')
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """Sanitize description"""
        # Remove excessive whitespace
        v = ' '.join(v.split())
        # Truncate if too long
        if len(v) > 500:
            v = v[:497] + "..."
        return v


class RefundRequest(BaseModel):
    """Validation model for refund requests"""
    receipt_id: str = Field(..., min_length=1, description="Receipt identifier")
    user_id: str = Field(..., min_length=1, description="User identifier")
    amount: float = Field(..., gt=0, description="Refund amount (must be positive)")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$", description="3-letter currency code")
    reason: str = Field(..., min_length=1, max_length=50, description="Refund reason code")
    reason_details: Optional[str] = Field(None, max_length=1000, description="Detailed refund reason")
    
    @validator('amount')
    def validate_amount(cls, v):
        """Validate refund amount"""
        if v <= 0:
            raise ValueError('Refund amount must be positive')
        if v > 1000000:  # $1M limit
            raise ValueError('Refund amount exceeds maximum limit of $1,000,000')
        return round(v, 2)
    
    @validator('reason')
    def validate_reason(cls, v):
        """Validate refund reason"""
        valid_reasons = {
            "requested_by_customer", "duplicate", "fraudulent", 
            "product_unsatisfactory", "product_not_received", "other"
        }
        if v not in valid_reasons:
            raise ValueError(f'Invalid refund reason. Valid reasons: {", ".join(sorted(valid_reasons))}')
        return v


class CustomerCreateRequest(BaseModel):
    """Validation model for customer creation"""
    email: constr(strict=True, min_length=1, max_length=255) = Field(..., description="Customer email")
    name: str = Field(..., min_length=1, max_length=100, description="Customer name")
    phone: Optional[str] = Field(None, max_length=20, description="Customer phone number")
    billing_address: Optional[Dict[str, Any]] = Field(None, description="Billing address")
    shipping_address: Optional[Dict[str, Any]] = Field(None, description="Shipping address")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('email')
    def validate_email(cls, v):
        """Validate email format"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower()  # Normalize to lowercase
    
    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format"""
        if v is None:
            return v
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', v)
        if len(digits) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        return digits


class InvoiceCreateRequest(BaseModel):
    """Validation model for invoice creation"""
    subscription_id: str = Field(..., min_length=1, description="Subscription identifier")
    user_id: str = Field(..., min_length=1, description="User identifier")
    amount: float = Field(..., gt=0, le=1000000, description="Invoice amount")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$", description="3-letter currency code")
    description: str = Field(..., min_length=1, max_length=500, description="Invoice description")
    period_start: datetime = Field(..., description="Billing period start")
    period_end: datetime = Field(..., description="Billing period end")
    due_days: int = Field(default=30, ge=0, le=365, description="Days until due")
    
    @validator('period_end')
    def validate_period_end(cls, v, values):
        """Validate period_end is after period_start"""
        if 'period_start' in values and v <= values['period_start']:
            raise ValueError('period_end must be after period_start')
        return v
    
    @validator('amount')
    def validate_amount(cls, v):
        """Validate invoice amount"""
        if v <= 0:
            raise ValueError('Invoice amount must be positive')
        return round(v, 2)


class SubscriptionCreateRequest(BaseModel):
    """Validation model for subscription creation"""
    user_id: str = Field(..., min_length=1, description="User identifier")
    plan_id: str = Field(..., min_length=1, description="Subscription plan identifier")
    payment_method_id: Optional[str] = Field(None, description="Payment method identifier")
    start_trial: bool = Field(default=False, description="Start with trial period")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('plan_id')
    def validate_plan_id(cls, v):
        """Validate plan ID"""
        valid_plans = {"free", "basic", "pro", "elite"}
        if v not in valid_plans:
            raise ValueError(f'Invalid plan ID. Valid plans: {", ".join(sorted(valid_plans))}')
        return v


class IdempotencyKeyRequest(BaseModel):
    """Validation model for idempotency key requests"""
    idempotency_key: str = Field(..., min_length=1, max_length=128, description="Idempotency key")
    operation: str = Field(..., min_length=1, max_length=50, description="Operation type")
    request_hash: Optional[str] = Field(None, description="Hash of request parameters for validation")


def validate_payment_request(data: Dict[str, Any]) -> PaymentRequest:
    """Validate payment request data"""
    return PaymentRequest(**data)


def validate_refund_request(data: Dict[str, Any]) -> RefundRequest:
    """Validate refund request data"""
    return RefundRequest(**data)


def validate_customer_create_request(data: Dict[str, Any]) -> CustomerCreateRequest:
    """Validate customer creation request data"""
    return CustomerCreateRequest(**data)