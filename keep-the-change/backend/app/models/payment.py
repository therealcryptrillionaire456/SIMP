"""
Payment models for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Float, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class PaymentMethod(Base):
    """User payment method"""
    
    __tablename__ = "payment_methods"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Payment provider
    provider = Column(String(50), nullable=False)  # stripe, paypal, apple_pay, google_pay
    provider_customer_id = Column(String(100), nullable=True)  # Customer ID in provider system
    provider_payment_method_id = Column(String(100), nullable=False)  # Payment method ID in provider system
    
    # Payment details (encrypted or tokenized)
    payment_type = Column(String(50), nullable=False)  # card, bank_account, wallet
    card_brand = Column(String(50), nullable=True)  # visa, mastercard, amex, discover
    card_last4 = Column(String(4), nullable=True)
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)
    bank_name = Column(String(100), nullable=True)
    bank_last4 = Column(String(4), nullable=True)
    
    # Billing address
    billing_address = Column(JSON, nullable=True)  # {street, city, state, zip, country}
    
    # Status
    is_default = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Fraud prevention
    fraud_score = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True)  # low, medium, high
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payment_methods")
    purchases = relationship("Purchase", back_populates="payment_method")
    
    def __repr__(self):
        return f"<PaymentMethod(id={self.id}, type={self.payment_type}, last4={self.card_last4})>"
    
    @property
    def masked_number(self) -> str:
        """Get masked card number"""
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


class Purchase(Base):
    """Purchase record"""
    
    __tablename__ = "purchases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    list_id = Column(UUID(as_uuid=True), ForeignKey("shopping_lists.id"), nullable=True, index=True)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)
    
    # Purchase details
    purchase_number = Column(String(50), unique=True, nullable=False, index=True)  # Human-readable ID
    total_amount = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    shipping_amount = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    
    # Savings calculation
    estimated_retail_price = Column(Float, nullable=True)  # Estimated price at regular retailers
    savings_amount = Column(Float, default=0.0)  # The "change" - savings vs estimated retail
    savings_percentage = Column(Float, nullable=True)
    
    # Payment information
    currency = Column(String(3), default="USD")
    payment_status = Column(String(20), default="pending")  # pending, processing, completed, failed, refunded
    payment_provider = Column(String(50), nullable=True)  # stripe, paypal, etc.
    payment_transaction_id = Column(String(100), nullable=True)  # Provider transaction ID
    payment_receipt_url = Column(Text, nullable=True)
    
    # Shipping information
    shipping_address = Column(JSON, nullable=True)
    shipping_method = Column(String(100), nullable=True)
    shipping_carrier = Column(String(50), nullable=True)  # ups, fedex, usps
    tracking_number = Column(String(100), nullable=True)
    tracking_url = Column(Text, nullable=True)
    estimated_delivery_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)
    
    # Order details
    retailer_breakdown = Column(JSON, nullable=True)  # {retailer: amount, items: [...]}
    item_count = Column(Integer, default=0)
    
    # Investment status
    change_invested = Column(Boolean, default=False)
    investment_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to crypto investment
    
    # Status tracking
    status = Column(String(20), default="created")  # created, processing, shipped, delivered, cancelled
    status_history = Column(JSON, default=[])  # Array of {status, timestamp, note}
    
    # Customer notes
    customer_notes = Column(Text, nullable=True)
    
    # Fraud and risk
    fraud_score = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    purchased_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="purchases")
    shopping_list = relationship("ShoppingList", back_populates="purchase")
    payment_method = relationship("PaymentMethod", back_populates="purchases")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")
    crypto_investment = relationship("CryptoInvestment", back_populates="purchase", uselist=False)
    
    def __repr__(self):
        return f"<Purchase(id={self.id}, total={self.total_amount}, status={self.status})>"
    
    @property
    def formatted_total(self) -> str:
        """Get formatted total amount"""
        return f"${self.total_amount:.2f}"
    
    @property
    def formatted_savings(self) -> str:
        """Get formatted savings amount"""
        return f"${self.savings_amount:.2f}"
    
    @property
    def is_completed(self) -> bool:
        """Check if purchase is completed"""
        return self.status == "delivered" and self.payment_status == "completed"
    
    @property
    def can_be_invested(self) -> bool:
        """Check if savings can be invested"""
        return (self.savings_amount >= 0.01 and  # Minimum $0.01
                not self.change_invested and
                self.is_completed)


class PurchaseItem(Base):
    """Individual item in a purchase"""
    
    __tablename__ = "purchase_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_id = Column(UUID(as_uuid=True), ForeignKey("purchases.id"), nullable=False, index=True)
    list_item_id = Column(UUID(as_uuid=True), ForeignKey("list_items.id"), nullable=True)
    
    # Product information
    product_name = Column(String(255), nullable=False)
    brand = Column(String(100), nullable=True)
    upc = Column(String(20), nullable=True)
    sku = Column(String(100), nullable=True)
    
    # Purchase details
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    # Retailer information
    retailer = Column(String(100), nullable=False)
    retailer_product_id = Column(String(100), nullable=True)
    product_url = Column(Text, nullable=True)
    
    # Shipping
    shipping_cost = Column(Float, default=0.0)
    estimated_delivery_days = Column(Integer, nullable=True)
    
    # Comparison data
    estimated_retail_price = Column(Float, nullable=True)
    savings_amount = Column(Float, nullable=True)
    
    # Status
    status = Column(String(20), default="ordered")  # ordered, shipped, delivered, cancelled
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase = relationship("Purchase", back_populates="items")
    
    def __repr__(self):
        return f"<PurchaseItem(id={self.id}, product={self.product_name}, quantity={self.quantity})>"
    
    @property
    def savings_percentage(self) -> Optional[float]:
        """Calculate savings percentage"""
        if self.estimated_retail_price and self.estimated_retail_price > 0:
            return ((self.estimated_retail_price - self.unit_price) / self.estimated_retail_price) * 100
        return None


class Refund(Base):
    """Refund record"""
    
    __tablename__ = "refunds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_id = Column(UUID(as_uuid=True), ForeignKey("purchases.id"), nullable=False, index=True)
    
    # Refund details
    refund_amount = Column(Float, nullable=False)
    refund_reason = Column(String(255), nullable=True)
    refund_notes = Column(Text, nullable=True)
    
    # Payment provider information
    provider_refund_id = Column(String(100), nullable=True)
    provider_status = Column(String(50), nullable=True)
    
    # Status
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    purchase = relationship("Purchase")
    
    def __repr__(self):
        return f"<Refund(id={self.id}, amount={self.refund_amount}, status={self.status})>"