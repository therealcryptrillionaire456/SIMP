"""
Predictive safety helpers for BRP.

The runtime BRP bridge is intentionally simple and deterministic. This module
adds a bounded predictive layer that can:

1. Raise concern on repeated suspicious signals within a recent window.
2. Learn lightweight defensive rules from negative observations.
3. Surface cross-domain and ProjectX-sensitive activity as metadata.

The goal is defensive early warning, not autonomous remediation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


class PredictiveSafetyIntelligence:
    """Stateless predictive analysis and bounded rule evolution."""

    WINDOW_HOURS = 48
    _NEGATIVE_OUTCOMES = {
        "failure",
        "failed",
        "blocked",
        "deny",
        "denied",
        "rollback",
        "rolled_back",
        "timeout",
        "timed_out",
        "error",
        "partial",
        "anomaly",
        "escalated",
        "elevated",
    }
    _KEYWORD_GROUPS = {
        "zero_day_signal": {
            "weight": 0.22,
            "terms": {
                "fuzz",
                "probe",
                "payload",
                "overflow",
                "header",
                "deserialize",
                "exploit",
                "inject",
                "sandbox",
                "memory corruption",
            },
        },
        "autonomous_signal": {
            "weight": 0.18,
            "terms": {
                "autonomous",
                "multi-step",
                "multi_step",
                "chain",
                "delegate_loop",
                "self_modify",
                "self-update",
                "escalation",
            },
        },
        "evasion_signal": {
            "weight": 0.15,
            "terms": {
                "bypass",
                "unsigned",
                "hidden",
                "obfuscated",
                "stealth",
                "covert",
            },
        },
    }
    _DOMAIN_MARKERS = {
        "network": {"network", "socket", "header", "proxy", "dns", "http", "mesh"},
        "filesystem": {"file", "filesystem", "path", "directory", "artifact"},
        "financial": {"trade", "order", "withdrawal", "fund", "position", "wallet"},
        "auth": {"auth", "credential", "token", "permission", "identity"},
        "system": {"shell", "process", "service", "projectx", "computer_use"},
        "code": {"code", "patch", "deploy", "runtime", "build"},
    }

    def evaluate(
        self,
        record: Dict[str, Any],
        *,
        recent_events: Optional[Sequence[Dict[str, Any]]] = None,
        recent_observations: Optional[Sequence[Dict[str, Any]]] = None,
        adaptive_rules: Optional[Dict[str, Dict[str, Any]]] = None,
        sensitive_action_tier: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return predictive metadata and a bounded threat boost."""
        recent_events = recent_events or []
        recent_observations = recent_observations or []
        adaptive_rules = adaptive_rules or {}

        serialised = self._normalise_text(record)
        source_agent = str(
            record.get("source_agent")
            or record.get("agent_id")
            or record.get("source_ip")
            or ""
        ).strip()
        action = str(record.get("action") or record.get("event_type") or "").strip().lower()
        tags = {str(tag).strip().lower() for tag in record.get("tags", []) if str(tag).strip()}

        score_boost = 0.0
        threat_tags: List[str] = []
        evidence: List[str] = []
        matched_keywords: Dict[str, List[str]] = {}

        for label, config in self._KEYWORD_GROUPS.items():
            hits = sorted(term for term in config["terms"] if term in serialised)
            if not hits:
                continue
            matched_keywords[label] = hits
            score_boost += config["weight"]
            threat_tags.append(label)
            evidence.append(f"{label} matched: {', '.join(hits[:3])}")

        domains = self._detect_domains(serialised)
        if len(domains) >= 2 and matched_keywords:
            score_boost += 0.12
            threat_tags.append("cross_domain_signal")
            evidence.append(f"cross-domain coupling: {', '.join(sorted(domains))}")

        if sensitive_action_tier is not None and sensitive_action_tier >= 2:
            tier_boost = 0.12 if sensitive_action_tier == 2 else 0.2
            score_boost += tier_boost
            threat_tags.append("projectx_sensitive_action")
            evidence.append(f"ProjectX-sensitive action tier {sensitive_action_tier}")

        repeated_signal_count = self._count_related_events(
            recent_events,
            source_agent=source_agent,
            action=action,
            tags=tags,
        )
        if repeated_signal_count >= 2:
            repeated_boost = min(0.06 * min(repeated_signal_count, 4), 0.18)
            score_boost += repeated_boost
            threat_tags.append("repeat_signal_cluster")
            evidence.append(f"{repeated_signal_count} related events in {self.WINDOW_HOURS}h window")

        near_miss_count = self._count_related_negative_observations(
            recent_observations,
            source_agent=source_agent,
            action=action,
            tags=tags,
        )
        if near_miss_count:
            near_miss_boost = min(0.1 + (0.05 * max(0, near_miss_count - 1)), 0.25)
            score_boost += near_miss_boost
            threat_tags.append("near_miss_cluster")
            evidence.append(f"{near_miss_count} negative observations in {self.WINDOW_HOURS}h window")

        matched_rules = []
        for rule in adaptive_rules.values():
            if not rule.get("active", True):
                continue
            if self._rule_matches(rule, action=action, tags=tags):
                matched_rules.append(rule["key"])
                score_boost += float(rule.get("boost", 0.0))
        if matched_rules:
            threat_tags.append("adaptive_rule_match")
            evidence.append(f"adaptive rules: {', '.join(matched_rules[:3])}")

        score_boost = min(score_boost, 0.65)
        threat_level = self._predictive_threat_level(score_boost)
        confidence = 0.0 if score_boost == 0.0 else min(0.98, 0.55 + score_boost)

        return {
            "score_boost": round(score_boost, 4),
            "confidence": round(confidence, 4),
            "threat_level": threat_level,
            "threat_tags": self._dedupe(threat_tags),
            "evidence": evidence,
            "domains": sorted(domains),
            "matched_keywords": matched_keywords,
            "repeated_signal_count": repeated_signal_count,
            "near_miss_count": near_miss_count,
            "adaptive_rule_matches": matched_rules,
            "window_hours": self.WINDOW_HOURS,
        }

    def derive_rules_from_observation(self, observation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Derive bounded defensive rules from a negative outcome."""
        outcome = str(observation.get("outcome", "")).strip().lower()
        if outcome not in self._NEGATIVE_OUTCOMES:
            return []

        action = str(observation.get("action", "")).strip().lower()
        tags = [
            str(tag).strip().lower()
            for tag in observation.get("tags", [])
            if str(tag).strip()
        ]
        severity = "high" if outcome in {"blocked", "deny", "denied", "rollback", "escalated"} else "medium"

        rules = []
        if action:
            rules.append(
                {
                    "key": f"action:{action}",
                    "name": f"action:{action}",
                    "match": {"action": action},
                    "severity": severity,
                }
            )
        for tag in tags[:3]:
            if tag in {"shadow", "advisory", "enforced"}:
                continue
            rules.append(
                {
                    "key": f"tag:{tag}",
                    "name": f"tag:{tag}",
                    "match": {"tag": tag},
                    "severity": "medium",
                }
            )
        return rules

    def rule_boost_for_count(self, count: int, severity: str) -> float:
        base = 0.05 if severity == "medium" else 0.08
        return round(min(base + (0.03 * min(count, 4)), 0.2), 4)

    @classmethod
    def is_negative_outcome(cls, outcome: str) -> bool:
        return str(outcome).strip().lower() in cls._NEGATIVE_OUTCOMES

    def synthetic_patterns(self, predictive: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Expose predictive results in the mesh gateway's pattern format."""
        patterns = []
        confidence = float(predictive.get("confidence", 0.0))
        for tag in predictive.get("threat_tags", []):
            patterns.append(
                {
                    "type": tag,
                    "confidence": confidence,
                    "description": f"Predictive BRP signal: {tag}",
                }
            )
        return patterns

    def _count_related_events(
        self,
        events: Sequence[Dict[str, Any]],
        *,
        source_agent: str,
        action: str,
        tags: Set[str],
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.WINDOW_HOURS)
        matches = 0
        for event in events:
            ts = self._parse_timestamp(event.get("timestamp") or event.get("ts"))
            if ts is None or ts < cutoff:
                continue
            event_source = str(
                event.get("source_agent")
                or event.get("agent_id")
                or event.get("source_ip")
                or ""
            ).strip()
            event_action = str(event.get("action") or event.get("event_type") or "").strip().lower()
            event_tags = {
                str(tag).strip().lower()
                for tag in event.get("tags", [])
                if str(tag).strip()
            }
            if source_agent and event_source and source_agent == event_source:
                matches += 1
                continue
            if action and event_action and action == event_action:
                matches += 1
                continue
            if tags and event_tags and tags.intersection(event_tags):
                matches += 1
        return matches

    def _count_related_negative_observations(
        self,
        observations: Sequence[Dict[str, Any]],
        *,
        source_agent: str,
        action: str,
        tags: Set[str],
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.WINDOW_HOURS)
        matches = 0
        for observation in observations:
            outcome = observation.get("outcome", "")
            if not self.is_negative_outcome(outcome):
                continue
            ts = self._parse_timestamp(observation.get("timestamp") or observation.get("ts"))
            if ts is None or ts < cutoff:
                continue
            obs_source = str(observation.get("source_agent", "")).strip()
            obs_action = str(observation.get("action", "")).strip().lower()
            obs_tags = {
                str(tag).strip().lower()
                for tag in observation.get("tags", [])
                if str(tag).strip()
            }
            if source_agent and obs_source and source_agent == obs_source:
                matches += 1
                continue
            if action and obs_action and action == obs_action:
                matches += 1
                continue
            if tags and obs_tags and tags.intersection(obs_tags):
                matches += 1
        return matches

    @staticmethod
    def _rule_matches(rule: Dict[str, Any], *, action: str, tags: Set[str]) -> bool:
        match = rule.get("match", {})
        action_match = str(match.get("action", "")).strip().lower()
        tag_match = str(match.get("tag", "")).strip().lower()
        if action_match and action_match == action:
            return True
        if tag_match and tag_match in tags:
            return True
        return False

    @staticmethod
    def _predictive_threat_level(score_boost: float) -> str:
        if score_boost >= 0.45:
            return "high"
        if score_boost >= 0.22:
            return "medium"
        if score_boost > 0.0:
            return "low"
        return "clean"

    @classmethod
    def _detect_domains(cls, text: str) -> Set[str]:
        domains = set()
        for domain, markers in cls._DOMAIN_MARKERS.items():
            if any(marker in text for marker in markers):
                domains.add(domain)
        return domains

    @staticmethod
    def _normalise_text(record: Dict[str, Any]) -> str:
        try:
            return json.dumps(record, sort_keys=True, default=str).lower()
        except TypeError:
            return str(record).lower()

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        ordered = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered
