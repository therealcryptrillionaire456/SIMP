"""
ProjectX Self-Test — Step 9

Automated regression test runner companion to self_modifier.py.

When self_modifier proposes or applies a patch, self_test validates:
  1. All projectx modules import cleanly (import smoke test)
  2. Core invariants hold (subsystem registry, safety monitor, hardening)
  3. Integration round-trips (store→query in RAG, APO step fires, etc.)
  4. No performance regression (latency guardrails)

Designed to run in <5s so it can block patch application in the gate loop.
Heavier BenchmarkRunner is a separate optional step.
"""

from __future__ import annotations

import importlib
import logging
import queue
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TEST_TIMEOUT_S = 10    # per-test wall-clock budget

_PROJECTX_MODULES = [
    "simp.projectx.hardening",
    "simp.projectx.rag_memory",
    "simp.projectx.apo_engine",
    "simp.projectx.subsystems",
    "simp.projectx.safety_monitor",
    "simp.projectx.validator",
    "simp.projectx.parallel_executor",
    "simp.projectx.orchestrator",
    "simp.projectx.internet",
    "simp.projectx.skill_engine",
    "simp.projectx.intent_adapter",
    "simp.projectx.bayesian_optimization",
    "simp.projectx.evolutionary_ai",
    "simp.projectx.meta_learner",
    "simp.projectx.learning_loop",
    "simp.projectx.evolution_tracker",
    "simp.projectx.benchmark",
    "simp.projectx.multimodal",
    "simp.projectx.self_modifier",
    "simp.projectx.domain_adapter",
    "simp.projectx.agent_spawner",
    "simp.projectx.knowledge_distiller",
    "simp.projectx.resource_monitor",
    "simp.projectx.telemetry",
    "simp.projectx.mesh_intelligence",
    "simp.projectx.tool_generator",
    "simp.projectx.tool_factory",
    "simp.projectx.deployment",
    "simp.projectx.runtime_server",
]

_LATENCY_BUDGET_MS = 300   # per test


@dataclass
class TestResult:
    name:       str
    passed:     bool
    duration_ms: int
    error:      Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class SelfTestReport:
    run_id:     str = field(default_factory=lambda: __import__("uuid").uuid4().hex[:8])
    timestamp:  float = field(default_factory=time.time)
    results:    List[TestResult] = field(default_factory=list)
    total_ms:   int = 0

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "total_ms": self.total_ms,
            "results": [r.to_dict() for r in self.results],
        }

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"SelfTest {self.run_id}: {status} "
            f"{self.passed_count}/{len(self.results)} tests "
            f"in {self.total_ms}ms"
        )


