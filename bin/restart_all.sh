#!/usr/bin/env bash
# restart_all.sh — Clean restart of the entire SIMP system
# Usage: bash bin/restart_all.sh

BULLBEAR="$HOME/bullbear"
SIMP_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }
info() { echo -e "${BLUE}  →${NC} $*"; }

echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${BOLD}  SIMP Clean Restart${NC}"
echo -e "${BOLD}══════════════════════════════════════${NC}"

# ── Step 1: Kill everything ───────────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ 1/4 ] Stopping all servers...${NC}"

launchctl unload "$HOME/Library/LaunchAgents/com.simp.broker.plist"       2>/dev/null || true
launchctl unload "$HOME/Library/LaunchAgents/com.simp.cowork_bridge.plist" 2>/dev/null || true
launchctl unload "$HOME/Library/LaunchAgents/com.simp.runs_api.plist"      2>/dev/null || true

sleep 1

for port in 5555 8050 8080 8767 8765 8766 8770; do
    pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null || true
        info "Cleared port :$port (PID $pid)"
    fi
done

sleep 1
ok "All servers stopped"

# ── Step 2: Ensure directories exist ─────────────────────────────────────────
echo ""
echo -e "${BOLD}[ 2/4 ] Preparing directories...${NC}"

mkdir -p "$BULLBEAR/logs"
mkdir -p "$BULLBEAR/signals/cowork_inbox"
mkdir -p "$BULLBEAR/signals/cowork_outbox"
mkdir -p "$BULLBEAR/data"
mkdir -p "$SIMP_REPO/data/inboxes"
mkdir -p "$SIMP_REPO/data/tmp"
ok "Directories ready"

# ── Step 3: Reload launchd services ──────────────────────────────────────────
echo ""
echo -e "${BOLD}[ 3/4 ] Starting services via launchd...${NC}"

for plist in com.simp.broker com.simp.cowork_bridge com.simp.runs_api; do
    plist_path="$HOME/Library/LaunchAgents/${plist}.plist"
    if [ -f "$plist_path" ]; then
        launchctl load "$plist_path" 2>/dev/null || true
        info "Loaded $plist"
    else
        warn "Plist not found: $plist_path"
    fi
done

# ── Step 4: Wait and verify ───────────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ 4/4 ] Waiting for services (8 seconds)...${NC}"
sleep 8

echo ""
echo "── Health Checks ──"

BROKER=$(curl -sf --max-time 4 http://127.0.0.1:5555/health 2>/dev/null || true)
if [ -n "$BROKER" ]; then
    AGENTS=$(echo "$BROKER" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('agents_online', d.get('agent_count', '?')))" 2>/dev/null || echo "?")
    ok "Broker online — $AGENTS agents  (http://127.0.0.1:5555)"
else
    fail "Broker not responding at :5555"
    echo "    Check: tail -30 $BULLBEAR/logs/simp_broker.log"
    echo "    Check: tail -30 $BULLBEAR/logs/simp_broker_err.log"
fi

COWORK=$(curl -sf --max-time 4 http://127.0.0.1:8767/health 2>/dev/null || true)
if [ -n "$COWORK" ]; then
    PENDING=$(echo "$COWORK" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('pending_count','?'))" 2>/dev/null || echo "?")
    ok "claude_cowork online — $PENDING pending tasks  (http://127.0.0.1:8767)"
else
    warn "claude_cowork not responding at :8767"
    echo "    Check: tail -30 $BULLBEAR/logs/cowork_bridge.log"
fi

echo ""
echo "── Listening Ports ──"
for port in 5555 8767 8768 8769 8050; do
    proc=$(lsof -i :$port 2>/dev/null | grep LISTEN | awk '{print $1}' | head -1 || true)
    if [ -n "$proc" ]; then
        echo -e "  :$port  ${GREEN}UP${NC}  ($proc)"
    else
        echo "  :$port  down"
    fi
done

INBOX="$BULLBEAR/signals/cowork_inbox"
PENDING_FILES=$(ls "$INBOX"/*.json 2>/dev/null | wc -l | tr -d ' ' || echo "0")
[ "$PENDING_FILES" -gt 0 ] && warn "$PENDING_FILES task(s) waiting in inbox: $INBOX"

echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${BOLD}  Done. System restarted.${NC}"
echo ""
echo "  Status:     bash bin/broker_status.sh"
echo "  Queue task: bash bin/queue_intent.sh \"your task here\""
echo "  Logs:       tail -f $BULLBEAR/logs/simp_broker.log"
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo ""
