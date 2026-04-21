"""Deterministic namespaced runtime cache for BRP."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .atomic_state_checkpointing import load_checkpoint_payload, save_checkpoint_payload


class NamespacedRuntimeCache:
    """Replay-safe cache with namespace-scoped invalidation."""

    KIND = "runtime_cache"
    STATE_VERSION = "brp.runtime_cache.v1"

    def __init__(self, checkpoint_path: Path | None = None):
        self.checkpoint_path = checkpoint_path
        self._state: dict[str, Any] = {
            "schema_version": self.STATE_VERSION,
            "namespaces": {},
        }
        if checkpoint_path is not None:
            loaded = load_checkpoint_payload(
                checkpoint_path,
                default=None,
                expected_kind=self.KIND,
            )
            if isinstance(loaded, dict) and isinstance(loaded.get("namespaces"), dict):
                self._state = loaded

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        namespace_state = self._namespace_state(namespace)
        entry = namespace_state["entries"].get(key)
        if not isinstance(entry, dict):
            return None
        return entry.get("value")

    def set(
        self,
        namespace: str,
        key: str,
        value: dict[str, Any],
        *,
        dependencies: list[str] | None = None,
    ) -> None:
        namespace_state = self._namespace_state(namespace)
        namespace_state["entries"][key] = {
            "updated_at": self._timestamp(),
            "dependencies": list(dependencies or []),
            "value": value,
        }
        namespace_state["updated_at"] = self._timestamp()
        self.save()

    def invalidate_namespace(self, namespace: str, *, reason: str | None = None) -> None:
        namespace_state = self._namespace_state(namespace)
        namespace_state["entries"] = {}
        namespace_state["invalidated_at"] = self._timestamp()
        namespace_state["invalidate_reason"] = reason
        namespace_state["updated_at"] = self._timestamp()
        self.save()

    def namespace_summary(self) -> dict[str, Any]:
        namespaces = self._state.get("namespaces", {})
        summary: dict[str, Any] = {}
        for name, state in namespaces.items():
            if not isinstance(state, dict):
                continue
            summary[name] = {
                "entries": len(state.get("entries", {})),
                "updated_at": state.get("updated_at"),
                "invalidated_at": state.get("invalidated_at"),
            }
        return summary

    def snapshot(self) -> dict[str, Any]:
        return self._state

    def save(self) -> None:
        if self.checkpoint_path is None:
            return
        save_checkpoint_payload(
            self.checkpoint_path,
            kind=self.KIND,
            payload=self._state,
        )

    def _namespace_state(self, namespace: str) -> dict[str, Any]:
        namespaces = self._state.setdefault("namespaces", {})
        if namespace not in namespaces or not isinstance(namespaces[namespace], dict):
            namespaces[namespace] = {
                "entries": {},
                "updated_at": None,
                "invalidated_at": None,
                "invalidate_reason": None,
            }
        return namespaces[namespace]

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
