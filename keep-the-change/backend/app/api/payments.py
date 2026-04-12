"""
Payments API router for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.payment import PaymentMethod, Purchase, Refund
from app.schemas.payment import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
    PaymentMethodResponse,
    PurchaseResponse,
    RefundRequest,
    RefundResponse
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/methods", response_model=List[PaymentMethodResponse])
async def get_payment_methods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's payment methods
    """
    result = await db.execute(
        select(PaymentMethod).where(
            and_(
                PaymentMethod.user_id == current_user.id,
                PaymentMethod.is_active == True
            )
        ).order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
    )
    methods = result.scalars().all()
    
    return [PaymentMethodResponse.from_orm(method) for method in methods]


@router.post("/methods", response_model=PaymentMethodResponse, status_code=status.HTTP_201_CREATED)
async def add_payment_method(
    method_data: PaymentMethodCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new payment method
    
    In production, this would integrate with Stripe/PayPal to tokenize payment info
    """
    # In production, you would:
    # 1. Validate payment details with Stripe/PayPal
    # 2. Create payment method token
    # 3. Store token securely
    
    # For now, create mock payment method
    payment_method = PaymentMethod(
        user_id=current_user.id,
        provider=method_data.provider,
        provider_payment_method_id=f"pm_{uuid.uuid4().hex[:24]}",
        payment_type=method_data.payment_type,
        card_brand=method_data.card_brand,
        card_last4=method_data.card_last4,
        card_exp_month=method_data.card_exp_month,
        card_exp_year=method_data.card_exp_year,
        billing_address=method_data.billing_address,
        is_default=method_data.is_default or False,
        is_verified=True  # Mock verification
    )
    
    # If this is set as default, unset other defaults
    if payment_method.is_default:
        result = await db.execute(
            select(PaymentMethod).where(
                and_(
                    PaymentMethod.user_id == current_user.id,
                    PaymentMethod.is_default == True,
                    PaymentMethod.is_active == True
                )
            )
        )
        existing_defaults = result.scalars().all()
        
        for default_method in existing_defaults:
            default_method.is_default = False
    
    db.add(payment_method)
    await db.commit()
    await db.refresh(payment_method)
    
    return PaymentMethodResponse.from_orm(payment_method)


@router.put("/methods/{method_id}", response_model=PaymentMethodResponse)
async def update_payment_method(
    method_id: str,
    method_data: PaymentMethodUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update payment method
    """
    try:
        method_uuid = uuid.UUID(method_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment method ID"
        )
    
    result = await db.execute(
        select(PaymentMethod).where(
            and_(
                PaymentMethod.id == method_uuid,
                PaymentMethod.user_id == current_user.id
            )
        )
    )
    payment_method = result.scalar_one_or_none()
    
    if not payment_method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Update fields
    update_data = method_data.dict(exclude_unset=True)
    
    # Handle setting as default
    if update_data.get("is_default") and not payment_method.is_default:
        # Unset other defaults
        result = await db.execute(
            select(PaymentMethod).where(
                and_(
                    PaymentMethod.user_id == current_user.id,
                    PaymentMethod.is_default == True,
                    PaymentMethod.is_active == True,
                    PaymentMethod.id != method_uuid
                )
            )
        )
        existing_defaults = result.scalars().all()
        
        for default_method in existing_defaults:
            default_method.is_default = False
    
    for field, value in update_data.items():
        if hasattr(payment_method, field):
            setattr(payment_method, field, value)
    
    payment_method.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(payment_method)
    
    return PaymentMethodResponse.from_orm(payment_method)


@router.delete("/methods/{method_id}")
async def delete_payment_method(
    method_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete payment method (soft delete)
    """
    try:
        method_uuid = uuid.UUID(method_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment method ID"
        )
    
    result = await db.execute(
        select(PaymentMethod).where(
            and_(
                PaymentMethod.id == method_uuid,
                PaymentMethod.user_id == current_user.id
            )
        )
    )
    payment_method = result.scalar_one_or_none()
    
    if not payment_method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Soft delete
    payment_method.is_active = False
    payment_method.updated_at = datetime.utcnow()
    
    # If this was the default, set another as default
    if payment_method.is_default:
        result = await db.execute(
            select(PaymentMethod).where(
                and_(
                    PaymentMethod.user_id == current_user.id,
                    PaymentMethod.is_active == True,
                    PaymentMethod.id != method_uuid
                )
            ).order_by(PaymentMethod.created_at.desc()).limit(1)
        )
        alternative = result.scalar_one_or_none()
        
        if alternative:
            alternative.is_default = True
    
    await db.commit()
    
    return {"message": "Payment method deleted successfully"}


@router.post("/methods/{method_id}/verify")
async def verify_payment_method(
    method_id: str,
    verification_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify payment method (for bank accounts, etc.)
    
    In production, this would integrate with Stripe/PayPal verification
    """
    try:
        method_uuid = uuid.UUID(method_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment method ID"
        )
    
    result = await db.execute(
        select(PaymentMethod).where(
            and_(
                PaymentMethod.id == method_uuid,
                PaymentMethod.user_id == current_user.id
            )
        )
    )
    payment_method = result.scalar_one_or_none()
    
    if not payment_method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Mock verification
    # In production, you would:
    # 1. Send micro-deposits for bank accounts
    # 2. Verify 3D Secure for cards
    # 3. Confirm with payment provider
    
    payment_method.is_verified = True
    payment_method.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "message": "Payment method verified successfully",
        "method_id": method_id,
        "verified": True
    }


@router.get("/purchases", response_model=List[PurchaseResponse])
async def get_payment_purchases(
    status_filter: Optional[str] = Query(None, description="Filter by payment status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's purchases with payment details
    """
    query = select(Purchase).where(Purchase.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Purchase.payment_status == status_filter)
    
    query = query.order_by(Purchase.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    purchases = result.scalars().all()
    
    return [PurchaseResponse.from_orm(purchase) for purchase in purchases]


@router.post("/purchases/{purchase_id}/refund", response_model=RefundResponse)
async def request_refund(
    purchase_id: str,
    refund_data: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Request refund for a purchase
    """
    try:
        purchase_uuid = uuid.UUID(purchase_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid purchase ID"
        )
    
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
    
    # Check if refund is possible
    if purchase.payment_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot refund purchase that hasn't been paid"
        )
    
    if purchase.status in ["cancelled", "refunded"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase has already been cancelled or refunded"
        )
    
    # Calculate refund amount
    refund_amount = refund_data.amount or purchase.total_amount
    
    if refund_amount > purchase.total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund amount cannot exceed purchase amount"
        )
    
    # Create refund record
    refund = Refund(
        purchase_id=purchase_uuid,
        refund_amount=refund_amount,
        refund_reason=refund_data.reason,
        refund_notes=refund_data.notes,
        status="pending"
    )
    
    # Update purchase status
    purchase.status = "refund_requested"
    purchase.updated_at = datetime.utcnow()
    
    db.add(refund)
    await db.commit()
    await db.refresh(refund)
    
    # In production, this would:
    # 1. Initiate refund with payment provider
    # 2. Notify customer service
    # 3. Process return shipping if applicable
    
    return RefundResponse.from_orm(refund)


@router.get("/balance")
async def get_payment_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's payment balance and transaction summary
    """
    # Get total spent
    result = await db.execute(
        select(sqlalchemy.func.sum(Purchase.total_amount)).where(
            and_(
                Purchase.user_id == current_user.id,
                Purchase.payment_status == "completed"
            )
        )
    )
    total_spent = result.scalar() or 0.0
    
    # Get total savings
    result = await db.execute(
        select(sqlalchemy.func.sum(Purchase.savings_amount)).where(
            and_(
                Purchase.user_id == current_user.id,
                Purchase.payment_status == "completed"
            )
        )
    )
    total_savings = result.scalar() or 0.0
    
    # Get recent transactions
    result = await db.execute(
        select(Purchase).where(
            Purchase.user_id == current_user.id
        ).order_by(Purchase.created_at.desc()).limit(5)
    )
    recent_transactions = result.scalars().all()
    
    return {
        "total_spent": total_spent,
        "total_savings": total_savings,
        "average_savings_percentage": (total_savings / total_spent * 100) if total_spent > 0 else 0,
        "payment_methods_count": len(await get_payment_methods(current_user, db)),
        "recent_transactions": [
            {
                "id": str(tx.id),
                "purchase_number": tx.purchase_number,
                "amount": tx.total_amount,
                "savings": tx.savings_amount,
                "status": tx.payment_status,
                "date": tx.created_at
            }
            for tx in recent_transactions
        ]
    }


@router.post("/webhook/stripe")
async def stripe_webhook(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhook events
    
    In production, this would:
    1. Verify webhook signature
    2. Process different event types
    3. Update database accordingly
    """
    event_type = payload.get("type")
    event_data = payload.get("data", {}).get("object", {})
    
    # Log webhook for debugging
    print(f"Stripe webhook received: {event_type}")
    
    # Handle different event types
    if event_type == "payment_intent.succeeded":
        # Payment succeeded
        payment_intent_id = event_data.get("id")
        customer_id = event_data.get("customer")
        
        # Find and update purchase
        result = await db.execute(
            select(Purchase).where(
                Purchase.payment_transaction_id == payment_intent_id
            )
        )
        purchase = result.scalar_one_or_none()
        
        if purchase:
            purchase.payment_status = "completed"
            purchase.status = "processing"
            purchase.updated_at = datetime.utcnow()
            await db.commit()
    
    elif event_type == "payment_intent.payment_failed":
        # Payment failed
        payment_intent_id = event_data.get("id")
        
        result = await db.execute(
            select(Purchase).where(
                Purchase.payment_transaction_id == payment_intent_id
            )
        )
        purchase = result.scalar_one_or_none()
        
        if purchase:
            purchase.payment_status = "failed"
            purchase.updated_at = datetime.utcnow()
            await db.commit()
    
    elif event_type == "charge.refunded":
        # Refund processed
        charge_id = event_data.get("id")
        refund_id = event_data.get("refunds", {}).get("data", [{}])[0].get("id")
        
        # Find and update refund
        result = await db.execute(
            select(Refund).where(
                Refund.provider_refund_id == refund_id
            )
        )
        refund = result.scalar_one_or_none()
        
        if refund:
            refund.status = "completed"
            refund.provider_status = "succeeded"
            refund.completed_at = datetime.utcnow()
            
            # Update purchase
            result = await db.execute(
                select(Purchase).where(Purchase.id == refund.purchase_id)
            )
            purchase = result.scalar_one_or_none()
            
            if purchase:
                purchase.status = "refunded"
                purchase.updated_at = datetime.utcnow()
            
            await db.commit()
    
    return {"received": True}


# Import sqlalchemy for sum function
import sqlalchemy