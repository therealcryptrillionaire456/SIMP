"""Tests for the shared observability truth helpers."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open


# ── helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_env():
    """Fixture that patches os.environ to include SIMP environment variables."""
    with patch.dict("os.environ", {"SIMP_API_KEY": "test-key"}, clear=True):
        yield


# ── process health ───────────────────────────────────────────────────────────


def test_process_running_found():
    """check_process returns True when pgrep finds the process."""
    from scripts.observability_truth import check_process

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"12345\n")
        assert check_process("broker", r"bin/start_server") is True


def test_process_running_not_found():
    """check_process returns False when pgrep finds nothing."""
    from scripts.observability_truth import check_process

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout=b"")
        assert check_process("broker", r"bin/start_server") is False


def test_process_running_timeout():
    """check_process returns False on subprocess timeout."""
    from subprocess import TimeoutExpired
    from scripts.observability_truth import check_process

    with patch("subprocess.run", side_effect=TimeoutExpired("cmd", 5)):
        assert check_process("broker", r"bin/start_server") is False


# ── freshness ────────────────────────────────────────────────────────────────


def test_tail_ndjson(tmp_path):
    """tail_ndjson reads the last N records from an NDJSON file."""
    from scripts.observability_truth import tail_ndjson

    f = tmp_path / "test.jsonl"
    f.write_text(
        json.dumps({"id": 1}) + "\n"
        + json.dumps({"id": 2}) + "\n"
        + json.dumps({"id": 3}) + "\n"
    )
    records = tail_ndjson(f, n=2)
    assert len(records) == 2
    assert records[0]["id"] == 2
    assert records[1]["id"] == 3


def test_tail_ndjson_empty_file(tmp_path):
    """tail_ndjson returns empty list for an empty file."""
    from scripts.observability_truth import tail_ndjson

    f = tmp_path / "empty.jsonl"
    f.write_text("")
    assert tail_ndjson(f, n=3) == []


def test_tail_ndjson_missing_file():
    """tail_ndjson returns empty list for a missing file."""
    from scripts.observability_truth import tail_ndjson

    assert tail_ndjson(Path("/nonexistent/test.jsonl"), n=3) == []


def test_freshness_age_s():
    """freshness returns seconds since the given ISO timestamp."""
    from scripts.observability_truth import freshness

    # Use a timestamp 5 seconds in the past
    import datetime
    five_sec_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)).isoformat()
    age = freshness(five_sec_ago)
    assert 3.0 < age < 10.0  # ~5 seconds, with some tolerance
    assert isinstance(age, float)


# ── stage verification ───────────────────────────────────────────────────────


def test_verifier_stage_result():
    """StageResult holds and reports stage status correctly."""
    from scripts.observability_truth import StageResult

    s = StageResult(name="test_stage", ok=True, detail="all good")
    assert s.name == "test_stage"
    assert s.ok is True
    assert s.detail == "all good"
    assert s.terminal_ok is True

    s2 = StageResult(name="test_fail", ok=False, detail="something wrong")
    assert s2.ok is False
    assert s2.terminal_ok is False
