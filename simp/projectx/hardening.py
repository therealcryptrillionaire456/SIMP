"""
ProjectX Hardening Layer

Central security and reliability primitives used throughout the projectx
module. Import from here rather than reimplementing in each file.

Primitives:
  CircuitBreaker  — open/half-open/closed state machine for external calls
  Watchdog        — monitors daemon threads; restarts them on silent death
  AtomicWriter    — fsync + rename for crash-safe file writes
  InputGuard      — validates and bounds-checks all external inputs
  CommandSanitizer — restricts run_shell to a safe pattern allowlist
  PayloadSchema   — validates mesh task payloads before deserialisation
  CorrelationCtx  — injects a correlation ID into log records

All primitives are dependency-free (stdlib only).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import tempfile
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Circuit Breaker ───────────────────────────────────────────────────────────

class BreakerState(Enum):
    CLOSED    = "closed"      # normal — calls pass through
    OPEN      = "open"        # failing — calls fail fast
    HALF_OPEN = "half_open"   # probing — one test call allowed


@dataclass
class BreakerConfig:
    failure_threshold: int   = 5      # consecutive failures before opening
    success_threshold: int   = 2      # consecutive successes to close from half-open
    timeout_seconds: float   = 60.0   # how long to stay open before half-open
    call_timeout: float      = 30.0   # max wall time for a single call


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the breaker is open."""


class CircuitBreaker:
    """
    Thread-safe circuit breaker.

    Usage::

        cb = CircuitBreaker("broker", BreakerConfig(failure_threshold=3))

        try:
            result = cb.call(requests.get, url, timeout=5)
        except CircuitBreakerOpen:
            # fail fast — use cached result or fallback
        except Exception as exc:
            # real error from the wrapped call
    """

    def __init__(self, name: str, config: Optional[BreakerConfig] = None) -> None:
        self.name = name
        self._cfg = config or BreakerConfig()
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()
        self._call_count = 0
        self._rejected_count = 0

    @property
    def state(self) -> BreakerState:
        return self._state

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        """Execute fn(*args, **kwargs) through the breaker."""
        with self._lock:
            if self._state == BreakerState.OPEN:
                if time.time() - self._opened_at >= self._cfg.timeout_seconds:
                    self._state = BreakerState.HALF_OPEN
                    self._success_count = 0
                    logger.info("[CB:%s] → HALF_OPEN (probing)", self.name)
                else:
                    self._rejected_count += 1
                    raise CircuitBreakerOpen(
                        f"Circuit '{self.name}' is OPEN — call rejected"
                    )

        self._call_count += 1
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state == BreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._cfg.success_threshold:
                    self._state = BreakerState.CLOSED
                    logger.info("[CB:%s] → CLOSED (recovered)", self.name)

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == BreakerState.HALF_OPEN:
                self._state = BreakerState.OPEN
                self._opened_at = time.time()
                logger.warning("[CB:%s] HALF_OPEN probe failed → OPEN", self.name)
            elif self._failure_count >= self._cfg.failure_threshold:
                self._state = BreakerState.OPEN
                self._opened_at = time.time()
                logger.warning(
                    "[CB:%s] %d failures → OPEN for %ds",
                    self.name, self._failure_count, int(self._cfg.timeout_seconds),
                )

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "calls": self._call_count,
                "rejected": self._rejected_count,
                "opened_at": self._opened_at or None,
            }

    def reset(self) -> None:
        with self._lock:
            self._state = BreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0


# ── Watchdog ──────────────────────────────────────────────────────────────────

