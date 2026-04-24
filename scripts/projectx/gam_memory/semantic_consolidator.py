"""
GAM Semantic Consolidator — Phase 7

Promotes ephemeral event graph episodes into durable topic nodes
suitable for long-term memory storage.

Summarizes episodes into durable node types:
  - service: a deployed or configured service
  - agent: an agent identity or role
  - strategy: a trading or operational strategy
  - exchange: a trading venue or API
  - policy: an operational policy or rule
  - failure_mode: a categorized failure pattern
  - lesson: a learned insight or best practice

Edge types for durable graph:
  - triggered: cause-effect relationship
  - depends_on: dependency ordering
  - failed_with: failure association
  - explains: explanatory relationship
  - learned_from: derivation chain
  - used_tool: tool usage relationship
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .event_buffer import EventBuffer, GAMEdge, GAMNode, GameEdge, GameNode, NodeType

logger = logging.getLogger(__name__)


class DurableNodeType(str, Enum):
    """Durable node types for the consolidated graph."""
    SERVICE = "service"
    AGENT = "agent"
    STRATEGY = "strategy"
    EXCHANGE = "exchange"
    POLICY = "policy"
    FAILURE_MODE = "failure_mode"
    LESSON = "lesson"


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class DurableNode:
    """
    A durable node promoted from ephemeral event episodes.
    These are stored long-term and form the consolidated memory graph.
    """
    node_id: str
    durable_type: DurableNodeType
    title: str
    summary: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.7
    source_episode_ids: List[str] = field(default_factory=list)
    durability_score: float = 1.0  # How "important" this node is
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed_at: float = field(default_factory=time.time)
    ttl_seconds: float = 0  # 0 = never expire

    def touch(self) -> None:
        self.access_count += 1
        self.last_accessed_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "durable_type": self.durable_type.value,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "metadata": self.metadata,
            "confidence": self.confidence,
            "source_episode_ids": self.source_episode_ids,
            "durability_score": self.durability_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at,
            "ttl_seconds": self.ttl_seconds,
        }


@dataclass
class DurableEdge:
    """Edge in the durable consolidated graph."""
    from_node_id: str
    to_node_id: str
    edge_type: str  # triggered, depends_on, failed_with, explains, learned_from, used_tool
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class ConsolidationResult:
    """Result of a consolidation operation."""
    durable_nodes_created: int
    durable_edges_created: int
    episodes_processed: List[str]
    errors: List[str]
    summaries: List[str]


# ── Consolidator ─────────────────────────────────────────────────────────────

class SemanticConsolidator:
    """
    Consolidates ephemeral event episodes into durable topic memory.

    The consolidator:
    1. Takes closure events from the boundary detector
    2. Analyzes the episode content and structure
    3. Promotes key insights to durable nodes
    4. Creates semantic edges between related durable nodes
    5. Stores results in SystemMemoryStore for persistence

    Example::

        consolidator = SemanticConsolidator(event_buffer, system_store)
        result = consolidator.consolidate_episode(trace_id, nodes)
    """

    def __init__(
        self,
        event_buffer: EventBuffer,
        system_store=None,  # Optional SystemMemoryStore
        rag_memory=None,    # Optional RAGMemory fallback
    ) -> None:
        self._buf = event_buffer
        self._system_store = system_store
        self._rag = rag_memory

        # In-memory durable graph (backed by SystemMemoryStore if available)
        self._durable_nodes: Dict[str, DurableNode] = {}
        self._durable_edges: List[DurableEdge] = []
        self._type_index: Dict[DurableNodeType, Set[str]] = {t: set() for t in DurableNodeType}
        self._embedding_index: Dict[str, List[float]] = {}

        # Node type classifiers
        self._type_keywords: Dict[DurableNodeType, List[str]] = {
            DurableNodeType.SERVICE: [
                "service", "server", "api", "endpoint", "deploy", "pod",
                "container", "microservice", "gateway", "broker",
            ],
            DurableNodeType.AGENT: [
                "agent", "orchestrator", "coordinator", "worker",
                "safety_monitor", "trading_agent", "executor",
            ],
            DurableNodeType.STRATEGY: [
                "strategy", "trading", "signal", "entry", "exit",
                "position", "portfolio", "hedge", "arbitrage",
            ],
            DurableNodeType.EXCHANGE: [
                "exchange", "binance", "coinbase", "kraken", "ftx",
                "trading_venue", "market", "orderbook", "liquidity",
            ],
            DurableNodeType.POLICY: [
                "policy", "rule", "constraint", "limit", "threshold",
                "risk_management", "circuit_breaker", "rate_limit",
            ],
            DurableNodeType.FAILURE_MODE: [
                "error", "failure", "exception", "timeout", "crash",
                "bug", "issue", "problem", "incident", "outage",
            ],
            DurableNodeType.LESSON: [
                "learned", "insight", "best_practice", "remember",
                "note", "key_takeaway", "lesson", "pattern",
            ],
        }

    # ── Public API ─────────────────────────────────────────────────────────

    def consolidate_episode(
        self,
        trace_id: str,
        nodes: List[GAMNode],
        edges: List[GAMEdge],
    ) -> ConsolidationResult:
        """
        Consolidate an episode into durable memory.

        Returns a ConsolidationResult with created nodes/edges.
        """
        if not nodes:
            return ConsolidationResult(
                durable_nodes_created=0,
                durable_edges_created=0,
                episodes_processed=[trace_id],
                errors=["No nodes to consolidate"],
                summaries=[],
            )

        errors: List[str] = []
        created_nodes: List[DurableNode] = []
        created_edges: List[DurableEdge] = []
        summaries: List[str] = []

        try:
            # 1. Classify and create durable nodes from episode content
            durable_nodes = self._extract_durable_nodes(trace_id, nodes, edges)
            created_nodes.extend(durable_nodes)

            # 2. Create edges between durable nodes
            durable_edges = self._create_durable_edges(durable_nodes, nodes, edges)
            created_edges.extend(durable_edges)

            # 3. Store in system memory if available
            if self._system_store:
                self._persist_to_system_store(trace_id, durable_nodes, durable_edges)

            # 4. Also store summaries in RAG memory
            if self._rag:
                self._persist_to_rag(durable_nodes)

            # 5. Build summary for the episode
            summary = self._summarize_episode(durable_nodes)
            summaries.append(summary)

        except Exception as exc:
            logger.error("Consolidation failed for trace %s: %s", trace_id, exc)
            errors.append(str(exc))

        return ConsolidationResult(
            durable_nodes_created=len(created_nodes),
            durable_edges_created=len(created_edges),
            episodes_processed=[trace_id],
            errors=errors,
            summaries=summaries,
        )

    def find_related_durable(
        self,
        node_id: str,
        edge_types: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Tuple[DurableNode, float]]:
        """
        Find related durable nodes for a given node.
        Returns nodes with similarity scores.
        """
        source = self._durable_nodes.get(node_id)
        if not source:
            return []

        scores: List[Tuple[DurableNode, float]] = []
        for nid, node in self._durable_nodes.items():
            if nid == node_id:
                continue

            # Edge-based scoring
            edge_score = 0.0
            for edge in self._durable_edges:
                if edge_types and edge.edge_type not in edge_types:
                    continue
                if edge.from_node_id == node_id and edge.to_node_id == nid:
                    edge_score += edge.weight
                elif edge.from_node_id == nid and edge.to_node_id == node_id:
                    edge_score += edge.weight

            # Embedding similarity
            emb_score = 0.0
            if source.embedding and node.embedding:
                emb_score = self._cosine_sim(source.embedding, node.embedding)

            # Combined score
            combined = 0.6 * emb_score + 0.4 * min(edge_score, 1.0)
            if combined > 0:
                scores.append((node, combined))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_durable_nodes(
        self,
        durable_type: Optional[DurableNodeType] = None,
        limit: int = 100,
    ) -> List[DurableNode]:
        """Get durable nodes, optionally filtered by type."""
        nodes = list(self._durable_nodes.values())
        if durable_type:
            nodes = [n for n in nodes if n.durable_type == durable_type]
        nodes.sort(key=lambda n: n.durability_score, reverse=True)
        return nodes[:limit]

    def get_durable_edges(
        self,
        from_node_id: Optional[str] = None,
        to_node_id: Optional[str] = None,
        edge_type: Optional[str] = None,
    ) -> List[DurableEdge]:
        """Get durable edges with optional filtering."""
        edges = list(self._durable_edges)
        if from_node_id:
            edges = [e for e in edges if e.from_node_id == from_node_id]
        if to_node_id:
            edges = [e for e in edges if e.to_node_id == to_node_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges

    # ── Internal Methods ───────────────────────────────────────────────────

    def _extract_durable_nodes(
        self,
        trace_id: str,
        nodes: List[GAMNode],
        edges: List[GAMEdge],
    ) -> List[DurableNode]:
        """Extract and create durable nodes from ephemeral event nodes."""
        durable_nodes: List[DurableNode] = []

        # Group nodes by type and create durable representations
        by_type: Dict[NodeType, List[GAMNode]] = {}
        for node in nodes:
            by_type.setdefault(node.node_type, []).append(node)

        # Process each ephemeral type into durable types
        durable_by_type: Dict[DurableNodeType, DurableNode] = {}

        for ephemeral_type, type_nodes in by_type.items():
            # Classify into durable types based on content
            durable_types = self._classify_nodes(type_nodes)
            for durable_type in durable_types:
                if durable_type not in durable_by_type:
                    durable_node = self._promote_nodes(
                        trace_id, durable_type, type_nodes, durable_types[durable_type]
                    )
                    durable_by_type[durable_type] = durable_node
                    durable_nodes.append(durable_node)

        # Also extract specific patterns
        durable_nodes.extend(self._extract_patterns(nodes))

        # Store in memory
        for node in durable_nodes:
            self._store_durable_node(node)

        return durable_nodes

    def _classify_nodes(self, nodes: List[GAMNode]) -> Dict[DurableNodeType, List[GAMNode]]:
        """Classify ephemeral nodes into durable types."""
        classification: Dict[DurableNodeType, List[GAMNode]] = {}

        for node in nodes:
            content_lower = (node.content + " " + str(node.metadata)).lower()
            best_type: Optional[DurableNodeType] = None
            best_score = 0

            for durable_type, keywords in self._type_keywords.items():
                score = sum(1 for kw in keywords if kw in content_lower)
                if score > best_score:
                    best_score = score
                    best_type = durable_type

            if best_type and best_score > 0:
                classification.setdefault(best_type, []).append(node)

        return classification

    def _promote_nodes(
        self,
        trace_id: str,
        durable_type: DurableNodeType,
        source_nodes: List[GAMNode],
        associated_nodes: List[GAMNode],
    ) -> DurableNode:
        """Promote ephemeral nodes to a single durable node."""
        # Combine content from source nodes
        contents = [n.content for n in source_nodes]
        combined_content = " ".join(contents)
        combined_embedding = self._average_embeddings([n.embedding for n in source_nodes if n.embedding])

        # Generate title from first significant content
        title = self._generate_title(source_nodes, durable_type)
        summary = self._generate_summary(source_nodes, durable_type)

        node_id = self._generate_durable_id(trace_id, durable_type)

        # Calculate confidence from source nodes
        avg_confidence = sum(n.confidence for n in source_nodes) / len(source_nodes) if source_nodes else 0.5

        return DurableNode(
            node_id=node_id,
            durable_type=durable_type,
            title=title,
            summary=summary,
            content=combined_content[:4000],  # Truncate long content
            embedding=combined_embedding,
            metadata={
                "source_trace_id": trace_id,
                "source_node_count": len(source_nodes),
                "source_types": [n.node_type.value for n in source_nodes],
            },
            confidence=avg_confidence,
            source_episode_ids=[trace_id],
            durability_score=avg_confidence * len(source_nodes),
            ttl_seconds=0,  # Never expire by default
        )

    def _extract_patterns(self, nodes: List[GAMNode]) -> List[DurableNode]:
        """Extract specific patterns like failure modes from nodes."""
        patterns: List[DurableNode] = []

        # Look for failure/error patterns
        error_nodes = [n for n in nodes if self._is_error_node(n)]
        if len(error_nodes) >= 2:
            # Create a failure_mode node
            failure_summary = " ".join(n.content for n in error_nodes[:3])
            patterns.append(DurableNode(
                node_id=self._generate_durable_id(error_nodes[0].trace_id or "unknown", DurableNodeType.FAILURE_MODE),
                durable_type=DurableNodeType.FAILURE_MODE,
                title=self._extract_error_type(error_nodes[0]),
                summary=failure_summary[:500],
                content=failure_summary,
                confidence=min(0.9, 0.5 + 0.1 * len(error_nodes)),
                source_episode_ids=[n.trace_id for n in error_nodes if n.trace_id],
            ))

        return patterns

    def _is_error_node(self, node: GAMNode) -> bool:
        """Check if a node represents an error."""
        error_signals = ["error", "exception", "failed", "crash", "timeout", "rejected"]
        content_lower = node.content.lower()
        return any(sig in content_lower for sig in error_signals) or node.metadata.get("status") == "error"

    def _extract_error_type(self, node: GAMNode) -> str:
        """Extract the type of error from a node."""
        error_types = ["timeout", "connection", "auth", "validation", "permission", "not_found", "rate_limit"]
        content_lower = node.content.lower()
        for et in error_types:
            if et in content_lower:
                return f"{et} error"
        return "unknown error"

    def _create_durable_edges(
        self,
        durable_nodes: List[DurableNode],
        ephemeral_nodes: List[GAMNode],
        ephemeral_edges: List[GAMEdge],
    ) -> List[DurableEdge]:
        """Create edges between durable nodes based on ephemeral relationships."""
        durable_edges: List[DurableEdge] = []

        # Map ephemeral nodes to durable nodes
        node_mapping: Dict[str, DurableNode] = {}
        for dn in durable_nodes:
            for src_trace in dn.source_episode_ids:
                for en in ephemeral_nodes:
                    if en.trace_id == src_trace:
                        node_mapping[en.node_id] = dn

        # Convert ephemeral edges to durable edges
        for eedge in ephemeral_edges:
            from_durable = node_mapping.get(eedge.from_node_id)
            to_durable = node_mapping.get(eedge.to_node_id)

            if from_durable and to_durable and from_durable != to_durable:
                # Map edge type
                edge_type = self._map_edge_type(eedge.edge_type)
                durable_edge = DurableEdge(
                    from_node_id=from_durable.node_id,
                    to_node_id=to_durable.node_id,
                    edge_type=edge_type,
                    weight=eedge.weight,
                    metadata={"ephemeral_trace": eedge.from_node_id},
                )
                durable_edges.append(durable_edge)
                self._durable_edges.append(durable_edge)

        return durable_edges

    def _map_edge_type(self, ephemeral_type: str) -> str:
        """Map ephemeral edge types to durable edge types."""
        mapping = {
            "triggered": "triggered",
            "resulted_in": "triggered",
            "depends_on": "depends_on",
            "failed_with": "failed_with",
            "explains": "explains",
            "learned_from": "learned_from",
            "used_tool": "used_tool",
        }
        return mapping.get(ephemeral_type, "triggered")

    def _store_durable_node(self, node: DurableNode) -> None:
        """Store a durable node in the in-memory graph."""
        self._durable_nodes[node.node_id] = node
        self._type_index[node.durable_type].add(node.node_id)
        if node.embedding:
            self._embedding_index[node.node_id] = node.embedding

    def _persist_to_system_store(self, trace_id: str, nodes: List[DurableNode], edges: List[DurableEdge]) -> None:
        """Persist durable nodes to SystemMemoryStore."""
        if not self._system_store:
            return

        try:
            from simp.memory.system_memory import Episode, Lesson

            for node in nodes:
                if node.durable_type == DurableNodeType.LESSON:
                    lesson = Lesson(
                        title=node.title,
                        summary=node.summary,
                        lesson_type="gam_consolidated",
                        confidence=node.confidence,
                        evidence={"trace_id": trace_id, "content": node.content[:1000]},
                        source_episode_ids=node.source_episode_ids,
                    )
                    self._system_store.upsert_lesson(lesson)

            # Store as episode
            episode = Episode(
                episode_type="gam_consolidation",
                source="gam_consolidator",
                entity=",".join(n.durable_type.value for n in nodes),
                summary=self._summarize_episode(nodes),
                occurred_at=datetime.now(timezone.utc).isoformat(),
                payload={"node_ids": [n.node_id for n in nodes], "trace_id": trace_id},
                tags=[n.durable_type.value for n in nodes],
            )
            self._system_store.add_episode(episode)

        except ImportError:
            logger.debug("SystemMemoryStore not available for persistence")
        except Exception as exc:
            logger.warning("Failed to persist to system store: %s", exc)

    def _persist_to_rag(self, nodes: List[DurableNode]) -> None:
        """Persist summaries to RAG memory for vector search."""
        if not self._rag:
            return

        try:
            for node in nodes:
                if node.confidence >= 0.7:  # Only high-confidence nodes
                    self._rag.store(
                        content=node.summary,
                        source=f"gam:{node.durable_type.value}",
                        metadata={"node_id": node.node_id, "confidence": node.confidence},
                    )
        except Exception as exc:
            logger.debug("RAG persistence failed: %s", exc)

    def _generate_durable_id(self, trace_id: str, durable_type: DurableNodeType) -> str:
        """Generate a deterministic ID for a durable node."""
        raw = f"{trace_id}:{durable_type.value}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _generate_title(self, nodes: List[GAMNode], durable_type: DurableNodeType) -> str:
        """Generate a title from node content."""
        if not nodes:
            return f"{durable_type.value}_unnamed"

        # Use first significant content as basis
        first = nodes[0].content[:100]
        # Clean up
        title = first.strip().replace("\n", " ")
        if len(title) > 60:
            title = title[:57] + "..."
        return title or f"{durable_type.value}_episode"

    def _generate_summary(self, nodes: List[GAMNode], durable_type: DurableNodeType) -> str:
        """Generate a summary of the episode."""
        if not nodes:
            return ""

        # Combine key content
        contents = [n.content for n in nodes[:5]]
        combined = " ".join(contents)
        # Truncate to reasonable length
        if len(combined) > 500:
            combined = combined[:497] + "..."
        return combined.strip()

    def _summarize_episode(self, nodes: List[DurableNode]) -> str:
        """Generate a summary string for the episode."""
        if not nodes:
            return "Empty episode"

        type_counts: Dict[str, int] = {}
        for node in nodes:
            type_counts[node.durable_type.value] = type_counts.get(node.durable_type.value, 0) + 1

        parts = [f"Episode created {len(nodes)} durable nodes:"]
        for dtype, count in sorted(type_counts.items()):
            parts.append(f"  - {count}x {dtype}")
        return "\n".join(parts)

    def _average_embeddings(self, embeddings: List[Optional[List[float]]]) -> Optional[List[float]]:
        """Average multiple embeddings."""
        valid = [e for e in embeddings if e is not None]
        if not valid:
            return None

        dim = len(valid[0])
        result = [0.0] * dim
        for emb in valid:
            for i, v in enumerate(emb):
                result[i] += v
        count = len(valid)
        return [v / count for v in result]

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity."""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        ma = math.sqrt(sum(x * x for x in a)) or 1e-9
        mb = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / (ma * mb)

    def stats(self) -> Dict[str, Any]:
        """Return consolidator statistics."""
        return {
            "durable_nodes": len(self._durable_nodes),
            "durable_edges": len(self._durable_edges),
            "by_type": {t.value: len(ns) for t, ns in self._type_index.items()},
        }
