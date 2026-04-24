#!/bin/bash
# DEPLOY_FIXES.sh
# Run this from your simp directory:
#   cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
#   bash ~/Downloads/DEPLOY_FIXES.sh
# (or wherever you save this file)
#
# What this does:
#   1. Patches quantum_mesh_consumer.py (adds simp_versions to registration)
#   2. Fixes scripts/kloutbot/load_context.py Obsidian vault path
#   3. Deploys scripts/bootstrap/launch_goose.sh
#   4. Restarts quantum stack
#   5. Tails logs to confirm registration success

set -uo pipefail
SIMP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OBSIDIAN_VAULT="/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs"

cd "$SIMP_DIR"
source venv_gate4/bin/activate

echo "════════════════════════════════════════════"
echo "  KLOUTBOT DEPLOY_FIXES — $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════"

# ── FIX 1: Add simp_versions to quantum_mesh_consumer.py ─────────────────────
echo ""
echo "── Fix 1: quantum_mesh_consumer.py simp_versions ───────────"
python3.10 - <<'PYEOF'
import re, sys
path = "quantum_mesh_consumer.py"
try:
    content = open(path).read()
except FileNotFoundError:
    print(f"  ⚠️  {path} not found — skipping")
    sys.exit(0)

old = '"agent_type": AGENT_TYPE,'
new = '"agent_type": AGENT_TYPE,\n        "simp_versions": ["1.0"],'
if '"simp_versions"' in content:
    print("  ✅ simp_versions already present")
elif old in content:
    open(path, 'w').write(content.replace(old, new, 1))
    print("  ✅ PATCHED: added simp_versions to register payload")
else:
    # Try broader pattern
    pattern = r'("agent_type"\s*:\s*AGENT_TYPE\s*,)'
    m = re.search(pattern, content)
    if m:
        replacement = m.group(1) + '\n        "simp_versions": ["1.0"],'
        open(path, 'w').write(content[:m.start()] + replacement + content[m.end():])
        print("  ✅ PATCHED (regex): added simp_versions to register payload")
    else:
        print("  ❌ Pattern not found — inspect quantum_mesh_consumer.py manually")
        print("     Add this line after agent_type: '\"simp_versions\": [\"1.0\"],'")
PYEOF

# ── FIX 2: Update Obsidian vault path in scripts/kloutbot/load_context.py ───
echo ""
echo "── Fix 2: scripts/kloutbot/load_context.py vault path ──────"
python3.10 - <<PYEOF
import re, sys
path = "scripts/kloutbot/load_context.py"
vault = "$OBSIDIAN_VAULT"
try:
    content = open(path).read()
except FileNotFoundError:
    print(f"  ⚠️  {path} not found — skipping")
    sys.exit(0)

if vault in content:
    print(f"  ✅ Vault path already present: {vault}")
else:
    # Find OBSIDIAN_VAULT_CANDIDATES list and prepend our path
    pattern = r'(OBSIDIAN_VAULT_CANDIDATES\s*=\s*\[)'
    replacement = r'\1\n    "' + vault + r'",  # primary'
    new_content = re.sub(pattern, replacement, content, count=1)
    if new_content != content:
        open(path, 'w').write(new_content)
        print(f"  ✅ PATCHED: prepended {vault} to OBSIDIAN_VAULT_CANDIDATES")
    else:
        # Fallback: try to find any path list and add it
        if "OBSIDIAN_VAULT" in content:
            print(f"  ⚠️  OBSIDIAN_VAULT exists but pattern not matched.")
            print(f"     Manually ensure this path is in candidates: {vault}")
        else:
            print(f"  ⚠️  OBSIDIAN_VAULT_CANDIDATES not found in {path}")
PYEOF

# ── FIX 3: Deploy scripts/bootstrap/launch_goose.sh ─────────────────────────
echo ""
echo "── Fix 3: Deploy scripts/bootstrap/launch_goose.sh ─────────"
LAUNCH_SRC="$HOME/Downloads/launch_goose.sh"
LAUNCH_DST="$SIMP_DIR/scripts/bootstrap/launch_goose.sh"

if [ -f "$LAUNCH_SRC" ]; then
    mkdir -p "$(dirname "$LAUNCH_DST")"
    cp "$LAUNCH_SRC" "$LAUNCH_DST"
    chmod +x "$LAUNCH_DST"
    echo "  ✅ Deployed from Downloads"
elif [ -f "$LAUNCH_DST" ]; then
    chmod +x "$LAUNCH_DST"
    echo "  ✅ Already present in scripts/bootstrap"
