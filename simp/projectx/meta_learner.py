"""
ProjectX Meta-Learner — Phase 3 (Deep Integration)

Bridges ProjectX's evaluation history with SIMP's structured memory layer
(SystemMemoryStore / Episodes / Lessons / PolicyCandidates).

What it does each cycle:
  1. Reads APO eval history, orchestrator outcomes, and safety monitor metrics
  2. Clusters outcomes into episodes stored in SystemMemoryStore
  3. Promotes statistically significant patterns to Lessons
  4. Generates PolicyCandidates for top lessons (operator review)
  5. Syncs promoted lessons into RAGMemory for retrieval
  6. Emits a learning summary packet to the mesh

This implements the outer loop of the meta-learning architecture
(roadmap Phase 3: outer/inner learning + experience replay).
"""

from __future__ import annotations

import json
import logging
import statistics
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum samples before we promote a pattern to a Lesson
_MIN_SAMPLES_FOR_LESSON = 5
# Confidence threshold for promoting a Lesson to a PolicyCandidate
_POLICY_CONFIDENCE_THRESHOLD = 0.72
# How many cycles of history to keep in an episode before summarising
_EPISODE_WINDOW = 50


@dataclass
class LearningCycleReport:
    cycle_id: str
    timestamp: float
    episodes_recorded: int
    lessons_promoted: int
    policies_proposed: int
    rag_entries_added: int
    top_insight: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "episodes_recorded": self.episodes_recorded,
            "lessons_promoted": self.lessons_promoted,
            "policies_proposed": self.policies_proposed,
            "rag_entries_added": self.rag_entries_added,
            "top_insight": self.top_insight,
            "error": self.error,
        }


