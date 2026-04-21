#!/bin/bash
# Startup script for Gate 4 agent

set -e

echo "Starting Gate 4 Scaled Microscopic Agent..."
echo "Date: $(date)"
echo "Working directory: $(pwd)"

# Activate virtual environment
source venv_gate4/bin/activate

# Run the agent
python3.10 agents/gate4_scaled_microscopic_agent.py --config config/gate4_scaled_microscopic.json

echo "Agent stopped at: $(date)"
