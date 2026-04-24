"""
ProjectX Intent Adapter — Phase 2/5 (Deep Integration)

Bidirectional bridge between ProjectX tasks and the SIMP canonical intent layer.

Direction A — Outbound (ProjectX → SIMP mesh):
  When the orchestrator needs to delegate a task, this adapter:
    1. Maps the task to the closest INTENT_TYPE_REGISTRY type
    2. Wraps it as a signed SIMP Intent
    3. Posts it to the broker's intent router
    4. Awaits the result (with timeout) and returns it

Direction B — Inbound (SIMP mesh → ProjectX):
  Registers a handler with the broker so that intents addressed to
  "projectx_native" are routed through the orchestrator.
  The adapter receives the intent, converts it to a goal string,
  runs it through ProjectXOrchestrator.run(), and returns the result.

This makes ProjectX a first-class participant in the SIMP agent mesh
rather than a side-car that can only be called by computer tasks.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

_BROKER_URL = "http://127.0.0.1:5555"
_ADAPTER_AGENT_ID = "projectx_intent_adapter"
_RESPONSE_TIMEOUT = 45  # seconds
_RESULT_POLL_INTERVAL = 0.5  # seconds


@dataclass
class IntentRequest:
    intent_type: str
    goal: str
    params: Dict[str, Any] = field(default_factory=dict)
    requester_id: str = _ADAPTER_AGENT_ID
    priority: str = "normal"
    timeout: int = _RESPONSE_TIMEOUT


@dataclass
class IntentResponse:
    intent_id: str
    intent_type: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    agent_id: str = ""
    latency_ms: int = 0


class IntentAdapter:
    """
    ProjectX ↔ SIMP Intent bridge.

    Usage::

        adapter = IntentAdapter()
        # Route a task through the full SIMP agent mesh:
        resp = adapter.dispatch(
            intent_type="market_analysis",
            goal="Analyse BTC/USD price action for the last 24h",
        )
        if resp.success:
            print(resp.result)
    """

    def __init__(
        self,
        broker_url: str = _BROKER_URL,
        agent_id: str = _ADAPTER_AGENT_ID,
        skill_engine=None,
    ) -> None:
        self._broker = broker_url.rstrip("/")
        self._agent_id = agent_id
        self._skill_engine = skill_engine
        self._registered = False

    # ── Direction A: Outbound (ProjectX → mesh) ───────────────────────────

    def dispatch(
        self,
        intent_type: str,
        goal: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = _RESPONSE_TIMEOUT,
    ) -> IntentResponse:
        """
        Send a task to the SIMP mesh via the canonical intent system.

        Falls back to local execution (via skill engine) if the broker
        is unreachable.
        """
        intent_id = str(uuid.uuid4())
        t0 = time.time()

        # Validate intent type against registry
        canonical = self._resolve_intent_type(intent_type, goal)
        payload = self._build_intent_payload(intent_id, canonical, goal, params or {})

        try:
            resp = requests.post(
                f"{self._broker}/intents",
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201, 202):
                # Poll for the result
                result = self._poll_result(intent_id, timeout=timeout)
                return IntentResponse(
                    intent_id=intent_id,
                    intent_type=canonical,
                    success=result.get("success", False),
                    result=result.get("result"),
                    error=result.get("error"),
                    agent_id=result.get("agent_id", ""),
                    latency_ms=int((time.time() - t0) * 1000),
                )
            else:
                logger.warning(
                    "Broker returned %d for intent %s — falling back to local",
                    resp.status_code, canonical,
                )
        except requests.exceptions.ConnectionError:
            logger.debug("Broker unreachable — executing locally for intent %s", canonical)
        except Exception as exc:
            logger.warning("Intent dispatch failed: %s", exc)

        # Local fallback
        return self._local_fallback(intent_id, canonical, goal, params or {}, t0)

    def map_goal_to_intent_type(self, goal: str) -> str:
        """
        Infer the best SIMP intent type for a free-text goal.
        Uses keyword matching against the INTENT_TYPE_REGISTRY.
        """
        try:
            from simp.models.canonical_intent import INTENT_TYPE_REGISTRY
        except ImportError:
            return "research"

        goal_lower = goal.lower()
        # Score each intent type by keyword overlap
        scores: Dict[str, int] = {}
        for itype, meta in INTENT_TYPE_REGISTRY.items():
            desc = meta.get("description", "").lower()
            score = sum(1 for word in itype.replace("_", " ").split() if word in goal_lower)
            score += sum(1 for word in desc.split() if len(word) > 4 and word in goal_lower)
            scores[itype] = score

        best = max(scores, key=lambda k: scores[k])
        if scores[best] == 0:
            return "research"  # safe default
        return best

    # ── Direction B: Inbound (mesh → ProjectX) ────────────────────────────

    def register_as_handler(self, orchestrator=None) -> bool:
        """
        Register projectx_intent_adapter with the broker so intents
        addressed to projectx can be processed by the orchestrator.
        """
        if self._registered:
            return True
        try:
            resp = requests.post(
                f"{self._broker}/agents/register",
                json={
                    "agent_id": self._agent_id,
                    "agent_type": "intent_adapter",
                    "endpoint": "http://127.0.0.1:8772",
                    "capabilities": [
                        "research", "analysis", "planning", "code_gen",
                        "orchestration", "meta_learning",
                    ],
                    "metadata": {"projectx": True, "bidirectional": True},
                },
                timeout=5,
            )
            self._registered = resp.status_code in (200, 201, 409)
            if self._registered:
                logger.info("IntentAdapter registered with broker (status=%d)", resp.status_code)
            return self._registered
        except Exception as exc:
            logger.warning("IntentAdapter registration failed: %s", exc)
            return False

    def handle_inbound_intent(self, intent: Dict[str, Any], orchestrator) -> Dict[str, Any]:
        """
        Convert a raw SIMP intent dict into a ProjectX orchestrator task.
        Called by the mesh bridge when an intent arrives for projectx.
        """
        intent_type = intent.get("intent_type", "research")
        params = intent.get("params", {})
        goal = params.get("goal") or params.get("query") or params.get("task") or str(params)

        try:
            result = orchestrator.run(goal)
            return {
                "success": result.success,
                "result": result.final_output,
                "validation_score": result.validation_score,
                "agent_id": self._agent_id,
                "intent_type": intent_type,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "agent_id": self._agent_id,
                "intent_type": intent_type,
            }

    # ── Mesh channel polling ──────────────────────────────────────────────

    def _poll_result(self, intent_id: str, timeout: int) -> Dict[str, Any]:
        """Poll the broker or mesh for a result matching intent_id."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(
                    f"{self._broker}/intents/{intent_id}/result",
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") in ("completed", "failed"):
                        return data
                elif resp.status_code == 404:
                    pass  # not ready yet
            except Exception:
                pass
            time.sleep(_RESULT_POLL_INTERVAL)
        return {"success": False, "error": f"Timed out after {timeout}s"}

    # ── Helpers ───────────────────────────────────────────────────────────

    def _resolve_intent_type(self, intent_type: str, goal: str) -> str:
        """Validate/infer intent type against canonical registry."""
        try:
            from simp.models.canonical_intent import INTENT_TYPE_REGISTRY
            if intent_type in INTENT_TYPE_REGISTRY:
                return intent_type
        except ImportError:
            pass
        inferred = self.map_goal_to_intent_type(goal)
        if inferred != intent_type:
            logger.debug("Intent type '%s' not in registry — using inferred '%s'", intent_type, inferred)
        return inferred

    def _build_intent_payload(
        self, intent_id: str, intent_type: str, goal: str, params: Dict
    ) -> Dict[str, Any]:
        return {
            "simp_version": "1.0",
            "id": intent_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_agent": {"id": self._agent_id, "organization": "projectx"},
            "intent_type": intent_type,
            "params": {"goal": goal, **params},
            "signature": "",
        }

    def _local_fallback(
        self,
        intent_id: str,
        intent_type: str,
        goal: str,
        params: Dict,
        t0: float,
    ) -> IntentResponse:
        """Execute locally when the broker is unreachable."""
        if self._skill_engine:
            try:
                registry = self._skill_engine._get_registry()
                subsystem_name = self._skill_engine.subsystem_for_intent(intent_type)
                if registry and subsystem_name:
                    handle = registry.get(subsystem_name)
                    if handle:
                        stub_result = handle.run(goal, executor=self._stub_executor)
                        return IntentResponse(
                            intent_id=intent_id,
                            intent_type=intent_type,
                            success=stub_result.success,
                            result=stub_result.output,
                            error=stub_result.error,
                            agent_id=f"local:{subsystem_name}",
                            latency_ms=int((time.time() - t0) * 1000),
                        )
            except Exception as exc:
                logger.debug("Local skill fallback failed: %s", exc)

        return IntentResponse(
            intent_id=intent_id,
            intent_type=intent_type,
            success=False,
            error="Broker unreachable and no local executor available",
            latency_ms=int((time.time() - t0) * 1000),
        )

    @staticmethod
    def _stub_executor(system_prompt: str, user_message: str) -> str:
        return f"[local-stub] {user_message[:200]}"


# Module-level singleton
_adapter: Optional[IntentAdapter] = None


def get_intent_adapter(broker_url: str = _BROKER_URL) -> IntentAdapter:
    global _adapter
    if _adapter is None:
        _adapter = IntentAdapter(broker_url=broker_url)
    return _adapter
