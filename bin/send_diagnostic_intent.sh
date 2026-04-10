#!/usr/bin/env bash
# send_diagnostic_intent.sh — Send a safe diagnostic intent through the SIMP system
# Verifies: broker routing → file inbox delivery → BRP logging
# Usage: bash bin/send_diagnostic_intent.sh

BROKER="${SIMP_BROKER:-http://127.0.0.1:5555}"
API_KEY="${SIMP_API_KEY:-}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ID="intent:diagnostic:$(python3 -c 'import uuid; print(str(uuid.uuid4())[:8])')"
TS=$(python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')

PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'intent_id': '$ID',
    'source_agent': 'diagnostic_runner',
    'target_agent': 'claude_cowork',
    'intent_type': 'status_check',
    'priority': 'low',
    'timestamp': '$TS',
    'params': {
        'task': 'DIAGNOSTIC: Echo this message back. No side effects needed.',
        'diagnostic': True,
        'dry_run': True,
    }
}))
")

echo "═══════════════════════════════════════════"
echo "  SIMP Diagnostic Intent"
echo "═══════════════════════════════════════════"
echo ""
echo "Intent ID: $ID"
echo "Target: claude_cowork"
echo "Type: status_check (safe, no side effects)"
echo ""

echo "1. Sending to broker at $BROKER..."
CURL_ARGS=(-sf -X POST "$BROKER/intents/route" -H "Content-Type: application/json")
if [ -n "$API_KEY" ]; then
    CURL_ARGS+=(-H "Authorization: Bearer $API_KEY" -H "X-SIMP-API-Key: $API_KEY")
fi
CURL_ARGS+=(-d "$PAYLOAD")
RESULT=$( curl "${CURL_ARGS[@]}" 2>&1 )

if [ $? -eq 0 ]; then
    echo "   ✓ Broker accepted intent"
    echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
else
    echo "   ✗ Broker rejected intent or is not running"
    echo "$RESULT"
    echo ""
    echo "   Check: curl $BROKER/health"
    exit 1
fi

echo ""
echo "2. Checking file inbox..."
INBOX="$REPO_DIR/data/inboxes/claude_cowork"
if ls "$INBOX"/*.json 2>/dev/null | head -3; then
    echo "   ✓ Intent file found in inbox"
else
    echo "   (No files — intent may have been delivered via HTTP)"
fi

echo ""
echo "3. Checking BRP logs..."
BRP_DIR="$REPO_DIR/data/brp"
for f in events.jsonl plans.jsonl observations.jsonl responses.jsonl; do
    if [ -f "$BRP_DIR/$f" ]; then
        lines=$(wc -l < "$BRP_DIR/$f" | tr -d ' ')
        echo "   ✓ $f: $lines entries"
    else
        echo "   - $f: not yet created"
    fi
done

echo ""
echo "4. Checking outbox..."
OUTBOX="$REPO_DIR/data/outboxes/claude_cowork"
if ls "$OUTBOX"/*.json 2>/dev/null | head -3; then
    echo "   ✓ Response file found in outbox"
else
    echo "   - No response yet (agent may not have processed)"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  Diagnostic complete"
echo "═══════════════════════════════════════════"
