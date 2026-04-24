#!/usr/bin/env bash
# Launch the Obsidian/Graphify watcher for continuous second-brain updates.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/venv_gate4/bin/python"

if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(command -v python3.10 || command -v python3)"
fi

if [ -z "${PYTHON_BIN}" ]; then
    echo "No compatible Python interpreter found" >&2
    exit 1
fi

export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

exec "${PYTHON_BIN}" "${ROOT_DIR}/scripts/obsidian_state_watch.py" \
    --interval "${OBSIDIAN_STATE_WATCH_INTERVAL:-5}" \
    --settle-seconds "${OBSIDIAN_STATE_WATCH_SETTLE_SECONDS:-4}" \
    "$@"
