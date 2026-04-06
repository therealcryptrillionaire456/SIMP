#!/usr/bin/env bash
# install.sh — Install SIMP launchd services
set -e

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/bullbear/logs"

PYTHON="$(which python3.10 2>/dev/null || which python3)"

echo "=== Installing SIMP launchd services ==="
echo "Repo:   $REPO_PATH"
echo "Python: $PYTHON"

mkdir -p "$LOG_DIR"

# Substitute paths in plist templates
for plist in "$REPO_PATH/launchd/"*.plist; do
    name=$(basename "$plist")
    target="$LAUNCHD_DIR/$name"

    sed \
        -e "s|REPLACE_WITH_REPO_PATH|$REPO_PATH|g" \
        -e "s|REPLACE_WITH_HOME|$HOME|g" \
        -e "s|REPLACE_PYTHON|$PYTHON|g" \
        -e "s|/usr/bin/python3.10|$PYTHON|g" \
        "$plist" > "$target"

    # Unload first if already loaded
    launchctl unload "$target" 2>/dev/null || true
    launchctl load "$target"
    echo "  Loaded $(basename "$target" .plist)"
done

echo ""
echo "=== Done ==="
echo "Verify broker:  curl http://127.0.0.1:5555/health"
echo "Verify cowork:  curl http://127.0.0.1:8767/health"
echo "Logs:           tail -f $LOG_DIR/simp_broker.log"
echo "                tail -f $LOG_DIR/cowork_bridge.log"
