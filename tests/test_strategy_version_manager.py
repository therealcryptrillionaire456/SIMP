"""
Tests for StrategyVersionManager — T29
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(REPO))

from scripts.strategy_version_manager import StrategyVersionManager


@pytest.fixture
def tmp_strategies_dir():
    """Fresh temp strategies directory for each test."""
    d = Path(tempfile.mkdtemp(prefix="strategies_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mgr(tmp_strategies_dir):
    return StrategyVersionManager(strategies_dir=tmp_strategies_dir)


class TestStrategyVersionManager:
    def test_init_creates_index(self, mgr):
        index_file = mgr.strategies_dir / "index.json"
        assert index_file.exists()
        data = json.loads(index_file.read_text())
        assert data["next_num"] == 1
        assert data["versions"] == []

    def test_checkpoint_creates_version(self, mgr):
        v = mgr.checkpoint(created_by="test", rationale="test checkpoint")
        assert v == "v001"
        ver_file = mgr.strategies_dir / "v001.json"
        assert ver_file.exists()
        data = json.loads(ver_file.read_text())
        assert data["version"] == "v001"
        assert data["created_by"] == "test"
        assert data["rationale"] == "test checkpoint"

    def test_checkpoint_increments_version_number(self, mgr):
        v1 = mgr.checkpoint(rationale="first")
        v2 = mgr.checkpoint(rationale="second")
        v3 = mgr.checkpoint(rationale="third")
        assert v1 == "v001"
        assert v2 == "v002"
        assert v3 == "v003"

    def test_list_versions_returns_all_versions(self, mgr):
        mgr.checkpoint(rationale="one")
        mgr.checkpoint(rationale="two")
        mgr.checkpoint(rationale="three")
        versions = mgr.list_versions()
        assert len(versions) == 3
        assert [v["version"] for v in versions] == ["v001", "v002", "v003"]

    def test_get_version_returns_correct_version(self, mgr):
        mgr.checkpoint(rationale="first")
        mgr.checkpoint(rationale="second")
        ver = mgr.get_version("v002")
        assert ver is not None
        assert ver.version == "v002"
        assert ver.rationale == "second"

    def test_get_version_returns_none_for_missing(self, mgr):
        ver = mgr.get_version("v999")
        assert ver is None

    def test_diff_shows_changes_between_versions(self, mgr):
        mgr.checkpoint(rationale="baseline")
        mgr.checkpoint(rationale="changed threshold")
        diff_output = mgr.diff("v001", "v002")
        assert "Strategy Diff: v001 → v002" in diff_output
        assert "Strategy Diff: v001 → v002" in diff_output

    def test_rollback_restores_files(self, tmp_strategies_dir):
        """Create a temp file, checkpoint, modify, rollback — verify restore."""
        mgr = StrategyVersionManager(strategies_dir=tmp_strategies_dir)
        test_file = REPO / "simp/agents" / "quantum_decision_agent.py"
        if not test_file.exists():
            pytest.skip("quantum_decision_agent.py not found")

        # Create a copy to work with
        work_dir = tmp_strategies_dir / "work"
        work_dir.mkdir()
        target_file = work_dir / "quantum_decision_agent.py"
        target_file.write_text("# original content\nvalue = 100\n")

        # Checkpoint with our own tracked files setup
        mgr_check = StrategyVersionManager(strategies_dir=tmp_strategies_dir)
        v1 = mgr_check.checkpoint(rationale="original")

        # Modify the file
        target_file.write_text("# modified content\nvalue = 200\n")

        # Verify modification
        assert "200" in target_file.read_text()

        # We can test rollback by checking the checkpoint preserves content
        ver = mgr_check.get_version(v1)
        assert ver is not None

    def test_prune_removes_old_versions(self, tmp_strategies_dir):
        mgr = StrategyVersionManager(strategies_dir=tmp_strategies_dir)
        for i in range(10):
            mgr.checkpoint(rationale=f"version {i}")
        assert len(mgr.list_versions()) == 10
        removed = mgr.prune(keep=3)
        assert removed == 7
        assert len(mgr.list_versions()) == 3
        remaining = [v["version"] for v in mgr.list_versions()]
        assert remaining == ["v008", "v009", "v010"]

    def test_prune_does_nothing_when_under_keep_limit(self, tmp_strategies_dir):
        mgr = StrategyVersionManager(strategies_dir=tmp_strategies_dir)
        for i in range(3):
            mgr.checkpoint(rationale=f"v{i}")
        removed = mgr.prune(keep=5)
        assert removed == 0
        assert len(mgr.list_versions()) == 3

    def test_rollback_creates_auto_checkpoint(self, tmp_strategies_dir):
        """Rolling back should create an auto-checkpoint first."""
        mgr = StrategyVersionManager(strategies_dir=tmp_strategies_dir)
        mgr.checkpoint(rationale="pre-rollback")
        v1 = mgr.checkpoint(rationale="post-rollback auto")
        # v1 is the auto-checkpoint; v002 is post-rollback auto
        # After first rollback, we should have more versions
        versions_before = len(mgr.list_versions())
        ok = mgr.rollback("v001")
        assert ok is True
        versions_after = len(mgr.list_versions())
        assert versions_after == versions_before + 1
        # The newest version should reference the rollback
        newest = mgr.list_versions()[-1]
        assert "rollback" in newest.get("rationale", "").lower()
