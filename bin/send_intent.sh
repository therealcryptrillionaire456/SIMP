#!/usr/bin/env bash
# send_intent.sh — Send an intent to claude_cowork using the correct schema.
#
# The cowork bridge (bin/cowork_bridge.py) listens on port 8767 and accepts
# POST /intents/handle with the following JSON schema:
#
#   {
#     "intent_id":    str  — unique ID (auto-generated if omitted),
#     "intent_type":  str  — one of: code_task, code_editing, implementation,
#                            code_review, research, summarization, planning,
#                            architecture, spec, test_harness, test, docs,
#                            scaffolding, orchestration, native_agent_repo_scan,
#                            improve_tree  (falls back to generic handler),
#     "source_agent": str  — who sent this intent (default: simp_broker),
#     "params":       dict — task-specific parameters:
#                            code_task/code_editing/implementation:
#                              task|description (str), file (str), code (str)
#                            code_review:
#                              code|diff (str)
#                            research/summarization:
#                              query|text|topic (str)
#                            planning/architecture/spec:
#                              goal|description (str)
#                            test_harness/test:
#                              task|description (str)
#                            docs:
#                              description|topic (str)
#                            scaffolding:
#                              task|description (str), context (str)
#                            orchestration:
#                              task|description (str)
#   }
#
# The 422 from the broker was caused by POSTing to /intents/route on port 5555
# (the broker) instead of /intents/handle on port 8767 (the bridge).
#
# Usage: bash bin/send_intent.sh "task description" [type] [priority]

set -euo pipefail

TASK="${1:-Fix protocol_updater.py}"
TYPE="${2:-code_task}"
PRIORITY="${3:-high}"
BRIDGE="http://127.0.0.1:8767"

ID="intent:cowork:$(python3 -c 'import uuid; print(str(uuid.uuid4())[:8])')"

echo "Sending intent ${ID} to ${BRIDGE}/intents/handle ..."

curl -s -X POST "${BRIDGE}/intents/handle" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json, sys
print(json.dumps({
    'intent_id': '${ID}',
    'source_agent': 'perplexity_research',
    'intent_type': '${TYPE}',
    'params': {
        'task': '''${TASK}''',
        'priority': '${PRIORITY}',
    }
}))
")" | python3 -m json.tool
