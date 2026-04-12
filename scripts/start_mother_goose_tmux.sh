#!/bin/bash
# SIMP Flock tmux startup script
# Creates a detached tmux session named 'mothergoose' with 4 windows
# Only creates the session if it doesn't already exist

SESSION_NAME="mothergoose"
SIMP_REPO_PATH="$HOME/Downloads/kashclaw (claude rebuild)/simp"
STRAY_GOOSE_PATH="$HOME/stray_goose"

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' already exists."
    echo "To attach: tmux attach -t $SESSION_NAME"
    exit 0
fi

# Create new detached session
echo "Creating tmux session '$SESSION_NAME'..."

# Start with first window (control) in SIMP repo
tmux new-session -d -s "$SESSION_NAME" -c "$SIMP_REPO_PATH" -n "control"

# Split control window into two panes
tmux split-window -h -t "$SESSION_NAME:control" -c "$SIMP_REPO_PATH"
tmux select-pane -t 0

# Create second window (geese)
tmux new-window -t "$SESSION_NAME" -c "$SIMP_REPO_PATH" -n "geese"
tmux split-window -h -t "$SESSION_NAME:geese" -c "$STRAY_GOOSE_PATH"
tmux select-pane -t 0

# Create third window (observability)
tmux new-window -t "$SESSION_NAME" -c "$SIMP_REPO_PATH" -n "observability"
tmux split-window -h -t "$SESSION_NAME:observability" -c "$SIMP_REPO_PATH"
tmux select-pane -t 0

# Create fourth window (scratch)
tmux new-window -t "$SESSION_NAME" -c "$SIMP_REPO_PATH" -n "scratch"

# Set initial pane titles
tmux send-keys -t "$SESSION_NAME:control.0" "echo 'Control Pane 1: SIMP repo shell'" C-m
tmux send-keys -t "$SESSION_NAME:control.1" "echo 'Control Pane 2: broker/server startup'" C-m
tmux send-keys -t "$SESSION_NAME:geese.0" "echo 'SIMP Goose: code/tests in SIMP repo'" C-m
tmux send-keys -t "$SESSION_NAME:geese.1" "echo 'Stray Goose: planning in ~/stray_goose'" C-m
tmux send-keys -t "$SESSION_NAME:observability.0" "echo 'Watchtower Pane 1: broker logs/health'" C-m
tmux send-keys -t "$SESSION_NAME:observability.1" "echo 'Watchtower Pane 2: proxy/TimesFM checks'" C-m
tmux send-keys -t "$SESSION_NAME:scratch.0" "echo 'Scratch pane: free shell for tests'" C-m

# Select control window as default
tmux select-window -t "$SESSION_NAME:control"

echo ""
echo "Session created: $SESSION_NAME"
echo ""
echo "Pane layout:"
echo "  Window 1: control"
echo "    - pane 0: SIMP repo shell"
echo "    - pane 1: broker/server startup"
echo "  Window 2: geese"
echo "    - pane 0: SIMP Goose (SIMP repo)"
echo "    - pane 1: Stray Goose (~/stray_goose)"
echo "  Window 3: observability"
echo "    - pane 0: broker logs/health checks"
echo "    - pane 1: proxy/TimesFM checks"
echo "  Window 4: scratch"
echo "    - pane 0: free shell for tests"
echo ""
echo "To attach: tmux attach -t $SESSION_NAME"
echo "To detach: Ctrl-b d"
echo ""
echo "Note: No startup commands are automatically run."
echo "Start broker/proxy manually after attaching."