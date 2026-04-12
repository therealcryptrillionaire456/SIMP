#!/bin/bash
# Manage Graphify Git hooks

HOOKS_DIR=".git/hooks"
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
    install)
        echo "Installing Graphify Git hooks..."
        "$TOOLS_DIR/git_hook_integration.sh"
        ;;
    uninstall)
        echo "Removing Graphify Git hooks..."
        rm -f "$HOOKS_DIR/pre-commit" "$HOOKS_DIR/post-commit" "$HOOKS_DIR/prepare-commit-msg"
        echo "✅ Graphify hooks removed"
        ;;
    status)
        echo "Graphify Git hooks status:"
        if [ -f "$HOOKS_DIR/pre-commit" ]; then
            echo "✅ pre-commit: Installed"
        else
            echo "❌ pre-commit: Not installed"
        fi
        if [ -f "$HOOKS_DIR/post-commit" ]; then
            echo "✅ post-commit: Installed"
        else
            echo "❌ post-commit: Not installed"
        fi
        if [ -f "$HOOKS_DIR/prepare-commit-msg" ]; then
            echo "✅ prepare-commit-msg: Installed"
        else
            echo "❌ prepare-commit-msg: Not installed"
        fi
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        exit 1
        ;;
esac
