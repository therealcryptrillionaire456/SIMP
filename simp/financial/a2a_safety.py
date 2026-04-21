"""
A2A Safety Harness.

This module implements safety checks for A2A financial operations plans.
All functions are pure (no side effects) and only perform risk evaluation.

The safety harness works with the A2APlan schema to:
1. Evaluate risk level based on exposures and conflicts
2. Determine if a plan must be blocked due to safety violations
3. Provide clear reasons for safety decisions
"""

from typing import Dict, List, Tuple, Optional
from .a2a_schema import A2APlan, AgentDecisionSummary, Side, RiskPosture
from .a2a_aggregator import compute_aggregate_exposure, calculate_net_direction


# Safety configuration constants
MAX_SINGLE_INSTRUMENT_EXPOSURE = 0.3  # 30% of total notional
MAX_CONFLICTING_SIZE_RATIO = 0.2  # 20% of total notional in conflicting directions
HIGH_RISK_EXPOSURE_THRESHOLD = 0.5  # 50% exposure triggers high risk
MEDIUM_RISK_EXPOSURE_THRESHOLD = 0.3  # 30% exposure triggers medium risk
MIN_CONFIDENCE_THRESHOLD = 0.3  # Minimum confidence for decisions


def evaluate_risk(plan: A2APlan) -> Dict[str, any]:
    """
    Evaluate risk level of an A2A plan.
    
    Args:
        plan: A2APlan to evaluate
        
    Returns:
        Dict with:
            - risk_level: "conservative" | "neutral" | "aggressive"
            - reasons: list of risk reasons
            - max_single_instrument_exposure: float
            - number_of_conflicting_decisions: int
            - total_notional: float
    """
    reasons = []
    
    # Calculate exposures from the plan's decisions
    aggregate_exposure = plan.portfolio_posture.aggregate_exposure
    
    # Calculate total notional (sum of absolute exposures)
    total_notional = sum(abs(exposure) for exposure in aggregate_exposure.values())
    
    # Calculate max single instrument exposure
    max_exposure = 0.0
    max_instrument = None
    
    for instrument, net_exposure in aggregate_exposure.items():
        exposure_pct = abs(net_exposure) / total_notional if total_notional > 0 else 0
        if exposure_pct > max_exposure:
            max_exposure = exposure_pct
            max_instrument = instrument
    
    # Check for single instrument concentration
    if max_exposure > MAX_SINGLE_INSTRUMENT_EXPOSURE:
        reasons.append(
            f"Single instrument concentration: {max_instrument} has "
            f"{max_exposure:.1%} exposure (limit: {MAX_SINGLE_INSTRUMENT_EXPOSURE:.1%})"
        )
    
    # Check for conflicting decisions
    net_direction = calculate_net_direction(plan.decisions)
    conflict_count = 0
    conflicting_instruments = []
    
    for instrument, analysis in net_direction.items():
        if analysis["has_conflict"]:
            conflict_count += 1
            conflicting_instruments.append(instrument)
    
    if conflict_count > 0:
        # Calculate total size in conflicting instruments
        conflict_size = 0.0
        for instrument in conflicting_instruments:
            conflict_size += abs(aggregate_exposure.get(instrument, 0))
        
        conflict_ratio = conflict_size / total_notional if total_notional > 0 else 0
        if conflict_ratio > MAX_CONFLICTING_SIZE_RATIO:
            reasons.append(
                f"High conflicting exposure: {conflict_ratio:.1%} of notional in "
                f"conflicting directions (limit: {MAX_CONFLICTING_SIZE_RATIO:.1%})"
            )
    
    # Determine risk level based on exposures and plan's posture
    risk_level = plan.portfolio_posture.risk_posture
    
    # Adjust risk level based on safety analysis
    if max_exposure > HIGH_RISK_EXPOSURE_THRESHOLD:
        # Override to aggressive if exposure is very high
        risk_level = RiskPosture.AGGRESSIVE
        if not any("Single instrument concentration" in r for r in reasons):
            reasons.append(
                f"High exposure concentration: {max_exposure:.1%} in {max_instrument}"
            )
    elif max_exposure > MEDIUM_RISK_EXPOSURE_THRESHOLD:
        # Consider elevating to aggressive if already neutral
        if risk_level == RiskPosture.NEUTRAL:
            risk_level = RiskPosture.AGGRESSIVE
        elif risk_level == RiskPosture.CONSERVATIVE:
            risk_level = RiskPosture.NEUTRAL
            
        if not any("Single instrument concentration" in r for r in reasons):
            reasons.append(
                f"Medium exposure concentration: {max_exposure:.1%} in {max_instrument}"
            )
    
    # Add conflict count to reasons if significant
    if conflict_count > 0 and conflict_count <= 2:
        reasons.append(f"{conflict_count} instrument(s) with conflicting directions")
    elif conflict_count > 2:
        reasons.append(f"High conflict count: {conflict_count} instruments with conflicting directions")
        # Elevate risk level if not already aggressive
        if risk_level == RiskPosture.CONSERVATIVE:
            risk_level = RiskPosture.NEUTRAL
        elif risk_level == RiskPosture.NEUTRAL:
            risk_level = RiskPosture.AGGRESSIVE
    
    # Check for low confidence decisions
    low_conf_decisions = [
        d for d in plan.decisions 
        if d.confidence is not None and d.confidence < MIN_CONFIDENCE_THRESHOLD
    ]
    if low_conf_decisions:
        agents = ", ".join(d.agent_name for d in low_conf_decisions[:3])  # Limit to 3
        if len(low_conf_decisions) > 3:
            agents += f" and {len(low_conf_decisions) - 3} more"
        reasons.append(f"Low confidence decisions from: {agents}")
    
    return {
        "risk_level": risk_level.value,
        "reasons": reasons,
        "max_single_instrument_exposure": max_exposure,
        "number_of_conflicting_decisions": conflict_count,
        "total_notional": total_notional,
        "conflicting_instruments": conflicting_instruments,
    }


def must_block(plan: A2APlan) -> bool:
    """
    Determine if an A2A plan must be blocked due to safety violations.
    
    Hard safety constraints:
    1. Any single instrument exposure > MAX_SINGLE_INSTRUMENT_EXPOSURE
    2. Conflicting exposure ratio > MAX_CONFLICTING_SIZE_RATIO
    3. Execution already not allowed in the plan
    
    Args:
        plan: A2APlan to evaluate
        
    Returns:
        True if plan must be blocked, False otherwise
    """
    # If execution is already not allowed, treat as blocked
    if not plan.execution_allowed:
        return True
    
    # Calculate exposures
    aggregate_exposure = plan.portfolio_posture.aggregate_exposure
    total_notional = sum(abs(exposure) for exposure in aggregate_exposure.values())
    
    if total_notional == 0:
        return False  # Empty plan is safe
    
    # Check single instrument concentration
    for instrument, net_exposure in aggregate_exposure.items():
        exposure_pct = abs(net_exposure) / total_notional
        if exposure_pct > MAX_SINGLE_INSTRUMENT_EXPOSURE:
            return True
    
    # Check conflicting exposure
    net_direction = calculate_net_direction(plan.decisions)
    conflicting_instruments = [
        instrument for instrument, analysis in net_direction.items()
        if analysis["has_conflict"]
    ]
    
    if conflicting_instruments:
        conflict_size = 0.0
        for instrument in conflicting_instruments:
            conflict_size += abs(aggregate_exposure.get(instrument, 0))
        
        conflict_ratio = conflict_size / total_notional
        if conflict_ratio > MAX_CONFLICTING_SIZE_RATIO:
            return True
    
    # Check for extremely low confidence
    extremely_low_conf = any(
        d.confidence is not None and d.confidence < 0.1
        for d in plan.decisions
    )
    if extremely_low_conf:
        return True
    
    return False


def get_safety_limits() -> Dict[str, float]:
    """
    Get current safety limit configuration.
    
    Returns:
        Dictionary of safety limits
    """
    return {
        "max_single_instrument_exposure": MAX_SINGLE_INSTRUMENT_EXPOSURE,
        "max_conflicting_size_ratio": MAX_CONFLICTING_SIZE_RATIO,
        "high_risk_exposure_threshold": HIGH_RISK_EXPOSURE_THRESHOLD,
        "medium_risk_exposure_threshold": MEDIUM_RISK_EXPOSURE_THRESHOLD,
        "min_confidence_threshold": MIN_CONFIDENCE_THRESHOLD,
    }


def check_plan_safety(plan: A2APlan) -> Dict[str, any]:
    """
    Comprehensive safety check for an A2A plan.
    
    Combines risk evaluation and blocking decision with detailed analysis.
    
    Args:
        plan: A2APlan to evaluate
        
    Returns:
        Dict with complete safety analysis
    """
    risk_assessment = evaluate_risk(plan)
    blocked = must_block(plan)
    
    # Determine overall safety status
    if blocked:
        safety_status = "BLOCKED"
    elif plan.portfolio_posture.risk_posture == RiskPosture.AGGRESSIVE:
        safety_status = "HIGH_RISK"
    elif plan.portfolio_posture.risk_posture == RiskPosture.NEUTRAL:
        safety_status = "MEDIUM_RISK"
    else:
        safety_status = "LOW_RISK"
    
    # Check if plan passes basic safety checks
    passes_basic_safety = (
        not blocked and
        plan.execution_allowed and
        len(plan.safety_checks_failed) == 0
    )
    
    return {
        "safety_status": safety_status,
        "blocked": blocked,
        "passes_basic_safety": passes_basic_safety,
        "risk_assessment": risk_assessment,
        "plan_execution_allowed": plan.execution_allowed,
        "plan_execution_reason": plan.execution_reason,
        "plan_safety_checks_passed": plan.safety_checks_passed,
        "plan_safety_checks_failed": plan.safety_checks_failed,
        "safety_limits": get_safety_limits(),
    }