"""
A2A Simulator - Stub Executor.

This module implements a stub executor that simulates execution of A2A plans
without talking to real systems. It's a pure, side-effect-free simulator
for testing and inspection.

Core function: simulate_execution() - takes an A2A plan and returns
simulated execution results including what trades would be taken and
the resulting portfolio posture.
"""

from typing import Dict, List, Any, Optional
from .a2a_schema import A2APlan, PortfolioPosture, Side, RiskPosture, ExecutionMode
from .a2a_safety import must_block, evaluate_risk
from .a2a_aggregator import compute_aggregate_exposure, calculate_net_direction


def simulate_execution(plan: A2APlan) -> Dict[str, Any]:
    """
    Simulate execution of an A2A plan.
    
    This is a stub executor that never talks to real systems.
    It simulates what trades would be taken based on the plan's decisions,
    applies safety checks, and returns simulated results.
    
    Args:
        plan: A2APlan to simulate execution for
        
    Returns:
        Dict with:
            - simulated_trades: list of simulated trade actions (empty if blocked)
            - resulting_posture: post-trade PortfolioPosture
            - blocked: bool (True if plan was blocked by safety checks)
            - blocked_reason: str or None
            - simulation_id: unique identifier for this simulation
            - original_plan: reference to the input plan
    """
    import uuid
    import datetime
    
    simulation_id = f"sim_{uuid.uuid4().hex[:8]}"
    
    # Check if plan is blocked by safety harness
    blocked = must_block(plan)
    
    if blocked:
        # Plan is blocked - no trades executed
        return {
            "simulated_trades": [],
            "resulting_posture": plan.portfolio_posture,  # No change
            "blocked": True,
            "blocked_reason": _get_blocked_reason(plan),
            "simulation_id": simulation_id,
            "original_plan_id": getattr(plan, 'plan_id', 'unknown'),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "simulation_notes": "Plan blocked by safety checks - no trades simulated"
        }
    
    # Plan is not blocked - simulate trades
    simulated_trades = _simulate_trades_from_plan(plan)
    
    # Calculate resulting posture after simulated trades
    resulting_posture = _calculate_resulting_posture(plan, simulated_trades)
    
    return {
        "simulated_trades": simulated_trades,
        "resulting_posture": resulting_posture,
        "blocked": False,
        "blocked_reason": None,
        "simulation_id": simulation_id,
        "original_plan_id": getattr(plan, 'plan_id', 'unknown'),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "simulation_notes": f"Simulated {len(simulated_trades)} trades successfully"
    }


def _get_blocked_reason(plan: A2APlan) -> str:
    """
    Determine why a plan was blocked.
    
    Args:
        plan: A2APlan that was blocked
        
    Returns:
        String explaining why the plan was blocked
    """
    # Check if execution was already not allowed in the plan
    if not plan.execution_allowed:
        return f"Execution not allowed in plan: {plan.execution_reason}"
    
    # Evaluate risk to get detailed reasons
    risk_assessment = evaluate_risk(plan)
    
    if risk_assessment.get("reasons"):
        reasons = "; ".join(risk_assessment["reasons"])
        return f"Safety violations: {reasons}"
    
    # Check for specific safety violations
    if risk_assessment.get("max_single_instrument_exposure", 0) > 0.3:
        return f"Single instrument concentration: {risk_assessment['max_single_instrument_exposure']:.1%}"
    
    if risk_assessment.get("number_of_conflicting_decisions", 0) > 0:
        return f"Conflicting decisions: {risk_assessment['number_of_conflicting_decisions']} instruments"
    
    return "Blocked by safety checks (reason unspecified)"


def _simulate_trades_from_plan(plan: A2APlan) -> List[Dict[str, Any]]:
    """
    Simulate trades based on plan decisions.
    
    Converts agent decisions into simulated trade actions.
    Only includes BUY and SELL decisions (HOLD is ignored).
    
    Args:
        plan: A2APlan with decisions to simulate
        
    Returns:
        List of simulated trade dictionaries
    """
    simulated_trades = []
    
    for decision in plan.decisions:
        # Only simulate BUY and SELL decisions
        if decision.side == Side.HOLD:
            continue
        
        # Create a simulated trade
        trade = {
            "instrument": decision.instrument,
            "side": decision.side.value,
            "quantity": decision.quantity,
            "units": decision.units,
            "agent": decision.agent_name,
            "confidence": decision.confidence,
            "simulated_price": _get_simulated_price(decision.instrument),
            "timestamp": decision.timestamp,
            "trade_id": f"sim_trade_{len(simulated_trades) + 1:03d}"
        }
        
        simulated_trades.append(trade)
    
    return simulated_trades


def _get_simulated_price(instrument: str) -> float:
    """
    Get a simulated price for an instrument.
    
    This is a stub function that returns deterministic "prices"
    based on the instrument name. In a real system, this would
    query market data.
    
    Args:
        instrument: Instrument identifier
        
    Returns:
        Simulated price
    """
    # Simple deterministic price mapping for simulation
    price_map = {
        "BTC-USD": 65000.0,
        "ETH-USD": 3500.0,
        "SOL-USD": 150.0,
        "ADA-USD": 0.5,
        "XRP-USD": 0.6,
        "DOGE-USD": 0.15,
    }
    
    # Default price for unknown instruments
    default_price = 100.0
    
    # Try to get price from map, fall back to hash-based deterministic price
    if instrument in price_map:
        return price_map[instrument]
    
    # Generate deterministic price based on instrument name hash
    import hashlib
    hash_val = int(hashlib.md5(instrument.encode()).hexdigest()[:8], 16)
    return 10.0 + (hash_val % 1000) / 10.0


