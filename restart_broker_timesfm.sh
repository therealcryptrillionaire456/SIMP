#!/bin/bash
# Restart broker with TimesFM enabled

set -e

echo "========================================="
echo "RESTARTING BROKER WITH TIMESFM ENABLED"
echo "========================================="

# Set environment variables
export SIMP_TIMESFM_ENABLED=true
export SIMP_TIMESFM_SHADOW_MODE=true
export SIMP_TIMESFM_CHECKPOINT="google/timesfm-2.0-500m-pytorch"
export SIMP_TIMESFM_CONTEXT_LEN=512
export SIMP_TIMESFM_HORIZON=64

# Find and kill existing broker
echo "Stopping existing broker..."
pkill -f "python.*broker.py" || true
sleep 2

# Start broker with TimesFM enabled
echo "Starting broker with TimesFM enabled..."
cd "$(dirname "$0")"

# Start broker in background
python3.10 -m simp.server.broker &
BROKER_PID=$!

echo "Broker started with PID: $BROKER_PID"

# Wait for broker to start
echo "Waiting for broker to start..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:5555/health >/dev/null 2>&1; then
        echo "Broker is healthy!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 1
done

# Check broker health
echo ""
echo "Checking broker health..."
curl -s http://127.0.0.1:5555/health | python3 -m json.tool

# Check TimesFM stats
echo ""
echo "Checking TimesFM stats..."
curl -s http://127.0.0.1:5555/stats | python3 -c "
import sys, json
data = json.load(sys.stdin)
timesfm = data.get('timesfm', {})
if timesfm:
    print('TimesFM Status:')
    print(f'  Enabled: {timesfm.get(\"enabled\", False)}')
    print(f'  Shadow Mode: {timesfm.get(\"shadow_mode\", False)}')
    print(f'  Model Loaded: {timesfm.get(\"model_loaded\", False)}')
    print(f'  Total Requests: {timesfm.get(\"total_requests\", 0)}')
else:
    print('TimesFM not yet initialized in stats')
"

echo ""
echo "========================================="
echo "BROKER RESTARTED WITH TIMESFM"
echo "========================================="
echo ""
echo "TimesFM is now enabled in shadow mode."
echo "QuantumArb agents can use TimesFM forecasts for volatility posture."
echo ""
echo "To test TimesFM integration:"
echo "1. Send a QuantumArb intent with timesfm_used=true"
echo "2. Check /stats endpoint for TimesFM activity"
echo "3. Monitor logs for TimesFM forecast requests"