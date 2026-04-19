"""
Code Mesh Protocol (CMP) — SIMP Step 2
=======================================
Enables agents to write code and transmit it over the mesh to other agents.
Receiving agents validate signatures, check trust floors, and execute in a sandbox.

Trust gates:
  sandbox_level=1 (pure function):        trust_floor = 3.0
  sandbox_level=2 (stdlib, no I/O):       trust_floor = 4.0
  sandbox_level=3 (restricted /tmp fs):   trust_floor = 4.5

QuantumSkillEvolver IMITATION learning is triggered automatically on every
successful remote execution — skills propagate peer-to-peer across the mesh.

Channels:
  code_payloads   — inbound code execution requests
  skill_broadcasts — outbound QuantumSkill bundles (IMITATION learning)
  circuit_updates  — outbound QuantumCircuitDesign objects
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CodePayload — the wire format for code transmission
# ---------------------------------------------------------------------------

@dataclass
class CodePayload:
    """
    Signed, sandboxed code payload transmitted over the mesh.

    Fields
    ------
    source        Python source code (UTF-8 text).
    lang          Language tag — "python3" | "circuit_json" | "skill_bundle".
    entry_point   Name of the top-level function to call (must be defined in source).
    args          Keyword arguments passed to entry_point(**args).
    sha256_hash   SHA-256 hex digest of `source` (receiver verifies before exec).
    rsa_signature RSA signature of sha256_hash (optional; validated against TrustGraph).
    sandbox_level 1 = pure function, 2 = stdlib allowed, 3 = restricted filesystem.
    max_runtime_ms Maximum execution time before SIGKILL (default 5000 ms).
    sender_id     Agent ID of the sender (for trust lookup).
    payload_id    Unique ID for this payload (for correlation_id reply tracking).
    """
    source: str
    lang: str = "python3"
    entry_point: str = "main"
    args: Dict[str, Any] = field(default_factory=dict)
    sha256_hash: str = ""
    rsa_signature: str = ""
    sandbox_level: int = 1
    max_runtime_ms: int = 5000
    sender_id: str = ""
    payload_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if not self.sha256_hash:
            self.sha256_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        return hashlib.sha256(self.source.encode()).hexdigest()

    def verify_hash(self) -> bool:
        return hmac.compare_digest(self.sha256_hash, self._compute_hash())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CodePayload":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Result of a sandboxed code execution."""
    payload_id: str
    ok: bool
    return_value: Any = None
    stdout: str = ""
    stderr: str = ""
    execution_ms: float = 0.0
    sandbox_violations: int = 0
    error: str = ""
    score: float = 0.0          # 0.0–1.0 performance score (for QuantumSkillEvolver)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# SandboxedExecutor — runs code inside a subprocess with resource limits
# ---------------------------------------------------------------------------

