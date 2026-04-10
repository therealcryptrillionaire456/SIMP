# ADR 003: Kloutbot Horizon Bucket Policy

## Status

**Accepted** - 2026-04-09

## Context

Kloutbot generates trading strategies with varying time horizons based on TimesFM affinity forecasts. The system needs to translate continuous forecast persistence values into discrete horizon buckets for downstream consumption by the QIntentCompiler and A2A agents.

The key problem: How should continuous persistence values (1-32 steps) be mapped to discrete horizon categories that are meaningful for strategy generation and execution?

## Decision

We adopt a fixed three-bucket system with the following mapping:

| Horizon Label | Step Count | Persistence Threshold |
|---------------|------------|----------------------|
| Short         | 8 steps    | < 12 steps           |
| Medium        | 16 steps   | ≥ 12 and < 24 steps  |
| Long          | 32 steps   | ≥ 24 steps           |

Where:
- **Persistence** = number of consecutive forecast steps where affinity > 0.5
- **Step count** = fixed values (8, 16, 32) passed to QIntentCompiler
- **Thresholds** = fixed boundaries (12, 24) for bucket assignment

## Rationale

### Why three buckets?
1. **Cognitive simplicity**: Humans and agents can easily reason about "short", "medium", and "long" horizons
2. **Compiler optimization**: QIntentCompiler can pre-optimize for these specific step counts
3. **A2A compatibility**: Standardized categories simplify agent-to-agent communication
4. **Execution alignment**: Maps cleanly to trading timeframes (intraday, daily, weekly)

### Why these specific step counts?
- **8 steps (short)**: Approximately 1-2 hours for typical data frequencies
- **16 steps (medium)**: Approximately 1 trading day
- **32 steps (long)**: Approximately 1 trading week

### Why these persistence thresholds?
- **12-step boundary**: Clear separation between intraday and multi-day strategies
- **24-step boundary**: Clear separation between daily and weekly strategies
- **0.5 threshold**: Standard statistical significance threshold for binary classification

### Alternatives Considered

1. **Continuous mapping**: Pass exact persistence value to compiler
   - Pros: More precise
   - Cons: Compiler can't pre-optimize, harder for humans to reason about
   - Rejected: Optimization benefits outweigh precision loss

2. **More buckets (5 or 7)**
   - Pros: Finer granularity
   - Cons: Increased complexity, diminishing returns
   - Rejected: Three buckets provide sufficient granularity for trading decisions

3. **Dynamic buckets based on market regime**
   - Pros: Adapts to market conditions
   - Cons: Introduces complexity, harder to debug
   - Rejected: Simplicity and predictability are higher priorities

## Consequences

### Positive
- **Predictable behavior**: Always produces one of three known horizon values
- **Compiler optimization**: QIntentCompiler can cache optimizations for each step count
- **Clear semantics**: Each bucket has well-defined trading implications
- **Testable**: Easy to write comprehensive tests for all boundary cases
- **A2A friendly**: Standardized categories simplify agent communication

### Negative
- **Loss of precision**: Some information lost in bucketization
- **Boundary effects**: Small persistence changes near thresholds can flip buckets
- **Fixed thresholds**: May not adapt to changing market volatility

### Neutral
- **Implementation complexity**: Simple threshold logic required
- **Maintenance**: Thresholds may need adjustment if trading patterns change

## Governance

### Change Control
- Horizon buckets and thresholds are considered **stable API**
- Changes require:
  1. Performance impact analysis
  2. A2A compatibility assessment
  3. Test updates for all boundary cases
  4. Documentation updates

### Monitoring
- Track bucket distribution in production
- Alert if >50% of strategies fall into a single bucket for extended periods
- Monitor boundary cases (persistence near 12 or 24)

### Fallback Behavior
When TimesFM is unavailable:
- Default to **medium horizon (16 steps)**
- Rationale: Conservative default, avoids extreme positions
- Documented in `timesfm_horizon_rationale` field

## Compliance

### Test Coverage
- ✅ All three buckets tested (`test_timesfm_horizon_advice_*_persistence`)
- ✅ Boundary values tested (`test_timesfm_horizon_boundary_values`)
- ✅ Fallback behavior tested (`test_timesfm_horizon_shadow_mode`)
- ✅ Integration tested (`test_timesfm_horizon_integration_in_strategy_generation`)

### A2A Compatibility
- Horizon labels map to standard A2A time horizon categories
- Step counts included in AgentDecisionSummary
- Rationale text provides human-readable explanation

## Related Documents

- [Kloutbot Compiler & Horizon Contract](../kloutbot_compiler_and_horizon_contract.md)
- [TimesFM Integration Guide](../../outputs/timesfm_simp/README.md)
- [A2A AgentDecisionSummary Schema](../../compat/agent_card.py)

## Revision History

| Version | Date | Change | Author |
|---------|------|--------|--------|
| 1.0 | 2026-04-09 | Initial ADR | Kloutbot Team |
| 1.1 | 2026-04-09 | Added governance section | Kloutbot Team |

---

*This ADR will be reviewed annually or when significant changes to trading patterns are observed.*