#!/usr/bin/env bash
# FIX_AND_VERIFY.command
# Written by KLOUTBOT, 2026-04-20.
#
# Purpose: apply the broker.register_agent idempotency patch (already on disk)
# by restarting the broker, then prove the KLOUTBOT ↔ Goose round-trip works
# end-to-end. Double-click in Finder to run.
#
# What it does:
#   1. Kill existing broker + bridge + QIP consumer
#   2. Start broker (python3.10 -m simp.server.broker)
#   3. Wait for /health to respond
#   4. Start kloutbot_bridge_fixed.py --loop in background (disowned)
#   5. Start quantum_mesh_consumer.py in background (disowned)
#   6. Verify bridge agent goose_kloutbot_bridge is in mesh bus
#   7. Send a tiny test instruction, poll kloutbot_results for 30s
#   8. Print PASS / FAIL banner

set -u

BROKER="http://127.0.0.1:5555"
SIMP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$SIMP_DIR/data/logs/goose"
mkdir -p "$LOG_DIR"

say() { printf '\033[1;36m▶\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
bad() { printf '\033[1;31m✗\033[0m %s\n' "$*"; }
hr()  { printf '\033[1;35m────────────────────────────────────────────\033[0m\n'; }

cd "$SIMP_DIR"

hr
say "KLOUTBOT fix-and-verify sequence — $(date)"
hr

# ── 1. Kill stale processes ───────────────────────────────────────────────────
say "Killing any running broker / bridge / QIP consumer..."
pkill -f "simp.server.broker" 2>/dev/null || true
pkill -f "simp/server/http_server" 2>/dev/null || true
pkill -f "kloutbot_bridge" 2>/dev/null || true
pkill -f "quantum_mesh_consumer" 2>/dev/null || true
sleep 3
ok "Old processes cleared."

# ── 2. Start broker ───────────────────────────────────────────────────────────
say "Starting broker with patched register_agent (idempotent mesh reconcile)..."
nohup python3.10 -m simp.server.broker \
  > "$LOG_DIR/broker.log" 2>&1 &
BROKER_PID=$!
disown $BROKER_PID 2>/dev/null || true
sleep 1
if ! kill -0 "$BROKER_PID" 2>/dev/null; then
  bad "Broker failed to start. Check $LOG_DIR/broker.log"
  echo "Last 40 lines:"
  tail -40 "$LOG_DIR/broker.log"
  exit 1
fi

say "Waiting for broker /health to respond..."
for i in $(seq 1 45); do
  if curl -s -m 2 "$BROKER/health" > /dev/null 2>&1; then
    ok "Broker up on :5555 (PID $BROKER_PID, took ${i}s)"
    break
  fi
  printf '.'
  sleep 1
done
printf '\n'
if ! curl -s -m 2 "$BROKER/health" > /dev/null 2>&1; then
  bad "Broker never became healthy. Last 40 lines of broker.log:"
  tail -40 "$LOG_DIR/broker.log"
  exit 1
fi

# ── 3. Start bridge ───────────────────────────────────────────────────────────
say "Starting scripts/kloutbot/kloutbot_bridge_fixed.py --loop..."
nohup python3.10 scripts/kloutbot/kloutbot_bridge_fixed.py --loop \
  > "$LOG_DIR/kloutbot_bridge_fixed.log" 2>&1 &
BRIDGE_PID=$!
disown $BRIDGE_PID 2>/dev/null || true
sleep 2
if kill -0 "$BRIDGE_PID" 2>/dev/null; then
  ok "Bridge alive (PID $BRIDGE_PID)"
else
  bad "Bridge died. Last 30 lines:"
  tail -30 "$LOG_DIR/kloutbot_bridge_fixed.log"
fi

# ── 4. Start QIP consumer ─────────────────────────────────────────────────────
say "Starting quantum_mesh_consumer.py..."
nohup python3.10 quantum_mesh_consumer.py \
  > "$LOG_DIR/quantum_mesh_consumer.log" 2>&1 &
QIP_PID=$!
disown $QIP_PID 2>/dev/null || true
sleep 2
if kill -0 "$QIP_PID" 2>/dev/null; then
  ok "QIP consumer alive (PID $QIP_PID)"
else
  bad "QIP consumer died. Last 30 lines:"
  tail -30 "$LOG_DIR/quantum_mesh_consumer.log"
fi

# ── 5. Verify bridge is in mesh bus ───────────────────────────────────────────
hr
say "Verifying goose_kloutbot_bridge is in mesh bus..."
sleep 3
STATUS=$(curl -s -m 5 "$BROKER/mesh/agent/goose_kloutbot_bridge/status")
echo "$STATUS" | python3.10 -m json.tool 2>/dev/null || echo "$STATUS"
if echo "$STATUS" | grep -q '"status": "success"'; then
  ok "Bridge IS in mesh bus."
else
  bad "Bridge NOT in mesh bus. Bridge log:"
  tail -30 "$LOG_DIR/kloutbot_bridge_fixed.log"
  bad "Broker log (last 30):"
  tail -30 "$LOG_DIR/broker.log"
  bad "FAILED — patch did not take effect. Abort."
  exit 1
fi

# ── 6. Send a test instruction and wait for round-trip ────────────────────────
hr
say "Sending round-trip test instruction (simple echo)..."
TEST_ID="verify-$(date +%s)"
cat > /tmp/kloutbot_verify_instruction.json <<EOF
{
  "instruction_id": "$TEST_ID",
  "type": "commands",
  "description": "Round-trip verification — KLOUTBOT asks Goose to echo and date",
  "stop_on_failure": false,
  "commands": [
    { "type": "bash", "cmd": "echo KLOUTBOT_VERIFY_OK && date", "description": "echo" }
  ]
}
EOF
python3.10 scripts/kloutbot/send_kloutbot_instruction.py --file /tmp/kloutbot_verify_instruction.json

say "Polling kloutbot_results for up to 30s..."
python3.10 scripts/kloutbot/send_kloutbot_instruction.py --results --wait &
POLL_PID=$!
wait $POLL_PID

# ── 7. Final verdict ──────────────────────────────────────────────────────────
hr
RESULTS_FILE="$LOG_DIR/kloutbot_results.jsonl"
if [ -f "$RESULTS_FILE" ] && grep -q "$TEST_ID" "$RESULTS_FILE"; then
  ok "ROUND-TRIP CONFIRMED — instruction $TEST_ID found in $RESULTS_FILE"
  echo ""
  grep "$TEST_ID" "$RESULTS_FILE" | tail -1 | python3.10 -m json.tool 2>/dev/null
  hr
  ok "ALL SYSTEMS GREEN. KLOUTBOT can now drive Goose via the mesh."
  echo ""
  echo "From now on, to send an instruction:"
  echo "    python3.10 scripts/kloutbot/send_kloutbot_instruction.py"
  echo "Then read:"
  echo "    python3.10 scripts/kloutbot/send_kloutbot_instruction.py --results --wait"
else
  bad "ROUND-TRIP FAILED — no result for $TEST_ID yet."
  echo ""
  echo "Check bridge log: tail -40 $LOG_DIR/kloutbot_bridge_fixed.log"
  echo "Check broker log: tail -40 $LOG_DIR/broker.log"
fi

hr
echo "Broker PID:  $BROKER_PID  (log: $LOG_DIR/broker.log)"
echo "Bridge PID:  $BRIDGE_PID  (log: $LOG_DIR/kloutbot_bridge_fixed.log)"
echo "QIP PID:     $QIP_PID  (log: $LOG_DIR/quantum_mesh_consumer.log)"
hr
