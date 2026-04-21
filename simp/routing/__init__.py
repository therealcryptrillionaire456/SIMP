"""
SIMP Routing — Builder pool management, routing policy, and multi-platform signal router.
"""

from simp.routing.builder_pool import BuilderPool
from simp.routing.signal_router import MultiPlatformRouter, RouterSignal, RouterResult, route_signal, get_router

__all__ = ["BuilderPool", "MultiPlatformRouter", "RouterSignal", "RouterResult", "route_signal", "get_router"]
