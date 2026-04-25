"""
Strategy Version Manager — T29
=============================
Versions all decision criteria and config changes so they can be rolled back.
Every change to go_criteria, safety_backstop config, or capital weights is snapshotted.

Commands:
  python3 scripts/strategy_version_manager.py --list
  python3 scripts/strategy_version_manager.py --diff v001 v002
  python3 scripts/strategy_version_manager.py --rollback v001
  python3 scripts/strategy_version_manager.py --checkpoint "reason for change"
  python3 scripts/strategy_version_manager.py --prune 50
"""

from __future__ import annotations

import difflib
import json
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("strategy_version_manager")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

STRATEGIES_DIR = REPO / "data" / "strategies"
TRACKED_FILES = [
    REPO / "simp/agents/quantum_decision_agent.py",
    REPO / "simp/organs/quantumarb/safety_backstop.py",
    REPO / "simp/organs/quantumarb/capital_allocator.py",
    REPO / "simp/organs/quantumarb/confidence_calibrator.py",
    REPO / "config/current_trading_config.json",
]


@dataclass
class StrategyVersion:
    """A single strategy snapshot with all criteria and config files."""
    version: str
    created_at: str
    created_by: str  # "operator" or agent name
    rationale: str
    files: Dict[str, str]  # filename (relative) -> content snapshot
    criteria_snapshot: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyVersionManager:
    """
    Manages strategy versions and rollbacks.

    Every criteria/config change creates a versioned snapshot.
    Rollback restores files to a previous version.
    """

    def __init__(self, strategies_dir: Path = STRATEGIES_DIR):
        self.strategies_dir = strategies_dir
        self.strategies_dir.mkdir(parents=True, exist_ok=True)
        self._init_index()

    def _init_index(self) -> None:
        index_file = self.strategies_dir / "index.json"
        if not index_file.exists():
            with open(index_file, "w") as f:
                json.dump({"versions": [], "next_num": 1}, f)

    def _read_index(self) -> Dict[str, Any]:
        with open(self.strategies_dir / "index.json") as f:
            return json.load(f)

    def _write_index(self, data: Dict[str, Any]) -> None:
        with open(self.strategies_dir / "index.json", "w") as f:
            json.dump(data, f, indent=2)

    def checkpoint(
        self,
        created_by: str = "operator",
        rationale: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new strategy version snapshot.
        Returns the version string (e.g., "v001").
        """
        index = self._read_index()
        next_num = index["next_num"]
        version = f"v{next_num:03d}"

        # Snapshot all tracked files
        files: Dict[str, str] = {}
        for fpath in TRACKED_FILES:
            if fpath.exists():
                try:
                    with open(fpath) as f:
                        files[str(fpath.relative_to(REPO))] = f.read()
                except Exception as e:
                    log.warning(f"Could not snapshot {fpath}: {e}")

        # Snapshot criteria from quantum_decision_agent
        criteria = self._snapshot_criteria()

        ver = StrategyVersion(
            version=version,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
            rationale=rationale,
            files=files,
            criteria_snapshot=criteria,
            metadata=metadata or {},
        )

        # Write version file
        ver_file = self.strategies_dir / f"{version}.json"
        with open(ver_file, "w") as f:
            json.dump(
                {
                    "version": ver.version,
                    "created_at": ver.created_at,
                    "created_by": ver.created_by,
                    "rationale": ver.rationale,
                    "files": ver.files,
                    "criteria_snapshot": ver.criteria_snapshot,
                    "metadata": ver.metadata,
                },
                f,
                indent=2,
            )

        # Update index
        index["versions"].append(
            {
                "version": version,
                "created_at": ver.created_at,
                "created_by": ver.created_by,
                "rationale": ver.rationale,
            }
        )
        index["next_num"] = next_num + 1
        self._write_index(index)

        log.info(f"Strategy checkpoint created: {version}")
        return version

    def _snapshot_criteria(self) -> Dict[str, Any]:
        """Extract current go_criteria from quantum_decision_agent."""
        criteria: Dict[str, Any] = {}
        agent_file = REPO / "simp/agents/quantum_decision_agent.py"
        if not agent_file.exists():
            return criteria
        try:
            content = agent_file.read_text()
            import ast

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and "CRITERIA" in target.id.upper():
                            criteria[target.id] = ast.literal_eval(node.value)
        except Exception as e:
            log.warning(f"Could not parse criteria from agent: {e}")
        return criteria

    def list_versions(self) -> List[Dict[str, str]]:
        """List all strategy versions."""
        index = self._read_index()
        return index.get("versions", [])

    def get_version(self, version: str) -> Optional[StrategyVersion]:
        """Load a specific version."""
        ver_file = self.strategies_dir / f"{version}.json"
        if not ver_file.exists():
            log.error(f"Version file not found: {ver_file}")
            return None
        with open(ver_file) as f:
            data = json.load(f)
        return StrategyVersion(**data)

    def diff(self, version_a: str, version_b: str) -> str:
        """Generate a human-readable diff between two versions."""
        ver_a = self.get_version(version_a)
        ver_b = self.get_version(version_b)
        if not ver_a:
            return f"Version not found: {version_a}"
        if not ver_b:
            return f"Version not found: {version_b}"

        lines = [
            f"Strategy Diff: {version_a} → {version_b}",
            "=" * 60,
            f"Created:  {ver_a.created_at}  →  {ver_b.created_at}",
            f"By:       {ver_a.created_by}  →  {ver_b.created_by}",
            f"Rationale: {ver_a.rationale}  →  {ver_b.rationale}",
            "=" * 60,
            "",
        ]

        all_files = set(ver_a.files.keys()) | set(ver_b.files.keys())
        for fname in sorted(all_files):
            f_a = ver_a.files.get(fname, "")
            f_b = ver_b.files.get(fname, "")
            if f_a != f_b:
                diff = list(
                    difflib.unified_diff(
                        f_a.splitlines(keepends=True),
                        f_b.splitlines(keepends=True),
                        fromfile=f"{version_a}:{fname}",
                        tofile=f"{version_b}:{fname}",
                        lineterm="",
                    )
                )
                lines.append(f"--- {fname}")
                lines.append(f"+++ {fname}")
                lines.extend(diff)

        # Criteria diff
        if ver_a.criteria_snapshot != ver_b.criteria_snapshot:
            lines.append("")
            lines.append("Criteria changes:")
            all_keys = set(ver_a.criteria_snapshot.keys()) | set(ver_b.criteria_snapshot.keys())
            for key in sorted(all_keys):
                a_val = ver_a.criteria_snapshot.get(key, "<missing>")
                b_val = ver_b.criteria_snapshot.get(key, "<missing>")
                if a_val != b_val:
                    lines.append(f"  {key}: {a_val}  →  {b_val}")

        return "\n".join(lines)

    def rollback(self, target_version: str) -> bool:
        """
        Roll back to a previous strategy version.
        Restores all tracked files and criteria.
        """
        ver = self.get_version(target_version)
        if not ver:
            log.error(f"Version not found: {target_version}")
            return False

        # Create rollback checkpoint first
        self.checkpoint(
            created_by="system",
            rationale=f"Auto-checkpoint before rollback to {target_version}",
        )

        # Restore files
        for rel_path, content in ver.files.items():
            fpath = REPO / rel_path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            if fpath.exists():
                backup = fpath.with_suffix(f"{fpath.suffix}.rbk_{int(time.time())}")
                shutil.copy2(fpath, backup)
                log.info(f"Backed up: {rel_path} → {backup.name}")
            with open(fpath, "w") as f:
                f.write(content)
            log.info(f"Restored: {rel_path}")

        log.info(f"Rollback complete: now at {target_version}")
        return True

    def prune(self, keep: int = 50) -> int:
        """Remove old versions beyond the keep limit."""
        index = self._read_index()
        versions = index.get("versions", [])
        if len(versions) <= keep:
            return 0

        removed = 0
        to_remove = versions[:-keep]
        for ver_entry in to_remove:
            v = ver_entry["version"]
            ver_file = self.strategies_dir / f"{v}.json"
            if ver_file.exists():
                ver_file.unlink()
                removed += 1

        index["versions"] = versions[-keep:]
        self._write_index(index)
        log.info(f"Pruned {removed} old versions, kept {keep}")
        return removed


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description="Strategy Version Manager — T29")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--diff", nargs=2, metavar=("VERSION_A", "VERSION_B"))
    parser.add_argument("--rollback", metavar="VERSION")
    parser.add_argument("--checkpoint", nargs="?", const="manual checkpoint")
    parser.add_argument("--prune", type=int, nargs="?", const=50)
    args = parser.parse_args()

    mgr = StrategyVersionManager()

    if args.list:
        for v in mgr.list_versions():
            print(
                f"  {v['version']}  {v['created_at']}  {v['created_by']}  {v.get('rationale', '')}"
            )
    elif args.diff:
        print(mgr.diff(args.diff[0], args.diff[1]))
    elif args.rollback:
        ok = mgr.rollback(args.rollback)
        print(f"Rollback {'successful' if ok else 'FAILED'}")
    elif args.checkpoint is not None:
        v = mgr.checkpoint(rationale=args.checkpoint)
        print(f"Checkpoint created: {v}")
    elif args.prune is not None:
        n = mgr.prune(args.prune)
        print(f"Pruned {n} versions")
    else:
        parser.print_help()
