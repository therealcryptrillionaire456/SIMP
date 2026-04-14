#!/bin/bash
# Stop script for Gate 4 agent

echo "Stopping Gate 4 agent..."

# Find and kill the agent process
pkill -f "gate4_scaled_microscopic_agent" || true

# Wait for process to stop
sleep 2

# Check if still running
if pgrep -f "gate4_scaled_microscopic_agent" > /dev/null; then
    echo "Agent still running, forcing kill..."
    pkill -9 -f "gate4_scaled_microscopic_agent" || true
fi

echo "Agent stopped"
