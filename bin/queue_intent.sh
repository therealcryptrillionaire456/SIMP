#!/usr/bin/env bash
# queue_intent.sh — Queue a single intent to the SIMP broker
# Usage: bash bin/queue_intent.sh "Fix the login bug in auth.py" [intent_type] [priority]
#
# Examples:
#   bash bin/queue_intent.sh "Add logging to broker.py"
#   bash bin/queue_intent.sh "Review the routing code" code_review high
#   bash bin/queue_intent.sh "Write tests for gemma4_agent.py" test_harness medium

BROKER="${SIMP_BROKER:-http://127.0.0.1:5555}"
API_KEY="${SIMP_API_KEY:-}"

TASK="${1:-help}"
INTENT_TYPE="${2:-code_task}"
PRIORITY="${3:-medium}"
TARGET="${4:-claude_cowork}"
SOURCE="${5:-perplexity_research}"

if [ "$TASK" = "help" ] || [ -z "$TASK" ]; then
    echo "Usage: bash bin/queue_intent.sh \"task description\" [type] [priority] [target] [source]"
    echo ""
    echo "Types: code_task, research, planning, test_harness, scaffolding, docs, code_review, orchestration"
    echo "Priority: critical, high, medium, low"
    exit 0
fi

ID="intent:${SOURCE}:$(python3 -c 'import uuid; print(str(uuid.uuid4())[:8])')"
TS=$(python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')

PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'intent_id': '$ID',
    'source_agent': '$SOURCE',
    'target_agent': '$TARGET',
    'intent_type': '$INTENT_TYPE',
    'priority': '$PRIORITY',
    'timestamp': '$TS',
    'params': {'task': '''$TASK'''}
}))
")

echo "Queuing: $TASK"
echo "  type=$INTENT_TYPE priority=$PRIORITY target=$TARGET"
echo ""

RESULT=$(curl -sf -X POST "$BROKER/intents/route" \
    -H "Content-Type: application/json" \
    ${API_KEY:+-H "Authorization: Bearer $API_KEY"} \
    -d "$PAYLOAD" 2>&1)

if [ $? -eq 0 ]; then
    echo "✓ Queued: $ID"
    echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
else
    echo "✗ Failed to queue intent"
    echo "$RESULT"
    echo ""
    echo "Is the broker running? curl $BROKER/health"
fi
