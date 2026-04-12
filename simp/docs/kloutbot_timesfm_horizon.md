# Kloutbot TimesFM Horizon Advice

## Overview

Kloutbot uses TimesFM (Time Series Foundation Model) to forecast affinity persistence and recommend optimal strategy horizons. This document describes how horizon advice is computed, its safety guarantees, and how operators should interpret the results.

## How Horizon Advice is Computed

### 1. Data Collection
- **Affinity History**: Kloutbot maintains a rolling buffer of affinity values (0.0-1.0) representing market alignment
- **Minimum History**: Requires at least 16 observations before using TimesFM
- **Series ID**: `{agent_id}:affinity` uniquely identifies each agent's affinity series

### 2. TimesFM Integration Flow
```python
# Simplified flow in KloutbotAgent._get_strategy_horizon_advice()
1. Check history length (≥16 observations)
2. Policy evaluation via PolicyEngine
3. TimesFM forecast request (32-step horizon)
4. Persistence calculation (steps > 0.5 threshold)
5. Bucket mapping (short/medium/long)
6. Rationale generation
```

### 3. Persistence Calculation
```python
# Estimate how long affinity stays above 0.5 threshold
persistence_steps = next(
    (i for i, v in enumerate(forecast) if v < 0.5),
    len(forecast),  # All steps above threshold
)
```

### 4. Horizon Bucket Mapping (ADR 003)
| Persistence Steps | Horizon Label | Step Count | Trading Implication |
|-------------------|---------------|------------|---------------------|
| ≥ 24              | Long          | 32 steps   | Strategic positioning |
| ≥ 12 and < 24     | Medium        | 16 steps   | Near-term planning |
| < 12              | Short         | 8 steps    | Immediate execution |

**Threshold Rationale:**
- **0.5**: Standard statistical significance threshold
- **12 steps**: Boundary between intraday and multi-day strategies
- **24 steps**: Boundary between daily and weekly strategies

## Safety Guarantees

### 1. Never Raises
The horizon advice method is wrapped in a try-except block and never raises exceptions. Any error results in fallback to default medium horizon.

### 2. Conservative Fallbacks
When TimesFM is unavailable or cannot provide advice, the system falls back to:
- **Default Horizon**: Medium (16 steps)
- **Default Rationale**: Explains why TimesFM wasn't used

**Fallback Conditions:**
- Insufficient history (< 16 observations)
- Policy denied by PolicyEngine
- TimesFM service unavailable (shadow mode)
- Any exception during processing

### 3. Safe Step Ranges
- **Short**: 8 steps (1-2 hours for typical frequencies)
- **Medium**: 16 steps (≈1 trading day)
- **Long**: 32 steps (≈1 trading week)

All step counts are:
- Positive integers (> 0)
- Powers of 2 (8, 16, 32)
- Bounded (≤ 32 steps maximum)

### 4. Policy Enforcement
- **AgentContext**: Includes agent_id, series metadata, and request context
- **PolicyEngine**: Evaluates safety policies before forecast
- **Audit Logging**: All requests and responses are logged

## Operator Interpretation

### Response Schema
```json
{
  "recommended_horizon": "medium",
  "recommended_horizon_steps": 16,
  "timesfm_horizon_applied": true,
  "timesfm_horizon_rationale": "TimesFM forecast: affinity persists 18 steps > 0.5 threshold. Using medium horizon (16 steps) for near-term planning."
}
```

### Field Descriptions

#### `recommended_horizon`
- **Values**: `"short"`, `"medium"`, `"long"`
- **Interpretation**: Qualitative horizon recommendation
- **Action**: Use for strategy categorization and reporting

#### `recommended_horizon_steps`
- **Values**: `8`, `16`, `32`
- **Interpretation**: Quantitative step count for QIntentCompiler
- **Action**: Pass directly to compiler for strategy generation

#### `timesfm_horizon_applied`
- **Type**: Boolean
- **True**: TimesFM forecast was successfully used
- **False**: Fallback to default horizon (check rationale)
- **Action**: Monitor for high fallback rates (indicates system issues)

