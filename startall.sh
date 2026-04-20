#!/bin/bash
# Canonical SIMP bring-up entrypoint.
# Starts the broker, dashboard, KTC, optional external services, and the
# quantum stack in a safe, idempotent order.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_ROOT="${ROOT_DIR}/logs/runtime"
PID_ROOT="${LOG_ROOT}/pids"
mkdir -p "${LOG_ROOT}" "${PID_ROOT}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SESSION_LOG="${LOG_ROOT}/startall_${TIMESTAMP}.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PYTHON_BIN="${ROOT_DIR}/venv_gate4/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(command -v python3.10 || true)"
fi
if [ -z "${PYTHON_BIN}" ]; then
    echo "python3.10 not found and ${ROOT_DIR}/venv_gate4/bin/python is unavailable" >&2
    exit 1
fi

SIMP_BROKER_URL="${SIMP_BROKER_URL:-http://127.0.0.1:5555}"
PROJECTX_GUARD_URL="${PROJECTX_GUARD_URL:-http://127.0.0.1:8771}"
DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8050}"
KTC_HOST="${KTC_HOST:-127.0.0.1}"
KTC_PORT="${KTC_PORT:-8765}"
QUANTUMARB_PHASE4_CONFIG="${QUANTUMARB_PHASE4_CONFIG:-config/phase4_microscopic.json}"

START_KTC=1
START_QUANTUM=1
START_EXTERNAL=1

usage() {
    cat <<EOF
Usage: bash startall.sh [options]

Options:
  --no-ktc         Skip KTC startup
  --no-quantum     Skip the quantum stack bootstrap
  --no-external    Skip ProjectX, BullBear, and Gemma external services
  --help           Show this help
EOF
}

for arg in "$@"; do
    case "$arg" in
        --no-ktc)
            START_KTC=0
            ;;
        --no-quantum)
            START_QUANTUM=0
            ;;
        --no-external)
            START_EXTERNAL=0
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            usage
            exit 1
            ;;
    esac
done

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "${SESSION_LOG}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN${NC} $1" | tee -a "${SESSION_LOG}"
}

fail() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR${NC} $1" | tee -a "${SESSION_LOG}"
    exit 1
}

http_ok() {
    local url="$1"
    curl -fsS "${url}" > /dev/null 2>&1
}

wait_for_http() {
    local url="$1"
    local timeout="$2"
    local elapsed=0

    while [ "${elapsed}" -lt "${timeout}" ]; do
        if http_ok "${url}"; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    return 1
}

process_running() {
    local pattern="$1"
    pgrep -f "${pattern}" > /dev/null 2>&1
}

start_http_service() {
    local slug="$1"
    local name="$2"
    local health_url="$3"
    local pattern="$4"
    local timeout="$5"
    local workdir="$6"
    shift 6

    if http_ok "${health_url}"; then
        log "✓ ${name} already healthy at ${health_url}"
        return 0
    fi

    if process_running "${pattern}"; then
        fail "${name} appears to be running but is not healthy at ${health_url}. Refusing to start a duplicate."
    fi

    local log_file="${LOG_ROOT}/${slug}.log"
    log "Starting ${name}..."
    (
        cd "${workdir}"
        nohup "$@" >> "${log_file}" 2>&1 &
        echo $! > "${PID_ROOT}/${slug}.pid"
    )

    if wait_for_http "${health_url}" "${timeout}"; then
        log "✓ ${name} is healthy"
        return 0
    fi

    fail "${name} failed health checks. Inspect ${log_file}"
}

start_background_service() {
    local slug="$1"
    local name="$2"
    local pattern="$3"
    local workdir="$4"
    shift 4

    if process_running "${pattern}"; then
        log "✓ ${name} already running"
        return 0
    fi

    local log_file="${LOG_ROOT}/${slug}.log"
    log "Starting ${name}..."
    (
        cd "${workdir}"
        nohup "$@" >> "${log_file}" 2>&1 &
        echo $! > "${PID_ROOT}/${slug}.pid"
    )
    sleep 2

    if process_running "${pattern}"; then
        log "✓ ${name} is running"
        return 0
    fi

    fail "${name} failed to stay running. Inspect ${log_file}"
}

start_optional_http_service() {
    local required_path="$1"
    local slug="$2"
    local name="$3"
    local health_url="$4"
    local pattern="$5"
    local timeout="$6"
    local workdir="$7"
    shift 7

    if [ ! -e "${required_path}" ]; then
        warn "Skipping ${name}; path not found: ${required_path}"
        return 0
    fi

    start_http_service "${slug}" "${name}" "${health_url}" "${pattern}" "${timeout}" "${workdir}" "$@"
}

bootstrap_quantum_stack() {
    local log_file="${LOG_ROOT}/quantum_stack.log"
    local required_processes=(
        "quantum_mesh_consumer.py"
        "quantum_signal_bridge.py"
        "quantum_advisory_broadcaster.py"
    )

    log "Bootstrapping quantum stack..."
    (
        cd "${ROOT_DIR}"
        env \
            SIMP_BROKER_URL="${SIMP_BROKER_URL}" \
            PROJECTX_GUARD_URL="${PROJECTX_GUARD_URL}" \
            bash "${ROOT_DIR}/start_quantum_goose.sh" --headless
    ) >> "${log_file}" 2>&1

    for pattern in "${required_processes[@]}"; do
        if process_running "${pattern}"; then
            log "✓ Quantum component running: ${pattern}"
        else
            fail "Quantum bootstrap completed without ${pattern}. Inspect ${log_file}"
        fi
    done
}

