#!/bin/bash

echo "Gate 2 Progress Monitor"
echo "======================="
echo "Time: $(date)"
echo ""

# Check if agent is running
if pgrep -f quantumarb_gate2_simple > /dev/null; then
    echo "✅ Gate 2 agent is running"
    AGENT_PID=$(pgrep -f quantumarb_gate2_simple)
    echo "   PID: $AGENT_PID"
else
    echo "❌ Gate 2 agent is not running"
    echo "   Start with: python3.10 simp/agents/quantumarb_gate2_simple.py --config config/live_phase2_sol_microscopic.json"
    exit 1
fi

echo ""
echo "Session Progress:"

# Check decisions directory
DECISIONS_DIR="data/quantumarb_gate2_simple/decisions"
if [ -d "$DECISIONS_DIR" ]; then
    DECISION_COUNT=$(ls -1 "$DECISIONS_DIR"/*.json 2>/dev/null | wc -l)
    echo "  Decisions made: $DECISION_COUNT"
    
    # Count approvals vs rejections
    APPROVALS=0
    REJECTIONS=0
    
    for file in "$DECISIONS_DIR"/*.json; do
        if [ -f "$file" ]; then
            DECISION=$(python3.10 -c "
import json
try:
    with open('$file', 'r') as f:
        data = json.load(f)
    print(data.get('opportunity', {}).get('decision', ''))
except:
    print('')
")
            if [ "$DECISION" = "execute" ]; then
                APPROVALS=$((APPROVALS + 1))
            elif [ "$DECISION" != "" ]; then
                REJECTIONS=$((REJECTIONS + 1))
            fi
        fi
    done
    
    echo "  Approved trades: $APPROVALS"
    echo "  Rejected trades: $REJECTIONS"
    
    if [ $DECISION_COUNT -gt 0 ]; then
        APPROVAL_RATE=$(echo "scale=1; $APPROVALS * 100 / $DECISION_COUNT" | bc)
        echo "  Approval rate: $APPROVAL_RATE%"
    fi
else
    echo "  No decisions directory yet"
fi

echo ""
echo "Session Results:"

# Check for session results
RESULTS_FILE=$(find data/quantumarb_gate2_simple -name "session_*.json" -type f | head -1)
if [ -f "$RESULTS_FILE" ]; then
    echo "  Results file: $(basename "$RESULTS_FILE")"
    
    python3.10 -c "
import json
with open('$RESULTS_FILE', 'r') as f:
    data = json.load(f)
print(f'  Trades executed: {data.get(\"trades_executed\", 0)}')
print(f'  Total P&L: \${data.get(\"total_pnl\", 0.0):.6f}')
print(f'  Opportunities evaluated: {data.get(\"opportunities_evaluated\", 0)}')
"
else
    echo "  No session results yet"
fi

echo ""
echo "Gate 2 Targets:"
echo "  Minimum trades for success: 80"
echo "  Target trades: 100"
echo "  Max session loss: \$1.00"

echo ""
echo "Recent Logs:"
tail -n 5 logs/gate2_simple_session.log 2>/dev/null || echo "  No log file yet"

echo ""
echo "To stop the agent: pkill -f quantumarb_gate2_simple"