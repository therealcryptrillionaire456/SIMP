# A2A Simulation Runbook

## Overview

This runbook provides operational guidance for using the A2A Safety and Simulation system. It covers how to construct trading scenarios, run safety evaluations, execute simulations, and interpret results for rollout decisions.

## System Architecture

### Core Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Agent         │    │   A2A Safety    │    │   Simulator     │
│   Decisions     │───▶│   Harness       │───▶│   (Stub)        │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Schema        │    │   Risk          │    │   Results       │
│   Validation    │    │   Evaluation    │    │   Interpretation│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Modules
- `a2a_schema.py` - Data structures and validation
- `a2a_safety.py` - Risk evaluation and blocking logic
- `a2a_simulator.py` - Stub execution simulation
- `a2a_aggregator.py` - Plan building from decisions

## Step-by-Step: simulate_execution() Guide

### Step 1: Understanding the Input - A2APlan Structure
Before simulation, understand what an A2APlan contains:

```python
from simp.financial.a2a_schema import A2APlan, PortfolioPosture, RiskPosture

# Key components of A2APlan:
plan = A2APlan(
    decisions=[...],  # List of AgentDecisionSummary objects
    portfolio_posture=PortfolioPosture(
        aggregate_exposure={"BTC-USD": 300.0, "ETH-USD": 200.0},
        risk_posture=RiskPosture.CONSERVATIVE,
        max_leverage=3.0,
        per_instrument_caps={"BTC-USD": 100000.0},
        constraints={"max_daily_loss": 0.1}
    ),
    execution_allowed=True,
    execution_reason="Passed initial checks",
    safety_checks_passed=["concentration", "conflict"],
    safety_checks_failed=[],
    plan_id="plan_001"
)
```

### Step 2: Safety Check Execution Flow
The `simulate_execution()` function follows this exact sequence:

```python
def simulate_execution(plan: A2APlan) -> Dict[str, Any]:
    # 1. Generate unique simulation ID
    simulation_id = f"sim_{uuid.uuid4().hex[:8]}"
    
    # 2. Check if plan is blocked by safety harness
    blocked = must_block(plan)  # ← FIRST SAFETY CHECK
    
    if blocked:
        # 3a. If blocked: return early with reason
        return {
            "simulated_trades": [],
            "resulting_posture": plan.portfolio_posture,
            "blocked": True,
            "blocked_reason": _get_blocked_reason(plan),
            "simulation_id": simulation_id,
            # ... other metadata
        }
    
    # 3b. If not blocked: simulate trades
    simulated_trades = _simulate_trades_from_plan(plan)
    
    # 4. Calculate resulting posture
    resulting_posture = _calculate_resulting_posture(plan, simulated_trades)
    
    # 5. Return simulation results
    return {
        "simulated_trades": simulated_trades,
        "resulting_posture": resulting_posture,
        "blocked": False,
        "blocked_reason": None,
        "simulation_id": simulation_id,
        # ... other metadata
    }
```

### Step 3: Detailed Breakdown of Each Phase

#### Phase A: Safety Check (`must_block()`)
**What happens**:
1. Checks `plan.execution_allowed` flag (immediate block if False)
2. Calculates total notional from aggregate exposures
3. Checks each instrument for concentration > 30%
4. Checks for conflicting exposure ratio > 20%
5. Checks for any decision with confidence < 0.1

**Decision Rules**:
- **Rule 1**: If any single check returns True, entire plan is blocked
- **Rule 2**: Checks happen in order (concentration → conflict → confidence)
- **Rule 3**: First violation found determines block reason

**Example Block Reasons**:
- `"Single instrument concentration: BTC-USD has 35.0% exposure"`
- `"High conflicting exposure: 25.0% of notional in conflicting directions"`
- `"Extremely low confidence decisions"`
- `"Execution not allowed in plan: Manual override"`

#### Phase B: Trade Simulation (`_simulate_trades_from_plan()`)
**What happens**:
1. Iterates through all decisions in the plan
2. Filters out HOLD decisions (no trade generated)
3. For each BUY/SELL decision:
   - Creates trade dictionary with metadata
   - Gets simulated price from `_get_simulated_price()`
   - Assigns unique trade ID
   - Preserves agent, confidence, timestamp

