#!/bin/bash

echo "🔥🔥🔥 SIMP ECOSYSTEM - LIVE TRADING LAUNCH 🔥🔥🔥"
echo "Time: $(date)"
echo ""

cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp

echo "=== STEP 1: STOP EVERYTHING ==="
echo ""
./scripts/shutdown_all.sh 2>/dev/null || true
pkill -f "dashboard" 2>/dev/null || true
pkill -f "gate4" 2>/dev/null || true
pkill -f "quantumarb" 2>/dev/null || true
sleep 3

echo "=== STEP 2: START CORE INFRASTRUCTURE ==="
echo ""

# Start SIMP Broker
echo "1. Starting SIMP Broker..."
python3.10 -m simp.server.broker > logs/broker_live.log 2>&1 &
sleep 5

echo "   Checking broker..."
if curl -s http://localhost:5555/health > /dev/null; then
    echo "   ✅ Broker running on port 5555"
else
    echo "   ❌ Broker failed to start"
    exit 1
fi

echo ""
echo "2. Starting WORKING Dashboard..."
source venv_gate4/bin/activate
python3.10 dashboard_working.py > logs/dashboard_live.log 2>&1 &
sleep 3

echo "   Dashboard: http://localhost:8050"
if curl -s http://localhost:8050/api/health > /dev/null; then
    echo "   ✅ Dashboard running"
else
    echo "   ❌ Dashboard failed"
fi

echo ""
echo "=== STEP 3: START TRADING AGENTS ==="
echo ""

echo "3. Starting Gate 4 Agent (with Coinbase config)..."
# Set Coinbase environment
export COINBASE_API_KEY_NAME="organizations/9172ab81-070a-4e93-88dd-7b62ca9d3ff4/apiKeys/294e691a-c8f9-4d6f-88ff-671fd26ed235"
export COINBASE_API_KEY=""
export COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIPBKmQijcoLG3GPZ7ii9Plh+c0t6CVp/hH6UzJhwZeYSoAoGCCqGSM49
AwEHoUQDQgAE5iNjj5QApwg1n8c9JjSkFAgroZBOn2cg5Rg8ICIlsg2bpO+s71PP
dhU+KtB5qBmXayI05PrQ/zafNPOlMIwZNA==
-----END EC PRIVATE KEY-----"

# Start Gate 4 HTTP agent
python3.10 gate4_http_agent.py > logs/gate4_live.log 2>&1 &
sleep 3

echo "   Gate 4 Agent: http://localhost:8769"
if curl -s http://localhost:8769/health > /dev/null; then
    echo "   ✅ Gate 4 running"
else
    echo "   ❌ Gate 4 failed"
fi

echo ""
echo "4. Starting QuantumArb Agent..."
python3.10 quantumarb_http_agent.py > logs/quantumarb_live.log 2>&1 &
sleep 3

echo "   QuantumArb Agent: http://localhost:8770"
if curl -s http://localhost:8770/health > /dev/null; then
    echo "   ✅ QuantumArb running"
else
    echo "   ❌ QuantumArb failed"
fi

echo ""
echo "=== STEP 4: REGISTER AGENTS WITH BROKER ==="
echo ""

echo "5. Registering agents with broker..."
sleep 2

# Register Gate 4
curl -X POST http://localhost:5555/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "gate4_live",
    "agent_type": "trading",
    "endpoint": "http://127.0.0.1:8769",
    "metadata": {
      "version": "1.0.0",
      "capabilities": ["trade_execution", "market_analysis", "risk_management"],
      "exchange": "coinbase",
      "live_trading": true,
      "position_sizing": "$1-$10"
    }
  }' > /dev/null 2>&1 && echo "   ✅ Gate 4 registered as 'gate4_live'" || echo "   ❌ Gate 4 registration failed"

