"""
External Integration Layer Package.
"""

from integrations.external_integration import (
    ExternalIntegrationLayer, IntegrationConfig, IntegrationMetrics,
    ExternalRequest, ExternalResponse, CachedData,
    IntegrationType, IntegrationStatus, DataFormat
)

from integrations.api_client import (
    APIClient, APIClientConfig, APIRequest, APIResponse,
    PACERClient, SECEdgarClient, USPTOClient
)

__version__ = "1.0.0"
__author__ = "Pentagram Legal Department"
__description__ = "External Integration Layer for connecting to legal systems"

__all__ = [
    # Main integration layer
    "ExternalIntegrationLayer",
    "IntegrationConfig",
    "IntegrationMetrics",
    "ExternalRequest",
    "ExternalResponse",
    "CachedData",
    
    # Enums
    "IntegrationType",
    "IntegrationStatus",
    "DataFormat",
    
    # API clients
    "APIClient",
    "APIClientConfig",
    "APIRequest",
    "APIResponse",
    "PACERClient",
    "SECEdgarClient",
    "USPTOClient"
]