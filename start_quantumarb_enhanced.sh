#!/bin/bash
# Startup script for Enhanced QuantumArb Agent with BRP Protection

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Enhanced QuantumArb Agent Startup     ${NC}"
echo -e "${BLUE}  with BRP Live Protection             ${NC}"
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
    echo "  ./bin/start_broker.sh"
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p data/inboxes/quantumarb_enhanced
mkdir -p data/outboxes/quantumarb_enhanced
mkdir -p logs/quantumarb
mkdir -p logs/quantumarb/brp
echo -e "${GREEN}✓ Directories created${NC}"

# Check BRP integration
echo -e "${YELLOW}Checking BRP integration...${NC}"
if python3.10 -c "import simp.organs.quantumarb.brp_integration" 2>/dev/null; then
    echo -e "${GREEN}✓ BRP integration module available${NC}"
else
    echo -e "${YELLOW}⚠ BRP integration module not found, compiling...${NC}"
    if python3.10 -m py_compile simp/organs/quantumarb/brp_integration.py; then
        echo -e "${GREEN}✓ BRP integration module compiled${NC}"
    else
        echo -e "${RED}✗ Failed to compile BRP integration module${NC}"
        exit 1
    fi
fi

# Check enhanced agent
echo -e "${YELLOW}Checking enhanced agent...${NC}"
if python3.10 -m py_compile simp/agents/quantumarb_agent_enhanced.py; then
    echo -e "${GREEN}✓ Enhanced agent compiled successfully${NC}"
else
    echo -e "${RED}✗ Failed to compile enhanced agent${NC}"
    exit 1
fi

# Register agent with SIMP broker
echo -e "${YELLOW}Registering enhanced agent with SIMP broker...${NC}"
if python3.10 -c "
import sys
sys.path.insert(0, '.')
from simp.agents.quantumarb_agent_enhanced import register_with_simp
import os
os.environ['SIMP_API_KEY'] = 'dev_key'
if register_with_simp(agent_id='quantumarb_enhanced'):
    print('Registration successful')
else:
    print('Registration failed')
    sys.exit(1)
"; then
    echo -e "${GREEN}✓ Enhanced agent registered successfully${NC}"
else
    echo -e "${YELLOW}⚠ Agent registration failed, continuing anyway...${NC}"
fi

# Start the enhanced agent
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Starting Enhanced QuantumArb Agent...${NC}"
echo -e "${BLUE}Mode: BRP ENFORCED Protection Enabled${NC}"
echo -e "${BLUE}Agent ID: quantumarb_enhanced${NC}"
echo -e "${BLUE}========================================${NC}"

# Set environment variables
export SIMP_API_KEY="dev_key"
export SIMP_BROKER_URL="http://127.0.0.1:5555"

# Run the enhanced agent
python3.10 simp/agents/quantumarb_agent_enhanced.py \
    --poll-interval 2.0 \
    --agent-id quantumarb_enhanced

# Capture exit code
EXIT_CODE=$?

echo -e "${BLUE}========================================${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Enhanced QuantumArb Agent stopped normally${NC}"
else
    echo -e "${RED}Enhanced QuantumArb Agent exited with code $EXIT_CODE${NC}"
fi
echo -e "${BLUE}========================================${NC}"

exit $EXIT_CODE