"""
Enhanced Mesh Integration for QuantumArb Agent
Features:
- Real-time trade updates via mesh
- Safety command processing
- Performance monitoring
- Security integration
"""

import json
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from simp.mesh.smart_client import SmartMeshClient, create_smart_mesh_client
from simp.mesh.security import MeshSecurityLayer, SecurityLevel, get_mesh_security_layer
from simp.mesh.discovery import get_mesh_discovery_service

logger = logging.getLogger(__name__)


class TradeEventType(Enum):
    """Types of trade events."""
    OPPORTUNITY_DETECTED = "opportunity_detected"
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    POSITION_UPDATE = "position_update"
    PNL_UPDATE = "pnl_update"
    RISK_ALERT = "risk_alert"


class SafetyCommandType(Enum):
    """Types of safety commands."""
    PAUSE_TRADING = "pause_trading"
    RESUME_TRADING = "resume_trading"
    REDUCE_RISK = "reduce_risk"
    INCREASE_MONITORING = "increase_monitoring"
    FULL_AUDIT = "full_audit"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class TradeEvent:
    """Trade event for mesh broadcasting."""
    event_type: TradeEventType
    timestamp: float = field(default_factory=time.time)
    agent_id: str = ""
    exchange: str = ""
    symbol: str = ""
    side: str = ""
    amount: float = 0.0
    price: float = 0.0
    pnl: float = 0.0
    risk_level: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for mesh transmission."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "price": self.price,
            "pnl": self.pnl,
            "risk_level": self.risk_level,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeEvent':
        """Create from dictionary."""
        return cls(
            event_type=TradeEventType(data["event_type"]),
            timestamp=data.get("timestamp", time.time()),
            agent_id=data.get("agent_id", ""),
            exchange=data.get("exchange", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            amount=data.get("amount", 0.0),
            price=data.get("price", 0.0),
            pnl=data.get("pnl", 0.0),
            risk_level=data.get("risk_level", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SafetyCommand:
    """Safety command from mesh."""
    command_type: SafetyCommandType
    timestamp: float = field(default_factory=time.time)
    source_agent: str = ""
    reason: str = ""
    duration: Optional[float] = None  # seconds, None = indefinite
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "command_type": self.command_type.value,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "reason": self.reason,
            "duration": self.duration,
            "parameters": self.parameters,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SafetyCommand':
        """Create from dictionary."""
        return cls(
            command_type=SafetyCommandType(data["command_type"]),
            timestamp=data.get("timestamp", time.time()),
            source_agent=data.get("source_agent", ""),
            reason=data.get("reason", ""),
            duration=data.get("duration"),
            parameters=data.get("parameters", {}),
        )


class EnhancedQuantumArbMeshIntegration:
    """
    Enhanced mesh integration for QuantumArb agent.
    """
    
    def __init__(
        self,
        agent_id: str,
        broker_url: str = "http://localhost:5555",
        mesh_bus_url: str = "http://localhost:8765",
        local_endpoint: str = "http://localhost:8770",
        enable_security: bool = True,
        enable_discovery: bool = True,
    ):
        """
        Initialize enhanced mesh integration.
        
        Args:
            agent_id: QuantumArb agent ID
            broker_url: SIMP broker URL
            mesh_bus_url: Mesh bus HTTP endpoint
            local_endpoint: Local agent endpoint
            enable_security: Enable security features
            enable_discovery: Enable peer discovery
        """
        self.agent_id = agent_id
        self.broker_url = broker_url
        self.mesh_bus_url = mesh_bus_url
        self.local_endpoint = local_endpoint
        
        # Mesh components
        self.mesh_client: Optional[SmartMeshClient] = None
        self.security_layer: Optional[MeshSecurityLayer] = None
        self.discovery_service = None
        
        # Configuration
        self.enable_security = enable_security
        self.enable_discovery = enable_discovery
        
        # Event handlers
        self._trade_event_handlers: List[Callable] = []
        self._safety_command_handlers: List[Callable] = []
        self._mesh_message_handlers: List[Callable] = []
        
        # State
        self._running = False
        self._mesh_thread: Optional[threading.Thread] = None
        self._last_heartbeat = 0
        self._trade_count = 0
        self._safety_commands_received = 0
        
        # Statistics
        self._stats = {
            "trade_events_sent": 0,
            "safety_commands_received": 0,
            "mesh_messages_sent": 0,
            "mesh_messages_received": 0,
            "security_violations": 0,
            "peer_count": 0,
            "uptime_seconds": 0,
        }
        
        # Safety state
        self.trading_paused = False
        self.risk_level = 1.0  # 1.0 = normal, 0.0 = no trading
        self.monitoring_level = 1.0  # 1.0 = normal, >1.0 = increased
        
        logger.info(f"Enhanced QuantumArb Mesh Integration initialized for {agent_id}")
    
    def start(self) -> bool:
        """Start mesh integration."""
        if self._running:
            logger.warning("Mesh integration already running")
            return False
        
        try:
            # Initialize mesh client
            self.mesh_client = create_smart_mesh_client(
                agent_id=self.agent_id,
                broker_url=self.broker_url,
                mesh_bus_url=self.mesh_bus_url,
                enable_direct_mesh=True,
            )
            
            # Initialize security layer
            if self.enable_security:
                self.security_layer = get_mesh_security_layer(self.agent_id)
                
                # Register with mesh client for key exchange
                # In production, this would be done via secure channel
                public_key = self.security_layer.get_public_key_pem()
                # TODO: Register public key with other agents
            
            # Initialize discovery service
            if self.enable_discovery:
                self.discovery_service = get_mesh_discovery_service(
                    local_agent_id=self.agent_id,
                    local_endpoint=self.local_endpoint,
                    broker_url=self.broker_url,
                )
            
            # Subscribe to channels
            self._subscribe_to_channels()
            
            # Start mesh processing thread
            self._running = True
            self._mesh_thread = threading.Thread(
                target=self._mesh_processing_loop,
                daemon=True,
                name=f"QuantumArbMesh-{self.agent_id}",
            )
            self._mesh_thread.start()
            
            self._start_time = time.time()
            logger.info(f"Enhanced mesh integration started for {self.agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start mesh integration: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop mesh integration."""
        self._running = False
        
        if self._mesh_thread:
            self._mesh_thread.join(timeout=5)
            self._mesh_thread = None
        
        if self.mesh_client:
            self.mesh_client.close()
            self.mesh_client = None
        
        if self.discovery_service:
            self.discovery_service.stop()
        
        logger.info(f"Enhanced mesh integration stopped for {self.agent_id}")
    
    def _subscribe_to_channels(self):
        """Subscribe to mesh channels."""
        if not self.mesh_client:
            return
        
        channels = [
            "quantumarb_trades",
            "quantumarb_safety",
            "system_alerts",
            "trade_updates",
            "risk_monitoring",
        ]
        
        for channel in channels:
            try:
                if self.mesh_client.subscribe(channel):
                    logger.debug(f"Subscribed to channel: {channel}")
                else:
                    logger.warning(f"Failed to subscribe to channel: {channel}")
            except Exception as e:
                logger.error(f"Error subscribing to {channel}: {e}")
    
    def _mesh_processing_loop(self):
        """Main mesh processing loop."""
        logger.info("Mesh processing loop started")
        
        while self._running:
            try:
                # Receive and process messages
                self._process_mesh_messages()
                
                # Send heartbeat
                self._send_heartbeat()
                
                # Update statistics
                self._update_statistics()
                
                # Sleep to prevent CPU spinning
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Mesh processing loop error: {e}")
                time.sleep(5)
        
        logger.info("Mesh processing loop stopped")
    
    def _process_mesh_messages(self):
        """Process incoming mesh messages."""
        if not self.mesh_client:
            return
        
        try:
            # Receive messages
            messages = self.mesh_client.receive(max_messages=10)
            
            for message in messages:
                self._stats["mesh_messages_received"] += 1
                
                # Process based on message type
                payload = message.payload
                message_type = payload.get("type")
                
                if message_type == "trade_event":
                    self._handle_trade_event(payload)
                elif message_type == "safety_command":
                    self._handle_safety_command(payload)
                elif message_type == "system_command":
                    self._handle_system_command(payload)
                elif message_type == "key_exchange":
                    self._handle_key_exchange(payload)
                else:
                    # Generic message handling
                    self._handle_generic_message(message)
                
                # Call registered handlers
                for handler in self._mesh_message_handlers:
                    try:
                        handler(message)
                    except Exception as e:
                        logger.error(f"Mesh message handler error: {e}")
        
        except Exception as e:
            logger.error(f"Error processing mesh messages: {e}")
    
    def _handle_trade_event(self, payload: Dict[str, Any]):
        """Handle trade event from mesh."""
        try:
            event = TradeEvent.from_dict(payload.get("data", {}))
            
            # Update statistics
            self._trade_count += 1
            
            # Call registered handlers
            for handler in self._trade_event_handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Trade event handler error: {e}")
            
            logger.debug(f"Processed trade event: {event.event_type.value}")
            
        except Exception as e:
            logger.error(f"Error handling trade event: {e}")
    
    def _handle_safety_command(self, payload: Dict[str, Any]):
        """Handle safety command from mesh."""
        try:
            command = SafetyCommand.from_dict(payload.get("data", {}))
            
            # Update statistics
            self._safety_commands_received += 1
            self._stats["safety_commands_received"] += 1
            
            # Execute safety command
            self._execute_safety_command(command)
            
            # Call registered handlers
            for handler in self._safety_command_handlers:
                try:
                    handler(command)
                except Exception as e:
                    logger.error(f"Safety command handler error: {e}")
            
            logger.info(f"Executed safety command: {command.command_type.value} from {command.source_agent}")
            
        except Exception as e:
            logger.error(f"Error handling safety command: {e}")
    
    def _handle_system_command(self, payload: Dict[str, Any]):
        """Handle system command from mesh."""
        command = payload.get("data", {})
        action = command.get("action")
        
        if action == "status_request":
            # Send status update
            self.send_status_update()
        elif action == "health_check":
            # Send health check response
            self.send_health_check()
        elif action == "configuration_update":
            # Update configuration
            self._update_configuration(command.get("config", {}))
    
    def _handle_key_exchange(self, payload: Dict[str, Any]):
        """Handle key exchange message."""
        if not self.security_layer:
            return
        
        agent_id = payload.get("agent_id")
        public_key = payload.get("public_key")
        
        if agent_id and public_key:
            self.security_layer.register_agent_public_key(agent_id, public_key)
            logger.info(f"Registered public key for {agent_id}")
    
    def _handle_generic_message(self, message):
        """Handle generic mesh message."""
        # Log the message
        logger.debug(f"Received generic mesh message: {message.message_type}")
    
    def _execute_safety_command(self, command: SafetyCommand):
        """Execute safety command."""
        if command.command_type == SafetyCommandType.PAUSE_TRADING:
            self.trading_paused = True
            logger.warning(f"Trading paused: {command.reason}")
            
        elif command.command_type == SafetyCommandType.RESUME_TRADING:
            self.trading_paused = False
            logger.info(f"Trading resumed: {command.reason}")
            
        elif command.command_type == SafetyCommandType.REDUCE_RISK:
            reduction = command.parameters.get("reduction", 0.5)
            self.risk_level = max(0.0, self.risk_level * reduction)
            logger.warning(f"Risk reduced to {self.risk_level}: {command.reason}")
            
        elif command.command_type == SafetyCommandType.INCREASE_MONITORING:
            increase = command.parameters.get("increase", 2.0)
            self.monitoring_level *= increase
            logger.info(f"Monitoring increased to {self.monitoring_level}: {command.reason}")
            
        elif command.command_type == SafetyCommandType.FULL_AUDIT:
            # Trigger full audit
            self._trigger_full_audit(command)
            
        elif command.command_type == SafetyCommandType.EMERGENCY_STOP:
            self.trading_paused = True
            self.risk_level = 0.0
            logger.critical(f"EMERGENCY STOP: {command.reason}")
    
    def _trigger_full_audit(self, command: SafetyCommand):
        """Trigger full audit."""
        logger.info(f"Starting full audit: {command.reason}")
        
        # In production, this would trigger comprehensive audit
        # For now, just log and send audit report
        audit_report = {
            "timestamp": time.time(),
            "agent_id": self.agent_id,
            "audit_type": "full",
            "trading_paused": self.trading_paused,
            "risk_level": self.risk_level,
            "monitoring_level": self.monitoring_level,
            "trade_count": self._trade_count,
            "safety_commands": self._safety_commands_received,
            "findings": [],
        }
        
        self.send_audit_report(audit_report)
    
    def _update_configuration(self, config: Dict[str, Any]):
        """Update configuration from mesh."""
        # Update configuration parameters
        # This would be agent-specific
        logger.info(f"Configuration updated via mesh: {config}")
    
    def _send_heartbeat(self):
        """Send heartbeat to mesh."""
        if not self.mesh_client:
            return
        
        # Send heartbeat every 30 seconds
        current_time = time.time()
        if current_time - self._last_heartbeat < 30:
            return
        
        try:
            heartbeat = {
                "type": "heartbeat",
                "data": {
                    "agent_id": self.agent_id,
                    "timestamp": current_time,
                    "status": "healthy",
                    "trading_paused": self.trading_paused,
                    "risk_level": self.risk_level,
                    "trade_count": self._trade_count,
                }
            }
            
            self.mesh_client.broadcast_to_channel(
                channel="heartbeats",
                payload=heartbeat,
                priority="low",
            )
            
            self._last_heartbeat = current_time
            self._stats["mesh_messages_sent"] += 1
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    def _update_statistics(self):
        """Update statistics."""
        self._stats["uptime_seconds"] = time.time() - self._start_time
        
        if self.discovery_service:
            peers = self.discovery_service.get_peers()
            self._stats["peer_count"] = len(peers)
    
    def send_trade_event(self, event: TradeEvent) -> bool:
        """
        Send trade event to mesh.
        
        Returns:
            True if sent successfully
        """
        if not self.mesh_client:
            return False
        
        if self.trading_paused:
            logger.warning(f"Cannot send trade event: trading paused")
            return False
        
        try:
            # Set agent ID if not set
            if not event.agent_id:
                event.agent_id = self.agent_id
            
            # Prepare message
            message = {
                "type": "trade_event",
                "data": event.to_dict(),
                "security_level": "signed" if self.enable_security else "none",
            }
            
            # Apply security if enabled
            if self.enable_security and self.security_layer:
                message = self.security_layer.secure_message(
                    message,
                    security_level=SecurityLevel.SIGNED,
                )
            
            # Send to trade updates channel
            success = self.mesh_client.broadcast_to_channel(
                channel="trade_updates",
                payload=message,
                priority="normal",
            ) is not None
            
            if success:
                self._stats["trade_events_sent"] += 1
                self._stats["mesh_messages_sent"] += 1
                logger.debug(f"Trade event sent: {event.event_type.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send trade event: {e}")
            return False
    
    def send_safety_command(
        self,
        command_type: SafetyCommandType,
        target_agent: Optional[str] = None,
        reason: str = "",
        duration: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send safety command via mesh.
        
        Returns:
            True if sent successfully
        """
        if not self.mesh_client:
            return False
        
        try:
            command = SafetyCommand(
                command_type=command_type,
                source_agent=self.agent_id,
                reason=reason,
                duration=duration,
                parameters=parameters or {},
            )
            
            # Prepare message
            message = {
                "type": "safety_command",
                "data": command.to_dict(),
                "security_level": "signed" if self.enable_security else "none",
            }
            
            # Apply security if enabled
            if self.enable_security and self.security_layer:
                message = self.security_layer.secure_message(
                    message,
                    security_level=SecurityLevel.SIGNED,
                )
            
            # Send to target agent or broadcast
            if target_agent:
                success = self.mesh_client.send_to_agent(
                    target_agent=target_agent,
                    payload=message,
                    priority="high",
                ) is not None
            else:
                success = self.mesh_client.broadcast_to_channel(
                    channel="safety_alerts",
                    payload=message,
                    priority="high",
                ) is not None
            
            if success:
                self._stats["mesh_messages_sent"] += 1
                logger.info(f"Safety command sent: {command_type.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send safety command: {e}")
            return False
    
    def send_status_update(self) -> bool:
        """Send status update to mesh."""
        if not self.mesh_client:
            return False
        
        try:
            status = {
                "type": "status_update",
                "data": {
                    "agent_id": self.agent_id,
                    "timestamp": time.time(),
                    "trading_paused": self.trading_paused,
                    "risk_level": self.risk_level,
                    "monitoring_level": self.monitoring_level,
                    "trade_count": self._trade_count,
                    "uptime_seconds": self._stats["uptime_seconds"],
                    "peer_count": self._stats["peer_count"],
                }
            }
            
            success = self.mesh_client.broadcast_to_channel(
                channel="system",
                payload=status,
                priority="low",
            ) is not None
            
            if success:
                self._stats["mesh_messages_sent"] += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send status update: {e}")
            return False
    
    def send_health_check(self) -> bool:
        """Send health check response."""
        if not self.mesh_client:
            return False
        
        try:
            health = {
                "type": "health_check",
                "data": {
                    "agent_id": self.agent_id,
                    "timestamp": time.time(),
                    "status": "healthy",
                    "components": {
                        "mesh_client": self.mesh_client is not None,
                        "security_layer": self.security_layer is not None,
                        "discovery_service": self.discovery_service is not None,
                        "trading_paused": self.trading_paused,
                    }
                }
            }
            
            success = self.mesh_client.broadcast_to_channel(
                channel="system",
                payload=health,
                priority="low",
            ) is not None
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send health check: {e}")
            return False
    
    def send_audit_report(self, report: Dict[str, Any]) -> bool:
        """Send audit report to mesh."""
        if not self.mesh_client:
            return False
        
        try:
            message = {
                "type": "audit_report",
                "data": report,
                "security_level": "signed" if self.enable_security else "none",
            }
            
            # Apply security if enabled
            if self.enable_security and self.security_layer:
                message = self.security_layer.secure_message(
                    message,
                    security_level=SecurityLevel.SIGNED,
                )
            
            success = self.mesh_client.broadcast_to_channel(
                channel="security_audit",
                payload=message,
                priority="normal",
            ) is not None
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send audit report: {e}")
            return False
    
    def register_trade_event_handler(self, handler: Callable):
        """Register handler for trade events."""
        self._trade_event_handlers.append(handler)
    
    def register_safety_command_handler(self, handler: Callable):
        """Register handler for safety commands."""
        self._safety_command_handlers.append(handler)
    
    def register_mesh_message_handler(self, handler: Callable):
        """Register handler for generic mesh messages."""
        self._mesh_message_handlers.append(handler)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get mesh integration statistics."""
        stats = self._stats.copy()
        
        stats.update({
            "agent_id": self.agent_id,
            "running": self._running,
            "trading_paused": self.trading_paused,
            "risk_level": self.risk_level,
            "monitoring_level": self.monitoring_level,
            "trade_count": self._trade_count,
            "safety_commands_received": self._safety_commands_received,
            "mesh_client_available": self.mesh_client is not None,
            "security_enabled": self.enable_security and self.security_layer is not None,
            "discovery_enabled": self.enable_discovery and self.discovery_service is not None,
        })
        
        return stats
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            "agent_id": self.agent_id,
            "mesh_integration": {
                "running": self._running,
                "mesh_client": self.mesh_client is not None,
                "security_layer": self.security_layer is not None,
                "discovery_service": self.discovery_service is not None,
            },
            "trading_state": {
                "paused": self.trading_paused,
                "risk_level": self.risk_level,
                "monitoring_level": self.monitoring_level,
            },
            "statistics": self.get_statistics(),
        }


def get_enhanced_quantumarb_mesh_integration(
    agent_id: str,
    broker_url: str = "http://localhost:5555",
    mesh_bus_url: str = "http://localhost:8765",
    local_endpoint: str = "http://localhost:8770",
) -> EnhancedQuantumArbMeshIntegration:
    """
    Get or create enhanced QuantumArb mesh integration.
    
    Args:
        agent_id: QuantumArb agent ID
        broker_url: SIMP broker URL
        mesh_bus_url: Mesh bus HTTP endpoint
        local_endpoint: Local agent endpoint
        
    Returns:
        EnhancedQuantumArbMeshIntegration instance
    """
    if not hasattr(get_enhanced_quantumarb_mesh_integration, "_instances"):
        get_enhanced_quantumarb_mesh_integration._instances = {}
    
    key = f"{agent_id}_{broker_url}"
    
    if key not in get_enhanced_quantumarb_mesh_integration._instances:
        get_enhanced_quantumarb_mesh_integration._instances[key] = EnhancedQuantumArbMeshIntegration(
            agent_id=agent_id,
            broker_url=broker_url,
            mesh_bus_url=mesh_bus_url,
            local_endpoint=local_endpoint,
        )
    
    return get_enhanced_quantumarb_mesh_integration._instances[key]


def start_enhanced_quantumarb_mesh_integration(
    agent_id: str,
    broker_url: str = "http://localhost:5555",
    mesh_bus_url: str = "http://localhost:8765",
    local_endpoint: str = "http://localhost:8770",
) -> bool:
    """
    Start enhanced QuantumArb mesh integration.
    
    Returns:
        True if started successfully
    """
    integration = get_enhanced_quantumarb_mesh_integration(
        agent_id=agent_id,
        broker_url=broker_url,
        mesh_bus_url=mesh_bus_url,
        local_endpoint=local_endpoint,
    )
    
    return integration.start()


def stop_enhanced_quantumarb_mesh_integration(agent_id: str):
    """Stop enhanced QuantumArb mesh integration."""
    if hasattr(get_enhanced_quantumarb_mesh_integration, "_instances"):
        for key, instance in list(get_enhanced_quantumarb_mesh_integration._instances.items()):
            if instance.agent_id == agent_id:
                instance.stop()
                del get_enhanced_quantumarb_mesh_integration._instances[key]
                break