**Simulated Price Logic**:
```python
def _get_simulated_price(instrument: str) -> float:
    price_map = {
        "BTC-USD": 65000.0,
        "ETH-USD": 3500.0,
        "SOL-USD": 150.0,
        # ... other known instruments
    }
    
    if instrument in price_map:
        return price_map[instrument]
    
    # Deterministic hash-based price for unknown instruments
    import hashlib
    hash_val = int(hashlib.md5(instrument.encode()).hexdigest()[:8], 16)
    return 10.0 + (hash_val % 1000) / 10.0
```

**Trade Structure**:
```python
trade = {
    "instrument": "BTC-USD",
    "side": "buy",  # or "sell"
    "quantity": 300.0,
    "units": "USD",
    "agent": "quantumarb",
    "confidence": 0.8,
    "simulated_price": 65000.0,
    "timestamp": "2024-04-09T10:30:00Z",
    "trade_id": "sim_trade_001"
}
```

#### Phase C: Posture Update (`_calculate_resulting_posture()`)
**What happens**:
1. Starts with original portfolio exposures
2. Applies each simulated trade:
   - BUY: adds quantity to exposure
   - SELL: subtracts quantity from exposure
3. Calculates new risk posture based on updated concentrations
4. Returns updated PortfolioPosture object

**Risk Posture Recalculation**:
```python
# Simplified logic
total_abs_exposure = sum(abs(exposure) for exposure in exposures.values())

if total_abs_exposure == 0:
    new_risk_posture = RiskPosture.CONSERVATIVE
else:
    max_concentration = max(abs(exposure) / total_abs_exposure for exposure in exposures.values())
    
    if max_concentration > 0.5:
        new_risk_posture = RiskPosture.AGGRESSIVE
    elif max_concentration > 0.3:
        new_risk_posture = RiskPosture.NEUTRAL
    else:
        new_risk_posture = RiskPosture.CONSERVATIVE
```

### Step 4: Interpreting Simulation Results

#### Successful Simulation Output
```python
{
    "simulated_trades": [
        # List of trade dictionaries
    ],
    "resulting_posture": PortfolioPosture(...),
    "blocked": False,
    "blocked_reason": None,
    "simulation_id": "sim_a1b2c3d4",
    "original_plan_id": "plan_001",
    "timestamp": "2024-04-09T10:30:00Z",
    "simulation_notes": "Simulated 3 trades successfully"
}
```

#### Blocked Simulation Output
```python
{
    "simulated_trades": [],  # Empty list
    "resulting_posture": original_posture,  # Unchanged
    "blocked": True,
    "blocked_reason": "Single instrument concentration: BTC-USD has 35.0% exposure",
    "simulation_id": "sim_e5f6g7h8",
    "original_plan_id": "plan_002",
    "timestamp": "2024-04-09T10:31:00Z",
    "simulation_notes": "Plan blocked by safety checks - no trades simulated"
}
```

### Step 5: Decision Rules for Operators

#### Rule Set 1: Based on Simulation Outcome
```
IF blocked == True:
    DECISION: Do not execute
    ACTION: Review block reason, adjust plan if needed
    DOCUMENT: Log block reason for audit
    
ELSE IF blocked == False AND risk_posture == CONSERVATIVE:
    DECISION: Can consider for live execution
    ACTION: Verify simulated trades make sense
    DOCUMENT: Record simulation results
    
ELSE IF blocked == False AND risk_posture == NEUTRAL:
    DECISION: Proceed with caution
    ACTION: Additional review recommended
    DOCUMENT: Note elevated risk factors
    
ELSE IF blocked == False AND risk_posture == AGGRESSIVE:
    DECISION: Simulation-only, do not execute live
    ACTION: Investigate why risk is aggressive
    DOCUMENT: Flag for risk committee review
```

#### Rule Set 2: Based on Trade Characteristics
```
IF number_of_trades == 0:
    DECISION: No action needed
    REASON: Either blocked or all HOLD decisions
    
IF any trade has confidence < 0.3:
    DECISION: Review low-confidence trades
    ACTION: Consider excluding or reducing size
    DOCUMENT: Note which agents have low confidence
    
IF simulated_price differs significantly from market:
    DECISION: Note price discrepancy
    ACTION: Consider using real market data
    DOCUMENT: Simulation limitation acknowledged
```

