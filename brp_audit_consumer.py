#!/usr/bin/env python3
"""
BRP Audit Consumer — Listens to brp_alerts channel for quantum BRP audits.

Subscribes to the 'brp_alerts' mesh channel, receives BRP threat alerts,
persists them to audit logs, and can trigger automated responses.

Features:
1. Real-time BRP alert monitoring
2. Audit log persistence (JSONL)
3. Threat severity classification
4. Automated response triggers
5. Integration with trust scoring
6. Quantum BRP audit support

Usage:
    python3.10 brp_audit_consumer.py --run-daemon
    python3.10 brp_audit_consumer.py --test-alert
"""

import sys
import os
import json
import time
import logging
import argparse
import threading
import signal
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from enum import Enum

# Allow running from simp root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s %(message)s'
)
logger = logging.getLogger("brp_audit_consumer")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
AUDIT_LOG_DIR = DATA_DIR / "brp_audit_logs"
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Data Models ──────────────────────────────────────────────────────────────

class ThreatSeverity(Enum):
    """BRP threat severity levels."""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"
    QUANTUM = "quantum"  # Special: quantum BRP audit findings


class AuditAction(Enum):
    """Actions taken in response to BRP alerts."""
    LOGGED = "logged"
    ALERTED = "alerted"
    BLOCKED = "blocked"
    QUARANTINED = "quarantined"
    TRUST_ADJUSTED = "trust_adjusted"
    ESCALATED = "escalated"


@dataclass
class BRPAlert:
    """BRP threat alert from mesh channel."""
    alert_id: str
    agent_id: str
    threat_level: str
    confidence: float
    patterns: List[Dict[str, Any]]
    timestamp: str
    blocked: bool
    source: str = "brp_gateway"
    quantum_relevance: Optional[float] = None  # For quantum BRP audits
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "agent_id": self.agent_id,
            "threat_level": self.threat_level,
            "confidence": self.confidence,
            "patterns": self.patterns,
            "timestamp": self.timestamp,
            "blocked": self.blocked,
            "source": self.source,
            "quantum_relevance": self.quantum_relevance,
        }


@dataclass
class AuditRecord:
    """Audit record for BRP alerts."""
    record_id: str
    alert: BRPAlert
    action_taken: AuditAction
    action_details: Dict[str, Any]
    processed_by: str = "brp_audit_consumer"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "alert": self.alert.to_dict(),
            "action_taken": self.action_taken.value,
            "action_details": self.action_details,
            "processed_by": self.processed_by,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentThreatProfile:
    """Threat profile for an agent based on BRP alerts."""
    agent_id: str
    total_alerts: int = 0
    high_severity_count: int = 0
    last_alert_time: Optional[str] = None
    trust_score_adjustment: float = 0.0
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "total_alerts": self.total_alerts,
            "high_severity_count": self.high_severity_count,
            "last_alert_time": self.last_alert_time,
            "trust_score_adjustment": self.trust_score_adjustment,
            "is_quarantined": self.is_quarantined,
            "quarantine_reason": self.quarantine_reason,
        }


# ── BRP Audit Consumer ──────────────────────────────────────────────────────

