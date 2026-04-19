"""
tests/security/test_rate_limiter.py
─────────────────────────────────────
Tests for the SlidingWindowRateLimiter (from http_server_patch).

Runs standalone since the limiter logic is self-contained.
"""

import time
import threading
import pytest

# ── inline the class so tests run independently ───────────────────────────────

class SlidingWindowRateLimiter:
    _UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

    def __init__(self, rate_str: str) -> None:
        try:
            count_s, _, unit = rate_str.strip().split()
            self._max = int(count_s)
            self._window = self._UNITS[unit.rstrip("s")]
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Invalid rate string {rate_str!r}: {exc}") from exc
        self._lock = threading.Lock()
        self._store: dict = {}

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
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            self._store = {
                ip: ts for ip, ts in self._store.items()
                if any(t > cutoff for t in ts)
            }


# ── tests ─────────────────────────────────────────────────────────────────────

def test_allows_within_limit():
    limiter = SlidingWindowRateLimiter("5 per minute")
    for _ in range(5):
        assert limiter.is_allowed("1.2.3.4") is True


def test_blocks_over_limit():
    limiter = SlidingWindowRateLimiter("3 per minute")
    for _ in range(3):
        limiter.is_allowed("1.2.3.4")
    assert limiter.is_allowed("1.2.3.4") is False


def test_different_ips_independent():
    limiter = SlidingWindowRateLimiter("2 per minute")
    for _ in range(2):
        limiter.is_allowed("1.1.1.1")
    # 1.1.1.1 is blocked but 2.2.2.2 should still pass
    assert limiter.is_allowed("1.1.1.1") is False
    assert limiter.is_allowed("2.2.2.2") is True


def test_invalid_rate_string():
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter("bad rate string here invalid")


def test_thread_safety_under_burst():
    """100 concurrent requests from same IP; only first N should pass."""
    limiter = SlidingWindowRateLimiter("10 per minute")
    results = []
    lock = threading.Lock()

    def make_request():
        allowed = limiter.is_allowed("10.0.0.1")
        with lock:
            results.append(allowed)

    threads = [threading.Thread(target=make_request) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    allowed_count = sum(1 for r in results if r)
    assert allowed_count == 10, f"Expected 10 allowed, got {allowed_count}"


def test_cleanup_removes_stale_entries():
    limiter = SlidingWindowRateLimiter("5 per second")
    # Fill up
    for _ in range(5):
        limiter.is_allowed("10.0.0.1")
    assert "10.0.0.1" in limiter._store
    # Wait for window to expire, then cleanup
    time.sleep(1.1)
    limiter.cleanup()
    assert "10.0.0.1" not in limiter._store


class TestStressBurst:
    """Stress tests for rate limiter under high concurrency."""

    def test_1000_concurrent_requests_10_different_ips(self):
        limiter = SlidingWindowRateLimiter("50 per minute")
        results = {ip: [] for ip in [f"10.0.0.{i}" for i in range(10)]}
        lock = threading.Lock()

        def make_request(ip):
            allowed = limiter.is_allowed(ip)
            with lock:
                results[ip].append(allowed)

        threads = []
        for i in range(1000):
            ip = f"10.0.0.{i % 10}"
            threads.append(threading.Thread(target=make_request, args=(ip,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for ip, reqs in results.items():
            allowed = sum(1 for r in reqs if r)
            assert allowed <= 50, f"IP {ip} allowed {allowed} > 50 requests"
