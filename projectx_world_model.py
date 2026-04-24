"""ProjectX bounded world model / system twin.

Phase 8 scope:
  - JSONL-backed entity, relation, invariant, and scenario records
  - deterministic snapshotting and risk estimation
  - read-only twin queries plus append-only record updates

The module is intentionally conservative. It does not execute code, mutate
outside files, or apply repairs. It only records structured state and derives
bounded summaries from it.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from projectx_security import append_redacted_jsonl, utc_now_iso
from projectx_simp_config import get_projectx_runtime_dir


WORLD_MODEL_PHASE = 8
DEFAULT_WORLD_MODEL_DIR = get_projectx_runtime_dir() / "data" / "world_model"
DEFAULT_WORLD_MODEL_DIR.mkdir(parents=True, exist_ok=True)


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return max(0.0, min(1.0, parsed))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def _read_jsonl(path: Path, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    if limit is not None and limit >= 0:
        return rows[-limit:]
    return rows


def _now() -> str:
    return utc_now_iso()


@dataclass
class WorldEntity:
    entity_id: str = field(default_factory=lambda: f"entity-{uuid4().hex[:12]}")
    kind: str = "system"
    name: str = ""
    status: str = "active"
    criticality: float = 0.0
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_agent: str = "projectx_native"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["criticality"] = _clamp01(data.get("criticality"))
        data["confidence"] = _clamp01(data.get("confidence"), default=1.0)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldEntity":
        return cls(
            entity_id=str(data.get("entity_id") or f"entity-{uuid4().hex[:12]}"),
            kind=str(data.get("kind") or "system"),
            name=str(data.get("name") or ""),
            status=str(data.get("status") or "active"),
            criticality=_clamp01(data.get("criticality")),
            confidence=_clamp01(data.get("confidence"), default=1.0),
            tags=list(data.get("tags") or []),
            attributes=dict(data.get("attributes") or {}),
            source_agent=str(data.get("source_agent") or "projectx_native"),
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or _now()),
        )


@dataclass
class WorldRelation:
    relation_id: str = field(default_factory=lambda: f"relation-{uuid4().hex[:12]}")
    source_id: str = ""
    relation_type: str = "related_to"
    target_id: str = ""
    weight: float = 1.0
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    source_agent: str = "projectx_native"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["weight"] = _safe_float(data.get("weight"), 1.0)
        data["confidence"] = _clamp01(data.get("confidence"), default=1.0)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldRelation":
        return cls(
            relation_id=str(data.get("relation_id") or f"relation-{uuid4().hex[:12]}"),
            source_id=str(data.get("source_id") or ""),
            relation_type=str(data.get("relation_type") or "related_to"),
            target_id=str(data.get("target_id") or ""),
            weight=_safe_float(data.get("weight"), 1.0),
            confidence=_clamp01(data.get("confidence"), default=1.0),
            evidence=dict(data.get("evidence") or {}),
            source_agent=str(data.get("source_agent") or "projectx_native"),
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or _now()),
        )


@dataclass
class WorldInvariant:
    invariant_id: str = field(default_factory=lambda: f"invariant-{uuid4().hex[:12]}")
    name: str = ""
    scope: str = "system"
    condition: str = "entity_exists"
    target_id: str = ""
    subject_attribute: str = ""
    expected: Dict[str, Any] = field(default_factory=dict)
    severity: str = "medium"
    source_agent: str = "projectx_native"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldInvariant":
        return cls(
            invariant_id=str(data.get("invariant_id") or f"invariant-{uuid4().hex[:12]}"),
            name=str(data.get("name") or ""),
            scope=str(data.get("scope") or "system"),
            condition=str(data.get("condition") or "entity_exists"),
            target_id=str(data.get("target_id") or ""),
            subject_attribute=str(data.get("subject_attribute") or ""),
            expected=dict(data.get("expected") or {}),
            severity=str(data.get("severity") or "medium"),
            source_agent=str(data.get("source_agent") or "projectx_native"),
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or _now()),
        )


@dataclass
class ScenarioRiskEstimate:
    scenario_id: str = field(default_factory=lambda: f"scenario-{uuid4().hex[:12]}")
    name: str = ""
    description: str = ""
    likelihood: float = 0.0
    impact: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.0
    affected_entities: List[str] = field(default_factory=list)
    indicators: List[str] = field(default_factory=list)
    mitigations: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["likelihood"] = _clamp01(data.get("likelihood"))
        data["impact"] = _clamp01(data.get("impact"))
        data["risk_score"] = _clamp01(data.get("risk_score"))
        data["confidence"] = _clamp01(data.get("confidence"))
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioRiskEstimate":
        return cls(
            scenario_id=str(data.get("scenario_id") or f"scenario-{uuid4().hex[:12]}"),
            name=str(data.get("name") or ""),
            description=str(data.get("description") or ""),
            likelihood=_clamp01(data.get("likelihood")),
            impact=_clamp01(data.get("impact")),
            risk_score=_clamp01(data.get("risk_score")),
            confidence=_clamp01(data.get("confidence")),
            affected_entities=list(data.get("affected_entities") or []),
            indicators=list(data.get("indicators") or []),
            mitigations=list(data.get("mitigations") or []),
            generated_at=str(data.get("generated_at") or _now()),
        )


@dataclass
class InvariantCheck:
    invariant_id: str
    name: str
    scope: str
    condition: str
    target_id: str
    severity: str
    status: str
    observed_value: Any
    message: str
    checked_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WorldModelStore:
    """Append-only JSONL store for world model records."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or DEFAULT_WORLD_MODEL_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.entities_path = self.root / "entities.jsonl"
        self.relations_path = self.root / "relations.jsonl"
        self.invariants_path = self.root / "invariants.jsonl"
        self.scenarios_path = self.root / "scenarios.jsonl"
        self.checks_path = self.root / "invariant_checks.jsonl"
        self.snapshots_path = self.root / "snapshots.jsonl"
        self._lock = threading.Lock()

    def record_entity(self, entity: WorldEntity | Dict[str, Any]) -> Dict[str, Any]:
        record = entity.to_dict() if isinstance(entity, WorldEntity) else WorldEntity.from_dict(entity).to_dict()
        record["record_type"] = "entity"
        with self._lock:
            append_redacted_jsonl(self.entities_path, record)
        return record

    def record_relation(self, relation: WorldRelation | Dict[str, Any]) -> Dict[str, Any]:
        record = relation.to_dict() if isinstance(relation, WorldRelation) else WorldRelation.from_dict(relation).to_dict()
        record["record_type"] = "relation"
        with self._lock:
            append_redacted_jsonl(self.relations_path, record)
        return record

    def record_invariant(self, invariant: WorldInvariant | Dict[str, Any]) -> Dict[str, Any]:
        record = invariant.to_dict() if isinstance(invariant, WorldInvariant) else WorldInvariant.from_dict(invariant).to_dict()
        record["record_type"] = "invariant"
        with self._lock:
            append_redacted_jsonl(self.invariants_path, record)
        return record

    def record_scenario(self, scenario: ScenarioRiskEstimate | Dict[str, Any]) -> Dict[str, Any]:
        record = scenario.to_dict() if isinstance(scenario, ScenarioRiskEstimate) else ScenarioRiskEstimate.from_dict(scenario).to_dict()
        record["record_type"] = "scenario"
        with self._lock:
            append_redacted_jsonl(self.scenarios_path, record)
        return record

    def record_invariant_check(self, check: InvariantCheck | Dict[str, Any]) -> Dict[str, Any]:
        record = check.to_dict() if isinstance(check, InvariantCheck) else dict(check)
        record["record_type"] = "invariant_check"
        with self._lock:
            append_redacted_jsonl(self.checks_path, record)
        return record

    def record_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(snapshot)
        payload["record_type"] = "snapshot"
        with self._lock:
            append_redacted_jsonl(self.snapshots_path, payload)
        return payload

    def read_entities(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return _read_jsonl(self.entities_path, limit=limit)

    def read_relations(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return _read_jsonl(self.relations_path, limit=limit)

    def read_invariants(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return _read_jsonl(self.invariants_path, limit=limit)

    def read_scenarios(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return _read_jsonl(self.scenarios_path, limit=limit)

    def read_checks(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return _read_jsonl(self.checks_path, limit=limit)

    def read_snapshots(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return _read_jsonl(self.snapshots_path, limit=limit)


class WorldModelTwin:
    """Bounded system twin derived from JSONL world-model records."""

    def __init__(self, store: Optional[WorldModelStore] = None, *, max_records: int = 5_000) -> None:
        self.store = store or WorldModelStore()
        self.max_records = max(1, int(max_records))
        self.generated_at = _now()
        self.entities: Dict[str, WorldEntity] = {}
        self.relations: Dict[str, WorldRelation] = {}
        self.invariants: Dict[str, WorldInvariant] = {}
        self.scenarios: Dict[str, ScenarioRiskEstimate] = {}
        self.refresh()

    def refresh(self) -> "WorldModelTwin":
        self.entities.clear()
        self.relations.clear()
        self.invariants.clear()
        self.scenarios.clear()

        for row in self.store.read_entities(limit=self.max_records):
            entity = WorldEntity.from_dict(row)
            self.entities[entity.entity_id] = entity
        for row in self.store.read_relations(limit=self.max_records):
            relation = WorldRelation.from_dict(row)
            self.relations[relation.relation_id] = relation
        for row in self.store.read_invariants(limit=self.max_records):
            invariant = WorldInvariant.from_dict(row)
            self.invariants[invariant.invariant_id] = invariant
        for row in self.store.read_scenarios(limit=self.max_records):
            scenario = ScenarioRiskEstimate.from_dict(row)
            self.scenarios[scenario.scenario_id] = scenario

        self.generated_at = _now()
        return self

    def upsert_entity(self, **kwargs: Any) -> Dict[str, Any]:
        record = self.store.record_entity(WorldEntity(**kwargs))
        self.refresh()
        return record

    def upsert_relation(self, **kwargs: Any) -> Dict[str, Any]:
        record = self.store.record_relation(WorldRelation(**kwargs))
        self.refresh()
        return record

    def upsert_invariant(self, **kwargs: Any) -> Dict[str, Any]:
        record = self.store.record_invariant(WorldInvariant(**kwargs))
        self.refresh()
        return record

    def upsert_scenario(self, **kwargs: Any) -> Dict[str, Any]:
        record = self.store.record_scenario(ScenarioRiskEstimate(**kwargs))
        self.refresh()
        return record

    def entity(self, entity_id: str) -> Optional[WorldEntity]:
        return self.entities.get(entity_id)

    def relations_for(self, entity_id: str) -> List[WorldRelation]:
        return [
            relation
            for relation in self.relations.values()
            if relation.source_id == entity_id or relation.target_id == entity_id
        ]

    def scenario_risk_estimates(self) -> List[ScenarioRiskEstimate]:
        if not self.scenarios:
            return [self._fallback_system_risk()]
        return [self._estimate_scenario(scenario) for scenario in self.scenarios.values()]

    def evaluate_invariants(self, *, persist_checks: bool = False) -> List[InvariantCheck]:
        checks = [self.evaluate_invariant(invariant) for invariant in self.invariants.values()]
        if persist_checks:
            for check in checks:
                self.store.record_invariant_check(check)
        return checks

    def evaluate_invariant(self, invariant: WorldInvariant) -> InvariantCheck:
        status, observed, message = self._evaluate_invariant_record(invariant)
        return InvariantCheck(
            invariant_id=invariant.invariant_id,
            name=invariant.name,
            scope=invariant.scope,
            condition=invariant.condition,
            target_id=invariant.target_id,
            severity=invariant.severity,
            status=status,
            observed_value=observed,
            message=message,
            checked_at=_now(),
        )

    def snapshot(self, *, persist: bool = True) -> Dict[str, Any]:
        checks = self.evaluate_invariants(persist_checks=persist)
        risks = [estimate.to_dict() for estimate in self.scenario_risk_estimates()]
        snapshot = {
            "phase": WORLD_MODEL_PHASE,
            "generated_at": self.generated_at,
            "counts": {
                "entities": len(self.entities),
                "relations": len(self.relations),
                "invariants": len(self.invariants),
                "scenarios": len(self.scenarios),
            },
            "entities": [entity.to_dict() for entity in self.entities.values()],
            "relations": [relation.to_dict() for relation in self.relations.values()],
            "invariants": [check.to_dict() for check in checks],
            "scenarios": risks,
            "risk_summary": self._risk_summary(risks, checks),
        }
        if persist:
            self.store.record_snapshot(snapshot)
        return snapshot

    def _risk_summary(self, risks: List[Dict[str, Any]], checks: List[InvariantCheck]) -> Dict[str, Any]:
        scenario_risk = max([_safe_float(item.get("risk_score"), 0.0) for item in risks] or [0.0])
        failed = sum(1 for check in checks if check.status == "fail")
        total = len(checks) or 1
        invariant_pressure = failed / total
        overall = max(scenario_risk, invariant_pressure)
        return {
            "overall_risk": _clamp01(overall),
            "max_scenario_risk": _clamp01(scenario_risk),
            "invariant_failure_rate": _clamp01(invariant_pressure),
        }

    def _evaluate_invariant_record(self, invariant: WorldInvariant) -> Tuple[str, Any, str]:
        condition = invariant.condition.lower()
        target_id = invariant.target_id
        entity = self.entities.get(target_id) if target_id else None
        if condition == "entity_exists":
            if entity is None:
                return "fail", None, f"entity {target_id!r} not present"
            return "pass", entity.to_dict(), f"entity {target_id!r} exists"

        if condition == "entity_status_in":
            expected = invariant.expected.get("allowed", invariant.expected.get("values", []))
            allowed = {str(value) for value in expected}
            observed = entity.status if entity else None
            if entity is None:
                return "fail", observed, f"entity {target_id!r} not present"
            if allowed and str(observed) not in allowed:
                return "fail", observed, f"entity status {observed!r} not in {sorted(allowed)!r}"
            return "pass", observed, f"entity status {observed!r} accepted"

        if condition in {"attribute_equals", "attribute_min", "attribute_max"}:
            if entity is None:
                return "fail", None, f"entity {target_id!r} not present"
            attr = invariant.subject_attribute
            observed = entity.attributes.get(attr)
            expected_value = invariant.expected.get("value")
            if condition == "attribute_equals":
                if observed != expected_value:
                    return "fail", observed, f"attribute {attr!r} expected {expected_value!r} but observed {observed!r}"
                return "pass", observed, f"attribute {attr!r} matched {expected_value!r}"
            observed_num = _safe_float(observed, default=math.nan)
            expected_num = _safe_float(expected_value, default=math.nan)
            if math.isnan(observed_num) or math.isnan(expected_num):
                return "unknown", observed, f"attribute {attr!r} is not numeric"
            if condition == "attribute_min" and observed_num < expected_num:
                return "fail", observed, f"attribute {attr!r} below minimum {expected_num!r}"
            if condition == "attribute_max" and observed_num > expected_num:
                return "fail", observed, f"attribute {attr!r} above maximum {expected_num!r}"
            return "pass", observed, f"attribute {attr!r} within expected bounds"

        if condition == "relation_exists":
            source_id = invariant.expected.get("source_id") or target_id
            relation_type = invariant.expected.get("relation_type")
            target = invariant.expected.get("target_id")
            found = self._find_relation(source_id=source_id, relation_type=relation_type, target_id=target)
            if found is None:
                return "fail", None, "required relation not present"
            return "pass", found.to_dict(), "required relation present"

        if condition in {"relation_count_min", "relation_count_max"}:
            rels = self.relations_for(target_id)
            relation_type = invariant.expected.get("relation_type")
            if relation_type:
                rels = [rel for rel in rels if rel.relation_type == relation_type]
            observed = len(rels)
            threshold = int(invariant.expected.get("value", 0) or 0)
            if condition == "relation_count_min" and observed < threshold:
                return "fail", observed, f"only {observed} relation(s), expected at least {threshold}"
            if condition == "relation_count_max" and observed > threshold:
                return "fail", observed, f"{observed} relation(s) exceeds maximum {threshold}"
            return "pass", observed, f"relation count {observed} within bounds"

        return "unknown", None, f"unsupported invariant condition {invariant.condition!r}"

    def _find_relation(
        self,
        *,
        source_id: Optional[str] = None,
        relation_type: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> Optional[WorldRelation]:
        for relation in self.relations.values():
            if source_id and relation.source_id != source_id:
                continue
            if relation_type and relation.relation_type != relation_type:
                continue
            if target_id and relation.target_id != target_id:
                continue
            return relation
        return None

    def _estimate_scenario(self, scenario: ScenarioRiskEstimate) -> ScenarioRiskEstimate:
        likelihood = _clamp01(scenario.likelihood)
        impact = _clamp01(scenario.impact)
        structural_pressure = self._scenario_structural_pressure(scenario)
        risk_score = _clamp01((0.45 * likelihood) + (0.45 * impact) + (0.10 * structural_pressure))
        confidence = _clamp01(max(scenario.confidence, 1.0 - abs(likelihood - impact)))
        return ScenarioRiskEstimate(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            description=scenario.description,
            likelihood=likelihood,
            impact=impact,
            risk_score=risk_score,
            confidence=confidence,
            affected_entities=list(scenario.affected_entities),
            indicators=list(scenario.indicators),
            mitigations=list(scenario.mitigations),
            generated_at=_now(),
        )

    def _fallback_system_risk(self) -> ScenarioRiskEstimate:
        checks = self.evaluate_invariants()
        failed = sum(1 for check in checks if check.status == "fail")
        failure_rate = failed / max(1, len(checks))
        critical_entities = sum(1 for entity in self.entities.values() if _clamp01(entity.criticality) >= 0.7)
        entity_pressure = critical_entities / max(1, len(self.entities))
        relation_pressure = min(1.0, len(self.relations) / max(1, len(self.entities) * 2))
        risk_score = _clamp01(max(failure_rate, entity_pressure, relation_pressure))
        return ScenarioRiskEstimate(
            scenario_id="scenario-system-twin",
            name="system_twin_health",
            description="Fallback risk estimate derived from invariant failures and graph density.",
            likelihood=_clamp01(failure_rate),
            impact=_clamp01(max(entity_pressure, relation_pressure)),
            risk_score=risk_score,
            confidence=_clamp01(1.0 - failure_rate * 0.5),
            affected_entities=[entity.entity_id for entity in self.entities.values() if _clamp01(entity.criticality) > 0.5],
            indicators=["invariant_failures", "entity_criticality", "graph_density"],
            mitigations=["refresh_world_model", "review_failed_invariants", "tighten_monitoring"],
            generated_at=_now(),
        )

    def _scenario_structural_pressure(self, scenario: ScenarioRiskEstimate) -> float:
        if not scenario.affected_entities:
            return 0.0
        pressures = []
        for entity_id in scenario.affected_entities:
            entity = self.entities.get(entity_id)
            if not entity:
                pressures.append(0.4)
                continue
            local_pressure = _clamp01(entity.criticality)
            local_pressure = max(local_pressure, min(1.0, len(self.relations_for(entity_id)) / 5.0))
            pressures.append(local_pressure)
        return sum(pressures) / max(1, len(pressures))

    def status(self) -> Dict[str, Any]:
        snapshot = self.snapshot(persist=False)
        return {
            "phase": WORLD_MODEL_PHASE,
            "generated_at": self.generated_at,
            "counts": snapshot["counts"],
            "risk_summary": snapshot["risk_summary"],
        }


_world_twin: Optional[WorldModelTwin] = None


def get_world_twin() -> WorldModelTwin:
    global _world_twin
    if _world_twin is None:
        _world_twin = WorldModelTwin()
    return _world_twin


def build_world_model_snapshot(*, persist: bool = True) -> Dict[str, Any]:
    return get_world_twin().snapshot(persist=persist)


def world_model_status() -> Dict[str, Any]:
    return get_world_twin().status()


__all__ = [
    "WORLD_MODEL_PHASE",
    "WorldEntity",
    "WorldRelation",
    "WorldInvariant",
    "ScenarioRiskEstimate",
    "InvariantCheck",
    "WorldModelStore",
    "WorldModelTwin",
    "get_world_twin",
    "build_world_model_snapshot",
    "world_model_status",
]
