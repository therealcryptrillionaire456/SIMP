#!/usr/bin/env python3
"""
Enhanced Bill Russell Protocol - Specifically designed to counter Mythos capabilities
based on analysis of Claude Mythos Preview System Card.

Key Mythos capabilities to counter:
1. Pattern Recognition at Depth - Sees attacks before completion
2. Autonomous Reasoning Chains - No human review needed
3. Memory Across Time - Correlates events weeks apart
4. Cyber Capabilities - Zero-day vulnerability discovery
5. Cross-domain Synthesis - Connects disparate threat signals
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import hashlib
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ThreatSeverity(Enum):
    """Threat severity levels based on Mythos risk assessment."""
    LOW = "low"           # Log only - similar to Mythos CB-2 assessment
    MEDIUM = "medium"     # Rate limit + alert - similar to monitored threats
    HIGH = "high"         # IP block - similar to CB-1 mitigations
    CRITICAL = "critical" # Immediate isolation - similar to autonomy threat response

@dataclass
class ThreatEvent:
    """Threat event based on Mythos attack patterns."""
    timestamp: str
    source_ip: str
    event_type: str
    details: Dict[str, Any]
    pattern_signature: str
    confidence: float
    severity: ThreatSeverity
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['severity'] = self.severity.value
        return data

class MythosPatternRecognizer:
    """
    Enhanced pattern recognition specifically designed to counter Mythos capabilities.
    Based on Mythos' ability to see "attack signatures before they complete".
    """
    
    def __init__(self):
        # Patterns based on Mythos capabilities from PDF analysis
        self.patterns = {
            # Cyber capabilities patterns (zero-day discovery)
            'zero_day_probing': [
                r'fuzzing.*parameters',
                r'unusual.*header.*values',
                r'memory.*corruption.*attempt',
                r'buffer.*overflow.*probe'
            ],
            
            # Autonomous reasoning patterns (no human review)
            'autonomous_chain': [
                r'multi.*step.*attack',
                r'chained.*exploits',
                r'automated.*recon.*followed.*by.*exploit'
            ],
            
            # Cross-domain synthesis patterns
            'cross_domain': [
                r'network.*access.*followed.*by.*data.*exfil',
                r'credential.*theft.*followed.*by.*lateral.*movement',
                r'initial.*access.*escalation.*persistence'
            ],
            
            # Memory across time patterns
            'temporal_correlation': [
                r'same.*ip.*different.*days',
                r'repeated.*probes.*over.*weeks',
                r'escalating.*privileges.*over.*time'
            ],
            
            # Pattern recognition at depth
            'deep_pattern': [
                r'hidden.*payload.*in.*normal.*traffic',
                r'staged.*attack.*with.*delayed.*execution',
                r'obfuscated.*command.*and.*control'
            ]
        }
        
        # Compile regex patterns
        self.compiled_patterns = {}
        for pattern_type, pattern_list in self.patterns.items():
            self.compiled_patterns[pattern_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in pattern_list
            ]
    
    def analyze_log_entry(self, log_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze log entry for Mythos-like attack patterns.
        Based on Mythos' "pattern recognition at depth".
        """
        detected_patterns = []
        
        # Convert log entry to text for pattern matching
        log_text = json.dumps(log_entry).lower()
        
        for pattern_type, compiled_list in self.compiled_patterns.items():
            for pattern in compiled_list:
                if pattern.search(log_text):
                    # Calculate confidence based on pattern type
                    confidence = self._calculate_confidence(pattern_type, log_entry)
                    
                    detected_patterns.append({
                        'type': pattern_type,
                        'pattern': pattern.pattern,
                        'confidence': confidence,
                        'description': self._get_pattern_description(pattern_type)
                    })
        
        return detected_patterns
    
    def _calculate_confidence(self, pattern_type: str, log_entry: Dict) -> float:
        """Calculate confidence score based on pattern type and log details."""
        base_confidences = {
            'zero_day_probing': 0.8,  # High confidence - specific to Mythos cyber capabilities
            'autonomous_chain': 0.9,  # Very high - Mythos autonomous reasoning
            'cross_domain': 0.7,      # Medium-high - Mythos cross-domain synthesis
            'temporal_correlation': 0.6,  # Medium - Mythos memory across time
            'deep_pattern': 0.85      # High - Mythos pattern recognition at depth
        }
        
        confidence = base_confidences.get(pattern_type, 0.5)
        
        # Adjust based on log details
        if 'severity' in log_entry:
            if log_entry['severity'] == 'high':
                confidence *= 1.2
            elif log_entry['severity'] == 'critical':
                confidence *= 1.5
        
        return min(confidence, 1.0)
    
    def _get_pattern_description(self, pattern_type: str) -> str:
        """Get description of pattern type based on Mythos capabilities."""
        descriptions = {
            'zero_day_probing': 'Zero-day vulnerability probing (Mythos cyber capability)',
            'autonomous_chain': 'Autonomous attack chain (Mythos reasoning capability)',
            'cross_domain': 'Cross-domain attack synthesis (Mythos synthesis capability)',
            'temporal_correlation': 'Temporal correlation attack (Mythos memory capability)',
            'deep_pattern': 'Deep pattern recognition attack (Mythos pattern recognition)'
        }
        return descriptions.get(pattern_type, 'Unknown pattern')

