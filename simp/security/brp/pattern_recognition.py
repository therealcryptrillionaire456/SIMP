"""
Pattern Recognition at Depth - Pillar 1 of Bill Russel Protocol

Capabilities:
1. Attack signatures before completion (PCAP + Sysmon)
2. Probing behavior recognition (access logs)
3. Data exfiltration detection (traffic patterns)
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Types of security patterns."""
    ATTACK_SIGNATURE = "attack_signature"
    PROBING_BEHAVIOR = "probing_behavior"
    DATA_EXFILTRATION = "data_exfiltration"
    ANOMALOUS_TRAFFIC = "anomalous_traffic"
    BRUTE_FORCE = "brute_force"
    ENUMERATION = "enumeration"


@dataclass
class SecurityPattern:
    """Detected security pattern."""
    pattern_type: PatternType
    confidence: float  # 0.0 to 1.0
    description: str
    indicators: List[str]
    timestamp: datetime
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None


class PatternRecognizer:
    """Recognizes security patterns at depth."""
    
    def __init__(self):
        # Known attack signatures
        self.attack_signatures = self._load_attack_signatures()
        
        # Probing behavior patterns
        self.probing_patterns = self._load_probing_patterns()
        
        # Exfiltration patterns
        self.exfiltration_patterns = self._load_exfiltration_patterns()
        
        # Behavioral baselines
        self.baselines = {}
        
        logger.info("PatternRecognizer initialized")
    
    def _load_attack_signatures(self) -> Dict[str, Dict]:
        """Load known attack signatures."""
        return {
            "sql_injection": {
                "patterns": [
                    r"(['\"]?\s*(union|select|insert|update|delete|drop|create|alter)\s+.*?)",
                    r"(/\*.*?\*/)",
                    r"(--\s+.*)",
                    r"(;\s*--\s*)",
                    r"(waitfor\s+delay\s+)",
                    r"(exec\s*\(.*\))"
                ],
                "description": "SQL Injection attempt",
                "severity": "high"
            },
            "xss": {
                "patterns": [
                    r"(<script.*?>.*?</script>)",
                    r"(javascript:.*?)",
                    r"(on\w+\s*=)",
                    r"(alert\s*\(.*\))",
                    r"(document\.cookie)"
                ],
                "description": "Cross-site scripting attempt",
                "severity": "medium"
            },
            "path_traversal": {
                "patterns": [
                    r"(\.\./\.\./)",
                    r"(\.\.\\\.\.\\)",
                    r"(/etc/passwd)",
                    r"(/etc/shadow)",
                    r"(C:\\Windows\\System32\\)"
                ],
                "description": "Path traversal attempt",
                "severity": "high"
            },
            "command_injection": {
                "patterns": [
                    r"(;\s*\w+.*?)",
                    r"(\|\s*\w+.*?)",
                    r"(&\s*\w+.*?)",
                    r"(`.*?`)",
                    r"(\$\{.*?\})",
                    r"(\(.*?\))"
                ],
                "description": "Command injection attempt",
                "severity": "critical"
            }
        }
    
    def _load_probing_patterns(self) -> Dict[str, Dict]:
        """Load probing behavior patterns."""
        return {
            "port_scanning": {
                "description": "Port scanning activity",
                "indicators": [
                    "Multiple connection attempts to different ports",
                    "Sequential port access",
                    "Rapid connection attempts",
                    "SYN packets without completion"
                ],
                "threshold": {
                    "ports_per_minute": 50,
                    "unique_ports": 20
                }
            },
            "directory_enumeration": {
                "description": "Directory/file enumeration",
                "indicators": [
                    "404 responses for common paths",
                    "Access to hidden directories",
                    "Attempts to access backup files",
                    "Common wordlist paths"
                ],
                "common_paths": [
                    "/admin", "/backup", "/config", "/database",
                    "/.git", "/.env", "/wp-admin", "/phpmyadmin"
                ]
            },
            "brute_force": {
                "description": "Brute force authentication attempts",
                "indicators": [
                    "Multiple failed login attempts",
                    "Rapid authentication requests",
                    "Common username/password combinations",
                    "Account lockout triggers"
                ],
                "threshold": {
                    "failed_logins_per_minute": 10,
                    "unique_usernames": 5
                }
            }
        }
    
    def _load_exfiltration_patterns(self) -> Dict[str, Dict]:
        """Load data exfiltration patterns."""
        return {
            "large_outbound": {
                "description": "Large outbound data transfer",
                "indicators": [
                    "Unusually large outbound packets",
                    "Sustained high outbound bandwidth",
                    "Data to unknown external IPs",
                    "Encrypted traffic to suspicious domains"
                ],
                "threshold": {
                    "bytes_out_per_minute": 100000000,  # 100MB
                    "duration_minutes": 5
                }
            },
            "data_staging": {
                "description": "Data staging before exfiltration",
                "indicators": [
                    "Files copied to temporary locations",
                    "Compression of sensitive data",
                    "Creation of archive files",
                    "Multiple file accesses in short time"
                ]
            },
            "covert_channels": {
                "description": "Covert channel communication",
                "indicators": [
                    "DNS tunneling patterns",
                    "ICMP data exfiltration",
                    "HTTP header manipulation",
                    "Steganography in images/files"
                ]
            }
        }
    
    def analyze_pcap(self, pcap_data: bytes) -> List[SecurityPattern]:
        """
        Analyze PCAP data for attack signatures.
        
        Args:
            pcap_data: Raw PCAP packet data
            
        Returns:
            List of detected security patterns
        """
        patterns = []
        
        # Convert PCAP to text for analysis (simplified)
        try:
            pcap_text = pcap_data.decode('latin-1', errors='ignore')
            
            # Check for attack signatures in packet payloads
            for sig_name, signature in self.attack_signatures.items():
                for pattern in signature['patterns']:
                    matches = re.findall(pattern, pcap_text, re.IGNORECASE)
                    if matches:
                        confidence = min(0.3 + (len(matches) * 0.1), 0.9)
                        patterns.append(SecurityPattern(
                            pattern_type=PatternType.ATTACK_SIGNATURE,
                            confidence=confidence,
                            description=f"{signature['description']} - {sig_name}",
                            indicators=[f"Matched pattern: {pattern[:50]}..."],
                            timestamp=datetime.now(),
                            source_ip=self._extract_source_ip(pcap_text),
                            target_ip=self._extract_dest_ip(pcap_text)
                        ))
                        
        except Exception as e:
            logger.error(f"Error analyzing PCAP: {e}")
        
        return patterns
    
    def analyze_access_logs(self, log_entries: List[Dict]) -> List[SecurityPattern]:
        """
        Analyze access logs for probing behavior.
        
        Args:
            log_entries: List of access log entries
            
        Returns:
            List of detected security patterns
        """
        patterns = []
        
        # Group by IP and analyze patterns
        ip_activity = {}
        for entry in log_entries:
            ip = entry.get('remote_addr', 'unknown')
            if ip not in ip_activity:
                ip_activity[ip] = {
                    'requests': [],
                    'status_codes': [],
                    'paths': [],
                    'timestamps': []
                }
            
            ip_activity[ip]['requests'].append(entry)
            ip_activity[ip]['status_codes'].append(entry.get('status', 200))
            ip_activity[ip]['paths'].append(entry.get('request', ''))
            ip_activity[ip]['timestamps'].append(
                datetime.fromisoformat(entry.get('time', datetime.now().isoformat()))
            )
        
        # Analyze each IP's activity
        for ip, activity in ip_activity.items():
            # Check for port scanning patterns
            port_scan_patterns = self._detect_port_scanning(activity)
            patterns.extend(port_scan_patterns)
            
            # Check for directory enumeration
            enum_patterns = self._detect_enumeration(activity)
            patterns.extend(enum_patterns)
            
            # Check for brute force
            brute_patterns = self._detect_brute_force(activity)
            patterns.extend(brute_patterns)
        
        return patterns
    
    def analyze_traffic_patterns(self, netflow_data: List[Dict]) -> List[SecurityPattern]:
        """
        Analyze netflow data for exfiltration patterns.
        
        Args:
            netflow_data: List of netflow records
            
        Returns:
            List of detected security patterns
        """
        patterns = []
        
        # Group by source IP
        source_traffic = {}
        for flow in netflow_data:
            src_ip = flow.get('src_ip', 'unknown')
            if src_ip not in source_traffic:
                source_traffic[src_ip] = {
                    'bytes_out': 0,
                    'bytes_in': 0,
                    'destinations': set(),
                    'start_time': None,
                    'end_time': None
                }
            
            traffic = source_traffic[src_ip]
            traffic['bytes_out'] += flow.get('bytes_out', 0)
            traffic['bytes_in'] += flow.get('bytes_in', 0)
            traffic['destinations'].add(flow.get('dst_ip', 'unknown'))
            
            # Track time range
            flow_time = datetime.fromisoformat(flow.get('timestamp', datetime.now().isoformat()))
            if traffic['start_time'] is None or flow_time < traffic['start_time']:
                traffic['start_time'] = flow_time
            if traffic['end_time'] is None or flow_time > traffic['end_time']:
                traffic['end_time'] = flow_time
        
        # Analyze for exfiltration
        for src_ip, traffic in source_traffic.items():
            # Calculate duration
            if traffic['start_time'] and traffic['end_time']:
                duration = (traffic['end_time'] - traffic['start_time']).total_seconds() / 60  # minutes
                
                # Check for large outbound transfers
                if duration > 0 and traffic['bytes_out'] > 0:
                    bytes_per_minute = traffic['bytes_out'] / duration
                    
                    if bytes_per_minute > self.exfiltration_patterns['large_outbound']['threshold']['bytes_out_per_minute']:
                        patterns.append(SecurityPattern(
                            pattern_type=PatternType.DATA_EXFILTRATION,
                            confidence=0.7,
                            description="Large outbound data transfer detected",
                            indicators=[
                                f"Outbound rate: {bytes_per_minute/1e6:.1f} MB/min",
                                f"Total outbound: {traffic['bytes_out']/1e6:.1f} MB",
                                f"Duration: {duration:.1f} minutes",
                                f"Destinations: {len(traffic['destinations'])}"
                            ],
                            timestamp=datetime.now(),
                            source_ip=src_ip
                        ))
            
            # Check for data staging patterns
            if len(traffic['destinations']) > 10 and traffic['bytes_out'] > 50000000:  # 50MB
                patterns.append(SecurityPattern(
                    pattern_type=PatternType.DATA_EXFILTRATION,
                    confidence=0.6,
                    description="Possible data staging to multiple destinations",
                    indicators=[
                        f"Multiple destinations: {len(traffic['destinations'])}",
                        f"Total data: {traffic['bytes_out']/1e6:.1f} MB"
                    ],
                    timestamp=datetime.now(),
                    source_ip=src_ip
                ))
        
        return patterns
    
    def _detect_port_scanning(self, activity: Dict) -> List[SecurityPattern]:
        """Detect port scanning patterns."""
        patterns = []
        
        # Analyze request patterns
        requests = activity['requests']
        if len(requests) < 10:  # Need minimum requests for pattern
            return patterns
        
        # Extract ports from requests (simplified)
        ports = []
        for req in requests:
            # Extract port from request if present
            request_str = str(req.get('request', ''))
            port_match = re.search(r':(\d+)(?:\s|$)', request_str)
            if port_match:
                ports.append(int(port_match.group(1)))
        
        if len(ports) >= self.probing_patterns['port_scanning']['threshold']['unique_ports']:
            # Check if ports are sequential (common in scans)
            sorted_ports = sorted(set(ports))
            sequential_count = 0
            for i in range(1, len(sorted_ports)):
                if sorted_ports[i] == sorted_ports[i-1] + 1:
                    sequential_count += 1
            
            if sequential_count > len(sorted_ports) * 0.3:  # 30% sequential
                patterns.append(SecurityPattern(
                    pattern_type=PatternType.PROBING_BEHAVIOR,
                    confidence=0.8,
                    description="Port scanning detected",
                    indicators=[
                        f"Unique ports accessed: {len(sorted_ports)}",
                        f"Sequential pattern detected",
                        f"Total requests: {len(requests)}"
                    ],
                    timestamp=datetime.now(),
                    source_ip=requests[0].get('remote_addr', 'unknown')
                ))
        
        return patterns
    
    def _detect_enumeration(self, activity: Dict) -> List[SecurityPattern]:
        """Detect directory/file enumeration."""
        patterns = []
        
        paths = activity['paths']
        status_codes = activity['status_codes']
        
        # Check for common enumeration paths
        common_path_hits = 0
        for path in paths:
            for common_path in self.probing_patterns['directory_enumeration']['common_paths']:
                if common_path in path.lower():
                    common_path_hits += 1
                    break
        
        # Check for 404 responses
        error_responses = sum(1 for code in status_codes if 400 <= code < 500)
        
        if common_path_hits > 5 or error_responses > len(status_codes) * 0.5:  # 50% errors
            confidence = min(0.5 + (common_path_hits * 0.1), 0.9)
            patterns.append(SecurityPattern(
                pattern_type=PatternType.ENUMERATION,
                confidence=confidence,
                description="Directory enumeration detected",
                indicators=[
                    f"Common path hits: {common_path_hits}",
                    f"Error responses: {error_responses}/{len(status_codes)}",
                    f"Total requests: {len(paths)}"
                ],
                timestamp=datetime.now(),
                source_ip=activity['requests'][0].get('remote_addr', 'unknown') if activity['requests'] else 'unknown'
            ))
        
        return patterns
    
    def _detect_brute_force(self, activity: Dict) -> List[SecurityPattern]:
        """Detect brute force attempts."""
        patterns = []
        
        requests = activity['requests']
        timestamps = activity['timestamps']
        
        if len(requests) < self.probing_patterns['brute_force']['threshold']['failed_logins_per_minute']:
            return patterns
        
        # Check request rate (simplified)
        if len(timestamps) >= 2:
            time_range = max(timestamps) - min(timestamps)
            minutes = time_range.total_seconds() / 60
            
            if minutes > 0:
                requests_per_minute = len(requests) / minutes
                
                if requests_per_minute > self.probing_patterns['brute_force']['threshold']['failed_logins_per_minute']:
                    patterns.append(SecurityPattern(
                        pattern_type=PatternType.BRUTE_FORCE,
                        confidence=0.7,
                        description="Brute force attempt detected",
                        indicators=[
                            f"Request rate: {requests_per_minute:.1f}/min",
                            f"Total requests: {len(requests)}",
                            f"Time window: {minutes:.1f} minutes"
                        ],
                        timestamp=datetime.now(),
                        source_ip=requests[0].get('remote_addr', 'unknown')
                    ))
        
        return patterns
    
    def _extract_source_ip(self, pcap_text: str) -> Optional[str]:
        """Extract source IP from PCAP text (simplified)."""
        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+->', pcap_text)
        return ip_match.group(1) if ip_match else None
    
    def _extract_dest_ip(self, pcap_text: str) -> Optional[str]:
        """Extract destination IP from PCAP text (simplified)."""
        ip_match = re.search(r'->\s+(\d+\.\d+\.\d+\.\d+)', pcap_text)
        return ip_match.group(1) if ip_match else None
    
    def analyze(self, event_data: Dict) -> List[SecurityPattern]:
        """
        Analyze event data for security patterns.
        
        Args:
            event_data: Dictionary containing event information
            
        Returns:
            List of detected security patterns
        """
        patterns = []
        
        # Check data type and route to appropriate analyzer
        data_type = event_data.get('data_type', 'unknown')
        
        if data_type == 'pcap':
            pcap_data = event_data.get('data', b'')
            patterns.extend(self.analyze_pcap(pcap_data))
        
        elif data_type == 'access_logs':
            log_entries = event_data.get('data', [])
            patterns.extend(self.analyze_access_logs(log_entries))
        
        elif data_type == 'netflow':
            netflow_data = event_data.get('data', [])
            patterns.extend(self.analyze_traffic_patterns(netflow_data))
        
        else:
            # Generic pattern matching
            text_data = json.dumps(event_data)
            for sig_name, signature in self.attack_signatures.items():
                for pattern in signature['patterns']:
                    if re.search(pattern, text_data, re.IGNORECASE):
                        patterns.append(SecurityPattern(
                            pattern_type=PatternType.ATTACK_SIGNATURE,
                            confidence=0.5,
                            description=f"Generic {signature['description']}",
                            indicators=[f"Matched {sig_name} pattern"],
                            timestamp=datetime.now()
                        ))
        
        return patterns