"""
Subscriptions API router for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionTier, Invoice, PromoCode, PromoCodeRedemption
from app.schemas.subscription import (
    SubscriptionTierResponse,
    SubscriptionResponse,
    SubscriptionCreate,
    SubscriptionUpdate,
    InvoiceResponse,
    PromoCodeRequest,
    PromoCodeResponse,
    BillingInfoResponse
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/tiers", response_model=List[SubscriptionTierResponse])
async def get_subscription_tiers(
    include_inactive: bool = Query(False, description="Include inactive tiers"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get available subscription tiers
    """
    query = select(SubscriptionTier)
    
    if not include_inactive:
        query = query.where(SubscriptionTier.is_active == True)
    
    query = query.where(SubscriptionTier.is_visible == True).order_by(SubscriptionTier.sort_order)
    
    result = await db.execute(query)
    tiers = result.scalars().all()
    
    return [SubscriptionTierResponse.from_orm(tier) for tier in tiers]


@router.get("/tiers/{tier_name}", response_model=SubscriptionTierResponse)
async def get_subscription_tier(
    tier_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get subscription tier by name
    """
    result = await db.execute(
        select(SubscriptionTier).where(
            and_(
                SubscriptionTier.name == tier_name,
                SubscriptionTier.is_active == True,
                SubscriptionTier.is_visible == True
            )
        )
    )
    tier = result.scalar_one_or_none()
    
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription tier not found"
        )
    
    return SubscriptionTierResponse.from_orm(tier)


@router.get("/my", response_model=SubscriptionResponse)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's subscription
    """
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status == "active"
            )
        )
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        # Return free tier subscription
        return SubscriptionResponse(
            id=uuid.uuid4(),
            user_id=current_user.id,
            tier_id=uuid.uuid4(),
            status="active",
            billing_cycle="monthly",
            price_usd=0.0,
            currency="USD",
            start_date=current_user.created_at,
            current_period_start=current_user.created_at,
            current_period_end=datetime.utcnow() + timedelta(days=365 * 10),  # Far future
            auto_renew=False,
            tier=SubscriptionTierResponse(
                id=uuid.uuid4(),
                name="free",
                display_name="Free",
                description="Basic free tier",
                price_monthly_usd=0.0,
                price_yearly_usd=0.0,
                billing_cycle="monthly",
                features=["basic_price_comparison", "manual_purchasing"],
                limits={},
                user_share_percentage=0.0,
                transaction_fee_percentage=0.02,
                is_active=True,
                is_visible=True,
                sort_order=0,
                trial_days=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
    
    # Get tier details
    result = await db.execute(
        select(SubscriptionTier).where(SubscriptionTier.id == subscription.tier_id)
    )
    tier = result.scalar_one_or_none()
    
    subscription.tier = tier
    return SubscriptionResponse.from_orm(subscription)


@router.post("/subscribe", response_model=SubscriptionResponse)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new subscription
    """
    # Get tier
    result = await db.execute(
        select(SubscriptionTier).where(
            and_(
                SubscriptionTier.name == subscription_data.tier_name,
                SubscriptionTier.is_active == True
            )
        )
    )
    tier = result.scalar_one_or_none()
    
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription tier not found"
        )
    
    # Check if user already has active subscription
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status == "active"
            )
        )
    )
    existing_subscription = result.scalar_one_or_none()
    
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active subscription"
        )
    
    # Validate promo code if provided
    promo_discount = 0.0
    if subscription_data.promo_code:
        result = await db.execute(
            select(PromoCode).where(
                and_(
                    PromoCode.code == subscription_data.promo_code,
                    PromoCode.is_active == True
                )
            )
        )
        promo = result.scalar_one_or_none()
        
        if not promo or not promo.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired promo code"
            )
        
        # Check if user has already used this promo
        result = await db.execute(
            select(PromoCodeRedemption).where(
                and_(
                    PromoCodeRedemption.promo_code_id == promo.id,
                    PromoCodeRedemption.user_id == current_user.id
                )
            )
        )
        existing_redemption = result.scalar_one_or_none()
        
        if existing_redemption:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already used this promo code"
            )
        
        # Calculate discount
        if promo.discount_type == "percentage":
            promo_discount = (tier.price_monthly_usd * promo.discount_value) / 100
        else:
            promo_discount = promo.discount_value
        
        # Ensure discount doesn't exceed price
        promo_discount = min(promo_discount, tier.price_monthly_usd)
    
    # Calculate price
    price = tier.price_monthly_usd - promo_discount
    
    # Determine billing dates
    now = datetime.utcnow()
    start_date = now
    
    # Trial period
    trial_end = None
    if tier.trial_days > 0:
        trial_end = now + timedelta(days=tier.trial_days)
    
    # Billing period
    if subscription_data.billing_cycle == "yearly" and tier.price_yearly_usd:
        price = tier.price_yearly_usd - promo_discount
        period_end = now + timedelta(days=365)
    else:
        period_end = now + timedelta(days=30)
    
    # Create subscription
    subscription = Subscription(
        user_id=current_user.id,
        tier_id=tier.id,
        status="active",
        billing_cycle=subscription_data.billing_cycle,
        price_usd=price,
        start_date=start_date,
        current_period_start=start_date,
        current_period_end=period_end,
        trial_start=start_date if tier.trial_days > 0 else None,
        trial_end=trial_end,
        auto_renew=True,
        payment_method_id=subscription_data.payment_method_id
    )
    
    db.add(subscription)
    
    # Create invoice
    invoice = Invoice(
        subscription_id=subscription.id,
        user_id=current_user.id,
        invoice_number=f"INV-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        amount_usd=price,
        total_amount=price,
        period_start=start_date,
        period_end=period_end,
        status="draft",
        payment_status="pending",
        payment_method_id=subscription_data.payment_method_id,
        due_date=period_end
    )
    
    db.add(invoice)
    
    # Record promo code redemption if used
    if subscription_data.promo_code and promo:
        redemption = PromoCodeRedemption(
            promo_code_id=promo.id,
            user_id=current_user.id,
            subscription_id=subscription.id,
            discount_applied=promo_discount,
            original_amount=tier.price_monthly_usd,
            final_amount=price
        )
        db.add(redemption)
        
        # Update promo code usage
        promo.current_uses += 1
    
    # Update user subscription tier
    current_user.subscription_tier = tier.name
    current_user.subscription_status = "active"
    current_user.subscription_start_date = start_date
    current_user.subscription_end_date = period_end
    
    await db.commit()
    await db.refresh(subscription)
    
    # In production, this would:
    # 1. Process payment with Stripe
    # 2. Create subscription in payment provider
    # 3. Send confirmation email
    
    subscription.tier = tier
    return SubscriptionResponse.from_orm(subscription)


@router.put("/my", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_data: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current subscription
    """
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status == "active"
            )
        )
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    
    # Handle tier upgrade/downgrade
    if subscription_data.tier_name:
        result = await db.execute(
            select(SubscriptionTier).where(
                and_(
                    SubscriptionTier.name == subscription_data.tier_name,
                    SubscriptionTier.is_active == True
                )
            )
        )
        new_tier = result.scalar_one_or_none()
        
        if not new_tier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription tier not found"
            )
        
        # Update subscription
        subscription.tier_id = new_tier.id
        
        # Update user
        current_user.subscription_tier = new_tier.name
    
    # Update other fields
    if subscription_data.auto_renew is not None:
        subscription.auto_renew = subscription_data.auto_renew
    
    if subscription_data.payment_method_id:
        subscription.payment_method_id = subscription_data.payment_method_id
    
    subscription.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(subscription)
    
    # Get tier details
    result = await db.execute(
        select(SubscriptionTier).where(SubscriptionTier.id == subscription.tier_id)
    )
    tier = result.scalar_one_or_none()
    
    subscription.tier = tier
    return SubscriptionResponse.from_orm(subscription)