else
    echo "  ⚠️  launch_goose.sh not found — writing it now"
    cat > "$LAUNCH_DST" << 'GOOSE_EOF'
#!/bin/bash
# launch_goose.sh — KLOUTBOT context injector for Goose
SIMP_DIR="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
OBSIDIAN_VAULT="/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs"
CONTEXT_FILE="$SIMP_DIR/SIMP_MASTER_CONTEXT.md"

cd "$SIMP_DIR"
source venv_gate4/bin/activate

echo "Generating KLOUTBOT context..."
python3.10 scripts/kloutbot/load_context.py --brief > "$CONTEXT_FILE"

if [ -d "$OBSIDIAN_VAULT" ]; then
    echo "Updating Obsidian vault..."
    python3.10 scripts/kloutbot/load_context.py --update
fi

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

echo "── KLOUTBOT instruction check ──────────────────────────────"
python3.10 scripts/kloutbot/kloutbot_bridge.py --poll

if [[ "${1:-}" == "--headless" || "${2:-}" == "--headless" ]]; then
    echo "Headless mode — context updated, stack running."; exit 0
fi
if [[ "${1:-}" == "--update" || "${2:-}" == "--update" ]]; then
    echo "Update complete."; exit 0
fi

echo "── Launching Goose with KLOUTBOT context ───────────────────"
echo "  Context file: $CONTEXT_FILE"
export GOOSE_MOIM_MESSAGE_FILE="$CONTEXT_FILE"
export SIMP_DIR="$SIMP_DIR"
export OBSIDIAN_VAULT="$OBSIDIAN_VAULT"
export KLOUTBOT_ACTIVE=1
goose session
GOOSE_EOF
    chmod +x "$LAUNCH_DST"
    echo "  ✅ Written fresh"
fi

# ── FIX 4: Restart quantum stack ─────────────────────────────────────────────
echo ""
echo "── Fix 4: Restart quantum stack ────────────────────────────"
for proc in "quantum_mesh_consumer" "quantum_signal_bridge" "quantumarb_mesh_consumer" "projectx_quantum_advisor"; do
    if pgrep -f "$proc" > /dev/null; then
        echo "  🔄 Stopping $proc..."
        pkill -f "$proc" 2>/dev/null || true
        sleep 1
    fi
done
sleep 2

mkdir -p data/logs/goose
for proc in "quantum_mesh_consumer" "quantum_signal_bridge" "quantumarb_mesh_consumer" "projectx_quantum_advisor"; do
    if [ -f "${proc}.py" ]; then
        echo "  🚀 Starting $proc..."
        nohup python3.10 ${proc}.py > "data/logs/goose/${proc}.log" 2>&1 &
        sleep 1
    else
        echo "  ⚠️  ${proc}.py not found — skipping"
    fi
done

sleep 5

# ── FIX 5: Check registration results ────────────────────────────────────────
echo ""
echo "── Fix 5: Registration check ───────────────────────────────"
sleep 3
for proc in "quantum_mesh_consumer" "quantum_signal_bridge" "quantumarb_mesh_consumer" "projectx_quantum_advisor"; do
    LOG="data/logs/goose/${proc}.log"
    if [ -f "$LOG" ]; then
        LAST=$(tail -5 "$LOG" | tr '\n' ' ')
        if echo "$LAST" | grep -qi "registered\|success\|connected"; then
            echo "  ✅ $proc — registered"
        elif echo "$LAST" | grep -qi "400\|error\|fail"; then
            echo "  ❌ $proc — error: $LAST"
        else
            echo "  🔄 $proc — $LAST"
        fi
    fi
done

echo ""
echo "── Mesh agent roster ───────────────────────────────────────"
curl -s http://localhost:5555/agents 2>/dev/null | python3.10 -c "
import sys, json
try:
    agents = json.load(sys.stdin)
    if isinstance(agents, list):
        for a in agents:
            aid = a.get('agent_id', a.get('id', '?'))
            atype = a.get('agent_type', a.get('type', '?'))
            print(f'  • {aid} ({atype})')
    elif isinstance(agents, dict):
        for k, v in agents.items():
            print(f'  • {k}: {v}')
    else:
        print(f'  raw: {agents}')
except Exception as e:
    print(f'  broker unreachable: {e}')
" 2>/dev/null || echo "  broker unreachable"

echo ""
echo "════════════════════════════════════════════"
echo "  DEPLOY_FIXES complete"
echo "  To start a KLOUTBOT-context Goose session:"
echo "  bash $SIMP_DIR/scripts/bootstrap/launch_goose.sh"
echo "════════════════════════════════════════════"
