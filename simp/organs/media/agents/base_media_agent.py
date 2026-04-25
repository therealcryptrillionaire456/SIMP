"""
Base class for all KashClaw Media Grid agents.
"""
import asyncio
import functools
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable


def timed_operation(name=None):
    """Decorator that logs execution time of agent methods.

    Wraps a method call, measures elapsed wall-clock time, and logs
    the duration (and any error) via the agent's _log_metric method.

    Args:
        name: Optional override for the operation name.  Defaults to
              the wrapped function's __name__.

    Usage::

        class MyAgent(BaseMediaAgent):
            @timed_operation("my_op")
            async def do_stuff(self) -> str:
                ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            op_name = name or func.__name__
            start = time.time()
            try:
                result = func(self, *args, **kwargs)
                elapsed = time.time() - start
                self._log_metric(f"{op_name}_duration_seconds", elapsed)
                return result
            except Exception as e:
                elapsed = time.time() - start
                self._log_metric(f"{op_name}_error", 1)
                self._log_metric(f"{op_name}_duration_seconds", elapsed)
                raise
        return wrapper
    return decorator

from simp.organs.media.models import (
    AffiliateOffer, ContentBrief, ScriptPackage, AssetJob,
    GeneratedAsset, ContentPackage, PublishedPost, PerformanceMetrics,
    LandingPage, ContentOpportunityScore
)


class CircuitBreakerState(Enum):
    """State of the circuit breaker."""
    CLOSED = auto()      # Normal operation, requests pass through
    OPEN = auto()        # Circuit is tripped, requests fail fast
    HALF_OPEN = auto()   # Testing if service has recovered


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is OPEN and blocks a call."""
    pass


@dataclass
class CircuitBreaker:
    """Tracks failure count and determines whether calls should be blocked."""
    failure_count: int = 0
    max_failures: int = 5
    half_open_timeout: float = 60.0
    last_failure_time: Optional[float] = None
    state: CircuitBreakerState = CircuitBreakerState.CLOSED


