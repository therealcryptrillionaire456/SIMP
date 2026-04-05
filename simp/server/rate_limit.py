"""
SIMP Rate Limiter — Lightweight in-process per-endpoint rate limiting.

Uses a token-bucket algorithm with no external dependencies.
Thread-safe for use with Flask's threaded mode.
"""

import os
import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Optional

from flask import request, jsonify

# Trusted proxy list — only trust X-Forwarded-For from these IPs
TRUSTED_PROXIES = {
    p.strip()
    for p in os.environ.get("SIMP_TRUSTED_PROXIES", "127.0.0.1,::1").split(",")
    if p.strip()
}


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens added per second.
            capacity: Maximum tokens in the bucket.
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


def get_client_id(req) -> str:
    """Get client identifier. Only trust X-Forwarded-For from trusted proxies."""
    remote_addr = req.remote_addr or "unknown"

    if remote_addr in TRUSTED_PROXIES:
        forwarded = req.headers.get("X-Forwarded-For", "")
        if forwarded:
            # Take the first (client) IP
            return forwarded.split(",")[0].strip()

    return remote_addr


class RateLimiter:
    """Per-client, per-endpoint rate limiter for Flask."""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._cleanup_timer: Optional[threading.Timer] = None
        self._start_cleanup_timer()

    def _start_cleanup_timer(self):
        """Run cleanup_stale every 60 seconds."""
        self._cleanup_timer = threading.Timer(60.0, self._cleanup_loop)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup_loop(self):
        """Periodic cleanup of stale buckets."""
        try:
            self.cleanup_stale()
        except Exception:
            pass
        self._start_cleanup_timer()

    def _get_bucket(self, key: str, rate: float, capacity: int) -> TokenBucket:
        """Get or create a token bucket for a given key."""
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(rate, capacity)
            return self._buckets[key]

    # Keep public alias for tests that reference get_bucket
    def get_bucket(self, key: str, rate: float, capacity: int) -> TokenBucket:
        """Public alias for _get_bucket."""
        return self._get_bucket(key, rate, capacity)

    def limit(self, requests_per_minute: int):
        """Decorator to rate limit a Flask route handler.

        Args:
            requests_per_minute: Maximum requests allowed per minute per client.
        """
        rate = requests_per_minute / 60.0  # tokens per second
        capacity = requests_per_minute  # burst capacity = 1 minute's worth

        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                client_id = get_client_id(request)
                endpoint = request.path
                key = f"{client_id}:{endpoint}"
                bucket = self._get_bucket(key, rate, capacity)

                if not bucket.consume():
                    return jsonify({
                        "status": "error",
                        "error_code": "RATE_LIMITED",
                        "error": f"Rate limit exceeded. Max {requests_per_minute} requests/minute.",
                    }), 429

                return f(*args, **kwargs)
            return wrapper
        return decorator

    def cleanup_stale(self, max_age_seconds: float = 3600.0) -> int:
        """Remove buckets that haven't been used recently. Returns count removed."""
        now = time.monotonic()
        stale_keys = []
        with self._lock:
            for key, bucket in self._buckets.items():
                if now - bucket.last_refill > max_age_seconds:
                    stale_keys.append(key)
            for key in stale_keys:
                del self._buckets[key]
        return len(stale_keys)
