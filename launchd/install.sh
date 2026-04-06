#!/usr/bin/env bash
# install.sh — Install SIMP launchd services
set -e

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/bullbear/logs"

echo "=== Installing SIMP cowork_bridge service ==="
echo "Repo: $REPO_PATH"

mkdir -p "$LOG_DIR"

# Substitute paths in plist templates
for plist in "$REPO_PATH/launchd/"*.plist; do
    name=$(basename "$plist")
    target="$LAUNCHD_DIR/$name"

    sed \
        -e "s|REPLACE_WITH_REPO_PATH|$REPO_PATH|g" \
        -e "s|REPLACE_WITH_HOME|$HOME|g" \
        -e "s|/usr/bin/python3.10|$(which python3.10 2>/dev/null || which python3)|g" \
        "$plist" > "$target"

    # Unload first if already loaded
    launchctl unload "$target" 2>/dev/null || true
    launchctl load "$target"
    echo "  Loaded $(basename "$target" .plist)"
done

echo ""
echo "=== Done ==="
echo "Verify: curl http://127.0.0.1:8767/health"
echo "Logs:   tail -f $LOG_DIR/cowork_bridge.log"
