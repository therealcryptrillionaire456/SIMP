#!/bin/bash
# Simple Daily ASI-Evolve Evolution Loop

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "🧬 Starting Daily ASI-Evolve Evolution Loop - $(date)"
echo "======================================================"

# Create directories
mkdir -p logs
mkdir -p data/evolution_results

# Define log file
LOG_FILE="logs/daily_evolution_$(date +%Y%m%d).log"
echo "📝 Logging to: $LOG_FILE"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check system health
check_system_health() {
    log "🏥 Checking system health..."
    
    # Check if broker is running
    if curl -s http://127.0.0.1:5555/health >/dev/null 2>&1; then
        log "✅ Broker is running"
    else
        log "❌ Broker is not running"
    fi
    
    # Check if ASI-Evolve module can be loaded
    python3 -c "
import sys
sys.path.append('brp_enhancement')
try:
    from integration.modules.asi_evolve_simple_module import create_asi_evolve_simple_module
    module = create_asi_evolve_simple_module()
    status = module.get_status()
    print('✅ ASI-Evolve module loaded: ' + status['name'])
    print('   Version: ' + status['version'])
    print('   Capabilities: ' + str(len(status['capabilities'])))
except Exception as e:
    print('❌ ASI-Evolve module failed to load: ' + str(e))
" 2>&1 | tee -a "$LOG_FILE"
    
    # Check disk space
    DISK_SPACE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$DISK_SPACE" -lt 90 ]; then
        log "✅ Disk space: ${DISK_SPACE}% used"
    else
        log "⚠️ Disk space: ${DISK_SPACE}% used (high)"
    fi
}

# Run evolution experiment
run_evolution_experiment() {
    local component="$1"
    local rounds="$2"
    local experiment_name="$3"
    
    log "🧪 Starting evolution experiment for $component"
    log "   Experiment: $experiment_name"
    log "   Rounds: $rounds"
    
    python3 -c "
import sys
sys.path.append('brp_enhancement')
try:
    from integration.modules.asi_evolve_simple_module import create_asi_evolve_simple_module
    module = create_asi_evolve_simple_module()
    
    # Run evolution
    results = module.evolve_threat_detection(
        rounds=$rounds,
        population_size=4,
        experiment_name='$experiment_name'
    )"
    
    if results.get('success'):
        print(f'✅ Evolution successful for brp_threat_detection')
        print(f'   Best score: {results.get(\"final_best_score\", 0):.3f}')
        print(f'   Improvement: {results.get(\"improvement_percent\", 0):.1f}%')
        print(f'   Rounds completed: {results.get(\"rounds_completed\", 0)}')
        
        # Save results
        import json
        from datetime import datetime
        import os
        
        result_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'component': 'brp_threat_detection',
            'experiment': experiment_name,
            'results': results,
            'success': True
        }
        
        # Create directory if it doesn't exist
        os.makedirs('data/evolution_results', exist_ok=True)
        
        # Generate filename with current date
        from datetime import datetime
        current_date = datetime.now().strftime('%Y%m%d')
        filename = f'data/evolution_results/brp_threat_detection_{experiment_name}_{current_date}.json'
        
        with open(filename, 'w') as f:
            json.dump(result_data, f, indent=2)
        print(f'   Results saved to: {filename}')
            
    else:
        print(f'❌ Evolution failed for brp_threat_detection: {results.get(\"error\", \"unknown\")}')
        
except Exception as e:
    print(f'❌ Error running evolution for brp_threat_detection: {e}')
    import traceback
    traceback.print_exc()
" 2>&1 | tee -a "$LOG_FILE"
}

# Update evolution dashboard
update_evolution_dashboard() {
    log "📊 Updating evolution dashboard..."
    
    python3 -c "
import json
import glob
from datetime import datetime

results_files = glob.glob('data/evolution_results/*.json')
dashboard_data = {
    'last_updated': datetime.utcnow().isoformat() + 'Z',
    'total_experiments': len(results_files),
    'successful_experiments': 0,
    'failed_experiments': 0,
    'average_improvement': 0,
    'recent_results': []
}

improvements = []

for file in results_files[-10:]:
    try:
        with open(file, 'r') as f:
            data = json.load(f)
        
        if data.get('success'):
            dashboard_data['successful_experiments'] += 1
            results = data.get('results', {})
            improvement = results.get('improvement_percent', 0)
            if improvement > 0:
                improvements.append(improvement)
            
            dashboard_data['recent_results'].append({
                'component': data.get('component'),
                'experiment': data.get('experiment'),
                'timestamp': data.get('timestamp'),
                'improvement': improvement,
                'best_score': results.get('final_best_score', 0)
            })
        else:
            dashboard_data['failed_experiments'] += 1
    except:
        pass

if improvements:
    dashboard_data['average_improvement'] = sum(improvements) / len(improvements)

# Write dashboard data
with open('data/evolution_dashboard.json', 'w') as f:
    json.dump(dashboard_data, f, indent=2)

print(f'✅ Dashboard updated: {len(results_files)} total experiments')
print(f'   Successful: {dashboard_data[\"successful_experiments\"]}')
print(f'   Failed: {dashboard_data[\"failed_experiments\"]}')
print(f'   Avg Improvement: {dashboard_data[\"average_improvement\"]:.1f}%')
" 2>&1 | tee -a "$LOG_FILE"
}

# Main execution
main() {
    log "🚀 Starting daily evolution process"
    
    # Check system health
    check_system_health
    
    # Run evolution experiments
    run_evolution_experiment "brp_threat_detection" 5 "daily_threat_evolution"
    
    # Update dashboard
    update_evolution_dashboard
    
    log "======================================================"
    log "🧬 Daily Evolution Loop Complete"
    log "📁 Results saved in: data/evolution_results/"
    log "📈 Dashboard: data/evolution_dashboard.json"
    log "======================================================"
}

# Run main function
main

exit 0