"""
SIMP Rate Limiter — Lightweight in-process per-endpoint rate limiting.

Uses a token-bucket algorithm with no external dependencies.
Thread-safe for use with Flask's threaded mode.
"""

import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Optional

from flask import request, jsonify


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


class RateLimiter:
    """Per-client, per-endpoint rate limiter for Flask."""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, key: str, rate: float, capacity: int) -> TokenBucket:
        """Get or create a token bucket for a given key."""
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(rate, capacity)
            return self._buckets[key]

    def _get_client_id(self) -> str:
        """Get client identifier from request."""
        # Use X-Forwarded-For if behind a reverse proxy, else remote_addr
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"

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
                client_id = self._get_client_id()
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
