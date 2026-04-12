"""
Alert Orchestrator for Bill Russel Protocol.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .reasoning_engine import ThreatAssessment, ResponseAction

logger = logging.getLogger(__name__)


@dataclass
class AlertResponse:
    """Response from alert orchestrator."""
    action: str
    confidence: float
    details: str
    timestamp: datetime
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    alert_sent: bool = False
    response_executed: bool = False


class AlertOrchestrator:
    """Orchestrates alerts and responses based on threat assessments."""
    
    def __init__(self, telegram_enabled: bool = False):
        """
        Initialize alert orchestrator.
        
        Args:
            telegram_enabled: Whether Telegram alerts are enabled
        """
        self.telegram_enabled = telegram_enabled
        self.response_log = []
        
        # Response implementations
        self.response_handlers = {
            ResponseAction.LOG_ONLY: self._handle_log_only,
            ResponseAction.MONITOR: self._handle_monitor,
            ResponseAction.ALERT: self._handle_alert,
            ResponseAction.RATE_LIMIT: self._handle_rate_limit,
            ResponseAction.BLOCK_IP: self._handle_block_ip,
            ResponseAction.ISOLATE: self._handle_isolate
        }
        
        logger.info("AlertOrchestrator initialized")
    
    def orchestrate_response(self, threat_assessment: ThreatAssessment,
                           event_data: Dict) -> AlertResponse:
        """
        Orchestrate response based on threat assessment.
        
        Args:
            threat_assessment: Threat assessment
            event_data: Original event data
            
        Returns:
            Alert response
        """
        # Get handler for recommended action
        handler = self.response_handlers.get(
            threat_assessment.recommended_action,
            self._handle_log_only
        )
        
        # Execute response
        response = handler(threat_assessment, event_data)
        
        # Log response
        self.response_log.append({
            'timestamp': datetime.now().isoformat(),
            'assessment': threat_assessment.description,
            'action': response.action,
            'confidence': response.confidence,
            'source_ip': response.source_ip
        })
        
        # Keep only recent responses (last 1000)
        if len(self.response_log) > 1000:
            self.response_log = self.response_log[-1000:]
        
        logger.info(f"Orchestrated response: {response.action} "
                   f"(confidence: {response.confidence:.2f})")
        
        return response
    
    def _handle_log_only(self, assessment: ThreatAssessment,
                        event_data: Dict) -> AlertResponse:
        """Handle log-only response."""
        return AlertResponse(
            action="log_only",
            confidence=assessment.confidence,
            details=f"Logged threat: {assessment.description}",
            timestamp=datetime.now(),
            source_ip=assessment.source_ip,
            target_ip=assessment.target_ip,
            alert_sent=False,
            response_executed=False
        )
    
    def _handle_monitor(self, assessment: ThreatAssessment,
                       event_data: Dict) -> AlertResponse:
        """Handle monitor response."""
        # Enhanced logging and monitoring
        details = (f"Monitoring threat: {assessment.description}. "
                  f"Patterns: {len(assessment.patterns)}. "
                  f"Reasoning: {assessment.reasoning[:100]}...")
        
        return AlertResponse(
            action="monitor",
            confidence=assessment.confidence,
            details=details,
            timestamp=datetime.now(),
            source_ip=assessment.source_ip,
            target_ip=assessment.target_ip,
            alert_sent=False,
            response_executed=False
        )
    
    def _handle_alert(self, assessment: ThreatAssessment,
                     event_data: Dict) -> AlertResponse:
        """Handle alert response."""
        # Send alert via Telegram if enabled
        alert_sent = False
        if self.telegram_enabled:
            alert_sent = self._send_telegram_alert(assessment, event_data)
        
        details = (f"Alert generated: {assessment.description}. "
                  f"Threat level: {assessment.threat_level.value}. "
                  f"Alert sent: {alert_sent}")
        
        return AlertResponse(
            action="alert",
            confidence=assessment.confidence,
            details=details,
            timestamp=datetime.now(),
            source_ip=assessment.source_ip,
            target_ip=assessment.target_ip,
            alert_sent=alert_sent,
            response_executed=False
        )
    
    def _handle_rate_limit(self, assessment: ThreatAssessment,
                          event_data: Dict) -> AlertResponse:
        """Handle rate limit response."""
        # Apply rate limiting
        response_executed = self._apply_rate_limit(
            assessment.source_ip,
            assessment.confidence
        )
        
        # Send alert
        alert_sent = False
        if self.telegram_enabled:
            alert_sent = self._send_telegram_alert(assessment, event_data)
        
        details = (f"Rate limiting applied to {assessment.source_ip}. "
                  f"Threat: {assessment.description}. "
                  f"Rate limit applied: {response_executed}. "
                  f"Alert sent: {alert_sent}")
        
        return AlertResponse(
            action="rate_limit",
            confidence=assessment.confidence,
            details=details,
            timestamp=datetime.now(),
            source_ip=assessment.source_ip,
            target_ip=assessment.target_ip,
            alert_sent=alert_sent,
            response_executed=response_executed
        )
    
    def _handle_block_ip(self, assessment: ThreatAssessment,
                        event_data: Dict) -> AlertResponse:
        """Handle IP block response."""
        # Block IP
        response_executed = self._block_ip_address(
            assessment.source_ip,
            assessment.confidence
        )
        
        # Send alert
        alert_sent = False
        if self.telegram_enabled:
            alert_sent = self._send_telegram_alert(assessment, event_data)
        
        # Log full session
        session_logged = self._log_full_session(event_data)
        
        details = (f"IP {assessment.source_ip} blocked. "
                  f"Threat: {assessment.description}. "
                  f"Block applied: {response_executed}. "
                  f"Session logged: {session_logged}. "
                  f"Alert sent: {alert_sent}")
        
        return AlertResponse(
            action="block_ip",
            confidence=assessment.confidence,
            details=details,
            timestamp=datetime.now(),
            source_ip=assessment.source_ip,
            target_ip=assessment.target_ip,
            alert_sent=alert_sent,
            response_executed=response_executed
        )
    
    def _handle_isolate(self, assessment: ThreatAssessment,
                       event_data: Dict) -> AlertResponse:
        """Handle isolation response."""
        # Isolate system/network segment
        response_executed = self._isolate_system(
            assessment.source_ip,
            assessment.target_ip,
            assessment.confidence
        )
        
        # Send critical alert
        alert_sent = False
        if self.telegram_enabled:
            alert_sent = self._send_critical_alert(assessment, event_data)
        
        # Initiate incident response
        incident_id = self._initiate_incident_response(assessment, event_data)
        
        details = (f"System isolation initiated. "
                  f"Threat: {assessment.description}. "
                  f"Isolation applied: {response_executed}. "
                  f"Incident ID: {incident_id}. "
                  f"Alert sent: {alert_sent}")
        
        return AlertResponse(
            action="isolate",
            confidence=assessment.confidence,
            details=details,
            timestamp=datetime.now(),
            source_ip=assessment.source_ip,
            target_ip=assessment.target_ip,
            alert_sent=alert_sent,
            response_executed=response_executed
        )
    
    def _send_telegram_alert(self, assessment: ThreatAssessment,
                           event_data: Dict) -> bool:
        """Send Telegram alert (simulated)."""
        try:
            # Simulate Telegram API call
            message = self._format_telegram_message(assessment, event_data)
            logger.info(f"Telegram alert (simulated): {message[:100]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
    
    def _send_critical_alert(self, assessment: ThreatAssessment,
                           event_data: Dict) -> bool:
        """Send critical alert (simulated)."""
        try:
            # Simulate critical alert
            message = f"🚨 CRITICAL THREAT: {assessment.description}"
            logger.info(f"Critical alert (simulated): {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send critical alert: {e}")
            return False
    
    def _apply_rate_limit(self, source_ip: str, confidence: float) -> bool:
        """Apply rate limiting (simulated)."""
        try:
            # Simulate rate limiting
            logger.info(f"Rate limiting applied to {source_ip} "
                       f"(confidence: {confidence:.2f})")
            return True
        except Exception as e:
            logger.error(f"Failed to apply rate limit: {e}")
            return False
    
    def _block_ip_address(self, source_ip: str, confidence: float) -> bool:
        """Block IP address (simulated)."""
        try:
            # Simulate IP blocking
            logger.info(f"IP {source_ip} blocked "
                       f"(confidence: {confidence:.2f})")
            return True
        except Exception as e:
            logger.error(f"Failed to block IP: {e}")
            return False
    
    def _log_full_session(self, event_data: Dict) -> bool:
        """Log full session data (simulated)."""
        try:
            # Simulate session logging
            logger.info(f"Full session logged for event")
            return True
        except Exception as e:
            logger.error(f"Failed to log session: {e}")
            return False
    
    def _isolate_system(self, source_ip: str, target_ip: str,
                       confidence: float) -> bool:
        """Isolate system (simulated)."""
        try:
            # Simulate system isolation
            target = target_ip or source_ip
            logger.info(f"System {target} isolated "
                       f"(confidence: {confidence:.2f})")
            return True
        except Exception as e:
            logger.error(f"Failed to isolate system: {e}")
            return False
    
    def _initiate_incident_response(self, assessment: ThreatAssessment,
                                  event_data: Dict) -> str:
        """Initiate incident response (simulated)."""
        # Generate incident ID
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        logger.info(f"Incident response initiated: {incident_id} "
                   f"for threat: {assessment.description}")
        
        return incident_id
    
    def _format_telegram_message(self, assessment: ThreatAssessment,
                               event_data: Dict) -> str:
        """Format Telegram message."""
        emoji = {
            'low': 'ℹ️',
            'medium': '⚠️',
            'high': '🚨',
            'critical': '🔥'
        }.get(assessment.threat_level.value, '📝')
        
        message = (
            f"{emoji} *Threat Alert*\n"
            f"Level: {assessment.threat_level.value.upper()}\n"
            f"Confidence: {assessment.confidence:.2f}\n"
            f"Source: {assessment.source_ip or 'Unknown'}\n"
            f"Target: {assessment.target_ip or 'Unknown'}\n"
            f"Description: {assessment.description}\n"
            f"Action: {assessment.recommended_action.value.replace('_', ' ').title()}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return message
    
    def get_response_stats(self, hours: int = 24) -> Dict:
        """Get response statistics for specified period."""
        cutoff = datetime.now().timestamp() - (hours * 3600)
        
        recent_responses = [
            r for r in self.response_log
            if datetime.fromisoformat(r['timestamp']).timestamp() > cutoff
        ]
        
        stats = {
            'total_responses': len(recent_responses),
            'by_action': {},
            'by_confidence': {
                'low': 0,      # 0.0-0.3
                'medium': 0,   # 0.3-0.7
                'high': 0      # 0.7-1.0
            },
            'alerts_sent': 0,
            'responses_executed': 0
        }
        
        for response in recent_responses:
            # Count by action
            action = response['action']
            stats['by_action'][action] = stats['by_action'].get(action, 0) + 1
            
            # Count by confidence
            confidence = response['confidence']
            if confidence >= 0.7:
                stats['by_confidence']['high'] += 1
            elif confidence >= 0.3:
                stats['by_confidence']['medium'] += 1
            else:
                stats['by_confidence']['low'] += 1
            
            # Check if alert was sent
            if 'alert_sent' in response and response['alert_sent']:
                stats['alerts_sent'] += 1
            
            # Check if response was executed
            if 'response_executed' in response and response['response_executed']:
                stats['responses_executed'] += 1
        
        return stats