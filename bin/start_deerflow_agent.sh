#!/bin/bash
# Start DeerFlow Agent for SIMP System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/venv_gate4"

# Check if DeerFlow is running
echo "🔍 Checking DeerFlow status..."
if ! curl -s http://127.0.0.1:8001/health > /dev/null; then
    echo "❌ DeerFlow is not running on port 8001"
    echo "   Start DeerFlow first: cd /Users/kaseymarcelle/ProjectX/deer-flow && make run"
    exit 1
fi
echo "✅ DeerFlow is running"

# Activate virtual environment
if [ -f "$VENV_PATH/bin/activate" ]; then
    echo "🐍 Activating Python virtual environment..."
    source "$VENV_PATH/bin/activate"
else
    echo "⚠️  Virtual environment not found at $VENV_PATH"
    echo "   Using system Python"
fi

# Set environment variables
export DEERFLOW_URL="http://127.0.0.1:8001"
export DEERFLOW_AGENT_PORT="8888"
export SIMP_BROKER_URL="http://127.0.0.1:5555"

# Start the agent
echo "🚀 Starting DeerFlow Agent..."
cd "$PROJECT_ROOT"
python3 agents/deerflow_agent.py &

# Get PID
DEERFLOW_AGENT_PID=$!
echo $DEERFLOW_AGENT_PID > /tmp/deerflow_agent.pid
echo "📝 DeerFlow Agent PID: $DEERFLOW_AGENT_PID"

# Wait for agent to start
echo "⏳ Waiting for agent to start..."
sleep 3

# Check if agent is running
if curl -s http://127.0.0.1:8888/health > /dev/null; then
    echo "✅ DeerFlow Agent started successfully on port 8888"
    
    # Register with SIMP broker
    echo "🔗 Registering with SIMP broker..."
    REGISTER_RESPONSE=$(curl -s -X POST "$SIMP_BROKER_URL/agents/register" \
        -H "Content-Type: application/json" \
        -d '{
            "agent_id": "deerflow",
            "agent_type": "management",
            "endpoint": "http://127.0.0.1:8888",
            "capabilities": ["subagent_spawning", "skill_management", "sandbox_execution", "concurrency_management"],
            "metadata": {
                "deerflow_integration": true,
                "version": "1.0.0"
            }
        }')
    
    if echo "$REGISTER_RESPONSE" | grep -q "registered"; then
        echo "✅ Successfully registered with SIMP broker"
    else
        echo "⚠️  Could not register with SIMP broker (might already be registered)"
    fi
    
    echo ""
    echo "🎉 DeerFlow Agent is ready!"
    echo "   Health check: curl http://127.0.0.1:8888/health"
    echo "   Capabilities: curl http://127.0.0.1:8888/capabilities"
    echo "   Subagents:    curl http://127.0.0.1:8888/subagents"
    echo ""
    echo "To stop: kill $DEERFLOW_AGENT_PID"
else
    echo "❌ Failed to start DeerFlow Agent"
    kill $DEERFLOW_AGENT_PID 2>/dev/null
    exit 1
fi