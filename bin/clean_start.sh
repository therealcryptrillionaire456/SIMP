#!/usr/bin/env bash
# clean_start.sh — Full clean restart: kill, clear ledger + BRP logs, start fresh
# Usage: bash bin/clean_start.sh

SIMP_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }
info() { echo -e "${BLUE}  →${NC} $*"; }

echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${BOLD}  SIMP Clean Start${NC}"
echo -e "${BOLD}══════════════════════════════════════${NC}"

# ── Step 1: Kill running processes ──────────────────────────────────────────
echo ""
echo -e "${BOLD}[ 1/4 ] Stopping all servers...${NC}"

for port in 5555 8050 8080 8767 8765 8766 8770; do
    pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null || true
        info "Cleared port :$port (PID $pid)"
    fi
done

sleep 1
ok "All servers stopped"

# ── Step 2: Clear stale data ───────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ 2/4 ] Clearing stale data...${NC}"

# Clear task ledger
if [ -f "$SIMP_REPO/data/task_ledger.jsonl" ]; then
    > "$SIMP_REPO/data/task_ledger.jsonl"
    ok "Cleared task_ledger.jsonl"
else
    info "task_ledger.jsonl not found (clean state)"
fi

# Clear BRP data files
BRP_DIR="$SIMP_REPO/data/brp"
for f in events.jsonl observations.jsonl responses.jsonl plans.jsonl; do
    if [ -f "$BRP_DIR/$f" ]; then
        rm -f "$BRP_DIR/$f"
        ok "Removed brp/$f"
    fi
done

# Clear intent inboxes
if [ -d "$SIMP_REPO/data/inboxes" ]; then
    find "$SIMP_REPO/data/inboxes" -name "*.json" -mmin +60 -delete 2>/dev/null || true
    ok "Cleaned old inbox files"
fi

ok "Stale data cleared"

# ── Step 3: Ensure directories exist ───────────────────────────────────────
echo ""
echo -e "${BOLD}[ 3/4 ] Preparing directories...${NC}"

mkdir -p "$SIMP_REPO/data/inboxes"
mkdir -p "$SIMP_REPO/data/outboxes"
mkdir -p "$SIMP_REPO/data/brp"
mkdir -p "$SIMP_REPO/data/tmp"
mkdir -p "$SIMP_REPO/logs"
ok "Directories ready"

# ── Step 4: Restart ────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ 4/4 ] Starting fresh...${NC}"

if [ -f "$SIMP_REPO/bin/restart_all.sh" ]; then
    info "Delegating to restart_all.sh..."
    bash "$SIMP_REPO/bin/restart_all.sh"
else
    info "No restart_all.sh found — start services manually"
fi

echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${BOLD}  Clean start complete.${NC}"
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo ""