class Watchdog:
    """
    Monitors a daemon thread and restarts it if it dies unexpectedly.

    Usage::

        def make_thread():
            t = threading.Thread(target=my_loop, daemon=True)
            t.start()
            return t

        wd = Watchdog("my_loop", make_thread, check_interval=15)
        wd.start()
        ...
        wd.stop()
    """

    def __init__(
        self,
        name: str,
        factory: Callable[[], threading.Thread],
        check_interval: float = 15.0,
        max_restarts: int = 10,
        cooldown: float = 5.0,
    ) -> None:
        self.name = name
        self._factory = factory
        self._interval = check_interval
        self._max_restarts = max_restarts
        self._cooldown = cooldown

        self._thread: Optional[threading.Thread] = None
        self._watcher: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._restart_count = 0
        self._last_restart: float = 0.0

    def start(self) -> None:
        self._thread = self._factory()
        self._stop.clear()
        self._watcher = threading.Thread(
            target=self._watch, daemon=True, name=f"Watchdog:{self.name}"
        )
        self._watcher.start()
        logger.debug("[Watchdog:%s] started", self.name)

    def stop(self) -> None:
        self._stop.set()

    def _watch(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(timeout=self._interval)
            if self._stop.is_set():
                break
            if self._thread and not self._thread.is_alive():
                if self._restart_count >= self._max_restarts:
                    logger.critical(
                        "[Watchdog:%s] max restarts (%d) reached — giving up",
                        self.name, self._max_restarts,
                    )
                    break
                # Cooldown before restart
                time.sleep(self._cooldown)
                self._restart_count += 1
                self._last_restart = time.time()
                logger.warning(
                    "[Watchdog:%s] thread dead — restarting (attempt %d/%d)",
                    self.name, self._restart_count, self._max_restarts,
                )
                try:
                    self._thread = self._factory()
                except Exception as exc:
                    logger.error("[Watchdog:%s] restart failed: %s", self.name, exc)

    @property
    def restart_count(self) -> int:
        return self._restart_count

    def status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "thread_alive": bool(self._thread and self._thread.is_alive()),
            "restart_count": self._restart_count,
            "last_restart": self._last_restart or None,
        }


# ── Atomic Writer ─────────────────────────────────────────────────────────────

