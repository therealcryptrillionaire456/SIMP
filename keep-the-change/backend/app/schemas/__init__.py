"""
KEEPTHECHANGE.com Pydantic Schemas
"""

from .user import *
from .shopping import *
from .payment import *
from .crypto import *
from .subscription import *
from .admin import *

__all__ = [
    # User schemas
    "UserBase",
    "UserCreate", 
    "UserUpdate",
    "UserLogin",
    "SocialAuthRequest",
    "UserResponse",
    "TokenResponse",
    "UserStatsResponse",
    
    # Shopping schemas
    "ShoppingListBase",
    "ShoppingListCreate",
    "ShoppingListUpdate",
    "ShoppingListResponse",
    "ListItemBase",
    "ListItemCreate",
    "ListItemResponse",
    "PriceComparisonResponse",
    "ProductSearchItem",
    "ProductSearchResponse",
    "OptimizationRequest",
    "OptimizationItem",
    "OptimizationResponse",
    "PurchaseRequest",
    "PurchaseResponse",
    "ReceiptScanRequest",
    "ReceiptScanResponse",
    "BarcodeScanRequest",
    "BarcodeScanResponse",
    
    # Payment schemas
    "PaymentMethodBase",
    "PaymentMethodCreate",
    "PaymentMethodUpdate",
    "PaymentMethodResponse",
    "PurchaseResponse",
    "RefundRequest",
    "RefundResponse",
    "PaymentIntentRequest",
    "PaymentIntentResponse",
    "InvoiceResponse",
    "TransactionSummary",
    "WebhookEvent",
    
    # Crypto schemas
    "CryptoInvestmentBase",
    "CryptoInvestmentResponse",
    "UserInvestmentCreate",
    "UserInvestmentResponse",
    "AgentPortfolioResponse",
    "ReturnsDistributionResponse",
    "CryptoTradeResponse",
    "TipRequest",
    "InvestmentStatsResponse",
    "SIMPInvestmentRequest",
    "SIMPInvestmentResponse",
    "WalletBalanceResponse",
    
    # Subscription schemas
    "SubscriptionTierBase",
    "SubscriptionTierResponse",
    "SubscriptionBase",
    "SubscriptionCreate",
    "SubscriptionUpdate",
    "SubscriptionResponse",
    "InvoiceResponse",
    "PromoCodeRequest",
    "PromoCodeResponse",
    "BillingInfoResponse",
    "SubscriptionComparison",
    "UpgradePath",
    "TrialStatus",
    
    # Admin schemas
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