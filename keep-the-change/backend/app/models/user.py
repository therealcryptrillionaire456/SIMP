"""
User models for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Boolean, Float, JSON, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """User account model"""
    
    __tablename__ = "users"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    email_verified = Column(Boolean, default=False)
    password_hash = Column(String(255), nullable=True)  # Nullable for social auth
    
    # Social authentication
    social_auth_provider = Column(String(50), nullable=True)  # google, facebook, apple
    social_auth_id = Column(String(255), nullable=True, unique=True, index=True)
    social_auth_data = Column(JSON, nullable=True)  # Store additional social data
    
    # Profile
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    avatar_url = Column(Text, nullable=True)
    
    # Subscription
    subscription_tier = Column(String(20), default="free")
    subscription_status = Column(String(20), default="active")  # active, cancelled, expired
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    
    # Financial tracking
    total_savings = Column(Float, default=0.0)  # Total savings from all purchases
    total_invested = Column(Float, default=0.0)  # Total amount invested in crypto
    crypto_balance = Column(Float, default=0.0)  # Current crypto balance in USD
    total_returns = Column(Float, default=0.0)  # Total returns from investments
    
    # Wallet information (for crypto payouts)
    crypto_wallet_address = Column(String(255), nullable=True)
    crypto_wallet_type = Column(String(50), nullable=True)  # solana, ethereum, etc.
    
    # Preferences
    preferences = Column(JSON, default={
        "auto_purchase": False,
        "auto_invest": True,
        "investment_risk": "medium",
        "default_shipping_address": None,
        "notification_preferences": {
            "email": True,
            "push": True,
            "sms": False
        }
    })
    
    # Security
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Relationships
    payment_methods = relationship("PaymentMethod", back_populates="user", cascade="all, delete-orphan")
    shopping_lists = relationship("ShoppingList", back_populates="user", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="user", cascade="all, delete-orphan")
    investments = relationship("UserInvestment", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, tier={self.subscription_tier})>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.email.split('@')[0]
    
    @property
    def is_active(self) -> bool:
        """Check if user account is active"""
        return self.deleted_at is None and self.subscription_status == "active"
    
    @property
    def is_premium(self) -> bool:
        """Check if user has premium subscription"""
        return self.subscription_tier in ["basic", "pro", "elite"]
    
    @property
    def total_portfolio_value(self) -> float:
        """Calculate total portfolio value (invested + returns)"""
        return self.total_invested + self.total_returns


class UserSession(Base):
    """User session tracking"""
    
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    device_info = Column(JSON, nullable=True)  # Browser, OS, device type
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, expires_at={self.expires_at})>"


class UserAuditLog(Base):
    """Audit log for user actions"""
    
    __tablename__ = "user_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # login, logout, update_profile, etc.
    resource_type = Column(String(50), nullable=True)  # user, payment, purchase, etc.
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)  # Additional details about the action
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserAuditLog(user_id={self.user_id}, action={self.action})>"