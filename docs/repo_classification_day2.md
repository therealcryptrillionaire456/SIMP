# Repo Classification — Day 2 Update

## Scripts (scripts/) — Alive/Dead/Ambiguous

### 🟢 RUNNING (active processes)
| File | Lines | Role | Started By |
|---|---|---|---|
| `closed_loop_scheduler.py` | 88 | Periodic learning cycles | startall.sh |
| `obsidian_state_watch.py` | 151 | Obsidian/Graphify sync | startall.sh |
| `runtime_snapshot.py` | 294 | A6 status/snapshot collector | startall.sh (kit) |
| `verify_revenue_path.py` | 407 | A2 verifier (12-stage gate) | startall.sh (kit) |
| `signal_cycle.py` | 131 | Day 2 sustained signal injector | goose (manual) |

### 🟡 STARTALL / RUNBOOK (potential to run)
| File | Lines | Role | Starting Condition |
|---|---|---|---|
| `inject_quantum_signal.py` | 107 | Gate4 signal injector | Manual operator |
| `solana_seeker_integration.py` | 489 | Solana blockchain integration | `--with-solana` flag |

### ⚪ UNKNOWN (not running, not in startall.sh — candidates for retirement)
| File | Lines | Role | Recommendation |
|---|---|---|---|
| `generate_wire_up_report.py` | 266 | Reporting | Archive if not referenced |
| `inject_live_signal.py` | 104 | Kit signal injector (superseded by signal_cycle.py) | Keep as manual tool |
| `kalshi_trader.py` | 355 | Kalshi exchange connector | Keep — future revenue organ |
| `learn_from_system.py` | 128 | System learning | Keep |
| `learn_from_trades.py` | 101 | Trade learning | Keep |
| `test_gate4_minimal.py` | 87 | Test script | Move to tests/ |
| `validate_gate4.py` | 212 | Validation | Keep |
| `verify_quantumarb_path.py` | 45 | Quick check | Keep |
| `verify_solana_path.py` | 38 | Solana check | Keep (if solana active) |

## Root-Level Scripts

96 `.sh`/`.py` files at repo root. Key classifications:

### Canonical (startall.sh dependencies)
- `startall.sh` — canonical entry point
- `gate4_inbox_consumer.py` — trade execution
- `quantum_signal_bridge.py` — signal bridge
- `quantum_mesh_consumer.py` — mesh listener
- `quantum_advisory_broadcaster.py` — advisory broadcasts
- `quantum_consensus.py` — mesh consensus
- `agent_coordination.py` — coordination utility
- `projectx_quantum_advisor.py` — ProjectX integration
- `brp_audit_consumer.py` — BRP audit

### Historical/Integration
- `activate_live_trading.sh` — live trading toggle
- `apply_agent_lightning_patch.py` — Lightning patch
- `begin_gate1_testing.py` → through `complete_gate2.sh` — gate stage scripts
- `PHASE2_MESH_COMPLETION_TEST.py` — phase-specific

### Data Directories (68 entries)
- **Append-only JSONL ledgers**: `task_ledger.jsonl`, `financial_ops_proposals.jsonl`, etc.
- **Runtime state**: `inboxes/`, `outboxes/`, `logs/`
- **Historical artifacts**: `archive/`, `processed/`, various gate stage dirs

## Ambiguity Hotspots
1. Root-level 96 scripts — many are phase-specific tests that should be archived
2. `data/` has 68 entries — some are test artifacts mixing with live state
3. `data/archive/` — unclear what's safe to remove vs. what's needed for audit trail
