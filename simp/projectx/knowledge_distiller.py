"""
ProjectX Knowledge Distiller — Step 6

Distills RAG + KnowledgeIndex + SystemMemory into compact, deduplicated,
high-signal knowledge fragments that feed future APO and subsystem prompts.

Pipeline:
  1. Drain RAG memory (top-N by recency and access count)
  2. Pull top Lessons from SystemMemoryStore
  3. Cross-reference: cluster related fragments
  4. Deduplicate by content-hash and cosine similarity
  5. Score by signal strength (lesson confidence × access frequency)
  6. Emit DistilledFragment list + persist snapshot

The distiller is non-destructive: it only reads, never deletes source stores.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DISTILL_DIR = Path("projectx_logs/knowledge")
_SIM_THRESHOLD = 0.72   # cosine similarity above which fragments are "duplicates"
_MAX_FRAGMENTS = 500
_MAX_WORD_VEC_TOKENS = 5_000   # cap token count fed to cosine similarity
_DEDUP_TIME_BUDGET_S = 5.0     # max wall-clock for similarity dedup pass
_MAX_SNAPSHOTS = 10            # rotate old snapshots to prevent disk accumulation


@dataclass
class DistilledFragment:
    """A compact, high-signal knowledge unit."""
    fragment_id:    str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    source:         str = ""        # "rag" | "lesson" | "policy" | "merged"
    content:        str = ""
    signal_score:   float = 0.5    # 0–1 (higher = more valuable)
    tags:           List[str] = field(default_factory=list)
    created_at:     float = field(default_factory=time.time)
    content_hash:   str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fragment_id": self.fragment_id,
            "source": self.source,
            "content": self.content[:1000],
            "signal_score": round(self.signal_score, 4),
            "tags": self.tags,
            "content_hash": self.content_hash,
        }


@dataclass
class DistillationReport:
    run_id:         str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp:      float = field(default_factory=time.time)
    fragments_in:   int = 0
    fragments_out:  int = 0
    duplicates_dropped: int = 0
    low_signal_dropped: int = 0
    elapsed_ms:     int = 0
    fragments:      List[DistilledFragment] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "fragments_in": self.fragments_in,
            "fragments_out": self.fragments_out,
            "duplicates_dropped": self.duplicates_dropped,
            "low_signal_dropped": self.low_signal_dropped,
            "elapsed_ms": self.elapsed_ms,
        }


def _word_vec(text: str) -> Dict[str, int]:
    # Operate on a bounded prefix to prevent regex over huge strings
    words = re.findall(r"\b\w{3,}\b", text[:50_000].lower())
    vec: Dict[str, int] = {}
    for w in words[:_MAX_WORD_VEC_TOKENS]:
        vec[w] = vec.get(w, 0) + 1
    return vec


def _cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[w] * b[w] for w in common)
    mag_a = sum(v * v for v in a.values()) ** 0.5
    mag_b = sum(v * v for v in b.values()) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class KnowledgeDistiller:
    """
    Distills RAG, SystemMemory, and policy candidates into compact fragments.

    Usage::

        distiller = KnowledgeDistiller()
        report = distiller.run(top_n=200, min_signal=0.3)
        print(f"{report.fragments_out} fragments distilled")
    """

    def __init__(
        self,
        store_dir: str = str(_DISTILL_DIR),
        sim_threshold: float = _SIM_THRESHOLD,
        max_fragments: int = _MAX_FRAGMENTS,
    ) -> None:
        self._store = Path(store_dir)
        self._store.mkdir(parents=True, exist_ok=True)
        self._sim_threshold = sim_threshold
        self._max_fragments = max_fragments

    # ── Public API ────────────────────────────────────────────────────────

    def run(self, top_n: int = 200, min_signal: float = 0.25) -> DistillationReport:
        # Clamp params to safe ranges
        top_n = max(1, min(top_n, 2000))
        min_signal = max(0.0, min(min_signal, 1.0))

        t0 = time.time()
        report = DistillationReport()

        raw: List[DistilledFragment] = []
        raw += self._collect_rag(top_n)
        raw += self._collect_lessons(top_n)
        raw += self._collect_policies(max(1, top_n // 4))
        report.fragments_in = len(raw)

        # Deduplicate by hash
        seen_hashes: set = set()
        unique: List[DistilledFragment] = []
        for f in raw:
            if f.content_hash in seen_hashes:
                report.duplicates_dropped += 1
            else:
                seen_hashes.add(f.content_hash)
                unique.append(f)

        # Deduplicate by similarity (O(n²) bounded by wall-clock budget)
        kept: List[DistilledFragment] = []
        kept_vecs: List[Dict[str, int]] = []
        dedup_deadline = time.time() + _DEDUP_TIME_BUDGET_S
        for f in sorted(unique, key=lambda x: x.signal_score, reverse=True):
            if time.time() > dedup_deadline:
                # Budget exhausted — keep remainder without similarity check
                kept.append(f)
                continue
            vec = _word_vec(f.content)
            is_dup = any(_cosine(vec, kv) >= self._sim_threshold for kv in kept_vecs)
            if is_dup:
                report.duplicates_dropped += 1
            else:
                kept.append(f)
                kept_vecs.append(vec)

        # Filter by signal
        final: List[DistilledFragment] = []
        for f in kept:
            if f.signal_score < min_signal:
                report.low_signal_dropped += 1
            else:
                final.append(f)

        # Truncate to max
        final = final[: self._max_fragments]
        report.fragments_out = len(final)
        report.fragments = final
        report.elapsed_ms = int((time.time() - t0) * 1000)

        self._persist(report)
        logger.info(
            "Distillation %s: %d → %d fragments (%d dups, %d low-signal) in %dms",
            report.run_id,
            report.fragments_in,
            report.fragments_out,
            report.duplicates_dropped,
            report.low_signal_dropped,
            report.elapsed_ms,
        )
        return report

    def get_top(self, n: int = 20, tag: Optional[str] = None) -> List[DistilledFragment]:
        """Load and return top-n fragments from the latest snapshot."""
        latest = self._latest_snapshot()
        if not latest:
            return []
        try:
            data = json.loads(latest.read_text())
            frags = [DistilledFragment(**f) for f in data.get("fragments", [])]
            if tag:
                frags = [f for f in frags if tag in f.tags]
            return sorted(frags, key=lambda f: f.signal_score, reverse=True)[:n]
        except Exception as exc:
            logger.warning("get_top failed: %s", exc)
            return []

    def inject_into_rag(self, fragments: Optional[List[DistilledFragment]] = None) -> int:
        """Store distilled fragments back into RAG memory for retrieval."""
        if fragments is None:
            fragments = self.get_top(50)
        # Cap injection batch to prevent memory exhaustion
        fragments = fragments[:200]
        try:
            from simp.projectx.rag_memory import get_rag_memory
            mem = get_rag_memory()
            for f in fragments:
                mem.store(
                    content=f.content,
                    source=f"distilled:{f.source}",
                    metadata={"signal": f.signal_score, "tags": list(f.tags)},
                )
            return len(fragments)
        except Exception as exc:
            logger.warning("inject_into_rag failed: %s", exc)
            return 0

    # ── Collection ────────────────────────────────────────────────────────

    def _collect_rag(self, top_n: int) -> List[DistilledFragment]:
        fragments: List[DistilledFragment] = []
        try:
            from simp.projectx.rag_memory import get_rag_memory
            mem = get_rag_memory()
            results = mem.query("knowledge insight learning pattern", top_k=top_n)
            for r in results:
                score = float(getattr(r, "similarity", 0.5))
                entry = getattr(r, "entry", None)
                content = getattr(entry, "content", "")
                if len(content) < 20:
                    continue
                metadata = getattr(entry, "metadata", {}) or {}
                tags = metadata.get("tags", [])
                if not isinstance(tags, list):
                    tags = [str(tags)]
                fragments.append(DistilledFragment(
                    source="rag",
                    content=content[:2000],
                    signal_score=min(1.0, score),
                    tags=[str(tag) for tag in tags[:20]],
                ))
        except Exception as exc:
            logger.debug("RAG collection failed: %s", exc)
        return fragments

    def _collect_lessons(self, top_n: int) -> List[DistilledFragment]:
        fragments: List[DistilledFragment] = []
        try:
            from simp.memory.system_memory import SystemMemoryStore
            store = SystemMemoryStore()
            lessons = store.get_top_lessons(limit=top_n)
            for lesson in lessons:
                content = lesson.get("content", lesson.get("lesson", ""))
                if not content or len(content) < 10:
                    continue
                fragments.append(DistilledFragment(
                    source="lesson",
                    content=str(content)[:2000],
                    signal_score=float(lesson.get("confidence", 0.5)),
                    tags=["lesson", lesson.get("domain", "general")],
                ))
        except Exception as exc:
            logger.debug("Lesson collection failed: %s", exc)
        return fragments

    def _collect_policies(self, top_n: int) -> List[DistilledFragment]:
        fragments: List[DistilledFragment] = []
        try:
            from simp.memory.system_memory import SystemMemoryStore
            store = SystemMemoryStore()
            policies = store.get_policy_candidates(limit=top_n)
            for p in policies:
                content = p.get("description", p.get("policy", ""))
                if not content:
                    continue
                fragments.append(DistilledFragment(
                    source="policy",
                    content=str(content)[:2000],
                    signal_score=float(p.get("confidence", 0.4)),
                    tags=["policy"],
                ))
        except Exception as exc:
            logger.debug("Policy collection failed: %s", exc)
        return fragments

    # ── Persistence ───────────────────────────────────────────────────────

    def _persist(self, report: DistillationReport) -> None:
        snapshot = {
            **report.to_dict(),
            "fragments": [f.to_dict() for f in report.fragments],
        }
        path = self._store / f"snapshot_{report.run_id}.json"
        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.write_json(path, snapshot)
        except Exception as exc:
            logger.warning("Persist failed: %s", exc)
        # Rotate old snapshots to prevent unbounded disk growth
        self._rotate_snapshots()

    def _rotate_snapshots(self) -> None:
        try:
            snaps = sorted(
                self._store.glob("snapshot_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old in snaps[_MAX_SNAPSHOTS:]:
                old.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("Snapshot rotation failed: %s", exc)

    def _latest_snapshot(self) -> Optional[Path]:
        snaps = sorted(self._store.glob("snapshot_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return snaps[0] if snaps else None


# Module-level singleton
_distiller: Optional[KnowledgeDistiller] = None


def get_knowledge_distiller() -> KnowledgeDistiller:
    global _distiller
    if _distiller is None:
        _distiller = KnowledgeDistiller()
    return _distiller
