"""
patches/http_server_patch.py
──────────────────────────────
Drop-in replacement sections for http_server.py.

Issues addressed:
  #4  Rate limiting / DOS protection
  #9  Asyncio event loop leaks
  #10 CSRF / auth on control endpoints
  #13 HTTP API request signing / API key auth
"""

# ─────────────────────────────────────────────────────────────────────────────
# NEW IMPORTS (add near top of http_server.py)
# ─────────────────────────────────────────────────────────────────────────────
NEW_IMPORTS = """
import asyncio
import functools
import hashlib
import hmac
import os
import threading
import time
from typing import Optional

try:
    from config.config import config as _cfg
    _REQUIRE_API_KEY    = _cfg.REQUIRE_API_KEY
    _API_KEYS           = _cfg.get_api_keys()
    _RATE_LIMIT_ROUTE   = _cfg.RATE_LIMIT_ROUTE
    _MAX_PENDING        = _cfg.MAX_PENDING_INTENTS
    _MAX_PAYLOAD_BYTES  = _cfg.MAX_PAYLOAD_BYTES
except Exception:
    _REQUIRE_API_KEY   = os.environ.get("SIMP_REQUIRE_API_KEY", "true") == "true"
    _API_KEYS          = set(filter(None, os.environ.get("SIMP_API_KEYS", "").split(",")))
    _RATE_LIMIT_ROUTE  = os.environ.get("SIMP_RATE_LIMIT_ROUTE", "60 per minute")
    _MAX_PENDING       = int(os.environ.get("SIMP_MAX_PENDING_INTENTS", "500"))
    _MAX_PAYLOAD_BYTES = int(os.environ.get("SIMP_MAX_PAYLOAD_BYTES", "1000000"))

from simp.models.intent_schema import parse_intent_request
from simp.audit.audit_logger import get_audit_logger
_audit = get_audit_logger()
"""

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMITER  (pure-Python sliding-window, no extra dependencies)
# ─────────────────────────────────────────────────────────────────────────────
RATE_LIMITER_CLASS = '''
class SlidingWindowRateLimiter:
    """
    Thread-safe per-IP sliding-window rate limiter.

    rate_str format: "<count> per <unit>"  e.g. "60 per minute"
    Supported units: second, minute, hour, day
    """

    _UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

    def __init__(self, rate_str: str) -> None:
        try:
            count_s, _, unit = rate_str.strip().split()
            self._max = int(count_s)
            self._window = self._UNITS[unit.rstrip("s")]
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Invalid rate string {rate_str!r}: {exc}") from exc
        self._lock = threading.Lock()
        self._store: dict[str, list[float]] = {}  # ip → [timestamp, ...]

    def is_allowed(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = self._store.get(ip, [])
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self._max:
                self._store[ip] = timestamps
                return False
            timestamps.append(now)
            self._store[ip] = timestamps
            return True

    def cleanup(self) -> None:
        """Purge stale IP entries (call periodically)."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            self._store = {
                ip: ts for ip, ts in self._store.items()
                if any(t > cutoff for t in ts)
            }


# Process-wide limiters
_route_limiter   = SlidingWindowRateLimiter(_RATE_LIMIT_ROUTE)
_default_limiter = SlidingWindowRateLimiter("200 per day")
'''

# ─────────────────────────────────────────────────────────────────────────────
# AUTH DECORATOR  (API key / bearer token)
# ─────────────────────────────────────────────────────────────────────────────
AUTH_DECORATOR = '''
def require_api_key(f):
    """
    Decorator: enforce API key authentication on a Flask endpoint.

    Accepts key via:
      - Authorization: Bearer <key>
      - X-SIMP-API-Key: <key>

    Returns 401 if the key is missing or invalid.
    Skip enforcement when _REQUIRE_API_KEY is False (dev mode).
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not _REQUIRE_API_KEY:
            return f(*args, **kwargs)

        key = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            key = auth_header[7:].strip()
        if not key:
            key = request.headers.get("X-SIMP-API-Key", "").strip()

        if not key or key not in _API_KEYS:
            ip = request.remote_addr or "unknown"
            logger.warning("Unauthorized request from %s", ip)
            _audit.log_security_event(
                event_type="AUTH_FAILURE",
                status="REJECTED",
                details={"reason": "invalid or missing API key"},
                ip_address=ip,
            )
            return jsonify({
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Valid API key required",
            }), 401

        return f(*args, **kwargs)
    return wrapper


def check_rate_limit(limiter: "SlidingWindowRateLimiter"):
    """Decorator: enforce rate limiting."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "0.0.0.0"
            if not limiter.is_allowed(ip):
                logger.warning("Rate limit exceeded for %s", ip)
                return jsonify({
                    "status": "error",
                    "error_code": "RATE_LIMITED",
                    "message": "Too many requests",
                }), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator
'''