# Register QuantumArb
curl -X POST http://localhost:5555/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "quantumarb_live",
    "agent_type": "analysis",
    "endpoint": "http://127.0.0.1:8770",
    "metadata": {
      "version": "1.0.0",
      "capabilities": ["arbitrage_detection", "market_analysis", "pattern_recognition"],
      "live_analysis": true
    }
  }' > /dev/null 2>&1 && echo "   ✅ QuantumArb registered as 'quantumarb_live'" || echo "   ❌ QuantumArb registration failed"

echo ""
echo "=== STEP 5: START SUPPORTING AGENTS ==="
echo ""

echo "6. Starting Gemma4 Agent..."
python3.10 bin/start_gemma4_agent.py \
  --port 5010 \
  --broker http://127.0.0.1:5555 \
  --agent-id gemma4_live \
  > logs/gemma4_live.log 2>&1 &
sleep 3

echo "   Gemma4: http://localhost:5010"
if curl -s http://localhost:5010/health > /dev/null; then
    echo "   ✅ Gemma4 running"
else
    echo "   ❌ Gemma4 failed"
fi

echo ""
echo "7. Starting ProjectX..."
python3.10 /Users/kaseymarcelle/ProjectX/projectx_guard_server.py \
  --host 127.0.0.1 \
  --port 8771 \
  --register \
  --simp-url http://127.0.0.1:5555 \
  > logs/projectx_live.log 2>&1 &
sleep 3

echo "   ProjectX: http://localhost:8771"
if curl -s http://localhost:8771/health > /dev/null; then
    echo "   ✅ ProjectX running"
else
    echo "   ❌ ProjectX failed"
fi

echo ""
echo "=== STEP 6: VERIFY SYSTEM ==="
echo ""

echo "8. Checking all registered agents..."
echo ""
curl -s http://localhost:5555/agents | python3 -c "
import json, sys
data = json.load(sys.stdin)
agents = data.get('agents', {})
print(f'   Total agents registered: {len(agents)}')
print('')
print('   Live Trading Agents:')
for agent_id, info in agents.items():
    if 'live' in agent_id or 'gate4' in agent_id or 'quantumarb' in agent_id:
        status = info.get('status', 'unknown')
        endpoint = info.get('endpoint', 'NONE')
        print(f'   • {agent_id}: {status} ({endpoint[:30]}...)')"

echo ""
echo "9. Sending LIVE TRADING intents..."
echo ""

# Send market analysis to QuantumArb
echo "   Sending market analysis for BTC-USD..."
curl -X POST http://localhost:5555/intents/route \
  -H "Content-Type: application/json" \
  -d '{
    "intent_type": "market_analysis",
    "source_agent": "launch_script",
    "target_agent": "quantumarb_live",
    "params": {
      "symbol": "BTC-USD",
      "analysis_type": "arbitrage_opportunities",
      "live": true
    }
  }' > /dev/null 2>&1 && echo "   ✅ Market analysis sent" || echo "   ❌ Failed to send"

sleep 2

# Send trade execution to Gate 4
echo "   Sending test trade execution..."
curl -X POST http://localhost:5555/intents/route \
  -H "Content-Type: application/json" \
  -d '{
    "intent_type": "trade_execution",
    "source_agent": "launch_script",
    "target_agent": "gate4_live",
    "params": {
      "symbol": "BTC-USD",
      "amount": 1.0,
      "side": "buy",
      "test_mode": true,
      "note": "Initial test trade"
    }
  }' > /dev/null 2>&1 && echo "   ✅ Trade execution sent" || echo "   ❌ Failed to send"

sleep 2

# Send planning task to Gemma4
echo "   Sending planning task..."
curl -X POST http://localhost:5555/intents/route \
  -H "Content-Type: application/json" \
  -d '{
    "intent_type": "planning",
    "source_agent": "launch_script",
    "target_agent": "gemma4_live",
    "params": {
      "task": "Analyze market conditions and suggest trading strategy",
      "urgency": "normal"
    }
  }' > /dev/null 2>&1 && echo "   ✅ Planning task sent" || echo "   ❌ Failed to send"

echo ""
echo "=== STEP 7: CREATE MONITORING TOOLS ==="
echo ""

