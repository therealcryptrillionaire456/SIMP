#!/usr/bin/env bash
# START_THE_MACHINE.sh
# Written by KLOUTBOT overnight (2026-04-20) to bring the mesh pipeline
# back online with one command.
#
# Usage:  bash scripts/bootstrap/START_THE_MACHINE.command
#
# What it does, in order:
#   1. Sanity-check broker health on :5555
#   2. Kill any half-dead bridge / consumer processes
#   3. Start kloutbot_bridge_fixed.py --loop in background
#   4. Start quantum_mesh_consumer.py in background
#   5. Wait 8 seconds, then drain + show kloutbot_results.jsonl
#   6. Print 1-page system status

set -u

BROKER="http://127.0.0.1:5555"
SIMP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$SIMP_DIR/data/logs/goose"
mkdir -p "$LOG_DIR"

say() { printf '\033[1;36m▶\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
bad() { printf '\033[1;31m✗\033[0m %s\n' "$*"; }

cd "$SIMP_DIR"

# ── 1. Broker health ──────────────────────────────────────────────────────────
say "Checking broker at $BROKER ..."
if curl -s -m 3 "$BROKER/health" > /dev/null 2>&1; then
  ok "Broker is up."
else
  bad "Broker is DOWN. Start it first:"
  echo "    python3.10 simp/server/http_server.py &"
  echo "    (or whatever command you normally use)"
  exit 1
fi

# ── 2. Kill stale bridges/consumers ──────────────────────────────────────────
say "Cleaning up stale processes..."
pkill -f "kloutbot_bridge" 2>/dev/null
pkill -f "quantum_mesh_consumer" 2>/dev/null
sleep 2
ok "Old processes cleared."

# ── 3. Start the KLOUTBOT bridge ──────────────────────────────────────────────
say "Starting KLOUTBOT ↔ Goose bridge (scripts/kloutbot/kloutbot_bridge_fixed.py --loop)..."
nohup python3.10 scripts/kloutbot/kloutbot_bridge_fixed.py --loop \
  > "$LOG_DIR/kloutbot_bridge_fixed.log" 2>&1 &
BRIDGE_PID=$!
sleep 1
if kill -0 "$BRIDGE_PID" 2>/dev/null; then
  ok "Bridge alive (PID $BRIDGE_PID) — tailing log to data/logs/goose/kloutbot_bridge_fixed.log"
else
  bad "Bridge failed to start. Check $LOG_DIR/kloutbot_bridge_fixed.log"
fi

# ── 4. Start the QIP quantum consumer ─────────────────────────────────────────
say "Starting quantum_mesh_consumer (QIP intent listener)..."
nohup python3.10 quantum_mesh_consumer.py \
  > "$LOG_DIR/quantum_mesh_consumer.log" 2>&1 &
QIP_PID=$!
sleep 1
if kill -0 "$QIP_PID" 2>/dev/null; then
  ok "QIP consumer alive (PID $QIP_PID)"
else
  bad "QIP consumer failed to start. Check $LOG_DIR/quantum_mesh_consumer.log"
fi

# ── 5. Drain queued instructions ──────────────────────────────────────────────
say "Waiting 8s for bridge to drain the queue..."
sleep 8

RESULTS_FILE="$LOG_DIR/kloutbot_results.jsonl"
if [ -f "$RESULTS_FILE" ]; then
  COUNT=$(wc -l < "$RESULTS_FILE" | tr -d ' ')
  ok "Total results in $RESULTS_FILE: $COUNT"
  echo ""
  say "Last 5 results:"
  tail -5 "$RESULTS_FILE" | python3.10 -m json.tool --no-ensure-ascii 2>/dev/null || tail -5 "$RESULTS_FILE"
else
  bad "No results file yet."
fi

# ── 6. System snapshot ────────────────────────────────────────────────────────
echo ""
say "── SYSTEM SNAPSHOT ───────────────────────────────────────"
echo "Time:              $(date)"
echo "Broker:            $(curl -s -m 3 "$BROKER/health" | head -c 200)"
echo "Bridge PID:        $BRIDGE_PID"
echo "QIP consumer PID:  $QIP_PID"
echo "Gate4 signals:     $(ls data/inboxes/gate4_real/*.json 2>/dev/null | wc -l | tr -d ' ')"
echo "Processed signals: $(ls data/inboxes/gate4_real/_processed/*.json 2>/dev/null | wc -l | tr -d ' ')"
echo "Failed signals:    $(ls data/inboxes/gate4_real/_failed/*.json 2>/dev/null | wc -l | tr -d ' ')"
echo ""
say "── RECENT MESH EVENTS ────────────────────────────────────"
tail -5 data/mesh_events.jsonl 2>/dev/null

echo ""
ok "Machine is up. KLOUTBOT sends instructions → bridge → Goose → results."
echo "Send a new instruction from KLOUTBOT side with:"
echo "    python3.10 scripts/kloutbot/send_kloutbot_instruction.py"
echo "Then read results with:"
echo "    python3.10 scripts/kloutbot/send_kloutbot_instruction.py --results --wait"
