"""
Incident memory index for BRP.

Builds replay-safe temporal correlations from persisted BRP audit records. This
is retrieval over explicit audit logs, not hidden model memory.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


class IncidentMemoryIndex:
    """Operator-safe memory across time for BRP audit records."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    def build_summary(self, *, recent_limit: int = 200) -> Dict[str, Any]:
        events = self._load_jsonl_tail(self.data_dir / "events.jsonl", limit=recent_limit)
        observations = self._load_jsonl_tail(self.data_dir / "observations.jsonl", limit=recent_limit)
        remediations = self._load_jsonl_tail(self.data_dir / "remediations.jsonl", limit=recent_limit)
        response_count = self._count_jsonl(self.data_dir / "responses.jsonl")

        top_agents = Counter(str(item.get("source_agent") or "") for item in events if item.get("source_agent"))
        top_actions = Counter(str(item.get("action") or "") for item in events if item.get("action"))
        negative_observations = [
            item for item in observations
            if str(item.get("outcome") or "").lower() not in {"success", "executed", "completed", "ok"}
        ]

        return {
            "indexed_events": len(events),
            "indexed_observations": len(observations),
            "indexed_remediations": len(remediations),
            "response_count": response_count,
            "negative_observation_count": len(negative_observations),
            "top_agents": [{"source_agent": key, "count": value} for key, value in top_agents.most_common(5)],
            "top_actions": [{"action": key, "count": value} for key, value in top_actions.most_common(5)],
        }

    def assess(self, record: Dict[str, Any]) -> Dict[str, Any]:
        source_agent = str(record.get("source_agent") or "").strip()
        action = str(record.get("action") or "").strip()
        tags = {str(tag).strip().lower() for tag in record.get("tags", []) or [] if str(tag).strip()}

        recent_events = self._load_jsonl_tail(self.data_dir / "events.jsonl", limit=256)
        recent_observations = self._load_jsonl_tail(self.data_dir / "observations.jsonl", limit=256)
        recent_remediations = self._load_jsonl_tail(self.data_dir / "remediations.jsonl", limit=128)

        related_events = [
            item for item in recent_events
            if (source_agent and str(item.get("source_agent") or "") == source_agent)
            or (action and str(item.get("action") or "") == action)
            or tags.intersection({str(tag).lower() for tag in item.get("tags", []) or []})
        ]
        negative_observations = [
            item for item in recent_observations
            if str(item.get("event_id") or "") in {str(event.get("event_id") or "") for event in related_events}
            or str(item.get("action") or "") == action
        ]
        failed_remediations = [
            item for item in recent_remediations
            if str(item.get("action") or "") == action and str(item.get("status") or "").lower() == "failed"
        ]

        recurring_pattern = len(related_events) >= 3 or len(negative_observations) >= 2 or len(failed_remediations) >= 1
        score_boost = 0.0
        threat_tags: List[str] = []
        if len(related_events) >= 3:
            score_boost += 0.02
            threat_tags.append("incident_memory_recurrence")
        if len(negative_observations) >= 2:
            score_boost += 0.03
            threat_tags.append("incident_memory_negative_outcomes")
        if failed_remediations:
            score_boost += 0.03
            threat_tags.append("incident_memory_failed_remediation")

        return {
            "enabled": True,
            "related_event_count": len(related_events),
            "negative_observation_count": len(negative_observations),
            "failed_remediation_count": len(failed_remediations),
            "recurring_pattern": recurring_pattern,
            "recent_related_event_ids": [
                str(item.get("event_id") or "")
                for item in related_events[-5:]
                if item.get("event_id")
            ],
            "score_boost": round(min(score_boost, 0.1), 4),
            "threat_tags": threat_tags,
        }

    @staticmethod
    def _load_jsonl_tail(filepath: Path, *, limit: int) -> List[Dict[str, Any]]:
        if not filepath.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with open(filepath, "r", encoding="utf-8") as handle:
            for line in deque(handle, maxlen=max(1, limit)):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    @staticmethod
    def _count_jsonl(filepath: Path) -> int:
        if not filepath.exists():
            return 0
        count = 0
        with open(filepath, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count

