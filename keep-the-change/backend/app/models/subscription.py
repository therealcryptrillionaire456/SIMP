"""
Subscription models for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SubscriptionTier(Base):
    """Subscription tier definition"""
    
    __tablename__ = "subscription_tiers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Tier identification
    name = Column(String(50), nullable=False, unique=True, index=True)  # free, basic, pro, elite
    display_name = Column(String(100), nullable=False)  # Free, Basic, Pro, Elite
    description = Column(Text, nullable=True)
    
    # Pricing
    price_monthly_usd = Column(Float, nullable=False)
    price_yearly_usd = Column(Float, nullable=True)  # Annual price if available
    billing_cycle = Column(String(20), default="monthly")  # monthly, yearly
    
    # Features
    features = Column(JSON, nullable=False, default=[])
    limits = Column(JSON, nullable=True)  # Usage limits for this tier
    
    # Investment share
    user_share_percentage = Column(Float, default=0.0)  # Percentage of agent returns user gets
    transaction_fee_percentage = Column(Float, default=0.02)  # Transaction fee percentage
    
    # Status
    is_active = Column(Boolean, default=True)
    is_visible = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)  # For display ordering
    
    # Trial period
    trial_days = Column(Integer, default=0)  # Free trial days
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="tier")
    
    def __repr__(self):
        return f"<SubscriptionTier(id={self.id}, name={self.name}, price={self.price_monthly_usd})>"
    
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


class Subscription(Base):
    """User subscription"""
    
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tier_id = Column(UUID(as_uuid=True), ForeignKey("subscription_tiers.id"), nullable=False, index=True)
    
    # Subscription details
    status = Column(String(20), default="active")  # active, cancelled, expired, past_due
    billing_cycle = Column(String(20), default="monthly")  # monthly, yearly
    
    # Payment details
    price_usd = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)
    
    # Billing dates
    start_date = Column(DateTime, nullable=False)
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Auto-renewal
    auto_renew = Column(Boolean, default=True)
    renewal_failure_count = Column(Integer, default=0)
    
    # Payment provider
    provider = Column(String(50), nullable=True)  # stripe, paypal, etc.
    provider_subscription_id = Column(String(100), nullable=True)
    provider_customer_id = Column(String(100), nullable=True)
    
    # Investment tracking
    total_invested_from_fees = Column(Float, default=0.0)  # Subscription fees invested
    total_returns_from_investment = Column(Float, default=0.0)  # Returns from those investments
    
    # Usage tracking
    usage_metrics = Column(JSON, default={})  # Monthly usage statistics
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    tier = relationship("SubscriptionTier", back_populates="subscriptions")
    payment_method = relationship("PaymentMethod")
    invoices = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user={self.user_id}, tier={self.tier_id}, status={self.status})>"
    
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


class Invoice(Base):
    """Subscription invoice"""
    
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Invoice details
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    tax_amount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    
    # Billing period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Payment status
    status = Column(String(20), default="draft")  # draft, open, paid, void, uncollectible
    payment_status = Column(String(20), default="pending")  # pending, paid, failed, refunded
    
    # Payment details
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    
    # Provider information
    provider = Column(String(50), nullable=True)  # stripe, paypal, etc.
    provider_invoice_id = Column(String(100), nullable=True)
    provider_payment_intent_id = Column(String(100), nullable=True)
    receipt_url = Column(Text, nullable=True)
    
    # Line items
    line_items = Column(JSON, nullable=True)  # Array of line items
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")
    user = relationship("User")
    payment_method = relationship("PaymentMethod")
    
    def __repr__(self):
        return f"<Invoice(id={self.id}, number={self.invoice_number}, amount={self.amount_usd})>"
    
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


class PromoCode(Base):
    """Promotion code for subscriptions"""
    
    __tablename__ = "promo_codes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Code details
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Discount details
    discount_type = Column(String(20), default="percentage")  # percentage, fixed_amount
    discount_value = Column(Float, nullable=False)  # Percentage or fixed amount
    currency = Column(String(3), default="USD")
    
    # Applicability
    applies_to = Column(String(20), default="all")  # all, specific_tiers, specific_users
    applicable_tiers = Column(JSON, nullable=True)  # Array of tier names
    applicable_users = Column(JSON, nullable=True)  # Array of user IDs
    
    # Usage limits
    max_uses = Column(Integer, nullable=True)  # Total maximum uses
    max_uses_per_user = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    
    # Validity period
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    
    # Minimum requirements
    minimum_amount = Column(Float, nullable=True)
    minimum_subscription_term = Column(String(20), nullable=True)  # monthly, yearly
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    redemptions = relationship("PromoCodeRedemption", back_populates="promo_code", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PromoCode(id={self.id}, code={self.code}, discount={self.discount_value})>"
    
    @property
    def is_valid(self) -> bool:
        """Check if promo code is currently valid"""
        now = datetime.utcnow()
        
        # Check active status
        if not self.is_active:
            return False
        
        # Check usage limits
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        
        # Check validity period
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


class PromoCodeRedemption(Base):
    """Promo code redemption record"""
    
    __tablename__ = "promo_code_redemptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("promo_codes.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True, index=True)
    
    # Redemption details
    discount_applied = Column(Float, nullable=False)
    original_amount = Column(Float, nullable=False)
    final_amount = Column(Float, nullable=False)
    
    # Context
    redemption_context = Column(JSON, nullable=True)  # Additional context about redemption
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    promo_code = relationship("PromoCode", back_populates="redemptions")
    user = relationship("User")
    subscription = relationship("Subscription")
    
    def __repr__(self):
        return f"<PromoCodeRedemption(id={self.id}, code={self.promo_code_id}, user={self.user_id})>"