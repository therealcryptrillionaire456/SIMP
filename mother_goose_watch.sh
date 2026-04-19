#!/usr/bin/env bash
set -euo pipefail

SESSION="${1:-flock}"
OUTDIR="${2:-$HOME/goose-monitor}"
STATUS_FILE="$OUTDIR/status_board.txt"
INBOX_FILE="$OUTDIR/inbox_for_mother_goose.txt"

mkdir -p "$OUTDIR"
touch "$STATUS_FILE" "$INBOX_FILE"

while true; do
  {
    echo "Mother Goose Status Board"
    echo "Session: $SESSION"
    echo "Updated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo
  } > "$STATUS_FILE"

  tmux list-windows -t "$SESSION" -F '#{window_name}' | while read -r win; do
    [[ "$win" == "watcher" ]] && continue

    pane_dump="$(tmux capture-pane -p -t "$SESSION:$win" -S -200 2>/dev/null || true)"
    latest_signal="$(printf '%s\n' "$pane_dump" | grep -E '^(CHECK-IN|SHIFT COMPLETE|STANDING BY|ERROR)$' | tail -n 1 || true)"
    latest_worker="$(printf '%s\n' "$pane_dump" | grep -E '^Worker: ' | tail -n 1 | sed 's/^Worker: //')"
    latest_phase="$(printf '%s\n' "$pane_dump" | grep -E '^Phase completed: ' | tail -n 1 | sed 's/^Phase completed: //')"

    if [[ -z "${latest_signal:-}" ]]; then
      echo "- $win: NO SIGNAL" >> "$STATUS_FILE"
      continue
    fi

    echo "- $win: $latest_signal | ${latest_worker:-unknown} | ${latest_phase:-n/a}" >> "$STATUS_FILE"

    marker_file="$OUTDIR/${win}.last_marker"
    current_marker="${latest_signal}|${latest_worker}|${latest_phase}"
    last_marker=""
    [[ -f "$marker_file" ]] && last_marker="$(cat "$marker_file")"

    if [[ "$current_marker" != "$last_marker" ]]; then
      {
        echo "============================================================"
        echo "NEW SIGNAL from $win at $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Signal: ${latest_signal}"
        echo "Worker: ${latest_worker:-unknown}"
        echo "Phase: ${latest_phase:-n/a}"
        echo "------------------------------------------------------------"
        printf '%s\n' "$pane_dump" | tail -n 60
        echo
      } >> "$INBOX_FILE"

      printf '%s\n' "$current_marker" > "$marker_file"
    fi
  done

  sleep 8
done
