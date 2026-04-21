#!/bin/bash

set -uo pipefail

PROJECTX_ROOT="${PROJECTX_ROOT:-/Users/kaseymarcelle/ProjectX}"
BROKER_URL="${SIMP_BROKER_URL:-http://127.0.0.1:5555}"
GUARD_URL="${PROJECTX_GUARD_URL:-http://127.0.0.1:8771}"
HEALTH_URL="${GUARD_URL}/health"
RESTART_DELAY="${PROJECTX_RESTART_DELAY:-3}"
HEALTH_GRACE_SECONDS="${PROJECTX_HEALTH_GRACE_SECONDS:-12}"
HEALTH_INTERVAL_SECONDS="${PROJECTX_HEALTH_INTERVAL_SECONDS:-4}"

child_pid=""
stopping=0

log() {
    printf '[projectx-supervisor] %s\n' "$*"
}

health_ok() {
    curl -fsS "${HEALTH_URL}" > /dev/null 2>&1
}

cleanup() {
    stopping=1
    log "received shutdown signal"
    if [ -n "${child_pid}" ] && kill -0 "${child_pid}" > /dev/null 2>&1; then
        kill "${child_pid}" > /dev/null 2>&1 || true
        wait "${child_pid}" || true
    fi
    exit 0
}

trap cleanup INT TERM HUP

start_child() {
    if [ ! -f "${PROJECTX_ROOT}/projectx_guard_server.py" ]; then
        log "ProjectX guard not found at ${PROJECTX_ROOT}/projectx_guard_server.py"
        sleep "${RESTART_DELAY}"
        return 1
    fi

    (
        cd "${PROJECTX_ROOT}"
        exec env SIMP_API_KEY="${SIMP_API_KEY:-}" python3.10 projectx_guard_server.py \
            --register \
            --simp-url "${BROKER_URL}"
    ) &
    child_pid=$!
    log "spawned child pid=${child_pid}"
    return 0
}

while true; do
    if ! start_child; then
        continue
    fi

    started_at="$(date +%s)"
    health_confirmed=0

    while kill -0 "${child_pid}" > /dev/null 2>&1; do
        now="$(date +%s)"
        elapsed=$((now - started_at))

        if health_ok; then
            health_confirmed=1
        elif [ "${health_confirmed}" -eq 1 ] || [ "${elapsed}" -ge "${HEALTH_GRACE_SECONDS}" ]; then
            log "health check failed after ${elapsed}s; restarting child pid=${child_pid}"
            kill "${child_pid}" > /dev/null 2>&1 || true
            wait "${child_pid}" || true
            break
        fi

        sleep "${HEALTH_INTERVAL_SECONDS}"
    done

    if [ "${stopping}" -eq 1 ]; then
        exit 0
    fi

    if wait "${child_pid}"; then
        exit_code=0
    else
        exit_code=$?
    fi

    log "child pid=${child_pid} exited with status ${exit_code}; restarting in ${RESTART_DELAY}s"
    child_pid=""
    sleep "${RESTART_DELAY}"
done
