"""
Amazon API retailer integration for KEEPTHECHANGE.com

This module provides integration with Amazon's Product Advertising API
for product search, pricing, and availability.
"""

import asyncio
import aiohttp
import json
import hmac
import hashlib
import base64
import urllib.parse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from xml.etree import ElementTree

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


class AmazonRetailer(RetailerInterface):
    """Amazon Product Advertising API retailer integration"""
    
    # Different endpoints for different regions
    ENDPOINTS = {
        "US": "https://webservices.amazon.com",
        "CA": "https://webservices.amazon.ca",
        "UK": "https://webservices.amazon.co.uk",
        "DE": "https://webservices.amazon.de",
        "FR": "https://webservices.amazon.fr",
        "JP": "https://webservices.amazon.co.jp",
        "IT": "https://webservices.amazon.it",
        "ES": "https://webservices.amazon.es",
        "AU": "https://webservices.amazon.com.au",
        "BR": "https://webservices.amazon.com.br",
        "MX": "https://webservices.amazon.com.mx"
    }
    
    def __init__(self, api_key: str, api_secret: str, associate_tag: str, region: str = "US"):
        super().__init__(api_key=api_key, api_secret=api_secret)
        self.retailer_name = "amazon"
        self.associate_tag = associate_tag
        self.region = region.upper()
        self.endpoint = self.ENDPOINTS.get(self.region, self.ENDPOINTS["US"])
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_remaining = 100  # Default rate limit
        self._rate_limit_reset = datetime.utcnow()
        
    async def authenticate(self) -> bool:
        """Authenticate with Amazon API"""
        try:
            # Amazon API requires API key, secret, and associate tag
            if not self.api_key or not self.api_secret or not self.associate_tag:
                logger.error("Amazon API credentials not fully configured")
                self.is_authenticated = False
                return False
            
            # Create session if not exists
            if not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            
            # Test authentication with a simple item lookup
            test_params = self._build_request_params(
                operation="ItemLookup",
                item_id="B00005N5PF",  # Test ASIN
                response_group="ItemAttributes"
            )
            
            async with self.session.get(
                f"{self.endpoint}/onca/xml",
                params=test_params
            ) as response:
                if response.status == 200:
                    xml_data = await response.text()
                    root = ElementTree.fromstring(xml_data)
                    
                    # Check for errors
                    error = root.find(".//Error")
                    if error is not None:
                        error_code = error.find("Code").text if error.find("Code") is not None else "Unknown"
                        if error_code == "AWS.InvalidAssociate":
                            logger.error("Amazon API authentication failed: Invalid Associate Tag")
                            self.is_authenticated = False
                            return False
                        elif error_code == "AWS.AccessDenied":
                            logger.error("Amazon API authentication failed: Access Denied")
                            self.is_authenticated = False
                            return False
                    
                    self.is_authenticated = True
                    logger.info("Successfully authenticated with Amazon API")
                    return True
                else:
                    logger.warning(f"Amazon API test returned status {response.status}")
                    # Might be temporary error, assume authenticated for now
                    self.is_authenticated = True
                    return True
                    
        except Exception as e:
            logger.error(f"Error authenticating with Amazon API: {str(e)}")
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
        """Search for products on Amazon"""
        try:
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Prepare search parameters
            params = self._build_request_params(
                operation="ItemSearch",
                search_index=self._convert_category(category),
                keywords=query,
                response_group="ItemAttributes,Offers,Images",
                sort=self._convert_sort(sort_by),
                item_page=str(min((limit // 10) + 1, 10)),  # Max 10 pages
                minimum_price=str(int(min_price)) if min_price is not None else None,
                maximum_price=str(int(max_price)) if max_price is not None else None,
                brand=brand,
                availability="Available" if in_stock_only else None
            )
            
            # Make API request
            async with self.session.get(
                f"{self.endpoint}/onca/xml",
                params=params
            ) as response:
                await self._handle_rate_limit(response)
                
                if response.status == 200:
                    xml_data = await response.text()
                    return self._parse_search_results(xml_data)
                elif response.status == 429:
                    raise RateLimitError("Amazon API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Amazon API authentication failed")
                else:
                    raise RetailerError(f"Amazon API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Amazon API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Amazon API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error searching Amazon products: {str(e)}")
            raise RetailerError(f"Error searching Amazon products: {str(e)}")
    
    async def get_product_by_id(self, product_id: str) -> Optional[RetailerProduct]:
        """Get product by Amazon ASIN"""
        try:
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Prepare lookup parameters
            params = self._build_request_params(
                operation="ItemLookup",
                item_id=product_id,
                response_group="ItemAttributes,Offers,Images,Reviews",
                id_type="ASIN"
            )
            
            # Make API request
            async with self.session.get(
                f"{self.endpoint}/onca/xml",
                params=params
            ) as response:
                await self._handle_rate_limit(response)
                
                if response.status == 200:
                    xml_data = await response.text()
                    return self._parse_product_data(xml_data)
                elif response.status == 404:
                    raise ProductNotFoundError(f"Product {product_id} not found on Amazon")
                elif response.status == 429:
                    raise RateLimitError("Amazon API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Amazon API authentication failed")
                else:
                    raise RetailerError(f"Amazon API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Amazon API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Amazon API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting Amazon product: {str(e)}")
            raise RetailerError(f"Error getting Amazon product: {str(e)}")
    
    async def get_product_by_upc(self, upc: str) -> Optional[RetailerProduct]:
        """Get product by UPC code"""
        try:
            # Amazon API supports UPC lookup
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Prepare lookup parameters
            params = self._build_request_params(
                operation="ItemLookup",
                item_id=upc,
                response_group="ItemAttributes,Offers,Images",
                id_type="UPC",
                search_index="All"
            )
            
            # Make API request
            async with self.session.get(
                f"{self.endpoint}/onca/xml",
                params=params
            ) as response:
                await self._handle_rate_limit(response)
                
                if response.status == 200:
                    xml_data = await response.text()
                    return self._parse_product_data(xml_data)
                elif response.status == 404:
                    return None  # Product not found
                elif response.status == 429:
                    raise RateLimitError("Amazon API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Amazon API authentication failed")
                else:
                    raise RetailerError(f"Amazon API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Amazon API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Amazon API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting Amazon product by UPC: {str(e)}")
            raise RetailerError(f"Error getting Amazon product by UPC: {str(e)}")
    
    async def get_product_price(self, product_id: str) -> Optional[float]:
        """Get current price for a product"""
        try:
            product = await self.get_product_by_id(product_id)
            return product.price if product else None
            
        except ProductNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting Amazon product price: {str(e)}")
            raise RetailerError(f"Error getting Amazon product price: {str(e)}")
    
    async def check_availability(self, product_id: str) -> bool:
        """Check if product is in stock"""
        try:
            product = await self.get_product_by_id(product_id)
            return product.in_stock if product else False
            
        except ProductNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking Amazon product availability: {str(e)}")
            raise RetailerError(f"Error checking Amazon product availability: {str(e)}")
    
    async def batch_get_prices(self, product_ids: List[str]) -> Dict[str, Optional[float]]:
        """Get prices for multiple products"""
        try:
            # Amazon API supports batch lookup
            if not self.is_authenticated:
                await self.authenticate()
            
            if not self.session:
                raise RetailerUnavailableError("Session not initialized")
            
            # Prepare batch lookup parameters
            params = self._build_request_params(
                operation="ItemLookup",
                item_id=",".join(product_ids[:10]),  # Max 10 items per request
                response_group="ItemAttributes,Offers",
                id_type="ASIN"
            )
            
            # Make API request
            async with self.session.get(
                f"{self.endpoint}/onca/xml",
                params=params
            ) as response:
                await self._handle_rate_limit(response)
                
                if response.status == 200:
                    xml_data = await response.text()
                    products = self._parse_batch_results(xml_data)
                    
                    # Map results
                    results = {}
                    for product in products:
                        results[product.product_id] = product.price
                    
                    # Fill in missing products
                    for product_id in product_ids:
                        if product_id not in results:
                            results[product_id] = None
                    
                    return results
                elif response.status == 429:
                    raise RateLimitError("Amazon API rate limit exceeded")
                elif response.status == 401:
                    raise AuthenticationError("Amazon API authentication failed")
                else:
                    raise RetailerError(f"Amazon API error: {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetailerUnavailableError("Amazon API timeout")
        except aiohttp.ClientError as e:
            raise RetailerUnavailableError(f"Amazon API connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Error batch getting Amazon prices: {str(e)}")
            raise RetailerError(f"Error batch getting Amazon prices: {str(e)}")
    
    async def get_shipping_cost(
        self,
        product_id: str,
        quantity: int = 1,
        zip_code: Optional[str] = None,
        shipping_method: str = "standard"
    ) -> float:
        """Get shipping cost for a product"""
        try:
            # Amazon Prime offers free shipping
            # For non-Prime, estimate shipping
            product = await self.get_product_by_id(product_id)
            if not product:
                return 5.99  # Default shipping cost
            
            # Check if product is eligible for Prime
            is_prime = False
            try:
                # Try to get product details to check for Prime
                params = self._build_request_params(
                    operation="ItemLookup",
                    item_id=product_id,
                    response_group="Offers"
                )
                
                async with self.session.get(
                    f"{self.endpoint}/onca/xml",
                    params=params
                ) as response:
                    if response.status == 200:
                        xml_data = await response.text()
                        root = ElementTree.fromstring(xml_data)
                        # Check for Prime eligibility
                        prime_eligible = root.find(".//IsEligibleForPrime")
                        if prime_eligible is not None and prime_eligible.text == "1":
                            is_prime = True
            except:
                pass
            
            # Estimate shipping
            if is_prime:
                return 0.0  # Free Prime shipping
            
            if product.price >= 25.0:
                return 0.0  # Free shipping over $25 for non-Prime
            
            if shipping_method == "express":
                return 9.99
            elif shipping_method == "standard":
                return 5.99
            else:
                return 5.99
            
        except Exception as e:
            logger.error(f"Error getting Amazon shipping cost: {str(e)}")
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
            days = 2  # Default delivery days for Prime
            if shipping_method == "express":
                days = 1
            elif shipping_method == "standard":
                days = 3
            elif shipping_method == "free":
                days = 5
            
            # Adjust based on product availability
            if not product.in_stock:
                days += 7  # Additional days for out of stock items
            
            return datetime.utcnow() + timedelta(days=days)
            
        except Exception as e:
            logger.error(f"Error estimating Amazon delivery: {str(e)}")
            return None
    
    async def get_retailer_info(self) -> Dict[str, Any]:
        """Get retailer information"""
        return {
            "name": "Amazon",
            "retailer_id": "amazon",
            "description": "Amazon - Earth's Most Customer-Centric Company",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg",
            "website": f"https://www.amazon.{self.region.lower()}",
            "supports_direct_checkout": False,
            "requires_api_key": True,
            "requires_associate_tag": True,
            "is_authenticated": self.is_authenticated,
            "rate_limit_remaining": self._rate_limit_remaining,
            "supports_categories": True,
            "supports_brand_filter": True,
            "supports_price_filter": True,
            "max_search_limit": 100,
            "supports_upc_lookup": True,
            "free_shipping_threshold": 25.0,
            "average_delivery_days": 2,
            "supports_prime": True,
            "region": self.region
        }
    
    def _build_request_params(self, operation: str, **kwargs) -> Dict[str, str]:
        """Build signed request parameters for Amazon API"""
        # Base parameters
        params = {
            "Service": "AWSECommerceService",
            "AWSAccessKeyId": self.api_key,
            "AssociateTag": self.associate_tag,
            "Operation": operation,
            "Timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Version": "2013-08-01",
            "ResponseGroup": kwargs.get("response_group", "ItemAttributes"),
        }
        
        # Add operation-specific parameters
        if operation == "ItemSearch":
            params.update({
                "SearchIndex": kwargs.get("search_index", "All"),
                "Keywords": kwargs.get("keywords", ""),
                "Sort": kwargs.get("sort", "relevancerank"),
                "ItemPage": kwargs.get("item_page", "1"),
            })
            
            if kwargs.get("minimum_price"):
                params["MinimumPrice"] = kwargs["minimum_price"]
            if kwargs.get("maximum_price"):
                params["MaximumPrice"] = kwargs["maximum_price"]
            if kwargs.get("brand"):
                params["Brand"] = kwargs["brand"]
            if kwargs.get("availability"):
                params["Availability"] = kwargs["availability"]
                
        elif operation == "ItemLookup":
            params.update({
                "ItemId": kwargs.get("item_id", ""),
                "IdType": kwargs.get("id_type", "ASIN"),
                "SearchIndex": kwargs.get("search_index", "All"),
            })
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        # Sort parameters
        sorted_params = sorted(params.items())
        
        # Create canonical query string
        canonical_query_string = "&".join(
            f"{urllib.parse.quote(key, safe='')}={urllib.parse.quote(str(value), safe='')}"
            for key, value in sorted_params
        )
        
        # Create string to sign
        host = urllib.parse.urlparse(self.endpoint).hostname
        string_to_sign = f"GET\n{host}\n/onca/xml\n{canonical_query_string}"
        
        # Calculate signature
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Add signature to parameters
        params["Signature"] = signature
        
        return params
    
    def _convert_sort(self, sort_by: str) -> str:
        """Convert internal sort to Amazon API sort parameter"""
        sort_map = {
            "relevance": "relevancerank",
            "price_low": "price",
            "price_high": "-price",
            "rating": "reviewrank",
            "newest": "date-desc-rank",
            "best_seller": "salesrank"
        }
        return sort_map.get(sort_by, "relevancerank")
    
    def _convert_category(self, category: str) -> str:
        """Convert internal category to Amazon search index"""
        # Amazon search indexes
        category_map = {
            "dairy": "Grocery",
            "produce": "Grocery",
            "meat": "Grocery",
            "bakery": "Grocery",
            "beverages": "Grocery",
            "snacks": "Grocery",
            "frozen": "Grocery",
            "household": "HomeGarden",
            "electronics": "Electronics",
            "clothing": "Fashion",
            "home": "HomeImprovement",
            "toys": "Toys",
            "books": "Books",
            "movies": "Movies",
            "music": "Music",
            "software": "Software",
            "video_games": "VideoGames",
            "sports": "SportingGoods",
            "beauty": "Beauty",
            "health": "HealthPersonalCare",
            "automotive": "Automotive",
            "industrial": "Industrial"
        }
        return category_map.get(category.lower(), "All")
    
    async def _handle_rate_limit(self, response: aiohttp.ClientResponse):
        """Handle rate limiting"""
        # Amazon API doesn't provide rate limit headers in response
        # We'll implement conservative rate limiting
        self._rate_limit_remaining -= 1
        
        # Log rate limit status
        if self._rate_limit_remaining < 20:
            logger.warning(f"Amazon API rate limit low: {self._rate_limit_remaining} remaining")
        
        # Reset rate limit after 1 second (simulating 1 request per second)
        self._rate_limit_reset = datetime.utcnow() + timedelta(seconds=1)
    
    def _parse_search_results(self, xml_data: str) -> List[RetailerProduct]:
        """Parse Amazon API search results"""
        products = []
        
        try:
            root = ElementTree.fromstring(xml_data)
            
            # Check for errors
            error = root.find(".//Error")
            if error is not None:
                error_msg = error.find("Message").text if error.find("Message") is not None else "Unknown error"
                raise RetailerError(f"Amazon API error: {error_msg}")
            
            # Extract items
            items = root.findall(".//Item")
            for item in items:
                try:
                    product = self._parse_item_xml(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Error parsing Amazon product: {str(e)}")
                    continue
            
            return products
            
        except ElementTree.ParseError as e:
            logger.error(f"Error parsing Amazon XML response: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Amazon search results: {str(e)}")
            return []
    
    def _parse_product_data(self, xml_data: str) -> Optional[RetailerProduct]:
        """Parse Amazon API product data"""
        try:
            root = ElementTree.fromstring(xml_data)
            
            # Check for errors
            error = root.find(".//Error")
            if error is not None:
                error_msg = error.find("Message").text if error.find("Message") is not None else "Unknown error"
                if "not found" in error_msg.lower():
                    raise ProductNotFoundError(f"Product not found on Amazon")
                raise RetailerError(f"Amazon API error: {error_msg}")
            
            # Extract item
            item = root.find(".//Item")
            if item is None:
                return None
            
            return self._parse_item_xml(item)
            
        except ElementTree.ParseError as e:
            logger.error(f"Error parsing Amazon XML response: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error parsing Amazon product data: {str(e)}")
            return None
    
    def _parse_batch_results(self, xml_data: str) -> List[RetailerProduct]:
        """Parse Amazon API batch results"""
        products = []
        
        try:
            root = ElementTree.fromstring(xml_data)
            
            # Check for errors
            error = root.find(".//Error")
            if error is not None:
                error_msg = error.find("Message").text if error.find("Message") is not None else "Unknown error"
                raise RetailerError(f"Amazon API error: {error_msg}")
            
            # Extract items
            items = root.findall(".//Item")
            for item in items:
                try:
                    product = self._parse_item_xml(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Error parsing Amazon product: {str(e)}")
                    continue
            
            return products
            
        except ElementTree.ParseError as e:
            logger.error(f"Error parsing Amazon XML response: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Amazon batch results: {str(e)}")
            return []
    
    def _parse_item_xml(self, item: ElementTree.Element) -> Optional[RetailerProduct]:
        """Parse item XML element"""
        try:
            # Extract basic information
            asin = item.find("ASIN")
            if asin is None or asin.text is None:
                return None
            
            item_attributes = item.find("ItemAttributes")
            if item_attributes is None:
                return None
            
            # Extract title
            title = item_attributes.find("Title")
            if title is None or title.text is None:
                return None
            
            # Extract brand
            brand = item_attributes.find("Brand")
            brand_name = brand.text if brand is not None else ""
            
            # Extract category
            product_group = item_attributes.find("ProductGroup")
            category = product_group.text if product_group is not None else ""
            
            # Extract UPC
            upc = item_attributes.find("UPC")
            upc_code = upc.text if upc is not None else ""
            
            # Extract size and unit
            size = item_attributes.find("Size")
            size_text = size.text if size is not None else ""
            
            unit = item_attributes.find("Unit")
            unit_text = unit.text if unit is not None else ""
            
            # Extract offers
            offers = item.find("Offers")
            offer = offers.find("Offer") if offers is not None else None
            offer_listing = offer.find("OfferListing") if offer is not None else None
            
            # Extract price
            price = None
            original_price = None
            
            if offer_listing is not None:
                price_element = offer_listing.find("Price")
                if price_element is not None:
                    amount = price_element.find("Amount")
                    if amount is not None and amount.text is not None:
                        price = float(amount.text) / 100  # Convert from cents
                
                # Check for sale price
                sale_price_element = offer_listing.find("SalePrice")
                if sale_price_element is not None:
                    sale_amount = sale_price_element.find("Amount")
                    if sale_amount is not None and sale_amount.text is not None:
                        sale_price = float(sale_amount.text) / 100
                        if price is not None and sale_price < price:
                            original_price = price
                            price = sale_price
            
            # If no offer price, check item attributes
            if price is None:
                list_price = item_attributes.find("ListPrice")
                if list_price is not None:
                    amount = list_price.find("Amount")
                    if amount is not None and amount.text is not None:
                        price = float(amount.text) / 100
            
            if price is None:
                return None
            
            # Extract availability
            availability = offer_listing.find("Availability") if offer_listing is not None else None
            availability_text = availability.text if availability is not None else ""
            in_stock = "In Stock" in availability_text or "Available" in availability_text
            
            # Extract stock quantity
            stock_quantity = 0
            if in_stock:
                stock_quantity = 100  # Default quantity
            
            # Extract images
            image_sets = item.find("ImageSets")
            image_url = ""
            if image_sets is not None:
                image_set = image_sets.find("ImageSet")
                if image_set is not None:
                    large_image = image_set.find("LargeImage")
                    if large_image is not None:
                        url = large_image.find("URL")
                        if url is not None and url.text is not None:
                            image_url = url.text
            
            # Extract ratings
            customer_reviews = item.find("CustomerReviews")
            rating = 0.0
            review_count = 0
            
            if customer_reviews is not None:
                avg_rating = customer_reviews.find("AverageRating")
                if avg_rating is not None and avg_rating.text is not None:
                    rating = float(avg_rating.text)
                
                total_reviews = customer_reviews.find("TotalReviews")
                if total_reviews is not None and total_reviews.text is not None:
                    review_count = int(total_reviews.text)
            
            # Create RetailerProduct
            return RetailerProduct(
                retailer_id="amazon",
                product_id=asin.text,
                name=title.text,
                brand=brand_name,
                category=category,
                price=price,
                original_price=original_price,
                shipping_cost=0.0,  # Will be calculated separately
                free_shipping_threshold=25.0,
                estimated_delivery_days=2,
                in_stock=in_stock,
                stock_quantity=stock_quantity,
                upc=upc_code,
                sku=asin.text,  # Use ASIN as SKU
                size=size_text,
                unit=unit_text,
                description=title.text,  # Use title as description
                image_url=image_url,
                product_url=f"https://www.amazon.{self.region.lower()}/dp/{asin.text}",
                retailer_rating=4.5,  # Amazon average rating
                product_rating=rating,
                review_count=review_count
            )
            
        except Exception as e:
            logger.error(f"Error parsing Amazon item XML: {str(e)}")
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


# Factory function to create Amazon retailer
def create_amazon_retailer(api_key: str, api_secret: str, associate_tag: str, region: str = "US") -> AmazonRetailer:
    """Create an Amazon retailer instance"""
    return AmazonRetailer(
        api_key=api_key,
        api_secret=api_secret,
        associate_tag=associate_tag,
        region=region
    )