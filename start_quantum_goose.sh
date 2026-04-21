#!/bin/bash
# Startup script for full quantum stack as persistent background services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Full Quantum Stack Startup           ${NC}"
echo -e "${BLUE}  Continuous portfolio optimization   ${NC}"
echo -e "${BLUE}  and ProjectX quantum entrainment    ${NC}"
echo -e "${BLUE}========================================${NC}"

# Check if Python 3.10 is available
if ! command -v python3.10 &> /dev/null; then
    echo -e "${RED}ERROR: python3.10 is required but not found${NC}"
    echo "Please install Python 3.10 or update the script to use your Python version"
    exit 1
fi

# Check if SIMP broker is running
echo -e "${YELLOW}Checking SIMP broker status...${NC}"
if curl -s http://127.0.0.1:5555/health > /dev/null; then
    echo -e "${GREEN}✓ SIMP broker is running${NC}"
else
    echo -e "${RED}✗ SIMP broker is not running on port 5555${NC}"
    echo "Please start the SIMP broker first:"
    echo "  ./bin/start_server.py --debug"
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p data/inboxes/gate4_real
mkdir -p data/inboxes/projectx_quantum
mkdir -p data/inboxes/quantumarb_real
mkdir -p logs/quantum
mkdir -p logs/mesh
echo -e "${GREEN}✓ Directories created${NC}"

# Check if we're running in headless mode
HEADLESS=false
GOAL="continuous portfolio optimization and ProjectX quantum entrainment"
for arg in "$@"; do
    case $arg in
        --headless)
            HEADLESS=true
            shift
            ;;
        --goal=*)
            GOAL="${arg#*=}"
            shift
            ;;
    esac
done

echo -e "${YELLOW}Mode: ${HEADLESS}${NC}"
echo -e "${YELLOW}Goal: ${GOAL}${NC}"

# Start quantum_mesh_consumer (QIP agent) if not already running
echo -e "${YELLOW}Starting quantum_mesh_consumer (QIP agent)...${NC}"
if ps aux | grep -q "[q]uantum_mesh_consumer"; then
    echo -e "${GREEN}✓ quantum_mesh_consumer already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 quantum_mesh_consumer.py --broker http://127.0.0.1:5555 --interval 2 > logs/quantum/qip.log 2>&1 &
    QIP_PID=$!
    echo $QIP_PID > /tmp/quantum_qip.pid
    echo -e "${GREEN}✓ quantum_mesh_consumer started (PID: $QIP_PID)${NC}"
    sleep 2
fi

# Start quantum_signal_bridge
echo -e "${YELLOW}Starting quantum_signal_bridge...${NC}"
if ps aux | grep -q "[q]uantum_signal_bridge"; then
    echo -e "${GREEN}✓ quantum_signal_bridge already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 quantum_signal_bridge.py --interval 30 > logs/quantum/signal_bridge.log 2>&1 &
    SIGNAL_PID=$!
    echo $SIGNAL_PID > /tmp/quantum_signal.pid
    echo -e "${GREEN}✓ quantum_signal_bridge started (PID: $SIGNAL_PID)${NC}"
    sleep 2
fi

# Start projectx_quantum_advisor
echo -e "${YELLOW}Starting projectx_quantum_advisor...${NC}"
if ps aux | grep -q "[p]rojectx_quantum_advisor"; then
    echo -e "${GREEN}✓ projectx_quantum_advisor already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 projectx_quantum_advisor.py > logs/quantum/projectx_advisor.log 2>&1 &
    PROJECTX_PID=$!
    echo $PROJECTX_PID > /tmp/quantum_projectx.pid
    echo -e "${GREEN}✓ projectx_quantum_advisor started (PID: $PROJECTX_PID)${NC}"
    sleep 2
fi

# Start goose_quantum_orchestrator with the goal
echo -e "${YELLOW}Starting goose_quantum_orchestrator...${NC}"
if ps aux | grep -q "[g]oose_quantum_orchestrator"; then
    echo -e "${GREEN}✓ goose_quantum_orchestrator already running${NC}"
