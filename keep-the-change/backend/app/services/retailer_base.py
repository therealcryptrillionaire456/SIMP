"""
Base retailer interface for KEEPTHECHANGE.com

This module defines the abstract base class for all retailer integrations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class RetailerProduct:
    """Represents a product from a retailer"""
    
    def __init__(
        self,
        retailer: str,
        product_id: str,
        name: str,
        price: float,
        original_price: Optional[float] = None,
        currency: str = "USD",
        in_stock: bool = True,
        stock_quantity: Optional[int] = None,
        shipping_cost: float = 0.0,
        free_shipping_threshold: Optional[float] = None,
        estimated_delivery_days: Optional[int] = None,
        product_url: Optional[str] = None,
        image_url: Optional[str] = None,
        description: Optional[str] = None,
        brand: Optional[str] = None,
        upc: Optional[str] = None,
        sku: Optional[str] = None,
        category: Optional[str] = None,
        size: Optional[str] = None,
        unit: Optional[str] = None,
        unit_price: Optional[float] = None,
        unit_type: Optional[str] = None,
        retailer_rating: Optional[float] = None,
        product_rating: Optional[float] = None,
        review_count: Optional[int] = None
    ):
        self.retailer = retailer
        self.product_id = product_id
        self.name = name
        self.price = price
        self.original_price = original_price
        self.currency = currency
        self.in_stock = in_stock
        self.stock_quantity = stock_quantity
        self.shipping_cost = shipping_cost
        self.free_shipping_threshold = free_shipping_threshold
        self.estimated_delivery_days = estimated_delivery_days
        self.product_url = product_url
        self.image_url = image_url
        self.description = description
        self.brand = brand
        self.upc = upc
        self.sku = sku
        self.category = category
        self.size = size
        self.unit = unit
        self.unit_price = unit_price
        self.unit_type = unit_type
        self.retailer_rating = retailer_rating
        self.product_rating = product_rating
        self.review_count = review_count
        self.fetched_at = datetime.utcnow()
    
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
    
    @property
    def is_free_shipping(self) -> bool:
        """Check if shipping is free"""
        if self.free_shipping_threshold:
            return self.price >= self.free_shipping_threshold
        return self.shipping_cost == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "retailer": self.retailer,
            "product_id": self.product_id,
            "name": self.name,
            "price": self.price,
            "original_price": self.original_price,
            "currency": self.currency,
            "in_stock": self.in_stock,
            "stock_quantity": self.stock_quantity,
            "shipping_cost": self.shipping_cost,
            "free_shipping_threshold": self.free_shipping_threshold,
            "estimated_delivery_days": self.estimated_delivery_days,
            "total_price": self.total_price,
            "savings_percentage": self.savings_percentage,
            "is_free_shipping": self.is_free_shipping,
            "product_url": self.product_url,
            "image_url": self.image_url,
            "brand": self.brand,
            "upc": self.upc,
            "sku": self.sku,
            "category": self.category,
            "size": self.size,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "unit_type": self.unit_type,
            "retailer_rating": self.retailer_rating,
            "product_rating": self.product_rating,
            "review_count": self.review_count,
            "fetched_at": self.fetched_at.isoformat()
        }
    
    def __repr__(self):
        return f"<RetailerProduct(retailer={self.retailer}, name={self.name[:30]}..., price={self.price})>"


class RetailerInterface(ABC):
    """Abstract base class for retailer integrations"""
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.retailer_name = self.__class__.__name__.replace("Retailer", "").lower()
        self.is_authenticated = False
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with retailer API"""
        pass
    
    @abstractmethod
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = True,
        limit: int = 20
    ) -> List[RetailerProduct]:
        """Search for products"""
        pass
    
    @abstractmethod
    async def get_product_by_id(self, product_id: str) -> Optional[RetailerProduct]:
        """Get product by retailer's product ID"""
        pass
    
    @abstractmethod
    async def get_product_by_upc(self, upc: str) -> Optional[RetailerProduct]:
        """Get product by UPC"""
        pass
    
    async def get_product_price(self, product_id: str) -> Optional[float]:
        """Get current price for a product"""
        product = await self.get_product_by_id(product_id)
        return product.price if product else None
    
    async def check_availability(self, product_id: str) -> bool:
        """Check if product is in stock"""
        product = await self.get_product_by_id(product_id)
        return product.in_stock if product else False
    
    async def batch_get_prices(self, product_ids: List[str]) -> Dict[str, Optional[float]]:
        """Get prices for multiple products (optimized for batch operations)"""
        results = {}
        for product_id in product_ids:
            price = await self.get_product_price(product_id)
            results[product_id] = price
        return results
    
    @abstractmethod
    async def get_shipping_cost(
        self,
        product_id: str,
        quantity: int = 1,
        zip_code: Optional[str] = None
    ) -> float:
        """Calculate shipping cost for a product"""
        pass
    
    @abstractmethod
    async def estimate_delivery(
        self,
        product_id: str,
        zip_code: str,
        shipping_method: str = "standard"
    ) -> Optional[datetime]:
        """Estimate delivery date"""
        pass
    
    def get_retailer_info(self) -> Dict[str, Any]:
        """Get retailer information"""
        return {
            "name": self.retailer_name,
            "requires_auth": self.api_key is not None,
            "is_authenticated": self.is_authenticated,
            "supports_upc_lookup": True,
            "supports_batch_operations": True
        }


class RetailerError(Exception):
    """Base exception for retailer errors"""
    pass


class AuthenticationError(RetailerError):
    """Raised when authentication fails"""
    pass


class ProductNotFoundError(RetailerError):
    """Raised when product is not found"""
    pass


class RateLimitError(RetailerError):
    """Raised when rate limit is exceeded"""
    pass


class RetailerUnavailableError(RetailerError):
    """Raised when retailer API is unavailable"""
    pass