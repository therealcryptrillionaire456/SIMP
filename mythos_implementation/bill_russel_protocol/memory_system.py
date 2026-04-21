"""
Memory Across Time - Pillar 3 of Bill Russel Protocol

Capabilities:
1. Long-term threat memory with SQLite
2. Weekly correlation sweeps
3. Compound threat scoring
4. Behavioral baseline tracking
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

from .pattern_recognition import SecurityPattern, PatternType
from .reasoning_engine import ThreatAssessment, ThreatLevel

logger = logging.getLogger(__name__)


@dataclass
class ThreatMemoryEntry:
    """Entry in threat memory database."""
    id: Optional[int] = None
    timestamp: datetime = None
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    pattern_type: Optional[str] = None
    confidence: float = 0.0
    description: str = ""
    indicators: str = ""  # JSON serialized
    threat_level: Optional[str] = None
    response_action: Optional[str] = None
    correlation_id: Optional[str] = None
    compound_score: float = 0.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if isinstance(self.indicators, list):
            self.indicators = json.dumps(self.indicators)


@dataclass
class CorrelationResult:
    """Result of correlation analysis."""
    correlation_id: str
    source_ip: str
    pattern_count: int
    time_span_days: int
    first_seen: datetime
    last_seen: datetime
    threat_level: str
    compound_score: float
    patterns: List[str]
    description: str


class MemorySystem:
    """Long-term memory system for threat correlation."""
    
    def __init__(self, db_path: str = "threat_memory.db"):
        """
        Initialize memory system.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Behavioral baselines
        self.baselines = {}
        
        logger.info(f"MemorySystem initialized with database: {self.db_path}")
    
    def _init_database(self):
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create threats table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS threats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            source_ip TEXT,
            target_ip TEXT,
            pattern_type TEXT,
            confidence REAL,
            description TEXT,
            indicators TEXT,
            threat_level TEXT,
            response_action TEXT,
            correlation_id TEXT,
            compound_score REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_ip ON threats (source_ip)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON threats (timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_correlation_id ON threats (correlation_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pattern_type ON threats (pattern_type)')
        
        # Create correlations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS correlations (
            correlation_id TEXT PRIMARY KEY,
            source_ip TEXT NOT NULL,
            pattern_count INTEGER,
            time_span_days INTEGER,
            first_seen DATETIME,
            last_seen DATETIME,
            threat_level TEXT,
            compound_score REAL,
            patterns TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create behavioral baselines table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS baselines (
            entity_type TEXT,
            entity_id TEXT,
            metric_name TEXT,
            avg_value REAL,
            std_dev REAL,
            min_value REAL,
            max_value REAL,
            sample_count INTEGER,
            last_updated DATETIME,
            PRIMARY KEY (entity_type, entity_id, metric_name)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_event(self, event_data: Dict, assessment: ThreatAssessment):
        """
        Record a security event and its assessment.
        
        Args:
            event_data: Original event data
            assessment: Threat assessment
        """
        # Convert patterns to memory entries
        entries = []
        for pattern in assessment.patterns:
            entry = ThreatMemoryEntry(
                timestamp=pattern.timestamp or datetime.now(),
                source_ip=pattern.source_ip,
                target_ip=pattern.target_ip,
                pattern_type=pattern.pattern_type.value,
                confidence=pattern.confidence,
                description=pattern.description,
                indicators=[indicator[:500] for indicator in pattern.indicators],  # Truncate long indicators
                threat_level=assessment.threat_level.value,
                response_action=assessment.recommended_action.value,
                compound_score=self._calculate_compound_score(pattern, assessment)
            )
            entries.append(entry)
        
        # Store entries
        for entry in entries:
            self._store_threat_entry(entry)
        
        # Update behavioral baseline
        self._update_baseline(event_data, assessment)
        
        logger.info(f"Recorded {len(entries)} threat entries for assessment")
    
    def _store_threat_entry(self, entry: ThreatMemoryEntry):
        """Store a threat entry in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO threats (
            timestamp, source_ip, target_ip, pattern_type,
            confidence, description, indicators, threat_level,
            response_action, compound_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry.timestamp.isoformat(),
            entry.source_ip,
            entry.target_ip,
            entry.pattern_type,
            entry.confidence,
            entry.description,
            entry.indicators,
            entry.threat_level,
            entry.response_action,
            entry.compound_score
        ))
        
        entry_id = cursor.lastrowid
        
        # Generate correlation ID for related entries
        if entry.source_ip:
            correlation_id = self._generate_correlation_id(entry)
            cursor.execute(
                'UPDATE threats SET correlation_id = ? WHERE id = ?',
                (correlation_id, entry_id)
            )
        
        conn.commit()
        conn.close()
    
    def _generate_correlation_id(self, entry: ThreatMemoryEntry) -> str:
        """Generate correlation ID for an entry."""
        if not entry.source_ip:
            return "unknown"
        
        # Use source IP and date for correlation
        date_str = entry.timestamp.strftime("%Y%m%d")
        return f"{entry.source_ip}_{date_str}"
    
    def _calculate_compound_score(self, pattern: SecurityPattern,
                                assessment: ThreatAssessment) -> float:
        """Calculate compound threat score."""
        base_score = pattern.confidence
        
        # Adjust by threat level
        threat_multipliers = {
            ThreatLevel.LOW: 1.0,
            ThreatLevel.MEDIUM: 1.5,
            ThreatLevel.HIGH: 2.0,
            ThreatLevel.CRITICAL: 3.0
        }
        
        multiplier = threat_multipliers.get(assessment.threat_level, 1.0)
        
        # Adjust by pattern type
        pattern_multipliers = {
            PatternType.ATTACK_SIGNATURE: 1.5,
            PatternType.DATA_EXFILTRATION: 2.0,
            PatternType.BRUTE_FORCE: 1.3,
            PatternType.PROBING_BEHAVIOR: 1.2,
            PatternType.ENUMERATION: 1.1,
            PatternType.ANOMALOUS_TRAFFIC: 1.0
        }
        
        pattern_multiplier = pattern_multipliers.get(pattern.pattern_type, 1.0)
        
        return min(base_score * multiplier * pattern_multiplier, 10.0)
    
    def _update_baseline(self, event_data: Dict, assessment: ThreatAssessment):
        """Update behavioral baseline."""
        # Extract baseline metrics from event data
        metrics = self._extract_baseline_metrics(event_data)
        
        # Update baseline for source IP if available
        source_ip = assessment.source_ip
        if source_ip:
            for metric_name, value in metrics.items():
                self._update_entity_baseline(
                    entity_type="ip",
                    entity_id=source_ip,
                    metric_name=metric_name,
                    value=value
                )
    
    def _extract_baseline_metrics(self, event_data: Dict) -> Dict[str, float]:
        """Extract baseline metrics from event data."""
        metrics = {}
        
        # Extract request count if available
        if 'request_count' in event_data:
            metrics['request_count'] = float(event_data['request_count'])
        
        # Extract byte counts if available
        if 'bytes_in' in event_data:
            metrics['bytes_in'] = float(event_data['bytes_in'])
        if 'bytes_out' in event_data:
            metrics['bytes_out'] = float(event_data['bytes_out'])
        
        # Extract timing metrics
        if 'response_time' in event_data:
            metrics['response_time'] = float(event_data['response_time'])
        
        return metrics
    
    def _update_entity_baseline(self, entity_type: str, entity_id: str,
                              metric_name: str, value: float):
        """Update baseline for an entity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current baseline
        cursor.execute('''
        SELECT avg_value, std_dev, sample_count
        FROM baselines
        WHERE entity_type = ? AND entity_id = ? AND metric_name = ?
        ''', (entity_type, entity_id, metric_name))
        
        result = cursor.fetchone()
        
        if result:
            # Update existing baseline
            current_avg, current_std, sample_count = result
            new_count = sample_count + 1
            
            # Update average (online algorithm)
            new_avg = current_avg + (value - current_avg) / new_count
            
            # Update standard deviation (simplified)
            # For production, use proper online algorithm for variance
            new_std = current_std * 0.9 + abs(value - new_avg) * 0.1
            
            cursor.execute('''
            UPDATE baselines
            SET avg_value = ?, std_dev = ?, sample_count = ?, last_updated = ?
            WHERE entity_type = ? AND entity_id = ? AND metric_name = ?
            ''', (
                new_avg, new_std, new_count, datetime.now().isoformat(),
                entity_type, entity_id, metric_name
            ))
        else:
            # Create new baseline
            cursor.execute('''
            INSERT INTO baselines (
                entity_type, entity_id, metric_name,
                avg_value, std_dev, min_value, max_value,
                sample_count, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entity_type, entity_id, metric_name,
                value, 0.0, value, value,
                1, datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def get_context(self, event_data: Dict) -> Dict:
        """
        Get historical context for an event.
        
        Args:
            event_data: Event data
            
        Returns:
            Historical context dictionary
        """
        context = {
            'repeated_offenders': [],
            'recent_similar_activity': 0,
            'historical_patterns': [],
            'baseline_deviations': []
        }
        
        # Extract source IP from event data
        source_ip = event_data.get('source_ip') or event_data.get('remote_addr')
        if not source_ip:
            return context
        
        # Check for repeated offenders
        context['repeated_offenders'] = self._get_repeated_offenders(source_ip)
        
        # Check for recent similar activity
        context['recent_similar_activity'] = self._get_recent_activity_count(
            source_ip, hours=24
        )
        
        # Get historical patterns
        context['historical_patterns'] = self._get_historical_patterns(source_ip)
        
        # Check for baseline deviations
        context['baseline_deviations'] = self._check_baseline_deviations(
            event_data, source_ip
        )
        
        return context
    
    def _get_repeated_offenders(self, source_ip: str) -> List[str]:
        """Get list of IPs with repeated threat activity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT source_ip, COUNT(*) as threat_count
        FROM threats
        WHERE timestamp > datetime('now', '-30 days')
          AND threat_level IN ('medium', 'high', 'critical')
        GROUP BY source_ip
        HAVING threat_count >= 3
        ORDER BY threat_count DESC
        LIMIT 10
        ''')
        
        offenders = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return offenders
    
    def _get_recent_activity_count(self, source_ip: str, hours: int = 24) -> int:
        """Get count of recent activity for an IP."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT COUNT(*)
        FROM threats
        WHERE source_ip = ?
          AND timestamp > datetime('now', ?)
        ''', (source_ip, f'-{hours} hours'))
        
        result = cursor.fetchone()
        count = result[0] if result else 0
        conn.close()
        
        return count
    
    def _get_historical_patterns(self, source_ip: str) -> List[Dict]:
        """Get historical patterns for an IP."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT pattern_type, COUNT(*) as count, AVG(confidence) as avg_confidence
        FROM threats
        WHERE source_ip = ?
          AND timestamp > datetime('now', '-90 days')
        GROUP BY pattern_type
        ORDER BY count DESC
        LIMIT 5
        ''', (source_ip,))
        
        patterns = []
        for row in cursor.fetchall():
            patterns.append({
                'pattern_type': row[0],
                'count': row[1],
                'avg_confidence': row[2]
            })
        
        conn.close()
        return patterns
    
    def _check_baseline_deviations(self, event_data: Dict, 
                                 source_ip: str) -> List[Dict]:
        """Check for deviations from behavioral baseline."""
        deviations = []
        
        # Extract metrics from event
        metrics = self._extract_baseline_metrics(event_data)
        
        # Check each metric against baseline
        for metric_name, value in metrics.items():
            baseline = self._get_baseline("ip", source_ip, metric_name)
            if baseline:
                avg, std = baseline['avg_value'], baseline['std_dev']
                
                # Check if value is outside 3 standard deviations
                if std > 0 and abs(value - avg) > (3 * std):
                    deviations.append({
                        'metric': metric_name,
                        'value': value,
                        'baseline_avg': avg,
                        'deviation_sigma': (value - avg) / std
                    })
        
        return deviations
    
    def _get_baseline(self, entity_type: str, entity_id: str,
                     metric_name: str) -> Optional[Dict]:
        """Get baseline for an entity and metric."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT avg_value, std_dev, min_value, max_value, sample_count
        FROM baselines
        WHERE entity_type = ? AND entity_id = ? AND metric_name = ?
        ''', (entity_type, entity_id, metric_name))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'avg_value': result[0],
                'std_dev': result[1],
                'min_value': result[2],
                'max_value': result[3],
                'sample_count': result[4]
            }
        
        return None
    
    def correlate_events(self, time_window_days: int = 7) -> List[CorrelationResult]:
        """
        Perform correlation analysis across events.
        
        Args:
            time_window_days: Time window for correlation
            
        Returns:
            List of correlation results
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get correlated events
        cursor.execute('''
        SELECT 
            correlation_id,
            source_ip,
            COUNT(*) as pattern_count,
            MIN(timestamp) as first_seen,
            MAX(timestamp) as last_seen,
            GROUP_CONCAT(DISTINCT pattern_type) as patterns,
            AVG(compound_score) as avg_score,
            MAX(threat_level) as max_threat_level
        FROM threats
        WHERE timestamp > datetime('now', ?)
          AND correlation_id IS NOT NULL
          AND source_ip IS NOT NULL
        GROUP BY correlation_id, source_ip
        HAVING pattern_count >= 2
        ORDER BY avg_score DESC
        ''', (f'-{time_window_days} days',))
        
        results = []
        for row in cursor.fetchall():
            correlation_id, source_ip, pattern_count, first_seen, last_seen, \
            patterns_str, avg_score, max_threat_level = row
            
            # Calculate time span
            first_seen_dt = datetime.fromisoformat(first_seen)
            last_seen_dt = datetime.fromisoformat(last_seen)
            time_span = (last_seen_dt - first_seen_dt).days
            
            # Parse patterns
            patterns = patterns_str.split(',') if patterns_str else []
            
            # Determine overall threat level
            threat_level = self._determine_correlation_threat_level(
                max_threat_level, pattern_count, avg_score
            )
            
            result = CorrelationResult(
                correlation_id=correlation_id,
                source_ip=source_ip,
                pattern_count=pattern_count,
                time_span_days=time_span,
                first_seen=first_seen_dt,
                last_seen=last_seen_dt,
                threat_level=threat_level,
                compound_score=avg_score,
                patterns=patterns,
                description=self._generate_correlation_description(
                    source_ip, pattern_count, patterns, time_span
                )
            )
            
            results.append(result)
            
            # Store correlation in database
            cursor.execute('''
            INSERT OR REPLACE INTO correlations (
                correlation_id, source_ip, pattern_count, time_span_days,
                first_seen, last_seen, threat_level, compound_score,
                patterns, description, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                correlation_id, source_ip, pattern_count, time_span,
                first_seen, last_seen, threat_level, avg_score,
                patterns_str, result.description, datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Correlation sweep completed: {len(results)} correlations found")
        return results
    
    def _determine_correlation_threat_level(self, max_threat_level: str,
                                          pattern_count: int,
                                          avg_score: float) -> str:
        """Determine threat level for correlation."""
        # Base on maximum threat level in correlation
        threat_priority = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }
        
        base_level = max_threat_level or 'low'
        
        # Adjust based on pattern count and score
        if pattern_count >= 5 or avg_score >= 5.0:
            # Escalate threat level
            if base_level == 'low':
                return 'medium'
            elif base_level == 'medium':
                return 'high'
        
        return base_level
    
    def _generate_correlation_description(self, source_ip: str,
                                        pattern_count: int,
                                        patterns: List[str],
                                        time_span_days: int) -> str:
        """Generate description for correlation."""
        unique_patterns = set(patterns)
        
        if pattern_count >= 10:
            severity = "Highly concerning"
        elif pattern_count >= 5:
            severity = "Concerning"
        else:
            severity = "Notable"
        
        return (
            f"{severity} correlation: {source_ip} showed {pattern_count} "
            f"patterns ({', '.join(list(unique_patterns)[:3])}) "
            f"over {time_span_days} days"
        )
    
    def get_threat_report(self, days: int = 30) -> Dict:
        """
        Generate threat report for specified period.
        
        Args:
            days: Number of days to include in report
            
        Returns:
            Threat report dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get threat statistics
        cursor.execute('''
        SELECT 
            threat_level,
            COUNT(*) as count,
            AVG(confidence) as avg_confidence,
            AVG(compound_score) as avg_score
        FROM threats
        WHERE timestamp > datetime('now', ?)
        GROUP BY threat_level
        ORDER BY 
            CASE threat_level
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 1
                ELSE 0
            END DESC
        ''', (f'-{days} days',))
        
        threat_stats = {}
        for row in cursor.fetchall():
            threat_level, count, avg_confidence, avg_score = row
            threat_stats[threat_level] = {
                'count': count,
                'avg_confidence': avg_confidence,
                'avg_score': avg_score
            }
        
        # Get top sources
        cursor.execute('''
        SELECT 
            source_ip,
            COUNT(*) as threat_count,
            MAX(compound_score) as max_score,
            GROUP_CONCAT(DISTINCT pattern_type) as patterns
        FROM threats
        WHERE timestamp > datetime('now', ?)
          AND source_ip IS NOT NULL
        GROUP BY source_ip
        ORDER BY threat_count DESC, max_score DESC
        LIMIT 10
        ''', (f'-{days} days',))
        
        top_sources = []
        for row in cursor.fetchall():
            source_ip, threat_count, max_score, patterns_str = row
            patterns = patterns_str.split(',') if patterns_str else []
            top_sources.append({
                'source_ip': source_ip,
                'threat_count': threat_count,
                'max_score': max_score,
                'patterns': patterns
            })
        
        # Get recent correlations
        cursor.execute('''
        SELECT 
            correlation_id,
            source_ip,
            pattern_count,
            time_span_days,
            threat_level,
            compound_score,
            description
        FROM correlations
        WHERE updated_at > datetime('now', ?)
        ORDER BY compound_score DESC
        LIMIT 5
        ''', (f'-{days} days',))
        
        recent_correlations = []
        for row in cursor.fetchall():
            recent_correlations.append({
                'correlation_id': row[0],
                'source_ip': row[1],
                'pattern_count': row[2],
                'time_span_days': row[3],
                'threat_level': row[4],
                'compound_score': row[5],
                'description': row[6]
            })
        
        conn.close()
        
        # Generate report
        report = {
            'period_days': days,
            'generated_at': datetime.now().isoformat(),
            'threat_statistics': threat_stats,
            'top_threat_sources': top_sources,
            'recent_correlations': recent_correlations,
            'summary': self._generate_report_summary(threat_stats, top_sources)
        }
        
        return report
    
    def _generate_report_summary(self, threat_stats: Dict,
                               top_sources: List[Dict]) -> str:
        """Generate summary text for threat report."""
        total_threats = sum(stats['count'] for stats in threat_stats.values())
        
        if total_threats == 0:
            return "No threats detected in the reporting period."
        
        # Count critical/high threats
        critical_threats = threat_stats.get('critical', {'count': 0})['count']
        high_threats = threat_stats.get('high', {'count': 0})['count']
        
        summary_parts = [
            f"Total threats: {total_threats}",
            f"Critical threats: {critical_threats}",
            f"High threats: {high_threats}"
        ]
        
        if top_sources:
            top_source = top_sources[0]
            summary_parts.append(
                f"Top source: {top_source['source_ip']} "
                f"({top_source['threat_count']} threats)"
            )
        
        return ". ".join(summary_parts) + "."