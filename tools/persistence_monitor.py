#!/usr/bin/env python3
"""
Persistence Performance Monitor for SIMP System

This tool monitors and benchmarks persistence operations for:
- AgentRegistry JSONL operations
- OrchestrationManager plan persistence  
- IntentLedger append operations
- File rotation and cleanup

Usage:
    python3 tools/persistence_monitor.py [--interval 60] [--output metrics.json]
    python3 tools/persistence_monitor.py --benchmark [--iterations 1000]
"""

import json
import time
import threading
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.agent_registry import AgentRegistry, AgentRegistryConfig
from simp.orchestration.orchestration_manager import OrchestrationManager, OrchestrationManagerConfig


@dataclass
class PersistenceMetrics:
    """Metrics collected for persistence operations"""
    timestamp: str
    operation: str
    duration_ms: float
    file_size_bytes: int
    line_count: int
    success: bool
    error: Optional[str] = None
    
    @classmethod
    def now(cls, operation: str, duration_ms: float, file_path: Path, success: bool, error: Optional[str] = None):
        """Create metrics with current timestamp"""
        file_size = file_path.stat().st_size if file_path.exists() else 0
        line_count = 0
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    line_count = sum(1 for _ in f)
            except:
                line_count = 0
        
        return cls(
            timestamp=datetime.utcnow().isoformat() + "Z",
            operation=operation,
            duration_ms=duration_ms,
            file_size_bytes=file_size,
            line_count=line_count,
            success=success,
            error=error
        )


@dataclass
class BenchmarkResult:
    """Results from performance benchmarking"""
    timestamp: str
    component: str
    operation: str
    iterations: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    throughput_ops_per_sec: float
    file_size_before_bytes: int
    file_size_after_bytes: int
    file_growth_bytes: int


class PersistenceMonitor:
    """Monitor persistence operations and collect metrics"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.metrics: List[PersistenceMetrics] = []
        self._lock = threading.Lock()
        self._running = False
        
        # File paths to monitor
        self.files_to_monitor = {
            "agent_registry": self.data_dir / "agent_registry.jsonl",
            "task_ledger": self.data_dir / "task_ledger.jsonl",
            "orchestration_plans": self.data_dir / "orchestration_plans.jsonl",
            "orchestration_log": self.data_dir / "orchestration_log.jsonl",
            "financial_ops": self.data_dir / "financial_ops_proposals.jsonl",
        }
    
    def record_operation(self, operation: str, duration_ms: float, file_path: Path, success: bool, error: Optional[str] = None):
        """Record a persistence operation"""
        with self._lock:
            metric = PersistenceMetrics.now(operation, duration_ms, file_path, success, error)
            self.metrics.append(metric)
            return metric
    
    def get_file_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get current statistics for all monitored files"""
        stats = {}
        for name, path in self.files_to_monitor.items():
            if path.exists():
                stat = path.stat()
                lines = 0
                with open(path, 'r') as f:
                    lines = sum(1 for _ in f)
                
                stats[name] = {
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "line_count": lines,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "exists": True
                }
            else:
                stats[name] = {
                    "path": str(path),
                    "exists": False
                }
        return stats
    
    def get_recent_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent metrics as dictionaries"""
        with self._lock:
            recent = self.metrics[-limit:] if self.metrics else []
            return [asdict(m) for m in recent]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all recorded metrics"""
        with self._lock:
            if not self.metrics:
                return {"total_operations": 0}
            
            # Group by operation
            by_operation = {}
            for metric in self.metrics:
                if metric.operation not in by_operation:
                    by_operation[metric.operation] = []
                by_operation[metric.operation].append(metric.duration_ms)
            
            # Calculate stats per operation
            operation_stats = {}
            for op, durations in by_operation.items():
                operation_stats[op] = {
                    "count": len(durations),
                    "avg_ms": statistics.mean(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                    "p95_ms": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
                    "success_rate": sum(1 for m in self.metrics if m.operation == op and m.success) / len(durations)
                }
            
            # Overall stats
            all_durations = [m.duration_ms for m in self.metrics]
            success_count = sum(1 for m in self.metrics if m.success)
            
            return {
                "total_operations": len(self.metrics),
                "success_rate": success_count / len(self.metrics) if self.metrics else 0,
                "avg_duration_ms": statistics.mean(all_durations) if all_durations else 0,
                "min_duration_ms": min(all_durations) if all_durations else 0,
                "max_duration_ms": max(all_durations) if all_durations else 0,
                "operations": operation_stats,
                "file_stats": self.get_file_stats(),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def save_metrics(self, output_path: Path):
        """Save metrics to JSON file"""
        with self._lock:
            data = {
                "summary": self.get_summary_stats(),
                "recent_metrics": self.get_recent_metrics(1000),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
    
    def monitor_file_growth(self, interval_seconds: int = 60):
        """Monitor file growth at regular intervals"""
        self._running = True
        
        initial_sizes = {}
        for name, path in self.files_to_monitor.items():
            if path.exists():
                initial_sizes[name] = path.stat().st_size
            else:
                initial_sizes[name] = 0
        
        print(f"Starting file growth monitoring (interval: {interval_seconds}s)")
        print("Press Ctrl+C to stop\n")
        
        try:
            while self._running:
                time.sleep(interval_seconds)
                
                current_stats = self.get_file_stats()
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] File Statistics:")
                print("-" * 80)
                
                for name, stats in current_stats.items():
                    if stats.get("exists"):
                        growth = stats["size_bytes"] - initial_sizes.get(name, 0)
                        growth_mb = growth / (1024 * 1024)
                        print(f"{name:20} | {stats['line_count']:8,d} lines | "
                              f"{stats['size_bytes'] / 1024:8.1f} KB | "
                              f"Growth: {growth_mb:+.2f} MB")
                    else:
                        print(f"{name:20} | File does not exist")
                
                # Update initial sizes for next interval
                for name, stats in current_stats.items():
                    if stats.get("exists"):
                        initial_sizes[name] = stats["size_bytes"]
                
                sys.stdout.flush()
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
            self._running = False
    
    def stop(self):
        """Stop monitoring"""
        self._running = False


class PersistenceBenchmark:
    """Benchmark persistence operations"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.results: List[BenchmarkResult] = []
    
    def benchmark_agent_registry(self, iterations: int = 1000) -> BenchmarkResult:
        """Benchmark AgentRegistry operations"""
        print(f"Benchmarking AgentRegistry with {iterations} iterations...")
        
        # Create temporary file for benchmarking
        temp_file = self.data_dir / "benchmark_agent_registry.jsonl"
        if temp_file.exists():
            temp_file.unlink()
        
        # Initialize AgentRegistry
        config = AgentRegistryConfig(
            persistence_enabled=True,
            registry_file=str(temp_file)
        )
        registry = AgentRegistry(config)
        
        # Measure registration operations
        durations = []
        file_size_before = temp_file.stat().st_size if temp_file.exists() else 0
        
        for i in range(iterations):
            agent_id = f"benchmark_agent_{i}"
            start_time = time.perf_counter()
            
            try:
                registry.register_agent(
                    agent_id=agent_id,
                    endpoint=f"http://127.0.0.1:{8000 + i}",
                    capabilities=["ping", "echo"],
                    metadata={"benchmark": True, "iteration": i}
                )
                success = True
            except Exception as e:
                success = False
                print(f"Error in iteration {i}: {e}")
            
            end_time = time.perf_counter()
            durations.append((end_time - start_time) * 1000)  # Convert to ms
        
        file_size_after = temp_file.stat().st_size if temp_file.exists() else 0
        
        # Cleanup
        registry = None
        if temp_file.exists():
            temp_file.unlink()
        
        # Calculate statistics
        if durations:
            avg = statistics.mean(durations)
            min_val = min(durations)
            max_val = max(durations)
            p50 = statistics.quantiles(durations, n=2)[0]
            p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
            p99 = statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else max(durations)
            throughput = iterations / (sum(durations) / 1000)  # ops per second
        else:
            avg = min_val = max_val = p50 = p95 = p99 = throughput = 0
        
        result = BenchmarkResult(
            timestamp=datetime.utcnow().isoformat() + "Z",
            component="AgentRegistry",
            operation="register_agent",
            iterations=iterations,
            total_duration_ms=sum(durations),
            avg_duration_ms=avg,
            min_duration_ms=min_val,
            max_duration_ms=max_val,
            p50_duration_ms=p50,
            p95_duration_ms=p95,
            p99_duration_ms=p99,
            throughput_ops_per_sec=throughput,
            file_size_before_bytes=file_size_before,
            file_size_after_bytes=file_size_after,
            file_growth_bytes=file_size_after - file_size_before
        )
        
        self.results.append(result)
        return result
    
    def benchmark_orchestration_manager(self, iterations: int = 100) -> BenchmarkResult:
        """Benchmark OrchestrationManager operations"""
        print(f"Benchmarking OrchestrationManager with {iterations} iterations...")
        
        # Create temporary files
        plans_file = self.data_dir / "benchmark_orchestration_plans.jsonl"
        log_file = self.data_dir / "benchmark_orchestration_log.jsonl"
        
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
        
        # Measure plan creation operations
        durations = []
        file_size_before = plans_file.stat().st_size if plans_file.exists() else 0
        
        for i in range(iterations):
            plan_name = f"benchmark_plan_{i}"
            start_time = time.perf_counter()
            
            try:
                plan = manager.create_plan(
                    name=plan_name,
                    description=f"Benchmark plan {i}",
                    steps=[
                        {
                            "name": f"step_{i}_1",
                            "intent_type": "ping",
                            "parameters": {"target": "test_agent"}
                        },
                        {
                            "name": f"step_{i}_2", 
                            "intent_type": "echo",
                            "parameters": {"message": f"benchmark {i}"}
                        }
                    ]
                )
                success = True
            except Exception as e:
                success = False
                print(f"Error in iteration {i}: {e}")
            
            end_time = time.perf_counter()
            durations.append((end_time - start_time) * 1000)  # Convert to ms
        
        file_size_after = plans_file.stat().st_size if plans_file.exists() else 0
        
        # Cleanup
        manager = None
        for f in [plans_file, log_file]:
            if f.exists():
                f.unlink()
        
        # Calculate statistics
        if durations:
            avg = statistics.mean(durations)
            min_val = min(durations)
            max_val = max(durations)
            p50 = statistics.quantiles(durations, n=2)[0]
            p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
            p99 = statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else max(durations)
            throughput = iterations / (sum(durations) / 1000)  # ops per second
        else:
            avg = min_val = max_val = p50 = p95 = p99 = throughput = 0
        
        result = BenchmarkResult(
            timestamp=datetime.utcnow().isoformat() + "Z",
            component="OrchestrationManager",
            operation="create_plan",
            iterations=iterations,
            total_duration_ms=sum(durations),
            avg_duration_ms=avg,
            min_duration_ms=min_val,
            max_duration_ms=max_val,
            p50_duration_ms=p50,
            p95_duration_ms=p95,
            p99_duration_ms=p99,
            throughput_ops_per_sec=throughput,
            file_size_before_bytes=file_size_before,
            file_size_after_bytes=file_size_after,
            file_growth_bytes=file_size_after - file_size_before
        )
        
        self.results.append(result)
        return result
    
    def benchmark_jsonl_append(self, iterations: int = 10000) -> BenchmarkResult:
        """Benchmark raw JSONL append operations"""
        print(f"Benchmarking JSONL append with {iterations} iterations...")
        
        temp_file = self.data_dir / "benchmark_jsonl_append.jsonl"
        if temp_file.exists():
            temp_file.unlink()
        
        # Measure append operations
        durations = []
        file_size_before = 0
        
        for i in range(iterations):
            record = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "operation": "benchmark",
                "iteration": i,
                "data": "x" * 100  # 100 bytes of data
            }
            
            start_time = time.perf_counter()
            
            try:
                with open(temp_file, 'a') as f:
                    f.write(json.dumps(record) + "\n")
                success = True
            except Exception as e:
                success = False
                print(f"Error in iteration {i}: {e}")
            
            end_time = time.perf_counter()
            durations.append((end_time - start_time) * 1000)  # Convert to ms
        
        file_size_after = temp_file.stat().st_size if temp_file.exists() else 0
        
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()
        
        # Calculate statistics
        if durations:
            avg = statistics.mean(durations)
            min_val = min(durations)
            max_val = max(durations)
            p50 = statistics.quantiles(durations, n=2)[0]
            p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
            p99 = statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else max(durations)
            throughput = iterations / (sum(durations) / 1000)  # ops per second
        else:
            avg = min_val = max_val = p50 = p95 = p99 = throughput = 0
        
        result = BenchmarkResult(
            timestamp=datetime.utcnow().isoformat() + "Z",
            component="JSONL",
            operation="append",
            iterations=iterations,
            total_duration_ms=sum(durations),
            avg_duration_ms=avg,
            min_duration_ms=min_val,
            max_duration_ms=max_val,
            p50_duration_ms=p50,
            p95_duration_ms=p95,
            p99_duration_ms=p99,
            throughput_ops_per_sec=throughput,
            file_size_before_bytes=file_size_before,
            file_size_after_bytes=file_size_after,
            file_growth_bytes=file_size_after - file_size_before
        )
        
        self.results.append(result)
        return result
    
    def run_all_benchmarks(self, iterations: Dict[str, int] = None):
        """Run all benchmarks"""
        if iterations is None:
            iterations = {
                "agent_registry": 1000,
                "orchestration": 100,
                "jsonl_append": 10000
            }
        
        print("=" * 80)
        print("Running Persistence Benchmarks")
        print("=" * 80)
        
        results = []
        
        # Run benchmarks
        if "agent_registry" in iterations:
            result = self.benchmark_agent_registry(iterations["agent_registry"])
            results.append(result)
            self._print_benchmark_result(result)
        
        if "orchestration" in iterations:
            result = self.benchmark_orchestration_manager(iterations["orchestration"])
            results.append(result)
            self._print_benchmark_result(result)
        
        if "jsonl_append" in iterations:
            result = self.benchmark_jsonl_append(iterations["jsonl_append"])
            results.append(result)
            self._print_benchmark_result(result)
        
        # Save results
        output_file = self.data_dir / "persistence_benchmark_results.json"
        with open(output_file, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
        return results
    
    def _print_benchmark_result(self, result: BenchmarkResult):
        """Print benchmark result in readable format"""
        print(f"\n{'=' * 60}")
        print(f"Benchmark: {result.component} - {result.operation}")
        print(f"{'=' * 60}")
        print(f"Iterations:      {result.iterations:,}")
        print(f"Total time:      {result.total_duration_ms/1000:.3f} s")
        print(f"Avg duration:    {result.avg_duration_ms:.3f} ms")
        print(f"Min duration:    {result.min_duration_ms:.3f} ms")
        print(f"Max duration:    {result.max_duration_ms:.3f} ms")
        print(f"P50 duration:    {result.p50_duration_ms:.3f} ms")
        print(f"P95 duration:    {result.p95_duration_ms:.3f} ms")
        print(f"P99 duration:    {result.p99_duration_ms:.3f} ms")
        print(f"Throughput:      {result.throughput_ops_per_sec:.1f} ops/sec")
        print(f"File growth:     {result.file_growth_bytes:,} bytes")
        print(f"                 ({result.file_growth_bytes/1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Persistence Performance Monitor for SIMP System")
    parser.add_argument("--monitor", action="store_true", help="Monitor file growth continuously")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmarks")
    parser.add_argument("--iterations", type=int, default=1000, help="Iterations for benchmarking")
    parser.add_argument("--output", type=str, default="persistence_metrics.json", help="Output file for metrics")
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory path")
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}")
        sys.exit(1)
    
    if args.monitor:
        # Run monitoring mode
        monitor = PersistenceMonitor(data_dir)
        try:
            monitor.monitor_file_growth(args.interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    
    elif args.benchmark:
        # Run benchmarking mode
        benchmark = PersistenceBenchmark(data_dir)
        iterations = {
            "agent_registry": args.iterations,
            "orchestration": args.iterations // 10,  # Fewer iterations for orchestration
            "jsonl_append": args.iterations * 10     # More iterations for raw append
        }
        benchmark.run_all_benchmarks(iterations)
    
    else:
        # Show current stats
        monitor = PersistenceMonitor(data_dir)
        stats = monitor.get_summary_stats()
        
        print("=" * 80)
        print("SIMP Persistence System Status")
        print("=" * 80)
        print(f"Timestamp: {stats['timestamp']}")
        print()
        
        print("File Statistics:")
        print("-" * 40)
        for name, file_stats in stats["file_stats"].items():
            if file_stats.get("exists"):
                size_mb = file_stats["size_bytes"] / (1024 * 1024)
                print(f"{name:20} | {file_stats['line_count']:8,d} lines | {size_mb:8.2f} MB")
            else:
                print(f"{name:20} | File does not exist")
        
        print()
        
        if stats["total_operations"] > 0:
            print("Performance Statistics:")
            print("-" * 40)
            print(f"Total operations: {stats['total_operations']:,}")
            print(f"Success rate:     {stats['success_rate']:.1%}")
            print(f"Avg duration:     {stats['avg_duration_ms']:.3f} ms")
            print(f"Min duration:     {stats['min_duration_ms']:.3f} ms")
            print(f"Max duration:     {stats['max_duration_ms']:.3f} ms")
            
            print()
            print("Operations Detail:")
            for op, op_stats in stats["operations"].items():
                print(f"  {op:30} | {op_stats['count']:6,d} ops | "
                      f"Avg: {op_stats['avg_ms']:6.3f} ms | "
                      f"Success: {op_stats['success_rate']:.1%}")
        
        # Save metrics
        output_path = Path(args.output)
        monitor.save_metrics(output_path)
        print(f"\nMetrics saved to: {output_path}")


if __name__ == "__main__":
    main()