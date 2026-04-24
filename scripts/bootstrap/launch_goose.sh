#!/bin/bash
# launch_goose.sh
# Goose launcher that injects KLOUTBOT context into every turn
# via the 'tom' (Top Of Mind) extension.
#
# Usage:
#   bash scripts/bootstrap/launch_goose.sh              # standard session
#   bash scripts/bootstrap/launch_goose.sh --headless   # no goose, just generate context
#   bash scripts/bootstrap/launch_goose.sh --update     # update Obsidian + context file only

SIMP_DIR="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
OBSIDIAN_VAULT="/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs"
CONTEXT_FILE="$SIMP_DIR/SIMP_MASTER_CONTEXT.md"

cd "$SIMP_DIR"
source venv_gate4/bin/activate

# ── 1. Generate fresh context file ───────────────────────────────────────────
echo "Generating KLOUTBOT context..."
python3.10 scripts/kloutbot/load_context.py --brief > "$CONTEXT_FILE"

# ── 2. Update Obsidian vault ──────────────────────────────────────────────────
if [ -d "$OBSIDIAN_VAULT" ]; then
    echo "Updating Obsidian vault: $OBSIDIAN_VAULT"
    python3.10 scripts/kloutbot/load_context.py --update
else
    echo "⚠️  Obsidian vault not found at $OBSIDIAN_VAULT"
fi

# ── 3. Verify quantum stack is running ────────────────────────────────────────
echo ""
echo "── Quantum stack check ─────────────────────────────────────"
for proc in "quantum_mesh_consumer" "quantum_signal_bridge" "quantumarb_mesh_consumer" "projectx_quantum_advisor"; do
    if pgrep -f "$proc" > /dev/null; then
        echo "  ✅ $proc"
    else
        echo "  🚀 Starting $proc..."
        nohup python3.10 ${proc}.py > "data/logs/goose/${proc}.log" 2>&1 &
        sleep 1
    fi
done

# ── 4. Check for KLOUTBOT instructions ───────────────────────────────────────
echo ""
echo "── KLOUTBOT instruction check ──────────────────────────────"
python3.10 scripts/kloutbot/kloutbot_bridge.py --poll

if [[ "${1:-}" == "--headless" || "${2:-}" == "--headless" ]]; then
    echo "Headless mode — context updated, stack running."
    exit 0
fi

if [[ "${1:-}" == "--update" || "${2:-}" == "--update" ]]; then
    echo "Update complete."
    exit 0
fi

# ── 5. Launch Goose with tom context injection ────────────────────────────────
echo ""
echo "── Launching Goose with KLOUTBOT context ───────────────────"
echo "  Context file: $CONTEXT_FILE"
echo "  Provider: $(grep GOOSE_PROVIDER ~/.config/goose/config.yaml | head -1)"
echo ""

# tom extension reads GOOSE_MOIM_MESSAGE_FILE and injects it into every turn
export GOOSE_MOIM_MESSAGE_FILE="$CONTEXT_FILE"

# Also expose key paths
export SIMP_DIR="$SIMP_DIR"
export OBSIDIAN_VAULT="$OBSIDIAN_VAULT"
export KLOUTBOT_ACTIVE=1

echo "GOOSE_MOIM_MESSAGE_FILE=$CONTEXT_FILE"
echo ""
goose session