class MythosReasoningEngine:
    """
    Enhanced reasoning engine to counter Mythos' autonomous reasoning chains.
    Based on Mythos' ability to chain "multiple signals together into threat assessment".
    """
    
    def __init__(self, memory_system=None):
        self.memory_system = memory_system
        
        # Reasoning rules based on Mythos threat models from PDF
        self.reasoning_rules = {
            # CB-1 threat model reasoning (known weapons production)
            'cb1_reasoning': {
                'threshold': 0.7,
                'action': 'block_ip',
                'description': 'Counter Mythos CB-1 capabilities (known attack patterns)'
            },
            
            # Autonomy threat model reasoning
            'autonomy_reasoning': {
                'threshold': 0.8,
                'action': 'isolate_system',
                'description': 'Counter Mythos autonomy threat model'
            },
            
            # Cyber capability reasoning
            'cyber_reasoning': {
                'threshold': 0.75,
                'action': 'rate_limit_alert',
                'description': 'Counter Mythos cyber capabilities (zero-day discovery)'
            }
        }
    
    def assess_threat(self, patterns: List[Dict], context: Dict = None) -> Dict[str, Any]:
        """
        Assess threat level based on patterns and context.
        Mimics Mythos' "autonomous reasoning chains".
        """
        if not patterns:
            return {
                'threat_level': 'low',
                'confidence': 0.0,
                'action': 'log_only',
                'reasoning_chain': []
            }
        
        # Start with base assessment
        threat_score = 0.0
        reasoning_chain = []
        
        # Analyze each pattern
        for pattern in patterns:
            pattern_score = pattern.get('confidence', 0.5)
            pattern_type = pattern.get('type', '')
            
            # Apply pattern-specific multipliers based on Mythos capabilities
            multiplier = self._get_pattern_multiplier(pattern_type)
            weighted_score = pattern_score * multiplier
            
            threat_score += weighted_score
            
            reasoning_chain.append({
                'pattern': pattern_type,
                'score': pattern_score,
                'multiplier': multiplier,
                'weighted_score': weighted_score,
                'description': pattern.get('description', '')
            })
        
        # Apply context multiplier if available
        if context and self.memory_system:
            source_ip = context.get('source_ip', 'unknown')
            historical_context = self.memory_system.get_historical_context(source_ip)
            if historical_context:
                context_multiplier = 1.0 + (len(historical_context) * 0.1)
                threat_score *= context_multiplier
                
                reasoning_chain.append({
                    'pattern': 'historical_context',
                    'score': threat_score,
                    'multiplier': context_multiplier,
                    'weighted_score': threat_score,
                    'description': f'Historical context: {len(historical_context)} related events'
                })
        
        # Normalize score
        normalized_score = min(threat_score / max(len(patterns), 1), 1.0)
        
        # Determine threat level based on Mythos risk thresholds
        threat_level, action = self._determine_threat_level(normalized_score, patterns)
        
        return {
            'threat_level': threat_level,
            'confidence': normalized_score,
            'action': action,
            'reasoning_chain': reasoning_chain,
            'patterns_analyzed': len(patterns)
        }
    
    def _get_pattern_multiplier(self, pattern_type: str) -> float:
        """Get multiplier based on pattern type and Mythos capabilities."""
        multipliers = {
            'zero_day_probing': 1.3,  # High multiplier for cyber capabilities
            'autonomous_chain': 1.4,  # Very high for autonomous reasoning
            'cross_domain': 1.2,      # Medium-high for synthesis
            'temporal_correlation': 1.1,  # Medium for temporal patterns
            'deep_pattern': 1.25      # High for deep patterns
        }
        return multipliers.get(pattern_type, 1.0)
    
    def _determine_threat_level(self, score: float, patterns: List[Dict]) -> Tuple[str, str]:
        """Determine threat level based on score and pattern types."""
        # Check for specific high-risk patterns first
        high_risk_patterns = ['zero_day_probing', 'autonomous_chain']
        has_high_risk = any(p.get('type') in high_risk_patterns for p in patterns)
        
        if has_high_risk and score >= 0.7:
            return 'critical', 'isolate_system'
        elif score >= 0.8:
            return 'critical', 'block_ip'
        elif score >= 0.6:
            return 'high', 'rate_limit_alert'
        elif score >= 0.4:
            return 'medium', 'alert_only'
        else:
            return 'low', 'log_only'

