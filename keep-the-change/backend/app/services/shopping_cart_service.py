"""
Shopping cart service for KEEPTHECHANGE.com

This service manages shopping carts, handles checkout, and coordinates purchases.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import asyncio

from .price_comparison_engine import PriceComparisonEngine, ComparisonStrategy
from .shopping_optimizer import ShoppingOptimizer, OptimizationConstraint

logger = logging.getLogger(__name__)


@dataclass
class CartItem:
    """Item in shopping cart"""
    cart_item_id: str
    product_name: str
    quantity: int
    unit_price: float
    retailer: str
    retailer_product_id: str
    product_url: Optional[str]
    image_url: Optional[str]
    estimated_delivery_days: Optional[int]
    shipping_cost: float
    added_at: datetime
    last_updated: datetime
    
    @property
    def subtotal(self) -> float:
        """Calculate subtotal for this item"""
        return self.unit_price * self.quantity
    
    @property
    def total_cost(self) -> float:
        """Calculate total cost including shipping"""
        return self.subtotal + self.shipping_cost
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "cart_item_id": self.cart_item_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "retailer": self.retailer,
            "retailer_product_id": self.retailer_product_id,
            "product_url": self.product_url,
            "image_url": self.image_url,
            "estimated_delivery_days": self.estimated_delivery_days,
            "shipping_cost": self.shipping_cost,
            "subtotal": self.subtotal,
            "total_cost": self.total_cost,
            "added_at": self.added_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }


@dataclass
class ShoppingCart:
    """User's shopping cart"""
    cart_id: str
    user_id: str
    items: Dict[str, CartItem]  # cart_item_id -> CartItem
    created_at: datetime
    last_accessed: datetime
    currency: str = "USD"
    
    @property
    def item_count(self) -> int:
        """Total number of items in cart"""
        return len(self.items)
    
    @property
    def total_quantity(self) -> int:
        """Total quantity of all items"""
        return sum(item.quantity for item in self.items.values())
    
    @property
    def subtotal(self) -> float:
        """Subtotal of all items (without shipping)"""
        return sum(item.subtotal for item in self.items.values())
    
    @property
    def total_shipping(self) -> float:
        """Total shipping cost"""
        return sum(item.shipping_cost for item in self.items.values())
    
    @property
    def total_cost(self) -> float:
        """Total cost including shipping"""
        return self.subtotal + self.total_shipping
    
    @property
    def retailers(self) -> List[str]:
        """List of retailers in cart"""
        return list(set(item.retailer for item in self.items.values()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "cart_id": self.cart_id,
            "user_id": self.user_id,
            "items": [item.to_dict() for item in self.items.values()],
            "item_count": self.item_count,
            "total_quantity": self.total_quantity,
            "subtotal": self.subtotal,
            "total_shipping": self.total_shipping,
            "total_cost": self.total_cost,
            "retailers": self.retailers,
            "currency": self.currency,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat()
        }


@dataclass
class CheckoutRequest:
    """Request for checkout"""
    cart_id: str
    shipping_address: Dict[str, Any]
    billing_address: Optional[Dict[str, Any]]
    payment_method_id: str
    shipping_method: str = "standard"
    gift_message: Optional[str] = None
    save_shipping_address: bool = False
    save_billing_address: bool = False


@dataclass
class CheckoutResult:
    """Result of checkout process"""
    checkout_id: str
    cart_id: str
    user_id: str
    status: str  # pending, processing, completed, failed
    total_amount: float
    currency: str
    estimated_delivery_date: Optional[datetime]
    order_number: Optional[str]
    payment_status: str
    shipping_status: str
    errors: List[str]
    warnings: List[str]
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "checkout_id": self.checkout_id,
            "cart_id": self.cart_id,
            "user_id": self.user_id,
            "status": self.status,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "estimated_delivery_date": self.estimated_delivery_date.isoformat() if self.estimated_delivery_date else None,
            "order_number": self.order_number,
            "payment_status": self.payment_status,
            "shipping_status": self.shipping_status,
            "errors": self.errors,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat()
        }


