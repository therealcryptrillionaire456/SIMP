# QuantumArb Integration Contract

## Overview

This document defines the integration contract between QuantumArb and the SIMP A2A system. QuantumArb is an arbitrage detection agent that identifies cross-exchange and statistical arbitrage opportunities. This contract ensures stable integration with:

1. **A2A Core** - Standardized decision summaries
2. **FinancialOps** - Safety evaluation and risk management
3. **KashClaw** - Multi-venue execution mapping
4. **Dashboard** - Real-time visualization

## Version

**Contract Version:** 1.0.0  
**Compatible With:** SIMP A2A Core v0.7.0  
**Last Updated:** 2024-04-09

## Data Flow

```
BullBear Signal → QuantumArb Agent → Decision Summary → A2A Mapping → AgentDecisionSummary
                                      ↓
                                 JSONL Log File
```

## QuantumArb Decision Summary Format

QuantumArb logs decisions in the following JSONL format:

```json
{
  "timestamp": "2024-04-09T12:34:56.789Z",
  "intent_id": "test-a2a-1",
  "source_agent": "bullbear_predictor",
  "asset_pair": "BTC-USD",
  "side": "BULL",
  "decision": "NO_OPPORTUNITY",
  "arb_type": "statistical",
  "dry_run": true,
  "confidence": 0.4,
  "timesfm_used": true,
  "timesfm_rationale": "Forecast available",
  "rationale_preview": "Test rationale...",
  "venue_a": "coinbase",
  "venue_b": "kraken",
  "estimated_spread_bps": 12.5
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | Yes | ISO 8601 UTC timestamp |
| `intent_id` | string | Yes | Unique identifier for traceability |
| `source_agent` | string | Yes | Source of the arbitrage signal |
| `asset_pair` | string | Yes | Trading instrument (e.g., "BTC-USD") |
| `side` | string | Yes | `BULL` \| `BEAR` \| `NOTRADE` |
| `decision` | string | Yes | Uppercase decision (e.g., "EXECUTE") |
| `arb_type` | string | Yes | `statistical` \| `cross_venue` |
| `dry_run` | boolean | Yes | Safety flag (always `true` in scaffold) |
| `confidence` | float | Yes | Confidence score 0.0-1.0 |
| `timesfm_used` | boolean | Yes | Whether TimesFM was consulted |
| `timesfm_rationale` | string | No | TimesFM-specific insight |
| `rationale_preview` | string | Yes | Abbreviated rationale (≤200 chars) |
| `venue_a` | string | No | First exchange venue |
| `venue_b` | string | No | Second exchange venue |
| `estimated_spread_bps` | float | No | Estimated spread in basis points |

## Mapping to AgentDecisionSummary

The `QuantumArbIntegrationContract.map_to_agent_decision_summary()` method converts QuantumArb summaries to the standard A2A format:

### Side Mapping

| QuantumArb Side | AgentDecisionSummary Side |
|-----------------|---------------------------|
| `BULL` | `buy` |
| `BEAR` | `sell` |
| `NOTRADE` | `hold` |

### Volatility Posture

Based on TimesFM usage and confidence:
- `timesfm_used = True` + `confidence > 0.7` → `"conservative"`
- `timesfm_used = True` + `confidence < 0.3` → `"aggressive"`
- Otherwise → `"neutral"`

### Default Values

Since QuantumArb doesn't specify trade quantities:
- `quantity`: 0.0 (default, should be overridden by execution layer)
- `units`: "USD" (default)
- `horizon_days`: 1 (intraday arbitrage)

### Example Mapping

**Input (QuantumArb):**
```json
{
  "timestamp": "2024-04-09T12:34:56.789Z",
  "intent_id": "test-001",
  "source_agent": "bullbear_predictor",
  "asset_pair": "ETH-USD",
  "side": "BULL",
  "decision": "EXECUTE",
  "arb_type": "cross_venue",
  "dry_run": true,
  "confidence": 0.75,
  "timesfm_used": true,
  "timesfm_rationale": "Low volatility forecast",
  "rationale_preview": "2.1% spread detected between Coinbase and Kraken",
  "venue_a": "coinbase",
  "venue_b": "kraken",
  "estimated_spread_bps": 210
}
```

**Output (AgentDecisionSummary):**
```json
{
  "agent_name": "quantumarb",
  "instrument": "ETH-USD",
  "side": "buy",
  "quantity": 0.0,
  "units": "USD",
  "confidence": 0.75,
  "horizon_days": 1,
  "volatility_posture": "conservative",
  "timesfm_used": true,
  "rationale": "2.1% spread detected between Coinbase and Kraken",
  "timestamp": "2024-04-09T12:34:56.789Z",
  "x_quantumarb": {
    "intent_id": "test-001",
    "source_agent": "bullbear_predictor",
    "decision": "EXECUTE",
    "arb_type": "cross_venue",
    "dry_run": true,
    "timesfm_rationale": "Low volatility forecast",
    "venue_a": "coinbase",
    "venue_b": "kraken",
    "estimated_spread_bps": 210
  }
}
```

## Safety Parameters

QuantumArb operations are governed by these safety parameters:

```python
{
    "max_confidence_threshold": 0.8,      # Block trades above this confidence
    "min_confidence_threshold": 0.2,      # Block trades below this confidence
    "required_timesfm_for_live": True,    # TimesFM required for live trades
    "max_daily_trades": 10,               # Maximum trades per day
    "position_size_limit_usd": 1000.0,    # Maximum position size
    "allowed_arb_types": ["statistical", "cross_venue"],
    "blocked_venues": [],                 # Blocked exchange venues
}
```

## Integration Points

### 1. A2A Core Integration
```python
from simp.organs.quantumarb import CONTRACT

