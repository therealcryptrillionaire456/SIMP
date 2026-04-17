"""
Performance Optimizer - Build 18
Main performance optimization system with caching, memoization, and resource monitoring.
"""

import sys
import os
import time
import json
import hashlib
import threading
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import functools
import concurrent.futures
import psutil
import gc

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live
    MRU = "mru"  # Most Recently Used
    RANDOM = "random"


class OptimizationLevel(Enum):
    """Optimization levels."""
    NONE = "none"
    BASIC = "basic"
    AGGRESSIVE = "aggressive"
    MAXIMUM = "maximum"


@dataclass
class CacheEntry:
    """Cache entry."""
    key: str
    value: Any
    size_bytes: int
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 1
    ttl_seconds: Optional[float] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetric:
    """Performance metric."""
    metric_id: str
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    component: str = ""
    optimization_applied: bool = False
    improvement_percentage: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceUsage:
    """Resource usage snapshot."""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    disk_usage_percent: float = 0.0
    network_bytes_sent: float = 0.0
    network_bytes_recv: float = 0.0
    process_count: int = 0
    thread_count: int = 0
    open_files: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceOptimizer:
    """
    Performance Optimizer for caching, memoization, and resource optimization.
    """
    
    def __init__(self, optimizer_id: str = "performance_optimizer_001",
                 max_cache_size_mb: int = 100,
                 optimization_level: OptimizationLevel = OptimizationLevel.BASIC):
        """
        Initialize Performance Optimizer.
        
        Args:
            optimizer_id: Unique optimizer identifier
            max_cache_size_mb: Maximum cache size in MB
            optimization_level: Optimization level
        """
        self.optimizer_id = optimizer_id
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self.optimization_level = optimization_level
        
        # Cache storage
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_strategy = CacheStrategy.LRU
        self.current_cache_size = 0
        
        # Memoization storage
        self.memoization_cache: Dict[str, Any] = {}
        
        # Performance metrics
        self.performance_metrics: Dict[str, PerformanceMetric] = {}
        
        # Resource monitoring
        self.resource_history: List[ResourceUsage] = []
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Statistics
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_evictions": 0,
            "memoization_hits": 0,
            "memoization_misses": 0,
            "total_optimizations": 0,
            "total_savings_ms": 0.0,
            "average_speedup": 0.0
        }
        
        # Thread pool for parallel processing
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._get_optimal_worker_count(),
            thread_name_prefix=f"{optimizer_id}_worker"
        )
        
        logger.info(f"Initialized Performance Optimizer {optimizer_id} "
                   f"(cache: {max_cache_size_mb}MB, level: {optimization_level.value})")
    
    def _get_optimal_worker_count(self) -> int:
        """Get optimal worker count based on system resources."""
        cpu_count = os.cpu_count() or 4
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        if self.optimization_level == OptimizationLevel.NONE:
            return 1
        elif self.optimization_level == OptimizationLevel.BASIC:
            return min(4, cpu_count)
        elif self.optimization_level == OptimizationLevel.AGGRESSIVE:
            return min(8, cpu_count * 2)
        else:  # MAXIMUM
            return min(16, cpu_count * 4)
    
    def cache_function(self, ttl_seconds: Optional[float] = None,
                      max_size_bytes: Optional[int] = None):
        """
        Decorator for caching function results.
        
        Args:
            ttl_seconds: Time to live in seconds
            max_size_bytes: Maximum size for this cache entry
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self._generate_cache_key(func.__name__, args, kwargs)
                
                # Check cache
                cached_result = self.get_from_cache(cache_key)
                if cached_result is not None:
                    self.stats["cache_hits"] += 1
                    logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                    return cached_result
                
                self.stats["cache_misses"] += 1
                
                # Execute function
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Calculate result size (estimate)
                result_size = self._estimate_size(result)
                
                # Cache result
                self.add_to_cache(
                    key=cache_key,
                    value=result,
                    size_bytes=result_size,
                    ttl_seconds=ttl_seconds,
                    metadata={
                        "function": func.__name__,
                        "execution_time": execution_time,
                        "args_hash": hashlib.md5(str(args).encode()).hexdigest()[:8],
                        "kwargs_hash": hashlib.md5(str(kwargs).encode()).hexdigest()[:8]
                    }
                )
                
                # Record performance metric
                self._record_performance_metric(
                    name=f"function_{func.__name__}",
                    value=execution_time,
                    unit="seconds",
                    component="caching",
                    optimization_applied=True
                )
                
                return result
            
            return wrapper
        
        return decorator
    
    def memoize_function(self):
        """
        Decorator for memoizing function results (no expiration).
        
        Returns:
            Decorated function
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Generate memoization key
                memo_key = self._generate_memo_key(func.__name__, args, kwargs)
                
                # Check memoization cache
                if memo_key in self.memoization_cache:
                    self.stats["memoization_hits"] += 1
                    logger.debug(f"Memoization hit for {func.__name__}: {memo_key}")
                    return self.memoization_cache[memo_key]
                
                self.stats["memoization_misses"] += 1
                
                # Execute function
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Store in memoization cache
                self.memoization_cache[memo_key] = result
                
                # Record performance metric
                self._record_performance_metric(
                    name=f"memoized_{func.__name__}",
                    value=execution_time,
                    unit="seconds",
                    component="memoization",
                    optimization_applied=True
                )
                
                return result
            
            return wrapper
        
        return decorator
    
    def _generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function name and arguments."""
        args_hash = hashlib.md5(str(args).encode()).hexdigest()[:16]
        kwargs_hash = hashlib.md5(str(kwargs).encode()).hexdigest()[:16]
        return f"{func_name}_{args_hash}_{kwargs_hash}"
    
    def _generate_memo_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate memoization key from function name and arguments."""
        # More comprehensive key for memoization
        args_str = json.dumps(args, default=str, sort_keys=True)
        kwargs_str = json.dumps(kwargs, default=str, sort_keys=True)
        full_str = f"{func_name}:{args_str}:{kwargs_str}"
        return hashlib.sha256(full_str.encode()).hexdigest()
    
    def _estimate_size(self, obj: Any) -> int:
        """Estimate size of an object in bytes."""
        try:
            return len(json.dumps(obj, default=str).encode('utf-8'))
        except:
            # Fallback estimation
            return 1024  # 1KB default
    
    def add_to_cache(self, key: str, value: Any, size_bytes: int,
                    ttl_seconds: Optional[float] = None,
                    metadata: Dict[str, Any] = None) -> bool:
        """
        Add item to cache.
        
        Args:
            key: Cache key
            value: Value to cache
            size_bytes: Size of value in bytes
            ttl_seconds: Time to live in seconds
            metadata: Additional metadata
            
        Returns:
            Success status
        """
        # Check if item would exceed cache size
        if size_bytes > self.max_cache_size_bytes:
            logger.warning(f"Item too large for cache: {size_bytes} bytes > {self.max_cache_size_bytes} bytes")
            return False
        
        # Make space if needed
        while self.current_cache_size + size_bytes > self.max_cache_size_bytes and self.cache:
            self._evict_from_cache()
        
        # Calculate expiration
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            size_bytes=size_bytes,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        # Add to cache
        self.cache[key] = entry
        self.current_cache_size += size_bytes
        
        logger.debug(f"Added to cache: {key} ({size_bytes} bytes)")
        return True
    
    def get_from_cache(self, key: str) -> Any:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Check expiration
        if entry.expires_at and datetime.now() > entry.expires_at:
            self._remove_from_cache(key)
            return None
        
        # Update access statistics
        entry.last_accessed = datetime.now()
        entry.access_count += 1
        
        return entry.value
    
    def _evict_from_cache(self):
        """Evict item from cache based on strategy."""
        if not self.cache:
            return
        
        if self.cache_strategy == CacheStrategy.LRU:
            # Least Recently Used
            oldest_key = min(self.cache.keys(),
                           key=lambda k: self.cache[k].last_accessed)
            self._remove_from_cache(oldest_key)
            
        elif self.cache_strategy == CacheStrategy.LFU:
            # Least Frequently Used
            least_used_key = min(self.cache.keys(),
                               key=lambda k: self.cache[k].access_count)
            self._remove_from_cache(least_used_key)
            
        elif self.cache_strategy == CacheStrategy.FIFO:
            # First In First Out
            oldest_key = min(self.cache.keys(),
                           key=lambda k: self.cache[k].created_at)
            self._remove_from_cache(oldest_key)
            
        elif self.cache_strategy == CacheStrategy.MRU:
            # Most Recently Used
            newest_key = max(self.cache.keys(),
                           key=lambda k: self.cache[k].last_accessed)
            self._remove_from_cache(newest_key)
            
        else:  # RANDOM or TTL
            # Random eviction
            import random
            random_key = random.choice(list(self.cache.keys()))
            self._remove_from_cache(random_key)
        
        self.stats["cache_evictions"] += 1
    
    def _remove_from_cache(self, key: str):
        """Remove item from cache."""
        if key in self.cache:
            entry = self.cache[key]
            self.current_cache_size -= entry.size_bytes
            del self.cache[key]
            logger.debug(f"Removed from cache: {key}")
    
    def clear_cache(self):
        """Clear entire cache."""
        self.cache.clear()
        self.current_cache_size = 0
        logger.info("Cache cleared")
    
    def clear_memoization(self):
        """Clear memoization cache."""
        self.memoization_cache.clear()
        logger.info("Memoization cache cleared")
    
    def parallel_execute(self, tasks: List[Callable], timeout_seconds: int = 30) -> List[Any]:
        """
        Execute tasks in parallel.
        
        Args:
            tasks: List of callable tasks
            timeout_seconds: Timeout for execution
            
        Returns:
            List of results
        """
        start_time = time.time()
        
        # Submit tasks to thread pool
        futures = []
        for task in tasks:
            future = self.thread_pool.submit(task)
            futures.append(future)
        
        # Collect results
        results = []
        for future in concurrent.futures.as_completed(futures, timeout=timeout_seconds):
            try:
                result = future.result(timeout=timeout_seconds)
                results.append(result)
            except Exception as e:
                logger.error(f"Task execution failed: {str(e)}")
                results.append(None)
        
        execution_time = time.time() - start_time
        
        # Record performance metric
        self._record_performance_metric(
            name="parallel_execution",
            value=execution_time,
            unit="seconds",
            component="parallel_processing",
            optimization_applied=True,
            metadata={
                "task_count": len(tasks),
                "successful_tasks": len([r for r in results if r is not None]),
                "timeout_seconds": timeout_seconds
            }
        )
        
        return results
    
    def start_resource_monitoring(self, interval_seconds: int = 5):
        """
        Start resource monitoring.
        
        Args:
            interval_seconds: Monitoring interval in seconds
        """
        if self.monitoring_active:
            logger.warning("Resource monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.monitoring_thread.start()
        
        logger.info(f"Resource monitoring started (interval: {interval_seconds}s)")
    
    def stop_resource_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Resource monitoring stopped")
    
    def _monitoring_loop(self, interval_seconds: int):
        """Resource monitoring loop."""
        while self.monitoring_active:
            try:
                snapshot = self._take_resource_snapshot()
                self.resource_history.append(snapshot)
                
                # Keep only last 1000 snapshots
                if len(self.resource_history) > 1000:
                    self.resource_history = self.resource_history[-1000:]
                
                time.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {str(e)}")
                time.sleep(interval_seconds)
    
    def _take_resource_snapshot(self) -> ResourceUsage:
        """Take resource usage snapshot."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024**2)
            memory_available_mb = memory.available / (1024**2)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            
            # Network usage
            net = psutil.net_io_counters()
            network_bytes_sent = net.bytes_sent
            network_bytes_recv = net.bytes_recv
            
            # Process and thread count
            process_count = len(psutil.pids())
            
            # Thread count for current process
            current_process = psutil.Process()
            thread_count = current_process.num_threads()
            
            # Open files for current process
            open_files = len(current_process.open_files())
            
            snapshot = ResourceUsage(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                process_count=process_count,
                thread_count=thread_count,
                open_files=open_files,
                metadata={
                    "optimizer_id": self.optimizer_id,
                    "cache_size": self.current_cache_size,
                    "cache_entries": len(self.cache)
                }
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error taking resource snapshot: {str(e)}")
            return ResourceUsage()
    
    def _record_performance_metric(self, name: str, value: float, unit: str,
                                 component: str, optimization_applied: bool,
                                 metadata: Dict[str, Any] = None):
        """Record performance metric."""
        metric_id = f"metric_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        metric = PerformanceMetric(
            metric_id=metric_id,
            name=name,
            value=value,
            unit=unit,
            component=component,
            optimization_applied=optimization_applied,
            metadata=metadata or {}
        )
        
        self.performance_metrics[metric_id] = metric
        
        # Keep only last 1000 metrics
        if len(self.performance_metrics) > 1000:
            # Remove oldest metrics
            oldest_ids = sorted(self.performance_metrics.keys())[:-1000]
            for old_id in oldest_ids:
                del self.performance_metrics[old_id]
    
    def optimize_memory(self):
        """Optimize memory usage."""
        logger.info("Optimizing memory usage...")
        
        # Run garbage collection
        gc.collect()
        
        # Clear unused caches if memory is high
        memory_percent = psutil.virtual_memory().percent
        if memory_percent > 80:
            logger.warning(f"High memory usage ({memory_percent}%), clearing caches")
            self.clear_cache()
            self.clear_memoization()
        
        # Record optimization
        self.stats["total_optimizations"] += 1
        
        logger.info("Memory optimization completed")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get performance optimization report.
        
        Returns:
            Performance report
        """
        # Calculate cache statistics
        cache_hit_rate = 0
        if self.stats["cache_hits"] + self.stats["cache_misses"] > 0:
            cache_hit_rate = (self.stats["cache_hits"] / 
                            (self.stats["cache_hits"] + self.stats["cache_misses"]) * 100)
        
        memoization_hit_rate = 0
        if self.stats["memoization_hits"] + self.stats["memoization_misses"] > 0:
            memoization_hit_rate = (self.stats["memoization_hits"] / 
                                  (self.stats["memoization_hits"] + self.stats["memoization_misses"]) * 100)
        
        # Get recent resource usage
        recent_resources = self.resource_history[-10:] if self.resource_history else []
        
        # Calculate resource averages
        if recent_resources:
            cpu_avg = statistics.mean([r.cpu_percent for r in recent_resources])
            memory_avg = statistics.mean([r.memory_percent for r in recent_resources])
        else:
            cpu_avg = 0
            memory_avg = 0
        
        # Get recent performance metrics
        recent_metrics = list(self.performance_metrics.values())[-20:]
        
        report = {
            "report_id": f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "optimizer_id": self.optimizer_id,
            "optimization_level": self.optimization_level.value,
            "statistics": self.stats,
            "cache_statistics": {
                "current_size_mb": self.current_cache_size / (1024**2),
                "max_size_mb": self.max_cache_size_bytes / (1024**2),
                "entries_count": len(self.cache),
                "hit_rate_percent": cache_hit_rate,
                "eviction_count": self.stats["cache_evictions"],
                "strategy": self.cache_strategy.value
            },
            "memoization_statistics": {
                "entries_count": len(self.memoization_cache),
                "hit_rate_percent": memoization_hit_rate
            },
            "resource_usage": {
                "cpu_percent_avg": cpu_avg,
                "memory_percent_avg": memory_avg,
                "monitoring_active": self.monitoring_active,
                "snapshot_count": len(self.resource_history)
            },
            "parallel_processing": {
                "worker_count": self.thread_pool._max_workers,
                "optimal_worker_count": self._get_optimal_worker_count()
            },
            "recent_metrics_count": len(recent_metrics),
            "recommendations": self._generate_optimization_recommendations()
        }
        
        return report
    
    def _generate_optimization_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Cache recommendations
        cache_hit_rate = 0
        if self.stats["cache_hits"] + self.stats["cache_misses"] > 0:
            cache_hit_rate = (self.stats["cache_hits"] / 
                            (self.stats["cache_hits"] + self.stats["cache_misses"]) * 100)
        
        if cache_hit_rate < 50:
            recommendations.append(f"Improve cache hit rate (currently {cache_hit_rate:.1f}%)")
        
        if self.stats["cache_evictions"] > 100:
            recommendations.append("Consider increasing cache size to reduce evictions")
        
        # Memory recommendations
        if self.resource_history:
            recent_memory = [r.memory_percent for r in self.resource_history[-10:]]
            avg_memory = statistics.mean(recent_memory) if recent_memory else 0
            
            if avg_memory > 80:
                recommendations.append(f"High memory usage ({avg_memory:.1f}%), consider optimizing memory-intensive operations")
        
        # Parallel processing recommendations
        optimal_workers = self._get_optimal_worker_count()
        current_workers = self.thread_pool._max_workers
        
        if current_workers < optimal_workers:
            recommendations.append(f"Increase worker count from {current_workers} to {optimal_workers} for better parallelization")
        
        if not recommendations:
            recommendations.append("Performance optimization is effective - continue current strategy")
        
        return recommendations
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get optimizer status.
        
        Returns:
            Status information
        """
        return {
            "optimizer_id": self.optimizer_id,
            "optimization_level": self.optimization_level.value,
            "cache_size_mb": self.current_cache_size / (1024**2),
            "cache_entries": len(self.cache),
            "memoization_entries": len(self.memoization_cache),
            "performance_metrics": len(self.performance_metrics),
            "resource_snapshots": len(self.resource_history),
            "monitoring_active": self.monitoring_active,
            "statistics": self.stats,
            "timestamp": datetime.now().isoformat()
        }


def test_performance_optimizer():
    """Test function for Performance Optimizer."""
    print("Testing Performance Optimizer...")
    
    # Create optimizer instance
    optimizer = PerformanceOptimizer(
        optimizer_id="test_optimizer_001",
        max_cache_size_mb=10,  # 10MB cache for testing
        optimization_level=OptimizationLevel.BASIC
    )
    
    # Test 1: Initial status
    print("\n1. Initial Status:")
    status = optimizer.get_status()
    print(f"   Optimizer ID: {status['optimizer_id']}")
    print(f"   Optimization level: {status['optimization_level']}")
    print(f"   Cache entries: {status['cache_entries']}")
    
    # Test 2: Cached function
    print("\n2. Testing cached function...")
    
    @optimizer.cache_function(ttl_seconds=10)
    def expensive_calculation(x: int, y: int) -> int:
        """Simulate expensive calculation."""
        time.sleep(0.1)  # Simulate work
        return x * y + x + y
    
    # First call (cache miss)
    start = time.time()
    result1 = expensive_calculation(5, 10)
    time1 = time.time() - start
    print(f"   First call: {result1} (took {time1:.3f}s)")
    
    # Second call (cache hit)
    start = time.time()
    result2 = expensive_calculation(5, 10)
    time2 = time.time() - start
    print(f"   Second call: {result2} (took {time2:.3f}s)")
    
    if time2 < time1:
        print(f"   ✓ Cache speedup: {(time1 - time2):.3f}s")
    
    # Test 3: Memoized function
    print("\n3. Testing memoized function...")
    
    @optimizer.memoize_function()
    def fibonacci(n: int) -> int:
        """Calculate Fibonacci number (recursive)."""
        if n <= 1:
            return n
        return fibonacci(n-1) + fibonacci(n-2)
    
    # First calculation
    start = time.time()
    fib1 = fibonacci(30)
    time1 = time.time() - start
    print(f"   First Fibonacci(30): {fib1} (took {time1:.3f}s)")
    
    # Second calculation (should be instant from memoization)
    start = time.time()
    fib2 = fibonacci(30)
    time2 = time.time() - start
    print(f"   Second Fibonacci(30): {fib2} (took {time2:.3f}s)")
    
    if time2 < time1:
        print(f"   ✓ Memoization speedup: {(time1 - time2):.3f}s")
    
    # Test 4: Parallel execution
    print("\n4. Testing parallel execution...")
    
    def task_simulation(task_id: int) -> Dict[str, Any]:
        """Simulate a task."""
        time.sleep(0.5)  # Simulate work
        return {
            "task_id": task_id,
            "result": task_id * 10,
            "timestamp": datetime.now().isoformat()
        }
    
    tasks = [lambda i=i: task_simulation(i) for i in range(5)]
    
    start = time.time()
    results = optimizer.parallel_execute(tasks, timeout_seconds=10)
    parallel_time = time.time() - start
    
    print(f"   Parallel execution of {len(tasks)} tasks: {parallel_time:.3f}s")
    print(f"   Results: {len([r for r in results if r])} successful")
    
    # Test 5: Resource monitoring
    print("\n5. Testing resource monitoring...")
    optimizer.start_resource_monitoring(interval_seconds=1)
    time.sleep(3)  # Let it collect some data
    optimizer.stop_resource_monitoring()
    print(f"   Collected {len(optimizer.resource_history)} resource snapshots")
    
    # Test 6: Memory optimization
    print("\n6. Testing memory optimization...")
    optimizer.optimize_memory()
    print("   Memory optimization completed")
    
    # Test 7: Performance report
    print("\n7. Generating performance report...")
    report = optimizer.get_performance_report()
    print(f"   Report ID: {report['report_id']}")
    print(f"   Cache hit rate: {report['cache_statistics']['hit_rate_percent']:.1f}%")
    print(f"   Cache size: {report['cache_statistics']['current_size_mb']:.2f}MB")
    print(f"   Recommendations: {len(report['recommendations'])}")
    
    # Test 8: Clear caches
    print("\n8. Clearing caches...")
    optimizer.clear_cache()
    optimizer.clear_memoization()
    print("   Caches cleared")
    
    # Final status
    print("\n9. Final Status:")
    final_status = optimizer.get_status()
    print(f"   Cache entries: {final_status['cache_entries']}")
    print(f"   Cache hits: {final_status['statistics']['cache_hits']}")
    print(f"   Cache misses: {final_status['statistics']['cache_misses']}")
    print(f"   Total optimizations: {final_status['statistics']['total_optimizations']}")
    
    # Cleanup
    optimizer.thread_pool.shutdown(wait=True)
    
    print("\nPerformance Optimizer test completed successfully!")


if __name__ == "__main__":
    test_performance_optimizer()