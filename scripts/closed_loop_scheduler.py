#!/usr/bin/env python3
"""
Periodic closed-loop reflection runner.

Runs system reflection on a fixed interval and refreshes the active policy
artifact consumed by runtime services.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import learn_from_system


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [closed_loop_scheduler] %(levelname)s %(message)s",
)
logger = logging.getLogger("closed_loop_scheduler")


class ClosedLoopScheduler:
    def __init__(self, interval_seconds: int = 900, db_path: str = "memory/system_memory.sqlite3"):
        self.interval_seconds = interval_seconds
        self.db_path = db_path
        self.running = True

    def run_once(self) -> dict:
        report = learn_from_system.build_report(db_path=self.db_path, persist=True)
        logger.info(
            "reflection refreshed: lessons=%s policies=%s live_trades=%s",
            len(report.get("lessons") or []),
            len(report.get("policy_candidates") or []),
            (report.get("trade_learning") or {}).get("successful_live_trades", 0),
        )
        return report

    def run_forever(self) -> int:
        logger.info("starting closed-loop scheduler interval=%ss", self.interval_seconds)
        while self.running:
            try:
                self.run_once()
            except Exception:  # pragma: no cover - defensive runtime path
                logger.exception("closed-loop reflection run failed")
            for _ in range(self.interval_seconds):
                if not self.running:
                    break
                time.sleep(1)
        logger.info("closed-loop scheduler stopped")
        return 0

    def stop(self) -> None:
        self.running = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run closed-loop reflection on a schedule.")
    parser.add_argument("--interval", type=int, default=900, help="Seconds between reflection runs")
    parser.add_argument("--db-path", default="memory/system_memory.sqlite3")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scheduler = ClosedLoopScheduler(interval_seconds=args.interval, db_path=args.db_path)

    def _shutdown(signum, frame):
        logger.info("received signal %s, shutting down", signum)
        scheduler.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if args.once:
        scheduler.run_once()
        return 0
    return scheduler.run_forever()


if __name__ == "__main__":
    sys.exit(main())
