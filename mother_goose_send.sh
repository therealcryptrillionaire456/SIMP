#!/usr/bin/env bash
set -euo pipefail

SESSION="${TMUX_SESSION:-flock}"
TARGET="${1:?usage: mother_goose_send.sh gooseN \"message\"}"
MESSAGE="${2:?usage: mother_goose_send.sh gooseN \"message\"}"

tmux list-windows -t "$SESSION" -F '#{window_name}' | grep -Fx "$TARGET" >/dev/null
tmux send-keys -t "$SESSION:$TARGET" "$MESSAGE" C-m
printf 'Sent to %s:%s\n' "$SESSION" "$TARGET"
