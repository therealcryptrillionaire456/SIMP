"""
patches/broker_patch.py
─────────────────────────
Drop-in replacement sections for broker.py.

Issues addressed:
  #2  Enforce cryptographic signature verification
  #3  Plaintext agent secrets storage
  #7  Race conditions / TOCTOU (thread safety)
  #14 Logging obfuscation
  #15 Intent TTL / memory leak
  #17 Distributed tracing / correlation IDs
  #18 Agent health checks / self-healing
"""

# ─────────────────────────────────────────────────────────────────────────────
# NEW IMPORTS (add near top of broker.py)
# ─────────────────────────────────────────────────────────────────────────────
NEW_IMPORTS = """
import threading
import uuid
from datetime import datetime, timezone, timedelta

try:
    from config.config import config as _cfg
    _REQUIRE_SIGS        = _cfg.REQUIRE_SIGNATURES
    _INTENT_TTL          = _cfg.INTENT_TTL_SECONDS
    _CLEANUP_INTERVAL    = _cfg.INTENT_CLEANUP_INTERVAL
    _HEALTH_INTERVAL     = _cfg.HEALTH_CHECK_INTERVAL
    _HEALTH_TIMEOUT      = _cfg.HEALTH_CHECK_TIMEOUT
    _HEALTH_FAIL_MAX     = _cfg.HEALTH_CHECK_FAIL_THRESHOLD
    _OBFUSCATE_IPS       = _cfg.OBFUSCATE_IPS
    _MAX_AGENTS          = _cfg.MAX_AGENTS
except Exception:
    import os
    _REQUIRE_SIGS     = os.environ.get("SIMP_REQUIRE_SIGNATURES", "true") == "true"
    _INTENT_TTL       = int(os.environ.get("SIMP_INTENT_TTL", "3600"))
    _CLEANUP_INTERVAL = int(os.environ.get("SIMP_CLEANUP_INTERVAL", "300"))
    _HEALTH_INTERVAL  = float(os.environ.get("SIMP_HEALTH_CHECK_INTERVAL", "30"))
    _HEALTH_TIMEOUT   = float(os.environ.get("SIMP_HEALTH_CHECK_TIMEOUT", "5"))
    _HEALTH_FAIL_MAX  = int(os.environ.get("SIMP_HEALTH_FAIL_THRESHOLD", "3"))
    _OBFUSCATE_IPS    = os.environ.get("SIMP_OBFUSCATE_IPS", "true") == "true"
    _MAX_AGENTS       = int(os.environ.get("SIMP_MAX_AGENTS", "100"))

from simp.security.log_utils import obfuscate_endpoint, safe_agent_id
from simp.audit.audit_logger import get_audit_logger

_audit = get_audit_logger()
"""

# ─────────────────────────────────────────────────────────────────────────────
# THREAD-SAFE AGENT REGISTRY  (replace the plain dict in __init__)
# ─────────────────────────────────────────────────────────────────────────────
THREAD_SAFE_INIT_ADDITIONS = '''
# In SimpBroker.__init__, replace bare dict assignments with these:

# ── agent registry ──────────────────────────────────────────────────────────
self._agent_lock   = threading.RLock()
self._agents: dict = {}          # non-sensitive metadata keyed by agent_id
self._secrets: dict = {}         # sensitive data (keys, tokens) — never logged
self._health_failures: dict = {} # agent_id → consecutive failure count

# ── intent store ────────────────────────────────────────────────────────────
self._intent_lock    = threading.RLock()
self._intent_records: dict = {}  # intent_id → {data, timestamp, status}

# ── stats (atomic via lock) ─────────────────────────────────────────────────
self._stats_lock  = threading.RLock()
self._stats: dict = {"routed": 0, "rejected": 0, "errors": 0}

# ── background threads ───────────────────────────────────────────────────────
self._cleanup_thread = threading.Thread(
    target=self._cleanup_expired_intents, daemon=True, name="simp-intent-cleanup"
)
self._cleanup_thread.start()

self._health_thread = threading.Thread(
    target=self._monitor_agent_health, daemon=True, name="simp-health-check"
)
self._health_thread.start()
'''

