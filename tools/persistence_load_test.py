#!/usr/bin/env python3
"""
Persistence Load Test for SIMP System

Tests persistence components under high load with concurrent operations.
Simulates production-like workload to identify bottlenecks and issues.

Usage:
    python3 tools/persistence_load_test.py [--agents 100] [--intents 1000] [--threads 10]
    python3 tools/persistence_load_test.py --scenario production [--duration 300]
"""

import json
import time
import threading
import random
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse
import sys
import os
import concurrent.futures

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.agent_registry import AgentRegistry, AgentRegistryConfig
from simp.orchestration.orchestration_manager import OrchestrationManager, OrchestrationManagerConfig
from simp.server.intent_ledger import IntentLedger


@dataclass
class LoadTestResult:
    """Results from a load test run"""
    scenario: str
    start_time: str
    end_time: str
    duration_seconds: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    success_rate: float
    operations_per_second: float
    
    # Performance metrics
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    
    # Resource usage
    peak_memory_mb: Optional[float] = None
    final_disk_usage_mb: Optional[float] = None
    file_growth_mb: Optional[float] = None
    
    # Component-specific metrics
    component_metrics: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    
    @classmethod
    def create(cls, scenario: str, start_time: datetime, end_time: datetime, 
               operations: List['OperationResult']):
        """Create result from operation results"""
        duration = (end_time - start_time).total_seconds()
        total_ops = len(operations)
        successful = sum(1 for op in operations if op.success)
        failed = total_ops - successful
        
        if total_ops > 0:
            success_rate = successful / total_ops
            ops_per_sec = total_ops / duration if duration > 0 else 0
            
            latencies = [op.duration_ms for op in operations if op.success]
            if latencies:
                avg = statistics.mean(latencies)
                min_val = min(latencies)
                max_val = max(latencies)
                p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
                p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)
            else:
                avg = min_val = max_val = p95 = p99 = 0
        else:
            success_rate = ops_per_sec = avg = min_val = max_val = p95 = p99 = 0
        
        return cls(
            scenario=scenario,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            total_operations=total_ops,
            successful_operations=successful,
            failed_operations=failed,
            success_rate=success_rate,
            operations_per_second=ops_per_sec,
            avg_latency_ms=avg,
            min_latency_ms=min_val,
            max_latency_ms=max_val,
            p95_latency_ms=p95,
            p99_latency_ms=p99
        )


@dataclass
class OperationResult:
    """Result of a single operation"""
    operation_id: str
    operation_type: str
    component: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    success: bool
    error: Optional[str] = None
    
    @classmethod
    def from_timing(cls, operation_id: str, operation_type: str, component: str,
                   start_time: datetime, end_time: datetime, success: bool, error: Optional[str] = None):
        duration = (end_time - start_time).total_seconds() * 1000  # Convert to ms
        return cls(
            operation_id=operation_id,
            operation_type=operation_type,
            component=component,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration,
            success=success,
            error=error
        )