# ─────────────────────────────────────────────────────────────────────────────
# PAYLOAD SIZE CHECK  (add as first step in route_intent handler)
# ─────────────────────────────────────────────────────────────────────────────
PAYLOAD_SIZE_CHECK = '''
# In the route_intent() view function, BEFORE parsing JSON:
content_length = request.content_length
if content_length and content_length > _MAX_PAYLOAD_BYTES:
    return jsonify({
        "status": "error",
        "error_code": "PAYLOAD_TOO_LARGE",
        "message": f"Request body exceeds {_MAX_PAYLOAD_BYTES} bytes",
    }), 413
'''

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATED ROUTE INTENT ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
ROUTE_INTENT_ENDPOINT = '''
@app.route("/intents/route", methods=["POST"])
@require_api_key
@check_rate_limit(_route_limiter)
def route_intent():
    """Validate, rate-limit, and route an intent to the broker."""

    # 1. Payload size guard
    content_length = request.content_length or 0
    if content_length > _MAX_PAYLOAD_BYTES:
        return jsonify({
            "status": "error",
            "error_code": "PAYLOAD_TOO_LARGE",
        }), 413

    # 2. Pending intents queue guard
    pending_count = broker.get_pending_intent_count()  # implement on broker
    if pending_count >= _MAX_PENDING:
        return jsonify({
            "status": "error",
            "error_code": "QUEUE_FULL",
            "message": f"Maximum pending intents ({_MAX_PENDING}) reached",
        }), 429

    # 3. Parse & validate with Pydantic schema
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}

    ok, parsed, error_msg = parse_intent_request(data)
    if not ok:
        return jsonify({
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": error_msg,
        }), 400

    # 4. Route via broker (returns dict with status/correlation_id)
    try:
        result = broker.route_intent(
            parsed.dict() if hasattr(parsed, "dict") else parsed.model_dump(),
            source_ip=request.remote_addr,
        )
    except Exception as exc:
        logger.error("Unexpected error routing intent: %s", exc, exc_info=True)
        return jsonify({
            "status": "error",
            "error_code": "INTERNAL_ERROR",
        }), 500

    status_code = 200 if result.get("status") == "ok" else 400
    return jsonify(result), status_code
'''

# ─────────────────────────────────────────────────────────────────────────────
# ASYNCIO EVENT LOOP  — single shared loop, not per-request
# ─────────────────────────────────────────────────────────────────────────────
ASYNCIO_LOOP_FIX = '''
# ── Shared asyncio event loop ────────────────────────────────────────────────
# Create ONE loop in a dedicated thread; HTTP handlers submit coroutines to it.
# This replaces the pattern of asyncio.new_event_loop() per request.

_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True, name="simp-async")
_loop_thread.start()


def run_async(coro) -> object:
    """Submit a coroutine to the shared event loop and block until done."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    try:
        return future.result(timeout=30)
    except asyncio.TimeoutError:
        logger.error("Async operation timed out", exc_info=True)
        raise
    except Exception as exc:
        logger.error("Async operation failed: %s", exc, exc_info=True)
        raise


def shutdown_async_loop() -> None:
    """Call during server shutdown to cleanly stop the event loop."""
    _loop.call_soon_threadsafe(_loop.stop)
    _loop_thread.join(timeout=5)
    if not _loop.is_closed():
        _loop.close()

# Register cleanup at exit
import atexit
atexit.register(shutdown_async_loop)
'''

# ─────────────────────────────────────────────────────────────────────────────
# CONTROL ENDPOINTS with auth
# ─────────────────────────────────────────────────────────────────────────────
CONTROL_ENDPOINTS = '''
@app.route("/control/start", methods=["POST"])
@require_api_key
def control_start():
    """Start the broker. Requires API key authentication."""
    try:
        result = broker.start()
        _audit.log_security_event(
            event_type="BROKER_START", status="OK",
            ip_address=request.remote_addr,
        )
        return jsonify({"status": "ok", "result": result})
    except Exception as exc:
        logger.error("Failed to start broker: %s", exc, exc_info=True)
        return jsonify({"status": "error", "error_code": "START_FAILED"}), 500


@app.route("/control/stop", methods=["POST"])
@require_api_key
def control_stop():
    """Stop the broker. Requires API key authentication."""
    try:
        result = broker.stop()
        _audit.log_security_event(
            event_type="BROKER_STOP", status="OK",
            ip_address=request.remote_addr,
        )
        return jsonify({"status": "ok", "result": result})
    except Exception as exc:
        logger.error("Failed to stop broker: %s", exc, exc_info=True)
        return jsonify({"status": "error", "error_code": "STOP_FAILED"}), 500
'''
