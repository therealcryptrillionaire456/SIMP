"""
Security Audit Log

Append-only audit logging for security-relevant events.
NEVER logs API keys, private key material, or payment credentials.
"""

import json
import os
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List


logger = logging.getLogger("SIMP.SecurityAudit")

# Fields that must NEVER appear in audit log entries
_SENSITIVE_FIELDS = frozenset({
    "api_key", "apikey", "api_secret", "secret_key", "private_key",
    "password", "passphrase", "token", "access_token", "refresh_token",
    "authorization", "credential", "credentials", "secret",
    "private_key_pem", "key_material",
})


def _redact_sensitive(details: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive fields from event details."""
    if not isinstance(details, dict):
        return details
    redacted = {}
    for k, v in details.items():
        if k.lower() in _SENSITIVE_FIELDS:
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = _redact_sensitive(v)
        else:
            redacted[k] = v
    return redacted


class SecurityAuditLog:
    """Append-only security audit log.

    Writes events to data/security_audit.jsonl in JSONL format.
    Thread-safe.
    """

    # Valid event types
    VALID_EVENT_TYPES = frozenset({
        "auth_failed",
        "rate_limited",
        "agent_registered",
        "agent_deregistered",
        "intent_rejected",
        "rollback_triggered",
        "validation_error",
        "security_header_violation",
    })

    # Valid severity levels
    VALID_SEVERITIES = frozenset({
        "low",
        "medium",
        "high",
        "critical",
    })

    def __init__(self, log_dir: str = "data"):
        """Initialize the audit log.

        Args:
            log_dir: Directory for the audit log file.
        """
        self._log_dir = log_dir
        self._log_path = os.path.join(log_dir, "security_audit.jsonl")
        self._lock = threading.Lock()

        # Ensure directory exists
        os.makedirs(log_dir, exist_ok=True)

        logger.info(f"Security audit log initialized: {self._log_path}")

    @property
    def log_path(self) -> str:
        return self._log_path

    def log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        severity: str = "medium",
    ) -> Dict[str, Any]:
        """Log a security event.

        Args:
            event_type: Type of security event (e.g., "auth_failed").
            details: Event details dict. Sensitive fields are auto-redacted.
            severity: One of "low", "medium", "high", "critical".

        Returns:
            The logged event dict.
        """
        if event_type not in self.VALID_EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}, logging anyway")

        if severity not in self.VALID_SEVERITIES:
            severity = "medium"

        # Redact sensitive fields
        safe_details = _redact_sensitive(details)

        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "severity": severity,
            "details": safe_details,
        }

        with self._lock:
            try:
                with open(self._log_path, "a") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

        return event

    def get_events(
        self,
        severity: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Read events from audit log with optional filtering.

        Args:
            severity: Filter by severity level.
            event_type: Filter by event type.
            limit: Maximum number of events to return (most recent first).

        Returns:
            List of event dicts.
        """
        events = []

        with self._lock:
            if not os.path.exists(self._log_path):
                return []

            try:
                with open(self._log_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            # Apply filters
                            if severity and event.get("severity") != severity:
                                continue
                            if event_type and event.get("event_type") != event_type:
                                continue
                            events.append(event)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"Failed to read audit log: {e}")

        # Return most recent first, limited
        return events[-limit:][::-1] if events else []

    def clear(self) -> None:
        """Clear the audit log (for testing only)."""
        with self._lock:
            if os.path.exists(self._log_path):
                os.remove(self._log_path)


# Module-level singleton
_audit_log: Optional[SecurityAuditLog] = None


def get_audit_log(log_dir: str = "data") -> SecurityAuditLog:
    """Get or create the singleton audit log instance."""
    global _audit_log
    if _audit_log is None:
        _audit_log = SecurityAuditLog(log_dir=log_dir)
    return _audit_log
