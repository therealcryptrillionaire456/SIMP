#!/usr/bin/env python3
"""
A1 — Auto-Heal Supervisor (Watchdog + Restart)

Runs every 30 seconds checking critical SIMP processes.
Restarts any that are missing. Respects kill switch.
Logs to logs/auto_heal.log
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
KILL_SWITCH_PATH = REPO / "state" / "KILL"
LOG_PATH = REPO / "logs" / "auto_heal.log"
PYTHON_BIN = str(REPO / "venv_gate4" / "bin" / "python")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_PATH)),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("auto_heal")


# (name, pgrep_pattern, restart_cmd_list)
PROCESSES = [
    ("broker", "bin.start_server", [PYTHON_BIN, "bin/start_server.py"]),
    ("gate4", "gate4_inbox_consumer", [PYTHON_BIN, "gate4_inbox_consumer.py"]),
    ("signal_bridge", "quantum_signal_bridge", [PYTHON_BIN, "quantum_signal_bridge.py", "--interval", "30"]),
    ("dashboard", "dashboard.server", [PYTHON_BIN, "dashboard/server.py"]),
    ("projectx", "projectx_guard_server", [PYTHON_BIN, "projectx_guard_server.py"]),
]


def is_running(pgrep_pattern: str) -> bool:
    """Check if a process matching the pattern is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pgrep_pattern],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def restart(name: str, cmd: list[str]) -> bool:
    """Restart a process, returning True if started successfully."""
    try:
        log.warning("RESTARTING %s: %s", name, " ".join(cmd))
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO)
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        if proc.poll() is None:
            log.info("  %s restarted (PID %d)", name, proc.pid)
            return True
        else:
            log.error("  %s failed to start (exit code %d)", name, proc.returncode)
            return False
    except Exception as e:
        log.error("  %s restart error: %s", name, e)
        return False


def check_and_heal() -> dict[str, str]:
    """Check all processes, restart any missing. Returns status dict."""
    status = {}
    for name, pattern, cmd in PROCESSES:
        running = is_running(pattern)
        if running:
            status[name] = "ok"
        else:
            log.warning("%s NOT RUNNING (pattern: %s)", name, pattern)
            ok = restart(name, cmd)
            status[name] = "restarted" if ok else "failed"
    return status


def main():
    log.info("=" * 60)
    log.info("Auto-Heal Supervisor starting (interval=30s)")
    log.info("Kill switch: %s", KILL_SWITCH_PATH)
    log.info("=" * 60)

    while True:
        if KILL_SWITCH_PATH.exists():
            log.warning("KILL SWITCH ACTIVE — auto-heal disabled")
            time.sleep(30)
            continue

        status = check_and_heal()

        failing = [k for k, v in status.items() if v == "failed"]
        if failing:
            log.warning("Failed to restart: %s", ", ".join(failing))

        time.sleep(30)


if __name__ == "__main__":
    main()