# ─────────────────────────────────────────────────────────────────────────────
# THREAD-SAFE AGENT REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────
REGISTER_AGENT = '''
def register_agent(self, agent_id: str, endpoint: str,
                   public_key: str = None, capabilities: dict = None,
                   **kwargs) -> dict:
    """Register or update an agent.  Sensitive fields are stored separately."""
    with self._agent_lock:
        if len(self._agents) >= _MAX_AGENTS and agent_id not in self._agents:
            self.logger.warning(
                "Agent registry full (%d/%d); rejecting %s",
                len(self._agents), _MAX_AGENTS, safe_agent_id(agent_id),
            )
            return {"status": "error", "error_code": "REGISTRY_FULL"}

        # ── non-sensitive metadata ──────────────────────────────────────────
        self._agents[agent_id] = {
            "agent_id": agent_id,
            "endpoint": endpoint,           # stored but obfuscated in logs
            "capabilities": capabilities or {},
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "healthy": True,
        }
        # ── sensitive data ─────────────────────────────────────────────────
        if public_key:
            self._secrets[agent_id] = {"public_key": public_key}

        self._health_failures[agent_id] = 0

    self.logger.info(
        "Agent registered: %s at %s",
        safe_agent_id(agent_id),
        obfuscate_endpoint(endpoint, enabled=_OBFUSCATE_IPS),
    )
    _audit.log_agent_lifecycle(
        agent_id=agent_id, event_type="AGENT_REGISTERED", status="OK",
        details={"endpoint_hash": obfuscate_endpoint(endpoint, enabled=True)},
    )
    return {"status": "ok"}


def deregister_agent(self, agent_id: str) -> None:
    with self._agent_lock:
        self._agents.pop(agent_id, None)
        self._secrets.pop(agent_id, None)
        self._health_failures.pop(agent_id, None)
    self.logger.info("Agent deregistered: %s", safe_agent_id(agent_id))
    _audit.log_agent_lifecycle(
        agent_id=agent_id, event_type="AGENT_DEREGISTERED", status="OK",
    )


def get_agent(self, agent_id: str) -> dict | None:
    """Return non-sensitive agent metadata, or None if not found."""
    with self._agent_lock:
        return dict(self._agents.get(agent_id, {})) or None


def get_agent_public_key(self, agent_id: str) -> str | None:
    """Return public key without exposing it in agent metadata."""
    with self._agent_lock:
        secrets = self._secrets.get(agent_id, {})
        return secrets.get("public_key")
'''

# ─────────────────────────────────────────────────────────────────────────────
# SIGNATURE VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
VERIFY_SIGNATURE = '''
def _verify_intent_signature(self, intent_data: dict) -> tuple[bool, str]:
    """
    Verify the cryptographic signature on an incoming intent.

    Returns (ok: bool, error_code: str).
    """
    if not _REQUIRE_SIGS:
        return True, ""

    source_agent = intent_data.get("source_agent")
    if not source_agent:
        return False, "MISSING_SOURCE_AGENT"

    # Source agent must be registered
    with self._agent_lock:
        agent_info = self._agents.get(source_agent)
        public_key_pem = self._secrets.get(source_agent, {}).get("public_key")

    if not agent_info:
        self.logger.warning(
            "Intent from unknown agent: %s", safe_agent_id(source_agent)
        )
        return False, "UNKNOWN_AGENT"

    if not public_key_pem:
        self.logger.warning(
            "No public key registered for agent: %s", safe_agent_id(source_agent)
        )
        return False, "NO_PUBLIC_KEY"

    if not intent_data.get("signature"):
        self.logger.warning(
            "Missing signature on intent from %s", safe_agent_id(source_agent)
        )
        return False, "MISSING_SIGNATURE"

    try:
        from simp.crypto import SimpCrypto  # adjust to actual module path
        public_key = SimpCrypto.load_public_key(public_key_pem.encode())
        if not SimpCrypto.verify_signature(intent_data, public_key):
            self.logger.warning(
                "Signature verification FAILED for intent from %s",
                safe_agent_id(source_agent),
            )
            return False, "SIGNATURE_VERIFICATION_FAILED"
    except ImportError:
        self.logger.error(
            "simp.crypto not available; cannot verify signature", exc_info=True
        )
        return False, "CRYPTO_UNAVAILABLE"
    except Exception as exc:
        self.logger.error(
            "Error verifying signature from %s: %s",
            safe_agent_id(source_agent), exc, exc_info=True,
        )
        return False, "SIGNATURE_ERROR"

    return True, ""
'''

