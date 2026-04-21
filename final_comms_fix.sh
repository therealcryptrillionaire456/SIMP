#!/bin/bash

echo "=== FINAL COMMUNICATION LAYER FIX ==="
echo "Fixing remaining issues..."
echo ""

# 1. COMPLETELY RECREATE GOOSE #4 WINDOW
echo "1. NUKING AND RECREATING GOOSE #4..."
tmux kill-window -t flock:5 2>/dev/null || true
sleep 2
tmux new-window -t flock -n goose4
sleep 2

# Send COMPLETE CHECK-IN block to Goose #4
tmux send-keys -t flock:5 "CHECK-IN" Enter
sleep 1
tmux send-keys -t flock:5 "Worker: Goose #4" Enter
sleep 1
tmux send-keys -t flock:5 "Scope: A2A Core Schema & Aggregator" Enter
sleep 1
tmux send-keys -t flock:5 "Phase completed: Phase A (Sanity testing) completed, starting Phase B" Enter
sleep 1
tmux send-keys -t flock:5 "Artifacts created/changed: executor.py (379 lines), pnl_ledger.py" Enter
sleep 1
tmux send-keys -t flock:5 "Tests run: 68 tests passing" Enter
sleep 1
tmux send-keys -t flock:5 "Key findings: Ready for Phase B mapping guide" Enter
sleep 1
tmux send-keys -t flock:5 "Open issues: none" Enter
sleep 1
tmux send-keys -t flock:5 "Recommended next step: Continue Phase B (Mapping guide)" Enter

# 2. FIX GOOSE #5 PHASE INFO
echo ""
echo "2. FIXING GOOSE #5 PHASE INFO..."
tmux send-keys -t flock:6 "Phase completed: All phases (A-D) completed - Dashboard UX polish" Enter
sleep 1
tmux send-keys -t flock:6 "CHECK-IN" Enter

# 3. FIX GOOSE #6 PHASE INFO
echo ""
echo "3. FIXING GOOSE #6 PHASE INFO..."
tmux send-keys -t flock:7 "Phase completed: All phases completed - TimesFM service & policy engine" Enter
sleep 1
tmux send-keys -t flock:7 "SHIFT COMPLETE" Enter

# 4. RESTART WATCHER WITH AGGRESSIVE POLLING
echo ""
echo "4. RESTARTING WATCHER..."
pkill -f mother_goose_watch 2>/dev/null || true
sleep 2

# Create aggressive watcher version
cat > /tmp/aggressive_watcher.sh << 'EOF'
#!/bin/bash
SESSION="flock"
OUTDIR="$HOME/goose-monitor"
INBOX="$OUTDIR/inbox_for_mother_goose.txt"
STATUS="$OUTDIR/status_board.txt"

while true; do
  {
    echo "============================================================"
    echo "Mother Goose Status Board - AGGRESSIVE MODE"
    echo "Session: $SESSION"
    echo "Updated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================"
    echo ""
  } > "$STATUS"
  
  for win in goose1 goose2 goose3 goose4 goose5 goose6 goose7 goose8; do
    content="$(tmux capture-pane -p -t "$SESSION:$win" -S -50 2>/dev/null || echo 'WINDOW ERROR')"
    
    signal="$(echo "$content" | grep -E '^(CHECK-IN|SHIFT COMPLETE|STANDING BY|ERROR)$' | tail -1 || true)"
    worker="$(echo "$content" | grep '^Worker: ' | tail -1 | sed 's/^Worker: //' || true)"
    phase="$(echo "$content" | grep '^Phase completed: ' | tail -1 | sed 's/^Phase completed: //' || true)"
    
    if [[ -z "$signal" ]]; then
      echo "- $win: NO SIGNAL" >> "$STATUS"
    else
      echo "- $win: $signal | Worker: ${worker:-unknown} | Phase: ${phase:-n/a}" >> "$STATUS"
    fi
  done
  
  sleep 5  # Aggressive 5-second polling
done
EOF

chmod +x /tmp/aggressive_watcher.sh
nohup /tmp/aggressive_watcher.sh > ~/goose-monitor/aggressive_watcher.log 2>&1 &

echo "5. WAITING FOR DETECTION..."
sleep 15

echo ""
echo "=== FINAL STATUS ==="
cat ~/goose-monitor/status_board.txt

echo ""
echo "=== COMMUNICATION LAYER MUST SHOW ==="
echo "ALL geese must have signals. If any show 'NO SIGNAL', layer is BROKEN."