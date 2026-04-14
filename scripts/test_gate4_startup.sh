#!/bin/bash
# Test Gate 4 Agent Startup

set -e

echo "========================================="
echo "GATE 4 AGENT STARTUP TEST"
echo "========================================="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Step 1: Activate virtual environment
echo "Step 1: Activating virtual environment..."
source venv_gate4/bin/activate
print_status "Virtual environment activated"

# Step 2: Validate configuration
echo "Step 2: Validating configuration..."
python3.10 scripts/validate_gate4.py
if [ $? -eq 0 ]; then
    print_status "Configuration validated"
else
    print_error "Configuration validation failed"
    exit 1
fi

# Step 3: Test agent validation
echo "Step 3: Testing agent validation..."
python3.10 agents/gate4_scaled_microscopic_agent.py --validate
if [ $? -eq 0 ]; then
    print_status "Agent validation passed"
else
    print_error "Agent validation failed"
    exit 1
fi

# Step 4: Start agent in background with timeout
echo "Step 4: Starting agent (10-second test)..."
python3.10 agents/gate4_scaled_microscopic_agent.py --config config/gate4_scaled_microscopic.json > logs/test_gate4_startup.log 2>&1 &
AGENT_PID=$!

echo "Agent started with PID: $AGENT_PID"
echo "Waiting 10 seconds for initialization..."

# Wait 10 seconds
sleep 10

# Check if agent is still running
if kill -0 $AGENT_PID 2>/dev/null; then
    print_status "Agent is running after 10 seconds"
    
    # Check logs for initialization
    if grep -q "initialized\|started\|ready" logs/test_gate4_startup.log; then
        print_status "Agent initialization detected in logs"
    else
        print_error "No initialization detected in logs"
    fi
    
    # Kill the agent
    kill $AGENT_PID 2>/dev/null
    sleep 2
    
    if kill -0 $AGENT_PID 2>/dev/null 2>&1; then
        kill -9 $AGENT_PID 2>/dev/null
        print_status "Agent stopped (force kill)"
    else
        print_status "Agent stopped gracefully"
    fi
else
    print_error "Agent exited prematurely"
    
    # Show last 20 lines of log
    echo "Last 20 lines of log:"
    tail -20 logs/test_gate4_startup.log
    exit 1
fi

# Step 5: Check SIMP broker integration
echo "Step 5: Checking SIMP broker integration..."
if curl -s http://127.0.0.1:5555/health > /dev/null; then
    print_status "SIMP broker is running"
    
    # Check agents endpoint
    AGENTS=$(curl -s http://127.0.0.1:5555/agents)
    if echo "$AGENTS" | grep -q "gate4"; then
        print_status "Gate 4 agent registered with broker"
    else
        print_error "Gate 4 agent not registered with broker"
    fi
else
    print_error "SIMP broker not running"
fi

echo
echo "========================================="
echo "TEST COMPLETE"
echo "========================================="
echo
echo "Next steps:"
echo "1. Run full startup: ./scripts/startup_all.sh"
echo "2. Monitor system: ./scripts/monitor_all.sh"
echo "3. Check dashboard: http://localhost:8050"
echo "4. Review logs: tail -f logs/gate4_agent.log"
echo
echo "Log files:"
echo "  Test log: logs/test_gate4_startup.log"
echo "  Agent log: logs/gate4_agent.log"
echo "  Broker log: logs/simp_broker.log"
echo "  Dashboard log: logs/dashboard.log"