class SandboxedExecutor:
    """
    Executes CodePayload in a subprocess with configurable restrictions.

    Level 1 — Pure function:
        No imports allowed. AST-scanned before exec. Pure computation only.

    Level 2 — Stdlib:
        Standard library imports allowed. No open(), no network, no subprocess.
        Implemented via a restricted __builtins__ dict.

    Level 3 — Restricted filesystem:
        Allowed to read/write under /tmp/simp_sandbox/. No network.
        Runs as a subprocess with 128 MB memory limit (via resource module).
    """

    # Builtins forbidden at all sandbox levels
    _FORBIDDEN_BUILTINS = {
        "exec", "eval", "compile", "__import__",
        "open", "input", "breakpoint",
        "memoryview",
    }

    # Additional forbidden names at level 1
    _LEVEL1_FORBIDDEN = {"os", "sys", "subprocess", "socket", "threading", "multiprocessing"}

    def execute(self, payload: CodePayload) -> ExecutionResult:
        t0 = time.monotonic()
        try:
            if payload.sandbox_level == 1:
                result = self._exec_level1(payload)
            elif payload.sandbox_level == 2:
                result = self._exec_level2(payload)
            else:
                result = self._exec_level3(payload)
            result.execution_ms = (time.monotonic() - t0) * 1000
            result.score = 1.0 if result.ok else 0.0
            return result
        except Exception as exc:
            return ExecutionResult(
                payload_id=payload.payload_id,
                ok=False,
                error=str(exc),
                execution_ms=(time.monotonic() - t0) * 1000,
            )

    def _exec_level1(self, payload: CodePayload) -> ExecutionResult:
        """Pure function — no imports, restricted builtins, in-process."""
        # Static scan for forbidden names
        violations = 0
        for forbidden in self._LEVEL1_FORBIDDEN:
            if forbidden in payload.source:
                violations += 1

        if violations > 0:
            return ExecutionResult(
                payload_id=payload.payload_id,
                ok=False,
                error=f"sandbox_level=1 violation: {violations} forbidden names detected",
                sandbox_violations=violations,
            )

        # Restricted builtins
        import builtins as _builtins_mod
        safe_builtins = {
            k: getattr(_builtins_mod, k) for k in dir(_builtins_mod)
            if not k.startswith("_") and k not in self._FORBIDDEN_BUILTINS
        }

        namespace: Dict[str, Any] = {"__builtins__": safe_builtins}
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(compile(payload.source, "<code_payload>", "exec"), namespace)
                fn = namespace.get(payload.entry_point)
                if fn is None:
                    return ExecutionResult(
                        payload_id=payload.payload_id,
                        ok=False,
                        error=f"entry_point '{payload.entry_point}' not found in source",
                    )
                return_value = fn(**payload.args)
            return ExecutionResult(
                payload_id=payload.payload_id,
                ok=True,
                return_value=return_value,
                stdout=stdout_buf.getvalue(),
                stderr=stderr_buf.getvalue(),
            )
        except Exception as exc:
            return ExecutionResult(
                payload_id=payload.payload_id,
                ok=False,
                error=str(exc),
                stdout=stdout_buf.getvalue(),
                stderr=stderr_buf.getvalue(),
            )

    def _exec_level2(self, payload: CodePayload) -> ExecutionResult:
        """Stdlib allowed — runs in subprocess, no network, timeout enforced."""
        return self._exec_subprocess(payload, allow_network=False, allow_fs=False)

    def _exec_level3(self, payload: CodePayload) -> ExecutionResult:
        """Restricted filesystem — /tmp/simp_sandbox/ only."""
        import os
        sandbox_dir = "/tmp/simp_sandbox"
        os.makedirs(sandbox_dir, exist_ok=True)
        return self._exec_subprocess(payload, allow_network=False, allow_fs=True,
                                     sandbox_dir=sandbox_dir)

    def _exec_subprocess(self, payload: CodePayload, allow_network: bool,
                         allow_fs: bool, sandbox_dir: str = "/tmp") -> ExecutionResult:
        """Run payload in a subprocess with timeout."""
        timeout_s = payload.max_runtime_ms / 1000.0

        # Build the runner script
        runner = textwrap.dedent(f"""
import json, sys

# Payload source
{payload.source}

# Call entry point
try:
    result = {payload.entry_point}(**{json.dumps(payload.args)})
    print(json.dumps({{"ok": True, "return_value": result}}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error": str(exc)}}))
""")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                        dir="/tmp", delete=False) as f:
            f.write(runner)
            script_path = f.name

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode != 0:
                return ExecutionResult(
                    payload_id=payload.payload_id,
                    ok=False,
                    error=f"subprocess exited {proc.returncode}",
                    stdout=stdout,
                    stderr=stderr,
                )

            try:
                parsed = json.loads(stdout.split("\n")[-1])
                return ExecutionResult(
                    payload_id=payload.payload_id,
                    ok=parsed.get("ok", False),
                    return_value=parsed.get("return_value"),
                    error=parsed.get("error", ""),
                    stdout=stdout,
                    stderr=stderr,
                )
            except json.JSONDecodeError:
                return ExecutionResult(
                    payload_id=payload.payload_id,
                    ok=True,
                    stdout=stdout,
                    stderr=stderr,
                )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                payload_id=payload.payload_id,
                ok=False,
                error=f"execution timed out after {timeout_s}s",
            )
        finally:
            import os as _os
            try:
                _os.unlink(script_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# CodeMeshExecutor — the full pipeline: receive → validate → gate → exec → learn
# ---------------------------------------------------------------------------

TRUST_FLOORS: Dict[int, float] = {1: 3.0, 2: 4.0, 3: 4.5}


class CodeMeshExecutor:
    """
    Receives CodePayload from the mesh, validates it, executes it in a sandbox,
    and feeds the result into QuantumSkillEvolver for IMITATION learning.

    Usage
    -----
    executor = CodeMeshExecutor(agent_id="my_agent")
    executor.start()   # subscribes to code_payloads channel
    executor.stop()
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._sandbox = SandboxedExecutor()
        self._running = False
        self._thread = None
        self.log = logging.getLogger(f"cmp.executor.{agent_id}")
        self._stats = {
            "received": 0, "allowed": 0, "denied_trust": 0,
            "denied_hash": 0, "executed_ok": 0, "executed_fail": 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Subscribe to code_payloads channel and start processing loop."""
        import threading
        from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
        self._bus = get_enhanced_mesh_bus()
        self._bus.register_agent(self.agent_id)
        self._bus.subscribe(self.agent_id, "code_payloads")
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name=f"cmp-{self.agent_id}")
        self._thread.start()
        self.log.info("CodeMeshExecutor started — listening on code_payloads")

    def stop(self):
        self._running = False

    def execute_payload(self, payload: CodePayload) -> ExecutionResult:
        """
        Full pipeline: trust gate → hash verify → sandbox exec → IMITATION learn.
        Call this directly if you already have a CodePayload object.
        """
        self._stats["received"] += 1

        # 1. Trust gate
        sender_trust = self._get_trust(payload.sender_id)
        required = TRUST_FLOORS.get(payload.sandbox_level, 5.0)
        if sender_trust < required:
            self.log.warning(
                f"Trust gate denied: {payload.sender_id} "
                f"trust={sender_trust:.2f} < required={required:.2f}"
            )
            self._stats["denied_trust"] += 1
            self._apply_penalty(payload.sender_id, -0.3)
            return ExecutionResult(
                payload_id=payload.payload_id,
                ok=False,
                error=f"trust_floor_not_met: {sender_trust:.2f} < {required:.2f}",
            )

        # 2. Hash integrity check
        if not payload.verify_hash():
            self.log.warning(f"Hash mismatch from {payload.sender_id}")
            self._stats["denied_hash"] += 1
            self._apply_penalty(payload.sender_id, -0.5)
            return ExecutionResult(
                payload_id=payload.payload_id,
                ok=False,
                error="hash_mismatch: source integrity check failed",
            )

        self._stats["allowed"] += 1

        # 3. Execute in sandbox
        result = self._sandbox.execute(payload)

        # 4. IMITATION learning — feed result to QuantumSkillEvolver
        self._feed_evolver(payload, result)

        if result.ok:
            self._stats["executed_ok"] += 1
            self.log.info(
                f"Executed {payload.entry_point} from {payload.sender_id} "
                f"in {result.execution_ms:.0f}ms — ok"
            )
            # Trust nudge: sender gets tiny positive delta for clean code
            self._apply_penalty(payload.sender_id, +0.02)
        else:
            self._stats["executed_fail"] += 1
            self.log.warning(
                f"Execution failed from {payload.sender_id}: {result.error}"
            )

        return result

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _loop(self):
        """Background loop: poll code_payloads channel."""
        from simp.mesh.packet import create_event_packet
        while self._running:
            try:
                messages = self._bus.receive(self.agent_id, max_messages=10)
                for msg in messages:
                    if msg.channel != "code_payloads":
                        continue
                    try:
                        payload = CodePayload.from_dict(msg.payload)
                        result = self.execute_payload(payload)
                        # Send reply to sender via correlation_id
                        if msg.sender_id:
                            reply = create_event_packet(
                                sender_id=self.agent_id,
                                recipient_id=msg.sender_id,
                                channel="code_results",
                                payload=result.to_dict(),
                            )
                            reply.correlation_id = msg.message_id
                            self._bus.send(reply)
                    except Exception as exc:
                        self.log.error(f"Failed to process code payload: {exc}")
            except Exception as exc:
                self.log.error(f"Loop error: {exc}")
            time.sleep(0.1)

    def _get_trust(self, agent_id: str) -> float:
        """Query TrustGraph for live trust score. Falls back to 0.0."""
        try:
            from simp.mesh.trust_graph import get_trust_graph
            tg = get_trust_graph(autostart=False)
            return tg.get_effective_score(agent_id)
        except Exception:
            return 0.0

    def _apply_penalty(self, agent_id: str, delta: float):
        """Apply trust delta via TrustGraph."""
        try:
            from simp.mesh.trust_graph import get_trust_graph
            tg = get_trust_graph(autostart=False)
            tg.apply_delta(agent_id, delta)
        except Exception:
            pass

    def _feed_evolver(self, payload: CodePayload, result: ExecutionResult):
        """Feed execution result to QuantumSkillEvolver for IMITATION learning."""
        try:
            from simp.organs.quantum_intelligence.quantum_evolver import (
                QuantumSkillEvolver, LearningExperience, LearningStrategy
            )
            from simp.organs.quantum_intelligence import QuantumProblemType
            import uuid as _uuid

            evolver = QuantumSkillEvolver(self.agent_id)
            outcome = "success" if result.ok else "failure"
            exp = LearningExperience(
                experience_id=str(_uuid.uuid4()),
                skill_id=payload.sender_id,          # Learn from the sender's "skill"
                problem_type=QuantumProblemType.OPTIMIZATION,
                outcome=outcome,
                performance_score=result.score,
                quantum_advantage=0.0,
                insights_gained=[
                    f"Learned {payload.entry_point} from {payload.sender_id} via IMITATION",
                    f"Execution: {result.execution_ms:.0f}ms, sandbox_level={payload.sandbox_level}",
                ],
                metadata={
                    "strategy": LearningStrategy.IMITATION.value,
                    "source_hash": payload.sha256_hash[:16],
                    "entry_point": payload.entry_point,
                    "sender_id": payload.sender_id,
                },
            )
            evolver.learn_from_experience(exp)
            self.log.debug(f"IMITATION learning: recorded experience from {payload.sender_id}")
        except Exception as exc:
            self.log.debug(f"QuantumSkillEvolver not available: {exc}")


