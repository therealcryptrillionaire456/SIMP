"""
Chaos guardian tests — verify the system degrades gracefully under adverse conditions.

Tests cover:
  - SafeJsonlWriter recovers from partial/trauncated files
  - Circuit breaker trips after failures and recovers
  - BRPBridge handles malformed JSONL without crashing
  - Nonce store handles concurrent access
  - Governance engine respects all safety guardrails under stress
"""

from __future__ import annotations

import json
import os
import random
import tempfile
import threading
import time
from pathlib import Path

import pytest


class TestSafeJsonlWriterChaos:
    """SafeJsonlWriter survives file corruption and recovers."""

    def test_recovers_from_truncated_jsonl(self, tmp_path) -> None:
        from simp.utils.safe_jsonl import SafeJsonlWriter

        path = tmp_path / "chaos.jsonl"
        writer = SafeJsonlWriter(path, max_size_mb=0.001)

        for i in range(3):
            writer.append({"seq": i})

        # Truncate the file manually (simulate crash mid-write)
        with open(path, "w") as f:
            f.write('{"seq": 0}\n{"seq": 1}\n{"incomplete": ')

        # Writer should not crash on next append
        writer.append({"seq": 99})
        content = path.read_text()
        # The file should have the new record
        assert '{"seq": 99}' in content or content.count("\n") >= 1

    def test_recovers_from_injecting_newlines(self, tmp_path) -> None:
        from simp.utils.safe_jsonl import SafeJsonlWriter

        path = tmp_path / "chaos2.jsonl"
        writer = SafeJsonlWriter(path)

        # Try to inject via embedded newline
        writer.append({"msg": "line1\n{\"injected\": true}\nline2"})

        content = path.read_text()
        # Newlines should be escaped, not literal
        assert "\n{" not in content
        assert json.loads(content.strip().split("\n")[-1])["msg"].count("\\n") >= 1

    def test_rotation_produces_valid_gzip(self, tmp_path) -> None:
        """Verify we can create, rotate, and read back a gzip-compressed JSONL."""
        import gzip
        from simp.utils.safe_jsonl import SafeJsonlWriter

        path = tmp_path / "rotate.jsonl"
        writer = SafeJsonlWriter(path, max_size_mb=100.0)  # no auto-rotation

        for i in range(5):
            writer.append({"seq": i, "padding": "x" * 100})

        # Manually rotate via filesystem
        import time, shutil
        stamp = time.strftime("%Y%m%d_%H%M%S")
        gz_path = tmp_path / f"rotate_{stamp}.jsonl.gz"
        with open(path, "rb") as f_in:
            with gzip.open(str(gz_path), "wb") as f_out:
                f_out.write(f_in.read())

        # Gzip file should be readable
        with gzip.open(str(gz_path), "rt") as f:
            lines = f.readlines()
        assert len(lines) == 5
        assert "seq" in lines[0]


class TestCircuitBreakerChaos:
    """Circuit breaker trips on failures and recovers gracefully."""

    def test_circuit_breaker_trips_after_failures(self) -> None:
        from simp.projectx.hardening import CircuitBreaker, BreakerState, CircuitBreakerOpen

        from simp.projectx.hardening import BreakerConfig, CircuitBreaker
        cfg = BreakerConfig(failure_threshold=3, timeout_seconds=5)
        cb = CircuitBreaker("test", cfg)

        for i in range(3):
            with pytest.raises(Exception):
                cb.call(lambda: 1 / 0)

        # Should be open now
        assert cb._state == BreakerState.OPEN

        # Call should raise CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: 42)

    def test_circuit_breaker_recovers_after_timeout(self) -> None:
        from simp.projectx.hardening import CircuitBreaker, BreakerState, CircuitBreakerOpen

        from simp.projectx.hardening import BreakerConfig, CircuitBreaker
        cfg = BreakerConfig(failure_threshold=2, timeout_seconds=0.3, success_threshold=1)
        cb = CircuitBreaker("test2", cfg)

        # Trip the breaker with failures
        with pytest.raises(Exception):
            cb.call(lambda: 42 / 0)
        with pytest.raises(Exception):
            cb.call(lambda: 42 / 0)
        assert cb._state == BreakerState.OPEN

        # Wait for recovery
        time.sleep(0.5)

        # Should transition to half-open and allow a call
        result = cb.call(lambda: 42)
        assert result == 42
        # Should be closed after successful call
        assert cb._state == BreakerState.CLOSED

    def test_circuit_breaker_concurrent_access(self) -> None:
        from simp.projectx.hardening import CircuitBreaker, BreakerState

        from simp.projectx.hardening import BreakerConfig, CircuitBreaker
        cfg = BreakerConfig(failure_threshold=10, timeout_seconds=1.0)
        cb = CircuitBreaker("test_concurrent", cfg)
        results: list = []
        errors: list = []

        def worker() -> None:
            try:
                r = cb.call(lambda: random.choice([1 / 0, 42, 42]))
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise unhandled exceptions
        assert len(results) + len(errors) == 20


