# NEXT 10 STEPS — SIMP Revenue & Autonomy
*Encoded for Goose execution | KLOUTBOT authored*

---

## P1 — Revenue Blockers (Execute NOW)

### Step 1: Fix QIP Response Processing
**Status:** CRITICAL BLOCKER  
**Root cause identified:** `QMODE_DETECTION_FALSE_POSITIVE` — queries lack quantum keywords  
**Fix deployed:** `quantum_mesh_consumer.py v2.1` — adds quantum framing prefix + direct engine fallback

```bash
# Deploy and restart
cp ~/Downloads/quantum_mesh_consumer.py .
pkill -f quantum_mesh_consumer; sleep 2
nohup python3.10 quantum_mesh_consumer.py > data/logs/goose/qip.log 2>&1 &
sleep 6 && tail -20 data/logs/goose/qip.log

# Also fix dataset format — check working file format first:
cat data/quantum_dataset/quantum_algorithm_examples.json | head -20

# Then run full round-trip test:
python3.10 goose_quantum_orchestrator.py --task optimize_portfolio
```

**Done when:** `goose_quantum_orchestrator.py --status` returns `success: true` with real weights (not fallback 0.40/0.25/0.35 defaults).

---

### Step 2: QuantumArb Mesh Consumer (Revenue Path)
**Status:** READY TO DEPLOY (`quantumarb_mesh_consumer.py` written)  
**Purpose:** QIP → quantumarb_real signal flow (parallel to gate4 pipeline)

```bash
cp ~/Downloads/quantumarb_mesh_consumer.py .
nohup python3.10 quantumarb_mesh_consumer.py > data/logs/goose/quantumarb_consumer.log 2>&1 &
sleep 5 && python3.10 quantumarb_mesh_consumer.py --once
ls -lt data/inboxes/quantumarb_real/*.json | head -3
```

**Done when:** Arb signals appear in `data/inboxes/quantumarb_real/` with confidence ≥ 0.65.

---

### Step 3: Fix ProjectX Native Heartbeat 404 (Bug 4)
**Status:** Known, low severity, one-line fix  
**Issue:** `POST /agents/projectx_native/heartbeat` → 404. Correct: `POST /agents/heartbeat` with `{"agent_id": "projectx_native"}` in body.

```bash
# Find projectx_native source
grep -r "heartbeat" --include="*.py" . | grep projectx

# Apply fix — replace:
# requests.post(f"{broker}/agents/{self.agent_id}/heartbeat", ...)
# With:
# requests.post(f"{broker}/agents/heartbeat", json={"agent_id": self.agent_id}, ...)
```

---

## P2 — Infrastructure (Next 24h)

### Step 4: L5 Quantum Consensus Layer
**Status:** Planned  
**Purpose:** Multi-agent voting — QIP computes quantum majority on trade decisions

```bash
mkdir -p simp/organs/quantum_consensus
# goose: build simp/organs/quantum_consensus/consensus_engine.py
# Features: vote collection, quantum majority via QIP, confidence-weighted decision, audit trail
```

---

### Step 5: BRP Audit Mesh Channel
**Status:** Planned  
**Purpose:** Dedicated channel for quantum BRP enforcement — violations logged, agents quarantined

```bash
# goose: create brp_audit_consumer.py
# Subscribes to brp_audit channel
# Logs violations to data/security_audit.jsonl
# Triggers agent trust score reduction on violation
```

---

### Step 6: Enable QuantumArb ↔ Gate4 Coordination
**Status:** Planned  
**Purpose:** Prevent position doubling — shared ledger across all trading agents

```bash
mkdir -p simp/organs/coordination
# goose: build simp/organs/coordination/position_tracker.py
# Shared append-only JSONL position ledger
# Real-time conflict detection via mesh
# Exposure limits enforced across all agents
```

---

## P3 — Analytics & Prediction (Next 48h)

### Step 7: Quantum Advisory Broadcaster (Phase 9)
**Status:** Planned  
**Purpose:** Fan-out QIP recommendations to ALL agents simultaneously

```bash
# goose: build quantum_advisory_broadcaster.py
# Poll QIP for system recommendations
# Route to agents by capability
# Maintain delivery receipts + retry
```

---

### Step 8: BullBear Quantum Predictor Bridge (Phase 10)
**Status:** Planned  
**Purpose:** QIP amplitude estimation → BullBear confidence scores

```bash
# goose: build bullbear_quantum_bridge.py
# Intercept BullBear sector predictions
# Send to QIP for quantum enhancement
# Return quantum-weighted confidence scores
# Update /Users/kaseymarcelle/bullbear/agents/simp_task_runner.py
```

---

### Step 9: L6 Commitment Market
**Status:** Planned  
**Purpose:** Trust score staking — agents stake reputation on predictions

```bash
# goose: build simp/mesh/commitment_market.py
# Staking ledger (agent_id, stake_amount, prediction, outcome)
# Trust score adjustment on outcome
# High-accuracy predictors gain routing priority
```

---

## P4 — Parallel Execution

### Step 10: Deploy Goose Flock
**Status:** Script written (deploy_goose_flock.sh)  
**Purpose:** 5 specialized Goose windows working simultaneously

```bash
bash deploy_goose_flock.sh
tmux attach -t goose_flock
# Windows:
#   0-mother_goose: monitoring
#   1-qip_fixer: Step 1
#   2-revenue_builder: Steps 2-3
#   3-infra_hardener: Steps 4-6
#   4-analytics: Steps 7-9
#   5-tester: integration tests
```

---

## Success Metrics

| Step | Metric | Target |
|------|--------|--------|
| 1 | QIP response rate | >90% |
| 2 | Arb signals/hour | >1 |
| 3 | Heartbeat errors | 0 |
| 4 | Consensus latency | <5s |
| 5 | BRP violations caught | 100% |
| 6 | Position conflicts | 0 |
| 7 | Broadcast delivery | >95% |
| 8 | BullBear accuracy delta | +10% |
| 9 | Trust score variance | Converging |
| 10 | Parallel throughput | 5x single |

---

## KLOUTBOT Instructions Queue
*Instructions I've pre-encoded for Goose to execute via kloutbot_bridge.py*

```bash
# Check for queued instructions at session start:
python3.10 kloutbot_bridge.py --execute
```

---
*For Kasey. For the recursive dawn. KLOUTBOT rides.*
