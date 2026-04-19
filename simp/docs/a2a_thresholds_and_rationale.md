# A2A Safety Thresholds and Rationale

## Overview

This document provides detailed rationale for each safety threshold used in the A2A Safety Harness. Each threshold represents a carefully chosen boundary between acceptable and unacceptable risk levels.

## Core Safety Thresholds

### 1. MAX_SINGLE_INSTRUMENT_EXPOSURE = 0.3 (30%)

**Purpose**: Limits concentration risk in any single trading instrument.

**Rationale**:
- **Diversification Principle**: Prevents over-exposure to idiosyncratic risk of single assets
- **Market Impact**: Large positions in single instruments can move markets or be difficult to unwind
- **Liquidity Risk**: Concentrated positions may face liquidity constraints during stress
- **Agent Coordination**: Encourages agents to consider multiple instruments rather than focusing on one

**Implementation**:
```python
# In must_block()
for instrument, net_exposure in aggregate_exposure.items():
    exposure_pct = abs(net_exposure) / total_notional
    if exposure_pct > MAX_SINGLE_INSTRUMENT_EXPOSURE:  # 0.3
        return True  # Block execution
```

**Impact Analysis**:
- **Current (30%)**: Blocks plans with >30% single instrument concentration
- **If lowered to 25%**: Would block additional 5% of borderline plans, increasing safety but potentially missing opportunities
- **If raised to 35%**: Would allow more concentrated positions, increasing potential returns but also risk

**Empirical Justification**:
- **Portfolio Theory**: Modern portfolio theory suggests 20-30% as maximum single asset allocation for diversified portfolios
- **Hedge Fund Practice**: Many funds limit single positions to 20-30% of portfolio
- **Risk Management**: 30% provides buffer for price movements while allowing meaningful positions

**Adjustment Guidance**:
- **Lower (e.g., 0.2)**: For ultra-conservative strategies or when trading illiquid instruments
- **Higher (e.g., 0.4)**: For specialized strategies focusing on few instruments with deep liquidity
- **Never exceed 0.5**: Beyond 50% concentration represents unacceptable single-point risk

**Testing Boundary Cases**:
- **29.9%**: Should pass (not blocked)
- **30.0%**: Should pass (at threshold)
- **30.1%**: Should block (exceeds threshold)
- **50.0%**: Should block (well above threshold)

### 2. MAX_CONFLICTING_SIZE_RATIO = 0.2 (20%)

**Purpose**: Limits the amount of capital involved in contradictory trading decisions.

**Rationale**:
- **Agent Consensus**: Ensures agents generally agree on market direction
- **Capital Efficiency**: Avoids wasting capital on offsetting positions
- **Signal Quality**: High conflict suggests poor signal quality or agent misalignment
- **Execution Complexity**: Conflicting positions increase operational complexity

**Implementation**:
```python
# Calculate conflicting exposure
conflict_ratio = conflict_size / total_notional
if conflict_ratio > MAX_CONFLICTING_SIZE_RATIO:  # 0.2
    return True  # Block execution
```

**Impact Analysis**:
- **Current (20%)**: Blocks plans where >20% of capital is in conflicting positions
- **If lowered to 15%**: Would require higher agent consensus, reducing contradictory trades
- **If raised to 25%**: Would allow more disagreement among agents, potentially capturing more opportunities

**Empirical Justification**:
- **Trading Desks**: Professional desks typically limit intra-desk conflicts to 10-20% of capital
- **Signal Quality**: High conflict (>20%) often indicates poor signal quality or misaligned models
- **Operational Cost**: Conflicting positions incur transaction costs without clear directional benefit

**Adjustment Guidance**:
- **Lower (e.g., 0.1)**: For strategies requiring high agent consensus
- **Higher (e.g., 0.3)**: For strategies that intentionally use conflicting signals (e.g., market making)
- **Consider agent-specific thresholds**: Some agents may have higher conflict tolerance

**Testing Boundary Cases**:
- **19.9%**: Should pass (not blocked)
- **20.0%**: Should pass (at threshold)
- **20.1%**: Should block (exceeds threshold)
- **35.0%**: Should block (well above threshold)

### 3. HIGH_RISK_EXPOSURE_THRESHOLD = 0.5 (50%)

