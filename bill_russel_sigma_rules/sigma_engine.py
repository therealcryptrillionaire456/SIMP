#!/usr/bin/env python3
"""
Bill Russell Protocol - Sigma Rules Engine

Implements Sigma rules for log normalization and threat detection.
Based on PDF analysis: "Better reasoning chains - deeper multi-step logic"

Sigma rules provide a standardized way to describe log events for threat detection.
This engine converts diverse log formats into a unified schema for analysis.
"""

import os
import sys
import json
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging
import hashlib

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
SIGMA_DIR = BASE_DIR / "sigma_rules"
RULES_DIR = SIGMA_DIR / "rules"
PROCESSED_RULES_DIR = SIGMA_DIR / "processed"
LOG_FILE = SIGMA_DIR / "sigma_engine.log"

# Ensure directories exist
for dir_path in [SIGMA_DIR, RULES_DIR, PROCESSED_RULES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SigmaRule:
    """Represents a Sigma rule for threat detection."""
    title: str
    id: str
    description: str
    author: str
    date: str
    modified: str
    references: List[str]
    tags: List[str]
    logsource: Dict[str, str]
    detection: Dict[str, Any]
    falsepositives: List[str]
    level: str
    status: str = "experimental"
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_yaml(self) -> str:
        """Convert rule to YAML format."""
        return yaml.dump(self.to_dict(), default_flow_style=False)
    
    def get_hash(self) -> str:
        """Get unique hash for this rule."""
        rule_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(rule_str.encode()).hexdigest()[:16]


@dataclass
class LogEvent:
    """Normalized log event using unified schema."""
    timestamp: str
    source: str  # syslog, windows, apache, etc.
    event_id: str
    event_type: str
    severity: str
    message: str
    raw_message: str
    normalized_fields: Dict[str, Any] = field(default_factory=dict)
    sigma_matches: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class DetectionResult:
    """Result of Sigma rule detection."""
    rule_id: str
    rule_title: str
    event_id: str
    timestamp: str
    confidence: float
    matched_fields: Dict[str, Any]
    raw_event: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Unified Schema Definition
# ---------------------------------------------------------------------------

UNIFIED_SCHEMA = {
    # Core fields (always present)
    "required": [
        "timestamp",
        "source",
        "event_id", 
        "event_type",
        "severity",
        "message"
    ],
    
    # Extended fields (contextual)
    "extended": {
        "network": [
            "source_ip",
            "source_port",
            "destination_ip",
            "destination_port",
            "protocol",
            "bytes_sent",
            "bytes_received",
            "duration"
        ],
        "authentication": [
            "username",
            "domain",
            "auth_method",
            "success",
            "failure_reason",
            "source_host"
        ],
        "file_system": [
            "filename",
            "file_path",
            "file_hash",
            "file_size",
            "operation",
            "process_name"
        ],
        "process": [
            "process_id",
            "parent_process_id",
            "process_name",
            "command_line",
            "user",
            "integrity_level"
        ],
        "registry": [
            "key_path",
            "value_name",
            "value_data",
            "operation"
        ],
        "dns": [
            "query_name",
            "query_type",
            "response_code",
            "answer"
        ],
        "http": [
            "method",
            "uri",
            "user_agent",
            "status_code",
            "referrer"
        ]
    },
    
    # Threat intelligence fields
    "threat_intel": [
        "ioc_type",
        "ioc_value",
        "confidence",
        "source_ti",
        "first_seen",
        "last_seen"
    ]
}


# ---------------------------------------------------------------------------
# Sigma Rules Engine
# ---------------------------------------------------------------------------

class SigmaEngine:
    """Sigma rules engine for log normalization and threat detection."""
    
    def __init__(self):
        self.rules: Dict[str, SigmaRule] = {}
        self.compiled_rules: Dict[str, Any] = {}
        self.field_mappings: Dict[str, Dict[str, str]] = {}
        
        self._load_builtin_rules()
        self._load_field_mappings()
        
        log.info(f"Sigma Engine initialized with {len(self.rules)} rules")
    
    def _load_builtin_rules(self):
        """Load built-in Sigma rules for Bill Russell Protocol."""
        builtin_rules = [
            # Network anomaly detection
            SigmaRule(
                title="Multiple Failed Authentication Attempts",
                id="BR-001",
                description="Detects multiple failed authentication attempts from same source",
                author="Bill Russell Protocol",
                date="2026-04-10",
                modified="2026-04-10",
                references=["https://attack.mitre.org/techniques/T1110/"],
                tags=["attack.t1110", "br.protocol"],
                logsource={"category": "authentication", "product": "windows"},
                detection={
                    "selection": {
                        "EventID": "4625",
                        "Status": "0xc000006a"  # Wrong password
                    },
                    "condition": "selection | count() by SourceIp > 5"
                },
                falsepositives=["Legitimate user forgetting password"],
                level="medium"
            ),
            
            # Suspicious process execution
            SigmaRule(
                title="Suspicious Process Execution from Temp Directory",
                id="BR-002",
                description="Detects process execution from temporary directories",
                author="Bill Russell Protocol",
                date="2026-04-10",
                modified="2026-04-10",
                references=["https://attack.mitre.org/techniques/T1059/"],
                tags=["attack.t1059", "br.protocol"],
                logsource={"category": "process_creation", "product": "windows"},
                detection={
                    "selection": {
                        "Image": ["*\\Temp\\*", "*\\tmp\\*", "*\\AppData\\Local\\Temp\\*"]
                    },
                    "condition": "selection"
                },
                falsepositives=["Legitimate software installers"],
                level="high"
            ),
            
            # Network scanning
            SigmaRule(
                title="Port Scanning Activity",
                id="BR-003",
                description="Detects port scanning patterns",
                author="Bill Russell Protocol",
                date="2026-04-10",
                modified="2026-04-10",
                references=["https://attack.mitre.org/techniques/T1046/"],
                tags=["attack.t1046", "br.protocol"],
                logsource={"category": "network", "product": "firewall"},
                detection={
                    "selection": {
                        "action": "deny"
                    },
                    "condition": "selection | count() by SourceIp, DestinationPort > 10"
                },
                falsepositives=["Network misconfiguration", "Legitimate scanning"],
                level="medium"
            ),
            
            # Data exfiltration
            SigmaRule(
                title="Large Outbound Data Transfer",
                id="BR-004",
                description="Detects large data transfers to external destinations",
                author="Bill Russell Protocol",
                date="2026-04-10",
                modified="2026-04-10",
                references=["https://attack.mitre.org/techniques/T1048/"],
                tags=["attack.t1048", "br.protocol"],
                logsource={"category": "network", "product": "firewall"},
                detection={
                    "selection": {
                        "destination_ip": ["!10.0.0.0/8", "!172.16.0.0/12", "!192.168.0.0/16"]
                    },
                    "filter": {
                        "bytes_sent": "> 100000000"  # 100MB
                    },
                    "condition": "selection and filter"
                },
                falsepositives=["Large legitimate transfers", "Backup operations"],
                level="high"
            ),
            
            # Zero-day probing (Mythos cyber capability counter)
            SigmaRule(
                title="Zero-Day Vulnerability Probing",
                id="BR-005",
                description="Detects patterns indicative of zero-day vulnerability probing",
                author="Bill Russell Protocol",
                date="2026-04-10",
                modified="2026-04-10",
                references=["Based on Mythos Preview System Card analysis"],
                tags=["mythos.counter", "zero_day", "br.protocol"],
                logsource={"category": "web", "product": "webserver"},
                detection={
                    "selection": {
                        "uri": ["*%00*", "*..*", "*\\x*", "*.php.bak*"]  # Common exploit patterns
                    },
                    "filter": {
                        "user_agent": ["*sqlmap*", "*nikto*", "*nmap*", "*hydra*"]
                    },
                    "condition": "selection or filter"
                },
                falsepositives=["Security testing", "Bug bounty programs"],
                level="critical"
            ),
            
            # Autonomous attack chain (Mythos reasoning counter)
            SigmaRule(
                title="Autonomous Attack Chain Detection",
                id="BR-006",
                description="Detects multi-step attack patterns across different log sources",
                author="Bill Russell Protocol",
                date="2026-04-10",
                modified="2026-04-10",
                references=["Based on Mythos Preview System Card analysis"],
                tags=["mythos.counter", "autonomous", "br.protocol"],
                logsource={"category": "multiple", "product": "multiple"},
                detection={
                    "step1": {
                        "EventID": "4625",  # Failed login
                        "source_ip": "*"
                    },
                    "step2": {
                        "EventID": "4688",  # Process creation
                        "source_ip": "step1.source_ip",
                        "Image": "*\\cmd.exe"
                    },
                    "step3": {
                        "EventID": "5156",  # Network connection
                        "source_ip": "step1.source_ip",
                        "destination_ip": "external"
                    },
                    "condition": "1 of step*"
                },
                falsepositives=["Administrative activities"],
                level="critical"
            )
        ]
        
        for rule in builtin_rules:
            self.rules[rule.id] = rule
            self._compile_rule(rule)
        
        # Save built-in rules to disk
        self._save_rules_to_disk()
    
    def _load_field_mappings(self):
        """Load field mappings for different log sources."""
        self.field_mappings = {
            "syslog": {
                "timestamp": "timestamp",
                "hostname": "source_host",
                "program": "process_name",
                "message": "message"
            },
            "windows": {
                "EventTime": "timestamp",
                "Computer": "source_host",
                "EventID": "event_id",
                "Level": "severity",
                "Message": "message",
                "IpAddress": "source_ip",
                "LogonType": "auth_method",
                "TargetUserName": "username"
            },
            "apache": {
                "time": "timestamp",
                "host": "source_ip",
                "request": "uri",
                "status": "status_code",
                "user_agent": "user_agent",
                "referrer": "referrer"
            },
            "json": {}  # Direct mapping for JSON logs
        }
    
    def _compile_rule(self, rule: SigmaRule):
        """Compile a Sigma rule for faster matching."""
        compiled = {
            "id": rule.id,
            "title": rule.title,
            "logsource": rule.logsource,
            "detection": rule.detection,
            "level": rule.level,
            "compiled_patterns": {}
        }
        
        # Extract patterns from detection section
        for key, value in rule.detection.items():
            if key not in ["condition", "timeframe"]:
                compiled["compiled_patterns"][key] = self._compile_pattern(value)
        
        self.compiled_rules[rule.id] = compiled
    
    def _compile_pattern(self, pattern: Any) -> Any:
        """Compile a pattern for matching."""
        if isinstance(pattern, dict):
            compiled = {}
            for k, v in pattern.items():
                compiled[k] = self._compile_pattern(v)
            return compiled
        elif isinstance(pattern, list):
            return [self._compile_pattern(item) for item in pattern]
        elif isinstance(pattern, str):
            # Convert wildcards to regex
            if "*" in pattern:
                regex_pattern = pattern.replace("*", ".*")
                return re.compile(regex_pattern, re.IGNORECASE)
            return pattern
        else:
            return pattern
    
    def _save_rules_to_disk(self):
        """Save rules to disk for persistence."""
        for rule_id, rule in self.rules.items():
            rule_file = RULES_DIR / f"{rule_id}.yml"
            with open(rule_file, 'w') as f:
                f.write(rule.to_yaml())
        
        log.info(f"Saved {len(self.rules)} rules to {RULES_DIR}")
    
    def normalize_log(self, raw_log: Dict[str, Any], source_type: str = "json") -> LogEvent:
        """Normalize a log event to unified schema."""
        # Extract timestamp
        timestamp = raw_log.get("timestamp") or raw_log.get("time") or datetime.utcnow().isoformat() + "Z"
        
        # Get field mappings for this source type
        mappings = self.field_mappings.get(source_type, {})
        
        # Build normalized fields
        normalized_fields = {}
        for source_field, target_field in mappings.items():
            if source_field in raw_log:
                normalized_fields[target_field] = raw_log[source_field]
        
        # Extract additional fields using heuristics
        self._extract_fields_heuristics(raw_log, normalized_fields)
        
        # Create log event
        event = LogEvent(
            timestamp=timestamp,
            source=source_type,
            event_id=raw_log.get("event_id", str(hash(json.dumps(raw_log, sort_keys=True)))),
            event_type=self._determine_event_type(raw_log, normalized_fields),
            severity=self._determine_severity(raw_log),
            message=raw_log.get("message", str(raw_log)),
            raw_message=json.dumps(raw_log),
            normalized_fields=normalized_fields
        )
        
        return event
    
    def _extract_fields_heuristics(self, raw_log: Dict, normalized_fields: Dict):
        """Extract fields using heuristics and pattern matching."""
        # Try to extract IP addresses
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        message = str(raw_log)
        
        ips = re.findall(ip_pattern, message)
        if ips:
            if "source_ip" not in normalized_fields and len(ips) >= 1:
                normalized_fields["source_ip"] = ips[0]
            if "destination_ip" not in normalized_fields and len(ips) >= 2:
                normalized_fields["destination_ip"] = ips[1]
        
        # Try to extract URLs
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message, re.IGNORECASE)
        if urls and "uri" not in normalized_fields:
            normalized_fields["uri"] = urls[0]
        
        # Try to extract usernames (common patterns)
        user_patterns = [
            r'user[=:]\s*([^\s,]+)',
            r'username[=:]\s*([^\s,]+)',
            r'login[=:]\s*([^\s,]+)',
            r'\\\\([^\\]+)\\([^\\\s]+)'  # DOMAIN\username
        ]
        
        for pattern in user_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                normalized_fields["username"] = match.group(1) if match.lastindex else match.group(0)
                break
    
    def _determine_event_type(self, raw_log: Dict, normalized_fields: Dict) -> str:
        """Determine event type based on log content."""
        # Check for authentication events
        auth_keywords = ["login", "logon", "authentication", "auth", "password", "credential"]
        message = str(raw_log).lower()
        
        if any(keyword in message for keyword in auth_keywords):
            return "authentication"
        
        # Check for network events
        network_keywords = ["connection", "packet", "port", "ip", "firewall", "network"]
        if any(keyword in message for keyword in network_keywords):
            return "network"
        
        # Check for process events
        process_keywords = ["process", "executable", "cmd", "powershell", "binary"]
        if any(keyword in message for keyword in process_keywords):
            return "process"
        
        # Default to generic
        return "generic"
    
    def _determine_severity(self, raw_log: Dict) -> str:
        """Determine severity based on log content."""
        severity_map = {
            "emergency": "critical",
            "alert": "critical",
            "critical": "critical",
            "error": "high",
            "warning": "medium",
            "notice": "low",
            "informational": "low",
            "debug": "low"
        }
        
        # Check for explicit severity field
        for field in ["severity", "level", "priority"]:
            if field in raw_log:
                value = str(raw_log[field]).lower()
                if value in severity_map:
                    return severity_map[value]
        
        # Heuristic based on keywords
        message = str(raw_log).lower()
        
        critical_keywords = ["failed", "error", "denied", "blocked", "attack", "exploit", "malware"]
        if any(keyword in message for keyword in critical_keywords):
            return "high"
        
        warning_keywords = ["warning", "suspicious", "unusual", "anomaly"]
        if any(keyword in message for keyword in warning_keywords):
            return "medium"
        
        return "low"
    
    def detect(self, log_event: LogEvent) -> List[DetectionResult]:
        """Detect threats using Sigma rules."""
        results = []
        
        for rule_id, compiled_rule in self.compiled_rules.items():
            # Check if rule applies to this log source
            logsource = compiled_rule["logsource"]
            if not self._matches_logsource(log_event, logsource):
                continue
            
            # Apply detection logic
            if self._matches_detection(log_event, compiled_rule):
                rule = self.rules[rule_id]
                
                result = DetectionResult(
                    rule_id=rule_id,
                    rule_title=rule.title,
                    event_id=log_event.event_id,
                    timestamp=log_event.timestamp,
                    confidence=self._calculate_confidence(log_event, compiled_rule),
                    matched_fields=self._get_matched_fields(log_event, compiled_rule),
                    raw_event=log_event.to_dict()
                )
                
                results.append(result)
                log_event.sigma_matches.append(rule_id)
        
        return results
    
    def _matches_logsource(self, log_event: LogEvent, logsource: Dict) -> bool:
        """Check if log event matches rule's logsource criteria."""
        # Simplified matching - in production would be more sophisticated
        if not logsource:
            return True
        
        # Check category
        if "category" in logsource:
            if logsource["category"] != log_event.event_type:
                return False
        
        # Check product (simplified)
        if "product" in logsource:
            # In real implementation, would check against known products
            pass
        
        return True
    
    def _matches_detection(self, log_event: LogEvent, compiled_rule: Dict) -> bool:
        """Check if log event matches detection criteria."""
        detection = compiled_rule["detection"]
        
        # Simple implementation - real Sigma engine would be more complex
        if "condition" not in detection:
            return False
        
        condition = detection["condition"]
        
        # Parse condition (simplified)
        if "|" in condition:
            # Has aggregation
            parts = condition.split("|")
            base_condition = parts[0].strip()
            aggregation = parts[1].strip() if len(parts) > 1 else ""
            
            # Check base condition
            if not self._check_selection(log_event, detection, base_condition):
                return False
            
            # Note: Aggregation would require multiple events
            # For now, we'll skip aggregation checks
            return True
        else:
            # Simple condition
            return self._check_selection(log_event, detection, condition)
    
    def _check_selection(self, log_event: LogEvent, detection: Dict, selection_name: str) -> bool:
        """Check if log event matches a selection."""
        if selection_name not in detection:
            return False
        
        selection = detection[selection_name]
        return self._matches_pattern(log_event, selection)
    
    def _matches_pattern(self, log_event: LogEvent, pattern: Any) -> bool:
        """Check if log event matches a pattern."""
        if isinstance(pattern, dict):
            # All key-value pairs must match
            for key, value in pattern.items():
                # Get value from log event
                event_value = self._get_event_value(log_event, key)
                
                # Check match
                if not self._value_matches(event_value, value):
                    return False
            return True
        elif isinstance(pattern, list):
            # Any item in list must match (OR condition)
            for item in pattern:
                if self._matches_pattern(log_event, item):
                    return True
            return False
        else:
            # Direct value match
            # This is simplified - real implementation would handle different patterns
            return True
    
    def _get_event_value(self, log_event: LogEvent, key: str) -> Any:
        """Get value from log event by key."""
        # Check normalized fields first
        if key in log_event.normalized_fields:
            return log_event.normalized_fields[key]
        
        # Check raw message (would parse in real implementation)
        return None
    
    def _value_matches(self, event_value: Any, pattern_value: Any) -> bool:
        """Check if event value matches pattern value."""
        if event_value is None:
            return False
        
        if isinstance(pattern_value, re.Pattern):
            # Regex match
            return bool(pattern_value.match(str(event_value)))
        elif isinstance(pattern_value, str):
            # String match (with wildcards)
            if "*" in pattern_value:
                regex = pattern_value.replace("*", ".*")
                return bool(re.match(regex, str(event_value), re.IGNORECASE))
            else:
                return str(event_value).lower() == pattern_value.lower()
        else:
            # Direct comparison
            return event_value == pattern_value
    
    def _calculate_confidence(self, log_event: LogEvent, compiled_rule: Dict) -> float:
        """Calculate detection confidence."""
        # Base confidence from rule level
        level_confidences = {
            "critical": 0.95,
            "high": 0.85,
            "medium": 0.70,
            "low": 0.50
        }
        
        base_confidence = level_confidences.get(compiled_rule["level"], 0.50)
        
        # Adjust based on field matches
        field_count = len(self._get_matched_fields(log_event, compiled_rule))
        field_bonus = min(0.20, field_count * 0.05)
        
        return min(1.0, base_confidence + field_bonus)
    
    def _get_matched_fields(self, log_event: LogEvent, compiled_rule: Dict) -> Dict[str, Any]:
        """Get fields that matched the rule."""
        matched = {}
        
        for selection_name, pattern in compiled_rule.get("compiled_patterns", {}).items():
            if self._matches_pattern(log_event, pattern):
                # Extract matched values
                if isinstance(pattern, dict):
                    for key in pattern.keys():
                        value = self._get_event_value(log_event, key)
                        if value is not None:
                            matched[key] = value
        
        return matched
    
    def process_log_file(self, file_path: Path, source_type: str = "json") -> List[DetectionResult]:
        """Process a log file and detect threats."""
        results = []
        
        log.info(f"Processing log file: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        # Parse log line
                        if source_type == "json":
                            raw_log = json.loads(line.strip())
                        else:
                            # For other formats, would use appropriate parser
                            raw_log = {"message": line.strip(), "line_number": line_num}
                        
                        # Normalize and detect
                        log_event = self.normalize_log(raw_log, source_type)
                        detections = self.detect(log_event)
                        
                        results.extend(detections)
                        
                        # Log progress
                        if line_num % 1000 == 0:
                            log.info(f"Processed {line_num} lines, {len(detections)} detections")
                    
                    except json.JSONDecodeError:
                        log.warning(f"Line {line_num}: Invalid JSON")
                    except Exception as e:
                        log.error(f"Line {line_num}: Error - {e}")
        
        except Exception as e:
            log.error(f"Error processing file {file_path}: {e}")
        
        log.info(f"Finished processing: {len(results)} detections found")
        return results
    
    def add_rule(self, rule: SigmaRule):
        """Add a new Sigma rule."""
        self.rules[rule.id] = rule
        self._compile_rule(rule)
        
        # Save to disk
        rule_file = RULES_DIR / f"{rule.id}.yml"
        with open(rule_file, 'w') as f:
            f.write(rule.to_yaml())
        
        log.info(f"Added new rule: {rule.id} - {rule.title}")
    
    def get_rule(self, rule_id: str) -> Optional[SigmaRule]:
        """Get a Sigma rule by ID."""
        return self.rules.get(rule_id)
    
    def list_rules(self) -> List[SigmaRule]:
        """List all Sigma rules."""
        return list(self.rules.values())
    
    def get_stats(self) -> Dict:
        """Get engine statistics."""
        return {
            "total_rules": len(self.rules),
            "compiled_rules": len(self.compiled_rules),
            "rule_levels": {
                level: sum(1 for r in self.rules.values() if r.level == level)
                for level in ["critical", "high", "medium", "low"]
            },
            "mythos_counter_rules": sum(1 for r in self.rules.values() if "mythos.counter" in r.tags)
        }


# ---------------------------------------------------------------------------
# Command Line Interface
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Bill Russell Protocol - Sigma Rules Engine"
    )
    parser.add_argument(
        "--process-log",
        type=Path,
        help="Process a log file for threat detection"
    )
    parser.add_argument(
        "--source-type",
        choices=["json", "syslog", "windows", "apache"],
        default="json",
        help="Log source type (default: json)"
    )
    parser.add_argument(
        "--add-rule",
        type=Path,
        help="Add a new Sigma rule from YAML file"
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="List all Sigma rules"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show engine statistics"
    )
    
    args = parser.parse_args()
    
    # Initialize engine
    engine = SigmaEngine()
    
    if args.stats:
        stats = engine.get_stats()
        print("\n" + "=" * 60)
        print("BILL RUSSELL PROTOCOL - SIGMA ENGINE STATISTICS")
        print("=" * 60)
        print(f"Total rules: {stats['total_rules']}")
        print(f"Mythos counter rules: {stats['mythos_counter_rules']}")
        print("\nRule levels:")
        for level, count in stats['rule_levels'].items():
            print(f"  {level}: {count}")
        print("=" * 60)
        return
    
    if args.list_rules:
        rules = engine.list_rules()
        print("\n" + "=" * 60)
        print("BILL RUSSELL PROTOCOL - SIGMA RULES")
        print("=" * 60)
        for rule in rules:
            print(f"\n{rule.id}: {rule.title}")
            print(f"  Level: {rule.level}")
            print(f"  Tags: {', '.join(rule.tags)}")
            print(f"  Description: {rule.description[:100]}...")
        print("=" * 60)
        return
    
    if args.add_rule:
        try:
            with open(args.add_rule, 'r') as f:
                rule_data = yaml.safe_load(f)
            
            rule = SigmaRule(**rule_data)
            engine.add_rule(rule)
            print(f"✓ Added rule: {rule.id} - {rule.title}")
        except Exception as e:
            print(f"✗ Error adding rule: {e}")
        return
    
    if args.process_log:
        if not args.process_log.exists():
            print(f"✗ Log file not found: {args.process_log}")
            return
        
        results = engine.process_log_file(args.process_log, args.source_type)
        
        print("\n" + "=" * 60)
        print(f"DETECTION RESULTS: {args.process_log.name}")
        print("=" * 60)
        
        if not results:
            print("No threats detected")
        else:
            for result in results:
                print(f"\n{result.rule_id}: {result.rule_title}")
                print(f"  Confidence: {result.confidence:.2%}")
                print(f"  Timestamp: {result.timestamp}")
                if result.matched_fields:
                    print(f"  Matched fields: {result.matched_fields}")
        
        print("=" * 60)
        print(f"Total detections: {len(results)}")
        return
    
    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()