class PersistenceLoadTest:
    """Load test persistence components"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.results: List[OperationResult] = []
        self._lock = threading.Lock()
        
        # Create test directory
        self.test_dir = self.data_dir / "load_test"
        self.test_dir.mkdir(exist_ok=True)
    
    def _record_result(self, result: OperationResult):
        """Record an operation result"""
        with self._lock:
            self.results.append(result)
    
    def test_agent_registry_concurrent(self, num_agents: int = 100, num_threads: int = 10) -> List[OperationResult]:
        """Test concurrent agent registration/deregistration"""
        print(f"Testing AgentRegistry with {num_agents} agents using {num_threads} threads...")
        
        # Create test file
        test_file = self.test_dir / "agent_registry_load_test.jsonl"
        if test_file.exists():
            test_file.unlink()
        
        # Initialize AgentRegistry
        config = AgentRegistryConfig(
            persistence_enabled=True,
            registry_file=str(test_file)
        )
        registry = AgentRegistry(config)
        
        # Function to register an agent
        def register_agent(agent_id: int):
            op_id = f"agent_reg_{agent_id}"
            start_time = datetime.now()
            
            try:
                registry.register_agent(
                    agent_id=f"load_test_agent_{agent_id}",
                    endpoint=f"http://127.0.0.1:{9000 + agent_id}",
                    capabilities=["ping", "echo", "compute"],
                    metadata={
                        "load_test": True,
                        "thread": threading.current_thread().name,
                        "timestamp": datetime.now().isoformat()
                    }
                )
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
            
            end_time = datetime.now()
            
            result = OperationResult.from_timing(
                op_id, "register_agent", "AgentRegistry",
                start_time, end_time, success, error
            )
            self._record_result(result)
            return result
        
        # Run concurrent registrations
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(register_agent, i) for i in range(num_agents)]
            concurrent.futures.wait(futures)
        
        # Verify all agents registered
        registered_count = len([r for r in self.results if r.component == "AgentRegistry" and r.success])
        print(f"  Registered {registered_count}/{num_agents} agents")
        
        # Test concurrent reads
        def read_agent(agent_id: int):
            op_id = f"agent_read_{agent_id}"
            start_time = datetime.now()
            
            try:
                agent = registry.get_agent(f"load_test_agent_{agent_id}")
                success = agent is not None
                error = None if success else "Agent not found"
            except Exception as e:
                success = False
                error = str(e)
            
            end_time = datetime.now()
            
            result = OperationResult.from_timing(
                op_id, "get_agent", "AgentRegistry",
                start_time, end_time, success, error
            )
            self._record_result(result)
            return result
        
        print("Testing concurrent agent reads...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_agent, i) for i in range(min(100, num_agents))]
            concurrent.futures.wait(futures)
        
        # Test concurrent deregistrations
        def deregister_agent(agent_id: int):
            op_id = f"agent_dereg_{agent_id}"
            start_time = datetime.now()
            
            try:
                registry.deregister_agent(f"load_test_agent_{agent_id}")
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
            
            end_time = datetime.now()
            
            result = OperationResult.from_timing(
                op_id, "deregister_agent", "AgentRegistry",
                start_time, end_time, success, error
            )
            self._record_result(result)
            return result
        
        print("Testing concurrent agent deregistrations...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Deregister half the agents
            agents_to_deregister = list(range(num_agents // 2))
            futures = [executor.submit(deregister_agent, i) for i in agents_to_deregister]
            concurrent.futures.wait(futures)
        
        # Cleanup
        registry = None
        if test_file.exists():
            # Keep file for inspection
            pass
        
        # Get results for this test
        agent_results = [r for r in self.results if r.component == "AgentRegistry"]
        return agent_results
    
    def test_orchestration_manager_concurrent(self, num_plans: int = 50, num_threads: int = 5) -> List[OperationResult]:
        """Test concurrent orchestration plan operations"""
        print(f"Testing OrchestrationManager with {num_plans} plans using {num_threads} threads...")
        
        # Create test files
        plans_file = self.test_dir / "orchestration_plans_load_test.jsonl"
        log_file = self.test_dir / "orchestration_log_load_test.jsonl"
        
        for f in [plans_file, log_file]:
            if f.exists():
                f.unlink()
        
        # Initialize OrchestrationManager
        config = OrchestrationManagerConfig(
            persistence_enabled=True,
            plans_file=str(plans_file),
            log_file=str(log_file)
        )
        manager = OrchestrationManager(config)
        
        # Function to create a plan
        def create_plan(plan_id: int):
            op_id = f"plan_create_{plan_id}"
            start_time = datetime.now()
            
            try:
                plan = manager.create_plan(
                    name=f"load_test_plan_{plan_id}",
                    description=f"Load test plan {plan_id}",
                    steps=[
                        {
                            "name": f"step_{plan_id}_1",
                            "intent_type": "ping",
                            "parameters": {"target": f"agent_{plan_id % 10}"}
                        },
                        {
                            "name": f"step_{plan_id}_2",
                            "intent_type": "echo",
                            "parameters": {"message": f"Load test message {plan_id}"}
                        },
                        {
                            "name": f"step_{plan_id}_3",
                            "intent_type": "compute",
                            "parameters": {"operation": "add", "values": [plan_id, plan_id * 2]}
                        }
                    ]
                )
                success = plan is not None
                error = None
            except Exception as e:
                success = False
                error = str(e)
            
            end_time = datetime.now()
            
            result = OperationResult.from_timing(
                op_id, "create_plan", "OrchestrationManager",
                start_time, end_time, success, error
            )
            self._record_result(result)
            return result
        
        # Run concurrent plan creation
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_plan, i) for i in range(num_plans)]
            concurrent.futures.wait(futures)
        
        # Test concurrent plan reads
        def read_plan(plan_id: int):
            op_id = f"plan_read_{plan_id}"
            start_time = datetime.now()
            
            try:
                # Get plan by ID (they're stored with UUIDs, so we get by index)
                all_plans = manager.list_plans()
                if plan_id < len(all_plans):
                    plan = all_plans[plan_id]
                    success = plan is not None
                    error = None
                else:
                    success = False
                    error = "Plan not found"
            except Exception as e:
                success = False
                error = str(e)
            
            end_time = datetime.now()
            
            result = OperationResult.from_timing(
                op_id, "get_plan", "OrchestrationManager",
                start_time, end_time, success, error
            )
            self._record_result(result)
            return result
        
        print("Testing concurrent plan reads...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_plan, i) for i in range(min(20, num_plans))]
            concurrent.futures.wait(futures)
        
        # Test plan execution
        def execute_plan(plan_id: int):
            op_id = f"plan_exec_{plan_id}"
            start_time = datetime.now()
            
            try:
                all_plans = manager.list_plans()
                if plan_id < len(all_plans):
                    plan = all_plans[plan_id]
                    # Start execution (simulated - would normally run steps)
                    manager.update_plan_status(plan.plan_id, "running")
                    time.sleep(0.01)  # Simulate work
                    manager.update_plan_status(plan.plan_id, "completed")
                    success = True
                    error = None
                else:
                    success = False
                    error = "Plan not found"
            except Exception as e:
                success = False
                error = str(e)
            
            end_time = datetime.now()
            
            result = OperationResult.from_timing(
                op_id, "execute_plan", "OrchestrationManager",
                start_time, end_time, success, error
            )
            self._record_result(result)
            return result
        
        print("Testing concurrent plan execution...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(execute_plan, i) for i in range(min(10, num_plans))]
            concurrent.futures.wait(futures)
        
        # Cleanup
        manager = None
        
        # Get results for this test
        orchestration_results = [r for r in self.results if r.component == "OrchestrationManager"]
        return orchestration_results
    
    def test_intent_ledger_high_volume(self, num_intents: int = 1000, batch_size: int = 100) -> List[OperationResult]:
        """Test high-volume intent logging"""
        print(f"Testing IntentLedger with {num_intents} intents (batch size: {batch_size})...")
        
        # Create test file
        test_file = self.test_dir / "intent_ledger_load_test.jsonl"
        if test_file.exists():
            test_file.unlink()
        
        # Initialize IntentLedger
        ledger = IntentLedger(str(test_file))
        
        # Test sequential writes
        print("Testing sequential intent logging...")
        sequential_results = []
        
        for i in range(num_intents):
            op_id = f"intent_seq_{i}"
            start_time = datetime.now()
            
            try:
                ledger.record_intent(
                    intent_id=f"load_test_intent_{i}",
                    intent_type=random.choice(["ping", "echo", "compute", "route", "analyze"]),
                    source_agent=f"agent_{i % 50}",
                    target_agent=f"agent_{(i + 1) % 50}",
                    timestamp=datetime.now().isoformat(),
                    payload={"iteration": i, "data": "x" * random.randint(10, 1000)}
                )
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
            
            end_time = datetime.now()
            
            result = OperationResult.from_timing(
                op_id, "record_intent", "IntentLedger",
                start_time, end_time, success, error
            )
            sequential_results.append(result)
            self._record_result(result)
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{num_intents} intents")
        
        # Test batch reads
        print("Testing intent ledger reads...")
        read_results = []
        
        # Read all intents
        start_time = datetime.now()
        try:
            # Note: IntentLedger doesn't have a read_all method in the current implementation
            # This simulates reading the file
            with open(test_file, 'r') as f:
                lines = f.readlines()
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
        
        end_time = datetime.now()
        
        result = OperationResult.from_timing(
            "intent_read_all", "read_all", "IntentLedger",
            start_time, end_time, success, error
        )
        read_results.append(result)
        self._record_result(result)
        
        print(f"  Read {len(lines) if success else 0} intent records")
        
        # Cleanup
        ledger = None
        
        # Get results for this test
        ledger_results = [r for r in self.results if r.component == "IntentLedger"]
        return ledger_results
    
    def test_mixed_workload(self, duration_seconds: int = 60, num_threads: int = 20):
        """Test mixed workload simulating production traffic"""
        print(f"Testing mixed workload for {duration_seconds} seconds with {num_threads} threads...")
        
        # Create test files
        test_files = {
            "agent_registry": self.test_dir / "mixed_agent_registry.jsonl",
            "orchestration_plans": self.test_dir / "mixed_orchestration_plans.jsonl",
            "orchestration_log": self.test_dir / "mixed_orchestration_log.jsonl",
            "intent_ledger": self.test_dir / "mixed_intent_ledger.jsonl"
        }
        
        for f in test_files.values():
            if f.exists():
                f.unlink()
        
        # Initialize components
        agent_config = AgentRegistryConfig(
            persistence_enabled=True,
            registry_file=str(test_files["agent_registry"])
        )
        agent_registry = AgentRegistry(agent_config)
        
        orchestration_config = OrchestrationManagerConfig(
            persistence_enabled=True,
            plans_file=str(test_files["orchestration_plans"]),
            log_file=str(test_files["orchestration_log"])
        )
        orchestration_manager = OrchestrationManager(orchestration_config)
        
        intent_ledger = IntentLedger(str(test_files["intent_ledger"]))
        
        # Statistics
        self._mixed_ops_count = 0
        self._mixed_start_time = datetime.now()
        self._mixed_stop = False
        
        # Worker function
        def mixed_worker(worker_id: int):
            """Worker thread performing mixed operations"""
            rng = random.Random(worker_id)
            
            while not self._mixed_stop:
                # Choose random operation
                op_type = rng.choices(
                    ["agent_register", "agent_deregister", "plan_create", "intent_log", "plan_execute"],
                    weights=[0.2, 0.1, 0.15, 0.4, 0.15]
                )[0]
                
                try:
                    if op_type == "agent_register":
                        agent_id = f"mixed_agent_{worker_id}_{rng.randint(0, 1000)}"
                        agent_registry.register_agent(
                            agent_id=agent_id,
                            endpoint=f"http://127.0.0.1:{10000 + worker_id}",
                            capabilities=["ping", "echo"],
                            metadata={"worker": worker_id, "timestamp": datetime.now().isoformat()}
                        )
                        
                    elif op_type == "agent_deregister":
                        # Try to deregister a random agent (may not exist)
                        agent_id = f"mixed_agent_{rng.randint(0, 5)}_{rng.randint(0, 100)}"
                        agent_registry.deregister_agent(agent_id)
                        
                    elif op_type == "plan_create":
                        plan_name = f"mixed_plan_{worker_id}_{rng.randint(0, 1000)}"
                        orchestration_manager.create_plan(
                            name=plan_name,
                            description=f"Mixed workload plan from worker {worker_id}",
                            steps=[
                                {
                                    "name": "step1",
                                    "intent_type": "ping",
                                    "parameters": {"target": f"agent_{rng.randint(0, 10)}"}
                                }
                            ]
                        )
                        
                    elif op_type == "intent_log":
                        intent_ledger.record_intent(
                            intent_id=f"mixed_intent_{worker_id}_{self._mixed_ops_count}",
                            intent_type=rng.choice(["ping", "echo", "compute"]),
                            source_agent=f"agent_{rng.randint(0, 10)}",
                            target_agent=f"agent_{rng.randint(0, 10)}",
                            timestamp=datetime.now().isoformat(),
                            payload={"worker": worker_id, "op_count": self._mixed_ops_count}
                        )
                        
                    elif op_type == "plan_execute":
                        # Get a plan and update its status
                        plans = orchestration_manager.list_plans()
                        if plans:
                            plan = rng.choice(plans)
                            orchestration_manager.update_plan_status(
                                plan.plan_id,
                                rng.choice(["running", "completed", "failed"])
                            )
                    
                    # Record successful operation
                    with self._lock:
                        self._mixed_ops_count += 1
                        
                except Exception:
                    # Expected that some operations will fail (e.g., deregister non-existent agent)
                    pass
                
                # Small random delay between operations
                time.sleep(rng.uniform(0.001, 0.01))
        
        # Start workers
        print("Starting mixed workload workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(mixed_worker, i) for i in range(num_threads)]
            
            # Run for specified duration
            time.sleep(duration_seconds)
            self._mixed_stop = True
            
            # Wait for workers to finish
            concurrent.futures.wait(futures, timeout=5)
        
        # Record results
        end_time = datetime.now()
        duration = (end_time - self._mixed_start_time).total_seconds()
        ops_per_sec = self._mixed_ops_count / duration if duration > 0 else 0
        
        print(f"Mixed workload completed:")
        print(f"  Total operations: {self._mixed_ops_count:,}")
        print(f"  Duration: {duration:.1f} seconds")
        print(f"  Throughput: {ops_per_sec:.1f} ops/sec")
        
        # Check file sizes
        print("\nFinal file sizes:")
        for name, path in test_files.items():
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"  {name:20} {size_mb:8.2f} MB")
        
        # Cleanup
        agent_registry = None
        orchestration_manager = None
        intent_ledger = None
        
        # Create a summary result
        summary_result = OperationResult.from_timing(
            "mixed_workload_summary", "mixed", "All",
            self._mixed_start_time, end_time, True
        )
        self._record_result(summary_result)
        
        return [summary_result]
    
    def run_scenario(self, scenario: str, **kwargs) -> LoadTestResult:
        """Run a specific test scenario"""
        print(f"\n{'=' * 80}")
        print(f"Running load test scenario: {scenario}")
        print(f"{'=' * 80}")
        
        start_time = datetime.now()
        
        if scenario == "agent_registry":
            results = self.test_agent_registry_concurrent(
                num_agents=kwargs.get('num_agents', 100),
                num_threads=kwargs.get('num_threads', 10)
            )
            
        elif scenario == "orchestration":
            results = self.test_orchestration_manager_concurrent(
                num_plans=kwargs.get('num_plans', 50),
                num_threads=kwargs.get('num_threads', 5)
            )
            
        elif scenario == "intent_ledger":
            results = self.test_intent_ledger_high_volume(
                num_intents=kwargs.get('num_intents', 1000),
                batch_size=kwargs.get('batch_size', 100)
            )
            
        elif scenario == "mixed":
            results = self.test_mixed_workload(
                duration_seconds=kwargs.get('duration', 60),
                num_threads=kwargs.get('num_threads', 20)
            )
            
        elif scenario == "production":
            # Run all tests in sequence
            all_results = []
            
            # Agent registry test
            print("\n--- Phase 1: Agent Registry ---")
            agent_results = self.test_agent_registry_concurrent(200, 20)
            all_results.extend(agent_results)
            
            # Orchestration test
            print("\n--- Phase 2: Orchestration Manager ---")
            orchestration_results = self.test_orchestration_manager_concurrent(100, 10)
            all_results.extend(orchestration_results)
            
            # Intent ledger test
            print("\n--- Phase 3: Intent Ledger ---")
            ledger_results = self.test_intent_ledger_high_volume(5000, 500)
            all_results.extend(ledger_results)
            
            # Mixed workload test
            print("\n--- Phase 4: Mixed Workload ---")
            mixed_results = self.test_mixed_workload(120, 30)
            all_results.extend(mixed_results)
            
            results = all_results
            
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
        
        end_time = datetime.now()
        
        # Create overall result
        overall_result = LoadTestResult.create(scenario, start_time, end_time, results)
        
        # Add component metrics
        component_results = {}
        for component in ["AgentRegistry", "OrchestrationManager", "IntentLedger"]:
            component_ops = [r for r in results if r.component == component]
            if component_ops:
                component_success = sum(1 for r in component_ops if r.success)
                component_latencies = [r.duration_ms for r in component_ops if r.success]
                
                component_results[component] = {
                    "operations": len(component_ops),
                    "success_rate": component_success / len(component_ops) if component_ops else 0,
                    "avg_latency_ms": statistics.mean(component_latencies) if component_latencies else 0,
                    "min_latency_ms": min(component_latencies) if component_latencies else 0,
                    "max_latency_ms": max(component_latencies) if component_latencies else 0
                }
        
        overall_result.component_metrics = component_results
        
        return overall_result
    
    def save_results(self, results: LoadTestResult, output_dir: Optional[Path] = None):
        """Save test results to file"""
        if output_dir is None:
            output_dir = self.test_dir
        
        output_dir.mkdir(exist_ok=True)
        
        # Save main results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = output_dir / f"load_test_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(asdict(results), f, indent=2)
        
        print(f"Results saved to: {results_file}")
        
        # Save detailed operation results
        if self.results:
            ops_file = output_dir / f"load_test_operations_{timestamp}.json"
            ops_data = [asdict(r) for r in self.results]
            
            with open(ops_file, 'w') as f:
                json.dump(ops_data, f, indent=2)
            
            print(f"Detailed operations saved to: {ops_file}")
        
        return results_file


def main():
    parser = argparse.ArgumentParser(description="Persistence Load Test for SIMP System")
    
    # Test scenarios
    parser.add_argument("--scenario", type=str, default="production",
                       choices=["agent_registry", "orchestration", "intent_ledger", "mixed", "production"],
                       help="Test scenario to run")
    
    # Scenario parameters
    parser.add_argument("--agents", type=int, default=100, help="Number of agents for agent registry test")
    parser.add_argument("--plans", type=int, default=50, help="Number of plans for orchestration test")
    parser.add_argument("--intents", type=int, default=1000, help="Number of intents for intent ledger test")
    parser.add_argument("--threads", type=int, default=10, help="Number of concurrent threads")
    parser.add_argument("--duration", type=int, default=60, help="Duration for mixed workload test (seconds)")
    
    # Output options
    parser.add_argument("--output-dir", type=str, default="data/load_test", help="Output directory for results")
    parser.add_argument("--no-save", action="store_true", help="Don't save results to file")
    
    # Data directory
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory path")
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}")
        sys.exit(1)
    
    # Create load tester
    tester = PersistenceLoadTest(data_dir)
    
    # Run test scenario
    scenario_params = {
        "num_agents": args.agents,
        "num_plans": args.plans,
        "num_intents": args.intents,
        "num_threads": args.threads,
        "duration": args.duration
    }
    
    try:
        result = tester.run_scenario(args.scenario, **scenario_params)
        
        # Print results
        print(f"\n{'=' * 80}")
        print(f"LOAD TEST COMPLETE: {args.scenario}")
        print(f"{'=' * 80}")
        print(f"Duration:          {result.duration_seconds:.1f} seconds")
        print(f"Total operations:  {result.total_operations:,}")
        print(f"Successful:        {result.successful_operations:,}")
        print(f"Failed:            {result.failed_operations:,}")
        print(f"Success rate:      {result.success_rate:.1%}")
        print(f"Throughput:        {result.operations_per_second:.1f} ops/sec")
        print()
        print(f"Latency (ms):")
        print(f"  Average:         {result.avg_latency_ms:.3f}")
        print(f"  Minimum:         {result.min_latency_ms:.3f}")
        print(f"  Maximum:         {result.max_latency_ms:.3f}")
        print(f"  P95:             {result.p95_latency_ms:.3f}")
        print(f"  P99:             {result.p99_latency_ms:.3f}")
        
        # Print component metrics
        if result.component_metrics:
            print(f"\nComponent Metrics:")
            for component, metrics in result.component_metrics.items():
                print(f"  {component}:")
                print(f"    Operations:    {metrics['operations']:,}")
                print(f"    Success rate:  {metrics['success_rate']:.1%}")
                print(f"    Avg latency:   {metrics['avg_latency_ms']:.3f} ms")
        
        # Save results
        if not args.no_save:
            output_dir = Path(args.output_dir)
            results_file = tester.save_results(result, output_dir)
            print(f"\nResults saved to: {results_file}")
        
        # Check for issues
        if result.success_rate < 0.95:
            print(f"\n⚠ WARNING: Low success rate ({result.success_rate:.1%})")
            print("  Check for concurrency issues or resource constraints")
        
        if result.avg_latency_ms > 100:
            print(f"\n⚠ WARNING: High average latency ({result.avg_latency_ms:.1f} ms)")
            print("  Consider performance optimizations for persistence operations")
        
        if result.max_latency_ms > 1000:
            print(f"\n⚠ WARNING: Very high maximum latency ({result.max_latency_ms:.1f} ms)")
            print("  Check for locking contention or disk I/O issues")
        
    except Exception as e:
        print(f"\n❌ Load test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()