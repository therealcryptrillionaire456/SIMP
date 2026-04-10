# KashClaw TimesFM Sizing Integration

## Overview

The KashClaw agent integrates TimesFM volatility forecasting to provide pre-trade sizing advice. This feature helps adjust trade quantities and slippage tolerances based on forecasted volatility, while maintaining a strict safety contract: **TimesFM sizing advice never blocks trade execution**.

## Safety Contract

1. **Non-blocking**: TimesFM sizing advice is advisory only. Trade execution proceeds regardless of TimesFM availability or errors.
2. **Fail-safe**: Any TimesFM error results in fallback to original trade parameters.
3. **Bounds-checked**: All adjustments are within safe, predefined limits.
4. **Audit-logged**: Every sizing decision includes a rationale for operator review.

## Integration Flow

```python
# Simplified flow in KashClawSimpAgent.handle_trade()
async def handle_trade(self, params):
    # 1. Get TimesFM sizing advice (advisory, never blocks)
    sizing_advice = await self._get_pre_trade_sizing_advice(
        asset_pair=params["asset_pair"],
        organ_id=params["organ_id"],
        quantity=params["quantity"],
        slippage_tolerance=params["slippage_tolerance"],
    )
    
    # 2. Apply adjustments if TimesFM was applied
    if sizing_advice["timesfm_applied"]:
        params["quantity"] = sizing_advice["adjusted_quantity"]
        params["slippage_tolerance"] = sizing_advice["adjusted_slippage_tolerance"]
    
    # 3. Always include rationale in params (for logging)
    params["timesfm_sizing_rationale"] = sizing_advice["timesfm_rationale"]
    
    # 4. Execute trade (proceeds regardless of TimesFM outcome)
    result = await organ.execute(params, intent_id)
    
    # 5. Include TimesFM metadata in response
    return {
        "status": "success",
        "execution": result.to_dict(),
        "timesfm_sizing": {
            "applied": sizing_advice["timesfm_applied"],
            "rationale": sizing_advice["timesfm_rationale"],
            "risk_posture": sizing_advice.get("risk_posture", "neutral"),
        },
        "risk_posture": sizing_advice.get("risk_posture", "neutral"),
    }
```

## Sizing Decision Logic

### High Volatility Scenario
When forecasted volatility exceeds 1.5× current volatility:

```python
if forecast_vol > current_vol * 1.5:
    # Reduce quantity by 20% (max reduction)
    adjusted_qty = max(quantity * 0.80, 0.0)
    
    # Widen slippage tolerance by 25% (max 5% total)
    adjusted_slip = min(max(slippage_tolerance, 0.0) * 1.25, 0.05)
    
    rationale = (
        f"TimesFM volatility rising: forecast_vol={forecast_vol:.4f} "
        f"> 1.5x current={current_vol:.4f}. "
        f"Reduced qty by 20%, slippage widened to {adjusted_slip:.4f}."
    )
    risk_posture = "conservative"
```

### Normal Volatility Scenario
When forecasted volatility is stable:

```python
else:
    # No adjustments needed
    rationale = (
        f"TimesFM: stable volatility forecast "
        f"(forecast_vol={forecast_vol:.4f}). Sizing unchanged."
    )
    risk_posture = "neutral"
```

## Safety Bounds

| Parameter | Constraint | Purpose |
|-----------|------------|---------|
| Quantity | `max(quantity, 0.0)` | Prevent negative quantities |
| Slippage Tolerance | `max(slippage_tolerance, 0.0)` | Prevent negative slippage |
| Quantity Reduction | ≤ 20% | Limit position size reduction |
| Slippage Increase | ≤ 25%, max 5% total | Prevent excessive slippage allowance |
| Forecast Values | Filter NaN/inf | Ensure numerical stability |

## Configuration Flags

### Environment Variables
```bash
# Enable/disable TimesFM service
SIMP_TIMESFM_ENABLED=true

# Shadow mode (compute forecasts but don't allow agents to act)
SIMP_TIMESFM_SHADOW_MODE=false

# Cache settings
SIMP_TIMESFM_CACHE_MAX_SERIES=100
SIMP_TIMESFM_CACHE_TTL_SECONDS=300
```

### Policy Engine Settings
```python
# Minimum observations required
MIN_OBSERVATIONS = 16

# Agent assessment thresholds
Q1_UTILITY_THRESHOLD = 3  # Minimum utility score
Q3_SHADOW_REQUIRED = True  # Require shadow mode confirmation
Q8_NONBLOCKING_REQUIRED = True  # Require non-blocking contract
```

## Examples

### Example 1: High Volatility Adjustment
**Input Trade:**
```json
{
  "organ_id": "spot:001",
  "asset_pair": "SOL/USDC",
  "side": "BUY",
  "quantity": 10.0,
  "price": 150.0,
  "slippage_tolerance": 0.02
}
```

