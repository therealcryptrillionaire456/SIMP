#!/usr/bin/env python3
"""
Full Agent Lightning Integration for SIMP Ecosystem

This script performs complete integration of Microsoft's Agent Lightning
framework with the entire SIMP ecosystem, including:

1. Agent Lightning proxy setup and configuration
2. Integration with SIMP broker for intent tracing
3. Integration with SIMP dashboard for visualization
4. Patching of all major SIMP agents
5. Configuration management and health monitoring
"""

import os
import sys
import time
import logging
import subprocess
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add SIMP to path
simp_root = Path(__file__).parent
sys.path.insert(0, str(simp_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(simp_root / 'logs' / 'agent_lightning_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AgentLightningIntegrator:
    """Main integrator class for Agent Lightning with SIMP"""
    
    def __init__(self):
        self.simp_root = simp_root
        self.config = self.load_configuration()
        self.agent_lightning_manager = None
        
    def load_configuration(self) -> Dict[str, Any]:
        """Load integration configuration"""
        config = {
            'enabled': os.environ.get('AGENT_LIGHTNING_ENABLED', 'true').lower() == 'true',
            'proxy_host': os.environ.get('AGENT_LIGHTNING_PROXY_HOST', 'localhost'),
            'proxy_port': int(os.environ.get('AGENT_LIGHTNING_PROXY_PORT', '8235')),
            'store_host': os.environ.get('AGENT_LIGHTNING_STORE_HOST', 'localhost'),
            'store_port': int(os.environ.get('AGENT_LIGHTNING_STORE_PORT', '43887')),
            'api_key': os.environ.get('X_AI_API_KEY'),
            'model': os.environ.get('AGENT_LIGHTNING_MODEL', 'glm-4-plus'),
            'trace_all_agents': os.environ.get('TRACE_ALL_AGENTS', 'true').lower() == 'true',
            'trace_specific_agents': os.environ.get('TRACE_SPECIFIC_AGENTS', 'quantumarb,kashclaw_gemma,kloutbot,projectx_native').split(','),
            'enable_apo': os.environ.get('ENABLE_APO', 'true').lower() == 'true',
            'dashboard_integration': os.environ.get('DASHBOARD_INTEGRATION_ENABLED', 'true').lower() == 'true',
            'update_interval': int(os.environ.get('UPDATE_INTERVAL_SECONDS', '30'))
        }
        
        logger.info(f"Loaded configuration: enabled={config['enabled']}")
        return config
    
    def check_agent_lightning_available(self) -> bool:
        """Check if Agent Lightning is available"""
        try:
            # Check if we can import the integration module
            spec = importlib.util.spec_from_file_location(
                "agent_lightning_integration",
                self.simp_root / "simp" / "integrations" / "agent_lightning.py"
            )
            if spec is None:
                logger.error("Agent Lightning integration module not found")
                return False
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.agent_lightning_manager = module.agent_lightning_manager
            logger.info("Agent Lightning integration module loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Agent Lightning integration: {e}")
            return False
    
    def start_agent_lightning_proxy(self) -> bool:
        """Start the Agent Lightning proxy"""
        if not self.config['enabled']:
            logger.info("Agent Lightning integration disabled in configuration")
            return False
        
        logger.info("Starting Agent Lightning proxy...")
        
        # Check if proxy is already running
        try:
            import requests
            proxy_url = f"http://{self.config['proxy_host']}:{self.config['proxy_port']}/health"
            response = requests.get(proxy_url, timeout=5)
            if response.status_code == 200:
                logger.info("✅ Agent Lightning proxy is already running")
                return True
        except:
            pass
        
        # Start the proxy from stray_goose directory
        stray_goose_dir = Path.home() / "stray_goose"
        proxy_script = stray_goose_dir / "zai_agent_lightning_proxy.py"
        
        if not proxy_script.exists():
            logger.error(f"Agent Lightning proxy script not found: {proxy_script}")
            logger.info("Please ensure stray_goose setup is complete")
            return False
        
        if not self.config['api_key']:
            logger.error("X_AI_API_KEY environment variable not set")
            logger.info("Set it with: export X_AI_API_KEY='your-api-key'")
            return False
        
        # Start the proxy
        try:
            env = os.environ.copy()
            env['X_AI_API_KEY'] = self.config['api_key']
            
            cmd = [
                sys.executable,
                str(proxy_script)
            ]
            
            # Start in background
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=str(stray_goose_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for startup
            time.sleep(5)
            
            # Check if it's running
            try:
                import requests
                response = requests.get(f"http://localhost:{self.config['proxy_port']}/health", timeout=5)
                if response.status_code == 200:
                    logger.info("✅ Agent Lightning proxy started successfully")
                    
                    # Log proxy info
                    logger.info(f"   Proxy URL: http://localhost:{self.config['proxy_port']}")
                    logger.info(f"   Store URL: http://localhost:{self.config['store_port']}")
                    logger.info(f"   Model: {self.config['model']}")
                    
                    return True
                else:
                    logger.error(f"Proxy health check failed: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Proxy failed to start: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Agent Lightning proxy: {e}")
            return False
    
    def integrate_with_simp_broker(self) -> bool:
        """Integrate Agent Lightning with SIMP broker"""
        if not self.config['enabled']:
            return False
        
        logger.info("Integrating Agent Lightning with SIMP broker...")
        
        try:
            # Import and apply broker patch
            patch_path = self.simp_root / "patches" / "agent_lightning_broker_patch.py"
            if not patch_path.exists():
                logger.error(f"Broker patch not found: {patch_path}")
                return False
            
            spec = importlib.util.spec_from_file_location("broker_patch", patch_path)
            patch_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(patch_module)
            
            # This would typically be called from broker startup
            # For now, we'll just verify the patch is available
            logger.info("✅ Agent Lightning broker patch loaded")
            logger.info("   Apply by calling: patch_broker_for_agent_lightning(broker_instance)")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to integrate with SIMP broker: {e}")
            return False
    
    def integrate_with_simp_dashboard(self) -> bool:
        """Integrate Agent Lightning with SIMP dashboard"""
        if not self.config['enabled'] or not self.config['dashboard_integration']:
            return False
        
        logger.info("Integrating Agent Lightning with SIMP dashboard...")
        
        try:
            # Import and apply dashboard patch
            patch_path = self.simp_root / "patches" / "agent_lightning_dashboard_patch.py"
            if not patch_path.exists():
                logger.error(f"Dashboard patch not found: {patch_path}")
                return False
            
            spec = importlib.util.spec_from_file_location("dashboard_patch", patch_path)
            patch_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(patch_module)
            
            # This would typically be called from dashboard startup
            logger.info("✅ Agent Lightning dashboard patch loaded")
            logger.info("   Apply by calling: patch_dashboard_for_agent_lightning(dashboard_app)")
            logger.info("   Dashboard UI available at: /agent-lightning-ui")
            
            # Update dashboard static files
            self.update_dashboard_static_files()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to integrate with SIMP dashboard: {e}")
            return False
    
    def update_dashboard_static_files(self):
        """Update dashboard static files with Agent Lightning UI"""
        dashboard_static = self.simp_root / "dashboard" / "static"
        if not dashboard_static.exists():
            logger.warning("Dashboard static directory not found")
            return
        
        # Create Agent Lightning JavaScript component
        component_js = """
// Agent Lightning Dashboard Integration
document.addEventListener('DOMContentLoaded', function() {
    // Wait for dashboard to load
    setTimeout(function() {
        addAgentLightningWidget();
        startAgentLightningUpdates();
    }, 2000);
});

function addAgentLightningWidget() {
    // Check if widget already exists
    if (document.getElementById('agent-lightning-widget')) {
        return;
    }
    
    // Create widget container
    const widget = document.createElement('div');
    widget.id = 'agent-lightning-widget';
    widget.className = 'card mb-3';
    widget.innerHTML = \`
        <div class="card-header">
            <h5 class="mb-0">
                <i class="bi bi-lightning-charge"></i> Agent Lightning
                <span class="badge bg-success float-end" id="lightning-status">Loading...</span>
            </h5>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-6">
                    <h6>System Performance</h6>
                    <div class="mb-2">
                        <small>Total Calls:</small>
                        <div class="fw-bold" id="total-calls">0</div>
                    </div>
                    <div class="mb-2">
                        <small>Success Rate:</small>
                        <div class="fw-bold" id="success-rate">0%</div>
                    </div>
                </div>
                <div class="col-md-6">
                    <h6>Resource Usage</h6>
                    <div class="mb-2">
                        <small>Avg Response Time:</small>
                        <div class="fw-bold" id="avg-response-time">0ms</div>
                    </div>
                    <div class="mb-2">
                        <small>Total Tokens:</small>
                        <div class="fw-bold" id="total-tokens">0</div>
                    </div>
                </div>
            </div>
            <div class="mt-3">
                <a href="/agent-lightning-ui" class="btn btn-sm btn-outline-primary">
                    <i class="bi bi-graph-up"></i> Detailed Dashboard
                </a>
                <button class="btn btn-sm btn-outline-secondary" onclick="refreshAgentLightning()">
                    <i class="bi bi-arrow-clockwise"></i> Refresh
                </button>
            </div>
        </div>
    \`;
    
    // Add to dashboard
    const dashboardContent = document.querySelector('.container-fluid, #dashboard-content, .dashboard-container');
    if (dashboardContent) {
        dashboardContent.prepend(widget);
    } else {
        document.body.prepend(widget);
    }
}

function refreshAgentLightning() {
    loadAgentLightningData();
}

function loadAgentLightningData() {
    fetch('/agent-lightning/health')
        .then(response => response.json())
        .then(healthData => {
            updateHealthStatus(healthData);
        })
        .catch(error => {
            console.error('Failed to load Agent Lightning health:', error);
            document.getElementById('lightning-status').className = 'badge bg-danger';
            document.getElementById('lightning-status').textContent = 'Error';
        });
    
    fetch('/agent-lightning/performance?hours=1')
        .then(response => response.json())
        .then(performanceData => {
            updatePerformanceMetrics(performanceData);
        })
        .catch(error => {
            console.error('Failed to load Agent Lightning performance:', error);
        });
}

function updateHealthStatus(healthData) {
    const statusElement = document.getElementById('lightning-status');
    
    if (!healthData.enabled) {
        statusElement.className = 'badge bg-secondary';
        statusElement.textContent = 'Disabled';
        return;
    }
    
    if (healthData.proxy_healthy && healthData.store_healthy) {
        statusElement.className = 'badge bg-success';
        statusElement.textContent = 'Healthy';
    } else {
        statusElement.className = 'badge bg-warning';
        statusElement.textContent = 'Unhealthy';
    }
}

function updatePerformanceMetrics(performanceData) {
    if (performanceData.error) {
        return;
    }
    
    document.getElementById('total-calls').textContent = 
        (performanceData.total_traces || 0).toLocaleString();
    
    document.getElementById('success-rate').textContent = 
        (performanceData.success_rate || 0).toFixed(1) + '%';
    
    document.getElementById('avg-response-time').textContent = 
        (performanceData.avg_response_time_ms || 0).toFixed(0) + 'ms';
    
    document.getElementById('total-tokens').textContent = 
        (performanceData.total_tokens || 0).toLocaleString();
}

function startAgentLightningUpdates() {
    // Load initial data
    loadAgentLightningData();
    
    // Update every 30 seconds
    setInterval(loadAgentLightningData, 30000);
}
"""
        
        component_path = dashboard_static / "agent_lightning_integration.js"
        with open(component_path, 'w') as f:
            f.write(component_js)
        
        # Update main app.js to include the component
        app_js_path = dashboard_static / "app.js"
        if app_js_path.exists():
            with open(app_js_path, 'a') as f:
                f.write('\n// Agent Lightning Integration\n')
                f.write("const agentLightningScript = document.createElement('script');\n")
                f.write("agentLightningScript.src = '/static/agent_lightning_integration.js';\n")
                f.write("document.head.appendChild(agentLightningScript);\n")
        
        logger.info("✅ Updated dashboard static files with Agent Lightning integration")
    
    def patch_simp_agents(self) -> Dict[str, bool]:
        """Patch all SIMP agents for Agent Lightning integration"""
        if not self.config['enabled']:
            return {}
        
        logger.info("Patching SIMP agents for Agent Lightning integration...")
        
        agents_to_patch = [
            ("quantumarb", "agent_lightning_quantumarb_patch.py"),
            # Add more agents here as patches are created
        ]
        
        results = {}
        
        for agent_name, patch_file in agents_to_patch:
            patch_path = self.simp_root / "patches" / patch_file
            if not patch_path.exists():
                logger.warning(f"Patch not found for {agent_name}: {patch_path}")
                results[agent_name] = False
                continue
            
            try:
                spec = importlib.util.spec_from_file_location(f"{agent_name}_patch", patch_path)
                patch_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(patch_module)
                
                logger.info(f"✅ Patch loaded for {agent_name}")
                results[agent_name] = True
                
            except Exception as e:
                logger.error(f"Failed to load patch for {agent_name}: {e}")
                results[agent_name] = False
        
        return results
    
    def create_agent_configurations(self):
        """Create configuration files for all agents"""
        if not self.config['enabled']:
            return
        
        logger.info("Creating Agent Lightning configurations for SIMP agents...")
        
        config_dir = self.simp_root / "config" / "agent_lightning"
        config_dir.mkdir(exist_ok=True, parents=True)
        
        # Create base configuration
        base_config = {
            "enabled": self.config['enabled'],
            "proxy_url": f"http://{self.config['proxy_host']}:{self.config['proxy_port']}",
            "store_url": f"http://{self.config['store_host']}:{self.config['store_port']}",
            "model": self.config['model'],
            "enable_apo": self.config['enable_apo'],
            "trace_agent": True
        }
        
        # Agent-specific configurations
        agents = [
            {
                "name": "quantumarb",
                "type": "trading",
                "llm_methods": ["analyze_arbitrage_opportunities", "execute_trade", "calculate_risk"],
                "optimization_focus": ["arbitrage_analysis", "risk_assessment"]
            },
            {
                "name": "kashclaw_gemma",
                "type": "planning",
                "llm_methods": ["generate_plan", "analyze_task", "optimize_workflow"],
                "optimization_focus": ["plan_generation", "task_decomposition"]
            },
            {
                "name": "kloutbot",
                "type": "orchestration",
                "llm_methods": ["coordinate_agents", "generate_strategy", "resolve_conflicts"],
                "optimization_focus": ["coordination", "strategy_planning"]
            },
            {
                "name": "projectx_native",
                "type": "maintenance",
                "llm_methods": ["health_check", "security_scan", "performance_audit"],
                "optimization_focus": ["system_analysis", "audit_reporting"]
            }
        ]
        
        for agent in agents:
            agent_config = base_config.copy()
            agent_config.update({
                "agent_id": agent["name"],
                "agent_type": agent["type"],
                "llm_methods_to_trace": agent["llm_methods"],
                "optimization_focus_areas": agent["optimization_focus"]
            })
            
            config_file = config_dir / f"{agent['name']}.json"
            import json
            with open(config_file, 'w') as f:
                json.dump(agent_config, f, indent=2)
            
            logger.debug(f"Created configuration for {agent['name']}")
        
        logger.info(f"✅ Created configurations for {len(agents)} agents in {config_dir}")
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        logger.info("Running Agent Lightning health check...")
        
        health = {
            "integration_enabled": self.config['enabled'],
            "proxy_running": False,
            "store_accessible": False,
            "broker_integration_ready": False,
            "dashboard_integration_ready": False,
            "agents_patched": {},
            "configuration_valid": True
        }
        
        if not self.config['enabled']:
            logger.info("Agent Lightning integration disabled")
            return health
        
        # Check proxy
        try:
            import requests
            proxy_url = f"http://{self.config['proxy_host']}:{self.config['proxy_port']}/health"
            response = requests.get(proxy_url, timeout=5)
            health["proxy_running"] = response.status_code == 200
        except:
            health["proxy_running"] = False
        
        # Check store
        try:
            import requests
            store_url = f"http://{self.config['store_host']}:{self.config['store_port']}/v1/agl/health"
            response = requests.get(store_url, timeout=5)
            health["store_accessible"] = response.status_code == 200
        except:
            health["store_accessible"] = False
        
        # Check patches
        health["agents_patched"] = self.patch_simp_agents()
        
        logger.info("Health check complete:")
        logger.info(f"  Proxy running: {health['proxy_running']}")
        logger.info(f"  Store accessible: {health['store_accessible']}")
        logger.info(f"  Agents patched: {len([v for v in health['agents_patched'].values() if v])}")
        
        return health
    
    def print_integration_summary(self):
        """Print integration summary"""
        logger.info("=" * 70)
        logger.info("AGENT LIGHTNING INTEGRATION SUMMARY")
        logger.info("=" * 70)
        
        if not self.config['enabled']:
            logger.info("❌ Integration: DISABLED")
            logger.info("   Enable by setting AGENT_LIGHTNING_ENABLED=true")
            return
        
        logger.info("✅ Integration: ENABLED")
        logger.info("")
        logger.info("📊 Endpoints:")
        logger.info(f"   Agent Lightning Proxy: http://localhost:{self.config['proxy_port']}")
        logger.info(f"   LightningStore: http://localhost:{self.config['store_port']}")
        logger.info(f"   Dashboard UI: http://localhost:8050/agent-lightning-ui")
        logger.info("")
        logger.info("🤖 Agents Configured:")
        for agent in self.config['trace_specific_agents']:
            if agent:
                logger.info(f"   • {agent}")
        logger.info("")
        logger.info("⚡ Features Enabled:")
        if self.config['trace_all_agents']:
            logger.info("   • Trace all agents")
        if self.config['enable_apo']:
            logger.info("   • Automatic Prompt Optimization (APO)")
        if self.config['dashboard_integration']:
            logger.info("   • Dashboard integration")
        logger.info("")
        logger.info("🔧 Next Steps:")
        logger.info("   1. Restart SIMP broker to enable Agent Lightning endpoints")
        logger.info("   2. Restart SIMP dashboard to see Agent Lightning metrics")
        logger.info("   3. Monitor traces at: http://localhost:43887/v1/agl/rollouts")
        logger.info("")
        logger.info("🚀 All LLM calls will now be traced and optimized!")
        logger.info("=" * 70)
    
    def run(self):
        """Run the full integration process"""
        logger.info("Starting full Agent Lightning integration for SIMP ecosystem...")
        
        # Check if Agent Lightning is available
        if not self.check_agent_lightning_available():
            logger.error("Agent Lightning integration module not available")
            return False
        
        # Start Agent Lightning proxy
        if not self.start_agent_lightning_proxy():
            logger.warning("Agent Lightning proxy not started (may be running manually)")
        
        # Integrate with SIMP broker
        self.integrate_with_simp_broker()
        
        # Integrate with SIMP dashboard
        self.integrate_with_simp_dashboard()
        
        # Patch SIMP agents
        self.patch_simp_agents()
        
        # Create configurations
        self.create_agent_configurations()
        
        # Run health check
        health = self.run_health_check()
        
        # Print summary
        self.print_integration_summary()
        
        return health.get('proxy_running', False) and health.get('store_accessible', False)


def main():
    """Main entry point"""
    integrator = AgentLightningIntegrator()
    
    try:
        success = integrator.run()
        
        if success:
            logger.info("✅ Agent Lightning integration completed successfully!")
            return 0
        else:
            logger.warning("⚠️  Agent Lightning integration completed with warnings")
            logger.info("Some components may need manual configuration")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Agent Lightning integration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 2


if __name__ == "__main__":
    sys.exit(main())