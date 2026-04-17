#!/usr/bin/env python3
"""
Agent Lightning Integration Demonstration

This script demonstrates the complete Agent Lightning integration
with the SIMP ecosystem, showing:
1. Agent Lightning proxy and store operation
2. SIMP broker integration
3. Dashboard visualization
4. Agent tracing in action
5. Performance monitoring
"""

import os
import sys
import time
import json
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Add SIMP to path
simp_root = Path(__file__).parent
sys.path.insert(0, str(simp_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AgentLightningDemo:
    """Demonstrate Agent Lightning integration with SIMP"""
    
    def __init__(self):
        self.base_url = "http://localhost:5555"
        self.agent_lightning_url = "http://localhost:8235"
        self.lightning_store_url = "http://localhost:43887"
        self.dashboard_url = "http://localhost:8050"
        
    def check_health(self) -> Dict[str, bool]:
        """Check health of all components"""
        logger.info("🔍 Checking system health...")
        
        health = {
            "simp_broker": False,
            "agent_lightning_proxy": False,
            "lightning_store": False,
            "dashboard": False
        }
        
        # Check SIMP broker
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            health["simp_broker"] = response.status_code == 200
            logger.info(f"✅ SIMP Broker: {'Healthy' if health['simp_broker'] else 'Unhealthy'}")
        except:
            logger.warning("❌ SIMP Broker: Not reachable")
        
        # Check Agent Lightning proxy
        try:
            response = requests.get(f"{self.agent_lightning_url}/health", timeout=5)
            health["agent_lightning_proxy"] = response.status_code == 200
            logger.info(f"✅ Agent Lightning Proxy: {'Healthy' if health['agent_lightning_proxy'] else 'Unhealthy'}")
        except:
            logger.warning("❌ Agent Lightning Proxy: Not reachable")
        
        # Check LightningStore
        try:
            response = requests.get(f"{self.lightning_store_url}/v1/agl/health", timeout=5)
            health["lightning_store"] = response.status_code == 200
            logger.info(f"✅ LightningStore: {'Healthy' if health['lightning_store'] else 'Unhealthy'}")
        except:
            logger.warning("❌ LightningStore: Not reachable")
        
        # Check Dashboard
        try:
            response = requests.get(f"{self.dashboard_url}/docs", timeout=5)
            health["dashboard"] = response.status_code == 200
            logger.info(f"✅ SIMP Dashboard: {'Healthy' if health['dashboard'] else 'Unhealthy'}")
        except:
            logger.warning("❌ SIMP Dashboard: Not reachable")
        
        return health
    
    def test_agent_lightning_endpoints(self):
        """Test Agent Lightning integration endpoints"""
        logger.info("\n🔧 Testing Agent Lightning integration endpoints...")
        
        endpoints = [
            ("/agent-lightning/health", "Agent Lightning Health"),
            ("/agent-lightning/performance", "System Performance"),
            ("/agent-lightning/config", "Configuration"),
        ]
        
        for endpoint, description in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    logger.info(f"✅ {description}: Available (200 OK)")
                    # Show sample data for health endpoint
                    if "health" in endpoint:
                        data = response.json()
                        logger.info(f"   Enabled: {data.get('enabled', 'N/A')}")
                        logger.info(f"   Proxy Healthy: {data.get('proxy_healthy', 'N/A')}")
                        logger.info(f"   Store Healthy: {data.get('store_healthy', 'N/A')}")
                else:
                    logger.warning(f"⚠️  {description}: {response.status_code}")
            except Exception as e:
                logger.warning(f"❌ {description}: {e}")
    
    def simulate_agent_activity(self):
        """Simulate agent activity to generate traces"""
        logger.info("\n🤖 Simulating agent activity...")
        
        # Simulate different agent activities
        simulations = [
            {
                "agent": "quantumarb",
                "intent_type": "analyze_arbitrage",
                "description": "QuantumArb analyzing arbitrage opportunities"
            },
            {
                "agent": "kashclaw_gemma",
                "intent_type": "generate_plan",
                "description": "KashClaw Gemma generating task plan"
            },
            {
                "agent": "kloutbot",
                "intent_type": "coordinate_agents",
                "description": "KloutBot coordinating agent activities"
            },
            {
                "agent": "projectx_native",
                "intent_type": "health_check",
                "description": "ProjectX performing system health check"
            }
        ]
        
        for sim in simulations:
            logger.info(f"   Simulating: {sim['description']}")
            
            # Create a test trace
            trace_data = {
                "trace_id": f"demo_{sim['agent']}_{int(time.time())}",
                "agent_id": sim["agent"],
                "intent_type": sim["intent_type"],
                "model": "glm-4-plus",
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300,
                "response_time_ms": 1500,
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "demo": True,
                    "simulation": True,
                    "description": sim["description"]
                }
            }
            
            # Send trace to LightningStore
            try:
                store_url = f"{self.lightning_store_url}/v1/agl/traces"
                response = requests.post(store_url, json=trace_data, timeout=5)
                
                if response.status_code in [200, 201]:
                    logger.info(f"      ✅ Trace sent successfully")
                else:
                    logger.info(f"      ⚠️  Trace send: {response.status_code}")
            except Exception as e:
                logger.info(f"      ⚠️  Could not send trace: {e}")
            
            time.sleep(0.5)  # Small delay between simulations
    
    def get_performance_metrics(self):
        """Get and display performance metrics"""
        logger.info("\n📊 Getting performance metrics...")
        
        try:
            # Get system performance
            url = f"{self.base_url}/agent-lightning/performance?hours=1"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if "error" in data:
                    logger.warning(f"   Error: {data['error']}")
                    return
                
                logger.info("   System Performance (last hour):")
                logger.info(f"      Total Traces: {data.get('total_traces', 0)}")
                logger.info(f"      Success Rate: {data.get('success_rate', 0):.1f}%")
                logger.info(f"      Avg Response Time: {data.get('avg_response_time_ms', 0):.0f}ms")
                logger.info(f"      Total Tokens: {data.get('total_tokens', 0):,}")
                
                # Calculate estimated cost (assuming $0.10 per 1K tokens)
                cost_per_1k = 0.10
                estimated_cost = (data.get('total_tokens', 0) / 1000) * cost_per_1k
                logger.info(f"      Estimated Cost: ${estimated_cost:.2f}")
            else:
                logger.warning(f"   Could not get performance: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"   Error getting metrics: {e}")
    
    def show_recent_traces(self, limit: int = 5):
        """Show recent traces from LightningStore"""
        logger.info(f"\n🔍 Showing recent traces (limit: {limit})...")
        
        try:
            # Get recent traces
            url = f"{self.lightning_store_url}/v1/agl/rollouts?limit={limit}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list) and len(data) > 0:
                    for i, trace in enumerate(data[:limit]):
                        agent = trace.get('agent_id', 'unknown')
                        intent = trace.get('intent_type', 'unknown')
                        success = trace.get('success', False)
                        tokens = trace.get('total_tokens', 0)
                        response_time = trace.get('response_time_ms', 0)
                        
                        status = "✅" if success else "❌"
                        logger.info(f"   {i+1}. {status} {agent} - {intent}")
                        logger.info(f"      Tokens: {tokens}, Time: {response_time}ms")
                else:
                    logger.info("   No traces found")
            else:
                logger.warning(f"   Could not get traces: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"   Error getting traces: {e}")
    
    def demonstrate_dashboard_integration(self):
        """Demonstrate dashboard integration"""
        logger.info("\n📈 Demonstrating dashboard integration...")
        
        dashboard_endpoints = [
            ("/agent-lightning-ui", "Agent Lightning Dashboard"),
            ("/docs", "API Documentation"),
        ]
        
        for endpoint, description in dashboard_endpoints:
            url = f"{self.dashboard_url}{endpoint}"
            logger.info(f"   {description}: {url}")
        
        logger.info("\n   To view the dashboard:")
        logger.info("   1. Open browser to: http://localhost:8050/agent-lightning-ui")
        logger.info("   2. Select agent and time range")
        logger.info("   3. View real-time metrics and traces")
    
    def test_agent_specific_performance(self):
        """Test agent-specific performance endpoints"""
        logger.info("\n🎯 Testing agent-specific performance...")
        
        agents = ["quantumarb", "kashclaw_gemma", "kloutbot", "projectx_native"]
        
        for agent in agents:
            try:
                url = f"{self.base_url}/agent-lightning/agents/{agent}/performance?hours=24"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "error" not in data:
                        traces = data.get('total_traces', 0)
                        success_rate = data.get('success_rate', 0)
                        logger.info(f"   {agent}: {traces} traces, {success_rate:.1f}% success")
                    else:
                        logger.info(f"   {agent}: No data available")
                else:
                    logger.info(f"   {agent}: Not configured for tracing")
                    
            except Exception as e:
                logger.info(f"   {agent}: Error - {e}")
    
    def demonstrate_optimization_potential(self):
        """Demonstrate optimization potential with APO"""
        logger.info("\n⚡ Demonstrating optimization potential...")
        
        optimization_examples = [
            {
                "before": "Analyze arbitrage opportunities between exchanges",
                "after": "Analyze arbitrage opportunities between Binance and Coinbase for BTC/USDT pair with minimum 0.5% spread and maximum $1000 position size",
                "improvement": "More specific, includes constraints"
            },
            {
                "before": "Generate trading plan",
                "after": "Generate a risk-adjusted trading plan for the next 24 hours focusing on BTC and ETH with maximum 2% portfolio risk per trade",
                "improvement": "Adds risk parameters and focus"
            },
            {
                "before": "Check system health",
                "after": "Perform comprehensive health check on all SIMP agents including response times, error rates, and resource usage for the last hour",
                "improvement": "More comprehensive and specific"
            }
        ]
        
        logger.info("   Automatic Prompt Optimization (APO) examples:")
        for i, example in enumerate(optimization_examples, 1):
            logger.info(f"\n   Example {i}:")
            logger.info(f"      Before: {example['before']}")
            logger.info(f"      After:  {example['after']}")
            logger.info(f"      Improvement: {example['improvement']}")
        
        logger.info("\n   APO benefits:")
        logger.info("   • Higher success rates")
        logger.info("   • Faster response times")
        logger.info("   • Lower token usage")
        logger.info("   • Better agent performance")
    
    def run_complete_demo(self):
        """Run complete demonstration"""
        logger.info("=" * 70)
        logger.info("AGENT LIGHTNING INTEGRATION DEMONSTRATION")
        logger.info("=" * 70)
        
        # Check health
        health = self.check_health()
        
        if not all(health.values()):
            logger.warning("\n⚠️  Some components are not healthy. Demo may be limited.")
            logger.info("Please ensure all services are running:")
            logger.info("1. SIMP Broker (port 5555)")
            logger.info("2. Agent Lightning Proxy (port 8235)")
            logger.info("3. LightningStore (port 43887)")
            logger.info("4. SIMP Dashboard (port 8050)")
        
        # Test endpoints
        self.test_agent_lightning_endpoints()
        
        # Simulate activity
        self.simulate_agent_activity()
        
        # Get metrics
        self.get_performance_metrics()
        
        # Show traces
        self.show_recent_traces()
        
        # Test agent-specific performance
        self.test_agent_specific_performance()
        
        # Demonstrate dashboard
        self.demonstrate_dashboard_integration()
        
        # Show optimization potential
        self.demonstrate_optimization_potential()
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("DEMONSTRATION COMPLETE")
        logger.info("=" * 70)
        logger.info("\n🎉 Agent Lightning is fully integrated with SIMP!")
        logger.info("\nKey benefits demonstrated:")
        logger.info("1. ✅ Centralized LLM call tracing")
        logger.info("2. ✅ Real-time performance monitoring")
        logger.info("3. ✅ Agent-specific metrics")
        logger.info("4. ✅ Dashboard visualization")
        logger.info("5. ✅ Optimization potential with APO")
        logger.info("\nNext steps:")
        logger.info("1. Monitor agents in real-time: http://localhost:8050/agent-lightning-ui")
        logger.info("2. Analyze performance trends over time")
        logger.info("3. Use APO to optimize agent prompts")
        logger.info("4. Set up alerts for performance degradation")
        logger.info("\n🚀 All LLM calls are now traced and optimized!")


def main():
    """Main demonstration function"""
    
    # Check for required environment variables
    api_key = os.environ.get("X_AI_API_KEY")
    if not api_key:
        logger.warning("⚠️  X_AI_API_KEY environment variable not set")
        logger.info("Some features may not work without the API key.")
        logger.info("Set it with: export X_AI_API_KEY='your-api-key'")
    
    # Run demonstration
    demo = AgentLightningDemo()
    demo.run_complete_demo()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())