# A2A Safety Scenario Catalog

## Overview

This catalog documents concrete scenarios for testing and validating the A2A Safety Harness. Each scenario includes specific agent decisions, expected risk evaluation, and block decisions.

## Scenario Categories

### Category 1: Single Agent Scenarios
Scenarios involving decisions from a single agent.

#### Scenario 1.1: Conservative Single Instrument
**Description**: Single agent recommends moderate position in one instrument.

**Decisions**:
- Agent: `quantumarb`
- Instrument: `BTC-USD`
- Side: `BUY`
- Quantity: `300 USD` (30% of 1000 total)
- Confidence: `0.8`

**Expected Results**:
- `must_block()`: `False` (concentration = 30%, at threshold but not exceeding)
- `evaluate_risk()`: `risk_level: "conservative"`
- `max_single_instrument_exposure`: `0.3`
- Block Reason: `None`

**Test Purpose**: Verify threshold boundary behavior.

#### Scenario 1.2: Aggressive Single Instrument
**Description**: Single agent recommends large position exceeding concentration limit.

**Decisions**:
- Agent: `kashclaw`
- Instrument: `ETH-USD`
- Side: `BUY`
- Quantity: `350 USD` (35% of 1000 total)
- Confidence: `0.7`

**Expected Results**:
- `must_block()`: `True` (concentration > 30%)
- Block Reason: `"Single instrument concentration: ETH-USD has 35.0% exposure"`
- `evaluate_risk()`: Should still run but show high risk

**Test Purpose**: Verify hard blocking on concentration limit.

#### Scenario 1.3: Low Confidence Single Instrument
**Description**: Single agent with extremely low confidence.

**Decisions**:
- Agent: `kloutbot`
- Instrument: `SOL-USD`
- Side: `BUY`
- Quantity: `100 USD` (10% of 1000 total)
- Confidence: `0.05` (extremely low)

**Expected Results**:
- `must_block()`: `True` (confidence < 0.1)
- Block Reason: `"Extremely low confidence decisions"`
- `evaluate_risk()`: Should flag low confidence

**Test Purpose**: Verify confidence-based blocking.

### Category 2: Multi-Agent Cooperative Scenarios
Scenarios where multiple agents agree on market direction.

#### Scenario 2.1: Diversified Consensus
**Description**: Multiple agents agree on different instruments.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `250 USD`, confidence `0.8`
2. `kashclaw`: `ETH-USD`, `BUY`, `250 USD`, confidence `0.7`
3. `kloutbot`: `SOL-USD`, `BUY`, `250 USD`, confidence `0.6`
4. `agent4`: `ADA-USD`, `BUY`, `250 USD`, confidence `0.5`

**Expected Results**:
- `must_block()`: `False` (max concentration = 25%)
- `evaluate_risk()`: `risk_level: "conservative"`
- `number_of_conflicting_decisions`: `0`
- Total Notional: `1000 USD`

**Test Purpose**: Verify well-diversified multi-agent plans pass.

#### Scenario 2.2: Concentrated Consensus
**Description**: Multiple agents agree on same instrument.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `200 USD`, confidence `0.8`
2. `kashclaw`: `BTC-USD`, `BUY`, `200 USD`, confidence `0.7`
3. `kloutbot`: `BTC-USD`, `BUY`, `200 USD`, confidence `0.6`

**Expected Results**:
- `must_block()`: `True` (concentration = 100% > 30%)
- Block Reason: `"Single instrument concentration: BTC-USD has 100.0% exposure"`
- `evaluate_risk()`: Should show aggressive risk

**Test Purpose**: Verify concentration detection across multiple agents.

### Category 3: Multi-Agent Conflicting Scenarios
Scenarios where agents disagree on market direction.

#### Scenario 3.1: Minor Conflict
**Description**: Small conflicting positions within limits.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `400 USD`, confidence `0.8`
2. `kashclaw`: `BTC-USD`, `SELL`, `100 USD`, confidence `0.7`
3. `kloutbot`: `ETH-USD`, `BUY`, `300 USD`, confidence `0.6`

**Expected Results**:
- `must_block()`: `False` (conflict ratio = 100/800 = 12.5% < 20%)
- `evaluate_risk()`: `risk_level: "neutral"` (due to BTC concentration = 37.5%)
- `number_of_conflicting_decisions`: `1` (BTC-USD)
- Conflicting ratio: `0.125`

