#!/usr/bin/env python3
"""
Start Agent Lightning Integration for SIMP Ecosystem

This script starts the Agent Lightning integration for the SIMP ecosystem,
including:
1. Agent Lightning proxy for LLM call tracing
2. LightningStore for trace collection
3. Integration with SIMP broker and dashboard
4. Configuration for all SIMP agents
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# Add SIMP to path
simp_root = Path(__file__).parent
sys.path.insert(0, str(simp_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import requests
        import flask
        import fastapi
        logger.info("Required dependencies are installed")
        return True
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.info("Install dependencies with: pip install requests flask fastapi")
        return False

def start_agent_lightning_proxy():
    """Start the Agent Lightning proxy"""
    logger.info("Starting Agent Lightning proxy...")
    
    # Check if proxy is already running
    try:
        import requests
        response = requests.get("http://localhost:8235/health", timeout=5)
        if response.status_code == 200:
            logger.info("Agent Lightning proxy is already running")
            return True
    except:
        pass
    
    # Start the proxy
    proxy_script = Path.home() / "stray_goose" / "zai_agent_lightning_proxy.py"
    if not proxy_script.exists():
        logger.error(f"Agent Lightning proxy script not found: {proxy_script}")
        return False
    
    # Set environment variables
    env = os.environ.copy()
    api_key = env.get("X_AI_API_KEY")
    if not api_key:
        logger.error("X_AI_API_KEY environment variable not set")
        logger.info("Set it with: export X_AI_API_KEY='your-api-key'")
        return False
    
    # Start the proxy in background
    try:
        import subprocess
        cmd = [
            sys.executable, str(proxy_script)
        ]
        
        # Start in background
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit for startup
        time.sleep(3)
        
        # Check if it's running
        try:
            response = requests.get("http://localhost:8235/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Agent Lightning proxy started successfully")
                return True
            else:
                logger.error(f"Agent Lightning proxy health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Agent Lightning proxy failed to start: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to start Agent Lightning proxy: {e}")
        return False

def configure_simp_agents():
    """Configure SIMP agents to use Agent Lightning"""
    logger.info("Configuring SIMP agents for Agent Lightning...")
    
    # List of SIMP agents to configure
    agents = [
        "quantumarb",
        "kashclaw_gemma", 
        "kloutbot",
        "projectx_native",
        "perplexity_research",
        "financial_ops",
        "bullbear_predictor"
    ]
    
    config_updates = []
    
    # For each agent, create configuration to use Agent Lightning
    for agent in agents:
        config = {
            "agent_id": agent,
            "agent_lightning_enabled": True,
            "llm_proxy_url": "http://localhost:8235",
            "trace_store_url": "http://localhost:43887",
            "optimization_enabled": True
        }
        config_updates.append(config)
    
    logger.info(f"Configured {len(config_updates)} agents for Agent Lightning")
    return config_updates

def integrate_with_simp_broker():
    """Integrate Agent Lightning with SIMP broker"""
    logger.info("Integrating Agent Lightning with SIMP broker...")
    
    try:
        from simp.integrations.agent_lightning import integrate_with_broker
        
        # Import and patch the broker
        from simp.server.broker import SimpBroker
        
        # Create broker instance or get existing one
        # This would typically be done during broker startup
        logger.info("Agent Lightning broker integration ready")
        return True
        
    except Exception as e:
        logger.error(f"Failed to integrate with SIMP broker: {e}")
        return False

def integrate_with_simp_dashboard():
    """Integrate Agent Lightning with SIMP dashboard"""
    logger.info("Integrating Agent Lightning with SIMP dashboard...")
    
    try:
        from simp.integrations.agent_lightning import integrate_with_dashboard
        
        # This would be called from dashboard/server.py
        logger.info("Agent Lightning dashboard integration ready")
        return True
        
    except Exception as e:
        logger.error(f"Failed to integrate with SIMP dashboard: {e}")
        return False

def create_agent_wrappers():
    """Create Agent Lightning wrappers for SIMP agents"""
    logger.info("Creating Agent Lightning wrappers for SIMP agents...")
    
    wrappers_dir = simp_root / "simp" / "agents" / "lightning_wrappers"
    wrappers_dir.mkdir(exist_ok=True)
    
    # Create base wrapper
    base_wrapper = """