else
    source venv_gate4/bin/activate
    # goose_quantum_orchestrator doesn't have --headless or --goal flags
    # We'll run it with a query that matches our goal
    python3.10 goose_quantum_orchestrator.py "continuous portfolio optimization and ProjectX quantum entrainment" > logs/quantum/orchestrator.log 2>&1 &
    ORCHESTRATOR_PID=$!
    echo $ORCHESTRATOR_PID > /tmp/quantum_orchestrator.pid
    echo -e "${GREEN}✓ goose_quantum_orchestrator started (PID: $ORCHESTRATOR_PID)${NC}"
    sleep 2
fi

# Start quantumarb_file_consumer (file-based alternative to mesh)
echo -e "${YELLOW}Starting quantumarb_file_consumer...${NC}"
if ps aux | grep -q "[q]uantumarb_file_consumer"; then
    echo -e "${GREEN}✓ quantumarb_file_consumer already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 quantumarb_file_consumer.py > logs/quantum/quantumarb_consumer.log 2>&1 &
    QUANTUMARB_PID=$!
    echo $QUANTUMARB_PID > /tmp/quantumarb_consumer.pid
    echo -e "${GREEN}✓ quantumarb_file_consumer started (PID: $QUANTUMARB_PID)${NC}"
    sleep 2
fi

echo -e "${YELLOW}Starting quantum_consensus daemon...${NC}"
if ps aux | grep -q "[q]uantum_consensus"; then
    echo -e "${GREEN}✓ quantum_consensus already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 quantum_consensus.py --run-daemon --interval 30 > logs/quantum/quantum_consensus.log 2>&1 &
    CONSENSUS_PID=$!
    echo $CONSENSUS_PID > /tmp/quantum_consensus.pid
    echo -e "${GREEN}✓ quantum_consensus started (PID: $CONSENSUS_PID)${NC}"
    sleep 2
fi

echo -e "${YELLOW}Starting BRP audit consumer...${NC}"
if ps aux | grep -q "[b]rp_audit_consumer"; then
    echo -e "${GREEN}✓ brp_audit_consumer already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 brp_audit_consumer.py --run-daemon --poll-interval 10 > logs/quantum/brp_audit.log 2>&1 &
    BRP_AUDIT_PID=$!
    echo $BRP_AUDIT_PID > /tmp/brp_audit.pid
    echo -e "${GREEN}✓ brp_audit_consumer started (PID: $BRP_AUDIT_PID)${NC}"
    sleep 2
fi

echo -e "${YELLOW}Starting Agent Coordination System...${NC}"
if ps aux | grep -q "[a]gent_coordination"; then
    echo -e "${GREEN}✓ agent_coordination already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 agent_coordination.py --run-daemon --poll-interval 5 > logs/quantum/agent_coordination.log 2>&1 &
    COORDINATION_PID=$!
    echo $COORDINATION_PID > /tmp/agent_coordination.pid
    echo -e "${GREEN}✓ agent_coordination started (PID: $COORDINATION_PID)${NC}"
    sleep 2
fi

echo -e "${YELLOW}Starting Quantum Advisory Broadcaster...${NC}"
if ps aux | grep -q "[q]uantum_advisory_broadcaster"; then
    echo -e "${GREEN}✓ quantum_advisory_broadcaster already running${NC}"
else
    source venv_gate4/bin/activate
    python3.10 quantum_advisory_broadcaster.py > logs/quantum/quantum_broadcaster.log 2>&1 &
    BROADCASTER_PID=$!
    echo $BROADCASTER_PID > /tmp/quantum_broadcaster.pid
    echo -e "${GREEN}✓ quantum_advisory_broadcaster started (PID: $BROADCASTER_PID)${NC}"
    sleep 2
fi

# Verify all quantum processes are running
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verifying all quantum stack processes...${NC}"
echo -e "${BLUE}========================================${NC}"

sleep 3

