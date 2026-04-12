"""
Crypto investment models for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CryptoInvestment(Base):
    """Crypto investment from purchase savings"""
    
    __tablename__ = "crypto_investments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_id = Column(UUID(as_uuid=True), ForeignKey("purchases.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Investment details
    investment_type = Column(String(50), default="savings")  # savings, tip, subscription_fee
    amount_usd = Column(Float, nullable=False)
    crypto_amount = Column(Float, nullable=False)  # Amount in crypto
    crypto_asset = Column(String(10), nullable=False)  # BTC, ETH, SOL, etc.
    exchange_rate = Column(Float, nullable=False)  # USD to crypto rate at time of investment
    
    # Trading details
    exchange = Column(String(50), nullable=True)  # coinbase, binance, kraken
    trading_strategy = Column(String(50), default="dollar_cost_average")  # dca, arbitrage, yield_farming
    transaction_hash = Column(String(100), nullable=True)  # Blockchain transaction hash
    wallet_address = Column(String(255), nullable=True)  # Destination wallet
    
    # Status
    status = Column(String(20), default="pending")  # pending, executing, completed, failed
    execution_status = Column(JSON, nullable=True)  # Detailed execution status
    
    # Returns tracking
    current_value_usd = Column(Float, nullable=True)
    profit_loss_usd = Column(Float, default=0.0)
    profit_loss_percentage = Column(Float, nullable=True)
    
    # Risk management
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    risk_level = Column(String(20), default="medium")  # low, medium, high
    
    # SIMP integration
    simp_intent_id = Column(String(100), nullable=True)  # SIMP intent ID for tracking
    simp_agent = Column(String(50), nullable=True)  # quantumarb, trading_organ, etc.
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    purchase = relationship("Purchase", back_populates="crypto_investment")
    user = relationship("User")
    returns_distributions = relationship("ReturnsDistribution", back_populates="investment", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CryptoInvestment(id={self.id}, amount={self.amount_usd}, asset={self.crypto_asset})>"
    
    @property
    def current_exchange_rate(self) -> Optional[float]:
        """Calculate current exchange rate based on current value"""
        if self.current_value_usd and self.crypto_amount > 0:
            return self.current_value_usd / self.crypto_amount
        return None
    
    @property
    def is_profitable(self) -> bool:
        """Check if investment is currently profitable"""
        return self.profit_loss_usd > 0 if self.profit_loss_usd else False
    
    @property
    def holding_period_days(self) -> Optional[int]:
        """Calculate holding period in days"""
        if self.executed_at:
            delta = datetime.utcnow() - self.executed_at
            return delta.days
        return None


class UserInvestment(Base):
    """User investment in agent's crypto trading (from tips/subscriptions)"""
    
    __tablename__ = "user_investments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Investment details
    investment_type = Column(String(20), nullable=False)  # tip, subscription
    amount_usd = Column(Float, nullable=False)
    share_percentage = Column(Float, nullable=False)  # Percentage of agent returns user gets
    subscription_tier = Column(String(20), nullable=True)  # For subscription investments
    
    # Returns tracking
    total_returns_usd = Column(Float, default=0.0)
    pending_returns_usd = Column(Float, default=0.0)  # Returns not yet distributed
    last_distribution_date = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(20), default="active")  # active, paused, cancelled, completed
    auto_reinvest = Column(Boolean, default=True)  # Automatically reinvest returns
    
    # Investment period
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)  # Null for ongoing investments
    
    # Performance
    annualized_return = Column(Float, nullable=True)
    total_return_percentage = Column(Float, nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="investments")
    returns_distributions = relationship("ReturnsDistribution", back_populates="user_investment", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<UserInvestment(id={self.id}, user={self.user_id}, amount={self.amount_usd})>"
    
    @property
    def is_active(self) -> bool:
        """Check if investment is active"""
        return self.status == "active" and (self.end_date is None or self.end_date > datetime.utcnow())
    
    @property
    def investment_duration_days(self) -> int:
        """Calculate investment duration in days"""
        delta = datetime.utcnow() - self.start_date
        return delta.days


class AgentPortfolio(Base):
    """Agent's overall crypto portfolio"""
    
    __tablename__ = "agent_portfolio"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Portfolio totals
    total_assets_usd = Column(Float, default=0.0)
    total_invested_usd = Column(Float, default=0.0)
    total_returns_usd = Column(Float, default=0.0)
    
    # Asset breakdown
    crypto_breakdown = Column(JSON, default={})  # { "BTC": 0.5, "ETH": 2.1, "SOL": 50.0 }
    asset_allocation = Column(JSON, default={})  # Percentage allocation per asset
    
    # Performance metrics
    daily_return_usd = Column(Float, default=0.0)
    daily_return_percentage = Column(Float, default=0.0)
    weekly_return_usd = Column(Float, default=0.0)
    weekly_return_percentage = Column(Float, default=0.0)
    monthly_return_usd = Column(Float, default=0.0)
    monthly_return_percentage = Column(Float, default=0.0)
    annual_return_usd = Column(Float, default=0.0)
    annual_return_percentage = Column(Float, default=0.0)
    
    # Risk metrics
    volatility = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    
    # Trading activity
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # User funds
    total_user_funds_usd = Column(Float, default=0.0)  # Total from tips and subscriptions
    total_distributed_returns_usd = Column(Float, default=0.0)  # Returns distributed to users
    platform_fees_usd = Column(Float, default=0.0)  # Platform's share of returns
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    snapshot_date = Column(DateTime, nullable=False, index=True)  # Date of this snapshot
    
    def __repr__(self):
        return f"<AgentPortfolio(id={self.id}, total_assets={self.total_assets_usd}, date={self.snapshot_date})>"
    
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


class ReturnsDistribution(Base):
    """Distribution of returns to users"""
    
    __tablename__ = "returns_distributions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investment_id = Column(UUID(as_uuid=True), ForeignKey("crypto_investments.id"), nullable=True, index=True)
    user_investment_id = Column(UUID(as_uuid=True), ForeignKey("user_investments.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Distribution details
    distribution_type = Column(String(50), nullable=False)  # savings_investment, tip_return, subscription_return
    amount_usd = Column(Float, nullable=False)
    crypto_amount = Column(Float, nullable=True)
    crypto_asset = Column(String(10), nullable=True)
    
    # Payment method
    payment_method = Column(String(50), default="crypto_wallet")  # crypto_wallet, bank_transfer, platform_credit
    wallet_address = Column(String(255), nullable=True)
    transaction_hash = Column(String(100), nullable=True)
    
    # Status
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    failure_reason = Column(Text, nullable=True)
    
    # Period covered
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    distributed_at = Column(DateTime, nullable=True)
    
    # Relationships
    investment = relationship("CryptoInvestment", back_populates="returns_distributions")
    user_investment = relationship("UserInvestment", back_populates="returns_distributions")
    user = relationship("User")
    
    def __repr__(self):
        return f"<ReturnsDistribution(id={self.id}, amount={self.amount_usd}, user={self.user_id})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if distribution is completed"""
        return self.status == "completed"


class CryptoTrade(Base):
    """Individual crypto trade"""
    
    __tablename__ = "crypto_trades"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investment_id = Column(UUID(as_uuid=True), ForeignKey("crypto_investments.id"), nullable=True, index=True)
    
    # Trade details
    trade_type = Column(String(10), nullable=False)  # buy, sell
    crypto_asset = Column(String(10), nullable=False)
    crypto_amount = Column(Float, nullable=False)
    usd_amount = Column(Float, nullable=False)
    price_per_unit = Column(Float, nullable=False)
    
    # Exchange details
    exchange = Column(String(50), nullable=False)
    exchange_order_id = Column(String(100), nullable=True)
    exchange_trade_id = Column(String(100), nullable=True)
    
    # Blockchain details
    transaction_hash = Column(String(100), nullable=True)
    block_number = Column(Integer, nullable=True)
    gas_fee = Column(Float, nullable=True)
    
    # Status
    status = Column(String(20), default="pending")  # pending, executing, filled, cancelled, failed
    fill_percentage = Column(Float, default=0.0)  # Percentage of order filled
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    
    # Relationships
    investment = relationship("CryptoInvestment")
    
    def __repr__(self):
        return f"<CryptoTrade(id={self.id}, type={self.trade_type}, asset={self.crypto_asset})>"
    
    @property
    def is_buy(self) -> bool:
        """Check if trade is a buy order"""
        return self.trade_type == "buy"
    
    @property
    def is_sell(self) -> bool:
        """Check if trade is a sell order"""
        return self.trade_type == "sell"