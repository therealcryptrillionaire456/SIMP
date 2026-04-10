# A2A Safety Risk Taxonomy

## Overview

This document defines the risk taxonomy used by the SIMP A2A Safety Harness. The taxonomy categorizes financial operations plans into three risk levels (Low, Medium, High) based on quantitative thresholds and qualitative factors.

## Risk Categories

### Low Risk (Conservative)
**Definition**: Plans that pose minimal risk to the system and can be executed with high confidence.

**Characteristics**:
- Single instrument concentration ≤ 30%
- Conflicting exposure ratio ≤ 20%
- All agent decisions have confidence ≥ 0.3
- No extreme value anomalies
- Execution mode: `SIMULATED_ONLY` or `LIVE_CANDIDATE` with conservative posture

**Concrete Numeric Examples**:
1. **Well-Diversified Portfolio**: 
   - BTC-USD: 25% ($250 of $1000), ETH-USD: 25%, SOL-USD: 25%, ADA-USD: 25%
   - All decisions confidence ≥ 0.7
   - No conflicting directions
   - **Result**: Conservative risk, not blocked

2. **Moderate Concentration with High Confidence**:
   - BTC-USD: 29% ($290 of $1000), ETH-USD: 35%, SOL-USD: 36%
   - All decisions confidence ≥ 0.8
   - **Result**: Conservative risk, not blocked (max concentration 36% > 30% but not in single instrument)

3. **Small Positions with Mixed Confidence**:
   - BTC-USD: 15% (confidence 0.9), ETH-USD: 10% (confidence 0.4), SOL-USD: 5% (confidence 0.35)
   - **Result**: Conservative risk, not blocked (all confidence ≥ 0.3)

**Safety Response**: 
- `must_block()` returns `False`
- `evaluate_risk()` returns `risk_level: "conservative"`
- Execution proceeds to simulation
- Can be considered for live execution with appropriate safeguards

### Medium Risk (Neutral)
**Definition**: Plans with elevated but acceptable risk levels that require monitoring.

**Characteristics**:
- Single instrument concentration: 30% < x ≤ 50%
- Conflicting exposure ratio: 20% < x ≤ 35%
- Some low-confidence decisions (confidence < 0.3 but ≥ 0.1)
- Moderate value anomalies detected
- Execution mode: Typically `SIMULATED_ONLY`

**Concrete Numeric Examples**:
1. **Borderline Concentration**:
   - BTC-USD: 32% ($320 of $1000), ETH-USD: 28%, SOL-USD: 40%
   - Max single instrument: 40% (SOL-USD)
   - All decisions confidence ≥ 0.6
   - **Result**: Neutral risk, not blocked (40% > 30% but ≤ 50%)

2. **Moderate Conflict with Good Confidence**:
   - BTC-USD: BUY 40% (confidence 0.8), BTC-USD: SELL 15% (confidence 0.7)
   - Conflicting exposure: 15% of total (15/100 = 15%)
   - **Result**: Neutral risk, not blocked (conflict 15% ≤ 20%)

3. **Low Confidence with Good Diversification**:
   - BTC-USD: 20% (confidence 0.25), ETH-USD: 20% (confidence 0.28), SOL-USD: 20% (confidence 0.9)
   - 2 decisions with confidence < 0.3
   - **Result**: Neutral risk, not blocked (confidence ≥ 0.1)

**Safety Response**:
- `must_block()` returns `False` (unless other hard constraints violated)
- `evaluate_risk()` returns `risk_level: "neutral"`
- Execution proceeds with caution flags
- May trigger additional logging or operator review
- Should remain in simulation-only mode

### High Risk (Aggressive)
**Definition**: Plans with significant risk that may require blocking or special handling.

**Characteristics**:
- Single instrument concentration > 50%
- Conflicting exposure ratio > 35%
- Extremely low confidence decisions (confidence < 0.1)
- Severe value anomalies
- Execution mode: Should remain `SIMULATED_ONLY`

**Concrete Numeric Examples**:
1. **Extreme Concentration**:
   - BTC-USD: 55% ($550 of $1000), ETH-USD: 45%
   - Max single instrument: 55%
   - All decisions confidence ≥ 0.8
   - **Result**: Aggressive risk, **BLOCKED** (55% > 30% blocking threshold)

2. **High Conflict with Large Positions**:
   - BTC-USD: BUY 40% (confidence 0.7), BTC-USD: SELL 30% (confidence 0.6)
   - Conflicting exposure: 30% of total (30/100 = 30%)
   - Net exposure: 10% BUY
   - **Result**: Aggressive risk, **BLOCKED** (conflict 30% > 20% blocking threshold)

3. **Extremely Low Confidence**:
   - BTC-USD: 10% (confidence 0.05), ETH-USD: 10% (confidence 0.08)
   - Small positions but extremely low confidence
   - **Result**: Aggressive risk, **BLOCKED** (confidence < 0.1)

