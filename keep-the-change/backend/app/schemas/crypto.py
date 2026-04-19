"""
Pydantic schemas for crypto models
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
import uuid


class CryptoInvestmentBase(BaseModel):
    """Base crypto investment schema"""
    investment_type: str = Field(..., description="Type: savings, tip, subscription_fee")
    amount_usd: float = Field(..., ge=0.01, description="Investment amount in USD")
    crypto_asset: str = Field(..., description="Crypto asset: BTC, ETH, SOL, etc.")
    trading_strategy: str = Field("dollar_cost_average", description="Trading strategy")


class CryptoInvestmentResponse(CryptoInvestmentBase):
    """Schema for crypto investment response"""
    id: uuid.UUID
    purchase_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    crypto_amount: float
    exchange_rate: float
    exchange: Optional[str]
    transaction_hash: Optional[str]
    status: str
    current_value_usd: Optional[float]
    profit_loss_usd: float
    profit_loss_percentage: Optional[float]
    risk_level: str
    simp_intent_id: Optional[str]
    simp_agent: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
    
    @property
    def current_exchange_rate(self) -> Optional[float]:
        """Calculate current exchange rate"""
        if self.current_value_usd and self.crypto_amount > 0:
            return self.current_value_usd / self.crypto_amount
        return None
    
    @property
    def is_profitable(self) -> bool:
        """Check if investment is profitable"""
        return self.profit_loss_usd > 0 if self.profit_loss_usd else False
    
    @property
    def holding_period_days(self) -> Optional[int]:
        """Calculate holding period in days"""
        if self.executed_at:
            delta = datetime.utcnow() - self.executed_at
            return delta.days
        return None


class UserInvestmentCreate(BaseModel):
    """Schema for user investment creation"""
    amount_usd: float = Field(..., ge=0.01, description="Investment amount in USD")
    auto_reinvest: bool = Field(True, description="Automatically reinvest returns")


class UserInvestmentResponse(BaseModel):
    """Schema for user investment response"""
    id: uuid.UUID
    user_id: uuid.UUID
    investment_type: str
    amount_usd: float
    share_percentage: float
    subscription_tier: Optional[str]
    total_returns_usd: float
    pending_returns_usd: float
    status: str
    auto_reinvest: bool
    start_date: datetime
    end_date: Optional[datetime]
    annualized_return: Optional[float]
    total_return_percentage: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True
    
    @property
    def is_active(self) -> bool:
        """Check if investment is active"""
        return self.status == "active" and (self.end_date is None or self.end_date > datetime.utcnow())
    
    @property
    def investment_duration_days(self) -> int:
        """Calculate investment duration in days"""
        delta = datetime.utcnow() - self.start_date
        return delta.days


class AgentPortfolioResponse(BaseModel):
    """Schema for agent portfolio response"""
    id: uuid.UUID
    total_assets_usd: float
    total_invested_usd: float
    total_returns_usd: float
    crypto_breakdown: Dict[str, float]
    asset_allocation: Dict[str, float]
    daily_return_usd: float
    daily_return_percentage: float
    weekly_return_usd: float
    weekly_return_percentage: float
    monthly_return_usd: float
    monthly_return_percentage: float
    annual_return_usd: float
    annual_return_percentage: float
    volatility: Optional[float]
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_user_funds_usd: float
    total_distributed_returns_usd: float
    platform_fees_usd: float
    snapshot_date: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True
    
    @property
    def net_profit(self) -> float:
        """Calculate net profit"""
        return self.total_returns_usd - self.total_invested_usd
    
    @property
    def roi(self) -> float:
        """Calculate return on investment"""
        if self.total_invested_usd > 0:
            return (self.net_profit / self.total_invested_usd) * 100
        return 0.0
    
    @property
    def user_share_value(self) -> float:
        """Calculate value of user shares"""
        return self.total_user_funds_usd + self.total_distributed_returns_usd


class ReturnsDistributionResponse(BaseModel):
    """Schema for returns distribution response"""
    id: uuid.UUID
    investment_id: Optional[uuid.UUID]
    user_investment_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    distribution_type: str
    amount_usd: float
    crypto_amount: Optional[float]
    crypto_asset: Optional[str]
    payment_method: str
    wallet_address: Optional[str]
    transaction_hash: Optional[str]
    status: str
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    created_at: datetime
    distributed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
    
    @property
    def is_completed(self) -> bool:
        """Check if distribution is completed"""
        return self.status == "completed"


class CryptoTradeResponse(BaseModel):
    """Schema for crypto trade response"""
    id: uuid.UUID
    investment_id: Optional[uuid.UUID]
    trade_type: str
    crypto_asset: str
    crypto_amount: float
    usd_amount: float
    price_per_unit: float
    exchange: str
    exchange_order_id: Optional[str]
    exchange_trade_id: Optional[str]
    transaction_hash: Optional[str]
    status: str
    fill_percentage: float
    created_at: datetime
    executed_at: Optional[datetime]
    filled_at: Optional[datetime]
    
    class Config:
        from_attributes = True
    
    @property
    def is_buy(self) -> bool:
        """Check if trade is a buy order"""
        return self.trade_type == "buy"
    
    @property
    def is_sell(self) -> bool:
        """Check if trade is a sell order"""
        return self.trade_type == "sell"


class TipRequest(BaseModel):
    """Schema for tipping the agent"""
    amount: float = Field(..., ge=0.01, description="Tip amount in USD")
    auto_reinvest: bool = Field(True, description="Automatically reinvest returns from tip")
    message: Optional[str] = Field(None, max_length=500, description="Optional message for the agent")


class InvestmentStatsResponse(BaseModel):
    """Schema for investment statistics"""
    user_id: uuid.UUID
    total_crypto_invested: float
    total_crypto_returns: float
    crypto_roi_percentage: float
    total_user_invested: float
    total_user_returns: float
    user_investment_roi_percentage: float
    asset_allocation: Dict[str, float]
    active_investments: int
    total_distributions: int
    estimated_annual_yield: float


class SIMPInvestmentRequest(BaseModel):
    """Schema for SIMP investment request"""
    intent_type: str = Field("crypto_investment", description="SIMP intent type")
    amount_usd: float = Field(..., ge=0.01, description="Amount to invest in USD")
    crypto_asset: str = Field(..., description="Target crypto asset")
    strategy: str = Field("dollar_cost_average", description="Investment strategy")
    risk_tolerance: str = Field("medium", description="Risk tolerance: low, medium, high")
    user_wallet: Optional[str] = Field(None, description="User's wallet address for returns")
    
    @validator('risk_tolerance')
    def validate_risk_tolerance(cls, v):
        allowed = ['low', 'medium', 'high']
        if v not in allowed:
            raise ValueError(f'Risk tolerance must be one of: {", ".join(allowed)}')
        return v


class SIMPInvestmentResponse(BaseModel):
    """Schema for SIMP investment response"""
    intent_id: str
    status: str
    trade_confirmation: bool
    transaction_hash: Optional[str]
    investment_details: Dict[str, Any]
    metadata: Dict[str, Any]


class WalletBalanceResponse(BaseModel):
    """Schema for wallet balance response"""
    wallet_address: str
    wallet_type: str
    balances: Dict[str, float]
    total_value_usd: float
    last_updated: datetime


# Export all schemas
__all__ = [
    "CryptoInvestmentBase",
    "CryptoInvestmentResponse",
    "UserInvestmentCreate",
    "UserInvestmentResponse",
    "AgentPortfolioResponse",
    "ReturnsDistributionResponse",
    "CryptoTradeResponse",
    "TipRequest",
    "InvestmentStatsResponse",
    "SIMPInvestmentRequest",
    "SIMPInvestmentResponse",
    "WalletBalanceResponse"
]