class ShoppingCartService:
    """Service for managing shopping carts and checkout"""
    
    def __init__(self, price_engine: PriceComparisonEngine, optimizer: ShoppingOptimizer):
        self.price_engine = price_engine
        self.optimizer = optimizer
        self._carts: Dict[str, ShoppingCart] = {}
        self._checkouts: Dict[str, CheckoutResult] = {}
        self.cart_ttl = timedelta(days=30)  # Carts expire after 30 days
    
    async def get_or_create_cart(self, user_id: str) -> ShoppingCart:
        """Get existing cart or create new one for user"""
        # Find existing cart for user
        for cart in self._carts.values():
            if cart.user_id == user_id:
                # Check if cart is expired
                if datetime.utcnow() - cart.last_accessed > self.cart_ttl:
                    logger.info(f"Cart {cart.cart_id} expired, creating new one")
                    del self._carts[cart.cart_id]
                    break
                
                # Update last accessed time
                cart.last_accessed = datetime.utcnow()
                logger.info(f"Returning existing cart {cart.cart_id} for user {user_id}")
                return cart
        
        # Create new cart
        cart_id = str(uuid.uuid4())
        cart = ShoppingCart(
            cart_id=cart_id,
            user_id=user_id,
            items={},
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow()
        )
        
        self._carts[cart_id] = cart
        logger.info(f"Created new cart {cart_id} for user {user_id}")
        
        return cart
    
    async def get_cart(self, cart_id: str, user_id: str) -> Optional[ShoppingCart]:
        """Get cart by ID (with user verification)"""
        cart = self._carts.get(cart_id)
        
        if not cart:
            logger.warning(f"Cart {cart_id} not found")
            return None
        
        if cart.user_id != user_id:
            logger.warning(f"User {user_id} not authorized to access cart {cart_id}")
            return None
        
        # Check if cart is expired
        if datetime.utcnow() - cart.last_accessed > self.cart_ttl:
            logger.info(f"Cart {cart_id} expired")
            del self._carts[cart_id]
            return None
        
        # Update last accessed time
        cart.last_accessed = datetime.utcnow()
        
        return cart
    
    async def add_to_cart(
        self,
        cart_id: str,
        user_id: str,
        product_name: str,
        retailer: str,
        retailer_product_id: str,
        quantity: int = 1,
        unit_price: Optional[float] = None,
        shipping_cost: Optional[float] = None,
        product_url: Optional[str] = None,
        image_url: Optional[str] = None,
        estimated_delivery_days: Optional[int] = None
    ) -> Tuple[bool, Optional[CartItem], str]:
        """Add item to cart"""
        # Get cart
        cart = await self.get_cart(cart_id, user_id)
        if not cart:
            return False, None, "Cart not found or unauthorized"
        
        # Validate quantity
        if quantity <= 0:
            return False, None, "Quantity must be greater than 0"
        
        # If price not provided, try to get from retailer
        if unit_price is None or shipping_cost is None:
            price_info = await self._get_product_price_info(retailer, retailer_product_id)
            if price_info:
                unit_price = price_info.get("price", unit_price)
                shipping_cost = price_info.get("shipping_cost", shipping_cost)
                estimated_delivery_days = price_info.get("estimated_delivery_days", estimated_delivery_days)
        
        if unit_price is None:
            return False, None, "Could not determine product price"
        
        if shipping_cost is None:
            shipping_cost = 0.0
        
        # Check if item already in cart (same retailer and product)
        existing_item = None
        for item in cart.items.values():
            if item.retailer == retailer and item.retailer_product_id == retailer_product_id:
                existing_item = item
                break
        
        if existing_item:
            # Update quantity
            existing_item.quantity += quantity
            existing_item.last_updated = datetime.utcnow()
            logger.info(f"Updated quantity for item {existing_item.cart_item_id} to {existing_item.quantity}")
            return True, existing_item, "Item quantity updated"
        else:
            # Add new item
            cart_item_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            cart_item = CartItem(
                cart_item_id=cart_item_id,
                product_name=product_name,
                quantity=quantity,
                unit_price=unit_price,
                retailer=retailer,
                retailer_product_id=retailer_product_id,
                product_url=product_url,
                image_url=image_url,
                estimated_delivery_days=estimated_delivery_days,
                shipping_cost=shipping_cost,
                added_at=now,
                last_updated=now
            )
            
            cart.items[cart_item_id] = cart_item
            logger.info(f"Added new item {cart_item_id} to cart {cart_id}")
            
            return True, cart_item, "Item added to cart"
    
    async def update_cart_item(
        self,
        cart_id: str,
        user_id: str,
        cart_item_id: str,
        quantity: Optional[int] = None,
        retailer: Optional[str] = None,
        retailer_product_id: Optional[str] = None
    ) -> Tuple[bool, Optional[CartItem], str]:
        """Update item in cart"""
        # Get cart
        cart = await self.get_cart(cart_id, user_id)
        if not cart:
            return False, None, "Cart not found or unauthorized"
        
        # Get item
        cart_item = cart.items.get(cart_item_id)
        if not cart_item:
            return False, None, "Item not found in cart"
        
        # Update quantity if provided
        if quantity is not None:
            if quantity <= 0:
                # Remove item if quantity is 0 or negative
                del cart.items[cart_item_id]
                logger.info(f"Removed item {cart_item_id} from cart {cart_id}")
                return True, None, "Item removed from cart"
            
            cart_item.quantity = quantity
            cart_item.last_updated = datetime.utcnow()
            logger.info(f"Updated quantity for item {cart_item_id} to {quantity}")
        
        # Update retailer/product if provided
        if retailer is not None:
            cart_item.retailer = retailer
        
        if retailer_product_id is not None:
            cart_item.retailer_product_id = retailer_product_id
        
        # If retailer or product changed, update price
        if retailer is not None or retailer_product_id is not None:
            price_info = await self._get_product_price_info(cart_item.retailer, cart_item.retailer_product_id)
            if price_info:
                cart_item.unit_price = price_info.get("price", cart_item.unit_price)
                cart_item.shipping_cost = price_info.get("shipping_cost", cart_item.shipping_cost)
                cart_item.estimated_delivery_days = price_info.get("estimated_delivery_days", cart_item.estimated_delivery_days)
        
        return True, cart_item, "Item updated"
    
    async def remove_from_cart(
        self,
        cart_id: str,
        user_id: str,
        cart_item_id: str
    ) -> Tuple[bool, str]:
        """Remove item from cart"""
        # Get cart
        cart = await self.get_cart(cart_id, user_id)
        if not cart:
            return False, "Cart not found or unauthorized"
        
        # Remove item
        if cart_item_id in cart.items:
            del cart.items[cart_item_id]
            logger.info(f"Removed item {cart_item_id} from cart {cart_id}")
            return True, "Item removed from cart"
        else:
            return False, "Item not found in cart"
    
    async def clear_cart(self, cart_id: str, user_id: str) -> Tuple[bool, str]:
        """Clear all items from cart"""
        # Get cart
        cart = await self.get_cart(cart_id, user_id)
        if not cart:
            return False, "Cart not found or unauthorized"
        
        # Clear items
        item_count = len(cart.items)
        cart.items.clear()
        logger.info(f"Cleared {item_count} items from cart {cart_id}")
        
        return True, f"Cart cleared ({item_count} items removed)"
    
    async def optimize_cart(
        self,
        cart_id: str,
        user_id: str,
        strategy: ComparisonStrategy = ComparisonStrategy.CHEAPEST,
        constraints: Optional[OptimizationConstraint] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """Optimize cart items for better prices"""
        # Get cart
        cart = await self.get_cart(cart_id, user_id)
        if not cart:
            return False, {}, "Cart not found or unauthorized"
        
        if not cart.items:
            return False, {}, "Cart is empty"
        
        # Convert cart items to optimization format
        items = []
        for cart_item in cart.items.values():
            items.append({
                "product_name": cart_item.product_name,
                "retailer": cart_item.retailer,
                "retailer_product_id": cart_item.retailer_product_id,
                "quantity": cart_item.quantity,
                "current_price": cart_item.unit_price,
                "current_shipping": cart_item.shipping_cost
            })
        
        # Run optimization
        try:
            # First, compare prices for all items
            comparison_result = await self.price_engine.compare_shopping_list(
                items=[{"product_name": item["product_name"], "quantity": item["quantity"]} for item in items],
                strategy=strategy,
                optimize_for_bundling=True
            )
            
            # Apply optimization to cart
            optimized_items = []
            total_savings = 0
            items_optimized = 0
            
            for i, (cart_item, item_detail) in enumerate(zip(cart.items.values(), comparison_result.get("item_details", []))):
                result_dict = item_detail.get("comparison_result")
                if not result_dict:
                    optimized_items.append({
                        "cart_item_id": cart_item.cart_item_id,
                        "product_name": cart_item.product_name,
                        "optimized": False,
                        "reason": "No comparison results available"
                    })
                    continue
                
                best_retailer = result_dict.get("best_retailer")
                best_price = result_dict.get("best_price")
                
                if not best_retailer or not best_price:
                    optimized_items.append({
                        "cart_item_id": cart_item.cart_item_id,
                        "product_name": cart_item.product_name,
                        "optimized": False,
                        "reason": "No best retailer/price found"
                    })
                    continue
                
                # Check if current retailer is already the best
                if cart_item.retailer == best_retailer:
                    optimized_items.append({
                        "cart_item_id": cart_item.cart_item_id,
                        "product_name": cart_item.product_name,
                        "optimized": False,
                        "reason": "Already using best retailer",
                        "current_retailer": cart_item.retailer,
                        "best_retailer": best_retailer,
                        "current_price": cart_item.unit_price,
                        "best_price": best_price
                    })
                    continue
                
                # Calculate potential savings
                current_total = cart_item.total_cost
                
                # Get best product details
                retailer_results = result_dict.get("retailer_results", {})
                best_product = retailer_results.get(best_retailer)
                
                if not best_product:
                    optimized_items.append({
                        "cart_item_id": cart_item.cart_item_id,
                        "product_name": cart_item.product_name,
                        "optimized": False,
                        "reason": "Could not get best product details"
                    })
                    continue
                
                best_total = best_product["total_price"] * cart_item.quantity
                potential_savings = current_total - best_total
                
                if potential_savings <= 0:
                    optimized_items.append({
                        "cart_item_id": cart_item.cart_item_id,
                        "product_name": cart_item.product_name,
                        "optimized": False,
                        "reason": "No savings available",
                        "current_retailer": cart_item.retailer,
                        "best_retailer": best_retailer,
                        "current_price": cart_item.unit_price,
                        "best_price": best_price,
                        "potential_savings": potential_savings
                    })
                    continue
                
                # This item can be optimized
                optimized_items.append({
                    "cart_item_id": cart_item.cart_item_id,
                    "product_name": cart_item.product_name,
                    "optimized": True,
                    "current_retailer": cart_item.retailer,
                    "best_retailer": best_retailer,
                    "current_price": cart_item.unit_price,
                    "best_price": best_price,
                    "current_total": current_total,
                    "best_total": best_total,
                    "potential_savings": potential_savings,
                    "product_details": best_product
                })
                
                total_savings += potential_savings
                items_optimized += 1
            
            result = {
                "cart_id": cart_id,
                "total_items": len(cart.items),
                "items_optimized": items_optimized,
                "total_savings": total_savings,
                "optimized_items": optimized_items,
                "strategy": strategy.value,
                "optimization_time": datetime.utcnow().isoformat()
            }
            
            return True, result, f"Found ${total_savings:.2f} in potential savings across {items_optimized} items"
            
        except Exception as e:
            logger.error(f"Error optimizing cart {cart_id}: {e}")
            return False, {}, f"Optimization failed: {str(e)}"
    
    async def apply_optimization(
        self,
        cart_id: str,
        user_id: str,
        optimization_result: Dict[str, Any]
    ) -> Tuple[bool, ShoppingCart, str]:
        """Apply optimization results to cart"""
        # Get cart
        cart = await self.get_cart(cart_id, user_id)
        if not cart:
            return False, None, "Cart not found or unauthorized"
        
        optimized_items = optimization_result.get("optimized_items", [])
        applied_count = 0
        
        for item_opt in optimized_items:
            if not item_opt.get("optimized", False):
                continue
            
            cart_item_id = item_opt.get("cart_item_id")
            if not cart_item_id:
                continue
            
            cart_item = cart.items.get(cart_item_id)
            if not cart_item:
                continue
            
            # Update cart item with optimized retailer and price
            product_details = item_opt.get("product_details", {})
            
            cart_item.retailer = item_opt.get("best_retailer", cart_item.retailer)
            cart_item.retailer_product_id = product_details.get("product_id", cart_item.retailer_product_id)
            cart_item.unit_price = product_details.get("price", cart_item.unit_price)
            cart_item.shipping_cost = product_details.get("shipping_cost", cart_item.shipping_cost)
            cart_item.estimated_delivery_days = product_details.get("estimated_delivery_days", cart_item.estimated_delivery_days)
            cart_item.product_url = product_details.get("product_url", cart_item.product_url)
            cart_item.image_url = product_details.get("image_url", cart_item.image_url)
            cart_item.last_updated = datetime.utcnow()
            
            applied_count += 1
        
        logger.info(f"Applied optimization to {applied_count} items in cart {cart_id}")
        
        return True, cart, f"Optimization applied to {applied_count} items"
    
    async def checkout(
        self,
        cart_id: str,
        user_id: str,
        checkout_request: CheckoutRequest
    ) -> Tuple[bool, Optional[CheckoutResult], str]:
        """Process checkout for cart"""
        # Get cart
        cart = await self.get_cart(cart_id, user_id)
        if not cart:
            return False, None, "Cart not found or unauthorized"
        
        if not cart.items:
            return False, None, "Cart is empty"
        
        # Validate checkout request
        validation_result = await self._validate_checkout_request(checkout_request, cart)
        if not validation_result[0]:
            return False, None, validation_result[1]
        
        # Create checkout
        checkout_id = str(uuid.uuid4())
        
        # Calculate estimated delivery date
        estimated_delivery_date = None
        max_delivery_days = 0
        
        for cart_item in cart.items.values():
            if cart_item.estimated_delivery_days and cart_item.estimated_delivery_days > max_delivery_days:
                max_delivery_days = cart_item.estimated_delivery_days
        
        if max_delivery_days > 0:
            estimated_delivery_date = datetime.utcnow() + timedelta(days=max_delivery_days)
        
        # Generate order number
        order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{checkout_id[:8].upper()}"
        
        checkout_result = CheckoutResult(
            checkout_id=checkout_id,
            cart_id=cart_id,
            user_id=user_id,
            status="pending",
            total_amount=cart.total_cost,
            currency=cart.currency,
            estimated_delivery_date=estimated_delivery_date,
            order_number=order_number,
            payment_status="pending",
            shipping_status="pending",
            errors=[],
            warnings=[],
            created_at=datetime.utcnow()
        )
        
        # Store checkout
        self._checkouts[checkout_id] = checkout_result
        
        logger.info(f"Created checkout {checkout_id} for cart {cart_id}, order {order_number}")
        
        # In a real implementation, this would:
        # 1. Process payment
        # 2. Create orders with retailers
        # 3. Update inventory
        # 4. Send confirmation emails
        # 5. Clear cart after successful checkout
        
        return True, checkout_result, "Checkout initiated"
    
    async def _validate_checkout_request(
        self,
        request: CheckoutRequest,
        cart: ShoppingCart
    ) -> Tuple[bool, str]:
        """Validate checkout request"""
        # Check shipping address
        shipping_address = request.shipping_address
        required_fields = ["street", "city", "state", "zip_code", "country"]
        
        for field in required_fields:
            if field not in shipping_address or not shipping_address[field]:
                return False, f"Missing required shipping address field: {field}"
        
        # Check payment method
        if not request.payment_method_id:
            return False, "Payment method is required"
        
        # Check cart is not empty
        if not cart.items:
            return False, "Cart is empty"
        
        # Check all items are still available
        # In a real implementation, this would verify with retailers
        
        return True, "Checkout request is valid"
    
    async def _get_product_price_info(
        self,
        retailer: str,
        product_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get current price information for a product"""
        # In a real implementation, this would query the retailer API
        # For now, return mock data
        
        # This is a placeholder - actual implementation would:
        # 1. Find the retailer interface
        # 2. Call get_product_by_id
        # 3. Return price, shipping, and delivery info
        
        return {
            "price": 10.0,  # Mock price
            "shipping_cost": 0.0,  # Mock shipping
            "estimated_delivery_days": 3  # Mock delivery
        }
    
    async def get_checkout_status(self, checkout_id: str, user_id: str) -> Optional[CheckoutResult]:
        """Get checkout status"""
        checkout = self._checkouts.get(checkout_id)
        
        if not checkout:
            return None
        
        if checkout.user_id != user_id:
            return None
        
        return checkout
    
    def cleanup_expired_carts(self):
        """Clean up expired carts"""
        now = datetime.utcnow()
        expired_carts = []
        
        for cart_id, cart in self._carts.items():
            if now - cart.last_accessed > self.cart_ttl:
                expired_carts.append(cart_id)
        
        for cart_id in expired_carts:
            del self._carts[cart_id]
        
        if expired_carts:
            logger.info(f"Cleaned up {len(expired_carts)} expired carts")
    
    def get_user_cart_count(self, user_id: str) -> int:
        """Get number of carts for user (should be 0 or 1)"""
        count = 0
        for cart in self._carts.values():
            if cart.user_id == user_id:
                count += 1
        return count