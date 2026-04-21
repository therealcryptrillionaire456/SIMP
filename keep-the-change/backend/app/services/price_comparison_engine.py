"""
Price comparison engine for KEEPTHECHANGE.com

This engine compares prices across multiple retailers to find the best deals.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum

from .retailer_base import RetailerInterface, RetailerProduct, RetailerError

logger = logging.getLogger(__name__)


class ComparisonStrategy(Enum):
    """Strategy for comparing prices"""
    CHEAPEST = "cheapest"  # Lowest total price (price + shipping)
    FASTEST = "fastest"    # Fastest delivery
    BALANCED = "balanced"  # Balance of price and delivery time
    HIGHEST_RATED = "highest_rated"  # Best retailer/product rating
    FREE_SHIPPING = "free_shipping"  # Prefer free shipping options


@dataclass
class ComparisonResult:
    """Result of price comparison for a single product"""
    product_name: str
    upc: Optional[str]
    sku: Optional[str]
    retailer_results: Dict[str, RetailerProduct]  # retailer -> product
    best_retailer: Optional[str]
    best_price: Optional[float]
    price_range: Tuple[Optional[float], Optional[float]]  # (min, max)
    average_price: Optional[float]
    estimated_savings: Optional[float]
    comparison_strategy: ComparisonStrategy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "product_name": self.product_name,
            "upc": self.upc,
            "sku": self.sku,
            "retailer_results": {
                retailer: product.to_dict()
                for retailer, product in self.retailer_results.items()
            },
            "best_retailer": self.best_retailer,
            "best_price": self.best_price,
            "price_range": self.price_range,
            "average_price": self.average_price,
            "estimated_savings": self.estimated_savings,
            "comparison_strategy": self.comparison_strategy.value
        }


class PriceComparisonEngine:
    """Engine for comparing prices across retailers"""
    
    def __init__(self, retailers: List[RetailerInterface]):
        self.retailers = retailers
        self._cache: Dict[str, Tuple[datetime, ComparisonResult]] = {}
        self.cache_ttl = timedelta(minutes=5)  # Cache prices for 5 minutes
        
    async def authenticate_all(self) -> Dict[str, bool]:
        """Authenticate with all retailers"""
        auth_results = {}
        for retailer in self.retailers:
            try:
                auth_results[retailer.retailer_name] = await retailer.authenticate()
                logger.info(f"Authenticated with {retailer.retailer_name}: {auth_results[retailer.retailer_name]}")
            except Exception as e:
                logger.error(f"Failed to authenticate with {retailer.retailer_name}: {e}")
                auth_results[retailer.retailer_name] = False
        return auth_results
    
    def _get_cache_key(self, product_identifier: str, strategy: ComparisonStrategy) -> str:
        """Generate cache key"""
        return f"{product_identifier}:{strategy.value}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[ComparisonResult]:
        """Get result from cache if not expired"""
        if cache_key in self._cache:
            cached_at, result = self._cache[cache_key]
            if datetime.utcnow() - cached_at < self.cache_ttl:
                return result
            else:
                del self._cache[cache_key]
        return None
    
    def _save_to_cache(self, cache_key: str, result: ComparisonResult):
        """Save result to cache"""
        self._cache[cache_key] = (datetime.utcnow(), result)
    
    async def compare_product(
        self,
        product_name: str,
        upc: Optional[str] = None,
        sku: Optional[str] = None,
        strategy: ComparisonStrategy = ComparisonStrategy.CHEAPEST,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        max_price: Optional[float] = None,
        require_in_stock: bool = True
    ) -> ComparisonResult:
        """
        Compare prices for a product across all retailers
        
        Args:
            product_name: Name of the product to search for
            upc: UPC code (if available)
            sku: SKU code (if available)
            strategy: Comparison strategy to use
            category: Product category filter
            brand: Brand filter
            max_price: Maximum price filter
            require_in_stock: Only include in-stock items
        
        Returns:
            ComparisonResult with prices from all retailers
        """
        # Generate cache key
        cache_key = self._get_cache_key(
            f"{product_name}:{upc}:{sku}:{category}:{brand}:{max_price}",
            strategy
        )
        
        # Check cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info(f"Returning cached result for {product_name}")
            return cached_result
        
        logger.info(f"Comparing prices for: {product_name} (UPC: {upc}, SKU: {sku})")
        
        # Search for product in all retailers
        search_tasks = []
        for retailer in self.retailers:
            task = self._search_retailer(
                retailer=retailer,
                product_name=product_name,
                upc=upc,
                sku=sku,
                category=category,
                brand=brand,
                max_price=max_price,
                require_in_stock=require_in_stock
            )
            search_tasks.append(task)
        
        # Wait for all searches to complete
        retailer_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Process results
        valid_results = {}
        for retailer, result in zip(self.retailers, retailer_results):
            retailer_name = retailer.retailer_name
            
            if isinstance(result, Exception):
                logger.error(f"Error searching {retailer_name}: {result}")
                continue
            
            if result:
                valid_results[retailer_name] = result
                logger.info(f"Found product at {retailer_name}: ${result.price}")
            else:
                logger.info(f"Product not found at {retailer_name}")
        
        # Determine best retailer based on strategy
        best_retailer = self._select_best_retailer(valid_results, strategy)
        
        # Calculate statistics
        prices = [product.total_price for product in valid_results.values()]
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None
        avg_price = sum(prices) / len(prices) if prices else None
        
        # Calculate estimated savings vs average
        estimated_savings = None
        if best_retailer and avg_price:
            best_product = valid_results[best_retailer]
            estimated_savings = avg_price - best_product.total_price
        
        # Create result
        result = ComparisonResult(
            product_name=product_name,
            upc=upc,
            sku=sku,
            retailer_results=valid_results,
            best_retailer=best_retailer,
            best_price=min_price,
            price_range=(min_price, max_price),
            average_price=avg_price,
            estimated_savings=estimated_savings,
            comparison_strategy=strategy
        )
        
        # Cache the result
        self._save_to_cache(cache_key, result)
        
        return result
    
    async def _search_retailer(
        self,
        retailer: RetailerInterface,
        product_name: str,
        upc: Optional[str] = None,
        sku: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        max_price: Optional[float] = None,
        require_in_stock: bool = True
    ) -> Optional[RetailerProduct]:
        """Search for product in a specific retailer"""
        try:
            # Try UPC lookup first if available
            if upc:
                product = await retailer.get_product_by_upc(upc)
                if product:
                    return product
            
            # Try SKU lookup if available
            if sku:
                # Note: Not all retailers support SKU lookup
                # This would need to be implemented per retailer
                pass
            
            # Fall back to product name search
            search_results = await retailer.search_products(
                query=product_name,
                category=category,
                brand=brand,
                max_price=max_price,
                in_stock_only=require_in_stock,
                limit=5  # Get top 5 results
            )
            
            if search_results:
                # Find the best match based on name similarity
                # For now, return the first result
                return search_results[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching {retailer.retailer_name}: {e}")
            return None
    
    def _select_best_retailer(
        self,
        retailer_results: Dict[str, RetailerProduct],
        strategy: ComparisonStrategy
    ) -> Optional[str]:
        """Select the best retailer based on the chosen strategy"""
        if not retailer_results:
            return None
        
        if strategy == ComparisonStrategy.CHEAPEST:
            return min(
                retailer_results.items(),
                key=lambda x: x[1].total_price
            )[0]
        
        elif strategy == ComparisonStrategy.FASTEST:
            # Find retailer with shortest delivery time
            fastest_retailer = None
            fastest_days = float('inf')
            
            for retailer_name, product in retailer_results.items():
                if product.estimated_delivery_days is not None:
                    if product.estimated_delivery_days < fastest_days:
                        fastest_days = product.estimated_delivery_days
                        fastest_retailer = retailer_name
            
            return fastest_retailer or list(retailer_results.keys())[0]
        
        elif strategy == ComparisonStrategy.BALANCED:
            # Balance price and delivery time
            best_score = float('-inf')
            best_retailer = None
            
            for retailer_name, product in retailer_results.items():
                # Simple scoring: lower price and faster delivery = better
                price_score = 100 / (product.total_price + 1)  # Avoid division by zero
                delivery_score = 0
                
                if product.estimated_delivery_days is not None:
                    delivery_score = 50 / (product.estimated_delivery_days + 1)
                
                total_score = price_score + delivery_score
                
                if total_score > best_score:
                    best_score = total_score
                    best_retailer = retailer_name
            
            return best_retailer
        
        elif strategy == ComparisonStrategy.HIGHEST_RATED:
            # Find retailer with highest rating
            best_retailer = None
            best_rating = float('-inf')
            
            for retailer_name, product in retailer_results.items():
                rating = product.retailer_rating or product.product_rating or 0
                if rating > best_rating:
                    best_rating = rating
                    best_retailer = retailer_name
            
            return best_retailer
        
        elif strategy == ComparisonStrategy.FREE_SHIPPING:
            # Prefer retailers with free shipping
            free_shipping_retailers = [
                name for name, product in retailer_results.items()
                if product.is_free_shipping
            ]
            
            if free_shipping_retailers:
                # Among free shipping retailers, choose cheapest
                return min(
                    [(name, retailer_results[name]) for name in free_shipping_retailers],
                    key=lambda x: x[1].price
                )[0]
            else:
                # No free shipping, fall back to cheapest
                return self._select_best_retailer(retailer_results, ComparisonStrategy.CHEAPEST)
        
        # Default to cheapest
        return self._select_best_retailer(retailer_results, ComparisonStrategy.CHEAPEST)
    
    async def compare_shopping_list(
        self,
        items: List[Dict[str, Any]],
        strategy: ComparisonStrategy = ComparisonStrategy.CHEAPEST,
        optimize_for_bundling: bool = True
    ) -> Dict[str, Any]:
        """
        Compare prices for an entire shopping list
        
        Args:
            items: List of items with product_name, quantity, etc.
            strategy: Comparison strategy
            optimize_for_bundling: Try to bundle items from same retailer
        
        Returns:
            Dictionary with comparison results for all items
        """
        logger.info(f"Comparing shopping list with {len(items)} items")
        
        # Compare each item
        comparison_tasks = []
        for item in items:
            task = self.compare_product(
                product_name=item.get("product_name"),
                upc=item.get("upc"),
                sku=item.get("sku"),
                strategy=strategy,
                category=item.get("category"),
                brand=item.get("brand"),
                max_price=item.get("max_price"),
                require_in_stock=True
            )
            comparison_tasks.append(task)
        
        # Wait for all comparisons
        results = await asyncio.gather(*comparison_tasks)
        
        # Calculate totals
        total_items = len(items)
        items_with_prices = sum(1 for r in results if r.best_price is not None)
        
        # Calculate total cost with and without optimization
        total_cost_by_retailer: Dict[str, float] = {}
        item_details = []
        
        for i, (item, result) in enumerate(zip(items, results)):
            quantity = item.get("quantity", 1)
            item_detail = {
                "item_index": i,
                "product_name": item.get("product_name"),
                "quantity": quantity,
                "comparison_result": result.to_dict() if result else None
            }
            
            if result and result.best_retailer and result.best_price:
                retailer = result.best_retailer
                item_cost = result.best_price * quantity
                
                # Add to retailer total
                total_cost_by_retailer[retailer] = total_cost_by_retailer.get(retailer, 0) + item_cost
                
                item_detail["selected_retailer"] = retailer
                item_detail["item_cost"] = item_cost
                item_detail["unit_price"] = result.best_price
            
            item_details.append(item_detail)
        
        # If optimizing for bundling, try to minimize number of retailers
        if optimize_for_bundling and total_cost_by_retailer:
            optimized_retailer = self._optimize_for_bundling(item_details, total_cost_by_retailer, strategy)
            
            if optimized_retailer:
                # Recalculate with optimized retailer
                total_cost_by_retailer = {optimized_retailer: 0}
                for item_detail in item_details:
                    result_dict = item_detail.get("comparison_result")
                    if result_dict:
                        retailer_results = result_dict.get("retailer_results", {})
                        if optimized_retailer in retailer_results:
                            product_data = retailer_results[optimized_retailer]
                            item_cost = product_data["total_price"] * item_detail["quantity"]
                            total_cost_by_retailer[optimized_retailer] += item_cost
                            
                            item_detail["selected_retailer"] = optimized_retailer
                            item_detail["item_cost"] = item_cost
                            item_detail["unit_price"] = product_data["price"]
                        else:
                            # Keep original selection if optimized retailer doesn't have this item
                            pass
        
        # Calculate totals
        total_cost = sum(total_cost_by_retailer.values())
        estimated_savings = sum(
            item_detail.get("comparison_result", {}).get("estimated_savings", 0) or 0
            for item_detail in item_details
            if item_detail.get("comparison_result")
        )
        
        return {
            "total_items": total_items,
            "items_with_prices": items_with_prices,
            "coverage_percentage": (items_with_prices / total_items * 100) if total_items > 0 else 0,
            "total_cost": total_cost,
            "estimated_savings": estimated_savings,
            "retailer_breakdown": total_cost_by_retailer,
            "item_details": item_details,
            "optimization_strategy": strategy.value,
            "optimized_for_bundling": optimize_for_bundling
        }
    
    def _optimize_for_bundling(
        self,
        item_details: List[Dict[str, Any]],
        retailer_totals: Dict[str, float],
        strategy: ComparisonStrategy
    ) -> Optional[str]:
        """Optimize shopping list to minimize number of retailers"""
        if len(retailer_totals) <= 1:
            return list(retailer_totals.keys())[0] if retailer_totals else None
        
        # Find retailer that has the most items or lowest total cost
        retailer_item_counts: Dict[str, int] = {}
        for item_detail in item_details:
            retailer = item_detail.get("selected_retailer")
            if retailer:
                retailer_item_counts[retailer] = retailer_item_counts.get(retailer, 0) + 1
        
        # Choose retailer with most items
        if strategy in [ComparisonStrategy.CHEAPEST, ComparisonStrategy.BALANCED]:
            # For cheapest/balanced, choose retailer with lowest total cost
            return min(retailer_totals.items(), key=lambda x: x[1])[0]
        else:
            # For other strategies, choose retailer with most items
            return max(retailer_item_counts.items(), key=lambda x: x[1])[0] if retailer_item_counts else None
    
    async def get_retailer_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all retailers"""
        status = {}
        for retailer in self.retailers:
            try:
                info = retailer.get_retailer_info()
                # Test connectivity with a simple search
                test_results = await retailer.search_products("test", limit=1)
                info["status"] = "online"
                info["test_search_worked"] = len(test_results) > 0
            except Exception as e:
                info = retailer.get_retailer_info()
                info["status"] = "offline"
                info["error"] = str(e)
            
            status[retailer.retailer_name] = info
        
        return status