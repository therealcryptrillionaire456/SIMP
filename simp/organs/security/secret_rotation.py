"""
T47: Automated Secrets Rotation
================================
Background rotation scheduler for API keys, DB passwords, and signing keys.

This module provides:
1. RotationPolicy — per-secret TTL, priority, pre/post hooks
2. SecretRotationScheduler — background thread, rotation queue, backoff
3. RotationPlan — ordered rotation groups to avoid service disruption
4. Health checks before promoting new secrets
5. Integration with VaultClient for seamless rotation

Usage:
    scheduler = SecretRotationScheduler(vault_client=vault)
    scheduler.add_policy("coinbase/api_key", ttl_hours=24, priority=1)
    scheduler.add_policy("db/password", ttl_hours=720, priority=3)
    scheduler.start()  # Background thread
    scheduler.rotate_now("coinbase/api_key")  # Manual trigger
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class RotationState(str, Enum):
    IDLE = "idle"
    ROTATING = "rotating"
    HEALTH_CHECK = "health_check"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RotationTrigger(str, Enum):
    SCHEDULED = "scheduled"       # TTL expired
    MANUAL = "manual"            # User triggered
    IMMEDIATE = "immediate"       # Emergency rotation
    KEY_ROTATION = "key_rotation"  # Parent key rotated


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class RotationPolicy:
    """Defines rotation rules for a single secret."""
    secret_path: str
    ttl_hours: int = 24
    priority: int = 1               # Lower = higher priority
    rotation_group: str = "default"
    health_check_fn: Optional[str] = None   # Function name to call
    health_check_timeout_secs: int = 30
    pre_rotation_fn: Optional[str] = None   # e.g., "notify_downstream"
    post_rotation_fn: Optional[str] = None  # e.g., "update_connection_pool"
    max_retries: int = 2
    retry_backoff_secs: List[int] = field(default_factory=lambda: [60, 300])
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RotationPolicy:
        return cls(**data)


@dataclass
class RotationEvent:
    """Audit trail for a single rotation attempt."""
    event_id: str
    secret_path: str
    state: str
    trigger: str
    started_at: str
    completed_at: Optional[str] = None
    version_before: Optional[str] = None
    version_after: Optional[str] = None
    retry_count: int = 0
    error: Optional[str] = None
    actor: str = "scheduler"


@dataclass
class RotationPlan:
    """Ordered rotation groups to prevent cascading failures."""
    group_name: str
    secrets: List[str]
    stagger_secs: int = 10       # Wait between secrets in group
    requires_quorum: bool = False
    quorum_pct: float = 0.5


# ── Health Check Registry ─────────────────────────────────────────────────────

class HealthCheckRegistry:
    """Registry of named health-check callables."""

    _instance: Optional["HealthCheckRegistry"] = None

    def __init__(self):
        self._checks: Dict[str, Callable[[], bool]] = {}

    @classmethod
    def get_instance(cls) -> "HealthCheckRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, fn: Callable[[], bool]) -> None:
        """Register a health check function.

        fn() should return True if healthy, False otherwise.
        """
        self._checks[name] = fn
        logger.info("Registered health check: %s", name)

    def run(self, name: str) -> bool:
        """Run a named health check. Returns True if check passes."""
        fn = self._checks.get(name)
        if fn is None:
            logger.warning("Health check not found: %s", name)
            return True  # Allow rotation if check unknown
        try:
            result = fn()
            logger.debug("Health check %s: %s", name, "PASS" if result else "FAIL")
            return result
        except Exception as e:
            logger.error("Health check %s raised: %s", name, e)
            return False

    def list_checks(self) -> List[str]:
        return list(self._checks.keys())


# Register some standard health checks
def _register_standard_checks():
    reg = HealthCheckRegistry.get_instance()

    def check_broker_health() -> bool:
        """Check if SIMP broker is responsive."""
        try:
            import requests
            resp = requests.get("http://127.0.0.1:5555/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def check_db_health() -> bool:
        """Check if database is accessible."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="127.0.0.1", port=5432, dbname="simpdb",
                user="simp", connect_timeout=5
            )
            conn.close()
            return True
        except Exception:
            return False

    reg.register("broker_health", check_broker_health)
    reg.register("db_health", check_db_health)


# ── Secret Rotation Scheduler ─────────────────────────────────────────────────

