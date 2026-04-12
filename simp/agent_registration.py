"""
Enhanced agent registration with verification
"""
import json
import requests
import logging
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class AgentVerificationResult:
    """Results of agent verification."""
    agent_id: str
    endpoint: str
    reachable: bool
    health_status: Optional[Dict] = None
    capabilities: Optional[List[str]] = None
    response_time_ms: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        """Check if verification passed all critical checks."""
        return self.reachable and self.health_status is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "endpoint": self.endpoint,
            "reachable": self.reachable,
            "health_status": self.health_status,
            "capabilities": self.capabilities,
            "response_time_ms": self.response_time_ms,
            "errors": self.errors,
            "passed": self.passed
        }

class AgentRegistrar:
    """Handles agent registration with verification."""
    
    def __init__(self, broker_url: str = "http://localhost:5555", api_key: Optional[str] = None):
        self.broker_url = broker_url.rstrip("/")
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def verify_agent(self, agent_id: str, endpoint: str, timeout: int = 10) -> AgentVerificationResult:
        """Verify an agent before registration."""
        
        result = AgentVerificationResult(
            agent_id=agent_id,
            endpoint=endpoint,
            reachable=False
        )
        
        try:
            # Check health endpoint
            start_time = time.time()
            
            if endpoint == "(file-based)":
                # File-based agent verification
                result.reachable = True
                result.health_status = {"type": "file-based", "status": "available"}
                result.response_time_ms = (time.time() - start_time) * 1000
                
            elif endpoint == "(compat-layer)":
                # Compat layer agent verification
                result.reachable = True
                result.health_status = {"type": "compat-layer", "status": "available"}
                result.response_time_ms = (time.time() - start_time) * 1000
                
            else:
                # HTTP-based agent verification
                health_url = f"{endpoint}/health"
                response = requests.get(health_url, timeout=timeout)
                result.response_time_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    result.reachable = True
                    result.health_status = response.json()
                    
                    # Try to get capabilities
                    try:
                        caps_response = requests.get(f"{endpoint}/capabilities", timeout=timeout)
                        if caps_response.status_code == 200:
                            caps_data = caps_response.json()
                            if isinstance(caps_data, dict) and "capabilities" in caps_data:
                                result.capabilities = caps_data["capabilities"]
                            elif isinstance(caps_data, list):
                                result.capabilities = caps_data
                    except requests.exceptions.RequestException:
                        logger.debug(f"Capabilities endpoint not available for {agent_id}")
                    except Exception as e:
                        logger.debug(f"Error getting capabilities for {agent_id}: {e}")
                        
                else:
                    result.errors.append(f"Health check failed with status {response.status_code}")
                    
        except requests.exceptions.ConnectionError:
            result.errors.append(f"Cannot connect to agent at {endpoint}")
        except requests.exceptions.Timeout:
            result.errors.append(f"Timeout connecting to agent at {endpoint}")
        except Exception as e:
            result.errors.append(f"Verification error: {e}")
        
        return result
    
    def register_agent(self, agent_id: str, agent_type: str, endpoint: str, 
                      capabilities: List[str], verify: bool = True) -> Dict[str, Any]:
        """Register an agent with the broker after verification."""
        
        if verify:
            verification = self.verify_agent(agent_id, endpoint)
            if not verification.passed:
                error_msg = f"Agent verification failed for {agent_id}: {verification.errors}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "agent_id": agent_id,
                    "error": error_msg,
                    "verification": verification.to_dict()
                }
            
            # Use discovered capabilities if available
            if verification.capabilities:
                capabilities = verification.capabilities
        
        registration_payload = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "endpoint": endpoint,
            "capabilities": capabilities
        }
        
        try:
            response = requests.post(
                f"{self.broker_url}/agents/register",
                json=registration_payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully registered agent {agent_id}")
                return {
                    "success": True,
                    "agent_id": agent_id,
                    **result
                }
            else:
                error_msg = f"Registration failed for {agent_id}: HTTP {response.status_code}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "agent_id": agent_id,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except requests.exceptions.ConnectionError:
            error_msg = f"Cannot connect to broker at {self.broker_url}"
            logger.error(error_msg)
            return {
                "success": False,
                "agent_id": agent_id,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Registration error for {agent_id}: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "agent_id": agent_id,
                "error": str(e)
            }
    
    def register_kashclaw_gemma(self, port: int = 8780, verify: bool = True) -> Dict[str, Any]:
        """Specialized registration for kashclaw_gemma agent."""
        return self.register_agent(
            agent_id="kashclaw_gemma",
            agent_type="llm_planner",
            endpoint=f"http://localhost:{port}",
            capabilities=["planning", "research", "summarization", "classification"],
            verify=verify
        )
    
    def register_projectx_native(self, port: int = 8771, verify: bool = True) -> Dict[str, Any]:
        """Specialized registration for projectx_native agent."""
        return self.register_agent(
            agent_id="projectx_native",
            agent_type="maintenance_kernel",
            endpoint=f"http://localhost:{port}",
            capabilities=[
                "native_agent_health_check",
                "native_agent_repo_scan",
                "native_agent_task_audit",
                "native_agent_security_audit",
                "projectx_query"
            ],
            verify=verify
        )
    
    def register_claude_cowork(self, port: int = 8767, verify: bool = True) -> Dict[str, Any]:
        """Specialized registration for claude_cowork agent."""
        return self.register_agent(
            agent_id="claude_cowork",
            agent_type="code_bridge",
            endpoint=f"http://localhost:{port}",
            capabilities=["code_generation", "code_review", "architecture", "refactoring"],
            verify=verify
        )
    
    def deregister_agent(self, agent_id: str) -> Dict[str, Any]:
        """Deregister an agent from the broker."""
        try:
            response = requests.delete(
                f"{self.broker_url}/agents/{agent_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully deregistered agent {agent_id}")
                return {
                    "success": True,
                    "agent_id": agent_id,
                    **response.json()
                }
            else:
                error_msg = f"Deregistration failed for {agent_id}: HTTP {response.status_code}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "agent_id": agent_id,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            error_msg = f"Deregistration error for {agent_id}: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "agent_id": agent_id,
                "error": str(e)
            }
    
    def list_agents(self) -> Dict[str, Any]:
        """List all registered agents."""
        try:
            response = requests.get(
                f"{self.broker_url}/agents",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "agents": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to list agents: HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


def create_agent_registration_template(agent_type: str, **kwargs) -> Dict[str, Any]:
    """
    Create a registration template for different agent types.
    
    Args:
        agent_type: Type of agent (http, file_based, compat_layer)
        **kwargs: Agent-specific parameters
    
    Returns:
        Registration template dictionary
    """
    templates = {
        "http": {
            "agent_id": kwargs.get("agent_id", "unknown"),
            "agent_type": kwargs.get("agent_type", "generic"),
            "endpoint": kwargs.get("endpoint", ""),
            "capabilities": kwargs.get("capabilities", []),
            "health_endpoint": "/health",
            "capabilities_endpoint": "/capabilities",
            "heartbeat_interval": 30,
            "max_response_time": 10,
            "circuit_breaker_threshold": 3
        },
        "file_based": {
            "agent_id": kwargs.get("agent_id", "unknown"),
            "agent_type": kwargs.get("agent_type", "file_processor"),
            "endpoint": "(file-based)",
            "capabilities": kwargs.get("capabilities", []),
            "watch_path": kwargs.get("watch_path", ""),
            "poll_interval": 60,
            "file_pattern": kwargs.get("file_pattern", "*.json"),
            "max_age_seconds": 300
        },
        "compat_layer": {
            "agent_id": kwargs.get("agent_id", "unknown"),
            "agent_type": kwargs.get("agent_type", "compat_processor"),
            "endpoint": "(compat-layer)",
            "capabilities": kwargs.get("capabilities", []),
            "module_path": kwargs.get("module_path", ""),
            "policy_version": kwargs.get("policy_version", "v1.0"),
            "simulation_mode": kwargs.get("simulation_mode", True)
        }
    }
    
    if agent_type not in templates:
        raise ValueError(f"Unknown agent type: {agent_type}. Must be one of: {list(templates.keys())}")
    
    return templates[agent_type]