@router.delete("/my")
async def cancel_subscription(
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel current subscription
    """
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status == "active"
            )
        )
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    
    # Cancel subscription
    subscription.status = "cancelled"
    subscription.cancelled_at = datetime.utcnow()
    subscription.auto_renew = False
    
    # Update user
    current_user.subscription_status = "cancelled"
    current_user.subscription_end_date = subscription.current_period_end
    
    await db.commit()
    
    return {
        "message": "Subscription cancelled successfully",
        "cancelled_at": subscription.cancelled_at,
        "active_until": subscription.current_period_end
    }


@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_invoices(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's subscription invoices
    """
    query = select(Invoice).where(Invoice.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Invoice.status == status_filter)
    
    query = query.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    invoices = result.scalars().all()
    
    return [InvoiceResponse.from_orm(invoice) for invoice in invoices]


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get invoice by ID
    """
    try:
        invoice_uuid = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID"
        )
    
    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.id == invoice_uuid,
                Invoice.user_id == current_user.id
            )
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return InvoiceResponse.from_orm(invoice)


@router.post("/promo/validate", response_model=PromoCodeResponse)
async def validate_promo_code(
    promo_request: PromoCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validate a promo code
    """
    result = await db.execute(
        select(PromoCode).where(
            and_(
                PromoCode.code == promo_request.code,
                PromoCode.is_active == True
            )
        )
    )
    promo = result.scalar_one_or_none()
    
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid promo code"
        )
    
    # Check validity
    if not promo.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promo code is no longer valid"
        )
    
    # Check if user has already used this promo
    result = await db.execute(
        select(PromoCodeRedemption).where(
            and_(
                PromoCodeRedemption.promo_code_id == promo.id,
                PromoCodeRedemption.user_id == current_user.id
            )
        )
    )
    existing_redemption = result.scalar_one_or_none()
    
    if existing_redemption:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already used this promo code"
        )
    
    # Check if promo applies to user's intended tier
    if promo.applies_to == "specific_tiers" and promo.applicable_tiers:
        if promo_request.tier_name not in promo.applicable_tiers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Promo code does not apply to this subscription tier"
            )
    
    # Check minimum requirements
    if promo.minimum_amount and promo_request.amount < promo.minimum_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Promo code requires minimum purchase of ${promo.minimum_amount}"
        )
    
    return PromoCodeResponse.from_orm(promo)


