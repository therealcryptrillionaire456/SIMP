"""
Pydantic schemas for subscription models
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
import uuid


class SubscriptionTierBase(BaseModel):
    """Base subscription tier schema"""
    name: str = Field(..., description="Tier name: free, basic, pro, elite")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = None


class SubscriptionTierResponse(SubscriptionTierBase):
    """Schema for subscription tier response"""
    id: uuid.UUID
    price_monthly_usd: float
    price_yearly_usd: Optional[float]
    billing_cycle: str
    features: List[str]
    limits: Optional[Dict[str, Any]]
    user_share_percentage: float
    transaction_fee_percentage: float
    is_active: bool
    is_visible: bool
    sort_order: int
    trial_days: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
    
    @property
    def yearly_savings(self) -> Optional[float]:
        """Calculate yearly savings vs monthly"""
        if self.price_yearly_usd and self.price_monthly_usd:
            yearly_from_monthly = self.price_monthly_usd * 12
            return yearly_from_monthly - self.price_yearly_usd
        return None
    
    @property
    def yearly_savings_percentage(self) -> Optional[float]:
        """Calculate yearly savings percentage"""
        if self.yearly_savings and self.price_monthly_usd:
            yearly_from_monthly = self.price_monthly_usd * 12
            return (self.yearly_savings / yearly_from_monthly) * 100
        return None


class SubscriptionBase(BaseModel):
    """Base subscription schema"""
    billing_cycle: str = Field("monthly", description="Billing cycle: monthly, yearly")


class SubscriptionCreate(SubscriptionBase):
    """Schema for subscription creation"""
    tier_name: str = Field(..., description="Subscription tier name")
    payment_method_id: uuid.UUID = Field(..., description="Payment method to use")
    promo_code: Optional[str] = Field(None, description="Promo code for discount")
    
    @validator('billing_cycle')
    def validate_billing_cycle(cls, v):
        allowed = ['monthly', 'yearly']
        if v not in allowed:
            raise ValueError(f'Billing cycle must be one of: {", ".join(allowed)}')
        return v


class SubscriptionUpdate(BaseModel):
    """Schema for subscription updates"""
    tier_name: Optional[str] = Field(None, description="New subscription tier")
    auto_renew: Optional[bool] = Field(None, description="Auto-renew setting")
    payment_method_id: Optional[uuid.UUID] = Field(None, description="New payment method")
    
    class Config:
        extra = "forbid"


class SubscriptionResponse(SubscriptionBase):
    """Schema for subscription response"""
    id: uuid.UUID
    user_id: uuid.UUID
    tier_id: uuid.UUID
    status: str
    price_usd: float
    currency: str
    start_date: datetime
    current_period_start: datetime
    current_period_end: datetime
    trial_start: Optional[datetime]
    trial_end: Optional[datetime]
    cancelled_at: Optional[datetime]
    ended_at: Optional[datetime]
    auto_renew: bool
    renewal_failure_count: int
    provider: Optional[str]
    provider_subscription_id: Optional[str]
    total_invested_from_fees: float
    total_returns_from_investment: float
    usage_metrics: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    tier: Optional[SubscriptionTierResponse] = None
    
    class Config:
        orm_mode = True
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is active"""
        return self.status == "active" and self.current_period_end > datetime.utcnow()
    
    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period"""
        if self.trial_end:
            return self.trial_end > datetime.utcnow()
        return False
    
    @property
    def days_until_renewal(self) -> int:
        """Calculate days until renewal"""
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def next_billing_date(self) -> datetime:
        """Get next billing date"""
        return self.current_period_end


class InvoiceResponse(BaseModel):
    """Schema for invoice response"""
    id: uuid.UUID
    subscription_id: uuid.UUID
    user_id: uuid.UUID
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
    payment_method_id: Optional[uuid.UUID]
    provider: Optional[str]
    provider_invoice_id: Optional[str]
    receipt_url: Optional[str]
    line_items: Optional[List[Dict[str, Any]]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
    
    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid"""
        return self.status == "paid" and self.payment_status == "paid"
    
    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue"""
        if self.due_date and not self.is_paid:
            return self.due_date < datetime.utcnow()
        return False


class PromoCodeRequest(BaseModel):
    """Schema for promo code validation request"""
    code: str = Field(..., description="Promo code to validate")
    tier_name: Optional[str] = Field(None, description="Subscription tier name")
    amount: Optional[float] = Field(None, ge=0, description="Purchase amount")


class PromoCodeResponse(BaseModel):
    """Schema for promo code response"""
    id: uuid.UUID
    code: str
    name: str
    description: Optional[str]
    discount_type: str
    discount_value: float
    currency: str
    applies_to: str
    applicable_tiers: Optional[List[str]]
    max_uses: Optional[int]
    max_uses_per_user: int
    current_uses: int
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
    minimum_amount: Optional[float]
    minimum_subscription_term: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
    
    @property
    def is_valid(self) -> bool:
        """Check if promo code is currently valid"""
        now = datetime.utcnow()
        
        if not self.is_active:
            return False
        
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        
        if self.valid_from and now < self.valid_from:
            return False
        
        if self.valid_until and now > self.valid_until:
            return False
        
        return True
    
    @property
    def remaining_uses(self) -> Optional[int]:
        """Get remaining uses"""
        if self.max_uses:
            return max(0, self.max_uses - self.current_uses)
        return None


class BillingInfoResponse(BaseModel):
    """Schema for billing information response"""
    user_id: uuid.UUID
    current_subscription: Optional[SubscriptionResponse]
    next_billing_date: Optional[datetime]
    days_until_billing: Optional[int]
    total_spent: float
    recent_invoices: List[InvoiceResponse]
    payment_methods: List[Dict[str, Any]]
    billing_address: Optional[Dict[str, Any]]


class SubscriptionComparison(BaseModel):
    """Schema for subscription tier comparison"""
    tiers: List[SubscriptionTierResponse]
    comparison: Dict[str, List[Any]]


class UpgradePath(BaseModel):
    """Schema for subscription upgrade path"""
    current_tier: str
    target_tier: str
    price_difference: float
    prorated_amount: Optional[float]
    effective_date: datetime
    features_gained: List[str]
    features_lost: List[str]


class TrialStatus(BaseModel):
    """Schema for trial status"""
    is_trialing: bool
    trial_start: Optional[datetime]
    trial_end: Optional[datetime]
    days_remaining: Optional[int]
    tier_name: Optional[str]


# Export all schemas
__all__ = [
    "SubscriptionTierBase",
    "SubscriptionTierResponse",
    "SubscriptionBase",
    "SubscriptionCreate",
    "SubscriptionUpdate",
    "SubscriptionResponse",
    "InvoiceResponse",
    "PromoCodeRequest",
    "PromoCodeResponse",
    "BillingInfoResponse",
    "SubscriptionComparison",
    "UpgradePath",
    "TrialStatus"
]