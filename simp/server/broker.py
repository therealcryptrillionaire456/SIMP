"""
SIMP Broker: Central Message Router

Acts as the central hub for inter-agent communication.
Receives intents, routes to appropriate agents, collects responses.
"""

import asyncio
import json
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import uuid
import queue
import threading
import time

from simp.task_ledger import TaskLedger
from simp.models.failure_taxonomy import FailureHandler, FailureClass
from simp.routing.builder_pool import BuilderPool
from simp.server.request_guards import sanitize_agent_id
from simp.orchestration.orchestration_loop import OrchestrationLoop

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class BrokerState(str, Enum):
    """Broker operational states"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class BrokerConfig:
    """Configuration for SIMP Broker"""
    port: int = 5555
    host: str = "127.0.0.1"
    max_agents: int = 100
    max_pending_intents: int = 1000
    intent_timeout: float = 30.0  # seconds
    delivery_timeout: float = 30.0  # seconds — HTTP delivery timeout
    health_check_interval: float = 30.0  # seconds — agent health check interval
    health_check_timeout: float = 5.0  # seconds — per-agent health check timeout
    inbox_base_dir: str = "data/inboxes"
    enable_logging: bool = True
    log_level: str = "INFO"
    max_log_lines: int = 10000


@dataclass
class IntentRecord:
    """Record of an intent in flight"""
    intent_id: str
    source_agent: str
    target_agent: str
    intent_type: str
    timestamp: str
    status: str  # pending, executing, completed, failed
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class SimpBroker:
    """
    SIMP Protocol Broker

    Central message router for inter-agent communication.
    Manages agent registration, intent routing, and response handling.
    """

    def __init__(self, config: Optional[BrokerConfig] = None,
                 task_ledger: Optional[TaskLedger] = None,
                 hooks: Optional[Any] = None):
        """Initialize SIMP Broker

        Args:
            config: Broker configuration.
            task_ledger: Optional TaskLedger instance.
            hooks: Optional MemoryHooks instance for event-driven memory updates.
        """
        self.config = config or BrokerConfig()
        self.state = BrokerState.INITIALIZING
        self.hooks = hooks
        self.logger = self._setup_logging()

        # Agent registry
        self.agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent info
        self.agent_lock = threading.RLock()

        # Intent tracking
        self.intent_records: Dict[str, IntentRecord] = {}
        self.intent_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(
            maxsize=self.config.max_pending_intents
        )
        self.intent_lock = threading.RLock()

        # Task ledger, failure handler, and builder pool
        self.task_ledger = task_ledger or TaskLedger()
        self.failure_handler = FailureHandler()
        try:
            self.builder_pool = BuilderPool()
        except FileNotFoundError:
            self.builder_pool = None
            self.logger.warning("Routing policy not found — builder pool disabled")

        # Statistics
        self.stats = {
            "intents_received": 0,
            "intents_routed": 0,
            "intents_completed": 0,
            "intents_failed": 0,
            "agents_registered": 0,
            "total_route_time_ms": 0.0,
        }
        self.stats_lock = threading.RLock()

        # Structured event log ring buffer
        self._event_log: deque = deque(maxlen=500)
        self._event_log_lock = threading.RLock()

        # Orchestration loop (optional, enabled by default)
        self._orchestration_loop: Optional[OrchestrationLoop] = None

        # Shutdown coordination
        self._shutdown_event = threading.Event()

        self.logger.info(f"🚀 SIMP Broker initialized (v0.1)")
        self.logger.info(f"   Config: {self.config.host}:{self.config.port}")
        self.logger.info(f"   Max agents: {self.config.max_agents}")
        self.logger.info(f"   Intent timeout: {self.config.intent_timeout}s")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for broker"""
        logger = logging.getLogger("SIMP.Broker")
        logger.setLevel(self.config.log_level)

        # Console handler
        handler = logging.StreamHandler()
        handler.setLevel(self.config.log_level)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        return logger

    def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        endpoint: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register an agent with the broker

        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent (e.g., "vision", "grok", "kashclaw")
            endpoint: How to reach agent (e.g., "localhost:5001" or "ipc://agent.sock")
            metadata: Additional agent metadata

        Returns:
            True if registered, False if already exists or limit reached
        """
        with self.agent_lock:
            if agent_id in self.agents:
                self.logger.warning(f"❌ Agent '{agent_id}' already registered")
                return False

            if len(self.agents) >= self.config.max_agents:
                self.logger.error(f"❌ Max agents ({self.config.max_agents}) reached")
                return False

            self.agents[agent_id] = {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "endpoint": endpoint,
                "metadata": metadata or {},
                "registered_at": _utcnow_iso(),
                "intents_received": 0,
                "intents_completed": 0,
                "status": "online",
            }

            with self.stats_lock:
                self.stats["agents_registered"] += 1

            self.logger.info(
                f"✅ Agent registered: {agent_id} ({agent_type}) → {endpoint}"
            )
            self._log_event("agent_registered", f"Agent {agent_id} registered", agent_id=agent_id)
            return True

    def deregister_agent(self, agent_id: str) -> bool:
        """Deregister an agent"""
        with self.agent_lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                self.logger.info(f"✅ Agent deregistered: {agent_id}")
                self._log_event("agent_deregistered", f"Agent {agent_id} deregistered", agent_id=agent_id)
                return True
            return False

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent information"""
        with self.agent_lock:
            return self.agents.get(agent_id)

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all registered agents"""
        with self.agent_lock:
            return dict(self.agents)

    async def route_intent(
        self, intent_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route an intent to target agent

        Intent format:
        {
            "intent_id": "...",
            "source_agent": "...",
            "target_agent": "...",
            "intent_type": "...",
            "params": {...},
            "timestamp": "..."
        }
        """
        if self.state != BrokerState.RUNNING:
            return {
                "status": "error",
                "error_code": "BROKER_NOT_RUNNING",
                "error": f"Broker is {self.state.value}, not accepting intents",
            }

        intent_id = intent_data.get("intent_id", str(uuid.uuid4()))
        source_agent = intent_data.get("source_agent", "client")
        target_agent = intent_data.get("target_agent")
        intent_type = intent_data.get("intent_type", "unknown")
        delivery_start = time.monotonic()

        with self.stats_lock:
            self.stats["intents_received"] += 1

        # Log to task ledger
        task_id = self.task_ledger.create_task(
            title=f"Intent: {intent_type}",
            description=f"Route intent {intent_id} from {source_agent} to {target_agent or 'unknown'}",
            task_type=self._map_intent_to_task_type(intent_type),
            assigned_agent=target_agent,
            tags=["intent", intent_type],
        )

        # Validate target agent exists
        target = self.get_agent(target_agent)
        if not target:
            error_msg = f"Target agent '{target_agent}' not found"
            self.logger.warning(f"❌ {error_msg}")

            error_resp = {
                "status": "error",
                "error_code": "AGENT_NOT_FOUND",
                "error_message": error_msg,
                "intent_id": intent_id,
            }

            # Classify failure and apply policy
            fc = self.failure_handler.classify_failure(error_resp)
            self.task_ledger.fail_task(task_id, error=error_resp, failure_class=fc.value)
            policy = self.failure_handler.get_retry_policy(fc)

            # Try fallback agent if policy allows
            if policy.get("should_retry") and self.builder_pool:
                fallback = self.failure_handler.get_fallback_agent(
                    fc, intent_type, self.builder_pool, exclude=[target_agent or ""]
                )
                if fallback and self.get_agent(fallback):
                    self.logger.info(f"🔄 Falling back to agent: {fallback}")
                    target_agent = fallback
                    target = self.get_agent(fallback)
                    self.task_ledger.update_status(task_id, "queued")

            if not target:
                with self.intent_lock:
                    record = IntentRecord(
                        intent_id=intent_id,
                        source_agent=source_agent,
                        target_agent=target_agent or "unknown",
                        intent_type=intent_type,
                        timestamp=_utcnow_iso(),
                        status="failed",
                        error=error_msg,
                    )
                    self.intent_records[intent_id] = record

                with self.stats_lock:
                    self.stats["intents_failed"] += 1

                self._log_event(
                    "intent_failed", error_msg, level="warning",
                    agent_id=target_agent or "unknown", intent_id=intent_id,
                )

                return error_resp

        # Claim task in ledger
        self.task_ledger.claim_task(task_id, target_agent)
        self.task_ledger.update_status(task_id, "in_progress")

        # Record intent as pending
        with self.intent_lock:
            record = IntentRecord(
                intent_id=intent_id,
                source_agent=source_agent,
                target_agent=target_agent,
                intent_type=intent_type,
                timestamp=_utcnow_iso(),
                status="pending",
            )
            self.intent_records[intent_id] = record

        self.logger.info(
            f"📤 Routing intent: {intent_id} ({intent_type}) "
            f"{source_agent} → {target_agent}"
        )
        self._log_event(
            "intent_routed", f"Intent {intent_id} ({intent_type}) {source_agent} → {target_agent}",
            agent_id=target_agent, intent_id=intent_id,
        )

        # Actually deliver the intent to the target agent
        target_endpoint = target.get("endpoint", "")
        retry_count = 0
        delivery_result = None

        if target_endpoint and target_endpoint.startswith("http"):
            # HTTP agent — POST the intent to their endpoint
            delivery_result = await self._deliver_http(
                target_endpoint, intent_data, intent_id
            )

            # On failure, classify and attempt retry/fallback
            if delivery_result.get("delivery_status") == "failed":
                error_resp = {
                    "error_code": delivery_result.get("error_code", "DELIVERY_FAILED"),
                    "error_message": delivery_result.get("error_message", "Delivery failed"),
                }
                fc = self.failure_handler.classify_failure(error_resp)
                policy = self.failure_handler.get_retry_policy(fc)

                if policy.get("should_retry") and self.builder_pool:
                    fallback = self.failure_handler.get_fallback_agent(
                        fc, intent_type, self.builder_pool, exclude=[target_agent]
                    )
                    if fallback:
                        fallback_target = self.get_agent(fallback)
                        if fallback_target:
                            fallback_endpoint = fallback_target.get("endpoint", "")
                            self.logger.info(
                                f"🔄 Retrying delivery to fallback agent: {fallback}"
                            )
                            retry_count += 1
                            if fallback_endpoint and fallback_endpoint.startswith("http"):
                                delivery_result = await self._deliver_http(
                                    fallback_endpoint, intent_data, intent_id
                                )
                            else:
                                delivery_result = self._deliver_file_based(
                                    fallback, intent_data, intent_id
                                )
                            delivery_result["fallback_agent"] = fallback
        else:
            # File-based agent — write to their inbox
            delivery_result = self._deliver_file_based(
                target_agent, intent_data, intent_id
            )

        delivery_latency_ms = (time.monotonic() - delivery_start) * 1000
        delivery_status = delivery_result.get("delivery_status", "failed")
        delivery_result["delivery_latency_ms"] = round(delivery_latency_ms, 1)
        delivery_result["retry_count"] = retry_count

        # Update intent record with delivery result
        with self.intent_lock:
            record = self.intent_records.get(intent_id)
            if record:
                if delivery_status in ("delivered", "queued", "queued_no_endpoint"):
                    record.status = "executing" if delivery_status == "delivered" else "pending"
                    record.execution_time_ms = delivery_latency_ms
                else:
                    record.status = "failed"
                    record.error = delivery_result.get("error_message", "Delivery failed")
                    record.execution_time_ms = delivery_latency_ms

        # Update task ledger based on delivery outcome
        if delivery_status in ("delivered", "queued", "queued_no_endpoint"):
            with self.stats_lock:
                self.stats["intents_routed"] += 1
                self.stats["total_route_time_ms"] += delivery_latency_ms
            if delivery_status == "delivered":
                agent_response = delivery_result.get("agent_response")
                if agent_response:
                    self.record_response(intent_id, agent_response, delivery_latency_ms)
                    self.task_ledger.update_status(task_id, "completed")
                else:
                    self.task_ledger.update_status(task_id, "in_progress")
        else:
            with self.stats_lock:
                self.stats["intents_failed"] += 1
            self.task_ledger.fail_task(
                task_id,
                error={"error_code": delivery_result.get("error_code"),
                       "error_message": delivery_result.get("error_message")},
                failure_class=delivery_result.get("failure_class", "execution_failed"),
            )

        route_result = {
            "status": "routed",
            "intent_id": intent_id,
            "target_agent": target_agent,
            "task_id": task_id,
            "delivery_status": delivery_status,
            "delivery_latency_ms": delivery_result.get("delivery_latency_ms"),
            "retry_count": retry_count,
            "fallback_agent": delivery_result.get("fallback_agent"),
            "timestamp": _utcnow_iso(),
        }

        # Fire memory hook after routing
        if self.hooks:
            try:
                self.hooks.on_intent_routed(intent_data, route_result)
            except Exception:
                self.logger.debug("Memory hook on_intent_routed failed", exc_info=True)

        return route_result

    async def _deliver_http(
        self, endpoint: str, intent_data: Dict[str, Any], intent_id: str
    ) -> Dict[str, Any]:
        """Deliver an intent to an HTTP agent via POST."""
        if not _HTTPX_AVAILABLE:
            return {
                "delivery_status": "failed",
                "error_code": "HTTPX_NOT_INSTALLED",
                "error_message": "httpx is not installed — cannot deliver via HTTP",
                "failure_class": "execution_failed",
            }

        url = f"{endpoint.rstrip('/')}/intents/handle"
        timeout = self.config.delivery_timeout

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=intent_data)

            if resp.status_code == 200:
                try:
                    agent_response = resp.json()
                except Exception:
                    agent_response = {"raw": resp.text}
                return {
                    "delivery_status": "delivered",
                    "http_status": resp.status_code,
                    "agent_response": agent_response,
                }
            elif resp.status_code == 202:
                return {
                    "delivery_status": "queued",
                    "http_status": resp.status_code,
                }
            elif resp.status_code == 429:
                return {
                    "delivery_status": "failed",
                    "http_status": resp.status_code,
                    "error_code": "RATE_LIMITED",
                    "error_message": f"Agent returned 429 rate limited",
                    "failure_class": "rate_limited",
                }
            elif 400 <= resp.status_code < 500:
                error_code = "SCHEMA_INVALID" if resp.status_code == 400 else "POLICY_DENIED"
                return {
                    "delivery_status": "failed",
                    "http_status": resp.status_code,
                    "error_code": error_code,
                    "error_message": f"Agent returned HTTP {resp.status_code}",
                    "failure_class": "schema_invalid" if resp.status_code == 400 else "policy_denied",
                }
            else:
                return {
                    "delivery_status": "failed",
                    "http_status": resp.status_code,
                    "error_code": "EXECUTION_FAILED",
                    "error_message": f"Agent returned HTTP {resp.status_code}",
                    "failure_class": "execution_failed",
                }

        except httpx.ConnectError:
            return {
                "delivery_status": "failed",
                "error_code": "AGENT_UNAVAILABLE",
                "error_message": f"Could not connect to agent at {endpoint}",
                "failure_class": "agent_unavailable",
            }
        except httpx.TimeoutException:
            return {
                "delivery_status": "failed",
                "error_code": "TIMEOUT",
                "error_message": f"Delivery timed out after {timeout}s",
                "failure_class": "timeout",
            }
        except Exception as exc:
            return {
                "delivery_status": "failed",
                "error_code": "DELIVERY_ERROR",
                "error_message": str(exc),
                "failure_class": "execution_failed",
            }

    def _deliver_file_based(
        self, agent_id: str, intent_data: Dict[str, Any], intent_id: str
    ) -> Dict[str, Any]:
        """Deliver an intent by writing it to the agent's inbox directory."""
        # Validate agent_id to prevent path traversal
        ok, err = sanitize_agent_id(agent_id)
        if not ok:
            self.logger.error(f"❌ Inbox delivery blocked — invalid agent_id: {err}")
            return {
                "delivery_status": "failed",
                "error_code": "INVALID_AGENT_ID",
                "error_message": f"agent_id failed validation: {err}",
                "failure_class": "policy_denied",
            }

        inbox_dir = Path(self.config.inbox_base_dir) / agent_id
        # Resolve and verify the path stays within the inbox base
        resolved = inbox_dir.resolve()
        base_resolved = Path(self.config.inbox_base_dir).resolve()
        if not str(resolved).startswith(str(base_resolved)):
            self.logger.error(f"❌ Inbox path escape detected: {resolved}")
            return {
                "delivery_status": "failed",
                "error_code": "PATH_ESCAPE",
                "error_message": "Inbox path resolves outside base directory",
                "failure_class": "policy_denied",
            }
        try:
            inbox_dir.mkdir(parents=True, exist_ok=True)
            intent_file = inbox_dir / f"{intent_id}.json"
            intent_file.write_text(json.dumps(intent_data, indent=2, default=str))
            self.logger.info(f"📂 Intent written to inbox: {intent_file}")
            return {
                "delivery_status": "queued_no_endpoint",
                "inbox_path": str(intent_file),
            }
        except OSError as exc:
            return {
                "delivery_status": "failed",
                "error_code": "INBOX_WRITE_ERROR",
                "error_message": f"Failed to write to inbox: {exc}",
                "failure_class": "execution_failed",
            }

    # ------------------------------------------------------------------
    # Agent Health Check System
    # ------------------------------------------------------------------

    async def _check_agent_health(self, agent_id: str) -> bool:
        """Ping an HTTP agent's health endpoint."""
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        endpoint = agent.get("endpoint", "")
        if not endpoint or not endpoint.startswith("http"):
            return True  # File-based agents are always "healthy" from broker perspective

        if not _HTTPX_AVAILABLE:
            return True  # Can't check without httpx, assume healthy

        try:
            async with httpx.AsyncClient(
                timeout=self.config.health_check_timeout
            ) as client:
                resp = await client.get(f"{endpoint.rstrip('/')}/health")
            healthy = resp.status_code == 200
            with self.agent_lock:
                if agent_id in self.agents:
                    self.agents[agent_id]["status"] = "online" if healthy else "degraded"
                    self.agents[agent_id]["last_seen"] = _utcnow_iso()
            if self.builder_pool:
                self.builder_pool.report_capacity(
                    agent_id, "available" if healthy else "busy"
                )
            return healthy
        except Exception:
            with self.agent_lock:
                if agent_id in self.agents:
                    self.agents[agent_id]["status"] = "unreachable"
            if self.builder_pool:
                self.builder_pool.report_capacity(agent_id, "offline")
            return False

    async def _health_check_loop(self) -> None:
        """Background loop that checks all HTTP agents periodically."""
        while self.state == BrokerState.RUNNING and not self._shutdown_event.is_set():
            agents_snapshot = self.list_agents()
            for agent_id, agent_info in agents_snapshot.items():
                endpoint = agent_info.get("endpoint", "")
                if endpoint and endpoint.startswith("http"):
                    old_status = agent_info.get("status")
                    healthy = await self._check_agent_health(agent_id)
                    new_status = "online" if healthy else "unreachable"
                    if old_status != new_status:
                        self.logger.info(
                            f"🏥 Agent health changed: {agent_id} "
                            f"{old_status} → {new_status}"
                        )
                        self._log_event(
                            "health_change", f"Agent {agent_id} health: {old_status} → {new_status}",
                            agent_id=agent_id,
                        )
            # Check shutdown event more frequently than the full interval
            for _ in range(int(self.config.health_check_interval)):
                if self._shutdown_event.is_set():
                    break
                await asyncio.sleep(1)

    def start_health_checks(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Start the background health-check loop.

        If an external event loop is provided, the health check coroutine is
        scheduled on it.  Otherwise a dedicated daemon thread with its own
        loop is created (backwards-compatible for standalone broker usage).
        """
        if loop is not None:
            # Schedule on the provided loop (e.g. SimpHttpServer._async_loop)
            asyncio.run_coroutine_threadsafe(self._health_check_loop(), loop)
            self.logger.info("🏥 Agent health check loop started (shared loop)")
        else:
            # Standalone fallback — create own loop in a thread
            def _run():
                _loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_loop)
                try:
                    _loop.run_until_complete(self._health_check_loop())
                finally:
                    _loop.close()

            self._health_thread = threading.Thread(
                target=_run, daemon=True, name="SIMP-HealthCheck"
            )
            self._health_thread.start()
            self.logger.info("🏥 Agent health check loop started (dedicated thread)")

    def record_response(
        self,
        intent_id: str,
        response_data: Dict[str, Any],
        execution_time_ms: float = 0.0,
    ) -> bool:
        """Record response to an intent"""
        with self.intent_lock:
            record = self.intent_records.get(intent_id)
            if not record:
                self.logger.warning(f"⚠️ Response for unknown intent: {intent_id}")
                return False

            record.response = response_data
            record.status = "completed"
            record.execution_time_ms = execution_time_ms

            with self.stats_lock:
                self.stats["intents_completed"] += 1
                self.stats["total_route_time_ms"] += execution_time_ms

            self.logger.info(
                f"📥 Response recorded: {intent_id} "
                f"({execution_time_ms:.1f}ms)"
            )
            self._log_event(
                "response_recorded", f"Response for intent {intent_id} ({execution_time_ms:.1f}ms)",
                intent_id=intent_id, agent_id=record.target_agent,
            )

            # Fire memory hook on task completion
            if self.hooks:
                try:
                    self.hooks.on_task_completed({
                        "intent_id": intent_id,
                        "title": f"Intent {record.intent_type}",
                        "task_type": record.intent_type,
                        "assigned_agent": record.target_agent,
                    })
                except Exception:
                    self.logger.debug("Memory hook on_task_completed failed", exc_info=True)

            return True

    def record_error(
        self, intent_id: str, error: str, execution_time_ms: float = 0.0
    ) -> bool:
        """Record error for an intent and classify failure"""
        with self.intent_lock:
            record = self.intent_records.get(intent_id)
            if not record:
                return False

            record.error = error
            record.status = "failed"
            record.execution_time_ms = execution_time_ms

            with self.stats_lock:
                self.stats["intents_failed"] += 1

            # Classify failure for any matching ledger tasks
            fc = self.failure_handler.classify_failure(
                {"error_code": error, "error_message": error}
            )
            self.logger.error(
                f"❌ Intent failed: {intent_id} - {error} "
                f"(class: {fc.value})"
            )
            self._log_event(
                "intent_error", f"Intent {intent_id} failed: {error}",
                level="error", intent_id=intent_id,
            )
            return True

    def _map_intent_to_task_type(self, intent_type: str) -> str:
        """Map an intent_type string to a valid task_type."""
        mapping = {
            "code_task": "implementation",
            "code_editing": "implementation",
            "planning": "architecture",
            "research": "research",
            "market_analysis": "analysis",
            "trade_execution": "implementation",
            "orchestration": "architecture",
            "scaffolding": "scaffold",
            "test_harness": "test",
            "prediction_signal": "analysis",
            "arbitrage": "implementation",
            "spec": "spec",
            "architecture": "architecture",
            "docs": "docs",
        }
        return mapping.get(intent_type, "implementation")

    def _log_event(
        self,
        event_type: str,
        message: str,
        level: str = "info",
        agent_id: Optional[str] = None,
        intent_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a structured event to the ring buffer.

        This supplements (does NOT replace) Python logging. Events are
        queryable via get_logs() and the /logs HTTP endpoint.
        """
        event: Dict[str, Any] = {
            "timestamp": _utcnow_iso(),
            "event_type": event_type,
            "level": level,
            "message": message,
        }
        if agent_id:
            event["agent_id"] = agent_id
        if intent_id:
            event["intent_id"] = intent_id
        if extra:
            event.update(extra)
        with self._event_log_lock:
            self._event_log.append(event)

    def get_intent_status(self, intent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an intent"""
        with self.intent_lock:
            record = self.intent_records.get(intent_id)
            if not record:
                return None

            return {
                "intent_id": record.intent_id,
                "source_agent": record.source_agent,
                "target_agent": record.target_agent,
                "intent_type": record.intent_type,
                "status": record.status,
                "timestamp": record.timestamp,
                "execution_time_ms": record.execution_time_ms,
                "response": record.response,
                "error": record.error,
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get broker statistics"""
        with self.stats_lock:
            stats = dict(self.stats)

        with self.agent_lock:
            stats["agents_online"] = len(self.agents)
            stats["agents_registered"] = len(self.agents)

        with self.intent_lock:
            stats["pending_intents"] = sum(
                1
                for r in self.intent_records.values()
                if r.status == "pending"
            )

        # Calculate averages
        if stats["intents_completed"] > 0:
            stats["avg_route_time_ms"] = (
                stats["total_route_time_ms"] / stats["intents_completed"]
            )
        else:
            stats["avg_route_time_ms"] = 0.0

        return stats

    def get_logs(self, limit: int = 100) -> list:
        """Get recent structured events from the ring buffer."""
        limit = max(1, min(limit, 500))
        with self._event_log_lock:
            items = list(self._event_log)
        # Most recent first
        items.reverse()
        return items[:limit]

    def start(self, async_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Start the broker.

        Args:
            async_loop: Optional shared event loop for scheduling background tasks.
        """
        self.state = BrokerState.RUNNING
        self.start_health_checks(loop=async_loop)

        # Start orchestration loop
        try:
            self._orchestration_loop = OrchestrationLoop(
                broker=self,
                task_ledger=self.task_ledger,
            )
            if async_loop:
                import asyncio as _asyncio
                _asyncio.run_coroutine_threadsafe(
                    self._orchestration_loop.run(), async_loop
                )
            self._log_event("orchestration_started", "Orchestration loop started")
            self.logger.info("🔄 Orchestration loop started")
        except Exception as exc:
            self.logger.warning(f"⚠️ Orchestration loop failed to start: {exc}")

        self.logger.info("✅ SIMP Broker RUNNING")

    def stop(self) -> None:
        """Gracefully stop the broker.

        1. Set state to SHUTTING_DOWN so no new intents are accepted
        2. Signal the health-check loop to exit
        3. Wait for the health thread to finish (up to 5s)
        4. Log the event and set STOPPED
        """
        self.state = BrokerState.SHUTTING_DOWN
        self._log_event("broker_stopping", "Broker shutdown initiated", level="warning")
        self.logger.info("🛑 SIMP Broker shutting down...")

        # Signal health-check loop to stop
        self._shutdown_event.set()

        # Wait for health thread to finish
        if hasattr(self, "_health_thread") and self._health_thread.is_alive():
            self._health_thread.join(timeout=5)
            if self._health_thread.is_alive():
                self.logger.warning("⚠️ Health check thread did not stop within 5s")

        # Stop orchestration loop
        if self._orchestration_loop:
            self._orchestration_loop.stop()
            self._log_event("orchestration_stopped", "Orchestration loop stopped")

        self.state = BrokerState.STOPPED
        self._log_event("broker_stopped", "Broker stopped")
        self.logger.info("✅ SIMP Broker stopped")

    def pause(self) -> None:
        """Pause the broker"""
        self.state = BrokerState.PAUSED
        self.logger.info("⏸️ SIMP Broker paused")

    def resume(self) -> None:
        """Resume the broker"""
        self.state = BrokerState.RUNNING
        self.logger.info("▶️ SIMP Broker resumed")

    def health_check(self) -> Dict[str, Any]:
        """Health check status"""
        return {
            "status": "healthy" if self.state == BrokerState.RUNNING else "degraded",
            "state": self.state.value,
            "agents_online": len(self.agents),
            "pending_intents": sum(
                1
                for r in self.intent_records.values()
                if r.status == "pending"
            ),
            "timestamp": _utcnow_iso(),
        }
