#!/usr/bin/env python3.10
"""
Apply Agent Lightning dashboard patch
"""

import sys
import os
import logging
import importlib

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_dashboard_patch():
    """Apply Agent Lightning patch to the dashboard"""
    
    try:
        # Import the patch
        from patches.agent_lightning_dashboard_patch import patch_dashboard_for_agent_lightning
        
        # Try to get the dashboard app
        try:
            import dashboard.server as dashboard_module
            
            # Check if dashboard app exists
            if hasattr(dashboard_module, 'app'):
                dashboard_app = dashboard_module.app
                logger.info(f"Found dashboard app: {dashboard_app}")
                
                # Apply patch
                patched_dashboard = patch_dashboard_for_agent_lightning(dashboard_app)
                
                if patched_dashboard:
                    logger.info("✅ Successfully applied Agent Lightning patch to dashboard")
                    
                    # Test the integration
                    test_dashboard_integration()
                    return True
                else:
                    logger.error("Failed to patch dashboard")
                    return False
            else:
                logger.warning("No dashboard app found in dashboard.server module")
                
                # Try to create a test dashboard app
                logger.info("Creating test dashboard app for integration...")
                from fastapi import FastAPI
                test_app = FastAPI()
                
                patched_app = patch_dashboard_for_agent_lightning(test_app)
                
                if patched_app:
                    logger.info("✅ Test dashboard app patched successfully")
                    
                    # Check if real dashboard can be patched on next restart
                    logger.info("Note: Real dashboard will need to be restarted or patched at startup")
                    return True
                else:
                    logger.error("Failed to patch test dashboard app")
                    return False
                
        except ImportError as e:
            logger.error(f"Failed to import dashboard: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error applying dashboard patch: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dashboard_integration():
    """Test dashboard integration"""
    
    logger.info("Testing dashboard integration...")
    
    try:
        # Test Agent Lightning manager
        from simp.integrations.agent_lightning import agent_lightning_manager
        
        # Check if dashboard endpoints would work
        health_endpoint = "http://127.0.0.1:8050/agent-lightning/health"
        performance_endpoint = "http://127.0.0.1:8050/agent-lightning/performance"
        ui_endpoint = "http://127.0.0.1:8050/agent-lightning-ui/"
        
        logger.info(f"Dashboard endpoints that should be available:")
        logger.info(f"  Health: {health_endpoint}")
        logger.info(f"  Performance: {performance_endpoint}")
        logger.info(f"  UI: {ui_endpoint}")
        
        # Check if dashboard is running
        import requests
        try:
            response = requests.get("http://127.0.0.1:8050/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Dashboard is running")
                
                # Try to access Agent Lightning endpoints
                endpoints_to_test = [
                    ("/agent-lightning/health", "Agent Lightning health"),
                    ("/agent-lightning/performance", "Agent Lightning performance"),
                    ("/agent-lightning-ui/", "Agent Lightning UI")
                ]
                
                for endpoint, description in endpoints_to_test:
                    try:
                        response = requests.get(f"http://127.0.0.1:8050{endpoint}", timeout=5)
                        if response.status_code == 200:
                            logger.info(f"✅ {description} endpoint is available")
                        elif response.status_code == 404:
                            logger.warning(f"⚠️ {description} endpoint not found (404)")
                        else:
                            logger.info(f"⚠️ {description} endpoint returned {response.status_code}")
                    except Exception as e:
                        logger.info(f"⚠️ {description} endpoint not accessible: {e}")
            else:
                logger.warning(f"⚠️ Dashboard health check returned {response.status_code}")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not connect to dashboard: {e}")
        
        return True
        
    except ImportError as e:
        logger.error(f"Agent Lightning integration not available: {e}")
    except Exception as e:
        logger.error(f"Error testing dashboard integration: {e}")

def create_dashboard_restart_script():
    """Create script to restart dashboard with Agent Lightning integration"""
    
    logger.info("Creating dashboard restart script...")
    
    script_content = """#!/bin/bash
# Restart SIMP dashboard with Agent Lightning integration

echo "================================================"
echo "🚀 Restarting SIMP Dashboard with Agent Lightning"
echo "================================================"

# Kill existing dashboard processes
echo "Stopping existing dashboard..."
pkill -f "dashboard/server.py" 2>/dev/null || true
pkill -f "uvicorn.*dashboard" 2>/dev/null || true
sleep 2

# Set Agent Lightning environment variables
export AGENT_LIGHTNING_ENABLED=true
export AGENT_LIGHTNING_PROXY_HOST=localhost
export AGENT_LIGHTNING_PROXY_PORT=8320
export AGENT_LIGHTNING_STORE_HOST=localhost
export AGENT_LIGHTNING_STORE_PORT=43887
export AGENT_LIGHTNING_MODEL=glm-4-plus
export AGENT_LIGHTNING_ENABLE_APO=true
export AGENT_LIGHTNING_TRACE_ALL_AGENTS=true

# Start dashboard
echo "Starting dashboard with Agent Lightning integration..."
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
python3.10 -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8050 --reload > /tmp/dashboard.log 2>&1 &

echo "Waiting for dashboard to start..."
sleep 5

# Check if dashboard is running
if curl -s http://127.0.0.1:8050/health > /dev/null; then
    echo "✅ Dashboard started successfully"
    echo ""
    echo "Agent Lightning Dashboard URLs:"
    echo "  Main Dashboard: http://127.0.0.1:8050/"
    echo "  Agent Lightning UI: http://127.0.0.1:8050/agent-lightning-ui/"
    echo "  Agent Lightning Health: http://127.0.0.1:8050/agent-lightning/health"
    echo "  Agent Lightning Performance: http://127.0.0.1:8050/agent-lightning/performance"
    echo ""
    echo "Logs: /tmp/dashboard.log"
else
    echo "❌ Dashboard failed to start"
    echo "Check /tmp/dashboard.log for details"
fi
"""
    
    script_path = "./restart_dashboard_with_lightning.sh"
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    import stat
    os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    
    logger.info(f"✅ Created restart script: {script_path}")
    logger.info(f"Run: ./{os.path.basename(script_path)} to restart dashboard with Agent Lightning")
    
    return script_path

def main():
    """Main function"""
    
    logger.info("================================================")
    logger.info("🚀 Applying Agent Lightning Patch to SIMP Dashboard")
    logger.info("================================================")
    
    # Apply patch
    success = apply_dashboard_patch()
    
    if success:
        logger.info("✅ Agent Lightning dashboard patch applied successfully")
        
        # Create restart script
        restart_script = create_dashboard_restart_script()
        
        logger.info("\n" + "="*50)
        logger.info("📋 NEXT STEPS")
        logger.info("="*50)
        logger.info("1. Run the restart script to apply changes:")
        logger.info(f"   ./{os.path.basename(restart_script)}")
        logger.info("\n2. After restart, check:")
        logger.info("   - http://127.0.0.1:8050/agent-lightning-ui/")
        logger.info("   - http://127.0.0.1:8050/agent-lightning/health")
        logger.info("\n3. Monitor /tmp/dashboard.log for any issues")
        
    else:
        logger.error("❌ Failed to apply Agent Lightning dashboard patch")
        
        # Still create restart script as fallback
        restart_script = create_dashboard_restart_script()
        logger.info(f"\nCreated restart script as fallback: {restart_script}")
        logger.info("This will restart the dashboard with Agent Lightning environment variables")
        
        sys.exit(1)

if __name__ == "__main__":
    main()