#!/usr/bin/env python3
"""
Enhanced Bill Russel Protocol Agent - Defensive system against Mythos-level threats.

Named after the greatest defensive basketball player ever.
Based on analysis of Claude Mythos Preview System Card capabilities.

Core Capabilities (countering Mythos):
1. Pattern Recognition at Depth - Sees attacks before completion
2. Autonomous Reasoning Chains - No human review needed
3. Memory Across Time - Correlates events weeks apart
4. Cyber Capability Detection - Zero-day vulnerability discovery
5. Cross-domain Synthesis - Connects disparate threat signals

This agent integrates with SIMP broker to provide advanced threat detection
and autonomous response capabilities specifically designed to counter
Mythos-like AI threats.
"""

import json
import logging
import os
import time
import uuid
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import urllib.request
import urllib.error
import argparse
import threading
import hashlib

# Import enhanced Bill Russell Protocol components
try:
    # Try relative import first
    from ..mythos_implementation.bill_russel_protocol_enhanced import (
        EnhancedBillRussellProtocol,
        MythosPatternRecognizer,
        MythosReasoningEngine,
        MythosMemorySystem,
        ThreatEvent,
        ThreatSeverity
    )
except ImportError:
    # Fall back to absolute import
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from mythos_implementation.bill_russel_protocol_enhanced import (
        EnhancedBillRussellProtocol,
        MythosPatternRecognizer,
        MythosReasoningEngine,
        MythosMemorySystem,
        ThreatEvent,
        ThreatSeverity
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_ID = "bill_russel_enhanced"
AGENT_VERSION = "2.0.0"
AGENT_DESCRIPTION = """
Enhanced Bill Russel Protocol - Defensive system against Mythos-level threats.
Based on analysis of Claude Mythos Preview System Card capabilities.

Key capabilities countering Mythos:
• Pattern Recognition at Depth (sees attacks before completion)
• Autonomous Reasoning Chains (no human review needed)
• Memory Across Time (correlates events weeks apart)
• Cyber Capability Detection (zero-day vulnerability discovery)
• Cross-domain Synthesis (connects disparate threat signals)
"""

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "bill_russel_enhanced"
INBOX_DIR = DATA_DIR / "inbox"
OUTBOX_DIR = DATA_DIR / "outbox"
THREAT_DB_PATH = DATA_DIR / "mythos_threat_memory.db"
LOGS_DIR = DATA_DIR / "logs"

# Ensure directories exist
for dir_path in [DATA_DIR, INBOX_DIR, OUTBOX_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "bill_russel_enhanced.log"),
        logging.StreamHandler()
    ]
)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class ThreatType(str, Enum):
    """Types of threats detected by enhanced Bill Russel Protocol."""
    ZERO_DAY_PROBING = "zero_day_probing"  # Mythos cyber capability
    AUTONOMOUS_CHAIN = "autonomous_chain"  # Mythos reasoning capability
    CROSS_DOMAIN = "cross_domain"  # Mythos synthesis capability
    TEMPORAL_CORRELATION = "temporal_correlation"  # Mythos memory capability
    DEEP_PATTERN = "deep_pattern"  # Mythos pattern recognition
    PROBING = "probing"
    ENUMERATION = "enumeration"
    BRUTE_FORCE = "brute_force"
    DATA_EXFILTRATION = "data_exfiltration"
    DDoS = "ddos"
    MALWARE = "malware"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"


class ResponseAction(str, Enum):
    """Response actions based on threat assessment."""
    LOG_ONLY = "log_only"  # Low confidence
    ALERT_ONLY = "alert_only"  # Medium confidence
    RATE_LIMIT_ALERT = "rate_limit_alert"  # High confidence
    BLOCK_IP = "block_ip"  # Very high confidence
    ISOLATE_SYSTEM = "isolate_system"  # Critical - Mythos-level threat


