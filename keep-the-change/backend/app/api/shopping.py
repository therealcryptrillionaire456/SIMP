"""
Shopping API router for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.shopping import ShoppingList, ListItem, PriceComparison, ProductCatalog
from app.models.purchase import Purchase, PurchaseItem
from app.schemas.shopping import (
    ShoppingListCreate,
    ShoppingListUpdate,
    ShoppingListResponse,
    ListItemCreate,
    ListItemResponse,
    PriceComparisonResponse,
    ProductSearchResponse,
    OptimizationRequest,
    OptimizationResponse,
    PurchaseRequest,
    PurchaseResponse
)

router = APIRouter(prefix="/shopping", tags=["shopping"])


@router.get("/lists", response_model=List[ShoppingListResponse])
async def get_shopping_lists(
    status_filter: Optional[str] = Query(None, description="Filter by status: draft, optimizing, ready, purchased, cancelled"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's shopping lists
    
    Returns paginated list of shopping lists
    """
    query = select(ShoppingList).where(ShoppingList.user_id == current_user.id)
    
    if status_filter:
        query = query.where(ShoppingList.status == status_filter)
    
    query = query.order_by(ShoppingList.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    lists = result.scalars().all()
    
    return [ShoppingListResponse.from_orm(lst) for lst in lists]


@router.post("/lists", response_model=ShoppingListResponse, status_code=status.HTTP_201_CREATED)
async def create_shopping_list(
    list_data: ShoppingListCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new shopping list
    """
    shopping_list = ShoppingList(
        user_id=current_user.id,
        name=list_data.name,
        description=list_data.description,
        budget_limit=list_data.budget_limit,
        max_items=list_data.max_items,
        priority=list_data.priority or "normal",
        optimization_strategy=list_data.optimization_strategy or "cheapest",
        delivery_preference=list_data.delivery_preference or "standard",
        retailer_preferences=list_data.retailer_preferences or []
    )
    
    db.add(shopping_list)
    await db.commit()
    await db.refresh(shopping_list)
    
    return ShoppingListResponse.from_orm(shopping_list)


@router.get("/lists/{list_id}", response_model=ShoppingListResponse)
async def get_shopping_list(
    list_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get shopping list by ID
    """
    try:
        list_uuid = uuid.UUID(list_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid list ID"
        )
    
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.id == list_uuid,
                ShoppingList.user_id == current_user.id
            )
        )
    )
    shopping_list = result.scalar_one_or_none()
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    return ShoppingListResponse.from_orm(shopping_list)


@router.put("/lists/{list_id}", response_model=ShoppingListResponse)
async def update_shopping_list(
    list_id: str,
    list_data: ShoppingListUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update shopping list
    """
    try:
        list_uuid = uuid.UUID(list_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid list ID"
        )
    
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.id == list_uuid,
                ShoppingList.user_id == current_user.id
            )
        )
    )
    shopping_list = result.scalar_one_or_none()
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Update fields
    update_data = list_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(shopping_list, field):
            setattr(shopping_list, field, value)
    
    shopping_list.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(shopping_list)
    
    return ShoppingListResponse.from_orm(shopping_list)


@router.delete("/lists/{list_id}")
async def delete_shopping_list(
    list_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete shopping list
    """
    try:
        list_uuid = uuid.UUID(list_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid list ID"
        )
    
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.id == list_uuid,
                ShoppingList.user_id == current_user.id
            )
        )
    )
    shopping_list = result.scalar_one_or_none()
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Soft delete by changing status
    shopping_list.status = "cancelled"
    shopping_list.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Shopping list deleted successfully"}


@router.post("/lists/{list_id}/items", response_model=ListItemResponse, status_code=status.HTTP_201_CREATED)
async def add_list_item(
    list_id: str,
    item_data: ListItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add item to shopping list
    """
    try:
        list_uuid = uuid.UUID(list_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid list ID"
        )
    
    # Verify list exists and belongs to user
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.id == list_uuid,
                ShoppingList.user_id == current_user.id
            )
        )
    )
    shopping_list = result.scalar_one_or_none()
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Create list item
    list_item = ListItem(
        list_id=list_uuid,
        product_name=item_data.product_name,
        brand=item_data.brand,
        upc=item_data.upc,
        sku=item_data.sku,
        category=item_data.category,
        subcategory=item_data.subcategory,
        size=item_data.size,
        unit=item_data.unit,
        quantity=item_data.quantity or 1,
        max_price=item_data.max_price,
        priority=item_data.priority or 5,
        notes=item_data.notes,
        dietary_tags=item_data.dietary_tags or []
    )
    
    db.add(list_item)
    shopping_list.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(list_item)
    
    return ListItemResponse.from_orm(list_item)


@router.get("/lists/{list_id}/items", response_model=List[ListItemResponse])
async def get_list_items(
    list_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get items in shopping list
    """
    try:
        list_uuid = uuid.UUID(list_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid list ID"
        )
    
    # Verify list exists and belongs to user
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.id == list_uuid,
                ShoppingList.user_id == current_user.id
            )
        )
    )
    shopping_list = result.scalar_one_or_none()
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Get items
    result = await db.execute(
        select(ListItem).where(ListItem.list_id == list_uuid).order_by(ListItem.priority.desc(), ListItem.created_at)
    )
    items = result.scalars().all()
    
    return [ListItemResponse.from_orm(item) for item in items]