class AtomicWriter:
    """
    Write files atomically: write to temp → fsync → rename.

    For JSONL append, use append_line() which also fsyncs.

    Usage::

        AtomicWriter.write_json(path, data)
        AtomicWriter.append_line(path, json_string)
    """

    @staticmethod
    def write_json(path: str | Path, data: Any, indent: int = 2) -> None:
        """Atomically overwrite a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=indent, default=str)
        AtomicWriter._atomic_write(path, text.encode())

    @staticmethod
    def write_text(path: str | Path, text: str) -> None:
        """Atomically overwrite a text file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        AtomicWriter._atomic_write(path, text.encode())

    @staticmethod
    def append_line(path: str | Path, line: str) -> None:
        """
        Append a line to a JSONL file with fsync.

        This is not atomic (appends can interleave) but each line is
        complete before fsync, so no partial writes survive a crash.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        dir_ = path.parent
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise


# ── Input Guard ───────────────────────────────────────────────────────────────

class InputGuardError(ValueError):
    """Raised when input fails validation."""


class InputGuard:
    """
    Validates and bounds-checks inputs before they enter the system.

    Usage::

        InputGuard.check_string(text, "content", max_len=10_000)
        InputGuard.check_url(url)
        InputGuard.check_dict(d, required=["action", "params"])
    """

    # Absolute maximum sizes
    MAX_CONTENT_BYTES = 128_000   # 128 KB per RAG entry
    MAX_PROMPT_BYTES  = 32_000    # 32 KB per prompt
    MAX_SHELL_CMD_LEN = 1_024     # 1 KB shell command
    MAX_URL_LEN       = 2_048

    @staticmethod
    def check_string(
        value: Any,
        field_name: str,
        max_len: int = MAX_CONTENT_BYTES,
        allow_empty: bool = False,
    ) -> str:
        if not isinstance(value, str):
            raise InputGuardError(f"{field_name}: expected str, got {type(value).__name__}")
        if not allow_empty and not value.strip():
            raise InputGuardError(f"{field_name}: must not be empty")
        if len(value.encode("utf-8")) > max_len:
            raise InputGuardError(
                f"{field_name}: exceeds {max_len} byte limit ({len(value.encode())} bytes)"
            )
        # Strip null bytes
        return value.replace("\x00", "")

    @staticmethod
    def check_url(url: Any) -> str:
        url = InputGuard.check_string(url, "url", max_len=InputGuard.MAX_URL_LEN)
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise InputGuardError(f"url: scheme '{parsed.scheme}' not allowed")
        if not parsed.netloc:
            raise InputGuardError("url: missing host")
        return url

    @staticmethod
    def check_dict(
        value: Any,
        field_name: str = "payload",
        required: Optional[List[str]] = None,
        max_depth: int = 10,
    ) -> Dict:
        if not isinstance(value, dict):
            raise InputGuardError(f"{field_name}: expected dict, got {type(value).__name__}")
        for key in (required or []):
            if key not in value:
                raise InputGuardError(f"{field_name}: missing required key '{key}'")
        InputGuard._check_depth(value, field_name, max_depth)
        return value

    @staticmethod
    def _check_depth(obj: Any, name: str, remaining: int) -> None:
        if remaining <= 0:
            raise InputGuardError(f"{name}: structure too deeply nested (max depth exceeded)")
        if isinstance(obj, dict):
            for v in obj.values():
                InputGuard._check_depth(v, name, remaining - 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                InputGuard._check_depth(item, name, remaining - 1)

    @staticmethod
    def sanitize_metadata(meta: Any) -> Dict:
        """Ensure metadata is a flat dict with string keys and safe scalar values."""
        if not isinstance(meta, dict):
            return {}
        result: Dict = {}
        for k, v in meta.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                result[k] = v
            else:
                result[k] = str(v)[:500]  # coerce complex types to truncated string
        return result


# ── Command Sanitizer ─────────────────────────────────────────────────────────

# Patterns that are NEVER allowed in shell commands regardless of tier
_BLOCKED_CMD_PATTERNS = re.compile(
    r"""
    (?:rm\s+-[rf]{1,3}\s+[/~])     # rm -rf /  or  rm -rf ~
    |(?:>\s*/etc/)                  # redirect into /etc
    |(?:curl\s.*\|\s*(?:bash|sh))  # curl | bash  (remote code exec)
    |(?:wget\s.*-O-\s.*\|\s*sh)    # wget | sh
    |(?:sudo\s)                     # sudo
    |(?:(?:^|\s)su\s)              # su (word-boundary, not 'sudo' prefix)
    |(?:chmod\s+[0-9]*7[0-9]*)    # world-writable chmod
    |(?:chown\s+root)              # chown to root
    |(?:dd\s+if=)                  # dd from device
    |(?:mkfs\b)                     # mkfs
    |(?::\s*\(\s*\)\s*\{)         # fork bomb
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Maximum command complexity (pipes + semicolons)
_MAX_CMD_OPERATORS = 5


class CommandSanitizer:
    """
    Validates a shell command before execution.

    Raises ValueError if the command matches blocked patterns or
    exceeds complexity limits.
    """

    @staticmethod
    def validate(command: str) -> str:
        """
        Validate and return the command, or raise ValueError.

        Does NOT guarantee safety — still use shell=False where possible.
        This is a defence-in-depth check against the most dangerous patterns.
        """
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Command must be a non-empty string")
        if len(command) > InputGuard.MAX_SHELL_CMD_LEN:
            raise ValueError(
                f"Command length {len(command)} exceeds {InputGuard.MAX_SHELL_CMD_LEN} char limit"
            )
        if _BLOCKED_CMD_PATTERNS.search(command):
            raise ValueError(f"Command matches blocked pattern: {command[:80]!r}")
        # Count pipe/semicolon operators
        op_count = command.count("|") + command.count(";") + command.count("&&") + command.count("||")
        if op_count > _MAX_CMD_OPERATORS:
            raise ValueError(
                f"Command has {op_count} chaining operators > allowed {_MAX_CMD_OPERATORS}"
            )
        return command

    @staticmethod
    def to_args(command: str) -> List[str]:
        """
        Split a validated command into argv for shell=False execution.
        Returns empty list if shlex parsing fails.
        """
        try:
            return shlex.split(command)
        except ValueError as exc:
            raise ValueError(f"Cannot parse command: {exc}") from exc


# ── Payload Schema Validator ──────────────────────────────────────────────────

_TASK_SCHEMA: Dict[str, type] = {
    "task_id":       str,
    "action":        str,
    "params":        dict,
    "requester_id":  str,
    "priority":      str,
    "timeout":       (int, float),
    "trust_required": (int, float),
}

_ALLOWED_PRIORITIES = frozenset({"low", "normal", "high", "critical"})


class PayloadSchema:
    """
    Validates mesh task payloads before deserialisation.

    Prevents action injection (e.g. injecting an action not in the
    remote allowlist) or type confusion attacks via malformed payloads.
    """

    @staticmethod
    def validate_task(payload: Any, allowed_actions: frozenset) -> Dict:
        """
        Validate a raw payload dict against the task schema.

        Returns the validated dict, or raises ValueError.
        """
        if not isinstance(payload, dict):
            raise ValueError(f"Task payload must be a dict, got {type(payload).__name__}")

        # Required fields
        action = payload.get("action", "")
        if not isinstance(action, str) or not action:
            raise ValueError("Task payload missing 'action' field")
        if action not in allowed_actions:
            raise ValueError(
                f"Action '{action}' not in remote allowlist "
                f"(allowed: {sorted(allowed_actions)})"
            )

        # Type checks
        for field_name, expected_type in _TASK_SCHEMA.items():
            val = payload.get(field_name)
            if val is not None and not isinstance(val, expected_type):
                raise ValueError(
                    f"Field '{field_name}': expected {expected_type}, got {type(val).__name__}"
                )

        # Priority sanity
        priority = str(payload.get("priority", "normal")).lower()
        if priority not in _ALLOWED_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'")

        # Timeout bounds
        timeout = payload.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or not (1 <= timeout <= 3600):
            raise ValueError(f"Timeout {timeout} out of range [1, 3600]")

        # Params depth check
        params = payload.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("'params' must be a dict")
        InputGuard.check_dict(params, "task.params")

        return payload


# ── Correlation Context ───────────────────────────────────────────────────────

_local = threading.local()


class CorrelationCtx:
    """
    Thread-local correlation ID injected into log records.

    Usage::

        with CorrelationCtx.bind("req-abc123"):
            logger.info("Processing")  # record will include corr_id
    """

    @staticmethod
    def get() -> str:
        return getattr(_local, "corr_id", "")

    @staticmethod
    def set(corr_id: str) -> None:
        _local.corr_id = corr_id

    @staticmethod
    def clear() -> None:
        _local.corr_id = ""

    def __init__(self, corr_id: str) -> None:
        self._id = corr_id
        self._prev = ""

    def __enter__(self) -> "CorrelationCtx":
        self._prev = CorrelationCtx.get()
        CorrelationCtx.set(self._id)
        return self

    def __exit__(self, *_) -> None:
        CorrelationCtx.set(self._prev)

    @staticmethod
    def bind(corr_id: str) -> "CorrelationCtx":
        return CorrelationCtx(corr_id)


class CorrelationFilter(logging.Filter):
    """Logging filter that injects corr_id into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.corr_id = CorrelationCtx.get() or "-"
        return True


# ── Module-level circuit breakers (shared singletons) ────────────────────────

_breakers: Dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(name: str, config: Optional[BreakerConfig] = None) -> CircuitBreaker:
    """Return (or create) the named circuit breaker singleton."""
    with _breakers_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name, config)
    return _breakers[name]


def all_breaker_statuses() -> List[Dict[str, Any]]:
    with _breakers_lock:
        return [cb.status() for cb in _breakers.values()]


# Needed for AtomicWriter._atomic_write
import contextlib
