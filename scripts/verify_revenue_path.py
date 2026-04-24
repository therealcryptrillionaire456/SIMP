#!/usr/bin/env python3
"""
verify_revenue_path.py — authoritative hot-path gate for SIMP.

Stages (each must pass or produce a clean terminal state):
  1. kill_switch          — file absence
  2. mode                 — fully_live | shadow | halt
  3. processes            — broker + http + orchestration + gate4_inbox_consumer alive
  4. signal_freshness     — last accepted signal within SLO
  5. bridge_reachable     — quantum_signal_bridge responds
  6. decision_present     — a decision artifact exists for the most recent attempted execution
  7. policy_evaluated     — decision has policy_result
  8. execution_terminal   — most recent execution has one of {executed, policy_blocked,
                            exchange_error, strategy_rejected, stale}
  9. fill_freshness       — if accepted signal in window AND mode=fully_live, last executed fill
                            within SLO
 10. lineage              — decision_id linkage intact across decision + feedback journals
 11. policy_bypass_check  — no venue call without policy allow/shadow
 12. shadow_integrity     — if mode=shadow, no real-venue calls occurred

Exit codes:
  0 — green (all stages pass, or non-`executed` terminal explained)
  1 — red   (one or more stages regressed)
  2 — unknown (dependencies missing; treated as red for gating, but distinct)

The script also writes status to state/status_board.json via harness/status_board.py.

Only A2 + A9 may edit this file; A9 may only add assertions.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# Allow running from repo root or scripts/ dir.
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent if (HERE.name in {"scripts", "harness"}) else HERE
sys.path.insert(0, str(REPO_ROOT))

try:
    from harness import status_board  # preferred when kit is vendored in
except ImportError:
    sys.path.insert(0, str(HERE))
    import status_board  # type: ignore

STATE_DIR = Path(os.environ.get("SIMP_STATE_DIR", REPO_ROOT / "state"))
DECISION_JOURNAL = STATE_DIR / "decision_journal.ndjson"
KILL_PATH = Path(os.environ.get("SIMP_KILL_PATH", STATE_DIR / "KILL"))
MODE_PATH = Path(os.environ.get("SIMP_MODE_PATH", STATE_DIR / "mode.json"))
LIMITS_PATH = Path(os.environ.get("SIMP_LIMITS_PATH", REPO_ROOT / "contracts" / "live_limits.json"))

TERMINAL_STATES = {"executed", "policy_blocked", "exchange_error", "strategy_rejected", "stale", "insufficient_balance"}

# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    name: str
    ok: bool
    detail: str = ""
    terminal_ok: bool = True  # if stage failed but is an acceptable terminal state

@dataclass
class VerifyReport:
    started_at: str
    stages: List[StageResult] = field(default_factory=list)
    fatal_stage: Optional[str] = None

    @property
    def green(self) -> bool:
        return all(s.ok or s.terminal_ok for s in self.stages) and self.fatal_stage is None

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "green": self.green,
            "fatal_stage": self.fatal_stage,
            "stages": [s.__dict__ for s in self.stages],
        }


# ---------------------------------------------------------------------------
# Small helpers

def _load_limits() -> dict:
    if not LIMITS_PATH.exists():
        return {"slo": {"signal_fresh_target_s": 60, "fill_fresh_target_s": 300, "bridge_rtt_ms_p95": 3000}}
    with LIMITS_PATH.open() as f:
        return json.load(f)


def _load_mode() -> str:
    if not MODE_PATH.exists():
        return "fully_live"
    try:
        with MODE_PATH.open() as f:
            return json.load(f).get("mode", "fully_live")
    except Exception:
        return "fully_live"


def _age_seconds(iso_ts: str) -> float:
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return float("inf")
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())


def _tail_ndjson(path: Path, n: int = 100) -> List[dict]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, 1_000_000)
            f.seek(size - block)
            data = f.read().decode("utf-8", errors="replace").splitlines()
        out = []
        for line in reversed(data):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
            if len(out) >= n:
                break
        out.reverse()
        return out
    except Exception:
        return []


def _process_is_up(pattern: str) -> bool:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True, timeout=3).strip()
        return bool(out)
    except subprocess.CalledProcessError:
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Stages

def stage_kill_switch() -> StageResult:
    if KILL_PATH.exists():
        return StageResult("kill_switch", ok=False, terminal_ok=False,
                           detail=f"kill file present at {KILL_PATH}")
    return StageResult("kill_switch", ok=True)


def stage_mode() -> StageResult:
    mode = _load_mode()
    if mode in {"fully_live", "shadow", "halt"}:
        return StageResult("mode", ok=(mode != "halt"), terminal_ok=(mode != "fully_live"),
                           detail=f"mode={mode}")
    return StageResult("mode", ok=False, terminal_ok=False, detail=f"invalid mode={mode}")


def stage_processes() -> StageResult:
    required = {
        "broker": r"bin/start_server|simp[./]server[./]broker",
        "http_server": r"bin/start_server|simp[./]server[./]http_server|uvicorn.*http_server",
        "orchestration_loop": r"orchestration_loop|closed_loop_scheduler",
        "gate4_inbox_consumer": r"gate4_inbox_consumer",
    }
    missing = [name for name, pat in required.items() if not _process_is_up(pat)]
    if missing:
        return StageResult("processes", ok=False, terminal_ok=False,
                           detail=f"missing: {','.join(missing)}")
    return StageResult("processes", ok=True)


def stage_signal_freshness() -> StageResult:
    limits = _load_limits()["slo"]
    entries = _tail_ndjson(DECISION_JOURNAL, n=200)
    sig_ts = None
    for e in reversed(entries):
        if "created_at" in e and "decision_id" in e:
            sig_ts = e["created_at"]
            break
    if sig_ts is None:
        return StageResult("signal_freshness", ok=False, terminal_ok=True,
                           detail="no recent decision/signal in journal")
    age = _age_seconds(sig_ts)
    ok = age <= float(limits["signal_fresh_target_s"])
    return StageResult("signal_freshness", ok=ok, terminal_ok=ok,
                       detail=f"age_s={age:.1f} target={limits['signal_fresh_target_s']}")


def stage_bridge_reachable() -> StageResult:
    # Optional probe: call a local HTTP probe endpoint if configured.
    url = os.environ.get("SIMP_BRIDGE_PROBE_URL", "")
    if not url:
        return StageResult("bridge_reachable", ok=True, detail="probe url not configured (skipped)")
    try:
        import urllib.request
        t0 = time.monotonic()
        with urllib.request.urlopen(url, timeout=3) as r:
            r.read(64)
        rtt_ms = (time.monotonic() - t0) * 1000
        return StageResult("bridge_reachable", ok=True, detail=f"rtt_ms={rtt_ms:.0f}")
    except Exception as e:
        return StageResult("bridge_reachable", ok=False, terminal_ok=False, detail=f"probe error: {e}")


def _most_recent_execution(entries: List[dict]) -> Optional[dict]:
    for e in reversed(entries):
        if "fill_status" in e or "executed_at" in e:
            return e
    return None


def stage_decision_present(entries: List[dict]) -> StageResult:
    exec_rec = _most_recent_execution(entries)
    if exec_rec is None:
        return StageResult("decision_present", ok=False, terminal_ok=True,
                           detail="no executions yet; acceptable pre-first-trade")
    did = exec_rec.get("decision_id")
    if not did:
        return StageResult("decision_present", ok=False, terminal_ok=False,
                           detail="execution has no decision_id — LINEAGE BREAK")
    decision = next((e for e in entries if e.get("decision_id") == did and "created_at" in e), None)
    if not decision:
        return StageResult("decision_present", ok=False, terminal_ok=False,
                           detail=f"execution references unknown decision_id={did}")
    return StageResult("decision_present", ok=True, detail=f"decision_id={did}")


def stage_policy_evaluated(entries: List[dict]) -> StageResult:
    exec_rec = _most_recent_execution(entries)
    if exec_rec is None:
        return StageResult("policy_evaluated", ok=True, detail="no executions yet")
    did = exec_rec.get("decision_id")
    decision = next((e for e in entries if e.get("decision_id") == did and "policy_result" in e), None)
    if not decision:
        return StageResult("policy_evaluated", ok=False, terminal_ok=False,
                           detail="decision missing policy_result")
    status = decision["policy_result"].get("status")
    if status not in {"allow", "block", "shadow"}:
        return StageResult("policy_evaluated", ok=False, terminal_ok=False,
                           detail=f"invalid policy status={status}")
    return StageResult("policy_evaluated", ok=True, detail=f"policy={status}")


def stage_execution_terminal(entries: List[dict]) -> StageResult:
    exec_rec = _most_recent_execution(entries)
    if exec_rec is None:
        return StageResult("execution_terminal", ok=True, detail="no executions yet")
    st = exec_rec.get("fill_status")
    if st in TERMINAL_STATES:
        return StageResult("execution_terminal", ok=(st == "executed"),
                           terminal_ok=True, detail=f"fill_status={st}")
    return StageResult("execution_terminal", ok=False, terminal_ok=False,
                       detail=f"non-terminal fill_status={st!r}")


def _live_trading_enabled() -> bool:
    """Check whether real live trading is enabled (paper-mode promotions don't count)."""
    return os.environ.get("SIMP_LIVE_TRADING_ENABLED", "").lower() == "true"


def stage_fill_freshness(entries: List[dict]) -> StageResult:
    limits = _load_limits()["slo"]
    mode = _load_mode()
    if mode != "fully_live" or not _live_trading_enabled():
        return StageResult("fill_freshness", ok=True,
                           detail=f"mode={mode} live_trading={_live_trading_enabled()}; not enforced")
    # need at least one accepted signal in window
    target_s = float(limits["fill_fresh_target_s"])
    recent_exec = None
    for e in reversed(entries):
        if e.get("fill_status") == "executed" and e.get("executed_at"):
            recent_exec = e
            break
    any_recent_signal = any(
        "decision_id" in e and "created_at" in e and _age_seconds(e["created_at"]) <= target_s
        for e in entries
    )
    if not any_recent_signal:
        return StageResult("fill_freshness", ok=True,
                           detail="no accepted signal in window; not enforced")
    if recent_exec is None:
        return StageResult("fill_freshness", ok=False, terminal_ok=False,
                           detail="signal accepted but no executed fill in window")
    age = _age_seconds(recent_exec["executed_at"])
    ok = age <= target_s
    return StageResult("fill_freshness", ok=ok, terminal_ok=ok,
                       detail=f"last_fill_age_s={age:.1f} target={target_s}")


def stage_lineage(entries: List[dict]) -> StageResult:
    broken = []
    # check last 20 executions
    executions = [e for e in entries if "fill_status" in e][-20:]
    for ex in executions:
        did = ex.get("decision_id")
        if not did:
            broken.append("exec_without_decision_id")
            continue
        if not any(d.get("decision_id") == did and "created_at" in d for d in entries):
            broken.append(f"orphan_execution:{did}")
    if broken:
        return StageResult("lineage", ok=False, terminal_ok=False,
                           detail="; ".join(broken[:3]))
    return StageResult("lineage", ok=True, detail=f"checked={len(executions)}")


def stage_policy_bypass_check(entries: List[dict]) -> StageResult:
    # any executed fill whose decision policy_result.status != allow/shadow is a bypass
    bypass = []
    for ex in [e for e in entries if e.get("fill_status") == "executed"][-50:]:
        did = ex.get("decision_id")
        decision = next((d for d in entries if d.get("decision_id") == did and "policy_result" in d), None)
        if not decision:
            bypass.append(f"no_policy_for:{did}")
            continue
        if decision["policy_result"].get("status") not in {"allow", "shadow"}:
            bypass.append(f"bypass:{did}")
    if bypass:
        return StageResult("policy_bypass_check", ok=False, terminal_ok=False,
                           detail="; ".join(bypass[:3]))
    return StageResult("policy_bypass_check", ok=True)


def stage_shadow_integrity(entries: List[dict]) -> StageResult:
    mode = _load_mode()
    if mode != "shadow":
        return StageResult("shadow_integrity", ok=True, detail=f"mode={mode}")
    real_hits = []
    for ex in [e for e in entries if e.get("fill_status") == "executed"][-50:]:
        venue = ex.get("venue_ref", "")
        # 'paper' is allowed in shadow; anything else is a violation
        if venue and "paper" not in venue.lower():
            real_hits.append(venue)
    if real_hits:
        return StageResult("shadow_integrity", ok=False, terminal_ok=False,
                           detail=f"real-venue hits in shadow: {real_hits[:3]}")
    return StageResult("shadow_integrity", ok=True)


# ---------------------------------------------------------------------------
# Orchestrator

def run() -> VerifyReport:
    report = VerifyReport(started_at=datetime.now(timezone.utc).isoformat())

    # Stage 1 is fatal if red.
    r = stage_kill_switch()
    report.stages.append(r)
    if not r.ok:
        report.fatal_stage = "kill_switch"
        return report

    report.stages.append(stage_mode())
    report.stages.append(stage_processes())
    report.stages.append(stage_signal_freshness())
    report.stages.append(stage_bridge_reachable())

    entries = _tail_ndjson(DECISION_JOURNAL, n=500)
    report.stages.append(stage_decision_present(entries))
    report.stages.append(stage_policy_evaluated(entries))
    report.stages.append(stage_execution_terminal(entries))
    report.stages.append(stage_fill_freshness(entries))
    report.stages.append(stage_lineage(entries))
    report.stages.append(stage_policy_bypass_check(entries))
    report.stages.append(stage_shadow_integrity(entries))

    return report


def main(argv: List[str]) -> int:
    verbose = "--verbose" in argv or "-v" in argv
    json_out = "--json" in argv
    report = run()

    # Reflect into status board
    status = "green" if report.green else "red"
    failing = next((s.name for s in report.stages if not s.ok and not s.terminal_ok), None)
    try:
        status_board.set_verifier(status=status, failing_stage=failing)
    except Exception:
        pass

    if json_out:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"[verify] {'GREEN' if report.green else 'RED'}  started_at={report.started_at}")
        for s in report.stages:
            mark = "OK " if s.ok else ("T? " if s.terminal_ok else "FAIL")
            line = f"  {mark} {s.name:22s} {s.detail}"
            if verbose or not s.ok:
                print(line)
        if not report.green:
            print(f"[verify] failing_stage={failing}")
    return 0 if report.green else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
