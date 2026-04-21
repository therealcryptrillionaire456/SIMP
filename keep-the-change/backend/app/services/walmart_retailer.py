"""
Walmart API retailer integration for KEEPTHECHANGE.com

This module provides integration with Walmart's Open API for product search,
pricing, and availability.
"""

import asyncio
import aiohttp
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from urllib.parse import urlencode, quote

from .retailer_base import (
    RetailerInterface, 
    RetailerProduct, 
    RetailerError,
    AuthenticationError,
    ProductNotFoundError,
    RateLimitError,
    RetailerUnavailableError
)

logger = logging.getLogger(__name__)


class WalmartRetailer(RetailerInterface):
    """Walmart API retailer integration"""
    
    BASE_URL = "https://developer.api.walmart.com/api-proxy/service/affil"
    SEARCH_ENDPOINT = "/product/v3/products"
    PRODUCT_ENDPOINT = "/product/v3/items/{item_id}"
    RECOMMENDATIONS_ENDPOINT = "/product/v3/nbp"
    TRENDING_ENDPOINT = "/product/v3/trends"
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        super().__init__(api_key=api_key, api_secret=api_secret)
        self.retailer_name = "walmart"
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_remaining = 100  # Default rate limit
        self._rate_limit_reset = datetime.utcnow()
        
    async def authenticate(self) -> bool:
        """Authenticate with Walmart API"""
        try:
            # Walmart API uses API key in headers
            # We'll test authentication with a simple search
            if not self.api_key:
                logger.error("Walmart API key not configured")
                self.is_authenticated = False
                return False
            
            # Create session if not exists
            if not self.session:
                self.session = aiohttp.ClientSession(
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "application/json",
                        "User-Agent": "KEEPTHECHANGE.com/1.0"
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            
            # Test authentication with a simple search
            test_params = {
                "query": "test",
                "format": "json",
                "count": 1
            }
            
            async with self.session.get(
                f"{self.BASE_URL}{self.SEARCH_ENDPOINT}",
                params=test_params
            ) as response:
                if response.status == 200:
                    self.is_authenticated = True
                    logger.info("Successfully authenticated with Walmart API")
                    return True
                elif response.status == 401:
                    logger.error("Walmart API authentication failed: Invalid API key")
                    self.is_authenticated = False
                    return False
                else:
                    # Other errors might be temporary
                    logger.warning(f"Walmart API test returned status {response.status}")
                    self.is_authenticated = True  # Assume authenticated for now
                    return True
                    
        except Exception as e:
            logger.error(f"Error authenticating with Walmart API: {str(e)}")
            self.is_authenticated = False
            return False
    
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = True,
        sort_by: str = "relevance",
        limit: int = 50
    ) -> List[RetailerProduct]:
        """Search for products on Walmart"""
        try:
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Prepare search parameters
            params = {
                "query": query,
                "format": "json",
                "count": min(limit, 100),  # Walmart max is 100
                "sort": self._convert_sort(sort_by),
                "responseGroup": "full"
            }
            
            if category:
                params["categoryId"] = self._convert_category(category)
            
            if brand:
                params["brand"] = brand
            
            if min_price is not None:
                params["minPrice"] = min_price
            
            if max_price is not None:
                params["maxPrice"] = max_price
            
            # Make API request
            async with self.session.get(
                f"{self.BASE_URL}{self.SEARCH_ENDPOINT}",
                params=params
            ) as response:
                await self._handle_rate_limit(response)
                
                if response.status == 200:
                    data = await response.json()
                    return self._parse_search_results(data)
                elif response.status == 404:
                    return []  # No products found
                elif response.status == 429:
                    raise RateLimitError("Walmart API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Walmart API authentication failed")
                else:
                    raise RetailerError(f"Walmart API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Walmart API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Walmart API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error searching Walmart products: {str(e)}")
            raise RetailerError(f"Error searching Walmart products: {str(e)}")
    
    async def get_product_by_id(self, product_id: str) -> Optional[RetailerProduct]:
        """Get product by Walmart item ID"""
        try:
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Make API request
            async with self.session.get(
                f"{self.BASE_URL}{self.PRODUCT_ENDPOINT.format(item_id=product_id)}",
                params={"format": "json"}
            ) as response:
                await self._handle_rate_limit(response)
                
                if response.status == 200:
                    data = await response.json()
                    return self._parse_product_data(data)
                elif response.status == 404:
                    raise ProductNotFoundError(f"Product {product_id} not found on Walmart")
                elif response.status == 429:
                    raise RateLimitError("Walmart API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Walmart API authentication failed")
                else:
                    raise RetailerError(f"Walmart API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Walmart API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Walmart API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting Walmart product: {str(e)}")
            raise RetailerError(f"Error getting Walmart product: {str(e)}")
    
    async def get_product_by_upc(self, upc: str) -> Optional[RetailerProduct]:
        """Get product by UPC code"""
        try:
            # Walmart API doesn't have direct UPC lookup in public API
            # We'll search by UPC as query
            products = await self.search_products(
                query=upc,
                limit=10
            )
            
            # Find product with matching UPC
            for product in products:
                if product.upc == upc:
                    return product
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Walmart product by UPC: {str(e)}")
            raise RetailerError(f"Error getting Walmart product by UPC: {str(e)}")
    
    async def get_product_price(self, product_id: str) -> Optional[float]:
        """Get current price for a product"""
        try:
            product = await self.get_product_by_id(product_id)
            return product.price if product else None
            
        except ProductNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting Walmart product price: {str(e)}")
            raise RetailerError(f"Error getting Walmart product price: {str(e)}")
    
    async def check_availability(self, product_id: str) -> bool:
        """Check if product is in stock"""
        try:
            product = await self.get_product_by_id(product_id)
            return product.in_stock if product else False
            
        except ProductNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking Walmart product availability: {str(e)}")
            raise RetailerError(f"Error checking Walmart product availability: {str(e)}")
    
    async def batch_get_prices(self, product_ids: List[str]) -> Dict[str, Optional[float]]:
        """Get prices for multiple products"""
        try:
            results = {}
            # Process in batches to avoid rate limiting
            batch_size = 10
            for i in range(0, len(product_ids), batch_size):
                batch = product_ids[i:i + batch_size]
                
                # Process batch concurrently
                tasks = []
                for product_id in batch:
                    task = self.get_product_price(product_id)
                    tasks.append(task)
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for j, result in enumerate(batch_results):
                    product_id = batch[j]
                    if isinstance(result, Exception):
                        logger.warning(f"Error getting price for {product_id}: {result}")
                        results[product_id] = None
                    else:
                        results[product_id] = result
                
                # Rate limiting delay
                if i + batch_size < len(product_ids):
                    await asyncio.sleep(0.5)  # 500ms delay between batches
            
            return results
            
        except Exception as e:
            logger.error(f"Error batch getting Walmart prices: {str(e)}")
            raise RetailerError(f"Error batch getting Walmart prices: {str(e)}")
    
    async def get_shipping_cost(
        self,
        product_id: str,
        quantity: int = 1,
        zip_code: Optional[str] = None,
        shipping_method: str = "standard"
    ) -> float:
        """Get shipping cost for a product"""
        try:
            # Walmart API doesn't provide shipping cost directly in public API
            # We'll use estimated shipping based on product price and category
            product = await self.get_product_by_id(product_id)
            if not product:
                return 5.99  # Default shipping cost
            
            # Estimate shipping based on product price
            if product.price >= 35.0:
                return 0.0  # Free shipping over $35
            
            # Estimate based on product category
            category = product.category.lower() if product.category else ""
            if "grocery" in category or "food" in category:
                return 7.99  # Grocery shipping
            elif "electronics" in category:
                return 9.99  # Electronics shipping
            else:
                return 5.99  # Standard shipping
            
        except Exception as e:
            logger.error(f"Error getting Walmart shipping cost: {str(e)}")
            return 5.99  # Default shipping cost
    
    async def estimate_delivery(
        self,
        product_id: str,
        quantity: int = 1,
        zip_code: Optional[str] = None,
        shipping_method: str = "standard"
    ) -> Optional[datetime]:
        """Estimate delivery date"""
        try:
            product = await self.get_product_by_id(product_id)
            if not product:
                return None
            
            # Estimate delivery based on shipping method
            days = 3  # Default delivery days
            if shipping_method == "express":
                days = 1
            elif shipping_method == "standard":
                days = 3
            elif shipping_method == "economy":
                days = 7
            
            # Adjust based on product availability
            if not product.in_stock:
                days += 3  # Additional days for out of stock items
            
            return datetime.utcnow() + timedelta(days=days)
            
        except Exception as e:
            logger.error(f"Error estimating Walmart delivery: {str(e)}")
            return None
    
    async def get_retailer_info(self) -> Dict[str, Any]:
        """Get retailer information"""
        return {
            "name": "Walmart",
            "retailer_id": "walmart",
            "description": "Walmart - Save Money. Live Better.",
            "logo_url": "https://corporate.walmart.com/content/dam/corporate/images/logos/walmart-logo-blue.png",
            "website": "https://www.walmart.com",
            "supports_direct_checkout": False,
            "requires_api_key": True,
            "is_authenticated": self.is_authenticated,
            "rate_limit_remaining": self._rate_limit_remaining,
            "supports_categories": True,
            "supports_brand_filter": True,
            "supports_price_filter": True,
            "max_search_limit": 100,
            "supports_upc_lookup": True,
            "free_shipping_threshold": 35.0,
            "average_delivery_days": 3
        }
    
    def _convert_sort(self, sort_by: str) -> str:
        """Convert internal sort to Walmart API sort parameter"""
        sort_map = {
            "relevance": "relevance",
            "price_low": "price",
            "price_high": "price",
            "rating": "customerRating",
            "newest": "date",
            "best_seller": "bestseller"
        }
        return sort_map.get(sort_by, "relevance")
    
    def _convert_category(self, category: str) -> str:
        """Convert internal category to Walmart category ID"""
        # Simplified category mapping
        category_map = {
            "dairy": "976759",
            "produce": "976759",
            "meat": "976760",
            "bakery": "976762",
            "beverages": "976763",
            "snacks": "976764",
            "frozen": "976766",
            "household": "1115193",
            "electronics": "3944",
            "clothing": "5438",
            "home": "4044",
            "toys": "4171"
        }
        return category_map.get(category.lower(), "")
    
    async def _handle_rate_limit(self, response: aiohttp.ClientResponse):
        """Handle rate limiting headers"""
        # Extract rate limit headers
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        
        if remaining:
            self._rate_limit_remaining = int(remaining)
        
        if reset:
            # Reset time is typically Unix timestamp
            try:
                reset_time = int(reset)
                self._rate_limit_reset = datetime.fromtimestamp(reset_time)
            except (ValueError, TypeError):
                pass
        
        # Log rate limit status
        if self._rate_limit_remaining < 20:
            logger.warning(f"Walmart API rate limit low: {self._rate_limit_remaining} remaining")
    
    def _parse_search_results(self, data: Dict[str, Any]) -> List[RetailerProduct]:
        """Parse Walmart API search results"""
        products = []
        
        try:
            items = data.get("items", [])
            for item in items:
                try:
                    product = self._parse_product_data(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Error parsing Walmart product: {str(e)}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Error parsing Walmart search results: {str(e)}")
            return []
    
    def _parse_product_data(self, data: Dict[str, Any]) -> Optional[RetailerProduct]:
        """Parse Walmart API product data"""
        try:
            # Extract basic product information
            item_id = str(data.get("itemId", ""))
            name = data.get("name", "")
            brand = data.get("brandName", "")
            
            # Extract pricing
            price_data = data.get("salePrice") or data.get("price")
            if not price_data:
                return None
            
            price = float(price_data)
            
            # Extract original price if available
            original_price = None
            msrp = data.get("msrp")
            if msrp:
                original_price = float(msrp)
            
            # Extract category
            category_path = data.get("categoryPath", "")
            category = category_path.split("/")[-1] if category_path else ""
            
            # Extract availability
            stock = data.get("stock", "Available")
            in_stock = stock.lower() != "not available"
            stock_quantity = data.get("availableOnlineStoreQuantity", 0)
            
            # Extract product details
            upc = data.get("upc", "")
            sku = data.get("sku", "")
            
            # Extract ratings
            customer_rating = data.get("customerRating", 0.0)
            num_reviews = data.get("numReviews", 0)
            
            # Extract shipping info
            free_shipping = data.get("freeShipping", False)
            shipping_cost = 0.0 if free_shipping else 5.99
            
            # Extract product attributes
            attributes = data.get("attributes", {})
            size = attributes.get("size", "")
            unit = attributes.get("unit", "")
            
            # Extract images
            images = data.get("imageEntities", [])
            image_url = images[0].get("largeImageUrl", "") if images else ""
            
            # Create RetailerProduct
            return RetailerProduct(
                retailer_id="walmart",
                product_id=item_id,
                name=name,
                brand=brand,
                category=category,
                price=price,
                original_price=original_price,
                shipping_cost=shipping_cost,
                free_shipping_threshold=35.0 if free_shipping else None,
                estimated_delivery_days=3,
                in_stock=in_stock,
                stock_quantity=stock_quantity,
                upc=upc,
                sku=sku,
                size=size,
                unit=unit,
                description=data.get("shortDescription", ""),
                image_url=image_url,
                product_url=f"https://www.walmart.com/ip/{item_id}",
                retailer_rating=4.5,  # Walmart average rating
                product_rating=customer_rating,
                review_count=num_reviews
            )
            
        except Exception as e:
            logger.error(f"Error parsing Walmart product data: {str(e)}")
            return None
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def __del__(self):
        """Ensure session is closed"""
        if self.session and not self.session.closed:
            asyncio.create_task(self.close())


# Factory function to create Walmart retailer
def create_walmart_retailer(api_key: str) -> WalmartRetailer:
    """Create a Walmart retailer instance"""
    return WalmartRetailer(api_key=api_key)