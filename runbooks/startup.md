# SIMP Startup Runbook

Canonical entry point: `bash startall.sh [options]` at repo root.

Each process launched is documented below with its pgrep pattern, health-check URL, and canonical hot-path classification.

---

## 1. SIMP Broker (`bin/start_server.py`)
- **Launch:** `start_http_service "broker" ... "${PYTHON_BIN}" bin/start_server.py`
- **Health:** `${SIMP_BROKER_URL:-http://127.0.0.1:5555}/health`
- **pgrep pattern:** `bin/start_server.py`
- **PID file:** `logs/runtime/pids/broker.pid`
- **Canonical:** YES — core message bus. All intents route through this.
- **Timeout:** 60s
- **Notes:** Starts `SimpHttpServer` which wraps `SimpBroker`. If this fails, nothing else works.

## 2. Dashboard (`dashboard/server.py`)
- **Launch:** `start_http_service "dashboard" ... "${PYTHON_BIN}" dashboard/server.py`
- **Health:** `http://127.0.0.1:${DASHBOARD_PORT:-8050}/health`
- **pgrep pattern:** `dashboard/server.py`
- **PID file:** `logs/runtime/pids/dashboard.pid`
- **Canonical:** YES — operator console, status board consumer.
- **Timeout:** 45s

## 3. KTC — Keep The Change (`simp/organs/ktc/start_ktc.py`) [OPTIONAL]
- **Launch:** `start_http_service "ktc" ...` (gated by `--no-ktc` / `START_KTC=1`)
- **Health:** `http://${KTC_HOST:-127.0.0.1}:${KTC_PORT:-8765}/health`
- **pgrep pattern:** `simp/organs/ktc/start_ktc.py`
- **PID file:** `logs/runtime/pids/ktc.pid`
- **Canonical:** NO — KTC is a separate webapp, not on the quantumarb hot path.
- **Timeout:** 45s

## 4. QuantumArb Phase 4 Agent (`simp/agents/quantumarb_agent_phase4.py`)
- **Launch:** `start_background_service "quantumarb_phase4" ...`
- **Health:** N/A (background process, no HTTP endpoint)
- **pgrep pattern:** `simp/agents/quantumarb_agent_phase4.py`
- **PID file:** `logs/runtime/pids/quantumarb_phase4.pid`
- **Canonical:** YES — signal consumer and arb opportunity producer.
- **Notes:** Loads config from `$QUANTUMARB_PHASE4_CONFIG`. Live mode gated by `QUANTUMARB_ALLOW_LIVE_TRADING`.

## 5. Gate4 Live Consumer (`gate4_inbox_consumer.py`) [OPTIONAL]
- **Launch:** `start_background_service "gate4_consumer" ...` (gated by `--with-gate4` / `START_GATE4=1`)
- **Health:** N/A (background process)
- **pgrep pattern:** `gate4_inbox_consumer.py`
- **PID file:** `logs/runtime/pids/gate4_consumer.pid`
- **Canonical:** YES — executes trades on the canonical hot path.
- **Notes:** Only started in `--hot` mode or explicit `--with-gate4`. Requires live Coinbase credentials.

## 6. BullBear Agent (`/Users/kaseymarcelle/bullbear/agents/bullbear_simp_agent.py`) [OPTIONAL — EXTERNAL]
- **Launch:** `start_optional_http_service "bullbear" ... python3.10 agents/bullbear_simp_agent.py --port 5559`
- **Health:** `http://127.0.0.1:5559/health`
- **pgrep pattern:** `bullbear_simp_agent.py`
- **PID file:** `logs/runtime/pids/bullbear.pid`
- **Canonical:** DEPUTY — prediction signal generator, feeds into quantum stack.
- **Timeout:** 45s
- **Notes:** Lives in `/Users/kaseymarcelle/bullbear/`. Skip if not present.

## 7. KashClaw Gemma (`/Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py`) [OPTIONAL — EXTERNAL]
- **Launch:** `start_optional_http_service "gemma" ... python3.10 agents/kashclaw_gemma_agent.py --port 8780`
- **Health:** `http://127.0.0.1:8780/health`
- **pgrep pattern:** `kashclaw_gemma_agent.py`
- **PID file:** `logs/runtime/pids/gemma.pid`
- **Canonical:** DEPUTY — local LLM for planning and summarization.
- **Timeout:** 45s
- **Notes:** Same repo as BullBear. Skip if not present.

