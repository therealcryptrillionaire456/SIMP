#!/bin/bash
# Enhanced Daily ASI-Evolve Evolution Loop
# Runs at 04:00 daily to evolve multiple SIMP components including QuantumArb

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "🧬 Starting Enhanced Daily ASI-Evolve Evolution Loop - $(date)"
echo "=============================================================="

# Create required directories
mkdir -p logs
mkdir -p data/evolution_results
mkdir -p data/daily_summaries

# Define log file
LOG_FILE="logs/daily_evolution_$(date +%Y%m%d).log"
echo "📝 Logging to: $LOG_FILE"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check system health
log "🔍 Checking system health..."
if ! python3 -c "import sys, json, pathlib; print('Python OK')" 2>/dev/null; then
    log "❌ Python check failed"
    exit 1
fi

if [ ! -f "tools/evolution_runner_v2.py" ]; then
    log "⚠️ Enhanced evolution runner not found, falling back to basic runner"
    RUNNER="tools/evolution_runner.py"
else
    RUNNER="tools/evolution_runner_v2.py"
    log "✅ Using enhanced evolution runner"
fi

# Check for QuantumArb evolution module
if [ -f "tools/evolution_quantumarb.py" ]; then
    log "✅ QuantumArb evolution module available"
    QUANTUMARB_ENABLED=true
else
    log "⚠️ QuantumArb evolution module not found"
    QUANTUMARB_ENABLED=false
fi

# Run the evolution
log "🚀 Starting multi-component evolution process"
log "Components to evolve:"
log "  - BRP Threat Detection (always)"
if [ "$QUANTUMARB_ENABLED" = true ]; then
    log "  - QuantumArb Trading Algorithms"
fi

# Run evolution runner
if [ "$RUNNER" = "tools/evolution_runner_v2.py" ]; then
    python3 "$RUNNER" --mode daily 2>&1 | tee -a "$LOG_FILE"
else
    python3 "$RUNNER" 2>&1 | tee -a "$LOG_FILE"
fi

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    log "✅ Evolution completed successfully"
else
    log "⚠️ Evolution completed with errors (exit code: $EXIT_CODE)"
fi

# Generate daily summary
log "📊 Generating daily evolution summary..."
if [ -f "data/daily_summaries/evolution_summary_$(date +%Y%m%d).json" ]; then
    log "✅ Daily summary generated"
    
    # Show summary
    python3 << EOF
import json
from pathlib import Path

summary_file = Path("data/daily_summaries/evolution_summary_$(date +%Y%m%d).json")
if summary_file.exists():
    with open(summary_file, 'r') as f:
        summary = json.load(f)
    
    print(f"📅 Date: {summary.get('date', 'Unknown')}")
    print(f"📦 Components: {summary.get('total_components', 0)}")
    print(f"✅ Successful: {summary.get('successful_components', 0)}")
    print(f"📈 Success Rate: {(summary.get('successful_components', 0) / summary.get('total_components', 1) * 100):.1f}%")
    
    for comp in summary.get('components', []):
        status = "✅" if comp.get('success') else "❌"
        print(f"  {status} {comp.get('name', 'Unknown')}: score={comp.get('score', 0):.3f}, improvement={comp.get('improvement', 0):.1f}%")
EOF
else
    log "⚠️ Daily summary not found"
fi

log "=============================================================="
log "🧬 Enhanced Daily Evolution Loop Complete"
log "📁 Results saved in: data/evolution_results/"
log "📈 Dashboard: data/evolution_dashboard.json"
log "📊 Daily summaries: data/daily_summaries/"
log "🔄 Next evolution: 04:00 tomorrow"
log "=============================================================="

exit $EXIT_CODE