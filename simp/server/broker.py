"""
SIMP Broker: Central Message Router

Acts as the central hub for inter-agent communication.
Receives intents, routes to appropriate agents, collects responses.
"""

import asyncio
import json
import logging
import os
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
import uuid
import queue
import threading
import time

from config.config import SimpConfig
from simp.crypto import SimpCrypto
from simp.task_ledger import TaskLedger
from simp.models.canonical_intent import CanonicalIntent, INTENT_TYPE_REGISTRY
from simp.models.failure_taxonomy import FailureHandler, FailureClass
from simp.routing.builder_pool import BuilderPool
from simp.server.request_guards import sanitize_agent_id
from simp.orchestration.orchestration_loop import OrchestrationLoop
from simp.projectx.computer import ProjectXComputer, ACTION_TIERS

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


from simp.security.brp_models import BRPPlan, BRPMode, BRPEvent, BRPEventType, BRPObservation
from simp.security.brp_bridge import BRPBridge


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


_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)


@dataclass
class BrokerConfig:
    """Broker configuration — reads defaults from SimpConfig."""
    port: int = 0
    host: str = ""
    max_agents: int = 0
    max_pending_intents: int = 1000
    intent_timeout: float = 30.0  # seconds
    delivery_timeout: float = 30.0  # seconds — HTTP delivery timeout
    health_check_interval: float = 0.0  # seconds — agent health check interval
    health_check_timeout: float = 0.0  # seconds — per-agent health check timeout
    inbox_base_dir: str = os.path.join(_REPO_ROOT, "data", "inboxes")
    enable_logging: bool = True
    log_level: str = ""
    max_log_lines: int = 10000
    max_intent_records: int = 10000

    def __post_init__(self):
        """Fill in defaults from SimpConfig if not explicitly set."""
        sc = SimpConfig()
        if not self.port:
            self.port = sc.PORT
        if not self.host:
            self.host = sc.HOST
        if not self.max_agents:
            self.max_agents = sc.MAX_AGENTS
        if not self.health_check_interval:
            self.health_check_interval = sc.HEALTH_CHECK_INTERVAL
        if not self.health_check_timeout:
            self.health_check_timeout = sc.HEALTH_CHECK_TIMEOUT
        if not self.log_level:
            self.log_level = sc.LOG_LEVEL


@dataclass
class IntentRecord:
    """Record of an intent in flight"""
    intent_id: str
    source_agent: str
    target_agent: str
    intent_type: str
    timestamp: str
    status: str  # pending, executing, completed, failed, expired
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    # Sprint 51 — delivery tracking
    delivery_status: Optional[str] = None
    delivery_attempts: int = 0
    delivery_elapsed_ms: float = 0.0
    # Sprint 63 — planner telemetry
    planned_at: Optional[str] = None
    dispatched_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0


