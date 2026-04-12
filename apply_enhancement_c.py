#!/usr/bin/env python3
"""
apply_enhancement_c.py
======================
Safe, idempotent patcher for Enhancement C — adds the `capabilities` field
to the agent_info dict in simp/server/broker.py.

Usage:
    python apply_enhancement_c.py [--simp-root /path/to/SIMP]
    python apply_enhancement_c.py --dry-run    (preview only, no write)

If --simp-root is not provided, the script walks up from its own location
to find the SIMP repo root (looks for simp/server/broker.py).

Exit codes:
    0 — patch applied (or already applied)
    1 — broker.py not found
    2 — anchor string not found (broker.py structure may differ)
    3 — dry-run complete (use without --dry-run to apply)
"""

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone


ANCHOR = '"metadata":         metadata or {}'
INSERTION = '                "capabilities":   (metadata or {}).get("capabilities", []),  # Enhancement C'
ALREADY_APPLIED_MARKER = "Enhancement C"


def find_simp_root(start: str) -> str | None:
    """Walk up from start looking for simp/server/broker.py."""
    path = os.path.abspath(start)
    for _ in range(8):  # Max 8 levels up
        candidate = os.path.join(path, "simp", "server", "broker.py")
        if os.path.exists(candidate):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return None


def patch_broker(broker_path: str, dry_run: bool = False) -> int:
    """
    Finds the agent_info dict in broker.py and inserts the capabilities line.
    Idempotent: if the marker is already present, skips and reports.
    Returns exit code.
    """
    with open(broker_path, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.splitlines(keepends=True)

    # Idempotency check
    if ALREADY_APPLIED_MARKER in content:
        print(f"✅ Enhancement C already applied to {broker_path} — nothing to do.")
        return 0

    # Find anchor line
    anchor_line_idx = None
    for i, line in enumerate(lines):
        if ANCHOR in line:
            anchor_line_idx = i
            break

    if anchor_line_idx is None:
        print(f"❌ Anchor string not found in {broker_path}:")
        print(f"   Looking for: {ANCHOR!r}")
        print("   The broker.py structure may differ from what CoWork analysed.")
        print("   Apply manually: add the capabilities line after the 'metadata' entry in agent_info.")
        return 2

    # Show context
    context_start = max(0, anchor_line_idx - 2)
    context_end = min(len(lines), anchor_line_idx + 4)
    print(f"\nFound anchor at line {anchor_line_idx + 1} of {broker_path}")
    print("Context:")
    for i in range(context_start, context_end):
        marker = ">>> " if i == anchor_line_idx else "    "
        print(f"  {marker}{i+1:4d}: {lines[i]}", end="")

    if dry_run:
        print(f"\n[DRY RUN] Would insert after line {anchor_line_idx + 1}:")
        print(f"  +{anchor_line_idx + 2:4d}: {INSERTION}")
        print("\nRun without --dry-run to apply.")
        return 3

    # Back up
    backup_path = broker_path + f".bak.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    shutil.copy2(broker_path, backup_path)
    print(f"\nBacked up original to: {backup_path}")

    # Insert capabilities line after anchor
    new_lines = lines[:anchor_line_idx + 1] + [INSERTION + "\n"] + lines[anchor_line_idx + 1:]
    new_content = "".join(new_lines)

    with open(broker_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ Enhancement C applied to {broker_path}")
    print(f"   Inserted at line {anchor_line_idx + 2}: {INSERTION.strip()}")
    print("\nNext: run your existing protocol tests to verify zero regressions.")
    print("  python bin/test_protocol.py")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Apply Enhancement C to broker.py")
    parser.add_argument("--simp-root", default=None, help="Path to SIMP repo root")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no write")
    args = parser.parse_args()

    # Locate SIMP root
    if args.simp_root:
        simp_root = os.path.abspath(args.simp_root)
    else:
        # Try to auto-detect from script location or common paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        simp_root = find_simp_root(script_dir)

        if not simp_root:
            # Try common Mac locations from context
            candidates = [
                os.path.expanduser("~/Downloads/kashclaw (claude rebuild)/simp"),
                os.path.expanduser("~/simp"),
                os.path.expanduser("~/SIMP"),
                os.path.expanduser("~/code/SIMP"),
            ]
            for c in candidates:
                if os.path.exists(os.path.join(c, "simp", "server", "broker.py")):
                    simp_root = c
                    print(f"Auto-detected SIMP root: {simp_root}")
                    break

    if not simp_root:
        print("❌ Could not locate SIMP repo root.")
        print("   Usage: python apply_enhancement_c.py --simp-root /path/to/SIMP")
        return 1

    broker_path = os.path.join(simp_root, "simp", "server", "broker.py")
    if not os.path.exists(broker_path):
        print(f"❌ broker.py not found at: {broker_path}")
        print(f"   Confirm --simp-root is correct: {simp_root}")
        return 1

    return patch_broker(broker_path, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