4. **Combination of Issues**:
   - BTC-USD: 40% (confidence 0.25), conflicting ETH-USD positions: 25%
   - Medium concentration + high conflict + low confidence
   - **Result**: Aggressive risk, may be blocked depending on exact thresholds

**Safety Response**:
- `must_block()` may return `True` if hard constraints violated
- `evaluate_risk()` returns `risk_level: "aggressive"`
- Execution may be blocked or require manual override
- Always triggers detailed logging and audit trail
- Requires operator review before any consideration for live execution

## Threshold Mapping

### Hard Constraints (Always Block)
These conditions always cause `must_block()` to return `True`:

1. **Concentration Limit**: Single instrument exposure > 30% of total notional
   - Rationale: Prevents over-concentration in single assets
   - Threshold: `MAX_SINGLE_INSTRUMENT_EXPOSURE = 0.3`
   - Example: BTC-USD: 31% of $1000 = $310 → **BLOCKED**

2. **Conflict Limit**: Conflicting exposure ratio > 20% of total notional
   - Rationale: Limits contradictory positions across agents
   - Threshold: `MAX_CONFLICTING_SIZE_RATIO = 0.2`
   - Example: BTC-USD BUY $400, BTC-USD SELL $250 → conflict $250/$650 = 38% → **BLOCKED**

3. **Extreme Low Confidence**: Any decision with confidence < 0.1
   - Rationale: Filters out extremely uncertain recommendations
   - Threshold: Implicit in `must_block()` logic
   - Example: Any decision with confidence 0.09 → **BLOCKED**

### Soft Constraints (Risk Elevation)
These conditions elevate risk level but don't necessarily block execution:

1. **Medium Concentration**: 30% < exposure ≤ 50%
   - Elevates risk from Conservative → Neutral or Neutral → Aggressive
   - Threshold: `MEDIUM_RISK_EXPOSURE_THRESHOLD = 0.3`
   - Example: BTC-USD: 35% → elevates risk level

2. **High Concentration**: Exposure > 50%
   - Elevates risk to Aggressive
   - Threshold: `HIGH_RISK_EXPOSURE_THRESHOLD = 0.5`
   - Example: BTC-USD: 55% → sets risk to Aggressive (also blocked by hard constraint)

3. **Low Confidence**: Confidence < 0.3 but ≥ 0.1
   - Adds to risk reasons but doesn't block
   - Threshold: `MIN_CONFIDENCE_THRESHOLD = 0.3`
   - Example: Confidence 0.25 → adds warning to risk reasons

## must_block() Behavior Documentation

### Decision Flowchart
```
                    START
                      │
                      ▼
           ┌─────────────────────┐
           │ execution_allowed?  │
           └──────────┬──────────┘
                      │
           No ────────┴─────────── Yes
           │                        │
           ▼                        ▼
      RETURN True          total_notional == 0?
           │                        │
           │              Yes ──────┴───────── No
           │              │                    │
           │              ▼                    ▼
           │        RETURN False      Check each instrument:
           │                          │
           │                          ▼
           │                  exposure_pct > 0.3?
           │                          │
           │              Yes ────────┴───────── No
           │              │                    │
           │              ▼                    ▼
           │          RETURN True      Check conflicts:
           │                          │
           │                          ▼
           │                  conflict_ratio > 0.2?
           │                          │
           │              Yes ────────┴───────── No
           │              │                    │
           │              ▼                    ▼
           │          RETURN True      Check confidence:
           │                          │
           │                          ▼
           │              any confidence < 0.1?
           │                          │
           │              Yes ────────┴───────── No
           │              │                    │
           │              ▼                    ▼
           │          RETURN True        RETURN False
           │
           └───────────────────────────────────┘
```

### Detailed Behavior by Constraint

#### 1. Single Instrument Concentration Check
```python
# Logic in must_block()
for instrument, net_exposure in aggregate_exposure.items():
    exposure_pct = abs(net_exposure) / total_notional
    if exposure_pct > MAX_SINGLE_INSTRUMENT_EXPOSURE:  # 0.3
        return True  # Immediate block
```

**Behavior**:
- Checks **absolute value** of exposure (both BUY and SELL count toward concentration)
- Uses **total notional** (sum of absolute exposures) as denominator
- **Immediate return**: First violation causes immediate block
- **Example**: If BTC-USD has 35% exposure, function returns True immediately without checking other instruments

#### 2. Conflicting Exposure Check
```python
# Calculate conflicting instruments
conflicting_instruments = [
    instrument for instrument, analysis in net_direction.items()
    if analysis["has_conflict"]
]

if conflicting_instruments:
    conflict_size = 0.0
    for instrument in conflicting_instruments:
        conflict_size += abs(aggregate_exposure.get(instrument, 0))
    
    conflict_ratio = conflict_size / total_notional
    if conflict_ratio > MAX_CONFLICTING_SIZE_RATIO:  # 0.2
        return True  # Block execution
```

