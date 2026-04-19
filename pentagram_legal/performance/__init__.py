"""
Performance Optimization Layer - Build 18
Caching, memoization, parallel processing, and resource optimization.
"""

from .performance_optimizer import (
    PerformanceOptimizer,
    CacheStrategy,
    OptimizationLevel,
    CacheEntry,
    PerformanceMetric,
    ResourceUsage
)

from .caching_system import (
    CachingSystem,
    CacheType,
    CachePolicy,
    CacheStats
)

from .parallel_processor import (
    ParallelProcessor,
    ProcessingMode,
    TaskResult,
    WorkerPool
)

__all__ = [
    # Performance Optimizer
    "PerformanceOptimizer",
    "CacheStrategy",
    "OptimizationLevel",
    "CacheEntry",
    "PerformanceMetric",
    "ResourceUsage",
    
    # Caching System
    "CachingSystem",
    "CacheType",
    "CachePolicy",
    "CacheStats",
    
    # Parallel Processor
    "ParallelProcessor",
    "ProcessingMode",
    "TaskResult",
    "WorkerPool"
]

__version__ = "1.0.0"