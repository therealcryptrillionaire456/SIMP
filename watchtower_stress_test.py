#!/usr/bin/env python3.10
"""
SIMP System Stress Test - Watchtower Goose
Stress tests the SIMP broker and registered agents with concurrent intents.
Measures performance, response times, success rates, and documents system limits.

Usage:
    python3.10 watchtower_stress_test.py --agents test_agent_1,projectx_native --concurrent 5 --duration 30
"""

import json
import time
import statistics
import threading
import concurrent.futures
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import sys
import os
import argparse
import traceback

# Add the current directory to the path to import SIMP modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
    from simp.server.agent_client import SimpAgentClient
    from config.config import config
    SIMP_API_KEY = config.SIMP_API_KEY
    SIMP_BROKER_URL = config.SIMP_BROKER_URL
except ImportError as e:
    print(f"Error importing SIMP modules: {e}")
    print("Make sure you're in the SIMP directory and dependencies are installed.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("watchtower_stress_test")

@dataclass
class TestResult:
    """Result of a single intent test."""
    test_id: str
    agent_id: str
    intent_type: str
    success: bool
    response_time_ms: float
    timestamp: str
    error_message: Optional[str] = None
    broker_response: Optional[Dict] = None

@dataclass
class AgentMetrics:
    """Metrics for a specific agent."""
    agent_id: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p95_response_time_ms: float
    success_rate: float
    errors: List[str]

@dataclass
class TestSummary:
    """Summary of the entire stress test."""
    test_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    total_requests: int
    total_successful: int
    total_failed: int
    overall_success_rate: float
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p95_response_time_ms: float
    concurrent_workers: int
    agents_tested: List[str]
    agent_metrics: Dict[str, AgentMetrics]
    system_limits_observed: Dict[str, any]
    recommendations: List[str]

class WatchtowerStressTester:
    """Main stress tester class for SIMP system."""
    
    def __init__(self, broker_url: str = None, api_key: str = None):
        """Initialize the stress tester."""
        self.broker_url = broker_url or SIMP_BROKER_URL
        self.api_key = api_key or SIMP_API_KEY
        self.results: List[TestResult] = []
        self.lock = threading.Lock()
        
        # Verify broker is reachable
        try:
            response = requests.get(f"{self.broker_url}/health", timeout=5)
            if response.status_code != 200:
                raise Exception(f"Broker health check failed: {response.status_code}")
            logger.info(f"Broker is reachable at {self.broker_url}")
        except Exception as e:
            logger.error(f"Failed to connect to broker: {e}")
            raise
    
    def get_registered_agents(self) -> List[str]:
        """Get list of currently registered agents."""
        try:
            response = requests.get(f"{self.broker_url}/agents", timeout=5)
            if response.status_code == 200:
                data = response.json()
                agents = list(data.get("agents", {}).keys())
                logger.info(f"Found {len(agents)} registered agents: {agents}")
                return agents
            else:
                logger.warning(f"Failed to get agents: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting agents: {e}")
            return []
    
    def send_intent_via_broker(self, agent_id: str, intent_type: str = "ping", 
                              payload: Dict = None) -> Tuple[bool, float, Optional[Dict], Optional[str]]:
        """
        Send an intent via the broker and measure response time.
        Returns: (success, response_time_ms, response_data, error_message)
        """
        start_time = time.time()
        success = False
        response_data = None
        error_msg = None
        
        try:
            # Prepare intent payload
            intent_payload = {
                "intent_type": intent_type,
                "source_agent": "watchtower_stress_test",
                "target_agent": agent_id,
                "payload": payload or {"message": f"Stress test from Watchtower at {datetime.utcnow().isoformat()}"}
            }
            
            # Send to broker
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            
            response = requests.post(
                f"{self.broker_url}/intents/route",
                json=intent_payload,
                headers=headers,
                timeout=30  # Longer timeout for stress testing
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                response_data = response.json()
                # Check if intent was successfully delivered
                if response_data.get("status") == "success":
                    success = True
                else:
                    error_msg = f"Broker returned error: {response_data.get('error', 'Unknown error')}"
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            response_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Request timeout after {response_time_ms:.0f}ms"
        except requests.exceptions.ConnectionError:
            response_time_ms = (time.time() - start_time) * 1000
            error_msg = "Connection error to broker"
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Unexpected error: {str(e)}"
        
        return success, response_time_ms, response_data, error_msg
    
    def test_agent(self, agent_id: str, intent_type: str = "ping", 
                  test_id: str = None) -> TestResult:
        """Test a single agent with an intent."""
        test_id = test_id or f"{agent_id}_{intent_type}_{intetime.time()}"
        
        success, response_time_ms, response_data, error_msg = self.send_intent_via_broker(
            agent_id, intent_type
        )
        
        result = TestResult(
            test_id=test_id,
            agent_id=agent_id,
            intent_type=intent_type,
            success=success,
            response_time_ms=response_time_ms,
            timestamp=datetime.utcnow().isoformat(),
            error_message=error_msg,
            broker_response=response_data
        )
        
        with self.lock:
            self.results.append(result)
        
        log_level = logging.INFO if success else logging.WARNING
        logger.log(log_level, 
                  f"Test {test_id}: {agent_id} - {'SUCCESS' if success else 'FAILED'} "
                  f"in {response_time_ms:.1f}ms")
        
        return result
    
    def run_concurrent_test(self, agents: List[str], concurrent_workers: int = 5,
                           requests_per_agent: int = 10, intent_type: str = "ping") -> TestSummary:
        """
        Run concurrent stress test against multiple agents.
        
        Args:
            agents: List of agent IDs to test
            concurrent_workers: Number of concurrent threads
            requests_per_agent: Number of requests to send to each agent
            intent_type: Type of intent to send
        
        Returns:
            TestSummary with results
        """
        test_id = f"stress_test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()
        total_requests = len(agents) * requests_per_agent
        
        logger.info(f"Starting stress test {test_id}")
        logger.info(f"Agents: {agents}")
        logger.info(f"Concurrent workers: {concurrent_workers}")
        logger.info(f"Requests per agent: {requests_per_agent}")
        logger.info(f"Total requests: {total_requests}")
        
        # Clear previous results
        self.results = []
        
        # Create test tasks
        test_tasks = []
        for agent in agents:
            for i in range(requests_per_agent):
                task_id = f"{test_id}_{agent}_{i}"
                test_tasks.append((task_id, agent, intent_type))
        
        # Run tests with thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            futures = []
            for task_id, agent, intent_type in test_tasks:
                future = executor.submit(self.test_agent, agent, intent_type, task_id)
                futures.append(future)
            
            # Wait for all to complete
            concurrent.futures.wait(futures)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate summary
        summary = self._calculate_summary(test_id, start_time, end_time, 
                                         concurrent_workers, agents)
        
        logger.info(f"Stress test completed in {duration:.1f}s")
        logger.info(f"Total requests: {summary.total_requests}")
        logger.info(f"Successful: {summary.total_successful} ({summary.overall_success_rate:.1%})")
        logger.info(f"Average response time: {summary.avg_response_time_ms:.1f}ms")
        
        return summary
    
    def _calculate_summary(self, test_id: str, start_time: float, end_time: float,
                          concurrent_workers: int, agents: List[str]) -> TestSummary:
        """Calculate summary statistics from test results."""
        duration = end_time - start_time
        
        # Group results by agent
        agent_results: Dict[str, List[TestResult]] = {}
        for result in self.results:
            if result.agent_id not in agent_results:
                agent_results[result.agent_id] = []
            agent_results[result.agent_id].append(result)
        
        # Calculate agent metrics
        agent_metrics = {}
        for agent_id, results in agent_results.items():
            response_times = [r.response_time_ms for r in results]
            successes = [r for r in results if r.success]
            failures = [r for r in results if not r.success]
            
            if response_times:
                avg_time = statistics.mean(response_times)
                min_time = min(response_times)
                max_time = max(response_times)
                # Calculate 95th percentile
                sorted_times = sorted(response_times)
                p95_idx = int(len(sorted_times) * 0.95)
                p95_time = sorted_times[p95_idx] if p95_idx < len(sorted_times) else sorted_times[-1]
            else:
                avg_time = min_time = max_time = p95_time = 0
            
            errors = [r.error_message for r in failures if r.error_message]
            
            agent_metrics[agent_id] = AgentMetrics(
                agent_id=agent_id,
                total_requests=len(results),
                successful_requests=len(successes),
                failed_requests=len(failures),
                avg_response_time_ms=avg_time,
                min_response_time_ms=min_time,
                max_response_time_ms=max_time,
                p95_response_time_ms=p95_time,
                success_rate=len(successes) / len(results) if results else 0,
                errors=errors
            )
        
        # Calculate overall metrics
        all_response_times = [r.response_time_ms for r in self.results]
        all_successes = [r for r in self.results if r.success]
        
        if all_response_times:
            overall_avg = statistics.mean(all_response_times)
            overall_min = min(all_response_times)
            overall_max = max(all_response_times)
            sorted_all = sorted(all_response_times)
            p95_idx = int(len(sorted_all) * 0.95)
            overall_p95 = sorted_all[p95_idx] if p95_idx < len(sorted_all) else sorted_all[-1]
        else:
            overall_avg = overall_min = overall_max = overall_p95 = 0
        
        # Observe system limits
        system_limits = self._observe_system_limits(agent_metrics, duration)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(agent_metrics, system_limits)
        
        return TestSummary(
            test_id=test_id,
            start_time=datetime.fromtimestamp(start_time).isoformat(),
            end_time=datetime.fromtimestamp(end_time).isoformat(),
            duration_seconds=duration,
            total_requests=len(self.results),
            total_successful=len(all_successes),
            total_failed=len(self.results) - len(all_successes),
            overall_success_rate=len(all_successes) / len(self.results) if self.results else 0,
            avg_response_time_ms=overall_avg,
            min_response_time_ms=overall_min,
            max_response_time_ms=overall_max,
            p95_response_time_ms=overall_p95,
            concurrent_workers=concurrent_workers,
            agents_tested=agents,
            agent_metrics=agent_metrics,
            system_limits_observed=system_limits,
            recommendations=recommendations
        )
    
    def _observe_system_limits(self, agent_metrics: Dict[str, AgentMetrics], 
                              duration: float) -> Dict[str, any]:
        """Observe and document system limits from test results."""
        limits = {
            "test_duration_seconds": duration,
            "agents_tested_count": len(agent_metrics),
            "requests_per_second": len(self.results) / duration if duration > 0 else 0,
            "max_concurrent_supported": "Unknown (needs incremental testing)",
            "bottlenecks_observed": [],
            "agent_performance_variation": {}
        }
        
        # Check for bottlenecks
        max_response_time = 0
        slowest_agent = None
        
        for agent_id, metrics in agent_metrics.items():
            limits["agent_performance_variation"][agent_id] = {
                "avg_response_ms": metrics.avg_response_time_ms,
                "p95_response_ms": metrics.p95_response_time_ms,
                "success_rate": metrics.success_rate
            }
            
            if metrics.p95_response_time_ms > max_response_time:
                max_response_time = metrics.p95_response_time_ms
                slowest_agent = agent_id
        
        if slowest_agent and max_response_time > 1000:  # > 1 second
            limits["bottlenecks_observed"].append(
                f"Agent {slowest_agent} has high p95 response time: {max_response_time:.0f}ms"
            )
        
        # Check for high error rates
        for agent_id, metrics in agent_metrics.items():
            if metrics.success_rate < 0.8:  # < 80% success rate
                limits["bottlenecks_observed"].append(
                    f"Agent {agent_id} has low success rate: {metrics.success_rate:.1%}"
                )
        
        return limits
    
    def _generate_recommendations(self, agent_metrics: Dict[str, AgentMetrics],
                                 system_limits: Dict[str, any]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check response times
        for agent_id, metrics in agent_metrics.items():
            if metrics.p95_response_time_ms > 500:  # > 500ms
                recommendations.append(
                    f"Optimize {agent_id} response time (p95: {metrics.p95_response_time_ms:.0f}ms)"
                )
            
            if metrics.success_rate < 0.9:  # < 90% success rate
                recommendations.append(
                    f"Improve reliability of {agent_id} (success rate: {metrics.success_rate:.1%})"
                )
        
        # System-level recommendations
        rps = system_limits.get("requests_per_second", 0)
        if rps < 10:
            recommendations.append(
                f"Consider optimizing broker throughput (current: {rps:.1f} requests/second)"
            )
        
        if system_limits.get("bottlenecks_observed"):
            recommendations.append(
                "Address identified bottlenecks before scaling up concurrent load"
            )
        
        if not recommendations:
            recommendations.append(
                "System performing well at current load level. Consider increasing "
                "concurrent load to find upper limits."
            )
        
        return recommendations
    
    def save_results(self, summary: TestSummary, output_dir: str = "stress_test_results"):
        """Save test results to JSON file."""
        os.makedirs(output_dir, exist_ok=True)
        
        # Create filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/stress_test_{timestamp}.json"
        
        # Convert to dict
        data = {
            "summary": asdict(summary),
            "detailed_results": [asdict(r) for r in self.results],
            "metadata": {
                "broker_url": self.broker_url,
                "test_tool": "watchtower_stress_test.py",
                "version": "1.0.0",
                "timestamp": timestamp
            }
        }
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Results saved to {filename}")
        return filename
    
    def print_summary(self, summary: TestSummary):
        """Print a human-readable summary of test results."""
        print("\n" + "="*80)
        print("WATCHTOWER STRESS TEST SUMMARY")
        print("="*80)
        print(f"Test ID: {summary.test_id}")
        print(f"Duration: {summary.duration_seconds:.1f}s")
        print(f"Concurrent workers: {summary.concurrent_workers}")
        print(f"Agents tested: {', '.join(summary.agents_tested)}")
        print()
        
        print("OVERALL PERFORMANCE:")
        print(f"  Total requests: {summary.total_requests}")
        print(f"  Successful: {summary.total_successful} ({summary.overall_success_rate:.1%})")
        print(f"  Failed: {summary.total_failed}")
        print(f"  Avg response time: {summary.avg_response_time_ms:.1f}ms")
        print(f"  Min response time: {summary.min_response_time_ms:.1f}ms")
        print(f"  Max response time: {summary.max_response_time_ms:.1f}ms")
        print(f"  p95 response time: {summary.p95_response_time_ms:.1f}ms")
        print(f"  Requests/second: {summary.total_requests / summary.duration_seconds:.1f}")
        print()
        
        print("AGENT PERFORMANCE:")
        for agent_id, metrics in summary.agent_metrics.items():
            print(f"  {agent_id}:")
            print(f"    Requests: {metrics.total_requests}")
            print(f"    Success rate: {metrics.success_rate:.1%}")
            print(f"    Avg response: {metrics.avg_response_time_ms:.1f}ms")
            print(f"    p95 response: {metrics.p95_response_time_ms:.1f}ms")
            if metrics.errors:
                print(f"    Errors: {len(metrics.errors)} unique")
        
        print()
        print("SYSTEM LIMITS OBSERVED:")
        for key, value in summary.system_limits_observed.items():
            if isinstance(value, list):
                if value:
                    print(f"  {key}:")
                    for item in value:
                        print(f"    - {item}")
            elif isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subvalue in value.items():
                    print(f"    {subkey}: {subvalue}")
            else:
                print(f"  {key}: {value}")
        
        print()
        print("RECOMMENDATIONS:")
        for i, rec in enumerate(summary.recommendations, 1):
            print(f"  {i}. {rec}")
        
        print("="*80)

def main():
    """Main entry point for the stress test."""
    parser = argparse.ArgumentParser(description="SIMP System Stress Test - Watchtower Goose")
    parser.add_argument("--agents", type=str, default="",
                       help="Comma-separated list of agent IDs to test (default: all registered agents)")
    parser.add_argument("--concurrent", type=int, default=5,
                       help="Number of concurrent workers (default: 5)")
    parser.add_argument("--requests", type=int, default=10,
                       help="Requests per agent (default: 10)")
    parser.add_argument("--intent-type", type=str, default="ping",
                       help="Type of intent to send (default: ping)")
    parser.add_argument("--output-dir", type=str, default="stress_test_results",
                       help="Directory to save results (default: stress_test_results)")
    parser.add_argument("--broker-url", type=str, default=None,
                       help="Broker URL (default: from config)")
    parser.add_argument("--api-key", type=str, default=None,
                       help="API key (default: from config)")
    
    args = parser.parse_args()
    
    try:
        # Initialize stress tester
        tester = WatchtowerStressTester(args.broker_url, args.api_key)
        
        # Determine which agents to test
        if args.agents:
            agents_to_test = [a.strip() for a in args.agents.split(",") if a.strip()]
        else:
            agents_to_test = tester.get_registered_agents()
        
        if not agents_to_test:
            logger.error("No agents to test. Either specify agents with --agents or ensure agents are registered.")
            return 1
        
        # Run stress test
        summary = tester.run_concurrent_test(
            agents=agents_to_test,
            concurrent_workers=args.concurrent,
            requests_per_agent=args.requests,
            intent_type=args.intent_type
        )
        
        # Print and save results
        tester.print_summary(summary)
        results_file = tester.save_results(summary, args.output_dir)
        
        print(f"\nResults saved to: {results_file}")
        print("Stress test completed successfully!")
        
        # Check for critical issues
        if summary.overall_success_rate < 0.5:
            print("\n⚠️  WARNING: Low overall success rate (< 50%)")
            return 2
        elif summary.overall_success_rate < 0.8:
            print("\n⚠️  WARNING: Moderate success rate (< 80%)")
            return 1
        else:
            print("\n✅ Success rate acceptable (> 80%)")
            return 0
            
    except KeyboardInterrupt:
        print("\n\nStress test interrupted by user.")
        return 130
    except Exception as e:
        logger.error(f"Stress test failed: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())