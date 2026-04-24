#!/usr/bin/env bash
set -euo pipefail

SIMP_DIR="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
OUT_DIR="/Users/kaseymarcelle/Downloads"   # adjust if the 6 files live elsewhere
SESSION="horsemen"
ARCHIVE_DOCS_DIR="$SIMP_DIR/docs/archive/2026-04"

cd "$SIMP_DIR"

# --- 1. Stage the delivered files -------------------------------------------
mkdir -p simp/mesh data/quantum_dataset data/inboxes/gate4_real

cp "$OUT_DIR/quantum_signal_bridge.py"        ./quantum_signal_bridge.py
cp "$OUT_DIR/goose_quantum_orchestrator.py"   ./goose_quantum_orchestrator.py
cp "$OUT_DIR/projectx_quantum_advisor.py"     ./projectx_quantum_advisor.py
cp "$OUT_DIR/simp_trust_scorer.py"            ./simp/mesh/trust_scorer.py
cp "$OUT_DIR/quantum_portfolio_examples.json" ./data/quantum_dataset/portfolio_optimization_examples.json
mkdir -p "$ARCHIVE_DOCS_DIR"
if [ -f "$OUT_DIR/QUANTUM_PERMEATION_ROADMAP.md" ]; then
  cp "$OUT_DIR/QUANTUM_PERMEATION_ROADMAP.md" "$ARCHIVE_DOCS_DIR/QUANTUM_PERMEATION_ROADMAP.md"
fi

echo "[stage] files copied."

# --- 2. Kill any stale session ----------------------------------------------
tmux kill-session -t "$SESSION" 2>/dev/null || true

# --- 3. Create session with Mother Goose in window 0 ------------------------
tmux new-session -d -s "$SESSION" -n mother-goose -x 220 -y 50 -c "$SIMP_DIR"
tmux send-keys -t "$SESSION:mother-goose" \
  'source venv_gate4/bin/activate && clear && echo "=== MOTHER GOOSE ===" && python3.10 goose_quantum_orchestrator.py' C-m

# --- 4. Spawn the 6 geese as their own windows ------------------------------
# name           : command
geese=(
  "goose1-bridge-once:python3.10 quantum_signal_bridge.py --once"
  "goose2-bridge-live:python3.10 quantum_signal_bridge.py"
  "goose3-px-scan:python3.10 projectx_quantum_advisor.py --proactive-scan"
  "goose4-px-live:python3.10 projectx_quantum_advisor.py"
  "goose5-trust:python3.10 -m simp.mesh.trust_scorer"
  "goose6-inbox-watch:watch -n 2 'ls -la data/inboxes/gate4_real/ | tail -20'"
)

for entry in "${geese[@]}"; do
  name="${entry%%:*}"
  cmd="${entry#*:}"
  tmux new-window -t "$SESSION" -n "$name" -c "$SIMP_DIR"
  tmux send-keys  -t "$SESSION:$name" \
    "source venv_gate4/bin/activate && clear && echo '=== $name ===' && $cmd" C-m
done

# --- 5. Land on Mother Goose and attach -------------------------------------
tmux select-window -t "$SESSION:mother-goose"
echo "[ok] Horsemen riding. Attaching..."
exec tmux attach -t "$SESSION"
