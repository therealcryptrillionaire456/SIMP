# TimesFM Forecasting Service — SIMP Integration

## Overview

The TimesFM Service provides a shared, policy-gated forecasting capability to all SIMP agents. It wraps Google's TimesFM time-series forecasting model with safety controls, audit logging, and feature-flag driven behavior to prevent agents from inadvertently acting on forecasts during development and shadow testing.

## Service API

### Core Classes

#### `ForecastRequest`
```python
@dataclass
class ForecastRequest:
    series_id: str                    # Unique stable identifier (cache key)
    values: List[float]               # Historical observations (most-recent last)
    requesting_agent: str             # Agent ID issuing request
    horizon: int = 64                 # Steps ahead to forecast
    frequency: int = 0                # TimesFM frequency hint
    context_metadata: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

#### `ForecastResponse`
```python
@dataclass
class ForecastResponse:
    available: bool                   # True when forecasts can be used
    shadow_mode: bool                 # Whether response was shadow-mode suppressed
    point_forecast: List[float]       # Predicted values (empty if unavailable)
    lower_bound: List[float]          # Lower confidence interval
    upper_bound: List[float]          # Upper confidence interval
    horizon: int                      # Steps forecasted
    series_id: str                    # Echo of request series_id
    request_id: str                   # Echo of request request_id
    cached: bool = False              # True if from cache
    latency_ms: float = 0.0           # Wall-clock time
    error: Optional[str] = None       # Non-None if forecasting failed
```

### Primary Interface

#### `TimesFMService`
```python
class TimesFMService:
    async def forecast(self, request: ForecastRequest) -> ForecastResponse
    def health(self) -> Dict[str, Any]
```

#### Singleton Accessors
```python
async def get_timesfm_service() -> TimesFMService  # Async-safe lazy init
def get_timesfm_service_sync() -> TimesFMService   # Synchronous access
```

## Feature Flags and Defaults

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SIMP_TIMESFM_ENABLED` | bool | `false` | Master switch for TimesFM service |
| `SIMP_TIMESFM_SHADOW_MODE` | bool | `true` | Compute forecasts but suppress in returns |
| `SIMP_TIMESFM_CHECKPOINT` | string | `"google/timesfm-2.0-500m-pytorch"` | HuggingFace checkpoint |
| `SIMP_TIMESFM_CONTEXT_LEN` | int | `512` | Context length for model |
| `SIMP_TIMESFM_HORIZON` | int | `64` | Default forecast horizon steps |

### Runtime Behavior Matrix

| Enabled | Shadow Mode | Result |
|---------|-------------|--------|
| `false` | any | `available=False`, immediate return |
| `true` | `true` | Forecast computed, logged, cached, but `available=False` |
| `true` | `false` | Forecast computed, `available=True` with real data |

## Expected Usage Pattern for Agents

### 1. Basic Usage
```python
from simp.integrations.timesfm_service import get_timesfm_service, ForecastRequest

async def make_forecast():
    svc = await get_timesfm_service()
    req = ForecastRequest(
        series_id="SOL/USDC:spread",
        values=[0.12, 0.14, 0.11, 0.13, 0.15],
        requesting_agent="quantumarb",
        horizon=32,
    )
    resp = await svc.forecast(req)
    
    if resp.available:
        # Use forecast for decision making
        trend = resp.point_forecast[-1] - resp.point_forecast[0]
        return trend > 0
    else:
        # Fallback to non-forecast logic
        return False
```

### 2. With Policy Engine (Recommended)
```python
from simp.integrations.timesfm_policy_engine import (
    PolicyEngine, make_agent_context_for
)

async def forecast_with_policy():
    # Create context for policy evaluation
    ctx = make_agent_context_for(
        agent_id="quantumarb",
        series_id="SOL/USDC:spread",
        series_length=len(values),
        requesting_handler="arb_detection_loop",
    )
    
    # Evaluate policy
    engine = PolicyEngine()
    decision = engine.evaluate(ctx)
    
    if decision.approved:
        svc = await get_timesfm_service()
        req = ForecastRequest(...)
        resp = await svc.forecast(req)
        return resp
    else:
        log.warning(f"Policy denied: {decision.reason}")
        return ForecastResponse.unavailable(...)
```

### 3. Cache-Aware Usage
```python
async def forecast_with_cache_awareness():
    svc = await get_timesfm_service()
    
    # Check health for cache status
    health = svc.health()
    if health["cache_size"] > 50:
        log.info("TimesFM cache is warm")
    
    # Make request (caching handled automatically)
    resp = await svc.forecast(req)
    
    if resp.cached:
        log.debug(f"Cache hit for {req.series_id}")
```

## Failure and Fallback Behavior

### Error Handling Philosophy
The service **never raises exceptions** — all errors are captured in `ForecastResponse.error`.

### Failure Scenarios