# ─────────────────────────────────────────────────────────────────────────────
# ROUTE INTENT  (thread-safe, with tracing, signature check, audit logging)
# ─────────────────────────────────────────────────────────────────────────────
ROUTE_INTENT = '''
def route_intent(self, intent_data: dict, source_ip: str = None) -> dict:
    """
    Route an intent from source_agent → target_agent.
    Thread-safe; adds correlation/trace IDs; verifies signatures; audits result.
    """
    # ── distributed tracing IDs ─────────────────────────────────────────────
    intent_data.setdefault("correlation_id", str(uuid.uuid4()))
    intent_data.setdefault("trace_id", str(uuid.uuid4()))
    correlation_id = intent_data["correlation_id"]
    intent_id = intent_data.get("intent_id", str(uuid.uuid4()))
    source_agent = intent_data.get("source_agent", "<unknown>")
    target_agent = intent_data.get("target_agent", "")

    self.logger.info(
        "Routing intent intent_id=%s correlation_id=%s source=%s target=%s",
        intent_id, correlation_id,
        safe_agent_id(source_agent), safe_agent_id(target_agent),
    )

    # ── signature verification ───────────────────────────────────────────────
    ok, error_code = self._verify_intent_signature(intent_data)
    if not ok:
        with self._stats_lock:
            self._stats["rejected"] += 1
        _audit.log_security_event(
            event_type="SIGNATURE_FAILURE",
            agent_id=source_agent,
            status="REJECTED",
            details={"error_code": error_code, "intent_id": intent_id},
            ip_address=obfuscate_endpoint(source_ip, enabled=_OBFUSCATE_IPS),
            correlation_id=correlation_id,
        )
        return {"status": "error", "error_code": error_code,
                "correlation_id": correlation_id}

    # ── store intent record (thread-safe) ────────────────────────────────────
    with self._intent_lock:
        self._intent_records[intent_id] = {
            "data": intent_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "PENDING",
        }

    # ── look up target agent (under lock to avoid TOCTOU) ────────────────────
    with self._agent_lock:
        target_info = self._agents.get(target_agent)

    if not target_info:
        self.logger.warning(
            "Target agent not found: %s (correlation_id=%s)",
            safe_agent_id(target_agent), correlation_id,
        )
        with self._intent_lock:
            if intent_id in self._intent_records:
                self._intent_records[intent_id]["status"] = "FAILED_NO_TARGET"
        with self._stats_lock:
            self._stats["rejected"] += 1
        return {"status": "error", "error_code": "TARGET_NOT_FOUND",
                "correlation_id": correlation_id}

    # ── dispatch (implement your actual delivery here) ───────────────────────
    try:
        # TODO: replace with actual intent delivery mechanism
        # result = self._deliver_intent(target_info, intent_data)

        with self._intent_lock:
            if intent_id in self._intent_records:
                self._intent_records[intent_id]["status"] = "DELIVERED"
        with self._stats_lock:
            self._stats["routed"] += 1

        _audit.log_intent(
            agent_id=source_agent, intent_id=intent_id,
            event_type="INTENT_ROUTED", status="OK",
            details={"target": target_agent},
            ip_address=obfuscate_endpoint(source_ip, enabled=_OBFUSCATE_IPS),
            correlation_id=correlation_id,
        )
        return {"status": "ok", "correlation_id": correlation_id}

    except Exception as exc:
        self.logger.error(
            "Failed to deliver intent intent_id=%s to %s: %s",
            intent_id, safe_agent_id(target_agent), exc, exc_info=True,
        )
        with self._intent_lock:
            if intent_id in self._intent_records:
                self._intent_records[intent_id]["status"] = "FAILED"
        with self._stats_lock:
            self._stats["errors"] += 1
        return {"status": "error", "error_code": "DELIVERY_FAILED",
                "correlation_id": correlation_id}
'''