show_summary() {
    log ""
    log "Bring-up summary"
    log "  Broker:    ${SIMP_BROKER_URL}"
    log "  Dashboard: http://127.0.0.1:${DASHBOARD_PORT}/health"

    if [ "${START_KTC}" -eq 1 ]; then
        if http_ok "http://${KTC_HOST}:${KTC_PORT}/health"; then
            log "  KTC:       http://${KTC_HOST}:${KTC_PORT}/health"
        else
            warn "KTC was requested but is not healthy"
        fi
    fi

    if [ "${START_EXTERNAL}" -eq 1 ]; then
        if http_ok "${PROJECTX_GUARD_URL}/health"; then
            log "  ProjectX:  ${PROJECTX_GUARD_URL}/health"
        fi
        if http_ok "http://127.0.0.1:5559/health"; then
            log "  BullBear:  http://127.0.0.1:5559/health"
        fi
        if http_ok "http://127.0.0.1:8780/health"; then
            log "  Gemma:     http://127.0.0.1:8780/health"
        fi
    fi

    if process_running "simp/agents/quantumarb_agent_phase4.py"; then
        log "  QuantumArb: simp/agents/quantumarb_agent_phase4.py"
    else
        warn "QuantumArb Phase 4 agent not running"
    fi

    if [ "${START_QUANTUM}" -eq 1 ]; then
        local quantum_checks=(
            "quantum_mesh_consumer.py"
            "quantum_signal_bridge.py"
            "projectx_quantum_advisor.py"
            "quantumarb_file_consumer.py"
            "quantum_consensus.py"
            "brp_audit_consumer.py"
            "agent_coordination.py"
            "quantum_advisory_broadcaster.py"
        )
        for pattern in "${quantum_checks[@]}"; do
            if process_running "${pattern}"; then
                log "  Quantum:   ${pattern}"
            else
                warn "Quantum component not running: ${pattern}"
            fi
        done
    fi
}

log "Starting canonical SIMP bring-up"
log "Session log: ${SESSION_LOG}"
log "Python: ${PYTHON_BIN}"
log "Broker URL: ${SIMP_BROKER_URL}"

start_http_service \
    "broker" \
    "SIMP Broker" \
    "${SIMP_BROKER_URL}/health" \
    "simp.server.broker" \
    60 \
    "${ROOT_DIR}" \
    env PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" "${PYTHON_BIN}" -m simp.server.broker

start_http_service \
    "dashboard" \
    "Dashboard" \
    "http://127.0.0.1:${DASHBOARD_PORT}/health" \
    "dashboard/server.py" \
    45 \
    "${ROOT_DIR}" \
    env \
        PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
        SIMP_BROKER_URL="${SIMP_BROKER_URL}" \
        PROJECTX_GUARD_URL="${PROJECTX_GUARD_URL}" \
        DASHBOARD_HOST="${DASHBOARD_HOST}" \
        DASHBOARD_PORT="${DASHBOARD_PORT}" \
        "${PYTHON_BIN}" dashboard/server.py

if [ "${START_KTC}" -eq 1 ]; then
    start_http_service \
        "ktc" \
        "KTC" \
        "http://${KTC_HOST}:${KTC_PORT}/health" \
        "simp/organs/ktc/start_ktc.py" \
        45 \
        "${ROOT_DIR}" \
        env \
            PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
            "${PYTHON_BIN}" simp/organs/ktc/start_ktc.py \
            --host "${KTC_HOST}" \
            --port "${KTC_PORT}" \
            --simp-url "${SIMP_BROKER_URL}"
fi

start_background_service \
    "quantumarb_phase4" \
    "QuantumArb Phase 4" \
    "simp/agents/quantumarb_agent_phase4.py" \
    "${ROOT_DIR}" \
    env \
        PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
        SIMP_BROKER_URL="${SIMP_BROKER_URL}" \
        "${PYTHON_BIN}" simp/agents/quantumarb_agent_phase4.py \
        --config "${QUANTUMARB_PHASE4_CONFIG}"

if [ "${START_EXTERNAL}" -eq 1 ]; then
    start_optional_http_service \
        "/Users/kaseymarcelle/ProjectX/projectx_guard_server.py" \
        "projectx" \
        "ProjectX" \
        "${PROJECTX_GUARD_URL}/health" \
        "projectx_guard_server.py" \
        45 \
        "/Users/kaseymarcelle/ProjectX" \
        python3.10 /Users/kaseymarcelle/ProjectX/projectx_guard_server.py

    start_optional_http_service \
        "/Users/kaseymarcelle/bullbear/agents/bullbear_simp_agent.py" \
        "bullbear" \
        "BullBear Agent" \
        "http://127.0.0.1:5559/health" \
        "bullbear_simp_agent.py" \
        45 \
        "/Users/kaseymarcelle/bullbear" \
        python3.10 agents/bullbear_simp_agent.py --port 5559

    start_optional_http_service \
        "/Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py" \
        "gemma" \
        "KashClaw Gemma" \
        "http://127.0.0.1:8780/health" \
        "kashclaw_gemma_agent.py" \
        45 \
        "/Users/kaseymarcelle/bullbear" \
        python3.10 agents/kashclaw_gemma_agent.py --port 8780
fi

if [ "${START_QUANTUM}" -eq 1 ]; then
    bootstrap_quantum_stack
fi

show_summary