#### Rule Set 3: Based on Resulting Posture
```
IF resulting_posture.risk_posture > original_posture.risk_posture:
    DECISION: Trades increased risk
    ACTION: Review if risk increase is justified
    DOCUMENT: Risk escalation noted
    
IF max_concentration > 0.4 in resulting posture:
    DECISION: High concentration after trades
    ACTION: Consider diversification
    DOCUMENT: Concentration risk highlighted
    
IF net_exposure_change > 50% of original:
    DECISION: Large position change
    ACTION: Verify gradual position building
    DOCUMENT: Significant exposure change
```

### Step 6: Common Operational Patterns

#### Pattern 1: Testing Safety Thresholds
```python
def test_concentration_threshold():
    """Test plans with different concentration levels."""
    test_levels = [0.29, 0.30, 0.31, 0.50, 0.75]
    
    for level in test_levels:
        plan = create_plan_with_concentration(level)
        result = simulate_execution(plan)
        
        print(f"Concentration {level:.1%}: Blocked={result['blocked']}")
        if result['blocked']:
            print(f"  Reason: {result['blocked_reason']}")
```

#### Pattern 2: Comparing Multiple Scenarios
```python
def compare_scenarios(scenario_plans):
    """Compare simulation results across scenarios."""
    comparisons = []
    
    for name, plan in scenario_plans.items():
        result = simulate_execution(plan)
        comparisons.append({
            "scenario": name,
            "blocked": result["blocked"],
            "trades": len(result["simulated_trades"]),
            "risk_posture": result["resulting_posture"].risk_posture.value
        })
    
    # Create comparison table
    df = pd.DataFrame(comparisons)
    print(df.to_string())
```

#### Pattern 3: Batch Simulation with Analysis
```python
from simp.financial.a2a_simulator import simulate_multiple_plans

def batch_simulation_analysis(plans):
    """Run batch simulation and analyze results."""
    batch_result = simulate_multiple_plans(plans)
    
    # Analyze summary statistics
    summary = batch_result["summary"]
    print(f"Total plans: {summary['total_plans']}")
    print(f"Blocked: {summary['blocked_plans']} ({summary['block_rate']:.1%})")
    print(f"Executed: {summary['executed_plans']}")
    print(f"Total trades: {summary['total_trades']}")
    
    # Drill into individual results
    for plan_id, result in batch_result["plan_results"].items():
        if result["blocked"]:
            print(f"{plan_id}: BLOCKED - {result['blocked_reason']}")
        else:
            print(f"{plan_id}: {len(result['simulated_trades'])} trades")
```

#### Pattern 4: Creating Simulation Reports
```python
from simp.financial.a2a_simulator import create_simulation_report

def generate_detailed_report(plan):
    """Generate and save detailed simulation report."""
    result = simulate_execution(plan)
    report = create_simulation_report(result)
    
    # Save to file
    report_file = f"simulation_report_{result['simulation_id']}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"Report saved to {report_file}")
    return report
```

### Step 7: Troubleshooting Guide

#### Issue 1: Plan Always Blocked
**Symptoms**: `blocked` is always True regardless of plan
**Check**:
1. Verify `plan.execution_allowed` is True
2. Check if any instrument has >30% concentration
3. Verify no decisions with confidence < 0.1
4. Check for conflicting exposure >20%

**Debug Script**:
```python
def debug_blocked_plan(plan):
    print(f"execution_allowed: {plan.execution_allowed}")
    
    # Check concentrations
    exposures = plan.portfolio_posture.aggregate_exposure
    total = sum(abs(e) for e in exposures.values())
    for inst, exp in exposures.items():
        pct = abs(exp) / total if total > 0 else 0
        print(f"{inst}: {exp} ({pct:.1%})")
        if pct > 0.3:
            print(f"  → Would block (>{0.3:.1%})")
    
    # Check confidence
    for decision in plan.decisions:
        if decision.confidence and decision.confidence < 0.1:
            print(f"Low confidence: {decision.agent_name} = {decision.confidence}")
```

