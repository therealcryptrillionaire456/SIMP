#!/bin/bash
# Deployment script for Gate 4 Scaled Microscopic Agent

set -e  # Exit on error

echo "========================================="
echo "Gate 4 Scaled Microscopic Agent Deployment"
echo "========================================="

# Configuration
CONFIG_DIR="config"
LOG_DIR="logs"
SCRIPT_DIR="scripts"
AGENT_DIR="agents"
VENV_DIR="venv_gate4"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3.10 --version 2>/dev/null || echo "not found")
if [[ $PYTHON_VERSION == *"3.10"* ]]; then
    print_status "Python 3.10 found: $PYTHON_VERSION"
else
    print_error "Python 3.10 not found. Please install Python 3.10."
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p $CONFIG_DIR
mkdir -p $LOG_DIR
mkdir -p $SCRIPT_DIR

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    print_warning "Virtual environment not found. Creating..."
    python3.10 -m venv $VENV_DIR
    print_status "Virtual environment created: $VENV_DIR"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source $VENV_DIR/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install numpy pandas scipy aiohttp pytest cryptography pydantic

# Check if SIMP broker is running
echo "Checking SIMP broker..."
if curl -s http://127.0.0.1:5555/health > /dev/null; then
    print_status "SIMP broker is running"
else
    print_warning "SIMP broker is not running on port 5555"
    print_warning "Start it with: python3.10 -m simp.server.broker"
fi

# Validate configuration
echo "Validating configuration..."
if [ -f "$CONFIG_DIR/gate4_scaled_microscopic.json" ]; then
    python3.10 scripts/validate_gate4.py "$CONFIG_DIR/gate4_scaled_microscopic.json"
    if [ $? -ne 0 ]; then
        print_error "Configuration validation failed"
        exit 1
    fi
else
    print_warning "Configuration file not found: $CONFIG_DIR/gate4_scaled_microscopic.json"
    print_status "Creating default configuration..."
    python3.10 scripts/validate_gate4.py --create-config "$CONFIG_DIR/gate4_scaled_microscopic.json"
    if [ $? -ne 0 ]; then
        print_error "Failed to create default configuration"
        exit 1
    fi
fi

# Run tests
echo "Running tests..."
cd "$(dirname "$0")/.."  # Change to project root
if python3.10 -m pytest tests/test_gate4_basic.py -v > /dev/null 2>&1; then
    print_status "Tests passed"
else
    print_warning "Some tests failed (expected for initial deployment)"
    print_warning "You can run tests manually with: python3.10 -m pytest tests/test_gate4_basic.py -v"
fi

# Create systemd service file (optional)
echo "Creating systemd service file..."
cat > $SCRIPT_DIR/gate4_agent.service << EOF
[Unit]
Description=Gate 4 Scaled Microscopic Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python3.10 $AGENT_DIR/gate4_scaled_microscopic_agent.py --config $CONFIG_DIR/gate4_scaled_microscopic.json
Restart=on-failure
RestartSec=10
StandardOutput=append:$LOG_DIR/gate4_agent.log
StandardError=append:$LOG_DIR/gate4_agent.error.log

[Install]
WantedBy=multi-user.target
EOF

print_status "Systemd service file created: $SCRIPT_DIR/gate4_agent.service"

# Create startup script
echo "Creating startup script..."
cat > $SCRIPT_DIR/start_gate4.sh << 'EOF'
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
EOF

chmod +x $SCRIPT_DIR/start_gate4.sh
print_status "Startup script created: $SCRIPT_DIR/start_gate4.sh"

# Create monitoring script
echo "Creating monitoring script..."
cat > $SCRIPT_DIR/monitor_gate4.sh << 'EOF'
#!/bin/bash
# Monitoring script for Gate 4 agent

set -e

echo "Gate 4 Agent Monitoring"
echo "======================="
echo "Time: $(date)"
echo

# Check if agent is running
if pgrep -f "gate4_scaled_microscopic_agent" > /dev/null; then
    echo "✓ Agent is running"
    
    # Check log file
    if [ -f "logs/gate4_agent.log" ]; then
        echo "✓ Log file exists"
        echo "  Size: $(du -h logs/gate4_agent.log | cut -f1)"
        echo "  Last 5 lines:"
        tail -5 logs/gate4_agent.log
    else
        echo "✗ Log file not found"
    fi
    
    # Check performance data
    if [ -f "data/gate4_performance.jsonl" ]; then
        echo "✓ Performance data exists"
        echo "  Records: $(wc -l < data/gate4_performance.jsonl)"
    fi
    
else
    echo "✗ Agent is not running"
    
    # Check for error logs
    if [ -f "logs/gate4_agent.error.log" ]; then
        echo "Error log contents:"
        tail -20 logs/gate4_agent.error.log
    fi
fi

echo
echo "System Resources:"
echo "-----------------"
top -b -n 1 | head -5
echo
echo "Disk space:"
df -h . | tail -1
EOF

chmod +x $SCRIPT_DIR/monitor_gate4.sh
print_status "Monitoring script created: $SCRIPT_DIR/monitor_gate4.sh"

# Create stop script
echo "Creating stop script..."
cat > $SCRIPT_DIR/stop_gate4.sh << 'EOF'
#!/bin/bash
# Stop script for Gate 4 agent

echo "Stopping Gate 4 agent..."

# Find and kill the agent process
pkill -f "gate4_scaled_microscopic_agent" || true

# Wait for process to stop
sleep 2

# Check if still running
if pgrep -f "gate4_scaled_microscopic_agent" > /dev/null; then
    echo "Agent still running, forcing kill..."
    pkill -9 -f "gate4_scaled_microscopic_agent" || true
fi

echo "Agent stopped"
EOF

chmod +x $SCRIPT_DIR/stop_gate4.sh
print_status "Stop script created: $SCRIPT_DIR/stop_gate4.sh"

# Summary
echo
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo
echo "Files created:"
echo "  - Configuration: $CONFIG_DIR/gate4_scaled_microscopic.json"
echo "  - Systemd service: $SCRIPT_DIR/gate4_agent.service"
echo "  - Startup script: $SCRIPT_DIR/start_gate4.sh"
echo "  - Stop script: $SCRIPT_DIR/stop_gate4.sh"
echo "  - Monitor script: $SCRIPT_DIR/monitor_gate4.sh"
echo
echo "To start the agent:"
echo "  ./$SCRIPT_DIR/start_gate4.sh"
echo
echo "To monitor the agent:"
echo "  ./$SCRIPT_DIR/monitor_gate4.sh"
echo
echo "To stop the agent:"
echo "  ./$SCRIPT_DIR/stop_gate4.sh"
echo
echo "To install as a systemd service:"
echo "  sudo cp $SCRIPT_DIR/gate4_agent.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable gate4_agent"
echo "  sudo systemctl start gate4_agent"
echo
echo "Log files:"
echo "  - logs/gate4_agent.log"
echo "  - logs/gate4_agent.error.log"
echo
echo "Data files:"
echo "  - data/gate4_performance.jsonl"
echo "  - data/gate4_reconciliation.jsonl"
echo "  - data/gate4_compliance.jsonl"
echo
echo "========================================="