#!/usr/bin/env python3
"""
A0 — Ownership Matrix Enforcement Checker

Reads contracts/ownership_matrix.md and validates that no two agents
have overlapping "Write" ownership of the same file or directory.
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parent.parent
MATRIX_PATH = REPO / "contracts" / "ownership_matrix.md"


def parse_ownership_matrix(path: Path):
    """Extract agent->write paths table from ownership_matrix.md."""
    if not path.exists():
        print(f"[ERROR] Ownership matrix not found at {path}")
        return {}

    text = path.read_text()
    ownership = {}

    # Find tables: look for lines with | Agent | Write | Read | Propose |
    lines = text.splitlines()
    in_table = False
    for line in lines:
        if line.startswith("| Agent ") and "Write" in line and "Read" in line:
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("| "):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                agent = parts[1].strip()
                write_col = parts[2].strip()
                ownership[agent] = write_col
            continue
        if in_table and not line.startswith("|"):
            in_table = False

    return ownership


def check_overlaps(ownership: dict):
    """Check for overlapping write ownership."""
    write_paths = defaultdict(list)  # path -> [agents]

    for agent, write_str in ownership.items():
        if not write_str or write_str == "-":
            continue
        paths = [p.strip() for p in write_str.replace(",", " ").split() if p.strip()]
        for p in paths:
            write_paths[p].append(agent)

    violations = []
    for path, agents in sorted(write_paths.items()):
        if len(agents) > 1:
            violations.append((path, agents))

    return violations


def main():
    ownership = parse_ownership_matrix(MATRIX_PATH)
    if not ownership:
        print("[FAIL] Could not parse ownership matrix")
        sys.exit(1)

    print(f"Found {len(ownership)} agents in ownership matrix")
    for agent, paths in sorted(ownership.items()):
        print(f"  {agent}: {paths or '-'}")

    violations = check_overlaps(ownership)
    if violations:
        print(f"\n[VIOLATIONS] {len(violations)} overlapping write assignments:")
        for path, agents in violations:
            print(f"  OVERLAP: {path} -> {', '.join(agents)}")
        sys.exit(1)
    else:
        print("\n[OK] No overlapping write assignments detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