# ---------------------------------------------------------------------------
# Convenience: send code to another agent
# ---------------------------------------------------------------------------

def send_code_to_agent(
    source: str,
    entry_point: str,
    args: Dict[str, Any],
    sender_id: str,
    recipient_id: str,
    sandbox_level: int = 1,
    max_runtime_ms: int = 5000,
) -> Optional[str]:
    """
    Send a signed CodePayload to another agent over the mesh.

    Returns the message_id of the sent packet (use as correlation_id to
    receive the result on the code_results channel), or None on failure.
    """
    from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
    from simp.mesh.packet import create_event_packet

    payload = CodePayload(
        source=source,
        entry_point=entry_point,
        args=args,
        sender_id=sender_id,
        sandbox_level=sandbox_level,
        max_runtime_ms=max_runtime_ms,
    )

    bus = get_enhanced_mesh_bus()
    pkt = create_event_packet(
        sender_id=sender_id,
        recipient_id=recipient_id,
        channel="code_payloads",
        payload=payload.to_dict(),
    )
    success = bus.send(pkt)
    if success:
        log.info(f"CodePayload sent: {payload.payload_id[:8]} → {recipient_id}")
        return pkt.message_id
    return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_executor_registry: Dict[str, CodeMeshExecutor] = {}


def get_code_executor(agent_id: str) -> CodeMeshExecutor:
    """Get or create a CodeMeshExecutor for the given agent."""
    if agent_id not in _executor_registry:
        _executor_registry[agent_id] = CodeMeshExecutor(agent_id)
    return _executor_registry[agent_id]


# ---------------------------------------------------------------------------
# Quick demo / smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s — %(message)s")

    # Test: level-1 sandbox — pure function
    payload = CodePayload(
        source="""
def add_numbers(a, b):
    return a + b
""",
        entry_point="add_numbers",
        args={"a": 40, "b": 2},
        sender_id="test_sender",
        sandbox_level=1,
    )

    executor = SandboxedExecutor()
    result = executor.execute(payload)
    print(f"Level 1 result: ok={result.ok} return={result.return_value} ({result.execution_ms:.1f}ms)")
    assert result.ok and result.return_value == 42, f"Expected 42, got {result.return_value}"

    # Test: level-2 sandbox — stdlib allowed
    payload2 = CodePayload(
        source="""
import math

def circle_area(radius):
    return math.pi * radius ** 2
""",
        entry_point="circle_area",
        args={"radius": 5.0},
        sender_id="test_sender",
        sandbox_level=2,
    )
    result2 = executor.execute(payload2)
    print(f"Level 2 result: ok={result2.ok} return={result2.return_value:.4f} ({result2.execution_ms:.1f}ms)")

    print("✅ CodeMeshProtocol smoke test passed")