**Behavior**:
- Only checks instruments with **conflicting directions** (BUY vs SELL)
- Sums **absolute exposures** of conflicting instruments
- Compares to **total notional**
- **Example**: BTC-USD BUY $400, BTC-USD SELL $250 → conflict size $250, total notional $650 → ratio 38% → BLOCKED

#### 3. Extreme Low Confidence Check
```python
# Check for extremely low confidence
extremely_low_conf = any(
    d.confidence is not None and d.confidence < 0.1
    for d in plan.decisions
)
if extremely_low_conf:
    return True
```

**Behavior**:
- Checks **any decision** with confidence < 0.1
- **Immediate block** if any decision below threshold
- **Example**: 10 decisions with confidence 0.8, 1 decision with confidence 0.09 → BLOCKED

#### 4. Execution Already Not Allowed
```python
# If execution is already not allowed, treat as blocked
if not plan.execution_allowed:
    return True
```

**Behavior**:
- Respects plan's own `execution_allowed` flag
- **Early return**: Checks this before any other safety logic
- **Example**: If plan was marked as simulation-only by aggregator, blocked immediately

### Return Value Semantics
- `True`: Plan **must be blocked**, no execution allowed
- `False`: Plan **may proceed** to simulation (subject to other checks)

## Risk Level Determination Algorithm

```python
def determine_risk_level(plan: A2APlan) -> RiskPosture:
    # Start with plan's inherent posture
    risk_level = plan.portfolio_posture.risk_posture
    
    # Apply concentration adjustments
    max_exposure = calculate_max_exposure(plan)
    
    if max_exposure > HIGH_RISK_EXPOSURE_THRESHOLD:
        risk_level = RiskPosture.AGGRESSIVE
    elif max_exposure > MEDIUM_RISK_EXPOSURE_THRESHOLD:
        if risk_level == RiskPosture.CONSERVATIVE:
            risk_level = RiskPosture.NEUTRAL
        elif risk_level == RiskPosture.NEUTRAL:
            risk_level = RiskPosture.AGGRESSIVE
    
    # Apply conflict adjustments
    if has_significant_conflicts(plan):
        if risk_level == RiskPosture.CONSERVATIVE:
            risk_level = RiskPosture.NEUTRAL
        elif risk_level == RiskPosture.NEUTRAL:
            risk_level = RiskPosture.AGGRESSIVE
    
    return risk_level
```

## Integration with Execution Pipeline

### Simulation Pipeline
```
Agent Decisions → A2APlan → Risk Evaluation → Block Decision → Simulation
```

1. **Risk Evaluation**: `evaluate_risk()` categorizes plan into Low/Medium/High
2. **Block Decision**: `must_block()` applies hard constraints
3. **Simulation**: `simulate_execution()` respects block decisions

### Risk-Based Routing
- **Low Risk**: Can proceed to live candidate evaluation
- **Medium Risk**: Requires additional validation or operator review
- **High Risk**: Should remain in simulation-only mode

## Evolution and Tuning

### Adjusting Thresholds
Thresholds are defined as constants in `a2a_safety.py`:
- `MAX_SINGLE_INSTRUMENT_EXPOSURE`
- `MAX_CONFLICTING_SIZE_RATIO` 
- `HIGH_RISK_EXPOSURE_THRESHOLD`
- `MEDIUM_RISK_EXPOSURE_THRESHOLD`
- `MIN_CONFIDENCE_THRESHOLD`

### Adding New Risk Factors
To add new risk factors:
1. Add detection logic to `evaluate_risk()`
2. Update threshold constants if needed
3. Extend `must_block()` for hard constraints
4. Update this taxonomy document
5. Add corresponding test scenarios

### Monitoring and Metrics
Key metrics to monitor:
- Block rate by risk category
- Average risk level over time
- Most common block reasons
- Concentration distribution across instruments

## Decision Matrix for Risk Levels

| Risk Factor | Low Risk (Conservative) | Medium Risk (Neutral) | High Risk (Aggressive) |
|-------------|-------------------------|----------------------|------------------------|
| **Max Single Instrument** | ≤ 30% | 30% < x ≤ 50% | > 50% (also blocked) |
| **Conflict Ratio** | ≤ 20% | 20% < x ≤ 35% | > 35% (also blocked) |
| **Min Confidence** | ≥ 0.3 | 0.1 ≤ x < 0.3 | < 0.1 (also blocked) |
| **Block Decision** | Never blocked | Blocked only if hard constraints | Often blocked |
| **Execution Mode** | Live candidate | Simulation-only | Simulation-only |
| **Operator Review** | Optional | Recommended | Required |

## References
- `simp/financial/a2a_safety.py` - Implementation
- `tests/test_financial_a2a_safety.py` - Validation tests
- `simp/docs/a2a_thresholds_and_rationale.md` - Detailed threshold rationale