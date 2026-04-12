"""
Crypto API router for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.crypto import CryptoInvestment, UserInvestment, AgentPortfolio, ReturnsDistribution, CryptoTrade
from app.models.purchase import Purchase
from app.schemas.crypto import (
    CryptoInvestmentResponse,
    UserInvestmentCreate,
    UserInvestmentResponse,
    AgentPortfolioResponse,
    ReturnsDistributionResponse,
    CryptoTradeResponse,
    TipRequest,
    InvestmentStatsResponse
)

router = APIRouter(prefix="/crypto", tags=["crypto"])


@router.get("/investments", response_model=List[CryptoInvestmentResponse])
async def get_crypto_investments(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    asset_filter: Optional[str] = Query(None, description="Filter by crypto asset"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's crypto investments
    """
    query = select(CryptoInvestment).where(CryptoInvestment.user_id == current_user.id)
    
    if status_filter:
        query = query.where(CryptoInvestment.status == status_filter)
    
    if asset_filter:
        query = query.where(CryptoInvestment.crypto_asset == asset_filter.upper())
    
    query = query.order_by(desc(CryptoInvestment.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    investments = result.scalars().all()
    
    return [CryptoInvestmentResponse.from_orm(inv) for inv in investments]


@router.post("/investments/from-purchase/{purchase_id}", response_model=CryptoInvestmentResponse)
async def invest_purchase_savings(
    purchase_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invest savings from a purchase into crypto
    """
    try:
        purchase_uuid = uuid.UUID(purchase_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid purchase ID"
        )
    
    # Get purchase
    result = await db.execute(
        select(Purchase).where(
            and_(
                Purchase.id == purchase_uuid,
                Purchase.user_id == current_user.id
            )
        )
    )
    purchase = result.scalar_one_or_none()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    
    # Check if savings can be invested
    if not purchase.can_be_invested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase savings cannot be invested. Ensure purchase is completed and has savings."
        )
    
    # Check if already invested
    if purchase.change_invested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Savings from this purchase have already been invested"
        )
    
    from app.core.config import settings
    
    # Create crypto investment
    # In production, this would:
    # 1. Route to SIMP QuantumArb agent
    # 2. Execute crypto trade
    # 3. Record transaction
    
    investment = CryptoInvestment(
        purchase_id=purchase_uuid,
        user_id=current_user.id,
        investment_type="savings",
        amount_usd=purchase.savings_amount,
        crypto_asset=settings.DEFAULT_CRYPTO_ASSET,
        crypto_amount=purchase.savings_amount / 1666.67,  # Mock exchange rate
        exchange_rate=1666.67,
        exchange="coinbase",  # Mock
        trading_strategy="dollar_cost_average",
        transaction_hash=f"0x{uuid.uuid4().hex}",  # Mock
        status="completed",
        current_value_usd=purchase.savings_amount * 1.02,  # Mock 2% gain
        profit_loss_usd=purchase.savings_amount * 0.02,
        profit_loss_percentage=2.0,
        executed_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    
    # Update purchase
    purchase.change_invested = True
    purchase.investment_id = investment.id
    
    # Update user stats
    current_user.total_invested = (current_user.total_invested or 0) + purchase.savings_amount
    current_user.crypto_balance = (current_user.crypto_balance or 0) + investment.crypto_amount
    current_user.total_returns = (current_user.total_returns or 0) + investment.profit_loss_usd
    
    db.add(investment)
    await db.commit()
    await db.refresh(investment)
    
    return CryptoInvestmentResponse.from_orm(investment)


@router.post("/tip", response_model=UserInvestmentResponse)
async def tip_agent(
    tip_data: TipRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Tip the agent for a share of crypto returns
    """
    from app.core.config import settings
    
    # Check user subscription tier for tip limits
    tier_config = settings.SUBSCRIPTION_TIERS.get(current_user.subscription_tier, {})
    user_share = tier_config.get("user_share", 0.0)
    
    if user_share == 0.0 and current_user.subscription_tier != "free":
        # User can't get returns from tips on their tier
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Your subscription tier ({current_user.subscription_tier}) does not support tip-based returns"
        )
    
    # Create user investment (tip)
    investment = UserInvestment(
        user_id=current_user.id,
        investment_type="tip",
        amount_usd=tip_data.amount,
        share_percentage=user_share,
        start_date=datetime.utcnow(),
        auto_reinvest=tip_data.auto_reinvest,
        status="active"
    )
    
    # In production, this would:
    # 1. Process payment for tip
    # 2. Add to agent's investment pool
    # 3. Update agent portfolio
    
    db.add(investment)
    await db.commit()
    await db.refresh(investment)
    
    return UserInvestmentResponse.from_orm(investment)


@router.get("/my-investments", response_model=List[UserInvestmentResponse])
async def get_user_investments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's investments in agent's crypto trading
    """
    result = await db.execute(
        select(UserInvestment).where(
            UserInvestment.user_id == current_user.id
        ).order_by(desc(UserInvestment.created_at))
    )
    investments = result.scalars().all()
    
    return [UserInvestmentResponse.from_orm(inv) for inv in investments]


@router.get("/agent/portfolio", response_model=AgentPortfolioResponse)
async def get_agent_portfolio(
    timeframe: str = Query("daily", description="Timeframe: daily, weekly, monthly"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get agent's crypto portfolio performance
    """
    # Get latest portfolio snapshot
    result = await db.execute(
        select(AgentPortfolio).order_by(desc(AgentPortfolio.snapshot_date)).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    
    if not portfolio:
        # Create mock portfolio if none exists
        portfolio = AgentPortfolio(
            total_assets_usd=100000.0,
            total_invested_usd=85000.0,
            total_returns_usd=15000.0,
            crypto_breakdown={"BTC": 0.5, "ETH": 2.1, "SOL": 50.0},
            asset_allocation={"BTC": 40.0, "ETH": 35.0, "SOL": 25.0},
            daily_return_usd=250.0,
            daily_return_percentage=0.25,
            weekly_return_usd=1750.0,
            weekly_return_percentage=1.75,
            monthly_return_usd=7500.0,
            monthly_return_percentage=7.5,
            annual_return_usd=15000.0,
            annual_return_percentage=15.0,
            total_trades=1250,
            winning_trades=850,
            losing_trades=400,
            win_rate=68.0,
            total_user_funds_usd=25000.0,
            total_distributed_returns_usd=5000.0,
            platform_fees_usd=3000.0,
            snapshot_date=datetime.utcnow()
        )
    
    return AgentPortfolioResponse.from_orm(portfolio)


@router.get("/returns/distributions", response_model=List[ReturnsDistributionResponse])
async def get_returns_distributions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's returns distributions
    """
    result = await db.execute(
        select(ReturnsDistribution).where(
            ReturnsDistribution.user_id == current_user.id
        ).order_by(desc(ReturnsDistribution.created_at))
    )
    distributions = result.scalars().all()
    
    return [ReturnsDistributionResponse.from_orm(dist) for dist in distributions]


@router.get("/stats", response_model=InvestmentStatsResponse)
async def get_investment_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's investment statistics
    """
    # Get crypto investments
    result = await db.execute(
        select(CryptoInvestment).where(
            CryptoInvestment.user_id == current_user.id
        )
    )
    crypto_investments = result.scalars().all()
    
    # Get user investments
    result = await db.execute(
        select(UserInvestment).where(
            UserInvestment.user_id == current_user.id
        )
    )
    user_investments = result.scalars().all()
    
    # Calculate stats
    total_crypto_invested = sum(inv.amount_usd for inv in crypto_investments)
    total_crypto_returns = sum(inv.profit_loss_usd for inv in crypto_investments if inv.profit_loss_usd)
    total_user_invested = sum(inv.amount_usd for inv in user_investments)
    total_user_returns = sum(inv.total_returns_usd for inv in user_investments)
    
    # Calculate ROI
    crypto_roi = (total_crypto_returns / total_crypto_invested * 100) if total_crypto_invested > 0 else 0
    user_investment_roi = (total_user_returns / total_user_invested * 100) if total_user_invested > 0 else 0
    
    # Get asset allocation
    asset_allocation = {}
    for inv in crypto_investments:
        asset = inv.crypto_asset
        if asset not in asset_allocation:
            asset_allocation[asset] = 0
        asset_allocation[asset] += inv.amount_usd
    
    return InvestmentStatsResponse(
        user_id=current_user.id,
        total_crypto_invested=total_crypto_invested,
        total_crypto_returns=total_crypto_returns,
        crypto_roi_percentage=crypto_roi,
        total_user_invested=total_user_invested,
        total_user_returns=total_user_returns,
        user_investment_roi_percentage=user_investment_roi,
        asset_allocation=asset_allocation,
        active_investments=len([inv for inv in crypto_investments if inv.status == "active"]),
        total_distributions=len([dist for dist in await get_returns_distributions(current_user, db)]),
        estimated_annual_yield=8.5  # Mock
    )


@router.post("/reinvest/{investment_id}")
async def reinvest_returns(
    investment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reinvest returns from an investment
    """
    try:
        investment_uuid = uuid.UUID(investment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid investment ID"
        )
    
    result = await db.execute(
        select(UserInvestment).where(
            and_(
                UserInvestment.id == investment_uuid,
                UserInvestment.user_id == current_user.id
            )
        )
    )
    investment = result.scalar_one_or_none()
    
    if not investment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment not found"
        )
    
    # Toggle auto-reinvest
    investment.auto_reinvest = not investment.auto_reinvest
    investment.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "message": f"Auto-reinvest {'enabled' if investment.auto_reinvest else 'disabled'}",
        "investment_id": investment_id,
        "auto_reinvest": investment.auto_reinvest
    }


@router.post("/withdraw/{distribution_id}")
async def withdraw_returns(
    distribution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Withdraw returns distribution to connected wallet
    """
    try:
        distribution_uuid = uuid.UUID(distribution_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid distribution ID"
        )
    
    result = await db.execute(
        select(ReturnsDistribution).where(
            and_(
                ReturnsDistribution.id == distribution_uuid,
                ReturnsDistribution.user_id == current_user.id
            )
        )
    )
    distribution = result.scalar_one_or_none()
    
    if not distribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Distribution not found"
        )
    
    if distribution.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Distribution is not available for withdrawal"
        )
    
    # Check if user has wallet connected
    if not current_user.crypto_wallet_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please connect a crypto wallet first"
        )
    
    # Update distribution with wallet info
    distribution.wallet_address = current_user.crypto_wallet_address
    distribution.payment_method = "crypto_wallet"
    distribution.status = "processing"
    distribution.updated_at = datetime.utcnow()
    
    # In production, this would:
    # 1. Initiate blockchain transaction
    # 2. Update distribution with transaction hash
    # 3. Mark as completed when confirmed
    
    await db.commit()
    
    return {
        "message": "Withdrawal initiated",
        "distribution_id": distribution_id,
        "amount": distribution.amount_usd,
        "wallet_address": current_user.crypto_wallet_address,
        "status": "processing"
    }


@router.get("/trades", response_model=List[CryptoTradeResponse])
async def get_crypto_trades(
    investment_id: Optional[str] = Query(None, description="Filter by investment ID"),
    asset_filter: Optional[str] = Query(None, description="Filter by crypto asset"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get crypto trades for user's investments
    """
    # Get user's investment IDs
    result = await db.execute(
        select(CryptoInvestment.id).where(CryptoInvestment.user_id == current_user.id)
    )
    user_investment_ids = [str(inv_id[0]) for inv_id in result.all()]
    
    if not user_investment_ids:
        return []
    
    # Build query
    query = select(CryptoTrade).where(CryptoTrade.investment_id.in_(user_investment_ids))
    
    if asset_filter:
        query = query.where(CryptoTrade.crypto_asset == asset_filter.upper())
    
    query = query.order_by(desc(CryptoTrade.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    trades = result.scalars().all()
    
    return [CryptoTradeResponse.from_orm(trade) for trade in trades]