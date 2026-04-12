"""
Pydantic schemas for admin models
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import uuid


class AdminUserResponse(BaseModel):
    """Schema for admin user response"""
    id: uuid.UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    subscription_tier: str
    subscription_status: str
    total_savings: float
    total_invested: float
    crypto_balance: float
    total_returns: float
    email_verified: bool
    social_auth_provider: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    deleted_at: Optional[datetime]
    
    class Config:
        orm_mode = True
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.email.split('@')[0]
    
    @property
    def is_active(self) -> bool:
        """Check if user account is active"""
        return self.deleted_at is None and self.subscription_status == "active"


class AdminStatsResponse(BaseModel):
    """Schema for admin statistics response"""
    users: Dict[str, int]
    financial: Dict[str, float]
    crypto: Dict[str, float]
    subscriptions: Dict[str, Any]


class SystemHealthResponse(BaseModel):
    """Schema for system health response"""
    status: str
    timestamp: datetime
    components: Dict[str, Dict[str, Any]]
    metrics: Dict[str, Any]
    alerts: List[Dict[str, Any]]


class AuditLogResponse(BaseModel):
    """Schema for audit log response"""
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    
    class Config:
        orm_mode = True


class FinancialReportResponse(BaseModel):
    """Schema for financial report response"""
    period: str
    start_date: datetime
    end_date: datetime
    summary: Dict[str, Any]
    daily_data: List[Dict[str, Any]]
    recommendations: List[str]


class AdminAlert(BaseModel):
    """Schema for admin alert"""
    id: str
    title: str
    description: str
    severity: str
    component: str
    created_at: datetime
    resolved: bool
    resolution_time: Optional[datetime]


class UserActivityReport(BaseModel):
    """Schema for user activity report"""
    user_id: uuid.UUID
    email: str
    last_active: Optional[datetime]
    total_purchases: int
    total_spent: float
    total_savings: float
    subscription_tier: str
    days_since_signup: int
    activity_score: float


class SystemMetrics(BaseModel):
    """Schema for system metrics"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    request_rate: float
    error_rate: float
    response_time_p95: float


class DatabaseReport(BaseModel):
    """Schema for database report"""
    total_tables: int
    total_rows: int
    database_size_mb: float
    index_size_mb: float
    last_backup: Optional[datetime]
    replication_lag_seconds: Optional[float]
    slow_queries: List[Dict[str, Any]]


class SecurityReport(BaseModel):
    """Schema for security report"""
    failed_login_attempts_24h: int
    suspicious_activities: List[Dict[str, Any]]
    api_key_rotations: int
    ssl_cert_expiry: Optional[datetime]
    firewall_rules: List[Dict[str, Any]]
    vulnerability_scan_results: Dict[str, Any]


class PerformanceReport(BaseModel):
    """Schema for performance report"""
    period: str
    average_response_time: float
    p95_response_time: float
    p99_response_time: float
    request_count: int
    error_count: int
    success_rate: float
    slow_endpoints: List[Dict[str, Any]]


class BusinessMetrics(BaseModel):
    """Schema for business metrics"""
    date: datetime
    active_users: int
    new_users: int
    revenue: float
    transactions: int
    average_order_value: float
    customer_acquisition_cost: float
    lifetime_value: float
    churn_rate: float


# Export all schemas
__all__ = [
    "AdminUserResponse",
    "AdminStatsResponse",
    "SystemHealthResponse",
    "AuditLogResponse",
    "FinancialReportResponse",
    "AdminAlert",
    "UserActivityReport",
    "SystemMetrics",
    "DatabaseReport",
    "SecurityReport",
    "PerformanceReport",
    "BusinessMetrics"
]