"""SIMP Integration Modules.

Expose stable package-level names without eagerly importing the heavier
KashClaw shim. That shim depends on BRP, and BRP transitively imports organs,
which import this package during broker/test bootstrap.
"""

from importlib import import_module
from typing import TYPE_CHECKING

from simp.integrations.trading_organ import (
    ExecutionStatus,
    OrganExecutionResult,
    OrganType,
    TradeExecution,
    TradingOrgan,
)
from simp.integrations.timesfm_policy_engine import (
    AgentContext,
    PolicyDecision,
    PolicyEngine,
    make_agent_context_for,
)
from simp.integrations.timesfm_service import (
    ContextCache,
    ForecastAuditLog,
    ForecastRequest,
    ForecastResponse,
    TimesFMService,
    get_timesfm_service,
    get_timesfm_service_sync,
)

if TYPE_CHECKING:
    from simp.integrations.kashclaw_shim import (
        KashClawRegistry,
        KashClawSimpAgent,
        get_registry,
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


def __getattr__(name: str):
    if name in {"KashClawSimpAgent", "KashClawRegistry", "get_registry"}:
        module = import_module("simp.integrations.kashclaw_shim")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
