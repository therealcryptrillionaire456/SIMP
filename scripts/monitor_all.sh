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
