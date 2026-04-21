#!/bin/bash
# Monitoring script for Gate 4 agent

set -e

echo "Gate 4 Agent Monitoring"
echo "======================="
echo "Time: $(date)"
echo

# Check if agent is running
if pgrep -f "gate4_scaled_microscopic_agent" > /dev/null; then
    echo "✓ Agent is running"
    
    # Check log file
    if [ -f "logs/gate4_agent.log" ]; then
        echo "✓ Log file exists"
        echo "  Size: $(du -h logs/gate4_agent.log | cut -f1)"
        echo "  Last 5 lines:"
        tail -5 logs/gate4_agent.log
    else
        echo "✗ Log file not found"
    fi
    
    # Check performance data
    if [ -f "data/gate4_performance.jsonl" ]; then
        echo "✓ Performance data exists"
        echo "  Records: $(wc -l < data/gate4_performance.jsonl)"
    fi
    
else
    echo "✗ Agent is not running"
    
    # Check for error logs
    if [ -f "logs/gate4_agent.error.log" ]; then
        echo "Error log contents:"
        tail -20 logs/gate4_agent.error.log
    fi
fi

echo
echo "System Resources:"
echo "-----------------"
top -b -n 1 | head -5
echo
echo "Disk space:"
df -h . | tail -1
