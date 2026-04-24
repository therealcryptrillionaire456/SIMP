#!/bin/bash

# Quick test script with built-in timeout
echo "🚀 Universal Trading System - Quick Test"
echo "=========================================="

# Set timeout using bash built-in
timeout_seconds=30
start_time=$(date +%s)

# Load environment and run test
source scripts/load_env.sh
source venv_gate4/bin/activate

# Run the test with timeout
python3.10 gate4_inbox_consumer.py --dry-run --once &
pid=$!

# Wait with timeout
while kill -0 $pid 2>/dev/null; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if [ $elapsed -ge $timeout_seconds ]; then
        echo "⏰ Timeout reached ($timeout_seconds seconds), killing process..."
        kill -9 $pid 2>/dev/null
        exit 1
    fi
    
    sleep 1
done

echo "✅ Test completed successfully"
exit 0