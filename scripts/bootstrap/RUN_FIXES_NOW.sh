#!/bin/bash
# RUN_FIXES_NOW.sh
# Paste this ONE script into terminal. It handles everything:
#   1. Deploys all new files to simp root
#   2. Runs QIP diagnostic
#   3. Fixes mesh routing registration
#   4. Kills stale processes, restarts clean
#   5. Deploys quantumarb_mesh_consumer (Phase 6)
#   6. Verifies full stack is alive
#
# Usage: bash scripts/bootstrap/RUN_FIXES_NOW.sh

set -euo pipefail

SIMP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECOVERY_DIR="$SIMP_DIR/scripts/recovery"
LOG_DIR="$SIMP_DIR/data/logs/goose"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║      KLOUTBOT — QUANTUM STACK FIX & RESTART             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

cd "$SIMP_DIR"
source venv_gate4/bin/activate

mkdir -p "$LOG_DIR"
mkdir -p data/inboxes/gate4_real
mkdir -p data/inboxes/quantumarb_real
mkdir -p data/inboxes/projectx_quantum
mkdir -p data/quantum_dataset

# ── STEP 1: Deploy all files ──────────────────────────────────────────────────
echo "── Step 1: Deploying latest files ─────────────────────────"

FILES=(
    "quantum_mesh_consumer.py"
    "quantum_signal_bridge.py"
    "goose_quantum_orchestrator.py"
    "projectx_quantum_advisor.py"
    "quantumarb_mesh_consumer.py"
    "start_quantum_goose.sh"
)

for f in "${FILES[@]}"; do
    if [ -f "$OUTPUTS_DIR/$f" ]; then
        cp "$OUTPUTS_DIR/$f" "$SIMP_DIR/$f"
        echo "  ✅ $f"
    else
        echo "  ⚠️  $f not in outputs — skipping"
    fi
done

# TrustScorer
if [ -f "$OUTPUTS_DIR/simp_trust_scorer.py" ]; then
    mkdir -p "$SIMP_DIR/simp/mesh"
    cp "$OUTPUTS_DIR/simp_trust_scorer.py" "$SIMP_DIR/simp/mesh/trust_scorer.py"
    echo "  ✅ simp/mesh/trust_scorer.py"
fi

# Dataset fix
if [ -f "$OUTPUTS_DIR/quantum_portfolio_examples.json" ]; then
    cp "$OUTPUTS_DIR/quantum_portfolio_examples.json" \
       "$SIMP_DIR/data/quantum_dataset/portfolio_optimization_examples.json"
    echo "  ✅ data/quantum_dataset/portfolio_optimization_examples.json"
fi

chmod +x "$SIMP_DIR/start_quantum_goose.sh" 2>/dev/null || true
echo ""