# Map QuantumArb summary to AgentDecisionSummary
quantumarb_summary = {...}  # From JSONL log
agent_decision = CONTRACT.map_to_agent_decision_summary(quantumarb_summary)
```

### 2. FinancialOps Safety Check
```python
# FinancialOps should use these safety parameters
safety_params = CONTRACT.get_safety_parameters()

# Validate QuantumArb summary before processing
is_valid = CONTRACT.validate_quantumarb_summary(quantumarb_summary)
```

### 3. KashClaw Execution Mapping
KashClaw should:
1. Read QuantumArb decision summaries from JSONL logs
2. Map to AgentDecisionSummary using the contract
3. Determine execution parameters:
   - For `cross_venue` arb: execute on both venues
   - For `statistical` arb: time-based execution
   - Quantity determination: Based on spread size and available capital

### 4. Dashboard Visualization
Dashboard should display:
- Real-time arbitrage opportunities
- Confidence scores and TimesFM usage
- Safety status (dry_run vs live)
- Historical performance metrics

## Validation Rules

1. **Timestamp**: Must be valid ISO 8601 format
2. **Confidence**: Must be between 0.0 and 1.0 inclusive
3. **Side**: Must be one of `BULL`, `BEAR`, `NOTRADE`
4. **Decision**: Must be uppercase string
5. **Arb Type**: Must be lowercase `statistical` or `cross_venue`
6. **Required Fields**: All required fields must be present

## Error Handling

### Invalid Summary
If a QuantumArb summary fails validation:
1. Log the error with full context
2. Do not process the decision
3. Increment error counter for monitoring
4. Alert operators if error rate exceeds threshold

### Missing Fields
If optional fields are missing:
1. Use default values where appropriate
2. Log warning for monitoring
3. Continue processing

## Monitoring and Alerting

### Key Metrics
- Decision summary validation success rate
- Average confidence score
- TimesFM consultation rate
- Cross-venue vs statistical arbitrage ratio
- Estimated spread distribution

### Alert Thresholds
- **Warning**: >5% validation failures in 1 hour
- **Critical**: >20% validation failures in 1 hour
- **Warning**: Average confidence <0.3 for 1 hour
- **Critical**: No decisions logged for 2 hours

## Version Compatibility

### Backward Compatibility
- New optional fields may be added
- Existing required fields cannot be removed
- Field types cannot change

### Forward Compatibility
Consumers should:
- Ignore unknown fields in `x_quantumarb` extension
- Handle missing optional fields gracefully
- Validate all required fields before processing

## Related Documents

1. [A2A Core Schema](../financial/a2a_schema.py)
2. [QuantumArb Agent](../../agents/quantumarb_agent.py)
3. [FinancialOps Safety](../financial/a2a_safety.py)
4. [KashClaw Execution Mapping](./kashclaw_execution_mapping.md)

## Change Log

### v1.0.0 (2024-04-09)
- Initial integration contract
- Defined QuantumArb decision summary format
- Created mapping to AgentDecisionSummary
- Established safety parameters
- Added validation rules