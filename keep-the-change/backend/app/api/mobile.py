"""
Mobile API router for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import base64
import io

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.shopping import ProductCatalog, ShoppingList, ListItem
from app.schemas.shopping import (
    ReceiptScanRequest,
    ReceiptScanResponse,
    BarcodeScanRequest,
    BarcodeScanResponse,
    ProductSearchResponse
)

router = APIRouter(prefix="/mobile", tags=["mobile"])


@router.post("/scan/receipt", response_model=ReceiptScanResponse)
async def scan_receipt(
    receipt_data: ReceiptScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scan receipt image using OCR
    
    In production, this would integrate with:
    - Google Cloud Vision API
    - Tesseract OCR
    - Custom receipt parsing models
    """
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(receipt_data.image_data)
        
        # In production, you would:
        # 1. Save image to storage
        # 2. Process with OCR service
        # 3. Parse receipt data
        # 4. Extract items and prices
        
        # For now, return mock data
        mock_items = [
            {
                "name": "Organic Milk",
                "brand": "Organic Valley",
                "quantity": 1,
                "price": 5.99,
                "unit_price": 5.99
            },
            {
                "name": "Whole Wheat Bread",
                "brand": "Nature's Own",
                "quantity": 1,
                "price": 3.49,
                "unit_price": 3.49
            },
            {
                "name": "Bananas",
                "brand": None,
                "quantity": 6,
                "price": 2.94,
                "unit_price": 0.49
            },
            {
                "name": "Eggs",
                "brand": "Happy Hens",
                "quantity": 12,
                "price": 4.99,
                "unit_price": 0.42
            }
        ]
        
        total = sum(item["price"] for item in mock_items)
        
        return ReceiptScanResponse(
            success=True,
            items=mock_items,
            total=total,
            store_name=receipt_data.store_name or "Unknown Store",
            receipt_date=datetime.utcnow(),
            confidence=0.85,
            raw_text="Mock receipt text for OCR demonstration"
        )
        
    except Exception as e:
        return ReceiptScanResponse(
            success=False,
            items=[],
            total=0.0,
            store_name=None,
            receipt_date=None,
            confidence=0.0,
            raw_text=None,
            error=str(e)
        )


