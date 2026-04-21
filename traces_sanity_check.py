#!/usr/bin/env python3
"""
Traces Sanity Check for Agent Lightning Integration

Goal: Prove traces really match reality and nothing critical is missing.
Check QuantumArb, BullBear, and Perplexity Research agents.
"""

import os
import sys
import json
import time
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple
import uuid

# Add SIMP to path
simp_root = Path(__file__).parent
sys.path.insert(0, str(simp_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TracesSanityCheck:
    """Comprehensive sanity check for Agent Lightning traces"""
    
    def __init__(self):
        self.base_url = "http://localhost:5555"
        self.lightning_store_url = "http://localhost:43887"
        self.task_ledger_path = simp_root / "data" / "task_ledger.jsonl"
        
        # Test tasks for each agent
        self.test_tasks = {
            "quantumarb": [
                {
                    "name": "Analyze BTC arbitrage",
                    "intent_type": "analyze_arbitrage",
                    "params": {
                        "asset": "BTC",
                        "exchanges": ["binance", "coinbase"],
                        "min_spread": 0.5
                    }
                },
                {
                    "name": "Check market conditions",
                    "intent_type": "market_analysis",
                    "params": {
                        "assets": ["BTC", "ETH"],
                        "timeframe": "1h"
                    }
                }
            ],
            "bullbear_predictor": [
                {
                    "name": "Generate BTC signal",
                    "intent_type": "generate_signal",
                    "params": {
                        "asset": "BTC",
                        "timeframe": "4h",
                        "confidence_threshold": 0.7
                    }
                },
                {
                    "name": "Analyze market sentiment",
                    "intent_type": "sentiment_analysis",
                    "params": {
                        "assets": ["BTC", "ETH", "SOL"],
                        "sources": ["twitter", "reddit"]
                    }
                }
            ],
            "perplexity_research": [
                {
                    "name": "Research DeFi trends",
                    "intent_type": "research_topic",
                    "params": {
                        "topic": "DeFi yield farming trends 2024",
                        "depth": "medium"
                    }
                },
                {
                    "name": "Analyze crypto regulation",
                    "intent_type": "analysis",
                    "params": {
                        "topic": "crypto regulation impact on arbitrage",
                        "perspective": "trading"
                    }
                }
            ]
        }
        
        # Track test results
        self.results = {
            "quantumarb": {"tasks": [], "passed": 0, "failed": 0},
            "bullbear_predictor": {"tasks": [], "passed": 0, "failed": 0},
            "perplexity_research": {"tasks": [], "passed": 0, "failed": 0}
        }
        
        # Store generated intent IDs for verification
        self.generated_intent_ids = []
    
    def check_system_health(self) -> bool:
        """Check if all systems are healthy"""
        logger.info("🔍 Checking system health...")
        
        systems = [
            ("SIMP Broker", f"{self.base_url}/health"),
            ("Agent Lightning Proxy", "http://localhost:8235/health"),
            ("LightningStore", f"{self.lightning_store_url}/v1/agl/health"),
        ]
        
        all_healthy = True
        for name, url in systems:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    logger.info(f"✅ {name}: Healthy")
                else:
                    logger.error(f"❌ {name}: Unhealthy ({response.status_code})")
                    all_healthy = False
            except Exception as e:
                logger.error(f"❌ {name}: Not reachable ({e})")
                all_healthy = False
        
        return all_healthy
    
    def trigger_test_task(self, agent_id: str, task: Dict[str, Any]) -> str:
        """Trigger a test task and return intent ID"""
        intent_id = f"test_{agent_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        intent_data = {
            "intent_id": intent_id,
            "intent_type": task["intent_type"],
            "source_agent": "sanity_check",
            "target_agent": agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "params": task["params"],
            "metadata": {
                "test": True,
                "sanity_check": True,
                "task_name": task["name"]
            }
        }
        
        logger.info(f"   Triggering: {task['name']}")
        logger.info(f"     Intent ID: {intent_id}")
        logger.info(f"     Type: {task['intent_type']}")
        
        try:
            # Send intent to SIMP broker
            url = f"{self.base_url}/intents/route"
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": os.environ.get("SIMP_API_KEY", "test")
            }
            
            response = requests.post(url, json=intent_data, headers=headers, timeout=10)
            
            if response.status_code in [200, 202]:
                logger.info(f"     ✅ Intent accepted")
                self.generated_intent_ids.append(intent_id)
                return intent_id
            else:
                logger.warning(f"     ⚠️  Intent rejected: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"     ❌ Error triggering task: {e}")
            return None
    
    def check_task_ledger(self, intent_id: str) -> Dict[str, Any]:
        """Check if task appears in SIMP task ledger"""
        if not self.task_ledger_path.exists():
            return {"found": False, "error": "Task ledger file not found"}
        
        try:
            with open(self.task_ledger_path, 'r') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if record.get("intent_id") == intent_id:
                            return {
                                "found": True,
                                "record": record,
                                "timestamp": record.get("timestamp"),
                                "status": record.get("status", "unknown")
                            }
            
            return {"found": False, "error": "Intent ID not found in ledger"}
            
        except Exception as e:
            return {"found": False, "error": f"Error reading ledger: {e}"}
    
    def check_lightning_traces(self, intent_id: str, agent_id: str) -> Dict[str, Any]:
        """Check if task appears in Agent Lightning traces"""
        try:
            # Get recent traces from LightningStore
            url = f"{self.lightning_store_url}/v1/agl/rollouts?limit=50"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return {"found": False, "error": f"Store error: {response.status_code}"}
            
            traces = response.json()
            if not isinstance(traces, list):
                return {"found": False, "error": "Invalid trace format"}
            
            # Look for our intent ID in traces
            matching_traces = []
            for trace in traces:
                if trace.get("trace_id") == intent_id or trace.get("agent_id") == agent_id:
                    matching_traces.append(trace)
            
            if matching_traces:
                # Get the most relevant trace
                trace = matching_traces[0]
                return {
                    "found": True,
                    "trace": trace,
                    "agent_id": trace.get("agent_id"),
                    "model": trace.get("model", "unknown"),
                    "latency": trace.get("response_time_ms", 0),
                    "success": trace.get("success", False),
                    "tokens": trace.get("total_tokens", 0),
                    "timestamp": trace.get("timestamp")
                }
            else:
                return {"found": False, "error": "No matching traces found"}
                
        except Exception as e:
            return {"found": False, "error": f"Error checking traces: {e}"}
    
    def check_agent_lightning_performance(self, agent_id: str) -> Dict[str, Any]:
        """Check Agent Lightning performance endpoint"""
        try:
            url = f"{self.base_url}/agent-lightning/agents/{agent_id}/performance?hours=1"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "available": True,
                    "data": data,
                    "total_traces": data.get("total_traces", 0),
                    "success_rate": data.get("success_rate", 0)
                }
            else:
                return {"available": False, "error": f"Endpoint error: {response.status_code}"}
                
        except Exception as e:
            return {"available": False, "error": f"Error checking performance: {e}"}
    
    def validate_trace_metrics(self, trace: Dict[str, Any], agent_id: str) -> Tuple[bool, List[str]]:
        """Validate trace metrics for correctness"""
        issues = []
        
        # Check agent name matches
        trace_agent = trace.get("agent_id", "")
        if trace_agent != agent_id:
            issues.append(f"Agent mismatch: expected {agent_id}, got {trace_agent}")
        
        # Check model is present
        model = trace.get("model", "")
        if not model:
            issues.append("Model field is empty")
        
        # Check latency is reasonable (0-30000ms)
        latency = trace.get("response_time_ms", 0)
        if latency < 0:
            issues.append(f"Negative latency: {latency}ms")
        elif latency > 30000:  # 30 seconds
            issues.append(f"Excessive latency: {latency}ms")
        
        # Check token counts are reasonable
        prompt_tokens = trace.get("prompt_tokens", 0)
        completion_tokens = trace.get("completion_tokens", 0)
        total_tokens = trace.get("total_tokens", 0)
        
        if prompt_tokens < 0 or completion_tokens < 0 or total_tokens < 0:
            issues.append("Negative token counts")
        
        if total_tokens != (prompt_tokens + completion_tokens):
            issues.append(f"Token sum mismatch: {prompt_tokens} + {completion_tokens} != {total_tokens}")
        
        # Check success flag is boolean
        success = trace.get("success")
        if not isinstance(success, bool):
            issues.append(f"Success flag is not boolean: {success}")
        
        return len(issues) == 0, issues
    
    def run_agent_sanity_check(self, agent_id: str):
        """Run sanity check for a specific agent"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🤖 SANITY CHECK: {agent_id.upper()}")
        logger.info(f"{'='*60}")
        
        if agent_id not in self.test_tasks:
            logger.error(f"❌ No test tasks defined for {agent_id}")
            return
        
        tasks = self.test_tasks[agent_id]
        
        for task in tasks:
            logger.info(f"\n📋 Task: {task['name']}")
            
            # Trigger the task
            intent_id = self.trigger_test_task(agent_id, task)
            if not intent_id:
                self.results[agent_id]["failed"] += 1
                self.results[agent_id]["tasks"].append({
                    "name": task["name"],
                    "status": "failed",
                    "error": "Failed to trigger task"
                })
                continue
            
            # Wait for processing
            logger.info("     ⏳ Waiting 3 seconds for processing...")
            time.sleep(3)
            
            # Check SIMP task ledger
            logger.info("     🔍 Checking SIMP task ledger...")
            ledger_result = self.check_task_ledger(intent_id)
            
            if ledger_result["found"]:
                logger.info(f"     ✅ Found in task ledger")
                logger.info(f"       Status: {ledger_result.get('status', 'unknown')}")
                logger.info(f"       Timestamp: {ledger_result.get('timestamp', 'unknown')}")
            else:
                logger.warning(f"     ⚠️  Not found in task ledger: {ledger_result.get('error')}")
            
            # Check Agent Lightning traces
            logger.info("     🔍 Checking Agent Lightning traces...")
            trace_result = self.check_lightning_traces(intent_id, agent_id)
            
            if trace_result["found"]:
                logger.info(f"     ✅ Found in Lightning traces")
                logger.info(f"       Model: {trace_result.get('model', 'unknown')}")
                logger.info(f"       Latency: {trace_result.get('latency', 0)}ms")
                logger.info(f"       Success: {trace_result.get('success', False)}")
                logger.info(f"       Tokens: {trace_result.get('tokens', 0)}")
                
                # Validate trace metrics
                is_valid, issues = self.validate_trace_metrics(trace_result["trace"], agent_id)
                if is_valid:
                    logger.info("     ✅ Trace metrics are valid")
                else:
                    logger.warning(f"     ⚠️  Trace metric issues: {', '.join(issues)}")
            else:
                logger.warning(f"     ⚠️  Not found in traces: {trace_result.get('error')}")
            
            # Check performance endpoint
            logger.info("     🔍 Checking performance endpoint...")
            perf_result = self.check_agent_lightning_performance(agent_id)
            
            if perf_result["available"]:
                logger.info(f"     ✅ Performance endpoint available")
                logger.info(f"       Total traces: {perf_result.get('total_traces', 0)}")
                logger.info(f"       Success rate: {perf_result.get('success_rate', 0):.1f}%")
            else:
                logger.warning(f"     ⚠️  Performance endpoint error: {perf_result.get('error')}")
            
            # Determine if this task passed
            task_passed = (
                ledger_result["found"] and 
                trace_result["found"] and 
                perf_result["available"]
            )
            
            if task_passed:
                logger.info(f"     🎉 Task PASSED all checks")
                self.results[agent_id]["passed"] += 1
                status = "passed"
            else:
                logger.info(f"     ❌ Task FAILED some checks")
                self.results[agent_id]["failed"] += 1
                status = "failed"
            
            self.results[agent_id]["tasks"].append({
                "name": task["name"],
                "intent_id": intent_id,
                "status": status,
                "ledger_found": ledger_result["found"],
                "trace_found": trace_result["found"],
                "perf_available": perf_result["available"]
            })
            
            # Small delay between tasks
            time.sleep(1)
    
    def run_comprehensive_check(self):
        """Run comprehensive sanity check for all agents"""
        logger.info("=" * 70)
        logger.info("🔬 TRACES SANITY CHECK - COMPREHENSIVE VALIDATION")
        logger.info("=" * 70)
        
        # Check system health
        if not self.check_system_health():
            logger.error("❌ System health check failed. Aborting sanity check.")
            return False
        
        # Run checks for each agent
        agents = ["quantumarb", "bullbear_predictor", "perplexity_research"]
        
        for agent in agents:
            self.run_agent_sanity_check(agent)
            time.sleep(2)  # Delay between agents
        
        # Print summary
        self.print_summary()
        
        # Return overall success
        total_passed = sum(self.results[agent]["passed"] for agent in agents)
        total_tasks = sum(len(self.results[agent]["tasks"]) for agent in agents)
        
        return total_passed == total_tasks
    
    def print_summary(self):
        """Print comprehensive summary"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 SANITY CHECK SUMMARY")
        logger.info("=" * 70)
        
        total_passed = 0
        total_failed = 0
        total_tasks = 0
        
        for agent_id, result in self.results.items():
            passed = result["passed"]
            failed = result["failed"]
            tasks = result["tasks"]
            
            total_passed += passed
            total_failed += failed
            total_tasks += len(tasks)
            
            logger.info(f"\n{agent_id.upper()}:")
            logger.info(f"  Tasks: {len(tasks)} total")
            logger.info(f"  Passed: {passed}")
            logger.info(f"  Failed: {failed}")
            
            for task in tasks:
                status_icon = "✅" if task["status"] == "passed" else "❌"
                logger.info(f"    {status_icon} {task['name']}")
                if task["status"] == "failed":
                    issues = []
                    if not task["ledger_found"]:
                        issues.append("missing from ledger")
                    if not task["trace_found"]:
                        issues.append("missing from traces")
                    if not task["perf_available"]:
                        issues.append("perf endpoint unavailable")
                    if issues:
                        logger.info(f"      Issues: {', '.join(issues)}")
        
        logger.info("\n" + "=" * 70)
        logger.info("OVERALL RESULTS:")
        logger.info(f"  Total Tasks: {total_tasks}")
        logger.info(f"  Total Passed: {total_passed}")
        logger.info(f"  Total Failed: {total_failed}")
        
        success_rate = (total_passed / total_tasks * 100) if total_tasks > 0 else 0
        logger.info(f"  Success Rate: {success_rate:.1f}%")
        
        if total_failed == 0:
            logger.info("\n🎉 ALL CHECKS PASSED! Traces match reality.")
        else:
            logger.info(f"\n⚠️  {total_failed} checks failed. Review issues above.")
        
        # Recommendations
        logger.info("\n" + "=" * 70)
        logger.info("🔧 RECOMMENDATIONS:")
        
        if total_failed > 0:
            logger.info("1. Check Agent Lightning proxy is correctly configured")
            logger.info("2. Verify agents are sending traces to LightningStore")
            logger.info("3. Check SIMP broker integration endpoints")
            logger.info("4. Review task ledger permissions and format")
        else:
            logger.info("1. Proceed to define 'better' metrics per agent")
            logger.info("2. Enable APO narrowly on one agent first")
            logger.info("3. Use traces to harden BRP and ProjectX")
            logger.info("4. Set up recurring eval loop")
        
        logger.info("\n📋 Generated Intent IDs for verification:")
        for intent_id in self.generated_intent_ids:
            logger.info(f"   - {intent_id}")


def main():
    """Main function"""
    
    # Check for required environment variables
    required_vars = ["X_AI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.warning(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        logger.info("Some features may not work correctly.")
        logger.info("Set them with: export VARIABLE_NAME='value'")
    
    # Run sanity check
    checker = TracesSanityCheck()
    success = checker.run_comprehensive_check()
    
    # Exit with appropriate code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())