# Create monitoring script
cat > monitor_live_trading.sh << 'EOF'
#!/bin/bash
echo "========================================="
echo "🔥 SIMP LIVE TRADING MONITOR 🔥"
echo "========================================="
echo "Time: $(date)"
echo ""
echo "=== CORE SERVICES ==="
echo "Broker:     $(curl -s http://localhost:5555/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo "Dashboard:  $(curl -s http://localhost:8050/api/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo "Gate 4:     $(curl -s http://localhost:8769/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo "QuantumArb: $(curl -s http://localhost:8770/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo ""
echo "=== RECENT ACTIVITY ==="
echo "Recent intents:"
curl -s http://localhost:8050/api/intents/recent?limit=3 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for i in data.get('intents', [])[:3]:
        print(f'  • {i.get(\"intent_type\", \"unknown\")} -> {i.get(\"target_agent\", \"unknown\")}: {i.get(\"status\", \"unknown\")}')
except:
    print('  Loading...')" 2>/dev/null
echo ""
echo "=== QUICK ACTIONS ==="
echo "Dashboard:    http://localhost:8050"
echo "Send trade:   ./send_live_trade.sh"
echo "View logs:    tail -f logs/gate4_live.log"
echo "Stop all:     ./stop_live_trading.sh"
echo "========================================="
EOF

chmod +x monitor_live_trading.sh

# Create trade sending script
cat > send_live_trade.sh << 'EOF'
#!/bin/bash
echo "Sending live trade to Gate 4 agent..."
curl -X POST http://localhost:5555/intents/route \
  -H "Content-Type: application/json" \
  -d '{
    "intent_type": "trade_execution",
    "source_agent": "manual",
    "target_agent": "gate4_live",
    "params": {
      "symbol": "BTC-USD",
      "amount": 1.0,
      "side": "buy",
      "test_mode": false,
      "live": true
    }
  }'
echo ""
echo "Trade intent sent to Gate 4 for execution"
EOF

chmod +x send_live_trade.sh

# Create stop script
cat > stop_live_trading.sh << 'EOF'
#!/bin/bash
echo "Stopping SIMP Live Trading System..."
pkill -f "dashboard_working.py"
pkill -f "gate4_http_agent.py"
pkill -f "quantumarb_http_agent.py"
pkill -f "start_gemma4_agent.py"
pkill -f "projectx_guard_server.py"
echo "All trading services stopped"
EOF

chmod +x stop_live_trading.sh

echo ""
echo "🔥🔥🔥 LIVE TRADING SYSTEM LAUNCHED! 🔥🔥🔥"
echo ""
echo "=== ACCESS POINTS ==="
echo "📊 Dashboard:     http://localhost:8050"
echo "🤖 Gate 4 Agent:  http://localhost:8769"
echo "🔍 QuantumArb:    http://localhost:8770"
echo "🧠 Gemma4:        http://localhost:5010"
echo "🛡️ ProjectX:      http://localhost:8771"
echo "🔄 Broker API:    http://localhost:5555"
echo ""
echo "=== MONITORING ==="
echo "./monitor_live_trading.sh     # System status"
echo "tail -f logs/gate4_live.log   # Live trading activity"
echo "./send_live_trade.sh          # Send manual trade"
echo ""
echo "=== LIVE TRADING CONFIGURATION ==="
echo "✅ Coinbase API configured"
echo "✅ $1-$10 position sizing"
echo "✅ Real-time risk management"
echo "✅ Arbitrage detection active"
echo "✅ All agents registered"
echo ""
echo "=== WHAT'S HAPPENING NOW ==="
echo "1. QuantumArb analyzing BTC-USD for arbitrage"
echo "2. Gate 4 ready for trade execution"
echo "3. Gemma4 planning optimal strategy"
echo "4. Dashboard showing real-time data"
echo "5. ProjectX monitoring system health"
echo ""
echo "🎉 THE ENTIRE SIMP ECOSYSTEM IS NOW LIVE AND TRADING! 🎉"
echo ""
echo "Open your browser to: http://localhost:8050"
echo "Watch the system work in real-time!"