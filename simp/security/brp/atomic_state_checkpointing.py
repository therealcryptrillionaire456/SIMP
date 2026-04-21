"""Atomic JSON checkpoint helpers for BRP runtime state."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKPOINT_SCHEMA_VERSION = "brp.checkpoint.v1"


def checkpoint_document(*, kind: str, payload: Any, version: str = CHECKPOINT_SCHEMA_VERSION) -> dict[str, Any]:
    """Wrap a payload in checkpoint metadata."""
    return {
        "checkpoint_schema": version,
        "kind": kind,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def load_checkpoint_payload(
    filepath: Path,
    *,
    default: Any = None,
    expected_kind: str | None = None,
) -> Any:
    """Load a checkpoint payload, falling back to raw JSON for legacy files."""
    if not filepath.exists():
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default

    if isinstance(data, dict) and data.get("checkpoint_schema") == CHECKPOINT_SCHEMA_VERSION:
        if expected_kind and str(data.get("kind") or "") != expected_kind:
            return default
        return data.get("payload", default)
    return data


def save_checkpoint_payload(
    filepath: Path,
    *,
    kind: str,
    payload: Any,
) -> None:
    """Atomically persist a JSON checkpoint."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    document = checkpoint_document(kind=kind, payload=payload)
    encoded = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")

    fd, tmp_name = tempfile.mkstemp(prefix=f".{filepath.name}.", suffix=".tmp", dir=str(filepath.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, filepath)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass
