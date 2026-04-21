"""
Mock retailer implementation for testing KEEPTHECHANGE.com

This provides a mock retailer interface for testing without real API dependencies.
"""

import asyncio
import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from .retailer_base import RetailerInterface, RetailerProduct, RetailerError

logger = logging.getLogger(__name__)


class MockRetailer(RetailerInterface):
    """Mock retailer for testing"""
    
    def __init__(self, name: str = "mock", api_key: Optional[str] = None):
        super().__init__(api_key=api_key)
        self.retailer_name = name
        self._products: Dict[str, Dict[str, Any]] = {}
        self._initialize_mock_products()
    
    def _initialize_mock_products(self):
        """Initialize mock product database"""
        mock_products = [
            {
                "id": "mock-001",
                "name": "Organic Whole Milk",
                "brand": "Organic Valley",
                "category": "dairy",
                "price": 4.99,
                "original_price": 5.99,
                "shipping_cost": 0.0,
                "free_shipping_threshold": 35.0,
                "estimated_delivery_days": 2,
                "in_stock": True,
                "stock_quantity": 50,
                "upc": "123456789012",
                "sku": "OV-MILK-GAL",
                "size": "1 gallon",
                "unit": "gallon",
                "description": "Fresh organic whole milk",
                "image_url": "https://example.com/milk.jpg",
                "retailer_rating": 4.5,
                "product_rating": 4.7
            },
            {
                "id": "mock-002",
                "name": "Whole Wheat Bread",
                "brand": "Nature's Own",
                "category": "bakery",
                "price": 3.49,
                "original_price": 3.99,
                "shipping_cost": 2.99,
                "free_shipping_threshold": 35.0,
                "estimated_delivery_days": 1,
                "in_stock": True,
                "stock_quantity": 100,
                "upc": "234567890123",
                "sku": "NO-BREAD-WW",
                "size": "20 oz",
                "unit": "loaf",
                "description": "100% whole wheat bread",
                "image_url": "https://example.com/bread.jpg",
                "retailer_rating": 4.3,
                "product_rating": 4.5
            },
            {
                "id": "mock-003",
                "name": "Fresh Bananas",
                "brand": None,
                "category": "produce",
                "price": 0.69,
                "original_price": 0.79,
                "shipping_cost": 0.0,
                "free_shipping_threshold": 35.0,
                "estimated_delivery_days": 3,
                "in_stock": True,
                "stock_quantity": 200,
                "upc": "345678901234",
                "sku": "BANANA-LB",
                "size": "1 lb",
                "unit": "pound",
                "description": "Fresh ripe bananas",
                "image_url": "https://example.com/bananas.jpg",
                "retailer_rating": 4.2,
                "product_rating": 4.8
            },
            {
                "id": "mock-004",
                "name": "Cage-Free Eggs",
                "brand": "Happy Hens",
                "category": "dairy",
                "price": 3.99,
                "original_price": 4.49,
                "shipping_cost": 1.99,
                "free_shipping_threshold": 25.0,
                "estimated_delivery_days": 2,
                "in_stock": True,
                "stock_quantity": 75,
                "upc": "456789012345",
                "sku": "HH-EGGS-12",
                "size": "12 count",
                "unit": "dozen",
                "description": "Cage-free large eggs",
                "image_url": "https://example.com/eggs.jpg",
                "retailer_rating": 4.6,
                "product_rating": 4.9
            },
            {
                "id": "mock-005",
                "name": "Ground Beef 80/20",
                "brand": "Premium Beef",
                "category": "meat",
                "price": 5.99,
                "original_price": 6.99,
                "shipping_cost": 3.99,
                "free_shipping_threshold": 50.0,
                "estimated_delivery_days": 1,
                "in_stock": True,
                "stock_quantity": 40,
                "upc": "567890123456",
                "sku": "PB-BEEF-1LB",
                "size": "1 lb",
                "unit": "pound",
                "description": "80% lean ground beef",
                "image_url": "https://example.com/beef.jpg",
                "retailer_rating": 4.4,
                "product_rating": 4.6
            }
        ]
        
        for product in mock_products:
            self._products[product["id"]] = product
        
        # Create UPC index
        self._upc_index = {product["upc"]: product["id"] for product in mock_products if product["upc"]}
        
        logger.info(f"Initialized mock retailer '{self.retailer_name}' with {len(mock_products)} products")
    
    async def authenticate(self) -> bool:
        """Mock authentication - always succeeds"""
        await asyncio.sleep(0.1)  # Simulate API call
        self.is_authenticated = True
        logger.info(f"Mock retailer '{self.retailer_name}' authenticated")
        return True
    
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
        """Mock product search"""
        await asyncio.sleep(0.2)  # Simulate API call
        
        results = []
        query_lower = query.lower()
        
        for product_data in self._products.values():
            # Apply filters
            if category and product_data["category"] != category:
                continue
            
            if brand and product_data["brand"] != brand:
                continue
            
            if min_price is not None and product_data["price"] < min_price:
                continue
            
            if max_price is not None and product_data["price"] > max_price:
                continue
            
            if in_stock_only and not product_data["in_stock"]:
                continue
            
            # Check if product matches query
            matches_query = (
                query_lower in product_data["name"].lower() or
                (product_data["brand"] and query_lower in product_data["brand"].lower()) or
                query_lower in product_data["category"].lower()
            )
            
            if not matches_query and query_lower:  # If query is empty, return all
                continue
            
            # Create RetailerProduct
            product = RetailerProduct(
                retailer=self.retailer_name,
                product_id=product_data["id"],
                name=product_data["name"],
                price=product_data["price"],
                original_price=product_data.get("original_price"),
                in_stock=product_data["in_stock"],
                stock_quantity=product_data.get("stock_quantity"),
                shipping_cost=product_data["shipping_cost"],
                free_shipping_threshold=product_data.get("free_shipping_threshold"),
                estimated_delivery_days=product_data.get("estimated_delivery_days"),
                product_url=f"https://mock-retailer.com/products/{product_data['id']}",
                image_url=product_data.get("image_url"),
                description=product_data.get("description"),
                brand=product_data.get("brand"),
                upc=product_data.get("upc"),
                sku=product_data.get("sku"),
                category=product_data.get("category"),
                size=product_data.get("size"),
                unit=product_data.get("unit"),
                retailer_rating=product_data.get("retailer_rating"),
                product_rating=product_data.get("product_rating"),
                review_count=random.randint(10, 1000)
            )
            
            results.append(product)
            
            if len(results) >= limit:
                break
        
        # Sort by relevance (simulated)
        results.sort(key=lambda p: (
            2 if query_lower in p.name.lower() else
            1 if p.brand and query_lower in p.brand.lower() else 0,
            -p.product_rating if p.product_rating else 0
        ), reverse=True)
        
        logger.info(f"Mock search for '{query}' returned {len(results)} results")
        return results
    
    async def get_product_by_id(self, product_id: str) -> Optional[RetailerProduct]:
        """Mock get product by ID"""
        await asyncio.sleep(0.1)  # Simulate API call
        
        product_data = self._products.get(product_id)
        if not product_data:
            return None
        
        # Add some random price variation
        current_price = product_data["price"] * random.uniform(0.95, 1.05)
        
        product = RetailerProduct(
            retailer=self.retailer_name,
            product_id=product_data["id"],
            name=product_data["name"],
            price=round(current_price, 2),
            original_price=product_data.get("original_price"),
            in_stock=product_data["in_stock"],
            stock_quantity=product_data.get("stock_quantity"),
            shipping_cost=product_data["shipping_cost"],
            free_shipping_threshold=product_data.get("free_shipping_threshold"),
            estimated_delivery_days=product_data.get("estimated_delivery_days"),
            product_url=f"https://mock-retailer.com/products/{product_data['id']}",
            image_url=product_data.get("image_url"),
            description=product_data.get("description"),
            brand=product_data.get("brand"),
            upc=product_data.get("upc"),
            sku=product_data.get("sku"),
            category=product_data.get("category"),
            size=product_data.get("size"),
            unit=product_data.get("unit"),
            retailer_rating=product_data.get("retailer_rating"),
            product_rating=product_data.get("product_rating"),
            review_count=random.randint(10, 1000)
        )
        
        return product
    
    async def get_product_by_upc(self, upc: str) -> Optional[RetailerProduct]:
        """Mock get product by UPC"""
        product_id = self._upc_index.get(upc)
        if product_id:
            return await self.get_product_by_id(product_id)
        return None
    
    async def get_shipping_cost(
        self,
        product_id: str,
        quantity: int = 1,
        zip_code: Optional[str] = None
    ) -> float:
        """Mock shipping cost calculation"""
        await asyncio.sleep(0.05)  # Simulate API call
        
        product_data = self._products.get(product_id)
        if not product_data:
            return 0.0
        
        base_shipping = product_data["shipping_cost"]
        
        # Simulate quantity-based shipping
        if quantity > 1:
            base_shipping += (quantity - 1) * 0.5
        
        # Simulate zip code based shipping (simplified)
        if zip_code:
            # East coast gets cheaper shipping
            if zip_code.startswith(("0", "1", "2")):
                base_shipping *= 0.8
            # West coast gets more expensive
            elif zip_code.startswith(("9", "8")):
                base_shipping *= 1.2
        
        return round(base_shipping, 2)
    
    async def estimate_delivery(
        self,
        product_id: str,
        zip_code: str,
        shipping_method: str = "standard"
    ) -> Optional[datetime]:
        """Mock delivery estimation"""
        await asyncio.sleep(0.05)  # Simulate API call
        
        product_data = self._products.get(product_id)
        if not product_data:
            return None
        
        base_days = product_data.get("estimated_delivery_days", 3)
        
        # Adjust based on shipping method
        if shipping_method == "express":
            base_days = max(1, base_days - 2)
        elif shipping_method == "overnight":
            base_days = 1
        
        # Adjust based on zip code (simplified)
        if zip_code:
            # Same region gets faster delivery
            if zip_code.startswith("1"):  # NY area
                base_days = max(1, base_days - 1)
        
        delivery_date = datetime.utcnow() + timedelta(days=base_days)
        return delivery_date
    
    async def batch_get_prices(self, product_ids: List[str]) -> Dict[str, Optional[float]]:
        """Mock batch price lookup"""
        await asyncio.sleep(0.1 * len(product_ids) / 10)  # Simulate batch API call
        
        results = {}
        for product_id in product_ids:
            product = await self.get_product_by_id(product_id)
            results[product_id] = product.price if product else None
        
        return results
    
    def get_retailer_info(self) -> Dict[str, Any]:
        """Get mock retailer information"""
        return {
            "name": self.retailer_name,
            "requires_auth": False,
            "is_authenticated": self.is_authenticated,
            "supports_upc_lookup": True,
            "supports_batch_operations": True,
            "product_count": len(self._products),
            "is_mock": True,
            "description": f"Mock retailer for testing ({len(self._products)} products)"
        }


class MockWalmartRetailer(MockRetailer):
    """Mock Walmart retailer"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="walmart", api_key=api_key)
    
    async def authenticate(self) -> bool:
        """Mock Walmart authentication"""
        await asyncio.sleep(0.15)
        self.is_authenticated = True
        logger.info("Mock Walmart retailer authenticated")
        return True


class MockTargetRetailer(MockRetailer):
    """Mock Target retailer"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="target", api_key=api_key)
        # Adjust some prices to be different from Walmart
        for product_id, product_data in self._products.items():
            # Target is slightly more expensive
            product_data["price"] = round(product_data["price"] * 1.05, 2)
            # But has better shipping
            product_data["shipping_cost"] = max(0, product_data["shipping_cost"] - 1.0)
    
    async def authenticate(self) -> bool:
        """Mock Target authentication"""
        await asyncio.sleep(0.2)
        self.is_authenticated = True
        logger.info("Mock Target retailer authenticated")
        return True


class MockAmazonRetailer(MockRetailer):
    """Mock Amazon retailer"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="amazon", api_key=api_key)
        # Amazon has competitive prices
        for product_id, product_data in self._products.items():
            # Amazon is cheapest but has Prime requirement
            product_data["price"] = round(product_data["price"] * 0.95, 2)
            product_data["free_shipping_threshold"] = None  # Prime has free shipping
            product_data["shipping_cost"] = 0.0 if random.random() > 0.3 else 2.99
    
    async def authenticate(self) -> bool:
        """Mock Amazon authentication"""
        await asyncio.sleep(0.25)
        self.is_authenticated = True
        logger.info("Mock Amazon retailer authenticated")
        return True
    
    async def search_products(self, *args, **kwargs) -> List[RetailerProduct]:
        """Amazon has more products"""
        results = await super().search_products(*args, **kwargs)
        
        # Amazon sometimes has more results
        if kwargs.get("limit", 20) > len(results) and random.random() > 0.5:
            # Add some extra mock products
            extra_products = [
                RetailerProduct(
                    retailer=self.retailer_name,
                    product_id=f"amazon-extra-{i}",
                    name=f"Amazon Exclusive Product {i}",
                    price=random.uniform(5.0, 50.0),
                    original_price=random.uniform(7.0, 60.0),
                    shipping_cost=0.0,
                    free_shipping_threshold=None,
                    estimated_delivery_days=random.randint(1, 3),
                    in_stock=True,
                    product_url=f"https://amazon.com/dp/extra{i}",
                    image_url="https://example.com/placeholder.jpg",
                    description="Amazon exclusive product",
                    retailer_rating=4.8,
                    product_rating=random.uniform(4.0, 5.0)
                )
                for i in range(random.randint(1, 3))
            ]
            results.extend(extra_products)
        
        return results


def create_mock_retailers() -> List[RetailerInterface]:
    """Create a list of mock retailers for testing"""
    return [
        MockWalmartRetailer(),
        MockTargetRetailer(),
        MockAmazonRetailer()
    ]