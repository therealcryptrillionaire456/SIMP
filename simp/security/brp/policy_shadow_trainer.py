"""
Shadow policy trainer for BRP.

This module generates candidate rules from audited outcomes in shadow mode.
Candidates are advisory only and never self-promote into live enforcement.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List


class PolicyShadowTrainer:
    """Builds shadow-mode candidate rules from BRP history."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    def build_summary(self, *, limit: int = 10) -> Dict[str, Any]:
        candidates = self.generate_candidates(limit=limit)
        promotable = [item for item in candidates if item["recommendation"] == "review_for_promotion"]
        return {
            "mode": "shadow_only",
            "candidate_count": len(candidates),
            "reviewable_count": len(promotable),
            "top_candidates": candidates[:limit],
        }

    def assess(self, record: Dict[str, Any], *, threat_score: float, threat_tags: List[str]) -> Dict[str, Any]:
        action = str(record.get("action") or "").strip().lower()
        candidates = self.generate_candidates(limit=25)
        matches = [
            item for item in candidates
            if item.get("action") == action or set(item.get("threat_tags", [])).intersection({str(tag).lower() for tag in threat_tags})
        ]

        score_boost = 0.0
        tags: List[str] = []
        if matches:
            score_boost += min(0.03, 0.01 * len(matches))
            tags.append("shadow_policy_candidate_match")
        if threat_score >= 0.7 and matches:
            score_boost += 0.01
            tags.append("shadow_policy_high_risk_review")

        return {
            "enabled": True,
            "mode": "shadow_only",
            "matched_candidates": matches[:5],
            "review_required": bool(matches),
            "score_boost": round(min(score_boost, 0.05), 4),
            "threat_tags": tags,
        }

    def generate_candidates(self, *, limit: int = 10) -> List[Dict[str, Any]]:
        responses = self._load_jsonl_tail(self.data_dir / "responses.jsonl", limit=400)
        observations = self._load_jsonl_tail(self.data_dir / "observations.jsonl", limit=400)
        outcomes_by_event = {
            str(item.get("event_id") or ""): str(item.get("outcome") or "").lower()
            for item in observations
            if item.get("event_id")
        }

        grouped: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "action": "",
                "samples": 0,
                "elevated": 0,
                "negative_outcomes": 0,
                "threat_sum": 0.0,
                "threat_tags": set(),
            }
        )
        for response in responses:
            event_id = str(response.get("event_id") or "")
            metadata = response.get("metadata") if isinstance(response.get("metadata"), dict) else {}
            action = self._extract_action(metadata) or "unknown"
            key = f"action:{action}"
            bucket = grouped[key]
            bucket["action"] = action
            bucket["samples"] += 1
            bucket["threat_sum"] += float(response.get("threat_score") or 0.0)
            bucket["threat_tags"].update(str(tag).lower() for tag in response.get("threat_tags", []) or [])
            if str(response.get("decision") or "").upper() in {"ELEVATE", "DENY"}:
                bucket["elevated"] += 1
            if outcomes_by_event.get(event_id) in {"error", "failed", "denied", "blocked", "partial"}:
                bucket["negative_outcomes"] += 1

        candidates: List[Dict[str, Any]] = []
        for key, bucket in grouped.items():
            if bucket["samples"] < 2:
                continue
            positive_evidence = bucket["elevated"] + bucket["negative_outcomes"]
            posterior = round((positive_evidence + 1) / (bucket["samples"] + 2), 4)
            recommendation = "review_for_promotion" if posterior >= 0.6 and bucket["samples"] >= 3 else "keep_shadow"
            candidates.append(
                {
                    "candidate_id": f"shadow::{key}",
                    "action": bucket["action"],
                    "support_count": bucket["samples"],
                    "average_threat_score": round(bucket["threat_sum"] / max(bucket["samples"], 1), 4),
                    "posterior_risk": posterior,
                    "negative_outcomes": bucket["negative_outcomes"],
                    "elevated_decisions": bucket["elevated"],
                    "threat_tags": sorted(bucket["threat_tags"])[:6],
                    "recommendation": recommendation,
                    "mode": "shadow_only",
                }
            )
        candidates.sort(
            key=lambda item: (
                -float(item.get("posterior_risk") or 0.0),
                -int(item.get("support_count") or 0),
                str(item.get("action") or ""),
            )
        )
        return candidates[: max(1, min(limit, 50))]

    @staticmethod
    def _extract_action(metadata: Dict[str, Any]) -> str:
        predictive_steps = metadata.get("predictive_steps") if isinstance(metadata.get("predictive_steps"), list) else []
        multimodal_steps = metadata.get("multimodal_steps") if isinstance(metadata.get("multimodal_steps"), list) else []
        for item in predictive_steps + multimodal_steps:
            action = str((item or {}).get("action") or "").strip().lower()
            if action:
                return action
        return ""

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