| Scenario | Response | Audit Log |
|----------|----------|-----------|
| Service disabled (`SIMP_TIMESFM_ENABLED=false`) | `available=False`, `error="TimesFM disabled..."` | Recorded with reason |
| Model loading fails | `available=False`, `error="Forecast error: ..."` | Recorded with exception |
| Forecast computation fails | `available=False`, `error="Forecast error: ..."` | Recorded with exception |
| Shadow mode active | `available=False`, `shadow_mode=True` | Recorded normally |
| Cache hit | `available=!shadow_mode`, `cached=True` | Recorded with `cached=True` |

### Fallback Strategies for Agents

1. **Default Values Fallback**
```python
def get_forecast_or_default(resp, default_trend=0.0):
    if resp.available and resp.point_forecast:
        return resp.point_forecast[-1] - resp.point_forecast[0]
    return default_trend
```

2. **Historical Average Fallback**
```python
def fallback_to_historical(values, window=5):
    recent = values[-window:] if len(values) >= window else values
    return sum(recent) / len(recent)
```

3. **Circuit Breaker Pattern**
```python
class ForecastCircuitBreaker:
    def __init__(self, max_failures=3):
        self.failures = 0
        
    async def safe_forecast(self, svc, req):
        try:
            resp = await svc.forecast(req)
            if resp.error:
                self.failures += 1
            else:
                self.failures = 0
            return resp
        except Exception:
            self.failures += 1
            raise
```

## Policy Engine Requirements

### Assessment Criteria
Agents must satisfy these criteria (from TimesFM Agent Assessment Framework):

