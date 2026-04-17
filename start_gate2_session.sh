#!/bin/bash

# Gate 2 Session Startup Script
# SOL Microscopic Live Trading

echo "============================================================"
echo "GATE 2 SESSION STARTUP - SOL MICROSCOPIC LIVE TRADING"
echo "Date: $(date)"
echo "============================================================"

# Check if system is already running
echo "1. Checking system status..."
python3.10 check_system_status.py

echo ""
echo "2. Stopping existing QuantumArb agents..."
pkill -f quantumarb_agent_minimal
pkill -f quantumarb_gate2_sol
sleep 2

echo ""
echo "3. Starting Gate 2 agent..."
nohup python3.10 simp/agents/quantumarb_gate2_sol.py --config config/live_phase2_sol_microscopic.json > logs/gate2_session.log 2>&1 &
GATE2_PID=$!
echo "   Gate 2 agent started with PID: $GATE2_PID"

echo ""
echo "4. Waiting for agent initialization..."
sleep 5

echo ""
echo "5. Checking agent status..."
if ps -p $GATE2_PID > /dev/null; then
    echo "   ✅ Gate 2 agent is running"
else
    echo "   ❌ Gate 2 agent failed to start"
    echo "   Check logs/gate2_session.log for details"
    exit 1
fi

echo ""
echo "6. Creating session directory..."
mkdir -p data/gate2_session
mkdir -p logs/gate2_session

echo ""
echo "7. Recording session start..."
SESSION_START_FILE="data/gate2_session/session_start_$(date +%Y%m%d_%H%M%S).json"
cat > "$SESSION_START_FILE" << EOF
{
  "session_type": "gate2_sol_microscopic",
  "start_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "config_file": "config/live_phase2_sol_microscopic.json",
  "primary_market": "SOL-USD",
  "position_sizing": {
    "min_notional": 0.01,
    "max_notional": 0.10,
    "default_notional": 0.05
  },
  "risk_limits": {
    "max_risk_per_trade_dollar": 0.10,
    "max_session_loss_dollar": 1.00
  },
  "target_trades": 100,
  "min_trades_for_success": 80,
  "gate2_pid": $GATE2_PID
}
EOF
echo "   Session start recorded: $SESSION_START_FILE"

echo ""
echo "8. Creating monitoring script..."
cat > monitor_gate2.sh << 'EOF'
#!/bin/bash
echo "Gate 2 Session Monitor"
echo "======================"
echo "Time: $(date)"
echo ""

# Check process
if ps -p $GATE2_PID > /dev/null; then
    echo "✅ Gate 2 agent running (PID: $GATE2_PID)"
else
    echo "❌ Gate 2 agent not running"
fi

echo ""
echo "Recent logs:"
tail -n 10 logs/gate2_session.log

echo ""
echo "Session progress:"
if [ -f "data/gate2_session/latest_progress.json" ]; then
    python3.10 -c "
import json
with open('data/gate2_session/latest_progress.json', 'r') as f:
    data = json.load(f)
print(f'Trades executed: {data.get(\"trades_executed\", 0)}')
print(f'Successful trades: {data.get(\"trades_successful\", 0)}')
print(f'Total P&L: ${data.get(\"total_pnl\", 0.0):.6f}')
"
else
    echo "No progress file yet"
fi

echo ""
echo "Ledger entries:"
if [ -f "data/live_phase2_sol_spend_ledger.jsonl" ]; then
    LEDGER_COUNT=$(wc -l < "data/live_phase2_sol_spend_ledger.jsonl")
    echo "Total ledger entries: $LEDGER_COUNT"
    if [ $LEDGER_COUNT -gt 0 ]; then
        echo "Last entry:"
        tail -n 1 "data/live_phase2_sol_spend_ledger.jsonl" | python3.10 -m json.tool
    fi
else
    echo "No ledger file yet"
fi
EOF
chmod +x monitor_gate2.sh

echo ""
echo "9. Creating session control script..."
cat > control_gate2.sh << 'EOF'
#!/bin/bash
case "$1" in
    status)
        ./monitor_gate2.sh
        ;;
    stop)
        echo "Stopping Gate 2 session..."
        pkill -f quantumarb_gate2_sol
        echo "Session stopped"
        ;;
    logs)
        tail -f logs/gate2_session.log
        ;;
    progress)
        if [ -f "data/gate2_session/latest_progress.json" ]; then
            python3.10 -m json.tool < "data/gate2_session/latest_progress.json"
        else
            echo "No progress file"
        fi
        ;;
    *)
        echo "Usage: $0 {status|stop|logs|progress}"
        exit 1
        ;;
esac
EOF
chmod +x control_gate2.sh

echo ""
echo "10. Setting up progress tracking..."
cat > update_gate2_progress.py << 'EOF'
#!/usr/bin/env python3.10
"""
Update Gate 2 progress from session data.
"""

import json
import time
from datetime import datetime
from pathlib import Path

def update_progress():
    """Update Gate 2 progress file."""
    data_dir = Path("data/gate2_session")
    progress_file = data_dir / "latest_progress.json"
    
    # Default progress
    progress = {
        "timestamp": datetime.now().isoformat(),
        "trades_executed": 0,
        "trades_successful": 0,
        "total_pnl": 0.0,
        "session_active": True
    }
    
    # Check ledger for trades
    ledger_file = Path("data/live_phase2_sol_spend_ledger.jsonl")
    if ledger_file.exists():
        with open(ledger_file, 'r') as f:
            lines = f.readlines()
            progress["trades_executed"] = len(lines)
            progress["trades_successful"] = len(lines)  # Assuming all ledger entries are successful
    
    # Check decisions directory
    decisions_dir = Path("data/quantumarb_gate2/decisions")
    if decisions_dir.exists():
        decision_files = list(decisions_dir.glob("*.json"))
        progress["opportunities_evaluated"] = len(decision_files)
        
        # Count decisions
        decisions = {"execute": 0, "reject_risk": 0, "reject_slippage": 0, "reject_brp": 0, "reject_symbol": 0}
        for file in decision_files:
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    decision = data.get("opportunity", {}).get("decision", "").lower()
                    if decision in decisions:
                        decisions[decision] += 1
            except:
                pass
        
        progress["decisions"] = decisions
    
    # Save progress
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)
    
    print(f"Progress updated: {progress['trades_executed']} trades executed")
    return progress

if __name__ == "__main__":
    update_progress()
EOF
chmod +x update_gate2_progress.py

echo ""
echo "============================================================"
echo "GATE 2 SESSION READY"
echo "============================================================"
echo ""
echo "Session Configuration:"
echo "  Primary Market: SOL-USD"
echo "  Position Size: $0.01-$0.10"
echo "  Target Trades: 100"
echo "  Min for Success: 80"
echo "  Max Session Loss: $1.00"
echo ""
echo "Control Commands:"
echo "  ./control_gate2.sh status   - Check session status"
echo "  ./control_gate2.sh stop     - Stop session"
echo "  ./control_gate2.sh logs     - View live logs"
echo "  ./control_gate2.sh progress - View progress"
echo ""
echo "Monitoring:"
echo "  ./monitor_gate2.sh          - Quick status check"
echo "  ./update_gate2_progress.py  - Update progress"
echo ""
echo "Session PID: $GATE2_PID"
echo "Log file: logs/gate2_session.log"
echo "============================================================"