## 8. ProjectX Guard (`/Users/kaseymarcelle/ProjectX/projectx_guard_server.py`) [OPTIONAL — EXTERNAL]
- **Launch:** `start_projectx_guard` → `bash scripts/projectx_supervisor.sh`
- **Health:** `${PROJECTX_GUARD_URL:-http://127.0.0.1:8771}/health`
- **pgrep pattern:** `projectx_supervisor.sh`
- **PID file:** `logs/runtime/pids/projectx.pid`
- **Canonical:** YES — native SIMP maintenance kernel, self-registers with broker.
- **Timeout:** 45s
- **Notes:** Registered as `projectx_native` agent. Broker registration reconciled after start.

## 9. Solana Seeker (`scripts/solana_seeker_integration.py`) [OPTIONAL]
- **Launch:** `start_background_service "solana_seeker" ...` (gated by `--with-solana` / `START_SOLANA=1`)
- **Health:** N/A (daemon process)
- **pgrep pattern:** `scripts/solana_seeker_integration.py`
- **PID file:** `logs/runtime/pids/solana_seeker.pid`
- **Canonical:** NO — separate blockchain integration, not on the core quantumarb hot path.
- **Notes:** Runs `--dry-run` by default; `--live` requires `SOLANA_SEEKER_LIVE=true`.

## 10. Closed-Loop Scheduler (`scripts/closed_loop_scheduler.py`)
- **Launch:** `start_background_service "closed_loop_scheduler" ...`
- **Health:** N/A (periodic scheduler)
- **pgrep pattern:** `scripts/closed_loop_scheduler.py`
- **PID file:** `logs/runtime/pids/closed_loop_scheduler.pid`
- **Canonical:** DEPUTY — runs closed-loop learning cycles every `$CLOSED_LOOP_INTERVAL` (default 900s).
- **Notes:** Never has an HTTP health check; only pgrep verification.

## 11. Quantum Stack (multiple components via `bootstrap_quantum_stack` → `start_quantum_goose.sh --headless`)
- **Launch:** Called inside `bootstrap_quantum_stack()`. Runs `start_quantum_goose.sh --headless`.
- **Required components verified:**
  - `quantum_mesh_consumer.py` — listens for quantum arb signals on mesh bus
  - `quantum_signal_bridge.py` — bridges quantum signals to broker intents
  - `quantum_advisory_broadcaster.py` — broadcasts advisory signals
- **Other components launched (non-critical):**
  - `quantumarb_file_consumer.py`, `quantum_consensus.py`, `brp_audit_consumer.py`, `agent_coordination.py`, `projectx_quantum_advisor.py`
- **Canonical:** YES (signal_bridge + mesh_consumer) / DEPUTY (others)
- **Notes:** bootstrap_quantum_stack fails FAST if required components aren't verified running.

## 12. Obsidian State Watcher (`scripts/obsidian_state_watch.py`) [OPTIONAL]
- **Launch:** `start_background_service "obsidian_state_watch" ...` (gated by `--no-second-brain` / `START_SECOND_BRAIN=1`)
- **Health:** N/A (background watcher)
- **pgrep pattern:** `scripts/obsidian_state_watch.py`
- **PID file:** `logs/runtime/pids/obsidian_state_watch.pid`
- **Canonical:** NO — Obsidian/Graphify integration, not on trading hot path.

---

## Canonical Hot Path (processes required for revenue)
The canonical revenue hot path requires:
1. **broker** (`bin/start_server.py`) — message bus
2. **http_server** (same process as broker) — HTTP routes
3. **orchestration_loop** (started inside broker) — periodic loop
4. **quantumarb_phase4** (`simp/agents/quantumarb_agent_phase4.py`) — signal consumer
5. **signal_bridge** (`quantum_signal_bridge.py`) — signal bridge
6. **gate4_inbox_consumer** (`gate4_inbox_consumer.py`) — trade execution (optional, for live)

All other processes are supportive (dashboard, KTC, external agents, solana, quantum utilities, docs watcher).

## Orphan Detection
Processes to flag as potential orphans (launched by some start* script but not in canonical path):
- `quantumarb_file_consumer.py` — file-based, likely deprecated
- `quantum_consensus.py` — mesh-level consensus, not on hot path
- `brp_audit_consumer.py` — BRP audit, not on hot path
- `agent_coordination.py` — coordination utility, not on hot path
- Anything in `show_summary()` quantum checks that isn't in required_processes
