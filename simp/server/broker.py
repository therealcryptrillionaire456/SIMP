"""
SIMP Broker: Central Message Router

Acts as the central hub for inter-agent communication.
Receives intents, routes to appropriate agents, collects responses.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import uuid
import queue
import threading

from simp.task_ledger import TaskLedger
from simp.models.failure_taxonomy import FailureHandler, FailureClass
from simp.routing.builder_pool import BuilderPool


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
                 task_ledger: Optional[TaskLedger] = None):
        """Initialize SIMP Broker"""
        self.config = config or BrokerConfig()
        self.state = BrokerState.INITIALIZING
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
                "registered_at": datetime.utcnow().isoformat(),
                "intents_received": 0,
                "intents_completed": 0,
                "status": "online",
            }

            with self.stats_lock:
                self.stats["agents_registered"] += 1

            self.logger.info(
                f"✅ Agent registered: {agent_id} ({agent_type}) → {endpoint}"
            )
            return True

    def deregister_agent(self, agent_id: str) -> bool:
        """Deregister an agent"""
        with self.agent_lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                self.logger.info(f"✅ Agent deregistered: {agent_id}")
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
        intent_id = intent_data.get("intent_id", str(uuid.uuid4()))
        source_agent = intent_data.get("source_agent", "client")
        target_agent = intent_data.get("target_agent")
        intent_type = intent_data.get("intent_type", "unknown")

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
                        timestamp=datetime.utcnow().isoformat(),
                        status="failed",
                        error=error_msg,
                    )
                    self.intent_records[intent_id] = record

                with self.stats_lock:
                    self.stats["intents_failed"] += 1

                return error_resp

        # Claim task in ledger
        self.task_ledger.claim_task(task_id, target_agent)
        self.task_ledger.update_status(task_id, "in_progress")

        # Record intent
        with self.intent_lock:
            record = IntentRecord(
                intent_id=intent_id,
                source_agent=source_agent,
                target_agent=target_agent,
                intent_type=intent_type,
                timestamp=datetime.utcnow().isoformat(),
                status="pending",
            )
            self.intent_records[intent_id] = record

        with self.stats_lock:
            self.stats["intents_routed"] += 1

        self.logger.info(
            f"📤 Routing intent: {intent_id} ({intent_type}) "
            f"{source_agent} → {target_agent}"
        )

        # In a real implementation, would send to agent via network
        # For now, return success to show protocol works
        return {
            "status": "routed",
            "intent_id": intent_id,
            "target_agent": target_agent,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

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
        """Get recent broker logs (simplified)"""
        # In real implementation, would track log entries
        return []

    def start(self) -> None:
        """Start the broker"""
        self.state = BrokerState.RUNNING
        self.logger.info("✅ SIMP Broker RUNNING")

    def stop(self) -> None:
        """Stop the broker"""
        self.state = BrokerState.SHUTTING_DOWN
        self.logger.info("🛑 SIMP Broker shutting down...")
        self.state = BrokerState.STOPPED
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
            "timestamp": datetime.utcnow().isoformat(),
        }
