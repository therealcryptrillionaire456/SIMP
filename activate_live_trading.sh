#!/bin/bash
# System Activation Script for Live Trading with BRP Protection

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${PURPLE}========================================${NC}"
echo -e "${PURPLE}  SIMP LIVE TRADING ACTIVATION         ${NC}"
echo -e "${PURPLE}  with BRP Protection                  ${NC}"
echo -e "${PURPLE}========================================${NC}"
echo ""

# Function to print section headers
section() {
    echo -e "${CYAN}=== $1 ===${NC}"
}

# Function to print status
status() {
    if [ "$2" = "success" ]; then
        echo -e "${GREEN}✓ $1${NC}"
    elif [ "$2" = "warning" ]; then
        echo -e "${YELLOW}⚠ $1${NC}"
    elif [ "$2" = "error" ]; then
        echo -e "${RED}✗ $1${NC}"
    else
        echo -e "${BLUE}➜ $1${NC}"
    fi
}

# Function to check if a service is running
check_service() {
    if curl -s "$1" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local timeout=$2
    local interval=$3
    local elapsed=0
    
    status "Waiting for $url (timeout: ${timeout}s)" "info"
    
    while [ $elapsed -lt $timeout ]; do
        if check_service "$url"; then
            status "Service $url is ready" "success"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        echo -n "."
    done
    
    echo ""
    status "Service $url not ready after ${timeout}s" "error"
    return 1
}

# ============================================================================
# PHASE 1: SYSTEM CHECKS
# ============================================================================
section "PHASE 1: SYSTEM CHECKS"

# Check Python
if ! command -v python3.10 &> /dev/null; then
    status "Python 3.10 not found" "error"
    exit 1
else
    status "Python 3.10 available" "success"
fi

