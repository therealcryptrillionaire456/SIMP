#!/usr/bin/env bash
# start_broker.sh — Start the SIMP broker with all prerequisites
set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$HOME/bullbear/logs"
LOG="$LOG_DIR/simp_broker.log"

mkdir -p "$LOG_DIR" "$REPO/data" "$REPO/data/inboxes" "$REPO/data/tmp" "$REPO/logs"

echo "Starting SIMP broker..."
echo "Repo: $REPO"
echo "Log:  $LOG"

cd "$REPO"
nohup python3.10 bin/start_server.py >> "$LOG" 2>&1 &
PID=$!
echo "Broker PID: $PID"
echo $PID > "$REPO/data/broker.pid"

sleep 2
if curl -sf http://127.0.0.1:5555/health > /dev/null 2>&1; then
    echo "✓ Broker is up at http://127.0.0.1:5555"
else
    echo "✗ Broker did not start. Check log:"
    echo "  tail -20 $LOG"
    tail -20 "$LOG"
fi
