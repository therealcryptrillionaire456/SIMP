"""
A2A/FinancialOps core layer for SIMP system.

This module provides pure, side-effect-free schemas and aggregators
for agent decision summaries, portfolio posture analysis, and A2A plan generation.
"""

from .a2a_schema import (
    AgentDecisionSummary,
    PortfolioPosture,
    A2APlan,
    Side,
    RiskPosture,
    ExecutionMode,
    validate_agent_decision_summary,
    validate_portfolio_posture,
    validate_a2a_plan,
)

from .a2a_aggregator import (
    build_a2a_plan,
    compute_aggregate_exposure,
    classify_posture,
    filter_decisions_by_confidence,
    group_decisions_by_instrument,
    calculate_net_direction,
)

from .a2a_safety import (
    evaluate_risk,
    must_block,
    get_safety_limits,
    check_plan_safety,
)

__all__ = [
    # Schema classes and enums
    "AgentDecisionSummary",
    "PortfolioPosture",
    "A2APlan",
    "Side",
    "RiskPosture",
    "ExecutionMode",
    
    # Validation functions
    "validate_agent_decision_summary",
    "validate_portfolio_posture",
    "validate_a2a_plan",
    
    # Aggregator functions
    "build_a2a_plan",
    "compute_aggregate_exposure",
    "classify_posture",
    "filter_decisions_by_confidence",
    "group_decisions_by_instrument",
    "calculate_net_direction",
    
    # Safety functions
    "evaluate_risk",
    "must_block",
    "get_safety_limits",
    "check_plan_safety",
]