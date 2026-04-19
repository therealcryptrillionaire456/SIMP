"""
Autonomous Reasoning Chains - Pillar 2 of Bill Russel Protocol

Capabilities:
1. Threat assessment without human review
2. Signal chaining into unified assessment
3. Confidence-based response orchestration
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from .pattern_recognition import SecurityPattern, PatternType

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResponseAction(Enum):
    """Response actions based on threat level."""
    LOG_ONLY = "log_only"
    MONITOR = "monitor"
    ALERT = "alert"
    RATE_LIMIT = "rate_limit"
    BLOCK_IP = "block_ip"
    ISOLATE = "isolate"


@dataclass
class ThreatAssessment:
    """Complete threat assessment."""
    threat_level: ThreatLevel
    confidence: float  # 0.0 to 1.0
    description: str
    patterns: List[SecurityPattern]
    recommended_action: ResponseAction
    reasoning: str
    timestamp: datetime
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    affected_systems: List[str] = None
    
    def __post_init__(self):
        if self.affected_systems is None:
            self.affected_systems = []


class ReasoningEngine:
    """Autonomous reasoning engine for threat assessment."""
    
    def __init__(self):
        # Threat scoring weights
        self.weights = {
            PatternType.ATTACK_SIGNATURE: 0.4,
            PatternType.PROBING_BEHAVIOR: 0.2,
            PatternType.DATA_EXFILTRATION: 0.3,
            PatternType.BRUTE_FORCE: 0.25,
            PatternType.ENUMERATION: 0.15,
            PatternType.ANOMALOUS_TRAFFIC: 0.1
        }
        
        # Response thresholds
        self.thresholds = {
            ThreatLevel.LOW: 0.3,
            ThreatLevel.MEDIUM: 0.5,
            ThreatLevel.HIGH: 0.7,
            ThreatLevel.CRITICAL: 0.9
        }
        
        # Response mappings
        self.response_mappings = {
            ThreatLevel.LOW: ResponseAction.LOG_ONLY,
            ThreatLevel.MEDIUM: ResponseAction.ALERT,
            ThreatLevel.HIGH: ResponseAction.RATE_LIMIT,
            ThreatLevel.CRITICAL: ResponseAction.BLOCK_IP
        }
        
        # Historical context (simplified)
        self.historical_context = {}
        
        logger.info("ReasoningEngine initialized")
    
    def assess_threat(self, patterns: List[SecurityPattern], 
                     context: Optional[Dict] = None) -> ThreatAssessment:
        """
        Assess threat based on patterns and context.
        
        Args:
            patterns: List of detected security patterns
            context: Historical context (optional)
            
        Returns:
            Complete threat assessment
        """
        if not patterns:
            return self._create_no_threat_assessment()
        
        # Calculate base threat score
        base_score = self._calculate_threat_score(patterns)
        
        # Apply context multiplier
        context_multiplier = self._get_context_multiplier(patterns, context)
        adjusted_score = base_score * context_multiplier
        
        # Determine threat level
        threat_level = self._determine_threat_level(adjusted_score)
        
        # Chain signals into reasoning
        reasoning = self._chain_signals(patterns, context)
        
        # Get recommended action
        recommended_action = self._determine_response(threat_level, patterns)
        
        # Extract common IPs
        source_ip = self._extract_common_ip(patterns, 'source_ip')
        target_ip = self._extract_common_ip(patterns, 'target_ip')
        
        # Create assessment
        assessment = ThreatAssessment(
            threat_level=threat_level,
            confidence=adjusted_score,
            description=self._generate_description(threat_level, patterns),
            patterns=patterns,
            recommended_action=recommended_action,
            reasoning=reasoning,
            timestamp=datetime.now(),
            source_ip=source_ip,
            target_ip=target_ip,
            affected_systems=self._extract_affected_systems(patterns)
        )
        
        logger.info(f"Threat assessment complete: {threat_level.value} "
                   f"(confidence: {adjusted_score:.2f})")
        
        return assessment
    
    def _calculate_threat_score(self, patterns: List[SecurityPattern]) -> float:
        """Calculate threat score from patterns."""
        if not patterns:
            return 0.0
        
        total_score = 0.0
        max_possible = 0.0
        
        for pattern in patterns:
            # Base pattern weight
            pattern_weight = self.weights.get(pattern.pattern_type, 0.1)
            
            # Adjust by confidence
            pattern_score = pattern_weight * pattern.confidence
            
            # Apply pattern-specific adjustments
            pattern_score = self._adjust_pattern_score(pattern_score, pattern)
            
            total_score += pattern_score
            max_possible += pattern_weight
        
        # Normalize to 0-1 range
        if max_possible > 0:
            normalized_score = total_score / max_possible
        else:
            normalized_score = 0.0
        
        # Apply pattern count multiplier (more patterns = higher concern)
        pattern_count_multiplier = min(1.0 + (len(patterns) * 0.1), 1.5)
        
        return min(normalized_score * pattern_count_multiplier, 1.0)
    
    def _adjust_pattern_score(self, base_score: float, 
                            pattern: SecurityPattern) -> float:
        """Apply pattern-specific adjustments to score."""
        adjusted = base_score
        
        # Attack signatures are more serious
        if pattern.pattern_type == PatternType.ATTACK_SIGNATURE:
            adjusted *= 1.3
        
        # Data exfiltration is critical
        elif pattern.pattern_type == PatternType.DATA_EXFILTRATION:
            adjusted *= 1.5
        
        # Recent patterns are more relevant
        if pattern.timestamp:
            age_hours = (datetime.now() - pattern.timestamp).total_seconds() / 3600
            if age_hours < 1:  # Within last hour
                adjusted *= 1.2
            elif age_hours < 24:  # Within last day
                adjusted *= 1.1
        
        return min(adjusted, 1.0)
    
    def _get_context_multiplier(self, patterns: List[SecurityPattern],
                              context: Optional[Dict]) -> float:
        """Get context multiplier for threat score."""
        multiplier = 1.0
        
        if not context:
            return multiplier
        
        # Check for repeated patterns from same source
        source_ip = self._extract_common_ip(patterns, 'source_ip')
        if source_ip and source_ip in context.get('repeated_offenders', []):
            multiplier *= 1.5
        
        # Check for recent similar activity
        recent_similar = context.get('recent_similar_activity', 0)
        if recent_similar > 0:
            multiplier *= min(1.0 + (recent_similar * 0.2), 2.0)
        
        # Check time of day (simplified anomaly detection)
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:  # Off-hours
            multiplier *= 1.2
        
        return multiplier
    
    def _determine_threat_level(self, score: float) -> ThreatLevel:
        """Determine threat level based on score."""
        if score >= self.thresholds[ThreatLevel.CRITICAL]:
            return ThreatLevel.CRITICAL
        elif score >= self.thresholds[ThreatLevel.HIGH]:
            return ThreatLevel.HIGH
        elif score >= self.thresholds[ThreatLevel.MEDIUM]:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW
    
    def _chain_signals(self, patterns: List[SecurityPattern],
                      context: Optional[Dict]) -> str:
        """Chain multiple signals into coherent reasoning."""
        reasoning_parts = []
        
        # Group patterns by type
        pattern_groups = {}
        for pattern in patterns:
            pattern_type = pattern.pattern_type.value
            if pattern_type not in pattern_groups:
                pattern_groups[pattern_type] = []
            pattern_groups[pattern_type].append(pattern)
        
        # Build reasoning for each pattern group
        for pattern_type, group_patterns in pattern_groups.items():
            if group_patterns:
                count = len(group_patterns)
                avg_confidence = sum(p.confidence for p in group_patterns) / count
                
                reasoning_parts.append(
                    f"Detected {count} {pattern_type} pattern(s) "
                    f"with average confidence {avg_confidence:.2f}"
                )
        
        # Add context to reasoning
        if context:
            if context.get('repeated_offender'):
                reasoning_parts.append("Source has history of similar activity")
            
            recent_count = context.get('recent_activity_count', 0)
            if recent_count > 0:
                reasoning_parts.append(
                    f"{recent_count} similar events in recent history"
                )
        
        # Chain the reasoning
        if reasoning_parts:
            chained_reasoning = " → ".join(reasoning_parts)
            
            # Add conclusion
            total_patterns = len(patterns)
            if total_patterns > 3:
                chained_reasoning += f" → Multiple converging indicators ({total_patterns} total)"
            elif total_patterns > 1:
                chained_reasoning += f" → {total_patterns} correlated indicators"
            
            return chained_reasoning
        else:
            return "No specific patterns detected"
    
    def _determine_response(self, threat_level: ThreatLevel,
                          patterns: List[SecurityPattern]) -> ResponseAction:
        """Determine appropriate response action."""
        base_action = self.response_mappings.get(threat_level, ResponseAction.LOG_ONLY)
        
        # Adjust based on specific patterns
        for pattern in patterns:
            # Critical patterns escalate response
            if pattern.pattern_type == PatternType.ATTACK_SIGNATURE:
                if pattern.confidence > 0.8:
                    return ResponseAction.BLOCK_IP
            
            # Data exfiltration requires immediate action
            elif pattern.pattern_type == PatternType.DATA_EXFILTRATION:
                if pattern.confidence > 0.7:
                    return ResponseAction.ISOLATE
        
        return base_action
    
    def _generate_description(self, threat_level: ThreatLevel,
                            patterns: List[SecurityPattern]) -> str:
        """Generate human-readable threat description."""
        pattern_types = set(p.pattern_type.value for p in patterns)
        
        if threat_level == ThreatLevel.CRITICAL:
            return f"CRITICAL: Multiple high-confidence attack patterns detected: {', '.join(pattern_types)}"
        elif threat_level == ThreatLevel.HIGH:
            return f"HIGH: Suspicious activity with concerning patterns: {', '.join(pattern_types)}"
        elif threat_level == ThreatLevel.MEDIUM:
            return f"MEDIUM: Unusual activity detected: {', '.join(pattern_types[:3])}"
        else:
            return f"LOW: Minor anomalies detected: {', '.join(list(pattern_types)[:2])}"
    
    def _extract_common_ip(self, patterns: List[SecurityPattern],
                          ip_field: str) -> Optional[str]:
        """Extract most common IP from patterns."""
        ip_counts = {}
        for pattern in patterns:
            ip = getattr(pattern, ip_field, None)
            if ip:
                ip_counts[ip] = ip_counts.get(ip, 0) + 1
        
        if ip_counts:
            return max(ip_counts.items(), key=lambda x: x[1])[0]
        return None
    
    def _extract_affected_systems(self, patterns: List[SecurityPattern]) -> List[str]:
        """Extract affected systems from patterns."""
        systems = set()
        
        for pattern in patterns:
            if pattern.target_ip:
                systems.add(pattern.target_ip)
            
            # Extract from indicators (simplified)
            for indicator in pattern.indicators:
                if 'port' in indicator.lower():
                    port_match = re.search(r'port\s+(\d+)', indicator, re.IGNORECASE)
                    if port_match:
                        systems.add(f"Port {port_match.group(1)}")
        
        return list(systems)
    
    def _create_no_threat_assessment(self) -> ThreatAssessment:
        """Create assessment for no threat detected."""
        return ThreatAssessment(
            threat_level=ThreatLevel.LOW,
            confidence=0.0,
            description="No threats detected",
            patterns=[],
            recommended_action=ResponseAction.LOG_ONLY,
            reasoning="No security patterns detected in analyzed data",
            timestamp=datetime.now()
        )
    
    def update_context(self, assessment: ThreatAssessment):
        """Update historical context with new assessment."""
        source_ip = assessment.source_ip
        if not source_ip:
            return
        
        if source_ip not in self.historical_context:
            self.historical_context[source_ip] = {
                'assessments': [],
                'first_seen': datetime.now(),
                'last_seen': datetime.now(),
                'threat_count': 0
            }
        
        context = self.historical_context[source_ip]
        context['assessments'].append(assessment)
        context['last_seen'] = datetime.now()
        
        if assessment.threat_level in [ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            context['threat_count'] += 1
        
        # Keep only recent assessments (last 30 days)
        cutoff = datetime.now() - timedelta(days=30)
        context['assessments'] = [
            a for a in context['assessments']
            if a.timestamp > cutoff
        ]
    
    def get_context_for_ip(self, ip: str) -> Dict:
        """Get historical context for an IP address."""
        return self.historical_context.get(ip, {
            'assessments': [],
            'first_seen': None,
            'last_seen': None,
            'threat_count': 0,
            'repeated_offender': False
        })


# Helper functions
import re

def chain_multiple_assessments(assessments: List[ThreatAssessment]) -> ThreatAssessment:
    """Chain multiple threat assessments into one."""
    if not assessments:
        return ThreatAssessment(
            threat_level=ThreatLevel.LOW,
            confidence=0.0,
            description="No assessments to chain",
            patterns=[],
            recommended_action=ResponseAction.LOG_ONLY,
            reasoning="No data available",
            timestamp=datetime.now()
        )
    
    # Use the highest threat level
    threat_levels = [a.threat_level for a in assessments]
    max_threat = max(threat_levels, key=lambda tl: tl.value)
    
    # Average confidence
    avg_confidence = sum(a.confidence for a in assessments) / len(assessments)
    
    # Combine all patterns
    all_patterns = []
    for assessment in assessments:
        all_patterns.extend(assessment.patterns)
    
    # Determine response (use most severe)
    response_priority = {
        ResponseAction.ISOLATE: 5,
        ResponseAction.BLOCK_IP: 4,
        ResponseAction.RATE_LIMIT: 3,
        ResponseAction.ALERT: 2,
        ResponseAction.MONITOR: 1,
        ResponseAction.LOG_ONLY: 0
    }
    
    recommended_action = max(
        assessments,
        key=lambda a: response_priority.get(a.recommended_action, 0)
    ).recommended_action
    
    # Create chained reasoning
    reasoning = f"Chained {len(assessments)} assessments: " + " | ".join(
        f"{a.threat_level.value} ({a.confidence:.2f})" for a in assessments
    )
    
    return ThreatAssessment(
        threat_level=max_threat,
        confidence=avg_confidence,
        description=f"Chained assessment: {len(assessments)} events",
        patterns=all_patterns,
        recommended_action=recommended_action,
        reasoning=reasoning,
        timestamp=datetime.now()
    )