class BRPAuditConsumer:
    """Consumes BRP alerts from mesh channel and manages audit logs."""
    
    def __init__(self, broker_url: str = "http://127.0.0.1:5555"):
        self.broker_url = broker_url
        self.agent_id = "brp_audit_consumer"
        self.running = False
        self._lock = threading.RLock()
        
        # Audit state
        self.audit_log_path = AUDIT_LOG_DIR / f"brp_audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self.agent_profiles: Dict[str, AgentThreatProfile] = {}
        self.quantum_audits: List[Dict[str, Any]] = []
        
        # Response thresholds
        self.thresholds = {
            "auto_quarantine": 3,  # Auto-quarantine after 3 HIGH+ alerts
            "trust_penalty_high": -0.5,
            "trust_penalty_critical": -1.5,
            "quantum_relevance_min": 0.7,  # Minimum quantum relevance for quantum classification
        }
        
        logger.info(f"BRP Audit Consumer initialized (broker: {broker_url})")
    
    def _append_audit_log(self, record: AuditRecord) -> None:
        """Append audit record to JSONL log file."""
        with self._lock:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
    
    def _load_agent_profiles(self) -> None:
        """Load agent threat profiles from disk."""
        profiles_file = AUDIT_LOG_DIR / "agent_threat_profiles.json"
        if profiles_file.exists():
            try:
                with open(profiles_file, "r") as f:
                    data = json.load(f)
                    for agent_id, profile_data in data.items():
                        self.agent_profiles[agent_id] = AgentThreatProfile(
                            agent_id=agent_id,
                            total_alerts=profile_data.get("total_alerts", 0),
                            high_severity_count=profile_data.get("high_severity_count", 0),
                            last_alert_time=profile_data.get("last_alert_time"),
                            trust_score_adjustment=profile_data.get("trust_score_adjustment", 0.0),
                            is_quarantined=profile_data.get("is_quarantined", False),
                            quarantine_reason=profile_data.get("quarantine_reason"),
                        )
                logger.info(f"Loaded {len(self.agent_profiles)} agent threat profiles")
            except Exception as e:
                logger.error(f"Failed to load agent profiles: {e}")
    
    def _save_agent_profiles(self) -> None:
        """Save agent threat profiles to disk."""
        profiles_file = AUDIT_LOG_DIR / "agent_threat_profiles.json"
        with self._lock:
            data = {agent_id: profile.to_dict() for agent_id, profile in self.agent_profiles.items()}
            with open(profiles_file, "w") as f:
                json.dump(data, f, indent=2)
    
    def _get_or_create_profile(self, agent_id: str) -> AgentThreatProfile:
        """Get or create threat profile for an agent."""
        if agent_id not in self.agent_profiles:
            self.agent_profiles[agent_id] = AgentThreatProfile(agent_id=agent_id)
        return self.agent_profiles[agent_id]
    
    def _determine_action(self, alert: BRPAlert) -> AuditAction:
        """Determine appropriate action based on alert severity and history."""
        profile = self._get_or_create_profile(alert.agent_id)
        
        # Update profile
        profile.total_alerts += 1
        if alert.threat_level in ["high", "critical", "quantum"]:
            profile.high_severity_count += 1
        profile.last_alert_time = alert.timestamp
        
        # Determine action
        if alert.threat_level == "critical":
            if profile.high_severity_count >= self.thresholds["auto_quarantine"]:
                return AuditAction.QUARANTINED
            return AuditAction.BLOCKED
        elif alert.threat_level == "high":
            if profile.high_severity_count >= self.thresholds["auto_quarantine"]:
                return AuditAction.QUARANTINED
            return AuditAction.TRUST_ADJUSTED
        elif alert.threat_level == "quantum":
            # Quantum BRP audits get special handling
            return AuditAction.ESCALATED
        elif alert.threat_level == "medium":
            return AuditAction.ALERTED
        else:  # low
            return AuditAction.LOGGED
    
    def _execute_action(self, alert: BRPAlert, action: AuditAction) -> Dict[str, Any]:
        """Execute the determined action and return details."""
        action_details = {
            "alert_id": alert.alert_id,
            "agent_id": alert.agent_id,
            "threat_level": alert.threat_level,
            "action": action.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        profile = self._get_or_create_profile(alert.agent_id)
        
        if action == AuditAction.QUARANTINED:
            profile.is_quarantined = True
            profile.quarantine_reason = f"Multiple high-severity alerts ({profile.high_severity_count})"
            action_details["quarantine_reason"] = profile.quarantine_reason
            action_details["trust_adjustment"] = self.thresholds["trust_penalty_critical"]
            profile.trust_score_adjustment += self.thresholds["trust_penalty_critical"]
            
            # TODO: Actually quarantine agent in mesh/broker
            logger.warning(f"Agent {alert.agent_id} quarantined: {profile.quarantine_reason}")
        
        elif action == AuditAction.BLOCKED:
            action_details["blocked"] = alert.blocked
            action_details["trust_adjustment"] = self.thresholds["trust_penalty_critical"]
            profile.trust_score_adjustment += self.thresholds["trust_penalty_critical"]
            
        elif action == AuditAction.TRUST_ADJUSTED:
            action_details["trust_adjustment"] = self.thresholds["trust_penalty_high"]
            profile.trust_score_adjustment += self.thresholds["trust_penalty_high"]
            
            # TODO: Apply trust adjustment to TrustGraph
            logger.info(f"Trust adjustment for {alert.agent_id}: {self.thresholds['trust_penalty_high']}")
        
        elif action == AuditAction.ESCALATED:
            # Quantum BRP audit - special handling
            action_details["quantum_relevance"] = alert.quantum_relevance
            action_details["escalation_reason"] = "Quantum BRP audit finding"
            
            # Store quantum audit for analysis
            quantum_audit = {
                "alert": alert.to_dict(),
                "action": action.value,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            self.quantum_audits.append(quantum_audit)
            
            # Save quantum audits to separate file
            quantum_file = AUDIT_LOG_DIR / "quantum_brp_audits.json"
            with open(quantum_file, "w") as f:
                json.dump(self.quantum_audits[-100:], f, indent=2)  # Keep last 100
            
            logger.info(f"Quantum BRP audit escalated: {alert.agent_id} (relevance: {alert.quantum_relevance})")
        
        elif action == AuditAction.ALERTED:
            action_details["alert_sent"] = True
            # TODO: Send alert to operator/dashboard
        
        # Save updated profiles
        self._save_agent_profiles()
        
        return action_details
    
    def process_alert(self, alert_data: Dict[str, Any]) -> Optional[AuditRecord]:
        """Process a BRP alert from mesh channel."""
        try:
            # Parse alert
            alert = BRPAlert(
                alert_id=f"brp_alert_{int(time.time())}_{hash(str(alert_data)) % 10000:04d}",
                agent_id=alert_data.get("agent_id", "unknown"),
                threat_level=alert_data.get("threat_level", "low"),
                confidence=alert_data.get("confidence", 0.0),
                patterns=alert_data.get("patterns", []),
                timestamp=alert_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                blocked=alert_data.get("blocked", False),
                source=alert_data.get("source", "brp_gateway"),
                quantum_relevance=alert_data.get("quantum_relevance"),
            )
            
            # Check if this is a quantum BRP audit
            if alert.quantum_relevance and alert.quantum_relevance >= self.thresholds["quantum_relevance_min"]:
                alert.threat_level = "quantum"
            
            # Determine and execute action
            action = self._determine_action(alert)
            action_details = self._execute_action(alert, action)
            
            # Create audit record
            record = AuditRecord(
                record_id=f"audit_{int(time.time())}_{hash(str(alert_data)) % 10000:04d}",
                alert=alert,
                action_taken=action,
                action_details=action_details,
            )
            
            # Log to audit trail
            self._append_audit_log(record)
            
            logger.info(f"Processed BRP alert: {alert.agent_id} -> {alert.threat_level} -> {action.value}")
            return record
            
        except Exception as e:
            logger.error(f"Failed to process BRP alert: {e}")
            return None
    
    def poll_mesh_alerts(self) -> List[Dict[str, Any]]:
        """Poll mesh for BRP alerts on brp_alerts channel."""
        try:
            import requests
            
            # Poll mesh for messages (GET with query params)
            poll_url = f"{self.broker_url}/mesh/poll"
            response = requests.get(poll_url, params={
                "agent_id": self.agent_id,
                "channel": "brp_alerts",
                "max_messages": 10,
            })
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])
                
                alerts = []
                for msg in messages:
                    if msg.get("channel") == "brp_alerts":
                        payload = msg.get("payload", {})
                        if payload.get("type") == "brp_threat_alert":
                            alerts.append(payload)
                
                return alerts
            else:
                logger.warning(f"Mesh poll failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to poll mesh: {e}")
            return []
    
    def register_with_broker(self) -> bool:
        """Register with SIMP broker."""
        try:
            import requests
            
            register_url = f"{self.broker_url}/agents/register"
            response = requests.post(register_url, json={
                "agent_id": self.agent_id,
                "agent_type": "security_audit",
                "endpoint": "(file-based)",
                "capabilities": ["security_monitoring", "threat_audit", "trust_adjustment"],
                "metadata": {
                    "description": "BRP Audit Consumer - Security monitoring agent",
                    "version": "1.0.0",
                }
            })
            
            if response.status_code in [200, 201]:  # 201 Created is also success
                logger.info(f"Registered with broker: {self.agent_id}")
                return True
            else:
                logger.warning(f"Registration failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False
    
    def subscribe_to_brp_alerts(self) -> bool:
        """Subscribe to brp_alerts mesh channel."""
        try:
            import requests
            
            subscribe_url = f"{self.broker_url}/mesh/subscribe"
            response = requests.post(subscribe_url, json={
                "agent_id": self.agent_id,
                "channel": "brp_alerts",
            })
            
            if response.status_code == 200:
                logger.info(f"Subscribed to brp_alerts channel")
                return True
            else:
                logger.warning(f"Subscription failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Subscription error: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        """Send heartbeat to broker."""
        try:
            import requests
            
            heartbeat_url = f"{self.broker_url}/agents/{self.agent_id}/heartbeat"
            response = requests.post(heartbeat_url, json={})
            
            if response.status_code == 200:
                return True
            else:
                # Try alternative endpoint
                heartbeat_url = f"{self.broker_url}/agents/heartbeat"
                response = requests.post(heartbeat_url, json={"agent_id": self.agent_id})
                return response.status_code == 200
                
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
            return False
    
    def run_daemon(self, poll_interval: int = 10):
        """Run BRP audit consumer daemon."""
        logger.info(f"Starting BRP Audit Consumer Daemon (interval: {poll_interval}s)")
        
        # Load existing profiles
        self._load_agent_profiles()
        
        # Register with broker
        if not self.register_with_broker():
            logger.warning("Failed to register with broker, continuing in offline mode")
        
        # Subscribe to brp_alerts channel
        if not self.subscribe_to_brp_alerts():
            logger.warning("Failed to subscribe to brp_alerts channel")
        
        self.running = True
        last_heartbeat = 0
        
        try:
            while self.running:
                current_time = time.time()
                
                # Send heartbeat every 30 seconds
                if current_time - last_heartbeat > 30:
                    if self.send_heartbeat():
                        last_heartbeat = current_time
                
                # Poll for BRP alerts
                alerts = self.poll_mesh_alerts()
                
                # Process alerts
                for alert_data in alerts:
                    record = self.process_alert(alert_data)
                    if record:
                        logger.debug(f"Processed alert: {record.alert.agent_id}")
                
                # Log status periodically
                if len(alerts) > 0:
                    logger.info(f"Processed {len(alerts)} BRP alerts")
                
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("BRP Audit Consumer stopped by user")
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")
        finally:
            self.running = False
            self._save_agent_profiles()
            logger.info("BRP Audit Consumer stopped")


# ── Test Functions ──────────────────────────────────────────────────────────

def send_test_alert(broker_url: str = "http://127.0.0.1:5555"):
    """Send a test BRP alert to brp_alerts channel."""
    try:
        import requests
        
        test_alert = {
            "type": "brp_threat_alert",
            "agent_id": "test_malicious_agent",
            "threat_level": "high",
            "confidence": 0.85,
            "patterns": [
                {"type": "unauthorized_intent", "details": "tried to escalate privileges"},
                {"type": "suspicious_timing", "details": "rapid fire requests"}
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "blocked": True,
            "source": "brp_gateway",
            "quantum_relevance": 0.15,  # Low quantum relevance
        }
        
        # Send via mesh
        send_url = f"{broker_url}/mesh/send"
        response = requests.post(send_url, json={
            "channel": "brp_alerts",
            "sender_id": "test_sender",
            "recipient_id": "*",  # Broadcast
            "payload": test_alert,
            "ttl_seconds": 300,
        })
        
        if response.status_code == 200:
            print(f"✓ Test alert sent: {test_alert['agent_id']} -> {test_alert['threat_level']}")
            return True
        else:
            print(f"✗ Failed to send test alert: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error sending test alert: {e}")
        return False


def send_quantum_brp_audit(broker_url: str = "http://127.0.0.1:5555"):
    """Send a quantum BRP audit alert (simulating QIP Grover's search result)."""
    try:
        import requests
        
        quantum_audit = {
            "type": "brp_threat_alert",
            "agent_id": "quantum_audit_target",
            "threat_level": "medium",  # Will be upgraded to "quantum" by consumer
            "confidence": 0.92,
            "patterns": [
                {"type": "quantum_anomaly", "details": "Grover's search found constraint violation"},
                {"type": "trust_score_drop", "details": "Score < 1.0 detected"},
                {"type": "intent_escalation", "details": "Unauthorized capability request"}
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "blocked": False,
            "source": "quantum_intelligence_prime",
            "quantum_relevance": 0.85,  # High quantum relevance
        }
        
        # Send via mesh
        send_url = f"{broker_url}/mesh/send"
        response = requests.post(send_url, json={
            "channel": "brp_alerts",
            "sender_id": "quantum_intelligence_prime",
            "recipient_id": "*",
            "payload": quantum_audit,
            "ttl_seconds": 600,
        })
        
        if response.status_code == 200:
            print(f"✓ Quantum BRP audit sent: {quantum_audit['agent_id']} (quantum relevance: {quantum_audit['quantum_relevance']})")
            return True
        else:
            print(f"✗ Failed to send quantum audit: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error sending quantum audit: {e}")
        return False


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BRP Audit Consumer")
    parser.add_argument("--run-daemon", action="store_true",
                       help="Run BRP audit consumer daemon")
    parser.add_argument("--poll-interval", type=int, default=10,
                       help="Polling interval in seconds (default: 10)")
    parser.add_argument("--broker", type=str, default="http://127.0.0.1:5555",
                       help="Broker URL (default: http://127.0.0.1:5555)")
    parser.add_argument("--test-alert", action="store_true",
                       help="Send a test BRP alert")
    parser.add_argument("--test-quantum", action="store_true",
                       help="Send a quantum BRP audit alert")
    parser.add_argument("--show-stats", action="store_true",
                       help="Show BRP audit statistics")
    
    args = parser.parse_args()
    consumer = BRPAuditConsumer(broker_url=args.broker)
    
    if args.test_alert:
        send_test_alert(args.broker)
    
    elif args.test_quantum:
        send_quantum_brp_audit(args.broker)
    
    elif args.show_stats:
        consumer._load_agent_profiles()
        print(f"\nBRP Audit Statistics:")
        print(f"  Agent profiles: {len(consumer.agent_profiles)}")
        print(f"  Audit log: {consumer.audit_log_path}")
        
        high_risk = sum(1 for p in consumer.agent_profiles.values() 
                       if p.high_severity_count > 0)
        quarantined = sum(1 for p in consumer.agent_profiles.values() 
                         if p.is_quarantined)
        
        print(f"  High-risk agents: {high_risk}")
        print(f"  Quarantined agents: {quarantined}")
        
        if consumer.agent_profiles:
            print(f"\nTop 5 high-risk agents:")
            sorted_profiles = sorted(consumer.agent_profiles.values(), 
                                   key=lambda p: p.high_severity_count, 
                                   reverse=True)[:5]
            for profile in sorted_profiles:
                print(f"  - {profile.agent_id}: {profile.high_severity_count} high alerts, "
                      f"trust adjustment: {profile.trust_score_adjustment}")
    
    elif args.run_daemon:
        consumer.run_daemon(poll_interval=args.poll_interval)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()