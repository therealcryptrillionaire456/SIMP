#!/bin/bash
# startall_dryrun.sh — prints what startall.sh would launch without launching anything.
# Idempotent (read-only). Sources startall.sh's environment logic then prints the plan.
#
# Usage: bash scripts/startall_dryrun.sh [--hot] [--with-gate4] [--with-solana] ...
# All flags are forwarded to startall.sh's option parser but execution never happens.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══ SIMP Startup Dry Run ═══${NC}"
echo "Repo root: ${ROOT_DIR}"
echo ""

# Parse flags just like startall.sh
START_KTC=1
START_QUANTUM=1
START_EXTERNAL=1
START_GATE4=0
START_SOLANA=0
START_SECOND_BRAIN=1
HOT_MODE=0

for arg in "$@"; do
    case "$arg" in
        --hot) HOT_MODE=1; START_GATE4=1; START_SOLANA=1 ;;
        --with-gate4) START_GATE4=1 ;;
        --with-solana) START_SOLANA=1 ;;
        --no-ktc) START_KTC=0 ;;
        --no-quantum) START_QUANTUM=0 ;;
        --no-external) START_EXTERNAL=0 ;;
        --no-second-brain) START_SECOND_BRAIN=0 ;;
        *) echo -e "${YELLOW}Unknown option: $arg${NC}" ;;
    esac
done

echo -e "${GREEN}Flags:${NC}"
echo "  HOT_MODE=$HOT_MODE  START_KTC=$START_KTC  START_QUANTUM=$START_QUANTUM"
echo "  START_EXTERNAL=$START_EXTERNAL  START_GATE4=$START_GATE4"
echo "  START_SOLANA=$START_SOLANA  START_SECOND_BRAIN=$START_SECOND_BRAIN"
echo ""

# Check environment
PYTHON_BIN="${ROOT_DIR}/venv_gate4/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(command -v python3.10 || echo 'python3.10 (not found)')"
fi
echo -e "${GREEN}Python:${NC} ${PYTHON_BIN}"
echo ""

echo -e "${GREEN}═══ Launch Plan ═══${NC}"

echo ""
echo -e "${BLUE}[1] SIMP Broker${NC}"
echo "  Type:     HTTP service (health: http://127.0.0.1:5555/health)"
echo "  Pattern:  bin/start_server.py"
echo "  Command:  ${PYTHON_BIN} bin/start_server.py"
echo "  Hot path: YES — core message bus"

echo ""
echo -e "${BLUE}[2] Dashboard${NC}"
echo "  Type:     HTTP service (health: http://127.0.0.1:8050/health)"
echo "  Pattern:  dashboard/server.py"
echo "  Command:  ${PYTHON_BIN} dashboard/server.py"
echo "  Hot path: YES — operator console"

if [ "${START_KTC}" -eq 1 ]; then
    KTC_FILE="${ROOT_DIR}/simp/organs/ktc/start_ktc.py"
    if [ -f "${KTC_FILE}" ]; then
        echo ""
        echo -e "${BLUE}[3] KTC — Keep The Change${NC}"
        echo "  Type:     HTTP service (health: http://127.0.0.1:8765/health)"
        echo "  Pattern:  simp/organs/ktc/start_ktc.py"
        echo "  Command:  ${PYTHON_BIN} ${KTC_FILE} --host 127.0.0.1 --port 8765"
        echo "  Hot path: NO — separate webapp"
    else
        echo ""
        echo -e "${YELLOW}[3] KTC — SKIPPED (file not found: ${KTC_FILE})${NC}"
    fi
fi

echo ""
echo -e "${BLUE}[4] QuantumArb Phase 4 Agent${NC}"
echo "  Type:     Background process"
echo "  Pattern:  simp/agents/quantumarb_agent_phase4.py"
echo "  Command:  ${PYTHON_BIN} simp/agents/quantumarb_agent_phase4.py"
echo "  Hot path: YES — signal consumer"

GATE4_FILE="${ROOT_DIR}/gate4_inbox_consumer.py"
if [ "${START_GATE4}" -eq 1 ]; then
    if [ -f "${GATE4_FILE}" ]; then
        echo ""
        echo -e "${BLUE}[5] Gate4 Live Consumer${NC}"
        echo "  Type:     Background process"
        echo "  Pattern:  gate4_inbox_consumer.py"
        echo "  Command:  ${PYTHON_BIN} gate4_inbox_consumer.py"
        echo "  Hot path: YES — trade execution"
    else
        echo ""
        echo -e "${YELLOW}[5] Gate4 — SKIPPED (file not found: ${GATE4_FILE})${NC}"
    fi
fi

