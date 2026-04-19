"""
Shopping list optimizer for KEEPTHECHANGE.com

This service optimizes shopping lists based on user preferences and price comparisons.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import json

from .price_comparison_engine import PriceComparisonEngine, ComparisonStrategy
from .retailer_base import RetailerProduct

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConstraint:
    """Constraints for optimization"""
    max_total_cost: Optional[float] = None
    max_items_per_retailer: Optional[int] = None
    delivery_deadline: Optional[datetime] = None
    preferred_retailers: List[str] = None
    excluded_retailers: List[str] = None
    max_delivery_days: Optional[int] = None
    
    def __post_init__(self):
        if self.preferred_retailers is None:
            self.preferred_retailers = []
        if self.excluded_retailers is None:
            self.excluded_retailers = []


@dataclass
class OptimizationResult:
    """Result of shopping list optimization"""
    shopping_list_id: str
    optimization_id: str
    status: str  # success, partial, failed
    optimized_items: List[Dict[str, Any]]
    total_cost: float
    estimated_savings: float
    savings_percentage: Optional[float]
    retailer_breakdown: Dict[str, float]
    delivery_estimate: Optional[datetime]
    constraints_met: bool
    optimization_time: datetime
    strategy_used: str
    notes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "shopping_list_id": self.shopping_list_id,
            "optimization_id": self.optimization_id,
            "status": self.status,
            "optimized_items": self.optimized_items,
            "total_cost": self.total_cost,
            "estimated_savings": self.estimated_savings,
            "savings_percentage": self.savings_percentage,
            "retailer_breakdown": self.retailer_breakdown,
            "delivery_estimate": self.delivery_estimate.isoformat() if self.delivery_estimate else None,
            "constraints_met": self.constraints_met,
            "optimization_time": self.optimization_time.isoformat(),
            "strategy_used": self.strategy_used,
            "notes": self.notes
        }


class ShoppingOptimizer:
    """Optimizes shopping lists based on user preferences"""
    
    def __init__(self, price_engine: PriceComparisonEngine):
        self.price_engine = price_engine
        self._optimization_cache: Dict[str, OptimizationResult] = {}
        self.cache_ttl = timedelta(minutes=10)
    
    async def optimize_shopping_list(
        self,
        shopping_list_id: str,
        items: List[Dict[str, Any]],
        user_preferences: Dict[str, Any],
        constraints: Optional[OptimizationConstraint] = None
    ) -> OptimizationResult:
        """
        Optimize a shopping list
        
        Args:
            shopping_list_id: ID of the shopping list
            items: List of items to optimize
            user_preferences: User's optimization preferences
            constraints: Optional constraints for optimization
        
        Returns:
            OptimizationResult with optimized shopping list
        """
        logger.info(f"Optimizing shopping list {shopping_list_id} with {len(items)} items")
        
        # Generate optimization ID
        optimization_id = self._generate_optimization_id(shopping_list_id, items, user_preferences)
        
        # Check cache
        cached_result = self._get_cached_optimization(optimization_id)
        if cached_result:
            logger.info(f"Returning cached optimization for {shopping_list_id}")
            return cached_result
        
        # Parse user preferences
        strategy = self._parse_optimization_strategy(user_preferences)
        
        # Apply constraints
        if constraints is None:
            constraints = OptimizationConstraint()
        
        # Compare prices for all items
        comparison_result = await self.price_engine.compare_shopping_list(
            items=items,
            strategy=strategy,
            optimize_for_bundling=user_preferences.get("optimize_for_bundling", True)
        )
        
        # Apply constraints to comparison results
        constrained_result = self._apply_constraints(
            comparison_result=comparison_result,
            constraints=constraints,
            items=items
        )
        
        # Calculate optimization metrics
        optimization_result = self._calculate_optimization_result(
            shopping_list_id=shopping_list_id,
            optimization_id=optimization_id,
            comparison_result=constrained_result,
            items=items,
            strategy=strategy,
            constraints=constraints
        )
        
        # Cache the result
        self._cache_optimization(optimization_id, optimization_result)
        
        return optimization_result
    
    def _generate_optimization_id(
        self,
        shopping_list_id: str,
        items: List[Dict[str, Any]],
        user_preferences: Dict[str, Any]
    ) -> str:
        """Generate unique optimization ID"""
        import hashlib
        
        # Create hashable representation
        data = {
            "shopping_list_id": shopping_list_id,
            "items": items,
            "preferences": user_preferences,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()[:16]
    
    def _get_cached_optimization(self, optimization_id: str) -> Optional[OptimizationResult]:
        """Get cached optimization result"""
        if optimization_id in self._optimization_cache:
            result, cached_at = self._optimization_cache[optimization_id]
            if datetime.utcnow() - cached_at < self.cache_ttl:
                return result
            else:
                del self._optimization_cache[optimization_id]
        return None
    
    def _cache_optimization(self, optimization_id: str, result: OptimizationResult):
        """Cache optimization result"""
        self._optimization_cache[optimization_id] = (result, datetime.utcnow())
    
    def _parse_optimization_strategy(self, user_preferences: Dict[str, Any]) -> ComparisonStrategy:
        """Parse optimization strategy from user preferences"""
        strategy_str = user_preferences.get("optimization_strategy", "cheapest")
        
        strategy_map = {
            "cheapest": ComparisonStrategy.CHEAPEST,
            "fastest": ComparisonStrategy.FASTEST,
            "balanced": ComparisonStrategy.BALANCED,
            "highest_rated": ComparisonStrategy.HIGHEST_RATED,
            "free_shipping": ComparisonStrategy.FREE_SHIPPING
        }
        
        return strategy_map.get(strategy_str.lower(), ComparisonStrategy.CHEAPEST)
    
    def _apply_constraints(
        self,
        comparison_result: Dict[str, Any],
        constraints: OptimizationConstraint,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply constraints to comparison results"""
        logger.info("Applying constraints to optimization")
        
        # Create a copy of the result to modify
        constrained_result = comparison_result.copy()
        item_details = constrained_result.get("item_details", [])
        notes = []
        
        # Apply retailer constraints
        if constraints.excluded_retailers:
            for item_detail in item_details:
                result_dict = item_detail.get("comparison_result")
                if result_dict:
                    retailer_results = result_dict.get("retailer_results", {})
                    
                    # Remove excluded retailers
                    for excluded in constraints.excluded_retailers:
                        if excluded in retailer_results:
                            del retailer_results[excluded]
                    
                    # Re-select best retailer
                    if retailer_results:
                        # Simple selection: choose cheapest among remaining
                        best_retailer = min(
                            retailer_results.items(),
                            key=lambda x: x[1]["total_price"]
                        )[0]
                        
                        # Update item detail
                        item_detail["selected_retailer"] = best_retailer
                        item_detail["item_cost"] = retailer_results[best_retailer]["total_price"] * item_detail["quantity"]
                        item_detail["unit_price"] = retailer_results[best_retailer]["price"]
                    else:
                        # No retailers left after exclusions
                        item_detail["selected_retailer"] = None
                        item_detail["item_cost"] = None
                        item_detail["unit_price"] = None
                        notes.append(f"No retailers available for {item_detail.get('product_name')} after exclusions")
        
        # Apply preferred retailers (boost their selection)
        if constraints.preferred_retailers:
            for item_detail in item_details:
                result_dict = item_detail.get("comparison_result")
                if result_dict:
                    retailer_results = result_dict.get("retailer_results", {})
                    
                    # Check if any preferred retailer has this item
                    preferred_available = [
                        retailer for retailer in constraints.preferred_retailers
                        if retailer in retailer_results
                    ]
                    
                    if preferred_available:
                        # Choose cheapest among preferred
                        best_preferred = min(
                            [(r, retailer_results[r]) for r in preferred_available],
                            key=lambda x: x[1]["total_price"]
                        )[0]
                        
                        # Update if different from current selection
                        current = item_detail.get("selected_retailer")
                        if current != best_preferred:
                            item_detail["selected_retailer"] = best_preferred
                            item_detail["item_cost"] = retailer_results[best_preferred]["total_price"] * item_detail["quantity"]
                            item_detail["unit_price"] = retailer_results[best_preferred]["price"]
        
        # Recalculate totals
        self._recalculate_totals(constrained_result)
        
        # Check delivery constraints
        if constraints.delivery_deadline or constraints.max_delivery_days:
            delivery_ok, delivery_notes = self._check_delivery_constraints(
                constrained_result, constraints
            )
            notes.extend(delivery_notes)
        
        # Check cost constraints
        if constraints.max_total_cost:
            total_cost = constrained_result.get("total_cost", 0)
            if total_cost > constraints.max_total_cost:
                notes.append(f"Total cost ${total_cost:.2f} exceeds budget ${constraints.max_total_cost:.2f}")
        
        constrained_result["notes"] = notes
        return constrained_result
    
    def _recalculate_totals(self, result: Dict[str, Any]):
        """Recalculate totals after constraint application"""
        item_details = result.get("item_details", [])
        
        # Recalculate retailer breakdown
        retailer_breakdown = {}
        total_cost = 0
        items_with_prices = 0
        
        for item_detail in item_details:
            retailer = item_detail.get("selected_retailer")
            item_cost = item_detail.get("item_cost")
            
            if retailer and item_cost is not None:
                retailer_breakdown[retailer] = retailer_breakdown.get(retailer, 0) + item_cost
                total_cost += item_cost
                items_with_prices += 1
        
        # Update result
        result["retailer_breakdown"] = retailer_breakdown
        result["total_cost"] = total_cost
        result["items_with_prices"] = items_with_prices
        
        # Recalculate coverage percentage
        total_items = result.get("total_items", 0)
        if total_items > 0:
            result["coverage_percentage"] = (items_with_prices / total_items) * 100
    
    def _check_delivery_constraints(
        self,
        result: Dict[str, Any],
        constraints: OptimizationConstraint
    ) -> Tuple[bool, List[str]]:
        """Check if delivery constraints are met"""
        notes = []
        all_ok = True
        
        item_details = result.get("item_details", [])
        
        for item_detail in item_details:
            retailer = item_detail.get("selected_retailer")
            if not retailer:
                continue
            
            result_dict = item_detail.get("comparison_result")
            if not result_dict:
                continue
            
            retailer_results = result_dict.get("retailer_results", {})
            product_data = retailer_results.get(retailer)
            
            if not product_data:
                continue
            
            delivery_days = product_data.get("estimated_delivery_days")
            
            if delivery_days is not None:
                # Check max delivery days constraint
                if constraints.max_delivery_days and delivery_days > constraints.max_delivery_days:
                    notes.append(
                        f"Item {item_detail.get('product_name')} from {retailer} "
                        f"has {delivery_days} day delivery, exceeding limit of {constraints.max_delivery_days}"
                    )
                    all_ok = False
                
                # Check delivery deadline constraint
                if constraints.delivery_deadline:
                    estimated_delivery = datetime.utcnow() + timedelta(days=delivery_days)
                    if estimated_delivery > constraints.delivery_deadline:
                        notes.append(
                            f"Item {item_detail.get('product_name')} from {retailer} "
                            f"estimated delivery {estimated_delivery.date()} after deadline {constraints.delivery_deadline.date()}"
                        )
                        all_ok = False
        
        return all_ok, notes
    
    def _calculate_optimization_result(
        self,
        shopping_list_id: str,
        optimization_id: str,
        comparison_result: Dict[str, Any],
        items: List[Dict[str, Any]],
        strategy: ComparisonStrategy,
        constraints: OptimizationConstraint
    ) -> OptimizationResult:
        """Calculate final optimization result"""
        # Determine status
        total_items = len(items)
        items_with_prices = comparison_result.get("items_with_prices", 0)
        
        if items_with_prices == 0:
            status = "failed"
        elif items_with_prices < total_items:
            status = "partial"
        else:
            status = "success"
        
        # Calculate savings percentage
        total_cost = comparison_result.get("total_cost", 0)
        estimated_savings = comparison_result.get("estimated_savings", 0)
        savings_percentage = None
        
        if total_cost > 0 and estimated_savings > 0:
            original_cost = total_cost + estimated_savings
            savings_percentage = (estimated_savings / original_cost) * 100
        
        # Check if constraints are met
        constraints_met = True
        notes = comparison_result.get("notes", [])
        
        if notes:
            # Check if any notes indicate constraint violations
            constraint_keywords = ["exceeds", "exceeding", "after deadline", "No retailers available"]
            for note in notes:
                if any(keyword in note.lower() for keyword in constraint_keywords):
                    constraints_met = False
                    break
        
        # Prepare optimized items
        optimized_items = []
        for i, (item, item_detail) in enumerate(zip(items, comparison_result.get("item_details", []))):
            optimized_item = {
                "item_index": i,
                "product_name": item.get("product_name"),
                "quantity": item.get("quantity", 1),
                "selected_retailer": item_detail.get("selected_retailer"),
                "unit_price": item_detail.get("unit_price"),
                "item_cost": item_detail.get("item_cost"),
                "comparison_available": item_detail.get("comparison_result") is not None
            }
            
            # Add comparison details if available
            result_dict = item_detail.get("comparison_result")
            if result_dict:
                optimized_item["available_retailers"] = list(result_dict.get("retailer_results", {}).keys())
                optimized_item["price_range"] = result_dict.get("price_range")
                optimized_item["best_price"] = result_dict.get("best_price")
            
            optimized_items.append(optimized_item)
        
        # Estimate delivery date (use longest delivery time)
        delivery_estimate = None
        max_delivery_days = 0
        
        for item_detail in comparison_result.get("item_details", []):
            retailer = item_detail.get("selected_retailer")
            if not retailer:
                continue
            
            result_dict = item_detail.get("comparison_result")
            if not result_dict:
                continue
            
            retailer_results = result_dict.get("retailer_results", {})
            product_data = retailer_results.get(retailer)
            
            if product_data:
                delivery_days = product_data.get("estimated_delivery_days")
                if delivery_days and delivery_days > max_delivery_days:
                    max_delivery_days = delivery_days
        
        if max_delivery_days > 0:
            delivery_estimate = datetime.utcnow() + timedelta(days=max_delivery_days)
        
        return OptimizationResult(
            shopping_list_id=shopping_list_id,
            optimization_id=optimization_id,
            status=status,
            optimized_items=optimized_items,
            total_cost=total_cost,
            estimated_savings=estimated_savings,
            savings_percentage=savings_percentage,
            retailer_breakdown=comparison_result.get("retailer_breakdown", {}),
            delivery_estimate=delivery_estimate,
            constraints_met=constraints_met,
            optimization_time=datetime.utcnow(),
            strategy_used=strategy.value,
            notes=notes
        )
    
    async def get_optimization_history(
        self,
        shopping_list_id: str,
        limit: int = 10
    ) -> List[OptimizationResult]:
        """Get optimization history for a shopping list"""
        # Filter cache for this shopping list
        history = []
        
        for opt_id, (result, cached_at) in self._optimization_cache.items():
            if result.shopping_list_id == shopping_list_id:
                history.append((cached_at, result))
        
        # Sort by most recent
        history.sort(key=lambda x: x[0], reverse=True)
        
        # Return limited results
        return [result for _, result in history[:limit]]
    
    def clear_cache_for_list(self, shopping_list_id: str):
        """Clear cache for a specific shopping list"""
        to_delete = []
        
        for opt_id, (result, _) in self._optimization_cache.items():
            if result.shopping_list_id == shopping_list_id:
                to_delete.append(opt_id)
        
        for opt_id in to_delete:
            del self._optimization_cache[opt_id]
        
        logger.info(f"Cleared {len(to_delete)} cached optimizations for list {shopping_list_id}")
    
    def clear_all_cache(self):
        """Clear all optimization cache"""
        count = len(self._optimization_cache)
        self._optimization_cache.clear()
        logger.info(f"Cleared all {count} cached optimizations")