@router.post("/scan/barcode", response_model=BarcodeScanResponse)
async def scan_barcode(
    barcode_data: BarcodeScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scan barcode and lookup product information
    """
    # Search for product in catalog
    result = await db.execute(
        select(ProductCatalog).where(
            (ProductCatalog.upc == barcode_data.barcode) |
            (ProductCatalog.sku == barcode_data.barcode)
        )
    )
    product = result.scalar_one_or_none()
    
    if product:
        # Product found in catalog
        retailers = [
            {
                "retailer": "Walmart",
                "price": product.average_price * 0.95 if product.average_price else 10.0,
                "in_stock": True,
                "estimated_delivery_days": 2
            },
            {
                "retailer": "Target",
                "price": product.average_price * 0.98 if product.average_price else 10.5,
                "in_stock": True,
                "estimated_delivery_days": 3
            },
            {
                "retailer": "Amazon",
                "price": product.average_price if product.average_price else 11.0,
                "in_stock": True,
                "estimated_delivery_days": 1
            }
        ]
        
        return BarcodeScanResponse(
            success=True,
            product_name=product.product_name,
            brand=product.brand,
            upc=product.upc,
            category=product.category,
            average_price=product.average_price,
            image_url=product.image_url,
            retailers=retailers
        )
    
    # Product not in catalog - search external APIs
    # In production, you would:
    # 1. Query UPC database APIs
    # 2. Search retailer APIs
    # 3. Use machine learning for product recognition
    
    # Mock response for unknown product
    mock_retailers = [
        {
            "retailer": "Walmart",
            "price": 12.99,
            "in_stock": True,
            "estimated_delivery_days": 2
        },
        {
            "retailer": "Amazon",
            "price": 13.49,
            "in_stock": True,
            "estimated_delivery_days": 1
        }
    ]
    
    return BarcodeScanResponse(
        success=True,
        product_name=f"Product {barcode_data.barcode}",
        brand=None,
        upc=barcode_data.barcode,
        category="General",
        average_price=12.99,
        image_url=None,
        retailers=mock_retailers
    )


@router.post("/scan/image")
async def scan_product_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scan product image using computer vision
    
    In production, this would use:
    - TensorFlow/PyTorch models
    - Google Cloud Vision
    - Custom product recognition
    """
    # Read image data
    image_data = await image.read()
    
    # In production, you would:
    # 1. Process image with ML model
    # 2. Identify product
    # 3. Search in catalog
    # 4. Return product info
    
    # Mock response
    return {
        "success": True,
        "product_name": "Organic Milk",
        "brand": "Organic Valley",
        "confidence": 0.78,
        "similar_products": [
            {
                "name": "Organic Milk",
                "brand": "Horizon Organic",
                "confidence": 0.65
            },
            {
                "name": "Whole Milk",
                "brand": "Generic",
                "confidence": 0.45
            }
        ],
        "message": "Product identified with 78% confidence"
    }


@router.get("/location/offers")
async def get_location_offers(
    latitude: float = Query(..., description="Latitude"),
    longitude: float = Query(..., description="Longitude"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0, description="Search radius in kilometers"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get location-based offers and deals
    
    In production, this would integrate with:
    - Retailer location APIs
    - Google Places API
    - Deal aggregation services
    """
    # Mock location-based offers
    offers = [
        {
            "store": "Walmart",
            "distance_km": 1.2,
            "offers": [
                {
                    "product": "Organic Milk",
                    "discount": "15% off",
                    "valid_until": "2026-04-15",
                    "original_price": 5.99,
                    "sale_price": 5.09
                },
                {
                    "product": "Eggs",
                    "discount": "Buy 1 Get 1 Free",
                    "valid_until": "2026-04-14",
                    "original_price": 4.99,
                    "sale_price": 2.50
                }
            ]
        },
        {
            "store": "Target",
            "distance_km": 2.5,
            "offers": [
                {
                    "product": "Whole Wheat Bread",
                    "discount": "20% off",
                    "valid_until": "2026-04-16",
                    "original_price": 3.49,
                    "sale_price": 2.79
                }
            ]
        },
        {
            "store": "Whole Foods",
            "distance_km": 3.1,
            "offers": [
                {
                    "product": "Organic Produce",
                    "discount": "10% off entire purchase",
                    "valid_until": "2026-04-13",
                    "minimum_purchase": 50.0
                }
            ]
        }
    ]
    
    return {
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km
        },
        "offers": offers,
        "total_offers": sum(len(store["offers"]) for store in offers)
    }


@router.post("/lists/quick-add")
async def quick_add_to_list(
    product_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Quick add product to shopping list from mobile scan
    """
    product_name = product_data.get("product_name")
    list_id = product_data.get("list_id")
    
    if not product_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product name is required"
        )
    
    # Get or create default shopping list
    if list_id:
        try:
            list_uuid = uuid.UUID(list_id)
            result = await db.execute(
                select(ShoppingList).where(
                    and_(
                        ShoppingList.id == list_uuid,
                        ShoppingList.user_id == current_user.id
                    )
                )
            )
            shopping_list = result.scalar_one_or_none()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid list ID"
            )
    else:
        # Get most recent active list or create new one
        result = await db.execute(
            select(ShoppingList).where(
                and_(
                    ShoppingList.user_id == current_user.id,
                    ShoppingList.status.in_(["draft", "optimizing", "ready"])
                )
            ).order_by(ShoppingList.created_at.desc()).limit(1)
        )
        shopping_list = result.scalar_one_or_none()
        
        if not shopping_list:
            shopping_list = ShoppingList(
                user_id=current_user.id,
                name="Mobile Shopping List",
                status="draft"
            )
            db.add(shopping_list)
            await db.commit()
            await db.refresh(shopping_list)
    
    # Add item to list
    list_item = ListItem(
        list_id=shopping_list.id,
        product_name=product_name,
        brand=product_data.get("brand"),
        upc=product_data.get("upc"),
        sku=product_data.get("sku"),
        quantity=product_data.get("quantity", 1),
        max_price=product_data.get("max_price"),
        priority=product_data.get("priority", 5)
    )
    
    db.add(list_item)
    shopping_list.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(list_item)
    
    return {
        "success": True,
        "list_id": str(shopping_list.id),
        "list_name": shopping_list.name,
        "item_id": str(list_item.id),
        "product_name": list_item.product_name,
        "message": f"Added {product_name} to {shopping_list.name}"
    }


@router.get("/notifications")
async def get_mobile_notifications(
    unread_only: bool = Query(True, description="Show only unread notifications"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get mobile notifications for user
    """
    # Mock notifications
    # In production, these would come from a notifications table
    
    notifications = [
        {
            "id": str(uuid.uuid4()),
            "type": "price_drop",
            "title": "Price Drop Alert",
            "message": "Organic Milk is now 15% cheaper at Walmart",
            "data": {
                "product": "Organic Milk",
                "retailer": "Walmart",
                "old_price": 5.99,
                "new_price": 5.09,
                "savings": 0.90
            },
            "read": False,
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "type": "investment_update",
            "title": "Investment Update",
            "message": "Your crypto investment gained 2.3% today",
            "data": {
                "investment_id": str(uuid.uuid4()),
                "gain_percentage": 2.3,
                "gain_amount": 1.15
            },
            "read": True,
            "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "type": "order_update",
            "title": "Order Shipped",
            "message": "Your order #KTCP-20260411-ABC123 has shipped",
            "data": {
                "order_number": "KTCP-20260411-ABC123",
                "tracking_number": "1Z1234567890123456",
                "carrier": "UPS"
            },
            "read": False,
            "created_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()
        }
    ]
    
    if unread_only:
        notifications = [n for n in notifications if not n["read"]]
    
    return {
        "notifications": notifications[:limit],
        "total": len(notifications),
        "unread_count": len([n for n in notifications if not n["read"]])
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark notification as read
    """
    # In production, this would update the notification in database
    
    return {
        "success": True,
        "notification_id": notification_id,
        "message": "Notification marked as read"
    }


@router.get("/dashboard")
async def get_mobile_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get mobile dashboard data
    """
    # Get active shopping lists
    result = await db.execute(
        select(ShoppingList).where(
            and_(
                ShoppingList.user_id == current_user.id,
                ShoppingList.status.in_(["draft", "optimizing", "ready"])
            )
        ).order_by(ShoppingList.updated_at.desc()).limit(3)
    )
    active_lists = result.scalars().all()
    
    # Get recent purchases
    from app.models.purchase import Purchase
    result = await db.execute(
        select(Purchase).where(
            Purchase.user_id == current_user.id
        ).order_by(Purchase.created_at.desc()).limit(3)
    )
    recent_purchases = result.scalars().all()
    
    # Calculate savings stats
    total_savings = current_user.total_savings or 0.0
    total_invested = current_user.total_invested or 0.0
    crypto_balance = current_user.crypto_balance or 0.0
    
    return {
        "user": {
            "name": current_user.full_name,
            "subscription_tier": current_user.subscription_tier,
            "avatar_url": current_user.avatar_url
        },
        "stats": {
            "total_savings": total_savings,
            "total_invested": total_invested,
            "crypto_balance": crypto_balance,
            "active_lists": len(active_lists),
            "pending_orders": len([p for p in recent_purchases if p.status in ["processing", "shipped"]])
        },
        "active_lists": [
            {
                "id": str(lst.id),
                "name": lst.name,
                "item_count": len(lst.items) if hasattr(lst, 'items') else 0,
                "status": lst.status,
                "updated_at": lst.updated_at.isoformat()
            }
            for lst in active_lists
        ],
        "quick_actions": [
            {
                "id": "scan_receipt",
                "title": "Scan Receipt",
                "icon": "receipt",
                "color": "blue"
            },
            {
                "id": "scan_barcode",
                "title": "Scan Barcode",
                "icon": "barcode",
                "color": "green"
            },
            {
                "id": "create_list",
                "title": "New List",
                "icon": "list",
                "color": "purple"
            },
            {
                "id": "find_deals",
                "title": "Nearby Deals",
                "icon": "tag",
                "color": "orange"
            }
        ]
    }


@router.post("/social/share")
async def share_savings(
    share_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Share savings achievement on social media
    """
    share_type = share_data.get("type", "savings")
    message = share_data.get("message")
    platforms = share_data.get("platforms", [])
    
    if not message:
        # Generate default message
        if share_type == "savings":
            message = f"I just saved ${current_user.total_savings:.2f} with KEEPTHECHANGE.com! 🛒➡️💰 #KeepTheChange #SmartShopping"
        elif share_type == "investment":
            message = f"My grocery savings are now earning crypto returns with KEEPTHECHANGE.com! 🛒➡️📈 #CryptoInvesting #KeepTheChange"
        else:
            message = "Check out KEEPTHECHANGE.com - it turns grocery savings into crypto investments! #FinTech #Crypto"
    
    # In production, this would:
    # 1. Generate shareable content
    # 2. Create tracking links
    # 3. Integrate with social media APIs
    
    share_urls = {}
    for platform in platforms:
        if platform == "twitter":
            share_urls["twitter"] = f"https://twitter.com/intent/tweet?text={message}"
        elif platform == "facebook":
            share_urls["facebook"] = f"https://www.facebook.com/sharer/sharer.php?u=https://keepthechange.com&quote={message}"
        elif platform == "linkedin":
            share_urls["linkedin"] = f"https://www.linkedin.com/sharing/share-offsite/?url=https://keepthechange.com&summary={message}"
    
    return {
        "success": True,
        "message": message,
        "share_urls": share_urls,
        "tracking_id": f"share_{uuid.uuid4().hex[:8]}"
    }


# Import timedelta for notifications
from datetime import timedelta
# Import and_ for queries
from sqlalchemy import and_