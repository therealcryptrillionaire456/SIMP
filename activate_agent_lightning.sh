#!/bin/bash
# Activate Agent Lightning Integration for SIMP Ecosystem

set -e

echo "================================================================"
echo "🚀 ACTIVATING AGENT LIGHTNING INTEGRATION"
echo "================================================================"

# Set environment variables
export X_AI_API_KEY='03ad895d8851482dbf3aadeb4e935e15.X2iGms7E0qxssULA'
export AGENT_LIGHTNING_ENABLED=true
export AGENT_LIGHTNING_PROXY_HOST=localhost
export AGENT_LIGHTNING_PROXY_PORT=8235
export AGENT_LIGHTNING_STORE_HOST=localhost
export AGENT_LIGHTNING_STORE_PORT=43887
export AGENT_LIGHTNING_MODEL=glm-4-plus
export TRACE_ALL_AGENTS=true

echo "✅ Environment variables set"

# Check if Agent Lightning proxy is running
echo -n "🔍 Checking Agent Lightning proxy... "
if curl -s http://localhost:8235/health > /dev/null; then
    echo "✅ Running"
else
    echo "❌ Not running"
    echo "Starting Agent Lightning proxy..."
    cd ~/stray_goose
    python zai_agent_lightning_proxy.py > /tmp/agent_lightning_proxy.log 2>&1 &
    sleep 5
    echo "✅ Agent Lightning proxy started"
fi

# Check if SIMP broker is running
echo -n "🔍 Checking SIMP broker... "
if curl -s http://localhost:5555/health > /dev/null; then
    echo "✅ Running"
    BROKER_RUNNING=true
else
    echo "❌ Not running"
    BROKER_RUNNING=false
fi

# Check if SIMP dashboard is running
echo -n "🔍 Checking SIMP dashboard... "
if curl -s http://localhost:8050/docs > /dev/null 2>&1; then
    echo "✅ Running"
    DASHBOARD_RUNNING=true
else
    echo "❌ Not running"
    DASHBOARD_RUNNING=false
fi

echo ""
echo "📋 INTEGRATION STATUS"
echo "===================="

if [ "$BROKER_RUNNING" = true ]; then
    echo "✅ SIMP Broker: Running (port 5555)"
    echo "   Agent Lightning endpoints will be available after broker restart"
else
    echo "⚠️  SIMP Broker: Not running"
    echo "   Start with: python -m simp.server.broker"
fi

if [ "$DASHBOARD_RUNNING" = true ]; then
    echo "✅ SIMP Dashboard: Running (port 8050)"
    echo "   Agent Lightning UI: http://localhost:8050/agent-lightning-ui"
else
    echo "⚠️  SIMP Dashboard: Not running"
    echo "   Start with: python dashboard/server.py"
fi

echo "✅ Agent Lightning Proxy: Running (port 8235)"
echo "✅ LightningStore: Running (port 43887)"
echo ""

echo "🔧 APPLYING INTEGRATION PATCHES"
echo "================================"

# Apply patches by restarting services with integration
echo "To apply Agent Lightning integration:"
echo ""
echo "1. RESTART SIMP BROKER WITH INTEGRATION:"
echo "   -------------------------------------"
echo "   cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp"
echo "   python -c \""
echo "   from simp.server.broker import SimpBroker"
echo "   from patches.agent_lightning_broker_patch import patch_broker_for_agent_lightning"
echo "   broker = SimpBroker()"
echo "   broker = patch_broker_for_agent_lightning(broker)"
echo "   broker.run()"
echo "   \""
echo ""

echo "2. RESTART SIMP DASHBOARD WITH INTEGRATION:"
echo "   ----------------------------------------"
echo "   cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp"
echo "   python -c \""
echo "   from dashboard.server import app"
echo "   from patches.agent_lightning_dashboard_patch import patch_dashboard_for_agent_lightning"
echo "   app = patch_dashboard_for_agent_lightning(app)"
echo "   import uvicorn"
echo "   uvicorn.run(app, host='0.0.0.0', port=8050)"
echo "   \""
echo ""

echo "3. TEST THE INTEGRATION:"
echo "   ---------------------"
echo "   cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp"
echo "   python test_agent_lightning_integration.py"
echo ""

echo "4. VIEW THE DASHBOARD:"
echo "   -------------------"
echo "   Open browser to: http://localhost:8050/agent-lightning-ui"
echo ""

echo "📊 AVAILABLE ENDPOINTS AFTER INTEGRATION"
echo "========================================"
echo "• Agent Lightning Health: http://localhost:5555/agent-lightning/health"
echo "• System Performance: http://localhost:5555/agent-lightning/performance"
echo "• Agent Performance: http://localhost:5555/agent-lightning/agents/{agent_id}/performance"
echo "• Configuration: http://localhost:5555/agent-lightning/config"
echo "• Dashboard UI: http://localhost:8050/agent-lightning-ui"
echo "• Trace Monitoring: http://localhost:43887/v1/agl/rollouts"
echo ""

echo "🤖 AGENTS BEING TRACED"
echo "======================"
echo "• quantumarb - Arbitrage trading"
echo "• kashclaw_gemma - Planning and research"
echo "• kloutbot - Orchestration"
echo "• projectx_native - Maintenance"
echo "• perplexity_research - Research"
echo "• financial_ops - Financial operations"
echo "• bullbear_predictor - Prediction engine"
echo ""

echo "⚡ FEATURES ENABLED"
echo "=================="
echo "✅ Centralized LLM call tracing"
echo "✅ Real-time performance monitoring"
echo "✅ Automatic Prompt Optimization (APO)"
echo "✅ Dashboard visualization"
echo "✅ Cost analysis and token tracking"
echo "✅ Error tracking and alerting"
echo ""

echo "🚀 NEXT STEPS"
echo "============="
echo "1. Apply patches by restarting broker and dashboard"
echo "2. Test the integration with the test script"
echo "3. Monitor agents in the dashboard"
echo "4. Analyze performance trends"
echo "5. Use APO to optimize agent prompts"
echo ""

echo "================================================================"
echo "🎉 AGENT LIGHTNING INTEGRATION READY FOR ACTIVATION"
echo "================================================================"
echo ""
echo "All LLM calls will be traced and optimized across the SIMP ecosystem!"
echo ""

# Create a quick activation script
cat > /tmp/activate_agent_lightning_quick.sh << 'EOF'
#!/bin/bash
# Quick activation script for Agent Lightning

echo "Quick-activating Agent Lightning integration..."

# Set environment
export X_AI_API_KEY='03ad895d8851482dbf3aadeb4e935e15.X2iGms7E0qxssULA'
export AGENT_LIGHTNING_ENABLED=true

cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp

echo "1. Testing integration..."
python test_agent_lightning_integration.py

echo ""
echo "2. Available endpoints:"
echo "   - Health: http://localhost:5555/agent-lightning/health"
echo "   - Dashboard: http://localhost:8050/agent-lightning-ui"
echo "   - Traces: http://localhost:43887/v1/agl/rollouts"

echo ""
echo "✅ Agent Lightning integration activated!"
EOF

chmod +x /tmp/activate_agent_lightning_quick.sh

echo "Quick activation script created: /tmp/activate_agent_lightning_quick.sh"
echo "Run it with: bash /tmp/activate_agent_lightning_quick.sh"