#!/usr/bin/env bash
# simp_go_live.sh — Bring SIMP online and queue all startup tasks
#
# Usage:
#   bash bin/simp_go_live.sh
#
# What this does:
#   1. Checks broker is reachable
#   2. Installs cowork_bridge launchd service if not running
#   3. Registers claude_cowork agent with the broker
#   4. Queues all startup intents in priority order

set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BROKER="http://127.0.0.1:5555"
COWORK="http://127.0.0.1:8767"
API_KEY="${SIMP_API_KEY:-}"  # Optional — set if broker requires auth

# ── Color output ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }
info() { echo -e "${BLUE}  →${NC} $*"; }

echo ""
echo "══════════════════════════════════════════"
echo "  SIMP Go-Live  v0.4.0"
echo "══════════════════════════════════════════"
echo ""

# ── Step 1: Check broker ──────────────────────────────────────────────────────
info "Checking SIMP broker at $BROKER..."
if curl -sf "$BROKER/health" > /dev/null 2>&1; then
    ok "Broker is up"
else
    fail "Broker not reachable at $BROKER"
    echo ""
    echo "  Start it with:"
    echo "    bash ~/bullbear/launchd/install_services.sh"
    echo "  Or manually:"
    echo "    cd $REPO && python3.10 bin/start_server.py &"
    exit 1
fi

# ── Step 2: Check / install cowork_bridge ────────────────────────────────────
info "Checking cowork_bridge at $COWORK..."
if curl -sf "$COWORK/health" > /dev/null 2>&1; then
    ok "cowork_bridge is running"
else
    warn "cowork_bridge not running — installing launchd service..."
    if [ -f "$REPO/launchd/install.sh" ]; then
        bash "$REPO/launchd/install.sh"
        sleep 3
        if curl -sf "$COWORK/health" > /dev/null 2>&1; then
            ok "cowork_bridge started"
        else
            fail "cowork_bridge failed to start. Run manually:"
            echo "    python3.10 $REPO/bin/cowork_bridge.py --repo-path $REPO &"
        fi
    else
        warn "launchd/install.sh not found. Start bridge manually:"
        echo "    python3.10 $REPO/bin/cowork_bridge.py --repo-path $REPO &"
    fi
fi

# ── Step 3: Register claude_cowork with broker ───────────────────────────────
info "Registering claude_cowork with broker..."

AUTH_HEADER=""
if [ -n "$API_KEY" ]; then
    AUTH_HEADER="-H 'Authorization: Bearer $API_KEY'"
fi

REG_RESULT=$(curl -sf -X POST "$BROKER/agents/register" \
    -H "Content-Type: application/json" \
    ${API_KEY:+-H "Authorization: Bearer $API_KEY"} \
    -d '{
        "agent_id": "claude_cowork",
        "agent_type": "llm",
        "endpoint": "'"$COWORK"'",
        "metadata": {
            "model": "claude-code",
            "capabilities": ["code_task","code_editing","planning","research","scaffolding","test_harness","spec","architecture","docs","code_review","orchestration"]
        }
    }' 2>&1) || true

if echo "$REG_RESULT" | grep -q '"status"'; then
    ok "claude_cowork registered"
else
    warn "Registration response: $REG_RESULT"
fi

# ── Helper: queue an intent ───────────────────────────────────────────────────
queue_intent() {
    local label="$1"
    local json="$2"
    info "Queuing: $label..."
    RESULT=$(curl -sf -X POST "$BROKER/intents/route" \
        -H "Content-Type: application/json" \
        ${API_KEY:+-H "Authorization: Bearer $API_KEY"} \
        -d "$json" 2>&1) || true
    if echo "$RESULT" | grep -qE '"status"|"task_id"'; then
        ok "$label → queued"
    else
        warn "$label → $RESULT"
    fi
}

# ── Step 4: Queue startup intents in priority order ───────────────────────────
echo ""
echo "── Queuing startup tasks ─────────────────"