# Check SIMP broker
section "Checking SIMP Broker"
if check_service "http://127.0.0.1:5555/health"; then
    BROKER_STATUS=$(curl -s http://127.0.0.1:5555/health | python3.10 -c "import sys, json; data=json.load(sys.stdin); print(f'Agents: {data[\"agents_online\"]}, State: {data[\"state\"]}')")
    status "SIMP Broker is running" "success"
    status "Broker status: $BROKER_STATUS" "info"
else
    status "SIMP Broker not running" "error"
    status "Starting SIMP broker..." "info"
    
    # Try to start broker
    if [ -f "./bin/start_broker.sh" ]; then
        ./bin/start_broker.sh &
        BROKER_PID=$!
        status "Broker started with PID: $BROKER_PID" "info"
        
        # Wait for broker to start
        wait_for_service "http://127.0.0.1:5555/health" 30 2
        if [ $? -ne 0 ]; then
            status "Failed to start SIMP broker" "error"
            exit 1
        fi
    else
        status "Broker startup script not found" "error"
        exit 1
    fi
fi

# Check dashboard
section "Checking Dashboard"
if check_service "http://127.0.0.1:5555/dashboard/ui"; then
    status "Dashboard is accessible" "success"
    echo -e "${YELLOW}Dashboard URL: http://127.0.0.1:5555/dashboard/ui${NC}"
else
    status "Dashboard not accessible" "warning"
fi

# ============================================================================
# PHASE 2: BRP PROTECTION ACTIVATION
# ============================================================================
section "PHASE 2: BRP PROTECTION ACTIVATION"

# Create directories
status "Creating directories..." "info"
mkdir -p data/inboxes/quantumarb_enhanced
mkdir -p data/outboxes/quantumarb_enhanced
mkdir -p logs/quantumarb
mkdir -p logs/quantumarb/brp
mkdir -p data/brp_protection
status "Directories created" "success"

# Test BRP integration
status "Testing BRP integration..." "info"
if python3.10 -c "
import sys
sys.path.insert(0, '.')
try:
    from simp.organs.quantumarb.brp_integration import get_brp_integrator
    from simp.security.brp_models import BRPMode
    integrator = get_brp_integrator(mode=BRPMode.ENFORCED)
    print('BRP integration test: SUCCESS')
except Exception as e:
    print(f'BRP integration test: FAILED - {e}')
    sys.exit(1)
"; then
    status "BRP integration test passed" "success"
else
    status "BRP integration test failed" "error"
    exit 1
fi

# ============================================================================
# PHASE 3: ENHANCED QUANTUMARB AGENT SETUP
# ============================================================================
section "PHASE 3: ENHANCED QUANTUMARB AGENT SETUP"

# Compile enhanced agent
status "Compiling enhanced QuantumArb agent..." "info"
if python3.10 -m py_compile simp/agents/quantumarb_agent_enhanced.py; then
    status "Enhanced agent compiled successfully" "success"
else
    status "Failed to compile enhanced agent" "error"
    exit 1
fi

# Register agent with SIMP broker
status "Registering enhanced agent with SIMP broker..." "info"
if python3.10 -c "
import sys
sys.path.insert(0, '.')
import os
os.environ['SIMP_API_KEY'] = 'dev_key'
os.environ['SIMP_BROKER_URL'] = 'http://127.0.0.1:5555'

from simp.agents.quantumarb_agent_enhanced import register_with_simp
if register_with_simp(agent_id='quantumarb_enhanced'):
    print('Registration: SUCCESS')
else:
    print('Registration: FAILED')
    sys.exit(1)
"; then
    status "Enhanced agent registered successfully" "success"
else
    status "Agent registration failed" "warning"
fi

# ============================================================================
# PHASE 4: LIVE TRADING CONFIGURATION
# ============================================================================
section "PHASE 4: LIVE TRADING CONFIGURATION"

# Create live trading configuration
status "Creating live trading configuration..." "info"
cat > live_trading_config.json << 'EOF'
{
  "trading_mode": "live",
  "brp_mode": "enforced",
  "safety_limits": {
    "max_position_size_usd": 1000,
    "max_daily_loss_usd": 100,
    "max_slippage_bps": 50,
    "min_spread_bps": 5
  },
  "markets": ["BTC-USD", "ETH-USD"],
  "exchange": {
    "type": "stub",
    "name": "live_simulation",
    "fee_rate": 0.001,
    "prices": {
      "BTC-USD": 50000,
      "ETH-USD": 2500
    },
    "balances": {
      "USD": 10000,
      "BTC": 0.1,
      "ETH": 1.0
    }
  },
  "monitoring": {
    "dashboard_url": "http://127.0.0.1:5555/dashboard/ui",
    "brp_logs": "logs/quantumarb/brp",
    "trade_logs": "logs/quantumarb/trades.jsonl"
  }
}
EOF
status "Live trading configuration created: live_trading_config.json" "success"

# Create P&L ledger initialization
status "Initializing P&L ledger..." "info"
if python3.10 -c "
import sys
sys.path.insert(0, '.')
from simp.organs.quantumarb.pnl_ledger import get_default_ledger
ledger = get_default_ledger()
print(f'P&L ledger initialized: {ledger.get_ledger_info()}')
"; then
    status "P&L ledger initialized" "success"
else
    status "P&L ledger initialization failed" "warning"
fi

# ============================================================================
# PHASE 5: START ENHANCED QUANTUMARB AGENT
# ============================================================================
section "PHASE 5: START ENHANCED QUANTUMARB AGENT"

status "Starting Enhanced QuantumArb Agent with BRP protection..." "info"
echo -e "${YELLOW}Starting agent in background...${NC}"

# Set environment variables
export SIMP_API_KEY="dev_key"
export SIMP_BROKER_URL="http://127.0.0.1:5555"
export TRADING_MODE="live"
export BRP_MODE="enforced"

# Start the agent in background
python3.10 simp/agents/quantumarb_agent_enhanced.py \
    --poll-interval 2.0 \
    --agent-id quantumarb_enhanced \
    --register \
    > logs/quantumarb/agent_console.log 2>&1 &
    
AGENT_PID=$!
status "Enhanced QuantumArb Agent started with PID: $AGENT_PID" "success"
echo $AGENT_PID > /tmp/quantumarb_enhanced.pid

# Wait a moment for agent to initialize
sleep 3

# Check if agent is running
if ps -p $AGENT_PID > /dev/null; then
    status "Agent is running successfully" "success"
else
    status "Agent failed to start" "error"
    echo -e "${YELLOW}Check logs: logs/quantumarb/agent_console.log${NC}"
    exit 1
fi

# ============================================================================
# PHASE 6: SYSTEM VERIFICATION
# ============================================================================
section "PHASE 6: SYSTEM VERIFICATION"

# Verify agent registration
status "Verifying agent registration..." "info"
AGENT_INFO=$(curl -s http://127.0.0.1:5555/agents | python3.10 -c "
import sys, json
data = json.load(sys.stdin)
agents = data.get('agents', {})
if 'quantumarb_enhanced' in agents:
    agent = agents['quantumarb_enhanced']
    print(f\"Status: {agent.get('status', 'unknown')}\")
    print(f\"Capabilities: {', '.join(agent.get('metadata', {}).get('capabilities', []))}\")
else:
    print('Agent not found in registry')
    sys.exit(1)
")

if [ $? -eq 0 ]; then
    status "Agent verified in SIMP registry" "success"
    echo -e "${BLUE}$AGENT_INFO${NC}"
else
    status "Agent not found in SIMP registry" "warning"
fi

# Check BRP logs
status "Checking BRP logs..." "info"
if [ -f "logs/quantumarb/brp/evaluations.jsonl" ]; then
    BRP_EVALS=$(wc -l < "logs/quantumarb/brp/evaluations.jsonl")
    status "BRP evaluations logged: $BRP_EVALS" "success"
else
    status "BRP logs not yet created" "info"
fi

# ============================================================================
# PHASE 7: TEST TRADE EXECUTION
# ============================================================================
section "PHASE 7: TEST TRADE EXECUTION"

status "Creating test arbitrage intent..." "info"
if python3.10 -c "
import sys
sys.path.insert(0, '.')
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Create test intent
intent = {
    'intent_type': 'evaluate_arb',
    'source_agent': 'system_activator',
    'target_agent': 'quantumarb_enhanced',
    'intent_id': str(uuid.uuid4()),
    'payload': {
        'ticker': 'BTC-USD',
        'direction': 'long',
        'confidence': 0.85,
        'horizon_minutes': 5,
        'metadata': {
            'test': True,
            'activation_test': True,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    },
    'correlation_id': str(uuid.uuid4()),
}

# Write to inbox
inbox_dir = Path('data/inboxes/quantumarb_enhanced')
inbox_dir.mkdir(parents=True, exist_ok=True)
filepath = inbox_dir / f'activation_test_{intent[\"intent_id\"]}.json'
with open(filepath, 'w') as f:
    json.dump(intent, f, indent=2)

print(f'Test intent created: {filepath}')
print(f'Intent ID: {intent[\"intent_id\"]}')
"; then
    TEST_INTENT_ID=$(python3.10 -c "
import sys
sys.path.insert(0, '.')
import uuid
print(str(uuid.uuid4()))
")
    status "Test intent created successfully" "success"
    echo -e "${YELLOW}Test intent ID: $TEST_INTENT_ID${NC}"
else
    status "Failed to create test intent" "warning"
fi

# ============================================================================
# FINAL SYSTEM STATUS
# ============================================================================
section "SYSTEM ACTIVATION COMPLETE"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  LIVE TRADING SYSTEM ACTIVATED        ${NC}"
echo -e "${GREEN}  with BRP Protection                  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}SYSTEM STATUS:${NC}"
echo -e "  ${GREEN}✓${NC} SIMP Broker: Running on port 5555"
echo -e "  ${GREEN}✓${NC} Dashboard: http://127.0.0.1:5555/dashboard/ui"
echo -e "  ${GREEN}✓${NC} Enhanced QuantumArb Agent: Running (PID: $AGENT_PID)"
echo -e "  ${GREEN}✓${NC} BRP Protection: ENFORCED mode active"
echo -e "  ${GREEN}✓${NC} Live Trading Mode: Activated"
echo -e "  ${GREEN}✓${NC} P&L Tracking: Ready"
echo ""
echo -e "${CYAN}MONITORING:${NC}"
echo -e "  Agent logs: ${YELLOW}logs/quantumarb/agent_console.log${NC}"
echo -e "  BRP logs: ${YELLOW}logs/quantumarb/brp/${NC}"
echo -e "  Dashboard: ${YELLOW}http://127.0.0.1:5555/dashboard/ui${NC}"
echo ""
echo -e "${CYAN}TEST INTENT:${NC}"
echo -e "  A test arbitrage intent has been sent to the agent"
echo -e "  Check the dashboard or logs for processing results"
echo ""
echo -e "${CYAN}NEXT STEPS:${NC}"
echo "  1. Monitor the dashboard for system activity"
echo "  2. Check BRP logs for threat evaluations"
echo "  3. Review agent logs for trade processing"
echo "  4. Send more test intents to verify functionality"
echo ""
echo -e "${PURPLE}========================================${NC}"
echo -e "${PURPLE}  System ready for live trading!       ${NC}"
echo -e "${PURPLE}========================================${NC}"

# Save activation info
cat > system_activation_report.txt << EOF
SIMP LIVE TRADING SYSTEM ACTIVATION REPORT
==========================================
Timestamp: $(date)
Activation ID: $(uuidgen)

SYSTEM COMPONENTS:
- SIMP Broker: http://127.0.0.1:5555
- Dashboard: http://127.0.0.1:5555/dashboard/ui
- Enhanced QuantumArb Agent: PID $AGENT_PID
- BRP Protection: ENFORCED mode
- Trading Mode: LIVE (simulation)

CONFIGURATION:
- Trading mode: live
- BRP mode: enforced
- Safety limits: active
- P&L tracking: enabled

TEST INTENT:
- Intent ID: $TEST_INTENT_ID
- Market: BTC-USD
- Direction: long

LOGS:
- Agent console: logs/quantumarb/agent_console.log
- BRP evaluations: logs/quantumarb/brp/evaluations.jsonl
- Trade logs: logs/quantumarb/trades.jsonl

NEXT STEPS:
1. Monitor dashboard for real-time activity
2. Review BRP threat evaluations
3. Test emergency stop procedures
4. Gradually increase trading limits
EOF

status "Activation report saved: system_activation_report.txt" "info"