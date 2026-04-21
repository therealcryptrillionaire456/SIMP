"""
Pydantic schemas for payment models
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
import uuid


class PaymentMethodBase(BaseModel):
    """Base payment method schema"""
    provider: str = Field(..., description="Payment provider: stripe, paypal, apple_pay, google_pay")
    payment_type: str = Field(..., description="Payment type: card, bank_account, wallet")
    billing_address: Optional[Dict[str, Any]] = None


class PaymentMethodCreate(PaymentMethodBase):
    """Schema for payment method creation"""
    card_brand: Optional[str] = Field(None, description="Card brand: visa, mastercard, amex, discover")
    card_last4: Optional[str] = Field(None, min_length=4, max_length=4, description="Last 4 digits of card")
    card_exp_month: Optional[int] = Field(None, ge=1, le=12, description="Card expiration month")
    card_exp_year: Optional[int] = Field(None, ge=2024, le=2030, description="Card expiration year")
    bank_name: Optional[str] = Field(None, description="Bank name for bank accounts")
    bank_last4: Optional[str] = Field(None, min_length=4, max_length=4, description="Last 4 digits of bank account")
    is_default: Optional[bool] = Field(False, description="Set as default payment method")
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed = ['stripe', 'paypal', 'apple_pay', 'google_pay']
        if v not in allowed:
            raise ValueError(f'Provider must be one of: {", ".join(allowed)}')
        return v
    
    @validator('payment_type')
    def validate_payment_type(cls, v):
        allowed = ['card', 'bank_account', 'wallet']
        if v not in allowed:
            raise ValueError(f'Payment type must be one of: {", ".join(allowed)}')
        return v
    
    @validator('card_brand')
    def validate_card_brand(cls, v, values):
        if values.get('payment_type') == 'card' and not v:
            raise ValueError('Card brand is required for card payments')
        return v
    
    @validator('card_last4')
    def validate_card_last4(cls, v, values):
        if values.get('payment_type') == 'card' and not v:
            raise ValueError('Card last 4 digits are required for card payments')
        return v


class PaymentMethodUpdate(BaseModel):
    """Schema for payment method updates"""
    is_default: Optional[bool] = None
    billing_address: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "forbid"


class PaymentMethodResponse(PaymentMethodBase):
    """Schema for payment method response"""
    id: uuid.UUID
    user_id: uuid.UUID
    card_brand: Optional[str]
    card_last4: Optional[str]
    card_exp_month: Optional[int]
    card_exp_year: Optional[int]
    bank_name: Optional[str]
    bank_last4: Optional[str]
    is_default: bool
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_used: Optional[datetime]
    
    class Config:
        from_attributes = True
    
    @property
    def masked_number(self) -> str:
        """Get masked card/bank number"""
        if self.card_last4:
            return f"**** **** **** {self.card_last4}"
        elif self.bank_last4:
            return f"****{self.bank_last4}"
        return "****"
    
    @property
    def display_name(self) -> str:
        """Get display name for payment method"""
        if self.card_brand and self.card_last4:
            return f"{self.card_brand.upper()} {self.masked_number}"
        elif self.bank_name and self.bank_last4:
            return f"{self.bank_name} {self.masked_number}"
        return f"{self.provider} {self.payment_type}"


class PurchaseResponse(BaseModel):
    """Schema for purchase response (payment focused)"""
    id: uuid.UUID
    purchase_number: str
    total_amount: float
    subtotal: float
    tax_amount: float
    shipping_amount: float
    savings_amount: float
    savings_percentage: Optional[float]
    currency: str
    payment_status: str
    payment_provider: Optional[str]
    status: str
    item_count: int
    created_at: datetime
    purchased_at: Optional[datetime]
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm(cls, purchase):
        """Create response from Purchase object"""
        return cls(
            id=purchase.id,
            purchase_number=purchase.purchase_number,
            total_amount=purchase.total_amount,
            subtotal=purchase.subtotal,
            tax_amount=purchase.tax_amount,
            shipping_amount=purchase.shipping_amount,
            savings_amount=purchase.savings_amount,
            savings_percentage=purchase.savings_percentage,
            currency=purchase.currency,
            payment_status=purchase.payment_status,
            payment_provider=purchase.payment_provider,
            status=purchase.status,
            item_count=purchase.item_count,
            created_at=purchase.created_at,
            purchased_at=purchase.purchased_at
        )


class RefundRequest(BaseModel):
    """Schema for refund request"""
    amount: Optional[float] = Field(None, ge=0.01, description="Refund amount (defaults to full amount)")
    reason: str = Field(..., min_length=1, max_length=255, description="Reason for refund")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")


class RefundResponse(BaseModel):
    """Schema for refund response"""
    id: uuid.UUID
    purchase_id: uuid.UUID
    refund_amount: float
    refund_reason: Optional[str]
    refund_notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm(cls, refund):
        """Create response from Refund object"""
        return cls(
            id=refund.id,
            purchase_id=refund.purchase_id,
            refund_amount=refund.refund_amount,
            refund_reason=refund.refund_reason,
            refund_notes=refund.refund_notes,
            status=refund.status,
            created_at=refund.created_at,
            updated_at=refund.updated_at,
            completed_at=refund.completed_at
        )


class PaymentIntentRequest(BaseModel):
    """Schema for payment intent creation"""
    amount: float = Field(..., ge=0.01, description="Amount in USD")
    currency: str = Field("USD", description="Currency code")
    payment_method_id: uuid.UUID = Field(..., description="Payment method to use")
    purchase_id: Optional[uuid.UUID] = Field(None, description="Associated purchase ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class PaymentIntentResponse(BaseModel):
    """Schema for payment intent response"""
    id: str
    client_secret: Optional[str]
    amount: float
    currency: str
    status: str
    payment_method: Optional[str]
    created_at: datetime


class InvoiceResponse(BaseModel):
    """Schema for invoice response"""
    id: uuid.UUID
    invoice_number: str
    amount_usd: float
    currency: str
    tax_amount: float
    total_amount: float
    status: str
    payment_status: str
    period_start: datetime
    period_end: datetime
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    receipt_url: Optional[str]
    created_at: datetime


class TransactionSummary(BaseModel):
    """Schema for transaction summary"""
    total_spent: float
    total_savings: float
    average_savings_percentage: float
    payment_methods_count: int
    recent_transactions: List[Dict[str, Any]]


class WebhookEvent(BaseModel):
    """Schema for webhook event"""
    id: str
    type: str
    data: Dict[str, Any]
    created: datetime
    livemode: bool


# Export all schemas
__all__ = [
    "PaymentMethodBase",
    "PaymentMethodCreate",
    "PaymentMethodUpdate",
    "PaymentMethodResponse",
    "PurchaseResponse",
    "RefundRequest",
    "RefundResponse",
    "PaymentIntentRequest",
    "PaymentIntentResponse",
    "InvoiceResponse",
    "TransactionSummary",
    "WebhookEvent"
]