if [ "${START_EXTERNAL}" -eq 1 ]; then
    BB_FILE="/Users/kaseymarcelle/bullbear/agents/bullbear_simp_agent.py"
    if [ -f "${BB_FILE}" ]; then
        echo ""
        echo -e "${BLUE}[6] BullBear Agent${NC}"
        echo "  Type:     HTTP service (health: http://127.0.0.1:5559/health)"
        echo "  Pattern:  bullbear_simp_agent.py"
        echo "  Command:  python3.10 ${BB_FILE} --port 5559"
        echo "  Hot path: DEPUTY — prediction signal generator"
    else
        echo ""
        echo -e "${YELLOW}[6] BullBear — SKIPPED (file not found${NC}"
    fi

    GEMMA_FILE="/Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py"
    if [ -f "${GEMMA_FILE}" ]; then
        echo ""
        echo -e "${BLUE}[7] KashClaw Gemma${NC}"
        echo "  Type:     HTTP service (health: http://127.0.0.1:8780/health)"
        echo "  Pattern:  kashclaw_gemma_agent.py"
        echo "  Command:  python3.10 ${GEMMA_FILE} --port 8780"
        echo "  Hot path: DEPUTY — local LLM"
    fi

    PROJECTX_FILE="/Users/kaseymarcelle/ProjectX/projectx_guard_server.py"
    if [ -f "${PROJECTX_FILE}" ]; then
        echo ""
        echo -e "${BLUE}[8] ProjectX Guard${NC}"
        echo "  Type:     HTTP service (health: http://127.0.0.1:8771/health)"
        echo "  Pattern:  projectx_supervisor.sh"
        echo "  Command:  bash scripts/projectx_supervisor.sh"
        echo "  Hot path: YES — maintenance kernel"
    else
        echo ""
        echo -e "${YELLOW}[8] ProjectX — SKIPPED (file not found${NC}"
    fi
fi

if [ "${START_SOLANA}" -eq 1 ]; then
    SOLANA_FILE="${ROOT_DIR}/scripts/solana_seeker_integration.py"
    if [ -f "${SOLANA_FILE}" ]; then
        echo ""
        echo -e "${BLUE}[9] Solana Seeker${NC}"
        echo "  Type:     Background daemon"
        echo "  Pattern:  scripts/solana_seeker_integration.py"
        echo "  Command:  ${PYTHON_BIN} ${SOLANA_FILE} --daemon --dry-run"
        echo "  Hot path: NO — separate blockchain integration"
    fi
fi

echo ""
echo -e "${BLUE}[10] Closed-Loop Scheduler${NC}"
SCHED_FILE="${ROOT_DIR}/scripts/closed_loop_scheduler.py"
if [ -f "${SCHED_FILE}" ]; then
    echo "  Type:     Background scheduler"
    echo "  Pattern:  scripts/closed_loop_scheduler.py"
    echo "  Command:  ${PYTHON_BIN} ${SCHED_FILE} --interval 900"
    echo "  Hot path: DEPUTY — periodic learning cycles"
else
    echo -e "${YELLOW}  SKIPPED (file not found)${NC}"
fi

if [ "${START_QUANTUM}" -eq 1 ]; then
    echo ""
    echo -e "${BLUE}[11] Quantum Stack (via start_quantum_goose.sh --headless)${NC}"
    echo "  Type:     Bootstrap script"
    echo "  Command:  bash start_quantum_goose.sh --headless"
    echo "  Requires: quantum_mesh_consumer.py, quantum_signal_bridge.py, quantum_advisory_broadcaster.py"
    echo "  Hot path: YES (signal_bridge + mesh_consumer) / DEPUTY (others)"
fi

if [ "${START_SECOND_BRAIN}" -eq 1 ]; then
    echo ""
    echo -e "${BLUE}[12] Obsidian State Watcher${NC}"
    echo "  Type:     Background watcher"
    echo "  Pattern:  scripts/obsidian_state_watch.py"
    echo "  Command:  bash scripts/bootstrap/launch_second_brain.sh"
    echo "  Hot path: NO — docs integration"
fi

echo ""
echo -e "${GREEN}═══ Summary ═══${NC}"
echo "Total processes in plan: $(
    count=$((2))  # broker + dashboard
    [ "${START_KTC}" -eq 1 ] && [ -f "${ROOT_DIR}/simp/organs/ktc/start_ktc.py" ] && count=$((count+1))
    count=$((count+1))  # quantumarb
    [ "${START_GATE4}" -eq 1 ] && [ -f "${GATE4_FILE}" ] && count=$((count+1))
    [ "${START_EXTERNAL}" -eq 1 ] && count=$((count+3))  # bullbear+gemma+projectx
    [ "${START_SOLANA}" -eq 1 ] && count=$((count+1))
    [ -f "${SCHED_FILE}" ] && count=$((count+2))  # scheduler + quantum stack
    [ "${START_SECOND_BRAIN}" -eq 1 ] && count=$((count+1))
    echo $count
)"
echo "Dry run complete. No processes were started."
