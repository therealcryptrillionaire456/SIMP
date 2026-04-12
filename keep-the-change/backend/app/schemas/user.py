"""
Pydantic schemas for user models
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field, validator
import uuid


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user creation"""
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        # Add more password validation as needed
        return v


class UserUpdate(BaseModel):
    """Schema for user updates"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "forbid"  # Don't allow extra fields


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str
    device_info: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SocialAuthRequest(BaseModel):
    """Schema for social authentication"""
    provider: str = Field(..., description="Social provider: google, facebook, apple")
    token: str = Field(..., description="Access token from social provider")
    user_info: Dict[str, Any] = Field(..., description="User information from social provider")
    device_info: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    @validator('provider')
    def validate_provider(cls, v):
        """Validate social provider"""
        allowed_providers = ['google', 'facebook', 'apple']
        if v not in allowed_providers:
            raise ValueError(f'Provider must be one of: {", ".join(allowed_providers)}')
        return v


class UserResponse(UserBase):
    """Schema for user response"""
    id: uuid.UUID
    email_verified: bool = False
    subscription_tier: str = "free"
    subscription_status: str = "active"
    total_savings: float = 0.0
    total_invested: float = 0.0
    crypto_balance: float = 0.0
    total_returns: float = 0.0
    avatar_url: Optional[str] = None
    preferences: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
    
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


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration
    user: UserResponse


class UserStatsResponse(BaseModel):
    """Schema for user statistics"""
    user_id: uuid.UUID
    total_savings: float
    total_invested: float
    crypto_balance: float
    total_returns: float
    portfolio_value: float
    subscription_tier: str
    account_age_days: int
    last_login: Optional[datetime]
    metrics: Dict[str, Any] = {}


class WalletConnectRequest(BaseModel):
    """Schema for wallet connection"""
    wallet_address: str
    wallet_type: str = Field("solana", description="Wallet type: solana, ethereum, etc.")
    network: str = Field("mainnet", description="Network: mainnet, testnet, devnet")


class TwoFactorSetupRequest(BaseModel):
    """Schema for 2FA setup"""
    enable: bool = True
    method: str = Field("totp", description="2FA method: totp, sms, email")


class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""
    token: str
    new_password: str = Field(..., min_length=8)


class EmailVerificationRequest(BaseModel):
    """Schema for email verification request"""
    token: str


class UserSearchResponse(BaseModel):
    """Schema for user search response"""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


class UserActivityResponse(BaseModel):
    """Schema for user activity response"""
    user_id: uuid.UUID
    activities: List[Dict[str, Any]]
    total_activities: int
    period_start: datetime
    period_end: datetime


# Export all schemas
__all__ = [
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserLogin",
    "SocialAuthRequest",
    "UserResponse",
    "TokenResponse",
    "UserStatsResponse",
    "WalletConnectRequest",
    "TwoFactorSetupRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "EmailVerificationRequest",
    "UserSearchResponse",
    "UserActivityResponse"
]