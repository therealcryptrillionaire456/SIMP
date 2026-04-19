#!/bin/bash
# Start Phase 4 System with proper sequencing
# Ensures all components start in correct order with health checks

set -e

SIMP_ROOT="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
LOG_DIR="${SIMP_ROOT}/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
STARTUP_LOG="${LOG_DIR}/phase4_startup_${TIMESTAMP}.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$STARTUP_LOG"
}

check_port() {
    local port=$1
    local service=$2
    if lsof -i :$port > /dev/null 2>&1; then
        log "✅ $service is already running on port $port"
        return 0
    else
        log "⚠ $service not running on port $port"
        return 1
    fi
}

wait_for_service() {
    local url=$1
    local service=$2
    local max_wait=60
    local wait_interval=2
    local elapsed=0
    
    log "Waiting for $service to be ready..."
    
    while [ $elapsed -lt $max_wait ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            log "✅ $service is responding"
            return 0
        fi
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
        log "  Waiting... ($elapsed/$max_wait seconds)"
    done
    
    log "❌ Timeout waiting for $service"
    return 1
}

kill_service() {
    local pattern=$1
    local service=$2
    
    if pgrep -f "$pattern" > /dev/null; then
        log "Stopping existing $service..."
        pkill -f "$pattern"
        sleep 2
        if pgrep -f "$pattern" > /dev/null; then
            log "⚠ Could not stop $service, trying force kill..."
            pkill -9 -f "$pattern"
            sleep 1
        fi
    fi
}

start_broker() {
    log "Starting SIMP Broker..."
    
    if check_port 5555 "SIMP Broker"; then
        log "Broker already running"
    else
        kill_service "simp.server.broker" "SIMP Broker"
        
        cd "$SIMP_ROOT"
        nohup python3.10 -m simp.server.broker >> "$LOG_DIR/broker_${TIMESTAMP}.log" 2>&1 &
        BROKER_PID=$!
        
        sleep 3
        
        if ! kill -0 $BROKER_PID 2>/dev/null; then
            log "❌ Failed to start broker"
            return 1
        fi
        
        log "✅ Broker started (PID: $BROKER_PID)"
    fi
    
    if wait_for_service "http://127.0.0.1:5555/health" "SIMP Broker"; then
        # Get broker status
        BROKER_STATUS=$(curl -s http://127.0.0.1:5555/health)
        AGENTS=$(echo "$BROKER_STATUS" | python3.10 -c "import json, sys; data=json.load(sys.stdin); print(data.get('agents_online', 0))")
        log "Broker status: $AGENTS agents online"
        return 0
    else
        return 1
    fi
}

start_dashboard() {
    log "Starting Dashboard..."
    
    if check_port 8050 "Dashboard"; then
        log "Dashboard already running"
    else
        kill_service "dashboard/server.py" "Dashboard"
        
        cd "$SIMP_ROOT"
        nohup python3.10 dashboard/server.py >> "$LOG_DIR/dashboard_${TIMESTAMP}.log" 2>&1 &
        DASH_PID=$!
        
        sleep 2
        
        if ! kill -0 $DASH_PID 2>/dev/null; then
            log "❌ Failed to start dashboard"
            return 1
        fi
        
        log "✅ Dashboard started (PID: $DASH_PID)"
    fi
    
    if wait_for_service "http://127.0.0.1:8050/health" "Dashboard"; then
        DASH_STATUS=$(curl -s http://127.0.0.1:8050/health)
        log "Dashboard status: healthy"
        return 0
    else
        return 1
    fi
}

start_quantumarb() {
    log "Starting QuantumArb Phase 4 Agent..."
    
    kill_service "quantumarb_agent_minimal" "QuantumArb Agent"
    
    cd "$SIMP_ROOT"
    nohup python3.10 simp/agents/quantumarb_agent_minimal.py \
        --config config/phase4_microscopic.json \
        >> "$LOG_DIR/quantumarb_${TIMESTAMP}.log" 2>&1 &
    QA_PID=$!
    
    sleep 2
    
    if ! kill -0 $QA_PID 2>/dev/null; then
        log "❌ Failed to start QuantumArb agent"
        return 1
    fi
    
    log "✅ QuantumArb Phase 4 agent started (PID: $QA_PID)"
    
    # Create agent directories
    mkdir -p "$SIMP_ROOT/data/quantumarb_minimal/inbox"
    mkdir -p "$SIMP_ROOT/data/quantumarb_minimal/outbox"
    mkdir -p "$SIMP_ROOT/data/quantumarb_minimal/inbox/processed"
    mkdir -p "$SIMP_ROOT/data/quantumarb_minimal/inbox/error"
    
    return 0
}

start_bullbear() {
    log "Starting BullBear Agent..."
    
    if check_port 5559 "BullBear Agent"; then
        log "BullBear already running"
        return 0
    fi
    
    BULLBEAR_ROOT="/Users/kaseymarcelle/bullbear"
    if [ ! -d "$BULLBEAR_ROOT" ]; then
        log "⚠ BullBear directory not found, skipping"
        return 1
    fi
    
    kill_service "bullbear_simp_agent.py" "BullBear Agent"
    
    cd "$BULLBEAR_ROOT"
    nohup python3.10 agents/bullbear_simp_agent.py --port 5559 \
        >> "$LOG_DIR/bullbear_${TIMESTAMP}.log" 2>&1 &
    BB_PID=$!
    
    sleep 2
    
    if ! kill -0 $BB_PID 2>/dev/null; then
        log "❌ Failed to start BullBear agent"
        return 1
    fi
    
    log "✅ BullBear agent started (PID: $BB_PID)"
    
    if wait_for_service "http://127.0.0.1:5559/health" "BullBear Agent"; then
        return 0
    else
        return 1
    fi
}

start_projectx() {
    log "Starting ProjectX..."
    
    if check_port 8771 "ProjectX"; then
        log "ProjectX already running"
        return 0
    fi
    
    PROJECTX_ROOT="/Users/kaseymarcelle/ProjectX"
    if [ ! -d "$PROJECTX_ROOT" ]; then
        log "⚠ ProjectX directory not found, skipping"
        return 1
    fi
    
    kill_service "projectx_guard_server.py" "ProjectX"
    
    cd "$PROJECTX_ROOT"
    nohup python3.10 projectx_guard_server.py \
        >> "$LOG_DIR/projectx_${TIMESTAMP}.log" 2>&1 &
    PX_PID=$!
    
    sleep 2
    
    if ! kill -0 $PX_PID 2>/dev/null; then
        log "❌ Failed to start ProjectX"
        return 1
    fi
    
    log "✅ ProjectX started (PID: $PX_PID)"
    
    if wait_for_service "http://127.0.0.1:8771/health" "ProjectX"; then
        return 0
    else
        return 1
    fi
}

initialize_gate1() {
    log "Initializing Gate 1 Sandbox Testing..."
    
    mkdir -p "$SIMP_ROOT/data/sandbox_test"
    
    PROGRESS_FILE="$SIMP_ROOT/data/sandbox_test/progress.json"
    if [ ! -f "$PROGRESS_FILE" ]; then
        cat > "$PROGRESS_FILE" << EOF
{
  "gate_1_progress": {
    "start_date": "$(date +%Y-%m-%d)",
    "target_trades": 100,
    "completed_trades": 0,
    "successful_trades": 0,
    "failed_trades": 0,
    "total_pnl_usd": 0.0,
    "average_slippage_pct": 0.0,
    "daily_progress": {}
  }
}
EOF
        log "✅ Gate 1 progress tracker created"
    else
        log "✅ Gate 1 progress tracker already exists"
    fi
    
    # Create P&L ledger if not exists
    LEDGER_FILE="$SIMP_ROOT/data/phase4_pnl_ledger.jsonl"
    if [ ! -f "$LEDGER_FILE" ]; then
        touch "$LEDGER_FILE"
        log "✅ P&L ledger created"
    fi
    
    return 0
}

update_obsidian() {
    log "Updating Obsidian documentation..."
    
    OBSIDIAN_ROOT="/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs"
    if [ -d "$OBSIDIAN_ROOT" ] && [ -f "$OBSIDIAN_ROOT/sync_with_simp.py" ]; then
        cd "$OBSIDIAN_ROOT"
        if python3.10 sync_with_simp.py >> "$STARTUP_LOG" 2>&1; then
            log "✅ Obsidian documentation updated"
        else
            log "⚠ Obsidian sync had issues"
        fi
        cd "$SIMP_ROOT"
    else
        log "⚠ Obsidian directory not found, skipping sync"
    fi
}

check_system_status() {
    log "Checking system status..."
    
    echo ""
    echo "="*60
    echo "SYSTEM STATUS CHECK"
    echo "="*60
    
    # Check broker
    echo -n "SIMP Broker (5555): "
    if curl -s http://127.0.0.1:5555/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Online${NC}"
        STATUS=$(curl -s http://127.0.0.1:5555/health)
        AGENTS=$(echo "$STATUS" | python3.10 -c "import json, sys; data=json.load(sys.stdin); print(data.get('agents_online', 'N/A'))")
        echo "  Agents: $AGENTS"
    else
        echo -e "${RED}❌ Offline${NC}"
    fi
    
    # Check dashboard
    echo -n "Dashboard (8050): "
    if curl -s http://127.0.0.1:8050/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Online${NC}"
    else
        echo -e "${RED}❌ Offline${NC}"
    fi
    
    # Check BullBear
    echo -n "BullBear (5559): "
    if curl -s http://127.0.0.1:5559/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Online${NC}"
    else
        echo -e "${YELLOW}⚠ Not running${NC}"
    fi
    
    # Check ProjectX
    echo -n "ProjectX (8771): "
    if curl -s http://127.0.0.1:8771/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Online${NC}"
    else
        echo -e "${YELLOW}⚠ Not running${NC}"
    fi
    
    # Check QuantumArb
    echo -n "QuantumArb Phase 4: "
    if pgrep -f "quantumarb_agent_minimal" > /dev/null; then
        echo -e "${GREEN}✅ Running${NC}"
    else
        echo -e "${RED}❌ Stopped${NC}"
    fi
    
    # Check Gate 1 progress
    echo -n "Gate 1 Progress: "
    if [ -f "$SIMP_ROOT/data/sandbox_test/progress.json" ]; then
        PROGRESS=$(python3.10 <<EOF
import json
with open('$SIMP_ROOT/data/sandbox_test/progress.json', 'r') as f:
    data = json.load(f)
gate1 = data['gate_1_progress']
print(f"{gate1['completed_trades']}/{gate1['target_trades']} trades, P&L: \${gate1['total_pnl_usd']:.4f}")
EOF
)
        echo -e "${BLUE}$PROGRESS${NC}"
    else
        echo -e "${YELLOW}⚠ Not initialized${NC}"
    fi
    
    echo "="*60
}

main() {
    log "="*60
    log "Starting Phase 4 SIMP System"
    log "Timestamp: $TIMESTAMP"
    log "Log file: $STARTUP_LOG"
    log "="*60
    
    # Step 1: Update Obsidian
    update_obsidian
    
    # Step 2: Initialize Gate 1
    initialize_gate1
    
    # Step 3: Start core services in order
    log "Starting core services..."
    
    if ! start_broker; then
        log "❌ Failed to start broker, aborting"
        exit 1
    fi
    
    if ! start_dashboard; then
        log "⚠ Dashboard failed, continuing without it"
    fi
    
    if ! start_quantumarb; then
        log "⚠ QuantumArb agent failed, continuing without it"
    fi
    
    # Step 4: Start optional services
    log "Starting optional services..."
    
    start_bullbear
    start_projectx
    
    # Step 5: Check system status
    check_system_status
    
    # Step 6: Display access information
    log ""
    log "="*60
    log "PHASE 4 SYSTEM STARTUP COMPLETE"
    log "="*60
    log ""
    log "${GREEN}Access URLs:${NC}"
    log "  ${BLUE}• Dashboard:${NC} http://127.0.0.1:8050"
    log "  ${BLUE}• Broker:${NC} http://127.0.0.1:5555"
    log "  ${BLUE}• Broker UI:${NC} http://127.0.0.1:5555/dashboard/ui"
    log "  ${BLUE}• BullBear:${NC} http://127.0.0.1:5559"
    log "  ${BLUE}• ProjectX:${NC} http://127.0.0.1:8771"
    log ""
    log "${GREEN}Phase 4 Status:${NC}"
    log "  ${BLUE}• Trading Mode:${NC} Microscopic Sandbox ($0.01-$0.10)"
    log "  ${BLUE}• Safety Gate:${NC} Gate 1 (Sandbox Testing)"
    log "  ${BLUE}• Target:${NC} 100 successful sandbox trades"
    log "  ${BLUE}• Progress:${NC} Check data/sandbox_test/progress.json"
    log ""
    log "${GREEN}Monitoring:${NC}"
    log "  ${YELLOW}• Agent Logs:${NC} tail -f logs/quantumarb_*.log"
    log "  ${YELLOW}• System Logs:${NC} tail -f $STARTUP_LOG"
    log "  ${YELLOW}• Gate 1 Progress:${NC} cat data/sandbox_test/progress.json"
    log ""
    log "${GREEN}Daily Operations:${NC}"
    log "  1. Morning: Run this script to start system"
    log "  2. Monitor: Check dashboard and logs"
    log "  3. Evening: Update Obsidian documentation"
    log "  4. Review: Check Gate 1 progress daily"
    log ""
    log "${GREEN}✅ Phase 4 system is now operational${NC}"
    log "="*60
    
    # Save startup summary
    SUMMARY_FILE="$LOG_DIR/startup_summary_${TIMESTAMP}.txt"
    cat > "$SUMMARY_FILE" << EOF
Phase 4 System Startup Summary
==============================
Timestamp: $(date)
Startup Log: $STARTUP_LOG

Services Started:
- SIMP Broker: http://127.0.0.1:5555
- Dashboard: http://127.0.0.1:8050
- QuantumArb Phase 4: Running
- BullBear Agent: http://127.0.0.1:5559
- ProjectX: http://127.0.0.1:8771

Phase 4 Status:
- Trading Mode: Microscopic Sandbox (\$0.01-\$0.10)
- Safety Gate: Gate 1 (Sandbox Testing)
- Target Trades: 100
- Progress: Check data/sandbox_test/progress.json

Next Steps:
1. Monitor trading activity
2. Update Obsidian documentation daily
3. Track Gate 1 progress
4. Prepare for Gate 2 promotion

System Ready for Operation.
EOF
    
    log "Startup summary saved to: $SUMMARY_FILE"
}

# Run main function
main "$@"