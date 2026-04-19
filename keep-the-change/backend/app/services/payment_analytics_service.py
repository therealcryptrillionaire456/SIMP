"""
Payment analytics service for KEEPTHECHANGE.com

This service provides analytics and insights for payment processing, revenue tracking, and financial reporting.
"""

import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import json
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class TimePeriod(str, Enum):
    """Time period for analytics"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class RevenueMetric:
    """Revenue metric definition"""
    period: str
    date: datetime
    total_revenue: float
    subscription_revenue: float
    transaction_revenue: float
    refund_amount: float
    net_revenue: float
    transaction_count: int
    average_transaction_value: float
    new_customers: int
    churned_customers: int
    customer_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "period": self.period,
            "date": self.date.isoformat(),
            "total_revenue": self.total_revenue,
            "subscription_revenue": self.subscription_revenue,
            "transaction_revenue": self.transaction_revenue,
            "refund_amount": self.refund_amount,
            "net_revenue": self.net_revenue,
            "transaction_count": self.transaction_count,
            "average_transaction_value": self.average_transaction_value,
            "new_customers": self.new_customers,
            "churned_customers": self.churned_customers,
            "customer_count": self.customer_count
        }


@dataclass
class PaymentMethodMetric:
    """Payment method metric definition"""
    payment_method: str
    transaction_count: int
    total_amount: float
    average_amount: float
    success_rate: float
    refund_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "payment_method": self.payment_method,
            "transaction_count": self.transaction_count,
            "total_amount": self.total_amount,
            "average_amount": self.average_amount,
            "success_rate": self.success_rate,
            "refund_rate": self.refund_rate
        }


@dataclass
class CustomerLifetimeValue:
    """Customer lifetime value metric"""
    customer_id: str
    total_revenue: float
    first_purchase_date: datetime
    last_purchase_date: datetime
    purchase_count: int
    average_order_value: float
    predicted_lifetime_value: float
    customer_segment: str  # high_value, medium_value, low_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "customer_id": self.customer_id,
            "total_revenue": self.total_revenue,
            "first_purchase_date": self.first_purchase_date.isoformat(),
            "last_purchase_date": self.last_purchase_date.isoformat(),
            "purchase_count": self.purchase_count,
            "average_order_value": self.average_order_value,
            "predicted_lifetime_value": self.predicted_lifetime_value,
            "customer_segment": self.customer_segment
        }


class PaymentAnalyticsService:
    """Payment analytics service"""
    
    def __init__(self, payment_service=None, billing_service=None, subscription_service=None, refund_service=None):
        self.payment_service = payment_service
        self.billing_service = billing_service
        self.subscription_service = subscription_service
        self.refund_service = refund_service
        
        # Mock data for demonstration
        self._mock_transactions = self._generate_mock_transactions()
        self._mock_customers = self._generate_mock_customers()
    
    def _generate_mock_transactions(self) -> List[Dict[str, Any]]:
        """Generate mock transaction data for demonstration"""
        transactions = []
        now = datetime.utcnow()
        
        # Generate 6 months of data
        for month_offset in range(6, 0, -1):
            month_date = now - timedelta(days=30 * month_offset)
            
            # Generate daily transactions for each month
            for day in range(30):
                transaction_date = month_date + timedelta(days=day)
                
                # Skip weekends (fewer transactions)
                if transaction_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                    continue
                
                # Generate 5-20 transactions per day
                for _ in range(5, 21):
                    amount = round(10 + (100 * (day % 10) / 10), 2)  # Varying amounts
                    payment_method = ["credit_card", "paypal", "bank_transfer"][day % 3]
                    status = "completed" if day % 20 != 0 else "failed"  # 5% failure rate
                    
                    transactions.append({
                        "transaction_id": f"tx_{uuid.uuid4().hex[:16]}",
                        "date": transaction_date,
                        "amount": amount,
                        "currency": "USD",
                        "payment_method": payment_method,
                        "status": status,
                        "customer_id": f"cust_{((day * 7) % 100) + 1:03d}",
                        "type": "subscription" if day % 3 == 0 else "one_time"
                    })
        
        return transactions
    
    def _generate_mock_customers(self) -> List[Dict[str, Any]]:
        """Generate mock customer data for demonstration"""
        customers = []
        now = datetime.utcnow()
        
        for i in range(1, 101):
            join_date = now - timedelta(days=30 * (i % 6))
            last_purchase = now - timedelta(days=(i % 30))
            
            customers.append({
                "customer_id": f"cust_{i:03d}",
                "join_date": join_date,
                "last_purchase_date": last_purchase,
                "total_spent": round(100 + (i * 10), 2),
                "purchase_count": (i % 10) + 1,
                "subscription_plan": ["free", "basic", "pro", "business"][i % 4],
                "country": ["US", "CA", "UK", "AU", "DE"][i % 5]
            })
        
        return customers
    
    async def get_revenue_metrics(
        self,
        period: TimePeriod = TimePeriod.MONTHLY,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[RevenueMetric]:
        """Get revenue metrics for a time period"""
        try:
            # Filter transactions by date range
            filtered_transactions = self._mock_transactions
            
            if start_date:
                filtered_transactions = [t for t in filtered_transactions if t["date"] >= start_date]
            if end_date:
                filtered_transactions = [t for t in filtered_transactions if t["date"] <= end_date]
            
            # Group by period
            metrics = []
            
            if period == TimePeriod.DAILY:
                # Group by day
                dates = sorted(set(t["date"].date() for t in filtered_transactions))
                for date in dates:
                    day_transactions = [t for t in filtered_transactions if t["date"].date() == date]
                    metric = self._calculate_revenue_metric(day_transactions, "daily", datetime.combine(date, datetime.min.time()))
                    metrics.append(metric)
            
            elif period == TimePeriod.WEEKLY:
                # Group by week
                transactions_by_week = {}
                for transaction in filtered_transactions:
                    week_start = transaction["date"] - timedelta(days=transaction["date"].weekday())
                    week_key = week_start.date()
                    
                    if week_key not in transactions_by_week:
                        transactions_by_week[week_key] = []
                    transactions_by_week[week_key].append(transaction)
                
                for week_start, week_transactions in transactions_by_week.items():
                    metric = self._calculate_revenue_metric(week_transactions, "weekly", datetime.combine(week_start, datetime.min.time()))
                    metrics.append(metric)
            
            elif period == TimePeriod.MONTHLY:
                # Group by month
                transactions_by_month = {}
                for transaction in filtered_transactions:
                    month_key = transaction["date"].replace(day=1).date()
                    
                    if month_key not in transactions_by_month:
                        transactions_by_month[month_key] = []
                    transactions_by_month[month_key].append(transaction)
                
                for month_start, month_transactions in transactions_by_month.items():
                    metric = self._calculate_revenue_metric(month_transactions, "monthly", datetime.combine(month_start, datetime.min.time()))
                    metrics.append(metric)
            
            # Sort by date ascending
            metrics.sort(key=lambda x: x.date)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting revenue metrics: {str(e)}")
            return []
    
    def _calculate_revenue_metric(
        self,
        transactions: List[Dict[str, Any]],
        period: str,
        date: datetime
    ) -> RevenueMetric:
        """Calculate revenue metric for a set of transactions"""
        # Filter completed transactions
        completed_transactions = [t for t in transactions if t["status"] == "completed"]
        
        # Calculate totals
        total_revenue = sum(t["amount"] for t in completed_transactions)
        subscription_revenue = sum(t["amount"] for t in completed_transactions if t["type"] == "subscription")
        transaction_revenue = sum(t["amount"] for t in completed_transactions if t["type"] == "one_time")
        
        # Mock refund amount (5% of revenue)
        refund_amount = total_revenue * 0.05
        net_revenue = total_revenue - refund_amount
        
        # Transaction counts
        transaction_count = len(completed_transactions)
        average_transaction_value = total_revenue / transaction_count if transaction_count > 0 else 0
        
        # Customer metrics (mock)
        unique_customers = len(set(t["customer_id"] for t in completed_transactions))
        new_customers = unique_customers // 4  # Mock: 25% new customers
        churned_customers = unique_customers // 10  # Mock: 10% churn
        customer_count = unique_customers + new_customers - churned_customers
        
        return RevenueMetric(
            period=period,
            date=date,
            total_revenue=total_revenue,
            subscription_revenue=subscription_revenue,
            transaction_revenue=transaction_revenue,
            refund_amount=refund_amount,
            net_revenue=net_revenue,
            transaction_count=transaction_count,
            average_transaction_value=average_transaction_value,
            new_customers=new_customers,
            churned_customers=churned_customers,
            customer_count=customer_count
        )
    
    async def get_payment_method_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[PaymentMethodMetric]:
        """Get metrics by payment method"""
        try:
            # Filter transactions by date range
            filtered_transactions = self._mock_transactions
            
            if start_date:
                filtered_transactions = [t for t in filtered_transactions if t["date"] >= start_date]
            if end_date:
                filtered_transactions = [t for t in filtered_transactions if t["date"] <= end_date]
            
            # Group by payment method
            payment_methods = {}
            
            for transaction in filtered_transactions:
                method = transaction["payment_method"]
                
                if method not in payment_methods:
                    payment_methods[method] = {
                        "transactions": [],
                        "completed": [],
                        "failed": []
                    }
                
                payment_methods[method]["transactions"].append(transaction)
                
                if transaction["status"] == "completed":
                    payment_methods[method]["completed"].append(transaction)
                else:
                    payment_methods[method]["failed"].append(transaction)
            
            # Calculate metrics for each payment method
            metrics = []
            
            for method, data in payment_methods.items():
                total_transactions = len(data["transactions"])
                completed_transactions = len(data["completed"])
                failed_transactions = len(data["failed"])
                
                total_amount = sum(t["amount"] for t in data["completed"])
                average_amount = total_amount / completed_transactions if completed_transactions > 0 else 0
                success_rate = completed_transactions / total_transactions if total_transactions > 0 else 0
                
                # Mock refund rate (varies by payment method)
                refund_rate = {
                    "credit_card": 0.03,
                    "paypal": 0.02,
                    "bank_transfer": 0.01
                }.get(method, 0.02)
                
                metric = PaymentMethodMetric(
                    payment_method=method,
                    transaction_count=total_transactions,
                    total_amount=total_amount,
                    average_amount=average_amount,
                    success_rate=success_rate,
                    refund_rate=refund_rate
                )
                
                metrics.append(metric)
            
            # Sort by total amount descending
            metrics.sort(key=lambda x: x.total_amount, reverse=True)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting payment method metrics: {str(e)}")
            return []
    
    async def get_customer_lifetime_values(
        self,
        segment: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CustomerLifetimeValue]:
        """Get customer lifetime value metrics"""
        try:
            clv_list = []
            
            for customer in self._mock_customers:
                total_revenue = customer["total_spent"]
                purchase_count = customer["purchase_count"]
                average_order_value = total_revenue / purchase_count if purchase_count > 0 else 0
                
                # Simple CLV prediction: average_order_value * expected_purchases_per_year * expected_years
                expected_purchases_per_year = min(purchase_count * 2, 12)  # Mock prediction
                expected_years = 3  # Mock: average customer lifetime
                predicted_lifetime_value = average_order_value * expected_purchases_per_year * expected_years
                
                # Segment customers
                if predicted_lifetime_value > 1000:
                    customer_segment = "high_value"
                elif predicted_lifetime_value > 500:
                    customer_segment = "medium_value"
                else:
                    customer_segment = "low_value"
                
                # Filter by segment if specified
                if segment and customer_segment != segment:
                    continue
                
                clv = CustomerLifetimeValue(
                    customer_id=customer["customer_id"],
                    total_revenue=total_revenue,
                    first_purchase_date=customer["join_date"],
                    last_purchase_date=customer["last_purchase_date"],
                    purchase_count=purchase_count,
                    average_order_value=average_order_value,
                    predicted_lifetime_value=predicted_lifetime_value,
                    customer_segment=customer_segment
                )
                
                clv_list.append(clv)
            
            # Sort by predicted lifetime value descending
            clv_list.sort(key=lambda x: x.predicted_lifetime_value, reverse=True)
            
            return clv_list[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error getting customer lifetime values: {str(e)}")
            return []
    
    async def get_financial_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive financial summary"""
        try:
            # Get revenue metrics
            revenue_metrics = await self.get_revenue_metrics(
                period=TimePeriod.MONTHLY,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get payment method metrics
            payment_method_metrics = await self.get_payment_method_metrics(
                start_date=start_date,
                end_date=end_date
            )
            
            # Get top customers
            top_customers = await self.get_customer_lifetime_values(limit=10)
            
            # Calculate summary statistics
            total_revenue = sum(metric.total_revenue for metric in revenue_metrics)
            total_transactions = sum(metric.transaction_count for metric in revenue_metrics)
            average_transaction_value = total_revenue / total_transactions if total_transactions > 0 else 0
            
            # Calculate growth (if we have at least 2 periods)
            revenue_growth = 0
            if len(revenue_metrics) >= 2:
                recent_revenue = revenue_metrics[-1].total_revenue
                previous_revenue = revenue_metrics[-2].total_revenue
                if previous_revenue > 0:
                    revenue_growth = ((recent_revenue - previous_revenue) / previous_revenue) * 100
            
            # Calculate customer metrics
            total_customers = len(self._mock_customers)
            active_customers = len([c for c in self._mock_customers 
                                  if (datetime.utcnow() - c["last_purchase_date"]).days <= 30])
            
            # Calculate churn rate (mock)
            churn_rate = 0.12  # 12% monthly churn
            
            return {
                "period": {
                    "start": start_date.isoformat() if start_date else "all",
                    "end": end_date.isoformat() if end_date else "all"
                },
                "summary": {
                    "total_revenue": total_revenue,
                    "total_transactions": total_transactions,
                    "average_transaction_value": average_transaction_value,
                    "revenue_growth_percent": revenue_growth,
                    "total_customers": total_customers,
                    "active_customers": active_customers,
                    "customer_churn_rate": churn_rate,
                    "monthly_recurring_revenue": total_revenue / len(revenue_metrics) if revenue_metrics else 0
                },
                "revenue_by_period": [metric.to_dict() for metric in revenue_metrics],
                "payment_methods": [metric.to_dict() for metric in payment_method_metrics],
                "top_customers": [customer.to_dict() for customer in top_customers],
                "key_metrics": {
                    "customer_acquisition_cost": 25.50,  # Mock
                    "lifetime_value": 312.75,  # Mock
                    "lifetime_value_to_cac_ratio": 12.26,  # Mock
                    "average_revenue_per_user": 42.30,  # Mock
                    "refund_rate": 0.05,  # 5%
                    "payment_success_rate": 0.95  # 95%
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting financial summary: {str(e)}")
            return {
                "error": str(e),
                "summary": {
                    "total_revenue": 0,
                    "total_transactions": 0,
                    "average_transaction_value": 0,
                    "revenue_growth_percent": 0,
                    "total_customers": 0,
                    "active_customers": 0,
                    "customer_churn_rate": 0,
                    "monthly_recurring_revenue": 0
                },
                "revenue_by_period": [],
                "payment_methods": [],
                "top_customers": [],
                "key_metrics": {}
            }
    
    async def get_forecast(
        self,
        periods: int = 12,
        period_type: TimePeriod = TimePeriod.MONTHLY
    ) -> Dict[str, Any]:
        """Get revenue forecast"""
        try:
            # Get historical data
            historical_metrics = await self.get_revenue_metrics(
                period=period_type,
                start_date=datetime.utcnow() - timedelta(days=365)
            )
            
            if not historical_metrics:
                return {"error": "No historical data available for forecasting"}
            
            # Extract historical revenue
            historical_revenue = [metric.total_revenue for metric in historical_metrics]
            
            # Simple forecasting: average of last 3 periods with 5% growth
            if len(historical_revenue) >= 3:
                base_revenue = statistics.mean(historical_revenue[-3:])
            else:
                base_revenue = statistics.mean(historical_revenue) if historical_revenue else 0
            
            # Generate forecast
            forecast = []
            current_date = datetime.utcnow()
            
            for i in range(periods):
                if period_type == TimePeriod.MONTHLY:
                    forecast_date = current_date + timedelta(days=30 * (i + 1))
                elif period_type == TimePeriod.WEEKLY:
                    forecast_date = current_date + timedelta(days=7 * (i + 1))
                else:  # DAILY
                    forecast_date = current_date + timedelta(days=i + 1)
                
                # Apply 5% monthly growth
                forecast_revenue = base_revenue * (1.05 ** (i + 1))
                
                forecast.append({
                    "period": i + 1,
                    "date": forecast_date.isoformat(),
                    "forecasted_revenue": forecast_revenue,
                    "confidence_interval_low": forecast_revenue * 0.9,  # ±10%
                    "confidence_interval_high": forecast_revenue * 1.1
                })
            
            return {
                "forecast_periods": periods,
                "period_type": period_type.value,
                "historical_data_points": len(historical_metrics),
                "historical_average_revenue": statistics.mean(historical_revenue) if historical_revenue else 0,
                "forecast": forecast,
                "summary": {
                    "total_forecasted_revenue": sum(f["forecasted_revenue"] for f in forecast),
                    "average_forecasted_revenue": statistics.mean(f["forecasted_revenue"] for f in forecast) if forecast else 0,
                    "growth_rate_per_period": 0.05  # 5%
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            return {
                "error": str(e),
                "forecast": [],
                "summary": {
                    "total_forecasted_revenue": 0,
                    "average_forecasted_revenue": 0,
                    "growth_rate_per_period": 0
                }
            }


# Singleton instance
payment_analytics_service = PaymentAnalyticsService()