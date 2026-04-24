#!/usr/bin/env python3.10
"""
load_context.py
Runs at the START of every Goose session.
Reads all .md context files, system state, and Obsidian vault notes,
then prints a structured briefing Goose injects into its context window.

Usage (add to Goose profile startup_sequence):
    python3.10 scripts/kloutbot/load_context.py
    python3.10 scripts/kloutbot/load_context.py --brief      # condensed version
    python3.10 scripts/kloutbot/load_context.py --obsidian   # include Obsidian vault notes
    python3.10 scripts/kloutbot/load_context.py --update     # update Obsidian vault with current state
"""

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
BROKER_URL = "http://127.0.0.1:5555"
REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DOCS_DIR = REPO_ROOT / "docs" / "archive" / "2026-04"
REPOSITORY_GUIDELINES = REPO_ROOT / "AGENTS.md"
VAULT_GUIDELINES_NOTE = "Repository Guidelines.md"

# Core context files — read in order at every session start
CONTEXT_FILES = [
    REPO_ROOT / "KLOUTBOT_KERNEL.md",
    REPOSITORY_GUIDELINES,
    REPO_ROOT / "STRAY_GOOSE_PLAN.md",
    ARCHIVE_DOCS_DIR / "QUANTUM_PERMEATION_ROADMAP.md",
    REPO_ROOT / "SIMP_MASTER_CONTEXT.md",       # generated/updated each session
    ARCHIVE_DOCS_DIR / "NEXT_10_STEPS.md",      # archived roadmap snapshot
]

# Obsidian vault — update this path to match your vault location
OBSIDIAN_VAULT_CANDIDATES = [
    "/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs",  # primary
    Path.home() / "Documents" / "Obsidian",
    Path.home() / "Obsidian",
    Path.home() / "Documents" / "obsidian-docs",
    Path.home() / "obsidian-docs",
    Path.home() / "Downloads" / "obsidian-docs",
    Path.home() / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents",
]
SIMP_VAULT_NOTE = "SIMP_KLOUTBOT_STATE.md"   # note written to vault each session


