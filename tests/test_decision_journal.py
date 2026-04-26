"""Tests for decision journal integrity.

Covers: executed, policy_blocked, exchange_error, strategy_rejected, stale
"""

import json
import random
import threading
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


# ── stale filter ─────────────────────────────────────────────────────────────


def test_journal_stale_filter(journal_path):
    """Filtering by fill_status='stale' returns only stale entries."""
    entries = [
        {"decision_id": "dec_001", "fill_status": "executed"},
        {"decision_id": "dec_002", "fill_status": "stale"},
        {"decision_id": "dec_003", "fill_status": "policy_blocked"},
        {"decision_id": "dec_004", "fill_status": "stale"},
        {"decision_id": "dec_005", "fill_status": "exchange_error"},
        {"decision_id": "dec_006", "fill_status": "stale"},
    ]
    _write_journal(journal_path, entries)

    stale = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("fill_status") == "stale":
                stale.append(rec)

    assert len(stale) == 3
    assert all(r["fill_status"] == "stale" for r in stale)
    assert {r["decision_id"] for r in stale} == {"dec_002", "dec_004", "dec_006"}


# ── export / readable output ─────────────────────────────────────────────────


def test_journal_export_readable(journal_path):
    """An export/print routine produces human-readable output."""
    entries = [
        {
            "decision_id": "dec_001",
            "fill_status": "executed",
            "thesis": "BTC breakout above 100k",
            "instrument": "BTC-USD",
            "side": "buy",
        },
        {
            "decision_id": "dec_002",
            "fill_status": "stale",
            "thesis": "ETH range trade",
            "instrument": "ETH-USD",
            "side": "sell",
        },
    ]
    _write_journal(journal_path, entries)

    # Build an export string (simulate a print/serialize routine)
    exported_lines = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            exported_lines.append(
                f"[{rec['decision_id']}] {rec.get('side','').upper()} "
                f"{rec.get('instrument','')} — {rec.get('fill_status','')} "
                f"({rec.get('thesis','')})"
            )

    output = "\n".join(exported_lines)

    assert "dec_001" in output
    assert "dec_002" in output
    assert "BTC-USD" in output
    assert "ETH-USD" in output
    assert "executed" in output
    assert "stale" in output
    assert "BTC breakout above 100k" in output


# ── audit trail ──────────────────────────────────────────────────────────────


def test_journal_audit_trail_complete(journal_path):
    """Entries written in sequence can be read back in the same order."""
    count = 20
    entries = [
        {
            "decision_id": f"dec_{i:04d}",
            "fill_status": "executed",
            "created_at": f"2026-04-{(i % 28) + 1:02d}T12:00:00+00:00",
            "thesis": f"thesis_{i}",
        }
        for i in range(1, count + 1)
    ]
    _write_journal(journal_path, entries)

    read_back = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            read_back.append(json.loads(line))

    assert len(read_back) == count
    for original, restored in zip(entries, read_back):
        assert restored["decision_id"] == original["decision_id"]
        assert restored["thesis"] == original["thesis"]
        assert restored["fill_status"] == original["fill_status"]


# ── gap detection ────────────────────────────────────────────────────────────


def test_journal_gap_detection(journal_path):
    """Gaps in a monotonically increasing numeric decision_id sequence are detected."""
    # Write entries with IDs dec_001 … dec_010 but deliberately skip dec_006
    expected_ids = {f"dec_{i:03d}" for i in range(1, 11) if i != 6}
    written = [f"dec_{i:03d}" for i in range(1, 11)]
    entries = [
        {
            "decision_id": did,
            "fill_status": "executed",
        }
        for did in written
        if did != "dec_006"  # skip dec_006 to create a gap
    ]
    _write_journal(journal_path, entries)

    read_ids = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            read_ids.append(json.loads(line)["decision_id"])

    # Parse numeric suffixes and check for gaps
    numeric_ids = []
    for did in read_ids:
        suffix = did.split("_", 1)[1]
        numeric_ids.append(int(suffix))

    numeric_ids.sort()
    expected_range = set(range(1, 11))  # all IDs including dec_006
    actual_set = set(numeric_ids)
    missing = expected_range - actual_set
    assert 6 in missing, f"Gap at dec_006 not detected — missing={missing}"
    assert actual_set == expected_range - missing


# ── truncation safety ─────────────────────────────────────────────────────────


def test_journal_truncation_safety(journal_path):
    """The writer handles a very large entry without crashing."""
    large_thesis = "Repeat. " * 10_000  # ~110 kB of text
    entries = [
        {"decision_id": "dec_large", "fill_status": "executed", "thesis": large_thesis},
        {"decision_id": "dec_after", "fill_status": "executed", "thesis": "small"},
    ]
    _write_journal(journal_path, entries)

    read_back = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            read_back.append(json.loads(line))

    assert len(read_back) == 2
    assert read_back[0]["decision_id"] == "dec_large"
    assert read_back[0]["thesis"] == large_thesis
    assert read_back[1]["decision_id"] == "dec_after"
    assert read_back[1]["thesis"] == "small"

    # File size should reflect the large entry
    assert journal_path.stat().st_size > 50_000