# ─────────────────────────────────────────────────────────────────────────────
# INTENT TTL CLEANUP  (#15)
# ─────────────────────────────────────────────────────────────────────────────
CLEANUP_THREAD = '''
def _cleanup_expired_intents(self) -> None:
    """Background thread: removes intent records older than INTENT_TTL_SECONDS."""
    import time
    while getattr(self, "_running", True):
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=_INTENT_TTL)
            expired_ids = []

            with self._intent_lock:
                for iid, record in list(self._intent_records.items()):
                    try:
                        ts = datetime.fromisoformat(record["timestamp"])
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if ts < cutoff:
                            expired_ids.append(iid)
                    except (KeyError, ValueError):
                        expired_ids.append(iid)  # malformed — clean up

                for iid in expired_ids:
                    del self._intent_records[iid]

            if expired_ids:
                self.logger.debug(
                    "Intent cleanup: removed %d expired records", len(expired_ids)
                )
        except Exception as exc:
            self.logger.error(
                "Error in intent cleanup thread: %s", exc, exc_info=True
            )
        time.sleep(_CLEANUP_INTERVAL)
'''

# ─────────────────────────────────────────────────────────────────────────────
# AGENT HEALTH CHECKS  (#18)
# ─────────────────────────────────────────────────────────────────────────────
HEALTH_CHECK_THREAD = '''
def _monitor_agent_health(self) -> None:
    """Background thread: periodically ping registered agents."""
    import time
    import requests as _requests

    while getattr(self, "_running", True):
        time.sleep(_HEALTH_INTERVAL)
        try:
            with self._agent_lock:
                agents_snapshot = dict(self._agents)

            for agent_id, info in agents_snapshot.items():
                ok = self._ping_agent(info.get("endpoint", ""))
                with self._agent_lock:
                    if agent_id not in self._agents:
                        continue  # deregistered while we were pinging
                    if ok:
                        self._health_failures[agent_id] = 0
                        self._agents[agent_id]["healthy"] = True
                    else:
                        failures = self._health_failures.get(agent_id, 0) + 1
                        self._health_failures[agent_id] = failures
                        self._agents[agent_id]["healthy"] = False
                        self.logger.warning(
                            "Agent %s health check failed (%d/%d)",
                            safe_agent_id(agent_id), failures, _HEALTH_FAIL_MAX,
                        )
                        if failures >= _HEALTH_FAIL_MAX:
                            self.logger.error(
                                "Agent %s exceeded failure threshold; deregistering",
                                safe_agent_id(agent_id),
                            )
                            # Deregister outside the loop to avoid dict-changed-during-iteration
                            threading.Thread(
                                target=self.deregister_agent,
                                args=(agent_id,), daemon=True,
                            ).start()
        except Exception as exc:
            self.logger.error(
                "Error in health check thread: %s", exc, exc_info=True
            )


def _ping_agent(self, endpoint: str) -> bool:
    """Return True if the agent's /health endpoint responds 200."""
    if not endpoint:
        return False
    import requests as _requests
    try:
        resp = _requests.get(
            f"http://{endpoint}/health",
            timeout=_HEALTH_TIMEOUT,
        )
        return resp.status_code == 200
    except (OSError, Exception):  # catches requests exceptions too
        return False
'''