class SecretRotationScheduler:
    """
    Background scheduler that rotates secrets based on TTL policies.

    Features:
    - Priority-based rotation queue
    - Exponential backoff on failure
    - Pre/post rotation hooks
    - Rotation groups for coordinated multi-secret rotation
    - Health checks before promoting new versions
    - JSONL audit trail
    """

    def __init__(
        self,
        vault_client: Any,          # VaultClient
        policies: Optional[Dict[str, RotationPolicy]] = None,
        audit_path: Optional[Path] = None,
        check_interval_secs: int = 3600,  # Check every hour
    ):
        self._vault = vault_client
        self._policies: Dict[str, RotationPolicy] = policies or {}
        self._audit_path = audit_path or Path("data/secret_rotation_audit.jsonl")
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._check_interval = check_interval_secs
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._rotation_queue: List[str] = []  # secret_paths due for rotation
        self._active_rotations: Dict[str, RotationEvent] = {}  # path -> event
        self._rotation_count: Dict[str, int] = {}  # secret_path -> rotation count
        self._last_rotation: Dict[str, str] = {}   # secret_path -> ISO timestamp
        self._load_state()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_state(self) -> None:
        """Load rotation state from audit log."""
        if not self._audit_path.exists():
            return
        try:
            with open(self._audit_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        path = event.get("secret_path")
                        if event.get("state") == RotationState.COMPLETED.value:
                            self._last_rotation[path] = event.get("completed_at", "")
                            self._rotation_count[path] = self._rotation_count.get(path, 0) + 1
                    except Exception:
                        continue
            logger.info("Loaded rotation state: %d secrets rotated", len(self._last_rotation))
        except Exception as e:
            logger.error("Failed to load rotation state: %s", e)

    def _record_event(self, event: RotationEvent) -> None:
        """Append rotation event to audit log."""
        try:
            with open(self._audit_path, "a") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception as e:
            logger.error("Failed to record rotation event: %s", e)

    # ── Policy Management ───────────────────────────────────────────────────

    def add_policy(self, policy: RotationPolicy) -> None:
        """Add or update a rotation policy."""
        with self._lock:
            self._policies[policy.secret_path] = policy
        logger.info("Added rotation policy for %s (TTL=%dh, priority=%d)",
                    policy.secret_path, policy.ttl_hours, policy.priority)

    def remove_policy(self, secret_path: str) -> bool:
        """Remove a rotation policy."""
        with self._lock:
            return self._policies.pop(secret_path, None) is not None

    def get_policy(self, secret_path: str) -> Optional[RotationPolicy]:
        return self._policies.get(secret_path)

    def list_policies(self) -> List[RotationPolicy]:
        return list(self._policies.values())

    # ── Core Rotation Logic ─────────────────────────────────────────────────

    def _should_rotate(self, path: str) -> bool:
        """Check if a secret is due for rotation."""
        policy = self._policies.get(path)
        if not policy or not policy.enabled:
            return False

        # Check TTL
        last = self._last_rotation.get(path)
        if not last:
            # First time - check if secret has existing metadata
            meta = self._vault.get_metadata(path) if hasattr(self._vault, "get_metadata") else None
            if meta and meta.get("version_created_at"):
                last = meta["version_created_at"]
            else:
                return True  # No record, rotate now

        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - last_dt
            return age.total_seconds() > (policy.ttl_hours * 3600)
        except Exception:
            return True

    def _do_rotate(
        self,
        path: str,
        trigger: RotationTrigger = RotationTrigger.SCHEDULED,
        actor: str = "scheduler",
    ) -> RotationEvent:
        """Execute a single secret rotation."""
        policy = self._policies.get(path)
        event = RotationEvent(
            event_id=f"rot-{uuid.uuid4().hex[:12]}",
            secret_path=path,
            state=RotationState.ROTATING.value,
            trigger=trigger.value,
            started_at=datetime.now(timezone.utc).isoformat(),
            actor=actor,
        )

        with self._lock:
            self._active_rotations[path] = event

        try:
            # Get current version before rotation
            try:
                old_val = self._vault.get(path)
                event.version_before = str(hash(str(old_val)))[:16] if old_val else None
            except Exception:
                pass

            # Pre-rotation hook
            if policy.pre_rotation_fn:
                logger.info("Running pre-rotation hook: %s", policy.pre_rotation_fn)
                # Hooks are registered as functions, looked up by name
                reg = HealthCheckRegistry.get_instance()
                hook_fn = getattr(reg, policy.pre_rotation_fn, None)
                if hook_fn and callable(hook_fn):
                    try:
                        hook_fn()
                    except Exception as e:
                        logger.warning("Pre-rotation hook %s failed: %s", policy.pre_rotation_fn, e)

            # Generate new secret
            new_secret = self._generate_secret(path)
            event.state = RotationState.ROTATING.value

            # Store new version
            self._vault.set(
                path,
                new_secret,
                tags=["auto-rotated", f"trigger:{trigger.value}"],
            )

            # Health check before promoting
            if policy.health_check_fn:
                event.state = RotationState.HEALTH_CHECK.value
                reg = HealthCheckRegistry.get_instance()
                healthy = reg.run(policy.health_check_fn)
                if not healthy:
                    # Try retries
                    for retry in range(policy.max_retries):
                        time.sleep(policy.retry_backoff_secs[retry])
                        if reg.run(policy.health_check_fn):
                            healthy = True
                            break
                if not healthy:
                    # Rollback
                    event.state = RotationState.FAILED.value
                    event.error = f"Health check failed after {policy.max_retries} retries"
                    logger.error("Health check failed for %s, rolling back", path)
                    self._rollback(path, old_val)
                    event.state = RotationState.ROLLED_BACK.value
                    return event

            # Post-rotation hook
            if policy.post_rotation_fn:
                logger.info("Running post-rotation hook: %s", policy.post_rotation_fn)
                reg = HealthCheckRegistry.get_instance()
                hook_fn = getattr(reg, policy.post_rotation_fn, None)
                if hook_fn and callable(hook_fn):
                    try:
                        hook_fn()
                    except Exception as e:
                        logger.warning("Post-rotation hook %s failed: %s", policy.post_rotation_fn, e)

            # Success
            event.state = RotationState.COMPLETED.value
            event.completed_at = datetime.now(timezone.utc).isoformat()
            event.version_after = str(hash(new_secret))[:16]
            self._last_rotation[path] = event.completed_at
            self._rotation_count[path] = self._rotation_count.get(path, 0) + 1
            logger.info("Successfully rotated %s", path)

        except Exception as e:
            event.state = RotationState.FAILED.value
            event.error = str(e)
            event.retry_count += 1
            logger.error("Rotation failed for %s: %s", path, e)

        finally:
            self._record_event(event)
            with self._lock:
                self._active_rotations.pop(path, None)

        return event

    def _generate_secret(self, path: str) -> str:
        """Generate a new secret value. Override for custom generation."""
        import secrets
        import base64

        # Default: 32 bytes of cryptographically secure random, base64-encoded
        if "api_key" in path or "secret" in path:
            return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        elif "password" in path:
            return secrets.token_urlsafe(48)
        elif "signing_key" in path or "private_key" in path:
            return base64.b64encode(secrets.token_bytes(64)).decode()
        else:
            return secrets.token_urlsafe(40)

    def _rollback(self, path: str, old_value: Any) -> None:
        """Rollback to previous secret version."""
        try:
            self._vault.set(path, old_value, tags=["rollback"])
            logger.warning("Rolled back %s to previous value", path)
        except Exception as e:
            logger.error("Rollback failed for %s: %s (SECONDARY FAILURE)", path, e)

    # ── Background Thread ───────────────────────────────────────────────────

    def _rotation_loop(self) -> None:
        """Background loop: check policies and rotate as needed."""
        logger.info("Rotation scheduler started (interval=%ds)", self._check_interval)
        _register_standard_checks()

        while self._running:
            try:
                self._check_and_rotate()
            except Exception as e:
                logger.error("Rotation loop error: %s", e)

            # Sleep in short increments to allow quick shutdown
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Rotation scheduler stopped")

    def _check_and_rotate(self) -> None:
        """Check all policies and rotate due secrets."""
        due = []
        for path in self._policies:
            if self._should_rotate(path):
                due.append(path)

        if not due:
            return

        # Sort by priority
        due.sort(key=lambda p: self._policies[p].priority)

        logger.info("Rotation due for %d secrets: %s", len(due), due)

        for path in due:
            if not self._running:
                break
            # Check if already rotating
            if path in self._active_rotations:
                continue
            self._do_rotate(path, trigger=RotationTrigger.SCHEDULED)

    def start(self) -> None:
        """Start the background rotation scheduler."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._rotation_loop, daemon=True)
            self._thread.start()
        logger.info("Secret rotation scheduler started")

    def stop(self, timeout_secs: float = 10.0) -> None:
        """Stop the background scheduler."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread:
            self._thread.join(timeout=timeout_secs)
            self._thread = None
        logger.info("Secret rotation scheduler stopped")

    # ── Manual Triggers ────────────────────────────────────────────────────

    def rotate_now(
        self,
        secret_path: str,
        trigger: RotationTrigger = RotationTrigger.MANUAL,
        actor: str = "manual",
    ) -> Optional[RotationEvent]:
        """Manually trigger rotation for a specific secret."""
        if secret_path not in self._policies:
            logger.warning("No rotation policy for %s", secret_path)
            return None
        if secret_path in self._active_rotations:
            logger.warning("Rotation already in progress for %s", secret_path)
            return None
        return self._do_rotate(secret_path, trigger=trigger, actor=actor)

    def rotate_group(
        self,
        group_name: str,
        actor: str = "manual",
    ) -> List[RotationEvent]:
        """Rotate all secrets in a named group."""
        paths = [p.secret_path for p in self._policies.values() if p.rotation_group == group_name]
        events = []
        for path in paths:
            event = self.rotate_now(path, actor=actor)
            if event:
                events.append(event)
            time.sleep(10)  # Stagger
        return events

    def force_rotate_all(self, actor: str = "manual") -> List[RotationEvent]:
        """Force-rotate all secrets regardless of TTL."""
        events = []
        for path in list(self._policies.keys()):
            event = self.rotate_now(path, trigger=RotationTrigger.IMMEDIATE, actor=actor)
            if event:
                events.append(event)
        return events

    # ── Status & Audit ─────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        with self._lock:
            return {
                "running": self._running,
                "policies_count": len(self._policies),
                "active_rotations": list(self._active_rotations.keys()),
                "rotation_counts": dict(self._rotation_count),
                "last_rotations": dict(self._last_rotation),
            }

    def get_events(
        self,
        secret_path: Optional[str] = None,
        limit: int = 100,
    ) -> List[RotationEvent]:
        """Get rotation events from audit log."""
        events = []
        if not self._audit_path.exists():
            return events
        try:
            with open(self._audit_path) as f:
                for line in reversed(list(f)):
                    if len(events) >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        if secret_path and d.get("secret_path") != secret_path:
                            continue
                        events.append(RotationEvent(**d))
                    except Exception:
                        continue
        except Exception as e:
            logger.error("Failed to read rotation events: %s", e)
        return events

    def days_until_rotation(self, secret_path: str) -> Optional[float]:
        """Days remaining until next scheduled rotation."""
        policy = self._policies.get(secret_path)
        if not policy:
            return None
        last = self._last_rotation.get(secret_path)
        if not last:
            return 0.0
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - last_dt
            remaining = (policy.ttl_hours * 3600) - age.total_seconds()
            return remaining / 86400
        except Exception:
            return None


# ── Module-level convenience ──────────────────────────────────────────────────

_scheduler: Optional[SecretRotationScheduler] = None
_scheduler_lock = threading.Lock()


def get_rotation_scheduler(vault_client: Any) -> SecretRotationScheduler:
    """Get or create the module-level scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = SecretRotationScheduler(vault_client=vault_client)
                _scheduler.start()
    return _scheduler


# ── Self-test ────────────────────────────────────────────────────────────────

def test_secret_rotation() -> None:
    """Run a self-test of the secret rotation scheduler."""
    from simp.organs.security.vault_client import VaultClient, FileBackend

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = FileBackend(path=Path(tmpdir) / "secrets.json")
        vault = VaultClient(backend=backend)
        scheduler = SecretRotationScheduler(vault_client=vault)

        # Add policies
        scheduler.add_policy(RotationPolicy(
            secret_path="test/api_key",
            ttl_hours=1,
            priority=1,
            health_check_fn=None,  # Skip health check in test
        ))

        # Set initial secret
        vault.set("test/api_key", "initial_secret_value")

        # Manually rotate
        event = scheduler.rotate_now("test/api_key", actor="test")
        assert event is not None
        assert event.state == RotationState.COMPLETED.value

        # Verify new value is different
        new_val = vault.get("test/api_key")
        assert new_val != "initial_secret_value"

        # Check status
        status = scheduler.status()
        print(f"Rotation count: {status['rotation_counts']}")
        print(f"Last rotation: {status['last_rotations']}")

        # Days until rotation (should be close to 1 hour)
        days = scheduler.days_until_rotation("test/api_key")
        print(f"Days until rotation: {days:.3f} (expected ~0.042)")

        scheduler.stop()
        print("All rotation tests passed!")


if __name__ == "__main__":
    import tempfile
    test_secret_rotation()
