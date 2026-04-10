# TimesFM Integration Guide for SIMP Agents

## Overview

This document explains how SIMP agents (QuantumArb, KashClaw, Kloutbot) should integrate with the TimesFM forecasting service. It covers safety policies, shadow mode behavior, and implementation patterns.

## Safety Architecture

### Two-Layer Protection
1. **Service-Level Shadow Mode**: `SIMP_TIMESFM_SHADOW_MODE=true` by default
   - Forecasts are computed but marked `available=False`
   - Agents cannot inadvertently act on forecasts
   - Audit logs track all requests

2. **Policy Engine Gate**: Q1-Q8 criteria system
   - Q1: Utility score (≥3 required)
   - Q3: Shadow mode confirmed (True for production agents)
   - Q8: Non-blocking (True for all agents)
   - Minimum series length: 100 observations

### Agent Assessments
Each agent has a policy assessment in `timesfm_policy_engine.py`:

```python
_ASSESSMENTS = {
    "quantumarb": {
        "q1_utility_score": 5,
        "q3_shadow_confirmed": True,  # Tested in shadow mode
        "q8_nonblocking": True,
    },
    "kashclaw": {
        "q1_utility_score": 4,
        "q3_shadow_confirmed": True,
        "q8_nonblocking": True,
    },
    "kloutbot": {
        "q1_utility_score": 4,
        "q3_shadow_confirmed": True,
        "q8_nonblocking": True,
    },
    # New agents start with q3_shadow_confirmed=False
    "new_agent": {
        "q1_utility_score": 2,
        "q3_shadow_confirmed": False,  # Must be tested first
        "q8_nonblocking": True,
    }
}
```

## Integration Pattern

### Step 1: Create Agent Context
```python
from simp.integrations.timesfm_policy_engine import (
    AgentContext,
    PolicyDecision,
    PolicyEngine,
    make_agent_context_for,
)

# Use helper function for standard agents
context = make_agent_context_for(
    agent_id="quantumarb",
    series_id="btc:usd:coinbase_vs_binance:spread_bps",
    series_length=len(historical_data),
    requesting_handler="handle_trade",  # or "analyze_market", "generate_signal"
)
```

### Step 2: Evaluate Policy
```python
engine = PolicyEngine()
policy_decision = engine.evaluate(context)

if not policy_decision.approved:
    # Handle denial gracefully
    logger.warning(f"Policy denied: {policy_decision.reasons}")
    return None  # or fallback logic
```

### Step 3: Request Forecast
```python
from simp.integrations.timesfm_service import (
    ForecastRequest,
    ForecastResponse,
    get_timesfm_service,
)

# Get service instance
service = get_timesfm_service()

# Create forecast request
request = ForecastRequest(
    series_id=context.series_id,
    values=historical_data,  # List[float], most recent last
    requesting_agent=context.agent_id,
    horizon=64,  # Default, can be 7, 30, 64
    frequency="D",  # "D" for daily, "H" for hourly, etc.
    context_metadata={
        "exchange": "coinbase",
        "pair": "BTC-USD",
        "strategy": "arbitrage"
    }
)

# Get forecast (async)
response = await service.forecast(request)
```

### Step 4: Handle Response
```python
# Check if forecast is available (not shadow mode)
if response.available:
    # Safe to use forecast
    point_forecast = response.point_forecast
    lower_bound = response.lower_bound
    upper_bound = response.upper_bound
    
    # Use in decision logic
    expected_return = point_forecast[0]  # Next period
    confidence_width = upper_bound[0] - lower_bound[0]
else:
    # Shadow mode active - forecast computed but not for use
    # Log for audit, but don't act
    logger.info(f"Shadow mode forecast: {response.shadow_mode}")
    # Use fallback logic or skip
```

## Agent-Specific Examples

### QuantumArb (Arbitrage Detection)
```python
async def detect_arbitrage_opportunity(self, spread_series: List[float]):
    """Use TimesFM to forecast spread convergence."""
    context = make_agent_context_for(
        agent_id="quantumarb",
        series_id=f"spread:{self.exchange_a}:{self.exchange_b}",
        series_length=len(spread_series),
        requesting_handler="detect_arbitrage",
    )
    
    if not PolicyEngine().evaluate(context).approved:
        return None  # Policy gate
    
    request = ForecastRequest(
        series_id=context.series_id,
        values=spread_series,
        requesting_agent="quantumarb",
        horizon=7,  # 7-step forecast for short-term arb
        frequency="5min",  # 5-minute intervals
        context_metadata={
            "exchange_pair": f"{self.exchange_a}-{self.exchange_b}",
            "asset": self.asset,
            "window_minutes": 35  # 7 * 5min
        }
    )
    
    response = await get_timesfm_service().forecast(request)
    
    if response.available:
        # Forecast spread convergence
        next_spread = response.point_forecast[0]
        if abs(next_spread) < self.threshold:
            return self._create_arb_signal(next_spread)
    
    return None
```

### KashClaw (Technical Analysis)
```python
async def generate_technical_signal(self, price_series: List[float]):
    """Forecast price movement for trading signals."""
    context = make_agent_context_for(
        agent_id="kashclaw",
        series_id=f"price:{self.symbol}:{self.timeframe}",
        series_length=len(price_series),
        requesting_handler="generate_signal",
    )
    
    policy = PolicyEngine().evaluate(context)
    if not policy.approved:
        logger.warning(f"KashClaw policy denied: {policy.reasons}")
        return self._fallback_technical_analysis(price_series)
    
    request = ForecastRequest(
        series_id=context.series_id,
        values=price_series,
        requesting_agent="kashclaw",
        horizon=30,  # 30-period forecast
        frequency=self.timeframe,  # "1H", "4H", "1D"
        context_metadata={
            "symbol": self.symbol,
            "indicator": "price_forecast",
            "strategy": self.strategy_name
        }
    )
    
    response = await get_timesfm_service().forecast(request)
    
    if response.available:
        # Combine with other indicators
        forecast_trend = self._calculate_trend(response.point_forecast)
        confidence = response.upper_bound[0] - response.lower_bound[0]
        return self._create_trading_signal(forecast_trend, confidence)
    
    # Shadow mode - use traditional TA
    return self._traditional_technical_analysis(price_series)
```