PROCESSES=(
    "quantum_mesh_consumer"
    "quantum_signal_bridge"
    "projectx_quantum_advisor"
    "goose_quantum_orchestrator"
    "quantumarb_file_consumer"
    "quantum_consensus"
    "brp_audit_consumer"
    "agent_coordination"
    "quantum_advisory_broadcaster"
)

ALL_RUNNING=true
for process in "${PROCESSES[@]}"; do
    if ps aux | grep -q "[${process:0:1}]${process:1}"; then
        echo -e "${GREEN}✓ $process is running${NC}"
    else
        echo -e "${RED}✗ $process is NOT running${NC}"
        ALL_RUNNING=false
    fi
done

echo -e "${BLUE}========================================${NC}"
if [ "$ALL_RUNNING" = true ]; then
    echo -e "${GREEN}All quantum stack processes are running!${NC}"
    echo ""
    echo "Process IDs:"
    echo "  quantum_mesh_consumer (QIP): $(cat /tmp/quantum_qip.pid 2>/dev/null || echo 'unknown')"
    echo "  quantum_signal_bridge: $(cat /tmp/quantum_signal.pid 2>/dev/null || echo 'unknown')"
    echo "  projectx_quantum_advisor: $(cat /tmp/quantum_projectx.pid 2>/dev/null || echo 'unknown')"
    echo "  goose_quantum_orchestrator: $(cat /tmp/quantum_orchestrator.pid 2>/dev/null || echo 'unknown')"
    echo "  quantumarb_file_consumer: $(cat /tmp/quantumarb_consumer.pid 2>/dev/null || echo 'unknown')"
    echo "  quantum_consensus: $(cat /tmp/quantum_consensus.pid 2>/dev/null || echo 'unknown')"
    echo "  brp_audit_consumer: $(cat /tmp/brp_audit.pid 2>/dev/null || echo 'unknown')"
    echo "  agent_coordination: $(cat /tmp/agent_coordination.pid 2>/dev/null || echo 'unknown')"
    echo "  quantum_advisory_broadcaster: $(cat /tmp/quantum_broadcaster.pid 2>/dev/null || echo 'unknown')"
    echo ""
    echo "Log files:"
    echo "  QIP: logs/quantum/qip.log"
    echo "  Signal Bridge: logs/quantum/signal_bridge.log"
    echo "  ProjectX Advisor: logs/quantum/projectx_advisor.log"
    echo "  Orchestrator: logs/quantum/orchestrator.log"
    echo "  QuantumArb Consumer: logs/quantum/quantumarb_consumer.log"
    echo "  Quantum Consensus: logs/quantum/quantum_consensus.log"
    echo "  BRP Audit: logs/quantum/brp_audit.log"
    echo "  Agent Coordination: logs/quantum/agent_coordination.log"
    echo "  Quantum Broadcaster: logs/quantum/quantum_broadcaster.log"
else
    echo -e "${YELLOW}Some processes failed to start. Check logs for details.${NC}"
fi

echo -e "${BLUE}========================================${NC}"

# If running in headless mode, exit
if [ "$HEADLESS" = true ]; then
    echo -e "${YELLOW}Running in headless mode - exiting script${NC}"
    exit 0
fi

# Otherwise, show monitoring instructions
echo -e "${YELLOW}Monitoring instructions:${NC}"
echo "  To view QIP logs: tail -f logs/quantum/qip.log"
echo "  To view signal bridge logs: tail -f logs/quantum/signal_bridge.log"
echo "  To stop all processes: ./stop_quantum_goose.sh"
echo ""
echo -e "${YELLOW}Checking initial status...${NC}"

# Check broker status
echo -e "${YELLOW}Broker status:${NC}"
curl -s http://127.0.0.1:5555/health | python3 -m json.tool 2>/dev/null || echo "Broker not responding"

# Check mesh status
echo -e "${YELLOW}Mesh status:${NC}"
curl -s http://127.0.0.1:5555/mesh/routing/status | python3 -m json.tool 2>/dev/null | grep -A10 "mesh_routing" || echo "Mesh not responding"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Quantum stack startup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
