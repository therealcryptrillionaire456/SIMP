"""
GAM Event Buffer — Phase 7

Local in-memory event graph for the current session. Nodes represent
episodic events (intents, tool calls, repo files, mesh messages, etc.)
with TTL-based forgetting to keep the working set fresh.

Node types: intent, tool_call, repo_file, mesh_message, market_snapshot,
            agent_response, hypothesis

Edges represent temporal/causal relationships and carry metadata about
the interaction (e.g., triggered_by, resulted_in, depends_on).
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Enums ─────────────────────────────────────────────────────────────────────

class NodeType(str, Enum):
    INTENT = "intent"
    TOOL_CALL = "tool_call"
    REPO_FILE = "repo_file"
    MESH_MESSAGE = "mesh_message"
    MARKET_SNAPSHOT = "market_snapshot"
    AGENT_RESPONSE = "agent_response"
    HYPOTHESIS = "hypothesis"


class EdgeType(str, Enum):
    TRIGGERED = "triggered"
    RESULTED_IN = "resulted_in"
    DEPENDS_ON = "depends_on"
    FAILED_WITH = "failed_with"
    EXPLAINS = "explains"
    LEARNED_FROM = "learned_from"
    USED_TOOL = "used_tool"


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class GAMNode:
    """A single node in the local event graph."""
    node_id: str
    node_type: NodeType
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    role: Optional[str] = None  # e.g., "orchestrator", "agent", "safety"
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    trace_id: Optional[str] = None  # Groups related events in a flow
    ttl_seconds: float = 3600  # Default: forget after 1 hour of inactivity

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return (time.time() - self.accessed_at) > self.ttl_seconds

    def touch(self) -> None:
        self.accessed_at = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "confidence": self.confidence,
            "role": self.role,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "trace_id": self.trace_id,
            "ttl_seconds": self.ttl_seconds,
        }


@dataclass
class GAMEdge:
    """Directed edge between two nodes with edge-type semantics."""
    from_node_id: str
    to_node_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ── Embedding Helpers ─────────────────────────────────────────────────────────

def _hash_embed(text: str, dim: int = 384) -> List[float]:
    """Deterministic hash-based pseudo-embedding (no external deps)."""
    vec = [0.0] * dim
    tokens = text.lower().split()
    for tok in tokens:
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        for i in range(dim):
            vec[i] += math.sin((h >> i) & 0xFF) / (len(tokens) or 1)
    mag = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / mag for v in vec]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    ma = math.sqrt(sum(x * x for x in a)) or 1e-9
    mb = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (ma * mb)


# ── Event Buffer ──────────────────────────────────────────────────────────────

class EventBuffer:
    """
    In-memory event graph for the current session.

    Provides fast writes and TTL-based forgetting. The graph is thread-safe
    and suitable for use in high-throughput agent loops.

    Example::

        buf = EventBuffer()
        node_id = buf.add_node(NodeType.INTENT, "deploy service", trace_id="t1")
        buf.add_edge(node_id, other_id, EdgeType.TRIGGERED)
        nodes = buf.get_trace_nodes("t1")
    """

    def __init__(
        self,
        max_nodes: int = 5000,
        default_ttl: float = 3600.0,
        embed_dim: int = 384,
    ) -> None:
        self._nodes: Dict[str, GAMNode] = {}
        self._out_edges: Dict[str, List[GAMEdge]] = {}
        self._in_edges: Dict[str, List[GAMEdge]] = {}
        self._trace_index: Dict[str, Set[str]] = {}  # trace_id → set of node_ids
        self._type_index: Dict[NodeType, Set[str]] = {t: set() for t in NodeType}

        self._lock = threading.RLock()
        self._max_nodes = max_nodes
        self._default_ttl = default_ttl
        self._embed_dim = embed_dim

        # Try to use sentence-transformers if available
        self._st_model = None
        try:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            logger.debug("sentence-transformers not available, using hash embeddings")

    # ── Node Operations ──────────────────────────────────────────────────────

    def add_node(
        self,
        node_type: NodeType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        role: Optional[str] = None,
        trace_id: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        embedding: Optional[List[float]] = None,
        node_id: Optional[str] = None,
    ) -> str:
        """Add a node to the event graph. Returns the node_id."""
        with self._lock:
            node_id = node_id or str(uuid.uuid4())

            # Lazy embedding
            if embedding is None:
                embedding = self._embed(content)

            node = GAMNode(
                node_id=node_id,
                node_type=node_type,
                content=content,
                embedding=embedding,
                metadata=metadata or {},
                confidence=confidence,
                role=role,
                trace_id=trace_id,
                ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl,
            )

            self._nodes[node_id] = node
            self._out_edges.setdefault(node_id, [])
            self._in_edges.setdefault(node_id, [])
            self._type_index[node_type].add(node_id)

            if trace_id:
                self._trace_index.setdefault(trace_id, set()).add(node_id)

            # Evict oldest nodes if over capacity
            self._maybe_evict()

            return node_id

    def get_node(self, node_id: str) -> Optional[GAMNode]:
        """Retrieve a node by ID. Touches accessed_at."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.touch()
            return node

    def get_trace_nodes(self, trace_id: str) -> List[GAMNode]:
        """Get all nodes belonging to a trace/flow."""
        with self._lock:
            node_ids = self._trace_index.get(trace_id, set())
            nodes = []
            for nid in node_ids:
                node = self._nodes.get(nid)
                if node and not node.is_expired:
                    nodes.append(node)
            nodes.sort(key=lambda n: n.created_at)
            return nodes

    def get_nodes_by_type(self, node_type: NodeType) -> List[GAMNode]:
        """Get all non-expired nodes of a given type."""
        with self._lock:
            return [
                n for nid in self._type_index.get(node_type, set())
                if (n := self._nodes.get(nid)) and not n.is_expired
            ]

    def find_similar_nodes(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.5,
        node_types: Optional[List[NodeType]] = None,
    ) -> List[Tuple[GAMNode, float]]:
        """Find nodes similar to the query by embedding distance."""
        query_vec = self._embed(query)
        candidates: List[str]
        if node_types:
            candidates = [nid for t in node_types for nid in self._type_index.get(t, set())]
        else:
            candidates = list(self._nodes.keys())

        results = []
        for nid in candidates:
            node = self._nodes.get(nid)
            if not node or node.is_expired:
                continue
            if node.embedding:
                sim = _cosine_similarity(query_vec, node.embedding)
                if sim >= threshold:
                    results.append((node, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete_node(self, node_id: str) -> bool:
        """Remove a node and its edges."""
        with self._lock:
            if node_id not in self._nodes:
                return False
            node = self._nodes[node_id]

            # Remove from indices
            self._type_index[node.node_type].discard(node_id)
            if node.trace_id:
                self._trace_index[node.trace_id].discard(node_id)
                if not self._trace_index[node.trace_id]:
                    del self._trace_index[node.trace_id]

            # Remove edges
            for edge in self._out_edges.pop(node_id, []):
                self._in_edges[edge.to_node_id] = [
                    e for e in self._in_edges.get(edge.to_node_id, [])
                    if e.from_node_id != node_id
                ]
            for edge in self._in_edges.pop(node_id, []):
                self._out_edges[edge.from_node_id] = [
                    e for e in self._out_edges.get(edge.from_node_id, [])
                    if e.to_node_id != node_id
                ]

            del self._nodes[node_id]
            return True

    # ── Edge Operations ──────────────────────────────────────────────────────

    def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[GAMEdge]:
        """Add a directed edge between nodes. Returns the edge or None if nodes missing."""
        with self._lock:
            if from_node_id not in self._nodes or to_node_id not in self._nodes:
                return None

            edge = GAMEdge(
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                edge_type=edge_type,
                weight=weight,
                metadata=metadata or {},
            )
            self._out_edges[from_node_id].append(edge)
            self._in_edges[to_node_id].append(edge)
            return edge

    def get_outgoing(self, node_id: str) -> List[GAMEdge]:
        return list(self._out_edges.get(node_id, []))

    def get_incoming(self, node_id: str) -> List[GAMEdge]:
        return list(self._in_edges.get(node_id, []))

    def get_neighbors(
        self,
        node_id: str,
        depth: int = 1,
        direction: str = "both",  # "out", "in", "both"
    ) -> Dict[str, List[GAMNode]]:
        """Get neighboring nodes within a traversal depth."""
        result: Dict[str, List[GAMNode]] = {"out": [], "in": []}
        visited: Set[str] = set()

        def _traverse(current_id: str, remaining_depth: int, dir_: str) -> None:
            if remaining_depth < 0 or current_id in visited:
                return
            visited.add(current_id)

            if dir_ in ("out", "both"):
                for edge in self._out_edges.get(current_id, []):
                    if (node := self._nodes.get(edge.to_node_id)) and not node.is_expired:
                        result["out"].append(node)
                        _traverse(edge.to_node_id, remaining_depth - 1, dir_)

            if dir_ in ("in", "both"):
                for edge in self._in_edges.get(current_id, []):
                    if (node := self._nodes.get(edge.from_node_id)) and not node.is_expired:
                        result["in"].append(node)
                        _traverse(edge.from_node_id, remaining_depth - 1, dir_)

        _traverse(node_id, depth, direction)
        return result

    # ── Maintenance ────────────────────────────────────────────────────────

    def prune_expired(self) -> int:
        """Remove all expired nodes. Returns count of pruned nodes."""
        with self._lock:
            expired = [nid for nid, n in self._nodes.items() if n.is_expired]
            for nid in expired:
                self.delete_node(nid)
            return len(expired)

    def _maybe_evict(self) -> None:
        """Evict oldest accessed nodes if over capacity."""
        if len(self._nodes) <= self._max_nodes:
            return
        # Sort by accessed_at (oldest first), evict bottom 10%
        sorted_nodes = sorted(
            self._nodes.items(),
            key=lambda x: x[1].accessed_at,
        )
        evict_count = max(1, len(sorted_nodes) // 10)
        for nid, _ in sorted_nodes[:evict_count]:
            self.delete_node(nid)

    def _embed(self, text: str) -> List[float]:
        """Get embedding for text using sentence-transformers or hash fallback."""
        if self._st_model is not None:
            vec = self._st_model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        return _hash_embed(text, self._embed_dim)

    def stats(self) -> Dict[str, Any]:
        """Return buffer statistics."""
        with self._lock:
            total_expired = sum(1 for n in self._nodes.values() if n.is_expired)
            return {
                "total_nodes": len(self._nodes),
                "total_edges": sum(len(e) for e in self._out_edges.values()),
                "expired_nodes": total_expired,
                "active_traces": len(self._trace_index),
                "by_type": {
                    t.value: len(ns) for t, ns in self._type_index.items()
                },
            }

    def export_episode(self, trace_id: str) -> Dict[str, Any]:
        """Export all nodes and edges for a trace as a portable episode dict."""
        nodes = self.get_trace_nodes(trace_id)
        node_ids = {n.node_id for n in nodes}
        edges = []
        for nid in node_ids:
            edges.extend([e for e in self._out_edges.get(nid, []) if e.to_node_id in node_ids])
        return {
            "trace_id": trace_id,
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
