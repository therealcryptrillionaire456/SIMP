#!/usr/bin/env bash
set -euo pipefail

# Enhanced mother goose watcher with better error handling and logging
SESSION="${1:-flock}"
OUTDIR="${2:-$HOME/goose-monitor}"
STATUS_FILE="$OUTDIR/status_board.txt"
INBOX_FILE="$OUTDIR/inbox_for_mother_goose.txt"
LOG_FILE="$OUTDIR/mother_goose_watch.log"

# Create directories and files
mkdir -p "$OUTDIR"
touch "$STATUS_FILE" "$INBOX_FILE" "$LOG_FILE"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "Starting Mother Goose Watcher"
log "Session: $SESSION"
log "Output directory: $OUTDIR"
log "Status file: $STATUS_FILE"
log "Inbox file: $INBOX_FILE"

# Check if tmux session exists
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    log "ERROR: Tmux session '$SESSION' not found!"
    exit 1
fi

log "Tmux session '$SESSION' found, starting monitoring loop..."

while true; do
    loop_start=$(date +%s)
    
    # Update status board header
    {
        echo "============================================================"
        echo "Mother Goose Status Board"
        echo "Session: $SESSION"
        echo "Updated: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "============================================================"
        echo ""
    } > "$STATUS_FILE"

    # Get list of windows in the session
    windows=()
    while IFS= read -r win; do
        windows+=("$win")
    done < <(tmux list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null || true)

    if [[ ${#windows[@]} -eq 0 ]]; then
        log "WARNING: No windows found in session '$SESSION'"
    else
        log "Found ${#windows[@]} windows: ${windows[*]}"
    fi

    # Process each window
    for win in "${windows[@]}"; do
        # Skip non-goose windows
        if [[ "$win" == "mother" ]] || [[ "$win" == "watcher" ]]; then
            continue
        fi

        # Get pane content
        pane_dump=""
        if ! pane_dump="$(tmux capture-pane -p -t "$SESSION:$win" -S -200 2>/dev/null)"; then
            echo "- $win: ERROR reading pane" >> "$STATUS_FILE"
            continue
        fi

        # Extract signals
        latest_signal="$(printf '%s\n' "$pane_dump" | grep -E '^(CHECK-IN|SHIFT COMPLETE|STANDING BY|ERROR)$' | tail -n 1 || true)"
        latest_worker="$(printf '%s\n' "$pane_dump" | grep -E '^Worker: ' | tail -n 1 | sed 's/^Worker: //' || true)"
        latest_phase="$(printf '%s\n' "$pane_dump" | grep -E '^Phase completed: ' | tail -n 1 | sed 's/^Phase completed: //' || true)"

        if [[ -z "${latest_signal:-}" ]]; then
            echo "- $win: NO SIGNAL" >> "$STATUS_FILE"
            continue
        fi

        # Update status board
        echo "- $win: $latest_signal | Worker: ${latest_worker:-unknown} | Phase: ${latest_phase:-n/a}" >> "$STATUS_FILE"

        # Check for new signals
        marker_file="$OUTDIR/${win}.last_marker"
        current_marker="${latest_signal}|${latest_worker}|${latest_phase}"
        last_marker=""
        
        if [[ -f "$marker_file" ]]; then
            last_marker="$(cat "$marker_file" 2>/dev/null || true)"
        fi

        if [[ "$current_marker" != "$last_marker" ]]; then
            log "NEW SIGNAL from $win: $latest_signal (Worker: ${latest_worker}, Phase: ${latest_phase})"
            
            # Append to inbox
            {
                echo "============================================================"
                echo "NEW SIGNAL from $win at $(date '+%Y-%m-%d %H:%M:%S')"
                echo "Signal: ${latest_signal}"
                echo "Worker: ${latest_worker:-unknown}"
                echo "Phase: ${latest_phase:-n/a}"
                echo "------------------------------------------------------------"
                printf '%s\n' "$pane_dump" | tail -n 60
                echo ""
            } >> "$INBOX_FILE"

            # Update marker
            printf '%s\n' "$current_marker" > "$marker_file"
        fi
    done

    # Calculate sleep time (8 seconds total per loop)
    loop_end=$(date +%s)
    loop_duration=$((loop_end - loop_start))
    sleep_time=$((8 - loop_duration))
    
    if [[ $sleep_time -lt 1 ]]; then
        sleep_time=1
    fi
    
    log "Loop completed in ${loop_duration}s, sleeping for ${sleep_time}s"
    sleep "$sleep_time"
done