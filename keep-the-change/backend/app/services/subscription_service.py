"""
Subscription management service for KEEPTHECHANGE.com

This service handles subscription plans, user subscriptions, billing cycles, and subscription lifecycle management.
"""

import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import json
from enum import Enum

logger = logging.getLogger(__name__)


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration"""
    ACTIVE = "active"
    TRIAL = "trial"
    PENDING = "pending"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BillingCycle(str, Enum):
    """Billing cycle enumeration"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class SubscriptionPlan:
    """Subscription plan definition"""
    plan_id: str
    name: str
    description: str
    price: float  # Monthly price
    currency: str = "USD"
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    features: List[str] = None
    max_shopping_lists: int = 5
    max_products_per_list: int = 50
    price_comparison_enabled: bool = True
    optimization_enabled: bool = True
    real_time_alerts: bool = True
    analytics_dashboard: bool = True
    priority_support: bool = False
    trial_days: int = 14
    is_active: bool = True
    
    def __post_init__(self):
        if self.features is None:
            self.features = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "currency": self.currency,
            "billing_cycle": self.billing_cycle.value,
            "features": self.features,
            "max_shopping_lists": self.max_shopping_lists,
            "max_products_per_list": self.max_products_per_list,
            "price_comparison_enabled": self.price_comparison_enabled,
            "optimization_enabled": self.optimization_enabled,
            "real_time_alerts": self.real_time_alerts,
            "analytics_dashboard": self.analytics_dashboard,
            "priority_support": self.priority_support,
            "trial_days": self.trial_days,
            "is_active": self.is_active
        }


@dataclass
class UserSubscription:
    """User subscription information"""
    subscription_id: str
    user_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    cancelled_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "subscription_id": self.subscription_id,
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "current_period_start": self.current_period_start.isoformat(),
            "current_period_end": self.current_period_end.isoformat(),
            "trial_start": self.trial_start.isoformat() if self.trial_start else None,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
    
    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        now = datetime.utcnow()
        if self.status == SubscriptionStatus.ACTIVE:
            return now <= self.current_period_end
        elif self.status == SubscriptionStatus.TRIAL:
            return self.trial_end and now <= self.trial_end
        return False
    
    def is_in_trial(self) -> bool:
        """Check if subscription is in trial period"""
        if self.status != SubscriptionStatus.TRIAL:
            return False
        if not self.trial_end:
            return False
        return datetime.utcnow() <= self.trial_end
    
    def days_remaining(self) -> int:
        """Get days remaining in current period"""
        now = datetime.utcnow()
        if self.is_in_trial() and self.trial_end:
            return (self.trial_end - now).days
        elif self.status == SubscriptionStatus.ACTIVE:
            return (self.current_period_end - now).days
        return 0


