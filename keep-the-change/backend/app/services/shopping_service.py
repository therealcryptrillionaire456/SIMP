"""
Main shopping service orchestrator for KEEPTHECHANGE.com

This service orchestrates all shopping-related functionality:
- Price comparison
- Shopping optimization
- Cart management
- Product catalog
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass

from .retailer_base import RetailerInterface, RetailerProduct
from .price_comparison_engine import PriceComparisonEngine, ComparisonStrategy
from .shopping_optimizer import ShoppingOptimizer, OptimizationConstraint, OptimizationResult
from .shopping_cart_service import ShoppingCartService, ShoppingCart, CheckoutRequest, CheckoutResult
from .product_catalog_service import ProductCatalogService, SearchFilters, SearchResult, Recommendation

logger = logging.getLogger(__name__)


@dataclass
class ShoppingServiceConfig:
    """Configuration for shopping service"""
    enable_caching: bool = True
    cache_ttl_minutes: int = 5
    max_retailer_connections: int = 10
    default_optimization_strategy: str = "cheapest"
    enable_recommendations: bool = True
    enable_price_alerts: bool = True


class ShoppingService:
    """Main shopping service orchestrator"""
    
    def __init__(
        self,
        retailers: List[RetailerInterface],
        config: Optional[ShoppingServiceConfig] = None
    ):
        self.config = config or ShoppingServiceConfig()
        
        # Initialize sub-services
        self.price_engine = PriceComparisonEngine(retailers)
        self.optimizer = ShoppingOptimizer(self.price_engine)
        self.cart_service = ShoppingCartService(self.price_engine, self.optimizer)
        self.catalog_service = ProductCatalogService()
        
        # Service status
        self.is_initialized = False
        self.retailer_status: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Shopping service initialized")
    
    async def initialize(self) -> bool:
        """Initialize shopping service"""
        try:
            logger.info("Initializing shopping service...")
            
            # Authenticate with all retailers
            self.retailer_status = await self.price_engine.authenticate_all()
            
            # Check if we have at least one working retailer
            working_retailers = [
                name for name, status in self.retailer_status.items()
                if status.get("status") == "online"
            ]
            
            if not working_retailers:
                logger.warning("No retailers are currently online")
                self.is_initialized = False
                return False
            
            logger.info(f"Connected to {len(working_retailers)} retailers: {', '.join(working_retailers)}")
            self.is_initialized = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize shopping service: {e}")
            self.is_initialized = False
            return False
    
    # ===== Product Catalog Methods =====
    
    async def search_products(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> SearchResult:
        """Search products in catalog"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Convert filters dict to SearchFilters object
        search_filters = None
        if filters:
            search_filters = SearchFilters(
                categories=filters.get("categories"),
                brands=filters.get("brands"),
                min_price=filters.get("min_price"),
                max_price=filters.get("max_price"),
                dietary_tags=filters.get("dietary_tags"),
                in_stock_only=filters.get("in_stock_only", True),
                sort_by=filters.get("sort_by", "relevance"),
                retailers=filters.get("retailers")
            )
        
        return self.catalog_service.search_products(
            query=query,
            filters=search_filters,
            page=page,
            page_size=page_size
        )
    
    async def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed product information"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        product = self.catalog_service.get_product(product_id)
        if not product:
            return None
        
        # Get current prices from retailers
        comparison_result = await self.price_engine.compare_product(
            product_name=product.name,
            upc=product.upc,
            sku=product.sku,
            strategy=ComparisonStrategy.CHEAPEST
        )
        
        return {
            "product": product.to_dict(),
            "current_prices": comparison_result.to_dict() if comparison_result else None,
            "recommendations": await self.get_recommendations(product_id=product_id)
        }
    
    async def get_recommendations(
        self,
        product_id: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get product recommendations"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Get user history if user_id provided
        user_history = None
        if user_id:
            # In a real implementation, this would fetch user's purchase history
            # For now, use empty history
            user_history = []
        
        recommendations = self.catalog_service.get_recommendations(
            product_id=product_id,
            category=category,
            user_history=user_history,
            limit=limit
        )
        
        return [rec.to_dict() for rec in recommendations]
    
    # ===== Price Comparison Methods =====
    
    async def compare_prices(
        self,
        product_name: str,
        upc: Optional[str] = None,
        sku: Optional[str] = None,
        strategy: str = "cheapest"
    ) -> Dict[str, Any]:
        """Compare prices for a product across retailers"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Convert strategy string to enum
        strategy_map = {
            "cheapest": ComparisonStrategy.CHEAPEST,
            "fastest": ComparisonStrategy.FASTEST,
            "balanced": ComparisonStrategy.BALANCED,
            "highest_rated": ComparisonStrategy.HIGHEST_RATED,
            "free_shipping": ComparisonStrategy.FREE_SHIPPING
        }
        
        comparison_strategy = strategy_map.get(strategy.lower(), ComparisonStrategy.CHEAPEST)
        
        result = await self.price_engine.compare_product(
            product_name=product_name,
            upc=upc,
            sku=sku,
            strategy=comparison_strategy
        )
        
        return result.to_dict()
    
    async def batch_compare_prices(
        self,
        items: List[Dict[str, Any]],
        strategy: str = "cheapest",
        optimize_bundling: bool = True
    ) -> Dict[str, Any]:
        """Compare prices for multiple items"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Convert strategy string to enum
        strategy_map = {
            "cheapest": ComparisonStrategy.CHEAPEST,
            "fastest": ComparisonStrategy.FASTEST,
            "balanced": ComparisonStrategy.BALANCED,
            "highest_rated": ComparisonStrategy.HIGHEST_RATED,
            "free_shipping": ComparisonStrategy.FREE_SHIPPING
        }
        
        comparison_strategy = strategy_map.get(strategy.lower(), ComparisonStrategy.CHEAPEST)
        
        result = await self.price_engine.compare_shopping_list(
            items=items,
            strategy=comparison_strategy,
            optimize_for_bundling=optimize_bundling
        )
        
        return result
    
    # ===== Shopping Optimization Methods =====
    
    async def optimize_shopping_list(
        self,
        shopping_list_id: str,
        items: List[Dict[str, Any]],
        user_preferences: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize a shopping list"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Convert constraints dict to OptimizationConstraint object
        optimization_constraints = None
        if constraints:
            optimization_constraints = OptimizationConstraint(
                max_total_cost=constraints.get("max_total_cost"),
                max_items_per_retailer=constraints.get("max_items_per_retailer"),
                delivery_deadline=constraints.get("delivery_deadline"),
                preferred_retailers=constraints.get("preferred_retailers", []),
                excluded_retailers=constraints.get("excluded_retailers", []),
                max_delivery_days=constraints.get("max_delivery_days")
            )
        
        result = await self.optimizer.optimize_shopping_list(
            shopping_list_id=shopping_list_id,
            items=items,
            user_preferences=user_preferences,
            constraints=optimization_constraints
        )
        
        return result.to_dict()
    
    async def get_optimization_history(
        self,
        shopping_list_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get optimization history for a shopping list"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        history = await self.optimizer.get_optimization_history(shopping_list_id, limit)
        return [result.to_dict() for result in history]
    
    # ===== Shopping Cart Methods =====
    
    async def get_cart(self, user_id: str) -> Dict[str, Any]:
        """Get or create shopping cart for user"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        cart = await self.cart_service.get_or_create_cart(user_id)
        return cart.to_dict()
    
    async def add_to_cart(
        self,
        user_id: str,
        product_name: str,
        retailer: str,
        retailer_product_id: str,
        quantity: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """Add item to cart"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Get user's cart
        cart = await self.cart_service.get_or_create_cart(user_id)
        
        success, cart_item, message = await self.cart_service.add_to_cart(
            cart_id=cart.cart_id,
            user_id=user_id,
            product_name=product_name,
            retailer=retailer,
            retailer_product_id=retailer_product_id,
            quantity=quantity,
            **kwargs
        )
        
        if success:
            # Record purchase in catalog (for recommendations)
            product = self.catalog_service.get_product_by_upc(kwargs.get("upc"))
            if product:
                self.catalog_service.record_purchase(product.product_id, quantity)
            
            return {
                "success": True,
                "message": message,
                "cart_item": cart_item.to_dict() if cart_item else None,
                "cart": cart.to_dict()
            }
        else:
            return {
                "success": False,
                "message": message,
                "cart_item": None,
                "cart": cart.to_dict()
            }
    
    async def update_cart_item(
        self,
        user_id: str,
        cart_item_id: str,
        quantity: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update item in cart"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Get user's cart
        cart = await self.cart_service.get_or_create_cart(user_id)
        
        success, cart_item, message = await self.cart_service.update_cart_item(
            cart_id=cart.cart_id,
            user_id=user_id,
            cart_item_id=cart_item_id,
            quantity=quantity,
            **kwargs
        )
        
        return {
            "success": success,
            "message": message,
            "cart_item": cart_item.to_dict() if cart_item else None,
            "cart": cart.to_dict()
        }
    
    async def remove_from_cart(
        self,
        user_id: str,
        cart_item_id: str
    ) -> Dict[str, Any]:
        """Remove item from cart"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Get user's cart
        cart = await self.cart_service.get_or_create_cart(user_id)
        
        success, message = await self.cart_service.remove_from_cart(
            cart_id=cart.cart_id,
            user_id=user_id,
            cart_item_id=cart_item_id
        )
        
        return {
            "success": success,
            "message": message,
            "cart": cart.to_dict()
        }
    
    async def optimize_cart(
        self,
        user_id: str,
        strategy: str = "cheapest",
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize cart for better prices"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Get user's cart
        cart = await self.cart_service.get_or_create_cart(user_id)
        
        # Convert strategy string to enum
        strategy_map = {
            "cheapest": ComparisonStrategy.CHEAPEST,
            "fastest": ComparisonStrategy.FASTEST,
            "balanced": ComparisonStrategy.BALANCED,
            "highest_rated": ComparisonStrategy.HIGHEST_RATED,
            "free_shipping": ComparisonStrategy.FREE_SHIPPING
        }
        
        comparison_strategy = strategy_map.get(strategy.lower(), ComparisonStrategy.CHEAPEST)
        
        # Convert constraints
        optimization_constraints = None
        if constraints:
            optimization_constraints = OptimizationConstraint(
                max_total_cost=constraints.get("max_total_cost"),
                max_items_per_retailer=constraints.get("max_items_per_retailer"),
                delivery_deadline=constraints.get("delivery_deadline"),
                preferred_retailers=constraints.get("preferred_retailers", []),
                excluded_retailers=constraints.get("excluded_retailers", []),
                max_delivery_days=constraints.get("max_delivery_days")
            )
        
        success, result, message = await self.cart_service.optimize_cart(
            cart_id=cart.cart_id,
            user_id=user_id,
            strategy=comparison_strategy,
            constraints=optimization_constraints
        )
        
        return {
            "success": success,
            "message": message,
            "optimization_result": result,
            "cart": cart.to_dict()
        }
    
    async def apply_cart_optimization(
        self,
        user_id: str,
        optimization_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply optimization results to cart"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Get user's cart
        cart = await self.cart_service.get_or_create_cart(user_id)
        
        success, updated_cart, message = await self.cart_service.apply_optimization(
            cart_id=cart.cart_id,
            user_id=user_id,
            optimization_result=optimization_result
        )
        
        return {
            "success": success,
            "message": message,
            "cart": updated_cart.to_dict() if updated_cart else None
        }
    
    async def checkout(
        self,
        user_id: str,
        checkout_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process checkout"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # Get user's cart
        cart = await self.cart_service.get_or_create_cart(user_id)
        
        # Create checkout request
        checkout_request = CheckoutRequest(
            cart_id=cart.cart_id,
            shipping_address=checkout_data.get("shipping_address", {}),
            billing_address=checkout_data.get("billing_address"),
            payment_method_id=checkout_data.get("payment_method_id", ""),
            shipping_method=checkout_data.get("shipping_method", "standard"),
            gift_message=checkout_data.get("gift_message"),
            save_shipping_address=checkout_data.get("save_shipping_address", False),
            save_billing_address=checkout_data.get("save_billing_address", False)
        )
        
        success, checkout_result, message = await self.cart_service.checkout(
            cart_id=cart.cart_id,
            user_id=user_id,
            checkout_request=checkout_request
        )
        
        if success and checkout_result:
            # Record purchases in catalog
            for cart_item in cart.items.values():
                product = self.catalog_service.get_product_by_upc(cart_item.retailer_product_id)
                if product:
                    self.catalog_service.record_purchase(product.product_id, cart_item.quantity)
            
            return {
                "success": True,
                "message": message,
                "checkout": checkout_result.to_dict(),
                "order_number": checkout_result.order_number
            }
        else:
            return {
                "success": False,
                "message": message,
                "checkout": None,
                "order_number": None
            }
    
    # ===== Service Management Methods =====
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get shopping service status"""
        retailer_status = await self.price_engine.get_retailer_status()
        
        return {
            "initialized": self.is_initialized,
            "retailers": retailer_status,
            "catalog_stats": self.catalog_service.get_catalog_stats(),
            "config": {
                "enable_caching": self.config.enable_caching,
                "cache_ttl_minutes": self.config.cache_ttl_minutes,
                "default_optimization_strategy": self.config.default_optimization_strategy,
                "enable_recommendations": self.config.enable_recommendations,
                "enable_price_alerts": self.config.enable_price_alerts
            }
        }
    
    async def clear_caches(self):
        """Clear all caches"""
        self.optimizer.clear_all_cache()
        self.catalog_service.clear_cache()
        logger.info("Cleared all shopping service caches")
    
    async def cleanup(self):
        """Clean up expired data"""
        self.cart_service.cleanup_expired_carts()
        logger.info("Cleaned up expired shopping carts")
    
    # ===== Price Alert Methods =====
    
    async def create_price_alert(
        self,
        user_id: str,
        product_identifier: str,
        target_price: float,
        alert_type: str = "below"  # below, above, change
    ) -> Dict[str, Any]:
        """Create price alert for a product"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # In a real implementation, this would:
        # 1. Store the alert in a database
        # 2. Schedule periodic price checks
        # 3. Send notifications when condition is met
        
        alert_id = f"alert_{user_id}_{product_identifier}_{datetime.utcnow().timestamp()}"
        
        return {
            "alert_id": alert_id,
            "user_id": user_id,
            "product_identifier": product_identifier,
            "target_price": target_price,
            "alert_type": alert_type,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
    
    async def check_price_alerts(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Check for triggered price alerts"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        # In a real implementation, this would:
        # 1. Query active alerts from database
        # 2. Check current prices
        # 3. Return triggered alerts
        
        # For now, return empty list
        return []
    
    # ===== Batch Operations =====
    
    async def process_batch_operations(
        self,
        operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process multiple shopping operations in batch"""
        if not self.is_initialized:
            raise RuntimeError("Shopping service not initialized")
        
        results = []
        
        for op in operations:
            try:
                op_type = op.get("type")
                op_data = op.get("data", {})
                
                if op_type == "search":
                    result = await self.search_products(**op_data)
                    results.append({
                        "type": "search",
                        "success": True,
                        "result": result.to_dict()
                    })
                
                elif op_type == "compare":
                    result = await self.compare_prices(**op_data)
                    results.append({
                        "type": "compare",
                        "success": True,
                        "result": result
                    })
                
                elif op_type == "add_to_cart":
                    result = await self.add_to_cart(**op_data)
                    results.append({
                        "type": "add_to_cart",
                        "success": result["success"],
                        "result": result
                    })
                
                else:
                    results.append({
                        "type": op_type,
                        "success": False,
                        "error": f"Unknown operation type: {op_type}"
                    })
                    
            except Exception as e:
                results.append({
                    "type": op.get("type", "unknown"),
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "total_operations": len(operations),
            "successful": sum(1 for r in results if r.get("success", False)),
            "failed": sum(1 for r in results if not r.get("success", False)),
            "results": results
        }