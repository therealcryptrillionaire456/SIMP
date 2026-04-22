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
QUANTUMARB_HOT_CONFIG="${QUANTUMARB_HOT_CONFIG:-config/live_phase2_sol_microscopic.json}"
SOLANA_SEEKER_CONFIG="${SOLANA_SEEKER_CONFIG:-config/solana_seeker_config.json}"
CLOSED_LOOP_INTERVAL="${CLOSED_LOOP_INTERVAL:-900}"

BOOT_SIMP_BROKER_URL="${SIMP_BROKER_URL}"
BOOT_PROJECTX_GUARD_URL="${PROJECTX_GUARD_URL}"
BOOT_DASHBOARD_HOST="${DASHBOARD_HOST}"
BOOT_DASHBOARD_PORT="${DASHBOARD_PORT}"
BOOT_KTC_HOST="${KTC_HOST}"
BOOT_KTC_PORT="${KTC_PORT}"

START_KTC=1
START_QUANTUM=1
START_EXTERNAL=1
START_GATE4=0
START_SOLANA=0
HOT_MODE=0
RESET_GATE4_STATE=0

usage() {
    cat <<EOF
Usage: bash startall.sh [options]

Options:
  --hot            Arm live-mode services and load live trading env files
  --with-gate4     Start the Gate4 live Coinbase consumer
  --with-solana    Start the Solana Seeker daemon
  --no-ktc         Skip KTC startup
  --no-quantum     Skip the quantum stack bootstrap
  --no-external    Skip ProjectX, BullBear, and Gemma external services
  --reset-gate4-state
                   Archive Gate4 breaker state before startup
  --help           Show this help
EOF
}

for arg in "$@"; do
    case "$arg" in
        --hot)
            HOT_MODE=1
            START_GATE4=1
            START_SOLANA=1
            ;;
        --with-gate4)
            START_GATE4=1
            ;;
        --with-solana)
            START_SOLANA=1
            ;;
        --no-ktc)
            START_KTC=0
            ;;
        --no-quantum)
            START_QUANTUM=0
            ;;
        --no-external)
            START_EXTERNAL=0
            ;;
        --reset-gate4-state)
            RESET_GATE4_STATE=1
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

stabilize_http_service() {
    local url="$1"
    local pattern="$2"
    local timeout="$3"
    local interval="${4:-2}"
    local elapsed=0

    while [ "${elapsed}" -lt "${timeout}" ]; do
        if ! http_ok "${url}"; then
            return 1
        fi
        if [ -n "${pattern}" ] && ! process_running "${pattern}"; then
            return 1
        fi
        sleep "${interval}"
        elapsed=$((elapsed + interval))
    done

    return 0
}

process_running() {
    local pattern="$1"
    pgrep -f "${pattern}" > /dev/null 2>&1
}

