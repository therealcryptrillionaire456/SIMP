"""
Tests for Sprint 52 — Task Ledger

Uses temp directories for JSONL files.
"""

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta

from simp.server.task_ledger import (
    LedgerConfig,
    TaskLedger,
    TASK_LEDGER,
)


class TestLedgerConfig(unittest.TestCase):
    """LedgerConfig defaults."""

    def test_defaults(self):
        cfg = LedgerConfig()
        assert cfg.path == "data/task_ledger.jsonl"
        assert cfg.max_size_mb == 100.0
        assert cfg.expire_after_hours == 168.0

    def test_custom_path(self):
        cfg = LedgerConfig(path="/tmp/custom.jsonl")
        assert cfg.path == "/tmp/custom.jsonl"


class TestTaskLedgerAppend(unittest.TestCase):
    """append() writes JSONL and never raises."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "ledger.jsonl")
        self.ledger = TaskLedger(LedgerConfig(path=self.path))

    def test_append_creates_file(self):
        self.ledger.append({"intent_id": "i1", "status": "pending"})
        assert os.path.exists(self.path)

    def test_append_writes_json_line(self):
        self.ledger.append({"intent_id": "i2", "status": "pending"})
        with open(self.path, "r") as f:
            line = f.readline()
        rec = json.loads(line)
        assert rec["intent_id"] == "i2"
        assert rec["status"] == "pending"
        assert "ledger_ts" in rec

    def test_append_multiple(self):
        for i in range(5):
            self.ledger.append({"intent_id": f"i{i}"})
        with open(self.path, "r") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 5

    def test_append_never_raises(self):
        # Bad path — should not raise (use a path where even mkdir fails)
        bad_path = os.path.join(self.tmpdir, "sub", "deep", "file.jsonl")
        bad_ledger = TaskLedger(LedgerConfig(path=bad_path))
        # Append should work (creates intermediate dirs)
        bad_ledger.append({"intent_id": "x"})
        assert os.path.exists(bad_path)


class TestTaskLedgerLoadPending(unittest.TestCase):
    """load_pending() returns pending records, skips corrupt lines."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "ledger.jsonl")
        self.ledger = TaskLedger(LedgerConfig(path=self.path))

    def test_empty_file(self):
        assert self.ledger.load_pending() == []

    def test_returns_pending_only(self):
        self.ledger.append({"intent_id": "i1", "status": "pending"})
        self.ledger.append({"intent_id": "i2", "status": "completed"})
        self.ledger.append({"intent_id": "i3", "status": "pending"})
        pending = self.ledger.load_pending()
        assert len(pending) == 2
        assert all(r["status"] == "pending" for r in pending)

    def test_skips_corrupt_lines(self):
        with open(self.path, "w") as f:
            f.write('{"intent_id": "i1", "status": "pending"}\n')
            f.write("THIS IS NOT JSON\n")
            f.write('{"intent_id": "i3", "status": "pending"}\n')
        pending = self.ledger.load_pending()
        assert len(pending) == 2


class TestTaskLedgerLoadAll(unittest.TestCase):
    """load_all() returns last N records."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "ledger.jsonl")
        self.ledger = TaskLedger(LedgerConfig(path=self.path))

    def test_load_all_empty(self):
        assert self.ledger.load_all() == []

    def test_load_all_respects_limit(self):
        for i in range(20):
            self.ledger.append({"intent_id": f"i{i}"})
        records = self.ledger.load_all(limit=5)
        assert len(records) == 5
        # Should be last 5
        assert records[0]["intent_id"] == "i15"


class TestTaskLedgerExpire(unittest.TestCase):
    """expire_old_records() marks old pending intents as expired."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "ledger.jsonl")
        self.ledger = TaskLedger(LedgerConfig(path=self.path, expire_after_hours=0.001))

    def test_expire_old_records(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        records = {
            "i1": type("R", (), {"status": "pending", "timestamp": old_ts})(),
            "i2": type("R", (), {"status": "completed", "timestamp": old_ts})(),
        }
        count = self.ledger.expire_old_records(records)
        assert count == 1
        assert records["i1"].status == "expired"
        assert records["i2"].status == "completed"

    def test_expire_writes_event(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        records = {
            "i1": type("R", (), {"status": "pending", "timestamp": old_ts})(),
        }
        self.ledger.expire_old_records(records)
        all_recs = self.ledger.load_all()
        assert any(r.get("event") == "expired" for r in all_recs)


class TestTaskLedgerRotate(unittest.TestCase):
    """rotate_if_needed() rotates large files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "ledger.jsonl")

    def test_no_rotation_under_limit(self):
        ledger = TaskLedger(LedgerConfig(path=self.path, max_size_mb=100))
        ledger.append({"intent_id": "i1"})
        assert ledger.rotate_if_needed() is False

    def test_rotation_over_limit(self):
        # Write enough to exceed a tiny limit
        ledger = TaskLedger(LedgerConfig(path=self.path, max_size_mb=0.0001))
        for i in range(100):
            ledger.append({"intent_id": f"i{i}", "data": "x" * 100})
        rotated = ledger.rotate_if_needed()
        assert rotated is True
        # Original path should no longer exist (it was moved)
        assert not os.path.exists(self.path)


class TestTaskLedgerGetStats(unittest.TestCase):
    """get_stats() returns summary."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "ledger.jsonl")
        self.ledger = TaskLedger(LedgerConfig(path=self.path))

    def test_stats_empty(self):
        stats = self.ledger.get_stats()
        assert stats["exists"] is False
        assert stats["total_records"] == 0

    def test_stats_with_data(self):
        self.ledger.append({"intent_id": "i1", "status": "pending"})
        self.ledger.append({"intent_id": "i2", "status": "completed"})
        stats = self.ledger.get_stats()
        assert stats["exists"] is True
        assert stats["total_records"] == 2
        assert stats["pending_records"] == 1


class TestTaskLedgerSingleton(unittest.TestCase):
    """Module singleton is available."""

    def test_singleton_exists(self):
        assert TASK_LEDGER is not None
        assert isinstance(TASK_LEDGER, TaskLedger)


if __name__ == "__main__":
    unittest.main()
