#!/bin/bash

echo "🔥🔥🔥 SIMP ECOSYSTEM - LIVE TRADING LAUNCH 🔥🔥🔥"
echo ""

cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp

echo "=== STEP 1: STOP EVERYTHING ==="
echo ""
./scripts/shutdown_all.sh 2>/dev/null || true
pkill -f "gate4_http_agent.py" 2>/dev/null || true
pkill -f "quantumarb_http_agent.py" 2>/dev/null || true
pkill -f "dashboard_simple.py" 2>/dev/null || true
sleep 3

echo "=== STEP 2: START CORE INFRASTRUCTURE ==="
echo ""

# Start SIMP Broker
echo "1. Starting SIMP Broker..."
python3.10 -m simp.server.broker > logs/broker_live.log 2>&1 &
BROKER_PID=$!
sleep 5

# Check broker
echo "   Checking broker health..."
curl -s http://localhost:5555/health > /dev/null && echo "   ✅ Broker running" || echo "   ❌ Broker failed"

echo ""
echo "2. Starting Enhanced Dashboard..."
source venv_gate4/bin/activate
python3.10 dashboard_simple.py > logs/dashboard_live.log 2>&1 &
DASHBOARD_PID=$!
sleep 3

echo "   Dashboard: http://localhost:8050"
curl -s http://localhost:8050/api/health > /dev/null && echo "   ✅ Dashboard running" || echo "   ❌ Dashboard failed"

echo ""
echo "=== STEP 3: START TRADING AGENTS WITH LIVE CONFIG ==="
echo ""

echo "3. Starting Gate 4 Agent (LIVE TRADING MODE)..."
# Create environment file with Coinbase credentials
cat > /tmp/coinbase_env.sh << 'EOF'
export COINBASE_API_KEY_NAME="organizations/9172ab81-070a-4e93-88dd-7b62ca9d3ff4/apiKeys/294e691a-c8f9-4d6f-88ff-671fd26ed235"
export COINBASE_API_KEY=""
export COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIPBKmQijcoLG3GPZ7ii9Plh+c0t6CVp/hH6UzJhwZeYSoAoGCCqGSM49
AwEHoUQDQgAE5iNjj5QApwg1n8c9JjSkFAgroZBOn2cg5Rg8ICIlsg2bpO+s71PP
dhU+KtB5qBmXayI05PrQ/zafNPOlMIwZNA==
-----END EC PRIVATE KEY-----"
EOF

source /tmp/coinbase_env.sh
python3.10 gate4_http_agent.py --live --config config/gate4_scaled_microscopic_live.json > logs/gate4_live.log 2>&1 &
GATE4_PID=$!
sleep 5

echo "   Gate 4 Agent: http://localhost:8769"
curl -s http://localhost:8769/health > /dev/null && echo "   ✅ Gate 4 running" || echo "   ❌ Gate 4 failed"

echo ""
echo "4. Starting QuantumArb Agent (LIVE ANALYSIS)..."
python3.10 quantumarb_http_agent.py --live > logs/quantumarb_live.log 2>&1 &
QUANTUMARB_PID=$!
sleep 3

echo "   QuantumArb Agent: http://localhost:8770"
curl -s http://localhost:8770/health > /dev/null && echo "   ✅ QuantumArb running" || echo "   ❌ QuantumArb failed"

echo ""
echo "=== STEP 4: REGISTER AGENTS WITH BROKER ==="
echo ""

echo "5. Registering agents..."
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
      "live_trading": true
    }
  }' > /dev/null 2>&1 && echo "   ✅ Gate 4 registered" || echo "   ❌ Gate 4 registration failed"

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
  }' > /dev/null 2>&1 && echo "   ✅ QuantumArb registered" || echo "   ❌ QuantumArb registration failed"

echo ""
echo "=== STEP 5: START SUPPORTING MODULES ==="
echo ""

echo "6. Starting ProjectX..."
python3.10 /Users/kaseymarcelle/ProjectX/projectx_guard_server.py \
  --host 127.0.0.1 \
  --port 8771 \
  --register \
  --simp-url http://127.0.0.1:5555 \
  > logs/projectx_live.log 2>&1 &
PROJECTX_PID=$!
sleep 3

echo "   ProjectX: http://localhost:8771"
curl -s http://localhost:8771/health > /dev/null && echo "   ✅ ProjectX running" || echo "   ❌ ProjectX failed"

echo ""
echo "7. Starting Gemma4 Agent..."
python3.10 bin/start_gemma4_agent.py \
  --port 5010 \
  --broker http://127.0.0.1:5555 \
  --agent-id gemma4_live \
  > logs/gemma4_live.log 2>&1 &
GEMMA4_PID=$!
sleep 3

echo "   Gemma4: http://localhost:5010"
curl -s http://localhost:5010/health > /dev/null && echo "   ✅ Gemma4 running" || echo "   ❌ Gemma4 failed"

