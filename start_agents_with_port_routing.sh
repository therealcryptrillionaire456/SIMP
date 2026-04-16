#!/bin/bash

echo "🚀 SIMP Agent Startup with Port Routing System"
echo "=============================================="
echo "Time: $(date)"
echo ""

# Kill any existing dashboard processes to avoid conflicts
echo "🔄 Stopping existing dashboard processes..."
pkill -f "dashboard_final_working.py" 2>/dev/null
pkill -f "dashboard_fixed.py" 2>/dev/null
sleep 2

# Start dashboard with dynamic port allocation
echo "📊 Starting Dashboard..."
python3 dashboard_final_working.py &
DASHBOARD_PID=$!
sleep 3

# Check if dashboard started successfully
if ps -p $DASHBOARD_PID > /dev/null; then
    echo "✅ Dashboard started (PID: $DASHBOARD_PID)"
    
    # Get the actual port being used
    DASHBOARD_PORT=$(lsof -i -P -n | grep "Python.*$DASHBOARD_PID" | grep LISTEN | head -1 | awk '{print $9}' | cut -d: -f2)
    if [ -n "$DASHBOARD_PORT" ]; then
        echo "📡 Dashboard running on port: $DASHBOARD_PORT"
        echo "🔗 URL: http://localhost:$DASHBOARD_PORT"
    else
        echo "⚠️  Could not determine dashboard port"
    fi
else
    echo "❌ Failed to start dashboard"
fi

echo ""
echo "🤖 Starting Trading Agents..."

# Start Gate 4 HTTP Agent
echo "🔄 Starting Gate 4 HTTP Agent..."
python3 gate4_http_agent.py &
GATE4_PID=$!
sleep 2

if ps -p $GATE4_PID > /dev/null; then
    echo "✅ Gate 4 HTTP Agent started (PID: $GATE4_PID)"
    GATE4_PORT=$(lsof -i -P -n | grep "Python.*$GATE4_PID" | grep LISTEN | head -1 | awk '{print $9}' | cut -d: -f2)
    if [ -n "$GATE4_PORT" ]; then
        echo "📡 Gate 4 running on port: $GATE4_PORT"
    fi
else
    echo "❌ Failed to start Gate 4 HTTP Agent"
fi

# Start QuantumArb HTTP Agent
echo "🔄 Starting QuantumArb HTTP Agent..."
python3 quantumarb_http_agent.py &
QUANTUMARB_PID=$!
sleep 2

if ps -p $QUANTUMARB_PID > /dev/null; then
    echo "✅ QuantumArb HTTP Agent started (PID: $QUANTUMARB_PID)"
    QUANTUMARB_PORT=$(lsof -i -P -n | grep "Python.*$QUANTUMARB_PID" | grep LISTEN | head -1 | awk '{print $9}' | cut -d: -f2)
    if [ -n "$QUANTUMARB_PORT" ]; then
        echo "📡 QuantumArb running on port: $QUANTUMARB_PORT"
    fi
else
    echo "❌ Failed to start QuantumArb HTTP Agent"
fi

echo ""
echo "🔍 Checking System Status..."

# Wait a moment for agents to register
sleep 5

# Check broker health
echo "🩺 Checking Broker Health..."
BROKER_HEALTH=$(curl -s http://localhost:5555/health)
if echo "$BROKER_HEALTH" | grep -q "healthy"; then
    AGENTS_ONLINE=$(echo "$BROKER_HEALTH" | python3 -c "import sys, json; print(json.load(sys.stdin).get('agents_online', 'N/A'))")
    echo "✅ Broker healthy with $AGENTS_ONLINE agents online"
else
    echo "❌ Broker issues detected"
fi

# Check dashboard
echo "🖥️  Checking Dashboard..."
if [ -n "$DASHBOARD_PORT" ]; then
    DASHBOARD_HEALTH=$(curl -s http://localhost:$DASHBOARD_PORT/api/health 2>/dev/null || echo "{}")
    if echo "$DASHBOARD_HEALTH" | grep -q '"dashboard":"ok"'; then
        echo "✅ Dashboard healthy on port $DASHBOARD_PORT"
    else
        echo "⚠️  Dashboard may have issues"
    fi
fi

echo ""
echo "📋 Agent Port Summary:"
echo "======================"
if [ -n "$DASHBOARD_PORT" ]; then
    echo "📊 Dashboard:      http://localhost:$DASHBOARD_PORT"
fi
if [ -n "$GATE4_PORT" ]; then
    echo "🎯 Gate 4 Agent:   http://localhost:$GATE4_PORT"
fi
if [ -n "$QUANTUMARB_PORT" ]; then
    echo "🔬 QuantumArb:     http://localhost:$QUANTUMARB_PORT"
fi

echo ""
echo "📊 Broker:          http://localhost:5555"
echo "🤖 Gemma4 Agent:    http://localhost:5010"
echo "📈 BullBear Agent:  http://localhost:5559"
echo "🏗️  ProjectX:        http://localhost:8771"
echo "🦌 DeerFlow:        http://localhost:8888"

echo ""
echo "🚀 Startup Complete!"
echo "==================="
echo "All agents started with dynamic port routing to avoid conflicts."
echo ""
echo "💡 Next Steps:"
echo "1. Open dashboard: http://localhost:${DASHBOARD_PORT:-8050}"
echo "2. Check system health: ./verify_operational.sh"
echo "3. Send test trade: Use dashboard 'Send Test Intent' button"
echo ""
echo "✅ Port routing system is active - no more port conflicts!"