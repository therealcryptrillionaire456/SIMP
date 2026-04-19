#!/bin/bash
echo "========================================="
echo "🔥 SIMP LIVE TRADING MONITOR 🔥"
echo "========================================="
echo "Time: $(date)"
echo ""
echo "=== CORE SERVICES ==="
echo "Broker:     $(curl -s http://localhost:5555/health 2>/dev/null | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "checking...")"
echo "Dashboard:  $(curl -s http://localhost:8050/api/health 2>/dev/null | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "checking...")"
echo "Gate 4:     $(curl -s http://localhost:8769/health 2>/dev/null | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "checking...")"
echo "QuantumArb: $(curl -s http://localhost:8770/health 2>/dev/null | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "checking...")"
echo ""
echo "=== RECENT ACTIVITY ==="
echo "Dashboard showing:"
curl -s http://localhost:8050/api/intents/recent?limit=3 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    count = data.get('count', 0)
    print(f'  {count} recent intents')
    for i in data.get('intents', [])[:3]:
        print(f'  • {i.get(\"intent_type\", \"unknown\")} -> {i.get(\"target_agent\", \"unknown\")}: {i.get(\"status\", \"unknown\")}')
except Exception as e:
    print(f'  Loading data...')" 2>/dev/null
echo ""
echo "=== QUICK ACTIONS ==="
echo "Dashboard:    http://localhost:8050"
echo "View logs:    tail -f logs/gate4_live.log"
echo "Stop all:     pkill -f \"dashboard\|gate4\|quantumarb\""
echo "========================================="
EOF && chmod +x monitor_live_trading.sh && ./monitor_live_trading.sh
