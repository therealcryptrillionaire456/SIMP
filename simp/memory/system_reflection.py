"""
System Reflection

Cross-system learning over trades, mesh traffic, orchestration, security events,
and registry churn. This is the first general-purpose reflection layer that
converts system activity into lessons and policy candidates.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.system_memory import Episode, Lesson, PolicyCandidate, SystemMemoryStore
from simp.memory.trade_learning import TradeLearningEngine, TradeLearningReport


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


@dataclass
class SystemLearningReport:
    trade_learning: Dict[str, Any]
    mesh_summary: Dict[str, Any]
    orchestration_summary: Dict[str, Any]
    security_summary: Dict[str, Any]
    registry_summary: Dict[str, Any]
    lessons: List[Dict[str, Any]]
    policy_candidates: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_learning": self.trade_learning,
            "mesh_summary": self.mesh_summary,
            "orchestration_summary": self.orchestration_summary,
            "security_summary": self.security_summary,
            "registry_summary": self.registry_summary,
            "lessons": self.lessons,
            "policy_candidates": self.policy_candidates,
        }


class SystemLearningEngine:
    """Aggregates cross-system evidence into reusable learning."""

    def __init__(
        self,
        *,
        trade_log_path: str = "logs/gate4_trades.jsonl",
        pnl_ledger_path: str = "data/phase4_pnl_ledger.jsonl",
        mesh_events_path: str = "data/mesh_events.jsonl",
        orchestration_log_path: str = "data/orchestration_log.jsonl",
        security_audit_path: str = "data/security_audit.jsonl",
        agent_registry_path: str = "data/agent_registry.jsonl",
        knowledge_index: Optional[KnowledgeIndex] = None,
    ):
        self.trade_engine = TradeLearningEngine(
            trade_log_path=trade_log_path,
            pnl_ledger_path=pnl_ledger_path,
            knowledge_index=knowledge_index,
        )
        self.mesh_events_path = Path(mesh_events_path)
        self.orchestration_log_path = Path(orchestration_log_path)
        self.security_audit_path = Path(security_audit_path)
        self.agent_registry_path = Path(agent_registry_path)
        self.knowledge_index = knowledge_index or KnowledgeIndex()

    def analyze(self) -> SystemLearningReport:
        trade_report = self.trade_engine.analyze().to_dict()
        mesh_events = _load_jsonl(self.mesh_events_path)
        orchestration_events = _load_jsonl(self.orchestration_log_path)
        security_events = _load_jsonl(self.security_audit_path)
        registry_events = _load_jsonl(self.agent_registry_path)

        mesh_summary = self._summarize_mesh(mesh_events)
        orchestration_summary = self._summarize_orchestration(orchestration_events)
        security_summary = self._summarize_security(security_events)
        registry_summary = self._summarize_registry(registry_events)

        lessons, policies = self._derive_lessons(
            trade_report=trade_report,
            mesh_summary=mesh_summary,
            orchestration_summary=orchestration_summary,
            security_summary=security_summary,
            registry_summary=registry_summary,
        )

        return SystemLearningReport(
            trade_learning=trade_report,
            mesh_summary=mesh_summary,
            orchestration_summary=orchestration_summary,
            security_summary=security_summary,
            registry_summary=registry_summary,
            lessons=lessons,
            policy_candidates=policies,
        )

    def persist(self, store: SystemMemoryStore) -> SystemLearningReport:
        trade_report = self.trade_engine.persist(store).to_dict()
        mesh_events = _load_jsonl(self.mesh_events_path)
        orchestration_events = _load_jsonl(self.orchestration_log_path)
        security_events = _load_jsonl(self.security_audit_path)
        registry_events = _load_jsonl(self.agent_registry_path)

        mesh_summary = self._summarize_mesh(mesh_events)
        orchestration_summary = self._summarize_orchestration(orchestration_events)
        security_summary = self._summarize_security(security_events)
        registry_summary = self._summarize_registry(registry_events)

        lessons, policies = self._derive_lessons(
            trade_report=trade_report,
            mesh_summary=mesh_summary,
            orchestration_summary=orchestration_summary,
            security_summary=security_summary,
            registry_summary=registry_summary,
        )

        summary_episodes = [
            Episode(
                episode_type="mesh_summary",
                source="mesh_events",
                entity="mesh_runtime",
                summary="Mesh delivery and drop summary",
                occurred_at=mesh_summary.get("latest_timestamp", ""),
                payload=mesh_summary,
                tags=["mesh", "summary"],
            ),
            Episode(
                episode_type="orchestration_summary",
                source="orchestration_log",
                entity="orchestrator",
                summary="Plan execution summary",
                occurred_at=orchestration_summary.get("latest_timestamp", ""),
                payload=orchestration_summary,
                tags=["orchestration", "summary"],
            ),
            Episode(
                episode_type="security_summary",
                source="security_audit",
                entity="security_runtime",
                summary="Security validation and audit summary",
                occurred_at=security_summary.get("latest_timestamp", ""),
                payload=security_summary,
                tags=["security", "summary"],
            ),
            Episode(
                episode_type="registry_summary",
                source="agent_registry",
                entity="agent_registry",
                summary="Agent registration and churn summary",
                occurred_at=registry_summary.get("latest_timestamp", ""),
                payload=registry_summary,
                tags=["registry", "summary"],
            ),
        ]
        for episode in summary_episodes:
            store.add_episode(episode)

        lesson_ids: List[str] = []
        for lesson_data in lessons:
            lesson = Lesson(
                title=lesson_data["title"],
                summary=lesson_data["summary"],
                lesson_type=lesson_data["lesson_type"],
                confidence=lesson_data["confidence"],
                evidence=lesson_data["evidence"],
            )
            lesson_id = store.upsert_lesson(lesson)
            lesson_ids.append(lesson_id)
            self.knowledge_index.add_entry("system_lessons", lesson_data)

        for policy_data in policies:
            candidate = PolicyCandidate(
                title=policy_data["title"],
                rationale=policy_data["rationale"],
                priority=policy_data["priority"],
                payload=policy_data["payload"],
                source_lesson_ids=lesson_ids,
            )
            store.upsert_policy_candidate(candidate)
            self.knowledge_index.add_entry("system_policy_candidates", policy_data)

        self.knowledge_index.update_topic(
            "system_reflection",
            {
                "code_locations": [
                    "simp/memory/system_reflection.py",
                    "scripts/learn_from_system.py",
                ],
                "decisions": [
                    "System learning now aggregates trades, mesh, orchestration, security, and registry churn.",
                ],
                "tags": [
                    "memory",
                    "reflection",
                    "mesh",
                    "revenue",
                    "autonomy",
                ],
            },
        )

        return SystemLearningReport(
            trade_learning=trade_report,
            mesh_summary=mesh_summary,
            orchestration_summary=orchestration_summary,
            security_summary=security_summary,
            registry_summary=registry_summary,
            lessons=lessons,
            policy_candidates=policies,
        )

    def _summarize_mesh(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        event_counts = Counter(event.get("event_type", "unknown") for event in events)
        error_counts = Counter(event.get("error_code", "none") for event in events if event.get("error_code"))
        total = len(events)
        dropped = event_counts.get("MESSAGE_DROPPED", 0)
        return {
            "total_events": total,
            "event_counts": dict(event_counts),
            "error_counts": dict(error_counts),
            "drop_rate": round((dropped / total), 4) if total else 0.0,
            "latest_timestamp": events[-1].get("timestamp", "") if events else "",
        }

    def _summarize_orchestration(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        event_counts = Counter(event.get("event_kind", "unknown") for event in events)
        plan_started = event_counts.get("plan_started", 0)
        plan_completed = event_counts.get("plan_completed", 0)
        return {
            "total_events": len(events),
            "event_counts": dict(event_counts),
            "plan_started": plan_started,
            "plan_completed": plan_completed,
            "completion_ratio": round((plan_completed / plan_started), 4) if plan_started else 0.0,
            "latest_timestamp": events[-1].get("timestamp", "") if events else "",
        }

    def _summarize_security(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        event_counts = Counter(event.get("event_type", "unknown") for event in events)
        severity_counts = Counter(event.get("severity", "unknown") for event in events)
        return {
            "total_events": len(events),
            "event_counts": dict(event_counts),
            "severity_counts": dict(severity_counts),
            "latest_timestamp": events[-1].get("timestamp", "") if events else "",
        }

    def _summarize_registry(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        event_counts = Counter(event.get("event", "unknown") for event in events)
        registered = event_counts.get("registered", 0)
        deregistered = event_counts.get("deregistered", 0)
        return {
            "total_events": len(events),
            "event_counts": dict(event_counts),
            "churn_ratio": round((deregistered / registered), 4) if registered else 0.0,
            "latest_timestamp": events[-1].get("timestamp", "") if events else "",
        }

    def _derive_lessons(
        self,
        *,
        trade_report: Dict[str, Any],
        mesh_summary: Dict[str, Any],
        orchestration_summary: Dict[str, Any],
        security_summary: Dict[str, Any],
        registry_summary: Dict[str, Any],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        lessons: List[Dict[str, Any]] = []
        policies: List[Dict[str, Any]] = []

        if mesh_summary["drop_rate"] > 0:
            lessons.append({
                "title": "Mesh friction is learnable operational signal, not just transport noise",
                "summary": (
                    "Dropped messages, TTL expiry, and no-subscriber events show where the "
                    "system's intended energy transfer is being lost. The mesh should treat "
                    "those failures as training data for routing and subscription hygiene."
                ),
                "lesson_type": "mesh_reliability",
                "confidence": 0.9,
                "evidence": mesh_summary,
            })
            policies.append({
                "title": "Daily mesh hygiene reflection",
                "rationale": (
                    "Summarize dropped-message causes and promote targeted routing/subscription "
                    "fixes instead of leaving delivery friction buried in logs."
                ),
                "priority": "high",
                "payload": {
                    "target": "mesh",
                    "action": "reflect_on_drop_causes",
                    "top_error_codes": mesh_summary["error_counts"],
                },
            })

        if registry_summary["churn_ratio"] > 0.2:
            lessons.append({
                "title": "Agent churn should be scored as system instability",
                "summary": (
                    "Repeated register-deregister cycles are not harmless bookkeeping. They are "
                    "evidence of unstable orchestration or supervision and should feed trust and "
                    "routing decisions."
                ),
                "lesson_type": "orchestration_stability",
                "confidence": 0.87,
                "evidence": registry_summary,
            })
            policies.append({
                "title": "Churn-aware routing and supervision review",
                "rationale": (
                    "Agents with elevated churn should be deprioritized or supervised more "
                    "tightly until stability recovers."
                ),
                "priority": "medium",
                "payload": {
                    "target": "agent_registry",
                    "action": "score_churn_into_trust",
                    "churn_ratio": registry_summary["churn_ratio"],
                },
            })

        if trade_report["successful_live_trades"] > 0 and orchestration_summary["plan_completed"] > 0:
            lessons.append({
                "title": "Revenue learning must join execution outcomes with orchestration intent",
                "summary": (
                    "To evolve recursively, the system has to connect why a plan was created, "
                    "what signals were emitted, and what economic outcome followed."
                ),
                "lesson_type": "closed_loop_learning",
                "confidence": 0.93,
                "evidence": {
                    "successful_live_trades": trade_report["successful_live_trades"],
                    "completed_plans": orchestration_summary["plan_completed"],
                },
            })
            policies.append({
                "title": "Plan-to-execution lineage capture",
                "rationale": (
                    "Attach plan IDs and intent lineage to downstream trades so successful and "
                    "failed strategies can be ranked by actual economic output."
                ),
                "priority": "high",
                "payload": {
                    "target": "broker_and_execution",
                    "action": "carry_plan_lineage",
                },
            })

        if security_summary["total_events"] > 0:
            lessons.append({
                "title": "Security and validation events belong in the learning loop",
                "summary": (
                    "Operational safety is part of system intelligence. Validation errors and "
                    "security events should shape prompts, routing, and execution gates."
                ),
                "lesson_type": "safety_learning",
                "confidence": 0.84,
                "evidence": security_summary,
            })

        return lessons, policies