#### Issue 2: No Trades Simulated
**Symptoms**: `simulated_trades` empty but plan not blocked
**Check**:
1. Verify decisions have BUY/SELL side (not HOLD)
2. Check quantity > 0
3. Verify instrument names are valid

**Debug Script**:
```python
def debug_no_trades(plan):
    for i, decision in enumerate(plan.decisions):
        print(f"Decision {i}: {decision.agent_name} {decision.instrument} "
              f"{decision.side.value} {decision.quantity} {decision.units}")
        
        if decision.side.value == "hold":
            print("  → HOLD (no trade)")
        elif decision.quantity <= 0:
            print("  → Quantity <= 0 (no trade)")
```

#### Issue 3: Unexpected Simulated Prices
**Symptoms**: Prices don't match expectations
**Check**:
1. Verify instrument is in price_map for known prices
2. Check hash-based price calculation for unknown instruments
3. Consider updating price_map with current market data

**Debug Script**:
```python
def debug_prices():
    from simp.financial.a2a_simulator import _get_simulated_price
    
    test_instruments = ["BTC-USD", "ETH-USD", "UNKNOWN-123", "MYTOKEN-USD"]
    
    for inst in test_instruments:
        price = _get_simulated_price(inst)
        print(f"{inst}: ${price:,.2f}")
```

### Step 8: Advanced Usage Patterns

#### Pattern A: Monte Carlo Simulation
```python
import random

def monte_carlo_simulation(base_plan, iterations=100):
    """Run Monte Carlo simulation with random variations."""
    results = []
    
    for i in range(iterations):
        # Create variation of the plan
        varied_plan = vary_plan_randomly(base_plan)
        
        # Run simulation
        result = simulate_execution(varied_plan)
        results.append(result)
    
    # Analyze distribution
    block_rate = sum(1 for r in results if r["blocked"]) / iterations
    avg_trades = sum(len(r["simulated_trades"]) for r in results if not r["blocked"]) / iterations
    
    return {
        "block_rate": block_rate,
        "avg_trades": avg_trades,
        "results": results
    }
```

#### Pattern B: Sensitivity Analysis
```python
def sensitivity_analysis(base_plan, parameter_ranges):
    """Analyze sensitivity to different parameters."""
    sensitivities = {}
    
    for param_name, values in parameter_ranges.items():
        param_results = []
        
        for value in values:
            # Modify plan with parameter value
            modified_plan = modify_plan_parameter(base_plan, param_name, value)
            
            # Run simulation
            result = simulate_execution(modified_plan)
            param_results.append({
                "value": value,
                "blocked": result["blocked"],
                "trades": len(result["simulated_trades"])
            })
        
        sensitivities[param_name] = param_results
    
    return sensitivities
```

#### Pattern C: Backtesting Framework
```python
def backtest_scenarios(historical_scenarios):
    """Backtest simulation against historical scenarios."""
    performance = []
    
    for scenario in historical_scenarios:
        # Get historical decisions
        historical_decisions = scenario["decisions"]
        
        # Build plan (as would have been done historically)
        plan = build_a2a_plan(historical_decisions)
        
        # Run simulation
        simulation_result = simulate_execution(plan)
        
        # Compare with historical outcome
        comparison = {
            "scenario_id": scenario["id"],
            "simulation_blocked": simulation_result["blocked"],
            "historical_outcome": scenario["outcome"],
            "match": (simulation_result["blocked"] == scenario["should_have_blocked"])
        }
        
        performance.append(comparison)
    
    # Calculate accuracy
    accuracy = sum(1 for p in performance if p["match"]) / len(performance)
    return {"accuracy": accuracy, "details": performance}
```

## Operational Workflows

### Workflow 1: Safety Evaluation Only
Use when you only need risk assessment without simulation.