@dataclass
class EnhancedThreatEvent:
    """Enhanced threat event with Mythos-specific detection."""
    event_id: str
    timestamp: str
    source_ip: str
    threat_type: ThreatType
    details: Dict[str, Any]
    patterns_detected: List[Dict[str, Any]]
    threat_assessment: Dict[str, Any]
    confidence: float
    severity: ThreatSeverity
    response_action: ResponseAction
    mythos_capability_countered: str  # Which Mythos capability this counters
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['threat_type'] = self.threat_type.value
        data['severity'] = self.severity.value
        data['response_action'] = self.response_action.value
        return data


@dataclass
class SecurityIntent:
    """Security intent for SIMP broker."""
    intent_id: str
    intent_type: str = "security_alert"
    source_agent: str = AGENT_ID
    target_agent: str = "auto"  # Let SIMP route it
    timestamp: str = ""
    payload: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if self.payload is None:
            self.payload = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for SIMP broker."""
        return {
            "intent_id": self.intent_id,
            "intent_type": self.intent_type,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "timestamp": self.timestamp,
            "payload": self.payload
        }


# ---------------------------------------------------------------------------
# Enhanced Bill Russel Agent
# ---------------------------------------------------------------------------

class EnhancedBillRusselAgent:
    """Enhanced Bill Russel Protocol agent for SIMP integration."""
    
    def __init__(self, poll_interval: float = 3.0, simp_url: str = "http://127.0.0.1:5555"):
        """Initialize the enhanced Bill Russel agent."""
        self.poll_interval = poll_interval
        self.simp_url = simp_url
        self.running = False
        self.protocol = None
        self._init_protocol()
        
        # Threads for background processing
        self.processing_thread = None
        self.alert_thread = None
        
        # Statistics
        self.stats = {
            'threats_detected': 0,
            'mythos_threats': 0,
            'responses_executed': 0,
            'alerts_sent': 0,
            'start_time': datetime.utcnow().isoformat()
        }
        
        log.info(f"Enhanced Bill Russel Agent initialized (v{AGENT_VERSION})")
        log.info(f"Data directory: {DATA_DIR}")
        log.info(f"Threat database: {THREAT_DB_PATH}")
        log.info(f"SIMP URL: {simp_url}")
    
    def _init_protocol(self):
        """Initialize the enhanced Bill Russel Protocol."""
        try:
            self.protocol = EnhancedBillRussellProtocol(
                db_path=str(THREAT_DB_PATH)
            )
            log.info("Enhanced Bill Russel Protocol initialized successfully")
            
            # Log capabilities
            status = self.protocol.get_system_status()
            log.info(f"System capabilities: {len(status['capabilities'])} capabilities loaded")
            for capability in status['capabilities']:
                log.info(f"  • {capability}")
                
        except Exception as e:
            log.error(f"Failed to initialize enhanced Bill Russel Protocol: {e}")
            raise
    
    def run(self):
        """Run the agent main loop."""
        self.running = True
        self._ensure_dirs()
        
        log.info("Enhanced Bill Russel Agent starting...")
        log.info(AGENT_DESCRIPTION.strip())
        
        # Start background threads
        self.processing_thread = threading.Thread(
            target=self._threat_detection_loop, 
            daemon=True,
            name="ThreatDetection"
        )
        self.processing_thread.start()
        
        self.alert_thread = threading.Thread(
            target=self._alert_processing_loop,
            daemon=True,
            name="AlertProcessing"
        )
        self.alert_thread.start()
        
        try:
            while self.running:
                # Main loop: process SIMP intents and monitor system
                self._process_simp_intents()
                self._update_statistics()
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            log.info("Shutdown signal received")
        except Exception as e:
            log.error(f"Error in main loop: {e}")
        finally:
            self.running = False
            self._shutdown()
    
    def _threat_detection_loop(self):
        """Background threat detection loop."""
        log.info("Mythos-level threat detection started")
        
        # Simulated threat sources (in production: log files, network traffic, etc.)
        threat_sources = [
            self._simulate_network_traffic,
            self._simulate_log_analysis,
            self._simulate_system_monitoring
        ]
        
        source_index = 0
        
        while self.running:
            try:
                # Rotate through threat sources
                threat_source = threat_sources[source_index % len(threat_sources)]
                threats = threat_source()
                
                # Process detected threats
                for threat in threats:
                    self._process_threat(threat)
                
                source_index += 1
                
            except Exception as e:
                log.error(f"Error in threat detection loop: {e}")
            
            time.sleep(self.poll_interval * 1.5)
    
    def _alert_processing_loop(self):
        """Background alert processing loop."""
        log.info("Alert processing started")
        
        while self.running:
            try:
                # Check for high-priority threats that need immediate alerts
                self._check_critical_threats()
                
                # Send periodic status updates to SIMP
                self._send_status_update()
                
            except Exception as e:
                log.error(f"Error in alert processing loop: {e}")
            
            time.sleep(self.poll_interval * 3)
    
    def _simulate_network_traffic(self) -> List[Dict]:
        """Simulate network traffic analysis (Mythos cyber capability detection)."""
        threats = []
        
        # Simulate zero-day probing (Mythos cyber capability)
        if hash(str(datetime.utcnow().minute)) % 3 == 0:
            threats.append({
                'source_ip': f'10.0.{hash(str(datetime.utcnow().hour)) % 256}.{hash(str(datetime.utcnow().minute)) % 256}',
                'event_type': 'network_traffic',
                'details': 'fuzzing parameters with unusual header values for buffer overflow probe',
                'severity': 'high',
                'simulated': True,
                'mythos_capability': 'zero_day_probing'
            })
        
        # Simulate autonomous attack chain (Mythos reasoning capability)
        if hash(str(datetime.utcnow().minute)) % 5 == 0:
            threats.append({
                'source_ip': f'192.168.{hash(str(datetime.utcnow().hour)) % 256}.{hash(str(datetime.utcnow().minute)) % 256}',
                'event_type': 'autonomous_attack',
                'details': 'multi-step attack with chained exploits and automated reconnaissance',
                'severity': 'critical',
                'simulated': True,
                'mythos_capability': 'autonomous_chain'
            })
        
        return threats
    
    def _simulate_log_analysis(self) -> List[Dict]:
        """Simulate log analysis (Mythos pattern recognition)."""
        threats = []
        
        # Simulate cross-domain attack (Mythos synthesis capability)
        if hash(str(datetime.utcnow().minute)) % 4 == 0:
            threats.append({
                'source_ip': f'172.16.{hash(str(datetime.utcnow().hour)) % 256}.{hash(str(datetime.utcnow().minute)) % 256}',
                'event_type': 'log_analysis',
                'details': 'network access followed by data exfiltration and lateral movement patterns',
                'severity': 'medium',
                'simulated': True,
                'mythos_capability': 'cross_domain'
            })
        
        # Simulate temporal correlation (Mythos memory capability)
        if hash(str(datetime.utcnow().minute)) % 7 == 0:
            threats.append({
                'source_ip': f'10.1.{hash(str(datetime.utcnow().hour)) % 256}.{hash(str(datetime.utcnow().minute)) % 256}',
                'event_type': 'temporal_pattern',
                'details': 'repeated probes over weeks with escalating privilege attempts',
                'severity': 'high',
                'simulated': True,
                'mythos_capability': 'temporal_correlation'
            })
        
        return threats
    
    def _simulate_system_monitoring(self) -> List[Dict]:
        """Simulate system monitoring."""
        threats = []
        
        # Simulate various system threats
        threat_types = [
            ('probing', 'Port scanning detected from suspicious IP', 'medium'),
            ('enumeration', 'Directory enumeration attempt', 'high'),
            ('brute_force', 'SSH brute force attack', 'high'),
            ('data_exfiltration', 'Large outbound data transfer to unknown destination', 'critical'),
            ('ddos', 'DDoS attack patterns detected', 'critical'),
            ('malware', 'Malware signature detected in downloaded file', 'high'),
            ('unauthorized_access', 'Unauthorized access attempt to admin panel', 'high'),
            ('anomalous_behavior', 'Anomalous user behavior detected', 'medium')
        ]
        
        for threat_type, description, severity in threat_types:
            if hash(f"{threat_type}{datetime.utcnow().minute}") % 10 == 0:
                threats.append({
                    'source_ip': f'203.0.{hash(threat_type) % 256}.{hash(str(datetime.utcnow().minute)) % 256}',
                    'event_type': threat_type,
                    'details': description,
                    'severity': severity,
                    'simulated': True,
                    'mythos_capability': 'general_threat'
                })
        
        return threats
    
    def _process_threat(self, threat_data: Dict):
        """Process a detected threat using enhanced protocol."""
        try:
            # Analyze with enhanced protocol
            analysis = self.protocol.analyze_event(threat_data)
            
            # Create enhanced threat event
            threat_event = EnhancedThreatEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow().isoformat() + 'Z',
                source_ip=threat_data.get('source_ip', 'unknown'),
                threat_type=ThreatType(threat_data.get('event_type', 'anomalous_behavior')),
                details=threat_data,
                patterns_detected=analysis['pattern_details'],
                threat_assessment=analysis['threat_assessment'],
                confidence=analysis['threat_assessment']['confidence'],
                severity=ThreatSeverity(analysis['threat_assessment']['threat_level']),
                response_action=ResponseAction(analysis['threat_assessment']['action']),
                mythos_capability_countered=threat_data.get('mythos_capability', 'general_threat')
            )
            
            # Update statistics
            self.stats['threats_detected'] += 1
            if threat_data.get('mythos_capability') != 'general_threat':
                self.stats['mythos_threats'] += 1
            
            # Log the threat
            log_level = logging.WARNING if threat_event.severity in [ThreatSeverity.HIGH, ThreatSeverity.CRITICAL] else logging.INFO
            log.log(log_level, 
                   f"Threat detected: {threat_event.threat_type.value} "
                   f"from {threat_event.source_ip} "
                   f"(severity: {threat_event.severity.value}, "
                   f"confidence: {threat_event.confidence:.2f})")
            
            # Send alert if needed
            if threat_event.severity in [ThreatSeverity.MEDIUM, ThreatSeverity.HIGH, ThreatSeverity.CRITICAL]:
                self._send_alert(threat_event)
                self.stats['alerts_sent'] += 1
            
            # Execute response if needed
            if threat_event.response_action != ResponseAction.LOG_ONLY:
                self._execute_response(threat_event)
                self.stats['responses_executed'] += 1
            
            # Store in SIMP outbox
            self._store_threat_event(threat_event)
            
        except Exception as e:
            log.error(f"Error processing threat: {e}")
    
    def _send_alert(self, threat_event: EnhancedThreatEvent):
        """Send alert to SIMP broker."""
        try:
            intent = SecurityIntent(
                intent_id=str(uuid.uuid4()),
                intent_type="security_alert",
                payload={
                    "threat_event": threat_event.to_dict(),
                    "agent_id": AGENT_ID,
                    "timestamp": datetime.utcnow().isoformat() + 'Z',
                    "description": f"Threat detected: {threat_event.threat_type.value} "
                                 f"from {threat_event.source_ip} "
                                 f"(Mythos capability countered: {threat_event.mythos_capability_countered})"
                }
            )
            
            # Store in outbox for SIMP to pick up
            outbox_file = OUTBOX_DIR / f"alert_{threat_event.event_id}.json"
            with open(outbox_file, 'w') as f:
                json.dump(intent.to_dict(), f, indent=2)
            
            log.info(f"Alert sent: {threat_event.threat_type.value} from {threat_event.source_ip}")
            
        except Exception as e:
            log.error(f"Error sending alert: {e}")
    
    def _execute_response(self, threat_event: EnhancedThreatEvent):
        """Execute response action based on threat assessment."""
        try:
            action = threat_event.response_action
            
            if action == ResponseAction.ALERT_ONLY:
                log.info(f"Alert only for {threat_event.source_ip} - {threat_event.threat_type.value}")
            
            elif action == ResponseAction.RATE_LIMIT_ALERT:
                log.warning(f"Rate limiting {threat_event.source_ip} - {threat_event.threat_type.value}")
                # In production: implement actual rate limiting
            
            elif action == ResponseAction.BLOCK_IP:
                log.warning(f"Blocking IP {threat_event.source_ip} - {threat_event.threat_type.value}")
                # In production: implement actual IP blocking
            
            elif action == ResponseAction.ISOLATE_SYSTEM:
                log.critical(f"Isolating system due to {threat_event.threat_type.value} from {threat_event.source_ip}")
                # In production: implement system isolation
            
        except Exception as e:
            log.error(f"Error executing response: {e}")
    
    def _store_threat_event(self, threat_event: EnhancedThreatEvent):
        """Store threat event in SIMP outbox."""
        try:
            outbox_file = OUTBOX_DIR / f"threat_{threat_event.event_id}.json"
            with open(outbox_file, 'w') as f:
                json.dump(threat_event.to_dict(), f, indent=2)
        except Exception as e:
            log.error(f"Error storing threat event: {e}")
    
    def _check_critical_threats(self):
        """Check for critical threats that need immediate attention."""
        try:
            # Check protocol memory for recent critical threats
            conn = sqlite3.connect(THREAT_DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM threat_events 
                WHERE severity = ? 
                AND timestamp >= datetime('now', '-1 hour')
            ''', ('critical',))
            
            critical_count = cursor.fetchone()[0]
            conn.close()
            
            if critical_count > 0:
                log.warning(f"Critical threats detected in last hour: {critical_count}")
                
                # Send critical alert
                intent = SecurityIntent(
                    intent_id=str(uuid.uuid4()),
                    intent_type="security_critical_alert",
                    payload={
                        "critical_threat_count": critical_count,
                        "agent_id": AGENT_ID,
                        "timestamp": datetime.utcnow().isoformat() + 'Z',
                        "message": f"{critical_count} critical threats detected in last hour"
                    }
                )
                
                outbox_file = OUTBOX_DIR / f"critical_alert_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                with open(outbox_file, 'w') as f:
                    json.dump(intent.to_dict(), f, indent=2)
                    
        except Exception as e:
            log.error(f"Error checking critical threats: {e}")
    
    def _send_status_update(self):
        """Send periodic status update to SIMP."""
        try:
            # Get system status from protocol
            status = self.protocol.get_system_status()
            
            # Combine with agent statistics
            status.update({
                'agent_id': AGENT_ID,
                'agent_version': AGENT_VERSION,
                'agent_stats': self.stats,
                'uptime': str(datetime.utcnow() - datetime.fromisoformat(self.stats['start_time'].replace('Z', '+00:00'))),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            
            intent = SecurityIntent(
                intent_id=str(uuid.uuid4()),
                intent_type="agent_status",
                payload=status
            )
            
            outbox_file = OUTBOX_DIR / f"status_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
            with open(outbox_file, 'w') as f:
                json.dump(intent.to_dict(), f, indent=2)
                
        except Exception as e:
            log.error(f"Error sending status update: {e}")
    
    def _process_simp_intents(self):
        """Process intents from SIMP broker."""
        try:
            # Check inbox for new intents
            for inbox_file in INBOX_DIR.glob("*.json"):
                try:
                    with open(inbox_file, 'r') as f:
                        intent_data = json.load(f)
                    
                    # Process the intent
                    self._handle_intent(intent_data)
                    
                    # Move to processed directory
                    processed_dir = INBOX_DIR / "processed"
                    processed_dir.mkdir(exist_ok=True)
                    inbox_file.rename(processed_dir / inbox_file.name)
                    
                except Exception as e:
                    log.error(f"Error processing intent file {inbox_file}: {e}")
                    # Move to error directory
                    error_dir = INBOX_DIR / "error"
                    error_dir.mkdir(exist_ok=True)
                    inbox_file.rename(error_dir / inbox_file.name)
                    
        except Exception as e:
            log.error(f"Error processing SIMP intents: {e}")
    
    def _handle_intent(self, intent_data: Dict):
        """Handle an intent from SIMP broker."""
        intent_type = intent_data.get('intent_type', '')
        
        if intent_type == 'security_query':
            self._handle_security_query(intent_data)
        elif intent_type == 'threat_analysis_request':
            self._handle_threat_analysis(intent_data)
        elif intent_type == 'system_status_request':
            self._handle_status_request(intent_data)
        else:
            log.warning(f"Unknown intent type: {intent_type}")
    
    def _handle_security_query(self, intent_data: Dict):
        """Handle security query intent."""
        try:
            query = intent_data.get('payload', {}).get('query', '')
            source_ip = intent_data.get('payload', {}).get('source_ip', '')
            
            # Analyze with enhanced protocol
            analysis = self.protocol.analyze_event({
                'source_ip': source_ip,
                'event_type': 'security_query',
                'details': query,
                'severity': 'medium'
            })
            
            # Send response
            response_intent = SecurityIntent(
                intent_id=str(uuid.uuid4()),
                intent_type="security_query_response",
                payload={
                    "original_intent_id": intent_data.get('intent_id', ''),
                    "analysis": analysis,
                    "timestamp": datetime.utcnow().isoformat() + 'Z'
                }
            )
            
            outbox_file = OUTBOX_DIR / f"query_response_{intent_data.get('intent_id', 'unknown')}.json"
            with open(outbox_file, 'w') as f:
                json.dump(response_intent.to_dict(), f, indent=2)
                
            log.info(f"Processed security query for IP: {source_ip}")
            
        except Exception as e:
            log.error(f"Error handling security query: {e}")
    
    def _handle_threat_analysis(self, intent_data: Dict):
        """Handle threat analysis request."""
        try:
            threat_data = intent_data.get('payload', {}).get('threat_data', {})
            
            # Analyze with enhanced protocol
            analysis = self.protocol.analyze_event(threat_data)
            
            # Send response
            response_intent = SecurityIntent(
                intent_id=str(uuid.uuid4()),
                intent_type="threat_analysis_response",
                payload={
                    "original_intent_id": intent_data.get('intent_id', ''),
                    "analysis": analysis,
                    "recommendations": self._generate_recommendations(analysis),
                    "timestamp": datetime.utcnow().isoformat() + 'Z'
                }
            )
            
            outbox_file = OUTBOX_DIR / f"analysis_response_{intent_data.get('intent_id', 'unknown')}.json"
            with open(outbox_file, 'w') as f:
                json.dump(response_intent.to_dict(), f, indent=2)
                
            log.info(f"Processed threat analysis request")
            
        except Exception as e:
            log.error(f"Error handling threat analysis: {e}")
    
    def _handle_status_request(self, intent_data: Dict):
        """Handle status request."""
        try:
            status = self.protocol.get_system_status()
            status.update({
                'agent_id': AGENT_ID,
                'agent_version': AGENT_VERSION,
                'agent_stats': self.stats,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            
            response_intent = SecurityIntent(
                intent_id=str(uuid.uuid4()),
                intent_type="system_status_response",
                payload=status
            )
            
            outbox_file = OUTBOX_DIR / f"status_response_{intent_data.get('intent_id', 'unknown')}.json"
            with open(outbox_file, 'w') as f:
                json.dump(response_intent.to_dict(), f, indent=2)
                
            log.info(f"Processed status request")
            
        except Exception as e:
            log.error(f"Error handling status request: {e}")
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate security recommendations based on analysis."""
        recommendations = []
        
        threat_level = analysis['threat_assessment']['threat_level']
        patterns = analysis['pattern_details']
        
        if threat_level in ['high', 'critical']:
            recommendations.append("Immediate investigation required")
            
            if any(p['type'] == 'zero_day_probing' for p in patterns):
                recommendations.append("Zero-day probing detected - review system patches and monitoring")
            
            if any(p['type'] == 'autonomous_chain' for p in patterns):
                recommendations.append("Autonomous attack chain detected - implement behavior-based detection")
            
            if any(p['type'] == 'cross_domain' for p in patterns):
                recommendations.append("Cross-domain attack detected - review access controls and segmentation")
        
        if analysis['historical_context']['event_count'] > 0:
            recommendations.append(f"Historical context available: {analysis['historical_context']['event_count']} previous events")
        
        if analysis.get('temporal_correlations'):
            recommendations.append(f"Temporal correlations found: {len(analysis['temporal_correlations'])} patterns")
        
        return recommendations
    
    def _update_statistics(self):
        """Update and log statistics."""
        # Log statistics every 60 seconds
        current_time = datetime.utcnow()
        start_time = datetime.fromisoformat(self.stats['start_time'].replace('Z', '+00:00'))
        uptime_seconds = (current_time - start_time).total_seconds()
        
        if uptime_seconds % 60 < self.poll_interval:  # Roughly every 60 seconds
            log.info(
                f"Statistics - Threats: {self.stats['threats_detected']} "
                f"(Mythos: {self.stats['mythos_threats']}), "
                f"Alerts: {self.stats['alerts_sent']}, "
                f"Responses: {self.stats['responses_executed']}, "
                f"Uptime: {uptime_seconds:.0f}s"
            )
    
    def _ensure_dirs(self):
        """Ensure required directories exist."""
        for dir_path in [INBOX_DIR, OUTBOX_DIR, LOGS_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _shutdown(self):
        """Shutdown the agent cleanly."""
        log.info("Enhanced Bill Russel Agent shutting down...")
        
        # Wait for threads to finish
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        if self.alert_thread:
            self.alert_thread.join(timeout=5.0)
        
        # Send final status update
        try:
            self._send_status_update()
        except:
            pass
        
        log.info("Enhanced Bill Russel Agent shutdown complete")


# ---------------------------------------------------------------------------
# Registration with SIMP
# ---------------------------------------------------------------------------

def register_with_simp(
    simp_url: str = "http://127.0.0.1:5555",
    api_key: Optional[str] = None,
) -> bool:
    """Register enhanced bill_russel with the SIMP broker."""
    payload = {
        "agent_id": AGENT_ID,
        "agent_type": "security_enhanced",
        "endpoint": f"file://{INBOX_DIR}",
        "metadata": {
            "capabilities": [
                "mythos_threat_detection",
                "pattern_recognition_at_depth",
                "autonomous_reasoning_chains",
                "memory_across_time",
                "cyber_capability_detection",
                "cross_domain_synthesis",
                "zero_day_probing_detection",
                "temporal_correlation",
                "security_audit",
                "threat_analysis",
                "autonomous_response"
            ],
            "description": AGENT_DESCRIPTION.strip(),
            "version": AGENT_VERSION,
            "dry_run_safe": True,
            "trade_execution": False,
            "inbox_path": str(INBOX_DIR),
            "outbox_path": str(OUTBOX_DIR),
            "requires_authentication": True,
            "security_level": "maximum",
            "mythos_counter_capabilities": [
                "Pattern Recognition at Depth (counter Mythos capability)",
                "Autonomous Reasoning Chains (counter Mythos reasoning)",
                "Memory Across Time (counter Mythos memory)",
                "Cyber Capability Detection (counter Mythos zero-day)",
                "Cross-domain Synthesis Detection (counter Mythos synthesis)"
            ]
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
            log.info(f"Registered enhanced bill_russel with SIMP: {body}")
            return True
    except urllib.error.URLError as e:
        log.warning(f"Could not register with SIMP: {e}")
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Main entry point for Enhanced Bill Russel Agent."""
    parser = argparse.ArgumentParser(
        description="Enhanced Bill Russel Protocol Agent - Defensive system against Mythos-level threats"
    )
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
        default=3.0,
        help="Poll interval in seconds (default: 3.0)"
    )
    parser.add_argument(
        "--demo-mode",
        action="store_true",
        help="Run in demo mode with simulated threats"
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
    agent = EnhancedBillRusselAgent(
        poll_interval=args.poll_interval,
        simp_url=args.simp_url
    )
    
    if args.demo_mode:
        log.info("Running in DEMO MODE - Simulating Mythos-level threats")
        log.info("Mythos capabilities being countered:")
        log.info("  • Pattern Recognition at Depth")
        log.info("  • Autonomous Reasoning Chains")
        log.info("  • Memory Across Time")
        log.info("  • Cyber Capability Detection")
        log.info("  • Cross-domain Synthesis")
    
    agent.run()


if __name__ == "__main__":
    main()