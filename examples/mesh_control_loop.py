#!/usr/bin/env python3
"""
Mesh Bus Control Loop Example

Demonstrates a real control loop on the mesh bus:
BRP safety alert → Watchtower reaction → ProjectX analysis → Dashboard notification

This example shows how the mesh bus enables coordinated behavior
across multiple agents without direct coupling.
"""

import time
import json
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MeshControlLoop")

try:
    from simp.mesh.client import MeshClient
    MESH_AVAILABLE = True
except ImportError:
    MESH_AVAILABLE = False
    logger.warning("MeshClient not available. Running in simulation mode.")


class BRPAgent:
    """Behavioral Risk Profiler - Detects safety risks"""
    
    def __init__(self, broker_url: str = "http://localhost:5555"):
        self.agent_id = "brp"
        self.broker_url = broker_url
        self.mesh_client = None
        
        if MESH_AVAILABLE:
            try:
                self.mesh_client = MeshClient(
                    agent_id=self.agent_id,
                    broker_url=self.broker_url
                )
                logger.info(f"BRP Agent initialized with mesh client")
            except Exception as e:
                logger.error(f"Failed to initialize BRP mesh client: {e}")
    
    def detect_high_risk(self, risk_score: float, reason: str) -> bool:
        """Detect high risk and send safety alert"""
        if not self.mesh_client:
            logger.warning("Mesh client not available. Simulating alert.")
            return False
        
        try:
            alert_payload = {
                "alert_type": "brp_high_risk",
                "severity": "CRITICAL" if risk_score > 0.9 else "WARNING",
                "risk_score": risk_score,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "brp",
                "recommended_action": "pause_quantumarb" if risk_score > 0.8 else "review_risk"
            }
            
            success = self.mesh_client.send_to_channel(
                channel="safety_alerts",
                payload=alert_payload,
                msg_type="event",
                priority="high"
            )
            
            if success:
                logger.info(f"BRP sent safety alert: {reason} (risk: {risk_score})")
            else:
                logger.error("Failed to send safety alert")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending safety alert: {e}")
            return False
    
    def simulate_risk_detection(self):
        """Simulate periodic risk detection"""
        import random
        
        while True:
            # Simulate random risk events
            risk_score = random.uniform(0.0, 1.0)
            
            if risk_score > 0.7:
                reasons = [
                    "Unusual trading volume detected",
                    "Risk limits approaching threshold",
                    "Market volatility spike",
                    "Connection instability detected",
                    "Position concentration too high"
                ]
                reason = random.choice(reasons)
                
                self.detect_high_risk(risk_score, reason)
            
            time.sleep(random.uniform(10, 30))  # Random interval