#### `timesfm_horizon_rationale`
- **Type**: String
- **Content**: Human-readable explanation of the recommendation
- **Includes**: Persistence steps, threshold, horizon logic
- **Action**: Review for debugging and operator awareness

### Monitoring Guidelines

#### Normal Operation
- `timesfm_horizon_applied`: Should be `true` most of the time
- Horizon distribution: Should vary based on market conditions
- Rationale: Should contain meaningful forecast information

#### Warning Signs
- High fallback rate (`timesfm_horizon_applied: false`)
- Single horizon dominating (> 80% of strategies)
- Vague or error rationales
- Policy denials increasing

#### Alert Thresholds
- **Critical**: > 50% fallback rate for 1 hour
- **Warning**: > 80% single horizon for 4 hours
- **Info**: Policy denial rate > 10%

## Integration Points

### 1. QIntentCompiler
- Receives `horizon_steps` parameter (8, 16, or 32)
- Optimizes strategy trees for the specified horizon
- Caches optimizations per step count

### 2. Strategy Generation
```python
# In KloutbotAgent.handle_generate_strategy()
advice = await self._get_strategy_horizon_advice(affinity, drift_risk)
tree = await self.compiler.compile_intent(
    streams=streams,
    foresight=foresight,
    deltas=deltas,
    horizon_steps=advice["recommended_horizon_steps"],  # ← From TimesFM
    timestamp=timestamp
)
```

### 3. A2A Compatibility
- Horizon labels map to standard A2A time categories
- Included in `AgentDecisionSummary` responses
- Rationale text provides transparency to other agents

## Testing Coverage

### Unit Tests (`test_kloutbot_timesfm_horizon.py`)
- ✅ All three horizon buckets
- ✅ Boundary values (12, 24 persistence steps)
- ✅ Fallback scenarios (insufficient history, policy denied, shadow mode)
- ✅ Error handling
- ✅ Integration with strategy generation
- ✅ Response schema validation
- ✅ Horizon stability with intermittent service

### Verification Tests
- Horizon mapping matches ADR specification
- Step ranges are safe and bounded
- Fallback behavior works correctly
- Rationale consistency across scenarios

## Troubleshooting

### Common Issues

#### 1. Always Falling Back
**Symptoms**: `timesfm_horizon_applied: false` consistently
**Check**:
- Affinity history length (need ≥ 16 observations)
- TimesFM service health (`GET /timesfm/health`)
- Policy engine logs
- Network connectivity to TimesFM service

#### 2. Single Horizon Dominating
**Symptoms**: > 80% strategies use same horizon
**Check**:
- Market conditions (volatile markets → shorter horizons)
- Affinity values (consistently high/low)
- TimesFM forecast quality
- Threshold sensitivity (0.5 may need adjustment)

#### 3. Invalid Step Counts
**Symptoms**: Step counts not in {8, 16, 32}
**Check**:
- Horizon mapping logic (persistence calculation)
- Forecast length (should be 32 steps)
- Bucket threshold logic (12, 24 boundaries)

### Diagnostic Commands
```bash
# Check TimesFM service health
curl http://localhost:5555/timesfm/health

# Check recent horizon advice
curl http://localhost:5555/agents/kloutbot/horizon-advice

# Monitor fallback rate
python3.10 -m pytest tests/test_kloutbot_timesfm_horizon.py -v
```

## Related Documents

- [ADR 003: Kloutbot Horizon Bucket Policy](./adr_kloutbot_horizon_buckets.md)
- [Kloutbot Compiler & Horizon Contract](./kloutbot_compiler_and_horizon_contract.md)
- [TimesFM Service Overview](./timesfm_service_overview.md)
- [A2A Compatibility Guide](./a2a_consumer_mapping_guide.md)

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-09 | Initial documentation | Goose #3 |
| 1.1 | 2026-04-09 | Added troubleshooting section | Goose #3 |

---

*Last Updated: 2026-04-09*  
*Maintained by: Kloutbot Team*