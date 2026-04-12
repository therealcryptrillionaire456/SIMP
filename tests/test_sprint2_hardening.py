"""Tests for Sprint 2 hardening: rate limiting, control auth, path safety."""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.rate_limit import TokenBucket, RateLimiter
from simp.server.control_auth import CONTROL_TOKEN
from simp.server.request_guards import sanitize_agent_id


class TestTokenBucket:
    def test_initial_capacity(self):
        bucket = TokenBucket(rate=1.0, capacity=5)
        # Should be able to consume up to capacity
        for _ in range(5):
            assert bucket.consume()
        # 6th should fail
        assert not bucket.consume()

    def test_refill(self):
        bucket = TokenBucket(rate=10.0, capacity=10)
        # Drain all tokens
        for _ in range(10):
            bucket.consume()
        assert not bucket.consume()
        # Wait for refill (0.15s at rate=10/s should add ~1.5 tokens)
        time.sleep(0.15)
        assert bucket.consume()

    def test_thread_safety(self):
        import threading
        bucket = TokenBucket(rate=100.0, capacity=100)
        results = []
        def consume_many():
            count = 0
            for _ in range(50):
                if bucket.consume():
                    count += 1
            results.append(count)
        threads = [threading.Thread(target=consume_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total = sum(results)
        assert total == 100, f"Expected 100 total, got {total}"


class TestRateLimiter:
    def test_init(self):
        limiter = RateLimiter()
        assert limiter._buckets == {}

    def test_cleanup_stale(self):
        limiter = RateLimiter()
        # Manually add a stale bucket
        bucket = TokenBucket(rate=1.0, capacity=1)
        bucket.last_refill = time.monotonic() - 7200  # 2 hours ago
        limiter._buckets["stale:key"] = bucket
        removed = limiter.cleanup_stale(max_age_seconds=3600)
        assert removed == 1
        assert "stale:key" not in limiter._buckets


class TestControlAuth:
    def test_token_from_env(self):
        """CONTROL_TOKEN should be whatever's in the env (may be empty in test)."""
        # This just verifies the module loads without error
        assert isinstance(CONTROL_TOKEN, str)


class TestInboxPathSafety:
    def test_normal_agent_id_passes(self):
        ok, _ = sanitize_agent_id("bullbear_predictor")
        assert ok

    def test_traversal_blocked(self):
        ok, _ = sanitize_agent_id("../../etc")
        assert not ok

    def test_slash_blocked(self):
        ok, _ = sanitize_agent_id("agent/subdir")
        assert not ok

    def test_backslash_blocked(self):
        ok, _ = sanitize_agent_id("agent\\subdir")
        assert not ok


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