class SubscriptionService:
    """Subscription management service"""
    
    def __init__(self, payment_service=None):
        self.payment_service = payment_service
        self.plans: Dict[str, SubscriptionPlan] = {}
        self._initialize_default_plans()
    
    def _initialize_default_plans(self):
        """Initialize default subscription plans"""
        self.plans = {
            "free": SubscriptionPlan(
                plan_id="free",
                name="Free",
                description="Basic features for casual shoppers",
                price=0.0,
                max_shopping_lists=3,
                max_products_per_list=20,
                price_comparison_enabled=True,
                optimization_enabled=False,
                real_time_alerts=False,
                analytics_dashboard=False,
                priority_support=False,
                trial_days=0,
                features=[
                    "3 shopping lists",
                    "20 products per list",
                    "Basic price comparison",
                    "Email support"
                ]
            ),
            "basic": SubscriptionPlan(
                plan_id="basic",
                name="Basic",
                description="Essential features for regular shoppers",
                price=4.99,
                max_shopping_lists=10,
                max_products_per_list=100,
                price_comparison_enabled=True,
                optimization_enabled=True,
                real_time_alerts=True,
                analytics_dashboard=True,
                priority_support=False,
                trial_days=14,
                features=[
                    "10 shopping lists",
                    "100 products per list",
                    "Advanced price comparison",
                    "Shopping optimization",
                    "Real-time price alerts",
                    "Basic analytics dashboard",
                    "Email support"
                ]
            ),
            "pro": SubscriptionPlan(
                plan_id="pro",
                name="Pro",
                description="Advanced features for power shoppers",
                price=9.99,
                max_shopping_lists=50,
                max_products_per_list=500,
                price_comparison_enabled=True,
                optimization_enabled=True,
                real_time_alerts=True,
                analytics_dashboard=True,
                priority_support=True,
                trial_days=14,
                features=[
                    "Unlimited shopping lists",
                    "500 products per list",
                    "Advanced price comparison",
                    "Smart shopping optimization",
                    "Real-time price alerts",
                    "Advanced analytics dashboard",
                    "Priority email support",
                    "Early access to new features"
                ]
            ),
            "business": SubscriptionPlan(
                plan_id="business",
                name="Business",
                description="Enterprise features for businesses",
                price=24.99,
                billing_cycle=BillingCycle.MONTHLY,
                max_shopping_lists=100,
                max_products_per_list=1000,
                price_comparison_enabled=True,
                optimization_enabled=True,
                real_time_alerts=True,
                analytics_dashboard=True,
                priority_support=True,
                trial_days=30,
                features=[
                    "Unlimited shopping lists",
                    "1000 products per list",
                    "Advanced price comparison",
                    "Smart shopping optimization",
                    "Real-time price alerts",
                    "Advanced analytics dashboard",
                    "Priority phone support",
                    "Custom integrations",
                    "API access",
                    "Team management",
                    "Custom reporting"
                ]
            )
        }
    
    async def get_plans(self) -> List[SubscriptionPlan]:
        """Get all available subscription plans"""
        return list(self.plans.values())
    
    async def get_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """Get a specific subscription plan"""
        return self.plans.get(plan_id)
    
    async def create_subscription(
        self,
        user_id: str,
        plan_id: str,
        payment_method_id: Optional[str] = None,
        start_trial: bool = True
    ) -> Tuple[bool, Optional[UserSubscription], str]:
        """Create a new subscription for a user"""
        try:
            # Get the plan
            plan = await self.get_plan(plan_id)
            if not plan:
                return False, None, f"Plan {plan_id} not found"
            
            # Generate subscription ID
            subscription_id = f"sub_{uuid.uuid4().hex[:16]}"
            
            now = datetime.utcnow()
            
            # Calculate trial period if applicable
            trial_start = None
            trial_end = None
            status = SubscriptionStatus.ACTIVE
            
            if start_trial and plan.trial_days > 0:
                trial_start = now
                trial_end = now + timedelta(days=plan.trial_days)
                status = SubscriptionStatus.TRIAL
            
            # Calculate billing period
            if plan.billing_cycle == BillingCycle.MONTHLY:
                period_days = 30
            elif plan.billing_cycle == BillingCycle.QUARTERLY:
                period_days = 90
            else:  # YEARLY
                period_days = 365
            
            current_period_start = trial_end if trial_end else now
            current_period_end = current_period_start + timedelta(days=period_days)
            
            # Create subscription
            subscription = UserSubscription(
                subscription_id=subscription_id,
                user_id=user_id,
                plan_id=plan_id,
                status=status,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
                trial_start=trial_start,
                trial_end=trial_end,
                created_at=now,
                updated_at=now
            )
            
            # Process payment if not free plan and not in trial
            if plan.price > 0 and not start_trial and self.payment_service:
                payment_result = await self.payment_service.process_subscription_payment(
                    user_id=user_id,
                    plan_id=plan_id,
                    amount=plan.price,
                    currency=plan.currency,
                    payment_method_id=payment_method_id,
                    subscription_id=subscription_id
                )
                
                if not payment_result.success:
                    return False, None, f"Payment failed: {payment_result.error_message}"
            
            logger.info(f"Created subscription {subscription_id} for user {user_id}, plan {plan_id}")
            return True, subscription, "Subscription created successfully"
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return False, None, f"Error creating subscription: {str(e)}"
    
    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True
    ) -> Tuple[bool, str]:
        """Cancel a subscription"""
        try:
            # In a real implementation, this would fetch from database
            # For now, we'll simulate the cancellation
            
            logger.info(f"Cancelling subscription {subscription_id}, cancel_at_period_end={cancel_at_period_end}")
            
            if cancel_at_period_end:
                return True, "Subscription will be cancelled at the end of the billing period"
            else:
                return True, "Subscription cancelled immediately"
                
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return False, f"Error cancelling subscription: {str(e)}"
    
    async def update_subscription(
        self,
        subscription_id: str,
        new_plan_id: str
    ) -> Tuple[bool, Optional[UserSubscription], str]:
        """Update subscription to a new plan"""
        try:
            # Get the new plan
            new_plan = await self.get_plan(new_plan_id)
            if not new_plan:
                return False, None, f"Plan {new_plan_id} not found"
            
            # In a real implementation, this would fetch and update from database
            # For now, we'll simulate the update
            
            logger.info(f"Updating subscription {subscription_id} to plan {new_plan_id}")
            
            # Simulate updated subscription
            now = datetime.utcnow()
            updated_subscription = UserSubscription(
                subscription_id=subscription_id,
                user_id="user_123",  # Would be fetched from DB
                plan_id=new_plan_id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
                created_at=now - timedelta(days=10),
                updated_at=now
            )
            
            return True, updated_subscription, "Subscription updated successfully"
            
        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")
            return False, None, f"Error updating subscription: {str(e)}"
    
    async def get_subscription(self, subscription_id: str) -> Optional[UserSubscription]:
        """Get subscription by ID"""
        # In a real implementation, this would fetch from database
        # For now, return a mock subscription
        now = datetime.utcnow()
        return UserSubscription(
            subscription_id=subscription_id,
            user_id="user_123",
            plan_id="basic",
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now - timedelta(days=10),
            current_period_end=now + timedelta(days=20),
            created_at=now - timedelta(days=10),
            updated_at=now
        )
    
    async def get_user_subscriptions(self, user_id: str) -> List[UserSubscription]:
        """Get all subscriptions for a user"""
        # In a real implementation, this would fetch from database
        # For now, return a mock list
        now = datetime.utcnow()
        return [
            UserSubscription(
                subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
                user_id=user_id,
                plan_id="basic",
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now - timedelta(days=10),
                current_period_end=now + timedelta(days=20),
                created_at=now - timedelta(days=10),
                updated_at=now
            )
        ]
    
    async def process_billing_cycle(self) -> Dict[str, Any]:
        """Process billing cycle for all active subscriptions"""
        try:
            logger.info("Processing billing cycle for active subscriptions")
            
            # In a real implementation, this would:
            # 1. Fetch all active subscriptions with billing due
            # 2. Process payments for each
            # 3. Update subscription statuses
            # 4. Send notifications
            
            result = {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "errors": []
            }
            
            # Simulate processing
            result["processed"] = 100
            result["successful"] = 95
            result["failed"] = 5
            
            logger.info(f"Billing cycle processed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing billing cycle: {str(e)}")
            return {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "errors": [str(e)]
            }
    
    async def check_user_limits(
        self,
        user_id: str,
        plan_id: str,
        current_lists: int,
        current_products: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if user is within plan limits"""
        plan = await self.get_plan(plan_id)
        if not plan:
            return False, {"error": f"Plan {plan_id} not found"}
        
        limits = {
            "within_limits": True,
            "exceeded_limits": [],
            "max_shopping_lists": plan.max_shopping_lists,
            "max_products_per_list": plan.max_products_per_list,
            "current_shopping_lists": current_lists,
            "current_products_per_list": current_products
        }
        
        if current_lists > plan.max_shopping_lists:
            limits["within_limits"] = False
            limits["exceeded_limits"].append("shopping_lists")
        
        if current_products > plan.max_products_per_list:
            limits["within_limits"] = False
            limits["exceeded_limits"].append("products_per_list")
        
        return limits["within_limits"], limits
    
    async def get_subscription_analytics(self) -> Dict[str, Any]:
        """Get subscription analytics"""
        # In a real implementation, this would aggregate data from database
        return {
            "total_subscriptions": 1250,
            "active_subscriptions": 980,
            "trial_subscriptions": 85,
            "cancelled_subscriptions": 185,
            "revenue_monthly": 4890.50,
            "revenue_yearly": 58686.00,
            "popular_plans": {
                "free": 450,
                "basic": 520,
                "pro": 210,
                "business": 70
            },
            "churn_rate": 0.148,  # 14.8%
            "average_revenue_per_user": 7.82,
            "conversion_rate": 0.32  # 32%
        }


# Singleton instance
subscription_service = SubscriptionService()