```python
from simp.financial.a2a_schema import AgentDecisionSummary, Side
from simp.financial.a2a_aggregator import build_a2a_plan
from simp.financial.a2a_safety import evaluate_risk, must_block

# 1. Create agent decisions
decisions = [
    AgentDecisionSummary(
        agent_name="quantumarb",
        instrument="BTC-USD",
        side=Side.BUY,
        quantity=300.0,
        units="USD",
        confidence=0.8
    ),
    # ... more decisions
]

# 2. Build A2A plan
plan = build_a2a_plan(decisions)

# 3. Evaluate risk
risk_assessment = evaluate_risk(plan)
print(f"Risk Level: {risk_assessment['risk_level']}")
print(f"Reasons: {risk_assessment['reasons']}")

# 4. Check if blocked
if must_block(plan):
    print("Plan would be blocked by safety checks")
else:
    print("Plan passes safety checks")
```

### Workflow 2: Full Simulation Pipeline
Use when you need end-to-end simulation including trade execution.

```python
from simp.financial.a2a_simulator import simulate_execution

# 1-3. Same as Workflow 1 (create decisions, build plan)

# 4. Run simulation
simulation_result = simulate_execution(plan)

# 5. Interpret results
if simulation_result["blocked"]:
    print(f"Blocked: {simulation_result['blocked_reason']}")
    print("No trades simulated")
else:
    print(f"Simulated {len(simulation_result['simulated_trades'])} trades")
    print(f"Resulting posture: {simulation_result['resulting_posture'].risk_posture}")
```

### Workflow 3: Batch Scenario Testing
Use when testing multiple scenarios or parameter sweeps.

```python
import itertools
from typing import List, Dict
from simp.financial.a2a_simulator import simulate_multiple_plans

def run_scenario_batch(scenarios: List[Dict]) -> Dict:
    """Run multiple scenarios and collect results."""
    plans = []
    
    for scenario in scenarios:
        # Build plan from scenario decisions
        plan = build_a2a_plan(scenario["decisions"])
        plans.append(plan)
    
    # Run batch simulation
    batch_results = simulate_multiple_plans(plans)
    
    # Analyze results
    analysis = {
        "total_scenarios": len(scenarios),
        "blocked_count": batch_results["summary"]["blocked_plans"],
        "block_rate": batch_results["summary"]["block_rate"],
        "detailed_results": batch_results["plan_results"]
    }
    
    return analysis
```

## Decision Support Framework

### Decision Matrix for Simulation Results

| Result Pattern | Recommended Action | Escalation Required | Documentation |
|----------------|-------------------|---------------------|---------------|
| **Blocked + Concentration** | Adjust position sizes | No | Log concentration violation |
| **Blocked + Conflict** | Review agent consensus | Yes if persistent | Document conflict analysis |
| **Blocked + Low Confidence** | Investigate agent signals | Yes | Flag agent for review |
| **Not Blocked + Conservative** | Can proceed to live | No | Standard approval |
| **Not Blocked + Neutral** | Additional review | Optional | Note risk factors |
| **Not Blocked + Aggressive** | Simulation only | Yes | Risk committee review |
| **Zero Trades** | Verify HOLD decisions | No | Document no-action |

### Escalation Pathways

```
Simulation Result → Decision Point → Action
────────────────────────────────────────────
Blocked (any reason) → Safety Violation → Do not execute
Not Blocked + Conservative → Normal Approval → Can execute
Not Blocked + Neutral → Caution Required → Review then decide
Not Blocked + Aggressive → High Risk → Simulation only
Unexpected Result → Anomaly Detection → Investigate
```

## Maintenance and Updates

### Updating Simulated Prices
To update price mappings in `_get_simulated_price()`:

1. Edit `a2a_simulator.py`
2. Update `price_map` dictionary
3. Add new instruments as needed
4. Run tests to verify changes

### Adding New Safety Checks
To extend safety logic:

1. Add check to `must_block()` in `a2a_safety.py`
2. Add corresponding test scenarios
3. Update documentation
4. Verify integration with simulator

### Performance Monitoring
Monitor these metrics:
- Simulation execution time
- Block rate by reason
- Average trades per simulation
- Memory usage for batch simulations

## References
- `simp/financial/a2a_safety.py` - Safety implementation
- `simp/financial/a2a_simulator.py` - Simulator implementation
- `simp/docs/a2a_risk_taxonomy.md` - Risk definitions
- `simp/docs/a2a_scenario_catalog.md` - Test scenarios
- `simp/docs/a2a_thresholds_and_rationale.md` - Threshold details