def _find_obsidian_vault() -> Path | None:
    for candidate in OBSIDIAN_VAULT_CANDIDATES:
        candidate = Path(candidate)
        if candidate.exists():
            return candidate
    # Search for .obsidian config directory
    try:
        result = subprocess.run(
            ["find", str(Path.home()), "-name", ".obsidian", "-type", "d",
             "-maxdepth", "5"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                vault = Path(line).parent
                if vault.exists():
                    return vault
    except Exception:
        pass
    return None


# ── System state reader ───────────────────────────────────────────────────────

def _broker_state() -> dict:
    try:
        r = requests.get(f"{BROKER_URL}/health", timeout=5)
        return r.json() if r.content else {"status": "unreachable"}
    except Exception:
        return {"status": "unreachable"}


def _mesh_state() -> dict:
    try:
        r = requests.get(f"{BROKER_URL}/mesh/routing/status", timeout=5)
        return r.json() if r.content else {}
    except Exception:
        return {}


def _running_processes() -> list[str]:
    try:
        proc = subprocess.run(
            "ps aux | grep -E '(quantum_mesh|signal_bridge|quantumarb_mesh|projectx_quantum|start_server)' | grep -v grep",
            shell=True, capture_output=True, text=True
        )
        lines = [l.split()[-1].split("/")[-1] for l in proc.stdout.strip().split("\n") if l]
        return lines
    except Exception:
        return []


def _gate4_signal_count() -> int:
    inbox = REPO_ROOT / "data" / "inboxes" / "gate4_real"
    if inbox.exists():
        return len(list(inbox.glob("*.json")))
    return 0


def _last_kloutbot_instruction() -> str:
    results_log = REPO_ROOT / "data" / "logs" / "goose" / "kloutbot_results.jsonl"
    if results_log.exists():
        lines = results_log.read_text().strip().split("\n")
        if lines and lines[-1]:
            try:
                last = json.loads(lines[-1])
                return f"[{last.get('timestamp','?')}] instruction {last.get('instruction_id','?')[:8]}..."
            except Exception:
                pass
    return "none"


# ── Context file reader ───────────────────────────────────────────────────────

def _read_context_file(filename: str, max_lines: int = 80) -> str:
    if "/" in filename:
        path = REPO_ROOT / filename
    else:
        path = next((candidate for candidate in CONTEXT_FILES if candidate.name == filename), REPO_ROOT / filename)
    if not path.exists():
        return f"[{filename} — NOT FOUND]"
    lines = path.read_text().split("\n")
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"\n... [{len(lines) - max_lines} more lines — read full file if needed]"]
    return "\n".join(lines)


def _sync_repository_guidelines(vault: Path) -> None:
    if not REPOSITORY_GUIDELINES.exists():
        return
    target = vault / VAULT_GUIDELINES_NOTE
    target.write_text(REPOSITORY_GUIDELINES.read_text())


# ── Briefing builder ──────────────────────────────────────────────────────────

def build_briefing(brief: bool = False, include_obsidian: bool = False) -> str:
    now     = datetime.utcnow().isoformat()
    broker  = _broker_state()
    mesh    = _mesh_state()
    procs   = _running_processes()
    signals = _gate4_signal_count()
    last_ki = _last_kloutbot_instruction()

    lines = []
    lines.append("=" * 70)
    lines.append("  KLOUTBOT CONTEXT BRIEFING — SESSION START")
    lines.append(f"  {now} UTC")
    lines.append("=" * 70)

    # ── Live system state ──────────────────────────────────────────────────
    lines.append("")
    lines.append("── LIVE SYSTEM STATE ───────────────────────────────────────")
    broker_status = broker.get("state", broker.get("status", "unknown"))
    lines.append(f"  Broker:          {broker_status} | agents={broker.get('agents_online', '?')}")

    mesh_routing = mesh.get("mesh_routing", mesh)
    lines.append(f"  Mesh mode:       {mesh_routing.get('mesh_mode', '?')} | mesh_agents={mesh_routing.get('mesh_agents_count', '?')}")
    lines.append(f"  Gate4 signals:   {signals} in inbox")
    lines.append(f"  Last KLOUTBOT:   {last_ki}")

    if procs:
        lines.append(f"  Running procs:   {', '.join(procs[:6])}")
    else:
        lines.append("  Running procs:   NONE — quantum stack may need restart")

    # ── Known issues ───────────────────────────────────────────────────────
    lines.append("")
    lines.append("── KNOWN ISSUES (from last session) ────────────────────────")
    lines.append("  1. QIP response timeout — QMODE_DETECTION_FALSE_POSITIVE")
    lines.append("     Fix: quantum_mesh_consumer v2.1 deployed, needs restart + test")
    lines.append("  2. portfolio_optimization_examples.json — invalid format")
    lines.append("     Fix: match format of quantum_algorithm_examples.json")
    lines.append("  3. projectx_native heartbeat 404 endpoint")
    lines.append("  4. Mesh shows 0 agents despite QIP running")

    # ── Immediate actions ──────────────────────────────────────────────────
    lines.append("")
    lines.append("── IMMEDIATE ACTIONS ───────────────────────────────────────")
    lines.append("  1. python3.10 scripts/kloutbot/kloutbot_bridge.py --execute  (check KLOUTBOT instructions)")
    lines.append("  2. python3.10 goose_quantum_orchestrator.py --status  (QIP health)")
    lines.append("  3. cp ~/Downloads/quantum_mesh_consumer.py . && restart QIP consumer")
    lines.append("  4. cat data/quantum_dataset/quantum_algorithm_examples.json | head -20")
    lines.append("     (get format → fix portfolio_optimization_examples.json)")

    if brief:
        lines.append("")
        lines.append("  [Brief mode — use --full for complete context files]")
        lines.append("=" * 70)
        return "\n".join(lines)

    # ── Context files ──────────────────────────────────────────────────────
    lines.append("")
    lines.append("── KLOUTBOT KERNEL ─────────────────────────────────────────")
    lines.append(_read_context_file("KLOUTBOT_KERNEL.md", max_lines=60))

    lines.append("")
    lines.append("── REPOSITORY GUIDELINES ───────────────────────────────────")
    lines.append(_read_context_file("AGENTS.md", max_lines=60))

    lines.append("")
    lines.append("── NEXT 10 STEPS ───────────────────────────────────────────")
    lines.append(_read_context_file("docs/archive/2026-04/NEXT_10_STEPS.md", max_lines=80))

    if include_obsidian:
        lines.append("")
        lines.append("── OBSIDIAN VAULT NOTES ────────────────────────────────────")
        vault = _find_obsidian_vault()
        if vault:
            lines.append(f"  Vault: {vault}")
            note_path = vault / SIMP_VAULT_NOTE
            if note_path.exists():
                lines.append(note_path.read_text()[:3000])
            else:
                lines.append(f"  [{SIMP_VAULT_NOTE} not yet created — run --update to generate]")
        else:
            lines.append("  Obsidian vault not found. Check scripts/kloutbot/load_context.py")

    lines.append("")
    lines.append("=" * 70)
    lines.append("  Context loaded. KLOUTBOT is watching. Ride.")
    lines.append("=" * 70)

    return "\n".join(lines)


# ── Obsidian vault updater ────────────────────────────────────────────────────

def update_obsidian_vault():
    vault = _find_obsidian_vault()
    if not vault:
        print("Obsidian vault not found.")
        print(f"Searched: {[str(c) for c in OBSIDIAN_VAULT_CANDIDATES]}")
        print("Set the correct path in OBSIDIAN_VAULT_CANDIDATES in scripts/kloutbot/load_context.py")
        return

    print(f"Vault found: {vault}")
    _sync_repository_guidelines(vault)

    broker  = _broker_state()
    mesh    = _mesh_state()
    procs   = _running_processes()
    signals = _gate4_signal_count()
    now     = datetime.utcnow().isoformat()

    # Read the kernel for key facts
    kernel_path = REPO_ROOT / "KLOUTBOT_KERNEL.md"
    kernel_content = kernel_path.read_text() if kernel_path.exists() else "(not found)"

    # Build the Obsidian note with wikilinks for graphify
    note = f"""# SIMP KLOUTBOT State
*Last updated: {now} UTC*

## Live Status
| Component | Status |
|-----------|--------|
| Broker | {broker.get('state', broker.get('status', '?'))} |
| Agents Online | {broker.get('agents_online', '?')} |
| Mesh Mode | {mesh.get('mesh_routing', mesh).get('mesh_mode', '?')} |
| Gate4 Signals | {signals} |
| Quantum Procs | {len(procs)} running |

## Architecture
[[KLOUTBOT]] directs [[Goose]] via [[SIMP Mesh]] channel `kloutbot_instructions`.
[[Goose]] executes and reports to [[kloutbot_results]].
[[quantum_intelligence_prime]] processes quantum intents.
[[gate4_real]] executes Coinbase trades from [[quantum_signal_bridge]].
[[quantumarb_real]] executes arbitrage from [[quantumarb_mesh_consumer]].
[[projectx_quantum_advisor]] entrains [[ProjectX]] with quantum recommendations.

## Agent Roster
- [[quantum_intelligence_prime]] — QIP, quantum compute engine
- [[quantum_mesh_consumer]] — QIP mesh listener
- [[quantum_signal_bridge]] — Revenue wire to [[gate4_real]]
- [[quantumarb_mesh_consumer]] — Arb signals to [[quantumarb_real]]
- [[projectx_quantum_advisor]] — [[ProjectX]] quantum entrainment
- [[goose_kloutbot_bridge]] — [[KLOUTBOT]] ↔ [[Goose]] bridge
- [[kloutbot]] — Claude/KLOUTBOT orchestrator layer

## Known Issues
1. [[QIP Response Timeout]] — QMODE_DETECTION_FALSE_POSITIVE
   - Fix deployed in quantum_mesh_consumer v2.1 (needs restart)
2. [[portfolio_optimization_examples.json]] — invalid format
3. [[ProjectX Heartbeat 404]] — wrong endpoint
4. Mesh shows 0 agents despite QIP running

## Next 10 Steps
1. Fix [[QIP Response Processing]] — critical blocker
2. [[QuantumArb Mesh Consumer]] — revenue path
3. [[ProjectX Heartbeat Fix]] — Bug 4
4. [[L5 Quantum Consensus]] — multi-agent voting
5. [[BRP Audit Channel]] — security enforcement
6. [[Agent Coordination]] — prevent position doubling
7. [[Quantum Advisory Broadcaster]] — Phase 9
8. [[BullBear Quantum Bridge]] — Phase 10
9. [[L6 Commitment Market]] — trust staking
10. [[Goose Flock]] — parallel execution

## Key Files
- [[KLOUTBOT_KERNEL.md]] — system state
- [[Repository Guidelines]] — contributor and operator workflow
- [[STRAY_GOOSE_PLAN.md]] — Goose integration plan
- [[docs/archive/2026-04/QUANTUM_PERMEATION_ROADMAP.md]] — 14-phase roadmap
- [[docs/archive/2026-04/NEXT_10_STEPS.md]] — archived execution plan

## Revenue Pipeline
`QIP → quantum_signal_bridge → gate4_real → Coinbase → live positions`

Quantum signals: {signals} delivered to gate4

## Session Notes
Running processes at last update:
{chr(10).join(f'- {p}' for p in procs) if procs else '- none detected'}
"""

    note_path = vault / SIMP_VAULT_NOTE
    note_path.write_text(note)
    print(f"✅ Obsidian vault updated: {note_path}")

    # Also write individual linked notes if they don't exist
    stubs = {
        "KLOUTBOT.md": "# KLOUTBOT\nClaude/Anthropic AI orchestrator layer. Directs [[Goose]] via [[SIMP Mesh]].\n\nSee [[SIMP KLOUTBOT State]] for current status.",
        "Goose.md": "# Goose\nBlock's AI coding agent. Execution layer for [[KLOUTBOT]] instructions.\n\nProfile: `scripts/kloutbot/goose_kloutbot_profile.json`\nBridge: `scripts/kloutbot/kloutbot_bridge.py`",
        "SIMP Mesh.md": "# SIMP Mesh\nStandardized Inter-agent Message Protocol mesh layer.\n\nBroker: http://127.0.0.1:5555\nKey channels: `quantum`, `kloutbot_instructions`, `kloutbot_results`, `arb_signals`",
        "quantum_intelligence_prime.md": "# quantum_intelligence_prime\nQIP — quantum compute engine.\n\nCapabilities: solve_quantum_problem, optimize_portfolio, evolve_quantum_skills\nConsumer: [[quantum_mesh_consumer]]",
    }
    for filename, content in stubs.items():
        stub_path = vault / filename
        if not stub_path.exists():
            stub_path.write_text(content)
            print(f"  Created stub: {stub_path.name}")

    print(f"\nObsidian graph nodes created: {len(stubs) + 1}")
    print("Open Obsidian → Graph View to see the SIMP architecture.")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KLOUTBOT context loader for Goose")
    parser.add_argument("--brief",    action="store_true", help="Condensed briefing")
    parser.add_argument("--obsidian", action="store_true", help="Include Obsidian vault notes")
    parser.add_argument("--update",   action="store_true", help="Update Obsidian vault and exit")
    parser.add_argument("--vault",    action="store_true", help="Show vault location and exit")
    args = parser.parse_args()

    if args.vault:
        v = _find_obsidian_vault()
        print(f"Vault: {v}" if v else "Vault not found")
    elif args.update:
        update_obsidian_vault()
    else:
        print(build_briefing(brief=args.brief, include_obsidian=args.obsidian))
