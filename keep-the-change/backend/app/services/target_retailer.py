"""
Target API retailer integration for KEEPTHECHANGE.com

This module provides integration with Target's API for product search,
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


class TargetRetailer(RetailerInterface):
    """Target API retailer integration"""
    
    BASE_URL = "https://redsky.target.com"
    SEARCH_ENDPOINT = "/redsky_aggregations/v1/web/plp_search_v1"
    PRODUCT_ENDPOINT = "/redsky_aggregations/v1/web/pdp_client_v1"
    STORE_LOCATOR_ENDPOINT = "/v3/stores"
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        super().__init__(api_key=api_key, api_secret=api_secret)
        self.retailer_name = "target"
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_remaining = 100  # Default rate limit
        self._rate_limit_reset = datetime.utcnow()
        
    async def authenticate(self) -> bool:
        """Authenticate with Target API"""
        try:
            # Target API uses API key in query parameters
            # We'll test authentication with a simple search
            if not self.api_key:
                logger.error("Target API key not configured")
                self.is_authenticated = False
                return False
            
            # Create session if not exists
            if not self.session:
                self.session = aiohttp.ClientSession(
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "KEEPTHECHANGE.com/1.0"
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            
            # Test authentication with a simple search
            test_params = {
                "key": self.api_key,
                "channel": "WEB",
                "count": "1",
                "default_purchasability_filter": "true",
                "include_sponsored": "true",
                "keyword": "test",
                "page": "/s/test",
                "platform": "desktop",
                "pricing_store_id": "911",
                "scheduled_delivery_store_id": "911",
                "store_ids": "911,2791,1946,3330",
                "visitor_id": "test_visitor"
            }
            
            async with self.session.get(
                f"{self.BASE_URL}{self.SEARCH_ENDPOINT}",
                params=test_params
            ) as response:
                if response.status == 200:
                    self.is_authenticated = True
                    logger.info("Successfully authenticated with Target API")
                    return True
                elif response.status == 401:
                    logger.error("Target API authentication failed: Invalid API key")
                    self.is_authenticated = False
                    return False
                else:
                    # Other errors might be temporary
                    logger.warning(f"Target API test returned status {response.status}")
                    self.is_authenticated = True  # Assume authenticated for now
                    return True
                    
        except Exception as e:
            logger.error(f"Error authenticating with Target API: {str(e)}")
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
        """Search for products on Target"""
        try:
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Prepare search parameters
            params = {
                "key": self.api_key,
                "channel": "WEB",
                "count": str(min(limit, 100)),  # Target max is 100
                "default_purchasability_filter": "true",
                "include_sponsored": "true",
                "keyword": query,
                "page": f"/s/{quote(query)}",
                "platform": "desktop",
                "pricing_store_id": "911",  # Default store ID
                "scheduled_delivery_store_id": "911",
                "store_ids": "911,2791,1946,3330",  # Common store IDs
                "visitor_id": "ktc_visitor",
                "sort_by": self._convert_sort(sort_by)
            }
            
            if category:
                params["category"] = self._convert_category(category)
            
            if brand:
                params["brand"] = brand
            
            if min_price is not None:
                params["min_price"] = str(min_price)
            
            if max_price is not None:
                params["max_price"] = str(max_price)
            
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
                    raise RateLimitError("Target API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Target API authentication failed")
                else:
                    raise RetailerError(f"Target API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Target API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Target API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error searching Target products: {str(e)}")
            raise RetailerError(f"Error searching Target products: {str(e)}")
    
    async def get_product_by_id(self, product_id: str) -> Optional[RetailerProduct]:
        """Get product by Target TCN (Target Catalog Number)"""
        try:
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Prepare product parameters
            params = {
                "key": self.api_key,
                "tcin": product_id,
                "pricing_store_id": "911",
                "has_size_context": "true",
                "has_color_context": "true",
                "store_ids": "911,2791,1946,3330",
                "visitor_id": "ktc_visitor",
                "channel": "WEB",
                "platform": "desktop"
            }
            
            # Make API request
            async with self.session.get(
                f"{self.BASE_URL}{self.PRODUCT_ENDPOINT}",
                params=params
            ) as response:
                await self._handle_rate_limit(response)
                
                if response.status == 200:
                    data = await response.json()
                    return self._parse_product_data(data)
                elif response.status == 404:
                    raise ProductNotFoundError(f"Product {product_id} not found on Target")
                elif response.status == 429:
                    raise RateLimitError("Target API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Target API authentication failed")
                else:
                    raise RetailerError(f"Target API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Target API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Target API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting Target product: {str(e)}")
            raise RetailerError(f"Error getting Target product: {str(e)}")
    
    async def get_product_by_upc(self, upc: str) -> Optional[RetailerProduct]:
        """Get product by UPC code"""
        try:
            # Target API doesn't have direct UPC lookup
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
            logger.error(f"Error getting Target product by UPC: {str(e)}")
            raise RetailerError(f"Error getting Target product by UPC: {str(e)}")
    
    async def get_product_price(self, product_id: str) -> Optional[float]:
        """Get current price for a product"""
        try:
            product = await self.get_product_by_id(product_id)
            return product.price if product else None
            
        except ProductNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting Target product price: {str(e)}")
            raise RetailerError(f"Error getting Target product price: {str(e)}")
    
    async def check_availability(self, product_id: str) -> bool:
        """Check if product is in stock"""
        try:
            product = await self.get_product_by_id(product_id)
            return product.in_stock if product else False
            
        except ProductNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking Target product availability: {str(e)}")
            raise RetailerError(f"Error checking Target product availability: {str(e)}")
    
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
            logger.error(f"Error batch getting Target prices: {str(e)}")
            raise RetailerError(f"Error batch getting Target prices: {str(e)}")
    
    async def get_shipping_cost(
        self,
        product_id: str,
        quantity: int = 1,
        zip_code: Optional[str] = None,
        shipping_method: str = "standard"
    ) -> float:
        """Get shipping cost for a product"""
        try:
            # Target API doesn't provide shipping cost directly
            # We'll use estimated shipping based on product price
            product = await self.get_product_by_id(product_id)
            if not product:
                return 5.99  # Default shipping cost
            
            # Estimate shipping based on product price
            if product.price >= 35.0:
                return 0.0  # Free shipping over $35
            
            # Target RedCard members get free shipping
            # For non-members, estimate shipping
            if shipping_method == "express":
                return 9.99
            elif shipping_method == "standard":
                return 5.99
            elif shipping_method == "store_pickup":
                return 0.0
            else:
                return 5.99
            
        except Exception as e:
            logger.error(f"Error getting Target shipping cost: {str(e)}")
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
            elif shipping_method == "store_pickup":
                days = 0  # Same day pickup
            
            # Adjust based on product availability
            if not product.in_stock:
                days += 5  # Additional days for out of stock items
            
            return datetime.utcnow() + timedelta(days=days)
            
        except Exception as e:
            logger.error(f"Error estimating Target delivery: {str(e)}")
            return None
    
    async def get_retailer_info(self) -> Dict[str, Any]:
        """Get retailer information"""
        return {
            "name": "Target",
            "retailer_id": "target",
            "description": "Target - Expect More. Pay Less.",
            "logo_url": "https://corporate.target.com/_media/TargetCorp/logo/Target_Bullseye-Logo_Red.svg",
            "website": "https://www.target.com",
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
            "average_delivery_days": 3,
            "supports_store_pickup": True
        }
    
    def _convert_sort(self, sort_by: str) -> str:
        """Convert internal sort to Target API sort parameter"""
        sort_map = {
            "relevance": "relevance",
            "price_low": "price-low-to-high",
            "price_high": "price-high-to-low",
            "rating": "highest-rated",
            "newest": "newest",
            "best_seller": "bestseller"
        }
        return sort_map.get(sort_by, "relevance")
    
    def _convert_category(self, category: str) -> str:
        """Convert internal category to Target category"""
        # Simplified category mapping
        category_map = {
            "dairy": "5xt1a",
            "produce": "5xt1a",
            "meat": "5xt1a",
            "bakery": "5xt1a",
            "beverages": "5xt1a",
            "snacks": "5xt1a",
            "frozen": "5xt1a",
            "household": "5xtg6",
            "electronics": "5xt0r",
            "clothing": "5xt0n",
            "home": "5xt0p",
            "toys": "5xt10"
        }
        return category_map.get(category.lower(), "5xt1a")  # Default to grocery
    
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
            logger.warning(f"Target API rate limit low: {self._rate_limit_remaining} remaining")
    
    def _parse_search_results(self, data: Dict[str, Any]) -> List[RetailerProduct]:
        """Parse Target API search results"""
        products = []
        
        try:
            # Extract search results from response
            search_results = data.get("data", {}).get("search", {})
            products_data = search_results.get("products", [])
            
            for item in products_data:
                try:
                    product = self._parse_product_data(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Error parsing Target product: {str(e)}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Error parsing Target search results: {str(e)}")
            return []
    
    def _parse_product_data(self, data: Dict[str, Any]) -> Optional[RetailerProduct]:
        """Parse Target API product data"""
        try:
            # Extract basic product information
            item_id = str(data.get("tcin", ""))
            if not item_id:
                return None
            
            product_info = data.get("item", {})
            price_info = data.get("price", {})
            
            name = product_info.get("product_description", {}).get("title", "")
            brand = product_info.get("primary_brand", {}).get("name", "")
            
            # Extract pricing
            current_price = price_info.get("current_retail")
            if not current_price:
                return None
            
            price = float(current_price)
            
            # Extract original price if available
            original_price = None
            formatted_price = price_info.get("formatted_current_price", "")
            if "was" in formatted_price.lower():
                # Try to extract original price from formatted string
                import re
                match = re.search(r'was\s*\$?(\d+\.?\d*)', formatted_price, re.IGNORECASE)
                if match:
                    original_price = float(match.group(1))
            
            # Extract category
            category_node = product_info.get("product_classification", {}).get("category", {})
            category = category_node.get("name", "")
            
            # Extract availability
            fulfillment = data.get("fulfillment", {})
            availability_status = fulfillment.get("availability_status", "")
            in_stock = availability_status.lower() in ["in_stock", "limited_stock"]
            
            # Extract product details
            upc = product_info.get("upc", "")
            sku = product_info.get("dpci", "")  # Target's internal SKU
            
            # Extract ratings
            ratings = data.get("ratings_and_reviews", {})
            customer_rating = ratings.get("average_overall_rating", 0.0)
            num_reviews = ratings.get("total_review_count", 0)
            
            # Extract shipping info
            shipping_info = fulfillment.get("shipping_options", {})
            free_shipping = shipping_info.get("availability_status") == "IN_STOCK"
            shipping_cost = 0.0 if free_shipping else 5.99
            
            # Extract product attributes
            attributes = product_info.get("product_description", {})
            size = attributes.get("size", "")
            unit = attributes.get("unit", "")
            
            # Extract images
            images = product_info.get("enrichment", {}).get("images", [])
            image_url = images[0].get("base_url", "") if images else ""
            
            # Create RetailerProduct
            return RetailerProduct(
                retailer_id="target",
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
                stock_quantity=100 if in_stock else 0,  # Default quantity
                upc=upc,
                sku=sku,
                size=size,
                unit=unit,
                description=attributes.get("downstream_description", ""),
                image_url=image_url,
                product_url=f"https://www.target.com/p/{item_id}",
                retailer_rating=4.3,  # Target average rating
                product_rating=customer_rating,
                review_count=num_reviews
            )
            
        except Exception as e:
            logger.error(f"Error parsing Target product data: {str(e)}")
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


# Factory function to create Target retailer
def create_target_retailer(api_key: str) -> TargetRetailer:
    """Create a Target retailer instance"""
    return TargetRetailer(api_key=api_key)