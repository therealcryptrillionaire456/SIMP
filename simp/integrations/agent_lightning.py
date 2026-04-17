"""
Agent Lightning Integration for SIMP Ecosystem

This module integrates Microsoft's Agent Lightning framework into the SIMP ecosystem
to provide comprehensive LLM call tracing, optimization, and agent intelligence
improvement across all agents in the system.

Key Features:
1. Centralized LLM call tracing for all agents
2. Performance optimization and APO (Automatic Prompt Optimization)
3. Agent intelligence improvement through trace analysis
4. Real-time monitoring and alerting
5. Integration with SIMP dashboard for visualization
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import threading
import requests
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AgentLightningConfig:
    """Configuration for Agent Lightning integration"""
    enabled: bool = False
    proxy_host: str = "localhost"
    proxy_port: int = 8235
    store_host: str = "localhost"
    store_port: int = 43887
    api_key: Optional[str] = None
    model: str = "glm-4-plus"
    trace_all_agents: bool = True
    trace_specific_agents: List[str] = None
    enable_apo: bool = True  # Automatic Prompt Optimization
    enable_performance_monitoring: bool = True
    enable_error_tracking: bool = True
    
    def __post_init__(self):
        if self.trace_specific_agents is None:
            self.trace_specific_agents = []

@dataclass
class LLMCallTrace:
    """Trace of an LLM call for analysis"""
    trace_id: str
    agent_id: str
    intent_type: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_ms: int
    success: bool
    error_message: Optional[str] = None
    timestamp: str = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.metadata is None:
            self.metadata = {}


class AgentLightningManager:
    """Manages Agent Lightning integration across SIMP ecosystem"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config = AgentLightningConfig()
        self._load_config()
        self.session = requests.Session()
        self._initialized = True
        logger.info("AgentLightningManager initialized")
    
    def _load_config(self):
        """Load configuration from environment and config files"""
        # Load from environment variables
        self.config.enabled = os.environ.get("AGENT_LIGHTNING_ENABLED", "false").lower() == "true"
        self.config.proxy_host = os.environ.get("AGENT_LIGHTNING_PROXY_HOST", "localhost")
        self.config.proxy_port = int(os.environ.get("AGENT_LIGHTNING_PROXY_PORT", "8235"))
        self.config.store_host = os.environ.get("AGENT_LIGHTNING_STORE_HOST", "localhost")
        self.config.store_port = int(os.environ.get("AGENT_LIGHTNING_STORE_PORT", "43887"))
        self.config.api_key = os.environ.get("X_AI_API_KEY")
        self.config.model = os.environ.get("AGENT_LIGHTNING_MODEL", "glm-4-plus")
        
        # Load from SIMP config if available
        try:
            from ..config import config as simp_config
            if hasattr(simp_config, 'agent_lightning'):
                # Merge config from SIMP
                pass
        except ImportError:
            pass
    
    def is_enabled_for_agent(self, agent_id: str) -> bool:
        """Check if Agent Lightning is enabled for a specific agent"""
        if not self.config.enabled:
            return False
        
        if self.config.trace_all_agents:
            return True
        
        return agent_id in self.config.trace_specific_agents
    
    def get_proxy_url(self) -> str:
        """Get the Agent Lightning proxy URL"""
        return f"http://{self.config.proxy_host}:{self.config.proxy_port}"
    
    def get_store_url(self) -> str:
        """Get the LightningStore URL"""
        return f"http://{self.config.store_host}:{self.config.store_port}"
    
    def trace_llm_call(self, trace: LLMCallTrace) -> bool:
        """Send LLM call trace to Agent Lightning store"""
        if not self.config.enabled:
            return False
        
        try:
            store_url = f"{self.get_store_url()}/v1/agl/traces"
            response = self.session.post(
                store_url,
                json=asdict(trace),
                timeout=5
            )
            response.raise_for_status()
            logger.debug(f"Trace sent to Agent Lightning: {trace.trace_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send trace to Agent Lightning: {e}")
            return False
    
    def get_agent_performance(self, agent_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics for an agent"""
        if not self.config.enabled:
            return {"error": "Agent Lightning not enabled"}
        
        try:
            store_url = f"{self.get_store_url()}/v1/agl/rollouts"
            params = {
                "agent_id": agent_id,
                "hours": hours
            }
            response = self.session.get(store_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get agent performance: {e}")
            return {"error": str(e)}
    
    def get_system_performance(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics for the entire SIMP system"""
        if not self.config.enabled:
            return {"error": "Agent Lightning not enabled"}
        
        try:
            store_url = f"{self.get_store_url()}/v1/agl/rollouts"
            params = {"hours": hours}
            response = self.session.get(store_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get system performance: {e}")
            return {"error": str(e)}
    
    def optimize_prompt(self, agent_id: str, original_prompt: str, context: Dict[str, Any] = None) -> str:
        """Use APO (Automatic Prompt Optimization) to improve a prompt"""
        if not self.config.enabled or not self.config.enable_apo:
            return original_prompt
        
        try:
            # This would call Agent Lightning's APO endpoint
            # For now, return the original prompt
            # TODO: Implement APO integration when available
            return original_prompt
        except Exception as e:
            logger.warning(f"APO failed: {e}")
            return original_prompt
    
    def start_proxy(self) -> bool:
        """Start the Agent Lightning proxy"""
        if not self.config.enabled:
            return False
        
        # Check if proxy is already running
        try:
            health_url = f"{self.get_proxy_url()}/health"
            response = self.session.get(health_url, timeout=5)
            if response.status_code == 200:
                logger.info("Agent Lightning proxy is already running")
                return True
        except:
            pass
        
        # Proxy is not running
        logger.warning("Agent Lightning proxy is not running. Please start it manually.")
        logger.info(f"Start command: python zai_agent_lightning_proxy.py")
        return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of Agent Lightning integration"""
        health = {
            "enabled": self.config.enabled,
            "proxy_healthy": False,
            "store_healthy": False,
            "config": asdict(self.config)
        }
        
        if not self.config.enabled:
            return health
        
        # Check proxy health
        try:
            proxy_health = self.session.get(f"{self.get_proxy_url()}/health", timeout=5)
            health["proxy_healthy"] = proxy_health.status_code == 200
        except:
            health["proxy_healthy"] = False
        
        # Check store health
        try:
            store_health = self.session.get(f"{self.get_store_url()}/v1/agl/health", timeout=5)
            health["store_healthy"] = store_health.status_code == 200
        except:
            health["store_healthy"] = False
        
        return health


# Global instance
agent_lightning_manager = AgentLightningManager()


class AgentLightningMiddleware:
    """Middleware for integrating Agent Lightning with SIMP agents"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.manager = agent_lightning_manager
        self.enabled = self.manager.is_enabled_for_agent(agent_id)
        
        if self.enabled:
            logger.info(f"Agent Lightning enabled for agent: {agent_id}")
    
    def wrap_llm_call(self, func):
        """Decorator to wrap LLM calls with tracing"""
        if not self.enabled:
            return func
        
        def wrapper(*args, **kwargs):
            import time
            import uuid
            
            start_time = time.time()
            trace_id = str(uuid.uuid4())
            
            # Extract call information
            model = kwargs.get('model', 'unknown')
            prompt = kwargs.get('prompt', '') or kwargs.get('messages', '')
            
            try:
                # Call the original function
                result = func(*args, **kwargs)
                
                # Calculate metrics
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                # Extract token counts if available
                prompt_tokens = getattr(result, 'prompt_tokens', 0)
                completion_tokens = getattr(result, 'completion_tokens', 0)
                total_tokens = getattr(result, 'total_tokens', 0)
                
                # Create trace
                trace = LLMCallTrace(
                    trace_id=trace_id,
                    agent_id=self.agent_id,
                    intent_type="llm_call",
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    response_time_ms=response_time_ms,
                    success=True,
                    metadata={
                        "function": func.__name__,
                        "args": str(args)[:500],
                        "kwargs_keys": list(kwargs.keys())
                    }
                )
                
                # Send trace
                self.manager.trace_llm_call(trace)
                
                return result
                
            except Exception as e:
                # Calculate metrics for failed call
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                # Create error trace
                trace = LLMCallTrace(
                    trace_id=trace_id,
                    agent_id=self.agent_id,
                    intent_type="llm_call",
                    model=model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=str(e),
                    metadata={
                        "function": func.__name__,
                        "error_type": type(e).__name__
                    }
                )
                
                # Send trace
                self.manager.trace_llm_call(trace)
                
                # Re-raise the exception
                raise
        
        return wrapper
    
    def optimize_prompt(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Optimize a prompt using APO"""
        return self.manager.optimize_prompt(self.agent_id, prompt, context)
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics for this agent"""
        return self.manager.get_agent_performance(self.agent_id, hours)


# SIMP Broker integration
def integrate_with_broker(broker):
    """Integrate Agent Lightning with SIMP broker"""
    manager = agent_lightning_manager
    
    if not manager.config.enabled:
        logger.info("Agent Lightning integration disabled")
        return
    
    # Add Agent Lightning endpoints to broker
    from flask import jsonify
    
    @broker.app.route('/agent-lightning/health', methods=['GET'])
    def agent_lightning_health():
        """Health check endpoint for Agent Lightning"""
        health = manager.health_check()
        return jsonify(health)
    
    @broker.app.route('/agent-lightning/performance', methods=['GET'])
    def agent_lightning_performance():
        """Get system performance from Agent Lightning"""
        hours = int(broker.request.args.get('hours', 24))
        performance = manager.get_system_performance(hours)
        return jsonify(performance)
    
    @broker.app.route('/agent-lightning/agents/<agent_id>/performance', methods=['GET'])
    def agent_performance(agent_id):
        """Get agent performance from Agent Lightning"""
        hours = int(broker.request.args.get('hours', 24))
        performance = manager.get_agent_performance(agent_id, hours)
        return jsonify(performance)
    
    @broker.app.route('/agent-lightning/config', methods=['GET'])
    def agent_lightning_config():
        """Get Agent Lightning configuration"""
        return jsonify(asdict(manager.config))
    
    logger.info("Agent Lightning integrated with SIMP broker")


# Dashboard integration
def integrate_with_dashboard(dashboard_app):
    """Integrate Agent Lightning with SIMP dashboard"""
    manager = agent_lightning_manager
    
    if not manager.config.enabled:
        return
    
    # Add Agent Lightning routes to dashboard
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/agent-lightning", tags=["agent-lightning"])
    
    @router.get("/health")
    async def dashboard_agent_lightning_health():
        return manager.health_check()
    
    @router.get("/performance")
    async def dashboard_agent_lightning_performance(hours: int = 24):
        return manager.get_system_performance(hours)
    
    @router.get("/agents/{agent_id}/performance")
    async def dashboard_agent_performance(agent_id: str, hours: int = 24):
        return manager.get_agent_performance(agent_id, hours)
    
    # Add router to dashboard app
    dashboard_app.include_router(router)
    
    logger.info("Agent Lightning integrated with SIMP dashboard")


# Agent registration hook
def register_agent_with_lightning(agent_id: str, agent_info: Dict[str, Any]):
    """Register an agent with Agent Lightning"""
    manager = agent_lightning_manager
    
    if not manager.config.enabled:
        return
    
    # Send agent registration to LightningStore
    try:
        store_url = f"{manager.get_store_url()}/v1/agl/agents"
        registration_data = {
            "agent_id": agent_id,
            "agent_info": agent_info,
            "timestamp": datetime.utcnow().isoformat(),
            "system": "simp"
        }
        
        response = manager.session.post(store_url, json=registration_data, timeout=5)
        response.raise_for_status()
        logger.info(f"Agent {agent_id} registered with Agent Lightning")
    except Exception as e:
        logger.warning(f"Failed to register agent {agent_id} with Agent Lightning: {e}")


# SIMP intent delivery hook
def trace_intent_delivery(intent_id: str, source_agent: str, target_agent: str, 
                         intent_type: str, success: bool, error_message: Optional[str] = None):
    """Trace intent delivery for Agent Lightning analysis"""
    manager = agent_lightning_manager
    
    if not manager.config.enabled:
        return
    
    # Create intent trace
    trace = LLMCallTrace(
        trace_id=intent_id,
        agent_id=source_agent,
        intent_type=intent_type,
        model="simp_intent",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        response_time_ms=0,  # Would need timing info
        success=success,
        error_message=error_message,
        metadata={
            "target_agent": target_agent,
            "intent_type": intent_type,
            "system": "simp"
        }
    )
    
    # Send trace
    manager.trace_llm_call(trace)