#!/usr/bin/env python3
"""
SIMP Broker Stress Test - Watchtower Goose Edition
Stress tests the SIMP broker by sending multiple concurrent intents to test_agent_1.
Collects performance metrics, identifies bottlenecks, and documents system limits.
"""

import asyncio
import aiohttp
import json
import time
import statistics
import threading
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import sys
import os

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
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Default headers
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def send_intent(
        self,
        intent_type: str = "ping",
        params: Dict = None,
        intent_id: str = None
    ) -> TestResult:
        """Send a single intent to the broker."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
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
            async with self.session.post(
                f"{self.broker_url}/intents/route",
                headers=self.headers,
                json=intent_data,
                timeout=30.0
            ) as response:
                status_code = response.status
                response_text = await response.text()
                
                if 200 <= status_code < 300:
                    try:
                        response_data = json.loads(response_text)
                        if response_data.get("status") in ["success", "delivered"]:
                            success = True
                        else:
                            error_message = f"Response status not success: {response_data.get('status')}"
                    except json.JSONDecodeError:
                        error_message = f"Invalid JSON response: {response_text[:100]}"
                else:
                    error_message = f"HTTP {status_code}: {response_text[:100]}"
        
        except asyncio.TimeoutError:
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
    
    async def run_concurrent_test(
        self,
        num_requests: int,
        concurrent_workers: int,
        intent_type: str = "ping",
        params: Dict = None
    ) -> Tuple[List[TestResult], TestSummary]:
        """Run concurrent stress test."""
        logger.info(f"Starting stress test: {num_requests} requests, {concurrent_workers} concurrent workers")
        
        if params is None:
            params = {"message": "stress_test"}
        
        start_time = time.time()
        results = []
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrent_workers)
        
        async def worker(request_num: int):
            async with semaphore:
                result = await self.send_intent(
                    intent_type=intent_type,
                    params=params,
                    intent_id=f"stress_{request_num}_{int(time.time())}"
                )
                return result
        
        # Create tasks
        tasks = [worker(i) for i in range(num_requests)]
        
        # Run tasks and collect results
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            
            # Log progress every 10%
            if len(results) % max(1, num_requests // 10) == 0:
                logger.info(f"Progress: {len(results)}/{num_requests} requests completed")
        
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

async def run_scalability_test():
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
        (1000, 100),  # Extreme load
    ]
    
    all_summaries = []
    
    async with SIMPStressTester(broker_url, target_agent) as tester:
        for num_requests, concurrent_workers in test_configs:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running test: {num_requests} requests, {concurrent_workers} concurrent workers")
            logger.info(f"{'='*60}")
            
            try:
                results, summary = await tester.run_concurrent_test(
                    num_requests=num_requests,
                    concurrent_workers=concurrent_workers,
                    intent_type="ping",
                    params={"message": f"stress_test_{num_requests}_{concurrent_workers}"}
                )
                
                tester.print_summary(summary)
                all_summaries.append(summary)
                
                # Save individual test results
                filename = f"stress_test_{num_requests}_{concurrent_workers}_{int(time.time())}.json"
                tester.save_results(results, summary, filename)
                
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
                
                # Brief pause between tests
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Test failed with error: {e}")
                break
    
    # Print final comparison
    print("\n" + "="*80)
    print("SCALABILITY TEST COMPARISON")
    print("="*80)
    print(f"{'Requests':>10} {'Workers':>10} {'Success %':>10} {'Avg RT (ms)':>12} {'RPS':>10} {'P95 (ms)':>10}")
    print("-"*80)
    
    for summary in all_summaries:
        print(f"{summary.total_requests:>10} {summary.concurrent_workers:>10} "
              f"{summary.success_rate:>9.1f}% {summary.avg_response_time_ms:>11.1f} "
              f"{summary.requests_per_second:>9.1f} {summary.p95_response_time_ms:>9.1f}")

async def monitor_system_health():
    """Monitor system health during tests."""
    import psutil
    
    logger.info("Starting system health monitoring...")
    
    start_time = time.time()
    metrics = []
    
    while True:
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "disk_read_mb": disk_io.read_bytes / (1024**2) if disk_io else 0,
                "disk_write_mb": disk_io.write_bytes / (1024**2) if disk_io else 0,
                "net_sent_mb": net_io.bytes_sent / (1024**2),
                "net_recv_mb": net_io.bytes_recv / (1024**2),
            }
            
            metrics.append(metric)
            
            # Log every 10 seconds
            if len(metrics) % 10 == 0:
                logger.info(f"System Health - CPU: {cpu_percent:.1f}%, Memory: {memory.percent:.1f}%")
            
            await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")
            break
    
    # Save health metrics
    if metrics:
        with open("system_health_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"System health metrics saved ({len(metrics)} samples)")

async def main():
    """Main entry point."""
    print("\n" + "="*80)
    print("SIMP BROKER STRESS TEST SUITE - Watchtower Goose")
    print("="*80)
    print("This test will:")
    print("1. Send concurrent intents to test_agent_1")
    print("2. Measure response times and success rates")
    print("3. Identify system bottlenecks")
    print("4. Document system limits")
    print("="*80)
    
    # Check if broker is running
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:5555/health", timeout=5.0)
            if response.status_code == 200:
                logger.info("✅ SIMP broker is running")
            else:
                logger.error("❌ SIMP broker is not responding correctly")
                return
    except Exception as e:
        logger.error(f"❌ Cannot connect to SIMP broker: {e}")
        logger.info("Please start the SIMP broker first: python3 -m simp.server.http_server")
        return
    
    # Check if test_agent_1 is registered
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:5555/agents", timeout=5.0)
            agents = response.json()
            if "test_agent_1" not in agents.get("agents", {}):
                logger.warning("⚠️  test_agent_1 is not registered with the broker")
                logger.info("Starting test_agent_1...")
                # Start test agent in background
                import subprocess
                subprocess.Popen([
                    "python3", "test_agent.py", 
                    "--agent-id", "test_agent_1",
                    "--port", "8889"
                ])
                logger.info("Waiting 5 seconds for test_agent_1 to start...")
                await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"❌ Error checking agents: {e}")
    
    # Run scalability test
    await run_scalability_test()
    
    print("\n" + "="*80)
    print("STRESS TEST COMPLETE")
    print("="*80)
    print("Check the generated JSON files for detailed results.")
    print("Look for bottlenecks in:")
    print("1. High P95/P99 response times")
    print("2. Success rate degradation under load")
    print("3. System resource saturation (CPU/Memory)")
    print("="*80)

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())