1. **Q1 Utility Score** ≥ 3 (1=none, 5=critical)
2. **Q3 Shadow Confirmed** = True (tested in shadow mode)
3. **Q8 Non-blocking** = True (forecast doesn't stall agent)
4. **Minimum Series Length** ≥ 16 observations

### Pre-Assessed Agents
```python
_AGENT_ASSESSMENTS = {
    "quantumarb": {"q1": 5, "q3": True, "q8": True},
    "kashclaw": {"q1": 4, "q3": True, "q8": True},
    "kloutbot": {"q1": 4, "q3": True, "q8": True},
    "bullbear_predictor": {"q1": 5, "q3": True, "q8": True},
    "projectx_native": {"q1": 3, "q3": False, "q8": True},
    "claude_cowork": {"q1": 2, "q3": False, "q8": True},
    "financial_ops": {"q1": 3, "q3": False, "q8": True},
}
```

## Safety and Clarity Improvements (Implemented)

### 1. Request Validation (Implemented)
```python
# Added to ForecastRequest
def validate(self) -> List[str]:
    errors = []
    if len(self.values) < 16:
        errors.append("Need ≥16 observations for meaningful forecast")
    if self.horizon > 128:
        errors.append(f"Horizon {self.horizon} exceeds safe limit (128)")
    if not self.series_id or ":" not in self.series_id:
        errors.append("series_id should follow 'domain:metric' format")
    if not self.requesting_agent:
        errors.append("requesting_agent must be non-empty")
    # Also validates that all values are finite numbers
    return errors
```

### 2. Enhanced Health Reporting (Implemented)
```python
# Enhanced TimesFMService.health()
def health(self) -> Dict[str, Any]:
    return {
        # Service identity
        "version": "1.0.0",
        # Basic status
        "enabled": self._enabled,
        "shadow_mode": self._shadow_mode,
        "model_loaded": self._model is not None,
        "checkpoint": self._checkpoint,
        "context_len": self._context_len,
        "default_horizon": self._default_horizon,
        # Operational state
        "cache_size": self.cache.size,
        "audit_records": len(self.audit._log),
        # Enhanced metrics
        "cache_hit_rate": round(cache_hit_rate, 3),
        "avg_latency_ms": round(avg_latency_ms, 1),
        "error_rate": round(error_rate, 3),
        "shadow_mode_samples": self._shadow_mode_samples,
        "total_requests": self._total_requests,
        "cache_hits": self._cache_hits,
        "errors": self._errors,
        # Policy and validation rules
        "policy_rules": {
            "min_observations": 16,
            "max_horizon": 128,
            "series_id_format": "domain:metric",
            "q1_utility_threshold": 3,
            "q3_shadow_required": True,
            "q8_nonblocking_required": True,
        },
        # Debugging
        "last_error": last_error,  # Extracted from audit log
    }
```

#### Policy Engine Health
```python
# PolicyEngine.health()
def health(self) -> Dict[str, Any]:
    return {
        "version": "1.0.0",
        "min_observations": self.MIN_OBSERVATIONS,  # 16
        "q1_utility_threshold": Q1_UTILITY_THRESHOLD,  # 3
        "q3_shadow_required": Q3_SHADOW_REQUIRED,  # True
        "q8_nonblocking_required": Q8_NONBLOCKING_REQUIRED,  # True
        "policy_description": (
            "Evaluates agent context against Q1 (utility ≥ 3), "
            "Q3 (shadow mode confirmed), Q8 (non-blocking), "
            "and minimum series length (≥ 16 observations)"
        ),
    }
```

### 3. Enhanced Audit Logging (Implemented)
Audit log entries now include `validation_errors` field containing any validation errors from the request.

### 4. Runtime Environment Configuration (Implemented)
Environment variables are now read at service instantiation time (in `__init__`) rather than module import time, allowing runtime configuration changes.

### 5. Validation Integration in Forecast Flow (Implemented)
Request validation is now automatically called in the `forecast()` method before attempting to load the model or compute forecasts:

```python
async def forecast(self, request: ForecastRequest) -> ForecastResponse:
    # ... cache check ...
    
    # Validate request before loading model
    validation_errors = request.validate()
    if validation_errors:
        resp = ForecastResponse.unavailable(
            request_id=request.request_id,
            series_id=request.series_id,
            horizon=request.horizon,
            reason=f"Validation failed: {', '.join(validation_errors)}",
            shadow_mode=self._shadow_mode,
        )
        # Track error and latency
        async with self._stats_lock:
            self._errors += 1
            self._total_latency_ms += resp.latency_ms
        return resp
    
    # ... proceed with forecast if validation passes ...
```

This ensures invalid requests fail fast without consuming model loading or computation resources.

## Future Enhancements (Proposed)

### 1. Rate Limiting Per Agent
```python
# Proposed addition to TimesFMService
class TimesFMService:
    def __init__(self):
        # ... existing init
        self._rate_limiter = RateLimiter(
            requests_per_minute=60,  # 1 forecast/second per agent
            burst_size=10,
        )
    
    async def forecast(self, request: ForecastRequest):
        if not self._rate_limiter.allow(request.requesting_agent):
            return ForecastResponse.unavailable(
                request_id=request.request_id,
                series_id=request.series_id,
                horizon=request.horizon,
                reason="Rate limit exceeded",
                shadow_mode=self._shadow_mode,
            )
        # ... proceed with forecast
```

### 2. Forecast Quality Metrics
```python
# Proposed addition to ForecastResponse
@dataclass
class ForecastResponse:
    # ... existing fields
    confidence_score: float = 0.0  # 0.0-1.0 quality estimate
    seasonality_detected: bool = False
    trend_strength: float = 0.0  # -1.0 to 1.0
    
    @classmethod
    def unavailable(cls, ...):
        resp = cls(...)
        resp.confidence_score = 0.0
        return resp
```

### 3. Clearer Shadow Mode Logging
```python
# Proposed enhancement to shadow mode logging
if self._shadow_mode:
    log.info(
        "[SHADOW] TimesFM forecast suppressed | "
        "series=%s agent=%s horizon=%d values=%d "
        "point_forecast_range=[%.3f, %.3f]",
        request.series_id,
        request.requesting_agent,
        request.horizon,
        len(request.values),
        min(point) if point else 0.0,
        max(point) if point else 0.0,
    )
```

## Integration Notes

1. **Thread Safety**: All public methods are async-safe with proper locking
2. **Memory Management**: LRU cache with 100-entry limit, 5-minute TTL
3. **Audit Trail**: In-memory audit log (2000 records, not persisted)
4. **Model Loading**: Lazy-loaded on first forecast request
5. **Dependencies**: Requires `timesfm` package and `numpy`

## Production Readiness Checklist

### Configuration
- [ ] Set `SIMP_TIMESFM_ENABLED=true` for production
- [ ] Set `SIMP_TIMESFM_SHADOW_MODE=false` for live forecasts
- [ ] Set appropriate `SIMP_TIMESFM_HORIZON` for your use case (default: 64)
- [ ] Set `SIMP_TIMESFM_CONTEXT_LEN` based on your time series characteristics (default: 512)

### Agent Assessments
- [ ] Verify all agents have Q1≥3, Q3=True assessments in `timesfm_policy_engine.py`
- [ ] Register new agents in `_AGENT_ASSESSMENTS` dictionary with proper Q1/Q3/Q8 scores

### Monitoring
- [ ] Monitor cache hit rate via `health()["cache_hit_rate"]` (>50% indicates good reuse)
- [ ] Monitor error rate via `health()["error_rate"]` (alert if >5%)
- [ ] Monitor average latency via `health()["avg_latency_ms"]`
- [ ] Set up alerting for forecast error rate >5%
- [ ] Monitor shadow mode samples during transition from shadow to live mode

### Validation
- [ ] Validate fallback logic for all agent use cases
- [ ] Test with malformed inputs to ensure proper error handling
- [ ] Verify request validation catches invalid inputs (short series, bad horizon, malformed series_id)
- [ ] Test cache behavior under load

### Safety
- [ ] Review audit logs periodically for unusual patterns
- [ ] Ensure all agents use the policy engine before calling `forecast()`
- [ ] Verify shadow mode works correctly before enabling live forecasts
- [ ] Test service disabled mode (`SIMP_TIMESFM_ENABLED=false`)