**Test Purpose**: Verify conflict detection within acceptable limits.

#### Scenario 3.2: Major Conflict
**Description**: Large conflicting positions exceeding limit.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `400 USD`, confidence `0.8`
2. `kashclaw`: `BTC-USD`, `SELL`, `300 USD`, confidence `0.7`
3. `kloutbot`: `ETH-USD`, `BUY`, `300 USD`, confidence `0.6`

**Expected Results**:
- `must_block()`: `True` (conflict ratio = 300/1000 = 30% > 20%)
- Block Reason: `"High conflicting exposure: 30.0% of notional in conflicting directions"`
- `evaluate_risk()`: Should show aggressive risk

**Test Purpose**: Verify conflict ratio blocking.

#### Scenario 3.3: Cross-Instrument Conflict
**Description**: Agents taking opposite sides on correlated instruments.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `300 USD`, confidence `0.8`
2. `kashclaw`: `ETH-USD`, `SELL`, `300 USD`, confidence `0.7`
3. `kloutbot`: `SOL-USD`, `BUY`, `200 USD`, confidence `0.6`
4. `agent4`: `ADA-USD`, `SELL`, `200 USD`, confidence `0.5`

**Expected Results**:
- `must_block()`: `False` (no single-instrument conflicts)
- `evaluate_risk()`: `risk_level: "neutral"`
- `number_of_conflicting_decisions`: `0` (different instruments)
- Note: Cross-instrument conflicts not currently detected

**Test Purpose**: Verify current conflict detection scope.

### Category 4: Edge Cases and Boundary Conditions

#### Scenario 4.1: Zero Quantity
**Description**: Agent recommends zero quantity (effectively HOLD).

**Decisions**:
- Agent: `quantumarb`
- Instrument: `BTC-USD`
- Side: `BUY`
- Quantity: `0 USD`
- Confidence: `0.8`

**Expected Results**:
- `must_block()`: `False` (empty plan)
- `evaluate_risk()`: `risk_level: "conservative"`
- Total Notional: `0`
- Special handling for zero notional plans

**Test Purpose**: Verify zero-quantity handling.

#### Scenario 4.2: Mixed Confidence Levels
**Description**: Agents with varying confidence levels.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `200 USD`, confidence `0.9` (high)
2. `kashclaw`: `ETH-USD`, `BUY`, `200 USD`, confidence `0.25` (low)
3. `kloutbot`: `SOL-USD`, `BUY`, `200 USD`, confidence `None` (missing)

**Expected Results**:
- `must_block()`: `False` (no hard blocks)
- `evaluate_risk()`: Should flag low confidence from kashclaw
- Risk reasons should include: `"Low confidence decisions from: kashclaw"`

**Test Purpose**: Verify confidence threshold warnings.

#### Scenario 4.3: Extreme Values
**Description**: Very large quantities and mixed directions.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `1000000 USD`, confidence `0.8`
2. `kashclaw`: `BTC-USD`, `SELL`, `500000 USD`, confidence `0.7`
3. `kloutbot`: `ETH-USD`, `BUY`, `500000 USD`, confidence `0.6`

**Expected Results**:
- `must_block()`: `True` (multiple violations)
- Likely block reasons: Concentration and conflict ratio
- `evaluate_risk()`: Should show aggressive risk with multiple reasons

**Test Purpose**: Verify handling of extreme numerical values.

### Category 5: Integration Scenarios

#### Scenario 5.1: Full Pipeline - Safe Plan
**Description**: Complete pipeline from decisions to simulation.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `300 USD`, confidence `0.8`
2. `kashclaw`: `ETH-USD`, `BUY`, `300 USD`, confidence `0.7`
3. `kloutbot`: `SOL-USD`, `BUY`, `200 USD`, confidence `0.6`
4. `agent4`: `ADA-USD`, `BUY`, `200 USD`, confidence `0.5`

**Pipeline Steps**:
1. `build_a2a_plan()` → Creates A2APlan
2. `evaluate_risk()` → Returns conservative risk
3. `must_block()` → Returns False
4. `simulate_execution()` → Returns simulated trades

**Expected Results**:
- Plan passes all safety checks
- Simulation produces 4 trades (one per instrument)
- Resulting posture shows diversified exposure

**Test Purpose**: Verify end-to-end happy path.

