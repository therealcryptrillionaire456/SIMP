"""
SIMP Rollback System — Sprint 46

Instant rollback to simulated-only mode.
When FINANCIAL_OPS_LIVE_ENABLED != "true", rollback is always ACTIVE.
Appends to data/rollback_log.jsonl (append-only).
"""

import json
import os
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SIMP.Rollback")

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _ensure_data_dir() -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    return _DATA_DIR


# ---------------------------------------------------------------------------
# RollbackState
# ---------------------------------------------------------------------------

class RollbackState(str, Enum):
    ACTIVE = "active"          # Rolled back — simulated only
    INACTIVE = "inactive"      # Live mode running normally
    NEVER_LIVE = "never_live"  # Live mode was never enabled


# ---------------------------------------------------------------------------
# RollbackRecord
# ---------------------------------------------------------------------------

@dataclass
class RollbackRecord:
    record_id: str = ""
    state: str = ""
    triggered_by: str = ""
    reason: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# LedgerFrozenError
# ---------------------------------------------------------------------------

class LedgerFrozenError(Exception):
    """Raised when a write operation is attempted on a frozen ledger."""
    pass


# ---------------------------------------------------------------------------
# RollbackManager
# ---------------------------------------------------------------------------

class RollbackManager:
    """
    Manages rollback state for the financial-ops system.
    Appends to data/rollback_log.jsonl (append-only).
    """

    def __init__(self, filepath: Optional[str] = None):
        _ensure_data_dir()
        self._filepath = filepath or os.path.join(_DATA_DIR, "rollback_log.jsonl")
        self._lock = threading.Lock()
        self._history: List[RollbackRecord] = []
        self._current_state = RollbackState.NEVER_LIVE
        self._rebuild_from_events()

    def _rebuild_from_events(self) -> None:
        if not os.path.exists(self._filepath):
            return
        with open(self._filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    rec = RollbackRecord(
                        record_id=event.get("record_id", ""),
                        state=event.get("state", ""),
                        triggered_by=event.get("triggered_by", ""),
                        reason=event.get("reason", ""),
                        timestamp=event.get("timestamp", ""),
                    )
                    self._history.append(rec)
                    self._current_state = RollbackState(rec.state)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    def _append_event(self, record: RollbackRecord) -> None:
        with open(self._filepath, "a") as f:
            f.write(json.dumps(record.to_dict(), default=str) + "\n")

    def get_state(self) -> RollbackState:
        """
        Get current rollback state.
        If FINANCIAL_OPS_LIVE_ENABLED != "true", always returns ACTIVE or NEVER_LIVE.
        """
        live_enabled = os.environ.get("FINANCIAL_OPS_LIVE_ENABLED", "").lower() == "true"
        if not live_enabled:
            # If we have history of being active, state is ACTIVE; otherwise NEVER_LIVE
            if self._current_state == RollbackState.INACTIVE:
                return RollbackState.ACTIVE
            if self._current_state == RollbackState.ACTIVE:
                return RollbackState.ACTIVE
            return RollbackState.NEVER_LIVE
        return self._current_state

    def trigger_rollback(self, triggered_by: str = "system", reason: str = "") -> RollbackRecord:
        """
        Trigger a rollback — sets state to ACTIVE and records the event.
        """
        record = RollbackRecord(
            state=RollbackState.ACTIVE.value,
            triggered_by=triggered_by,
            reason=reason or "Manual rollback triggered",
        )
        with self._lock:
            self._append_event(record)
            self._history.append(record)
            self._current_state = RollbackState.ACTIVE

        logger.warning("ROLLBACK TRIGGERED by %s: %s", triggered_by, reason)
        return record

    def deactivate_rollback(self, triggered_by: str = "system", reason: str = "") -> RollbackRecord:
        """
        Deactivate rollback — sets state to INACTIVE (only if live is enabled).
        """
        record = RollbackRecord(
            state=RollbackState.INACTIVE.value,
            triggered_by=triggered_by,
            reason=reason or "Rollback deactivated",
        )
        with self._lock:
            self._append_event(record)
            self._history.append(record)
            self._current_state = RollbackState.INACTIVE

        logger.info("Rollback deactivated by %s: %s", triggered_by, reason)
        return record

    def get_rollback_status(self) -> Dict[str, Any]:
        """Get current rollback status."""
        state = self.get_state()
        live_enabled = os.environ.get("FINANCIAL_OPS_LIVE_ENABLED", "").lower() == "true"
        return {
            "state": state.value,
            "live_enabled": live_enabled,
            "rollback_count": sum(1 for r in self._history if r.state == RollbackState.ACTIVE.value),
            "last_rollback": self._history[-1].to_dict() if self._history else None,
        }

    def get_rollback_history(self) -> List[Dict[str, Any]]:
        """Get rollback history (most recent first)."""
        with self._lock:
            return [r.to_dict() for r in reversed(self._history)]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

ROLLBACK_MANAGER = RollbackManager()
