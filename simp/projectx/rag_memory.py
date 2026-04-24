"""
ProjectX RAG Memory — Phase 2

Long-term vector memory for agents. Stores embeddings with metadata,
supports similarity search, and implements a TTL-based forgetting mechanism
so stale knowledge doesn't pollute retrieval.

Backends (in priority order):
  1. ChromaDB (if installed) — persistent, full-featured
  2. In-process numpy fallback — zero-dependency, ephemeral

Public API is the same regardless of backend.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default TTL: 7 days.  Set to 0 to disable forgetting.
DEFAULT_TTL_SECONDS = 7 * 24 * 3600
# Minimum cosine similarity to surface a result
DEFAULT_SIMILARITY_THRESHOLD = 0.65
# Maximum results from a single query
DEFAULT_TOP_K = 8


@dataclass
class MemoryEntry:
    """A single stored piece of knowledge."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: float = DEFAULT_TTL_SECONDS  # 0 = never expire

    @property
    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return (time.time() - self.created_at) > self.ttl

    def touch(self) -> None:
        self.accessed_at = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RetrievalResult:
    entry: MemoryEntry
    similarity: float

    def to_dict(self) -> Dict:
        return {
            "entry": self.entry.to_dict(),
            "similarity": self.similarity,
        }


# ── Embedding helpers ─────────────────────────────────────────────────────────

def _embed_text(text: str) -> List[float]:
    """
    Return a text embedding. Uses sentence-transformers if available,
    otherwise falls back to a fast TF-IDF-style hash embedding (768-d).
    """
    try:
        from sentence_transformers import SentenceTransformer
        _model = _get_st_model()
        vec = _model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except ImportError:
        pass
    return _hash_embed(text)


_st_model_cache = None


def _get_st_model():
    global _st_model_cache
    if _st_model_cache is None:
        from sentence_transformers import SentenceTransformer
        _st_model_cache = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model_cache


def _hash_embed(text: str, dim: int = 384) -> List[float]:
    """Deterministic hash-based pseudo-embedding. Not semantically meaningful
    but preserves uniqueness for dedup and is stable across runs."""
    vec = [0.0] * dim
    tokens = text.lower().split()
    for tok in tokens:
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        for i in range(dim):
            vec[i] += math.sin((h >> i) & 0xFF) / (len(tokens) or 1)
    mag = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / mag for v in vec]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    ma = math.sqrt(sum(x * x for x in a)) or 1e-9
    mb = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (ma * mb)


# ── In-process fallback store ─────────────────────────────────────────────────

class _NumpyStore:
    """Pure-Python in-memory vector store. No persistence between restarts."""

    def __init__(self) -> None:
        self._entries: Dict[str, MemoryEntry] = {}
        self._vectors: Dict[str, List[float]] = {}

    def add(self, entry: MemoryEntry, vector: List[float]) -> None:
        self._entries[entry.id] = entry
        self._vectors[entry.id] = vector

    def query(
        self, vector: List[float], top_k: int, threshold: float
    ) -> List[RetrievalResult]:
        results = []
        for eid, evec in self._vectors.items():
            entry = self._entries[eid]
            if entry.is_expired:
                continue
            sim = _cosine(vector, evec)
            if sim >= threshold:
                results.append(RetrievalResult(entry=entry, similarity=sim))
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            del self._vectors[entry_id]
            return True
        return False

    def count(self) -> int:
        return len(self._entries)

    def prune_expired(self) -> int:
        expired = [eid for eid, e in self._entries.items() if e.is_expired]
        for eid in expired:
            self.delete(eid)
        return len(expired)


# ── Main RAGMemory class ──────────────────────────────────────────────────────

