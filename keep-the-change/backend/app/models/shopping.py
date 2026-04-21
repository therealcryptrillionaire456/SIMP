"""
Shopping models for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ShoppingList(Base):
    """Shopping list model"""
    
    __tablename__ = "shopping_lists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # List details
    name = Column(String(100), nullable=False, default="My Shopping List")
    description = Column(Text, nullable=True)
    
    # Budget and constraints
    budget_limit = Column(Float, nullable=True)  # Maximum user is willing to spend
    max_items = Column(Integer, nullable=True)  # Maximum number of items
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    
    # Optimization preferences
    optimization_strategy = Column(String(50), default="cheapest")  # cheapest, fastest, balanced
    delivery_preference = Column(String(50), default="standard")  # standard, express, pickup
    retailer_preferences = Column(JSON, default=[])  # Preferred retailers
    
    # Status
    status = Column(String(20), default="draft")  # draft, optimizing, ready, purchased, cancelled
    optimization_id = Column(String(100), nullable=True)  # ID from optimization service
    
    # Results
    optimized_total = Column(Float, nullable=True)  # Optimized total price
    estimated_savings = Column(Float, nullable=True)  # Estimated savings vs retail
    estimated_delivery_days = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    optimized_at = Column(DateTime, nullable=True)
    purchased_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="shopping_lists")
    items = relationship("ListItem", back_populates="shopping_list", cascade="all, delete-orphan")
    purchase = relationship("Purchase", back_populates="shopping_list", uselist=False)
    
    def __repr__(self):
        return f"<ShoppingList(id={self.id}, name={self.name}, status={self.status})>"
    
    @property
    def item_count(self) -> int:
        """Get number of items in list"""
        return len(self.items) if self.items else 0
    
    @property
    def is_optimized(self) -> bool:
        """Check if list has been optimized"""
        return self.status in ["ready", "purchased"]


class ListItem(Base):
    """Item in a shopping list"""
    
    __tablename__ = "list_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id = Column(UUID(as_uuid=True), ForeignKey("shopping_lists.id"), nullable=False, index=True)
    
    # Product identification
    product_name = Column(String(255), nullable=False)
    brand = Column(String(100), nullable=True)
    upc = Column(String(20), nullable=True)  # Universal Product Code
    sku = Column(String(100), nullable=True)  # Stock Keeping Unit
    
    # Product details
    category = Column(String(100), nullable=True)  # dairy, produce, meat, etc.
    subcategory = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)  # 16oz, 1lb, etc.
    unit = Column(String(20), nullable=True)  # oz, lb, each, etc.
    
    # User preferences
    quantity = Column(Integer, default=1)
    max_price = Column(Float, nullable=True)  # Maximum price user is willing to pay
    priority = Column(Integer, default=5)  # 1-10 priority level
    notes = Column(Text, nullable=True)  # Additional notes from user
    
    # Dietary restrictions
    dietary_tags = Column(JSON, default=[])  # organic, gluten_free, vegan, etc.
    
    # Status
    status = Column(String(20), default="pending")  # pending, found, not_found, substituted
    
    # Optimization results
    optimized_price = Column(Float, nullable=True)
    optimized_retailer = Column(String(100), nullable=True)
    optimized_product_id = Column(String(100), nullable=True)
    substitution_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shopping_list = relationship("ShoppingList", back_populates="items")
    price_comparisons = relationship("PriceComparison", back_populates="list_item", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ListItem(id={self.id}, product={self.product_name}, quantity={self.quantity})>"
    
    @property
    def total_cost(self) -> Optional[float]:
        """Calculate total cost for this item"""
        if self.optimized_price and self.quantity:
            return self.optimized_price * self.quantity
        return None


class PriceComparison(Base):
    """Price comparison for a list item"""
    
    __tablename__ = "price_comparisons"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("list_items.id"), nullable=False, index=True)
    
    # Retailer information
    retailer = Column(String(100), nullable=False)
    retailer_id = Column(String(100), nullable=True)  # Internal retailer ID
    product_id = Column(String(100), nullable=True)  # Retailer's product ID
    product_url = Column(Text, nullable=True)
    
    # Pricing
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)  # Original price before discount
    currency = Column(String(3), default="USD")
    unit_price = Column(Float, nullable=True)  # Price per unit
    unit = Column(String(20), nullable=True)  # Price unit (per oz, per lb, etc.)
    
    # Availability
    in_stock = Column(Boolean, default=True)
    stock_quantity = Column(Integer, nullable=True)
    availability_status = Column(String(50), nullable=True)  # in_stock, low_stock, out_of_stock
    
    # Shipping
    shipping_cost = Column(Float, default=0.0)
    free_shipping_threshold = Column(Float, nullable=True)
    estimated_delivery_days = Column(Integer, nullable=True)
    delivery_date = Column(DateTime, nullable=True)
    
    # Additional costs
    tax_rate = Column(Float, nullable=True)
    estimated_tax = Column(Float, nullable=True)
    
    # Product details
    product_title = Column(String(255), nullable=True)
    product_image = Column(Text, nullable=True)
    product_description = Column(Text, nullable=True)
    
    # Quality metrics
    retailer_rating = Column(Float, nullable=True)
    product_rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    
    # Comparison metadata
    is_best_price = Column(Boolean, default=False)
    savings_vs_average = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    list_item = relationship("ListItem", back_populates="price_comparisons")
    
    def __repr__(self):
        return f"<PriceComparison(item_id={self.item_id}, retailer={self.retailer}, price={self.price})>"
    
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


class ProductCatalog(Base):
    """Product catalog for caching and search"""
    
    __tablename__ = "product_catalog"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Product identification
    upc = Column(String(20), nullable=True, index=True)
    sku = Column(String(100), nullable=True, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    brand = Column(String(100), nullable=True, index=True)
    
    # Product details
    category = Column(String(100), nullable=True, index=True)
    subcategory = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    size = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=True)
    
    # Images
    image_url = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    
    # Nutritional information (for food items)
    nutritional_info = Column(JSON, nullable=True)
    
    # Dietary tags
    dietary_tags = Column(JSON, default=[])
    
    # Price history
    average_price = Column(Float, nullable=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    price_history = Column(JSON, nullable=True)  # Array of {price, date, retailer}
    
    # Popularity metrics
    search_count = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_price_update = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ProductCatalog(id={self.id}, product={self.product_name})>"
    
    @property
    def current_price_range(self) -> dict:
        """Get current price range"""
        return {
            "average": self.average_price,
            "min": self.min_price,
            "max": self.max_price
        }