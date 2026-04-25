"""
Rate limiter for KashClaw Media Grid using a token bucket algorithm.

Provides both a standalone RateLimiter class and a decorator pattern
for use with agent methods. Thread-safe.
"""
import functools
import threading
import time
from typing import Callable, Optional


class RateLimiter:
    """Token bucket rate limiter with configurable rate and window.
    
    Thread-safe. Tracks call timestamps to enforce a maximum number of
    calls within a sliding time window.
    
    Attributes:
        max_calls: Maximum permitted calls within the window.
        window_seconds: Width of the sliding window in seconds.
    """
    
    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._timestamps: list[float] = []
    
    def allow(self) -> bool:
        """Check whether a call is allowed under the current rate.
        
        Thread-safe. Prunes expired timestamps from the window before
        checking capacity.
        
        Returns:
            True if the call is permitted, False if rate-limited.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        
        with self._lock:
            # Prune expired entries
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            
            if len(self._timestamps) >= self.max_calls:
                return False
            
            self._timestamps.append(now)
            return True
    
    @property
    def remaining(self) -> int:
        """Number of calls still available in the current window (approximate)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        
        with self._lock:
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            return max(0, self.max_calls - len(self._timestamps))
    
    @property
    def window_remaining(self) -> float:
        """Seconds until the oldest timestamp expires (0 if no calls made)."""
        with self._lock:
            if not self._timestamps:
                return 0.0
            elapsed = time.monotonic() - self._timestamps[0]
            return max(0.0, self.window_seconds - elapsed)
    
    def reset(self) -> None:
        """Clear all tracked timestamps, resetting the rate limiter."""
        with self._lock:
            self._timestamps.clear()
    
    def __call__(self, func: Callable) -> Callable:
        """Use as a decorator: reject calls when rate-limited.
        
        The decorated function will raise RateLimitError if the rate
        limit has been exceeded.
        
        Usage::
        
            limiter = RateLimiter(max_calls=5, window_seconds=60)
            
            @limiter
            def my_method(self, ...):
                ...
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self.allow():
                raise RateLimitError(
                    f"Rate limit exceeded: max {self.max_calls} calls "
                    f"per {self.window_seconds}s"
                )
            return func(*args, **kwargs)
        return wrapper


class RateLimitError(Exception):
    """Raised when a rate-limited call is rejected."""
    pass
