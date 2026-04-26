"""Tests for RAG Memory — ProjectX vector store."""

import time
import pytest
from pathlib import Path

# Force numpy fallback (no network)
import sys
sys.modules["sentence_transformers"] = None

from simp.projectx.rag_memory import (
    RAGMemory,
    MemoryEntry,
    RetrievalResult,
    DEFAULT_TTL_SECONDS,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K,
)


@pytest.fixture
def mem(tmp_path) -> RAGMemory:
    """Fresh in-memory RAG store per test."""
    return RAGMemory(persist_dir=str(tmp_path / "rag"))


class TestStoreQuery:
    def test_store_and_query(self, mem) -> None:
        # Hash embeddings use token overlap — identical text scores 1.0
        eid = mem.store("cats are furry mammals", source="test")
        results = mem.query("cats are furry mammals", top_k=5)
        found = any(e.entry.content == "cats are furry mammals" for e in results)
        assert found, "Stored entry should be retrievable by identical query"

    def test_similarity_threshold(self, mem) -> None:
        mem.store("apple fruit red", source="test")
        mem.store("car vehicle red", source="test")
        # Threshold 0.99: only exact token match scores that high
        results = mem.query("apple fruit red", top_k=5, threshold=0.99)
        assert len(results) == 1
        assert "apple" in results[0].entry.content

    def test_top_k_limit(self, mem) -> None:
        for i in range(10):
            mem.store(f"entry number {i} with some content", source="test")
        results = mem.query("entry", top_k=3)
        assert len(results) <= 3

    def test_forget(self, mem) -> None:
        eid = mem.store("temporary fact", source="test")
        assert mem.count() == 1
        removed = mem.forget(eid)
        assert removed is True
        assert mem.count() == 0

    def test_prune_expired(self, mem) -> None:
        mem.store("short-lived", source="test", ttl=1)
        assert mem.count() == 1
        time.sleep(1.5)
        pruned = mem.prune_expired()
        assert mem.count() == 0
        assert pruned >= 1

    def test_ttl_expiry(self, mem) -> None:
        mem.store("expires soon", source="test", ttl=1)
        time.sleep(0.2)
        # Still present (not expired yet)
        results = mem.query("expires soon", top_k=5)
        assert len(results) == 1
        time.sleep(1.2)
        # Now expired
        results = mem.query("expires soon", top_k=5)
        assert len(results) == 0

    def test_touch_updates_access(self, mem) -> None:
        eid = mem.store("frequently accessed", source="test")
        results = mem.query("frequently accessed", top_k=1)
        assert results[0].entry.access_count >= 1

    def test_hash_embedding_stability(self, mem) -> None:
        from simp.projectx.rag_memory import _embed_text
        v1 = _embed_text("stable content")
        v2 = _embed_text("stable content")
        assert v1 == v2, "Same text must produce identical embedding"

    def test_different_texts_different_embeddings(self, mem) -> None:
        from simp.projectx.rag_memory import _embed_text
        v1 = _embed_text("the quick brown fox")
        v2 = _embed_text("jumps over the lazy dog")
        assert v1 != v2, "Different texts should produce different embeddings"

    def test_memory_count(self, mem) -> None:
        for i in range(5):
            mem.store(f"fact {i}", source="test")
        assert mem.count() == 5

    def test_metadata_preserved(self, mem) -> None:
        eid = mem.store("data", source="test", metadata={"key": "value", "num": 42})
        results = mem.query("data", top_k=1)
        assert results[0].entry.metadata.get("key") == "value"
        assert results[0].entry.metadata.get("num") == 42

    def test_source_filter(self, mem) -> None:
        mem.store("alpha content", source="source_a")
        mem.store("beta content", source="source_b")
        mem.store("gamma content", source="source_a")
        results = mem.query("alpha beta gamma", top_k=5, filter_source="source_a")
        for r in results:
            assert r.entry.source == "source_a"

    def test_store_document_chunks(self, mem) -> None:
        long_doc = "This is sentence one. " * 200
        ids = mem.store_document(long_doc, source="test", chunk_size=400)
        assert len(ids) > 1, "Long doc should be chunked"

    def test_retrieval_result_to_dict(self, mem) -> None:
        eid = mem.store("test content", source="test")
        results = mem.query("test content", top_k=1)
        d = results[0].to_dict()
        assert "entry" in d
        assert "similarity" in d
        assert isinstance(d["similarity"], float)

    def test_memory_entry_to_dict(self, mem) -> None:
        eid = mem.store("test content", source="test")
        results = mem.query("test content", top_k=1)
        d = results[0].entry.to_dict()
        assert "id" in d
        assert "content" in d
        assert "metadata" in d
        assert "created_at" in d

    def test_is_expired_property(self, mem) -> None:
        # TTL=0 means never expires
        eid = mem.store("never expires", source="test", ttl=0)
        results = mem.query("never expires", top_k=1)
        assert results[0].entry.is_expired is False

        # TTL=1 second
        mem.store("will expire", source="test", ttl=1)
        time.sleep(1.5)
        results = mem.query("will expire", top_k=5)
        assert len(results) == 0
