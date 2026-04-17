"""
Tests for the subscription service
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from services.subscription_service import (
    SubscriptionService,
    SubscriptionPlan,
    UserSubscription,
    SubscriptionStatus,
    BillingCycle
)


class TestSubscriptionService:
    """Test suite for SubscriptionService"""
    
    @pytest.fixture
    def subscription_service(self):
        """Create a subscription service instance for testing"""
        return SubscriptionService()
    
    @pytest.fixture
    def mock_payment_service(self):
        """Create a mock payment service"""
        payment_service = AsyncMock()
        payment_service.process_subscription_payment.return_value = AsyncMock(
            success=True,
            transaction_id="tx_123",
            error_message=None
        )
        return payment_service
    
    @pytest.fixture
    def basic_plan(self):
        """Create a basic subscription plan for testing"""
        return SubscriptionPlan(
            plan_id="basic",
            name="Basic",
            description="Basic plan",
            price=4.99,
            max_shopping_lists=10,
            max_products_per_list=100,
            trial_days=14
        )
    
    @pytest.fixture
    def pro_plan(self):
        """Create a pro subscription plan for testing"""
        return SubscriptionPlan(
            plan_id="pro",
            name="Pro",
            description="Pro plan",
            price=9.99,
            max_shopping_lists=50,
            max_products_per_list=500,
            trial_days=14
        )
    
    @pytest.mark.asyncio
    async def test_subscription_service_initialization(self, subscription_service):
        """Test subscription service initialization"""
        assert subscription_service is not None
        assert subscription_service.payment_service is None
        assert subscription_service.plans is not None
        
        # Check that default plans are initialized
        assert "free" in subscription_service.plans
        assert "basic" in subscription_service.plans
        assert "pro" in subscription_service.plans
        assert "business" in subscription_service.plans
        
        # Check free plan
        free_plan = subscription_service.plans["free"]
        assert free_plan.plan_id == "free"
        assert free_plan.price == 0.0
        assert free_plan.max_shopping_lists == 3
        
        # Check basic plan
        basic_plan = subscription_service.plans["basic"]
        assert basic_plan.plan_id == "basic"
        assert basic_plan.price == 4.99
        assert basic_plan.max_shopping_lists == 10
        
        # Check pro plan
        pro_plan = subscription_service.plans["pro"]
        assert pro_plan.plan_id == "pro"
        assert pro_plan.price == 9.99
        assert pro_plan.max_shopping_lists == 50
    
    @pytest.mark.asyncio
    async def test_get_plans(self, subscription_service):
        """Test getting all subscription plans"""
        plans = await subscription_service.get_plans()
        
        assert isinstance(plans, list)
        assert len(plans) == 4  # free, basic, pro, business
        
        # Check plan IDs
        plan_ids = [plan.plan_id for plan in plans]
        assert "free" in plan_ids
        assert "basic" in plan_ids
        assert "pro" in plan_ids
        assert "business" in plan_ids
    
    @pytest.mark.asyncio
    async def test_get_plan(self, subscription_service):
        """Test getting a specific subscription plan"""
        # Get existing plan
        basic_plan = await subscription_service.get_plan("basic")
        assert basic_plan is not None
        assert basic_plan.plan_id == "basic"
        assert basic_plan.name == "Basic"
        assert basic_plan.price == 4.99
        
        # Get non-existent plan
        nonexistent_plan = await subscription_service.get_plan("nonexistent")
        assert nonexistent_plan is None
    
    @pytest.mark.asyncio
    async def test_create_subscription_with_trial(self, subscription_service, mock_payment_service):
        """Test creating a subscription with trial period"""
        # Set up payment service
        subscription_service.payment_service = mock_payment_service
        
        # Create subscription with trial
        success, subscription, message = await subscription_service.create_subscription(
            user_id="user_123",
            plan_id="basic",
            start_trial=True
        )
        
        # Verify result
        assert success is True
        assert subscription is not None
        assert "successfully" in message.lower()
        
        # Verify subscription details
        assert subscription.user_id == "user_123"
        assert subscription.plan_id == "basic"
        assert subscription.status == SubscriptionStatus.TRIAL
        assert subscription.trial_start is not None
        assert subscription.trial_end is not None
        assert subscription.current_period_start is not None
        assert subscription.current_period_end is not None
        
        # Verify trial period
        trial_days = (subscription.trial_end - subscription.trial_start).days
        assert trial_days == 14  # Basic plan has 14-day trial
        
        # Verify payment service was NOT called (trial period)
        mock_payment_service.process_subscription_payment.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_create_subscription_without_trial(self, subscription_service, mock_payment_service):
        """Test creating a subscription without trial period"""
        # Set up payment service
        subscription_service.payment_service = mock_payment_service
        
        # Create subscription without trial
        success, subscription, message = await subscription_service.create_subscription(
            user_id="user_456",
            plan_id="pro",
            start_trial=False,
            payment_method_id="pm_123"
        )
        
        # Verify result
        assert success is True
        assert subscription is not None
        assert "successfully" in message.lower()
        
        # Verify subscription details
        assert subscription.user_id == "user_456"
        assert subscription.plan_id == "pro"
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.trial_start is None
        assert subscription.trial_end is None
        
        # Verify payment service was called (no trial)
        mock_payment_service.process_subscription_payment.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_subscription_free_plan(self, subscription_service):
        """Test creating a subscription with free plan"""
        # Create subscription with free plan
        success, subscription, message = await subscription_service.create_subscription(
            user_id="user_789",
            plan_id="free",
            start_trial=False
        )
        
        # Verify result
        assert success is True
        assert subscription is not None
        
        # Verify subscription details
        assert subscription.user_id == "user_789"
        assert subscription.plan_id == "free"
        assert subscription.status == SubscriptionStatus.ACTIVE
        
        # Free plan should not have trial
        assert subscription.trial_start is None
        assert subscription.trial_end is None
    
    @pytest.mark.asyncio
    async def test_create_subscription_nonexistent_plan(self, subscription_service):
        """Test creating a subscription with non-existent plan"""
        # Create subscription with non-existent plan
        success, subscription, message = await subscription_service.create_subscription(
            user_id="user_123",
            plan_id="nonexistent",
            start_trial=True
        )
        
        # Verify failure
        assert success is False
        assert subscription is None
        assert "not found" in message.lower()
    
    @pytest.mark.asyncio
    async def test_cancel_subscription(self, subscription_service):
        """Test canceling a subscription"""
        # Cancel subscription
        success, message = await subscription_service.cancel_subscription(
            subscription_id="sub_123",
            cancel_at_period_end=True
        )
        
        # Verify result
        assert success is True
        assert "cancelled" in message.lower()
        assert "end of the billing period" in message
        
        # Test immediate cancellation
        success, message = await subscription_service.cancel_subscription(
            subscription_id="sub_456",
            cancel_at_period_end=False
        )
        
        # Verify result
        assert success is True
        assert "cancelled immediately" in message
    
    @pytest.mark.asyncio
    async def test_update_subscription(self, subscription_service):
        """Test updating a subscription to a new plan"""
        # Update subscription
        success, subscription, message = await subscription_service.update_subscription(
            subscription_id="sub_123",
            new_plan_id="pro"
        )
        
        # Verify result
        assert success is True
        assert subscription is not None
        assert "successfully" in message.lower()
        
        # Verify subscription details
        assert subscription.subscription_id == "sub_123"
        assert subscription.plan_id == "pro"
        assert subscription.status == SubscriptionStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_update_subscription_nonexistent_plan(self, subscription_service):
        """Test updating a subscription to a non-existent plan"""
        # Update subscription with non-existent plan
        success, subscription, message = await subscription_service.update_subscription(
            subscription_id="sub_123",
            new_plan_id="nonexistent"
        )
        
        # Verify failure
        assert success is False
        assert subscription is None
        assert "not found" in message.lower()
    
    @pytest.mark.asyncio
    async def test_get_subscription(self, subscription_service):
        """Test getting a subscription by ID"""
        # Get subscription
        subscription = await subscription_service.get_subscription("sub_123")
        
        # Verify result
        assert subscription is not None
        assert subscription.subscription_id == "sub_123"
        assert subscription.user_id == "user_123"
        assert subscription.plan_id == "basic"
        assert subscription.status == SubscriptionStatus.ACTIVE
        
        # Verify dates
        assert subscription.current_period_start is not None
        assert subscription.current_period_end is not None
        assert subscription.created_at is not None
        assert subscription.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_get_user_subscriptions(self, subscription_service):
        """Test getting all subscriptions for a user"""
        # Get user subscriptions
        subscriptions = await subscription_service.get_user_subscriptions("user_123")
        
        # Verify result
        assert isinstance(subscriptions, list)
        assert len(subscriptions) == 1
        
        subscription = subscriptions[0]
        assert subscription.user_id == "user_123"
        assert subscription.plan_id == "basic"
        assert subscription.status == SubscriptionStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_check_user_limits_within_limits(self, subscription_service):
        """Test checking user limits when within limits"""
        # Check limits for basic plan
        within_limits, limits = await subscription_service.check_user_limits(
            user_id="user_123",
            plan_id="basic",
            current_lists=5,  # Within 10 limit
            current_products=50  # Within 100 limit
        )
        
        # Verify result
        assert within_limits is True
        assert limits["within_limits"] is True
        assert limits["exceeded_limits"] == []
        assert limits["max_shopping_lists"] == 10
        assert limits["max_products_per_list"] == 100
        assert limits["current_shopping_lists"] == 5
        assert limits["current_products_per_list"] == 50
    
    @pytest.mark.asyncio
    async def test_check_user_limits_exceeded(self, subscription_service):
        """Test checking user limits when exceeded"""
        # Check limits for basic plan (exceeded)
        within_limits, limits = await subscription_service.check_user_limits(
            user_id="user_123",
            plan_id="basic",
            current_lists=15,  # Exceeds 10 limit
            current_products=150  # Exceeds 100 limit
        )
        
        # Verify result
        assert within_limits is False
        assert limits["within_limits"] is False
        assert "shopping_lists" in limits["exceeded_limits"]
        assert "products_per_list" in limits["exceeded_limits"]
        assert limits["max_shopping_lists"] == 10
        assert limits["max_products_per_list"] == 100
        assert limits["current_shopping_lists"] == 15
        assert limits["current_products_per_list"] == 150
    
    @pytest.mark.asyncio
    async def test_check_user_limits_nonexistent_plan(self, subscription_service):
        """Test checking user limits with non-existent plan"""
        # Check limits with non-existent plan
        within_limits, limits = await subscription_service.check_user_limits(
            user_id="user_123",
            plan_id="nonexistent",
            current_lists=5,
            current_products=50
        )
        
        # Verify failure
        assert within_limits is False
        assert "error" in limits
        assert "not found" in limits["error"].lower()
    
    @pytest.mark.asyncio
    async def test_subscription_is_active(self, subscription_service):
        """Test checking if subscription is active"""
        # Create a subscription
        success, subscription, _ = await subscription_service.create_subscription(
            user_id="user_123",
            plan_id="basic",
            start_trial=True
        )
        
        # Verify is_active method
        assert subscription.is_active() is True
        
        # Test trial subscription
        assert subscription.is_in_trial() is True
        
        # Test days remaining
        days_remaining = subscription.days_remaining()
        assert days_remaining >= 0
        assert days_remaining <= 14  # Trial period
    
    @pytest.mark.asyncio
    async def test_process_billing_cycle(self, subscription_service):
        """Test processing billing cycle"""
        # Process billing cycle
        result = await subscription_service.process_billing_cycle()
        
        # Verify result
        assert isinstance(result, dict)
        assert "processed" in result
        assert "successful" in result
        assert "failed" in result
        assert "errors" in result
        
        # Verify mock data
        assert result["processed"] == 100
        assert result["successful"] == 95
        assert result["failed"] == 5
        assert result["errors"] == []
    
    @pytest.mark.asyncio
    async def test_get_subscription_analytics(self, subscription_service):
        """Test getting subscription analytics"""
        # Get analytics
        analytics = await subscription_service.get_subscription_analytics()
        
        # Verify result
        assert isinstance(analytics, dict)
        
        # Check required fields
        assert "total_subscriptions" in analytics
        assert "active_subscriptions" in analytics
        assert "trial_subscriptions" in analytics
        assert "cancelled_subscriptions" in analytics
        assert "revenue_monthly" in analytics
        assert "revenue_yearly" in analytics
        assert "popular_plans" in analytics
        assert "churn_rate" in analytics
        assert "average_revenue_per_user" in analytics
        assert "conversion_rate" in analytics
        
        # Check popular plans
        popular_plans = analytics["popular_plans"]
        assert "free" in popular_plans
        assert "basic" in popular_plans
        assert "pro" in popular_plans
        assert "business" in popular_plans
        
        # Verify data types
        assert isinstance(analytics["total_subscriptions"], int)
        assert isinstance(analytics["revenue_monthly"], float)
        assert isinstance(analytics["churn_rate"], float)
    
    @pytest.mark.asyncio
    async def test_plan_to_dict(self, subscription_service):
        """Test converting plan to dictionary"""
        # Get a plan
        basic_plan = await subscription_service.get_plan("basic")
        
        # Convert to dict
        plan_dict = basic_plan.to_dict()
        
        # Verify dictionary structure
        assert isinstance(plan_dict, dict)
        assert plan_dict["plan_id"] == "basic"
        assert plan_dict["name"] == "Basic"
        assert plan_dict["price"] == 4.99
        assert plan_dict["currency"] == "USD"
        assert plan_dict["billing_cycle"] == "monthly"
        assert isinstance(plan_dict["features"], list)
        assert plan_dict["max_shopping_lists"] == 10
        assert plan_dict["max_products_per_list"] == 100
        assert plan_dict["price_comparison_enabled"] is True
        assert plan_dict["optimization_enabled"] is True
        assert plan_dict["real_time_alerts"] is True
        assert plan_dict["analytics_dashboard"] is True
        assert plan_dict["priority_support"] is False
        assert plan_dict["trial_days"] == 14
        assert plan_dict["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_subscription_to_dict(self, subscription_service):
        """Test converting subscription to dictionary"""
        # Create a subscription
        success, subscription, _ = await subscription_service.create_subscription(
            user_id="user_123",
            plan_id="basic",
            start_trial=True
        )
        
        # Convert to dict
        subscription_dict = subscription.to_dict()
        
        # Verify dictionary structure
        assert isinstance(subscription_dict, dict)
        assert subscription_dict["subscription_id"] == subscription.subscription_id
        assert subscription_dict["user_id"] == "user_123"
        assert subscription_dict["plan_id"] == "basic"
        assert subscription_dict["status"] == "trial"
        assert "current_period_start" in subscription_dict
        assert "current_period_end" in subscription_dict
        assert "trial_start" in subscription_dict
        assert "trial_end" in subscription_dict
        assert subscription_dict["cancel_at_period_end"] is False
        assert "created_at" in subscription_dict
        assert "updated_at" in subscription_dict
        assert isinstance(subscription_dict["metadata"], dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])