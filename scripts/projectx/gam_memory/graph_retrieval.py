"""
GAM Graph Retrieval — Phase 7

Multi-factor ranking retrieval from both local (session) and global
(durable) memory graphs.

Scoring formula:
  score = 0.40 * semantic + 0.20 * recency + 0.15 * confidence + 
          0.15 * role_match + 0.10 * graph_proximity

Supports both local (session) and global (durable) graph traversal.
Falls back to RAGMemory for vector-based search when graph unavailable.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .event_buffer import EventBuffer, GAMNode, NodeType
from .semantic_consolidator import DurableNode, DurableNodeType, SemanticConsolidator

logger = logging.getLogger(__name__)

# ── Scoring weights ────────────────────────────────────────────────────────────

SEMANTIC_WEIGHT = 0.40
RECENCY_WEIGHT = 0.20
CONFIDENCE_WEIGHT = 0.15
ROLE_MATCH_WEIGHT = 0.15
GRAPH_PROXIMITY_WEIGHT = 0.10


@dataclass
class RetrievalScore:
    """A scored retrieval result with factor breakdown."""
    node_id: str
    node_type: str
    title: str
    content: str
    total_score: float
    semantic_score: float
    recency_score: float
    confidence_score: float
    role_match_score: float
    graph_proximity_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "local"  # "local" or "durable"


@dataclass
class RetrievalQuery:
    """Query parameters for graph retrieval."""
    query_text: str
    query_embedding: Optional[List[float]] = None
    role: Optional[str] = None
    node_types: Optional[List[str]] = None
    trace_id: Optional[str] = None
    top_k: int = 8
    min_score: float = 0.3
    include_local: bool = True
    include_durable: bool = True


# ── Retrieval Engine ───────────────────────────────────────────────────────────

class GraphRetrieval:
    """
    Multi-factor ranking retrieval from memory graphs.

    Combines semantic similarity, recency, confidence, role matching,
    and graph proximity into a unified ranking score.

    Example::

        retrieval = GraphRetrieval(event_buffer, consolidator, rag_memory)
        results = retrieval.query(RetrievalQuery(
            query_text="How did we handle errors in the trading agent?",
            role="orchestrator",
            top_k=10,
        ))
    """

    def __init__(
        self,
        event_buffer: EventBuffer,
        consolidator: Optional[SemanticConsolidator] = None,
        rag_memory=None,
    ) -> None:
        self._buf = event_buffer
        self._consolidator = consolidator
        self._rag = rag_memory

        # Cache for query embeddings
        self._embed_cache: Dict[str, List[float]] = {}

        # Try sentence-transformers if available
        self._st_model = None
        try:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            logger.debug("sentence-transformers not available for retrieval")

    # ── Public API ─────────────────────────────────────────────────────────

    def query(self, query: RetrievalQuery) -> List[RetrievalScore]:
        """
        Execute a multi-factor retrieval query.

        Returns scored results from local graph, durable graph, and RAG
        (if available), merged and ranked.
        """
        results: List[RetrievalScore] = []

        # Get query embedding
        q_emb = query.query_embedding or self._embed(query.query_text)

        # 1. Local graph retrieval
        if query.include_local:
            local_results = self._retrieve_local(query, q_emb)
            results.extend(local_results)

        # 2. Durable graph retrieval
        if query.include_durable and self._consolidator:
            durable_results = self._retrieve_durable(query, q_emb)
            results.extend(durable_results)

        # 3. RAG fallback
        if not results and self._rag:
            rag_results = self._retrieve_rag(query)
            results.extend(rag_results)

        # 4. Filter and rank
        filtered = [r for r in results if r.total_score >= query.min_score]
        filtered.sort(key=lambda r: r.total_score, reverse=True)

        return filtered[:query.top_k]

    def query_local(
        self,
        query_text: str,
        node_types: Optional[List[NodeType]] = None,
        trace_id: Optional[str] = None,
        top_k: int = 8,
        role: Optional[str] = None,
    ) -> List[RetrievalScore]:
        """Convenience method for local graph-only queries."""
        return self.query(RetrievalQuery(
            query_text=query_text,
            node_types=[t.value for t in node_types] if node_types else None,
            trace_id=trace_id,
            top_k=top_k,
            role=role,
            include_durable=False,
        ))

    def query_durable(
        self,
        query_text: str,
        durable_types: Optional[List[DurableNodeType]] = None,
        top_k: int = 8,
        role: Optional[str] = None,
    ) -> List[RetrievalScore]:
        """Convenience method for durable graph-only queries."""
        return self.query(RetrievalQuery(
            query_text=query_text,
            node_types=[t.value for t in durable_types] if durable_types else None,
            top_k=top_k,
            role=role,
            include_local=False,
        ))

    def get_context_chain(
        self,
        start_node_id: str,
        max_depth: int = 3,
    ) -> List[RetrievalScore]:
        """
        Retrieve a context chain from a starting node.
        Useful for understanding dependencies and context flow.
        """
        chain: List[RetrievalScore] = []
        visited: set = set()

        current_ids = [start_node_id]
        for _ in range(max_depth):
            next_ids = []
            for nid in current_ids:
                if nid in visited:
                    continue
                visited.add(nid)

                # Get from local graph
                node = self._buf.get_node(nid)
                if node:
                    score = RetrievalScore(
                        node_id=node.node_id,
                        node_type=node.node_type.value,
                        title=self._extract_title(node.content),
                        content=node.content,
                        total_score=1.0,
                        semantic_score=1.0,
                        recency_score=1.0,
                        confidence_score=node.confidence,
                        role_match_score=1.0 if node.role else 0.5,
                        graph_proximity_score=1.0,
                        metadata=node.metadata,
                        source="local",
                    )
                    chain.append(score)

                # Get from durable graph
                if self._consolidator:
                    durable = self._consolidator._durable_nodes.get(nid)
                    if durable:
                        score = RetrievalScore(
                            node_id=durable.node_id,
                            node_type=durable.durable_type.value,
                            title=durable.title,
                            content=durable.summary,
                            total_score=1.0,
                            semantic_score=1.0,
                            recency_score=1.0,
                            confidence_score=durable.confidence,
                            role_match_score=1.0,
                            graph_proximity_score=1.0,
                            metadata=durable.metadata,
                            source="durable",
                        )
                        chain.append(score)

                # Get neighbors
                neighbors = self._buf.get_neighbors(nid, depth=1)
                next_ids.extend(n.node_id for n in neighbors.get("out", []) if n.node_id not in visited)
                next_ids.extend(n.node_id for n in neighbors.get("in", []) if n.node_id not in visited)

            current_ids = list(set(next_ids))[:5]  # Limit breadth

        return chain

    # ── Internal Retrieval Methods ─────────────────────────────────────────

    def _retrieve_local(
        self,
        query: RetrievalQuery,
        q_emb: List[float],
    ) -> List[RetrievalScore]:
        """Retrieve from local event graph."""
        results: List[RetrievalScore] = []

        # Get candidate nodes
        if query.trace_id:
            candidates = self._buf.get_trace_nodes(query.trace_id)
        elif query.node_types:
            candidates = []
            for nt_str in query.node_types:
                try:
                    nt = NodeType(nt_str)
                    candidates.extend(self._buf.get_nodes_by_type(nt))
                except ValueError:
                    pass
        else:
            # All non-expired nodes
            candidates = [n for n in self._buf._nodes.values() if not n.is_expired]

        # Score each candidate
        for node in candidates:
            score = self._score_local_node(node, query, q_emb)
            if score.total_score >= query.min_score:
                results.append(score)

        return results

    def _retrieve_durable(
        self,
        query: RetrievalQuery,
        q_emb: List[float],
    ) -> List[RetrievalScore]:
        """Retrieve from durable consolidated graph."""
        if not self._consolidator:
            return []

        results: List[RetrievalScore] = []

        # Get candidates
        if query.node_types:
            candidates: List[DurableNode] = []
            for nt_str in query.node_types:
                try:
                    dt = DurableNodeType(nt_str)
                    candidates.extend(self._consolidator.get_durable_nodes(dt))
                except ValueError:
                    pass
        else:
            candidates = list(self._consolidator._durable_nodes.values())

        # Score each candidate
        for node in candidates:
            score = self._score_durable_node(node, query, q_emb)
            if score.total_score >= query.min_score:
                results.append(score)

        return results

    def _retrieve_rag(self, query: RetrievalQuery) -> List[RetrievalScore]:
        """Fallback to RAG memory for vector-based retrieval."""
        if not self._rag:
            return []

        results: List[RetrievalScore] = []
        try:
            rag_results = self._rag.query(query.query_text, top_k=query.top_k)
            for rr in rag_results:
                results.append(RetrievalScore(
                    node_id=rr.entry.id,
                    node_type="rag_memory",
                    title=self._extract_title(rr.entry.content),
                    content=rr.entry.content,
                    total_score=rr.similarity,
                    semantic_score=rr.similarity,
                    recency_score=self._recency_score(rr.entry.created_at),
                    confidence_score=rr.entry.access_count / 10.0,  # Proxy for confidence
                    role_match_score=0.5,  # Neutral
                    graph_proximity_score=0.5,  # Neutral
                    metadata=rr.entry.metadata,
                    source="rag",
                ))
        except Exception as exc:
            logger.debug("RAG retrieval failed: %s", exc)

        return results

    # ── Scoring Methods ────────────────────────────────────────────────────

    def _score_local_node(
        self,
        node: GAMNode,
        query: RetrievalQuery,
        q_emb: List[float],
    ) -> RetrievalScore:
        """Compute multi-factor score for a local graph node."""
        # Semantic score (embedding similarity)
        semantic = self._semantic_score(node.embedding, q_emb)

        # Recency score (exponential decay)
        recency = self._recency_score(node.created_at)

        # Confidence score (direct)
        confidence = min(node.confidence, 1.0)

        # Role match
        role_match = self._role_match_score(node.role, query.role)

        # Graph proximity (to query context)
        # This is simplified - in production you'd trace actual graph distance
        proximity = 0.5  # Default neutral

        # Weighted total
        total = (
            SEMANTIC_WEIGHT * semantic +
            RECENCY_WEIGHT * recency +
            CONFIDENCE_WEIGHT * confidence +
            ROLE_MATCH_WEIGHT * role_match +
            GRAPH_PROXIMITY_WEIGHT * proximity
        )

        return RetrievalScore(
            node_id=node.node_id,
            node_type=node.node_type.value,
            title=self._extract_title(node.content),
            content=node.content,
            total_score=total,
            semantic_score=semantic,
            recency_score=recency,
            confidence_score=confidence,
            role_match_score=role_match,
            graph_proximity_score=proximity,
            metadata=node.metadata,
            source="local",
        )

    def _score_durable_node(
        self,
        node: DurableNode,
        query: RetrievalQuery,
        q_emb: List[float],
    ) -> RetrievalScore:
        """Compute multi-factor score for a durable graph node."""
        # Semantic score
        semantic = self._semantic_score(node.embedding, q_emb)

        # Recency (based on last access, not creation)
        recency = self._recency_score(node.last_accessed_at)

        # Confidence
        confidence = min(node.confidence, 1.0)

        # Role match (durables don't have roles, so neutral)
        role_match = 0.5

        # Graph proximity (higher for durable nodes - they're refined)
        proximity = 0.7

        # Weighted total
        total = (
            SEMANTIC_WEIGHT * semantic +
            RECENCY_WEIGHT * recency +
            CONFIDENCE_WEIGHT * confidence +
            ROLE_MATCH_WEIGHT * role_match +
            GRAPH_PROXIMITY_WEIGHT * proximity
        )

        return RetrievalScore(
            node_id=node.node_id,
            node_type=node.durable_type.value,
            title=node.title,
            content=node.summary,
            total_score=total,
            semantic_score=semantic,
            recency_score=recency,
            confidence_score=confidence,
            role_match_score=role_match,
            graph_proximity_score=proximity,
            metadata=node.metadata,
            source="durable",
        )

    def _semantic_score(self, node_emb: Optional[List[float]], query_emb: List[float]) -> float:
        """Compute semantic similarity score."""
        if node_emb is None:
            return 0.3  # Neutral fallback
        return self._cosine_sim(node_emb, query_emb)

    def _recency_score(self, timestamp: float) -> float:
        """
        Compute recency score with exponential decay.
        Score of 1.0 for very recent, decaying over 24 hours.
        """
        age_seconds = time.time() - timestamp
        half_life = 24 * 3600  # 24 hours
        return math.exp(-0.693 * age_seconds / half_life)

    def _role_match_score(self, node_role: Optional[str], query_role: Optional[str]) -> float:
        """Compute role match score (0-1)."""
        if not query_role:
            return 0.5  # Neutral if no role filter
        if not node_role:
            return 0.3  # Slight penalty for unknown role
        if node_role == query_role:
            return 1.0
        # Partial match for related roles
        related_roles = {
            "orchestrator": ["coordinator", "controller"],
            "safety": ["guardian", "monitor"],
            "trading": ["agent", "executor"],
        }
        related = related_roles.get(query_role, [])
        if node_role in related:
            return 0.7
        return 0.2

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        ma = math.sqrt(sum(x * x for x in a)) or 1e-9
        mb = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / (ma * mb)

    def _embed(self, text: str) -> List[float]:
        """Get embedding for text."""
        if text in self._embed_cache:
            return self._embed_cache[text]

        if self._st_model is not None:
            vec = self._st_model.encode(text, normalize_embeddings=True).tolist()
        else:
            vec = self._hash_embed(text)

        self._embed_cache[text] = vec
        return vec

    def _hash_embed(self, text: str, dim: int = 384) -> List[float]:
        """Fallback hash embedding."""
        vec = [0.0] * dim
        tokens = text.lower().split()
        for tok in tokens:
            h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
            for i in range(dim):
                vec[i] += math.sin((h >> i) & 0xFF) / (len(tokens) or 1)
        mag = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / mag for v in vec]

    def _extract_title(self, content: str, max_len: int = 80) -> str:
        """Extract a title from content."""
        first_line = content.split("\n")[0][:max_len]
        if len(first_line) < len(content):
            first_line += "..."
        return first_line or content[:max_len]

    def stats(self) -> Dict[str, Any]:
        """Return retrieval engine statistics."""
        return {
            "embed_cache_size": len(self._embed_cache),
            "local_nodes": len(self._buf._nodes),
            "durable_nodes": len(self._consolidator._durable_nodes) if self._consolidator else 0,
            "rag_available": self._rag is not None,
        }
