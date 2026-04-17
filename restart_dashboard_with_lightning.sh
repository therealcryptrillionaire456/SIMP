#!/bin/bash
# Restart SIMP dashboard with Agent Lightning integration

echo "================================================"
echo "🚀 Restarting SIMP Dashboard with Agent Lightning"
echo "================================================"

# Kill existing dashboard processes
echo "Stopping existing dashboard..."
pkill -f "dashboard/server.py" 2>/dev/null || true
pkill -f "uvicorn.*dashboard" 2>/dev/null || true
sleep 2

# Set Agent Lightning environment variables
export AGENT_LIGHTNING_ENABLED=true
export AGENT_LIGHTNING_PROXY_HOST=localhost
export AGENT_LIGHTNING_PROXY_PORT=8320
export AGENT_LIGHTNING_STORE_HOST=localhost
export AGENT_LIGHTNING_STORE_PORT=43887
export AGENT_LIGHTNING_MODEL=glm-4-plus
export AGENT_LIGHTNING_ENABLE_APO=true
export AGENT_LIGHTNING_TRACE_ALL_AGENTS=true

# Start dashboard
echo "Starting dashboard with Agent Lightning integration..."
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
python3.10 -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8050 --reload > /tmp/dashboard.log 2>&1 &

echo "Waiting for dashboard to start..."
sleep 5

# Check if dashboard is running
if curl -s http://127.0.0.1:8050/health > /dev/null; then
    echo "✅ Dashboard started successfully"
    echo ""
    echo "Agent Lightning Dashboard URLs:"
    echo "  Main Dashboard: http://127.0.0.1:8050/"
    echo "  Agent Lightning UI: http://127.0.0.1:8050/agent-lightning-ui/"
    echo "  Agent Lightning Health: http://127.0.0.1:8050/agent-lightning/health"
    echo "  Agent Lightning Performance: http://127.0.0.1:8050/agent-lightning/performance"
    echo ""
    echo "Logs: /tmp/dashboard.log"
else
    echo "❌ Dashboard failed to start"
    echo "Check /tmp/dashboard.log for details"
fi