class MetaLearner:
    """
    Converts raw operational data into structured lessons and policies.

    Integrates with:
      - simp.memory.SystemMemoryStore  (Episodes, Lessons, PolicyCandidates)
      - simp.projectx.rag_memory       (RAGMemory for retrieval)
      - simp.projectx.safety_monitor   (SafetyMonitor for metrics)
      - simp.projectx.apo_engine       (APOEngine eval history)

    Usage::

        from simp.projectx.meta_learner import MetaLearner
        learner = MetaLearner()
        report = learner.run_cycle()
    """

    def __init__(
        self,
        db_path: str = "memory/system_memory.sqlite3",
        rag_memory=None,
        safety_monitor=None,
        apo_engine=None,
        trade_log_path: str = "data/phase4_pnl_ledger.jsonl",
        trade_reconstruction_path: str = "data/trade_reconstruction.jsonl",
    ) -> None:
        self._db_path = db_path
        self._rag = rag_memory
        self._safety = safety_monitor
        self._apo = apo_engine
        self._trade_log = Path(trade_log_path)
        self._trade_reconstruction = Path(trade_reconstruction_path)
        self._store = self._init_store()

    def _init_store(self):
        try:
            from simp.memory.system_memory import SystemMemoryStore
            return SystemMemoryStore(db_path=self._db_path)
        except Exception as exc:
            logger.warning("SystemMemoryStore unavailable (%s) — running in-memory only", exc)
            return None

    # ── Public API ────────────────────────────────────────────────────────

    def run_cycle(self) -> LearningCycleReport:
        """Execute one full meta-learning cycle."""
        cycle_id = uuid.uuid4().hex[:8]
        t0 = time.time()
        report = LearningCycleReport(
            cycle_id=cycle_id,
            timestamp=t0,
            episodes_recorded=0,
            lessons_promoted=0,
            policies_proposed=0,
            rag_entries_added=0,
        )

        try:
            # 1. Collect raw data streams
            apo_outcomes = self._collect_apo_outcomes()
            trade_outcomes = self._collect_trade_outcomes()
            safety_metrics = self._collect_safety_metrics()

            # 2. Record episodes
            ep_ids = []
            for outcome in apo_outcomes:
                eid = self._record_apo_episode(outcome)
                if eid:
                    ep_ids.append(eid)
            for outcome in trade_outcomes:
                eid = self._record_trade_episode(outcome)
                if eid:
                    ep_ids.append(eid)
            report.episodes_recorded = len(ep_ids)

            # 3. Extract and promote lessons
            lessons = self._extract_lessons(apo_outcomes, trade_outcomes, safety_metrics)
            promoted = self._promote_lessons(lessons, ep_ids)
            report.lessons_promoted = len(promoted)

            # 4. Generate policy candidates from high-confidence lessons
            policies = self._propose_policies(promoted)
            report.policies_proposed = len(policies)

            # 5. Sync to RAGMemory
            rag_count = self._sync_to_rag(promoted)
            report.rag_entries_added = rag_count

            # 6. Surface top insight
            if promoted:
                best = max(promoted, key=lambda l: l.get("confidence", 0))
                report.top_insight = best.get("summary", "")

        except Exception as exc:
            logger.error("MetaLearner cycle %s failed: %s", cycle_id, exc)
            report.error = str(exc)

        return report

    # ── Data collection ───────────────────────────────────────────────────

    def _collect_apo_outcomes(self) -> List[Dict[str, Any]]:
        if self._apo is None:
            return []
        try:
            candidates = self._apo.get_population()
            return [
                {
                    "candidate_id": c.candidate_id,
                    "mean_score": c.mean_score,
                    "variance": c.score_variance,
                    "generation": c.generation,
                    "scores": c.scores[-_EPISODE_WINDOW:],
                    "template_preview": c.template[:120],
                }
                for c in candidates
                if c.scores
            ]
        except Exception as exc:
            logger.debug("APO outcome collection failed: %s", exc)
            return []

    def _collect_trade_outcomes(self) -> List[Dict[str, Any]]:
        outcomes: List[Dict[str, Any]] = []
        for path in (self._trade_log, self._trade_reconstruction):
            if not path.exists():
                continue
            try:
                lines = path.read_text().splitlines()
                for line in lines[-200:]:  # last 200 entries
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        outcomes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            except Exception as exc:
                logger.debug("Trade log read failed (%s): %s", path, exc)
        return outcomes

    def _collect_safety_metrics(self) -> Dict[str, Any]:
        if self._safety is None:
            return {}
        try:
            return self._safety.get_summary()
        except Exception:
            return {}

    # ── Episode recording ─────────────────────────────────────────────────

    def _record_apo_episode(self, outcome: Dict) -> Optional[str]:
        if self._store is None:
            return None
        try:
            from simp.memory.system_memory import Episode
            episode = Episode(
                episode_type="apo_evaluation",
                source="projectx_apo_engine",
                entity=outcome.get("candidate_id", "unknown"),
                summary=(
                    f"APO candidate gen={outcome['generation']} "
                    f"score={outcome['mean_score']:.3f} "
                    f"variance={outcome['variance']:.4f}"
                ),
                occurred_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                payload=outcome,
                tags=["apo", "self_improvement", "projectx"],
            )
            self._store.add_episode(episode)
            return episode.episode_id
        except Exception as exc:
            logger.debug("APO episode record failed: %s", exc)
            return None

    def _record_trade_episode(self, outcome: Dict) -> Optional[str]:
        if self._store is None:
            return None
        try:
            from simp.memory.system_memory import Episode
            pnl = outcome.get("realized_pnl") or outcome.get("pnl") or outcome.get("profit_loss", 0)
            symbol = outcome.get("symbol") or outcome.get("asset", "unknown")
            episode = Episode(
                episode_type="trade_outcome",
                source="projectx_trade_learner",
                entity=symbol,
                summary=f"Trade {symbol} pnl={pnl}",
                occurred_at=outcome.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                payload={k: v for k, v in outcome.items() if k not in ("raw",)},
                tags=["trade", "pnl", "projectx"],
            )
            self._store.add_episode(episode)
            return episode.episode_id
        except Exception as exc:
            logger.debug("Trade episode record failed: %s", exc)
            return None

    # ── Lesson extraction ─────────────────────────────────────────────────

    def _extract_lessons(
        self,
        apo_outcomes: List[Dict],
        trade_outcomes: List[Dict],
        safety_metrics: Dict,
    ) -> List[Dict[str, Any]]:
        lessons: List[Dict[str, Any]] = []

        # APO: find best performing generation
        if len(apo_outcomes) >= _MIN_SAMPLES_FOR_LESSON:
            scores = [o["mean_score"] for o in apo_outcomes]
            best_score = max(scores)
            avg_score = statistics.mean(scores)
            improvement = best_score - avg_score
            confidence = min(1.0, improvement * 2 + 0.5)
            lessons.append({
                "title": "APO prompt evolution pattern",
                "summary": (
                    f"Best candidate score {best_score:.3f} vs average {avg_score:.3f}. "
                    f"Improvement margin {improvement:.3f}. "
                    f"Prefer generation {max(apo_outcomes, key=lambda x: x['mean_score'])['generation']}+ templates."
                ),
                "lesson_type": "prompt_optimization",
                "confidence": confidence,
                "evidence": {"scores": scores[:20], "best_score": best_score, "avg_score": avg_score},
            })

        # Trade: identify profitable symbol patterns
        if trade_outcomes:
            by_symbol: Dict[str, List[float]] = {}
            for t in trade_outcomes:
                sym = t.get("symbol") or t.get("asset", "unknown")
                pnl = float(t.get("realized_pnl") or t.get("pnl") or t.get("profit_loss") or 0)
                by_symbol.setdefault(sym, []).append(pnl)
            for sym, pnls in by_symbol.items():
                if len(pnls) < 3:
                    continue
                win_rate = sum(1 for p in pnls if p > 0) / len(pnls)
                avg_pnl = statistics.mean(pnls)
                if win_rate >= 0.6:
                    lessons.append({
                        "title": f"High win-rate pattern: {sym}",
                        "summary": (
                            f"{sym} shows {win_rate:.0%} win rate over {len(pnls)} trades, "
                            f"avg PnL {avg_pnl:+.4f}. Consider higher allocation."
                        ),
                        "lesson_type": "trade_pattern",
                        "confidence": min(0.9, win_rate),
                        "evidence": {"symbol": sym, "win_rate": win_rate, "avg_pnl": avg_pnl, "n": len(pnls)},
                    })
                elif win_rate < 0.35:
                    lessons.append({
                        "title": f"Low win-rate pattern: {sym}",
                        "summary": (
                            f"{sym} shows only {win_rate:.0%} win rate over {len(pnls)} trades. "
                            f"Review strategy or reduce allocation."
                        ),
                        "lesson_type": "trade_risk",
                        "confidence": min(0.85, (1 - win_rate)),
                        "evidence": {"symbol": sym, "win_rate": win_rate, "avg_pnl": avg_pnl, "n": len(pnls)},
                    })

        # Safety: latency regression detection
        avg_lat = (safety_metrics.get("metrics") or {}).get("avg_latency_ms")
        if avg_lat and avg_lat > 2000:
            lessons.append({
                "title": "Elevated inference latency detected",
                "summary": (
                    f"Average inference latency {avg_lat:.0f}ms exceeds 2000ms target. "
                    "Consider model quantization or parallel execution tuning."
                ),
                "lesson_type": "performance",
                "confidence": 0.8,
                "evidence": {"avg_latency_ms": avg_lat},
            })

        return lessons

    def _promote_lessons(
        self, lessons: List[Dict], episode_ids: List[str]
    ) -> List[Dict[str, Any]]:
        promoted: List[Dict[str, Any]] = []
        for lesson_data in lessons:
            if self._store is not None:
                try:
                    from simp.memory.system_memory import Lesson
                    lesson = Lesson(
                        title=lesson_data["title"],
                        summary=lesson_data["summary"],
                        lesson_type=lesson_data["lesson_type"],
                        confidence=lesson_data["confidence"],
                        evidence=lesson_data.get("evidence", {}),
                        source_episode_ids=episode_ids[:10],
                    )
                    self._store.add_lesson(lesson)
                    lesson_data["lesson_id"] = lesson.lesson_id
                except Exception as exc:
                    logger.debug("Lesson promotion failed: %s", exc)
            promoted.append(lesson_data)
        return promoted

    def _propose_policies(self, lessons: List[Dict]) -> List[Dict[str, Any]]:
        policies: List[Dict[str, Any]] = []
        for lesson in lessons:
            if lesson.get("confidence", 0) < _POLICY_CONFIDENCE_THRESHOLD:
                continue
            policy_data = {
                "title": f"Policy from: {lesson['title']}",
                "rationale": lesson["summary"],
                "priority": "medium" if lesson["confidence"] < 0.85 else "high",
                "payload": {"lesson_type": lesson["lesson_type"], "evidence": lesson.get("evidence", {})},
                "source_lesson_ids": [lesson.get("lesson_id", "")] if lesson.get("lesson_id") else [],
            }
            if self._store is not None:
                try:
                    from simp.memory.system_memory import PolicyCandidate
                    policy = PolicyCandidate(
                        title=policy_data["title"],
                        rationale=policy_data["rationale"],
                        priority=policy_data["priority"],
                        payload=policy_data["payload"],
                        source_lesson_ids=policy_data["source_lesson_ids"],
                    )
                    self._store.add_policy_candidate(policy)
                    policy_data["policy_id"] = policy.policy_id
                except Exception as exc:
                    logger.debug("Policy proposal failed: %s", exc)
            policies.append(policy_data)
        return policies

    # ── RAG sync ──────────────────────────────────────────────────────────

    def _sync_to_rag(self, lessons: List[Dict]) -> int:
        if self._rag is None:
            return 0
        count = 0
        for lesson in lessons:
            try:
                content = f"{lesson['title']}\n{lesson['summary']}"
                self._rag.store(
                    content,
                    source=f"meta_learner:{lesson['lesson_type']}",
                    metadata={"confidence": lesson.get("confidence", 0), "lesson_type": lesson["lesson_type"]},
                    ttl=14 * 24 * 3600,  # 14 days for lessons
                )
                count += 1
            except Exception as exc:
                logger.debug("RAG sync failed for lesson: %s", exc)
        return count