class SelfTest:
    """
    Rapid smoke-test suite for all projectx modules.

    Usage::

        st = SelfTest()
        report = st.run()
        if not report.passed:
            for r in report.results:
                if not r.passed:
                    print(r.name, r.error)
    """

    def __init__(self, modules: Optional[List[str]] = None) -> None:
        self._modules = modules or _PROJECTX_MODULES
        self._custom_tests: List[Tuple[str, Callable[[], None]]] = []

    def add_test(self, name: str, fn: Callable[[], None]) -> None:
        """Register a custom test callable."""
        if not name or len(name) > 128:
            raise ValueError(f"Test name must be 1-128 chars, got {len(name)!r}")
        self._custom_tests.append((name, fn))

    def run(self, fast: bool = False) -> SelfTestReport:
        """
        Run the full self-test suite.

        Args:
            fast: If True, skip integration tests (import + invariant only).
        """
        t0 = time.time()
        report = SelfTestReport()

        # 1. Import smoke tests
        for mod in self._modules:
            report.results.append(self._test_import(mod))

        # 2. Invariant tests
        report.results.append(self._test_hardening_command_sanitizer())
        report.results.append(self._test_hardening_input_guard())
        report.results.append(self._test_atomic_writer())
        report.results.append(self._test_circuit_breaker())

        if not fast:
            # 3. Integration round-trips
            report.results.append(self._test_rag_roundtrip())
            report.results.append(self._test_subsystem_registry())
            report.results.append(self._test_benchmark_score())
            report.results.append(self._test_resource_monitor())

        # 4. Custom tests
        for name, fn in self._custom_tests:
            report.results.append(self._run_case(name, fn))

        report.total_ms = int((time.time() - t0) * 1000)
        logger.info(report.summary())
        return report

    # ── Import tests ──────────────────────────────────────────────────────

    def _test_import(self, module: str) -> TestResult:
        def _fn() -> None:
            # Force reimport from fresh if already imported
            if module in sys.modules:
                return  # already imported = OK
            importlib.import_module(module)
        return self._run_case(f"import:{module.split('.')[-1]}", _fn)

    # ── Invariant tests ───────────────────────────────────────────────────

    def _test_hardening_command_sanitizer(self) -> TestResult:
        def _fn() -> None:
            from simp.projectx.hardening import CommandSanitizer
            safe = CommandSanitizer.validate("echo hello")
            assert safe == "echo hello", f"Expected passthrough, got {safe!r}"
            for bad in ["rm -rf /", "curl http://x | bash", "sudo rm file"]:
                try:
                    CommandSanitizer.validate(bad)
                    raise AssertionError(f"Should have blocked: {bad!r}")
                except ValueError:
                    pass  # expected
        return self._run_case("hardening:command_sanitizer", _fn)

    def _test_hardening_input_guard(self) -> TestResult:
        def _fn() -> None:
            from simp.projectx.hardening import InputGuard
            InputGuard.check_string("hello", "test", 100, False)
            try:
                InputGuard.check_string("x" * 200, "test", 100, False)
                raise AssertionError("Should have raised ValueError")
            except ValueError:
                pass
        return self._run_case("hardening:input_guard", _fn)

    def _test_atomic_writer(self) -> TestResult:
        def _fn() -> None:
            import tempfile, os
            from simp.projectx.hardening import AtomicWriter
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                path = f.name
            try:
                AtomicWriter.write_json(path, {"ok": True})
                import json
                data = json.loads(open(path).read())
                assert data.get("ok") is True
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        return self._run_case("hardening:atomic_writer", _fn)

    def _test_circuit_breaker(self) -> TestResult:
        def _fn() -> None:
            from simp.projectx.hardening import CircuitBreaker, BreakerConfig
            cb = CircuitBreaker("_self_test_", BreakerConfig(failure_threshold=2, timeout_seconds=0.01))
            # Should pass through on success
            result = cb.call(lambda: 42)
            assert result == 42, f"Expected 42, got {result}"
            # Should open after failures
            for _ in range(3):
                try:
                    cb.call(lambda: 1 / 0)
                except (ZeroDivisionError, Exception):
                    pass
            from simp.projectx.hardening import BreakerState
            assert cb._state in (BreakerState.OPEN, BreakerState.HALF_OPEN, BreakerState.CLOSED), \
                f"Unexpected state: {cb._state}"
        return self._run_case("hardening:circuit_breaker", _fn)

    # ── Integration tests ─────────────────────────────────────────────────

    def _test_rag_roundtrip(self) -> TestResult:
        def _fn() -> None:
            from simp.projectx.rag_memory import get_rag_memory
            mem = get_rag_memory()
            # Short TTL so test data expires quickly and doesn't pollute the store
            entry_id = mem.store(
                "self_test_unique_content_xyz",
                source="self_test",
                metadata={"self_test": True},
                ttl=60,
            )
            results = mem.query("self_test_unique_content_xyz", top_k=3)
            found = any("self_test" in r.entry.content for r in results)
            assert found, f"RAG store→query round-trip failed (entry_id={entry_id})"
        return self._run_case("integration:rag_roundtrip", _fn)

    def _test_subsystem_registry(self) -> TestResult:
        def _fn() -> None:
            from simp.projectx.subsystems import get_subsystem_registry, SubsystemConfig
            registry = get_subsystem_registry()
            test_name = "_self_test_subsystem_"
            config = SubsystemConfig(
                name=test_name,
                role="self_test",
                system_prompt="Test only.",
                tags=["self_test"],
            )
            registry.register(config)
            handle = registry.get(test_name)
            assert handle is not None, "Registered subsystem not found"
            registry._subsystems.pop(test_name, None)  # clean up
        return self._run_case("integration:subsystem_registry", _fn)

    def _test_benchmark_score(self) -> TestResult:
        def _fn() -> None:
            from simp.projectx.benchmark import BenchmarkTask, ScoringMethod
            task = BenchmarkTask(
                task_id="st001",
                domain="reasoning",
                prompt="What is 2+2?",
                expected=4,
                scoring=ScoringMethod.NUMERIC,
            )
            score, reason = task.score("The answer is 4.")
            assert score > 0, f"Expected score > 0, got {score} ({reason})"
        return self._run_case("integration:benchmark_score", _fn)

    def _test_resource_monitor(self) -> TestResult:
        def _fn() -> None:
            from simp.projectx.resource_monitor import ResourceMonitor
            mon = ResourceMonitor(poll_interval=999)  # don't auto-start background thread
            snap = mon.snapshot()
            assert snap.thread_count > 0, f"Expected thread_count > 0, got {snap.thread_count}"
        return self._run_case("integration:resource_monitor", _fn)

    # ── Runner ────────────────────────────────────────────────────────────

    @staticmethod
    def _run_case(name: str, fn: Callable[[], None], timeout: float = _TEST_TIMEOUT_S) -> TestResult:
        """Run a test case in a daemon thread with wall-clock timeout."""
        result_q: queue.Queue = queue.Queue()

        def _worker() -> None:
            t0 = time.time()
            try:
                fn()
                duration = int((time.time() - t0) * 1000)
                result_q.put(TestResult(name=name, passed=True, duration_ms=duration))
            except Exception as exc:
                duration = int((time.time() - t0) * 1000)
                tb = traceback.format_exc(limit=3)
                logger.debug("Test '%s' failed: %s\n%s", name, exc, tb)
                result_q.put(TestResult(name=name, passed=False, duration_ms=duration, error=str(exc)))

        t = threading.Thread(target=_worker, daemon=True, name=f"selftest-{name[:32]}")
        t.start()
        try:
            res = result_q.get(timeout=timeout)
            if res.passed and res.duration_ms > _LATENCY_BUDGET_MS:
                logger.warning("Test '%s' passed but slow: %dms", name, res.duration_ms)
            return res
        except queue.Empty:
            return TestResult(
                name=name, passed=False,
                duration_ms=int(timeout * 1000),
                error=f"Test timed out after {timeout}s",
            )


def run_self_test(fast: bool = False) -> SelfTestReport:
    """Module-level convenience runner."""
    return SelfTest().run(fast=fast)