### Kloutbot (Sentiment & Narrative)
```python
async def forecast_sentiment_trend(self, sentiment_scores: List[float]):
    """Forecast social sentiment trends."""
    context = make_agent_context_for(
        agent_id="kloutbot",
        series_id=f"sentiment:{self.topic}:{self.platform}",
        series_length=len(sentiment_scores),
        requesting_handler="forecast_narrative",
    )
    
    # Kloutbot always approved (q3_shadow_confirmed=True)
    request = ForecastRequest(
        series_id=context.series_id,
        values=sentiment_scores,
        requesting_agent="kloutbot",
        horizon=64,  # Long horizon for narrative forecasting
        frequency="D",  # Daily sentiment scores
        context_metadata={
            "topic": self.topic,
            "platform": self.platform,
            "horizon_days": 64
        }
    )
    
    response = await get_timesfm_service().forecast(request)
    
    # Kloutbot can use forecasts even in shadow mode for analysis
    # (doesn't execute trades, only produces insights)
    trend = self._analyze_sentiment_trend(response.point_forecast)
    confidence = self._calculate_forecast_confidence(response)
    
    return {
        "trend": trend,
        "confidence": confidence,
        "shadow_mode": response.shadow_mode,
        "available": response.available
    }
```

## Safety Guarantees

### 1. Default Deny
- New agents: `q3_shadow_confirmed=False`
- Must be tested in shadow mode first
- Policy engine blocks live forecasts

### 2. Shadow Mode Protection
- `SIMP_TIMESFM_SHADOW_MODE=true` by default
- Forecasts marked `available=False`
- Agents must explicitly check `response.available`
- Audit logs track all shadow mode requests

### 3. Audit Trail
- All requests logged to `ForecastAuditLog`
- Includes agent ID, series ID, timestamp
- Shadow mode samples counted in health report
- Review via `service.health()["shadow_mode_samples"]`

### 4. Graceful Degradation
- Model import errors → returns unavailable response
- Policy denial → clear reasons in `policy_decision.reasons`
- Cache fallback for repeated requests
- Timeout protection (async)

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SIMP_TIMESFM_ENABLED` | `false` | Master switch for TimesFM |
| `SIMP_TIMESFM_SHADOW_MODE` | `true` | Shadow mode (safety) |
| `SIMP_TIMESFM_CACHE_MAX_SIZE` | `1000` | Cache entries |
| `SIMP_TIMESFM_CACHE_TTL_SECONDS` | `300` | Cache TTL |

## Testing New Agents

### Phase 1: Shadow Testing
1. Agent runs with `q3_shadow_confirmed=False`
2. All forecasts return `available=False`
3. Audit logs verify agent behavior
4. No live actions based on forecasts

### Phase 2: Policy Assessment
1. Review shadow mode audit logs
2. Verify agent handles `available=False` correctly
3. Check for proper error handling
4. Update assessment: `q3_shadow_confirmed=True`

### Phase 3: Live Mode
1. Set `SIMP_TIMESFM_SHADOW_MODE=false`
2. Agent receives `available=True` forecasts
3. Monitor initial live forecasts
4. Rollback available if issues

## Monitoring & Debugging

### Health Endpoint
```python
service = get_timesfm_service()
health = service.health()

# Key metrics:
print(f"Shadow mode: {health['shadow_mode']}")
print(f"Shadow samples: {health['shadow_mode_samples']}")
print(f"Cache size: {health['cache_size']}")
print(f"Policy rules: {health['policy_rules']}")
```

### Audit Log Access
```python
service = get_timesfm_service()
recent = service._audit_log.recent(50)  # Last 50 requests
agent_requests = service._audit_log.for_agent("quantumarb", 20)
```

### Common Issues

1. **Policy Denial**
   - Check agent assessment in `timesfm_policy_engine.py`
   - Verify `q3_shadow_confirmed=True`
   - Check `q1_utility_score ≥ 3`

2. **Shadow Mode Active**
   - Check `SIMP_TIMESFM_SHADOW_MODE` environment variable
   - Verify agent checks `response.available`
   - Review audit logs for shadow samples

3. **Model Errors**
   - TimesFM package installed? (`pip install timesfm`)
   - GPU available for acceleration?
   - Fallback to traditional methods

## Migration Checklist

For agents migrating to use TimesFM:

- [ ] Add policy evaluation before forecast requests
- [ ] Handle `response.available` check
- [ ] Implement fallback for shadow mode
- [ ] Add context metadata for audit trails
- [ ] Test in shadow mode first
- [ ] Update agent assessment after testing
- [ ] Monitor initial live forecasts

## Related Documentation

- [TimesFM Service Overview](timesfm_service_overview.md) - Technical service details
- [Policy Engine Source](simp/integrations/timesfm_policy_engine.py) - Q1-Q8 criteria
- [Integration Tests](tests/test_timesfm_integration.py) - Example patterns
- [Agent Tests](tests/test_*_timesfm_*.py) - Agent-specific examples