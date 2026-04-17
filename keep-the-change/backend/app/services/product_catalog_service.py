"""
Product catalog service for KEEPTHECHANGE.com

This service manages the product catalog, handles search, and provides product recommendations.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import asyncio
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class CatalogProduct:
    """Product in catalog"""
    product_id: str
    name: str
    brand: Optional[str]
    category: str
    subcategory: Optional[str]
    description: Optional[str]
    upc: Optional[str]
    sku: Optional[str]
    size: Optional[str]
    unit: Optional[str]
    image_url: Optional[str]
    thumbnail_url: Optional[str]
    nutritional_info: Optional[Dict[str, Any]]
    dietary_tags: List[str]
    average_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    popularity_score: float
    search_count: int
    purchase_count: int
    created_at: datetime
    updated_at: datetime
    last_price_update: Optional[datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "upc": self.upc,
            "sku": self.sku,
            "size": self.size,
            "unit": self.unit,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "nutritional_info": self.nutritional_info,
            "dietary_tags": self.dietary_tags,
            "average_price": self.average_price,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "price_range": {
                "average": self.average_price,
                "min": self.min_price,
                "max": self.max_price
            },
            "popularity_score": self.popularity_score,
            "search_count": self.search_count,
            "purchase_count": self.purchase_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_price_update": self.last_price_update.isoformat() if self.last_price_update else None
        }


@dataclass
class SearchFilters:
    """Filters for product search"""
    categories: Optional[List[str]] = None
    brands: Optional[List[str]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    dietary_tags: Optional[List[str]] = None
    in_stock_only: bool = True
    sort_by: str = "relevance"  # relevance, price_asc, price_desc, popularity, newest
    retailers: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "categories": self.categories,
            "brands": self.brands,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "dietary_tags": self.dietary_tags,
            "in_stock_only": self.in_stock_only,
            "sort_by": self.sort_by,
            "retailers": self.retailers
        }


@dataclass
class SearchResult:
    """Result of product search"""
    products: List[CatalogProduct]
    total_results: int
    query: str
    filters: SearchFilters
    page: int
    page_size: int
    search_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "products": [product.to_dict() for product in self.products],
            "total_results": self.total_results,
            "query": self.query,
            "filters": self.filters.to_dict(),
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": (self.total_results + self.page_size - 1) // self.page_size if self.page_size > 0 else 0,
            "search_time_ms": self.search_time_ms
        }


@dataclass
class Recommendation:
    """Product recommendation"""
    product: CatalogProduct
    reason: str  # "frequently_bought_together", "similar_product", "popular_in_category", etc.
    confidence_score: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "product": self.product.to_dict(),
            "reason": self.reason,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata
        }


class ProductCatalogService:
    """Service for managing product catalog and search"""
    
    def __init__(self):
        self._products: Dict[str, CatalogProduct] = {}
        self._upc_index: Dict[str, str] = {}  # UPC -> product_id
        self._sku_index: Dict[str, str] = {}  # SKU -> product_id
        self._category_index: Dict[str, List[str]] = {}  # category -> [product_id]
        self._brand_index: Dict[str, List[str]] = {}  # brand -> [product_id]
        self._search_cache: Dict[str, Tuple[datetime, SearchResult]] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        # Initialize with sample data
        self._initialize_sample_data()
    
    def _initialize_sample_data(self):
        """Initialize with sample products for testing"""
        sample_products = [
            CatalogProduct(
                product_id=str(uuid.uuid4()),
                name="Organic Whole Milk",
                brand="Organic Valley",
                category="dairy",
                subcategory="milk",
                description="Fresh organic whole milk, 1 gallon",
                upc="123456789012",
                sku="OV-MILK-GAL",
                size="1 gallon",
                unit="gallon",
                image_url="https://example.com/milk.jpg",
                thumbnail_url="https://example.com/milk-thumb.jpg",
                nutritional_info={"calories": 150, "fat": 8, "protein": 8},
                dietary_tags=["organic", "gluten_free"],
                average_price=4.99,
                min_price=3.99,
                max_price=5.99,
                popularity_score=8.5,
                search_count=150,
                purchase_count=75,
                created_at=datetime.utcnow() - timedelta(days=30),
                updated_at=datetime.utcnow(),
                last_price_update=datetime.utcnow()
            ),
            CatalogProduct(
                product_id=str(uuid.uuid4()),
                name="Whole Wheat Bread",
                brand="Nature's Own",
                category="bakery",
                subcategory="bread",
                description="100% whole wheat bread, 20 oz",
                upc="234567890123",
                sku="NO-BREAD-WW",
                size="20 oz",
                unit="loaf",
                image_url="https://example.com/bread.jpg",
                thumbnail_url="https://example.com/bread-thumb.jpg",
                nutritional_info={"calories": 110, "fat": 1.5, "protein": 5},
                dietary_tags=["whole_grain", "low_fat"],
                average_price=3.49,
                min_price=2.99,
                max_price=3.99,
                popularity_score=7.8,
                search_count=120,
                purchase_count=60,
                created_at=datetime.utcnow() - timedelta(days=25),
                updated_at=datetime.utcnow(),
                last_price_update=datetime.utcnow()
            ),
            CatalogProduct(
                product_id=str(uuid.uuid4()),
                name="Fresh Bananas",
                brand=None,
                category="produce",
                subcategory="fruit",
                description="Fresh ripe bananas, per pound",
                upc="345678901234",
                sku="BANANA-LB",
                size="1 lb",
                unit="pound",
                image_url="https://example.com/bananas.jpg",
                thumbnail_url="https://example.com/bananas-thumb.jpg",
                nutritional_info={"calories": 105, "fat": 0.4, "protein": 1.3},
                dietary_tags=["vegan", "gluten_free", "organic"],
                average_price=0.69,
                min_price=0.49,
                max_price=0.89,
                popularity_score=9.2,
                search_count=200,
                purchase_count=150,
                created_at=datetime.utcnow() - timedelta(days=20),
                updated_at=datetime.utcnow(),
                last_price_update=datetime.utcnow()
            ),
            CatalogProduct(
                product_id=str(uuid.uuid4()),
                name="Cage-Free Eggs",
                brand="Happy Hens",
                category="dairy",
                subcategory="eggs",
                description="Cage-free large eggs, 12 count",
                upc="456789012345",
                sku="HH-EGGS-12",
                size="12 count",
                unit="dozen",
                image_url="https://example.com/eggs.jpg",
                thumbnail_url="https://example.com/eggs-thumb.jpg",
                nutritional_info={"calories": 70, "fat": 5, "protein": 6},
                dietary_tags=["cage_free", "gluten_free"],
                average_price=3.99,
                min_price=2.99,
                max_price=4.99,
                popularity_score=8.0,
                search_count=100,
                purchase_count=50,
                created_at=datetime.utcnow() - timedelta(days=15),
                updated_at=datetime.utcnow(),
                last_price_update=datetime.utcnow()
            ),
            CatalogProduct(
                product_id=str(uuid.uuid4()),
                name="Ground Beef 80/20",
                brand="Premium Beef",
                category="meat",
                subcategory="beef",
                description="80% lean ground beef, 1 lb",
                upc="567890123456",
                sku="PB-BEEF-1LB",
                size="1 lb",
                unit="pound",
                image_url="https://example.com/beef.jpg",
                thumbnail_url="https://example.com/beef-thumb.jpg",
                nutritional_info={"calories": 280, "fat": 23, "protein": 19},
                dietary_tags=[],
                average_price=5.99,
                min_price=4.99,
                max_price=6.99,
                popularity_score=7.5,
                search_count=80,
                purchase_count=40,
                created_at=datetime.utcnow() - timedelta(days=10),
                updated_at=datetime.utcnow(),
                last_price_update=datetime.utcnow()
            )
        ]
        
        for product in sample_products:
            self.add_product(product)
        
        logger.info(f"Initialized catalog with {len(self._products)} sample products")
    
    def add_product(self, product: CatalogProduct) -> bool:
        """Add product to catalog"""
        if product.product_id in self._products:
            logger.warning(f"Product {product.product_id} already exists")
            return False
        
        self._products[product.product_id] = product
        
        # Update indexes
        if product.upc:
            self._upc_index[product.upc] = product.product_id
        
        if product.sku:
            self._sku_index[product.sku] = product.product_id
        
        if product.category:
            if product.category not in self._category_index:
                self._category_index[product.category] = []
            self._category_index[product.category].append(product.product_id)
        
        if product.brand:
            if product.brand not in self._brand_index:
                self._brand_index[product.brand] = []
            self._brand_index[product.brand].append(product.product_id)
        
        logger.info(f"Added product {product.product_id}: {product.name}")
        return True
    
    def update_product(self, product_id: str, updates: Dict[str, Any]) -> Optional[CatalogProduct]:
        """Update product in catalog"""
        if product_id not in self._products:
            logger.warning(f"Product {product_id} not found")
            return None
        
        product = self._products[product_id]
        
        # Update fields
        for key, value in updates.items():
            if hasattr(product, key):
                setattr(product, key, value)
        
        product.updated_at = datetime.utcnow()
        
        # Re-index if category or brand changed
        if "category" in updates:
            # Remove from old category index
            for category, product_ids in self._category_index.items():
                if product_id in product_ids:
                    product_ids.remove(product_id)
                    if not product_ids:
                        del self._category_index[category]
                    break
            
            # Add to new category
            new_category = updates["category"]
            if new_category:
                if new_category not in self._category_index:
                    self._category_index[new_category] = []
                self._category_index[new_category].append(product_id)
        
        if "brand" in updates:
            # Remove from old brand index
            for brand, product_ids in self._brand_index.items():
                if product_id in product_ids:
                    product_ids.remove(product_id)
                    if not product_ids:
                        del self._brand_index[brand]
                    break
            
            # Add to new brand
            new_brand = updates["brand"]
            if new_brand:
                if new_brand not in self._brand_index:
                    self._brand_index[new_brand] = []
                self._brand_index[new_brand].append(product_id)
        
        logger.info(f"Updated product {product_id}")
        return product
    
    def get_product(self, product_id: str) -> Optional[CatalogProduct]:
        """Get product by ID"""
        return self._products.get(product_id)
    
    def get_product_by_upc(self, upc: str) -> Optional[CatalogProduct]:
        """Get product by UPC"""
        product_id = self._upc_index.get(upc)
        if product_id:
            return self._products.get(product_id)
        return None
    
    def get_product_by_sku(self, sku: str) -> Optional[CatalogProduct]:
        """Get product by SKU"""
        product_id = self._sku_index.get(sku)
        if product_id:
            return self._products.get(product_id)
        return None
    
    def search_products(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        page: int = 1,
        page_size: int = 20
    ) -> SearchResult:
        """Search products in catalog"""
        import time
        start_time = time.time()
        
        if filters is None:
            filters = SearchFilters()
        
        # Generate cache key
        cache_key = self._generate_cache_key(query, filters, page, page_size)
        
        # Check cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info(f"Returning cached search results for query: {query}")
            return cached_result
        
        # Normalize query
        normalized_query = query.lower().strip()
        
        # Filter products
        filtered_products = []
        
        for product in self._products.values():
            # Apply filters
            if not self._matches_filters(product, filters):
                continue
            
            # Apply search query
            if normalized_query:
                if not self._matches_query(product, normalized_query):
                    continue
            
            filtered_products.append(product)
        
        # Sort results
        filtered_products = self._sort_products(filtered_products, filters.sort_by)
        
        # Apply pagination
        total_results = len(filtered_products)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        if start_idx >= total_results:
            paginated_products = []
        else:
            paginated_products = filtered_products[start_idx:end_idx]
        
        # Increment search count for found products
        for product in paginated_products:
            product.search_count += 1
        
        # Calculate search time
        search_time_ms = (time.time() - start_time) * 1000
        
        # Create result
        result = SearchResult(
            products=paginated_products,
            total_results=total_results,
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            search_time_ms=search_time_ms
        )
        
        # Cache the result
        self._save_to_cache(cache_key, result)
        
        logger.info(f"Search for '{query}' returned {total_results} results in {search_time_ms:.2f}ms")
        
        return result
    
    def _generate_cache_key(
        self,
        query: str,
        filters: SearchFilters,
        page: int,
        page_size: int
    ) -> str:
        """Generate cache key for search"""
        import hashlib
        
        data = {
            "query": query,
            "filters": filters.to_dict(),
            "page": page,
            "page_size": page_size
        }
        
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()[:16]
    
    def _get_from_cache(self, cache_key: str) -> Optional[SearchResult]:
        """Get result from cache if not expired"""
        if cache_key in self._search_cache:
            cached_at, result = self._search_cache[cache_key]
            if datetime.utcnow() - cached_at < self.cache_ttl:
                return result
            else:
                del self._search_cache[cache_key]
        return None
    
    def _save_to_cache(self, cache_key: str, result: SearchResult):
        """Save result to cache"""
        self._search_cache[cache_key] = (datetime.utcnow(), result)
    
    def _matches_filters(self, product: CatalogProduct, filters: SearchFilters) -> bool:
        """Check if product matches filters"""
        # Category filter
        if filters.categories and product.category not in filters.categories:
            return False
        
        # Brand filter
        if filters.brands and product.brand not in filters.brands:
            return False
        
        # Price filter
        if filters.min_price is not None and product.average_price is not None:
            if product.average_price < filters.min_price:
                return False
        
        if filters.max_price is not None and product.average_price is not None:
            if product.average_price > filters.max_price:
                return False
        
        # Dietary tags filter
        if filters.dietary_tags:
            if not any(tag in product.dietary_tags for tag in filters.dietary_tags):
                return False
        
        # Retailer filter (not implemented in this simple version)
        # In a real implementation, this would check which retailers carry the product
        
        return True
    
    def _matches_query(self, product: CatalogProduct, query: str) -> bool:
        """Check if product matches search query"""
        # Check name
        if query in product.name.lower():
            return True
        
        # Check brand
        if product.brand and query in product.brand.lower():
            return True
        
        # Check category
        if query in product.category.lower():
            return True
        
        # Check description
        if product.description and query in product.description.lower():
            return True
        
        # Check dietary tags
        for tag in product.dietary_tags:
            if query in tag.lower():
                return True
        
        return False
    
    def _sort_products(self, products: List[CatalogProduct], sort_by: str) -> List[CatalogProduct]:
        """Sort products based on sort criteria"""
        if sort_by == "relevance":
            # Sort by popularity score (simulating relevance)
            return sorted(products, key=lambda p: p.popularity_score, reverse=True)
        
        elif sort_by == "price_asc":
            # Sort by price ascending
            return sorted(products, key=lambda p: p.average_price or float('inf'))
        
        elif sort_by == "price_desc":
            # Sort by price descending
            return sorted(products, key=lambda p: p.average_price or float('-inf'), reverse=True)
        
        elif sort_by == "popularity":
            # Sort by popularity score
            return sorted(products, key=lambda p: p.popularity_score, reverse=True)
        
        elif sort_by == "newest":
            # Sort by creation date
            return sorted(products, key=lambda p: p.created_at, reverse=True)
        
        # Default to relevance
        return sorted(products, key=lambda p: p.popularity_score, reverse=True)
    
    def get_recommendations(
        self,
        product_id: Optional[str] = None,
        category: Optional[str] = None,
        user_history: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[Recommendation]:
        """Get product recommendations"""
        recommendations = []
        
        if product_id:
            # Get recommendations based on a specific product
            product = self.get_product(product_id)
            if product:
                # Find similar products in same category
                similar_products = self._get_similar_products(product, limit)
                for similar in similar_products:
                    recommendations.append(Recommendation(
                        product=similar,
                        reason="similar_product",
                        confidence_score=0.8,
                        metadata={"based_on": product.name}
                    ))
        
        elif category:
            # Get popular products in category
            popular_products = self._get_popular_in_category(category, limit)
            for popular in popular_products:
                recommendations.append(Recommendation(
                    product=popular,
                    reason="popular_in_category",
                    confidence_score=0.7,
                    metadata={"category": category}
                ))
        
        elif user_history and len(user_history) > 0:
            # Get recommendations based on user purchase history
            # Find frequently bought together items
            frequently_bought = self._get_frequently_bought_together(user_history, limit)
            for item in frequently_bought:
                recommendations.append(Recommendation(
                    product=item,
                    reason="frequently_bought_together",
                    confidence_score=0.9,
                    metadata={"based_on_history": True}
                ))
        
        else:
            # Get general popular products
            popular_products = self._get_popular_products(limit)
            for popular in popular_products:
                recommendations.append(Recommendation(
                    product=popular,
                    reason="popular",
                    confidence_score=0.6,
                    metadata={}
                ))
        
        return recommendations
    
    def _get_similar_products(self, product: CatalogProduct, limit: int) -> List[CatalogProduct]:
        """Get products similar to the given product"""
        similar = []
        
        for other in self._products.values():
            if other.product_id == product.product_id:
                continue
            
            # Check category match
            if other.category == product.category:
                similar.append(other)
            
            if len(similar) >= limit * 2:  # Get more than needed for sorting
                break
        
        # Sort by similarity (simplified: same brand, then popularity)
        similar.sort(key=lambda p: (
            1 if p.brand == product.brand else 0,
            p.popularity_score
        ), reverse=True)
        
        return similar[:limit]
    
    def _get_popular_in_category(self, category: str, limit: int) -> List[CatalogProduct]:
        """Get popular products in a category"""
        products_in_category = []
        
        for product in self._products.values():
            if product.category == category:
                products_in_category.append(product)
        
        # Sort by popularity
        products_in_category.sort(key=lambda p: p.popularity_score, reverse=True)
        
        return products_in_category[:limit]
    
    def _get_frequently_bought_together(
        self,
        user_history: List[str],
        limit: int
    ) -> List[CatalogProduct]:
        """Get products frequently bought together with user's history"""
        # Simplified implementation
        # In a real system, this would use collaborative filtering or association rules
        
        # Get categories from user history
        history_categories = set()
        for product_id in user_history[:5]:  # Use recent items
            product = self.get_product(product_id)
            if product and product.category:
                history_categories.add(product.category)
        
        # Find popular products in those categories
        recommendations = []
        for category in history_categories:
            category_recs = self._get_popular_in_category(category, limit)
            recommendations.extend(category_recs)
        
        # Remove duplicates and products already in history
        seen_ids = set(user_history)
        unique_recs = []
        
        for rec in recommendations:
            if rec.product_id not in seen_ids:
                unique_recs.append(rec)
                seen_ids.add(rec.product_id)
            
            if len(unique_recs) >= limit:
                break
        
        return unique_recs
    
    def _get_popular_products(self, limit: int) -> List[CatalogProduct]:
        """Get generally popular products"""
        all_products = list(self._products.values())
        all_products.sort(key=lambda p: p.popularity_score, reverse=True)
        return all_products[:limit]
    
    def update_price_history(
        self,
        product_id: str,
        price: float,
        retailer: str,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """Update price history for a product"""
        if product_id not in self._products:
            return False
        
        product = self._products[product_id]
        
        # Update price statistics
        if product.average_price is None:
            product.average_price = price
            product.min_price = price
            product.max_price = price
        else:
            # Simple moving average
            product.average_price = (product.average_price + price) / 2
            product.min_price = min(product.min_price or price, price)
            product.max_price = max(product.max_price or price, price)
        
        product.last_price_update = timestamp or datetime.utcnow()
        
        logger.info(f"Updated price for {product_id}: ${price} from {retailer}")
        return True
    
    def record_purchase(self, product_id: str, quantity: int = 1) -> bool:
        """Record a purchase for a product"""
        if product_id not in self._products:
            return False
        
        product = self._products[product_id]
        product.purchase_count += quantity
        
        # Update popularity score
        product.popularity_score = self._calculate_popularity_score(product)
        
        logger.info(f"Recorded purchase of {quantity} {product_id}: {product.name}")
        return True
    
    def _calculate_popularity_score(self, product: CatalogProduct) -> float:
        """Calculate popularity score for a product"""
        # Simple formula: weighted combination of search and purchase counts
        search_weight = 0.3
        purchase_weight = 0.7
        
        # Normalize counts (log scale to handle large numbers)
        search_norm = min(1.0, product.search_count / 1000)
        purchase_norm = min(1.0, product.purchase_count / 500)
        
        score = (search_weight * search_norm + purchase_weight * purchase_norm) * 10
        return min(score, 10.0)  # Cap at 10
    
    def get_catalog_stats(self) -> Dict[str, Any]:
        """Get catalog statistics"""
        total_products = len(self._products)
        
        # Count by category
        category_counts = {}
        for product in self._products.values():
            category = product.category or "uncategorized"
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Count by brand
        brand_counts = {}
        for product in self._products.values():
            if product.brand:
                brand_counts[product.brand] = brand_counts.get(product.brand, 0) + 1
        
        # Price statistics
        prices = [p.average_price for p in self._products.values() if p.average_price is not None]
        avg_price = sum(prices) / len(prices) if prices else 0
        
        return {
            "total_products": total_products,
            "categories": len(category_counts),
            "brands": len(brand_counts),
            "average_price": avg_price,
            "category_distribution": category_counts,
            "top_brands": dict(sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "most_popular": [
                p.to_dict() for p in sorted(
                    self._products.values(),
                    key=lambda x: x.popularity_score,
                    reverse=True
                )[:5]
            ]
        }
    
    def clear_cache(self):
        """Clear search cache"""
        count = len(self._search_cache)
        self._search_cache.clear()
        logger.info(f"Cleared {count} cached search results")