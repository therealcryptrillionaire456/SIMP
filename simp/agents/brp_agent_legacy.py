#!/usr/bin/env python3
"""
Bill Russel Protocol Agent - Defensive MVP for Mythos Reconstruction.

Named after the greatest defensive basketball player ever.

Core Capabilities:
1. Pattern Recognition at Depth
2. Autonomous Reasoning Chains  
3. Memory Across Time

This agent integrates with SIMP broker to provide threat detection
and autonomous response capabilities.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import urllib.request
import urllib.error
import argparse
import threading
import sqlite3

# Import Bill Russel Protocol components
try:
    # Try relative import first
    from ..mythos_implementation.bill_russel_protocol import BillRusselProtocol
    from ..mythos_implementation.bill_russel_protocol.pattern_recognition import PatternType
    from ..mythos_implementation.bill_russel_protocol.reasoning_engine import ThreatLevel, ThreatAssessment
    from ..mythos_implementation.bill_russel_protocol.alert_orchestrator import ResponseAction
except ImportError:
    # Fall back to absolute import
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from mythos_implementation.bill_russel_protocol import BillRusselProtocol
    from mythos_implementation.bill_russel_protocol.pattern_recognition import PatternType
    from mythos_implementation.bill_russel_protocol.reasoning_engine import ThreatLevel, ThreatAssessment
    from mythos_implementation.bill_russel_protocol.alert_orchestrator import ResponseAction

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_ID = "bill_russel"
AGENT_VERSION = "1.0.0"

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
BILL_RUSSEL_DIR = BASE_DIR / "mythos_implementation" / "bill_russel_protocol"
DATA_DIR = BASE_DIR / "data" / "bill_russel"
INBOX_DIR = DATA_DIR / "inbox"
OUTBOX_DIR = DATA_DIR / "outbox"
THREAT_DB_PATH = DATA_DIR / "threat_memory.db"

# Ensure directories exist
for dir_path in [DATA_DIR, INBOX_DIR, OUTBOX_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "bill_russel_agent.log"),
        logging.StreamHandler()
    ]
)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class ThreatType(str, Enum):
    """Types of threats detected by Bill Russel Protocol."""
    PROBING = "probing"
    ENUMERATION = "enumeration"
    BRUTE_FORCE = "brute_force"
    DATA_EXFILTRATION = "data_exfiltration"
    DDoS = "ddos"
    MALWARE = "malware"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"


@dataclass
class ThreatEvent:
    """A threat event detected by the Bill Russel Protocol."""
    event_id: str
    timestamp: str
    source_ip: str
    threat_type: ThreatType
    description: str
    confidence: float
    patterns: List[str]
    context: Dict[str, Any]
    
    @classmethod
    def from_bill_russel(cls, detection_result: Dict[str, Any]) -> "ThreatEvent":
        """Create a ThreatEvent from Bill Russel Protocol detection."""
        return cls(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            source_ip=detection_result.get("source_ip", "unknown"),
            threat_type=ThreatType(detection_result.get("threat_type", "anomalous_behavior")),
            description=detection_result.get("description", ""),
            confidence=detection_result.get("confidence", 0.0),
            patterns=detection_result.get("patterns", []),
            context=detection_result.get("context", {})
        )
    
    def to_simp_intent(self, source_agent: str = "bill_russel") -> Dict[str, Any]:
        """Convert to SIMP intent format."""
        return {
            "intent_type": "threat_detected",
            "source_agent": source_agent,
            "target_agent": "auto",  # Let broker route
            "payload": {
                "event_id": self.event_id,
                "timestamp": self.timestamp,
                "threat_type": self.threat_type.value,
                "source_ip": self.source_ip,
                "confidence": self.confidence,
                "description": self.description,
                "patterns": self.patterns,
                "context": self.context,
                "response_required": self.confidence > 0.5,
                "severity": "high" if self.confidence > 0.7 else "medium" if self.confidence > 0.3 else "low"
            },
            "metadata": {
                "version": "1.0",
                "priority": "high" if self.confidence > 0.7 else "normal",
                "requires_acknowledgment": True
            }
        }


@dataclass
class ThreatResponse:
    """Response to a threat event."""
    response_id: str
    event_id: str
    timestamp: str
    action: str
    details: Dict[str, Any]
    effectiveness: Optional[float] = None
    
    @classmethod
    def from_bill_russel(cls, event_id: str, response: Dict[str, Any]) -> "ThreatResponse":
        """Create a ThreatResponse from Bill Russel Protocol response."""
        return cls(
            response_id=str(uuid.uuid4()),
            event_id=event_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            action=response.get("action", "monitor"),
            details=response,
            effectiveness=response.get("confidence", 0.0)
        )


# ---------------------------------------------------------------------------
# Bill Russel Agent
# ---------------------------------------------------------------------------

class BillRusselAgent:
    """Bill Russel Protocol agent for SIMP integration."""
    
    def __init__(self, poll_interval: float = 5.0):
        """Initialize the Bill Russel agent."""
        self.poll_interval = poll_interval
        self.running = False
        self.protocol = None
        self._init_protocol()
        
        # Thread for background processing
        self.processing_thread = None
        
        log.info(f"Bill Russel Agent initialized (v{AGENT_VERSION})")
        log.info(f"Inbox: {INBOX_DIR}")
        log.info(f"Outbox: {OUTBOX_DIR}")
        log.info(f"Threat DB: {THREAT_DB_PATH}")
    
    def _init_protocol(self):
        """Initialize the Bill Russel Protocol."""
        try:
            self.protocol = BillRusselProtocol(
                db_path=str(THREAT_DB_PATH),
                telegram_enabled=False  # Will integrate with SIMP instead
            )
            log.info("Bill Russel Protocol initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize Bill Russel Protocol: {e}")
            raise
    
    def _ensure_dirs(self):
        """Ensure required directories exist."""
        for dir_path in [INBOX_DIR, OUTBOX_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def run(self):
        """Run the agent main loop."""
        self.running = True
        self._ensure_dirs()
        
        log.info("Bill Russel Agent starting...")
        
        # Start background processing thread
        self.processing_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.processing_thread.start()
        
        try:
            while self.running:
                # Check for new intents in inbox
                self._process_inbox()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            log.info("Shutdown signal received")
        finally:
            self.running = False
            if self.processing_thread:
                self.processing_thread.join(timeout=5.0)
            log.info("Bill Russel Agent stopped")
    
    def _process_loop(self):
        """Background processing loop for threat detection."""
        log.info("Background threat detection started")
        
        while self.running:
            try:
                # Check for new threat data (simulated for now)
                # In production, this would monitor logs, network traffic, etc.
                self._check_for_threats()
            except Exception as e:
                log.error(f"Error in threat detection loop: {e}")
            
            time.sleep(self.poll_interval * 2)  # Check less frequently
    
    def _check_for_threats(self):
        """Check for new threats (simulated for demo)."""
        # This is where real threat detection would happen
        # For now, we'll simulate occasional threats
        import random
        
        if random.random() < 0.1:  # 10% chance per check
            simulated_threat = {
                "source_ip": f"192.168.1.{random.randint(1, 255)}",
                "threat_type": random.choice(list(ThreatType)).value,
                "description": f"Simulated {random.choice(['probing', 'enumeration', 'brute_force'])} attempt",
                "confidence": random.uniform(0.3, 0.9),
                "patterns": [random.choice(["directory_enum", "port_scan", "sql_injection"])],
                "context": {"simulated": True, "timestamp": datetime.utcnow().isoformat()}
            }
            
            threat_event = ThreatEvent.from_bill_russel(simulated_threat)
            self._handle_threat_event(threat_event)
    
    def _process_inbox(self):
        """Process incoming SIMP intents."""
        try:
            inbox_files = list(INBOX_DIR.glob("*.json"))
            for file_path in inbox_files:
                try:
                    with open(file_path, 'r') as f:
                        intent = json.load(f)
                    
                    log.info(f"Processing intent from {file_path.name}")
                    self._handle_intent(intent)
                    
                    # Move to processed
                    processed_dir = INBOX_DIR / "processed"
                    processed_dir.mkdir(exist_ok=True)
                    file_path.rename(processed_dir / file_path.name)
                    
                except Exception as e:
                    log.error(f"Error processing {file_path}: {e}")
                    # Move to failed
                    failed_dir = INBOX_DIR / "failed"
                    failed_dir.mkdir(exist_ok=True)
                    file_path.rename(failed_dir / file_path.name)
                    
        except Exception as e:
            log.error(f"Error processing inbox: {e}")
    
    def _handle_intent(self, intent: Dict[str, Any]):
        """Handle an incoming SIMP intent."""
        intent_type = intent.get("intent_type", "")
        
        handlers = {
            "threat_analysis": self._handle_threat_analysis,
            "security_audit": self._handle_security_audit,
            "pattern_detection": self._handle_pattern_detection,
            "ping": self._handle_ping
        }
        
        handler = handlers.get(intent_type)
        if handler:
            try:
                result = handler(intent)
                self._write_response(intent, result)
            except Exception as e:
                log.error(f"Error handling intent {intent_type}: {e}")
                self._write_error(intent, str(e))
        else:
            log.warning(f"Unknown intent type: {intent_type}")
            self._write_error(intent, f"Unknown intent type: {intent_type}")
    
    def _handle_threat_analysis(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a potential threat."""
        payload = intent.get("payload", {})
        
        # Extract threat data from intent
        threat_data = {
            "source_ip": payload.get("source_ip", "unknown"),
            "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
            "event_type": payload.get("event_type", "unknown"),
            "details": payload.get("details", {}),
            "raw_data": payload.get("raw_data", "")
        }
        
        # Use Bill Russel Protocol to analyze
        patterns = self.protocol.pattern_recognizer.analyze(threat_data)
        assessment = self.protocol.reasoning_engine.assess_threat(patterns, threat_data)
        
        # Get historical context
        context = self.protocol.memory_system.get_context(threat_data)
        
        # Orchestrate response
        response = self.protocol.alert_orchestrator.orchestrate_response(
            assessment, context
        )
        
        # Convert dataclasses to dicts
        from dataclasses import asdict
        
        return {
            "analysis_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "patterns_detected": [asdict(p) for p in patterns],
            "threat_assessment": asdict(assessment),
            "historical_context": context,
            "recommended_response": response,
            "confidence": assessment.confidence
        }
    
    def _handle_security_audit(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a security audit."""
        # Get threat report for last 24 hours (1 day)
        threat_report = self.protocol.memory_system.get_threat_report(days=1)
        
        # Run correlation sweep
        correlations = self.protocol.memory_system.correlate_events(time_window_days=1)
        
        # Extract threat statistics from report
        threat_stats = threat_report.get('threat_statistics', {})
        total_threats = threat_report.get('total_threats', 0)
        
        # Calculate confidence breakdown
        high_confidence = 0
        medium_confidence = 0
        for level, stats in threat_stats.items():
            if level in ['critical', 'high']:
                high_confidence += stats.get('count', 0)
            elif level == 'medium':
                medium_confidence += stats.get('count', 0)
        
        # Get recent threat entries
        recent_threats = threat_report.get('recent_threats', [])
        
        return {
            "audit_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "time_period_days": 1,
            "total_threats": total_threats,
            "high_confidence_threats": high_confidence,
            "medium_confidence_threats": medium_confidence,
            "threat_statistics": threat_stats,
            "recent_threats": recent_threats[:10],  # Limit to 10 most recent
            "correlations_found": len(correlations),
            "correlations": correlations[:5],  # Limit to 5 most significant
            "threat_memory_size": self._get_threat_db_size(),
            "recommendations": self._generate_audit_recommendations(recent_threats)
        }
    
    def _handle_pattern_detection(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Detect patterns in security data."""
        payload = intent.get("payload", {})
        data = payload.get("data", [])
        
        if not data:
            return {"error": "No data provided for pattern detection"}
        
        patterns = []
        for item in data:
            detected = self.protocol.pattern_recognizer.analyze(item)
            patterns.extend(detected)
        
        # Group patterns by type
        pattern_counts = {}
        for pattern in patterns:
            p_type = pattern.pattern_type.value
            pattern_counts[p_type] = pattern_counts.get(p_type, 0) + 1
        
        # Convert dataclasses to dicts
        from dataclasses import asdict
        
        return {
            "detection_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_patterns": len(patterns),
            "pattern_counts": pattern_counts,
            "patterns": [asdict(p) for p in patterns[:20]],  # Limit output
            "most_common_pattern": max(pattern_counts.items(), key=lambda x: x[1])[0] if pattern_counts else "none"
        }
    
    def _handle_ping(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping intent."""
        return {
            "status": "active",
            "agent_id": AGENT_ID,
            "version": AGENT_VERSION,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "capabilities": [
                "threat_detection",
                "pattern_recognition",
                "autonomous_reasoning",
                "threat_memory",
                "security_audit"
            ],
            "stats": {
                "threat_db_size": self._get_threat_db_size(),
                "protocol_initialized": self.protocol is not None,
                "inbox_dir": str(INBOX_DIR),
                "outbox_dir": str(OUTBOX_DIR)
            }
        }
    
    def _handle_threat_event(self, threat_event: ThreatEvent):
        """Handle a detected threat event."""
        log.info(f"Threat detected: {threat_event.threat_type} from {threat_event.source_ip} "
                f"(confidence: {threat_event.confidence:.2f})")
        
        # Create a threat assessment for the event
        # ThreatLevel, ThreatAssessment, and ResponseAction are already imported at the top
        
        # Determine threat level based on confidence
        if threat_event.confidence < 0.3:
            threat_level = ThreatLevel.LOW
        elif threat_event.confidence < 0.5:
            threat_level = ThreatLevel.MEDIUM
        elif threat_event.confidence < 0.7:
            threat_level = ThreatLevel.HIGH
        else:
            threat_level = ThreatLevel.CRITICAL
        
        # Determine recommended action based on confidence
        if threat_event.confidence < 0.3:
            recommended_action = ResponseAction.LOG_ONLY
        elif threat_event.confidence < 0.5:
            recommended_action = ResponseAction.MONITOR
        elif threat_event.confidence < 0.7:
            recommended_action = ResponseAction.ALERT
        elif threat_event.confidence < 0.8:
            recommended_action = ResponseAction.RATE_LIMIT
        elif threat_event.confidence < 0.9:
            recommended_action = ResponseAction.BLOCK_IP
        else:
            recommended_action = ResponseAction.ISOLATE
        
        # Create assessment
        assessment = ThreatAssessment(
            threat_level=threat_level,
            confidence=threat_event.confidence,
            description=threat_event.description,
            patterns=[],  # Would be populated by pattern recognition
            recommended_action=recommended_action,
            reasoning=f"Threat type: {threat_event.threat_type.value}",
            timestamp=datetime.utcnow(),
            source_ip=threat_event.source_ip
        )
        
        # Store in threat memory
        event_data = {
            "source_ip": threat_event.source_ip,
            "timestamp": threat_event.timestamp,
            "threat_type": threat_event.threat_type.value,
            "description": threat_event.description,
            "confidence": threat_event.confidence,
            "patterns": threat_event.patterns,
            "context": threat_event.context
        }
        
        self.protocol.memory_system.record_event(event_data, assessment)
        
        # Create SIMP intent
        simp_intent = threat_event.to_simp_intent()
        
        # Write to outbox for broker pickup
        self._write_to_outbox(simp_intent)
        
        # Log the threat
        log.warning(f"Threat {threat_event.event_id}: {threat_event.description}")
    
    def _write_response(self, original_intent: Dict[str, Any], result: Dict[str, Any]):
        """Write response to outbox."""
        response_intent = {
            "intent_type": "response",
            "source_agent": AGENT_ID,
            "target_agent": original_intent.get("source_agent", "unknown"),
            "payload": result,
            "metadata": {
                "original_intent_id": original_intent.get("metadata", {}).get("intent_id", "unknown"),
                "response_timestamp": datetime.utcnow().isoformat() + "Z",
                "version": AGENT_VERSION
            }
        }
        
        self._write_to_outbox(response_intent)
    
    def _write_error(self, original_intent: Dict[str, Any], error_message: str):
        """Write error response to outbox."""
        error_intent = {
            "intent_type": "error",
            "source_agent": AGENT_ID,
            "target_agent": original_intent.get("source_agent", "unknown"),
            "payload": {
                "error": error_message,
                "original_intent_type": original_intent.get("intent_type", "unknown")
            },
            "metadata": {
                "original_intent_id": original_intent.get("metadata", {}).get("intent_id", "unknown"),
                "error_timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        self._write_to_outbox(error_intent)
    
    def _write_to_outbox(self, intent: Dict[str, Any]):
        """Write intent to outbox directory."""
        filename = f"{intent.get('intent_type', 'unknown')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.json"
        filepath = OUTBOX_DIR / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(intent, f, indent=2)
            log.debug(f"Written intent to {filepath}")
        except Exception as e:
            log.error(f"Failed to write intent to outbox: {e}")
    
    def _get_threat_db_size(self) -> int:
        """Get size of threat database in bytes."""
        try:
            return THREAT_DB_PATH.stat().st_size if THREAT_DB_PATH.exists() else 0
        except:
            return 0
    
    def _generate_audit_recommendations(self, recent_threats: List[Dict]) -> List[str]:
        """Generate security recommendations based on recent threats."""
        recommendations = []
        
        if not recent_threats:
            recommendations.append("No recent threats detected. System appears secure.")
            return recommendations
        
        # Analyze threat patterns
        ip_counts = {}
        threat_type_counts = {}
        
        for threat in recent_threats:
            # Extract IP from threat data
            threat_data = threat.get('threat_data', {})
            ip = threat_data.get("source_ip", "unknown")
            
            # Extract threat type from assessment
            assessment = threat.get('assessment', {})
            threat_level = assessment.get("threat_level", "unknown")
            
            ip_counts[ip] = ip_counts.get(ip, 0) + 1
            threat_type_counts[threat_level] = threat_type_counts.get(threat_level, 0) + 1
        
        # Generate recommendations
        if ip_counts:
            most_common_ip = max(ip_counts.items(), key=lambda x: x[1])
            if most_common_ip[1] > 5:
                recommendations.append(f"Consider blocking IP {most_common_ip[0]} - {most_common_ip[1]} threats detected")
        
        if threat_type_counts.get("critical", 0) > 0:
            recommendations.append("Critical threats detected. Review immediately and consider incident response.")
        
        if threat_type_counts.get("high", 0) > 3:
            recommendations.append("Multiple high-confidence threats detected. Consider implementing additional security controls.")
        
        if len(recent_threats) > 10:
            recommendations.append("High volume of threats detected. Consider increasing monitoring frequency.")
        
        # Add general recommendations
        if not recommendations:
            recommendations.append("System security posture appears normal. Continue regular monitoring.")
        else:
            recommendations.append("Review threat memory database for detailed analysis.")
        
        return recommendations


# ---------------------------------------------------------------------------
# Registration with SIMP
# ---------------------------------------------------------------------------

def register_with_simp(
    simp_url: str = "http://127.0.0.1:5555",
    api_key: Optional[str] = None,
) -> bool:
    """Register bill_russel with the SIMP broker."""
    payload = {
        "agent_id": AGENT_ID,
        "agent_type": "security",
        "endpoint": f"file://{INBOX_DIR}",
        "metadata": {
            "capabilities": [
                "threat_detection",
                "pattern_recognition", 
                "autonomous_reasoning",
                "threat_memory",
                "security_audit",
                "anomaly_detection"
            ],
            "description": (
                "Bill Russel Protocol - Defensive MVP for Mythos Reconstruction. "
                "Named after the greatest defensive basketball player ever. "
                "Provides pattern recognition at depth, autonomous reasoning chains, "
                "and memory across time for threat detection and response."
            ),
            "version": AGENT_VERSION,
            "dry_run_safe": True,
            "trade_execution": False,
            "inbox_path": str(INBOX_DIR),
            "outbox_path": str(OUTBOX_DIR),
            "requires_authentication": True,
            "security_level": "high"
        },
    }
    
    url = f"{simp_url}/agents/register"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-SIMP-API-Key"] = api_key
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            log.info(f"Registered bill_russel with SIMP: {body}")
            return True
    except urllib.error.URLError as e:
        log.warning(f"Could not register with SIMP: {e}")
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Main entry point for Bill Russel Agent."""
    parser = argparse.ArgumentParser(description="Bill Russel Protocol Agent")
    parser.add_argument(
        "--simp-url",
        default="http://127.0.0.1:5555",
        help="SIMP broker URL (default: http://127.0.0.1:5555)"
    )
    parser.add_argument(
        "--api-key",
        help="SIMP API key (if required)"
    )
    parser.add_argument(
        "--register-only",
        action="store_true",
        help="Register with SIMP and exit"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Poll interval in seconds (default: 5.0)"
    )
    
    args = parser.parse_args()
    
    # Register with SIMP
    if register_with_simp(args.simp_url, args.api_key):
        log.info("Successfully registered with SIMP broker")
    else:
        log.warning("Failed to register with SIMP broker (continuing anyway)")
    
    if args.register_only:
        return
    
    # Run the agent
    agent = BillRusselAgent(poll_interval=args.poll_interval)
    agent.run()


if __name__ == "__main__":
    main()