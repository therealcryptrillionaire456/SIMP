"""
TimesFM Shared Forecasting Service — SIMP Integration

Provides a singleton TimesFM service accessible to all SIMP agents.
All forecasting behavior is gated by feature flags and a policy engine,
ensuring agents cannot inadvertently act on forecasts during shadow mode.

Feature flags (environment variables):
    SIMP_TIMESFM_ENABLED       — master switch (default: false)
    SIMP_TIMESFM_SHADOW_MODE   — compute forecasts but suppress in returns (default: true)
    SIMP_TIMESFM_CHECKPOINT    — HuggingFace checkpoint string
    SIMP_TIMESFM_CONTEXT_LEN   — context length for model (default: 512)
    SIMP_TIMESFM_HORIZON       — default forecast horizon steps (default: 64)

Usage:
    from simp.integrations.timesfm_service import get_timesfm_service, ForecastRequest

    svc = get_timesfm_service()
    req = ForecastRequest(
        series_id="SOL/USDC:spread",
        values=[0.12, 0.14, 0.11, ...],
        requesting_agent="quantumarb",
        horizon=32,
    )
    resp = await svc.forecast(req)
    if resp.available:
        print(resp.point_forecast)
"""

from __future__ import annotations

import asyncio
import collections
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature-flag helpers
# ---------------------------------------------------------------------------

def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default).strip() or default


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

TIMESFM_ENABLED: bool = _env_bool("SIMP_TIMESFM_ENABLED", False)
TIMESFM_SHADOW_MODE: bool = _env_bool("SIMP_TIMESFM_SHADOW_MODE", True)
TIMESFM_CHECKPOINT: str = _env_str(
    "SIMP_TIMESFM_CHECKPOINT", "google/timesfm-2.0-500m-pytorch"
)
TIMESFM_CONTEXT_LEN: int = _env_int("SIMP_TIMESFM_CONTEXT_LEN", 512)
TIMESFM_DEFAULT_HORIZON: int = _env_int("SIMP_TIMESFM_HORIZON", 64)

# LRU cache settings
_CACHE_MAX_SERIES: int = 100
_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes

# Service version
_TIMESFM_SERVICE_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Request / Response dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ForecastRequest:
    """
    Standardized request for a TimesFM forecast.

    Args:
        series_id:        Unique stable identifier for the time series
                          (e.g. "SOL/USDC:spread", "kloutbot:affinity").
                          Used as the LRU cache key.
        values:           Ordered list of historical float observations,
                          most-recent last.
        requesting_agent: The agent_id issuing the request.
        horizon:          Steps ahead to forecast. Defaults to TIMESFM_DEFAULT_HORIZON.
        frequency:        TimesFM frequency hint (0 = high-freq default).
        context_metadata: Optional dict attached to this request for audit.
    """
    series_id: str
    values: List[float]
    requesting_agent: str
    horizon: int = TIMESFM_DEFAULT_HORIZON
    frequency: int = 0
    context_metadata: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> List[str]:
        """
        Validate request parameters.
        
        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []
        
        # Minimum observations for meaningful forecast
        if len(self.values) < 16:
            errors.append("Need ≥16 observations for meaningful forecast")
        
        # Horizon safety limit
        if self.horizon > 128:
            errors.append(f"Horizon {self.horizon} exceeds safe limit (128)")
        
        # Series ID format (domain:metric)
        if not self.series_id or ":" not in self.series_id:
            errors.append("series_id should follow 'domain:metric' format")
        
        # Requesting agent must be non-empty
        if not self.requesting_agent:
            errors.append("requesting_agent must be non-empty")
        
        # Values must be finite numbers
        for i, val in enumerate(self.values):
            if not isinstance(val, (int, float)):
                errors.append(f"Value at index {i} is not a number: {val}")
            elif not (float('-inf') < val < float('inf')):
                errors.append(f"Value at index {i} is not finite: {val}")
        
        return errors


@dataclass
class ForecastResponse:
    """
    Standardized response from a TimesFM forecast call.

    Args:
        available:       True only when TIMESFM_ENABLED and NOT shadow_mode,
                         or when shadow_mode was explicitly bypassed by policy.
        shadow_mode:     Whether this response was produced in shadow mode.
        point_forecast:  List of predicted values (empty when not available).
        lower_bound:     Lower confidence interval (empty when not available).
        upper_bound:     Upper confidence interval (empty when not available).
        horizon:         Steps forecasted.
        series_id:       Echo of request series_id.
        request_id:      Echo of request request_id.
        cached:          True if result came from LRU cache.
        latency_ms:      Wall-clock time to produce the forecast.
        error:           Non-None if forecasting failed; contains error message.
    """
    available: bool
    shadow_mode: bool
    point_forecast: List[float]
    lower_bound: List[float]
    upper_bound: List[float]
    horizon: int
    series_id: str
    request_id: str
    cached: bool = False
    latency_ms: float = 0.0
    error: Optional[str] = None

    @classmethod
    def unavailable(
        cls,
        request_id: str,
        series_id: str,
        horizon: int,
        reason: str = "TimesFM disabled or shadow mode active",
        shadow_mode: bool = True,
    ) -> "ForecastResponse":
        return cls(
            available=False,
            shadow_mode=shadow_mode,
            point_forecast=[],
            lower_bound=[],
            upper_bound=[],
            horizon=horizon,
            series_id=series_id,
            request_id=request_id,
            error=reason,
        )


# ---------------------------------------------------------------------------
# LRU Context Cache
# ---------------------------------------------------------------------------

class _CacheEntry:
    __slots__ = ("response", "timestamp")

    def __init__(self, response: ForecastResponse):
        self.response = response
        self.timestamp: float = time.monotonic()

    def is_valid(self) -> bool:
        return (time.monotonic() - self.timestamp) < _CACHE_TTL_SECONDS


class ContextCache:
    """
    Thread-safe LRU cache mapping series_id → ForecastResponse.
    Max size: _CACHE_MAX_SERIES entries. TTL: _CACHE_TTL_SECONDS seconds.
    """

    def __init__(self, maxsize: int = _CACHE_MAX_SERIES):
        self._cache: "collections.OrderedDict[str, _CacheEntry]" = (
            collections.OrderedDict()
        )
        self._maxsize = maxsize
        self._lock = asyncio.Lock()

    async def get(self, series_id: str) -> Optional[ForecastResponse]:
        async with self._lock:
            entry = self._cache.get(series_id)
            if entry is None:
                return None
            if not entry.is_valid():
                del self._cache[series_id]
                return None
            # Move to end (most-recently-used)
            self._cache.move_to_end(series_id)
            return entry.response

    async def put(self, series_id: str, response: ForecastResponse) -> None:
        async with self._lock:
            if series_id in self._cache:
                self._cache.move_to_end(series_id)
            self._cache[series_id] = _CacheEntry(response)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)  # evict LRU

    async def invalidate(self, series_id: str) -> None:
        async with self._lock:
            self._cache.pop(series_id, None)

    @property
    def size(self) -> int:
        return len(self._cache)


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class ForecastAuditLog:
    """
    In-memory audit trail for all TimesFM forecast requests.
    Keeps the last 2000 records. Not persisted between restarts.
    """

    _MAX_RECORDS = 2000

    def __init__(self):
        self._log: List[Dict[str, Any]] = []

    def record(self, request: ForecastRequest, response: ForecastResponse) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "request_id": request.request_id,
            "series_id": request.series_id,
            "requesting_agent": request.requesting_agent,
            "horizon": request.horizon,
            "input_length": len(request.values),
            "available": response.available,
            "shadow_mode": response.shadow_mode,
            "cached": response.cached,
            "latency_ms": response.latency_ms,
            "error": response.error,
            "validation_errors": request.validate() if hasattr(request, 'validate') else [],
            "cache_hit": response.cached,  # Explicit cache hit field for easier querying
        }
        self._log.append(entry)
        if len(self._log) > self._MAX_RECORDS:
            self._log = self._log[-self._MAX_RECORDS :]

    def recent(self, n: int = 100) -> List[Dict[str, Any]]:
        return list(self._log[-n:])

    def for_agent(self, agent_id: str, n: int = 50) -> List[Dict[str, Any]]:
        matches = [e for e in self._log if e["requesting_agent"] == agent_id]
        return matches[-n:]


# ---------------------------------------------------------------------------
# TimesFM Service
# ---------------------------------------------------------------------------

class TimesFMService:
    """
    Singleton service providing TimesFM forecasting to all SIMP agents.

    Responsibilities:
    - Lazy-load the TimesFM model on first forecast call
    - Enforce feature flags (enabled, shadow_mode)
    - LRU-cache recent forecasts per series_id
    - Audit-log every request/response pair
    - Never raise — always return ForecastResponse (with error field if needed)
    """

    def __init__(self):
        self._model = None  # lazy-loaded
        self._model_lock = asyncio.Lock()
        self.cache = ContextCache()
        self.audit = ForecastAuditLog()
        # Read environment variables at instantiation time, not module import time
        self._enabled = _env_bool("SIMP_TIMESFM_ENABLED", False)
        self._shadow_mode = _env_bool("SIMP_TIMESFM_SHADOW_MODE", True)
        self._checkpoint = _env_str("SIMP_TIMESFM_CHECKPOINT", "google/timesfm-2.0-500m-pytorch")
        self._context_len = _env_int("SIMP_TIMESFM_CONTEXT_LEN", 512)
        self._default_horizon = _env_int("SIMP_TIMESFM_HORIZON", 64)
        
        # Statistics tracking for enhanced health reporting
        self._stats_lock = asyncio.Lock()
        self._total_requests = 0
        self._cache_hits = 0
        self._errors = 0
        self._shadow_mode_samples = 0
        self._total_latency_ms = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def forecast(self, request: ForecastRequest) -> ForecastResponse:
        """
        Main entry point. Returns ForecastResponse.

        When TIMESFM_ENABLED is False:
            Returns unavailable response immediately.
        When TIMESFM_SHADOW_MODE is True:
            Computes the forecast (for offline evaluation/logging) but
            sets available=False so agents cannot act on it.
        When TIMESFM_SHADOW_MODE is False:
            Returns available=True with real forecast data.
        """
        t_start = time.monotonic()
        
        # Update request statistics
        async with self._stats_lock:
            self._total_requests += 1

        if not self._enabled:
            resp = ForecastResponse.unavailable(
                request_id=request.request_id,
                series_id=request.series_id,
                horizon=request.horizon,
                reason="SIMP_TIMESFM_ENABLED=false",
                shadow_mode=self._shadow_mode,
            )
            resp.latency_ms = (time.monotonic() - t_start) * 1000
            self.audit.record(request, resp)
            
            # Track latency
            async with self._stats_lock:
                self._total_latency_ms += resp.latency_ms
            
            return resp

        # Check cache
        cached_resp = await self.cache.get(request.series_id)
        if cached_resp is not None:
            # Track cache hit
            async with self._stats_lock:
                self._cache_hits += 1
            
            resp = ForecastResponse(
                available=not self._shadow_mode,
                shadow_mode=self._shadow_mode,
                point_forecast=cached_resp.point_forecast,
                lower_bound=cached_resp.lower_bound,
                upper_bound=cached_resp.upper_bound,
                horizon=cached_resp.horizon,
                series_id=request.series_id,
                request_id=request.request_id,
                cached=True,
                latency_ms=(time.monotonic() - t_start) * 1000,
            )
            self.audit.record(request, resp)
            
            # Track latency
            async with self._stats_lock:
                self._total_latency_ms += resp.latency_ms
            
            return resp

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
            resp.latency_ms = (time.monotonic() - t_start) * 1000
            self.audit.record(request, resp)
            
            # Track error and latency
            async with self._stats_lock:
                self._errors += 1
                self._total_latency_ms += resp.latency_ms
            
            return resp

        # Load model (once) and run forecast
        try:
            model = await self._get_model()
            point, lower, upper = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_forecast_sync,
                model,
                request,
            )
        except Exception as exc:
            log.warning(
                "TimesFM forecast failed for series=%s agent=%s: %s",
                request.series_id,
                request.requesting_agent,
                exc,
            )
            
            # Track error
            async with self._stats_lock:
                self._errors += 1
            
            resp = ForecastResponse.unavailable(
                request_id=request.request_id,
                series_id=request.series_id,
                horizon=request.horizon,
                reason=f"Forecast error: {exc}",
                shadow_mode=self._shadow_mode,
            )
            resp.latency_ms = (time.monotonic() - t_start) * 1000
            self.audit.record(request, resp)
            
            # Track latency
            async with self._stats_lock:
                self._total_latency_ms += resp.latency_ms
            
            return resp

        resp = ForecastResponse(
            available=not self._shadow_mode,
            shadow_mode=self._shadow_mode,
            point_forecast=point,
            lower_bound=lower,
            upper_bound=upper,
            horizon=request.horizon,
            series_id=request.series_id,
            request_id=request.request_id,
            cached=False,
            latency_ms=(time.monotonic() - t_start) * 1000,
        )

        # Cache the live result (even in shadow mode — for consistency)
        await self.cache.put(request.series_id, resp)

        self.audit.record(request, resp)
        
        # Track statistics
        async with self._stats_lock:
            self._total_latency_ms += resp.latency_ms
            if self._shadow_mode:
                self._shadow_mode_samples += 1

        if self._shadow_mode:
            log.debug(
                "[SHADOW] TimesFM forecast computed but suppressed: "
                "series=%s agent=%s horizon=%d",
                request.series_id,
                request.requesting_agent,
                request.horizon,
            )

        return resp

    def health(self) -> Dict[str, Any]:
        """Return service health status dict."""
        # Calculate enhanced metrics
        cache_hit_rate = 0.0
        if self._total_requests > 0:
            cache_hit_rate = self._cache_hits / self._total_requests
        
        avg_latency_ms = 0.0
        if self._total_requests > 0:
            avg_latency_ms = self._total_latency_ms / self._total_requests
        
        error_rate = 0.0
        if self._total_requests > 0:
            error_rate = self._errors / self._total_requests
        
        # Get last error from audit log if any
        last_error = None
        if self.audit._log:
            for entry in reversed(self.audit._log):
                if entry.get("error"):
                    last_error = entry["error"]
                    break
        
        return {
            "version": _TIMESFM_SERVICE_VERSION,
            "enabled": self._enabled,
            "shadow_mode": self._shadow_mode,
            "model_loaded": self._model is not None,
            "checkpoint": self._checkpoint,
            "context_len": self._context_len,
            "default_horizon": self._default_horizon,
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
            "last_error": last_error,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_model(self):
        """Lazy-load the TimesFM model (thread-safe, loads once)."""
        if self._model is not None:
            return self._model

        async with self._model_lock:
            if self._model is not None:
                return self._model

            log.info(
                "Loading TimesFM model: checkpoint=%s context_len=%d",
                TIMESFM_CHECKPOINT,
                TIMESFM_CONTEXT_LEN,
            )
            try:
                import timesfm  # type: ignore

                model = timesfm.TimesFm(
                    hparams=timesfm.TimesFmHparams(
                        backend="pytorch",
                        per_core_batch_size=32,
                        horizon_len=TIMESFM_DEFAULT_HORIZON,
                        context_len=TIMESFM_CONTEXT_LEN,
                        num_layers=50,
                        model_dims=1280,
                    ),
                    checkpoint=timesfm.TimesFmCheckpoint(
                        huggingface_repo_id=TIMESFM_CHECKPOINT
                    ),
                )
                self._model = model
                log.info("TimesFM model loaded successfully.")
            except ImportError:
                raise RuntimeError(
                    "timesfm package not installed. "
                    "Run: pip install timesfm --break-system-packages"
                )
            return self._model

    @staticmethod
    def _run_forecast_sync(
        model, request: ForecastRequest
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Synchronous forecast execution (runs in thread pool executor).

        Returns (point_forecast, lower_bound, upper_bound) as Python lists.
        """
        import numpy as np  # type: ignore

        values = np.array(request.values, dtype=np.float32)
        # TimesFM expects a list of arrays
        forecast_input = [values]
        freq_input = [request.frequency]

        point_forecasts, quantile_forecasts = model.forecast(
            forecast_input,
            freq=freq_input,
        )

        # point_forecasts shape: (1, horizon)
        point = point_forecasts[0, : request.horizon].tolist()

        # quantile_forecasts shape: (1, horizon, num_quantiles)
        # Standard quantiles: [0.1, 0.2, ..., 0.9]
        num_quantiles = quantile_forecasts.shape[2] if quantile_forecasts.ndim == 3 else 0
        if num_quantiles >= 8:
            lower = quantile_forecasts[0, : request.horizon, 0].tolist()  # q0.1
            upper = quantile_forecasts[0, : request.horizon, -1].tolist()  # q0.9
        else:
            lower = point
            upper = point

        return point, lower, upper


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_service_instance: Optional[TimesFMService] = None
_service_lock = asyncio.Lock()


async def get_timesfm_service() -> TimesFMService:
    """
    Return the global TimesFM service singleton (async-safe, lazy init).
    """
    global _service_instance
    if _service_instance is not None:
        return _service_instance
    # Fast path without lock for already-initialized case
    # (double-checked locking pattern)
    async with _service_lock:
        if _service_instance is None:
            _service_instance = TimesFMService()
            log.info("TimesFMService singleton created.")
        return _service_instance


def get_timesfm_service_sync() -> TimesFMService:
    """
    Synchronous accessor — returns existing singleton or creates new one
    without async model loading. Safe to call at module import time.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = TimesFMService()
        log.info("TimesFMService singleton created (sync).")
    return _service_instance