@router.get("/billing", response_model=BillingInfoResponse)
async def get_billing_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's billing information
    """
    # Get active subscription
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status == "active"
            )
        )
    )
    subscription = result.scalar_one_or_none()
    
    # Get recent invoices
    result = await db.execute(
        select(Invoice).where(
            Invoice.user_id == current_user.id
        ).order_by(Invoice.created_at.desc()).limit(5)
    )
    recent_invoices = result.scalars().all()
    
    # Get payment methods (would come from payments API)
    payment_methods = []  # In production, fetch from payments API
    
    return BillingInfoResponse(
        user_id=current_user.id,
        current_subscription=SubscriptionResponse.from_orm(subscription) if subscription else None,
        next_billing_date=subscription.current_period_end if subscription else None,
        days_until_billing=subscription.days_until_renewal if subscription else None,
        total_spent=0.0,  # Would calculate from invoices
        recent_invoices=[InvoiceResponse.from_orm(inv) for inv in recent_invoices],
        payment_methods=payment_methods,
        billing_address=None  # Would come from payment method
    )


@router.post("/webhook/stripe")
async def stripe_subscription_webhook(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe subscription webhook events
    """
    event_type = payload.get("type")
    event_data = payload.get("data", {}).get("object", {})
    
    print(f"Stripe subscription webhook: {event_type}")
    
    if event_type == "customer.subscription.created":
        # Subscription created
        stripe_subscription_id = event_data.get("id")
        customer_id = event_data.get("customer")
        
        # Would update local subscription record
    
    elif event_type == "customer.subscription.updated":
        # Subscription updated
        stripe_subscription_id = event_data.get("id")
        status = event_data.get("status")
        
        # Find and update subscription
        result = await db.execute(
            select(Subscription).where(
                Subscription.provider_subscription_id == stripe_subscription_id
            )
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = status
            subscription.updated_at = datetime.utcnow()
            await db.commit()
    
    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled
        stripe_subscription_id = event_data.get("id")
        
        result = await db.execute(
            select(Subscription).where(
                Subscription.provider_subscription_id == stripe_subscription_id
            )
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = "cancelled"
            subscription.cancelled_at = datetime.utcnow()
            subscription.ended_at = datetime.utcnow()
            await db.commit()
    
    elif event_type == "invoice.payment_succeeded":
        # Invoice paid
        invoice_id = event_data.get("id")
        subscription_id = event_data.get("subscription")
        
        # Find and update invoice
        result = await db.execute(
            select(Invoice).where(
                Invoice.provider_invoice_id == invoice_id
            )
        )
        invoice = result.scalar_one_or_none()
        
        if invoice:
            invoice.status = "paid"
            invoice.payment_status = "paid"
            invoice.paid_at = datetime.utcnow()
            await db.commit()
    
    return {"received": True}