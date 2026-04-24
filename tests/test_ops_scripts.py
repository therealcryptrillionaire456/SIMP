"""Tests for operator scripts (verify_revenue_path, inject_quantum_signal)."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import inject_quantum_signal  # noqa: E402
import verify_revenue_path  # noqa: E402


def test_build_signal_uses_gate4_shape() -> None:
    signal = inject_quantum_signal.build_signal(
        asset="BTC-USD",
        side="sell",
        position_usd=2.52,
        source="test_suite",
        metadata={"ticket": "abc123"},
        signal_id="sig-1",
    )

    assert signal["signal_id"] == "sig-1"
    assert signal["signal_type"] == "portfolio_allocation"
    assert signal["assets"]["BTC-USD"]["action"] == "sell"
    assert signal["assets"]["BTC-USD"]["position_usd"] == 2.52
    assert signal["metadata"]["ticket"] == "abc123"


def test_verify_revenue_path_run_returns_report(monkeypatch) -> None:
    """Verify that run() returns a VerifyReport with expected structure."""

    # Prevent loading real state files during test
    def _no_file(*args, **kwargs):
        return None

    def _empty_list(*args, **kwargs):
        return []

    # Mock file reads so stages don't crash on missing files
    monkeypatch.setattr(verify_revenue_path, "_tail_ndjson", lambda p, n: [])

    # Mock kill switch check — not set
    monkeypatch.setattr(verify_revenue_path, "_process_is_up", lambda p: True)

    # Mock mode
    monkeypatch.setattr(verify_revenue_path, "_load_mode", lambda: "fully_live")

    # Mock limits
    monkeypatch.setattr(verify_revenue_path, "_load_limits", lambda: {"slo": {"signal_max_age": 60, "fill_max_age": 120}})

    # Mock subprocess calls for process / bridge checks
    def _mock_run(*args, **kwargs):
        class FakeResult:
            stdout = ""
            stderr = ""
            returncode = 0
        return FakeResult()
    monkeypatch.setattr(verify_revenue_path.subprocess, "run", _mock_run)

    # Mock datetime for freshness checks
    class _FrozenDatetime:
        @classmethod
        def now(cls, tz=None):
            import datetime as _dt
            return _dt.datetime(2026, 4, 21, 10, 55, 0, tzinfo=tz)

        @classmethod
        def fromisoformat(cls, value):
            import datetime as _dt
            return _dt.datetime.fromisoformat(value)

    monkeypatch.setattr(verify_revenue_path, "datetime", _FrozenDatetime)

    # Run the verifier
    report = verify_revenue_path.run()

    # Assert structure
    assert report is not None
    assert hasattr(report, "green")
    assert hasattr(report, "stages")
    assert hasattr(report, "fatal_stage")

    # All stages should be present (12 stages)
    assert len(report.stages) == 12

    # Verify all stages have required attributes
    for stage in report.stages:
        assert hasattr(stage, "name")
        assert hasattr(stage, "ok")
        assert hasattr(stage, "terminal_ok")
        assert hasattr(stage, "detail")

    # Should be green since we mocked everything healthy
    assert report.green is True
