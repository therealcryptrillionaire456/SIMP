#!/bin/bash
# SIMP System Startup Script
# Activates all systems, starts all processes, and verifies everything is running

set -e  # Exit on error

echo "========================================="
echo "SIMP SYSTEM STARTUP"
echo "========================================="

# Configuration
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="$PROJECT_ROOT/config"
LOG_DIR="$PROJECT_ROOT/logs"
SCRIPT_DIR="$PROJECT_ROOT/scripts"
DATA_DIR="$PROJECT_ROOT/data"
VENV_DIR="$PROJECT_ROOT/venv_gate4"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

# Function to check if a process is running
check_process() {
    local process_name="$1"
    if pgrep -f "$process_name" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to check if a port is listening
check_port() {
    local port="$1"
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local url="$1"
    local timeout="$2"
    local interval=2
    local elapsed=0
    
    print_info "Waiting for $url (timeout: ${timeout}s)..."
    
    while [ $elapsed -lt $timeout ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            print_status "Service ready: $url"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    
    print_error "Timeout waiting for $url"
    return 1
}

# Function to start a process in background
start_background() {
    local name="$1"
    local command="$2"
    local log_file="$3"
    
    print_info "Starting $name..."
    
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$log_file")"
    
    # Start process in background
    eval "$command" >> "$log_file" 2>&1 &
    local pid=$!
    
    # Save PID to file
    echo $pid > "$LOG_DIR/${name}.pid"
    
    # Wait a moment for process to start
    sleep 2
    
    # Check if process is running
    if check_process "$name"; then
        print_status "$name started (PID: $pid)"
        return 0
    else
        print_error "Failed to start $name"
        return 1
    fi
}

# =========================================
# STARTUP SEQUENCE
# =========================================

echo
print_info "Starting SIMP System Startup Sequence..."
echo

# Step 1: Check Python version
print_info "Step 1: Checking Python version..."
PYTHON_VERSION=$(python3.10 --version 2>/dev/null || echo "not found")
if [[ $PYTHON_VERSION == *"3.10"* ]]; then
    print_status "Python 3.10 found: $PYTHON_VERSION"
else
    print_error "Python 3.10 not found. Please install Python 3.10."
    exit 1
fi

# Step 2: Activate virtual environment
print_info "Step 2: Activating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    print_status "Virtual environment activated: $VENV_DIR"
else
    print_warning "Virtual environment not found. Creating..."
    python3.10 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Install dependencies
    print_info "Installing dependencies..."
    pip install --upgrade pip
    pip install numpy pandas scipy aiohttp pytest cryptography pydantic flask fastapi uvicorn httpx
    
    print_status "Virtual environment created and activated"
fi

# Step 3: Create necessary directories
print_info "Step 3: Creating directories..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$SCRIPT_DIR"
print_status "Directories created"

# Step 4: Validate Gate 4 configuration
print_info "Step 4: Validating Gate 4 configuration..."
if [ -f "$CONFIG_DIR/gate4_scaled_microscopic.json" ]; then
    python3.10 "$SCRIPT_DIR/validate_gate4.py" "$CONFIG_DIR/gate4_scaled_microscopic.json"
    if [ $? -ne 0 ]; then
        print_warning "Configuration validation failed, creating default..."
        python3.10 "$SCRIPT_DIR/validate_gate4.py" --create-config "$CONFIG_DIR/gate4_scaled_microscopic.json"
    fi
else
    print_warning "Configuration file not found, creating default..."
    python3.10 "$SCRIPT_DIR/validate_gate4.py" --create-config "$CONFIG_DIR/gate4_scaled_microscopic.json"
fi
print_status "Gate 4 configuration validated"

# Step 5: Start SIMP Broker (port 5555)
print_info "Step 5: Starting SIMP Broker..."
if check_port 5555; then
    print_status "SIMP Broker already running on port 5555"
else
    start_background "simp_broker" \
        "python3.10 -m simp.server.broker" \
        "$LOG_DIR/simp_broker.log"
    
    # Wait for broker to be ready
    wait_for_service "http://127.0.0.1:5555/health" 30
fi

# Step 6: Start Dashboard (port 8050)
print_info "Step 6: Starting Dashboard..."
if check_port 8050; then
    print_status "Dashboard already running on port 8050"
else
    # Change to project root to ensure proper imports
    cd "$PROJECT_ROOT"
    start_background "dashboard" \
        "python3.10 -m dashboard.server" \
        "$LOG_DIR/dashboard.log"
    
    # Wait for dashboard to be ready
    wait_for_service "http://127.0.0.1:8050/" 30
fi

# Step 7: Start ProjectX (port 8771)
print_info "Step 7: Starting ProjectX..."
if check_port 8771; then
    print_status "ProjectX already running on port 8771"
else
    # Check if ProjectX exists
    if [ -f "/Users/kaseymarcelle/ProjectX/projectx_guard_server.py" ]; then
        start_background "projectx" \
            "python3.10 /Users/kaseymarcelle/ProjectX/projectx_guard_server.py" \
            "$LOG_DIR/projectx.log"
        
        # Wait for ProjectX to be ready
        wait_for_service "http://127.0.0.1:8771/health" 30
    else
        print_warning "ProjectX not found at /Users/kaseymarcelle/ProjectX/"
    fi
fi

# Step 8: Start Gemma4 Agent (port 8780)
print_info "Step 8: Starting Gemma4 Agent..."
if check_port 8780; then
    print_status "Gemma4 Agent already running on port 8780"
else
    # Check if Gemma4 agent exists
    if [ -f "/Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py" ]; then
        start_background "gemma4_agent" \
            "python3.10 /Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py" \
            "$LOG_DIR/gemma4_agent.log"
        
        # Wait for Gemma4 to be ready
        wait_for_service "http://127.0.0.1:8780/health" 30
    else
        print_warning "Gemma4 agent not found at /Users/kaseymarcelle/bullbear/agents/"
    fi
fi

# Step 9: Start Gate 4 Agent
print_info "Step 9: Starting Gate 4 Scaled Microscopic Agent..."
if check_process "gate4_scaled_microscopic_agent"; then
    print_status "Gate 4 Agent already running"
else
    print_info "Starting Gate 4 Agent..."
    cd "$PROJECT_ROOT"
    
    # Start the agent in background
    python3.10 agents/gate4_scaled_microscopic_agent.py --config config/gate4_scaled_microscopic.json > "$LOG_DIR/gate4_agent.log" 2>&1 &
    AGENT_PID=$!
    
    # Save PID
    echo $AGENT_PID > "$LOG_DIR/gate4_agent.pid"
    
    # Give agent time to initialize
    sleep 5
    
    if check_process "gate4_scaled_microscopic_agent"; then
        print_status "Gate 4 Agent started (PID: $AGENT_PID)"
    else
        print_warning "Gate 4 Agent may have failed to start or exited"
        print_info "Check logs: tail -f $LOG_DIR/gate4_agent.log"
    fi
fi

# Step 10: Verify all systems
print_info "Step 10: Verifying all systems..."
echo

# Check SIMP Broker
if check_port 5555; then
    print_status "SIMP Broker: ✓ Running on port 5555"
    # Get broker status
    BROKER_STATUS=$(curl -s http://127.0.0.1:5555/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Agents: {data.get(\"agents_online\", 0)}, Intents: {data.get(\"pending_intents\", 0)}')")
    print_info "  $BROKER_STATUS"
else
    print_error "SIMP Broker: ✗ Not running"
fi

# Check Dashboard
if check_port 8050; then
    print_status "Dashboard: ✓ Running on port 8050"
    print_info "  Access at: http://localhost:8050"
else
    print_error "Dashboard: ✗ Not running"
fi

# Check ProjectX
if check_port 8771; then
    print_status "ProjectX: ✓ Running on port 8771"
else
    print_warning "ProjectX: ⚠ Not running (optional)"
fi

# Check Gemma4
if check_port 8780; then
    print_status "Gemma4 Agent: ✓ Running on port 8780"
else
    print_warning "Gemma4 Agent: ⚠ Not running (optional)"
fi

# Check Gate 4 Agent
if check_process "gate4_scaled_microscopic_agent"; then
    print_status "Gate 4 Agent: ✓ Running"
    
    # Check if agent is registered with broker
    sleep 2
    AGENTS=$(curl -s http://127.0.0.1:5555/agents | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    agents = data.get('agents', [])
    gate4_found = any('gate4' in agent.get('id', '').lower() for agent in agents)
    if gate4_found:
        print('  Registered with SIMP broker: ✓')
    else:
        print('  Not registered with broker: ⚠')
except:
    print('  Could not check broker registration')
")
    print_info "$AGENTS"
else
    print_error "Gate 4 Agent: ✗ Not running"
fi

# Step 11: Create monitoring dashboard
print_info "Step 11: Creating monitoring dashboard..."
cat > "$SCRIPT_DIR/monitor_all.sh" << 'EOF'
#!/bin/bash
# SIMP System Monitoring Dashboard

echo "========================================="
echo "SIMP SYSTEM MONITORING DASHBOARD"
echo "========================================="
echo "Time: $(date)"
echo

# System Resources
echo "=== SYSTEM RESOURCES ==="
echo "CPU Load:"
uptime | awk -F'load average:' '{print $2}'
echo
echo "Memory Usage:"
free -h | awk 'NR==2{printf "Used: %s/%s (%.1f%%)\n", $3, $2, $3/$2*100}'
echo
echo "Disk Space:"
df -h . | tail -1 | awk '{printf "Used: %s/%s (%s)\n", $3, $2, $5}'
echo

# Process Status
echo "=== PROCESS STATUS ==="
check_proc() {
    if pgrep -f "$1" > /dev/null; then
        echo "✓ $2"
    else
        echo "✗ $2"
    fi
}

check_proc "simp.server.broker" "SIMP Broker"
check_proc "dashboard/server.py" "Dashboard"
check_proc "projectx_guard_server" "ProjectX"
check_proc "kashclaw_gemma_agent" "Gemma4 Agent"
check_proc "gate4_scaled_microscopic_agent" "Gate 4 Agent"
echo

# Port Status
echo "=== PORT STATUS ==="
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "✓ Port $1: $2"
    else
        echo "✗ Port $1: $2"
    fi
}

check_port 5555 "SIMP Broker"
check_port 8050 "Dashboard"
check_port 8771 "ProjectX"
check_port 8780 "Gemma4 Agent"
echo

# Log Files
echo "=== LOG FILES ==="
for log in simp_broker.log dashboard.log projectx.log gemma4_agent.log gate4_agent.log; do
    if [ -f "logs/$log" ]; then
        size=$(du -h "logs/$log" 2>/dev/null | cut -f1 || echo "0B")
        lines=$(wc -l < "logs/$log" 2>/dev/null || echo "0")
        echo "📄 $log: $size, $lines lines"
    else
        echo "📄 $log: Not found"
    fi
done
echo

# Recent Errors
echo "=== RECENT ERRORS (last 5) ==="
for log in simp_broker.log dashboard.log gate4_agent.log; do
    if [ -f "logs/$log" ]; then
        errors=$(grep -i "error\|exception\|failed\|critical" "logs/$log" | tail -5)
        if [ -n "$errors" ]; then
            echo "🔴 $log:"
            echo "$errors" | sed 's/^/  /'
            echo
        fi
    fi
done

# Gate 4 Performance
echo "=== GATE 4 PERFORMANCE ==="
if [ -f "data/gate4_performance.jsonl" ]; then
    count=$(wc -l < "data/gate4_performance.jsonl")
    echo "Performance records: $count"
    
    # Get latest performance if available
    if [ $count -gt 0 ]; then
        latest=$(tail -1 "data/gate4_performance.jsonl")
        echo "Latest metrics available in data/gate4_performance.jsonl"
    fi
else
    echo "No performance data yet"
fi
echo

echo "========================================="
echo "Quick Commands:"
echo "  Start all: ./scripts/startup_all.sh"
echo "  Stop all: ./scripts/shutdown_all.sh"
echo "  Monitor: ./scripts/monitor_all.sh"
echo "  Gate 4 logs: tail -f logs/gate4_agent.log"
echo "========================================="
EOF

chmod +x "$SCRIPT_DIR/monitor_all.sh"
print_status "Monitoring dashboard created: $SCRIPT_DIR/monitor_all.sh"

# Step 12: Create shutdown script
print_info "Step 12: Creating shutdown script..."
cat > "$SCRIPT_DIR/shutdown_all.sh" << 'EOF'
#!/bin/bash
# SIMP System Shutdown Script

echo "========================================="
echo "SIMP SYSTEM SHUTDOWN"
echo "========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Function to stop a process
stop_process() {
    local name="$1"
    local pattern="$2"
    
    echo -n "Stopping $name... "
    
    # Find and kill the process
    pkill -f "$pattern" 2>/dev/null
    
    # Wait a moment
    sleep 2
    
    # Force kill if still running
    if pgrep -f "$pattern" > /dev/null; then
        pkill -9 -f "$pattern" 2>/dev/null
        sleep 1
    fi
    
    # Check if stopped
    if pgrep -f "$pattern" > /dev/null; then
        print_error "Failed to stop $name"
        return 1
    else
        print_status "Stopped"
        return 0
    fi
}

# Stop processes in reverse order
echo "Stopping processes..."

# Stop Gate 4 Agent
stop_process "Gate 4 Agent" "gate4_scaled_microscopic_agent"

# Stop Gemma4 Agent
stop_process "Gemma4 Agent" "kashclaw_gemma_agent"

# Stop ProjectX
stop_process "ProjectX" "projectx_guard_server"

# Stop Dashboard
stop_process "Dashboard" "dashboard/server.py"

# Stop SIMP Broker
stop_process "SIMP Broker" "simp.server.broker"

# Clean up PID files
rm -f logs/*.pid 2>/dev/null

echo
echo "========================================="
echo "Shutdown complete"
echo "========================================="

# Final check
echo
echo "Checking for remaining processes..."
if pgrep -f "simp\|dashboard\|projectx\|gate4\|gemma" > /dev/null; then
    print_warning "Some processes may still be running:"
    pgrep -fl "simp\|dashboard\|projectx\|gate4\|gemma"
else
    print_status "All processes stopped"
fi

echo
echo "To restart the system:"
echo "  ./scripts/startup_all.sh"
echo
echo "To monitor:"
echo "  ./scripts/monitor_all.sh"
EOF

chmod +x "$SCRIPT_DIR/shutdown_all.sh"
print_status "Shutdown script created: $SCRIPT_DIR/shutdown_all.sh"

# =========================================
# STARTUP COMPLETE
# =========================================

echo
echo "========================================="
echo "SIMP SYSTEM STARTUP COMPLETE"
echo "========================================="
echo
echo "All systems have been started and verified."
echo
echo "Access Points:"
echo "  SIMP Broker:     http://localhost:5555"
echo "  Dashboard:       http://localhost:8050"
echo "  ProjectX:        http://localhost:8771"
echo "  Gemma4 Agent:    http://localhost:8780"
echo
echo "Management Commands:"
echo "  Monitor system:  ./scripts/monitor_all.sh"
echo "  Stop all:        ./scripts/shutdown_all.sh"
echo "  Restart all:     ./scripts/startup_all.sh"
echo
echo "Gate 4 Agent:"
echo "  Logs:            tail -f logs/gate4_agent.log"
echo "  Config:          config/gate4_scaled_microscopic.json"
echo "  Performance:     data/gate4_performance.jsonl"
echo
echo "Next Steps:"
echo "  1. Open dashboard: http://localhost:8050"
echo "  2. Monitor Gate 4 performance"
echo "  3. Test SIMP broker endpoints"
echo "  4. Verify agent registration"
echo
echo "========================================="

# Run initial monitoring
echo
print_info "Running initial system check..."
"$SCRIPT_DIR/monitor_all.sh"