#### Scenario 5.2: Full Pipeline - Blocked Plan
**Description**: Plan that gets blocked in pipeline.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `500 USD`, confidence `0.8`
2. `kashclaw`: `ETH-USD`, `BUY`, `300 USD`, confidence `0.7`
3. `kloutbot`: `SOL-USD`, `BUY`, `200 USD`, confidence `0.6`

**Pipeline Steps**:
1. `build_a2a_plan()` → Creates A2APlan
2. `evaluate_risk()` → Returns aggressive risk (BTC = 50%)
3. `must_block()` → Returns True (concentration > 30%)
4. `simulate_execution()` → Returns blocked result

**Expected Results**:
- Plan blocked at safety check
- Simulation returns empty trades with block reason
- Block reason indicates concentration violation

**Test Purpose**: Verify end-to-end blocking path.

### Category 6: Specialized Agent Scenarios

#### Scenario 6.1: TimesFM-Enhanced Decisions
**Description**: Agents using TimesFM forecasting.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `300 USD`, confidence `0.8`, `timesfm_used: True`
2. `kashclaw`: `ETH-USD`, `BUY`, `300 USD`, confidence `0.7`, `timesfm_used: True`
3. `kloutbot`: `SOL-USD`, `HOLD`, `0 USD`, confidence `0.6`, `timesfm_used: True`

**Expected Results**:
- `must_block()`: `False` (safe concentrations)
- `evaluate_risk()`: Normal evaluation
- TimesFM usage doesn't affect safety (currently)
- HOLD decision doesn't generate trade

**Test Purpose**: Verify TimesFM integration doesn't break safety.

#### Scenario 6.2: Mixed Horizon Decisions
**Description**: Agents with different time horizons.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `300 USD`, confidence `0.8`, `horizon_days: 1`
2. `kashclaw`: `ETH-USD`, `BUY`, `300 USD`, confidence `0.7`, `horizon_days: 7`
3. `kloutbot`: `SOL-USD`, `BUY`, `200 USD`, confidence `0.6`, `horizon_days: 30`