class WatchtowerAgent:
    """Watchtower - Monitors safety alerts and reacts"""
    
    def __init__(self, broker_url: str = "http://localhost:5555"):
        self.agent_id = "watchtower"
        self.broker_url = broker_url
        self.mesh_client = None
        self.running = False
        self.thread = None
        
        if MESH_AVAILABLE:
            try:
                self.mesh_client = MeshClient(
                    agent_id=self.agent_id,
                    broker_url=self.broker_url
                )
                # Subscribe to safety alerts
                self.mesh_client.subscribe("safety_alerts")
                logger.info(f"Watchtower Agent initialized and subscribed to safety_alerts")
            except Exception as e:
                logger.error(f"Failed to initialize Watchtower mesh client: {e}")
    
    def handle_safety_alert(self, alert: Dict[str, Any]) -> None:
        """Handle incoming safety alert"""
        alert_type = alert.get("alert_type", "unknown")
        severity = alert.get("severity", "INFO")
        reason = alert.get("reason", "No reason provided")
        risk_score = alert.get("risk_score", 0.0)
        
        logger.warning(f"Watchtower received {severity} alert: {alert_type} - {reason}")
        
        # React based on severity
        if severity == "CRITICAL":
            self.react_critical_alert(alert)
        elif severity == "WARNING":
            self.react_warning_alert(alert)
        
        # Forward to dashboard for display
        self.forward_to_dashboard(alert)
    
    def react_critical_alert(self, alert: Dict[str, Any]) -> None:
        """React to critical alert"""
        logger.critical(f"CRITICAL ALERT - Taking immediate action")
        
        # Send pause recommendation
        if self.mesh_client:
            try:
                recommendation = {
                    "action": "pause_trading",
                    "agent": "quantumarb",
                    "reason": alert.get("reason", "Critical risk detected"),
                    "severity": "CRITICAL",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "watchtower"
                }
                
                self.mesh_client.send_to_channel(
                    channel="maintenance_events",
                    payload=recommendation,
                    msg_type="command",
                    priority="high"
                )
                
                logger.info("Sent pause trading recommendation")
                
            except Exception as e:
                logger.error(f"Error sending recommendation: {e}")
    
    def react_warning_alert(self, alert: Dict[str, Any]) -> None:
        """React to warning alert"""
        logger.warning(f"WARNING ALERT - Monitoring closely")
        
        # Send monitoring recommendation
        if self.mesh_client:
            try:
                recommendation = {
                    "action": "increase_monitoring",
                    "agent": "quantumarb",
                    "reason": alert.get("reason", "Elevated risk detected"),
                    "severity": "WARNING",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "watchtower"
                }
                
                self.mesh_client.send_to_channel(
                    channel="maintenance_events",
                    payload=recommendation,
                    msg_type="event",
                    priority="normal"
                )
                
                logger.info("Sent increased monitoring recommendation")
                
            except Exception as e:
                logger.error(f"Error sending recommendation: {e}")
    
    def forward_to_dashboard(self, alert: Dict[str, Any]) -> None:
        """Forward alert to dashboard channel"""
        if self.mesh_client:
            try:
                dashboard_alert = {
                    **alert,
                    "forwarded_by": "watchtower",
                    "dashboard_priority": "high" if alert.get("severity") == "CRITICAL" else "normal"
                }
                
                self.mesh_client.send_to_channel(
                    channel="dashboard_alerts",
                    payload=dashboard_alert,
                    msg_type="event",
                    priority="normal"
                )
                
                logger.debug("Forwarded alert to dashboard")
                
            except Exception as e:
                logger.error(f"Error forwarding to dashboard: {e}")
    
    def monitoring_loop(self):
        """Main monitoring loop"""
        self.running = True
        
        while self.running:
            try:
                if self.mesh_client:
                    # Poll for safety alerts
                    messages = self.mesh_client.poll(max_messages=10)
                    
                    for packet in messages:
                        if hasattr(packet, 'payload') and isinstance(packet.payload, dict):
                            self.handle_safety_alert(packet.payload)
                
                time.sleep(1.0)  # Poll interval
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5.0)  # Back off on error
    
    def start(self):
        """Start watchtower monitoring"""
        if self.thread is None:
            self.thread = threading.Thread(target=self.monitoring_loop, daemon=True)
            self.thread.start()
            logger.info("Watchtower monitoring started")
    
    def stop(self):
        """Stop watchtower monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info("Watchtower monitoring stopped")


class DashboardAgent:
    """Dashboard - Displays alerts and system status"""
    
    def __init__(self, broker_url: str = "http://localhost:5555"):
        self.agent_id = "dashboard"
        self.broker_url = broker_url
        self.mesh_client = None
        self.alerts = []
        self.max_alerts = 100
        
        if MESH_AVAILABLE:
            try:
                self.mesh_client = MeshClient(
                    agent_id=self.agent_id,
                    broker_url=self.broker_url
                )
                # Subscribe to relevant channels
                self.mesh_client.subscribe("dashboard_alerts")
                self.mesh_client.subscribe("maintenance_events")
                self.mesh_client.subscribe("safety_alerts")
                logger.info(f"Dashboard Agent initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Dashboard mesh client: {e}")
    
    def display_alert(self, alert: Dict[str, Any]) -> None:
        """Display alert on dashboard"""
        # Store alert
        alert["received_at"] = datetime.now(timezone.utc).isoformat()
        self.alerts.append(alert)
        
        # Keep only recent alerts
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        # Log for demonstration
        severity = alert.get("severity", "INFO")
        source = alert.get("source", "unknown")
        reason = alert.get("reason", "No reason")
        
        if severity == "CRITICAL":
            logger.critical(f"📊 DASHBOARD - CRITICAL from {source}: {reason}")
        elif severity == "WARNING":
            logger.warning(f"📊 DASHBOARD - WARNING from {source}: {reason}")
        else:
            logger.info(f"📊 DASHBOARD - INFO from {source}: {reason}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get dashboard status"""
        critical_alerts = [a for a in self.alerts if a.get("severity") == "CRITICAL"]
        warning_alerts = [a for a in self.alerts if a.get("severity") == "WARNING"]
        
        return {
            "total_alerts": len(self.alerts),
            "critical_alerts": len(critical_alerts),
            "warning_alerts": len(warning_alerts),
            "latest_alert": self.alerts[-1] if self.alerts else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def run_demo():
    """Run mesh control loop demonstration"""
    print("=" * 70)
    print("MESH BUS CONTROL LOOP DEMONSTRATION")
    print("=" * 70)
    print()
    print("This demo shows a real control loop on the mesh bus:")
    print("1. BRP detects high risk → sends safety_alert")
    print("2. Watchtower receives alert → reacts with recommendation")
    print("3. Dashboard displays alerts → operator notified")
    print("4. ProjectX (if running) analyzes patterns → suggests actions")
    print()
    
    if not MESH_AVAILABLE:
        print("⚠️  MeshClient not available. Running in simulation mode.")
        print()
    
    # Create agents
    brp = BRPAgent()
    watchtower = WatchtowerAgent()
    dashboard = DashboardAgent()
    
    # Start watchtower monitoring
    watchtower.start()
    
    print("✅ Agents initialized")
    print("⏱  Running demo for 60 seconds...")
    print()
    
    # Run demo for 60 seconds
    start_time = time.time()
    
    while time.time() - start_time < 60:
        # Simulate BRP risk detection
        import random
        
        # Random chance of risk detection
        if random.random() < 0.3:  # 30% chance each iteration
            risk_score = random.uniform(0.5, 1.0)
            reasons = [
                "Market volatility spike detected",
                "Position limits approaching",
                "Unusual trading pattern",
                "Risk metric threshold exceeded",
                "System performance degradation"
            ]
            reason = random.choice(reasons)
            
            brp.detect_high_risk(risk_score, reason)
        
        # Dashboard polls for messages
        if dashboard.mesh_client:
            try:
                messages = dashboard.mesh_client.poll(max_messages=5)
                for packet in messages:
                    if hasattr(packet, 'payload') and isinstance(packet.payload, dict):
                        dashboard.display_alert(packet.payload)
            except Exception as e:
                logger.error(f"Dashboard poll error: {e}")
        
        # Display status every 10 seconds
        if int(time.time() - start_time) % 10 == 0:
            status = dashboard.get_status()
            print(f"📈 Status: {status['total_alerts']} alerts "
                  f"({status['critical_alerts']} critical, "
                  f"{status['warning_alerts']} warnings)")
        
        time.sleep(2.0)
    
    # Stop watchtower
    watchtower.stop()
    
    # Final status
    print()
    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    
    status = dashboard.get_status()
    print(f"📊 Final Dashboard Status:")
    print(f"   Total alerts received: {status['total_alerts']}")
    print(f"   Critical alerts: {status['critical_alerts']}")
    print(f"   Warning alerts: {status['warning_alerts']}")
    
    if status['latest_alert']:
        latest = status['latest_alert']
        print(f"   Latest alert: {latest.get('source', 'unknown')} - "
              f"{latest.get('severity', 'INFO')}: {latest.get('reason', 'No reason')}")
    
    print()
    print("This demonstrates how the mesh bus enables:")
    print("✅ Decoupled agent communication")
    print("✅ Real-time safety monitoring")
    print("✅ Coordinated system responses")
    print("✅ Operator visibility and control")
    print()
    print("Next steps:")
    print("1. Integrate with real ProjectX for pattern analysis")
    print("2. Add QuantumArb trade updates to the loop")
    print("3. Implement actual trading pause commands")
    print("4. Add persistence for alert history")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()