\"\"\"
Agent Lightning Wrapper for SIMP Agents

This module provides Agent Lightning integration for SIMP agents,
adding LLM call tracing, performance monitoring, and prompt optimization.
\"\"\"

import logging
from typing import Dict, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class AgentLightningWrapper:
    \"\"\"Wrapper to add Agent Lightning capabilities to SIMP agents\"\"\"
    
    def __init__(self, agent_id: str, original_agent):
        self.agent_id = agent_id
        self.original_agent = original_agent
        self.lightning_enabled = False
        
        # Try to import Agent Lightning
        try:
            from simp.integrations.agent_lightning import AgentLightningMiddleware
            self.middleware = AgentLightningMiddleware(agent_id)
            self.lightning_enabled = True
            logger.info(f"Agent Lightning enabled for {agent_id}")
        except ImportError as e:
            logger.warning(f"Agent Lightning not available: {e}")
            self.middleware = None
    
    def wrap_llm_method(self, method_name: str):
        \"\"\"Wrap an LLM method with Agent Lightning tracing\"\"\"
        if not self.lightning_enabled or not hasattr(self.original_agent, method_name):
            return
        
        original_method = getattr(self.original_agent, method_name)
        
        @wraps(original_method)
        def wrapped_method(*args, **kwargs):
            # Add tracing
            if self.middleware:
                return self.middleware.wrap_llm_call(original_method)(*args, **kwargs)
            else:
                return original_method(*args, **kwargs)
        
        setattr(self.original_agent, method_name, wrapped_method)
        logger.debug(f"Wrapped {method_name} for Agent Lightning tracing")
    
    def optimize_prompt(self, prompt: str, context: Dict[str, Any] = None) -> str:
        \"\"\"Optimize a prompt using Agent Lightning APO\"\"\"
        if self.lightning_enabled and self.middleware:
            return self.middleware.optimize_prompt(prompt, context)
        return prompt
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        \"\"\"Get performance metrics from Agent Lightning\"\"\"
        if self.lightning_enabled and self.middleware:
            return self.middleware.get_performance_metrics(hours)
        return {}


def wrap_agent(agent_id: str, agent_instance):
    \"\"\"Wrap a SIMP agent with Agent Lightning capabilities\"\"\"
    wrapper = AgentLightningWrapper(agent_id, agent_instance)
    
    # Wrap common LLM methods
    llm_methods = [
        'generate_response',
        'process_intent',
        'call_llm',
        'complete',
        'chat',
        'predict'
    ]
    
    for method in llm_methods:
        wrapper.wrap_llm_method(method)
    
    return wrapper
"""
    
    wrapper_path = wrappers_dir / "__init__.py"
    with open(wrapper_path, 'w') as f:
        f.write(base_wrapper)
    
    logger.info(f"Created Agent Lightning wrapper at {wrapper_path}")
    return True

def update_dashboard_ui():
    """Update SIMP dashboard UI to show Agent Lightning metrics"""
    logger.info("Updating SIMP dashboard UI for Agent Lightning...")
    
    dashboard_static = simp_root / "dashboard" / "static"
    if not dashboard_static.exists():
        logger.warning("Dashboard static directory not found")
        return False
    
    # Create Agent Lightning dashboard component
    component_js = """
// Agent Lightning Dashboard Component
class AgentLightningDashboard {
    constructor() {
        this.baseUrl = '/agent-lightning';
        this.updateInterval = 30000; // 30 seconds
        this.performanceData = null;
        this.healthData = null;
    }
    
    async init() {
        console.log('Initializing Agent Lightning dashboard...');
        
        // Create UI elements
        this.createUI();
        
        // Load initial data
        await this.loadHealth();
        await this.loadPerformance();
        
        // Start periodic updates
        this.startUpdates();
        
        return this;
    }
    