@router.post("/search/products", response_model=ProductSearchResponse)
async def search_products(
    query: str = Query(..., min_length=1, max_length=100),
    category: Optional[str] = None,
    brand: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for products in catalog
    
    Returns products matching search query
    """
    search_query = select(ProductCatalog).where(
        or_(
            ProductCatalog.product_name.ilike(f"%{query}%"),
            ProductCatalog.brand.ilike(f"%{query}%"),
            ProductCatalog.description.ilike(f"%{query}%")
        )
    )
    
    if category:
        search_query = search_query.where(ProductCatalog.category == category)
    
    if brand:
        search_query = search_query.where(ProductCatalog.brand == brand)
    
    # Get total count
    count_query = select([sqlalchemy.func.count()]).select_from(search_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    search_query = search_query.order_by(
        ProductCatalog.search_count.desc(),
        ProductCatalog.purchase_count.desc()
    ).limit(limit).offset(offset)
    
    result = await db.execute(search_query)
    products = result.scalars().all()
    
    return ProductSearchResponse(
        products=[{
            "id": str(product.id),
            "product_name": product.product_name,
            "brand": product.brand,
            "category": product.category,
            "size": product.size,
            "unit": product.unit,
            "average_price": product.average_price,
            "image_url": product.image_url,
            "dietary_tags": product.dietary_tags
        } for product in products],
        total=total,
        query=query,
        limit=limit,
        offset=offset
    )


@router.post("/lists/{list_id}/optimize", response_model=OptimizationResponse)
async def optimize_shopping_list(
    list_id: str,
    optimization_data: OptimizationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Optimize shopping list for best prices
    
    This would integrate with price comparison services in production
    """
    try:
        list_uuid = uuid.UUID(list_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid list ID"
        )
    
    # Verify list exists and belongs to user
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.id == list_uuid,
                ShoppingList.user_id == current_user.id
            )
        )
    )
    shopping_list = result.scalar_one_or_none()
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Get list items
    result = await db.execute(
        select(ListItem).where(ListItem.list_id == list_uuid)
    )
    items = result.scalars().all()
    
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shopping list is empty"
        )
    
    # In production, this would call external price comparison APIs
    # For now, generate mock optimizations
    
    mock_optimizations = []
    total_optimized_price = 0.0
    total_estimated_retail = 0.0
    
    for item in items:
        # Mock price data
        estimated_retail = item.max_price or 10.0  # Default $10 if no max price
        optimized_price = estimated_retail * 0.85  # 15% savings
        
        # Create mock price comparisons
        comparisons = []
        retailers = ["Walmart", "Target", "Amazon", "Kroger", "Whole Foods"]
        
        for i, retailer in enumerate(retailers[:3]):  # Top 3 retailers
            price = optimized_price * (0.9 + (i * 0.05))  # Vary prices slightly
            is_best = i == 0  # First retailer has best price
            
            comparison = PriceComparison(
                item_id=item.id,
                retailer=retailer,
                price=price,
                original_price=price * 1.1,  # 10% "original" price
                in_stock=True,
                shipping_cost=0 if i == 0 else 5.99,  # First retailer has free shipping
                estimated_delivery_days=2 if i == 0 else 5
            )
            
            if is_best:
                comparison.is_best_price = True
                item.optimized_price = price
                item.optimized_retailer = retailer
                item.status = "found"
            
            comparisons.append(comparison)
            db.add(comparison)
        
        mock_optimizations.append({
            "item_id": str(item.id),
            "product_name": item.product_name,
            "optimized_price": item.optimized_price,
            "optimized_retailer": item.optimized_retailer,
            "comparisons": [{
                "retailer": comp.retailer,
                "price": comp.price,
                "shipping_cost": comp.shipping_cost,
                "total_price": comp.price + comp.shipping_cost,
                "estimated_delivery_days": comp.estimated_delivery_days,
                "is_best_price": comp.is_best_price
            } for comp in comparisons]
        })
        
        total_optimized_price += (item.optimized_price or 0) * item.quantity
        total_estimated_retail += estimated_retail * item.quantity
    
    # Update shopping list
    shopping_list.status = "ready"
    shopping_list.optimized_total = total_optimized_price
    shopping_list.estimated_savings = total_estimated_retail - total_optimized_price
    shopping_list.estimated_delivery_days = 2  # Mock delivery estimate
    shopping_list.optimized_at = datetime.utcnow()
    shopping_list.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return OptimizationResponse(
        list_id=list_id,
        status="optimized",
        optimized_total=total_optimized_price,
        estimated_savings=shopping_list.estimated_savings,
        estimated_delivery_days=shopping_list.estimated_delivery_days,
        optimizations=mock_optimizations,
        message=f"Found optimal prices with ${shopping_list.estimated_savings:.2f} in savings"
    )


