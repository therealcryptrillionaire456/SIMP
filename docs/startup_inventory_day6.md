# Startup Inventory — Day 6

Generated: 2026-04-24  
Source: `startall.sh`

## Overview

`startall.sh` is the canonical SIMP bring-up entrypoint. It orchestrates startup
of 12+ processes in a defined order with health-check gating, env-file loading,
and an optional `--hot` mode for live trading.

---

## 1. SIMP Broker

| Field          | Value |
|----------------|-------|
| **Script**     | `bin/start_server.py` |
| **Launch**     | `python3.10 bin/start_server.py` |
| **Health URL** | `${SIMP_BROKER_URL}/health` (default `http://127.0.0.1:5555`) |
| **pgrep**      | `bin/start_server.py` |
| **Timeout**    | 60s |
| **Flags**      | `env PYTHONPATH=... python3.10 bin/start_server.py` |
| **Always?**    | Yes |

---

## 2. Dashboard

| Field          | Value |
|----------------|-------|
| **Script**     | `dashboard/server.py` |
| **Launch**     | `python3.10 dashboard/server.py` |
| **Health URL** | `http://127.0.0.1:${DASHBOARD_PORT}/health` (default port 8050) |
| **pgrep**      | `dashboard/server.py` |
| **Timeout**    | 45s |
| **Flags**      | Env vars: `SIMP_BROKER_URL`, `PROJECTX_GUARD_URL`, `DASHBOARD_HOST`, `DASHBOARD_PORT` |
| **Always?**    | Yes |

---

## 3. KTC (Keep the Change)

| Field          | Value |
|----------------|-------|
| **Script**     | `simp/organs/ktc/start_ktc.py` |
| **Launch**     | `python3.10 simp/organs/ktc/start_ktc.py --host <host> --port <port> --simp-url <broker>` |
| **Health URL** | `http://${KTC_HOST}:${KTC_PORT}/health` (default `127.0.0.1:8765`) |
| **pgrep**      | `simp/organs/ktc/start_ktc.py` |
| **Timeout**    | 45s |
| **Flags**      | `--host`, `--port`, `--simp-url` |
| **Optional?**  | `--no-ktc` flag skips this |
| **Always?**    | Default yes |

---

## 4. QuantumArb Phase 4 Agent

| Field          | Value |
|----------------|-------|
| **Script**     | `simp/agents/quantumarb_agent_phase4.py` |
| **Launch**     | `python3.10 simp/agents/quantumarb_agent_phase4.py --config <config>` |
| **Health**     | Process-running check via `pgrep` (no HTTP health) |
| **pgrep**      | `simp/agents/quantumarb_agent_phase4.py` |
| **Config**     | `${QUANTUMARB_PHASE4_CONFIG}` (default `config/phase4_microscopic.json`) |
| **Flags**      | `--config`, env `SIMP_LIVE_TRADING_ENABLED`, `SIMP_LIVE_EXCHANGES`, `QUANTUMARB_ALLOW_LIVE_TRADING` |
| **Hot mode**   | Switches config to `${QUANTUMARB_HOT_CONFIG}` (default `config/live_phase2_sol_microscopic.json`) |
| **Always?**    | Yes (background service) |

---

## 5. Gate4 Live Consumer

| Field          | Value |
|----------------|-------|
| **Script**     | `gate4_inbox_consumer.py` (root-level) |
| **Launch**     | `python3.10 gate4_inbox_consumer.py` |
| **Health**     | Process-running check via `pgrep` |
| **pgrep**      | `gate4_inbox_consumer.py` |
| **Optional?**  | `--with-gate4` or `--hot` required |
| **Always?**    | Only on explicit request |

---

## 6. ProjectX Guard

| Field          | Value |
|----------------|-------|
| **Script**     | `scripts/projectx_supervisor.sh` (wraps `/Users/kaseymarcelle/ProjectX/projectx_guard_server.py`) |
| **Launch**     | `bash scripts/projectx_supervisor.sh` with env vars |
| **Health URL** | `${PROJECTX_GUARD_URL}/health` (default `http://127.0.0.1:8771`) |
| **pgrep**      | `projectx_supervisor.sh` |
| **Timeout**    | 45s |
| **Reconcile**  | Re-registers with broker if `/agents/projectx_native` missing; restarts if `/health` reports `registered=false` |
| **Optional?**  | `--no-external` skips |
| **Always?**    | Default yes |

---

## 7. BullBear Agent

| Field          | Value |
|----------------|-------|
| **Script**     | `/Users/kaseymarcelle/bullbear/agents/bullbear_simp_agent.py` |
| **Launch**     | `python3.10 agents/bullbear_simp_agent.py --port 5559` |
| **Health URL** | `http://127.0.0.1:5559/health` |
| **pgrep**      | `bullbear_simp_agent.py` |
| **Timeout**    | 45s |
| **Condition**  | Script path must exist |
| **Optional?**  | `--no-external` skips |
| **Always?**    | Default yes |

---

## 8. KashClaw Gemma (Gemma4)

| Field          | Value |
|----------------|-------|
| **Script**     | `/Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py` |
| **Launch**     | `python3.10 agents/kashclaw_gemma_agent.py --port 8780` |
| **Health URL** | `http://127.0.0.1:8780/health` |
| **pgrep**      | `kashclaw_gemma_agent.py` |
| **Timeout**    | 45s |
| **Condition**  | Script path must exist |
| **Optional?**  | `--no-external` skips |
| **Always?**    | Default yes |

