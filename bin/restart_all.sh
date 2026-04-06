#!/usr/bin/env bash
# restart_all.sh — Clean restart of the entire SIMP system
#
# Usage: bash bin/restart_all.sh
#
# Kills: all Python servers, launchd SIMP services
# Starts: bullbear broker, cowork bridge, runs_api (via launchd)
# Verifies: all three are healthy before exiting

set -e

BULLBEAR="$HOME/bullbear"
SIMP_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }
info() { echo -e "${BLUE}  →${NC} $*"; }
banner() { echo -e "\n${BOLD}$*${NC}"; }

banner "══════════════════════════════════════"
banner "  SIMP Clean Restart"
banner "══════════════════════════════════════"

# ── Step 1: Kill everything ───────────────────────────────────────────────────
banner "[ 1/4 ] Stopping all servers..."

# Unload launchd services
for plist in com.simp.broker com.simp.cowork_bridge com.simp.runs_api; do
    launchctl unload "$HOME/Library/LaunchAgents/${plist}.plist" 2>/dev/null && info "Unloaded $plist" || true
done

# Kill any stray Python processes on SIMP ports
for port in 5555 8050 8080 8767 8765 8766 8770 11434; do
    pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null && info "Killed PID $pid on :$port" || true
    fi
done

sleep 2
ok "All servers stopped"

# ── Step 2: Ensure required dirs exist ───────────────────────────────────────
banner "[ 2/4 ] Checking directories..."

mkdir -p "$BULLBEAR/logs"
mkdir -p "$BULLBEAR/signals/cowork_inbox"
mkdir -p "$BULLBEAR/signals/cowork_outbox"
mkdir -p "$BULLBEAR/data"
mkdir -p "$SIMP_REPO/data/inboxes"
mkdir -p "$SIMP_REPO/data/tmp"
ok "Directories ready"

# ── Step 3: Reload launchd services ──────────────────────────────────────────
banner "[ 3/4 ] Starting services via launchd..."

for plist in com.simp.broker com.simp.cowork_bridge com.simp.runs_api; do
    plist_path="$HOME/Library/LaunchAgents/${plist}.plist"
    if [ -f "$plist_path" ]; then
        launchctl load "$plist_path" && info "Loaded $plist" || warn "Failed to load $plist"
    else
        warn "Plist not found: $plist_path"
    fi
done

# ── Step 4: Wait and verify ───────────────────────────────────────────────────
banner "[ 4/4 ] Waiting for services to start..."

sleep 5

echo ""
echo "── Health Checks ──"

# Broker
BROKER_HEALTH=$(curl -sf --max-time 3 http://127.0.0.1:5555/health 2>/dev/null)
if [ -n "$BROKER_HEALTH" ]; then
    AGENTS=$(echo "$BROKER_HEALTH" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('agents_online', '?'))" 2>/dev/null)
    ok "Broker online — $AGENTS agents registered"
else
    fail "Broker not responding at :5555"
    echo "    Check: tail -20 $BULLBEAR/logs/simp_broker.log"
fi

# Cowork bridge
COWORK_HEALTH=$(curl -sf --max-time 3 http://127.0.0.1:8767/health 2>/dev/null)
if [ -n "$COWORK_HEALTH" ]; then
    PENDING=$(echo "$COWORK_HEALTH" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('pending_count', '?'))" 2>/dev/null)
    ok "claude_cowork online — $PENDING pending tasks"
else
    warn "claude_cowork not responding at :8767"
    echo "    Check: tail -20 $BULLBEAR/logs/cowork_bridge.log"
fi

# Runs API
RUNS_HEALTH=$(curl -sf --max-time 3 http://127.0.0.1:8768/health 2>/dev/null || \
              curl -sf --max-time 3 http://127.0.0.1:8769/health 2>/dev/null || \
              echo "")
if [ -n "$RUNS_HEALTH" ]; then
    ok "runs_api online"
else
    warn "runs_api not detected (may use a different port)"
fi

# Pending inbox tasks
INBOX="$BULLBEAR/signals/cowork_inbox"
PENDING_FILES=$(ls "$INBOX"/*.json 2>/dev/null | wc -l | tr -d ' ')
if [ "$PENDING_FILES" -gt 0 ]; then
    warn "$PENDING_FILES task(s) waiting in cowork inbox — will process when bridge is ready"
fi

echo ""
echo "── Active Ports ──"
for port in 5555 8767 8768 8769 8050; do
    result=$(lsof -i :$port 2>/dev/null | grep LISTEN | awk '{print $1}' | head -1)
    if [ -n "$result" ]; then
        echo -e "  :$port  ${GREEN}LISTENING${NC}  ($result)"
    fi
done

echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${BOLD}  System ready.${NC}"
echo ""
echo "  Monitor:  bash bin/broker_status.sh"
echo "  Queue task: bash bin/queue_intent.sh \"your task here\""
echo "  Logs: tail -f $BULLBEAR/logs/simp_broker.log"
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo ""
