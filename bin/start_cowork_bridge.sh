#!/bin/bash
# =============================================================================
# start_cowork_bridge.sh
# Starts the SIMP CoWork Bridge process on 127.0.0.1:8767
#
# Usage:
#   bash bin/start_cowork_bridge.sh            # Foreground
#   bash bin/start_cowork_bridge.sh --daemon   # Background (writes PID file)
#   bash bin/start_cowork_bridge.sh --stop     # Kill running bridge
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$SIMP_ROOT/.cowork_bridge.pid"
LOG_FILE="$SIMP_ROOT/logs/cowork_bridge.log"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

# ── Stop running bridge ───────────────────────────────────────────────────────
if [ "$1" = "--stop" ]; then
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill "$PID" 2>/dev/null; then
            echo -e "${GREEN}✅ Stopped CoWork Bridge (PID $PID)${NC}"
            rm "$PID_FILE"
        else
            echo -e "${YELLOW}⚠️  PID $PID not running — cleaning up${NC}"
            rm "$PID_FILE"
        fi
    else
        # Try to find by port
        EXISTING=$(lsof -ti:8767 2>/dev/null)
        if [ -n "$EXISTING" ]; then
            kill "$EXISTING" && echo -e "${GREEN}✅ Stopped process on port 8767 (PID $EXISTING)${NC}"
        else
            echo -e "${YELLOW}⚠️  No bridge running${NC}"
        fi
    fi
    exit 0
fi

# ── Check if already running ──────────────────────────────────────────────────
EXISTING=$(lsof -ti:8767 2>/dev/null)
if [ -n "$EXISTING" ]; then
    echo -e "${YELLOW}⚠️  Port 8767 already in use (PID $EXISTING).${NC}"
    echo "    Use: bash bin/start_cowork_bridge.sh --stop"
    exit 1
fi

# ── API key ───────────────────────────────────────────────────────────────────
if [ -z "$SIMP_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  SIMP_API_KEY not set. Bridge will start without auth.${NC}"
    echo "    Set it: export SIMP_API_KEY=your_key_here"
fi

# ── Daemon mode ───────────────────────────────────────────────────────────────
if [ "$1" = "--daemon" ]; then
    mkdir -p "$SIMP_ROOT/logs"
    nohup python3 -m simp.agents.cowork_bridge \
        --simp-url "${SIMP_URL:-http://127.0.0.1:5555}" \
        >> "$LOG_FILE" 2>&1 &
    BRIDGE_PID=$!
    echo "$BRIDGE_PID" > "$PID_FILE"
    sleep 1
    if kill -0 "$BRIDGE_PID" 2>/dev/null; then
        echo -e "${GREEN}✅ CoWork Bridge started (PID $BRIDGE_PID)${NC}"
        echo "   Logs: $LOG_FILE"
        echo "   PID file: $PID_FILE"
        echo "   Health: curl http://127.0.0.1:8767/health"
        # Quick health check
        sleep 1
        curl -sf http://127.0.0.1:8767/health | python3 -m json.tool 2>/dev/null || true
    else
        echo -e "${RED}❌ Bridge failed to start. Check $LOG_FILE${NC}"
        exit 1
    fi
else
    # Foreground
    echo -e "${GREEN}Starting CoWork Bridge (foreground — Ctrl+C to stop)${NC}"
    cd "$SIMP_ROOT"
    exec python3 -m simp.agents.cowork_bridge \
        --simp-url "${SIMP_URL:-http://127.0.0.1:5555}"
fi
