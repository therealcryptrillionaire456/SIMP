"""
Controlled connector registry for BRP.

This module does not perform any outbound I/O. It only describes the bounded
connector surface BRP is allowed to reason about and produces operator-safe
assessments for records that appear to touch external systems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class ConnectorPolicy:
    connector_id: str
    domains: Sequence[str]
    methods: Sequence[str]
    read_only: bool
    quota_per_hour: int
    purpose: str


class ControlledConnectorRegistry:
    """Allowlisted connector posture for BRP."""

    _DEFAULT_POLICIES: Sequence[ConnectorPolicy] = (
        ConnectorPolicy(
            connector_id="dashboard_api",
            domains=("127.0.0.1", "localhost"),
            methods=("GET",),
            read_only=True,
            quota_per_hour=2400,
            purpose="Read-only operator telemetry",
        ),
        ConnectorPolicy(
            connector_id="simp_broker",
            domains=("127.0.0.1", "localhost"),
            methods=("GET", "POST"),
            read_only=False,
            quota_per_hour=1200,
            purpose="Bounded SIMP intent routing",
        ),
        ConnectorPolicy(
            connector_id="projectx_guard",
            domains=("127.0.0.1", "localhost"),
            methods=("GET", "POST"),
            read_only=False,
            quota_per_hour=600,
            purpose="Bounded ProjectX playbook dispatch",
        ),
        ConnectorPolicy(
            connector_id="telegram_alerts",
            domains=("api.telegram.org",),
            methods=("POST",),
            read_only=False,
            quota_per_hour=120,
            purpose="Operator alert delivery only",
        ),
        ConnectorPolicy(
            connector_id="ibm_quantum_advisory",
            domains=("quantum-computing.ibm.com", "api.quantum.ibm.com"),
            methods=("GET",),
            read_only=True,
            quota_per_hour=120,
            purpose="Quantum advisory posture lookup only",
        ),
    )

    _CONNECTOR_MARKERS = {
        "dashboard": "dashboard_api",
        "broker": "simp_broker",
        "projectx": "projectx_guard",
        "telegram": "telegram_alerts",
        "ibm": "ibm_quantum_advisory",
        "quantum": "ibm_quantum_advisory",
        "http://127.0.0.1": "simp_broker",
        "http://localhost": "simp_broker",
    }

    def __init__(self, policies: Sequence[ConnectorPolicy] | None = None) -> None:
        self._policies = {policy.connector_id: policy for policy in (policies or self._DEFAULT_POLICIES)}

    def build_summary(self) -> Dict[str, Any]:
        connectors = sorted(self._policies.values(), key=lambda item: item.connector_id)
        return {
            "mode": "allowlisted_only",
            "connector_count": len(connectors),
            "read_only_connectors": sum(1 for item in connectors if item.read_only),
            "write_scoped_connectors": sum(1 for item in connectors if not item.read_only),
            "connectors": [
                {
                    "connector_id": item.connector_id,
                    "domains": list(item.domains),
                    "methods": list(item.methods),
                    "read_only": item.read_only,
                    "quota_per_hour": item.quota_per_hour,
                    "purpose": item.purpose,
                }
                for item in connectors
            ],
        }

    def assess(self, record: Dict[str, Any]) -> Dict[str, Any]:
        tokens = self._flatten_record(record)
        matched_connector_ids = self._matched_connectors(tokens)
        connector_policies = [self._policy_dict(self._policies[connector_id]) for connector_id in matched_connector_ids]
        mentioned_domains = self._extract_domains(tokens)
        allowed_domains = {
            str(domain).lower()
            for policy in connector_policies
            for domain in policy.get("domains", [])
        }
        unknown_domains = [
            domain
            for domain in mentioned_domains
            if domain not in allowed_domains
        ]
        mentions_external = bool(mentioned_domains)
        requires_review = bool(unknown_domains) or (mentions_external and not connector_policies)

        guardrails = [
            "allowlisted connectors only",
            "audit every outbound request",
            "reject arbitrary code fetch and execution",
        ]
        if connector_policies:
            guardrails.append("bound each connector by method and quota")
        if requires_review:
            guardrails.append("manual review required for unknown external endpoints")

        score_boost = 0.0
        threat_tags: List[str] = []
        if connector_policies:
            threat_tags.append("controlled_connector")
            if any(not policy["read_only"] for policy in connector_policies):
                score_boost += 0.02
                threat_tags.append("connector_write_scope")
        if requires_review:
            score_boost += 0.05
            threat_tags.append("unapproved_external_endpoint")

        return {
            "enabled": True,
            "connector_ids": matched_connector_ids,
            "connector_policies": connector_policies,
            "mentioned_domains": mentioned_domains,
            "unknown_domains": unknown_domains,
            "requires_review": requires_review,
            "guardrails": guardrails,
            "score_boost": round(min(score_boost, 0.08), 4),
            "threat_tags": threat_tags,
        }

    def _matched_connectors(self, tokens: Iterable[str]) -> List[str]:
        matches: List[str] = []
        for token in tokens:
            for marker, connector_id in self._CONNECTOR_MARKERS.items():
                if marker in token and connector_id in self._policies and connector_id not in matches:
                    matches.append(connector_id)
        return matches

    @staticmethod
    def _flatten_record(record: Dict[str, Any]) -> List[str]:
        chunks: List[str] = []
        for key in ("source_agent", "event_type", "action"):
            value = record.get(key)
            if value:
                chunks.append(str(value).lower())
        for key in ("context", "params", "metadata", "tags"):
            value = record.get(key)
            if value:
                chunks.append(str(value).lower())
        return chunks

    @staticmethod
    def _extract_domains(tokens: Iterable[str]) -> List[str]:
        domains: List[str] = []
        seen = set()
        for token in tokens:
            for match in re.findall(r"https?://([^/'\"\\\s]+)", token):
                domain = str(match).strip().lower()
                if domain and domain not in seen:
                    seen.add(domain)
                    domains.append(domain)
        return domains

    @staticmethod
    def _policy_dict(policy: ConnectorPolicy) -> Dict[str, Any]:
        return {
            "connector_id": policy.connector_id,
            "domains": list(policy.domains),
            "methods": list(policy.methods),
            "read_only": policy.read_only,
            "quota_per_hour": policy.quota_per_hour,
            "purpose": policy.purpose,
        }