# ── STEP 2: Verify broker is running ─────────────────────────────────────────
echo "── Step 2: Broker check ────────────────────────────────────"
if curl -sf http://127.0.0.1:5555/health > /dev/null 2>&1; then
    AGENT_COUNT=$(curl -sf http://127.0.0.1:5555/health | \
        python3.10 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agents_online','?'))" 2>/dev/null || echo "?")
    echo "  ✅ Broker alive ($AGENT_COUNT agents)"
else
    echo "  🚀 Broker not running — starting..."
    nohup python3.10 bin/start_server.py > "$LOG_DIR/broker.log" 2>&1 &
    echo $! > "$LOG_DIR/broker.pid"
    for i in {1..12}; do
        sleep 1
        if curl -sf http://127.0.0.1:5555/health > /dev/null 2>&1; then
            echo "  ✅ Broker started (PID $(cat $LOG_DIR/broker.pid))"
            break
        fi
        [ $i -eq 12 ] && { echo "  ❌ Broker failed — check $LOG_DIR/broker.log"; exit 1; }
    done
fi
echo ""

# ── STEP 3: Kill stale quantum processes ──────────────────────────────────────
echo "── Step 3: Killing stale quantum processes ─────────────────"
for proc in "quantum_mesh_consumer" "quantum_signal_bridge" "quantumarb_mesh_consumer" \
            "projectx_quantum_advisor" "goose_quantum_orchestrator"; do
    PIDS=$(pgrep -f "$proc" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "  Stopping $proc (PIDs: $PIDS)..."
        kill $PIDS 2>/dev/null || true
        sleep 1
    fi
done
echo "  ✅ Stale processes cleared"
echo ""

# ── STEP 4: Fix mesh mode ─────────────────────────────────────────────────────
echo "── Step 4: Setting mesh to PREFERRED mode ──────────────────"
curl -sf -X POST http://127.0.0.1:5555/mesh/routing/config \
    -H "Content-Type: application/json" \
    -d '{"mode":"preferred"}' > /dev/null 2>&1 && echo "  ✅ Mesh: preferred" || echo "  ⚠️  Mesh config call failed"
echo ""

# ── STEP 5: Run QIP diagnostic ────────────────────────────────────────────────
echo "── Step 5: Running QIP diagnostic ─────────────────────────"
python3.10 "$RECOVERY_DIR/debug_qip.py" 2>&1 | tail -60
echo ""

# ── STEP 6: Fix mesh routing registration ────────────────────────────────────
echo "── Step 6: Fixing QIP mesh routing registration ────────────"
python3.10 "$RECOVERY_DIR/fix_qip_mesh_registration.py" 2>&1
echo ""

# ── STEP 7: Start all quantum services (fresh) ───────────────────────────────
echo "── Step 7: Starting quantum services ───────────────────────"

sleep 2  # let mesh registration settle

# QIP consumer
nohup python3.10 quantum_mesh_consumer.py > "$LOG_DIR/qip.log" 2>&1 &
QIP_PID=$!
echo $QIP_PID > "$LOG_DIR/qip.pid"
sleep 3
if kill -0 $QIP_PID 2>/dev/null; then
    echo "  ✅ quantum_mesh_consumer (PID $QIP_PID)"
else
    echo "  ❌ quantum_mesh_consumer crashed — check $LOG_DIR/qip.log"
    tail -20 "$LOG_DIR/qip.log" 2>/dev/null || true
fi

# Signal bridge
nohup python3.10 quantum_signal_bridge.py > "$LOG_DIR/signal_bridge.log" 2>&1 &
SB_PID=$!
echo $SB_PID > "$LOG_DIR/signal_bridge.pid"
sleep 2
if kill -0 $SB_PID 2>/dev/null; then
    echo "  ✅ quantum_signal_bridge (PID $SB_PID)"
else
    echo "  ❌ quantum_signal_bridge crashed — check $LOG_DIR/signal_bridge.log"
fi

# QuantumArb consumer (NEW — Phase 6)
nohup python3.10 quantumarb_mesh_consumer.py > "$LOG_DIR/quantumarb_consumer.log" 2>&1 &
QA_PID=$!
echo $QA_PID > "$LOG_DIR/quantumarb_consumer.pid"
sleep 2
if kill -0 $QA_PID 2>/dev/null; then
    echo "  ✅ quantumarb_mesh_consumer (PID $QA_PID) — Phase 6 ONLINE"
else
    echo "  ❌ quantumarb_mesh_consumer crashed — check $LOG_DIR/quantumarb_consumer.log"
fi

# ProjectX advisor
nohup python3.10 projectx_quantum_advisor.py > "$LOG_DIR/px_advisor.log" 2>&1 &
PX_PID=$!
echo $PX_PID > "$LOG_DIR/px_advisor.pid"
sleep 2
if kill -0 $PX_PID 2>/dev/null; then
    echo "  ✅ projectx_quantum_advisor (PID $PX_PID)"
else
    echo "  ❌ projectx_quantum_advisor crashed — check $LOG_DIR/px_advisor.log"
fi

echo ""

# ── STEP 8: Wait for QIP to settle, then test round-trip ─────────────────────
echo "── Step 8: Testing QIP round-trip (15s) ────────────────────"
sleep 10

python3.10 goose_quantum_orchestrator.py --status 2>&1 | head -30
echo ""

# ── STEP 9: Fire first live revenue signal ────────────────────────────────────
echo "── Step 9: Firing revenue signal ───────────────────────────"
python3.10 quantum_signal_bridge.py --once 2>&1 | head -40
echo ""

# ── STEP 10: Final status ─────────────────────────────────────────────────────
echo "── Step 10: Full system status ─────────────────────────────"

echo ""
echo "  Broker:"
curl -sf http://127.0.0.1:5555/status | python3.10 -c "
import sys,json
d=json.load(sys.stdin)
b=d.get('broker',{})
s=b.get('stats',{})
print(f\"    State:   {b.get('state','?')}\")
print(f\"    Agents:  {s.get('agents_online','?')}\")
print(f\"    Intents: {s.get('intents_completed','?')} completed\")
" 2>/dev/null || echo "    (broker status unavailable)"

echo ""
echo "  Mesh routing:"
curl -sf http://127.0.0.1:5555/mesh/routing/status | python3.10 -c "
import sys,json
d=json.load(sys.stdin).get('mesh_routing',{})
print(f\"    Mode:    {d.get('mesh_mode','?')}\")
print(f\"    Agents:  {d.get('mesh_agents_count','?')}\")
" 2>/dev/null || echo "    (mesh status unavailable)"

echo ""
echo "  Running quantum processes:"
ps aux | grep -E "(quantum|signal_bridge|projectx_quantum)" | grep -v grep | \
    awk '{printf "    PID %s: %s\n", $2, $11}' | sed 's|.*/||' || echo "    none"

echo ""
echo "  Gate4 signals:"
ls data/inboxes/gate4_real/*.json 2>/dev/null | wc -l | \
    xargs -I{} echo "    {} quantum signals in inbox"

echo ""
echo "  QuantumArb signals:"
ls data/inboxes/quantumarb_real/*.json 2>/dev/null | wc -l | \
    xargs -I{} echo "    {} arb signals in inbox" 2>/dev/null || echo "    0 arb signals yet"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Stack fix complete.                                     ║"
echo "║  Monitor logs:  tail -f data/logs/goose/qip.log         ║"
echo "║  Watch signals: watch -n5 'ls -la data/inboxes/gate4_real/' ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
