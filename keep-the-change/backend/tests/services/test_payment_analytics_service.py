"""
Tests for the payment analytics service
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from services.payment_analytics_service import (
    PaymentAnalyticsService,
    RevenueMetric,
    PaymentMethodMetric,
    CustomerLifetimeValue,
    TimePeriod
)


class TestPaymentAnalyticsService:
    """Test suite for PaymentAnalyticsService"""
    
    @pytest.fixture
    def analytics_service(self):
        """Create an analytics service instance for testing"""
        return PaymentAnalyticsService()
    
    @pytest.fixture
    def mock_payment_service(self):
        """Create a mock payment service"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_billing_service(self):
        """Create a mock billing service"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_subscription_service(self):
        """Create a mock subscription service"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_refund_service(self):
        """Create a mock refund service"""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_analytics_service_initialization(self, analytics_service):
        """Test analytics service initialization"""
        assert analytics_service is not None
        assert analytics_service.payment_service is None
        assert analytics_service.billing_service is None
        assert analytics_service.subscription_service is None
        assert analytics_service.refund_service is None
        
        # Verify mock data is generated
        assert analytics_service._mock_transactions is not None
        assert isinstance(analytics_service._mock_transactions, list)
        assert len(analytics_service._mock_transactions) > 0
        
        assert analytics_service._mock_customers is not None
        assert isinstance(analytics_service._mock_customers, list)
        assert len(analytics_service._mock_customers) > 0
        
        # Verify transaction structure
        transaction = analytics_service._mock_transactions[0]
        assert "transaction_id" in transaction
        assert "date" in transaction
        assert "amount" in transaction
        assert "currency" in transaction
        assert "payment_method" in transaction
        assert "status" in transaction
        assert "customer_id" in transaction
        assert "type" in transaction
        
        # Verify customer structure
        customer = analytics_service._mock_customers[0]
        assert "customer_id" in customer
        assert "join_date" in customer
        assert "last_purchase_date" in customer
        assert "total_spent" in customer
        assert "purchase_count" in customer
        assert "subscription_plan" in customer
        assert "country" in customer
    
    @pytest.mark.asyncio
    async def test_get_revenue_metrics_daily(self, analytics_service):
        """Test getting daily revenue metrics"""
        # Get daily metrics
        metrics = await analytics_service.get_revenue_metrics(period=TimePeriod.DAILY)
        
        # Verify result
        assert isinstance(metrics, list)
        
        if metrics:  # May be empty if no transactions in date range
            metric = metrics[0]
            
            # Verify metric structure
            assert isinstance(metric, RevenueMetric)
            assert metric.period == "daily"
            assert metric.date is not None
            assert metric.total_revenue >= 0
            assert metric.subscription_revenue >= 0
            assert metric.transaction_revenue >= 0
            assert metric.refund_amount >= 0
            assert metric.net_revenue >= 0
            assert metric.transaction_count >= 0
            assert metric.average_transaction_value >= 0
            assert metric.new_customers >= 0
            assert metric.churned_customers >= 0
            assert metric.customer_count >= 0
            
            # Verify calculations
            assert metric.net_revenue == metric.total_revenue - metric.refund_amount
            if metric.transaction_count > 0:
                assert metric.average_transaction_value == metric.total_revenue / metric.transaction_count
            
            # Verify sorting (ascending by date)
            dates = [m.date for m in metrics]
            assert dates == sorted(dates)
    
    @pytest.mark.asyncio
    async def test_get_revenue_metrics_weekly(self, analytics_service):
        """Test getting weekly revenue metrics"""
        # Get weekly metrics
        metrics = await analytics_service.get_revenue_metrics(period=TimePeriod.WEEKLY)
        
        # Verify result
        assert isinstance(metrics, list)
        
        if metrics:
            metric = metrics[0]
            assert metric.period == "weekly"
            assert metric.total_revenue >= 0
    
    @pytest.mark.asyncio
    async def test_get_revenue_metrics_monthly(self, analytics_service):
        """Test getting monthly revenue metrics"""
        # Get monthly metrics
        metrics = await analytics_service.get_revenue_metrics(period=TimePeriod.MONTHLY)
        
        # Verify result
        assert isinstance(metrics, list)
        
        if metrics:
            metric = metrics[0]
            assert metric.period == "monthly"
            assert metric.total_revenue >= 0
    
    @pytest.mark.asyncio
    async def test_get_revenue_metrics_with_date_range(self, analytics_service):
        """Test getting revenue metrics with date range"""
        now = datetime.utcnow()
        start_date = now - timedelta(days=30)
        end_date = now - timedelta(days=15)
        
        # Get metrics with date range
        metrics = await analytics_service.get_revenue_metrics(
            period=TimePeriod.DAILY,
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify result
        assert isinstance(metrics, list)
        
        # All metrics should be within date range
        for metric in metrics:
            assert start_date <= metric.date <= end_date
    
    @pytest.mark.asyncio
    async def test_revenue_metric_to_dict(self, analytics_service):
        """Test converting revenue metric to dictionary"""
        # Get a metric
        metrics = await analytics_service.get_revenue_metrics(period=TimePeriod.MONTHLY)
        
        if metrics:
            metric = metrics[0]
            
            # Convert to dict
            metric_dict = metric.to_dict()
            
            # Verify dictionary structure
            assert isinstance(metric_dict, dict)
            assert metric_dict["period"] == "monthly"
            assert "date" in metric_dict
            assert "total_revenue" in metric_dict
            assert "subscription_revenue" in metric_dict
            assert "transaction_revenue" in metric_dict
            assert "refund_amount" in metric_dict
            assert "net_revenue" in metric_dict
            assert "transaction_count" in metric_dict
            assert "average_transaction_value" in metric_dict
            assert "new_customers" in metric_dict
            assert "churned_customers" in metric_dict
            assert "customer_count" in metric_dict
            
            # Verify data types
            assert isinstance(metric_dict["total_revenue"], float)
            assert isinstance(metric_dict["transaction_count"], int)
            assert isinstance(metric_dict["new_customers"], int)
    
    @pytest.mark.asyncio
    async def test_get_payment_method_metrics(self, analytics_service):
        """Test getting payment method metrics"""
        # Get payment method metrics
        metrics = await analytics_service.get_payment_method_metrics()
        
        # Verify result
        assert isinstance(metrics, list)
        assert len(metrics) > 0
        
        metric = metrics[0]
        
        # Verify metric structure
        assert isinstance(metric, PaymentMethodMetric)
        assert metric.payment_method is not None
        assert metric.transaction_count >= 0
        assert metric.total_amount >= 0
        assert metric.average_amount >= 0
        assert 0 <= metric.success_rate <= 1
        assert 0 <= metric.refund_rate <= 1
        
        # Verify calculations
        if metric.transaction_count > 0:
            assert metric.average_amount == metric.total_amount / metric.transaction_count
        
        # Verify sorting (by total amount descending)
        amounts = [m.total_amount for m in metrics]
        assert amounts == sorted(amounts, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_payment_method_metrics_with_date_range(self, analytics_service):
        """Test getting payment method metrics with date range"""
        now = datetime.utcnow()
        start_date = now - timedelta(days=30)
        
        # Get metrics with date range
        metrics = await analytics_service.get_payment_method_metrics(
            start_date=start_date
        )
        
        # Verify result
        assert isinstance(metrics, list)
        
        # Should have metrics for common payment methods
        payment_methods = [m.payment_method for m in metrics]
        assert "credit_card" in payment_methods
        assert "paypal" in payment_methods
        assert "bank_transfer" in payment_methods
    
    @pytest.mark.asyncio
    async def test_payment_method_metric_to_dict(self, analytics_service):
        """Test converting payment method metric to dictionary"""
        # Get metrics
        metrics = await analytics_service.get_payment_method_metrics()
        
        if metrics:
            metric = metrics[0]
            
            # Convert to dict
            metric_dict = metric.to_dict()
            
            # Verify dictionary structure
            assert isinstance(metric_dict, dict)
            assert metric_dict["payment_method"] == metric.payment_method
            assert metric_dict["transaction_count"] == metric.transaction_count
            assert metric_dict["total_amount"] == metric.total_amount
            assert metric_dict["average_amount"] == metric.average_amount
            assert metric_dict["success_rate"] == metric.success_rate
            assert metric_dict["refund_rate"] == metric.refund_rate
            
            # Verify data types
            assert isinstance(metric_dict["transaction_count"], int)
            assert isinstance(metric_dict["total_amount"], float)
            assert isinstance(metric_dict["success_rate"], float)
    
    @pytest.mark.asyncio
    async def test_get_customer_lifetime_values(self, analytics_service):
        """Test getting customer lifetime values"""
        # Get CLV metrics
        clv_list = await analytics_service.get_customer_lifetime_values()
        
        # Verify result
        assert isinstance(clv_list, list)
        assert len(clv_list) > 0
        
        clv = clv_list[0]
        
        # Verify CLV structure
        assert isinstance(clv, CustomerLifetimeValue)
        assert clv.customer_id is not None
        assert clv.total_revenue >= 0
        assert clv.first_purchase_date is not None
        assert clv.last_purchase_date is not None
        assert clv.purchase_count >= 0
        assert clv.average_order_value >= 0
        assert clv.predicted_lifetime_value >= 0
        assert clv.customer_segment in ["high_value", "medium_value", "low_value"]
        
        # Verify calculations
        if clv.purchase_count > 0:
            assert clv.average_order_value == clv.total_revenue / clv.purchase_count
        
        # Verify sorting (by predicted lifetime value descending)
        clv_values = [c.predicted_lifetime_value for c in clv_list]
        assert clv_values == sorted(clv_values, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_customer_lifetime_values_with_segment_filter(self, analytics_service):
        """Test getting customer lifetime values with segment filter"""
        # Get high-value customers
        high_value_clv = await analytics_service.get_customer_lifetime_values(
            segment="high_value"
        )
        
        # Verify all are high-value
        for clv in high_value_clv:
            assert clv.customer_segment == "high_value"
            assert clv.predicted_lifetime_value > 1000
        
        # Get medium-value customers
        medium_value_clv = await analytics_service.get_customer_lifetime_values(
            segment="medium_value"
        )
        
        # Verify all are medium-value
        for clv in medium_value_clv:
            assert clv.customer_segment == "medium_value"
            assert 500 < clv.predicted_lifetime_value <= 1000
        
        # Get low-value customers
        low_value_clv = await analytics_service.get_customer_lifetime_values(
            segment="low_value"
        )
        
        # Verify all are low-value
        for clv in low_value_clv:
            assert clv.customer_segment == "low_value"
            assert clv.predicted_lifetime_value <= 500
    
    @pytest.mark.asyncio
    async def test_get_customer_lifetime_values_with_limit(self, analytics_service):
        """Test getting customer lifetime values with limit"""
        # Get limited number of CLV metrics
        limit = 10
        clv_list = await analytics_service.get_customer_lifetime_values(limit=limit)
        
        # Verify result
        assert isinstance(clv_list, list)
        assert len(clv_list) <= limit
    
    @pytest.mark.asyncio
    async def test_customer_lifetime_value_to_dict(self, analytics_service):
        """Test converting customer lifetime value to dictionary"""
        # Get CLV metrics
        clv_list = await analytics_service.get_customer_lifetime_values(limit=1)
        
        if clv_list:
            clv = clv_list[0]
            
            # Convert to dict
            clv_dict = clv.to_dict()
            
            # Verify dictionary structure
            assert isinstance(clv_dict, dict)
            assert clv_dict["customer_id"] == clv.customer_id
            assert clv_dict["total_revenue"] == clv.total_revenue
            assert "first_purchase_date" in clv_dict
            assert "last_purchase_date" in clv_dict
            assert clv_dict["purchase_count"] == clv.purchase_count
            assert clv_dict["average_order_value"] == clv.average_order_value
            assert clv_dict["predicted_lifetime_value"] == clv.predicted_lifetime_value
            assert clv_dict["customer_segment"] == clv.customer_segment
            
            # Verify data types
            assert isinstance(clv_dict["total_revenue"], (int, float))  # Can be int or float
            assert isinstance(clv_dict["purchase_count"], int)
            assert isinstance(clv_dict["predicted_lifetime_value"], (int, float))  # Can be int or float
    
    @pytest.mark.asyncio
    async def test_get_financial_summary(self, analytics_service):
        """Test getting comprehensive financial summary"""
        # Get financial summary
        summary = await analytics_service.get_financial_summary()
        
        # Verify result
        assert isinstance(summary, dict)
        
        # Check required fields
        assert "period" in summary
        assert "summary" in summary
        assert "revenue_by_period" in summary
        assert "payment_methods" in summary
        assert "top_customers" in summary
        assert "key_metrics" in summary
        
        # Check period
        period = summary["period"]
        assert isinstance(period, dict)
        assert "start" in period
        assert "end" in period
        
        # Check summary
        financial_summary = summary["summary"]
        assert "total_revenue" in financial_summary
        assert "total_transactions" in financial_summary
        assert "average_transaction_value" in financial_summary
        assert "revenue_growth_percent" in financial_summary
        assert "total_customers" in financial_summary
        assert "active_customers" in financial_summary
        assert "customer_churn_rate" in financial_summary
        assert "monthly_recurring_revenue" in financial_summary
        
        # Verify data types
        assert isinstance(financial_summary["total_revenue"], float)
        assert isinstance(financial_summary["total_transactions"], int)
        assert isinstance(financial_summary["revenue_growth_percent"], float)
        assert isinstance(financial_summary["customer_churn_rate"], float)
        
        # Check revenue by period
        revenue_by_period = summary["revenue_by_period"]
        assert isinstance(revenue_by_period, list)
        
        # Check payment methods
        payment_methods = summary["payment_methods"]
        assert isinstance(payment_methods, list)
        
        # Check top customers
        top_customers = summary["top_customers"]
        assert isinstance(top_customers, list)
        assert len(top_customers) <= 10
        
        # Check key metrics
        key_metrics = summary["key_metrics"]
        assert isinstance(key_metrics, dict)
        assert "customer_acquisition_cost" in key_metrics
        assert "lifetime_value" in key_metrics
        assert "lifetime_value_to_cac_ratio" in key_metrics
        assert "average_revenue_per_user" in key_metrics
        assert "refund_rate" in key_metrics
        assert "payment_success_rate" in key_metrics
    
    @pytest.mark.asyncio
    async def test_get_financial_summary_with_date_range(self, analytics_service):
        """Test getting financial summary with date range"""
        now = datetime.utcnow()
        start_date = now - timedelta(days=90)
        end_date = now - timedelta(days=30)
        
        # Get summary with date range
        summary = await analytics_service.get_financial_summary(
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify result
        assert isinstance(summary, dict)
        assert summary["period"]["start"] == start_date.isoformat()
        assert summary["period"]["end"] == end_date.isoformat()
    
    @pytest.mark.asyncio
    async def test_get_forecast_monthly(self, analytics_service):
        """Test getting monthly revenue forecast"""
        # Get forecast
        forecast = await analytics_service.get_forecast(
            periods=6,
            period_type=TimePeriod.MONTHLY
        )
        
        # Verify result
        assert isinstance(forecast, dict)
        
        # Check required fields
        assert "forecast_periods" in forecast
        assert "period_type" in forecast
        assert "historical_data_points" in forecast
        assert "historical_average_revenue" in forecast
        assert "forecast" in forecast
        assert "summary" in forecast
        
        # Verify forecast parameters
        assert forecast["forecast_periods"] == 6
        assert forecast["period_type"] == "monthly"
        assert forecast["historical_data_points"] > 0
        assert forecast["historical_average_revenue"] >= 0
        
        # Check forecast data
        forecast_data = forecast["forecast"]
        assert isinstance(forecast_data, list)
        assert len(forecast_data) == 6
        
        # Check first forecast period
        if forecast_data:
            period = forecast_data[0]
            assert "period" in period
            assert "date" in period
            assert "forecasted_revenue" in period
            assert "confidence_interval_low" in period
            assert "confidence_interval_high" in period
            
            # Verify forecasted revenue is positive
            assert period["forecasted_revenue"] > 0
            
            # Verify confidence intervals
            assert period["confidence_interval_low"] <= period["forecasted_revenue"]
            assert period["confidence_interval_high"] >= period["forecasted_revenue"]
        
        # Check summary
        summary = forecast["summary"]
        assert "total_forecasted_revenue" in summary
        assert "average_forecasted_revenue" in summary
        assert "growth_rate_per_period" in summary
        
        # Verify summary calculations
        if forecast_data:
            total_forecasted = sum(f["forecasted_revenue"] for f in forecast_data)
            assert summary["total_forecasted_revenue"] == total_forecasted
            
            average_forecasted = total_forecasted / len(forecast_data)
            assert summary["average_forecasted_revenue"] == average_forecasted
    
    @pytest.mark.asyncio
    async def test_get_forecast_weekly(self, analytics_service):
        """Test getting weekly revenue forecast"""
        # Get forecast
        forecast = await analytics_service.get_forecast(
            periods=8,
            period_type=TimePeriod.WEEKLY
        )
        
        # Verify result
        assert isinstance(forecast, dict)
        assert forecast["period_type"] == "weekly"
        assert forecast["forecast_periods"] == 8
        
        forecast_data = forecast["forecast"]
        assert isinstance(forecast_data, list)
        assert len(forecast_data) == 8
    
    @pytest.mark.asyncio
    async def test_get_forecast_daily(self, analytics_service):
        """Test getting daily revenue forecast"""
        # Get forecast
        forecast = await analytics_service.get_forecast(
            periods=14,
            period_type=TimePeriod.DAILY
        )
        
        # Verify result
        assert isinstance(forecast, dict)
        assert forecast["period_type"] == "daily"
        assert forecast["forecast_periods"] == 14
        
        forecast_data = forecast["forecast"]
        assert isinstance(forecast_data, list)
        assert len(forecast_data) == 14
    
    @pytest.mark.asyncio
    async def test_calculate_revenue_metric(self, analytics_service):
        """Test revenue metric calculation"""
        # Create sample transactions
        transactions = [
            {
                "date": datetime.utcnow(),
                "amount": 49.99,
                "status": "completed",
                "type": "subscription",
                "customer_id": "cust_001"
            },
            {
                "date": datetime.utcnow(),
                "amount": 29.99,
                "status": "completed",
                "type": "one_time",
                "customer_id": "cust_002"
            },
            {
                "date": datetime.utcnow(),
                "amount": 19.99,
                "status": "failed",
                "type": "one_time",
                "customer_id": "cust_003"
            }
        ]
        
        # Calculate metric
        metric = analytics_service._calculate_revenue_metric(
            transactions=transactions,
            period="daily",
            date=datetime.utcnow()
        )
        
        # Verify calculations
        assert metric.total_revenue == 79.98  # 49.99 + 29.99
        assert metric.subscription_revenue == 49.99
        assert metric.transaction_revenue == 29.99
        assert metric.refund_amount == 79.98 * 0.05  # 5% refund rate
        assert metric.net_revenue == metric.total_revenue - metric.refund_amount
        assert metric.transaction_count == 2  # Only completed transactions
        assert metric.average_transaction_value == 79.98 / 2
        
        # Verify mock customer metrics
        assert metric.new_customers >= 0
        assert metric.churned_customers >= 0
        assert metric.customer_count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])