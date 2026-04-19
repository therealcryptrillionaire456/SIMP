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
