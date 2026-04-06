#!/usr/bin/env bash
# broker_status.sh — Check status of the live SIMP/bullbear system
BROKER="${SIMP_BROKER:-http://127.0.0.1:5555}"
COWORK="${COWORK_URL:-http://127.0.0.1:8767}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }

echo ""
echo "=== SIMP System Status ==="

# ── Broker ────────────────────────────────────────────────────────────────────
echo ""
echo "── Broker ($BROKER) ──"
HEALTH=$(curl -sf --max-time 3 "$BROKER/health" 2>/dev/null)
if [ -n "$HEALTH" ]; then
    ok "Broker is UP"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    fail "Broker UNREACHABLE at $BROKER"
    echo ""
    echo "  Check if it's running on a different port:"
    echo "    lsof -i :5555"
    echo "    lsof -i :8080"
    echo ""
    echo "  Check the log:"
    echo "    tail -20 ~/bullbear/logs/simp_broker.log"
    echo ""
    echo "  See what process owns port 5555:"
    lsof -i :5555 2>/dev/null | head -5 || echo "  (nothing on port 5555)"
    echo ""
    echo "  See what process owns port 8080:"
    lsof -i :8080 2>/dev/null | head -5 || echo "  (nothing on port 8080)"
fi

# ── cowork bridge ─────────────────────────────────────────────────────────────
echo ""
echo "── claude_cowork ($COWORK) ──"
COWORK_HEALTH=$(curl -sf --max-time 3 "$COWORK/health" 2>/dev/null)
if [ -n "$COWORK_HEALTH" ]; then
    ok "claude_cowork is UP"
    echo "$COWORK_HEALTH" | python3 -m json.tool 2>/dev/null || echo "$COWORK_HEALTH"
else
    fail "claude_cowork UNREACHABLE at $COWORK"
fi

# ── Port scan (show what's actually listening) ────────────────────────────────
echo ""
echo "── Active SIMP ports ──"
for port in 5555 8050 8080 8767 11434; do
    result=$(lsof -i :$port 2>/dev/null | grep LISTEN | awk '{print $1, $2}' | head -1)
    if [ -n "$result" ]; then
        echo "  :$port  LISTENING  ($result)"
    else
        echo "  :$port  closed"
    fi
done

# ── Broker agents (if broker is up) ──────────────────────────────────────────
if [ -n "$HEALTH" ]; then
    echo ""
    echo "── Registered Agents ──"
    curl -sf --max-time 3 "$BROKER/agents" 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    agents = data if isinstance(data, list) else (list(data.values()) if isinstance(data, dict) else [])
    if not agents:
        print('  No agents registered')
    for a in agents:
        aid = a.get('agent_id', a.get('id', '?'))
        status = a.get('status', '?')
        ep = a.get('endpoint', 'file-based')
        print(f'  {aid}  [{status}]  {ep}')
except Exception as e:
    print(f'  (parse error: {e})')
" 2>/dev/null || echo "  (could not fetch agents)"

    echo ""
    echo "── Pending Intent Queue ──"
    curl -sf --max-time 3 "$BROKER/stats" 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(f'  Intents routed: {d.get(\"intents_routed\", d.get(\"total_intents\", \"?\"))}')
    print(f'  Pending: {d.get(\"pending\", d.get(\"queue_depth\", \"?\"))}')
    print(f'  Agents: {d.get(\"agent_count\", d.get(\"agents\", \"?\"))}')
except Exception as e:
    print(f'  (parse error: {e})')
" 2>/dev/null || echo "  (could not fetch stats)"
fi

# ── Cowork inbox ──────────────────────────────────────────────────────────────
echo ""
echo "── Cowork Inbox ──"
INBOX="$HOME/bullbear/signals/cowork_inbox"
if [ -d "$INBOX" ]; then
    count=$(ls "$INBOX"/*.json 2>/dev/null | wc -l | tr -d ' ')
    echo "  $INBOX"
    echo "  Files: $count"
    ls "$INBOX"/*.json 2>/dev/null | head -5 | while read f; do
        echo "  - $(basename "$f")"
    done
else
    echo "  Inbox dir not found: $INBOX"
fi

echo ""
