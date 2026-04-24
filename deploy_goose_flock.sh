#!/bin/bash
# Provision a tmux-based goose flock without auto-launching interactive Goose.

set -euo pipefail

SESSION_NAME="${GOOSE_FLOCK_SESSION:-goose_flock}"
SIMP_REPO_PATH="$(cd "$(dirname "$0")" && pwd)"
STRAY_GOOSE_PATH="${HOME}/stray_goose"
BROKER_URL="${SIMP_BROKER_URL:-http://127.0.0.1:5555}"
AUTORUN=0

if [[ "${1:-}" == "--autorun" ]]; then
  AUTORUN=1
fi

require_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_bin tmux
require_bin python3.10

if [[ ! -d "${SIMP_REPO_PATH}/venv_gate4" ]]; then
  echo "Missing virtualenv: ${SIMP_REPO_PATH}/venv_gate4" >&2
  exit 1
fi

if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  echo "Session '${SESSION_NAME}' already exists."
  echo "Attach with: tmux attach -t ${SESSION_NAME}"
  exit 0
fi

echo "Preflight:"
echo "  repo:   ${SIMP_REPO_PATH}"
echo "  broker: ${BROKER_URL}"

if curl -sf "${BROKER_URL}/health" >/dev/null 2>&1; then
  echo "  broker health: ok"
else
  echo "  broker health: unavailable"
fi

tmux new-session -d -s "${SESSION_NAME}" -c "${SIMP_REPO_PATH}" -n "control"
for window in qip_fixer revenue_builder infra_hardener analytics tester; do
  tmux new-window -t "${SESSION_NAME}" -c "${SIMP_REPO_PATH}" -n "${window}"
done

prime_window() {
  local window="$1"
  local title="$2"
  local hint="$3"
  tmux send-keys -t "${SESSION_NAME}:${window}" "source venv_gate4/bin/activate" C-m
  tmux send-keys -t "${SESSION_NAME}:${window}" "echo '${title}'" C-m
  tmux send-keys -t "${SESSION_NAME}:${window}" "echo '${hint}'" C-m
}

prime_window "control" "Mother Goose Control" "Run preflight, context sync, and broker checks from here."
prime_window "qip_fixer" "Goose 1 — QIP Fixer" "Focus on quantum mesh health, polling, and QIP round-trip validation."
prime_window "revenue_builder" "Goose 2 — Revenue Builder" "Focus on QuantumArb and BullBear revenue-path deliverables."
prime_window "infra_hardener" "Goose 3 — Infra Hardener" "Focus on consensus, BRP, coordination, and safety hardening."
prime_window "analytics" "Goose 4 — Analytics" "Focus on advisory broadcast, prediction enhancement, and reputation systems."
prime_window "tester" "Goose 5 — Tester" "Focus on targeted pytest and runtime validation."

tmux send-keys -t "${SESSION_NAME}:control" "python3.10 scripts/kloutbot/load_context.py --brief" C-m
tmux send-keys -t "${SESSION_NAME}:control" "python3.10 scripts/kloutbot/kloutbot_bridge.py --execute" C-m
tmux send-keys -t "${SESSION_NAME}:control" "curl -s ${BROKER_URL}/health | python3.10 -m json.tool" C-m

if [[ "${AUTORUN}" -eq 1 ]]; then
  tmux send-keys -t "${SESSION_NAME}:qip_fixer" "python3.10 goose_quantum_orchestrator.py --status" C-m
  tmux send-keys -t "${SESSION_NAME}:revenue_builder" "python3.10 quantumarb_mesh_consumer.py --once" C-m
  tmux send-keys -t "${SESSION_NAME}:analytics" "python3.10 quantum_advisory_broadcaster.py --once --dry-run" C-m
  tmux send-keys -t "${SESSION_NAME}:tester" "python3.10 -m pytest tests/test_quantum_advisory_broadcaster.py tests/test_bullbear_quantum_bridge.py tests/test_commitment_market.py -q" C-m
fi

tmux select-window -t "${SESSION_NAME}:control"

echo "Goose flock session created: ${SESSION_NAME}"
echo "Attach: tmux attach -t ${SESSION_NAME}"
echo "Detach: Ctrl-b d"
echo "Autorun enabled: ${AUTORUN}"
