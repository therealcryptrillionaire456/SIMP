# Repo Classification — Day 1

Five-way label applied to every top-level directory and file in the repo root.

## Legend
- **CRITICAL** — on the canonical revenue hot path. Must never be archived, moved, or renamed without orchestrated change management.
- **OPERATIONAL** — supports running the system (monitoring, config, docs, scripts). Safe to reorganize with notice.
- **EXPERIMENTAL** — proof-of-concept, partial implementation, or not yet integrated. Safe to archive.
- **HISTORICAL** — completed sprints, old iterations, merged branches, backup artifacts. Primary archive target.
- **GENERATED** — output artifacts, logs, traces, build output. Already gitignored.

---

## CRITICAL (on the hot path)

| Path | Reason |
|------|--------|
| `simp/server/` | Core broker, HTTP server, agent registry, delivery engine |
| `simp/routing/` | Signal router, builder pool, routing engine |
| `simp/models/` | CanonicalIntent, failure taxonomy |
| `simp/orchestration/` | Orchestration loop + manager |
| `simp/organs/quantumarb/` | QuantumArb arb detection, execution, P&L |
| `simp/agents/` | Agent implementations (quantumarb, kashclaw) |
| `simp/compat/` | A2A compatibility, FinancialOps, safety gates |
| `simp/policies/` | Trading policy, kill switch enforcement |
| `gate4_inbox_consumer.py` | Live trade execution on Coinbase |
| `quantum_signal_bridge.py` | Signal bridge into broker |
| `startall.sh` | Canonical bring-up entry point |
| `contracts/` | Swarm charter, ownership matrix, live limits, status board schema |
| `harness/` | Swarm runner harness (status board, verifier, snapshot, cycle runner) |
| `state/` | Runtime state (status board, mode, queue, decision journal, incidents) |

## OPERATIONAL (supports running)

| Path | Reason |
|------|--------|
| `dashboard/` | Operator console (FastAPI + static files) |
| `scripts/runtime_snapshot.py` | Snapshot collector (canonical observability) |
| `scripts/verify_revenue_path.py` | Hot-path verifier |
| `scripts/inject_live_signal.py` | Test signal injector |
| `scripts/startall_dryrun.sh` | Day 1 — new, idempotent dry-run |
| `docs/` | Operator docs, runbooks, protocol conformance, architecture decisions |
| `runbooks/` | Day 1 — startup.md, agent_runner.md, fill_writers.md, failure_classes.md |
| `config/` | Runtime configs (gate configs, trading hours, mesh, telegram) |
| `bin/` | Start scripts, broker status, agent registration |
| `logs/` | Runtime logs (should be gitignored) |
| `data/` | JSONL ledgers, state persistence, inboxes (app-only) |
| `simp/projectx/` | ProjectX maintenance kernel, risk engine, execution engine |
| `simp/integrations/` | TimesFM, KashClaw execution mapping, market news |
| `launchd/` | Launchd plists for daemon management |
| `tests/` | Pytest test suite |

## EXPERIMENTAL (partial or not integrated)

| Path | Reason |
|------|--------|
| `simp/organs/gate4/` | May exist — needs verification of integration status |
| `simp/organs/spot_trading_organ.py` | Partially built spot trading |
| `simp/organs/equities_organ.py` | Stock/ETF organ, not yet wired |
| `agents/` (root level) | DeerFlow agents, gate4 scaled agents — prototypes |
| `tools/` | Various utility tools (brief generators, evolution, compliance) |
| `brp_enhancement/` | BRP enhancement suite — large, mostly external repos |
| `mythos_implementation/` | Mythos model — separate research project |
| `self_compiler_v2/` | Self-compiler — experimental |
| `keep-the-change/` | KTC webapp design docs — separate project |
| `KTC-webapp/` | KTC webapp implementation — separate |
| `pentagram_legal/` | Legal dept architecture — aspirational |
| `sigma_rules/` | Sigma rules — empty |
| `security_reports/` | Generated security reports |

## HISTORICAL (archive candidates)