class BaseMediaAgent:
    """Base class for all media grid agents with common functionality."""
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        """
        Initialize base media agent.
        
        Args:
            agent_id: Unique identifier for this agent
            agent_name: Human-readable name for the agent
            data_dir: Directory for data storage (defaults to data/media/)
            log_level: Logging level
            circuit_breaker: Optional CircuitBreaker instance (auto-created if None)
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        
        # Setup data directory
        if data_dir is None:
            data_dir = "data/media"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.logger = self._setup_logging(log_level)
        
        # Agent state
        self.is_running = False
        self.last_heartbeat = datetime.utcnow().isoformat()
        
        # SIMP broker configuration
        self.broker_url = os.getenv("SIMP_BROKER_URL", "http://127.0.0.1:5555")
        self.api_key = os.getenv("SIMP_API_KEY", "")
        
        # Circuit breaker
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self.logger.info(f"Circuit breaker initialized: {self._circuit_breaker.state.name}")
        
        self.logger.info(f"Initialized {agent_name} ({agent_id})")
    
    def _setup_logging(self, log_level: str) -> logging.Logger:
        """Setup logging for the agent."""
        logger = logging.getLogger(f"media.{self.agent_id}")
        logger.setLevel(getattr(logging, log_level.upper()))
        
        if not logger.handlers:
            # Console handler
            ch = logging.StreamHandler()
            ch.setLevel(getattr(logging, log_level.upper()))
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            ch.setFormatter(formatter)
            
            logger.addHandler(ch)
            
            # File handler
            log_file = self.data_dir / f"{self.agent_id}.log"
            fh = logging.FileHandler(log_file)
            fh.setLevel(getattr(logging, log_level.upper()))
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        
        return logger
    
    def _get_ledger_path(self, ledger_name: str) -> Path:
        """Get path for a JSONL ledger file."""
        return self.data_dir / f"{ledger_name}.jsonl"
    
    def _append_to_ledger(self, ledger_name: str, record: Dict[str, Any]) -> str:
        """
        Append a record to a JSONL ledger.
        
        Args:
            ledger_name: Name of the ledger (without .jsonl)
            record: Dictionary record to append
            
        Returns:
            Record ID if present, otherwise generated ID
        """
        ledger_path = self._get_ledger_path(ledger_name)
        
        # Ensure record has an ID and timestamp
        if "id" not in record:
            record["id"] = f"{ledger_name}_{uuid.uuid4().hex[:8]}"
        
        if "timestamp" not in record:
            record["timestamp"] = datetime.utcnow().isoformat()
        
        if "agent_id" not in record:
            record["agent_id"] = self.agent_id
        
        # Append to ledger
        with open(ledger_path, "a") as f:
            f.write(json.dumps(record) + "\n")
        
        self.logger.debug(f"Appended record {record['id']} to {ledger_name} ledger")
        return record["id"]
    
    def _read_ledger(self, ledger_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Read records from a JSONL ledger.
        
        Args:
            ledger_name: Name of the ledger (without .jsonl)
            limit: Maximum number of records to return
            
        Returns:
            List of records, most recent first
        """
        ledger_path = self._get_ledger_path(ledger_name)
        
        if not ledger_path.exists():
            return []
        
        records = []
        with open(ledger_path, "r") as f:
            lines = f.readlines()
        
        # Read in reverse to get most recent first
        for line in reversed(lines[-limit:]):
            try:
                record = json.loads(line.strip())
                records.append(record)
            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse line in {ledger_name} ledger")
        
        return records
    
    def _find_in_ledger(
        self,
        ledger_name: str,
        field: str,
        value: Any,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find records in a ledger by field value.
        
        Args:
            ledger_name: Name of the ledger
            field: Field name to search
            value: Value to match
            limit: Maximum number of records to return
            
        Returns:
            List of matching records
        """
        all_records = self._read_ledger(ledger_name, limit=1000)
        matches = []
        
        for record in all_records:
            if record.get(field) == value:
                matches.append(record)
                if len(matches) >= limit:
                    break
        
        return matches
    
    def _send_heartbeat(self) -> bool:
        """Send heartbeat to SIMP broker and record to heartbeat ledger."""
        try:
            # This would be an HTTP POST to the broker
            # For now, just update local timestamp and write ledger
            now = datetime.utcnow().isoformat()
            self.last_heartbeat = now

            # Record heartbeat to append-only ledger
            heartbeat_record = {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "timestamp": now,
                "is_running": self.is_running,
            }
            self._append_to_ledger("agent_heartbeats", heartbeat_record)

            self.logger.debug(f"Heartbeat sent at {self.last_heartbeat}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat: {e}")
            return False
    
    def _register_with_broker(self) -> bool:
        """Register this agent with the SIMP broker."""
        try:
            # This would be an HTTP POST to /agents/register
            # For now, just log
            self.logger.info(f"Would register {self.agent_name} with SIMP broker")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register with broker: {e}")
            return False
    
    def _send_intent(self, intent_type: str, intent_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send an intent to the SIMP broker.
        
        Args:
            intent_type: Type of intent (e.g., "media.trend_research")
            intent_data: Intent payload
            
        Returns:
            Response from broker or None if failed
        """
        try:
            # This would be an HTTP POST to /intents/route
            intent_id = f"intent_{uuid.uuid4().hex[:8]}"
            
            full_intent = {
                "intent_id": intent_id,
                "intent_type": intent_type,
                "source_agent": self.agent_id,
                "target_agent": "auto",  # Let broker route
                "payload": intent_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Would send intent {intent_type} with ID {intent_id}")
            
            # For now, return a mock response
            return {
                "intent_id": intent_id,
                "status": "received",
                "routed_to": "mock_agent",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to send intent {intent_type}: {e}")
            return None
    
    def _log_metric(self, metric_name: str, value: float) -> None:
        """Record a numeric metric to the metrics JSONL ledger.

        Args:
            metric_name: Dot-separated metric path (e.g. ``trend_research_duration_seconds``).
            value: Numeric value (float or int).
        """
        record = {
            "metric": metric_name,
            "value": value,
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._append_to_ledger("metrics", record)

    def _log_operation(
        self,
        operation: str,
        status: str,
        details: Dict[str, Any],
        duration_seconds: Optional[float] = None
    ) -> str:
        """
        Log an operation to the operations ledger.
        
        Args:
            operation: Name of the operation
            status: "success", "failure", "pending"
            details: Operation details
            duration_seconds: How long the operation took
            
        Returns:
            Operation ID
        """
        operation_id = f"op_{uuid.uuid4().hex[:8]}"
        
        record = {
            "id": operation_id,
            "agent_id": self.agent_id,
            "operation": operation,
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if duration_seconds is not None:
            record["duration_seconds"] = duration_seconds
        
        self._append_to_ledger("operations", record)
        
        log_level = logging.INFO if status == "success" else logging.WARNING
        self.logger.log(log_level, f"Operation {operation}: {status}")
        
        return operation_id
    
    def _calculate_content_opportunity_score(
        self,
        demand: float,
        monetization: float,
        content_fit: float,
        distribution_fit: float,
        competition: float,
        compliance_risk: float,
        production_cost: float
    ) -> ContentOpportunityScore:
        """
        Calculate Content Opportunity Score (COS).
        
        Formula:
        COS = (Demand × Monetization × ContentFit × DistributionFit) - 
              (Competition + ComplianceRisk + ProductionCost)
        
        All inputs should be normalized to 0-100 scale.
        """
        # Component product (0-100^4, but we normalize)
        component_product = (demand * monetization * content_fit * distribution_fit) / 1000000
        
        # Risk sum (0-300)
        risk_sum = competition + compliance_risk + production_cost
        
        # Final score (theoretical range: -300 to 100)
        final_score = component_product - risk_sum
        
        # Create score object
        score = ContentOpportunityScore(
            demand_score=demand,
            monetization_score=monetization,
            content_fit_score=content_fit,
            distribution_fit_score=distribution_fit,
            competition_score=competition,
            compliance_risk_score=compliance_risk,
            production_cost_score=production_cost,
            final_score=final_score,
            recommendation="proceed" if final_score > 50 else "review" if final_score > 20 else "reject",
            confidence=min(100, max(0, final_score + 50))  # Map -50..100 to 0..100
        )
        
        return score
    
    async def start(self) -> bool:
        """Start the agent's main loop."""
        if self.is_running:
            self.logger.warning("Agent is already running")
            return False
        
        self.logger.info(f"Starting {self.agent_name}")
        self.is_running = True
        
        # Register with broker
        if not self._register_with_broker():
            self.logger.error("Failed to register with broker")
            self.is_running = False
            return False
        
        # Start heartbeat thread
        asyncio.create_task(self._heartbeat_loop())
        
        # Start main processing loop
        asyncio.create_task(self._process_loop())
        
        self.logger.info(f"{self.agent_name} started successfully")
        return True
    
    async def stop(self) -> bool:
        """Stop the agent."""
        if not self.is_running:
            self.logger.warning("Agent is not running")
            return False
        
        self.logger.info(f"Stopping {self.agent_name}")
        self.is_running = False
        
        # Give time for cleanup
        await asyncio.sleep(1)
        
        self.logger.info(f"{self.agent_name} stopped")
        return True
    
    async def _heartbeat_loop(self):
        """Background task to send heartbeats."""
        while self.is_running:
            try:
                self._send_heartbeat()
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(5)
    
    async def _process_loop(self):
        """Main processing loop to be overridden by subclasses."""
        while self.is_running:
            try:
                # Subclasses should implement their processing logic
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Processing loop error: {e}")
                await asyncio.sleep(5)
    
    @property
    def circuit_breaker_state(self) -> str:
        """Return current circuit breaker state name."""
        return self._circuit_breaker.state.name

    def _call_with_circuit_breaker(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Checks circuit state before calling the function. On success,
        resets failure count. On exception, increments counter and
        transitions state as needed.
        
        Args:
            func: Callable to invoke
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of the function call
            
        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Exception: Any exception raised by the wrapped function
        """
        cb = self._circuit_breaker

        if cb.state == CircuitBreakerState.OPEN:
            now = time.time()
            if cb.last_failure_time is not None and (now - cb.last_failure_time) >= cb.half_open_timeout:
                self.logger.info(
                    f"Circuit breaker half-open timeout elapsed ({cb.half_open_timeout}s), "
                    f"transitioning to HALF_OPEN"
                )
                cb.state = CircuitBreakerState.HALF_OPEN
            else:
                elapsed = 0.0 if cb.last_failure_time is None else now - cb.last_failure_time
                remaining = max(0.0, cb.half_open_timeout - elapsed)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN for agent '{self.agent_name}'. "
                    f"Retry in {remaining:.1f}s after {cb.max_failures} consecutive failures."
                )

        try:
            result = func(*args, **kwargs)
            # Success: reset circuit
            if cb.state != CircuitBreakerState.CLOSED:
                self.logger.info("Circuit breaker reset to CLOSED after successful call")
            cb.failure_count = 0
            cb.state = CircuitBreakerState.CLOSED
            cb.last_failure_time = None
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            cb.failure_count += 1
            cb.last_failure_time = time.time()
            self.logger.warning(
                f"Circuit breaker failure {cb.failure_count}/{cb.max_failures}: {e}"
            )
            if cb.failure_count >= cb.max_failures:
                cb.state = CircuitBreakerState.OPEN
                self.logger.error(
                    f"Circuit breaker OPEN after {cb.failure_count} consecutive failures"
                )
            raise

    def health_check(self) -> Dict[str, Any]:
        """Return agent health status."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": "running" if self.is_running else "stopped",
            "last_heartbeat": self.last_heartbeat,
            "data_dir": str(self.data_dir),
            "circuit_breaker": {
                "state": self._circuit_breaker.state.name,
                "failure_count": self._circuit_breaker.failure_count,
                "max_failures": self._circuit_breaker.max_failures,
                "last_failure_time": self._circuit_breaker.last_failure_time
            },
            "ledgers": {
                ledger.stem: ledger.stat().st_size if ledger.exists() else 0
                for ledger in self.data_dir.glob("*.jsonl")
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        operations = self._read_ledger("operations", limit=100)
        
        success_count = sum(1 for op in operations if op.get("status") == "success")
        failure_count = sum(1 for op in operations if op.get("status") == "failure")
        pending_count = sum(1 for op in operations if op.get("status") == "pending")
        
        return {
            "agent_id": self.agent_id,
            "operations_total": len(operations),
            "operations_success": success_count,
            "operations_failure": failure_count,
            "operations_pending": pending_count,
            "uptime_seconds": time.time() - os.path.getctime(__file__) if self.is_running else 0
        }