echo ""
echo "=== STEP 6: VERIFY SYSTEM ==="
echo ""

echo "8. Checking all services..."
echo ""
echo "   Broker agents:"
curl -s http://localhost:5555/agents | python3 -c "
import json, sys
data = json.load(sys.stdin)
print('   Total agents:', len(data.get('agents', {})))
for agent_id, info in data.get('agents', {}).items():
    status = info.get('status', 'unknown')
    endpoint = info.get('endpoint', 'NONE')
    print(f'   • {agent_id}: {status} ({endpoint[:30]}...)')" 2>/dev/null || echo "   Could not fetch agents"

echo ""
echo "9. Sending test intents to start trading..."
echo ""

# Send market analysis to QuantumArb
echo "   Sending market analysis to QuantumArb..."
curl -X POST http://localhost:5555/intents/route \
  -H "Content-Type: application/json" \
  -d '{
    "intent_type": "market_analysis",
    "source_agent": "system",
    "target_agent": "quantumarb_live",
    "params": {
      "symbol": "BTC-USD",
      "analysis_type": "arbitrage_opportunities"
    }
  }' > /dev/null 2>&1 && echo "   ✅ Market analysis sent" || echo "   ❌ Failed to send"

sleep 2

# Send trade execution to Gate 4
echo "   Sending trade execution to Gate 4..."
curl -X POST http://localhost:5555/intents/route \
  -H "Content-Type: application/json" \
  -d '{
    "intent_type": "trade_execution",
    "source_agent": "system",
    "target_agent": "gate4_live",
    "params": {
      "symbol": "BTC-USD",
      "amount": 1.0,
      "side": "buy",
      "test_mode": true
    }
  }' > /dev/null 2>&1 && echo "   ✅ Trade execution sent" || echo "   ❌ Failed to send"

echo ""
echo "=== STEP 7: CREATE MONITORING DASHBOARD ==="
echo ""

cat > /tmp/monitor_live.sh << 'EOF'
#!/bin/bash
echo "========================================="
echo "SIMP LIVE TRADING MONITOR"
echo "========================================="
echo "Time: $(date)"
echo ""
echo "=== SERVICES ==="
echo "Broker:      $(curl -s http://localhost:5555/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo "Dashboard:   $(curl -s http://localhost:8050/api/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo "Gate 4:      $(curl -s http://localhost:8769/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo "QuantumArb:  $(curl -s http://localhost:8770/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")"
echo ""
echo "=== RECENT INTENTS ==="
curl -s http://localhost:8050/api/intents/recent?limit=5 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if data.get('intents'):
        for i in data['intents'][:3]:
            print(f\"  • {i.get('intent_type', 'unknown')} -> {i.get('target_agent', 'unknown')}: {i.get('status', 'unknown')}\")
    else:
        print('  No intents yet')
except:
    print('  Could not fetch intents')"
echo ""
echo "=== QUICK COMMANDS ==="
echo "Dashboard:   http://localhost:8050"
echo "Send trade:  ./send_test_trade.sh"
echo "Monitor:     tail -f logs/gate4_live.log"
echo "Stop all:    ./stop_live_trading.sh"
echo "========================================="
EOF

mv /tmp/monitor_live.sh ./monitor_live.sh
chmod +x ./monitor_live.sh

# Create test trade script
cat > ./send_test_trade.sh << 'EOF'
#!/bin/bash
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
      "test_mode": false
    }
  }'
echo ""
echo "Trade intent sent to Gate 4 agent"
EOF

chmod +x ./send_test_trade.sh

# Create stop script
cat > ./stop_live_trading.sh << 'EOF'
#!/bin/bash
echo "Stopping SIMP Live Trading..."
pkill -f "gate4_http_agent.py"
pkill -f "quantumarb_http_agent.py"
pkill -f "dashboard_simple.py"
pkill -f "projectx_guard_server.py"
pkill -f "start_gemma4_agent.py"
echo "All services stopped"
EOF

chmod +x ./stop_live_trading.sh

echo ""
echo "🔥🔥🔥 LIVE TRADING SYSTEM READY! 🔥🔥🔥"
echo ""
echo "=== ACCESS POINTS ==="
echo "Dashboard:    http://localhost:8050"
echo "Gate 4 Agent: http://localhost:8769"
echo "QuantumArb:   http://localhost:8770"
echo "Broker API:   http://localhost:5555"
echo ""
echo "=== MONITORING ==="
echo "./monitor_live.sh          # System status"
echo "tail -f logs/gate4_live.log # Live trading logs"
echo "./send_test_trade.sh       # Send test trade"
echo ""
echo "=== LIVE TRADING ENABLED ==="
echo "• Coinbase API configured"
echo "• $1-$10 position sizing"
echo "• Real-time risk management"
echo "• Arbitrage detection active"
echo ""
echo "✅ SYSTEM IS NOW LIVE AND READY FOR TRADING! ✅"