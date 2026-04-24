# Restart & Remediation Runbook — Day 2

Canonical reference for restarting any component in the SIMP stack.
Every command is tested against the actual running system (2026-04-24).

---

## Process Identity Map

| Service | pgrep Pattern | Actual Process | Deviance |
|---|---|---|---|
| Broker | `bin/start_server` OR `simp[./]server[./]broker` | `bin/start_server.py` | ⚠️ Default verifier pattern misses real name |
| Dashboard | `dashboard/server` OR `uvicorn.*dashboard` | `dashboard/server.py` | ✅ Match |
| KTC | `simp/organs/ktc/start_ktc` | `ktc/start_ktc.py` | ✅ Match |
| QuantumArb Phase 4 | `quantumarb_agent_phase4` | `quantumarb_agent_phase4.py` | ✅ Match |
| Gate4 Consumer | `gate4_inbox_consumer` | `gate4_inbox_consumer.py` | ✅ Match |
| BullBear | `bullbear_simp_agent` | `bullbear_simp_agent.py` | ✅ Match |
| KashClaw Gemma | `kashclaw_gemma_agent` | `kashclaw_gemma_agent.py` | ✅ Match |
| ProjectX | `projectx_guard_server\|projectx_supervisor` | `projectx_guard_server.py` | ✅ Match |
| Signal Bridge | `quantum_signal_bridge` | `quantum_signal_bridge.py` | ✅ Match |
| Closed-Loop Scheduler | `closed_loop_scheduler` | `closed_loop_scheduler.py` | ✅ Match |
| Decision Adapter | `state/decision_adapter` | `state/decision_adapter.py` | ⚠️ Not in startall.sh |
| Obsidian Watch | `obsidian_state_watch` | `obsidian_state_watch.py` | ✅ Match |

---

## Per-Component Restart Commands

### 1. Broker (canonical core — restart last, start first)
```
# Find and kill
PID=$(pgrep -f "bin/start_server" | head -1)
kill $PID && sleep 2
# Verify dead
pgrep -f "bin/start_server" || echo "broker down"

# Restart
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
./venv_gate4/bin/python bin/start_server.py &

# Health check (up to 60s)
for i in $(seq 1 12); do
  curl -sf http://127.0.0.1:5555/health > /dev/null && echo "broker up" && break
  sleep 5
done
```

### 2. Dashboard (operator console)
```
PID=$(pgrep -f "dashboard/server" | head -1)
kill $PID && sleep 1
./venv_gate4/bin/python dashboard/server.py &
# Health: http://127.0.0.1:8050/health
```

### 3. Gate4 Inbox Consumer (trade execution)
```
PID=$(pgrep -f "gate4_inbox_consumer" | head -1)
kill $PID && sleep 1
./venv_gate4/bin/python gate4_inbox_consumer.py [--dry-run] &
# No HTTP health check — verify via trade log freshness:
# tail -1 logs/gate4_trades.jsonl
```

### 4. Quantum Signal Bridge (signal conduit)
```
PID=$(pgrep -f "quantum_signal_bridge" | head -1)
kill $PID && sleep 1
./venv_gate4/bin/python quantum_signal_bridge.py &
# No HTTP health check — verify via inbox file timestamps:
# ls -t data/inboxes/gate4_real/_processed/ | head -3
```

### 5. Quantum Mesh Consumer (arb signal receiver)
```
PID=$(pgrep -f "quantum_mesh_consumer" | head -1)
kill $PID && sleep 1
./venv_gate4/bin/python quantum_mesh_consumer.py --broker http://127.0.0.1:5555 --interval 2 &
```

### 6. Decision Adapter (kit decision bridge)
```
PID=$(pgrep -f "state/decision_adapter" | head -1)
kill $PID && sleep 1
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
python3 state/decision_adapter.py &
# Verify via:
# tail -1 state/decision_journal.ndjson
```

### 7. ProjectX Guard (maintenance kernel)
```
PID=$(pgrep -f "projectx_guard_server" | head -1)
kill $PID && sleep 1
cd /Users/kaseymarcelle/ProjectX
python3.10 projectx_guard_server.py --register --simp-url http://127.0.0.1:5555 &
# Health: http://127.0.0.1:8771/health
```

### 8. BullBear (prediction signals)
```
PID=$(pgrep -f "bullbear_simp_agent" | head -1)
kill $PID && sleep 1
cd /Users/kaseymarcelle/bullbear
python3.10 agents/bullbear_simp_agent.py --port 5559 &
# Health: http://127.0.0.1:5559/health
```

### 9. KashClaw Gemma (local LLM)
```
PID=$(pgrep -f "kashclaw_gemma_agent" | head -1)
kill $PID && sleep 1
cd /Users/kaseymarcelle/bullbear
python3.10 agents/kashclaw_gemma_agent.py --port 8780 &
# Health: http://127.0.0.1:8780/health
```

---

## Recovery Order (dependency chain)

```
1. Broker          ← everything depends on this
2. Dashboard       ← depends on broker for data
3. BullBear        ← independent HTTP service
4. Gemma           ← independent HTTP service
5. Quantum Mesh    ← depends on broker
6. Signal Bridge   ← depends on mesh consumer
7. Gate4 Consumer  ← depends on broker + bridge
8. ProjectX        ← registers with broker (can start after broker)
9. Decision Adapter ← reads trade log (can start anytime)
```

## Canonical Full Recovery
```bash
bash startall.sh
# Wait for all health checks to pass (~60s)
```

## Kill-Orphan Sequence
```bash
# Orphans are processes matching quantum* patterns that aren't in the canonical set:
# quantumarb_file_consumer, quantum_consensus, brp_audit_consumer, agent_coordination
BASEDIR="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
ORPHAN_PATTERNS="quantumarb_file_consumer|quantum_consensus|brp_audit_consumer|agent_coordination"
pgrep -f "$ORPHAN_PATTERNS" | while read pid; do
  kill $pid 2>/dev/null
  echo "killed orphan PID $pid"
done
```

## Post-Restart Verification
```bash
# After restart, run:
python3 scripts/verify_revenue_path.py
# Expected: all greens except possibly decision_present (yellow acceptable)
```

## Stale Component Detection
| Staleness Signal | What to Check | Action |
|---|---|---|
| Decision journal >60s old | `python3 -c "import json; e=json.loads(open('state/decision_journal.ndjson').readlines()[-1]); print(e['created_at'])"` | Inject fresh signal |
| Gate4 inbox stale >120s | `ls -t data/inboxes/gate4_real/_proc* \| head -1` | Restart signal bridge |
| No trade for >300s | `tail -1 logs/gate4_trades.jsonl \| python3 -c "import sys,json; print(json.load(sys.stdin)['ts'])"` | Inject quantum signal |
| Broker not responding | `curl -sf http://127.0.0.1:5555/health` | Restart broker |
