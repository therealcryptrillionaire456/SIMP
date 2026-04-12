#!/usr/bin/env python3
"""
SIMP Broker Stress Test - Simplified Version
Stress tests the SIMP broker by sending multiple concurrent intents to test_agent_1.
Collects performance metrics, identifies bottlenecks, and documents system limits.
"""

import json
import time
import statistics
import threading
import concurrent.futures
import requests
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import sys
import os
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stress_test")

@dataclass
class TestResult:
    """Individual test result."""
    intent_id: str
    success: bool
    response_time_ms: float
    status_code: int
    error_message: Optional[str] = None
    timestamp: str = ""

@dataclass
class TestSummary:
    """Summary of test results."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    requests_per_second: float
    test_duration_seconds: float
    concurrent_workers: int
    timestamp: str = ""

class SIMPStressTester:
    """Stress tester for SIMP broker."""
    
    def __init__(
        self,
        broker_url: str = "http://127.0.0.1:5555",
        target_agent: str = "test_agent_1",
        api_key: Optional[str] = None
    ):
        self.broker_url = broker_url.rstrip('/')
        self.target_agent = target_agent
        self.api_key = api_key
        
        # Default headers
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def send_intent(
        self,
        intent_type: str = "planning",
        params: Dict = None,
        intent_id: str = None
    ) -> TestResult:
        """Send a single intent to the broker."""
        if params is None:
            params = {}
        
        if intent_id is None:
            intent_id = f"stress_test_{int(time.time() * 1000)}_{threading.get_ident()}"
        
        intent_data = {
            "intent_type": intent_type,
            "source_agent": "stress_tester",
            "target_agent": self.target_agent,
            "params": params,
            "intent_id": intent_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        start_time = time.time()
        success = False
        status_code = 0
        error_message = None
        
        try:
            response = requests.post(
                f"{self.broker_url}/intents/route",
                headers=self.headers,
                json=intent_data,
                timeout=30.0
            )
            status_code = response.status_code
            
            if 200 <= status_code < 300:
                try:
                    response_data = response.json()
                    if response_data.get("status") in ["success", "delivered", "routed"]:
                        success = True
                    else:
                        error_message = f"Response status not success: {response_data.get('status')}"
                except json.JSONDecodeError:
                    error_message = f"Invalid JSON response: {response.text[:100]}"
            else:
                error_message = f"HTTP {status_code}: {response.text[:100]}"
        
        except requests.Timeout:
            error_message = "Request timeout (30s)"
        except Exception as e:
            error_message = str(e)
        
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        
        return TestResult(
            intent_id=intent_id,
            success=success,
            response_time_ms=response_time_ms,
            status_code=status_code,
            error_message=error_message,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def run_concurrent_test(
        self,
        num_requests: int,
        concurrent_workers: int,
        intent_type: str = "ping",
        params: Dict = None
    ) -> Tuple[List[TestResult], TestSummary]:
        """Run concurrent stress test using ThreadPoolExecutor."""
        logger.info(f"Starting stress test: {num_requests} requests, {concurrent_workers} concurrent workers")
        
        if params is None:
            params = {"message": "stress_test"}
        
        start_time = time.time()
        results = []
        
        # Create a function that sends one intent
        def send_one(request_num: int):
            return self.send_intent(
                intent_type=intent_type,
                params=params,
                intent_id=f"stress_{request_num}_{int(time.time())}"
            )
        
        # Use ThreadPoolExecutor for concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            # Submit all tasks
            future_to_num = {executor.submit(send_one, i): i for i in range(num_requests)}
            
            # Collect results as they complete
            completed = 0
            for future in concurrent.futures.as_completed(future_to_num):
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Log progress every 10%
                    if completed % max(1, num_requests // 10) == 0:
                        logger.info(f"Progress: {completed}/{num_requests} requests completed")
                except Exception as e:
                    logger.error(f"Error in request {future_to_num[future]}: {e}")
        
        end_time = time.time()
        test_duration = end_time - start_time
        
        # Calculate summary
        summary = self._calculate_summary(results, test_duration, concurrent_workers)
        
        return results, summary
    
    def _calculate_summary(
        self,
        results: List[TestResult],
        test_duration: float,
        concurrent_workers: int
    ) -> TestSummary:
        """Calculate test summary from results."""
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        response_times = [r.response_time_ms for r in results if r.success]
        
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            
            # Calculate percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.5)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) >= 20 else max_response
            p99 = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) >= 100 else max_response
        else:
            avg_response = min_response = max_response = p50 = p95 = p99 = 0.0
        
        success_rate = (successful / total * 100) if total > 0 else 0
        rps = total / test_duration if test_duration > 0 else 0
        
        return TestSummary(
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            success_rate=success_rate,
            avg_response_time_ms=avg_response,
            min_response_time_ms=min_response,
            max_response_time_ms=max_response,
            p50_response_time_ms=p50,
            p95_response_time_ms=p95,
            p99_response_time_ms=p99,
            requests_per_second=rps,
            test_duration_seconds=test_duration,
            concurrent_workers=concurrent_workers,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def print_summary(self, summary: TestSummary):
        """Print test summary in a readable format."""
        print("\n" + "="*80)
        print("SIMP BROKER STRESS TEST RESULTS - Watchtower Goose")
        print("="*80)
        print(f"Test Timestamp: {summary.timestamp}")
        print(f"Duration: {summary.test_duration_seconds:.2f} seconds")
        print(f"Concurrent Workers: {summary.concurrent_workers}")
        print(f"Total Requests: {summary.total_requests}")
        print(f"Successful: {summary.successful_requests}")
        print(f"Failed: {summary.failed_requests}")
        print(f"Success Rate: {summary.success_rate:.2f}%")
        print(f"Requests per Second: {summary.requests_per_second:.2f}")
        print("\nResponse Times (ms):")
        print(f"  Average: {summary.avg_response_time_ms:.2f}")
        print(f"  Minimum: {summary.min_response_time_ms:.2f}")
        print(f"  Maximum: {summary.max_response_time_ms:.2f}")
        print(f"  P50: {summary.p50_response_time_ms:.2f}")
        print(f"  P95: {summary.p95_response_time_ms:.2f}")
        print(f"  P99: {summary.p99_response_time_ms:.2f}")
        print("="*80)
    
    def save_results(self, results: List[TestResult], summary: TestSummary, filename: str = "stress_test_results.json"):
        """Save test results to JSON file."""
        data = {
            "metadata": {
                "broker_url": self.broker_url,
                "target_agent": self.target_agent,
                "test_timestamp": summary.timestamp,
                "test_duration_seconds": summary.test_duration_seconds,
                "concurrent_workers": summary.concurrent_workers
            },
            "summary": {
                "total_requests": summary.total_requests,
                "successful_requests": summary.successful_requests,
                "failed_requests": summary.failed_requests,
                "success_rate": summary.success_rate,
                "avg_response_time_ms": summary.avg_response_time_ms,
                "min_response_time_ms": summary.min_response_time_ms,
                "max_response_time_ms": summary.max_response_time_ms,
                "p50_response_time_ms": summary.p50_response_time_ms,
                "p95_response_time_ms": summary.p95_response_time_ms,
                "p99_response_time_ms": summary.p99_response_time_ms,
                "requests_per_second": summary.requests_per_second
            },
            "detailed_results": [
                {
                    "intent_id": r.intent_id,
                    "success": r.success,
                    "response_time_ms": r.response_time_ms,
                    "status_code": r.status_code,
                    "error_message": r.error_message,
                    "timestamp": r.timestamp
                }
                for r in results
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Results saved to {filename}")

def collect_system_metrics(duration_seconds: int = 10) -> Dict:
    """Collect system metrics during test."""
    metrics = []
    start_time = time.time()
    
    logger.info("Collecting system metrics...")
    
    while time.time() - start_time < duration_seconds:
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            
            metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "disk_read_mb": disk_io.read_bytes / (1024**2) if disk_io else 0,
                "disk_write_mb": disk_io.write_bytes / (1024**2) if disk_io else 0,
            }
            
            metrics.append(metric)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            break
    
    # Calculate averages
    if metrics:
        avg_cpu = statistics.mean([m["cpu_percent"] for m in metrics])
        avg_memory = statistics.mean([m["memory_percent"] for m in metrics])
        max_cpu = max([m["cpu_percent"] for m in metrics])
        
        return {
            "avg_cpu_percent": avg_cpu,
            "max_cpu_percent": max_cpu,
            "avg_memory_percent": avg_memory,
            "samples_collected": len(metrics),
            "metrics": metrics
        }
    
    return {}

def run_scalability_test():
    """Run scalability test with increasing load."""
    broker_url = "http://127.0.0.1:5555"
    target_agent = "test_agent_1"
    
    # Test configurations: (num_requests, concurrent_workers)
    test_configs = [
        (10, 1),      # Baseline
        (50, 5),      # Light load
        (100, 10),    # Medium load
        (200, 20),    # Heavy load
        (500, 50),    # Very heavy load
    ]
    
    all_summaries = []
    system_metrics = []
    
    tester = SIMPStressTester(broker_url, target_agent)
    
    for num_requests, concurrent_workers in test_configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test: {num_requests} requests, {concurrent_workers} concurrent workers")
        logger.info(f"{'='*60}")
        
        try:
            # Collect baseline system metrics
            baseline_metrics = collect_system_metrics(3)
            
            # Run the test
            results, summary = tester.run_concurrent_test(
                num_requests=num_requests,
                concurrent_workers=concurrent_workers,
                intent_type="ping",
                params={"message": f"stress_test_{num_requests}_{concurrent_workers}"}
            )
            
            tester.print_summary(summary)
            all_summaries.append(summary)
            
            # Collect post-test system metrics
            post_test_metrics = collect_system_metrics(3)
            
            # Save individual test results
            filename = f"stress_test_{num_requests}_{concurrent_workers}_{int(time.time())}.json"
            tester.save_results(results, summary, filename)
            
            # Save system metrics
            sys_metrics_file = f"system_metrics_{num_requests}_{concurrent_workers}.json"
            with open(sys_metrics_file, 'w') as f:
                json.dump({
                    "baseline": baseline_metrics,
                    "post_test": post_test_metrics,
                    "test_config": {
                        "requests": num_requests,
                        "concurrent_workers": concurrent_workers
                    }
                }, f, indent=2)
            
            system_metrics.append({
                "config": f"{num_requests}_{concurrent_workers}",
                "baseline_cpu": baseline_metrics.get("avg_cpu_percent", 0),
                "post_test_cpu": post_test_metrics.get("avg_cpu_percent", 0),
                "success_rate": summary.success_rate,
                "avg_response_ms": summary.avg_response_time_ms
            })
            
            # Check for system degradation
            if summary.success_rate < 95:
                logger.warning(f"⚠️  Success rate below 95%: {summary.success_rate:.2f}%")
                if summary.success_rate < 80:
                    logger.error(f"❌ Success rate critically low: {summary.success_rate:.2f}% - stopping tests")
                    break
            
            # Check response time degradation
            if summary.avg_response_time_ms > 1000:  # More than 1 second
                logger.warning(f"⚠️  High average response time: {summary.avg_response_time_ms:.2f}ms")
                if summary.avg_response_time_ms > 5000:  # More than 5 seconds
                    logger.error(f"❌ Response time critically high: {summary.avg_response_time_ms:.2f}ms - stopping tests")
                    break
            
            # Check system resource usage
            if post_test_metrics.get("avg_cpu_percent", 0) > 80:
                logger.warning(f"⚠️  High CPU usage during test: {post_test_metrics.get('avg_cpu_percent', 0):.1f}%")
            
            # Brief pause between tests
            logger.info("Pausing for 5 seconds before next test...")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            break
    
    # Print final comparison
    print("\n" + "="*80)
    print("SCALABILITY TEST COMPARISON")
    print("="*80)
    print(f"{'Requests':>10} {'Workers':>10} {'Success %':>10} {'Avg RT (ms)':>12} {'RPS':>10} {'P95 (ms)':>10} {'CPU %':>8}")
    print("-"*80)
    
    for i, summary in enumerate(all_summaries):
        cpu_info = system_metrics[i]["post_test_cpu"] if i < len(system_metrics) else 0
        print(f"{summary.total_requests:>10} {summary.concurrent_workers:>10} "
              f"{summary.success_rate:>9.1f}% {summary.avg_response_time_ms:>11.1f} "
              f"{summary.requests_per_second:>9.1f} {summary.p95_response_time_ms:>9.1f} {cpu_info:>7.1f}")
    
    # Identify bottlenecks
    print("\n" + "="*80)
    print("BOTTLENECK ANALYSIS")
    print("="*80)
    
    if len(all_summaries) > 1:
        # Check for response time degradation
        first_rt = all_summaries[0].avg_response_time_ms
        last_rt = all_summaries[-1].avg_response_time_ms
        
        if last_rt > first_rt * 3:
            print(f"⚠️  SIGNIFICANT RESPONSE TIME DEGRADATION: {first_rt:.1f}ms → {last_rt:.1f}ms")
            print("   Possible bottlenecks:")
            print("   - Broker thread pool saturation")
            print("   - Agent HTTP server concurrency limits")
            print("   - Network/IO bottlenecks")
        
        # Check for success rate degradation
        first_sr = all_summaries[0].success_rate
        last_sr = all_summaries[-1].success_rate
        
        if last_sr < first_sr - 10:
            print(f"⚠️  SUCCESS RATE DEGRADATION: {first_sr:.1f}% → {last_sr:.1f}%")
            print("   Possible issues:")
            print("   - Request timeouts under load")
            print("   - Agent becoming unresponsive")
            print("   - Broker queue overflow")
        
        # Check P95 vs P50
        for i, summary in enumerate(all_summaries):
            if summary.p95_response_time_ms > summary.p50_response_time_ms * 5:
                print(f"⚠️  HIGH TAIL LATENCY in test {i+1}: P95={summary.p95_response_time_ms:.1f}ms (P50={summary.p50_response_time_ms:.1f}ms)")
                print("   Some requests experiencing much higher latency than others")
                print("   Possible causes: GC pauses, thread contention, network variability")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    if len(all_summaries) >= 3:
        # Analyze system limits
        max_sustainable_rps = max(s.requests_per_second for s in all_summaries if s.success_rate > 95)
        max_sustainable_concurrency = max(s.concurrent_workers for s in all_summaries if s.success_rate > 95 and s.avg_response_time_ms < 1000)
        
        print(f"1. Maximum sustainable RPS: {max_sustainable_rps:.1f}")
        print(f"2. Maximum sustainable concurrency: {max_sustainable_concurrency}")
        print(f"3. Recommended concurrency limit: {max_sustainable_concurrency * 0.8:.0f} (80% of max)")
        print(f"4. Recommended RPS limit: {max_sustainable_rps * 0.8:.1f} (80% of max)")
        
        # Check for memory issues
        max_memory = max(m.get("post_test_cpu", 0) for m in system_metrics)  # Using CPU as proxy
        if max_memory > 70:
            print("5. ⚠️  High resource usage detected - consider:")
            print("   - Increasing broker thread pool size")
            print("   - Scaling test_agent horizontally")
            print("   - Implementing request rate limiting")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("Generated files:")
    print("- stress_test_*.json: Detailed test results")
    print("- system_metrics_*.json: System resource metrics")
    print("- Check logs for detailed error information")

def check_prerequisites():
    """Check if prerequisites are met."""
    print("\n" + "="*80)
    print("PREREQUISITE CHECK")
    print("="*80)
    
    # Check if broker is running
    try:
        response = requests.get("http://127.0.0.1:5555/health", timeout=5.0)
        if response.status_code == 200:
            print("✅ SIMP broker is running")
        else:
            print("❌ SIMP broker is not responding correctly")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to SIMP broker: {e}")
        print("Please start the SIMP broker first: python3 -m simp.server.http_server")
        return False
    
    # Check if test_agent_1 is registered
    try:
        response = requests.get("http://127.0.0.1:5555/agents", timeout=5.0)
        agents = response.json()
        if "test_agent_1" not in agents.get("agents", {}):
            print("⚠️  test_agent_1 is not registered with the broker")
            print("Starting test_agent_1...")
            
            # Start test agent in background
            import subprocess
            import sys
            agent_process = subprocess.Popen([
                sys.executable, "test_agent_1.py", 
                "--agent-id", "test_agent_1",
                "--port", "8889"
            ])
            
            print("Waiting 5 seconds for test_agent_1 to start...")
            time.sleep(5)
            
            # Check again
            response = requests.get("http://127.0.0.1:5555/agents", timeout=5.0)
            agents = response.json()
            if "test_agent_1" in agents.get("agents", {}):
                print("✅ test_agent_1 is now registered")
            else:
                print("❌ Failed to register test_agent_1")
                return False
        else:
            print("✅ test_agent_1 is registered")
    except Exception as e:
        print(f"❌ Error checking agents: {e}")
        return False
    
    # Check required Python packages
    try:
        import psutil
        print("✅ psutil is available for system monitoring")
    except ImportError:
        print("⚠️  psutil not installed. System metrics will be limited.")
        print("   Install with: pip install psutil")
    
    return True

def main():
    """Main entry point."""
    print("\n" + "="*80)
    print("SIMP BROKER STRESS TEST SUITE - Watchtower Goose")
    print("="*80)
    print("This test will:")
    print("1. Send concurrent intents to test_agent_1")
    print("2. Measure response times and success rates")
    print("3. Collect system resource metrics")
    print("4. Identify system bottlenecks and limits")
    print("="*80)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Exiting.")
        return
    
    # Run scalability test
    run_scalability_test()

if __name__ == "__main__":
    main()