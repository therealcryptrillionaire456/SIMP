#!/usr/bin/env python3
"""
cycle_runner.py — the 30-minute cycle harness every lane calls.

Usage (inside an agent's runtime loop):

    from harness.cycle_runner import Cycle

    with Cycle(lane="A2") as cyc:
        cyc.observe(...)              # optional free-form string
        if cyc.kill_switch_set:
            cyc.halt("kill switch observed")
            return
        plan = cyc.decide("remediate stale fill freshness")
        ok, why = cyc.gate_check(touches=["scripts/verify_revenue_path.py"])
        if not ok:
            cyc.block(why); return
        cyc.execute(touches=["scripts/verify_revenue_path.py"],
                    revert_cmd="git checkout HEAD -- scripts/verify_revenue_path.py")
        cyc.verify("green")
        cyc.note("added bridge_reachable stage")
        cyc.enqueue_next(["add consumer_backlog probe", "wire alert on stage=bridge_reachable"])

Behavior:
- Writes one journal entry on __exit__ (success or blocked or halted).
- Updates the lane's status_board entry.
- Enforces ownership via contracts/ownership_matrix.md (simple glob/prefix rules compiled below).
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent if HERE.name in {"scripts", "harness"} else HERE
sys.path.insert(0, str(REPO_ROOT))

try:
    from harness import status_board
except ImportError:
    sys.path.insert(0, str(HERE))
    import status_board  # type: ignore

STATE_DIR = Path(os.environ.get("SIMP_STATE_DIR", REPO_ROOT / "state"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
CYCLE_JOURNAL = STATE_DIR / "cycle_journal.ndjson"
KILL_PATH = Path(os.environ.get("SIMP_KILL_PATH", STATE_DIR / "KILL"))

# --- Ownership (kept in sync with contracts/ownership_matrix.md) ---

OWNERSHIP: dict[str, list[str]] = {
    "A0": ["state/daily_brief.md", "state/queue.json", "state/mode.json", "state/commander_log.md"],
    "A1": ["startall.sh", "scripts/start_*.sh", "simp/server/broker.py",
           "simp/orchestration/orchestration_loop.py", "state/process_events.ndjson"],
    "A2": ["simp/organs/gate4/**", "quantum_signal_bridge*", "gate4_inbox_consumer*",
           "scripts/verify_revenue_path.py", "state/decision_journal.ndjson"],
    "A3": ["simp/routing/builder_pool.py", "simp/routing/signal_router.py",
           "simp/organs/quantum*/**", "simp/organs/quantumarb/**",
           "simp/task_ledger.py", "state/decision_journal.ndjson"],
    "A4": ["simp/server/http_server.py", "simp/server/agent_registry.py",
           "simp/models/canonical_intent.py", "simp/projectx/**"],
    "A5": ["policy_guard*", "kill_switch*", "budget*", "risk_caps*", "live_mode*",
           ".env*", "state/mode.json", "state/KILL"],
    "A6": ["scripts/runtime_snapshot.py", "state/status_board.json",
           "dashboard/**", "state/metrics/**"],
    "A7": [".gitignore", "archive/**", "README.md"],  # layout moves validated separately
    "A8": ["docs/**", "AGENTS.md", "runbooks/**", "state/handoff/**"],
    "A9": ["state/incidents/**", "state/shift_truth_report.md",
           "state/audit_journal.ndjson"],  # + append-only assertions to verify_revenue_path.py
}

# Files A9 may append assertions to (not listed above to avoid conflict with A2)
A9_ASSERTION_TARGETS = {"scripts/verify_revenue_path.py"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _match(path: str, patterns: list[str]) -> bool:
    p = path.replace("\\", "/")
    for pat in patterns:
        # support '**' via translation to fnmatch's nested form
        if pat.endswith("/**"):
            prefix = pat[:-3]
            if p == prefix or p.startswith(prefix + "/") or p.startswith(prefix):
                return True
        if fnmatch.fnmatch(p, pat):
            return True
    return False


def _owner(path: str) -> Optional[str]:
    for lane, pats in OWNERSHIP.items():
        if _match(path, pats):
            return lane
    return None


@dataclass
class Cycle:
    lane: str
    cycle_id: str = field(default_factory=lambda: f"cyc_{uuid.uuid4().hex[:12]}")
    _observed: str = ""
    _decided: str = ""
    _executed: List[str] = field(default_factory=list)
    _verified: str = "na"
    _gate: str = "pass"
    _note: str = ""
    _next: List[str] = field(default_factory=list)
    _revert: Optional[str] = None
    _sev_opened: List[str] = field(default_factory=list)
    _sev_closed: List[str] = field(default_factory=list)
    _halted: bool = False
    _blocked_reason: str = ""

    def __enter__(self) -> "Cycle":
        return self

    @property
    def kill_switch_set(self) -> bool:
        return KILL_PATH.exists()

    def observe(self, note: str) -> None:
        self._observed = note[:500]

    def decide(self, plan: str) -> str:
        self._decided = plan[:500]
        return plan

    def gate_check(self, touches: List[str], needs_a5: bool = False, needs_a0: bool = False
                   ) -> Tuple[bool, str]:
        if self.kill_switch_set:
            self._gate = "halt"
            return False, "kill_switch_set"
        for p in touches:
            owner = _owner(p)
            if owner is None:
                # Unowned file — A7 proposes relocation; others may not mutate
                if self.lane != "A7":
                    self._gate = "owner_conflict"
                    return False, f"unowned path {p}"
                continue
            if owner != self.lane:
                # A9 may append assertions to explicit allow-list
                if self.lane == "A9" and p in A9_ASSERTION_TARGETS:
                    continue
                self._gate = "owner_conflict"
                return False, f"{p} owned by {owner}, lane={self.lane}"
        if needs_a5 and self.lane != "A5":
            # expect A5 ack already journaled; caller asserts this upstream
            self._gate = "needs_a5"
        if needs_a0 and self.lane != "A0":
            self._gate = "needs_a0"
        return True, "ok"

    def execute(self, touches: List[str], revert_cmd: str) -> None:
        self._executed = list(touches)
        self._revert = revert_cmd

    def verify(self, status: str) -> None:
        assert status in {"green", "yellow", "red", "na"}
        self._verified = status

    def note(self, text: str) -> None:
        self._note = text[:1000]

    def enqueue_next(self, items: List[str]) -> None:
        self._next = [s[:200] for s in items][:10]

    def halt(self, reason: str) -> None:
        self._halted = True
        self._gate = "halt"
        self._note = (self._note + " | " if self._note else "") + f"halt:{reason}"

    def block(self, reason: str) -> None:
        self._blocked_reason = reason
        self._gate = self._gate if self._gate in {"owner_conflict", "needs_a5", "needs_a0", "halt"} else "owner_conflict"
        self._note = (self._note + " | " if self._note else "") + f"blocked:{reason}"

    def open_sev(self, id_: str) -> None:
        self._sev_opened.append(id_)

    def close_sev(self, id_: str) -> None:
        self._sev_closed.append(id_)

    def __exit__(self, exc_type, exc_val, exc_tb):
        entry = {
            "ts": _utcnow(),
            "lane": self.lane,
            "cycle_id": self.cycle_id,
            "observed": self._observed,
            "decided": self._decided,
            "gate": self._gate,
            "executed": self._executed,
            "verified": self._verified,
            "journal_note": self._note,
            "next_candidates": self._next,
        }
        if self._revert:
            entry["revert_cmd"] = self._revert
        if self._sev_opened:
            entry["sev_opened"] = self._sev_opened
        if self._sev_closed:
            entry["sev_closed"] = self._sev_closed

        CYCLE_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with CYCLE_JOURNAL.open("a") as f:
            f.write(json.dumps(entry) + "\n")

        # Update lane card in status board
        last_status = "halted" if self._halted else (
            "blocked" if self._blocked_reason else (
                "rolled_back" if self._verified == "red" else "ok"
            )
        )
        try:
            status_board.update_lane(self.lane, {
                "last_status": last_status,
                "notes": self._note[:200],
            })
        except Exception:
            pass

        return False  # never swallow exceptions


if __name__ == "__main__":
    # smoke test
    with Cycle(lane="A6") as c:
        c.observe("self-test")
        c.decide("noop")
        ok, why = c.gate_check(touches=["state/status_board.json"])
        print("gate:", ok, why)
        if ok:
            c.execute(touches=["state/status_board.json"], revert_cmd="git checkout -- state/status_board.json")
            c.verify("green")
            c.note("harness smoke ok")
    print("journal at", CYCLE_JOURNAL)