**TimesFM Analysis:**
- Current volatility: 0.02
- Forecast volatility: 0.035 (1.75× current)
- Decision: High volatility detected

**Adjusted Trade:**
```json
{
  "quantity": 8.0,  # Reduced by 20%
  "slippage_tolerance": 0.025,  # Widened by 25%
  "timesfm_sizing_rationale": "TimesFM volatility rising: forecast_vol=0.0350 > 1.5x current=0.0200. Reduced qty by 20%, slippage widened to 0.0250."
}
```

### Example 2: Shadow Mode Operation
**Configuration:** `SIMP_TIMESFM_SHADOW_MODE=true`

**Trade Execution:**
- TimesFM computes forecast
- `available=False` in response
- Original trade parameters unchanged
- Rationale: "TimesFM: shadow mode active — sizing unchanged"
- Forecast logged for offline evaluation

### Example 3: Policy Denied
**Scenario:** Agent lacks shadow mode confirmation

**Trade Execution:**
- Policy engine denies TimesFM access
- Original trade parameters unchanged
- Rationale: "TimesFM policy denied: Q3_SHADOW: agent has not been confirmed through shadow mode evaluation"
- Risk posture: "conservative"

### Example 4: Insufficient History
**Scenario:** Only 10 volatility observations (16 required)

**Trade Execution:**
- TimesFM returns early
- Original trade parameters unchanged
- Rationale: "TimesFM: insufficient history (10/16 observations)"
- Risk posture: "conservative"

### Example 5: TimesFM Service Error
**Scenario:** TimesFM service unavailable

**Trade Execution:**
- Exception caught in try/except
- Original trade parameters unchanged
- Rationale: "TimesFM sizing advice error: Connection refused"
- Risk posture: "conservative"
- Trade proceeds normally

## Error Handling

All errors are handled gracefully:

1. **TimesFM Service Unavailable**: Falls back to original parameters
2. **Policy Denial**: Falls back to original parameters with conservative posture
3. **Insufficient Data**: Falls back to original parameters with conservative posture
4. **Invalid Forecast Values**: Filters NaN/inf, falls back if no valid values
5. **Any Exception**: Caught and logged, trade proceeds

## Monitoring & Audit

### Response Fields
Every trade response includes TimesFM metadata:

```json
{
  "timesfm_sizing": {
    "applied": true,
    "rationale": "TimesFM volatility rising...",
    "risk_posture": "conservative"
  },
  "risk_posture": "conservative"
}
```

### Audit Logging
- All forecast requests logged to `data/timesfm_audit.jsonl`
- Includes request/response pairs, latency, cache status
- Filterable by agent ID for compliance review

### Risk Posture Tracking
- **conservative**: High volatility, policy denied, insufficient data, or errors
- **neutral**: Stable volatility or shadow mode
- Used for aggregate risk reporting

## Testing

### Test Coverage
```bash
# Run TimesFM sizing tests
python3.10 -m pytest tests/test_kashclaw_timesfm_sizing.py -v

# Test results:
# - test_timesfm_sizing_advice_high_volatility
# - test_timesfm_sizing_advice_normal_volatility
# - test_timesfm_sizing_shadow_mode
# - test_timesfm_sizing_policy_denied
# - test_timesfm_sizing_insufficient_history
# - test_timesfm_sizing_integration_in_trade_execution
# - test_timesfm_sizing_error_handling
# - test_timesfm_sizing_never_blocks_execution
```

### Key Test Assertions
1. TimesFM never blocks trade execution
2. Adjustments stay within safe bounds
3. Rationale included for all outcomes
4. Error handling prevents propagation
5. Shadow mode prevents actual adjustments

## Operator Guidelines

### When to Enable TimesFM Sizing
1. **Production**: After shadow mode validation shows benefit
2. **Testing**: Use shadow mode to collect forecast accuracy data
3. **Development**: Disable to isolate trading logic issues

### Monitoring Recommendations
1. Review `timesfm_sizing.rationale` in trade logs
2. Track `risk_posture` distribution (should be mostly "neutral")
3. Alert on frequent "conservative" postures
4. Validate forecast accuracy against realized volatility

### Troubleshooting
| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| No TimesFM adjustments | Shadow mode enabled | Check `SIMP_TIMESFM_SHADOW_MODE` |
| Policy denials | Agent assessment incomplete | Verify agent Q1/Q3/Q8 scores |
| Insufficient history | New trading pair | Allow 16+ trades to accumulate data |
| Service errors | TimesFM unavailable | Check service health endpoint |

## Related Documentation

- [TimesFM Service Overview](./timesfm_service_overview.md)
- [KloutBot TimesFM Horizon Integration](./kloutbot_timesfm_horizon.md)
- [SIMP FinancialOps Guide](../docs/FINANCIAL_OPS.md)
- [A2A Compatibility Layer](../docs/A2A_DEMO.md)