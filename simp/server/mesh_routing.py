#!/usr/bin/env python3
"""
Mesh Routing Integration for SIMP Broker.
Extends the broker's routing engine with mesh capabilities.
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from simp.mesh.intent_router import get_intent_router, IntentMeshRouter
from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
from simp.mesh.trust_graph import get_trust_graph
from simp.security.brp_bridge import BRPBridge
from simp.security.brp_models import BRPDecision, BRPEvent, BRPEventType
from simp.server.routing_engine import RoutingDecision, RoutingEngine

logger = logging.getLogger(__name__)

class MeshRoutingMode(Enum):
    """Mesh routing modes."""
    DISABLED = "disabled"
    FALLBACK = "fallback"  # Use mesh only if HTTP fails
    PREFERRED = "preferred"  # Try mesh first, fallback to HTTP
    EXCLUSIVE = "exclusive"  # Only use mesh

@dataclass
class MeshRoutingConfig:
    """Configuration for mesh routing."""
    mode: MeshRoutingMode = MeshRoutingMode.FALLBACK
    enable_capability_discovery: bool = True
    mesh_stake_amount: float = 25.0  # Default stake for mesh intents
    mesh_timeout_seconds: float = 30.0  # Timeout for mesh operations
    mesh_retry_count: int = 3  # Number of retry attempts
    
    # Agent-specific mesh settings
    agent_mesh_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)

class MeshRoutingManager:
    """
    Manages mesh routing integration with the SIMP broker.
    Provides capability discovery and mesh-based intent routing.
    """
    
    def __init__(self, broker_id: str = "simp_broker",
                 config: Optional[MeshRoutingConfig] = None,
                 brp_bridge: Optional[BRPBridge] = None):
        self.broker_id = broker_id
        self.config = config or MeshRoutingConfig()
        self.brp_bridge = brp_bridge or BRPBridge()
        
        # Initialize mesh components
        self.bus = get_enhanced_mesh_bus()
        self.mesh_router = get_intent_router(broker_id, self.bus)
        
        # Track mesh-connected agents
        self.mesh_agents: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Set broker capabilities
        self.mesh_router.set_capabilities(
            ["broker_routing", "intent_coordination", "capability_discovery"],
            channel_capacity=10000.0  # High capacity for broker
        )
        
        # Register mesh intent handlers
        self._register_mesh_handlers()
        
        logger.info(f"MeshRoutingManager initialized for broker {broker_id}")
    
    def start(self) -> None:
        """Start mesh routing services."""
        self.mesh_router.start()
        logger.info("Mesh routing services started")
    
    def stop(self) -> None:
        """Stop mesh routing services."""
        self.mesh_router.stop()
        logger.info("Mesh routing services stopped")
    
    def _register_mesh_handlers(self) -> None:
        """Register handlers for mesh intents."""
        
        def handle_broker_routing(payload: Dict[str, Any]) -> Dict[str, Any]:
            """Handle routing requests from mesh agents."""
            try:
                # Extract routing request
                intent_type = payload.get("intent_type")
                source_agent = payload.get("source_agent")
                target_agent = payload.get("target_agent")
                intent_payload = payload.get("payload", {})
                
                logger.info(f"Mesh routing request: {intent_type} from {source_agent} to {target_agent}")
                
                # For now, return a stub response
                # In full implementation, this would integrate with the broker's routing engine
                return {
                    "routed": True,
                    "intent_id": f"mesh_{intent_type}_{source_agent}",
                    "message": f"Intent would be routed via mesh to {target_agent}",
                    "mesh_route_used": True
                }
            except Exception as e:
                logger.error(f"Error handling broker routing: {e}")
                return {"routed": False, "error": str(e)}
        
        def handle_capability_query(payload: Dict[str, Any]) -> Dict[str, Any]:
            """Handle capability queries from mesh agents."""
            try:
                capability = payload.get("capability")
                with self._lock:
                    # Find agents with this capability
                    agents_with_capability = [
                        agent_id for agent_id, agent_data in self.mesh_agents.items()
                        if capability in agent_data.get("capabilities", [])
                    ]
                
                return {
                    "capability": capability,
                    "agents": agents_with_capability,
                    "count": len(agents_with_capability)
                }
            except Exception as e:
                logger.error(f"Error handling capability query: {e}")
                return {"capability": payload.get("capability"), "agents": [], "error": str(e)}
        
        # Register handlers
        self.mesh_router.register_intent_handler("broker_routing", handle_broker_routing)
        self.mesh_router.register_intent_handler("capability_query", handle_capability_query)
    
    def register_agent_mesh_capabilities(self, agent_id: str, capabilities: List[str], 
                                        channel_capacity: float = 1000.0) -> bool:
        """
        Register an agent's mesh capabilities.
        Called when an agent registers with the broker.
        """
        try:
            with self._lock:
                self.mesh_agents[agent_id] = {
                    "capabilities": capabilities,
                    "channel_capacity": channel_capacity,
                    "registered_at": time.time(),
                    "reputation_score": self._normalize_reputation(
                        self._get_effective_trust_score(agent_id)
                    ),
                    "mesh_available": True
                }
            
            logger.info(f"Registered mesh capabilities for agent {agent_id}: {capabilities}")
            return True
        except Exception as e:
            logger.error(f"Error registering mesh capabilities for {agent_id}: {e}")
            return False
    
    def unregister_agent_mesh(self, agent_id: str) -> bool:
        """Unregister an agent's mesh capabilities."""
        try:
            with self._lock:
                if agent_id in self.mesh_agents:
                    del self.mesh_agents[agent_id]
                    logger.info(f"Unregistered mesh capabilities for agent {agent_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error unregistering mesh capabilities for {agent_id}: {e}")
            return False
    
    def can_route_via_mesh(self, source_agent: str, target_agent: str, 
                          intent_type: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an intent can be routed via mesh.
        Returns (can_route, reason_if_not)
        """
        # Check if mesh routing is enabled
        if self.config.mode == MeshRoutingMode.DISABLED:
            return False, "Mesh routing disabled"
        
        with self._lock:
            # Check if both agents are mesh-capable
            source_mesh = source_agent in self.mesh_agents
            target_mesh = target_agent in self.mesh_agents
            
            if not source_mesh:
                return False, f"Source agent {source_agent} not mesh-capable"
            
            if not target_mesh:
                return False, f"Target agent {target_agent} not mesh-capable"
            
            # Check if target agent has capability for this intent type
            target_capabilities = self.mesh_agents[target_agent].get("capabilities", [])
            if intent_type not in target_capabilities:
                return False, f"Target agent lacks capability for {intent_type}"
            
            return True, None
    
    def route_via_mesh(self, source_agent: str, target_agent: str, 
                      intent_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route an intent via mesh.
        Returns routing result with mesh-specific fields.
        """
        try:
            brp_mode = payload.get("brp_mode", self.brp_bridge.default_mode)
            brp_context = self._build_mesh_security_context(
                source_agent=source_agent,
                target_agent=target_agent,
                intent_type=intent_type,
                payload=payload,
            )
            brp_event = BRPEvent(
                source_agent=source_agent,
                event_type=BRPEventType.MESH_INTENT.value,
                action=intent_type,
                params=payload.get("params", {}) if isinstance(payload.get("params"), dict) else {},
                context=brp_context,
                mode=brp_mode,
                tags=["mesh", "route_via_mesh", self.config.mode.value, intent_type],
            )
            brp_response = self.brp_bridge.evaluate_event(brp_event)
            brp_evaluation = self._serialize_brp_response(brp_event, brp_response)
            incident = self._read_brp_incident_snapshot(brp_event.event_id)
            if incident is not None:
                brp_evaluation["incident"] = incident
            controller_state = str(((brp_evaluation.get("runtime") or {}).get("controller_terminal_state") or "")).lower()
            controller_review_required = controller_state == "escalate_bias" and float(brp_response.threat_score or 0.0) >= 0.6

            if brp_response.decision == BRPDecision.DENY.value:
                logger.warning(
                    "[BRP][MESH] Denied mesh intent %s -> %s (threat=%.2f)",
                    source_agent,
                    target_agent,
                    brp_response.threat_score,
                )
                return {
                    "success": False,
                    "mesh_routed": False,
                    "brp_blocked": True,
                    "review_required": False,
                    "error_code": "BRP_DENIED",
                    "error": "Mesh routing denied by BRP",
                    "brp_evaluation": brp_evaluation,
                }

            if brp_response.decision == BRPDecision.ELEVATE.value or controller_review_required:
                logger.warning(
                    "[BRP][MESH] Review required for mesh intent %s -> %s (threat=%.2f)",
                    source_agent,
                    target_agent,
                    brp_response.threat_score,
                )
                return {
                    "success": False,
                    "mesh_routed": False,
                    "brp_blocked": True,
                    "review_required": True,
                    "error_code": "BRP_REVIEW_REQUIRED",
                    "error": "Mesh routing requires operator review",
                    "brp_evaluation": brp_evaluation,
                }

            # Create mesh intent
            mesh_intent_id = self.mesh_router.route_intent(
                intent_type=intent_type,
                target_agent=target_agent,
                payload=payload,
                stake_amount=self.config.mesh_stake_amount
            )
            
            if mesh_intent_id:
                return {
                    "success": True,
                    "mesh_routed": True,
                    "mesh_intent_id": mesh_intent_id,
                    "stake_amount": self.config.mesh_stake_amount,
                    "message": f"Intent routed via mesh to {target_agent}",
                    "brp_blocked": False,
                    "review_required": False,
                    "brp_evaluation": brp_evaluation,
                }
            else:
                return {
                    "success": False,
                    "mesh_routed": False,
                    "error": "Mesh routing failed - no intent ID returned",
                    "brp_blocked": False,
                    "review_required": False,
                    "brp_evaluation": brp_evaluation,
                }
        except Exception as e:
            logger.error(f"Error routing via mesh: {e}")
            return {
                "success": False,
                "mesh_routed": False,
                "error": f"Mesh routing error: {str(e)}"
            }

    def _build_mesh_security_context(self, source_agent: str, target_agent: str,
                                     intent_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Build BRP context for mesh-routed intents."""
        with self._lock:
            source_info = dict(self.mesh_agents.get(source_agent, {}))
            target_info = dict(self.mesh_agents.get(target_agent, {}))

        source_trust = self._get_effective_trust_score(source_agent)
        target_trust = self._get_effective_trust_score(target_agent)
        source_reputation = source_info.get("reputation_score")
        target_reputation = target_info.get("reputation_score")

        if source_reputation is None:
            source_reputation = self._normalize_reputation(source_trust)
        if target_reputation is None:
            target_reputation = self._normalize_reputation(target_trust)

        return {
            "intent_id": payload.get("intent_id"),
            "source_agent": source_agent,
            "target_agent": target_agent,
            "intent_type": intent_type,
            "mesh_route_mode": self.config.mode.value,
            "mesh_stake_amount": self.config.mesh_stake_amount,
            "mesh_retry_count": self.config.mesh_retry_count,
            "source_mesh_capable": bool(source_info),
            "target_mesh_capable": bool(target_info),
            "source_channel_capacity": source_info.get("channel_capacity"),
            "target_channel_capacity": target_info.get("channel_capacity"),
            "source_capabilities": source_info.get("capabilities", []),
            "target_capabilities": target_info.get("capabilities", []),
            "source_trust_score": source_trust,
            "target_trust_score": target_trust,
            "source_reputation_score": source_reputation,
            "target_reputation_score": target_reputation,
        }

    def _get_effective_trust_score(self, agent_id: str) -> Optional[float]:
        """Return a best-effort mesh trust score for an agent."""
        if not agent_id:
            return None

        try:
            trust_graph = get_trust_graph(broadcast=False, autostart=False)
            return round(trust_graph.get_effective_score(agent_id), 4)
        except Exception as exc:
            logger.debug("Unable to load trust score for %s: %s", agent_id, exc)
            return None

    @staticmethod
    def _normalize_reputation(trust_score: Optional[float]) -> Optional[float]:
        """Map SIMP trust score [0-5] to a normalized reputation [0-1]."""
        if trust_score is None:
            return None
        return round(min(max(trust_score / 5.0, 0.0), 1.0), 4)

    @staticmethod
    def _serialize_brp_response(brp_event: BRPEvent, brp_response: Any) -> Dict[str, Any]:
        """Return a compact BRP payload for mesh routing responses."""
        metadata = brp_response.metadata if isinstance(getattr(brp_response, "metadata", None), dict) else {}
        predictive = metadata.get("predictive_assessment") if isinstance(metadata.get("predictive_assessment"), dict) else {}
        multimodal = metadata.get("multimodal_assessment") if isinstance(metadata.get("multimodal_assessment"), dict) else {}
        controller = metadata.get("controller_assessment") if isinstance(metadata.get("controller_assessment"), dict) else {}
        return {
            "event_id": brp_event.event_id,
            "event_type": brp_event.event_type,
            "decision": brp_response.decision,
            "mode": brp_response.mode,
            "severity": brp_response.severity,
            "threat_score": brp_response.threat_score,
            "confidence": brp_response.confidence,
            "threat_tags": brp_response.threat_tags,
            "summary": brp_response.summary,
            "review_required": brp_response.decision == BRPDecision.ELEVATE.value,
            "mesh_allowed": brp_response.decision in {
                BRPDecision.ALLOW.value,
                BRPDecision.SHADOW_ALLOW.value,
                BRPDecision.LOG_ONLY.value,
            },
            "runtime": {
                "predictive_score_boost": round(float(predictive.get("score_boost") or 0.0), 4),
                "multimodal_score_boost": round(float(multimodal.get("score_boost") or 0.0), 4),
                "controller_rounds": int(controller.get("controller_rounds") or 0),
                "controller_score_delta": round(float(controller.get("score_delta") or 0.0), 4),
                "controller_confidence_delta": round(float(controller.get("confidence_delta") or 0.0), 4),
                "controller_terminal_state": controller.get("terminal_state"),
                "controller_reasoning_tags": controller.get("reasoning_tags", []),
            },
        }

    def _read_brp_incident_snapshot(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Return the lifecycle-backed incident snapshot for a mesh BRP event."""
        detail = self.brp_bridge.read_operator_evaluation_detail(
            event_id=event_id,
            data_dir=str(self.brp_bridge.data_dir),
        )
        incident = (detail or {}).get("incident")
        if not isinstance(incident, dict):
            return None
        return {
            "alert_id": incident.get("alert_id"),
            "incident_state": incident.get("incident_state") or incident.get("state"),
            "severity": incident.get("severity"),
            "acknowledged": bool(incident.get("acknowledged")),
            "reopen_count": int(incident.get("reopen_count") or 0),
            "last_seen_at": incident.get("last_seen_at"),
        }
    
    def get_mesh_agent_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get mesh information for an agent."""
        with self._lock:
            return self.mesh_agents.get(agent_id)
    
    def get_all_mesh_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get all mesh-capable agents."""
        with self._lock:
            return self.mesh_agents.copy()
    
    def discover_mesh_capabilities(self) -> Dict[str, Any]:
        """
        Discover capabilities from the mesh.
        Returns capability table from the mesh router.
        """
        try:
            capability_table = self.mesh_router.get_capability_table()
            
            # Update our mesh agents registry with discovered capabilities
            with self._lock:
                for capability, advertisements in capability_table.items():
                    for ad in advertisements:
                        agent_id = ad.get("agent_id")
                        if agent_id and agent_id != self.broker_id:
                            if agent_id not in self.mesh_agents:
                                self.mesh_agents[agent_id] = {
                                    "capabilities": [],
                                    "channel_capacity": ad.get("channel_capacity", 0.0),
                                    "reputation_score": ad.get("reputation_score"),
                                    "discovered_via_mesh": True,
                                    "last_seen": time.time()
                                }
                            
                            # Add capability if not already present
                            if capability not in self.mesh_agents[agent_id]["capabilities"]:
                                self.mesh_agents[agent_id]["capabilities"].append(capability)
            
            return {
                "success": True,
                "capability_count": sum(len(ads) for ads in capability_table.values()),
                "unique_agents": len(set(
                    ad.get("agent_id") 
                    for ads in capability_table.values() 
                    for ad in ads 
                    if ad.get("agent_id") != self.broker_id
                )),
                "capability_table": capability_table
            }
        except Exception as e:
            logger.error(f"Error discovering mesh capabilities: {e}")
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get mesh routing status."""
        mesh_status = self.mesh_router.get_status()
        
        with self._lock:
            return {
                "mesh_enabled": self.config.mode != MeshRoutingMode.DISABLED,
                "mesh_mode": self.config.mode.value,
                "mesh_agents_count": len(self.mesh_agents),
                "brp_enabled": self.brp_bridge is not None,
                "mesh_router_status": mesh_status,
                "config": {
                    "mesh_stake_amount": self.config.mesh_stake_amount,
                    "mesh_timeout_seconds": self.config.mesh_timeout_seconds,
                    "enable_capability_discovery": self.config.enable_capability_discovery
                }
            }

# Singleton instance for broker integration
_mesh_routing_manager: Optional[MeshRoutingManager] = None

def get_mesh_routing_manager(broker_id: str = "simp_broker",
                             brp_bridge: Optional[BRPBridge] = None) -> MeshRoutingManager:
    """Get or create the mesh routing manager singleton."""
    global _mesh_routing_manager
    if _mesh_routing_manager is None:
        _mesh_routing_manager = MeshRoutingManager(broker_id, brp_bridge=brp_bridge)
    return _mesh_routing_manager

def init_mesh_routing(broker_id: str = "simp_broker",
                      brp_bridge: Optional[BRPBridge] = None) -> MeshRoutingManager:
    """Initialize mesh routing (for broker startup)."""
    global _mesh_routing_manager
    _mesh_routing_manager = MeshRoutingManager(broker_id, brp_bridge=brp_bridge)
    _mesh_routing_manager.start()
    return _mesh_routing_manager

def shutdown_mesh_routing() -> None:
    """Shutdown mesh routing (for broker shutdown)."""
    global _mesh_routing_manager
    if _mesh_routing_manager:
        _mesh_routing_manager.stop()
        _mesh_routing_manager = None
