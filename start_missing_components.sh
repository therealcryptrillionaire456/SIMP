#!/bin/bash
# Start missing SIMP components

set -e

SIMP_ROOT="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
LOG_DIR="${SIMP_ROOT}/logs"
mkdir -p "$LOG_DIR"

echo "Checking and starting missing components..."

# Function to check if running
is_running() {
    pgrep -f "$1" > /dev/null
}

# Function to start if not running
start_if_missing() {
    local name="$1"
    local cmd="$2"
    local log_file="$3"
    
    if is_running "$name"; then
        echo "✅ $name is already running"
    else
        echo "Starting $name..."
        eval "$cmd" >> "$log_file" 2>&1 &
        sleep 2
        if is_running "$name"; then
            echo "✅ $name started"
        else
            echo "❌ Failed to start $name"
        fi
    fi
}

# 1. Dashboard
start_if_missing "dashboard/server.py" \
    "cd '$SIMP_ROOT' && python3.10 dashboard/server.py" \
    "$LOG_DIR/dashboard_$(date +%Y%m%d_%H%M%S).log"

# 2. Phase 4 QuantumArb Agent
start_if_missing "quantumarb_agent_phase4.py" \
    "cd '$SIMP_ROOT' && python3.10 simp/agents/quantumarb_agent_phase4.py --config config/phase4_microscopic.json" \
    "$LOG_DIR/quantumarb_phase4_$(date +%Y%m%d_%H%M%S).log"

# 3. BullBear Agent
BULLBEAR_ROOT="/Users/kaseymarcelle/bullbear"
if [ -d "$BULLBEAR_ROOT" ]; then
    start_if_missing "bullbear_simp_agent.py" \
        "cd '$BULLBEAR_ROOT' && python3.10 agents/bullbear_simp_agent.py --port 5559" \
        "$LOG_DIR/bullbear_$(date +%Y%m%d_%H%M%S).log"
else
    echo "⚠ BullBear directory not found"
fi

# 4. ProjectX
PROJECTX_ROOT="/Users/kaseymarcelle/ProjectX"
if [ -d "$PROJECTX_ROOT" ]; then
    start_if_missing "projectx_guard_server.py" \
        "cd '$PROJECTX_ROOT' && python3.10 projectx_guard_server.py" \
        "$LOG_DIR/projectx_$(date +%Y%m%d_%H%M%S).log"
else
    echo "⚠ ProjectX directory not found"
fi

# 5. KashClaw Gemma
if [ -d "$BULLBEAR_ROOT" ]; then
    start_if_missing "kashclaw_gemma_agent.py" \
        "cd '$BULLBEAR_ROOT' && python3.10 agents/kashclaw_gemma_agent.py --port 8780" \
        "$LOG_DIR/kashclaw_gemma_$(date +%Y%m%d_%H%M%S).log"
fi

echo ""
echo "Checking system status..."

# Check broker
echo -n "Broker (5555): "
if curl -s http://127.0.0.1:5555/health > /dev/null 2>&1; then
    echo "✅ Online"
    AGENTS=$(curl -s http://127.0.0.1:5555/agents | python3.10 -c "import json, sys; data=json.load(sys.stdin); print(f'{len(data)} agents registered')" 2>/dev/null || echo "? agents")
    echo "  $AGENTS"
else
    echo "❌ Offline"
fi

# Check dashboard
echo -n "Dashboard (8050): "
if curl -s http://127.0.0.1:8050/health > /dev/null 2>&1; then
    echo "✅ Online"
else
    echo "❌ Offline"
fi

# Check BullBear
echo -n "BullBear (5559): "
if curl -s http://127.0.0.1:5559/health > /dev/null 2>&1; then
    echo "✅ Online"
else
    echo "❌ Offline"
fi

# Check ProjectX
echo -n "ProjectX (8771): "
if curl -s http://127.0.0.1:8771/health > /dev/null 2>&1; then
    echo "✅ Online"
else
    echo "❌ Offline"
fi

# Check KashClaw Gemma
echo -n "KashClaw Gemma (8780): "
if curl -s http://127.0.0.1:8780/health > /dev/null 2>&1; then
    echo "✅ Online"
else
    echo "❌ Offline"
fi

echo ""
echo "Phase 4 Status:"
echo "• Gate 1 Sandbox Testing: Initialized"
echo "• Microscopic Trading: Ready"
echo "• Configuration: config/phase4_microscopic.json"
echo "• Progress: data/sandbox_test/progress.json"

echo ""
echo "Access URLs:"
echo "• Dashboard: http://127.0.0.1:8050"
echo "• Broker: http://127.0.0.1:5555"
echo "• Broker UI: http://127.0.0.1:5555/dashboard/ui"