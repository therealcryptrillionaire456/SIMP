#!/usr/bin/env python3
"""
Evolution Runner for ASI-Evolve Daily Evolution Loop
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

def run_evolution_experiment(component, rounds, experiment_name):
    """Run an evolution experiment and save results."""
    try:
        sys.path.append('brp_enhancement')
        from integration.modules.asi_evolve_simple_module import create_asi_evolve_simple_module
        
        module = create_asi_evolve_simple_module()
        
        # Run evolution
        results = module.evolve_threat_detection(
            rounds=rounds,
            population_size=4,
            experiment_name=experiment_name
        )
        
        if results.get('success'):
            print(f'✅ Evolution successful for {component}')
            print(f'   Best score: {results.get("final_best_score", 0):.3f}')
            print(f'   Improvement: {results.get("improvement_percent", 0):.1f}%')
            print(f'   Rounds completed: {results.get("rounds_completed", 0)}')
            
            # Save results
            result_data = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'component': component,
                'experiment': experiment_name,
                'results': results,
                'success': True
            }
            
            # Create directory if it doesn't exist
            os.makedirs('data/evolution_results', exist_ok=True)
            
            # Generate filename with current date
            current_date = datetime.now().strftime('%Y%m%d')
            filename = f'data/evolution_results/{component}_{experiment_name}_{current_date}.json'
            
            with open(filename, 'w') as f:
                json.dump(result_data, f, indent=2)
            print(f'   Results saved to: {filename}')
            
            return True
        else:
            print(f'❌ Evolution failed for {component}: {results.get("error", "unknown")}')
            return False
            
    except Exception as e:
        print(f'❌ Error running evolution for {component}: {e}')
        import traceback
        traceback.print_exc()
        return False

def update_evolution_dashboard():
    """Update the evolution dashboard with latest results."""
    import glob
    
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
    
    for file in results_files[-10:]:  # Last 10 results
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
    print(f'   Successful: {dashboard_data["successful_experiments"]}')
    print(f'   Failed: {dashboard_data["failed_experiments"]}')
    print(f'   Avg Improvement: {dashboard_data["average_improvement"]:.1f}%')

def check_system_health():
    """Check system health before running evolution."""
    import requests
    
    print("🏥 Checking system health...")
    
    # Check if broker is running
    try:
        response = requests.get('http://127.0.0.1:5555/health', timeout=5)
        if response.status_code == 200:
            print("✅ Broker is running")
        else:
            print("❌ Broker returned non-200 status")
    except:
        print("❌ Broker is not running")
    
    # Check if ASI-Evolve module can be loaded
    try:
        sys.path.append('brp_enhancement')
        from integration.modules.asi_evolve_simple_module import create_asi_evolve_simple_module
        module = create_asi_evolve_simple_module()
        status = module.get_status()
        print(f'✅ ASI-Evolve module loaded: {status["name"]}')
        print(f'   Version: {status["version"]}')
        print(f'   Capabilities: {len(status["capabilities"])}')
    except Exception as e:
        print(f'❌ ASI-Evolve module failed to load: {e}')
    
    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        disk_percent = (used / total) * 100
        if disk_percent < 90:
            print(f'✅ Disk space: {disk_percent:.1f}% used')
        else:
            print(f'⚠️ Disk space: {disk_percent:.1f}% used (high)')
    except:
        print("⚠️ Could not check disk space")

def main():
    """Main evolution runner."""
    print("🧬 Starting Daily ASI-Evolve Evolution Loop")
    print("=" * 50)
    
    # Create directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data/evolution_results', exist_ok=True)
    
    # Check system health
    check_system_health()
    
    print("\n🚀 Starting evolution experiments")
    
    # Run evolution experiments
    success = run_evolution_experiment(
        component="brp_threat_detection",
        rounds=5,
        experiment_name="daily_threat_evolution"
    )
    
    # Update dashboard
    print("\n📊 Updating evolution dashboard...")
    update_evolution_dashboard()
    
    print("\n" + "=" * 50)
    print("🧬 Daily Evolution Loop Complete")
    print("📁 Results saved in: data/evolution_results/")
    print("📈 Dashboard: data/evolution_dashboard.json")
    print("=" * 50)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())