#!/usr/bin/env bash
# register_agents.sh — Register all SIMP agents with the broker
BROKER="${SIMP_BROKER:-http://127.0.0.1:5555}"
API_KEY="${SIMP_API_KEY:-}"

register() {
    local label="$1"; local data="$2"
    echo -n "  $label... "
    curl -sf -X POST "$BROKER/agents/register" \
        -H "Content-Type: application/json" \
        ${API_KEY:+-H "Authorization: Bearer $API_KEY"} \
        -d "$data" | python3 -c "import json,sys; d=json.load(sys.stdin); print('ok' if 'agent_id' in d or 'status' in d else d)" 2>/dev/null || echo "failed"
}

echo "Registering agents with $BROKER..."

register "claude_cowork (HTTP :8767)" '{
    "agent_id": "claude_cowork",
    "agent_type": "llm",
    "endpoint": "http://127.0.0.1:8767",
    "metadata": {"model": "claude-code", "capabilities": ["code_task","code_editing","planning","research","scaffolding","test_harness","spec","architecture","docs","code_review","orchestration"]}
}'

register "gemma4_local (HTTP :5010)" '{
    "agent_id": "gemma4_local",
    "agent_type": "llm",
    "endpoint": "http://127.0.0.1:5010",
    "metadata": {"model": "gemma4:e2b", "capabilities": ["research","planning","summarization"]}
}'

register "bullbear_predictor (file-based)" '{
    "agent_id": "bullbear_predictor",
    "agent_type": "predictor",
    "endpoint": "",
    "metadata": {"transport": "file", "inbox": "data/inboxes/bullbear_predictor"}
}'

register "kashclaw (file-based)" '{
    "agent_id": "kashclaw",
    "agent_type": "trader",
    "endpoint": "",
    "metadata": {"transport": "file", "inbox": "data/inboxes/kashclaw"}
}'

register "quantumarb (file-based)" '{
    "agent_id": "quantumarb",
    "agent_type": "arbitrage",
    "endpoint": "",
    "metadata": {"transport": "file", "inbox": "data/inboxes/quantumarb"}
}'

echo ""
echo "Done. Verify: curl $BROKER/agents | python3 -m json.tool"
