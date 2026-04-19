#!/bin/bash
echo "========================================="
echo "🔥 SIMP REAL SYSTEM MONITOR 🔥"
echo "========================================="
echo "Time: $(date)"
echo ""
echo "=== CORE SERVICES ==="
echo "Broker:     $(curl -s http://localhost:5555/health 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null || echo "checking")"
echo "Dashboard:  $(curl -s http://localhost:8050/api/health 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null || echo "checking")"
echo ""
echo "=== REAL AGENTS ==="
echo "Gate 4:     $(ps aux | grep -c '[g]ate4' || echo 0) processes"
echo "QuantumArb: $(ps aux | grep -c '[q]uantumarb' || echo 0) processes"
echo "Gemma4:     $(ps aux | grep -c '[g]emma4' || echo 0) processes"
echo ""
echo "=== RECENT ACTIVITY ==="
echo "Dashboard intents:"
curl -s http://localhost:8050/api/intents/recent?limit=2 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for i in data.get('intents', [])[:2]:
        print(f'  • {i.get(\"intent_type\", \"unknown\")} -> {i.get(\"target_agent\", \"unknown\")}')
except:
    print('  Checking...')" 2>/dev/null
echo ""
echo "=== LOGS ==="
echo "Gate 4 logs:   tail -f logs/gate4_real_trading.log"
echo "Dashboard:     http://localhost:8050"
echo "Broker API:    http://localhost:5555"
echo "========================================="