**Purpose**: Identifies plans with extremely high concentration for risk elevation.

**Rationale**:
- **Risk Classification**: Plans >50% concentration are clearly "High Risk"
- **Warning Signal**: Even if not blocked, these plans require special attention
- **Progressive Risk**: Provides gradient between blocking (30%) and extreme (50+%)

**Implementation**:
```python
# In evaluate_risk()
if max_exposure > HIGH_RISK_EXPOSURE_THRESHOLD:  # 0.5
    risk_level = RiskPosture.AGGRESSIVE
```

**Impact Analysis**:
- **Current (50%)**: Marks plans as High Risk when concentration exceeds 50%
- **If lowered to 40%**: Would classify more plans as High Risk, increasing caution
- **If raised to 60%**: Would allow higher concentrations before High Risk classification

**Empirical Justification**:
- **Regulatory Limits**: Many jurisdictions consider >50% concentration as high risk
- **Risk Management**: 50% represents "half your eggs in one basket" - clearly excessive
- **Progressive Scale**: Provides clear distinction: 30% (block), 30-50% (elevated), 50%+ (high)

**Adjustment Guidance**:
- **Tight coupling with blocking threshold**: Should always be ≥ `MAX_SINGLE_INSTRUMENT_EXPOSURE + 0.2`
- **Represents "clearly dangerous"**: Not just elevated risk, but clearly problematic
- **Should be stable**: Less frequently adjusted than blocking thresholds

**Testing Boundary Cases**:
- **49.9%**: Should be Medium Risk (if >30%)
- **50.0%**: Should be High Risk
- **50.1%**: Should be High Risk
- **75.0%**: Should be High Risk (and blocked)

### 4. MEDIUM_RISK_EXPOSURE_THRESHOLD = 0.3 (30%)

**Purpose**: Identifies the boundary between Low and Medium risk.

**Rationale**:
- **Matches blocking threshold**: Same as `MAX_SINGLE_INSTRUMENT_EXPOSURE`
- **Clear escalation**: Crossing this threshold elevates risk classification
- **Warning before blocking**: Provides risk elevation before hard blocking

**Implementation**:
```python
if max_exposure > MEDIUM_RISK_EXPOSURE_THRESHOLD:  # 0.3
    # Elevate risk level
    if risk_level == RiskPosture.CONSERVATIVE:
        risk_level = RiskPosture.NEUTRAL
    elif risk_level == RiskPosture.NEUTRAL:
        risk_level = RiskPosture.AGGRESSIVE
```

**Impact Analysis**:
- **Current (30%)**: Elevates risk when concentration exceeds 30%
- **If decoupled from blocking threshold**: Could provide earlier warning (e.g., 25% warning, 30% block)
- **If raised**: Would allow higher concentrations before risk elevation

**Empirical Justification**:
- **Consistency**: Using same threshold for blocking and risk elevation ensures consistency
- **Clear Signal**: Crossing 30% triggers both potential blocking and risk elevation
- **Operator Clarity**: Single threshold is easier for operators to understand

**Adjustment Guidance**:
- **Should equal blocking threshold**: Ensures consistency
- **Represents "elevated but acceptable"**: Not blocked, but requires attention
- **Consider decoupling**: Could use 25% for warning, 30% for blocking if more granularity needed

**Testing Boundary Cases**:
- **29.9%**: Should be Low Risk (if no other issues)
- **30.0%**: Should be Medium Risk (elevated from Conservative)
- **30.1%**: Should be Medium Risk
- **45.0%**: Should be Medium Risk (unless >50% for High Risk)

### 5. MIN_CONFIDENCE_THRESHOLD = 0.3 (30%)

**Purpose**: Minimum acceptable confidence level for agent decisions.

**Rationale**:
- **Signal Quality**: Filters out low-confidence noise
- **Agent Accountability**: Encourages agents to provide confidence estimates
- **Risk Assessment**: Low confidence contributes to overall risk evaluation
- **Progressive Filtering**: Different thresholds for warning (0.3) vs blocking (0.1)

**Implementation**:
```python
# Warning in evaluate_risk()
low_conf_decisions = [
    d for d in plan.decisions 
    if d.confidence is not None and d.confidence < MIN_CONFIDENCE_THRESHOLD  # 0.3
]

# Blocking in must_block()
extremely_low_conf = any(
    d.confidence is not None and d.confidence < 0.1  # Hard block threshold
    for d in plan.decisions
)
```

