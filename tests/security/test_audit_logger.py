"""
tests/security/test_audit_logger.py
─────────────────────────────────────
Tests for simp/audit/audit_logger.py

Run: pytest tests/security/test_audit_logger.py -v
"""

import json
import sqlite3
import tempfile
import threading
from pathlib import Path

import pytest

from simp.audit.audit_logger import AuditLogger


@pytest.fixture()
def audit(tmp_path):
    """Fresh AuditLogger backed by a temp SQLite file."""
    db = str(tmp_path / "test_audit.db")
    logger = AuditLogger(db_path=db)
    yield logger
    logger.close()


def _read_all(audit: AuditLogger) -> list[dict]:
    conn = sqlite3.connect(audit.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── basic writes ─────────────────────────────────────────────────────────────

def test_log_intent_writes_row(audit):
    audit.log_intent(
        agent_id="test-agent",
        intent_id="int-001",
        event_type="INTENT_ROUTED",
        status="OK",
        details={"target": "other-agent"},
        ip_address="10.0.0.1",
    )
    rows = _read_all(audit)
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "test-agent"
    assert rows[0]["intent_id"] == "int-001"
    assert rows[0]["event_type"] == "INTENT_ROUTED"
    assert rows[0]["status"] == "OK"


def test_log_security_event_writes_row(audit):
    audit.log_security_event(
        event_type="AUTH_FAILURE",
        agent_id="bad-agent",
        status="REJECTED",
        details={"reason": "invalid key"},
    )
    rows = _read_all(audit)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "AUTH_FAILURE"


def test_log_agent_lifecycle(audit):
    audit.log_agent_lifecycle(
        agent_id="my-agent", event_type="AGENT_REGISTERED", status="OK"
    )
    rows = _read_all(audit)
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "my-agent"


# ── secret redaction ──────────────────────────────────────────────────────────

def test_secret_keys_are_redacted(audit):
    audit.log_intent(
        agent_id="a",
        intent_id="i",
        event_type="E",
        status="OK",
        details={
            "password": "super-secret",
            "token": "my-token",
            "api_key": "key-123",
            "safe_field": "hello",
        },
    )
    rows = _read_all(audit)
    details = json.loads(rows[0]["details"])
    assert details["password"] == "***REDACTED***"
    assert details["token"] == "***REDACTED***"
    assert details["api_key"] == "***REDACTED***"
    assert details["safe_field"] == "hello"


# ── thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_writes(audit):
    """1000 concurrent writes should not corrupt the database."""
    errors = []

    def writer(i):
        try:
            audit.log_intent(
                agent_id=f"agent-{i}",
                intent_id=f"intent-{i}",
                event_type="STRESS_TEST",
                status="OK",
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(1000)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Concurrent write errors: {errors}"
    rows = _read_all(audit)
    assert len(rows) == 1000


# ── error handling ────────────────────────────────────────────────────────────

def test_non_serializable_details_handled_gracefully(audit):
    """Logger should not crash on non-serializable detail values."""
    audit.log_intent(
        agent_id="a",
        intent_id="i",
        event_type="E",
        status="OK",
        details={"obj": object()},  # not JSON serializable
    )
    rows = _read_all(audit)
    assert len(rows) == 1  # row was written despite bad details
