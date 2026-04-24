"""
GAM: Graph-based Associative Memory — Phase 7

A memory system for ProjectX that combines:
  - Local event graph (session-scoped) with TTL-based forgetting
  - Semantic boundary detection for episode segmentation
  - Consolidation of ephemeral events into durable memory
  - Multi-factor ranked retrieval with RAG fallback

Quick Start::

    from scripts.projectx.gam_memory import get_memory_server

    server = get_memory_server()
    
    # Store events
    server.write_intent("Deploy service X", trace_id="deploy-1", role="orchestrator")
    
    # Query memories
    results = server.query("How did we deploy services?")
    
    # Get stats
    stats = server.stats()

Modules:
    event_buffer: Local in-memory event graph with TTL
    boundary_detector: Semantic closure detection
    semantic_consolidator: Episode → Topic promotion
    graph_retrieval: Multi-factor ranking retrieval
    memory_server: MCP-style interface for agents
"""

from .event_buffer import (
    EventBuffer,
    GAMNode,
    GAMEdge,
    NodeType,
    EdgeType,
)

from .boundary_detector import (
    BoundaryDetector,
    BoundaryEvent,
    BoundaryTrigger,
    ClosureCandidate,
)

from .semantic_consolidator import (
    SemanticConsolidator,
    DurableNode,
    DurableEdge,
    DurableNodeType,
    ConsolidationResult,
)

from .graph_retrieval import (
    GraphRetrieval,
    RetrievalQuery,
    RetrievalScore,
)

from .memory_server import (
    MemoryServer,
    MemoryResponse,
    get_memory_server,
    shutdown_memory_server,
)

__all__ = [
    # Event Buffer
    "EventBuffer",
    "GAMNode",
    "GAMEdge",
    "NodeType",
    "EdgeType",
    # Boundary Detector
    "BoundaryDetector",
    "BoundaryEvent",
    "BoundaryTrigger",
    "ClosureCandidate",
    # Semantic Consolidator
    "SemanticConsolidator",
    "DurableNode",
    "DurableEdge",
    "DurableNodeType",
    "ConsolidationResult",
    # Graph Retrieval
    "GraphRetrieval",
    "RetrievalQuery",
    "RetrievalScore",
    # Memory Server
    "MemoryServer",
    "MemoryResponse",
    "get_memory_server",
    "shutdown_memory_server",
]
