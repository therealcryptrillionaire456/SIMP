"""
T46: Strategy Registry with Versioning
======================================
Version-controlled strategy definitions with promote/demote/rollback.

This module provides:
1. StrategyDefinition — versioned strategy metadata
2. StrategyRegistry — CRUD with version history
3. Promotion workflow — draft → staging → production
4. Rollback to any previous version
5. Diff between versions
6. Integration with StrategySwitcher

Usage:
    registry = StrategyRegistry(registry_path=Path("data/strategy_registry.jsonl"))
    reg.register(StrategyDefinition(...), version="1.0.0")
    reg.promote("momentum_arbitrage", from_stage="staging", to_stage="production")
    reg.rollback("momentum_arbitrage", to_version="1.0.0")
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class Stage(str, Enum):
    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class StrategyParams:
    """Typed parameter set for a strategy."""
    params: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"params": self.params, "constraints": self.constraints}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyParams:
        return cls(params=data.get("params", {}), constraints=data.get("constraints", {}))


@dataclass
class StrategyDefinition:
    """Versioned strategy definition with promotion lifecycle."""
    strategy_id: str
    name: str
    description: str
    version: str                      # Semver: e.g. "1.0.0", "2.1.3"
    stage: Stage                      # draft | staging | production | deprecated
    params: StrategyParams
    min_capital_usd: float = 0.0
    max_capital_usd: float = 1_000_000.0
    applicable_regimes: List[str] = field(default_factory=list)  # e.g. ["trending", "volatile"]
    applicable_pairs: List[str] = field(default_factory=list)     # e.g. ["BTC-USD", "ETH-USD"]
    tags: List[str] = field(default_factory=list)
    created_by: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promoted_at: Optional[str] = None
    promoted_by: Optional[str] = None
    deprecated_at: Optional[str] = None
    deprecation_reason: Optional[str] = None

    def _param_hash(self) -> str:
        """Stable hash of params for change detection."""
        payload = json.dumps(self.params.to_dict(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def signature(self) -> str:
        """Unique signature: name + version."""
        return f"{self.name}@{self.version}"

    def is_production(self) -> bool:
        return self.stage == Stage.PRODUCTION

    def is_active(self) -> bool:
        return self.stage in (Stage.PRODUCTION, Stage.STAGING)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        d["params"] = self.params.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyDefinition:
        d = dict(data)
        d["stage"] = Stage(d.get("stage", "draft"))
        d["params"] = StrategyParams.from_dict(d.get("params", {}))
        return cls(**d)


@dataclass
class VersionHistoryEntry:
    """Single version snapshot in history."""
    version: str
    stage: str
    params_hash: str
    created_at: str
    created_by: str
    change_note: str = ""


@dataclass
class PromotionEvent:
    """Audit trail entry for promotions/demotions."""
    event_id: str
    strategy_id: str
    from_stage: Optional[str]
    to_stage: str
    version: str
    actor: str
    timestamp: str
    reason: str = ""
    notes: str = ""


# ── Strategy Registry ─────────────────────────────────────────────────────────

class StrategyRegistry:
    """
    Version-controlled registry for strategy definitions.

    Provides:
    - CRUD operations with version history
    - Promotion workflow (draft → staging → production)
    - Rollback to any previous version
    - Diff between versions
    - Thread-safe operations
    """

    def __init__(
        self,
        registry_path: Optional[Path] = None,
        history_path: Optional[Path] = None,
        audit_path: Optional[Path] = None,
    ):
        self._lock = threading.Lock()
        self._registry_path = registry_path or Path("data/strategy_registry.jsonl")
        self._history_path = history_path or Path("data/strategy_history.jsonl")
        self._audit_path = audit_path or Path("data/strategy_audit.jsonl")

        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._strategies: Dict[str, StrategyDefinition] = {}
        self._versions: Dict[str, List[VersionHistoryEntry]] = {}  # strategy_id -> history

        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load registry from JSONL."""
        try:
            if not self._registry_path.exists():
                return
            with open(self._registry_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        # Take the latest version of each strategy
                        key = d["strategy_id"]
                        if key not in self._strategies or d["version"] > self._strategies[key].version:
                            self._strategies[key] = StrategyDefinition.from_dict(d)
                    except Exception:
                        continue
            logger.info("StrategyRegistry loaded %d strategies", len(self._strategies))
        except Exception as e:
            logger.error("Failed to load strategy registry: %s", e)

    def _persist(self, strategy: StrategyDefinition) -> None:
        """Append strategy state to JSONL."""
        try:
            with self._lock:
                with open(self._registry_path, "a") as f:
                    f.write(json.dumps(strategy.to_dict()) + "\n")
        except Exception as e:
            logger.error("Failed to persist strategy %s: %s", strategy.strategy_id, e)

    def _record_audit(self, event: PromotionEvent) -> None:
        """Record promotion/demotion event."""
        try:
            with open(self._audit_path, "a") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception as e:
            logger.error("Failed to record audit event: %s", e)

    def _record_history(self, strategy_id: str, entry: VersionHistoryEntry) -> None:
        """Record version history entry."""
        try:
            with open(self._history_path, "a") as f:
                record = {"strategy_id": strategy_id, **asdict(entry)}
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error("Failed to record history: %s", e)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def register(
        self,
        definition: StrategyDefinition,
        created_by: str = "system",
        change_note: str = "",
    ) -> StrategyDefinition:
        """Register or update a strategy definition."""
        with self._lock:
            definition.created_by = created_by
            definition.created_at = datetime.now(timezone.utc).isoformat()
            definition.updated_at = definition.created_at

            existing = self._strategies.get(definition.strategy_id)
            if existing:
                definition = self._upgrade(existing, definition)

            self._strategies[definition.strategy_id] = definition
            self._persist(definition)

            # Record history
            entry = VersionHistoryEntry(
                version=definition.version,
                stage=definition.stage.value,
                params_hash=definition._param_hash(),
                created_at=definition.created_at,
                created_by=created_by,
                change_note=change_note,
            )
            self._record_history(definition.strategy_id, entry)
            self._record_audit(PromotionEvent(
                event_id=f"ae-{int(time.time())}-{self._seq()}".replace("-", ""),
                strategy_id=definition.strategy_id,
                from_stage=None,
                to_stage=definition.stage.value,
                version=definition.version,
                actor=created_by,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reason="register",
                notes=change_note,
            ))

            logger.info("Registered strategy %s v%s (stage=%s)",
                        definition.strategy_id, definition.version, definition.stage.value)
            return definition

    def _upgrade(self, existing: StrategyDefinition, new_def: StrategyDefinition) -> StrategyDefinition:
        """Handle version upgrade logic."""
        # Verify semver bump
        if not self._is_newer_version(new_def.version, existing.version):
            raise ValueError(
                f"New version {new_def.version} must be > existing {existing.version}"
            )
        return new_def

    def _is_newer_version(self, new: str, old: str) -> bool:
        """Simple semver comparison."""
        def parse(v):
            return [int(x) for x in v.lstrip("v").split(".")[:3]] + [0, 0]
        return parse(new) > parse(old)

    def get(self, strategy_id: str, version: Optional[str] = None) -> Optional[StrategyDefinition]:
        """Get strategy by ID (latest version or specific version)."""
        if version:
            # Scan history for specific version
            path = self._registry_path
            if path.exists():
                with open(path) as f:
                    for line in f:
                        try:
                            d = json.loads(line.strip())
                            if d["strategy_id"] == strategy_id and d["version"] == version:
                                return StrategyDefinition.from_dict(d)
                        except Exception:
                            continue
            return None
        return self._strategies.get(strategy_id)

    def get_production_version(self, strategy_id: str) -> Optional[StrategyDefinition]:
        """Get the current production version of a strategy."""
        s = self._strategies.get(strategy_id)
        if s and s.stage == Stage.PRODUCTION:
            return s
        return None

    def list_by_stage(self, stage: Stage) -> List[StrategyDefinition]:
        """List all strategies in a given stage."""
        return [s for s in self._strategies.values() if s.stage == stage]

    def list_all(self) -> List[StrategyDefinition]:
        """List all strategies (latest version only)."""
        return list(self._strategies.values())

    def list_active(self) -> List[StrategyDefinition]:
        """List all active (staging + production) strategies."""
        return [s for s in self._strategies.values() if s.is_active()]

    def update_params(
        self,
        strategy_id: str,
        new_params: StrategyParams,
        updated_by: str = "system",
        change_note: str = "",
    ) -> StrategyDefinition:
        """Update params (creates new version)."""
        existing = self._strategies.get(strategy_id)
        if not existing:
            raise ValueError(f"Strategy not found: {strategy_id}")

        # Bump patch version
        version_parts = existing.version.split(".")
        version_parts[2] = str(int(version_parts[2]) + 1)
        new_version = ".".join(version_parts)

        updated = StrategyDefinition(
            strategy_id=existing.strategy_id,
            name=existing.name,
            description=existing.description,
            version=new_version,
            stage=Stage.DRAFT,
            params=new_params,
            min_capital_usd=existing.min_capital_usd,
            max_capital_usd=existing.max_capital_usd,
            applicable_regimes=existing.applicable_regimes,
            applicable_pairs=existing.applicable_pairs,
            tags=existing.tags,
            created_by=existing.created_by,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        return self.register(updated, created_by=updated_by, change_note=change_note)

    def deprecate(
        self,
        strategy_id: str,
        reason: str,
        deprecated_by: str = "system",
    ) -> StrategyDefinition:
        """Deprecate a strategy (marks as deprecated, doesn't delete)."""
        existing = self._strategies.get(strategy_id)
        if not existing:
            raise ValueError(f"Strategy not found: {strategy_id}")

        now = datetime.now(timezone.utc).isoformat()
        deprecated = StrategyDefinition(
            **asdict(existing),
            stage=Stage.DEPRECATED,
            deprecated_at=now,
            deprecation_reason=reason,
            updated_at=now,
        )
        self._strategies[strategy_id] = deprecated
        self._persist(deprecated)
        self._record_audit(PromotionEvent(
            event_id=f"ae-{int(time.time())}-{self._seq()}".replace("-", ""),
            strategy_id=strategy_id,
            from_stage=existing.stage.value,
            to_stage=Stage.DEPRECATED.value,
            version=existing.version,
            actor=deprecated_by,
            timestamp=now,
            reason="deprecate",
            notes=reason,
        ))
        logger.warning("Deprecated strategy %s: %s", strategy_id, reason)
        return deprecated

    # ── Promotion Workflow ───────────────────────────────────────────────────

    def promote(
        self,
        strategy_id: str,
        to_stage: Stage,
        actor: str = "system",
        reason: str = "",
    ) -> StrategyDefinition:
        """
        Promote a strategy to the next stage.

        Valid transitions:
          draft → staging
          staging → production
          production → deprecated (demotion)

        Returns the updated strategy.
        """
        existing = self._strategies.get(strategy_id)
        if not existing:
            raise ValueError(f"Strategy not found: {strategy_id}")

        # Validate transition
        valid = {
            Stage.DRAFT: {Stage.STAGING},
            Stage.STAGING: {Stage.PRODUCTION, Stage.DEPRECATED},
            Stage.PRODUCTION: {Stage.DEPRECATED},
            Stage.DEPRECATED: set(),
        }
        if to_stage not in valid.get(existing.stage, set()):
            raise ValueError(
                f"Invalid promotion: {existing.stage.value} → {to_stage.value} "
                f"(strategy={strategy_id}, version={existing.version})"
            )

        now = datetime.now(timezone.utc).isoformat()
        promoted = StrategyDefinition(
            **asdict(existing),
            stage=to_stage,
            updated_at=now,
            promoted_at=now if to_stage == Stage.PRODUCTION else existing.promoted_at,
            promoted_by=actor if to_stage == Stage.PRODUCTION else existing.promoted_by,
        )
        self._strategies[strategy_id] = promoted
        self._persist(promoted)

        entry = VersionHistoryEntry(
            version=promoted.version,
            stage=to_stage.value,
            params_hash=promoted._param_hash(),
            created_at=now,
            created_by=actor,
            change_note=f"Promoted to {to_stage.value}: {reason}",
        )
        self._record_history(strategy_id, entry)
        self._record_audit(PromotionEvent(
            event_id=f"ae-{int(time.time())}-{self._seq()}".replace("-", ""),
            strategy_id=strategy_id,
            from_stage=existing.stage.value,
            to_stage=to_stage.value,
            version=existing.version,
            actor=actor,
            timestamp=now,
            reason=reason,
        ))

        logger.info("Promoted %s v%s from %s to %s",
                    strategy_id, existing.version, existing.stage.value, to_stage.value)
        return promoted

    def rollback(
        self,
        strategy_id: str,
        to_version: str,
        actor: str = "system",
        reason: str = "",
    ) -> StrategyDefinition:
        """Rollback to a previous version (re-registers as new latest)."""
        old = self.get(strategy_id, version=to_version)
        if not old:
            raise ValueError(
                f"Version {to_version} of strategy {strategy_id} not found in registry"
            )

        # Bump version and reset stage to draft for re-review
        version_parts = self._strategies.get(strategy_id, old).version.split(".")
        version_parts[1] = str(int(version_parts[1]) + 1)
        version_parts[2] = "0"
        rollback_version = ".".join(version_parts)

        rollback_def = StrategyDefinition(
            strategy_id=old.strategy_id,
            name=old.name,
            description=old.description,
            version=rollback_version,
            stage=Stage.DRAFT,
            params=old.params,
            min_capital_usd=old.min_capital_usd,
            max_capital_usd=old.max_capital_usd,
            applicable_regimes=old.applicable_regimes,
            applicable_pairs=old.applicable_pairs,
            tags=old.tags,
            created_by=old.created_by,
            created_at=old.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._record_audit(PromotionEvent(
            event_id=f"ae-{int(time.time())}-{self._seq()}".replace("-", ""),
            strategy_id=strategy_id,
            from_stage=rollback_def.stage.value,
            to_stage=Stage.DRAFT.value,
            version=rollback_version,
            actor=actor,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=f"rollback to {to_version}: {reason}",
        ))
        return self.register(rollback_def, created_by=actor,
                             change_note=f"Rollback to {to_version}: {reason}")

    # ── Version History ──────────────────────────────────────────────────────

    def version_history(self, strategy_id: str) -> List[VersionHistoryEntry]:
        """Get full version history for a strategy."""
        history = []
        if self._history_path.exists():
            with open(self._history_path) as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                        if d.get("strategy_id") == strategy_id:
                            history.append(VersionHistoryEntry(**{
                                k: v for k, v in d.items()
                                if k != "strategy_id"
                            }))
                    except Exception:
                        continue
        return history

    def diff_versions(
        self,
        strategy_id: str,
        version_a: str,
        version_b: str,
    ) -> Dict[str, Any]:
        """Compute diff between two versions of a strategy."""
        s_a = self.get(strategy_id, version=version_a)
        s_b = self.get(strategy_id, version=version_b)
        if not s_a or not s_b:
            raise ValueError(f"One or both versions not found for {strategy_id}")

        changes = {
            "strategy_id": strategy_id,
            "version_a": version_a,
            "version_b": version_b,
            "diffs": [],
        }

        def diff_field(label, a, b):
            if a != b:
                changes["diffs"].append({
                    "field": label,
                    "from": a,
                    "to": b,
                })

        diff_field("version", s_a.version, s_b.version)
        diff_field("stage", s_a.stage.value, s_b.stage.value)
        diff_field("description", s_a.description, s_b.description)
        diff_field("min_capital", s_a.min_capital_usd, s_b.min_capital_usd)
        diff_field("max_capital", s_a.max_capital_usd, s_b.max_capital_usd)
        diff_field("regimes", s_a.applicable_regimes, s_b.applicable_regimes)
        diff_field("pairs", s_a.applicable_pairs, s_b.applicable_pairs)
        diff_field("params", s_a.params.to_dict(), s_b.params.to_dict())
        changes["params_changed"] = s_a.params.to_dict() != s_b.params.to_dict()
        return changes

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _seq(self) -> int:
        return int(time.time() * 1000) % 1000000

    def summary(self) -> Dict[str, Any]:
        """Get registry summary stats."""
        all_strategies = self.list_all()
        by_stage = {s.value: 0 for s in Stage}
        for s in all_strategies:
            by_stage[s.stage.value] += 1
        return {
            "total_strategies": len(all_strategies),
            "by_stage": by_stage,
            "active_count": len(self.list_active()),
        }


# ── Module-level singleton ───────────────────────────────────────────────────

_registry: Optional[StrategyRegistry] = None
_registry_lock = threading.Lock()


def get_strategy_registry(
    registry_path: Optional[Path] = None,
) -> StrategyRegistry:
    """Get or create the module-level StrategyRegistry singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = StrategyRegistry(registry_path=registry_path)
    return _registry


# ── Self-test ────────────────────────────────────────────────────────────────

def test_strategy_registry() -> None:
    """Run a self-test of the strategy registry."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        registry = StrategyRegistry(
            registry_path=Path(tmpdir) / "registry.jsonl",
            history_path=Path(tmpdir) / "history.jsonl",
            audit_path=Path(tmpdir) / "audit.jsonl",
        )

        # Register a strategy
        strat = StrategyDefinition(
            strategy_id="momentum_arbitrage",
            name="Momentum Arbitrage",
            description="Arbitrage strategy using momentum signals",
            version="1.0.0",
            stage=Stage.DRAFT,
            params=StrategyParams(params={"fast": 10, "slow": 30}),
            applicable_regimes=["trending"],
            applicable_pairs=["BTC-USD", "ETH-USD"],
        )
        reg_strat = registry.register(strat, created_by="alice", change_note="Initial draft")
        assert reg_strat.stage == Stage.DRAFT
        assert registry.get("momentum_arbitrage") is not None

        # Promote to staging
        staging = registry.promote("momentum_arbitrage", Stage.STAGING, actor="alice", reason="Initial review")
        assert staging.stage == Stage.STAGING

        # Update params (creates new version)
        new_params = StrategyParams(params={"fast": 15, "slow": 40})
        v2 = registry.update_params("momentum_arbitrage", new_params, updated_by="bob", change_note="Tune params")
        assert v2.version == "1.0.1"
        assert v2.stage == Stage.DRAFT

        # Promote to production
        prod = registry.promote("momentum_arbitrage", Stage.STAGING, actor="alice")
        prod = registry.promote("momentum_arbitrage", Stage.PRODUCTION, actor="alice", reason="Validated on staging")

        # Get production version
        prod_v = registry.get_production_version("momentum_arbitrage")
        assert prod_v is not None
        assert prod_v.stage == Stage.PRODUCTION
        assert prod_v.promoted_by == "alice"

        # Rollback
        rb = registry.rollback("momentum_arbitrage", "1.0.0", actor="carol", reason="Revert to stable")
        assert rb.version == "1.1.0"
        assert rb.stage == Stage.DRAFT

        # Diff
        diff = registry.diff_versions("momentum_arbitrage", "1.0.0", "1.0.1")
        assert diff["params_changed"] is True

        # Deprecate
        deprecated = registry.deprecate("momentum_arbitrage", "Superseded by v2", deprecated_by="alice")
        assert deprecated.stage == Stage.DEPRECATED

        summary = registry.summary()
        print(f"Registry summary: {summary}")
        print("All tests passed!")


if __name__ == "__main__":
    test_strategy_registry()