def _calculate_resulting_posture(
    plan: A2APlan,
    simulated_trades: List[Dict[str, Any]]
) -> PortfolioPosture:
    """
    Calculate portfolio posture after simulated trades.
    
    Args:
        plan: Original A2APlan
        simulated_trades: List of simulated trades
        
    Returns:
        Updated PortfolioPosture reflecting simulated trades
    """
    if not simulated_trades:
        # No trades simulated - return original posture
        return plan.portfolio_posture
    
    # Calculate new exposures based on simulated trades
    # For simplicity, we'll adjust the existing exposures
    # In a real system, this would track positions over time
    
    # Start with original exposures
    original_exposure = plan.portfolio_posture.aggregate_exposure.copy()
    
    # Apply simulated trades to exposures
    for trade in simulated_trades:
        instrument = trade["instrument"]
        quantity = trade["quantity"]
        
        # Adjust exposure based on trade side
        if trade["side"] == "buy":
            adjustment = quantity
        else:  # sell
            adjustment = -quantity
        
        # Apply adjustment
        if instrument not in original_exposure:
            original_exposure[instrument] = 0.0
        original_exposure[instrument] += adjustment
    
    # Calculate new risk posture
    # For simulation, we'll use a simplified version of the aggregator's logic
    total_abs_exposure = sum(abs(exposure) for exposure in original_exposure.values())
    
    if total_abs_exposure == 0:
        new_risk_posture = RiskPosture.CONSERVATIVE
    else:
        # Check concentration
        max_concentration = 0.0
        for exposure in original_exposure.values():
            concentration = abs(exposure) / total_abs_exposure
            if concentration > max_concentration:
                max_concentration = concentration
        
        # Determine risk posture based on concentration
        if max_concentration > 0.5:
            new_risk_posture = RiskPosture.AGGRESSIVE
        elif max_concentration > 0.3:
            new_risk_posture = RiskPosture.NEUTRAL
        else:
            new_risk_posture = RiskPosture.CONSERVATIVE
    
    # Create updated posture
    updated_posture = PortfolioPosture(
        aggregate_exposure=original_exposure,
        risk_posture=new_risk_posture,
        max_leverage=plan.portfolio_posture.max_leverage,
        per_instrument_caps=plan.portfolio_posture.per_instrument_caps,
        constraints=plan.portfolio_posture.constraints,
    )
    
    return updated_posture


def simulate_multiple_plans(plans: List[A2APlan]) -> Dict[str, Any]:
    """
    Simulate execution of multiple A2A plans.
    
    Useful for batch simulation or comparing multiple scenarios.
    
    Args:
        plans: List of A2APlan objects to simulate
        
    Returns:
        Dict with simulation results for each plan
    """
    results = {}
    
    for i, plan in enumerate(plans):
        plan_id = getattr(plan, 'plan_id', f'plan_{i:03d}')
        result = simulate_execution(plan)
        results[plan_id] = result
    
    # Calculate summary statistics
    total_plans = len(plans)
    blocked_plans = sum(1 for r in results.values() if r["blocked"])
    executed_plans = total_plans - blocked_plans
    total_trades = sum(len(r["simulated_trades"]) for r in results.values() if not r["blocked"])
    
    return {
        "plan_results": results,
        "summary": {
            "total_plans": total_plans,
            "blocked_plans": blocked_plans,
            "executed_plans": executed_plans,
            "total_trades": total_trades,
            "block_rate": blocked_plans / total_plans if total_plans > 0 else 0.0,
        }
    }


def create_simulation_report(simulation_result: Dict[str, Any]) -> str:
    """
    Create a human-readable report from simulation results.
    
    Args:
        simulation_result: Result from simulate_execution()
        
    Returns:
        Human-readable report string
    """
    report_lines = []
    
    # Header
    report_lines.append("=" * 60)
    report_lines.append(f"A2A SIMULATION REPORT - {simulation_result.get('simulation_id', 'UNKNOWN')}")
    report_lines.append("=" * 60)
    
    # Basic info
    report_lines.append(f"Original Plan ID: {simulation_result.get('original_plan_id', 'unknown')}")
    report_lines.append(f"Timestamp: {simulation_result.get('timestamp', 'unknown')}")
    report_lines.append(f"Blocked: {simulation_result['blocked']}")
    
    if simulation_result["blocked"]:
        report_lines.append(f"Blocked Reason: {simulation_result['blocked_reason']}")
        report_lines.append("No trades simulated (plan blocked by safety checks)")
    else:
        report_lines.append(f"Simulated Trades: {len(simulation_result['simulated_trades'])}")
        
        # Trade details
        if simulation_result["simulated_trades"]:
            report_lines.append("\n--- Simulated Trades ---")
            for i, trade in enumerate(simulation_result["simulated_trades"], 1):
                report_lines.append(
                    f"{i}. {trade['instrument']} {trade['side']} {trade['quantity']} {trade['units']} "
                    f"@ ${trade['simulated_price']:.2f} (by {trade['agent']})"
                )
        
        # Resulting posture
        posture = simulation_result["resulting_posture"]
        report_lines.append("\n--- Resulting Portfolio Posture ---")
        report_lines.append(f"Risk Posture: {posture.risk_posture.value}")
        
        if posture.aggregate_exposure:
            report_lines.append("Exposures:")
            for instrument, exposure in posture.aggregate_exposure.items():
                report_lines.append(f"  {instrument}: {exposure:,.2f} {posture.constraints.get('base_currency', 'USD') if posture.constraints else 'USD'}")
    
    # Notes
    if simulation_result.get("simulation_notes"):
        report_lines.append(f"\nNotes: {simulation_result['simulation_notes']}")
    
    report_lines.append("=" * 60)
    
    return "\n".join(report_lines)