---

## 9. Solana Seeker

| Field          | Value |
|----------------|-------|
| **Script**     | `scripts/solana_seeker_integration.py` |
| **Launch**     | `python3.10 scripts/solana_seeker_integration.py --daemon <--dry-run|--live> --config <config>` |
| **Health**     | Process-running check via `pgrep` |
| **pgrep**      | `scripts/solana_seeker_integration.py` |
| **Config**     | `${SOLANA_SEEKER_CONFIG}` (default `config/solana_seeker_config.json`) |
| **Optional?**  | `--with-solana` or `--hot` required |
| **Always?**    | Only on explicit request |

---

## 10. Closed-Loop Scheduler

| Field          | Value |
|----------------|-------|
| **Script**     | `scripts/closed_loop_scheduler.py` |
| **Launch**     | `python3.10 scripts/closed_loop_scheduler.py --interval <interval>` |
| **Health**     | Process-running check via `pgrep` |
| **pgrep**      | `scripts/closed_loop_scheduler.py` |
| **Flags**      | `--interval` (default 900 seconds) |
| **Always?**    | Yes (background service) |

---

## 11. Quantum Stack (bootstrap_quantum_stack)

| Field          | Value |
|----------------|-------|
| **Launch**     | `bash start_quantum_goose.sh --headless` |
| **Required processes** | `quantum_mesh_consumer.py`, `quantum_signal_bridge.py`, `quantum_advisory_broadcaster.py` |
| **Also checks for** | `projectx_quantum_advisor.py`, `quantumarb_file_consumer.py`, `quantum_consensus.py`, `brp_audit_consumer.py`, `agent_coordination.py`, `scripts/closed_loop_scheduler.py` |
| **Log**        | `logs/runtime/quantum_stack.log` |
| **Optional?**  | `--no-quantum` skips |
| **Always?**    | Default yes |

---

## 12. Obsidian State Watcher (Second Brain)

| Field          | Value |
|----------------|-------|
| **Script**     | `scripts/bootstrap/launch_second_brain.sh` (wraps `scripts/obsidian_state_watch.py`) |
| **Launch**     | `bash scripts/bootstrap/launch_second_brain.sh` via `start_background_service` |
| **Health**     | Process-running via `pgrep` matching `scripts/obsidian_state_watch.py` |
| **Optional?**  | `--no-second-brain` skips |
| **Always?**    | Default yes |

---

## Boot Mode Summary: `--hot`

When `--hot` is passed, the following additional behaviors activate:

1. **Loads env files**: `.env.multi_exchange` and `.env.solana_seeker`
2. **Sets live trading flags**: `SIMP_LIVE_TRADING_ENABLED=true`, `SIMP_LIVE_EXCHANGES`
3. **Enables Gate4** (`START_GATE4=1`)
4. **Enables Solana** (`START_SOLANA=1`)
5. **Switches QuantumArb config** to hot/live config
6. **Validates live credentials**: fails if no Coinbase creds found
7. **Gates recovery mode**: warns/prevents if existing breaker state persists
8. **Post-startup commands**: `verify_revenue_path.py`, `inject_quantum_signal.py`

---

## Post-Start Summary (show_summary)

The summary reports health/status of:

| Service              | Check method                     |
|----------------------|----------------------------------|
| Broker               | HTTP `/health` on broker URL     |
| Dashboard            | HTTP `http://127.0.0.1:8050/health` |
| KTC                  | HTTP `http://127.0.0.1:8765/health` |
| ProjectX             | HTTP `http://127.0.0.1:8771/health` |
| BullBear             | HTTP `http://127.0.0.1:5559/health` |
| Gemma                | HTTP `http://127.0.0.1:8780/health` |
| QuantumArb Phase 4   | `pgrep` on agent script          |
| Gate4                | `pgrep` on consumer script       |
| Solana Seeker        | `pgrep` on integration script    |
| 9 Quantum components | `pgrep` on each pattern          |
| Second Brain         | `pgrep` on watcher script        |

---

## Utility Functions in startall.sh

| Function                    | Purpose |
|-----------------------------|---------|
| `http_ok()`                 | Quick `curl -fsS` health check |
| `wait_for_http()`           | Polls URL up to timeout |
| `stabilize_http_service()`  | Verifies service stays healthy for a window |
| `process_running()`         | `pgrep -f` check |
| `stop_matching_processes()` | `pkill -f` with 20s graceful wait |
| `start_http_service()`      | Wrapper: kill old → nohup → health wait → stabilize |
| `start_background_service()` | Wrapper: nohup → `pgrep` confirm |
| `start_optional_http_service()` | Checks path exists, then calls `start_http_service` |
| `load_env_file()`           | Sources `.env` files with quote handling |
| `reset_gate4_state_if_requested()` | Archives `data/gate4_consumer_state.json` |
| `bootstrap_quantum_stack()` | Runs `start_quantum_goose.sh` and verifies 3+ processes |
| `reconcile_projectx_guard()` | Registration reconciliation + restart logic |
| `show_summary()`            | Final health summary |

---

## Script Paths Referenced in startall.sh

- `scripts/projectx_supervisor.sh`
- `scripts/solana_seeker_integration.py`
- `scripts/closed_loop_scheduler.py`
- `scripts/obsidian_state_watch.py`
- `scripts/runtime_snapshot.py`
- `scripts/verify_revenue_path.py`
- `scripts/inject_quantum_signal.py`
- `scripts/bootstrap/launch_second_brain.sh`
