"""SIMP Integration Modules

Provides integration layers for external systems like KashClaw trading organs,
Kloutbot code generation, quantumArb arbitrage trading, and the shared
TimesFM forecasting service.
"""

from simp.integrations.trading_organ import (
    TradingOrgan,
    TradeExecution,
    OrganExecutionResult,
    OrganType,
    ExecutionStatus
)
from simp.integrations.kashclaw_shim import (
    KashClawSimpAgent,
    KashClawRegistry,
    get_registry
)
from simp.integrations.timesfm_service import (
    TimesFMService,
    ForecastRequest,
    ForecastResponse,
    ContextCache,
    ForecastAuditLog,
    get_timesfm_service,
    get_timesfm_service_sync,
)
from simp.integrations.timesfm_policy_engine import (
    PolicyEngine,
    AgentContext,
    PolicyDecision,
    make_agent_context_for,
)

__all__ = [
    # Trading organs
    "TradingOrgan",
    "TradeExecution",
    "OrganExecutionResult",
    "OrganType",
    "ExecutionStatus",
    # KashClaw shim
    "KashClawSimpAgent",
    "KashClawRegistry",
    "get_registry",
    # TimesFM service
    "TimesFMService",
    "ForecastRequest",
    "ForecastResponse",
    "ContextCache",
    "ForecastAuditLog",
    "get_timesfm_service",
    "get_timesfm_service_sync",
    # TimesFM policy engine
    "PolicyEngine",
    "AgentContext",
    "PolicyDecision",
    "make_agent_context_for",
]
