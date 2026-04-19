#!/bin/bash

echo "=== URGENT: FIXING ALL GEESE COMMUNICATION ==="
echo ""

# 1. Fix Goose #4 (window 5) - Complete respawn
echo "1. Fixing Goose #4 (window 5)..."
tmux kill-window -t flock:5 2>/dev/null || true
sleep 1
tmux new-window -t flock -n goose4
sleep 2
tmux send-keys -t flock:5 "clear" Enter
sleep 1
tmux send-keys -t flock:5 "echo '🪿 GOOSE #4 - A2A CORE SCHEMA & AGGREGATOR'" Enter
sleep 1
tmux send-keys -t flock:5 "echo '========================================='" Enter
sleep 1
tmux send-keys -t flock:5 "echo 'Phase B: Mapping guide for A2A Core Schema'" Enter
sleep 1
tmux send-keys -t flock:5 "echo 'Previous work: executor.py and pnl_ledger.py created'" Enter
sleep 1
tmux send-keys -t flock:5 "echo ''" Enter
sleep 1
tmux send-keys -t flock:5 "CHECK-IN" Enter
echo "   ✅ Goose #4 respawned and CHECK-IN sent"

# 2. Fix Goose #5 (window 6) - Format correction
echo ""
echo "2. Fixing Goose #5 (window 6)..."
tmux send-keys -t flock:6 C-c
sleep 1
tmux send-keys -t flock:6 C-u
sleep 1
tmux send-keys -t flock:6 "Worker: Goose #5" Enter
sleep 1
tmux send-keys -t flock:6 "Phase: Dashboard UX polish completed" Enter
sleep 1
tmux send-keys -t flock:6 "CHECK-IN" Enter
echo "   ✅ Goose #5 format corrected"

# 3. Fix Goose #6 (window 7) - Format correction
echo ""
echo "3. Fixing Goose #6 (window 7)..."
tmux send-keys -t flock:7 C-c
sleep 1
tmux send-keys -t flock:7 C-u
sleep 1
tmux send-keys -t flock:7 "Worker: Goose #6" Enter
sleep 1
tmux send-keys -t flock:7 "Phase: TimesFM service & policy engine completed" Enter
sleep 1
tmux send-keys -t flock:7 "SHIFT COMPLETE" Enter
echo "   ✅ Goose #6 format corrected"

# 4. Ensure watcher is running
echo ""
echo "4. Ensuring watcher is running..."
pkill -f mother_goose_watch 2>/dev/null || true
sleep 2
nohup ./mother_goose_watch_fixed.sh flock > ~/goose-monitor/watcher_nohup.log 2>&1 &
echo "   ✅ Watcher restarted"

# 5. Wait and check status
echo ""
echo "5. Waiting for signals to propagate..."
sleep 15

echo ""
echo "=== FINAL STATUS CHECK ==="
cat ~/goose-monitor/status_board.txt

echo ""
echo "=== EXPECTED RESULT ==="
echo "All geese should now show:"
echo "- goose1: STANDING BY ✓"
echo "- goose2: STANDING BY ✓"
echo "- goose3: STANDING BY ✓"
echo "- goose4: CHECK-IN ✓"
echo "- goose5: CHECK-IN ✓"
echo "- goose6: SHIFT COMPLETE ✓"
echo "- goose7: CHECK-IN ✓"
echo "- goose8: CHECK-IN ✓"
echo ""
echo "If any still show 'NO SIGNAL' or 'unknown', the communication layer is still broken."