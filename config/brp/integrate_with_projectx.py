#!/usr/bin/env python3.10
"""
Integrate Agent Lightning monitors with ProjectX
"""

import json
import os
import sys
from pathlib import Path

def integrate_with_projectx():
    """Integrate Agent Lightning monitors with ProjectX"""
    
    print("🔗 Integrating Agent Lightning monitors with ProjectX...")
    
    # ProjectX configuration path
    projectx_config_path = "/Users/kaseymarcelle/ProjectX/config"
    monitors_file = "config/brp/projectx_agent_lightning.json"
    
    if not os.path.exists(monitors_file):
        print(f"❌ Monitors file not found: {monitors_file}")
        return False
        
    try:
        with open(monitors_file, 'r') as f:
            monitors_config = json.load(f)
            
        # Create ProjectX monitors directory if it doesn't exist
        projectx_monitors_dir = os.path.join(projectx_config_path, "monitors")
        os.makedirs(projectx_monitors_dir, exist_ok=True)
        
        # Save individual monitor files
        monitors = monitors_config.get("agent_lightning_monitors", {}).get("monitors", [])
        
        for monitor in monitors:
            monitor_id = monitor.get("monitor_id", "unknown")
            monitor_file = os.path.join(projectx_monitors_dir, f"{monitor_id}.json")
            
            with open(monitor_file, 'w') as f:
                json.dump(monitor, f, indent=2)
                
        print(f"✅ Created {len(monitors)} monitor files in {projectx_monitors_dir}")
        
        # Create integration summary
        summary = {
            "integration_time": monitors_config.get("agent_lightning_monitors", {}).get("integration_time"),
            "total_monitors": len(monitors),
            "source": "Agent Lightning Trace Analysis"
        }
        
        summary_file = os.path.join(projectx_monitors_dir, "integration_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print(f"📋 Integration summary saved: {summary_file}")
        
        # Instructions for ProjectX
        print("
🎯 NEXT STEPS FOR PROJECTX INTEGRATION:")
        print("1. Restart ProjectX to load new monitors")
        print("2. Verify monitors are active in ProjectX dashboard")
        print("3. Test monitor alerts with simulated agent behavior")
        print("4. Review alert thresholds and adjust as needed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error integrating with ProjectX: {e}")
        return False

if __name__ == "__main__":
    success = integrate_with_projectx()
    sys.exit(0 if success else 1)