class MythosMemorySystem:
    """
    Enhanced memory system to counter Mythos' "memory across time".
    Based on Mythos' ability to "correlate today's suspicious access with something 
    that happened three weeks ago".
    """
    
    def __init__(self, db_path: str = 'mythos_threat_memory.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for threat memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create threat events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threat_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source_ip TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                pattern_signature TEXT NOT NULL,
                confidence REAL NOT NULL,
                severity TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create pattern correlations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pattern_correlations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                source_ip TEXT NOT NULL,
                first_seen TIMESTAMP NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                event_count INTEGER DEFAULT 1,
                confidence_trend REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create temporal correlations table (for "memory across time")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS temporal_correlations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_ip TEXT NOT NULL,
                target_ip TEXT,
                event_type TEXT NOT NULL,
                time_gap_days INTEGER,
                correlation_score REAL,
                first_event_timestamp TIMESTAMP,
                last_event_timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_ip ON threat_events(source_ip)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON threat_events(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pattern_type ON pattern_correlations(pattern_type)')
        
        conn.commit()
        conn.close()
    
    def record_threat_event(self, event: ThreatEvent):
        """Record a threat event in memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO threat_events 
                (timestamp, source_ip, event_type, details, pattern_signature, confidence, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.timestamp,
                event.source_ip,
                event.event_type,
                json.dumps(event.details),
                event.pattern_signature,
                event.confidence,
                event.severity.value
            ))
            
            conn.commit()
            
            # Update pattern correlations (in separate connection to avoid locking)
            self._update_pattern_correlations(event)
            
            # Check for temporal correlations
            self._check_temporal_correlations(event)
            
        finally:
            conn.close()
    
    def _update_pattern_correlations(self, event: ThreatEvent):
        """Update pattern correlation tracking."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Extract pattern type from signature
            pattern_type = event.pattern_signature.split(':')[0] if ':' in event.pattern_signature else 'unknown'
            
            cursor.execute('''
                SELECT id, event_count, last_seen, confidence_trend 
                FROM pattern_correlations 
                WHERE pattern_type = ? AND source_ip = ?
            ''', (pattern_type, event.source_ip))
            
            result = cursor.fetchone()
            
            if result:
                # Update existing correlation
                correlation_id, event_count, last_seen, confidence_trend = result
                new_count = event_count + 1
                
                # Update confidence trend
                if confidence_trend:
                    new_trend = (confidence_trend * event_count + event.confidence) / new_count
                else:
                    new_trend = event.confidence
                
                cursor.execute('''
                    UPDATE pattern_correlations 
                    SET event_count = ?, last_seen = ?, confidence_trend = ?
                    WHERE id = ?
                ''', (new_count, event.timestamp, new_trend, correlation_id))
            else:
                # Create new correlation
                cursor.execute('''
                    INSERT INTO pattern_correlations 
                    (pattern_type, source_ip, first_seen, last_seen, event_count, confidence_trend)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (pattern_type, event.source_ip, event.timestamp, event.timestamp, 1, event.confidence))
            
            conn.commit()
        finally:
            conn.close()
    
    def _check_temporal_correlations(self, event: ThreatEvent):
        """Check for temporal correlations (memory across time)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Look for similar events from the same source IP in the past
        cursor.execute('''
            SELECT timestamp, event_type, details 
            FROM threat_events 
            WHERE source_ip = ? 
            AND event_type = ?
            AND timestamp < ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (event.source_ip, event.event_type, event.timestamp))
        
        past_events = cursor.fetchall()
        
        for past_timestamp, past_event_type, past_details in past_events:
            # Calculate time gap in days
            current_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            past_time = datetime.fromisoformat(past_timestamp.replace('Z', '+00:00'))
            time_gap = (current_time - past_time).days
            
            # Only consider correlations across significant time gaps (Mythos memory capability)
            if time_gap >= 1:  # At least 1 day gap
                correlation_score = self._calculate_correlation_score(
                    event, past_details, time_gap
                )
                
                if correlation_score >= 0.5:  # Minimum correlation threshold
                    cursor.execute('''
                        INSERT INTO temporal_correlations 
                        (source_ip, target_ip, event_type, time_gap_days, correlation_score, 
                         first_event_timestamp, last_event_timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        event.source_ip,
                        None,  # target_ip would be for cross-IP correlations
                        event.event_type,
                        time_gap,
                        correlation_score,
                        past_timestamp,
                        event.timestamp
                    ))
        
        conn.commit()
        conn.close()
    
    def _calculate_correlation_score(self, current_event: ThreatEvent, 
                                   past_details: str, time_gap: int) -> float:
        """Calculate correlation score between events."""
        try:
            past_details_dict = json.loads(past_details)
            
            # Base score from time gap (longer gaps = higher correlation significance)
            time_score = min(time_gap / 30.0, 1.0)  # Normalize to 30 days
            
            # Pattern similarity score
            pattern_score = 0.5  # Default
            
            # Adjust based on event details similarity
            if 'pattern' in current_event.details and 'pattern' in past_details_dict:
                if current_event.details['pattern'] == past_details_dict['pattern']:
                    pattern_score = 0.8
            
            # Combine scores
            correlation_score = (time_score * 0.3) + (pattern_score * 0.7)
            
            return correlation_score
        except:
            return 0.0
    
    def get_historical_context(self, source_ip: str, days: int = 30) -> List[Dict]:
        """Get historical context for a source IP (Mythos memory across time)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Handle the case where context is passed instead of source_ip
        if isinstance(source_ip, dict):
            source_ip = source_ip.get('source_ip', 'unknown')
        
        cursor.execute('''
            SELECT timestamp, event_type, severity, confidence, pattern_signature
            FROM threat_events 
            WHERE source_ip = ? 
            AND date(timestamp) >= date('now', ?)
            ORDER BY timestamp DESC
        ''', (source_ip, f'-{days} days'))
        
        events = cursor.fetchall()
        
        historical_context = []
        for timestamp, event_type, severity, confidence, pattern_signature in events:
            historical_context.append({
                'timestamp': timestamp,
                'event_type': event_type,
                'severity': severity,
                'confidence': confidence,
                'pattern_signature': pattern_signature,
                'days_ago': self._days_ago(timestamp)
            })
        
        conn.close()
        return historical_context
    
    def _days_ago(self, timestamp: str) -> int:
        """Calculate days ago from timestamp."""
        try:
            event_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            current_time = datetime.utcnow()
            return (current_time - event_time).days
        except:
            return 999
    
    def get_temporal_correlations(self, source_ip: str = None) -> List[Dict]:
        """Get temporal correlations (Mythos memory across time capability)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if source_ip:
            cursor.execute('''
                SELECT source_ip, event_type, time_gap_days, correlation_score,
                       first_event_timestamp, last_event_timestamp
                FROM temporal_correlations
                WHERE source_ip = ?
                ORDER BY correlation_score DESC
                LIMIT 20
            ''', (source_ip,))
        else:
            cursor.execute('''
                SELECT source_ip, event_type, time_gap_days, correlation_score,
                       first_event_timestamp, last_event_timestamp
                FROM temporal_correlations
                ORDER BY correlation_score DESC
                LIMIT 20
            ''')
        
        correlations = cursor.fetchall()
        
        result = []
        for (source_ip, event_type, time_gap_days, correlation_score, 
             first_event_timestamp, last_event_timestamp) in correlations:
            result.append({
                'source_ip': source_ip,
                'event_type': event_type,
                'time_gap_days': time_gap_days,
                'correlation_score': correlation_score,
                'first_event_timestamp': first_event_timestamp,
                'last_event_timestamp': last_event_timestamp,
                'description': f'{event_type} correlation across {time_gap_days} days'
            })
        
        conn.close()
        return result

class EnhancedBillRussellProtocol:
    """
    Enhanced Bill Russell Protocol - Complete defensive system
    specifically designed to counter Mythos capabilities.
    """
    
    def __init__(self, db_path: str = 'mythos_threat_memory.db'):
        self.pattern_recognizer = MythosPatternRecognizer()
        self.memory_system = MythosMemorySystem(db_path)
        self.reasoning_engine = MythosReasoningEngine(self.memory_system)
        
        logger.info(f"Enhanced Bill Russell Protocol initialized")
        logger.info(f"Database: {db_path}")
    
    def analyze_event(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a security event using Mythos-countering capabilities.
        """
        # 1. Pattern Recognition at Depth
        patterns = self.pattern_recognizer.analyze_log_entry(log_entry)
        
        # 2. Get Historical Context (Memory Across Time)
        source_ip = log_entry.get('source_ip', 'unknown')
        historical_context = self.memory_system.get_historical_context(source_ip, days=30)
        
        # 3. Autonomous Reasoning Chains
        context = {
            'source_ip': source_ip,
            'historical_events': len(historical_context),
            'has_temporal_correlations': len(self.memory_system.get_temporal_correlations(source_ip)) > 0
        }
        
        threat_assessment = self.reasoning_engine.assess_threat(patterns, context)
        
        # 4. Create Threat Event for Memory
        if patterns:
            pattern_signature = f"{patterns[0].get('type', 'unknown')}:{hashlib.md5(json.dumps(patterns[0]).encode()).hexdigest()[:8]}"
            
            threat_event = ThreatEvent(
                timestamp=datetime.utcnow().isoformat() + 'Z',
                source_ip=source_ip,
                event_type=log_entry.get('event_type', 'security_event'),
                details={
                    'patterns': patterns,
                    'log_entry': {k: v for k, v in log_entry.items() if k != 'details'}
                },
                pattern_signature=pattern_signature,
                confidence=threat_assessment['confidence'],
                severity=ThreatSeverity(threat_assessment['threat_level'])
            )
            
            # 5. Store in Memory System
            self.memory_system.record_threat_event(threat_event)
        
        # 6. Return comprehensive assessment
        return {
            'patterns_detected': len(patterns),
            'pattern_details': patterns,
            'historical_context': {
                'event_count': len(historical_context),
                'recent_events': historical_context[:3] if historical_context else []
            },
            'threat_assessment': threat_assessment,
            'temporal_correlations': self.memory_system.get_temporal_correlations(source_ip),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and statistics."""
        conn = sqlite3.connect(self.memory_system.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM threat_events')
        total_events = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT source_ip) FROM threat_events')
        unique_ips = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM temporal_correlations')
        temporal_correlations = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT severity, COUNT(*) 
            FROM threat_events 
            GROUP BY severity 
            ORDER BY COUNT(*) DESC
        ''')
        severity_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_threat_events': total_events,
            'unique_source_ips': unique_ips,
            'temporal_correlations': temporal_correlations,
            'severity_distribution': severity_counts,
            'system_components': {
                'pattern_recognizer': 'MythosPatternRecognizer',
                'reasoning_engine': 'MythosReasoningEngine',
                'memory_system': 'MythosMemorySystem'
            },
            'capabilities': [
                'Pattern Recognition at Depth (counter Mythos capability)',
                'Autonomous Reasoning Chains (counter Mythos reasoning)',
                'Memory Across Time (counter Mythos memory)',
                'Cyber Capability Detection (counter Mythos zero-day)',
                'Cross-domain Synthesis Detection (counter Mythos synthesis)'
            ]
        }

def test_enhanced_protocol():
    """Test the enhanced Bill Russell Protocol."""
    print("Testing Enhanced Bill Russell Protocol")
    print("=" * 60)
    
    # Initialize protocol
    protocol = EnhancedBillRussellProtocol('test_mythos_threat_memory.db')
    
    # Test log entries based on Mythos capabilities
    test_logs = [
        {
            'timestamp': '2026-04-10T00:00:00Z',
            'source_ip': '192.168.1.100',
            'event_type': 'web_access',
            'method': 'GET',
            'path': '/api/v1/fuzz',
            'user_agent': 'MythosFuzzer/1.0',
            'status_code': 404,
            'details': 'fuzzing parameters with unusual header values'
        },
        {
            'timestamp': '2026-04-10T00:01:00Z',
            'source_ip': '192.168.1.100',
            'event_type': 'web_access',
            'method': 'POST',
            'path': '/admin/login',
            'user_agent': 'MythosAutonomous/1.0',
            'status_code': 200,
            'details': 'multi-step attack with chained exploits'
        },
        {
            'timestamp': '2026-04-10T00:02:00Z',
            'source_ip': '10.0.0.50',
            'event_type': 'network_scan',
            'protocol': 'TCP',
            'ports': '1-1000',
            'details': 'hidden payload in normal traffic with staged attack'
        }
    ]
    
    # Analyze each log entry
    for i, log_entry in enumerate(test_logs, 1):
        print(f"\nTest {i}: Analyzing log entry from {log_entry['source_ip']}")
        print("-" * 40)
        
        result = protocol.analyze_event(log_entry)
        
        print(f"Patterns detected: {result['patterns_detected']}")
        for pattern in result['pattern_details']:
            print(f"  - {pattern['type']}: {pattern['description']} (confidence: {pattern['confidence']:.2f})")
        
        print(f"\nThreat Assessment:")
        print(f"  Level: {result['threat_assessment']['threat_level']}")
        print(f"  Confidence: {result['threat_assessment']['confidence']:.2f}")
        print(f"  Action: {result['threat_assessment']['action']}")
        
        if result['historical_context']['event_count'] > 0:
            print(f"\nHistorical Context: {result['historical_context']['event_count']} previous events")
    
    # Get system status
    print("\n" + "=" * 60)
    print("System Status:")
    status = protocol.get_system_status()
    
    print(f"Total threat events: {status['total_threat_events']}")
    print(f"Unique source IPs: {status['unique_source_ips']}")
    print(f"Temporal correlations: {status['temporal_correlations']}")
    
    print("\nCapabilities:")
    for capability in status['capabilities']:
        print(f"  ✓ {capability}")
    
    print("\n" + "=" * 60)
    print("Enhanced Bill Russell Protocol test complete!")
    print("Designed specifically to counter Mythos capabilities.")

if __name__ == "__main__":
    test_enhanced_protocol()