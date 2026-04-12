"""
Pydantic schemas for shopping models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
import uuid


class ShoppingListBase(BaseModel):
    """Base shopping list schema"""
    name: str = Field(..., min_length=1, max_length=100, description="Name of the shopping list")
    description: Optional[str] = Field(None, max_length=500)
    budget_limit: Optional[float] = Field(None, ge=0, description="Maximum budget for this list")
    max_items: Optional[int] = Field(None, ge=1, le=100, description="Maximum number of items")


class ShoppingListCreate(ShoppingListBase):
    """Schema for shopping list creation"""
    priority: Optional[str] = Field("normal", description="Priority: low, normal, high, urgent")
    optimization_strategy: Optional[str] = Field("cheapest", description="Strategy: cheapest, fastest, balanced")
    delivery_preference: Optional[str] = Field("standard", description="Delivery: standard, express, pickup")
    retailer_preferences: Optional[List[str]] = Field([], description="Preferred retailers")
    
    @validator('priority')
    def validate_priority(cls, v):
        allowed = ['low', 'normal', 'high', 'urgent']
        if v not in allowed:
            raise ValueError(f'Priority must be one of: {", ".join(allowed)}')
        return v
    
    @validator('optimization_strategy')
    def validate_strategy(cls, v):
        allowed = ['cheapest', 'fastest', 'balanced']
        if v not in allowed:
            raise ValueError(f'Strategy must be one of: {", ".join(allowed)}')
        return v
    
    @validator('delivery_preference')
    def validate_delivery(cls, v):
        allowed = ['standard', 'express', 'pickup']
        if v not in allowed:
            raise ValueError(f'Delivery preference must be one of: {", ".join(allowed)}')
        return v


class ShoppingListUpdate(BaseModel):
    """Schema for shopping list updates"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    budget_limit: Optional[float] = Field(None, ge=0)
    max_items: Optional[int] = Field(None, ge=1, le=100)
    priority: Optional[str] = None
    optimization_strategy: Optional[str] = None
    delivery_preference: Optional[str] = None
    retailer_preferences: Optional[List[str]] = None
    
    class Config:
        extra = "forbid"


class ShoppingListResponse(ShoppingListBase):
    """Schema for shopping list response"""
    id: uuid.UUID
    user_id: uuid.UUID
    priority: str
    optimization_strategy: str
    delivery_preference: str
    retailer_preferences: List[str]
    status: str
    optimized_total: Optional[float]
    estimated_savings: Optional[float]
    estimated_delivery_days: Optional[int]
    item_count: int
    created_at: datetime
    updated_at: datetime
    optimized_at: Optional[datetime]
    purchased_at: Optional[datetime]
    
    class Config:
        orm_mode = True
    
    @classmethod
    def from_orm(cls, obj):
        """Create response from ORM object with item count"""
        data = super().from_orm(obj)
        data.item_count = len(obj.items) if hasattr(obj, 'items') else 0
        return data


