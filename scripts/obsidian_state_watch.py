#!/usr/bin/env python3.10
"""
Watch state files and refresh the Obsidian/Graphify second brain when they change.
"""

import argparse
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATTERNS = [
    "AGENTS.md",
    "dashboard/operator_events.jsonl",
    "config/*.json",
    "data/**/*.jsonl",
]

LOGGER = logging.getLogger("obsidian_state_watch")
RUNNING = True


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [obsidian-watch] %(levelname)s %(message)s",
    )


def handle_signal(signum, _frame) -> None:
    global RUNNING
    LOGGER.info("received signal %s, shutting down", signum)
    RUNNING = False


def iter_matching_files(patterns: list[str]) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for pattern in patterns:
        for path in REPO_ROOT.glob(pattern):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            rel = str(path.relative_to(REPO_ROOT))
            snapshot[rel] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def summarize_changes(previous: dict[str, tuple[int, int]], current: dict[str, tuple[int, int]]) -> list[str]:
    changes: list[str] = []
    for path in sorted(current):
        if path not in previous:
            changes.append(f"created:{path}")
        elif current[path] != previous[path]:
            changes.append(f"updated:{path}")
    for path in sorted(previous):
        if path not in current:
            changes.append(f"deleted:{path}")
    return changes


def run_command(cmd: list[str], label: str) -> bool:
    LOGGER.info("running %s: %s", label, " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.stdout.strip():
        LOGGER.debug("%s stdout:\n%s", label, result.stdout.strip())
    if result.returncode != 0:
        LOGGER.warning("%s failed with exit code %s", label, result.returncode)
        if result.stderr.strip():
            LOGGER.warning("%s stderr:\n%s", label, result.stderr.strip())
        return False
    return True


def maybe_run_graphify(python_bin: str) -> None:
    sync_script = REPO_ROOT / "integrate_obsidian_graphify.py"
    if not sync_script.exists():
        LOGGER.debug("graphify integration script not found; skipping")
        return
    run_command([python_bin, str(sync_script), "--sync"], "graphify sync")


def run_sync(python_bin: str, graphify: bool) -> None:
    run_command(
        [python_bin, str(REPO_ROOT / "scripts/kloutbot/load_context.py"), "--update"],
        "obsidian context update",
    )
    if graphify:
        maybe_run_graphify(python_bin)


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch SIMP state files and refresh Obsidian/Graphify docs")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds")
    parser.add_argument("--settle-seconds", type=float, default=4.0, help="Quiet period before syncing")
    parser.add_argument("--python-bin", default=sys.executable, help="Python interpreter for child commands")
    parser.add_argument("--no-graphify", action="store_true", help="Skip integrate_obsidian_graphify.py")
    parser.add_argument("--no-initial-sync", action="store_true", help="Skip the startup sync")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle and exit")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    configure_logging(args.verbose)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    patterns = DEFAULT_PATTERNS
    LOGGER.info("watching patterns: %s", ", ".join(patterns))
    previous = iter_matching_files(patterns)

    if not args.no_initial_sync:
        run_sync(args.python_bin, graphify=not args.no_graphify)
        if args.once:
            return 0

    pending_since: float | None = None
    pending_changes: list[str] = []

    while RUNNING:
        current = iter_matching_files(patterns)
        changes = summarize_changes(previous, current)
        if changes:
            preview = ", ".join(changes[:6])
            suffix = "" if len(changes) <= 6 else f" (+{len(changes) - 6} more)"
            LOGGER.info("detected state changes: %s%s", preview, suffix)
            pending_since = time.monotonic()
            pending_changes = changes
            previous = current
        elif pending_since is not None and (time.monotonic() - pending_since) >= args.settle_seconds:
            LOGGER.info("state settled; refreshing second brain")
            run_sync(args.python_bin, graphify=not args.no_graphify)
            pending_since = None
            pending_changes = []

        time.sleep(args.interval)

    if pending_since and pending_changes:
        LOGGER.info("final refresh before shutdown")
        run_sync(args.python_bin, graphify=not args.no_graphify)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