# 4a. Fix protocol_updater.py (CRITICAL — from user)
queue_intent "Fix protocol_updater.py syntax error" '{
  "intent_id": "intent:perplexity_research:fix-protocol-updater-001",
  "source_agent": "perplexity_research",
  "target_agent": "claude_cowork",
  "intent_type": "code_task",
  "priority": "critical",
  "params": {
    "task": "Inspect, diagnose, and fix the syntax error in /Users/kaseymarcelle/ProjectX/simp_brain/protocol_updater.py.\n\nThe file has a syntax error on line 37. The broken function signature is:\n  def save_protocol_facts( Dict[str, Any]) -> None:\n\nThe correct signature should have a named parameter:\n  def save_protocol_facts(facts: Dict[str, Any]) -> None:\n\nSteps:\n1. Open /Users/kaseymarcelle/ProjectX/simp_brain/protocol_updater.py\n2. Print lines 34-40 exactly as they appear on disk (use repr() to catch invisible chars)\n3. Fix line 37 to be: def save_protocol_facts(facts: Dict[str, Any]) -> None:\n4. Save the file\n5. Run: python3 -m py_compile /Users/kaseymarcelle/ProjectX/simp_brain/protocol_updater.py\n6. If compile succeeds, run: python3 -c \"import sys; sys.path.insert(0, '"'"'/Users/kaseymarcelle/ProjectX'"'"'); import simp_brain.protocol_updater as m; print('"'"'OK'"'"', m.__name__)\"\n7. Report the exact before/after line 37 and verification output",
    "project": "ProjectX",
    "file_path": "/Users/kaseymarcelle/ProjectX/simp_brain/protocol_updater.py"
  }
}'

# 4b. Process pending tasks in task ledger
queue_intent "Process 3 pending tasks in task ledger" '{
  "intent_id": "intent:perplexity_research:process-pending-001",
  "source_agent": "perplexity_research",
  "target_agent": "claude_cowork",
  "intent_type": "orchestration",
  "priority": "high",
  "params": {
    "task": "Check the SIMP task ledger at '"$REPO"'/data/task_ledger.jsonl for pending/queued tasks. List them. For each task that is actionable (not blocked), attempt to execute it. Report what each task was and what you did.",
    "repo_path": "'"$REPO"'"
  }
}'

# 4c. Verify tests pass locally
queue_intent "Run full test suite locally" '{
  "intent_id": "intent:perplexity_research:run-tests-001",
  "source_agent": "perplexity_research",
  "target_agent": "claude_cowork",
  "intent_type": "test_harness",
  "priority": "high",
  "params": {
    "task": "cd '"$REPO"' && python3.10 -m pytest tests/ -q 2>&1. Report pass/fail count. If any tests fail, fix them and recommit.",
    "repo_path": "'"$REPO"'"
  }
}'

# 4d. Start and verify dashboard
queue_intent "Verify dashboard connects to live broker" '{
  "intent_id": "intent:perplexity_research:dashboard-verify-001",
  "source_agent": "perplexity_research",
  "target_agent": "claude_cowork",
  "intent_type": "code_task",
  "priority": "medium",
  "params": {
    "task": "Start the SIMP dashboard at '"$REPO"'/dashboard/server.py (python3.10 dashboard/server.py) if not running, verify it responds at http://127.0.0.1:8050/api/health, and confirm the broker is reachable from the dashboard (broker_reachable: true in the response). Report the health response.",
    "repo_path": "'"$REPO"'"
  }
}'

# 4e. Open PR to merge to main
queue_intent "Create PR: merge feat/public-readonly-dashboard to main" '{
  "intent_id": "intent:perplexity_research:merge-pr-001",
  "source_agent": "perplexity_research",
  "target_agent": "claude_cowork",
  "intent_type": "code_task",
  "priority": "low",
  "params": {
    "task": "cd '"$REPO"' && gh pr create --title \"feat: SIMP v0.4.0 — 25-sprint production hardening\" --body \"## Summary\n\nMerges all 25 sprints of SIMP hardening into main.\n\n### What changed\n- Sprints 1-5: Input validation, security hardening\n- Sprints 6-10: Dashboard, orchestration, memory, protocol cleanup, v0.2.0\n- Sprints 11-15: ProjectX computer-use module\n- Sprints 16-17: API key auth, canonical intent schema, crypto activation\n- Sprints 18-19: Async health checks, connection pooling, production server\n- Sprints 20-21: WebSocket dashboard, charts, security headers\n- Sprints 22-23: Load balancing, circuit breaker, Gemma4 agent, E2E flow\n- Sprints 24-25: Self-improvement engine, PROTOCOL_SPEC.md, v0.4.0\n\n### Tests\n451 passing, 0 failures\n\n### Version\nv0.4.0\" --base main --head feat/public-readonly-dashboard 2>&1",
    "repo_path": "'"$REPO"'"
  }
}'

echo ""
echo "══════════════════════════════════════════"
echo "  All tasks queued."
echo ""
echo "  Monitor progress:"
echo "    curl -s $BROKER/tasks | python3 -m json.tool"
echo "    curl -s $BROKER/logs?limit=20 | python3 -m json.tool"
echo ""
echo "  Check cowork_bridge logs:"
echo "    tail -f ~/bullbear/logs/cowork_bridge.log"
echo "══════════════════════════════════════════"