class SimpBroker:
    """
    SIMP Protocol Broker

    Central message router for inter-agent communication.
    Manages agent registration, intent routing, and response handling.
    """

    def __init__(self, config: Optional[BrokerConfig] = None,
                 task_ledger: Optional[TaskLedger] = None,
                 hooks: Optional[Any] = None,
                 brp_bridge: Optional[BRPBridge] = None):
        """Initialize SIMP Broker

        Args:
            config: Broker configuration.
            task_ledger: Optional TaskLedger instance.
            hooks: Optional MemoryHooks instance for event-driven memory updates.
            brp_bridge: Optional BRP bridge for plan-level security evaluation.
        """
        self.config = config or BrokerConfig()
        try:
            self.brp_bridge = brp_bridge or BRPBridge()
        except Exception as brp_err:
            # Fallback: create a best-effort bridge; log the error visibly.
            import traceback
            print(f"[BRP] WARNING: BRP bridge init failed: {brp_err}")
            traceback.print_exc()
            self.brp_bridge = BRPBridge(data_dir="/tmp/simp_brp_fallback")
        self.state = BrokerState.INITIALIZING
        self.hooks = hooks
        self.logger = self._setup_logging()
        self.logger.info(
            "[BRP] Bill Russell Protocol active — mode=%s, data_dir=%s",
            self.brp_bridge.default_mode, self.brp_bridge.data_dir,
        )

        # Sprint 64 — restart resilience
        self._startup_at: datetime = datetime.now(timezone.utc)
        self._ready: bool = False
        self._intents_loaded_from_disk: int = 0

        # Agent registry
        self.agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent info
        self.agent_lock = threading.RLock()

        # Intent tracking — bounded OrderedDict with LRU eviction
        self._max_intent_records = self.config.max_intent_records
        self.intent_records: OrderedDict[str, IntentRecord] = OrderedDict()
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

        # ProjectX computer-use layer (optional)
        self._projectx: Optional[ProjectXComputer] = None

        # HTTP connection pool (initialized in start(), closed in stop())
        self._http_pool: Optional["httpx.AsyncClient"] = None

        # Sprint 22: Circuit breaker state
        self._circuit_failures: Dict[str, Dict[str, Any]] = {}  # agent_id -> {"count": int, "last_failure": float}
        self._circuit_open_until: Dict[str, float] = {}  # agent_id -> timestamp

        # Shutdown coordination
        self._shutdown_event = threading.Event()

        # Background task tracking for clean cancellation
        self._background_tasks: list = []
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None

        # Sprint 51 — delivery engine
        from simp.server.delivery import DEFAULT_DELIVERY_ENGINE
        self.delivery_engine = DEFAULT_DELIVERY_ENGINE

        # Sprint 52 — intent ledger (renamed from task_ledger in Sprint 61)
        from simp.server.intent_ledger import INTENT_LEDGER
        self.intent_ledger = INTENT_LEDGER
        # Load pending intents from intent ledger on init (Sprint 64: count loaded)
        try:
            for rec in self.intent_ledger.load_pending():
                iid = rec.get("intent_id")
                if iid and iid not in self.intent_records:
                    self.intent_records[iid] = IntentRecord(
                        intent_id=iid,
                        source_agent=rec.get("source_agent", ""),
                        target_agent=rec.get("target_agent", ""),
                        intent_type=rec.get("intent_type", ""),
                        timestamp=rec.get("timestamp", ""),
                        status="pending",
                    )
                    self._intents_loaded_from_disk += 1
        except Exception:
            pass

        # Sprint 53 — routing engine
        from simp.server.routing_engine import RoutingEngine
        self.routing_engine = RoutingEngine()

        self.logger.info(f"🚀 SIMP Broker initialized (v0.3.0)")
        self.logger.info(f"   Config: {self.config.host}:{self.config.port}")
        self.logger.info(f"   Max agents: {self.config.max_agents}")
        self.logger.info(f"   Intent timeout: {self.config.intent_timeout}s")

    def init_projectx(self, log_dir: Optional[str] = None, max_tier: int = 2) -> None:
        """Initialize the ProjectX computer-use capability."""
        try:
            self._projectx = ProjectXComputer(
                log_dir=log_dir or "./projectx_logs",
                max_tier=max_tier,
            )
            self._log_event("projectx_initialized", "ProjectX computer-use layer initialized")
            self.logger.info("🖥️ ProjectX computer-use layer initialized")
        except Exception as exc:
            self.logger.warning(f"⚠️ ProjectX initialization failed: {exc}")

    @property
    def projectx(self) -> Optional[ProjectXComputer]:
        """Access the ProjectX computer-use layer."""
        return self._projectx

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

    def _add_intent_record(self, intent_id: str, record: IntentRecord) -> None:
        """Add an intent record with LRU eviction when at capacity.

        Must be called while holding self.intent_lock.
        """
        if intent_id in self.intent_records:
            self.intent_records.move_to_end(intent_id)
            self.intent_records[intent_id] = record
            return
        while len(self.intent_records) >= self._max_intent_records:
            self.intent_records.popitem(last=False)
        self.intent_records[intent_id] = record

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

            now = _utcnow_iso()
            is_file_based = "(file-based)" in (endpoint or "")
            self.agents[agent_id] = {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "endpoint": endpoint,
                "metadata": metadata or {},
                "public_key": (metadata or {}).get("public_key"),
                "simp_versions": (metadata or {}).get("simp_versions", ["1.0"]),
                "registered_at": now,
                "intents_received": 0,
                "intents_completed": 0,
                "status": "online",
                "health_check_failures": 0,
                # Sprint 62 — heartbeat tracking
                "last_heartbeat": now,
                "heartbeat_count": 0,
                "stale": False,
                "file_based": is_file_based,
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

    # ------------------------------------------------------------------
    # Sprint 62: Heartbeat System
    # ------------------------------------------------------------------

    def record_heartbeat(self, agent_id: str) -> bool:
        """Update heartbeat timestamp for an agent. Returns True if found."""
        with self.agent_lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return False
            agent["last_heartbeat"] = _utcnow_iso()
            agent["heartbeat_count"] = agent.get("heartbeat_count", 0) + 1
            agent["status"] = "active"
            agent["stale"] = False
            return True

    def get_stale_agents(self, stale_after_seconds: float = 90.0) -> list:
        """Return agent_ids whose last_heartbeat exceeds the threshold.
        Excludes file-based agents. Returns [] during startup grace period."""
        # Sprint 64 — startup grace period
        if hasattr(self, "_startup_at") and self._startup_at:
            uptime = (datetime.now(timezone.utc) - self._startup_at).total_seconds()
            if uptime < 60.0:
                return []

        now = datetime.now(timezone.utc)
        stale = []
        with self.agent_lock:
            for aid, info in self.agents.items():
                if info.get("file_based"):
                    continue
                hb = info.get("last_heartbeat", "")
                if not hb:
                    continue
                try:
                    hb_dt = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                    if (now - hb_dt).total_seconds() > stale_after_seconds:
                        stale.append(aid)
                        info["stale"] = True
                except (ValueError, TypeError):
                    pass
        return stale

    def deregister_stale_agents(self, deregister_after_seconds: float = 300.0) -> list:
        """Deregister agents whose heartbeat exceeds the threshold.
        Excludes file-based agents. Returns list of deregistered ids.
        Returns [] during startup grace period."""
        # Sprint 64 — startup grace period
        if hasattr(self, "_startup_at") and self._startup_at:
            uptime = (datetime.now(timezone.utc) - self._startup_at).total_seconds()
            if uptime < 60.0:
                return []

        now = datetime.now(timezone.utc)
        to_deregister = []
        with self.agent_lock:
            for aid, info in list(self.agents.items()):
                if info.get("file_based"):
                    continue
                hb = info.get("last_heartbeat", "")
                if not hb:
                    continue
                try:
                    hb_dt = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                    if (now - hb_dt).total_seconds() > deregister_after_seconds:
                        to_deregister.append(aid)
                except (ValueError, TypeError):
                    pass
            for aid in to_deregister:
                del self.agents[aid]
                self.logger.info(f"Deregistered stale agent: {aid}")
                self._log_event("agent_stale_deregistered", f"Stale agent {aid} deregistered", agent_id=aid)
        return to_deregister

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent information"""
        with self.agent_lock:
            return self.agents.get(agent_id)

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all registered agents"""
        with self.agent_lock:
            return dict(self.agents)

    def evaluate_plan(self, steps, source_agent="mother_goose", mode=BRPMode.SHADOW.value):
        """Submit a multi-step plan to BRP for review (Mother Goose integration).

        Args:
            steps: List of plan step dicts, each with at least an "action" key.
            source_agent: Identifier of the planning agent.
            mode: BRP evaluation mode (default shadow).

        Returns:
            BRPResponse as a dict.
        """
        plan = BRPPlan(source_agent=source_agent, steps=steps, mode=mode)
        response = self.brp_bridge.evaluate_plan(plan)
        self.logger.info(
            f"BRP plan review: {plan.plan_id} -> {response.decision} "
            f"(threat={response.threat_score:.2f})"
        )
        return response.to_dict()

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

        # Normalize to canonical format
        canonical = CanonicalIntent.from_dict(intent_data)
        errors = canonical.validate()
        if errors:
            return {"status": "error", "errors": errors}
        intent_data = canonical.to_dict()

        # Version check
        supported_versions = {"1.0"}
        intent_version = canonical.simp_version
        if intent_version and intent_version not in supported_versions:
            self.logger.warning(f"Intent has unsupported protocol version: {intent_version}")
            # Allow through with warning (don't break backward compat yet)

        # Signature verification (if enabled)
        simp_config = SimpConfig()
        if simp_config.REQUIRE_SIGNATURES:
            signature = intent_data.get("signature")
            source_id = intent_data.get("source_agent", "")
            source_info = self.agents.get(source_id, {})
            public_key_pem = source_info.get("public_key")

            if signature and public_key_pem:
                try:
                    pub_key = SimpCrypto.load_public_key(public_key_pem.encode() if isinstance(public_key_pem, str) else public_key_pem)
                    if not SimpCrypto.verify_signature(intent_data, pub_key):
                        return {"status": "error", "error": "Invalid signature"}
                except Exception as exc:
                    self.logger.warning(f"Signature verification failed: {exc}")
                    return {"status": "error", "error": f"Signature verification error: {exc}"}
            elif signature and not public_key_pem:
                self.logger.warning(f"Agent '{source_id}' has no public key; signature cannot be verified")
            # If no signature provided, allow through with warning (graceful mode)

        intent_id = intent_data.get("intent_id", str(uuid.uuid4()))
        source_agent = intent_data.get("source_agent", "client")
        target_agent = intent_data.get("target_agent")
        intent_type = intent_data.get("intent_type", "unknown")
        delivery_start = time.monotonic()

        # --- BRP event-level evaluation for every routed intent ---
        brp_plan_response = None
        brp_event_id = ""
        try:
            brp_mode = intent_data.get("brp_mode", self.brp_bridge.default_mode)
            brp_event = BRPEvent(
                source_agent=source_agent,
                event_type=BRPEventType.PEER_INTENT.value,
                action=intent_type,
                context={
                    "intent_id": intent_id,
                    "target_agent": intent_data.get("target_agent", ""),
                    "params": intent_data.get("params", {}),
                },
                mode=brp_mode,
                tags=["broker", "route_intent", intent_type],
            )
            brp_event_id = brp_event.event_id
            self.brp_bridge.evaluate_event(brp_event)
        except Exception:
            self.logger.warning("BRP event evaluation failed for intent %s", intent_id, exc_info=True)

        # --- BRP plan-level evaluation for multi-step intents ---
        steps = intent_data.get("params", {}).get("steps") if isinstance(intent_data.get("params"), dict) else None
        if steps and isinstance(steps, list):
            try:
                brp_plan_response = self.evaluate_plan(
                    steps=steps,
                    source_agent=source_agent,
                    mode=intent_data.get("brp_mode", self.brp_bridge.default_mode),
                )
            except Exception:
                self.logger.warning("BRP plan evaluation failed for intent %s", intent_id, exc_info=True)

        with self.stats_lock:
            self.stats["intents_received"] += 1

        # Sprint 53 — routing engine: resolve target when "auto" or missing
        if not target_agent or target_agent == "auto":
            with self.agent_lock:
                agents_snapshot = dict(self.agents)
            decision = self.routing_engine.resolve(intent_type, target_agent, agents_snapshot)
            if decision.target_agent:
                target_agent = decision.target_agent

        # Log to task ledger — reuse existing task if one was already created
        existing_task_id = intent_data.get("task_id") or intent_data.get("params", {}).get("task_id")
        existing_task = self.task_ledger.get_task(existing_task_id) if existing_task_id else None

        if existing_task:
            task_id = existing_task["task_id"]
        else:
            task_id = self.task_ledger.create_task(
                title=f"Intent: {intent_type}",
                description=f"Route intent {intent_id} from {source_agent} to {target_agent or 'unknown'}",
                task_type=canonical.get_task_type(),
                assigned_agent=target_agent,
                tags=["intent", intent_type],
            )

        # Handle computer_use intents via ProjectX
        if intent_type.startswith("computer_use") and self._projectx:
            return await self._handle_computer_use_intent(intent_data, task_id)

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
                    self._add_intent_record(intent_id, record)

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

        # Record intent as pending — Sprint 63: set planned_at
        now_iso = _utcnow_iso()
        with self.intent_lock:
            record = IntentRecord(
                intent_id=intent_id,
                source_agent=source_agent,
                target_agent=target_agent,
                intent_type=intent_type,
                timestamp=now_iso,
                status="pending",
                planned_at=now_iso,
            )
            self._add_intent_record(intent_id, record)

        self.logger.info(
            f"📤 Routing intent: {intent_id} ({intent_type}) "
            f"{source_agent} → {target_agent}"
        )
        self._log_event(
            "intent_routed", f"Intent {intent_id} ({intent_type}) {source_agent} → {target_agent}",
            agent_id=target_agent, intent_id=intent_id,
        )

        # Sprint 63: set dispatched_at just before delivery
        with self.intent_lock:
            if intent_id in self.intent_records:
                self.intent_records[intent_id].dispatched_at = _utcnow_iso()

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

                fallback_succeeded = False
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
                            fallback_succeeded = delivery_result.get("delivery_status") != "failed"

                # If HTTP delivery and fallback both failed, write to file
                # inbox so the agent's file poller can pick it up
                if not fallback_succeeded and delivery_result.get("delivery_status") == "failed":
                    self.logger.info(
                        f"📂 HTTP delivery failed for '{target_agent}', "
                        f"falling back to file-based inbox delivery"
                    )
                    delivery_result = self._deliver_file_based(
                        target_agent, intent_data, intent_id
                    )
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
        if brp_plan_response is not None:
            route_result["brp_plan_review"] = brp_plan_response

        # --- BRP post-routing observation ---
        if brp_event_id:
            try:
                obs = BRPObservation(
                    source_agent="simp_broker",
                    event_id=brp_event_id,
                    action=intent_type,
                    outcome=delivery_status,
                    result_data={"target_agent": target_agent, "task_id": task_id},
                    mode=self.brp_bridge.default_mode,
                    tags=["broker", "route_intent", "post_route"],
                )
                self.brp_bridge.ingest_observation(obs)
            except Exception:
                self.logger.warning("BRP post-route observation failed", exc_info=True)

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
            if self._http_pool:
                resp = await self._http_pool.post(url, json=intent_data)
            else:
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
    # Sprint 22: Circuit Breaker
    # ------------------------------------------------------------------

    def _record_circuit_failure(self, agent_id: str) -> None:
        """Record a delivery failure for the circuit breaker."""
        now = time.time()
        entry = self._circuit_failures.setdefault(agent_id, {"count": 0, "last_failure": 0})
        # Reset if last failure was >10 min ago
        if now - entry["last_failure"] > 600:
            entry["count"] = 0
        entry["count"] += 1
        entry["last_failure"] = now
        # Open circuit after 5 failures in 10 minutes
        if entry["count"] >= 5:
            self._circuit_open_until[agent_id] = now + 300  # 5 min cooldown
            self._log_event("circuit_breaker_opened", f"Circuit breaker opened for '{agent_id}'")

    def _record_circuit_success(self, agent_id: str) -> None:
        """Reset circuit breaker state on successful delivery."""
        self._circuit_failures.pop(agent_id, None)
        self._circuit_open_until.pop(agent_id, None)

    def _is_circuit_open(self, agent_id: str) -> bool:
        """Check if the circuit breaker is open for an agent."""
        until = self._circuit_open_until.get(agent_id, 0)
        if time.time() < until:
            return True
        # Circuit closed — remove entry
        self._circuit_open_until.pop(agent_id, None)
        return False

    async def _deliver_with_retry(
        self, intent_data: Dict[str, Any], task_id: str, max_retries: int = 3
    ) -> Dict[str, Any]:
        """Deliver intent with multi-hop retry and exponential backoff."""
        target = intent_data.get("target_agent", "")
        excluded: set = set()
        last_error = None

        for attempt in range(max_retries):
            if attempt > 0:
                # Exponential backoff
                delay = min(2 ** attempt, 30)
                await asyncio.sleep(delay)

            # Check circuit breaker
            if self._is_circuit_open(target):
                excluded.add(target)
                # Find alternative via builder pool
                if self.builder_pool:
                    task_type = intent_data.get("task_type", intent_data.get("intent_type", "implementation"))
                    target = self.builder_pool.get_builder(task_type, exclude=excluded)
                    if not target:
                        last_error = "No available agents after circuit breaker exclusion"
                        continue

            if not target:
                last_error = "No target agent available"
                continue

            # Look up target endpoint
            agent_info = self.get_agent(target)
            if not agent_info:
                excluded.add(target)
                if self.builder_pool:
                    task_type = intent_data.get("task_type", intent_data.get("intent_type", "implementation"))
                    target = self.builder_pool.get_builder(task_type, exclude=excluded)
                last_error = f"Agent '{target}' not registered"
                continue

            endpoint = agent_info.get("endpoint", "")
            try:
                if endpoint and endpoint.startswith("http"):
                    result = await self._deliver_http(endpoint, intent_data, intent_data.get("intent_id", ""))
                else:
                    result = self._deliver_file_based(target, intent_data, intent_data.get("intent_id", ""))

                if result.get("delivery_status") in ("delivered", "queued", "queued_no_endpoint"):
                    self._record_circuit_success(target)
                    return result
                else:
                    last_error = result.get("error_message", "Delivery failed")
                    self._record_circuit_failure(target)
                    excluded.add(target)
                    # Get next candidate
                    if self.builder_pool:
                        task_type = intent_data.get("task_type", intent_data.get("intent_type", "implementation"))
                        target = self.builder_pool.get_builder(task_type, exclude=excluded)
            except Exception as exc:
                last_error = str(exc)
                self._record_circuit_failure(target)
                excluded.add(target)
                if self.builder_pool:
                    task_type = intent_data.get("task_type", intent_data.get("intent_type", "implementation"))
                    target = self.builder_pool.get_builder(task_type, exclude=excluded)

        return {"delivery_status": "failed", "error_message": f"All retry attempts exhausted: {last_error}"}

    async def _handle_computer_use_intent(
        self, intent_data: Dict[str, Any], task_id: str
    ) -> Dict[str, Any]:
        """Handle a computer_use intent by delegating to ProjectX."""
        params = intent_data.get("params", {})
        steps = params.get("steps", [])

        if not steps:
            # Design-only intent (like our design review) — no execution
            return {
                "status": "acknowledged",
                "intent_type": intent_data.get("intent_type", ""),
                "message": "Computer-use intent acknowledged (no execution steps provided)",
                "task_id": task_id,
            }

        results = []
        for step in steps:
            try:
                result = self._projectx.safe_execute(step)
                results.append(result)
                if not result.get("success"):
                    break  # Stop on first failure
            except Exception as exc:
                results.append({
                    "success": False,
                    "error": str(exc),
                    "step": step,
                })
                break

        all_success = all(r.get("success") for r in results)
        self.task_ledger.update_status(
            task_id,
            "completed" if all_success else "failed",
        )

        return {
            "status": "completed" if all_success else "failed",
            "task_id": task_id,
            "steps_executed": len(results),
            "steps_total": len(steps),
            "results": results,
        }

    # ------------------------------------------------------------------
    # Agent Health Check System
    # ------------------------------------------------------------------

    async def _check_agent_health(self, agent_id: str) -> bool:
        """Ping an HTTP agent's health endpoint.

        Uses the shared ``_http_pool`` when available, falling back to a
        one-shot client otherwise.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        endpoint = agent.get("endpoint", "")
        if not endpoint or not endpoint.startswith("http"):
            return True  # File-based agents are always "healthy" from broker perspective

        if not _HTTPX_AVAILABLE:
            return True  # Can't check without httpx, assume healthy

        try:
            url = f"{endpoint.rstrip('/')}/health"
            if self._http_pool:
                resp = await self._http_pool.get(url)
            else:
                async with httpx.AsyncClient(
                    timeout=self.config.health_check_timeout
                ) as client:
                    resp = await client.get(url)

            if resp.status_code == 200:
                with self.agent_lock:
                    if agent_id in self.agents:
                        self.agents[agent_id]["status"] = "online"
                        self.agents[agent_id]["last_seen"] = _utcnow_iso()
                        self.agents[agent_id]["health_check_failures"] = 0
                if self.builder_pool:
                    self.builder_pool.report_capacity(agent_id, "available")
                return True
            else:
                await self._record_health_failure(agent_id)
                return False
        except Exception:
            await self._record_health_failure(agent_id)
            return False

    async def _record_health_failure(self, agent_id: str) -> None:
        """Record a health check failure. Auto-deregister after threshold."""
        threshold = 3
        with self.agent_lock:
            if agent_id not in self.agents:
                return
            self.agents[agent_id]["health_check_failures"] = (
                self.agents[agent_id].get("health_check_failures", 0) + 1
            )
            failures = self.agents[agent_id]["health_check_failures"]
            self.agents[agent_id]["status"] = "unreachable"

        if self.builder_pool:
            self.builder_pool.report_capacity(agent_id, "offline")

        if failures >= threshold:
            self.logger.warning(
                f"Agent '{agent_id}' failed {failures} consecutive health checks — auto-deregistering"
            )
            self._log_event(
                "agent_auto_deregistered",
                f"Agent '{agent_id}' auto-deregistered after {failures} health check failures",
                agent_id=agent_id,
            )
            with self.agent_lock:
                self.agents.pop(agent_id, None)
            with self.stats_lock:
                self.stats["agents_registered"] = max(
                    0, self.stats.get("agents_registered", 0) - 1
                )

    async def _bounded_health_check(
        self, semaphore: asyncio.Semaphore, agent_id: str, agent_info: Dict[str, Any]
    ) -> None:
        """Health check with semaphore-bounded concurrency."""
        async with semaphore:
            endpoint = agent_info.get("endpoint", "")
            if not endpoint or not endpoint.startswith("http"):
                return
            old_status = agent_info.get("status")
            healthy = await self._check_agent_health(agent_id)
            new_status = "online" if healthy else "unreachable"
            if old_status != new_status:
                self.logger.info(
                    f"🏥 Agent health changed: {agent_id} "
                    f"{old_status} → {new_status}"
                )
                self._log_event(
                    "health_change",
                    f"Agent {agent_id} health: {old_status} → {new_status}",
                    agent_id=agent_id,
                )

    async def _health_check_loop(self) -> None:
        """Check all agent health concurrently with bounded parallelism."""
        semaphore = asyncio.Semaphore(20)  # Max 20 concurrent checks

        while self.state == BrokerState.RUNNING and not self._shutdown_event.is_set():
            try:
                agents_snapshot = list(self.agents.items())
                if agents_snapshot:
                    tasks = [
                        self._bounded_health_check(semaphore, agent_id, agent_info)
                        for agent_id, agent_info in agents_snapshot
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as exc:
                self.logger.error(f"Health check loop error: {exc}")

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
            fut = asyncio.run_coroutine_threadsafe(self._health_check_loop(), loop)
            self._background_tasks.append(fut)
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
            # Sprint 63 — set completed_at
            record.completed_at = _utcnow_iso()

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

            # If response contains decomposed subtasks, wire them into the task ledger
            if response_data.get("status") == "decomposed" and "subtasks" in response_data:
                subtask_defs = response_data["subtasks"]
                # Find the task_id associated with this intent
                task_candidates = self.task_ledger.list_tasks()
                for tc in task_candidates:
                    if tc.get("description", "").find(intent_id) != -1:
                        self.task_ledger.decompose_task(tc["task_id"], subtask_defs)
                        break

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

            # Sprint 52 — ledger append on response
            self.intent_ledger.append({
                "intent_id": intent_id,
                "status": "completed",
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            })

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
            # Sprint 63 — set completed_at
            record.completed_at = _utcnow_iso()

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

            # Sprint 52 — ledger append on error
            self.intent_ledger.append({
                "intent_id": intent_id,
                "status": "failed",
                "error": error,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            })

            return True

    def _map_intent_to_task_type(self, intent_type: str) -> str:
        """Map an intent_type string to a valid task_type.

        Delegates to INTENT_TYPE_REGISTRY via CanonicalIntent.
        Retained for backward compatibility.
        """
        entry = INTENT_TYPE_REGISTRY.get(intent_type, {})
        return entry.get("task_type", "implementation")

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

    MAX_INTENT_RECORDS = 10000

    def _evict_oldest_records(self, count: int = 1000) -> int:
        """Evict the oldest completed/failed records. Must hold intent_lock."""
        removable = [
            (iid, rec)
            for iid, rec in self.intent_records.items()
            if rec.status in ("completed", "failed", "delivered")
        ]
        removable.sort(key=lambda x: x[1].timestamp)
        evicted = 0
        for iid, _ in removable[:count]:
            del self.intent_records[iid]
            evicted += 1
        return evicted

    async def _cleanup_intent_records(self):
        """Evict completed/failed intent records older than TTL."""
        while self.state in (BrokerState.RUNNING, BrokerState.INITIALIZING) and not self._shutdown_event.is_set():
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.config.intent_timeout * 120)
                with self.intent_lock:
                    to_remove = []
                    for intent_id, record in self.intent_records.items():
                        if record.status in ("completed", "failed", "delivered"):
                            record_time = record.timestamp
                            try:
                                if record_time and datetime.fromisoformat(record_time.replace("Z", "+00:00")) < cutoff:
                                    to_remove.append(intent_id)
                            except (ValueError, TypeError):
                                pass
                    for intent_id in to_remove:
                        del self.intent_records[intent_id]
                    if to_remove:
                        self._log_event("intent_records_evicted", f"Evicted {len(to_remove)} stale intent records")
            except Exception as exc:
                self.logger.error(f"Intent record cleanup error: {exc}")
            await asyncio.sleep(300)

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
                # Sprint 63 — telemetry fields
                "planned_at": record.planned_at,
                "dispatched_at": record.dispatched_at,
                "completed_at": record.completed_at,
                "retry_count": record.retry_count,
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

        # Queue depth
        stats["queue_depth"] = self.intent_queue.qsize()

        # Protocol versioning
        stats["protocol_versions"] = ["1.0"]
        stats["simp_version"] = "0.4.0"

        # Calculate averages
        if stats["intents_completed"] > 0:
            stats["avg_route_time_ms"] = (
                stats["total_route_time_ms"] / stats["intents_completed"]
            )
        else:
            stats["avg_route_time_ms"] = 0.0

        # Sprint 52 — intent ledger stats
        try:
            stats["task_ledger"] = self.intent_ledger.get_stats()
        except Exception:
            stats["task_ledger"] = {}

        # Sprint 62 — heartbeat stats
        with self.agent_lock:
            stats["stale_agents"] = sum(
                1 for a in self.agents.values()
                if a.get("stale") and not a.get("file_based")
            )
            stats["file_based_agents"] = sum(
                1 for a in self.agents.values()
                if a.get("file_based")
            )

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
        self._background_tasks = []
        self._async_loop = async_loop

        # Expire stale tasks from previous sessions (>1 hour old)
        try:
            expired = self.task_ledger.expire_stale_on_startup(max_age_seconds=3600.0)
            if expired:
                self.logger.info(f"♻️ Expired {expired} stale tasks from previous session")
                self._log_event("stale_tasks_expired", f"Expired {expired} stale tasks on startup")
        except Exception as exc:
            self.logger.warning(f"⚠️ Stale task cleanup failed: {exc}")

        # Initialize shared HTTP connection pool
        if _HTTPX_AVAILABLE and self._http_pool is None:
            self._http_pool = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.delivery_timeout, connect=5.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                follow_redirects=False,
            )

        self.start_health_checks(loop=async_loop)

        # Start intent record cleanup coroutine
        if async_loop:
            fut = asyncio.run_coroutine_threadsafe(self._cleanup_intent_records(), async_loop)
            self._background_tasks.append(fut)
        else:
            def _run_cleanup():
                _loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_loop)
                try:
                    _loop.run_until_complete(self._cleanup_intent_records())
                finally:
                    _loop.close()
            self._cleanup_thread = threading.Thread(
                target=_run_cleanup, daemon=True, name="SIMP-IntentCleanup"
            )
            self._cleanup_thread.start()

        # Start orchestration loop
        try:
            self._orchestration_loop = OrchestrationLoop(
                broker=self,
                task_ledger=self.task_ledger,
            )
            if async_loop:
                fut = asyncio.run_coroutine_threadsafe(
                    self._orchestration_loop.run(), async_loop
                )
                self._background_tasks.append(fut)
            self._log_event("orchestration_started", "Orchestration loop started")
            self.logger.info("🔄 Orchestration loop started")
        except Exception as exc:
            self.logger.warning(f"⚠️ Orchestration loop failed to start: {exc}")

        # Start intent queue workers (additive — does not alter inline route_intent)
        worker_count = 4
        if async_loop:
            for _ in range(worker_count):
                fut = asyncio.run_coroutine_threadsafe(self._intent_queue_worker(), async_loop)
                self._background_tasks.append(fut)
        self.logger.info(f"📬 Intent queue workers started ({worker_count})")

        # Sprint 64 — mark ready
        self._ready = True
        self.logger.info(
            f"✅ Broker ready — {len(self.agents)} agents, "
            f"{self._intents_loaded_from_disk} intents loaded"
        )
        self.logger.info("✅ SIMP Broker RUNNING")

    async def _intent_queue_worker(self) -> None:
        """Worker that processes intents from the queue (additive path)."""
        while self.state == BrokerState.RUNNING and not self._shutdown_event.is_set():
            try:
                try:
                    intent_data = self.intent_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue
                try:
                    await self.route_intent(intent_data)
                except Exception as exc:
                    self.logger.error(f"Intent queue worker error: {exc}")
            except Exception as exc:
                self.logger.error(f"Intent queue worker fatal: {exc}")
                await asyncio.sleep(1)

    async def _close_http_pool(self) -> None:
        """Close the shared HTTP connection pool."""
        if self._http_pool:
            await self._http_pool.aclose()
            self._http_pool = None

    def stop(self) -> None:
        """Gracefully stop the broker.

        1. Set state to SHUTTING_DOWN so no new intents are accepted
        2. Cancel background async tasks on the event loop
        3. Signal the health-check loop to exit
        4. Wait for the health thread to finish (up to 5s)
        5. Log the event and set STOPPED
        """
        self.state = BrokerState.SHUTTING_DOWN
        self._log_event("broker_stopping", "Broker shutdown initiated", level="warning")
        self.logger.info("🛑 SIMP Broker shutting down...")

        # Cancel all background tasks scheduled on the async loop
        for fut in getattr(self, '_background_tasks', []):
            fut.cancel()
        self._background_tasks = []

        # Signal health-check loop to stop
        self._shutdown_event.set()

        # Wait for health thread to finish
        if hasattr(self, "_health_thread") and self._health_thread.is_alive():
            self._health_thread.join(timeout=5)
            if self._health_thread.is_alive():
                self.logger.warning("⚠️ Health check thread did not stop within 5s")

        # Close HTTP connection pool
        if self._http_pool:
            try:
                import asyncio as _aio
                loop = _aio.get_event_loop()
                if loop.is_running():
                    _aio.ensure_future(self._close_http_pool())
                else:
                    loop.run_until_complete(self._close_http_pool())
            except Exception:
                self._http_pool = None

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
