from __future__ import annotations

from simp.projectx.knowledge_distiller import DistilledFragment, KnowledgeDistiller
from simp.projectx.rag_memory import MemoryEntry, RetrievalResult


def test_collect_rag_uses_retrieval_result_contract(monkeypatch) -> None:
    class FakeMemory:
        def query(self, text, top_k=8):
            return [
                RetrievalResult(
                    entry=MemoryEntry(
                        id="abc123",
                        content="ProjectX learned a durable retrieval pattern from benchmark feedback.",
                        metadata={"tags": ["lesson", "benchmark"]},
                        source="test",
                    ),
                    similarity=0.87,
                )
            ]

    monkeypatch.setattr(
        "simp.projectx.rag_memory.get_rag_memory",
        lambda: FakeMemory(),
    )

    distiller = KnowledgeDistiller()
    fragments = distiller._collect_rag(top_n=5)

    assert len(fragments) == 1
    assert fragments[0].signal_score == 0.87
    assert fragments[0].tags == ["lesson", "benchmark"]


def test_inject_into_rag_stores_tags_in_metadata(monkeypatch) -> None:
    calls = []

    class FakeMemory:
        def store(self, content, source="", metadata=None, ttl=None, entry_id=None):
            calls.append(
                {
                    "content": content,
                    "source": source,
                    "metadata": metadata,
                    "ttl": ttl,
                    "entry_id": entry_id,
                }
            )
            return "stored"

    monkeypatch.setattr(
        "simp.projectx.rag_memory.get_rag_memory",
        lambda: FakeMemory(),
    )

    distiller = KnowledgeDistiller()
    count = distiller.inject_into_rag(
        [
            DistilledFragment(
                source="lesson",
                content="Use benchmark deltas before promoting policy changes.",
                signal_score=0.91,
                tags=["policy", "benchmark"],
            )
        ]
    )

    assert count == 1
    assert calls[0]["source"] == "distilled:lesson"
    assert calls[0]["metadata"]["tags"] == ["policy", "benchmark"]