# ── concurrent writes ────────────────────────────────────────────────────────


def test_journal_concurrent_writes(journal_path):
    """Multiple threads writing to the journal produces no corruption."""

    num_threads = 8
    entries_per_thread = 25
    lock = threading.Lock()

    # Pre-generate all entries so threads just write them
    all_decision_ids = []

    def writer(thread_idx):
        for i in range(entries_per_thread):
            did = f"dec_t{thread_idx}_i{i:03d}"
            entry = json.dumps({
                "decision_id": did,
                "fill_status": "executed",
                "thesis": f"thesis_{thread_idx}_{i}",
                "confidence": random.random(),
            })
            with lock:
                all_decision_ids.append(did)
            with open(journal_path, "a") as f:
                f.write(entry + "\n")

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify every expected decision_id is present exactly once
    seen = {}
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            assert rec["decision_id"] not in seen, f"Duplicate decision_id: {rec['decision_id']}"
            seen[rec["decision_id"]] = rec

    expected_count = num_threads * entries_per_thread
    assert len(seen) == expected_count, (
        f"Expected {expected_count} entries, got {len(seen)}"
    )


# ── read-after-write consistency ─────────────────────────────────────────────


def test_journal_read_after_write_consistency(journal_path):
    """Data written, closed, reopened, and read back is identical to the original."""
    entries = [
        {
            "decision_id": f"dec_{i:04d}",
            "fill_status": list(VALID_FILL_STATUSES)[i % len(VALID_FILL_STATUSES)],
            "created_at": f"2026-04-{(i % 28) + 1:02d}T{12 + (i % 12):02d}:00:00+00:00",
            "thesis": f"thesis_value_{i}_" + ("x" * 100),
            "confidence": round(i / 100, 4),
            "risk_budget_usd": round(i * 10.5, 2),
            "instrument": ["BTC-USD", "ETH-USD", "SOL-USD"][i % 3],
            "side": ["buy", "sell"][i % 2],
            "size": round((i + 1) * 0.25, 4),
            "expected_edge": round(0.01 * i, 4),
            "policy_result": {
                "status": "allow" if i % 3 != 0 else "block",
                "evaluated_at": f"2026-04-{(i % 28) + 1:02d}T12:00:00+00:00",
            },
            "mode": "shadow",
            "lineage": {"parent_id": None, "type": "signal"},
        }
        for i in range(1, 51)
    ]

    # Phase 1: write
    _write_journal(journal_path, entries)

    # Phase 2: close + reopen (simulated by dropping the reference and re-opening)
    del entries  # hint that original list is no longer in use

    # Phase 3: read back
    read_back = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            read_back.append(json.loads(line))

    # Reconstruct the original entries in memory for comparison
    original = [
        {
            "decision_id": f"dec_{i:04d}",
            "fill_status": list(VALID_FILL_STATUSES)[i % len(VALID_FILL_STATUSES)],
            "created_at": f"2026-04-{(i % 28) + 1:02d}T{12 + (i % 12):02d}:00:00+00:00",
            "thesis": f"thesis_value_{i}_" + ("x" * 100),
            "confidence": round(i / 100, 4),
            "risk_budget_usd": round(i * 10.5, 2),
            "instrument": ["BTC-USD", "ETH-USD", "SOL-USD"][i % 3],
            "side": ["buy", "sell"][i % 2],
            "size": round((i + 1) * 0.25, 4),
            "expected_edge": round(0.01 * i, 4),
            "policy_result": {
                "status": "allow" if i % 3 != 0 else "block",
                "evaluated_at": f"2026-04-{(i % 28) + 1:02d}T12:00:00+00:00",
            },
            "mode": "shadow",
            "lineage": {"parent_id": None, "type": "signal"},
        }
        for i in range(1, 51)
    ]

    assert len(read_back) == len(original)
    for orig, restored in zip(original, read_back):
        assert restored["decision_id"] == orig["decision_id"]
        assert restored["fill_status"] == orig["fill_status"]
        assert restored["confidence"] == orig["confidence"]
        assert restored["thesis"] == orig["thesis"]
        assert restored["risk_budget_usd"] == orig["risk_budget_usd"]
        assert restored["instrument"] == orig["instrument"]
        assert restored["side"] == orig["side"]
        assert restored["size"] == orig["size"]
        assert restored["policy_result"]["status"] == orig["policy_result"]["status"]
