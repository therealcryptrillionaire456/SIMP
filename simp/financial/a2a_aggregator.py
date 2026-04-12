"""
A2A Plan Aggregator.

This module aggregates agent decisions into a coherent A2A plan.
All functions are pure (no side effects) and deterministic.

Core function: build_a2a_plan() - creates an A2A plan from agent decisions
by computing aggregate exposures, classifying risk posture, and applying
safety checks.
"""

import uuid
from typing import List, Dict, Any, Tuple
from .a2a_schema import (
    A2APlan, 
    AgentDecisionSummary, 
    PortfolioPosture,
    Side,
    RiskPosture,
    ExecutionMode,
)


def get_aggregator_config() -> Dict[str, Any]:
    """
    Get aggregator configuration parameters.
    
    Returns:
        Dict with configuration values:
            - concentration_threshold: float (0.3 = 30%)
            - confidence_threshold: float (0.3 = 30%)
            - high_confidence_threshold: float (0.8 = 80%)
            - aggressive_posture_threshold: float (0.5 = 50%)
            - large_exposure_threshold: float (10000.0) - for aggressive posture
            - moderate_confidence_threshold: float (0.6 = 60%)
    """
    return {
        "concentration_threshold": 0.3,      # 30% - max single instrument exposure
        "confidence_threshold": 0.3,         # 30% - minimum confidence for execution
        "high_confidence_threshold": 0.8,    # 80% - threshold for "high confidence"
        "aggressive_posture_threshold": 0.5, # 50% - threshold for aggressive posture
        "large_exposure_threshold": 10000.0, # Exposure needed for aggressive posture
        "moderate_confidence_threshold": 0.6, # 60% - threshold for moderate confidence
    }


def build_a2a_plan(agent_decisions: List[AgentDecisionSummary]) -> A2APlan:
    """
    Build an A2A plan from agent decisions.
    
    This is the main aggregator function that:
    1. Computes aggregate exposure per instrument
    2. Classifies portfolio risk posture
    3. Applies safety checks
    4. Determines if execution is allowed
    
    Args:
        agent_decisions: List of agent decision summaries
        
    Returns:
        A2APlan object with aggregated decisions, portfolio posture,
        and safety assessment.
    """
    if not agent_decisions:
        # Empty plan - conservative posture, no execution
        posture = PortfolioPosture(
            aggregate_exposure={},
            risk_posture=RiskPosture.CONSERVATIVE,
        )
        return A2APlan(
            decisions=[],
            portfolio_posture=posture,
            execution_allowed=False,
            execution_reason="No agent decisions provided",
        )
    
    # Compute aggregate exposure per instrument
    aggregate_exposure = compute_aggregate_exposure(agent_decisions)
    
    # Classify risk posture based on exposures
    risk_posture = classify_posture(agent_decisions, aggregate_exposure)
    
    # Create portfolio posture
    portfolio_posture = PortfolioPosture(
        aggregate_exposure=aggregate_exposure,
        risk_posture=risk_posture,
    )
    
    # Apply safety checks
    safety_checks_passed, safety_checks_failed = run_safety_checks(
        agent_decisions, aggregate_exposure, risk_posture
    )
    
    # Determine if execution is allowed
    execution_allowed, execution_reason = determine_execution_permission(
        safety_checks_passed, safety_checks_failed, risk_posture
    )
    
    # Create the A2A plan
    plan = A2APlan(
        decisions=agent_decisions,
        portfolio_posture=portfolio_posture,
        execution_allowed=execution_allowed,
        execution_reason=execution_reason,
        execution_mode=ExecutionMode.SIMULATED_ONLY,  # Always simulated in this phase
        safety_checks_passed=safety_checks_passed,
        safety_checks_failed=safety_checks_failed,
    )
    
    return plan


