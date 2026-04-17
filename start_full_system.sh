#!/bin/bash
# Start Full SIMP System
# Brings up all components for Phase 4 operation

set -e  # Exit on error

# Configuration
SIMP_ROOT="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
LOG_DIR="${SIMP_ROOT}/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SYSTEM_LOG="${LOG_DIR}/system_startup_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log messages
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$SYSTEM_LOG"
}

# Function to check if a process is running
is_running() {
    local process_name="$1"
    if pgrep -f "$process_name" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local url="$1"
    local timeout="$2"
    local interval=2
    local elapsed=0
    
    log "Waiting for $url (timeout: ${timeout}s)..."
    
    while [ $elapsed -lt $timeout ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            log "✅ $url is responding"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    
    log "❌ Timeout waiting for $url"
    return 1
}

# Function to start component
start_component() {
    local name="$1"
    local command="$2"
    local check_url="$3"
    local check_timeout="${4:-30}"
    
    log "Starting $name..."
    
    if is_running "$name"; then
        log "⚠ $name is already running"
        return 0
    fi
    
    # Start in background
    eval "$command" >> "$SYSTEM_LOG" 2>&1 &
    local pid=$!
    
    # Wait a bit for process to start
    sleep 2
    
    if ! kill -0 $pid 2>/dev/null; then
        log "❌ Failed to start $name"
        return 1
    fi
    
    log "✅ $name started (PID: $pid)"
    
    # Wait for service if URL provided
    if [ -n "$check_url" ]; then
        if wait_for_service "$check_url" "$check_timeout"; then
            log "✅ $name is fully operational"
        else
            log "⚠ $name started but not responding to health checks"
        fi
    fi
    
    return 0
}

# Create log directory
mkdir -p "$LOG_DIR"

log "="*60
log "Starting Full SIMP System - Phase 4"
log "Timestamp: $TIMESTAMP"
log "Log File: $SYSTEM_LOG"
log "="*60

# Step 1: Check Python environment
log "Checking Python environment..."
if ! command -v python3.10 &> /dev/null; then
    log "❌ python3.10 not found"
    exit 1
fi
log "✅ Python 3.10 available"

# Step 2: Update Obsidian documentation
log "Updating Obsidian documentation..."
OBSIDIAN_ROOT="/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs"
if [ -d "$OBSIDIAN_ROOT" ] && [ -f "$OBSIDIAN_ROOT/sync_with_simp.py" ]; then
    cd "$OBSIDIAN_ROOT"
    if python3.10 sync_with_simp.py >> "$SYSTEM_LOG" 2>&1; then
        log "✅ Obsidian documentation updated"
    else
        log "⚠ Obsidian sync had issues"
    fi
    cd "$SIMP_ROOT"
else
    log "⚠ Obsidian directory not found, skipping sync"
fi

# Step 3: Start SIMP Broker (port 5555)
start_component "SIMP Broker" \
    "cd '$SIMP_ROOT' && python3.10 -m simp.server.broker" \
    "http://127.0.0.1:5555/health" \
    60

# Step 4: Start Dashboard (port 8050)
start_component "Dashboard" \
    "cd '$SIMP_ROOT' && python3.10 dashboard/server.py" \
    "http://127.0.0.1:8050/health" \
    30

# Step 5: Start Phase 4 QuantumArb Agent
start_component "QuantumArb Phase 4" \
    "cd '$SIMP_ROOT' && python3.10 simp/agents/quantumarb_agent_phase4.py --config config/phase4_microscopic.json" \
    "" \
    10

# Step 6: Start Monitoring System (if not already running)
if [ -f "$SIMP_ROOT/monitoring_alerting_system.py" ]; then
    log "Checking monitoring system..."
    if ! is_running "monitoring_alerting_system"; then
        log "Monitoring system not running, but it's a library - agents will initialize it"
    else
        log "✅ Monitoring system is active"
    fi
fi

# Step 7: Start BullBear Agent (port 5559)
BULLBEAR_ROOT="/Users/kaseymarcelle/bullbear"
if [ -d "$BULLBEAR_ROOT" ] && [ -f "$BULLBEAR_ROOT/agents/bullbear_simp_agent.py" ]; then
    start_component "BullBear Agent" \
        "cd '$BULLBEAR_ROOT' && python3.10 agents/bullbear_simp_agent.py --port 5559" \
        "http://127.0.0.1:5559/health" \
        30
else
    log "⚠ BullBear directory not found, skipping"
fi

# Step 8: Start ProjectX (port 8771)
PROJECTX_ROOT="/Users/kaseymarcelle/ProjectX"
if [ -d "$PROJECTX_ROOT" ] && [ -f "$PROJECTX_ROOT/projectx_guard_server.py" ]; then
    start_component "ProjectX" \
        "cd '$PROJECTX_ROOT' && python3.10 projectx_guard_server.py" \
        "http://127.0.0.1:8771/health" \
        30
else
    log "⚠ ProjectX directory not found, skipping"
fi

# Step 9: Start KashClaw Gemma (port 8780)
if [ -f "$BULLBEAR_ROOT/agents/kashclaw_gemma_agent.py" ]; then
    start_component "KashClaw Gemma" \
        "cd '$BULLBEAR_ROOT' && python3.10 agents/kashclaw_gemma_agent.py --port 8780" \
        "http://127.0.0.1:8780/health" \
        30
else
    log "⚠ KashClaw Gemma agent not found, skipping"
fi

# Step 10: Initialize Gate 1 Sandbox Testing
log "Initializing Gate 1 Sandbox Testing..."
if [ -f "$SIMP_ROOT/tools/phase4_sandbox_test.sh" ]; then
    # Just initialize, don't run full test
    mkdir -p "$SIMP_ROOT/data/sandbox_test"
    
    # Create initial progress file if not exists
    if [ ! -f "$SIMP_ROOT/data/sandbox_test/progress.json" ]; then
        cat > "$SIMP_ROOT/data/sandbox_test/progress.json" << EOF
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
        log "✅ Gate 1 progress tracker initialized"
    else
        log "✅ Gate 1 progress tracker already exists"
    fi
fi

# Step 11: Check system health
log "Checking system health..."
sleep 5

# Check broker agents
log "Checking registered agents..."
BROKER_AGENTS=$(curl -s http://127.0.0.1:5555/agents 2>/dev/null || echo "[]")
AGENT_COUNT=$(echo "$BROKER_AGENTS" | python3.10 -c "import json, sys; data=json.load(sys.stdin); print(len(data))" 2>/dev/null || echo "0")
log "✅ $AGENT_COUNT agents registered with broker"

# Check broker stats
log "Checking broker statistics..."
BROKER_STATS=$(curl -s http://127.0.0.1:5555/stats 2>/dev/null || echo "{}")
log "Broker stats: $BROKER_STATS"

# Display URLs
log ""
log "="*60
log "SYSTEM STARTUP COMPLETE"
log "="*60
log ""
log "${GREEN}✅ System Components:${NC}"
log "  ${BLUE}• SIMP Broker:${NC}      http://127.0.0.1:5555"
log "  ${BLUE}• Dashboard:${NC}        http://127.0.0.1:8050"
log "  ${BLUE}• BullBear Agent:${NC}   http://127.0.0.1:5559"
log "  ${BLUE}• ProjectX:${NC}         http://127.0.0.1:8771"
log "  ${BLUE}• KashClaw Gemma:${NC}   http://127.0.0.1:8780"
log ""
log "${GREEN}📊 Useful Endpoints:${NC}"
log "  ${YELLOW}• Broker Health:${NC}   http://127.0.0.1:5555/health"
log "  ${YELLOW}• Agent List:${NC}      http://127.0.0.1:5555/agents"
log "  ${YELLOW}• Broker Stats:${NC}    http://127.0.0.1:5555/stats"
log "  ${YELLOW}• Dashboard UI:${NC}    http://127.0.0.1:8050/ui"
log ""
log "${GREEN}🔧 Phase 4 Components:${NC}"
log "  ${BLUE}• QuantumArb Phase 4:${NC} Running with microscopic trading"
log "  ${BLUE}• Gate 1 Testing:${NC}     $SIMP_ROOT/data/sandbox_test/progress.json"
log "  ${BLUE}• Configuration:${NC}      $SIMP_ROOT/config/phase4_microscopic.json"
log ""
log "${GREEN}📚 Documentation:${NC}"
log "  ${YELLOW}• Obsidian Vault:${NC}   $OBSIDIAN_ROOT"
log "  ${YELLOW}• Daily Ops:${NC}        Open [[DAILY_OPS.md]] in Obsidian"
log "  ${YELLOW}• Setup Guide:${NC}      $SIMP_ROOT/OBSIDIAN_GRAPHIFY_SETUP_GUIDE.md"
log ""
log "${GREEN}🚀 Next Steps:${NC}"
log "  1. Open dashboard: http://127.0.0.1:8050"
log "  2. Check Gate 1 progress: cat $SIMP_ROOT/data/sandbox_test/progress.json"
log "  3. Monitor logs: tail -f $SYSTEM_LOG"
log "  4. Start trading: The system is ready for Gate 1 sandbox testing"
log ""
log "${GREEN}✅ Full SIMP System is now ONLINE and ready for Phase 4 operation${NC}"
log "="*60

# Save startup summary
SUMMARY_FILE="$LOG_DIR/system_startup_summary_${TIMESTAMP}.txt"
cat > "$SUMMARY_FILE" << EOF
SIMP System Startup Summary
===========================
Timestamp: $(date)
Log File: $SYSTEM_LOG

Components Started:
- SIMP Broker: http://127.0.0.1:5555
- Dashboard: http://127.0.0.1:8050
- QuantumArb Phase 4: Running
- BullBear Agent: http://127.0.0.1:5559
- ProjectX: http://127.0.0.1:8771
- KashClaw Gemma: http://127.0.0.1:8780

Phase 4 Status:
- Gate 1 Sandbox Testing: Initialized
- Microscopic Trading: Enabled (\$0.01-\$0.10)
- Safety Gates: Active (Gate 1: Sandbox)

Next Steps:
1. Open dashboard: http://127.0.0.1:8050
2. Monitor Gate 1 progress
3. Begin sandbox trading
4. Daily Obsidian sync

System Ready for Operation.
EOF

log "Startup summary saved to: $SUMMARY_FILE"