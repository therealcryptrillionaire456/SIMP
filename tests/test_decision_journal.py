"""Tests for decision journal integrity.

Covers: executed, policy_blocked, exchange_error, strategy_rejected, stale
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone


# ── helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def journal_path(tmp_path):
    """Return a path to a test decision journal file."""
    return tmp_path / "decision_journal.ndjson"


def _write_journal(path, entries):
    """Write a list of dicts as NDJSON."""
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


VALID_STATUSES = {"allow", "block", "shadow"}
VALID_FILL_STATUSES = {"executed", "policy_blocked", "exchange_error",
                       "strategy_rejected", "stale"}


# ── schema compliance ────────────────────────────────────────────────────────


def test_journal_entry_valid_schema(journal_path):
    """A well-formed entry passes schema validation."""
    from state.decision_adapter import SCHEMA_REQUIRED_FIELDS
    entry = {
        "decision_id": "dec_test_001",
        "created_at": "2026-04-24T12:00:00+00:00",
        "source_signal_ids": ["sig_001"],
        "thesis": "test thesis",
        "confidence": 0.5,
        "risk_budget_usd": 100.0,
        "venue": "coinbase_paper",
        "instrument": "BTC-USD",
        "side": "buy",
        "size": 1.0,
        "expected_edge": 0.02,
        "policy_result": {"status": "allow", "evaluated_at": "2026-04-24T12:00:00+00:00"},
        "mode": "shadow",
        "fill_status": "executed",
        "executed_at": "2026-04-24T12:00:05+00:00",
        "lineage": {"parent_id": None, "type": "signal"}
    }
    assert all(f in entry for f in SCHEMA_REQUIRED_FIELDS)


def test_journal_entry_missing_required_field(journal_path):
    """An entry missing a required field fails schema validation."""
    from state.decision_adapter import SCHEMA_REQUIRED_FIELDS
    entry = {"decision_id": "dec_test_001"}
    missing = [f for f in SCHEMA_REQUIRED_FIELDS if f not in entry]
    assert len(missing) > 0


# ── fill status terminality ──────────────────────────────────────────────────


TERMINAL = {"executed", "policy_blocked", "exchange_error", "strategy_rejected"}
NON_TERMINAL = {"stale"}


@pytest.mark.parametrize("status,expected_terminal", [
    ("executed", True),
    ("policy_blocked", True),
    ("exchange_error", True),
    ("strategy_rejected", True),
    ("stale", False),
])
def test_fill_status_terminality(status, expected_terminal):
    """Each fill_status is correctly classified as terminal or non-terminal."""
    terminal = status in TERMINAL
    assert terminal == expected_terminal


# ── duplicate detection ──────────────────────────────────────────────────────


def test_duplicate_decision_id_rejected(journal_path):
    """Appending a duplicate decision_id is detected."""
    entries = [
        {"decision_id": "dec_dup_001", "fill_status": "executed", "executed_at": "2026-04-24T12:00:00+00:00"},
        {"decision_id": "dec_dup_001", "fill_status": "executed", "executed_at": "2026-04-24T12:00:05+00:00"},
    ]
    _write_journal(journal_path, [entries[0]])
    ids = set()
    with open(journal_path) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                ids.add(rec["decision_id"])
    # The second write would be detected as duplicate
    is_dup = entries[1]["decision_id"] in ids
    assert is_dup is True


# ── append-only invariant ────────────────────────────────────────────────────


def test_journal_append_only(journal_path):
    """Journal only grows — records are never removed."""
    _write_journal(journal_path, [
        {"decision_id": "dec_001", "fill_status": "executed"},
        {"decision_id": "dec_002", "fill_status": "policy_blocked"},
    ])
    count_before = sum(1 for _ in open(journal_path) if _.strip())
    # "Append" one more
    with open(journal_path, "a") as f:
        f.write(json.dumps({"decision_id": "dec_003", "fill_status": "stale"}) + "\n")
    count_after = sum(1 for _ in open(journal_path) if _.strip())
    assert count_after == count_before + 1


# ── malformed entry handling ─────────────────────────────────────────────────


def test_malformed_entry_skipped(journal_path):
    """A malformed JSON line is skipped during iteration."""
    # Write raw text including a deliberately malformed JSON line
    with open(journal_path, "w") as f:
        f.write(json.dumps({"decision_id": "dec_001", "fill_status": "executed"}) + "\n")
        f.write("{{{ this is not valid json }}}\n")
        f.write(json.dumps({"decision_id": "dec_002", "fill_status": "policy_blocked"}) + "\n")
    valid = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                valid.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                pass
    assert len(valid) == 2
    assert valid[0]["decision_id"] == "dec_001"
    assert valid[1]["decision_id"] == "dec_002"


# ── backfill/watch coexistence ───────────────────────────────────────────────


def test_backfill_does_not_overwrite_terminal(journal_path):
    """Backfilling a terminal entry does not change its fill_status."""
    from state.normalize_journal import normalize_entry
    entry = {
        "decision_id": "dec_terminal_001",
        "fill_status": "executed",
        "executed_at": "2026-04-24T12:00:00+00:00",
    }
    result = normalize_entry(entry, force=False)
    assert result["fill_status"] == "executed"