@router.post("/lists/{list_id}/purchase", response_model=PurchaseResponse)
async def purchase_shopping_list(
    list_id: str,
    purchase_data: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Purchase optimized shopping list
    
    In production, this would integrate with payment processors and retailer APIs
    """
    try:
        list_uuid = uuid.UUID(list_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid list ID"
        )
    
    # Verify list exists, belongs to user, and is optimized
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.id == list_uuid,
                ShoppingList.user_id == current_user.id,
                ShoppingList.status == "ready"
            )
        )
    )
    shopping_list = result.scalar_one_or_none()
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shopping list not found or not ready for purchase"
        )
    
    # Verify payment method exists (in production)
    # For now, just check if payment method ID is provided
    if not purchase_data.payment_method_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment method is required"
        )
    
    # Create purchase record
    purchase = Purchase(
        user_id=current_user.id,
        list_id=list_uuid,
        payment_method_id=purchase_data.payment_method_id,
        purchase_number=f"KTCP-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        total_amount=shopping_list.optimized_total or 0,
        subtotal=shopping_list.optimized_total or 0,
        savings_amount=shopping_list.estimated_savings or 0,
        estimated_retail_price=(shopping_list.optimized_total or 0) + (shopping_list.estimated_savings or 0),
        shipping_address=purchase_data.shipping_address,
        shipping_method=purchase_data.shipping_method or "standard",
        status="processing",
        payment_status="pending"
    )
    
    if shopping_list.estimated_savings and shopping_list.optimized_total:
        purchase.savings_percentage = (shopping_list.estimated_savings / 
                                      (shopping_list.optimized_total + shopping_list.estimated_savings)) * 100
    
    db.add(purchase)
    
    # Get list items to create purchase items
    result = await db.execute(
        select(ListItem).where(
            and_(
                ListItem.list_id == list_uuid,
                ListItem.status == "found"
            )
        )
    )
    items = result.scalars().all()
    
    purchase_items = []
    for item in items:
        purchase_item = PurchaseItem(
            purchase_id=purchase.id,
            list_item_id=item.id,
            product_name=item.product_name,
            brand=item.brand,
            quantity=item.quantity,
            unit_price=item.optimized_price or 0,
            total_price=(item.optimized_price or 0) * item.quantity,
            retailer=item.optimized_retailer or "Unknown",
            estimated_retail_price=item.max_price or (item.optimized_price or 0) * 1.15,
            savings_amount=(item.max_price or (item.optimized_price or 0) * 1.15) - (item.optimized_price or 0)
        )
        purchase_items.append(purchase_item)
        db.add(purchase_item)
    
    # Update shopping list status
    shopping_list.status = "purchased"
    shopping_list.purchased_at = datetime.utcnow()
    shopping_list.updated_at = datetime.utcnow()
    
    # Update user's total savings
    current_user.total_savings = (current_user.total_savings or 0) + (shopping_list.estimated_savings or 0)
    
    await db.commit()
    await db.refresh(purchase)
    
    # In production, this would:
    # 1. Process payment with Stripe/PayPal
    # 2. Place orders with retailers via APIs
    # 3. Schedule crypto investment for savings
    
    return PurchaseResponse(
        purchase_id=str(purchase.id),
        purchase_number=purchase.purchase_number,
        total_amount=purchase.total_amount,
        savings_amount=purchase.savings_amount,
        status=purchase.status,
        estimated_delivery="2-5 business days",  # Mock
        tracking_number=None,  # Would be populated after shipping
        message="Purchase initiated successfully. The change will be invested in crypto once the order is confirmed."
    )


@router.get("/purchases", response_model=List[PurchaseResponse])
async def get_user_purchases(
    status_filter: Optional[str] = Query(None, description="Filter by status: processing, shipped, delivered, cancelled"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's purchase history
    """
    query = select(Purchase).where(Purchase.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Purchase.status == status_filter)
    
    query = query.order_by(Purchase.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    purchases = result.scalars().all()
    
    return [PurchaseResponse.from_purchase(purchase) for purchase in purchases]


@router.get("/purchases/{purchase_id}", response_model=PurchaseResponse)
async def get_purchase_details(
    purchase_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get purchase details by ID
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
    
    return PurchaseResponse.from_purchase(purchase)


# Import sqlalchemy for count query
import sqlalchemy