| Path | Reason |
|------|--------|
| `backups/` | Empty — was for backups |
| `briefs/` | Generated architecture briefs — output artifacts |
| `compliance_reports/` | Generated compliance reports |
| `demos/` | Demo scripts and reports — not active |
| `examples/` | Example agent scripts — documentation, not production |
| `memory/` | Conversation archives, task memory — runtime data |
| `models/` | Empty ML model directories |
| `patches/` | Applied patches — historical |
| `projectx_memory/` | ProjectX runtime data |
| `projectx_tasks/` | ProjectX task files |
| `reports/` | Empty report directories |
| `sample_logs/` | Sample logs — demonstration |
| `security_audits/` | Generated security audit reports |
| `test_briefs/` | Test-generated briefs |
| `test_data/` | Test data files |
| `test_reports/` | Test output reports |
| `tmp/` | Temporary files |
| `traces/` | Quantum traces — output |
| `uploads/` | Upload receipts |
| `bill_russel_data_acquisition/` | Bill Russel project — completed |
| `bill_russel_integration/` | Bill Russel integration — completed |
| `bill_russel_ml_pipeline/` | Bill Russel ML — completed |
| `bill_russel_sigma_rules/` | Bill Russel sigma — completed |
| `simp_brain/` | Protocol updater — minimal |

## GENERATED

| Path | Reason |
|------|--------|
| `output/` | Output artifacts (TimesFM, etc.) |
| `var/` | Runtime variable data |
| `projectx_logs/` | ProjectX runtime logs |
| `logs/` | Runtime logs (covered under OPERATIONAL, also generated) |
| `graphify-out/` | Obsidian Graphify output |
| `*.pyc`, `__pycache__/` | Bytecode cache |
| `*.corrupt.*` | Corrupt state file backups |

## Root-Level Files Classification

| File | Label | Notes |
|------|-------|-------|
| `startall.sh` | CRITICAL | Canonical bring-up |
| `start_quantum_goose.sh` | CRITICAL | Quantum stack bootstrap |
| `gate4_inbox_consumer.py` | CRITICAL | Trade execution |
| `quantum_signal_bridge.py` | CRITICAL | Signal bridge |
| `quantumarb_http_agent.py` | OPERATIONAL | HTTP agent for quantumarb |
| `quantumarb_file_consumer.py` | EXPERIMENTAL | File-based consumer |
| `quantum_mesh_consumer.py` | EXPERIMENTAL | Mesh consumer |
| `README.md` | OPERATIONAL | Must be maintained |
| `AGENTS.md` | OPERATIONAL | Agent roster |
| `SPRINT_LOG.md` | HISTORICAL | Completed sprint log |
| `requirements.txt` | OPERATIONAL | Dependencies |
| `setup.py`, `pyproject.toml` | OPERATIONAL | Package config |
| All other `.md` files | HISTORICAL | Completed sprint/phase docs |
| All other `.py` files at root | EXPERIMENTAL/HISTORICAL | Most are single-run scripts |
| `HEARTBEAT.md` | OPERATIONAL | System heartbeat |

## Proposed Archive Moves

Target: `archive/day1_proposed/`

**Historical** (no impact to remove):
- `backups/`, `briefs/`, `compliance_reports/`, `demos/`, `examples/`, `memory/`
- `models/`, `patches/`, `reports/`, `sample_logs/`, `security_audits/`
- `test_briefs/`, `test_data/`, `test_reports/`, `tmp/`, `traces/`, `uploads/`
- `bill_russel_*`, `simp_brain/`
- Root-level `.md` files (except README, AGENTS.md, SPRINT_LOG.md)
- Root-level test scripts (`test_*.py`)

**Experimental** (consider archiving vs keeping):
- `brp_enhancement/` — 1.2MB, external repos
- `mythos_implementation/` — separate research
- `self_compiler_v2/` — experimental
- `keep-the-change/` — separate project
- `KTC-webapp/` — separate project
- `pentagram_legal/` — aspirational
- `tools/` — many utilities, some active

## Gitignore Status

Current `.gitignore` coverage:
- `state/` ✅ Covered by `.goosehints` convention but verify .gitignore entry
- `state/metrics/` ✅ Should be covered
- `*.corrupt.*` ✅ Should be covered

> **Note:** Zero archive moves executed today. Proposals only.
