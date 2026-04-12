#!/bin/bash
# Watchtower - SIMP flock observability script
# Lightweight health checks for the SIMP system

echo "=== SIMP Watchtower ==="
echo "Timestamp: $(date)"
echo ""

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "WARNING: jq not found. Install with: brew install jq"
    echo "Falling back to basic checks..."
    USE_JQ=false
else
    USE_JQ=true
fi

echo "1. Broker Health (port 5555):"
if $USE_JQ; then
    BROKER_HEALTH=$(curl -s -m 5 http://127.0.0.1:5555/health 2>/dev/null)
    if [ -n "$BROKER_HEALTH" ]; then
        echo "$BROKER_HEALTH" | jq -r '"Status: \(.status)\nMessage: \(.message)"'
    else
        echo "Broker unreachable or timeout"
    fi
else
    curl -s -m 5 http://127.0.0.1:5555/health 2>/dev/null && echo "Broker responding" || echo "Broker unreachable"
fi

echo ""
echo "2. Agent Count:"
if $USE_JQ; then
    BROKER_STATS=$(curl -s -m 5 http://127.0.0.1:5555/stats 2>/dev/null)
    if [ -n "$BROKER_STATS" ]; then
        AGENT_COUNT=$(echo "$BROKER_STATS" | jq -r '.agents_count // 0')
        echo "Registered agents: $AGENT_COUNT"
    else
        echo "Stats unavailable"
    fi
else
    curl -s -m 5 http://127.0.0.1:5555/stats 2>/dev/null && echo "Stats available" || echo "Stats unavailable"
fi

echo ""
echo "3. Dashboard (port 8050):"
DASHBOARD_RESPONSE=$(curl -s -m 5 http://127.0.0.1:8050/ 2>/dev/null)
if echo "$DASHBOARD_RESPONSE" | grep -q "SIMP"; then
    echo "Dashboard OK"
else
    echo "Dashboard down or not responding"
fi

echo ""
echo "4. ProjectX (port 8771):"
PROJECTX_RESPONSE=$(curl -s -m 5 http://127.0.0.1:8771/health 2>/dev/null)
if [ -n "$PROJECTX_RESPONSE" ]; then
    echo "ProjectX responding"
else
    echo "ProjectX not responding (may be normal if not running)"
fi

echo ""
echo "5. TimesFM Service (port 8780):"
TIMESFM_RESPONSE=$(curl -s -m 5 http://127.0.0.1:8780/health 2>/dev/null)
if [ -n "$TIMESFM_RESPONSE" ]; then
    echo "TimesFM responding"
else
    echo "TimesFM not responding (may be normal if not running)"
fi

echo ""
echo "6. Process Check:"
echo "Broker process: $(ps aux | grep -v grep | grep -c "python.*broker") running"
echo "Dashboard process: $(ps aux | grep -v grep | grep -c "python.*dashboard") running"

echo ""
echo "=== End Report ==="
echo "Healthy if: Broker responding, Dashboard OK, >0 agents"
echo "Run every 30s: watch -n 30 ./scripts/watchtower.sh"