#!/bin/bash

# =============================================================================
# GATE4 TRADING BOT RUNNER
# =============================================================================
# Secure script to run the gate4 inbox consumer with proper environment setup
#
# Usage:
#   ./scripts/run_trader.sh [mode]
#
# Modes:
#   dry-run    - Test without real orders (default)
#   once       - Process inbox once and exit
#   live       - Run continuously (daemon mode)
#
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_gate4"
CONSUMER_SCRIPT="$PROJECT_DIR/gate4_inbox_consumer.py"

# Check if we're in the right directory
if [ ! -f "$CONSUMER_SCRIPT" ]; then
    echo "ERROR: gate4_inbox_consumer.py not found in $PROJECT_DIR"
    exit 1
fi

# Load environment variables
echo "Loading environment variables..."
source "$SCRIPT_DIR/load_env.sh"

# Determine mode
MODE="${1:-dry-run}"

case "$MODE" in
    "dry-run")
        echo "🧪 Starting DRY-RUN mode (no real orders)"
        EXTRA_ARGS="--dry-run"
        ;;
    "once")
        echo "🎯 Starting ONCE mode (process inbox once and exit)"
        EXTRA_ARGS="--once"
        ;;
    "live")
        echo "🚀 Starting LIVE mode (daemon - continuous trading)"
        EXTRA_ARGS=""
        ;;
    *)
        echo "ERROR: Unknown mode '$MODE'"
        echo "Available modes: dry-run, once, live"
        exit 1
        ;;
esac

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if required packages are installed
echo "Checking dependencies..."
python -c "import coinbase.rest" 2>/dev/null || {
    echo "Installing Coinbase SDK..."
    pip install coinbase-advanced-py
}

# Change to project directory
cd "$PROJECT_DIR"

# Show configuration summary
echo ""
echo "=== TRADING CONFIGURATION ==="
echo "Mode: $MODE"
echo "Environment: ${SIM_ENVIRONMENT:-sandbox}"
echo "Debug: ${SIM_DEBUG_MODE:-false}"
echo "Emergency Stop: ${EMERGENCY_STOP:-false}"
echo "Symbols: BTC-USD, ETH-USD, SOL-USD"
echo "Position Size: $1.00 - $10.00"
echo "=============================="
echo ""

# Run the consumer
if [ "${EMERGENCY_STOP:-false}" = "true" ]; then
    echo "⚠️  EMERGENCY STOP ACTIVATED - Trading disabled"
    exit 1
fi

echo "🚀 Starting gate4 inbox consumer..."
echo "Press Ctrl+C to stop"
echo ""

# Run the consumer with appropriate arguments
python3.10 "$CONSUMER_SCRIPT" $EXTRA_ARGS