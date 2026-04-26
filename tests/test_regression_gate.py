"""CI Gate — Full projectx regression suite.

Run: python3.10 -m pytest tests/test_regression_gate.py -v

This file is the single command that verifies nothing is broken after any change.
All other test files are covered here; failures here block promotion.
"""

import importlib
import logging
import socket
import sys
import time
from pathlib import Path

import pytest


# ── module discovery ─────────────────────────────────────────────────────────

_PROJECTX_ROOT = Path("simp/projectx")
_MODULES = sorted(
    m.stem for m in _PROJECTX_ROOT.glob("*.py")
    if m.stem not in ("__init__", "__pycache__")
)


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def patch_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub out socket.getaddrinfo so network-dependent code skips gracefully."""
    def _stub_getaddrinfo(*args, **kwargs):
        raise socket.gaierror("Network stubbed in regression gate")
    monkeypatch.setattr(socket, "getaddrinfo", _stub_getaddrinfo, raising=True)
    for mod in (
        "sentence_transformers",
        "sentence_transformers.SentenceTransformer",
        "chromadb",
        "chromadb.Collection",
    ):
        monkeypatch.delitem(sys.modules, mod, raising=False)


# Singleton reset targets
_SENTINELS = {
    "rag_memory":        {"_memory": None},
    "evolution_tracker": {"_tracker": None},
    "tool_ecology":     {"_tool_ecology": None},
    "telemetry":         {"_registry": None, "_collector": None},
    "subsystems":        {"_registry": None},
    "cost_tracker":      {"_tracker": None},
    "pnl_tracker":        {"_tracker": None},
}


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    """Nullify module-level singletons before and after each test."""
    for module_name, attrs in _SENTINELS.items():
        try:
            mod = importlib.import_module(f"simp.projectx.{module_name}")
        except ImportError:
            continue
        for attr in attrs:
            if hasattr(mod, attr):
                setattr(mod, attr, None)

    yield

    for module_name, attrs in _SENTINELS.items():
        try:
            mod = importlib.import_module(f"simp.projectx.{module_name}")
        except ImportError:
            continue
        for attr in attrs:
            if hasattr(mod, attr):
                setattr(mod, attr, None)


# ── imports ─────────────────────────────────────────────────────────────────

class TestImports:
    @pytest.mark.parametrize("module", _MODULES, ids=_MODULES)
    def test_all_projectx_modules_import_cleanly(self, module: str) -> None:
        """Every projectx module must import without error."""
        full = f"simp.projectx.{module}"
        try:
            importlib.import_module(full)
        except Exception as exc:
            pytest.fail(f"Failed to import {full}: {exc}")


# ── hardening invariants ─────────────────────────────────────────────────────

class TestHardeningInvariants:
    def test_command_sanitizer(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest(modules=[])
        r = st._test_hardening_command_sanitizer()
        assert r.passed, f"command_sanitizer failed: {r.error}"

    def test_input_guard(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest(modules=[])
        r = st._test_hardening_input_guard()
        assert r.passed, f"input_guard failed: {r.error}"

    def test_atomic_writer(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest(modules=[])
        r = st._test_atomic_writer()
        assert r.passed, f"atomic_writer failed: {r.error}"

    def test_circuit_breaker(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest(modules=[])
        r = st._test_circuit_breaker()
        assert r.passed, f"circuit_breaker failed: {r.error}"


# ── subsystem smoke ──────────────────────────────────────────────────────────

class TestSubsystemSmoke:
    def test_subsystems_import(self) -> None:
        from simp.projectx.subsystems import SubsystemRegistry, SubsystemConfig
        assert SubsystemRegistry is not None

    def test_subsystem_register_roundtrip(self) -> None:
        from simp.projectx.subsystems import SubsystemRegistry, SubsystemConfig
        reg = SubsystemRegistry()
        cfg = SubsystemConfig(
            name="_gate_test_sub",
            role="gate",
            system_prompt="Gate only.",
            tags=["gate", "test"],
        )
        reg.register(cfg)
        handle = reg.get("_gate_test_sub")
        assert handle is not None
        reg._subsystems.pop("_gate_test_sub", None)


# ── governance smoke ─────────────────────────────────────────────────────────

class TestGovernanceSmoke:
    def test_governance_engine_instantiation(self, patch_network, tmp_path) -> None:
        from simp.projectx.governance import GovernedImprovementEngine
        engine = GovernedImprovementEngine(
            repo_root=None,
            contract_log_path=tmp_path / "contracts.jsonl",
        )
        assert engine is not None
        assert hasattr(engine, "_validation_threshold")


# ── validator smoke ─────────────────────────────────────────────────────────

class TestValidatorSmoke:
    def test_validator_validate_call(self) -> None:
        from simp.projectx.validator import AnswerValidator
        validator = AnswerValidator(threshold=0.5)
        report = validator.validate(
            question="What is 2+2?",
            answer="4",
        )
        assert report is not None
        assert hasattr(report, "composite_score")
        assert hasattr(report, "passed")


# ── RAG smoke ────────────────────────────────────────────────────────────────

class TestRAGMemorySmoke:
    def test_rag_store_query_roundtrip(self, patch_network, tmp_path) -> None:
        from simp.projectx.rag_memory import RAGMemory
        mem = RAGMemory(persist_dir=str(tmp_path / "rag_test"))
        marker = f"gate_{time.time_ns()}"
        entry_id = mem.store(marker, source="gate", ttl=60)
        assert entry_id, "store() returned empty entry_id"
        results = mem.query(marker, top_k=3, threshold=0.0)
        assert len(results) > 0, "RAG query returned no results"
        found = any(marker in r.entry.content for r in results)
        assert found, "RAG store-query round-trip failed: marker not in results"
        mem.forget(entry_id)


# ── evolution tracker smoke ─────────────────────────────────────────────────

class TestEvolutionTrackerSmoke:
    def test_evolution_tracker_track_cycle(self, tmp_path) -> None:
        from simp.projectx.evolution_tracker import EvolutionTracker
        tracker = EvolutionTracker(
            snapshot_path=str(tmp_path / "snapshots.jsonl"),
            dashboard_path=str(tmp_path / "dashboard.json"),
        )
        report = tracker.track_cycle()
        assert report is not None
        assert hasattr(report, "snapshot")
        assert hasattr(report.snapshot, "generation")


# ── tool ecology smoke ───────────────────────────────────────────────────────

class TestToolEcologySmoke:
    def test_tool_ecology_snapshot(self, patch_network) -> None:
        from simp.projectx.tool_ecology import ProjectXToolEcology
        ec = ProjectXToolEcology()
        snap = ec.snapshot(goal="gate test")
        assert snap is not None
        assert hasattr(snap, "tool_count")
        assert hasattr(snap, "timestamp")


# ── telemetry smoke ──────────────────────────────────────────────────────────

class TestTelemetrySmoke:
    def test_telemetry_emit_and_render(self) -> None:
        from simp.projectx.telemetry import MetricsRegistry, PrometheusExporter
        reg = MetricsRegistry(namespace="gate_test")
        c = reg.counter("gate_counter", "Gate test counter")
        c.inc(1.0)
        assert c.value() == 1.0

        exporter = PrometheusExporter(reg)
        rendered = exporter.render()
        assert "gate_test_gate_counter" in rendered

        g = reg.gauge("gate_gauge", "Gate test gauge")
        g.set(42.0)
        assert g.value() == 42.0

        h = reg.histogram("gate_histogram", "Gate test histogram", buckets=[0.1, 1.0])
        h.observe(0.5)
        counts, s, n = h.snapshot()
        assert n == 1
        assert s == 0.5


# ── self-test full suite ─────────────────────────────────────────────────────

class TestSelfTestFullSuite:
    def test_self_test_fast_pass(self, patch_network) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest()
        report = st.run(fast=True)
        failures = [r for r in report.results if not r.passed]
        assert report.passed, (
            f"SelfTest fast failed ({len(failures)}/{len(report.results)}): "
            + ", ".join(f"{r.name}" for r in failures)
        )

    def test_self_test_latency_budget(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest()
        report = st.run(fast=True)
        slow = [r for r in report.results if r.duration_ms > 3000]
        for r in slow:
            logging.getLogger("regression_gate").warning(
                "LATENCY SLOWDOWN: %s took %dms (budget 3000ms)",
                r.name, r.duration_ms,
            )
        assert len(slow) == 0, (
            f"Tests exceeding 3000ms latency budget: "
            + ", ".join(f"{r.name}={r.duration_ms}ms" for r in slow)
        )

    def test_self_test_full_pass(self, patch_network) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest()
        report = st.run(fast=False)
        network_skip_names = {
            r.name for r in report.results
            if not r.passed and r.error and "unreachable" in r.error.lower()
        }
        real_failures = [
            r for r in report.results
            if not r.passed and r.name not in network_skip_names
        ]
        msg = (
            f"SelfTest full failed ({len(real_failures)}/{len(report.results)}): "
            + ", ".join(f"{r.name}" for r in real_failures)
        )
        if network_skip_names:
            msg += f" (skipped {len(network_skip_names)} network tests: {', '.join(sorted(network_skip_names))})"
        assert len(real_failures) == 0, msg


# ── benchmark + APO smoke ───────────────────────────────────────────────────

class TestBenchmarkAndAPOSmoke:
    def test_benchmark_score(self) -> None:
        from simp.projectx.benchmark import BenchmarkTask, ScoringMethod
        task = BenchmarkTask(
            task_id="gate001",
            domain="reasoning",
            prompt="What is 2+2?",
            expected=4,
            scoring=ScoringMethod.NUMERIC,
        )
        score, reason = task.score("The answer is 4.")
        assert score > 0

    def test_apo_engine_import(self) -> None:
        from simp.projectx.apo_engine import APOEngine
        assert APOEngine is not None

    def test_meta_learner_import(self) -> None:
        from simp.projectx.meta_learner import MetaLearner
        assert MetaLearner is not None


# ── resource monitor ────────────────────────────────────────────────────────

class TestResourceMonitorSmoke:
    def test_resource_monitor_snapshot(self) -> None:
        from simp.projectx.resource_monitor import ResourceMonitor
        mon = ResourceMonitor(poll_interval=999)
        snap = mon.snapshot()
        assert snap.thread_count >= 1
        assert snap.memory_mb >= 0