def compute_aggregate_exposure(decisions: List[AgentDecisionSummary]) -> Dict[str, float]:
    """
    Compute aggregate exposure per instrument.
    
    For each instrument, sums quantities with appropriate sign:
    - BUY: positive contribution
    - SELL: negative contribution  
    - HOLD: zero contribution
    
    Args:
        decisions: List of agent decision summaries
        
    Returns:
        Dictionary mapping instrument -> net exposure
    """
    exposures = {}
    
    for decision in decisions:
        instrument = decision.instrument
        
        # Determine contribution sign based on side
        if decision.side == Side.BUY:
            contribution = decision.quantity
        elif decision.side == Side.SELL:
            contribution = -decision.quantity
        else:  # HOLD
            contribution = 0.0
        
        # Add to aggregate
        if instrument not in exposures:
            exposures[instrument] = 0.0
        exposures[instrument] += contribution
    
    return exposures


def classify_posture(
    decisions: List[AgentDecisionSummary], 
    aggregate_exposure: Dict[str, float]
) -> RiskPosture:
    """
    Classify portfolio risk posture based on agent decisions and exposures.
    
    Classification logic:
    - CONSERVATIVE: All agents agree on HOLD, or exposures are near zero
    - NEUTRAL: Mixed signals but within reasonable bounds
    - AGGRESSIVE: Strong consensus with large exposures
    
    Args:
        decisions: List of agent decision summaries
        aggregate_exposure: Net exposure per instrument
        
    Returns:
        RiskPosture classification
    """
    if not decisions:
        return RiskPosture.CONSERVATIVE
    
    # Count decision types
    buy_count = sum(1 for d in decisions if d.side == Side.BUY)
    sell_count = sum(1 for d in decisions if d.side == Side.SELL)
    hold_count = sum(1 for d in decisions if d.side == Side.HOLD)
    
    # Calculate total absolute exposure
    total_abs_exposure = sum(abs(exposure) for exposure in aggregate_exposure.values())
    
    # Calculate average confidence (if available)
    confidences = [d.confidence for d in decisions if d.confidence is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
    
    # Classification logic
    if hold_count == len(decisions):
        # All agents recommend HOLD
        return RiskPosture.CONSERVATIVE
    
    elif total_abs_exposure == 0:
        # Net zero exposure
        return RiskPosture.CONSERVATIVE
    
    elif buy_count > 0 and sell_count > 0:
        # Conflicting signals
        return RiskPosture.NEUTRAL
    
    # Get configurable thresholds
    config = get_aggregator_config()
    high_conf_threshold = config["high_confidence_threshold"]
    moderate_conf_threshold = config["moderate_confidence_threshold"]
    large_exposure_threshold = config["large_exposure_threshold"]
    
    if avg_confidence > high_conf_threshold and total_abs_exposure > large_exposure_threshold:
        # High confidence with large exposure
        return RiskPosture.AGGRESSIVE
    elif avg_confidence > moderate_conf_threshold:
        # Moderate confidence
        return RiskPosture.NEUTRAL
    else:
        # Low confidence or small exposure
        return RiskPosture.CONSERVATIVE


def run_safety_checks(
    decisions: List[AgentDecisionSummary],
    aggregate_exposure: Dict[str, float],
    risk_posture: RiskPosture
) -> Tuple[List[str], List[str]]:
    """
    Run safety checks on the aggregated plan.
    
    Safety checks:
    1. Agent consensus check
    2. Exposure concentration check
    3. Risk posture appropriateness
    4. Confidence threshold check
    
    Args:
        decisions: List of agent decision summaries
        aggregate_exposure: Net exposure per instrument
        risk_posture: Classified risk posture
        
    Returns:
        Tuple of (passed_checks, failed_checks)
    """
    passed = []
    failed = []
    
    # 1. Agent consensus check
    if check_agent_consensus(decisions):
        passed.append("Agent consensus: All agents agree on direction")
    else:
        failed.append("Agent consensus: Conflicting signals from agents")
    
    # 2. Exposure concentration check
    concentration_ok, concentration_msg = check_exposure_concentration(aggregate_exposure)
    if concentration_ok:
        passed.append(f"Exposure concentration: {concentration_msg}")
    else:
        failed.append(f"Exposure concentration: {concentration_msg}")
    
    # 3. Risk posture appropriateness
    posture_ok, posture_msg = check_risk_posture_appropriateness(decisions, risk_posture)
    if posture_ok:
        passed.append(f"Risk posture: {posture_msg}")
    else:
        failed.append(f"Risk posture: {posture_msg}")
    
    # 4. Confidence threshold check
    confidence_ok, confidence_msg = check_confidence_threshold(decisions)
    if confidence_ok:
        passed.append(f"Confidence: {confidence_msg}")
    else:
        failed.append(f"Confidence: {confidence_msg}")
    
    return passed, failed


def determine_execution_permission(
    passed_checks: List[str],
    failed_checks: List[str],
    risk_posture: RiskPosture
) -> Tuple[bool, str]:
    """
    Determine if execution is allowed based on safety checks.
    
    Execution is allowed only if:
    - All safety checks pass
    - Risk posture is not AGGRESSIVE (in this phase)
    
    Args:
        passed_checks: List of passed safety checks
        failed_checks: List of failed safety checks
        risk_posture: Classified risk posture
        
    Returns:
        Tuple of (execution_allowed, reason)
    """
    if failed_checks:
        return False, f"Execution blocked: {len(failed_checks)} safety check(s) failed"
    
    if risk_posture == RiskPosture.AGGRESSIVE:
        return False, "Execution blocked: Aggressive risk posture requires manual approval"
    
    if not passed_checks:
        return False, "Execution blocked: No safety checks passed"
    
    return True, "Execution allowed: All safety checks passed"


# Helper functions for safety checks
def check_agent_consensus(decisions: List[AgentDecisionSummary]) -> bool:
    """Check if all agents agree on direction for each instrument."""
    if not decisions:
        return True
    
    # Group by instrument
    by_instrument = {}
    for decision in decisions:
        if decision.instrument not in by_instrument:
            by_instrument[decision.instrument] = []
        by_instrument[decision.instrument].append(decision)
    
    # Check each instrument
    for instrument, instr_decisions in by_instrument.items():
        sides = {d.side for d in instr_decisions}
        
        # If we have both BUY and SELL for same instrument, no consensus
        if Side.BUY in sides and Side.SELL in sides:
            return False
        
        # HOLD with any other side is also no consensus
        if Side.HOLD in sides and len(sides) > 1:
            return False
    
    return True


def check_exposure_concentration(aggregate_exposure: Dict[str, float]) -> Tuple[bool, str]:
    """Check if any single instrument has excessive exposure concentration."""
    if not aggregate_exposure:
        return True, "No exposures"
    
    # Calculate total absolute exposure
    total_abs = sum(abs(exposure) for exposure in aggregate_exposure.values())
    if total_abs == 0:
        return True, "Zero total exposure"
    
    # Find maximum concentration
    max_concentration = 0.0
    max_instrument = None
    
    for instrument, exposure in aggregate_exposure.items():
        concentration = abs(exposure) / total_abs
        if concentration > max_concentration:
            max_concentration = concentration
            max_instrument = instrument
    
    # Check against configurable threshold
    config = get_aggregator_config()
    concentration_threshold = config["concentration_threshold"]
    
    if max_concentration > concentration_threshold:
        return False, f"High concentration: {max_instrument} has {max_concentration:.1%} of total exposure (threshold: {concentration_threshold:.0%})"
    elif max_concentration > concentration_threshold / 2:
        return True, f"Moderate concentration: {max_instrument} has {max_concentration:.1%} of total exposure"
    else:
        return True, f"Good diversification: max concentration {max_concentration:.1%}"


def check_risk_posture_appropriateness(
    decisions: List[AgentDecisionSummary],
    risk_posture: RiskPosture
) -> Tuple[bool, str]:
    """Check if the classified risk posture is appropriate for the decisions."""
    if not decisions:
        return True, "No decisions - conservative posture appropriate"
    
    # Get configurable thresholds
    config = get_aggregator_config()
    high_conf_threshold = config["high_confidence_threshold"]
    aggressive_threshold = config["aggressive_posture_threshold"]
    
    # Count high confidence decisions
    high_conf = sum(1 for d in decisions if d.confidence and d.confidence > high_conf_threshold)
    high_conf_pct = high_conf / len(decisions)
    
    # Check if posture matches confidence level
    if risk_posture == RiskPosture.AGGRESSIVE and high_conf_pct < aggressive_threshold:
        return False, f"Aggressive posture with low confidence decisions (need {aggressive_threshold:.0%} high confidence, have {high_conf_pct:.0%})"
    elif risk_posture == RiskPosture.CONSERVATIVE and high_conf_pct > high_conf_threshold:
        return True, "Conservative posture despite high confidence (safe)"
    else:
        return True, f"Posture {risk_posture.value} appropriate for confidence level"


def check_confidence_threshold(decisions: List[AgentDecisionSummary]) -> Tuple[bool, str]:
    """Check if decisions meet minimum confidence thresholds."""
    if not decisions:
        return True, "No decisions to check"
    
    # Get configurable threshold
    config = get_aggregator_config()
    confidence_threshold = config["confidence_threshold"]
    
    # Check each decision
    low_conf_decisions = []
    for decision in decisions:
        if decision.confidence is not None and decision.confidence < confidence_threshold:
            low_conf_decisions.append(decision.agent_name)
    
    if low_conf_decisions:
        agents = ", ".join(low_conf_decisions)
        return False, f"Low confidence (<{confidence_threshold:.0%}) from agents: {agents}"
    
    # Calculate average confidence
    confidences = [d.confidence for d in decisions if d.confidence is not None]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        if avg_conf > 0.7:
            return True, f"High average confidence: {avg_conf:.1%}"
        elif avg_conf > 0.5:
            return True, f"Moderate average confidence: {avg_conf:.1%}"
        else:
            return True, f"Low average confidence: {avg_conf:.1%} (monitor closely)"
    else:
        return True, "No confidence data available"


# Utility functions (compatible with existing code)
def filter_decisions_by_confidence(
    decisions: List[AgentDecisionSummary],
    min_confidence: float = 0.5
) -> List[AgentDecisionSummary]:
    """
    Filter agent decisions by minimum confidence threshold.
    
    Args:
        decisions: List of agent decision summaries
        min_confidence: Minimum confidence threshold (0.0 to 1.0)
        
    Returns:
        Filtered list of decisions with confidence >= min_confidence
    """
    return [d for d in decisions if d.confidence is not None and d.confidence >= min_confidence]


def group_decisions_by_instrument(
    decisions: List[AgentDecisionSummary]
) -> Dict[str, List[AgentDecisionSummary]]:
    """
    Group agent decisions by instrument.
    
    Args:
        decisions: List of agent decision summaries
        
    Returns:
        Dictionary mapping instrument to list of decisions for that instrument
    """
    grouped = {}
    for decision in decisions:
        if decision.instrument not in grouped:
            grouped[decision.instrument] = []
        grouped[decision.instrument].append(decision)
    return grouped


def calculate_net_direction(
    decisions: List[AgentDecisionSummary]
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate net direction and size for each instrument.
    
    Args:
        decisions: List of agent decision summaries
        
    Returns:
        Dictionary mapping instrument to net direction analysis
    """
    grouped = group_decisions_by_instrument(decisions)
    result = {}
    
    for instrument, instr_decisions in grouped.items():
        buy_size = sum(d.quantity for d in instr_decisions if d.side == Side.BUY)
        sell_size = sum(d.quantity for d in instr_decisions if d.side == Side.SELL)
        net_size = buy_size - sell_size
        
        # Determine net direction
        if net_size > 0:
            direction = Side.BUY
        elif net_size < 0:
            direction = Side.SELL
        else:
            direction = Side.HOLD
        
        result[instrument] = {
            "buy_size": buy_size,
            "sell_size": sell_size,
            "net_size": net_size,
            "direction": direction.value,
            "absolute_size": abs(net_size),
            "decision_count": len(instr_decisions),
            "has_conflict": buy_size > 0 and sell_size > 0
        }
    
    return result