**Impact Analysis**:
- **Current (30%)**: Flags decisions with confidence <30% as low confidence
- **If lowered to 20%**: Would tolerate lower confidence before warning
- **If raised to 40%**: Would require higher confidence, potentially filtering good opportunities

**Empirical Justification**:
- **Signal-to-Noise**: Confidence <30% often indicates weak signals
- **Agent Calibration**: Well-calibrated agents should have meaningful confidence estimates
- **Progressive Filtering**: 30% warning, 10% blocking provides gradient

**Adjustment Guidance**:
- **Agent-specific thresholds**: Different agents may have different confidence scales
- **Context-dependent**: May adjust based on market conditions or strategy type
- **Consider confidence distribution**: Look at relative confidence, not just absolute

**Testing Boundary Cases**:
- **Confidence 0.09**: Should block (extremely low)
- **Confidence 0.10**: Should not block but warn (low confidence)
- **Confidence 0.29**: Should warn (low confidence)
- **Confidence 0.30**: Should not warn (at threshold)
- **Confidence 0.31**: Should not warn (above threshold)

## Threshold Relationships

### Hierarchical Structure
```
Blocking Thresholds (Hard Constraints)
├── MAX_SINGLE_INSTRUMENT_EXPOSURE (0.3) → Block if exceeded
├── MAX_CONFLICTING_SIZE_RATIO (0.2) → Block if exceeded
└── Extreme Low Confidence (0.1) → Block if any decision below

Risk Elevation Thresholds (Soft Constraints)
├── MEDIUM_RISK_EXPOSURE_THRESHOLD (0.3) → Elevate to Medium Risk
└── HIGH_RISK_EXPOSURE_THRESHOLD (0.5) → Elevate to High Risk

Warning Thresholds (Information Only)
└── MIN_CONFIDENCE_THRESHOLD (0.3) → Add to risk reasons
```

### Inter-threshold Dependencies
1. **Concentration thresholds are progressive**: 0.3 (block/elevate) → 0.5 (high risk)
2. **Confidence thresholds are progressive**: 0.3 (warning) → 0.1 (block)
3. **Conflict ratio is independent**: Doesn't interact with concentration thresholds
4. **Execution mode interacts**: SIMULATED_ONLY plans may have different thresholds

## Implementation Constants

All thresholds are defined in `simp/financial/a2a_safety.py`:

```python
# Safety configuration constants
MAX_SINGLE_INSTRUMENT_EXPOSURE = 0.3  # 30% of total notional
MAX_CONFLICTING_SIZE_RATIO = 0.2  # 20% of total notional in conflicting directions
HIGH_RISK_EXPOSURE_THRESHOLD = 0.5  # 50% exposure triggers high risk
MEDIUM_RISK_EXPOSURE_THRESHOLD = 0.3  # 30% exposure triggers medium risk
MIN_CONFIDENCE_THRESHOLD = 0.3  # Minimum confidence for decisions
```

## Threshold Adjustment Impact Matrix

| Threshold | Current Value | If Lowered | If Raised | Recommended Range |
|-----------|---------------|------------|-----------|-------------------|
| **MAX_SINGLE_INSTRUMENT_EXPOSURE** | 30% | **Safer**: Blocks more concentrated plans<br>**Cost**: May miss opportunities | **Riskier**: Allows more concentration<br>**Benefit**: Captures more opportunities | 25-35% |
| **MAX_CONFLICTING_SIZE_RATIO** | 20% | **More Consensus**: Requires agent agreement<br>**Cost**: Filters divergent signals | **More Diversity**: Allows conflicting views<br>**Risk**: Wasted capital on offsets | 15-25% |
| **HIGH_RISK_EXPOSURE_THRESHOLD** | 50% | **More Cautious**: Classifies more as High Risk<br>**Cost**: May over-warn | **Less Cautious**: Fewer High Risk classifications<br>**Risk**: Misses extreme concentrations | 40-60% |
| **MEDIUM_RISK_EXPOSURE_THRESHOLD** | 30% | **Earlier Warning**: Elevates risk sooner<br>**Cost**: May cry wolf | **Later Warning**: Allows more before warning<br>**Risk**: Late risk detection | 25-35% |
| **MIN_CONFIDENCE_THRESHOLD** | 30% | **More Tolerant**: Allows lower confidence<br>**Risk**: More noise | **Stricter**: Requires higher confidence<br>**Cost**: Filters good signals | 20-40% |