class ListItemBase(BaseModel):
    """Base list item schema"""
    product_name: str = Field(..., min_length=1, max_length=255)
    brand: Optional[str] = Field(None, max_length=100)
    upc: Optional[str] = Field(None, max_length=20, description="Universal Product Code")
    sku: Optional[str] = Field(None, max_length=100, description="Stock Keeping Unit")
    category: Optional[str] = Field(None, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    size: Optional[str] = Field(None, max_length=50)
    unit: Optional[str] = Field(None, max_length=20)


class ListItemCreate(ListItemBase):
    """Schema for list item creation"""
    quantity: int = Field(1, ge=1, le=100)
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price user is willing to pay")
    priority: int = Field(5, ge=1, le=10, description="Priority level 1-10")
    notes: Optional[str] = Field(None, max_length=500)
    dietary_tags: Optional[List[str]] = Field([], description="Dietary restrictions: organic, gluten_free, vegan, etc.")


class ListItemResponse(ListItemBase):
    """Schema for list item response"""
    id: uuid.UUID
    list_id: uuid.UUID
    quantity: int
    max_price: Optional[float]
    priority: int
    notes: Optional[str]
    dietary_tags: List[str]
    status: str
    optimized_price: Optional[float]
    optimized_retailer: Optional[str]
    substitution_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
    
    @property
    def total_cost(self) -> Optional[float]:
        """Calculate total cost for this item"""
        if self.optimized_price and self.quantity:
            return self.optimized_price * self.quantity
        return None


class PriceComparisonResponse(BaseModel):
    """Schema for price comparison response"""
    retailer: str
    price: float
    original_price: Optional[float]
    currency: str = "USD"
    unit_price: Optional[float]
    unit: Optional[str]
    in_stock: bool
    stock_quantity: Optional[int]
    shipping_cost: float
    free_shipping_threshold: Optional[float]
    estimated_delivery_days: Optional[int]
    delivery_date: Optional[datetime]
    product_title: Optional[str]
    product_image: Optional[str]
    retailer_rating: Optional[float]
    product_rating: Optional[float]
    is_best_price: bool
    savings_vs_average: Optional[float]
    
    class Config:
        orm_mode = True
    
    @property
    def total_price(self) -> float:
        """Calculate total price including shipping"""
        return self.price + self.shipping_cost
    
    @property
    def savings_percentage(self) -> Optional[float]:
        """Calculate savings percentage vs original price"""
        if self.original_price and self.original_price > 0:
            return ((self.original_price - self.price) / self.original_price) * 100
        return None


class ProductSearchItem(BaseModel):
    """Schema for product search result item"""
    id: uuid.UUID
    product_name: str
    brand: Optional[str]
    category: Optional[str]
    size: Optional[str]
    unit: Optional[str]
    average_price: Optional[float]
    image_url: Optional[str]
    dietary_tags: List[str]


class ProductSearchResponse(BaseModel):
    """Schema for product search response"""
    products: List[ProductSearchItem]
    total: int
    query: str
    limit: int
    offset: int


class OptimizationRequest(BaseModel):
    """Schema for optimization request"""
    force_refresh: bool = Field(False, description="Force fresh price comparison")
    include_out_of_stock: bool = Field(False, description="Include out of stock items in results")
    max_retailers_per_item: int = Field(5, ge=1, le=10, description="Maximum number of retailers to compare per item")


class OptimizationItem(BaseModel):
    """Schema for optimized item"""
    item_id: uuid.UUID
    product_name: str
    optimized_price: Optional[float]
    optimized_retailer: Optional[str]
    comparisons: List[Dict[str, Any]]


class OptimizationResponse(BaseModel):
    """Schema for optimization response"""
    list_id: str
    status: str
    optimized_total: float
    estimated_savings: float
    estimated_delivery_days: Optional[int]
    optimizations: List[OptimizationItem]
    message: str


class PurchaseRequest(BaseModel):
    """Schema for purchase request"""
    payment_method_id: uuid.UUID = Field(..., description="ID of payment method to use")
    shipping_address: Dict[str, Any] = Field(..., description="Shipping address")
    shipping_method: Optional[str] = Field("standard", description="Shipping method: standard, express")
    auto_invest_savings: bool = Field(True, description="Automatically invest savings in crypto")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes for the order")
    
    @validator('shipping_address')
    def validate_shipping_address(cls, v):
        """Validate shipping address"""
        required_fields = ['street', 'city', 'state', 'zip', 'country']
        for field in required_fields:
            if field not in v or not v[field]:
                raise ValueError(f'Shipping address must include {field}')
        return v


class PurchaseResponse(BaseModel):
    """Schema for purchase response"""
    purchase_id: str
    purchase_number: str
    total_amount: float
    savings_amount: float
    status: str
    estimated_delivery: Optional[str]
    tracking_number: Optional[str]
    message: str
    
    @classmethod
    def from_purchase(cls, purchase):
        """Create response from Purchase object"""
        return cls(
            purchase_id=str(purchase.id),
            purchase_number=purchase.purchase_number,
            total_amount=purchase.total_amount,
            savings_amount=purchase.savings_amount,
            status=purchase.status,
            estimated_delivery=None,  # Would come from shipping service
            tracking_number=purchase.tracking_number,
            message="Purchase processed successfully"
        )


class ReceiptScanRequest(BaseModel):
    """Schema for receipt scan request"""
    image_data: str = Field(..., description="Base64 encoded receipt image")
    image_format: str = Field("jpg", description="Image format: jpg, png, pdf")
    store_name: Optional[str] = Field(None, description="Store name (for better OCR)")


class ReceiptScanResponse(BaseModel):
    """Schema for receipt scan response"""
    success: bool
    items: List[Dict[str, Any]]
    total: float
    store_name: Optional[str]
    receipt_date: Optional[datetime]
    confidence: float
    raw_text: Optional[str]


class BarcodeScanRequest(BaseModel):
    """Schema for barcode scan request"""
    barcode: str = Field(..., min_length=8, max_length=20, description="Barcode/UPC code")
    scan_type: str = Field("upc", description="Barcode type: upc, ean, qr")


class BarcodeScanResponse(BaseModel):
    """Schema for barcode scan response"""
    success: bool
    product_name: Optional[str]
    brand: Optional[str]
    upc: Optional[str]
    category: Optional[str]
    average_price: Optional[float]
    image_url: Optional[str]
    retailers: List[Dict[str, Any]]


# Export all schemas
__all__ = [
    "ShoppingListBase",
    "ShoppingListCreate",
    "ShoppingListUpdate",
    "ShoppingListResponse",
    "ListItemBase",
    "ListItemCreate",
    "ListItemResponse",
    "PriceComparisonResponse",
    "ProductSearchItem",
    "ProductSearchResponse",
    "OptimizationRequest",
    "OptimizationItem",
    "OptimizationResponse",
    "PurchaseRequest",
    "PurchaseResponse",
    "ReceiptScanRequest",
    "ReceiptScanResponse",
    "BarcodeScanRequest",
    "BarcodeScanResponse"
]