**Expected Results**:
- `must_block()`: `False` (horizon doesn't affect safety)
- `evaluate_risk()`: Normal evaluation
- Horizon information preserved but not used in safety

**Test Purpose**: Verify horizon field handling.

### Category 7: Failure Mode Scenarios

#### Scenario 7.1: Invalid Data Types
**Description**: Decisions with incorrect data types.

**Decisions Attempt**:
- Agent: `quantumarb`
- Instrument: `BTC-USD`
- Side: `"INVALID_SIDE"` (not a valid Side enum)
- Quantity: `"not_a_number"` (string instead of float)
- Confidence: `1.5` (outside 0-1 range)

**Expected Results**:
- `AgentDecisionSummary` constructor should raise `ValueError`
- Plan building should fail before safety checks
- Schema validation should catch errors

**Test Purpose**: Verify schema validation catches invalid data.

#### Scenario 7.2: Missing Required Fields
**Description**: Decisions with missing critical fields.

**Decisions Attempt**:
- Agent: `""` (empty string)
- Instrument: `None` (missing)
- Side: `BUY`
- Quantity: `100 USD`
- Confidence: `0.8`

**Expected Results**:
- `AgentDecisionSummary` constructor should raise `ValueError`
- Validation should fail on empty agent_name and None instrument

**Test Purpose**: Verify required field validation.

## NEW: Category 8: Complex Multi-Agent Conflict Scenarios

#### Scenario 8.1: Multiple Instrument Conflicts with Partial Agreement
**Description**: Agents disagree on multiple instruments but agree on others.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `300 USD`, confidence `0.8`
2. `kashclaw`: `BTC-USD`, `SELL`, `150 USD`, confidence `0.7`
3. `kloutbot`: `ETH-USD`, `BUY`, `200 USD`, confidence `0.6`
4. `agent4`: `ETH-USD`, `SELL`, `100 USD`, confidence `0.5`
5. `agent5`: `SOL-USD`, `BUY`, `250 USD`, confidence `0.9` (unanimous agreement)

**Analysis**:
- BTC conflict: $150 conflicting of $450 total = 33% conflict ratio for BTC
- ETH conflict: $100 conflicting of $300 total = 33% conflict ratio for ETH
- Total conflicting exposure: $150 + $100 = $250
- Total notional: $300 + $150 + $200 + $100 + $250 = $1000
- Overall conflict ratio: $250/$1000 = 25% (>20% threshold)

**Expected Results**:
- `must_block()`: `True` (overall conflict ratio 25% > 20%)
- Block Reason: `"High conflicting exposure: 25.0% of notional in conflicting directions"`
- `evaluate_risk()`: `risk_level: "aggressive"` (multiple conflicts)

**Test Purpose**: Verify aggregate conflict ratio calculation across multiple instruments.

#### Scenario 8.2: High Concentration with Compensating Conflicts
**Description**: High single instrument concentration partially offset by conflicting positions.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `600 USD`, confidence `0.8`
2. `kashclaw`: `BTC-USD`, `SELL`, `300 USD`, confidence `0.7`
3. `kloutbot`: `ETH-USD`, `BUY`, `100 USD`, confidence `0.6`

**Analysis**:
- Net BTC exposure: $600 - $300 = $300 BUY
- Total notional: $600 + $300 + $100 = $1000
- BTC concentration: $600/$1000 = 60% (gross, violates >30%)
- Conflict ratio: $300/$1000 = 30% (>20% threshold)

**Expected Results**:
- `must_block()`: `True` (multiple violations: concentration 60% > 30% AND conflict 30% > 20%)
- Which violation triggers first depends on implementation order
- Likely concentration check first (immediate block at 60% > 30%)

**Test Purpose**: Verify multiple violation handling and check order.

#### Scenario 8.3: Borderline Concentration with Multiple Small Conflicts
**Description**: Concentration at threshold with distributed small conflicts.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `310 USD`, confidence `0.8` (31% concentration)
2. `kashclaw`: `BTC-USD`, `SELL`, `50 USD`, confidence `0.7` (5% conflict)
3. `kloutbot`: `ETH-USD`, `BUY`, `200 USD`, confidence `0.6`
4. `agent4`: `ETH-USD`, `SELL`, `40 USD`, confidence `0.5` (4% conflict)
5. `agent5`: `SOL-USD`, `BUY`, `200 USD`, confidence `0.9`
6. `agent6`: `SOL-USD`, `SELL`, `30 USD`, confidence `0.4` (3% conflict)
7. `agent7`: `ADA-USD`, `BUY`, `170 USD`, confidence `0.3`

**Analysis**:
- Total notional: $310 + $50 + $200 + $40 + $200 + $30 + $170 = $1000
- BTC concentration: $310/$1000 = 31% (>30% threshold)
- Total conflict: $50 + $40 + $30 = $120
- Conflict ratio: $120/$1000 = 12% (<20% threshold)

**Expected Results**:
- `must_block()`: `True` (concentration 31% > 30%)
- Block Reason: `"Single instrument concentration: BTC-USD has 31.0% exposure"`
- `evaluate_risk()`: `risk_level: "aggressive"` (concentration >30%)

**Test Purpose**: Verify concentration check happens before conflict aggregation.

#### Scenario 8.4: Agent-Specific Confidence Thresholds (Future Feature)
**Description**: Different agents have different minimum confidence requirements.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `200 USD`, confidence `0.15` (low for quantumarb)
2. `kashclaw`: `ETH-USD`, `BUY`, `200 USD`, confidence `0.25` (acceptable for kashclaw)
3. `kloutbot`: `SOL-USD`, `BUY`, `200 USD`, confidence `0.35` (good for kloutbot)

**Current System Behavior**:
- All decisions checked against same MIN_CONFIDENCE_THRESHOLD (0.3)
- quantumarb decision (0.15) < 0.3 → warning but not blocked
- kashclaw decision (0.25) < 0.3 → warning but not blocked
- No decisions < 0.1 → not blocked by extreme low confidence

**Future Enhancement**:
- Agent-specific thresholds: quantumarb: 0.2, kashclaw: 0.3, kloutbot: 0.4
- Would block quantumarb decision (0.15 < 0.2)

**Test Purpose**: Document current behavior and future enhancement path.

## NEW: Category 9: Borderline and Gray Area Scenarios

#### Scenario 9.1: Exactly At Threshold Values
**Description**: Plans with values exactly at safety thresholds.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `300 USD`, confidence `0.8` (exactly 30% of $1000)
2. `kashclaw`: `ETH-USD`, `BUY`, `350 USD`, confidence `0.7`
3. `kloutbot`: `SOL-USD`, `BUY`, `350 USD`, confidence `0.6`

**Analysis**:
- Total notional: $300 + $350 + $350 = $1000
- BTC concentration: $300/$1000 = 30.0% (exactly at threshold)
- Implementation uses `>` not `>=` for blocking

**Expected Results**:
- `must_block()`: `False` (30.0% not > 30.0%)
- `evaluate_risk()`: `risk_level: "neutral"` (elevated due to 30% concentration)
- Max exposure reported as 0.3

**Test Purpose**: Verify threshold comparison is exclusive (> not >=).

#### Scenario 9.2: Floating Point Precision Edge Cases
**Description**: Very close to threshold values that might have floating point issues.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `300.0000001 USD`, confidence `0.8`
2. `kashclaw`: `ETH-USD`, `BUY`, `349.9999999 USD`, confidence `0.7`
3. `kloutbot`: `SOL-USD`, `BUY`, `350.0 USD`, confidence `0.6`

**Analysis**:
- Total notional: ~$1000.0000000
- BTC concentration: 300.0000001/1000 ≈ 30.00000001% (slightly above 30%)
- Floating point comparison: 0.3000000001 > 0.3 = True

**Expected Results**:
- `must_block()`: `True` (technically > 30% due to floating point)
- Block Reason: `"Single instrument concentration: BTC-USD has 30.00000001% exposure"`
- Practical consideration: May want epsilon tolerance

**Test Purpose**: Highlight floating point precision considerations.

#### Scenario 9.3: Mixed HOLD and Trade Decisions
**Description**: Some agents recommend HOLD while others trade.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `400 USD`, confidence `0.8`
2. `kashclaw`: `BTC-USD`, `HOLD`, `0 USD`, confidence `0.7`
3. `kloutbot`: `BTC-USD`, `SELL`, `200 USD`, confidence `0.6`
4. `agent4`: `ETH-USD`, `HOLD`, `0 USD`, confidence `0.5`

**Analysis**:
- HOLD decisions contribute 0 to notional and exposure
- Total notional: $400 + $0 + $200 + $0 = $600
- BTC concentration: $400/$600 = 66.7% (>30%)
- Conflict: $200 conflicting of $600 = 33.3% (>20%)

**Expected Results**:
- `must_block()`: `True` (multiple violations)
- HOLD decisions ignored in exposure calculations
- Only BUY/SELL decisions affect safety checks

**Test Purpose**: Verify HOLD decision handling.

#### Scenario 9.4: Negative Quantities (Error Case)
**Description**: Invalid negative quantity values.

**Decisions Attempt**:
- Agent: `quantumarb`
- Instrument: `BTC-USD`
- Side: `BUY`
- Quantity: `-100 USD` (negative)
- Confidence: `0.8`

**Expected Results**:
- `AgentDecisionSummary` should validate quantity > 0
- Should raise `ValueError` or similar
- Safety checks never reached due to validation failure

**Test Purpose**: Verify input validation catches negative quantities.

## NEW: Category 10: Simulation-Specific Scenarios

#### Scenario 10.1: Simulated Price Consistency
**Description**: Verify simulated prices are deterministic.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `100 USD`, confidence `0.8`
2. `kashclaw`: `ETH-USD`, `BUY`, `100 USD`, confidence `0.7`
3. `kloutbot`: `SOL-USD`, `BUY`, `100 USD`, confidence `0.6`

**Simulation Behavior**:
- `_get_simulated_price("BTC-USD")` returns 65000.0 (from price_map)
- `_get_simulated_price("ETH-USD")` returns 3500.0 (from price_map)
- `_get_simulated_price("SOL-USD")` returns 150.0 (from price_map)
- Unknown instruments get hash-based deterministic prices

**Expected Results**:
- Same plan → same simulated prices every time
- Simulation ID changes (UUID-based)
- Trade execution order consistent

**Test Purpose**: Verify simulation determinism for testing.

#### Scenario 10.2: Simulation with Blocked Plan
**Description**: What happens when simulate_execution receives blocked plan.

**Decisions**:
1. `quantumarb`: `BTC-USD`, `BUY`, `500 USD`, confidence `0.8` (50% concentration)

**Simulation Steps**:
1. `must_block()` returns True
2. `simulate_execution()` returns early with blocked result
3. No trades simulated
4. Resulting posture = original posture

**Expected Results**:
- `simulate_execution()` returns `blocked: True`
- `simulated_trades`: empty list
- `blocked_reason`: concentration violation
- `resulting_posture`: unchanged

**Test Purpose**: Verify simulation respects block decisions.

#### Scenario 10.3: Multiple Plan Batch Simulation
**Description**: Testing `simulate_multiple_plans()` function.

**Plans**:
1. Safe plan: 3 instruments, 25% concentration each
2. Blocked plan: BTC 50% concentration
3. Safe plan: 2 instruments, 40% each (borderline but not blocked)

**Expected Results**:
- `simulate_multiple_plans()` returns dict with 3 results
- Summary shows: total_plans=3, blocked_plans=1, executed_plans=2
- Block rate = 1/3 ≈ 33.3%
- Each plan has unique simulation_id

**Test Purpose**: Verify batch simulation functionality.

## Scenario Implementation Notes

### Test Data Generation
Each scenario should be implemented as a test fixture:

```python
@pytest.fixture
def scenario_1_1_conservative_single():
    """Scenario 1.1: Conservative single instrument."""
    decisions = [
        AgentDecisionSummary(
            agent_name="quantumarb",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=300.0,
            units="USD",
            confidence=0.8
        )
    ]
    return build_a2a_plan(decisions)
```

### Expected Results Verification
Tests should verify both safety evaluation and simulation:

```python
def test_scenario_1_1(scenario_1_1_conservative_single):
    plan = scenario_1_1_conservative_single
    
    # Safety evaluation
    assert must_block(plan) == False
    risk = evaluate_risk(plan)
    assert risk["risk_level"] == "conservative"
    assert risk["max_single_instrument_exposure"] == 0.3
    
    # Simulation
    simulation = simulate_execution(plan)
    assert simulation["blocked"] == False
    assert len(simulation["simulated_trades"]) == 1
```

### Scenario Coverage Matrix
| Scenario | Concentration | Conflict | Confidence | Expected Block | Risk Level |
|----------|---------------|----------|------------|----------------|------------|
| 1.1 | 30% | 0% | High | No | Conservative |
| 1.2 | 35% | 0% | Medium | Yes | Aggressive |
| 1.3 | 10% | 0% | Very Low | Yes | Aggressive |
| 2.1 | 25% | 0% | Mixed | No | Conservative |
| 2.2 | 100% | 0% | Mixed | Yes | Aggressive |
| 3.1 | 37.5% | 12.5% | Mixed | No | Neutral |
| 3.2 | 40% | 30% | Mixed | Yes | Aggressive |
| 3.3 | 30% | 0% | Mixed | No | Neutral |
| 4.1 | 0% | 0% | High | No | Conservative |
| 4.2 | 33% | 0% | Mixed | No | Neutral |
| 4.3 | 50% | 25% | Mixed | Yes | Aggressive |
| 5.1 | 30% | 0% | Mixed | No | Conservative |
| 5.2 | 50% | 0% | Mixed | Yes | Aggressive |
| 6.1 | 30% | 0% | Mixed | No | Conservative |
| 6.2 | 30% | 0% | Mixed | No | Conservative |
| 8.1 | 30% | 25% | Mixed | Yes | Aggressive |
| 8.2 | 60% | 30% | Mixed | Yes | Aggressive |
| 8.3 | 31% | 12% | Mixed | Yes | Aggressive |
| 9.1 | 30% | 0% | Mixed | No | Neutral |
| 9.2 | 30.00000001% | 0% | Mixed | Yes | Aggressive |
| 9.3 | 66.7% | 33.3% | Mixed | Yes | Aggressive |
| 10.1 | 33% | 0% | Mixed | No | Conservative |
| 10.2 | 50% | 0% | High | Yes | Aggressive |
| 10.3 | Mixed | Mixed | Mixed | Mixed | Mixed |

## Using This Catalog

### For Testing
1. Implement each scenario as a test case
2. Verify expected outcomes match actual behavior
3. Add new scenarios as safety logic evolves

### For Development
1. Use scenarios to understand safety behavior
2. Reference scenarios when modifying safety logic
3. Ensure modifications don't break existing scenario expectations

### For Documentation
1. Reference scenarios in API documentation
2. Use scenarios to explain safety concepts
3. Update scenarios when thresholds or logic change

## References
- `tests/test_financial_a2a_safety.py` - Existing safety tests
- `tests/test_financial_a2a_simulator.py` - Existing simulator tests
- `tests/test_financial_a2a_pipeline.py` - Pipeline integration tests
- `simp/docs/a2a_risk_taxonomy.md` - Risk category definitions
- `simp/docs/a2a_thresholds_and_rationale.md` - Threshold explanations