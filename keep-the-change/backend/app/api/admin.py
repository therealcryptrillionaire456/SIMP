"""
Admin API router for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserAuditLog
from app.models.shopping import ShoppingList, Purchase
from app.models.crypto import CryptoInvestment, AgentPortfolio
from app.models.subscription import Subscription, Invoice
from app.schemas.admin import (
    AdminUserResponse,
    AdminStatsResponse,
    SystemHealthResponse,
    AuditLogResponse,
    FinancialReportResponse
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def verify_admin(user: User = Depends(get_current_user)):
    """Verify user is admin"""
    if user.subscription_tier != "elite" and user.email != "admin@keepthechange.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get admin dashboard statistics
    """
    # User statistics
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar()
    
    result = await db.execute(
        select(func.count(User.id)).where(User.subscription_tier != "free")
    )
    premium_users = result.scalar()
    
    result = await db.execute(
        select(func.count(User.id)).where(
            User.created_at >= datetime.utcnow() - timedelta(days=30)
        )
    )
    new_users_30d = result.scalar()
    
    # Financial statistics
    result = await db.execute(
        select(func.sum(Purchase.total_amount)).where(
            Purchase.payment_status == "completed"
        )
    )
    total_revenue = result.scalar() or 0.0
    
    result = await db.execute(
        select(func.sum(Purchase.savings_amount)).where(
            Purchase.payment_status == "completed"
        )
    )
    total_savings = result.scalar() or 0.0
    
    # Subscription statistics
    result = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == "active")
    )
    active_subscriptions = result.scalar()
    
    result = await db.execute(
        select(func.sum(Subscription.price_usd)).where(
            and_(
                Subscription.status == "active",
                Subscription.current_period_end > datetime.utcnow()
            )
        )
    )
    mrr = result.scalar() or 0.0
    
    # Crypto statistics
    result = await db.execute(
        select(func.sum(CryptoInvestment.amount_usd))
    )
    total_crypto_invested = result.scalar() or 0.0
    
    result = await db.execute(
        select(func.sum(CryptoInvestment.profit_loss_usd))
    )
    total_crypto_returns = result.scalar() or 0.0
    
    # Get latest agent portfolio
    result = await db.execute(
        select(AgentPortfolio).order_by(desc(AgentPortfolio.snapshot_date)).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    
    return AdminStatsResponse(
        users={
            "total": total_users,
            "premium": premium_users,
            "new_30d": new_users_30d,
            "free": total_users - premium_users
        },
        financial={
            "total_revenue": total_revenue,
            "total_savings": total_savings,
            "average_order_value": total_revenue / max(1, total_users),
            "mrr": mrr,
            "arr": mrr * 12
        },
        crypto={
            "total_invested": total_crypto_invested,
            "total_returns": total_crypto_returns,
            "roi_percentage": (total_crypto_returns / total_crypto_invested * 100) if total_crypto_invested > 0 else 0,
            "agent_assets": portfolio.total_assets_usd if portfolio else 0.0,
            "user_funds": portfolio.total_user_funds_usd if portfolio else 0.0
        },
        subscriptions={
            "total_active": active_subscriptions,
            "tier_breakdown": {
                "basic": 0,  # Would calculate from database
                "pro": 0,
                "elite": 0
            },
            "churn_rate": 2.5,  # Mock
            "lifetime_value": 274.56  # Mock from business plan
        }
    )


@router.get("/users", response_model=List[AdminUserResponse])
async def get_admin_users(
    search: Optional[str] = Query(None, description="Search by email or name"),
    tier_filter: Optional[str] = Query(None, description="Filter by subscription tier"),
    status_filter: Optional[str] = Query(None, description="Filter by account status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get users with admin view
    """
    query = select(User)
    
    if search:
        query = query.where(
            (User.email.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%"))
        )
    
    if tier_filter:
        query = query.where(User.subscription_tier == tier_filter)
    
    if status_filter == "active":
        query = query.where(User.deleted_at == None)
    elif status_filter == "inactive":
        query = query.where(User.deleted_at != None)
    
    query = query.order_by(desc(User.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [AdminUserResponse.from_orm(user) for user in users]


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_admin_user(
    user_id: str,
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user details with admin view
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return AdminUserResponse.from_orm(user)


@router.put("/users/{user_id}")
async def update_admin_user(
    user_id: str,
    user_data: Dict[str, Any] = Body(...),
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user with admin privileges
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update allowed fields
    allowed_fields = [
        "subscription_tier",
        "subscription_status",
        "email_verified",
        "account_locked_until",
        "failed_login_attempts"
    ]
    
    for field, value in user_data.items():
        if field in allowed_fields and hasattr(user, field):
            setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=user.id,
        action="admin_update",
        resource_type="user",
        resource_id=str(user.id),
        details={
            "admin_id": str(admin.id),
            "admin_email": admin.email,
            "updated_fields": list(user_data.keys())
        }
    )
    db.add(audit_log)
    
    await db.commit()
    
    return {
        "success": True,
        "user_id": user_id,
        "updated_fields": list(user_data.keys()),
        "message": "User updated successfully"
    }


@router.get("/audit/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system audit logs
    """
    query = select(UserAuditLog)
    
    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
            query = query.where(UserAuditLog.user_id == user_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )
    
    if action:
        query = query.where(UserAuditLog.action == action)
    
    if start_date:
        query = query.where(UserAuditLog.created_at >= start_date)
    
    if end_date:
        query = query.where(UserAuditLog.created_at <= end_date)
    
    query = query.order_by(desc(UserAuditLog.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [AuditLogResponse.from_orm(log) for log in logs]


@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system health status
    """
    # Check database connection
    db_healthy = True
    try:
        result = await db.execute(select(1))
        result.scalar()
    except Exception:
        db_healthy = False
    
    # Check recent errors (would come from error logs)
    recent_errors = 0  # Would query error logs
    
    # Get system metrics
    from app.core.config import settings
    
    return SystemHealthResponse(
        status="healthy" if db_healthy else "degraded",
        timestamp=datetime.utcnow(),
        components={
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "connection": "connected" if db_healthy else "disconnected",
                "url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local"
            },
            "api": {
                "status": "healthy",
                "uptime": "100%",  # Would calculate
                "response_time": "125ms"  # Would measure
            },
            "payment_processor": {
                "status": "healthy" if settings.STRIPE_SECRET_KEY else "disabled",
                "provider": "stripe" if settings.STRIPE_SECRET_KEY else "none"
            },
            "crypto_trading": {
                "status": "healthy" if settings.CRYPTO_TRADING_ENABLED else "disabled",
                "exchanges": ["coinbase", "binance"] if settings.CRYPTO_TRADING_ENABLED else []
            }
        },
        metrics={
            "active_users_24h": 0,  # Would calculate
            "api_requests_24h": 0,
            "error_rate_24h": recent_errors / max(1, 1000),  # Mock
            "average_response_time": 125,
            "database_connections": 5  # Mock
        },
        alerts=[]
    )


@router.get("/financial/report", response_model=FinancialReportResponse)
async def get_financial_report(
    period: str = Query("monthly", description="Report period: daily, weekly, monthly, yearly"),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get financial report
    """
    # Set date range
    now = datetime.utcnow()
    if not start_date or not end_date:
        if period == "daily":
            start_date = now - timedelta(days=1)
            end_date = now
        elif period == "weekly":
            start_date = now - timedelta(days=7)
            end_date = now
        elif period == "monthly":
            start_date = now - timedelta(days=30)
            end_date = now
        else:  # yearly
            start_date = now - timedelta(days=365)
            end_date = now
    
    # Get revenue data
    result = await db.execute(
        select(
            func.date_trunc('day', Purchase.created_at).label('date'),
            func.sum(Purchase.total_amount).label('revenue'),
            func.sum(Purchase.savings_amount).label('savings'),
            func.count(Purchase.id).label('transactions')
        ).where(
            and_(
                Purchase.created_at >= start_date,
                Purchase.created_at <= end_date,
                Purchase.payment_status == "completed"
            )
        ).group_by(func.date_trunc('day', Purchase.created_at))
        .order_by(func.date_trunc('day', Purchase.created_at))
    )
    daily_data = result.all()
    
    # Get subscription revenue
    result = await db.execute(
        select(
            func.sum(Invoice.total_amount).label('subscription_revenue')
        ).where(
            and_(
                Invoice.created_at >= start_date,
                Invoice.created_at <= end_date,
                Invoice.payment_status == "paid"
            )
        )
    )
    subscription_revenue = result.scalar() or 0.0
    
    # Get crypto returns
    result = await db.execute(
        select(
            func.sum(CryptoInvestment.profit_loss_usd).label('crypto_returns')
        ).where(
            and_(
                CryptoInvestment.created_at >= start_date,
                CryptoInvestment.created_at <= end_date,
                CryptoInvestment.status == "completed"
            )
        )
    )
    crypto_returns = result.scalar() or 0.0
    
    # Calculate totals
    total_revenue = sum(row.revenue or 0 for row in daily_data) + subscription_revenue
    total_savings = sum(row.savings or 0 for row in daily_data)
    total_transactions = sum(row.transactions or 0 for row in daily_data)
    
    # Calculate averages
    avg_order_value = total_revenue / max(1, total_transactions)
    avg_savings_per_order = total_savings / max(1, total_transactions)
    
    return FinancialReportResponse(
        period=period,
        start_date=start_date,
        end_date=end_date,
        summary={
            "total_revenue": total_revenue,
            "subscription_revenue": subscription_revenue,
            "transaction_revenue": total_revenue - subscription_revenue,
            "total_savings": total_savings,
            "crypto_returns": crypto_returns,
            "total_transactions": total_transactions,
            "average_order_value": avg_order_value,
            "average_savings_per_order": avg_savings_per_order,
            "savings_rate": (total_savings / total_revenue * 100) if total_revenue > 0 else 0
        },
        daily_data=[
            {
                "date": row.date,
                "revenue": row.revenue or 0,
                "savings": row.savings or 0,
                "transactions": row.transactions or 0
            }
            for row in daily_data
        ],
        recommendations=[
            "Consider promoting premium tiers during checkout",
            "Optimize price comparison for higher savings rates",
            "Expand crypto investment options for users"
        ]
    )


@router.get("/subscriptions/analytics")
async def get_subscription_analytics(
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get subscription analytics
    """
    # Get subscription counts by tier
    result = await db.execute(
        select(
            SubscriptionTier.name,
            func.count(Subscription.id).label('count')
        ).join(
            SubscriptionTier, Subscription.tier_id == SubscriptionTier.id
        ).where(
            Subscription.status == "active"
        ).group_by(SubscriptionTier.name)
    )
    tier_counts = {row.name: row.count for row in result.all()}
    
    # Get churn rate (mock)
    churn_rate = 2.5
    
    # Get MRR growth
    result = await db.execute(
        select(
            func.date_trunc('month', Subscription.start_date).label('month'),
            func.sum(Subscription.price_usd).label('mrr')
        ).where(
            Subscription.status == "active"
        ).group_by(func.date_trunc('month', Subscription.start_date))
        .order_by(func.date_trunc('month', Subscription.start_date).desc())
        .limit(6)
    )
    mrr_history = [
        {"month": row.month, "mrr": row.mrr or 0}
        for row in result.all()
    ]
    
    return {
        "tier_distribution": tier_counts,
        "total_active": sum(tier_counts.values()),
        "churn_rate": churn_rate,
        "mrr_history": mrr_history,
        "lifetime_value": 274.56,  # Mock
        "acquisition_cost": 82.37  # Mock from business plan
    }


@router.post("/system/maintenance")
async def system_maintenance(
    action: str = Query(..., description="Maintenance action: backup, cleanup, restart"),
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Perform system maintenance actions
    """
    if action == "backup":
        # In production, this would:
        # 1. Create database backup
        # 2. Upload to cloud storage
        # 3. Log backup details
        
        backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "success": True,
            "action": "backup",
            "backup_id": backup_id,
            "message": "System backup initiated",
            "estimated_completion": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        }
    
    elif action == "cleanup":
        # Clean up old data
        # In production, this would archive old records
        
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        return {
            "success": True,
            "action": "cleanup",
            "cutoff_date": cutoff_date.isoformat(),
            "message": "Data cleanup scheduled",
            "estimated_records_affected": 0  # Would calculate
        }
    
    elif action == "restart":
        # In production, this would restart services
        
        return {
            "success": True,
            "action": "restart",
            "message": "System restart scheduled",
            "restart_time": (datetime.utcnow() + timedelta(minutes=1)).isoformat(),
            "warning": "Service will be temporarily unavailable"
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid maintenance action: {action}"
        )


@router.get("/alerts")
async def get_system_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical"),
    resolved: bool = Query(False, description="Show resolved alerts"),
    admin: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system alerts
    """
    # Mock alerts
    # In production, these would come from monitoring system
    
    alerts = [
        {
            "id": str(uuid.uuid4()),
            "title": "High Error Rate",
            "description": "API error rate exceeded 5% threshold",
            "severity": "warning",
            "component": "api",
            "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "resolved": False,
            "resolution_time": None
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Database Connection Spike",
            "description": "Unusual increase in database connections",
            "severity": "info",
            "component": "database",
            "created_at": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
            "resolved": True,
            "resolution_time": (datetime.utcnow() - timedelta(hours=5)).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Payment Processor Latency",
            "description": "Stripe API response time increased by 200%",
            "severity": "critical",
            "component": "payment_processor",
            "created_at": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
            "resolved": False,
            "resolution_time": None
        }
    ]
    
    if severity:
        alerts = [alert for alert in alerts if alert["severity"] == severity]
    
    if not resolved:
        alerts = [alert for alert in alerts if not alert["resolved"]]
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "critical_count": len([a for a in alerts if a["severity"] == "critical"]),
        "unresolved_count": len([a for a in alerts if not a["resolved"]])
    }


# Import SubscriptionTier for analytics
from app.models.subscription import SubscriptionTier