"""
SIMP Intent Ledger — Sprint 52 (renamed from task_ledger in Sprint 61)

Append-only JSONL ledger for intent lifecycle tracking.
All writes are flushed immediately; reads tolerate corrupt lines.
"""

import json
import logging
import os
import shutil
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SIMP.IntentLedger")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)


@dataclass
class LedgerConfig:
    """Tuning knobs for the intent ledger."""
    path: str = os.path.join(_REPO_ROOT, "data", "task_ledger.jsonl")
    max_size_mb: float = 100.0
    expire_after_hours: float = 168.0  # 7 days


# ---------------------------------------------------------------------------
# IntentLedger
# ---------------------------------------------------------------------------

class IntentLedger:
    """
    Append-only JSONL ledger that records every intent lifecycle event.

    Rules:
    - ``append()`` never raises — errors are logged.
    - ``load_pending()`` skips corrupt lines.
    - ``rotate_if_needed()`` renames the current file and starts a fresh one.
    """

    def __init__(self, config: Optional[LedgerConfig] = None):
        self.config = config or LedgerConfig()
        self._path = Path(self.config.path)
        self._lock = threading.Lock()
        self._ensure_dir()

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # append
    # ------------------------------------------------------------------

    def append(self, record: Dict[str, Any]) -> None:
        """
        Write one JSON line to the ledger.  Never raises.
        Thread-safe with file locking.
        """
        try:
            enriched = dict(record)
            if "ledger_ts" not in enriched:
                enriched["ledger_ts"] = datetime.now(timezone.utc).isoformat()
            line = json.dumps(enriched, default=str) + "\n"
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(line)
                    fh.flush()
        except Exception as exc:
            logger.error("IntentLedger.append failed: %s", exc)

    # ------------------------------------------------------------------
    # load helpers
    # ------------------------------------------------------------------

    def load_pending(self) -> List[Dict[str, Any]]:
        """Return records whose status is 'pending'.  Skips corrupt lines."""
        results: List[Dict[str, Any]] = []
        if not self._path.exists():
            return results
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("IntentLedger: skipping corrupt line")
                        continue
                    if rec.get("status") == "pending":
                        results.append(rec)
        except Exception as exc:
            logger.error("IntentLedger.load_pending failed: %s", exc)
        return results

    def load_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Return the last *limit* records from the ledger."""
        records: List[Dict[str, Any]] = []
        if not self._path.exists():
            return records
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    records.append(rec)
        except Exception as exc:
            logger.error("IntentLedger.load_all failed: %s", exc)
        # Return last N
        if len(records) > limit:
            records = records[-limit:]
        return records

    # ------------------------------------------------------------------
    # expire
    # ------------------------------------------------------------------

    def expire_old_records(
        self, intent_records: Dict[str, Any]
    ) -> int:
        """
        Mark old pending intents as 'expired' and append expiration events.

        Returns number of records expired.
        """
        now = time.time()
        cutoff_s = self.config.expire_after_hours * 3600
        expired = 0

        for intent_id, record in list(intent_records.items()):
            status = record.status if hasattr(record, "status") else record.get("status")
            ts = record.timestamp if hasattr(record, "timestamp") else record.get("timestamp", "")
            if status != "pending":
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                age_s = now - dt.timestamp()
            except Exception:
                continue
            if age_s > cutoff_s:
                # Mark as expired on the record object
                if hasattr(record, "status"):
                    record.status = "expired"
                else:
                    record["status"] = "expired"
                self.append({
                    "event": "expired",
                    "intent_id": intent_id,
                    "status": "expired",
                    "reason": f"Exceeded {self.config.expire_after_hours}h TTL",
                })
                expired += 1

        return expired

    # ------------------------------------------------------------------
    # rotate
    # ------------------------------------------------------------------

    def rotate_if_needed(self) -> bool:
        """
        Rotate the ledger file if it exceeds max_size_mb.

        Returns True if rotation happened.
        Thread-safe with file locking.
        """
        with self._lock:
            if not self._path.exists():
                return False
            size_mb = self._path.stat().st_size / (1024 * 1024)
            if size_mb <= self.config.max_size_mb:
                return False
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            rotated = self._path.with_suffix(f".{ts}.jsonl")
            try:
                shutil.move(str(self._path), str(rotated))
                logger.info("IntentLedger rotated: %s -> %s", self._path, rotated)
                return True
            except Exception as exc:
                logger.error("IntentLedger.rotate failed: %s", exc)
                return False

    # ------------------------------------------------------------------
    # stats helper
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return summary stats for the /stats endpoint."""
        exists = self._path.exists()
        size = self._path.stat().st_size if exists else 0
        records = self.load_all(limit=10000)
        pending = sum(1 for r in records if r.get("status") == "pending")
        return {
            "path": str(self._path),
            "exists": exists,
            "size_bytes": size,
            "total_records": len(records),
            "pending_records": pending,
        }


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

INTENT_LEDGER = IntentLedger()

# Backward-compatible aliases so existing code that imports the old names still works
TaskLedger = IntentLedger
TASK_LEDGER = INTENT_LEDGER