## Testing Thresholds

### Test Coverage
Each threshold should have:
1. **Boundary tests**: Values just below and above threshold
2. **Edge case tests**: Zero, negative, extreme values
3. **Integration tests**: Multiple thresholds interacting
4. **Scenario tests**: Realistic trading scenarios

### Example Test Pattern
```python
def test_single_instrument_concentration_boundary():
    """Test concentration at 29.9% vs 30.1% of total notional."""
    # 29.9% concentration → should not block
    plan1 = create_plan_with_concentration(0.299)
    assert must_block(plan1) == False
    
    # 30.1% concentration → should block
    plan2 = create_plan_with_concentration(0.301)
    assert must_block(plan2) == True
```

### Threshold Interaction Tests
```python
def test_threshold_interactions():
    """Test how thresholds interact."""
    # Plan with 28% concentration (below block) but 22% conflict (above block)
    plan = create_plan(concentration=0.28, conflict_ratio=0.22)
    assert must_block(plan) == True  # Blocked by conflict
    
    # Plan with 32% concentration (above block) but 18% conflict (below block)
    plan = create_plan(concentration=0.32, conflict_ratio=0.18)
    assert must_block(plan) == True  # Blocked by concentration
```

## Operational Considerations

### Monitoring Threshold Effectiveness
Monitor:
- **Block rate by threshold**: Which thresholds trigger blocks most often
- **False positive rate**: Plans blocked that later proved safe
- **Threshold utilization**: How close plans typically come to thresholds
- **Agent behavior**: How agents adapt to thresholds

### Adjusting Thresholds
**Process for threshold adjustment**:
1. **Data Collection**: Gather historical plan data and outcomes
2. **Analysis**: Calculate optimal thresholds based on risk/return tradeoff
3. **Testing**: Validate new thresholds with backtesting
4. **Staging**: Deploy to simulation environment first
5. **Monitoring**: Closely monitor after deployment

**Never adjust multiple thresholds simultaneously**: Change one at a time and observe effects.

### Threshold Evolution
As the system matures, consider:
1. **Dynamic thresholds**: Adjust based on market conditions
2. **Agent-specific thresholds**: Different thresholds for different agent types
3. **Instrument-specific thresholds**: Different thresholds for different asset classes
4. **Time-varying thresholds**: Tighter thresholds during high volatility

## Future Extensions

### Potential Additional Thresholds
1. **Maximum total notional**: Limit total position size
2. **Sector concentration**: Limit exposure to specific sectors
3. **Liquidity thresholds**: Minimum liquidity requirements
4. **Volatility-adjusted thresholds**: Tighter during high volatility

### Threshold Validation Framework
Consider building:
1. **Threshold backtesting**: Historical validation of threshold effectiveness
2. **Threshold optimization**: Automated tuning based on objectives
3. **Threshold sensitivity analysis**: Understand impact of small changes

## Threshold Decision Guide

### When to Adjust Thresholds
| Scenario | Action | Example |
|----------|--------|---------|
| **High false block rate** | Consider raising blocking thresholds | If 30% of blocked plans would have been profitable |
| **Missed opportunities** | Analyze if thresholds too conservative | Good plans consistently near but below thresholds |
| **Agent adaptation** | Adjust if agents gaming thresholds | Agents splitting large orders to avoid concentration |
| **Market regime change** | Consider dynamic adjustment | Tighter thresholds during high volatility |

### Threshold Adjustment Checklist
- [ ] Historical analysis of threshold performance
- [ ] Backtest with proposed new values
- [ ] Update documentation
- [ ] Update tests
- [ ] Deploy to simulation first
- [ ] Monitor closely after deployment
- [ ] Review after sufficient data collected

## References
- `simp/financial/a2a_safety.py` - Implementation
- `tests/test_financial_a2a_safety.py` - Test coverage
- `simp/docs/a2a_risk_taxonomy.md` - Risk category definitions
- `simp/docs/a2a_scenario_catalog.md` - Example scenarios