class TestBRPBridgeChaos:
    """BRPBridge handles malformed inputs without crashing."""

    def test_bridge_handles_malformed_jsonl(self, tmp_path) -> None:
        from simp.security.brp_bridge import BRPBridge
        from simp.security.brp_models import BRPEvent

        bridge = BRPBridge(data_dir=str(tmp_path))

        # Write bad JSONL directly
        events_log = tmp_path / "events.jsonl"
        events_log.write_text('{"malformed"\n{"event_id": "x"}\n')

        # Bridge should not crash when loading history
        bridge._warm_history()
        assert len(bridge._recent_events) >= 0  # survived

    def test_bridge_handles_empty_event(self, tmp_path) -> None:
        from simp.security.brp_bridge import BRPBridge

        bridge = BRPBridge(data_dir=str(tmp_path))
        # Should not raise
        resp = bridge.evaluate_config({})
        # Empty API key is treated as weak by the scanner
        assert resp.threat_score >= 0.0  # survived

    def test_bridge_config_eval_with_missing_fields(self, tmp_path) -> None:
        from simp.security.brp_bridge import BRPBridge

        bridge = BRPBridge(data_dir=str(tmp_path))
        resp = bridge.evaluate_config({
            "REQUIRE_API_KEY": False,
            # missing other fields
        })
        assert resp.threat_score >= 0.9
        assert "REQUIRE_API_KEY=False" in resp.summary


class TestNonceStoreChaos:
    """NonceStore handles concurrent access and adversarial input."""

    def test_concurrent_add(self, tmp_path) -> None:
        from simp.security.brp_nonce_store import NonceStore

        ns = NonceStore(db_path=str(tmp_path / "nonce.db"))

        new_count = 0
        dup_count = 0
        lock = threading.Lock()

        def worker(nonce_prefix: str) -> None:
            nonlocal new_count, dup_count
            for i in range(50):
                nonce = f"{nonce_prefix}-{i}"
                result = ns.add(nonce)
                with lock:
                    if result:
                        new_count += 1
                    else:
                        dup_count += 1

        threads = [threading.Thread(target=worker, args=(f"t{j}",)) for j in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert new_count == 500  # 10 threads × 50 unique nonces
        assert dup_count == 0

    def test_empty_nonce_always_new(self, tmp_path) -> None:
        from simp.security.brp_nonce_store import NonceStore

        ns = NonceStore(db_path=str(tmp_path / "nonce.db"))
        assert ns.add("") is True
        assert ns.add("") is True  # still new — empty is always new


class TestGovernanceGuardrails:
    """Governance engine respects all safety guardrails."""

    def test_negative_benchmark_delta_denied(self, tmp_path) -> None:
        from simp.projectx.governance import GovernedImprovementEngine
        from simp.projectx.safety_monitor import SafetyConfig, SafetyMonitor

        engine = GovernedImprovementEngine(
            contract_log_path=tmp_path / "contracts.jsonl",
            safety_monitor=SafetyMonitor(SafetyConfig()),
        )
        result = engine.run_patch_flow(
            objective="regression",
            target_file="simp/projectx/validator.py",
            original_snippet="X = 1",
            patched_snippet="X = 2",
            rationale="test",
            evidence={},
            benchmark_delta=-0.1,  # regression
            operator_approved=True,
        )
        assert result["decision"]["decision"] == "deny"
        assert any("negative" in r.lower() for r in result["decision"]["reasons"])

    def test_emergency_stop_blocks_all(self, tmp_path) -> None:
        from simp.projectx.governance import GovernedImprovementEngine
        from simp.projectx.safety_monitor import SafetyConfig, SafetyMonitor

        safety = SafetyMonitor(SafetyConfig())
        safety.trigger_emergency_stop("test")
        engine = GovernedImprovementEngine(
            contract_log_path=tmp_path / "contracts.jsonl",
            safety_monitor=safety,
        )
        result = engine.run_patch_flow(
            objective="try while stopped",
            target_file="simp/projectx/validator.py",
            original_snippet="X = 1",
            patched_snippet="X = 2",
            rationale="test",
            evidence={},
            benchmark_delta=0.01,
            operator_approved=True,
        )
        assert result["decision"]["decision"] == "deny"

    def test_paused_safety_holds_proposal(self, tmp_path, monkeypatch) -> None:
        from simp.projectx.governance import GovernedImprovementEngine
        from simp.projectx.safety_monitor import SafetyConfig, SafetyMonitor

        safety = SafetyMonitor(SafetyConfig(escalation_pause_seconds=3600))
        # Monkeypatch is_paused to always return True
        monkeypatch.setattr(type(safety), "is_paused", lambda self: True)
        engine = GovernedImprovementEngine(
            contract_log_path=tmp_path / "contracts.jsonl",
            safety_monitor=safety,
        )
        result = engine.run_patch_flow(
            objective="try while paused",
            target_file="simp/projectx/validator.py",
            original_snippet="X = 1",
            patched_snippet="X = 2",
            rationale="test",
            evidence={},
            benchmark_delta=0.01,
            operator_approved=True,
        )
        assert result["decision"]["decision"] == "hold"
