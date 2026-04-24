"""
GAM Memory Server — Phase 7

MCP-style interface for ProjectX agents to access graph-based associative
memory. Provides a unified API for reading and writing to both local (session)
and global (durable) memory graphs.

This server integrates with:
  - RAGMemory as fallback for vector-only queries
  - LearningLoop for consolidation triggers
  - SystemMemoryStore for episode/lesson persistence
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from .event_buffer import EdgeType, EventBuffer, NodeType
from .semantic_consolidator import DurableNodeType, SemanticConsolidator
from .graph_retrieval import GraphRetrieval, RetrievalQuery, RetrievalScore

logger = logging.getLogger(__name__)


@dataclass
class MemoryResponse:
    """Standard response format for memory server operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ── Memory Server ─────────────────────────────────────────────────────────────

class MemoryServer:
    """
    MCP-style memory interface for ProjectX agents.

    Provides read/write access to the graph-based associative memory system
    with automatic fallbacks and integration with existing memory stores.

    Example::

        server = MemoryServer()
        
        # Store an event
        server.write_event(
            node_type="intent",
            content="Deploy the trading service to production",
            trace_id="deploy-001",
            role="orchestrator",
        )
        
        # Retrieve relevant memories
        results = server.query(
            query="How did we deploy services in the past?",
            role="orchestrator",
            top_k=5,
        )
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        rag_memory=None,
        system_store=None,
    ) -> None:
        self._persist_dir = persist_dir

        # Initialize components
        self._event_buffer = EventBuffer(
            max_nodes=5000,
            default_ttl=3600.0,
        )

        self._consolidator = SemanticConsolidator(
            event_buffer=self._event_buffer,
            system_store=system_store,
            rag_memory=rag_memory,
        )

        self._retrieval = GraphRetrieval(
            event_buffer=self._event_buffer,
            consolidator=self._consolidator,
            rag_memory=rag_memory,
        )

        self._rag = rag_memory

        # Boundary detection for consolidation
        self._boundary_detector = None
        self._consolidation_thread: Optional[threading.Thread] = None
        self._consolidation_running = False

        # Session state
        self._session_id = self._generate_session_id()
        self._created_at = time.time()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background consolidation."""
        if self._consolidation_running:
            return

        from .boundary_detector import BoundaryDetector
        self._boundary_detector = BoundaryDetector(self._event_buffer)
        self._boundary_detector.register_callback(self._on_boundary)
        self._boundary_detector.start()

        self._consolidation_running = True
        self._consolidation_thread = threading.Thread(
            target=self._consolidation_loop,
            daemon=True,
            name="GAMConsolidation",
        )
        self._consolidation_thread.start()

        logger.info("MemoryServer started (session=%s)", self._session_id)

    def stop(self) -> None:
        """Stop background consolidation."""
        self._consolidation_running = False
        if self._boundary_detector:
            self._boundary_detector.stop()
        logger.info("MemoryServer stopped")

    # ── Write Operations ─────────────────────────────────────────────────

    def write_event(
        self,
        node_type: str,
        content: str,
        trace_id: Optional[str] = None,
        role: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        edge_to: Optional[str] = None,
        edge_type: str = "triggered",
        ttl_seconds: Optional[float] = None,
    ) -> MemoryResponse:
        """
        Write an event to the local graph.

        Args:
            node_type: Type of node (intent, tool_call, repo_file, etc.)
            content: The event content
            trace_id: Optional trace/flow ID to group events
            role: Agent role (orchestrator, safety, etc.)
            metadata: Additional metadata
            confidence: Confidence level (0-1)
            edge_to: Optional node ID to create an edge TO
            edge_type: Type of edge to create
            ttl_seconds: TTL for this node

        Returns:
            MemoryResponse with the created node_id
        """
        try:
            nt = NodeType(node_type)
        except ValueError:
            return MemoryResponse(
                success=False,
                error=f"Invalid node_type: {node_type}",
            )

        # Generate trace_id if not provided
        if not trace_id:
            trace_id = f"session-{self._session_id}"

        # Add node
        node_id = self._event_buffer.add_node(
            node_type=nt,
            content=content,
            metadata=metadata or {},
            confidence=confidence,
            role=role,
            trace_id=trace_id,
            ttl_seconds=ttl_seconds,
        )

        # Add edge if specified
        if edge_to:
            try:
                et = EdgeType(edge_type)
                self._event_buffer.add_edge(
                    from_node_id=edge_to,
                    to_node_id=node_id,
                    edge_type=et,
                )
            except ValueError:
                logger.warning("Invalid edge_type: %s", edge_type)

        return MemoryResponse(
            success=True,
            data={"node_id": node_id, "trace_id": trace_id},
            meta={"node_type": node_type},
        )

    def write_intent(
        self,
        content: str,
        trace_id: Optional[str] = None,
        role: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryResponse:
        """Convenience method to write an intent node."""
        return self.write_event(
            node_type="intent",
            content=content,
            trace_id=trace_id,
            role=role,
            metadata=metadata,
        )

    def write_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryResponse:
        """Convenience method to write a tool call node."""
        content = f"Called {tool_name} with {json.dumps(args)}"
        if result:
            content += f"\nResult: {result[:200]}"
        return self.write_event(
            node_type="tool_call",
            content=content,
            trace_id=trace_id,
            metadata={**(metadata or {}), "tool_name": tool_name, "args": args},
        )

    def write_agent_response(
        self,
        content: str,
        trace_id: Optional[str] = None,
        role: Optional[str] = None,
        confidence: float = 0.8,
    ) -> MemoryResponse:
        """Convenience method to write an agent response node."""
        return self.write_event(
            node_type="agent_response",
            content=content,
            trace_id=trace_id,
            role=role,
            confidence=confidence,
        )

    def write_error(
        self,
        error: str,
        context: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryResponse:
        """Record an error event."""
        content = f"Error: {error}"
        if context:
            content += f"\nContext: {context}"
        return self.write_event(
            node_type="tool_call",
            content=content,
            trace_id=trace_id,
            metadata={**(metadata or {}), "status": "error", "error": error},
            confidence=0.3,  # Lower confidence for errors
        )

    # ── Read Operations ──────────────────────────────────────────────────

    def query(
        self,
        query: str,
        role: Optional[str] = None,
        node_types: Optional[List[str]] = None,
        trace_id: Optional[str] = None,
        top_k: int = 8,
        include_local: bool = True,
        include_durable: bool = True,
    ) -> MemoryResponse:
        """
        Query the memory graph.

        Args:
            query: Natural language query
            role: Filter by agent role
            node_types: Filter by node types
            trace_id: Filter by trace/flow
            top_k: Number of results
            include_local: Include session graph
            include_durable: Include durable memory

        Returns:
            MemoryResponse with list of RetrievalScore results
        """
        try:
            nt_types = None
            if node_types:
                try:
                    nt_types = [NodeType(nt) for nt in node_types]
                except ValueError:
                    pass

            retrieval_query = RetrievalQuery(
                query_text=query,
                role=role,
                node_types=node_types,
                trace_id=trace_id,
                top_k=top_k,
                include_local=include_local,
                include_durable=include_durable,
            )

            results = self._retrieval.query(retrieval_query)

            return MemoryResponse(
                success=True,
                data=[{
                    "node_id": r.node_id,
                    "node_type": r.node_type,
                    "title": r.title,
                    "content": r.content,
                    "score": r.total_score,
                    "source": r.source,
                    "breakdown": {
                        "semantic": r.semantic_score,
                        "recency": r.recency_score,
                        "confidence": r.confidence_score,
                        "role_match": r.role_match_score,
                        "proximity": r.graph_proximity_score,
                    },
                    "metadata": r.metadata,
                } for r in results],
                meta={"query": query, "result_count": len(results)},
            )

        except Exception as exc:
            logger.error("Query failed: %s", exc)
            return MemoryResponse(
                success=False,
                error=str(exc),
            )

    def get_trace(self, trace_id: str) -> MemoryResponse:
        """Get all events for a trace/flow."""
        try:
            nodes = self._event_buffer.get_trace_nodes(trace_id)
            return MemoryResponse(
                success=True,
                data={
                    "trace_id": trace_id,
                    "nodes": [n.to_dict() for n in nodes],
                    "count": len(nodes),
                },
            )
        except Exception as exc:
            return MemoryResponse(success=False, error=str(exc))

    def get_context(
        self,
        node_id: str,
        depth: int = 2,
    ) -> MemoryResponse:
        """Get context chain starting from a node."""
        try:
            chain = self._retrieval.get_context_chain(node_id, max_depth=depth)
            return MemoryResponse(
                success=True,
                data={
                    "start_node_id": node_id,
                    "chain": [{
                        "node_id": r.node_id,
                        "type": r.node_type,
                        "title": r.title,
                        "content": r.content,
                    } for r in chain],
                },
            )
        except Exception as exc:
            return MemoryResponse(success=False, error=str(exc))

    def get_related(
        self,
        node_id: str,
        top_k: int = 5,
    ) -> MemoryResponse:
        """Get nodes related to a given node."""
        try:
            related = self._consolidator.find_related_durable(node_id, top_k=top_k)
            return MemoryResponse(
                success=True,
                data=[{
                    "node_id": n.node_id,
                    "type": n.durable_type.value,
                    "title": n.title,
                    "similarity": score,
                } for n, score in related],
            )
        except Exception as exc:
            return MemoryResponse(success=False, error=str(exc))

    # ── Management Operations ─────────────────────────────────────────────

    def consolidate(
        self,
        trace_id: Optional[str] = None,
        force: bool = False,
    ) -> MemoryResponse:
        """
        Trigger consolidation of episodes to durable memory.

        If trace_id is provided, consolidate that specific episode.
        Otherwise, checks for ready episodes and consolidates them.
        """
        try:
            from .boundary_detector import BoundaryDetector

            if trace_id:
                candidate = BoundaryDetector(self._event_buffer).detect_closure(trace_id, force=force)
                if not candidate:
                    return MemoryResponse(success=True, data={"message": "Episode not ready for consolidation"})
                
                result = self._consolidator.consolidate_episode(
                    trace_id,
                    candidate.nodes,
                    candidate.edges,
                )
            else:
                # Check all traces
                results = []
                for tid in list(self._event_buffer._trace_index.keys()):
                    candidate = BoundaryDetector(self._event_buffer).detect_closure(tid)
                    if candidate:
                        result = self._consolidator.consolidate_episode(
                            tid, candidate.nodes, candidate.edges
                        )
                        results.append(result)

                result = {
                    "episodes_processed": len(results),
                    "total_nodes_created": sum(r.durable_nodes_created for r in results),
                }

            return MemoryResponse(success=True, data=result)

        except Exception as exc:
            logger.error("Consolidation failed: %s", exc)
            return MemoryResponse(success=False, error=str(exc))

    def prune(self) -> MemoryResponse:
        """Prune expired nodes from the local graph."""
        try:
            count = self._event_buffer.prune_expired()
            return MemoryResponse(
                success=True,
                data={"pruned_nodes": count},
            )
        except Exception as exc:
            return MemoryResponse(success=False, error=str(exc))

    def stats(self) -> MemoryResponse:
        """Get memory system statistics."""
        return MemoryResponse(
            success=True,
            data={
                "session": {
                    "session_id": self._session_id,
                    "created_at": self._created_at,
                    "age_seconds": time.time() - self._created_at,
                },
                "local_graph": self._event_buffer.stats(),
                "consolidator": self._consolidator.stats(),
                "retrieval": self._retrieval.stats(),
            },
        )

    # ── Integration Points ────────────────────────────────────────────────

    def trigger_consolidation(self, trace_id: str) -> None:
        """
        External trigger for consolidation.
        Called by LearningLoop or other systems.
        """
        result = self.consolidate(trace_id=trace_id, force=True)
        if result.success:
            logger.info("Consolidated trace %s: %s", trace_id, result.data)
        else:
            logger.warning("Consolidation failed for %s: %s", trace_id, result.error)

    def get_lessons(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get consolidated lessons from durable memory."""
        lessons = self._consolidator.get_durable_nodes(DurableNodeType.LESSON, limit=limit)
        return [n.to_dict() for n in lessons]

    def get_failure_modes(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get consolidated failure modes from durable memory."""
        failures = self._consolidator.get_durable_nodes(DurableNodeType.FAILURE_MODE, limit=limit)
        return [n.to_dict() for n in failures]

    # ── Internal Methods ─────────────────────────────────────────────────

    def _on_boundary(self, boundary_event) -> None:
        """Callback for boundary detection events."""
        logger.debug("Boundary detected for trace %s: %s", boundary_event.trace_id, boundary_event.trigger)
        # Trigger consolidation
        self.trigger_consolidation(boundary_event.trace_id)

    def _consolidation_loop(self) -> None:
        """Background loop for periodic consolidation checks."""
        while self._consolidation_running:
            time.sleep(60)  # Check every minute
            if not self._consolidation_running:
                break

            # Periodic prune
            try:
                self._event_buffer.prune_expired()
            except Exception:
                pass

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import uuid
        return str(uuid.uuid4())[:8]


# ── Module-level Singleton ────────────────────────────────────────────────────

_server: Optional[MemoryServer] = None
_server_lock = threading.Lock()


def get_memory_server(
    persist_dir: Optional[str] = None,
    rag_memory=None,
    system_store=None,
) -> MemoryServer:
    """Get or create the global memory server singleton."""
    global _server
    with _server_lock:
        if _server is None:
            _server = MemoryServer(
                persist_dir=persist_dir,
                rag_memory=rag_memory,
                system_store=system_store,
            )
            _server.start()
        return _server


def shutdown_memory_server() -> None:
    """Shutdown the global memory server."""
    global _server
    with _server_lock:
        if _server:
            _server.stop()
            _server = None
