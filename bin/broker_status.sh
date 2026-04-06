#!/usr/bin/env bash
# broker_status.sh — Quick SIMP system status
BROKER="${SIMP_BROKER:-http://127.0.0.1:5555}"
COWORK="${COWORK_URL:-http://127.0.0.1:8767}"

echo "=== SIMP System Status ==="
echo ""
echo "── Broker ($BROKER) ──"
curl -sf "$BROKER/health" | python3 -m json.tool 2>/dev/null || echo "  UNREACHABLE"
echo ""
echo "── claude_cowork ($COWORK) ──"
curl -sf "$COWORK/health" | python3 -m json.tool 2>/dev/null || echo "  UNREACHABLE"
echo ""
echo "── Task Queue ──"
curl -sf "$BROKER/tasks/queue" | python3 -c "
import json, sys
tasks = json.load(sys.stdin)
if not tasks:
    print('  Queue empty')
else:
    for t in tasks[:10]:
        print(f'  [{t.get(\"priority\",\"?\")}] {t.get(\"task_type\",\"?\")} — {t.get(\"status\",\"?\")} — {t.get(\"description\",\"\")[:60]}')
" 2>/dev/null || echo "  (no queue data)"
echo ""
echo "── Agents ──"
curl -sf "$BROKER/agents" | python3 -c "
import json, sys
agents = json.load(sys.stdin)
if isinstance(agents, dict):
    agents = list(agents.values())
for a in agents:
    print(f'  {a.get(\"agent_id\",\"?\")} — {a.get(\"status\",\"?\")} — {a.get(\"endpoint\",\"file-based\")}')
" 2>/dev/null || echo "  (no agent data)"