class RAGMemory:
    """
    Long-term vector memory for ProjectX agents.

    Example::

        mem = RAGMemory(persist_dir="./projectx_memory")
        mem.store("Python uses indentation for blocks.", source="docs")
        results = mem.query("How does Python handle code blocks?")
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "projectx_knowledge",
        ttl: float = DEFAULT_TTL_SECONDS,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self._ttl = ttl
        self._threshold = similarity_threshold
        self._top_k = top_k
        self._persist_dir = Path(persist_dir or "./projectx_memory")
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._collection_name = collection_name
        self._store = self._init_store()
        logger.info("RAGMemory ready (backend=%s)", type(self._store).__name__)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def _init_store(self):
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(self._persist_dir))
            collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            return _ChromaStore(collection)
        except ImportError:
            logger.debug("chromadb not installed — using in-process fallback store")
            return _NumpyStore()

    # ── Public API ────────────────────────────────────────────────────────

    # Maximum content size per entry (bytes)
    MAX_CONTENT_BYTES = 128_000

    def store(
        self,
        content: str,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[float] = None,
        entry_id: Optional[str] = None,
    ) -> str:
        """
        Store a piece of knowledge and return its ID.

        Args:
            content: The text to embed and store.
            source:  Where this knowledge came from (URL, file, agent ID…).
            metadata: Arbitrary key/value pairs attached to the entry.
            ttl:     Override the default TTL (seconds). 0 = never expire.
            entry_id: Optional explicit ID (auto-generated if omitted).

        Returns:
            The assigned entry ID.
        """
        if not isinstance(content, str) or not content.strip():
            raise ValueError("RAGMemory.store: content must be a non-empty string")

        # Enforce size cap before embedding (protects against OOM on giant docs)
        encoded = content.encode("utf-8")
        if len(encoded) > self.MAX_CONTENT_BYTES:
            logger.warning(
                "RAGMemory: content truncated from %d to %d bytes",
                len(encoded), self.MAX_CONTENT_BYTES,
            )
            content = encoded[:self.MAX_CONTENT_BYTES].decode("utf-8", errors="replace")

        # Deduplication: if exact content hash already exists, skip re-embedding
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        if entry_id is None:
            entry_id = content_hash  # deterministic: same content → same ID

        entry = MemoryEntry(
            id=entry_id,
            content=content,
            metadata=metadata or {},
            source=source,
            created_at=time.time(),
            accessed_at=time.time(),
            ttl=ttl if ttl is not None else self._ttl,
        )
        vector = _embed_text(content)
        self._store.add(entry, vector)
        logger.debug("Stored memory %s (%d chars, source=%s)", entry_id, len(content), source)
        return entry_id

    def query(
        self,
        text: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        filter_source: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        Retrieve the most relevant memories for a query.

        Args:
            text:   The query string to embed and match.
            top_k:  Max results to return.
            threshold: Minimum cosine similarity (0–1).
            filter_source: Only return entries from this source.

        Returns:
            List of RetrievalResult sorted by similarity descending.
        """
        vector = _embed_text(text)
        results = self._store.query(
            vector=vector,
            top_k=top_k or self._top_k,
            threshold=threshold if threshold is not None else self._threshold,
        )
        if filter_source:
            results = [r for r in results if r.entry.source == filter_source]
        for r in results:
            r.entry.touch()
        return results

    def forget(self, entry_id: str) -> bool:
        """Delete a specific memory entry. Returns True if it existed."""
        return self._store.delete(entry_id)

    def prune_expired(self) -> int:
        """Remove all expired entries. Returns count of pruned entries."""
        return self._store.prune_expired()

    def count(self) -> int:
        """Return total number of stored memories (including not-yet-expired)."""
        return self._store.count()

    def store_document(self, document: str, source: str = "", chunk_size: int = 800) -> List[str]:
        """
        Split a long document into chunks and store each chunk.

        Returns the list of assigned entry IDs.
        """
        chunks = self._chunk(document, chunk_size)
        ids = []
        for i, chunk in enumerate(chunks):
            eid = self.store(chunk, source=source, metadata={"chunk": i, "total": len(chunks)})
            ids.append(eid)
        return ids

    @staticmethod
    def _chunk(text: str, size: int) -> List[str]:
        """Split text into overlapping chunks at sentence boundaries."""
        sentences = text.replace("\n\n", "\n").split(". ")
        chunks, current = [], ""
        for sent in sentences:
            if len(current) + len(sent) > size and current:
                chunks.append(current.strip())
                current = sent + ". "
            else:
                current += sent + ". "
        if current.strip():
            chunks.append(current.strip())
        return chunks or [text[:size]]


# ── ChromaDB wrapper ──────────────────────────────────────────────────────────

class _ChromaStore:
    def __init__(self, collection) -> None:
        self._col = collection
        self._entries: Dict[str, MemoryEntry] = {}

    def add(self, entry: MemoryEntry, vector: List[float]) -> None:
        self._entries[entry.id] = entry
        self._col.upsert(
            ids=[entry.id],
            embeddings=[vector],
            documents=[entry.content],
            metadatas=[{
                "source": entry.source,
                "created_at": entry.created_at,
                "ttl": entry.ttl,
                **{k: str(v) for k, v in entry.metadata.items()},
            }],
        )

    def query(self, vector: List[float], top_k: int, threshold: float) -> List[RetrievalResult]:
        results = self._col.query(
            query_embeddings=[vector],
            n_results=min(top_k, max(1, self._col.count())),
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for i, doc_id in enumerate(results["ids"][0]):
            dist = results["distances"][0][i]
            sim = 1.0 - dist  # Chroma cosine distance → similarity
            if sim < threshold:
                continue
            meta = results["metadatas"][0][i]
            content = results["documents"][0][i]
            entry = self._entries.get(doc_id) or MemoryEntry(
                id=doc_id,
                content=content,
                source=meta.get("source", ""),
                created_at=float(meta.get("created_at", 0)),
                ttl=float(meta.get("ttl", DEFAULT_TTL_SECONDS)),
            )
            out.append(RetrievalResult(entry=entry, similarity=sim))
        return out

    def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._col.delete(ids=[entry_id])
            return True
        return False

    def count(self) -> int:
        return self._col.count()

    def prune_expired(self) -> int:
        expired = [eid for eid, e in self._entries.items() if e.is_expired]
        for eid in expired:
            self.delete(eid)
        return len(expired)


# Module-level singleton
_memory: Optional[RAGMemory] = None


def get_rag_memory(persist_dir: Optional[str] = None) -> RAGMemory:
    global _memory
    if _memory is None:
        _memory = RAGMemory(persist_dir=persist_dir or "./projectx_memory")
    return _memory
