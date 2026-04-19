#!/bin/bash
# Daily Evolution Review Script
# Creates a daily review of evolution results for the SIMP log

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "📊 Creating Daily Evolution Review - $(date)"
echo "=============================================="

# Create directories
mkdir -p logs
mkdir -p data/daily_reviews

# Define log file
LOG_FILE="logs/daily_evolution_review_$(date +%Y%m%d).log"
echo "📝 Logging to: $LOG_FILE"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create daily review
create_daily_review() {
    log "📋 Creating daily evolution review..."
    
    REVIEW_FILE="data/daily_reviews/evolution_review_$(date +%Y%m%d).md"
    
    # Get today's date
    TODAY=$(date '+%Y-%m-%d')
    
    # Check for evolution results
    if [ ! -f "data/evolution_dashboard.json" ]; then
        log "⚠️ No evolution dashboard data found"
        echo "# Daily Evolution Review - $TODAY" > "$REVIEW_FILE"
        echo "## No evolution data available" >> "$REVIEW_FILE"
        echo "Run the evolution script to generate data." >> "$REVIEW_FILE"
        return
    fi
    
    # Get dashboard data
    DASHBOARD_DATA=$(cat data/evolution_dashboard.json)
    
    # Create review
    {
        echo "# Daily Evolution Review - $TODAY"
        echo "## Generated: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "## Executive Summary"
        
        # Extract metrics from dashboard
        TOTAL_EXPERIMENTS=$(echo "$DASHBOARD_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_experiments', 0))")
        SUCCESSFUL=$(echo "$DASHBOARD_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('successful_experiments', 0))")
        FAILED=$(echo "$DASHBOARD_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('failed_experiments', 0))")
        AVG_IMPROVEMENT=$(echo "$DASHBOARD_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('average_improvement', 0))")
        LAST_UPDATED=$(echo "$DASHBOARD_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('last_updated', 'Never'))")
        
        echo "- **Total Experiments**: $TOTAL_EXPERIMENTS"
        echo "- **Successful**: $SUCCESSFUL"
        echo "- **Failed**: $FAILED"
        echo "- **Average Improvement**: ${AVG_IMPROVEMENT}%"
        echo "- **Last Updated**: $LAST_UPDATED"
        echo ""
        
        echo "## Recent Evolution Results"
        echo ""
        
        # Get recent results
        RECENT_RESULTS=$(echo "$DASHBOARD_DATA" | python3 -c "
import sys, json
data = json.load(sys.stdin)
recent = data.get('recent_results', [])
for result in recent[:5]:  # Last 5 results
    component = result.get('component', 'Unknown')
    experiment = result.get('experiment', 'Unknown')
    timestamp = result.get('timestamp', 'Unknown')
    improvement = result.get('improvement', 0)
    best_score = result.get('best_score', 0)
    
    # Format timestamp
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        formatted_time = timestamp
    
    print(f'### {component} - {experiment}')
    print(f'- **Time**: {formatted_time}')
    print(f'- **Improvement**: {improvement:.1f}%')
    print(f'- **Best Score**: {best_score:.3f}')
    print('')
")
        
        echo "$RECENT_RESULTS"
        
        echo "## Evolution Progress"
        echo ""
        
        # Calculate success rate
        if [ "$TOTAL_EXPERIMENTS" -gt 0 ]; then
            SUCCESS_RATE=$((SUCCESSFUL * 100 / TOTAL_EXPERIMENTS))
            echo "- **Success Rate**: ${SUCCESS_RATE}%"
            
            # Progress bar
            echo "- **Progress**:"
            echo "  \`\`\`"
            echo "  [$(printf '#%.0s' $(seq 1 $((SUCCESS_RATE / 5))))$(printf ' %.0s' $(seq 1 $((20 - SUCCESS_RATE / 5))))] ${SUCCESS_RATE}%"
            echo "  \`\`\`"
        else
            echo "- **No experiments completed yet**"
        fi
        
        echo ""
        echo "## Recommendations"
        echo ""
        
        if [ "$TOTAL_EXPERIMENTS" -eq 0 ]; then
            echo "1. **Run initial evolution**: Start the evolution process to generate baseline data"
            echo "2. **Monitor system health**: Ensure all components are operational"
            echo "3. **Review evolution parameters**: Adjust rounds and population size as needed"
        elif [ "$AVG_IMPROVEMENT" -gt 0 ]; then
            echo "1. **Continue evolution**: Positive improvements detected, continue current strategy"
            echo "2. **Expand experiments**: Consider adding more components to the evolution process"
            echo "3. **Deploy improvements**: Implement successful evolved algorithms"
        else
            echo "1. **Review evolution strategy**: No improvements detected, consider adjusting parameters"
            echo "2. **Check system health**: Ensure all dependencies are functioning correctly"
            echo "3. **Increase experiment diversity**: Try different evolution approaches"
        fi
        
        echo ""
        echo "## Next Actions"
        echo ""
        echo "1. **Review evolution dashboard**: Check real-time metrics"
        echo "2. **Run manual evolution if needed**: Use \`bash tools/run_daily_evolution.sh\`"
        echo "3. **Update evolution parameters**: Based on today's results"
        echo "4. **Document lessons learned**: Add to evolution knowledge base"
        
        echo ""
        echo "---"
        echo "*Generated automatically by Daily Evolution Review System*"
        echo "*Part of SIMP ASI-Evolve Integration*"
        
    } > "$REVIEW_FILE"
    
    log "✅ Daily review created: $REVIEW_FILE"
    
    # Also create a symlink for easy access
    ln -sf "$(basename "$REVIEW_FILE")" "data/daily_reviews/evolution_review_latest.md" 2>/dev/null || true
}

# Create SIMP log entry
create_simp_log_entry() {
    log "📝 Creating SIMP log entry..."
    
    SIMP_LOG="data/daily_reviews/simp_log_$(date +%Y%m%d).md"
    
    # Check if SIMP log exists
    if [ ! -f "$SIMP_LOG" ]; then
        echo "# SIMP Daily Log - $(date '+%Y-%m-%d')" > "$SIMP_LOG"
        echo "## Generated: $(date '+%Y-%m-%d %H:%M:%S')" >> "$SIMP_LOG"
        echo "" >> "$SIMP_LOG"
    fi
    
    # Add evolution section
    {
        echo "## 🧬 ASI-Evolve Daily Evolution"
        echo ""
        echo "### Status"
        echo "- **Evolution System**: ✅ Operational"
        echo "- **Daily Schedule**: 04:00 AM"
        echo "- **Last Run**: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "### Today's Results"
        
        if [ -f "data/evolution_dashboard.json" ]; then
            DASHBOARD_DATA=$(cat data/evolution_dashboard.json)
            TOTAL_EXPERIMENTS=$(echo "$DASHBOARD_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_experiments', 0))")
            AVG_IMPROVEMENT=$(echo "$DASHBOARD_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('average_improvement', 0))")
            
            echo "- **Total Experiments**: $TOTAL_EXPERIMENTS"
            echo "- **Average Improvement**: ${AVG_IMPROVEMENT}%"
            
            # Get latest result
            LATEST_RESULT=$(echo "$DASHBOARD_DATA" | python3 -c "
import sys, json
data = json.load(sys.stdin)
recent = data.get('recent_results', [])
if recent:
    latest = recent[0]
    component = latest.get('component', 'Unknown')
    improvement = latest.get('improvement', 0)
    best_score = latest.get('best_score', 0)
    print(f'- **Latest Experiment**: {component}')
    print(f'- **Latest Improvement**: {improvement:.1f}%')
    print(f'- **Best Score**: {best_score:.3f}')
else:
    print('- **No recent experiments**')
")
            echo "$LATEST_RESULT"
        else
            echo "- **No evolution data available**"
        fi
        
        echo ""
        echo "### Evolution Dashboard"
        echo "- **Access**: [Evolution Dashboard](dashboard/static/evolution_dashboard.html)"
        echo "- **API**: \`/api/evolution/status\`"
        echo "- **Data**: \`data/evolution_dashboard.json\`"
        echo ""
        echo "### Next Evolution"
        echo "- **Scheduled**: 04:00 tomorrow"
        echo "- **Manual Run**: \`bash tools/run_daily_evolution.sh\`"
        echo ""
        echo "---"
        
    } >> "$SIMP_LOG"
    
    log "✅ SIMP log entry created"
}

# Main execution
main() {
    log "🚀 Starting daily evolution review process"
    
    # Create daily review
    create_daily_review
    
    # Create SIMP log entry
    create_simp_log_entry
    
    log "=============================================="
    log "📊 Daily Evolution Review Complete"
    log "📁 Review saved: data/daily_reviews/evolution_review_$(date +%Y%m%d).md"
    log "📝 SIMP log updated: data/daily_reviews/simp_log_$(date +%Y%m%d).md"
    log "=============================================="
}

# Run main function
main

exit 0