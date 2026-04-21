"""
simp/audit/audit_logger.py
───────────────────────────
Thread-safe, SQLite-backed audit logger for SIMP security events.

Usage:
    from simp.audit.audit_logger import get_audit_logger
    audit = get_audit_logger()
    audit.log_intent(agent_id="my-agent", intent_id="abc", ...)

The logger is a process-wide singleton; call get_audit_logger() anywhere.
Configure the DB path via the SIMP_AUDIT_DB_PATH environment variable or
the central config module.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _get_db_path() -> str:
    try:
        from config.config import config
        return config.AUDIT_DB_PATH
    except Exception:
        fallback = Path(__file__).resolve().parents[2] / "var" / "simp_audit.db"
        return os.environ.get("SIMP_AUDIT_DB_PATH", str(fallback))


class AuditLogger:
    """
    Persistent, multi-thread-safe audit log backed by SQLite.

    All writes are serialized via a reentrant lock so concurrent requests
    never corrupt the database. Connection is created once per instance
    with check_same_thread=False (safe because we use our own lock).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or _get_db_path()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ── internal ──────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=10,
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp     TEXT    NOT NULL,
                    event_type    TEXT    NOT NULL,
                    agent_id      TEXT,
                    intent_id     TEXT,
                    correlation_id TEXT,
                    status        TEXT    NOT NULL,
                    details       TEXT,
                    ip_address    TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_agent
                    ON audit_log(agent_id);
                CREATE INDEX IF NOT EXISTS idx_audit_event_type
                    ON audit_log(event_type);
            """)
            conn.commit()
        logger.debug("Audit log initialized at %s", self.db_path)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_details(self, details: Optional[Dict[str, Any]]) -> Optional[str]:
        """Serialize details, stripping any keys that look like secrets."""
        if details is None:
            return None
        REDACT_KEYS = {"password", "secret", "token", "key", "private_key",
                       "api_key", "signature", "credential"}
        sanitized = {
            k: ("***REDACTED***" if k.lower() in REDACT_KEYS else v)
            for k, v in details.items()
        }
        try:
            return json.dumps(sanitized)
        except (TypeError, ValueError) as exc:
            logger.warning("Could not serialize audit details: %s", exc)
            return json.dumps({"_error": "details not serializable"})

    def _write(self, row: tuple) -> None:
        with self._lock:
            try:
                conn = self._connect()
                conn.execute(
                    """INSERT INTO audit_log
                       (timestamp, event_type, agent_id, intent_id,
                        correlation_id, status, details, ip_address)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    row,
                )
                conn.commit()
            except sqlite3.Error as exc:
                # Never let audit failures crash the caller
                logger.error("Audit log write failed: %s", exc, exc_info=True)

    # ── public API ────────────────────────────────────────────────────────

    def log_intent(
        self,
        *,
        agent_id: str,
        intent_id: str,
        event_type: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Record an intent routing event."""
        self._write((
            self._now(), event_type, agent_id, intent_id,
            correlation_id, status, self._safe_details(details), ip_address,
        ))

    def log_security_event(
        self,
        *,
        event_type: str,
        agent_id: Optional[str] = None,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Record a security-relevant event (auth failure, bad signature, etc.)."""
        self._write((
            self._now(), event_type, agent_id, None,
            correlation_id, status, self._safe_details(details), ip_address,
        ))

    def log_agent_lifecycle(
        self,
        *,
        agent_id: str,
        event_type: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record agent registration / deregistration events."""
        self._write((
            self._now(), event_type, agent_id, None,
            None, status, self._safe_details(details), None,
        ))

    def close(self) -> None:
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except sqlite3.Error as exc:
                    logger.warning("Error closing audit DB connection: %s", exc)
                finally:
                    self._conn = None


# ── process-wide singleton ────────────────────────────────────────────────────

_singleton_lock = threading.Lock()
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db_path: Optional[str] = None) -> AuditLogger:
    """Return (and lazily create) the process-wide AuditLogger singleton."""
    global _audit_logger
    if _audit_logger is None:
        with _singleton_lock:
            if _audit_logger is None:
                _audit_logger = AuditLogger(db_path=db_path)
    return _audit_logger
