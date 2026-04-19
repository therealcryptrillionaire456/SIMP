"""
SIMP Agent Health Check Module — Sprint 70

Provides health checking and filtering for agents to prevent 'agent_unavailable' errors.
Integrates with the routing engine to skip unhealthy agents during routing decisions.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("SIMP.AgentHealth")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_HEALTH_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "agent_health_log.jsonl"
_HEALTH_CHECK_TIMEOUT = 5.0  # seconds
_MAX_HEALTH_FAILURES = 3  # consecutive failures before marking as unhealthy


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HealthCheckResult:
    """Result of a single agent health check."""
    agent_id: str
    is_healthy: bool
    timestamp: str  # ISO8601 UTC
    endpoint: str = ""
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    error: str = ""
    consecutive_failures: int = 0


@dataclass
class AgentHealthStatus:
    """Current health status of an agent."""
    agent_id: str
    is_healthy: bool
    last_check: str  # ISO8601 UTC
    consecutive_failures: int = 0
    last_error: str = ""
    endpoint: str = ""


# ---------------------------------------------------------------------------
# AgentHealthChecker
# ---------------------------------------------------------------------------

class AgentHealthChecker:
    """
    Checks agent health and maintains health status.
    
    Features:
    1. Health checking for HTTP agents (via /health endpoint)
    2. File-based agents are always considered healthy
    3. Health status tracking with failure counting
    4. Health log persistence (JSONL)
    5. Integration with routing engine via filter_unhealthy_agents()
    """
    
    def __init__(
        self,
        health_log_path: Optional[Path] = None,
        health_check_timeout: float = _HEALTH_CHECK_TIMEOUT,
        max_health_failures: int = _MAX_HEALTH_FAILURES,
    ):
        self.health_log_path = health_log_path or _DEFAULT_HEALTH_LOG_PATH
        self.health_check_timeout = health_check_timeout
        self.max_health_failures = max_health_failures
        
        # Thread-safe health status tracking
        self._lock = threading.Lock()
        self._health_status: Dict[str, AgentHealthStatus] = {}
        
        # Ensure health log directory exists
        self.health_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"AgentHealthChecker initialized with log: {self.health_log_path}")
    
    # ------------------------------------------------------------------
    # Health checking
    # ------------------------------------------------------------------
    
    def check_agent_health(self, agent_id: str, endpoint: str, agent_info: Dict[str, Any]) -> HealthCheckResult:
        """
        Check health of a single agent.
        
        Returns HealthCheckResult with health status and details.
        """
        start_time = time.monotonic()
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # File-based agents are always healthy
        if self._is_file_based(endpoint):
            result = HealthCheckResult(
                agent_id=agent_id,
                is_healthy=True,
                timestamp=timestamp,
                endpoint=endpoint,
                response_time_ms=round((time.monotonic() - start_time) * 1000, 2),
            )
            self._update_health_status(result)
            self._log_health_result(result)
            return result
        
        # HTTP agents: check /health endpoint
        try:
            import httpx
            
            health_url = f"{endpoint.rstrip('/')}/health"
            
            # Use sync client for simplicity (can be async in future)
            with httpx.Client(timeout=self.health_check_timeout) as client:
                response = client.get(health_url)
                elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
                
                is_healthy = response.status_code == 200
                result = HealthCheckResult(
                    agent_id=agent_id,
                    is_healthy=is_healthy,
                    timestamp=timestamp,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_time_ms=elapsed_ms,
                    error="" if is_healthy else f"HTTP {response.status_code}",
                    consecutive_failures=0 if is_healthy else self._get_consecutive_failures(agent_id) + 1,
                )
                
                self._update_health_status(result)
                self._log_health_result(result)
                return result
                
        except ImportError:
            # httpx not available - assume healthy
            logger.warning("httpx not available, assuming agent is healthy")
            result = HealthCheckResult(
                agent_id=agent_id,
                is_healthy=True,
                timestamp=timestamp,
                endpoint=endpoint,
                response_time_ms=round((time.monotonic() - start_time) * 1000, 2),
                error="httpx not available, assuming healthy",
            )
            self._update_health_status(result)
            self._log_health_result(result)
            return result
            
        except Exception as exc:
            # Connection error or timeout
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            result = HealthCheckResult(
                agent_id=agent_id,
                is_healthy=False,
                timestamp=timestamp,
                endpoint=endpoint,
                response_time_ms=elapsed_ms,
                error=str(exc),
                consecutive_failures=self._get_consecutive_failures(agent_id) + 1,
            )
            
            self._update_health_status(result)
            self._log_health_result(result)
            return result
    
    # ------------------------------------------------------------------
    # Health status management
    # ------------------------------------------------------------------
    
    def _update_health_status(self, result: HealthCheckResult) -> None:
        """Update internal health status tracking."""
        with self._lock:
            self._health_status[result.agent_id] = AgentHealthStatus(
                agent_id=result.agent_id,
                is_healthy=result.is_healthy,
                last_check=result.timestamp,
                consecutive_failures=result.consecutive_failures,
                last_error=result.error,
                endpoint=result.endpoint,
            )
    
    def _get_consecutive_failures(self, agent_id: str) -> int:
        """Get current consecutive failure count for an agent."""
        with self._lock:
            status = self._health_status.get(agent_id)
            return status.consecutive_failures if status else 0
    
    def get_agent_health_status(self, agent_id: str) -> Optional[AgentHealthStatus]:
        """Get current health status for an agent."""
        with self._lock:
            return self._health_status.get(agent_id)
    
    def is_agent_healthy(self, agent_id: str) -> bool:
        """
        Check if an agent is considered healthy.
        
        An agent is unhealthy if:
        1. It has consecutive failures >= max_health_failures, OR
        2. Its last health check was unhealthy
        """
        with self._lock:
            status = self._health_status.get(agent_id)
            if not status:
                return True  # Unknown agents are assumed healthy (for backward compatibility)
            
            if status.consecutive_failures >= self.max_health_failures:
                return False
            
            return status.is_healthy
    
    def filter_unhealthy_agents(self, agents: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Filter out unhealthy agents from a dictionary of agents.
        
        Returns a new dictionary containing only healthy agents.
        """
        healthy_agents = {}
        for agent_id, agent_info in agents.items():
            if self.is_agent_healthy(agent_id):
                healthy_agents[agent_id] = agent_info
            else:
                logger.debug(f"Filtering out unhealthy agent: {agent_id}")
        
        return healthy_agents
    
    # ------------------------------------------------------------------
    # Health logging
    # ------------------------------------------------------------------
    
    def _log_health_result(self, result: HealthCheckResult) -> None:
        """Log health check result to JSONL file."""
        try:
            log_entry = {
                "timestamp": result.timestamp,
                "agent_id": result.agent_id,
                "is_healthy": result.is_healthy,
                "endpoint": result.endpoint,
                "status_code": result.status_code,
                "response_time_ms": result.response_time_ms,
                "error": result.error,
                "consecutive_failures": result.consecutive_failures,
            }
            
            with open(self.health_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
                
            if not result.is_healthy:
                logger.warning(
                    f"Health check failed for agent {result.agent_id}: "
                    f"{result.error} (failures: {result.consecutive_failures})"
                )
                
        except Exception as exc:
            logger.error(f"Failed to log health result: {exc}")
    
    def get_health_log_summary(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent health check entries from the log."""
        entries = []
        try:
            if self.health_log_path.exists():
                with open(self.health_log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            entries.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        except Exception as exc:
            logger.error(f"Failed to read health log: {exc}")
        
        return entries
    
    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    
    @staticmethod
    def _is_file_based(endpoint: str) -> bool:
        """Check if endpoint indicates a file-based agent."""
        if not endpoint:
            return True
        if "(file-based)" in endpoint:
            return True
        if not endpoint.lower().startswith("http"):
            return True
        return False
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of health status for all tracked agents."""
        with self._lock:
            total = len(self._health_status)
            healthy = sum(1 for status in self._health_status.values() if status.is_healthy)
            unhealthy = total - healthy
            high_failure = sum(
                1 for status in self._health_status.values() 
                if status.consecutive_failures >= self.max_health_failures
            )
            
            return {
                "total_agents_tracked": total,
                "healthy_agents": healthy,
                "unhealthy_agents": unhealthy,
                "agents_with_high_failures": high_failure,
                "max_consecutive_failures": self.max_health_failures,
            }


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

# Global health checker instance
_health_checker: Optional[AgentHealthChecker] = None

def get_health_checker() -> AgentHealthChecker:
    """Get or create the global AgentHealthChecker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = AgentHealthChecker()
    return _health_checker