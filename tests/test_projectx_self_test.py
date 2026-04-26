"""Tests for SelfTest — ProjectX self-test smoke suite."""

import pytest


class TestSelfTestImports:
    def test_self_test_imports(self) -> None:
        from simp.projectx.self_test import SelfTest, SelfTestReport, TestResult
        assert SelfTest is not None
        assert SelfTestReport is not None
        assert TestResult is not None

    def test_self_test_report_passes_initially(self) -> None:
        from simp.projectx.self_test import SelfTestReport
        r = SelfTestReport()
        assert r.passed is True
        assert r.passed_count == 0
        assert r.failed_count == 0

    def test_test_result_to_dict(self) -> None:
        from simp.projectx.self_test import TestResult
        tr = TestResult(name="test_foo", passed=True, duration_ms=12)
        d = tr.to_dict()
        assert d["name"] == "test_foo"
        assert d["passed"] is True
        assert d["duration_ms"] == 12
        assert "error" not in d or d["error"] is None

    def test_test_result_with_error(self) -> None:
        from simp.projectx.self_test import TestResult
        tr = TestResult(name="test_bar", passed=False, duration_ms=5, error="boom")
        d = tr.to_dict()
        assert d["passed"] is False
        assert d["error"] == "boom"

    def test_self_test_report_to_dict(self) -> None:
        from simp.projectx.self_test import SelfTestReport, TestResult
        r = SelfTestReport()
        r.results.append(TestResult(name="ok", passed=True, duration_ms=1))
        r.results.append(TestResult(name="fail", passed=False, duration_ms=1, error="err"))
        d = r.to_dict()
        assert d["passed"] is False
        assert d["passed_count"] == 1
        assert d["failed_count"] == 1
        assert len(d["results"]) == 2

    def test_self_test_summary_pass(self) -> None:
        from simp.projectx.self_test import SelfTestReport, TestResult
        r = SelfTestReport()
        r.results.append(TestResult(name="ok", passed=True, duration_ms=1))
        summary = r.summary()
        assert "PASS" in summary

    def test_self_test_summary_fail(self) -> None:
        from simp.projectx.self_test import SelfTestReport, TestResult
        r = SelfTestReport()
        r.results.append(TestResult(name="bad", passed=False, duration_ms=1, error="x"))
        summary = r.summary()
        assert "FAIL" in summary

    def test_custom_test_registration(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest(modules=[])  # skip import tests
        st.add_test("custom_passing", lambda: None)
        report = st.run(fast=True)
        names = [r.name for r in report.results]
        assert "custom_passing" in names

    def test_custom_test_failure_reported(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest(modules=[])
        st.add_test("custom_failing", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        report = st.run(fast=True)
        bad = [r for r in report.results if not r.passed]
        assert len(bad) >= 1
        assert any("boom" in (r.error or "") for r in bad)

    def test_fast_mode_runs_fewer_tests(self) -> None:
        from simp.projectx.self_test import SelfTest
        st_fast = SelfTest(modules=[])
        report_fast = st_fast.run(fast=True)
        st_full = SelfTest(modules=[])
        report_full = st_full.run(fast=False)
        # Fast mode should not run integration tests (fewer results)
        assert len(report_fast.results) <= len(report_full.results)

    def test_add_test_name_validation(self) -> None:
        from simp.projectx.self_test import SelfTest
        st = SelfTest(modules=[])
        with pytest.raises(ValueError):
            st.add_test("", lambda: None)  # empty name rejected
        with pytest.raises(ValueError):
            st.add_test("x" * 200, lambda: None)  # too long rejected

    def test_run_self_test_module_level(self) -> None:
        from simp.projectx.self_test import run_self_test
        report = run_self_test(fast=True)
        assert report is not None
        assert isinstance(report.passed, bool)