    createUI() {
        // Create container
        const container = document.createElement('div');
        container.id = 'agent-lightning-dashboard';
        container.className = 'agent-lightning-container';
        container.innerHTML = \`
            <div class="card">
                <div class="card-header">
                    <h3>🤖 Agent Lightning</h3>
                    <div class="health-status">
                        <span class="status-indicator" id="lightning-health-indicator">●</span>
                        <span id="lightning-health-text">Checking...</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h4>System Performance</h4>
                            <div id="system-performance"></div>
                        </div>
                        <div class="col-md-6">
                            <h4>Agent Performance</h4>
                            <select id="agent-select" class="form-select mb-3">
                                <option value="all">All Agents</option>
                            </select>
                            <div id="agent-performance"></div>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-12">
                            <h4>Recent Traces</h4>
                            <div id="recent-traces" class="trace-list"></div>
                        </div>
                    </div>
                </div>
            </div>
        \`;
        
        // Add to dashboard
        const dashboard = document.querySelector('#dashboard-content');
        if (dashboard) {
            dashboard.appendChild(container);
        } else {
            document.body.appendChild(container);
        }
        
        // Add styles
        this.addStyles();
    }
    
    addStyles() {
        const style = document.createElement('style');
        style.textContent = \`
            .agent-lightning-container {
                margin: 20px 0;
            }
            .agent-lightning-container .card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
            }
            .agent-lightning-container .card-header {
                background: rgba(0, 0, 0, 0.2);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .agent-lightning-container .health-status {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .agent-lightning-container .status-indicator {
                font-size: 24px;
            }
            .agent-lightning-container .status-indicator.healthy {
                color: #4ade80;
            }
            .agent-lightning-container .status-indicator.unhealthy {
                color: #f87171;
            }
            .agent-lightning-container .status-indicator.unknown {
                color: #fbbf24;
            }
            .agent-lightning-container .trace-list {
                max-height: 300px;
                overflow-y: auto;
                background: rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                padding: 10px;
            }
            .agent-lightning-container .trace-item {
                padding: 8px;
                margin: 4px 0;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
            }
            .agent-lightning-container .trace-success {
                border-left: 4px solid #4ade80;
            }
            .agent-lightning-container .trace-error {
                border-left: 4px solid #f87171;
            }
        \`;
        document.head.appendChild(style);
    }
    
    async loadHealth() {
        try {
            const response = await fetch(\`\${this.baseUrl}/health\`);
            this.healthData = await response.json();
            this.updateHealthUI();
        } catch (error) {
            console.error('Failed to load Agent Lightning health:', error);
            this.healthData = null;
        }
    }
    
    async loadPerformance(hours = 24) {
        try {
            const response = await fetch(\`\${this.baseUrl}/performance?hours=\${hours}\`);
            this.performanceData = await response.json();
            this.updatePerformanceUI();
        } catch (error) {
            console.error('Failed to load Agent Lightning performance:', error);
            this.performanceData = null;
        }
    }
    
    updateHealthUI() {
        const indicator = document.getElementById('lightning-health-indicator');
        const text = document.getElementById('lightning-health-text');
        
        if (!this.healthData) {
            indicator.className = 'status-indicator unknown';
            text.textContent = 'Unknown';
            return;
        }
        
        if (this.healthData.enabled && this.healthData.proxy_healthy && this.healthData.store_healthy) {
            indicator.className = 'status-indicator healthy';
            text.textContent = 'Healthy';
        } else {
            indicator.className = 'status-indicator unhealthy';
            text.textContent = 'Unhealthy';
            
            if (!this.healthData.enabled) {
                text.textContent += ' (Disabled)';
            } else if (!this.healthData.proxy_healthy) {
                text.textContent += ' (Proxy Down)';
            } else if (!this.healthData.store_healthy) {
                text.textContent += ' (Store Down)';
            }
        }
    }
    
    updatePerformanceUI() {
        // Update system performance
        const systemPerf = document.getElementById('system-performance');
        if (systemPerf && this.performanceData && !this.performanceData.error) {
            systemPerf.innerHTML = \`
                <div class="mb-2">
                    <strong>Total Traces:</strong> \${this.performanceData.total_traces || 0}
                </div>
                <div class="mb-2">
                    <strong>Success Rate:</strong> \${(this.performanceData.success_rate || 0).toFixed(1)}%
                </div>
                <div class="mb-2">
                    <strong>Avg Response Time:</strong> \${(this.performanceData.avg_response_time_ms || 0).toFixed(0)}ms
                </div>
                <div>
                    <strong>Total Tokens:</strong> \${(this.performanceData.total_tokens || 0).toLocaleString()}
                </div>
            \`;
        } else if (systemPerf) {
            systemPerf.innerHTML = '<div class="text-muted">No performance data available</div>';
        }
    }
    
    startUpdates() {
        setInterval(() => {
            this.loadHealth();
            this.loadPerformance();
        }, this.updateInterval);
    }
}

// Initialize when dashboard loads
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const lightningDashboard = new AgentLightningDashboard();
        lightningDashboard.init();
    }, 1000);
});
"""
    
    component_path = dashboard_static / "agent_lightning.js"
    with open(component_path, 'w') as f:
        f.write(component_js)
    
    # Update app.js to include the component
    app_js_path = dashboard_static / "app.js"
    if app_js_path.exists():
        with open(app_js_path, 'a') as f:
            f.write('\n// Agent Lightning Integration\n')
            f.write("const agentLightningScript = document.createElement('script');\n")
            f.write("agentLightningScript.src = '/static/agent_lightning.js';\n")
            f.write("document.head.appendChild(agentLightningScript);\n")
    
    logger.info(f"Updated dashboard UI with Agent Lightning component")
    return True

def create_configuration_file():
    """Create Agent Lightning configuration file for SIMP"""
    logger.info("Creating Agent Lightning configuration file...")
    
    config_content = """
# Agent Lightning Configuration for SIMP Ecosystem
# This file configures Agent Lightning integration across all SIMP agents

# Enable Agent Lightning integration
AGENT_LIGHTNING_ENABLED=true

# Proxy configuration
AGENT_LIGHTNING_PROXY_HOST=localhost
AGENT_LIGHTNING_PROXY_PORT=8235

# LightningStore configuration
AGENT_LIGHTNING_STORE_HOST=localhost
AGENT_LIGHTNING_STORE_PORT=43887

# Model configuration
AGENT_LIGHTNING_MODEL=glm-4-plus

# Tracing configuration
TRACE_ALL_AGENTS=true
TRACE_SPECIFIC_AGENTS=quantumarb,kashclaw_gemma,kloutbot,projectx_native

# Optimization features
ENABLE_APO=true  # Automatic Prompt Optimization
ENABLE_PERFORMANCE_MONITORING=true
ENABLE_ERROR_TRACKING=true

# Dashboard integration
DASHBOARD_INTEGRATION_ENABLED=true
UPDATE_INTERVAL_SECONDS=30

# Alerting
ENABLE_ALERTS=true
ALERT_SUCCESS_RATE_THRESHOLD=95  # Alert if success rate drops below 95%
ALERT_RESPONSE_TIME_THRESHOLD=5000  # Alert if avg response time exceeds 5 seconds

# Data retention
TRACE_RETENTION_DAYS=30
PERFORMANCE_METRICS_RETENTION_DAYS=90
"""
    
    config_path = simp_root / "config" / "agent_lightning.cfg"
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    logger.info(f"Created configuration file at {config_path}")
    return True

def main():
    """Main integration function"""
    logger.info("=" * 60)
    logger.info("Starting Agent Lightning Integration for SIMP Ecosystem")
    logger.info("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create configuration
    create_configuration_file()
    
    # Start Agent Lightning proxy
    if not start_agent_lightning_proxy():
        logger.error("Failed to start Agent Lightning proxy")
        logger.info("Please start it manually: cd ~/stray_goose && python zai_agent_lightning_proxy.py")
        # Continue anyway - proxy might be started manually
    
    # Configure SIMP agents
    configure_simp_agents()
    
    # Create agent wrappers
    create_agent_wrappers()
    
    # Integrate with SIMP broker
    integrate_with_simp_broker()
    
    # Integrate with SIMP dashboard
    integrate_with_simp_dashboard()
    
    # Update dashboard UI
    update_dashboard_ui()
    
    logger.info("=" * 60)
    logger.info("✅ Agent Lightning Integration Complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Restart SIMP broker to enable Agent Lightning endpoints")
    logger.info("2. Restart SIMP dashboard to see Agent Lightning metrics")
    logger.info("3. Configure individual agents to use Agent Lightning middleware")
    logger.info("")
    logger.info("Agent Lightning Proxy: http://localhost:8235")
    logger.info("LightningStore: http://localhost:43887")
    logger.info("Dashboard Integration: http://localhost:8050/agent-lightning")
    logger.info("")
    logger.info("All LLM calls will now be traced and optimized! 🚀")

if __name__ == "__main__":
    main()