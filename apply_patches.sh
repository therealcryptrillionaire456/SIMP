#!/usr/bin/env bash
# apply_patches.sh
# ─────────────────
# Copies all SIMP v0.2 security-hardened files into ~/code/SIMP.
# Run from anywhere; requires ~/code/SIMP to exist.
#
# Usage:
#   chmod +x apply_patches.sh
#   ./apply_patches.sh
#
# What it does:
#   1. Backs up the four core source files to .bak
#   2. Copies new versions into place
#   3. Copies new modules (config, models, audit, security)
#   4. Copies new test suite, SECURITY.md, .env.example
#   5. Verifies Python can import the new modules
#   6. Prints suggested commit commands

set -euo pipefail

REPO="$HOME/code/SIMP"
SRC="$(cd "$(dirname "$0")" && pwd)"   # directory of this script

echo "╔══════════════════════════════════════════════════╗"
echo "║  SIMP v0.2 Security Patch Applicator             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Source: $SRC"
echo "Target: $REPO"
echo ""

# ── pre-flight ────────────────────────────────────────────────────────────────
if [ ! -d "$REPO" ]; then
    echo "❌  $REPO not found. Clone the repo first:"
    echo "    git clone https://github.com/therealcryptrillionaire456/SIMP.git ~/code/SIMP"
    exit 1
fi

cd "$REPO"

echo "── Step 1: Back up original files ───────────────────"
for f in \
    simp/server/broker.py \
    simp/server/http_server.py \
    simp/server/agent_client.py \
    simp/server/agent_manager.py
do
    if [ -f "$f" ]; then
        cp "$f" "${f}.bak"
        echo "  backed up → ${f}.bak"
    fi
done

echo ""
echo "── Step 2: Copy hardened core files ─────────────────"
for f in \
    simp/server/broker.py \
    simp/server/http_server.py \
    simp/server/agent_client.py \
    simp/server/agent_manager.py
do
    if [ -f "$SRC/$f" ]; then
        cp "$SRC/$f" "$REPO/$f"
        echo "  ✅  $f"
    else
        echo "  ⚠️  $SRC/$f not found — skipping"
    fi
done

echo ""
echo "── Step 3: Copy new modules ─────────────────────────"
mkdir -p config simp/models simp/audit simp/security

for f in \
    config/__init__.py \
    config/config.py \
    simp/models/__init__.py \
    simp/models/intent_schema.py \
    simp/audit/__init__.py \
    simp/audit/audit_logger.py \
    simp/security/__init__.py \
    simp/security/log_utils.py
do
    if [ -f "$SRC/$f" ]; then
        cp "$SRC/$f" "$REPO/$f"
        echo "  ✅  $f"
    fi
done

# Create __init__.py files for new packages if missing
for pkg in config simp/models simp/audit simp/security; do
    touch "$REPO/$pkg/__init__.py" 2>/dev/null || true
done

echo ""
echo "── Step 4: Copy tests ───────────────────────────────"
mkdir -p tests/security
for f in \
    tests/__init__.py \
    tests/security/__init__.py \
    tests/security/test_intent_schema.py \
    tests/security/test_audit_logger.py \
    tests/security/test_log_utils.py \
    tests/security/test_agent_manager_security.py \
    tests/security/test_rate_limiter.py
do
    if [ -f "$SRC/$f" ]; then
        cp "$SRC/$f" "$REPO/$f"
        echo "  ✅  $f"
    fi
done

echo ""
echo "── Step 5: Copy docs & config template ─────────────"
for f in SECURITY.md .env.example; do
    if [ -f "$SRC/$f" ]; then
        cp "$SRC/$f" "$REPO/$f"
        echo "  ✅  $f"
    fi
done

echo ""
echo "── Step 6: Create var/ directory ────────────────────"
mkdir -p var
echo "  ✅  var/ (for SQLite DBs)"

echo ""
echo "── Step 7: Smoke-test imports ───────────────────────"
cd "$REPO"
python3 -c "
import sys
sys.path.insert(0, '.')
ok = 0; fail = 0
for mod in [
    'simp.security.log_utils',
    'simp.audit.audit_logger',
]:
    try:
        __import__(mod)
        print(f'  ✅  import {mod}')
        ok += 1
    except Exception as e:
        print(f'  ❌  import {mod}: {e}')
        fail += 1
print(f'  {ok} OK, {fail} failed')
"

echo ""
echo "── Step 8: Run tests (if pytest is installed) ───────"
if python3 -m pytest --version &>/dev/null; then
    python3 -m pytest tests/security/ -v --tb=short 2>&1 | tail -20
else
    echo "  pytest not installed — skipping (install with: pip install pytest)"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Patch applied! Suggested git workflow:          ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  git add config/ simp/models/ simp/audit/        ║"
echo "║         simp/security/ tests/security/           ║"
echo "║         simp/server/broker.py                    ║"
echo "║         simp/server/http_server.py               ║"
echo "║         simp/server/agent_client.py              ║"
echo "║         simp/server/agent_manager.py             ║"
echo "║         SECURITY.md .env.example                 ║"
echo "║                                                  ║"
echo "║  # Week-1 commit:                               ║"
echo "║  git commit -m 'fix: input validation, rate     ║"
echo "║    limiting, bare exceptions, hardcoded paths'  ║"
echo "║                                                  ║"
echo "║  # Week-2 commit:                               ║"
echo "║  git commit -m 'feat: signature verification,   ║"
echo "║    audit logging, TTL cleanup, thread safety'   ║"
echo "║                                                  ║"
echo "║  # Week-3 commit:                               ║"
echo "║  git commit -m 'feat: TLS, health checks,       ║"
echo "║    tracing, config management, log obfuscation' ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
