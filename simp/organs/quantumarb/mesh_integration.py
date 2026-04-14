#!/usr/bin/env python3
"""
QuantumArb Mesh Integration

Integrates QuantumArb with the SIMP Agent Mesh Bus for:
1. Sending trade updates to the trade_updates channel
2. Receiving safety commands from the safety_alerts channel
3. Reporting system health via system_heartbeats
4. Correlating trade execution with mesh trace IDs
"""

import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
import logging
from enum import Enum

# Try to import MeshClient, but handle gracefully if not available
try:
    from simp.mesh.client import MeshClient
    MESH_AVAILABLE = True
except ImportError:
    MESH_AVAILABLE = False
    logging.warning("MeshClient not available. QuantumArb mesh integration will run in simulation mode.")


class TradeStatus(str, Enum):
    """Status of a trade"""
    DETECTED = "detected"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SafetyCommand(str, Enum):
    """Safety commands that can be received"""
    PAUSE_TRADING = "pause_trading"
    RESUME_TRADING = "resume_trading"
    REDUCE_RISK = "reduce_risk"
    INCREASE_MONITORING = "increase_monitoring"
    FULL_AUDIT = "full_audit"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class TradeUpdate:
    """Trade update message for mesh bus"""
    trade_id: str
    status: TradeStatus
    symbol: str
    venue: str
    spread_percent: float
    expected_profit: float
    risk_score: float
    brp_decision: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to mesh payload"""
        return {
            "trade_id": self.trade_id,
            "status": self.status.value,
            "symbol": self.symbol,
            "venue": self.venue,
            "spread_percent": self.spread_percent,
            "expected_profit": self.expected_profit,
            "risk_score": self.risk_score,
            "brp_decision": self.brp_decision,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "metadata": self.metadata
        }


@dataclass
class SafetyAction:
    """Safety action received from mesh"""
    command: SafetyCommand
    reason: str
    severity: str  # INFO, WARNING, CRITICAL
    source: str
    timestamp: str
    trace_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_mesh_payload(cls, payload: Dict[str, Any]) -> Optional['SafetyAction']:
        """Create SafetyAction from mesh payload"""
        try:
            command_str = payload.get("command")
            if not command_str:
                return None
            
            return cls(
                command=SafetyCommand(command_str),
                reason=payload.get("reason", "No reason provided"),
                severity=payload.get("severity", "INFO"),
                source=payload.get("source", "unknown"),
                timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
                trace_id=payload.get("trace_id"),
                parameters=payload.get("parameters", {})
            )
        except (ValueError, KeyError) as e:
            logging.error(f"Failed to parse safety action: {e}")
            return None


class QuantumArbMeshMonitor:
    """Monitor for QuantumArb mesh integration"""
    
    def __init__(self, broker_url: str = "http://localhost:5555"):
        """
        Initialize QuantumArb mesh monitor.
        
        Args:
            broker_url: Base URL of SIMP broker
        """
        self.logger = logging.getLogger("QuantumArbMesh")
        self.broker_url = broker_url
        self.agent_id = "quantumarb"
        self.mesh_client = None
        self.running = False
        self.thread = None
        self.callbacks = {}
        
        if MESH_AVAILABLE:
            try:
                self.mesh_client = MeshClient(
                    agent_id=self.agent_id,
                    broker_url=self.broker_url
                )
                self.logger.info(f"QuantumArb mesh monitor initialized with broker: {broker_url}")
            except Exception as e:
                self.logger.error(f"Failed to initialize mesh client: {e}")
                self.mesh_client = None
        else:
            self.logger.warning("MeshClient not available. Running in simulation mode.")
    
    def start(self) -> bool:
        """Start mesh monitoring"""
        if not self.mesh_client:
            self.logger.warning("Cannot start mesh monitor: mesh client not available")
            return False
        
        try:
            # Subscribe to safety alerts
            success = self.mesh_client.subscribe("safety_alerts")
            if not success:
                self.logger.error("Failed to subscribe to safety_alerts")
                return False
            
            # Subscribe to maintenance events
            success = self.mesh_client.subscribe("maintenance_events")
            if not success:
                self.logger.warning("Failed to subscribe to maintenance_events")
            
            self.logger.info("Subscribed to mesh channels: safety_alerts, maintenance_events")
            
            # Start monitoring thread
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            
            self.logger.info("QuantumArb mesh monitor started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start mesh monitor: {e}")
            return False
    
    def stop(self) -> None:
        """Stop mesh monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        self.logger.info("QuantumArb mesh monitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self.running:
            try:
                if self.mesh_client:
                    # Poll for messages
                    messages = self.mesh_client.poll(max_messages=10)
                    
                    for packet in messages:
                        self._handle_packet(packet)
                
                time.sleep(1.0)  # Poll interval
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(5.0)  # Back off on error
    
    def _handle_packet(self, packet) -> None:
        """Handle incoming mesh packet"""
        try:
            if not hasattr(packet, 'payload') or not isinstance(packet.payload, dict):
                return
            
            payload = packet.payload
            
            # Check if this is a safety command
            if payload.get("command") in [cmd.value for cmd in SafetyCommand]:
                self._handle_safety_command(payload)
            
            # Check if this is a maintenance event
            elif payload.get("kind") in ["pause_suggested", "config_drift_detected"]:
                self._handle_maintenance_event(payload)
            
            # Check if this is a system command
            elif payload.get("system_command"):
                self._handle_system_command(payload)
            
        except Exception as e:
            self.logger.error(f"Error handling packet: {e}")
    
    def _handle_safety_command(self, payload: Dict[str, Any]) -> None:
        """Handle safety command from mesh"""
        action = SafetyAction.from_mesh_payload(payload)
        if not action:
            return
        
        self.logger.warning(f"Received safety command: {action.command.value} - {action.reason}")
        
        # Execute the command
        self._execute_safety_command(action)
        
        # Call registered callbacks
        if "safety_command" in self.callbacks:
            for callback in self.callbacks["safety_command"]:
                try:
                    callback(action)
                except Exception as e:
                    self.logger.error(f"Error in safety command callback: {e}")
    
    def _execute_safety_command(self, action: SafetyAction) -> None:
        """Execute safety command"""
        if action.command == SafetyCommand.PAUSE_TRADING:
            self._pause_trading(action)
        elif action.command == SafetyCommand.RESUME_TRADING:
            self._resume_trading(action)
        elif action.command == SafetyCommand.REDUCE_RISK:
            self._reduce_risk(action)
        elif action.command == SafetyCommand.INCREASE_MONITORING:
            self._increase_monitoring(action)
        elif action.command == SafetyCommand.FULL_AUDIT:
            self._full_audit(action)
        elif action.command == SafetyCommand.EMERGENCY_STOP:
            self._emergency_stop(action)
    
    def _pause_trading(self, action: SafetyAction) -> None:
        """Pause trading"""
        self.logger.critical(f"PAUSING TRADING: {action.reason}")
        # In a real implementation, this would set a global flag or call a method
        # to pause the trading engine
        
        # Send acknowledgment
        self.send_trade_update(
            TradeUpdate(
                trade_id="system",
                status=TradeStatus.CANCELLED,
                symbol="ALL",
                venue="ALL",
                spread_percent=0.0,
                expected_profit=0.0,
                risk_score=1.0,
                brp_decision="PAUSED",
                metadata={
                    "safety_command": "pause_trading",
                    "reason": action.reason,
                    "severity": action.severity,
                    "source": action.source
                }
            )
        )
    
    def _resume_trading(self, action: SafetyAction) -> None:
        """Resume trading"""
        self.logger.info(f"RESUMING TRADING: {action.reason}")
        # In a real implementation, this would resume the trading engine
        
        # Send acknowledgment
        self.send_trade_update(
            TradeUpdate(
                trade_id="system",
                status=TradeStatus.DETECTED,
                symbol="ALL",
                venue="ALL",
                spread_percent=0.0,
                expected_profit=0.0,
                risk_score=0.0,
                brp_decision="RESUMED",
                metadata={
                    "safety_command": "resume_trading",
                    "reason": action.reason,
                    "severity": action.severity,
                    "source": action.source
                }
            )
        )
    
    def _reduce_risk(self, action: SafetyAction) -> None:
        """Reduce risk parameters"""
        self.logger.warning(f"REDUCING RISK: {action.reason}")
        # In a real implementation, this would adjust risk parameters
        
        # Send acknowledgment
        self.send_trade_update(
            TradeUpdate(
                trade_id="system",
                status=TradeStatus.EVALUATING,
                symbol="ALL",
                venue="ALL",
                spread_percent=0.0,
                expected_profit=0.0,
                risk_score=0.5,
                brp_decision="RISK_REDUCED",
                metadata={
                    "safety_command": "reduce_risk",
                    "reason": action.reason,
                    "severity": action.severity,
                    "source": action.source
                }
            )
        )
    
    def _increase_monitoring(self, action: SafetyAction) -> None:
        """Increase monitoring frequency"""
        self.logger.info(f"INCREASING MONITORING: {action.reason}")
        # In a real implementation, this would increase monitoring frequency
        
        # Send acknowledgment
        self.send_trade_update(
            TradeUpdate(
                trade_id="system",
                status=TradeStatus.EVALUATING,
                symbol="ALL",
                venue="ALL",
                spread_percent=0.0,
                expected_profit=0.0,
                risk_score=0.3,
                brp_decision="MONITORING_INCREASED",
                metadata={
                    "safety_command": "increase_monitoring",
                    "reason": action.reason,
                    "severity": action.severity,
                    "source": action.source
                }
            )
        )
    
    def _full_audit(self, action: SafetyAction) -> None:
        """Perform full audit"""
        self.logger.warning(f"INITIATING FULL AUDIT: {action.reason}")
        # In a real implementation, this would trigger a full audit
        
        # Send acknowledgment
        self.send_trade_update(
            TradeUpdate(
                trade_id="system",
                status=TradeStatus.EVALUATING,
                symbol="ALL",
                venue="ALL",
                spread_percent=0.0,
                expected_profit=0.0,
                risk_score=0.8,
                brp_decision="AUDIT_INITIATED",
                metadata={
                    "safety_command": "full_audit",
                    "reason": action.reason,
                    "severity": action.severity,
                    "source": action.source
                }
            )
        )
    
    def _emergency_stop(self, action: SafetyAction) -> None:
        """Emergency stop all trading"""
        self.logger.critical(f"EMERGENCY STOP: {action.reason}")
        # In a real implementation, this would immediately stop all trading
        
        # Send acknowledgment
        self.send_trade_update(
            TradeUpdate(
                trade_id="system",
                status=TradeStatus.CANCELLED,
                symbol="ALL",
                venue="ALL",
                spread_percent=0.0,
                expected_profit=0.0,
                risk_score=1.0,
                brp_decision="EMERGENCY_STOPPED",
                metadata={
                    "safety_command": "emergency_stop",
                    "reason": action.reason,
                    "severity": action.severity,
                    "source": action.source
                }
            )
        )
    
    def _handle_maintenance_event(self, payload: Dict[str, Any]) -> None:
        """Handle maintenance event from mesh"""
        kind = payload.get("kind", "unknown")
        severity = payload.get("severity", "INFO")
        reason = payload.get("reason", "No reason provided")
        
        self.logger.info(f"Maintenance event: {kind} ({severity}) - {reason}")
        
        # Call registered callbacks
        if "maintenance_event" in self.callbacks:
            for callback in self.callbacks["maintenance_event"]:
                try:
                    callback(payload)
                except Exception as e:
                    self.logger.error(f"Error in maintenance event callback: {e}")
    
    def _handle_system_command(self, payload: Dict[str, Any]) -> None:
        """Handle system command from mesh"""
        command = payload.get("system_command", "unknown")
        self.logger.info(f"System command: {command}")
        
        # Call registered callbacks
        if "system_command" in self.callbacks:
            for callback in self.callbacks["system_command"]:
                try:
                    callback(payload)
                except Exception as e:
                    self.logger.error(f"Error in system command callback: {e}")
    
    def send_trade_update(self, update: TradeUpdate) -> bool:
        """
        Send trade update to mesh bus.
        
        Args:
            update: TradeUpdate to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.mesh_client:
            self.logger.warning("Cannot send trade update: mesh client not available")
            return False
        
        try:
            payload = update.to_payload()
            
            success = self.mesh_client.broadcast_to_channel(
                channel="trade_updates",
                payload=payload,
                msg_type="event",
                priority="normal"
            )
            
            if success:
                self.logger.debug(f"Sent trade update: {update.trade_id} - {update.status.value}")
            else:
                self.logger.error(f"Failed to send trade update: {update.trade_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending trade update: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        """
        Send system heartbeat to mesh bus.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.mesh_client:
            return False
        
        try:
            heartbeat = {
                "agent_id": self.agent_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "healthy",
                "metrics": {
                    "trades_today": 0,  # Would be populated in real implementation
                    "success_rate": 1.0,
                    "avg_profit": 0.0
                }
            }
            
            success = self.mesh_client.broadcast_to_channel(
                channel="system_heartbeats",
                payload=heartbeat,
                msg_type="heartbeat",
                priority="low"
            )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending heartbeat: {e}")
            return False
    
    def register_callback(self, event_type: str, callback: Callable) -> None:
        """
        Register callback for mesh events.
        
        Args:
            event_type: Type of event ("safety_command", "maintenance_event", "system_command")
            callback: Callback function to call when event occurs
        """
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        
        self.callbacks[event_type].append(callback)
        self.logger.debug(f"Registered callback for {event_type}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitor status"""
        return {
            "running": self.running,
            "mesh_available": MESH_AVAILABLE and self.mesh_client is not None,
            "subscribed_channels": ["safety_alerts", "maintenance_events"] if self.mesh_client else [],
            "callbacks_registered": list(self.callbacks.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
_quantumarb_mesh_monitor = None


def get_quantumarb_mesh_monitor(broker_url: str = "http://localhost:5555") -> QuantumArbMeshMonitor:
    """
    Get or create QuantumArb mesh monitor singleton.
    
    Args:
        broker_url: Base URL of SIMP broker
        
    Returns:
        QuantumArbMeshMonitor: Mesh monitor instance
    """
    global _quantumarb_mesh_monitor
    
    if _quantumarb_mesh_monitor is None:
        _quantumarb_mesh_monitor = QuantumArbMeshMonitor(broker_url)
    
    return _quantumarb_mesh_monitor


def start_quantumarb_mesh_monitor(broker_url: str = "http://localhost:5555") -> bool:
    """
    Start QuantumArb mesh monitor.
    
    Args:
        broker_url: Base URL of SIMP broker
        
    Returns:
        bool: True if started successfully, False otherwise
    """
    monitor = get_quantumarb_mesh_monitor(broker_url)
    return monitor.start()


def stop_quantumarb_mesh_monitor() -> None:
    """Stop QuantumArb mesh monitor"""
    global _quantumarb_mesh_monitor
    
    if _quantumarb_mesh_monitor:
        _quantumarb_mesh_monitor.stop()


if __name__ == "__main__":
    # Test the mesh integration
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing QuantumArb mesh integration...")
    
    monitor = get_quantumarb_mesh_monitor()
    
    if not monitor.mesh_client:
        print("❌ Mesh client not available")
        sys.exit(1)
    
    # Start monitor
    if monitor.start():
        print("✅ Mesh monitor started")
    else:
        print("❌ Failed to start mesh monitor")
        sys.exit(1)
    
    # Send test trade update
    test_update = TradeUpdate(
        trade_id="test_123",
        status=TradeStatus.DETECTED,
        symbol="BTC-USD",
        venue="Coinbase",
        spread_percent=1.5,
        expected_profit=150.0,
        risk_score=0.2,
        brp_decision="APPROVED",
        trace_id="test_trace_123"
    )
    
    if monitor.send_trade_update(test_update):
        print("✅ Test trade update sent")
    else:
        print("❌ Failed to send test trade update")
    
    # Send heartbeat
    if monitor.send_heartbeat():
        print("✅ Heartbeat sent")
    else:
        print("❌ Failed to send heartbeat")
    
    print(f"Status: {monitor.get_status()}")
    
    # Run for a bit to receive messages
    print("Monitoring for 10 seconds...")
    time.sleep(10)
    
    monitor.stop()
    print("✅ Test complete")