stop_matching_processes() {
    local pattern="$1"
    local name="$2"

    if ! process_running "${pattern}"; then
        return 0
    fi

    log "Stopping ${name}..."
    pkill -f "${pattern}" > /dev/null 2>&1 || true

    local elapsed=0
    while process_running "${pattern}" && [ "${elapsed}" -lt 20 ]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done

    if process_running "${pattern}"; then
        fail "${name} did not stop cleanly"
    fi
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
        if stabilize_http_service "${health_url}" "${pattern}" 6 2; then
            log "✓ ${name} already healthy at ${health_url}"
            return 0
        fi
        warn "${name} answered health checks briefly but did not remain stable; restarting"
        stop_matching_processes "${pattern}" "${name}"
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

    if wait_for_http "${health_url}" "${timeout}" && stabilize_http_service "${health_url}" "${pattern}" 6 2; then
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

load_env_file() {
    local env_file="$1"
    local label="$2"

    if [ ! -f "${env_file}" ]; then
        warn "Skipping ${label} env file; not found: ${env_file}"
        return 0
    fi

    log "Loading ${label} environment from ${env_file}"
    while IFS='=' read -r key value || [ -n "${key:-}" ]; do
        if [[ "${key:-}" =~ ^[[:space:]]*# ]] || [[ -z "${key:-}" ]]; then
            continue
        fi
        key="$(printf '%s' "${key}" | xargs)"
        value="$(printf '%s' "${value:-}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        export "${key}=${value}"
    done < "${env_file}"
}

projectx_registered() {
    local url="${SIMP_BROKER_URL}/agents/projectx_native"
    if [ -n "${SIMP_API_KEY:-}" ]; then
        curl -fsS -H "Authorization: Bearer ${SIMP_API_KEY}" -H "X-API-Key: ${SIMP_API_KEY}" "${url}" 2>/dev/null \
            | grep -q '"agent_id"[[:space:]]*:[[:space:]]*"projectx_native"'
    else
        curl -fsS "${url}" 2>/dev/null | grep -q '"agent_id"[[:space:]]*:[[:space:]]*"projectx_native"'
    fi
}

projectx_self_registered() {
    curl -fsS "${PROJECTX_GUARD_URL}/health" 2>/dev/null \
        | grep -q '"registered"[[:space:]]*:[[:space:]]*true'
}

start_projectx_guard() {
    start_optional_http_service \
        "/Users/kaseymarcelle/ProjectX/projectx_guard_server.py" \
        "projectx" \
        "ProjectX" \
        "${PROJECTX_GUARD_URL}/health" \
        "projectx_supervisor.sh" \
        45 \
        "${ROOT_DIR}" \
        env \
            SIMP_API_KEY="${SIMP_API_KEY:-}" \
            SIMP_BROKER_URL="${SIMP_BROKER_URL}" \
            PROJECTX_GUARD_URL="${PROJECTX_GUARD_URL}" \
            bash "${ROOT_DIR}/scripts/projectx_supervisor.sh"
}

ensure_projectx_registered() {
    if ! http_ok "${PROJECTX_GUARD_URL}/health"; then
        fail "ProjectX health endpoint is unavailable; cannot verify registration"
    fi

    if projectx_registered; then
        log "✓ ProjectX registered with broker"
        return 0
    fi

    log "ProjectX is healthy but not broker-registered; reconciling registration..."

    local payload
    payload="$(cat <<EOF
{
  "agent_id": "projectx_native",
  "agent_type": "native_maintenance",
  "endpoint": "http://127.0.0.1:8771",
  "metadata": {
    "name": "projectx_native",
    "version": "0.1.0",
    "description": "ProjectX native bounded maintenance and remediation agent.",
    "dry_run_safe": true,
    "capabilities": [
      "native_agent_repo_scan",
      "native_agent_health_check",
      "native_agent_code_maintenance",
      "native_agent_provider_repair",
      "native_agent_task_audit",
      "native_agent_security_audit",
      "projectx_query"
    ]
  }
}
EOF
)"

    local -a curl_args
    curl_args=(-fsS -X POST "${SIMP_BROKER_URL}/agents/register" -H "Content-Type: application/json" -d "${payload}")
    if [ -n "${SIMP_API_KEY:-}" ]; then
        curl_args+=(-H "Authorization: Bearer ${SIMP_API_KEY}" -H "X-API-Key: ${SIMP_API_KEY}")
    fi

    if ! curl "${curl_args[@]}" > /dev/null 2>&1; then
        fail "ProjectX registration POST failed"
    fi

    sleep 2
    if projectx_registered; then
        log "✓ ProjectX registration reconciled"
        return 0
    fi

    fail "ProjectX remained unregistered after reconciliation"
}

reconcile_projectx_guard() {
    if [ ! -e "/Users/kaseymarcelle/ProjectX/projectx_guard_server.py" ]; then
        warn "Skipping ProjectX; path not found: /Users/kaseymarcelle/ProjectX/projectx_guard_server.py"
        return 0
    fi

    if http_ok "${PROJECTX_GUARD_URL}/health" && projectx_registered && ! projectx_self_registered; then
        warn "ProjectX broker registration is healthy but /health reports registered=false; forcing clean restart"
        stop_matching_processes "projectx_supervisor.sh|projectx_guard_server.py" "ProjectX"
    fi

    start_projectx_guard
    ensure_projectx_registered

    if ! projectx_self_registered; then
        warn "ProjectX still reports registered=false after broker reconciliation; restarting once more"
        stop_matching_processes "projectx_supervisor.sh|projectx_guard_server.py" "ProjectX"
        start_projectx_guard
        ensure_projectx_registered
    fi

    if projectx_self_registered; then
        log "✓ ProjectX self-registration healthy"
    else
        warn "ProjectX broker registration is healthy but /health still reports registered=false"
    fi
}

gate4_env_ready() {
    env_value_ready "${COINBASE_API_KEY_NAME:-}" && env_value_ready "${COINBASE_API_PRIVATE_KEY:-}"
}

quantumarb_live_env_ready() {
    (
        env_value_ready "${COINBASE_API_KEY:-}" &&
        env_value_ready "${COINBASE_API_SECRET:-}" &&
        env_value_ready "${COINBASE_API_PASSPHRASE:-}"
    ) || (
        env_value_ready "${COINBASE_PRODUCTION_API_KEY:-}" &&
        env_value_ready "${COINBASE_PRODUCTION_API_SECRET:-}" &&
        env_value_ready "${COINBASE_PRODUCTION_PASSPHRASE:-}"
    )
}

solana_env_ready() {
    env_value_ready "${SOLANA_SEEKER_API_KEY:-}" && env_value_ready "${SOLANA_WALLET_ADDRESS:-}"
}

env_value_ready() {
    local value="$1"
    [ -n "${value}" ] || return 1
    [[ "${value}" != your_* ]] || return 1
    [[ "${value}" != YOUR_* ]] || return 1
    [[ "${value}" != placeholder* ]] || return 1
    [[ "${value}" != PLACEHOLDER* ]] || return 1
    return 0
}

reset_gate4_state_if_requested() {
    local state_file="${ROOT_DIR}/data/gate4_consumer_state.json"
    if [ "${RESET_GATE4_STATE}" -ne 1 ] || [ ! -f "${state_file}" ]; then
        return 0
    fi

    local archived="${state_file}.bak.${TIMESTAMP}"
    mv "${state_file}" "${archived}"
    log "Archived Gate4 state to ${archived}"
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
    if [ "${HOT_MODE}" -eq 1 ]; then
        log "  Mode:      HOT"
    fi

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

    if [ "${START_GATE4}" -eq 1 ]; then
        if process_running "gate4_inbox_consumer.py"; then
            log "  Gate4:     gate4_inbox_consumer.py"
        else
            warn "Gate4 consumer requested but not running"
        fi
    fi

    if [ "${START_SOLANA}" -eq 1 ]; then
        if process_running "scripts/solana_seeker_integration.py"; then
            log "  Solana:    scripts/solana_seeker_integration.py"
        else
            warn "Solana Seeker requested but not running"
        fi
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
            "scripts/closed_loop_scheduler.py"
        )
        for pattern in "${quantum_checks[@]}"; do
            if process_running "${pattern}"; then
                log "  Quantum:   ${pattern}"
            else
                warn "Quantum component not running: ${pattern}"
            fi
        done
    fi

    log "  Snapshot:  ${PYTHON_BIN} scripts/runtime_snapshot.py --format markdown"
    if [ "${HOT_MODE}" -eq 1 ]; then
        log "  Verify:    ${PYTHON_BIN} scripts/verify_revenue_path.py"
        log "  Inject:    ${PYTHON_BIN} scripts/inject_quantum_signal.py --asset BTC-USD --side sell --usd 1.00"
    fi
}

log "Starting canonical SIMP bring-up"
log "Session log: ${SESSION_LOG}"
log "Python: ${PYTHON_BIN}"
log "Broker URL: ${SIMP_BROKER_URL}"

if [ "${HOT_MODE}" -eq 1 ]; then
    load_env_file "${ROOT_DIR}/.env.multi_exchange" "multi-exchange"
    load_env_file "${ROOT_DIR}/.env.solana_seeker" "solana"

    export SIMP_BROKER_URL="${BOOT_SIMP_BROKER_URL}"
    export PROJECTX_GUARD_URL="${BOOT_PROJECTX_GUARD_URL}"
    export DASHBOARD_HOST="${BOOT_DASHBOARD_HOST}"
    export DASHBOARD_PORT="${BOOT_DASHBOARD_PORT}"
    export KTC_HOST="${BOOT_KTC_HOST}"
    export KTC_PORT="${BOOT_KTC_PORT}"
    SIMP_BROKER_URL="${BOOT_SIMP_BROKER_URL}"
    PROJECTX_GUARD_URL="${BOOT_PROJECTX_GUARD_URL}"
    DASHBOARD_HOST="${BOOT_DASHBOARD_HOST}"
    DASHBOARD_PORT="${BOOT_DASHBOARD_PORT}"
    KTC_HOST="${BOOT_KTC_HOST}"
    KTC_PORT="${BOOT_KTC_PORT}"

    if gate4_env_ready; then
        log "Hot mode: Gate4 live Coinbase credentials detected"
    else
        warn "Hot mode: Gate4 Coinbase credentials not detected"
    fi

    if quantumarb_live_env_ready; then
        log "Hot mode: QuantumArb live Coinbase credentials detected"
        export QUANTUMARB_PHASE4_CONFIG="${QUANTUMARB_HOT_CONFIG}"
        export QUANTUMARB_ALLOW_LIVE_TRADING="${QUANTUMARB_ALLOW_LIVE_TRADING:-true}"
    else
        warn "Hot mode: QuantumArb live credentials not detected; Gate4 will be the live Coinbase path"
        export QUANTUMARB_ALLOW_LIVE_TRADING="false"
    fi

    if ! gate4_env_ready && ! quantumarb_live_env_ready; then
        fail "Hot mode requested but no live Coinbase credentials were loaded"
    fi

    if [ "${START_SOLANA}" -eq 1 ] && ! solana_env_ready; then
        warn "Hot mode: Solana credentials not detected; Solana Seeker will be skipped"
        START_SOLANA=0
    elif [ "${START_SOLANA}" -eq 1 ]; then
        if [ "${SOLANA_SEEKER_LIVE:-false}" = "true" ]; then
            log "Hot mode: Solana Seeker live mode armed"
        else
            warn "Hot mode: Solana Seeker will start in dry-run mode unless SOLANA_SEEKER_LIVE=true"
        fi
    fi

    if [ -f "${ROOT_DIR}/data/gate4_consumer_state.json" ] && [ "${RESET_GATE4_STATE}" -ne 1 ]; then
        warn "Hot mode: existing Gate4 breaker state may still block signals; use --reset-gate4-state to archive it"
    fi
fi

reset_gate4_state_if_requested

start_http_service \
    "broker" \
    "SIMP Broker" \
    "${SIMP_BROKER_URL}/health" \
    "bin/start_server.py" \
    60 \
    "${ROOT_DIR}" \
    env PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" "${PYTHON_BIN}" bin/start_server.py

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
        QUANTUMARB_ALLOW_LIVE_TRADING="${QUANTUMARB_ALLOW_LIVE_TRADING:-false}" \
        "${PYTHON_BIN}" simp/agents/quantumarb_agent_phase4.py \
        --config "${QUANTUMARB_PHASE4_CONFIG}"

if [ "${START_GATE4}" -eq 1 ]; then
    start_background_service \
        "gate4_consumer" \
        "Gate4 Live Consumer" \
        "gate4_inbox_consumer.py" \
        "${ROOT_DIR}" \
        env \
            PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
            "${PYTHON_BIN}" gate4_inbox_consumer.py
fi

if [ "${START_EXTERNAL}" -eq 1 ]; then
    reconcile_projectx_guard

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

if [ "${START_SOLANA}" -eq 1 ]; then
    solana_mode_arg="--dry-run"
    if [ "${SOLANA_SEEKER_LIVE:-false}" = "true" ]; then
        solana_mode_arg="--live"
    fi
    start_background_service \
        "solana_seeker" \
        "Solana Seeker" \
        "scripts/solana_seeker_integration.py" \
        "${ROOT_DIR}" \
        env \
            PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
            "${PYTHON_BIN}" scripts/solana_seeker_integration.py --daemon "${solana_mode_arg}" --config "${SOLANA_SEEKER_CONFIG}"
fi

start_background_service \
    "closed_loop_scheduler" \
    "Closed-Loop Scheduler" \
    "scripts/closed_loop_scheduler.py" \
    "${ROOT_DIR}" \
    env \
        PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
        "${PYTHON_BIN}" scripts/closed_loop_scheduler.py --interval "${CLOSED_LOOP_INTERVAL}"

if [ "${START_QUANTUM}" -eq 1 ]; then
    bootstrap_quantum_stack
fi

show_summary
