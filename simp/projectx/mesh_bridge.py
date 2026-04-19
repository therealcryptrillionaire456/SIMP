"""
ProjectX Mesh Bridge — SIMP
============================
Connects the ProjectXComputer bounded action layer to the SIMP mesh,
enabling other agents to:

  • Request protocol health checks via intent
  • Request shell commands via intent (with BRP trust gate)
  • Receive heartbeat acknowledgements from projectx_native

Bug 4 fix (heartbeat path mismatch)
────────────────────────────────────
The broker defines:
    POST /agents/<agent_id>/heartbeat   (http_server.py:491)

projectx_native was calling the wrong path.  This bridge always uses
the correct parameterised path.  The bridge also handles the case where
the agent isn't yet registered (retries registration before heartbeat).

Mesh channels used
──────────────────
  projectx_tasks    — inbound task requests (this bridge consumes)
  projectx_results  — outbound task results  (this bridge publishes)
  heartbeats        — standard heartbeat channel
  system            — system-level events
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from .computer import ProjectXComputer, TaskAbortError, ACTION_TIERS

logger = logging.getLogger(__name__)

AGENT_ID         = "projectx_native"
HEARTBEAT_PATH   = "/agents/{agent_id}/heartbeat"   # Bug 4 fix — correct path
HEARTBEAT_INTERVAL = 30.0   # seconds
REGISTRATION_TTL   = 300.0  # seconds between re-registration attempts
TASK_CHANNEL     = "projectx_tasks"
RESULT_CHANNEL   = "projectx_results"


@dataclass
class ProjectXTask:
    """Inbound task request from another mesh agent."""
    task_id:      str
    action:       str
    params:       Dict = field(default_factory=dict)
    requester_id: str  = ""
    priority:     str  = "normal"
    timeout:      int  = 30
    trust_required: float = 0.0  # minimum requester trust score

    def to_dict(self) -> Dict:
        return {
            "task_id":       self.task_id,
            "action":        self.action,
            "params":        self.params,
            "requester_id":  self.requester_id,
            "priority":      self.priority,
            "timeout":       self.timeout,
            "trust_required": self.trust_required,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> ProjectXTask:
        return cls(
            task_id       = d.get("task_id", ""),
            action        = d.get("action", ""),
            params        = d.get("params", {}),
            requester_id  = d.get("requester_id", ""),
            priority      = d.get("priority", "normal"),
            timeout       = d.get("timeout", 30),
            trust_required = d.get("trust_required", 0.0),
        )


class ProjectXMeshBridge:
    """
    Connects ProjectXComputer to the SIMP mesh.

    Lifecycle:
        bridge = ProjectXMeshBridge(broker_url="http://127.0.0.1:5555")
        bridge.start()
        ...
        bridge.stop()
    """

    # Actions allowed to be called remotely (NEVER tier 3 — approval required)
    REMOTE_ALLOWED_ACTIONS = frozenset({
        "get_screenshot",
        "get_active_window",
        "ocr_screen",
        "snapshot_state",
        "sync_knowledge",
        "update_knowledge",
        "check_protocol_health",
        "log_action",
    })

    # Tier 1-2 actions require trust score >= TIER1_TRUST_FLOOR
    TIER1_TRUST_FLOOR = 3.0
    TIER2_TRUST_FLOOR = 4.5

    def __init__(
        self,
        broker_url:   str = "http://127.0.0.1:5555",
        agent_id:     str = AGENT_ID,
        computer:     Optional[ProjectXComputer] = None,
        trust_graph   = None,
    ):
        self.broker_url  = broker_url.rstrip("/")
        self.agent_id    = agent_id
        self.computer    = computer or ProjectXComputer()
        self._trust_graph = trust_graph

        self._running            = False
        self._thread:            Optional[threading.Thread] = None
        self._last_heartbeat     = 0.0
        self._last_registration  = 0.0
        self._registered         = False

        self._stats = {
            "tasks_received":   0,
            "tasks_completed":  0,
            "tasks_denied":     0,
            "tasks_errored":    0,
            "heartbeats_sent":  0,
            "heartbeat_failures": 0,
        }

        logger.info("[ProjectXMeshBridge] init  agent=%s  broker=%s", agent_id, broker_url)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Register with broker, subscribe to mesh channels, start loop."""
        if self._running:
            return True

        ok = self._ensure_registered()
        self._setup_mesh_subscriptions()

        self._running = True
        self._thread  = threading.Thread(
            target=self._loop,
            daemon=True,
            name="ProjectXMeshBridge",
        )
        self._thread.start()
        logger.info("[ProjectXMeshBridge] started")
        return ok

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[ProjectXMeshBridge] stopped")

    # ── Main loop ──────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                now = time.time()

                # Re-register periodically (belt-and-suspenders)
                if now - self._last_registration > REGISTRATION_TTL:
                    self._ensure_registered()

                # Send heartbeat  ← Bug 4 fix: uses correct path
                if now - self._last_heartbeat >= HEARTBEAT_INTERVAL:
                    self._send_heartbeat()

                # Process task queue
                self._process_tasks()

                time.sleep(2)

            except Exception as exc:
                logger.error("[ProjectXMeshBridge] loop error: %s", exc)
                time.sleep(5)

    # ── Registration + heartbeat ──────────────────────────────────────────────

    def _ensure_registered(self) -> bool:
        """Register projectx_native with the broker if not already registered."""
        try:
            resp = requests.post(
                f"{self.broker_url}/agents/register",
                json={
                    "agent_id":   self.agent_id,
                    "agent_type": "native_maintenance",
                    "endpoint":   f"http://127.0.0.1:8771",
                    "capabilities": [
                        "protocol_health_check",
                        "screenshot",
                        "knowledge_sync",
                        "system_maintenance",
                    ],
                    "metadata": {
                        "computer_use": True,
                        "max_tier":     self.computer.max_tier,
                    },
                },
                timeout=5,
            )
            self._registered     = resp.status_code in (200, 201, 409)
            self._last_registration = time.time()
            logger.debug(
                "[ProjectXMeshBridge] register status=%d registered=%s",
                resp.status_code, self._registered,
            )
            return self._registered
        except Exception as exc:
            logger.warning("[ProjectXMeshBridge] registration failed: %s", exc)
            return False

    def _send_heartbeat(self) -> bool:
        """
        POST /agents/<agent_id>/heartbeat  ← Bug 4 corrected path.
        Falls back to re-registration if the agent isn't registered.
        """
        path = HEARTBEAT_PATH.format(agent_id=self.agent_id)
        try:
            resp = requests.post(
                f"{self.broker_url}{path}",
                json={"status": "healthy", "timestamp": time.time()},
                timeout=5,
            )

            if resp.status_code == 404:
                # Agent not registered — re-register then retry
                logger.warning("[ProjectXMeshBridge] heartbeat 404 — re-registering")
                self._ensure_registered()
                resp = requests.post(
                    f"{self.broker_url}{path}",
                    json={"status": "healthy", "timestamp": time.time()},
                    timeout=5,
                )

            success = resp.status_code == 200
            if success:
                self._last_heartbeat   = time.time()
                self._stats["heartbeats_sent"] += 1
            else:
                self._stats["heartbeat_failures"] += 1
                logger.warning(
                    "[ProjectXMeshBridge] heartbeat %s → %d", path, resp.status_code
                )

            # Also send mesh heartbeat packet
            self._mesh_heartbeat()
            return success

        except Exception as exc:
            self._stats["heartbeat_failures"] += 1
            logger.warning("[ProjectXMeshBridge] heartbeat exception: %s", exc)
            return False

    def _mesh_heartbeat(self) -> None:
        """Broadcast a heartbeat packet to the mesh heartbeats channel."""
        try:
            from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
            from simp.mesh.packet import create_event_packet, Priority

            bus = get_enhanced_mesh_bus()
            pkt = create_event_packet(
                sender_id    = self.agent_id,
                recipient_id = "*",
                channel      = "heartbeats",
                payload      = {
                    "agent_id":  self.agent_id,
                    "type":      "native_maintenance",
                    "status":    "healthy",
                    "timestamp": time.time(),
                    "stats":     self._stats.copy(),
                },
                ttl_seconds  = 60,
            )
            pkt.priority = Priority.LOW
            bus.send(pkt)
        except Exception as exc:
            logger.debug("[ProjectXMeshBridge] mesh heartbeat failed: %s", exc)

    # ── Mesh subscriptions ────────────────────────────────────────────────────

    def _setup_mesh_subscriptions(self) -> None:
        try:
            from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
            bus = get_enhanced_mesh_bus()
            bus.register_agent(self.agent_id)
            for ch in (TASK_CHANNEL, "system", "heartbeats"):
                bus.subscribe(self.agent_id, ch)
            logger.debug("[ProjectXMeshBridge] subscribed to mesh channels")
        except Exception as exc:
            logger.warning("[ProjectXMeshBridge] mesh subscription failed: %s", exc)

    # ── Task processing ───────────────────────────────────────────────────────

    def _process_tasks(self) -> None:
        """Pull and execute tasks from the projectx_tasks channel."""
        try:
            from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
            bus     = get_enhanced_mesh_bus()
            packets = bus.receive(self.agent_id, max_messages=5)

            for pkt in packets:
                if pkt.channel != TASK_CHANNEL:
                    continue
                self._stats["tasks_received"] += 1
                self._execute_task(pkt)

        except Exception as exc:
            logger.debug("[ProjectXMeshBridge] task poll error: %s", exc)

    def _execute_task(self, pkt) -> None:
        """Validate and execute a single ProjectX task packet."""
        try:
            task = ProjectXTask.from_dict(pkt.payload)
        except Exception as exc:
            logger.warning("[ProjectXMeshBridge] bad task payload: %s", exc)
            return

        # Action allowlist gate
        if task.action not in self.REMOTE_ALLOWED_ACTIONS:
            logger.warning(
                "[ProjectXMeshBridge] remote action '%s' not in allowlist (requester=%s)",
                task.action, task.requester_id,
            )
            self._stats["tasks_denied"] += 1
            self._send_result(task, success=False, error=f"Action '{task.action}' not remotely allowed")
            return

        # Trust gate for higher-tier actions
        tier = ACTION_TIERS.get(task.action, 0)
        if tier >= 1:
            requester_trust = self._get_requester_trust(task.requester_id)
            required = self.TIER1_TRUST_FLOOR if tier == 1 else self.TIER2_TRUST_FLOOR
            if requester_trust < required:
                logger.warning(
                    "[ProjectXMeshBridge] denied tier-%d action '%s' for %s (trust=%.2f < %.2f)",
                    tier, task.action, task.requester_id, requester_trust, required,
                )
                self._stats["tasks_denied"] += 1
                self._send_result(
                    task, success=False,
                    error=f"Insufficient trust: {requester_trust:.2f} < {required:.2f} required for tier-{tier}"
                )
                return

        # Execute
        try:
            step   = {"action": task.action, "params": task.params}
            result = self.computer.safe_execute(step)

            if result.get("success"):
                self._stats["tasks_completed"] += 1
            else:
                self._stats["tasks_errored"] += 1

            self._send_result(task, success=result.get("success", False),
                              data=result.get("data"), error=result.get("error"))

        except TaskAbortError as exc:
            self._stats["tasks_errored"] += 1
            self._send_result(task, success=False, error=f"Aborted: {exc.reason}")
        except Exception as exc:
            self._stats["tasks_errored"] += 1
            self._send_result(task, success=False, error=str(exc))

    def _get_requester_trust(self, requester_id: str) -> float:
        """Return effective trust score for requester (1.0 if no graph)."""
        if self._trust_graph is None:
            return 1.0
        try:
            return self._trust_graph.get_effective_score(requester_id)
        except Exception:
            return 1.0

    def _send_result(
        self,
        task:    ProjectXTask,
        success: bool,
        data:    Any = None,
        error:   Optional[str] = None,
    ) -> None:
        """Publish task result to RESULT_CHANNEL."""
        try:
            from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
            from simp.mesh.packet import create_event_packet

            bus  = get_enhanced_mesh_bus()
            pkt  = create_event_packet(
                sender_id    = self.agent_id,
                recipient_id = task.requester_id or "*",
                channel      = RESULT_CHANNEL,
                payload      = {
                    "task_id":  task.task_id,
                    "action":   task.action,
                    "success":  success,
                    "data":     data,
                    "error":    error,
                    "agent_id": self.agent_id,
                    "ts":       time.time(),
                },
                ttl_seconds=120,
            )
            bus.send(pkt)
        except Exception as exc:
            logger.debug("[ProjectXMeshBridge] result send failed: %s", exc)

    # ── Introspection ─────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        return {
            "agent_id":     self.agent_id,
            "running":      self._running,
            "registered":   self._registered,
            "last_heartbeat": self._last_heartbeat,
            "broker_url":   self.broker_url,
            "stats":        self._stats.copy(),
            "computer":     {
                "max_tier": self.computer.max_tier,
                "log_dir":  str(self.computer.log_dir),
                "action_count": self.computer._action_count,
            },
        }


# ── Singleton factory ─────────────────────────────────────────────────────────

_bridge_instance: Optional[ProjectXMeshBridge] = None
_bridge_lock = threading.Lock()


def get_projectx_mesh_bridge(
    broker_url:  str = "http://127.0.0.1:5555",
    agent_id:    str = AGENT_ID,
    trust_graph  = None,
    autostart:   bool = True,
) -> ProjectXMeshBridge:
    """
    Return the process-level ProjectXMeshBridge singleton.
    Auto-starts the bridge on first call.
    """
    global _bridge_instance

    with _bridge_lock:
        if _bridge_instance is None:
            _bridge_instance = ProjectXMeshBridge(
                broker_url  = broker_url,
                agent_id    = agent_id,
                trust_graph = trust_graph,
            )
            if autostart:
                _bridge_instance.start()

    return _bridge_instance
