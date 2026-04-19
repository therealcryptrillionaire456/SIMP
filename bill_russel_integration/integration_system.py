#!/usr/bin/env python3
"""
Bill Russell Protocol - Integration System

Integrates all components into a unified threat detection system:
1. Data acquisition → Sigma normalization → ML detection → Telegram alerts
2. SIMP broker integration for agent communication
3. Performance monitoring and logging

Based on PDF analysis: "Autonomy loops - let it act, observe results, self-correct"
"""

import os
import sys
import json
import time
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import hashlib
import queue

# Import Bill Russell components
try:
    # Try relative imports
    from ..bill_russel_data_acquisition.web_scraper import SecurityDatasetScraper
    from ..bill_russel_data_acquisition.dataset_processor import SecurityDatasetProcessor
    from ..bill_russel_sigma_rules.sigma_engine import SigmaEngine, LogEvent, DetectionResult
    from ..bill_russel_ml_pipeline.training_pipeline import MLTrainingPipeline
    from ..simp.agents.bill_russel_agent_enhanced import EnhancedBillRusselAgent, EnhancedThreatEvent
except ImportError:
    # Try absolute imports
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from bill_russel_data_acquisition.web_scraper import SecurityDatasetScraper
    from bill_russel_data_acquisition.dataset_processor import SecurityDatasetProcessor
    from bill_russel_sigma_rules.sigma_engine import SigmaEngine, LogEvent, DetectionResult
    from bill_russel_ml_pipeline.training_pipeline import MLTrainingPipeline

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
INTEGRATION_DIR = BASE_DIR / "bill_russel_integration"
DATA_DIR = BASE_DIR / "data" / "bill_russel_integration"
LOGS_DIR = DATA_DIR / "logs"
CONFIG_FILE = INTEGRATION_DIR / "integration_config.json"
LOG_FILE = LOGS_DIR / "integration_system.log"

# Ensure directories exist
for dir_path in [DATA_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Default configuration
DEFAULT_CONFIG = {
    "components": {
        "data_acquisition": {
            "enabled": True,
            "auto_download": False,
            "download_interval_hours": 24
        },
        "sigma_engine": {
            "enabled": True,
            "auto_process_logs": True,
            "log_directories": ["/var/log", "./logs"]
        },
        "ml_pipeline": {
            "enabled": True,
            "auto_train": False,
            "training_interval_days": 7
        },
        "telegram_alerts": {
            "enabled": False,  # Will be implemented
            "bot_token": "",
            "chat_id": ""
        },
        "simp_integration": {
            "enabled": True,
            "simp_url": "http://127.0.0.1:5555",
            "poll_interval_seconds": 5
        }
    },
    "performance": {
        "max_concurrent_tasks": 4,
        "log_retention_days": 30,
        "alert_threshold": 0.85  # Confidence threshold for alerts
    },
    "mythos_counter": {
        "enabled": True,
        "focus_patterns": ["zero_day_probing", "autonomous_chain", "cross_domain"],
        "memory_window_days": 30
    }
}

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
class IntegrationStatus:
    """Status of integration system components."""
    timestamp: str
    components: Dict[str, Dict[str, Any]]
    performance: Dict[str, float]
    threats_detected: Dict[str, int]
    system_health: str  # green, yellow, red
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ThreatPipelineResult:
    """Result of threat detection pipeline."""
    log_event: LogEvent
    sigma_detections: List[DetectionResult]
    ml_predictions: List[Dict[str, Any]]
    final_assessment: Dict[str, Any]
    actions_taken: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "log_event": self.log_event.to_dict(),
            "sigma_detections": [d.to_dict() for d in self.sigma_detections],
            "ml_predictions": self.ml_predictions,
            "final_assessment": self.final_assessment,
            "actions_taken": self.actions_taken
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for integration system."""
    processing_latency_ms: float
    detection_accuracy: float
    false_positive_rate: float
    system_uptime_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Integration System Core
# ---------------------------------------------------------------------------

class BillRussellIntegrationSystem:
    """Main integration system for Bill Russell Protocol."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.status = IntegrationStatus(
            timestamp=datetime.utcnow().isoformat() + "Z",
            components={},
            performance={},
            threats_detected={},
            system_health="green"
        )
        
        # Initialize components
        self.components = {}
        self._init_components()
        
        # Performance tracking
        self.metrics = PerformanceMetrics(
            processing_latency_ms=0.0,
            detection_accuracy=0.0,
            false_positive_rate=0.0,
            system_uptime_seconds=0.0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0
        )
        
        # Threading
        self.running = False
        self.processing_queue = queue.Queue()
        self.alert_queue = queue.Queue()
        
        # Statistics
        self.stats = {
            "logs_processed": 0,
            "threats_detected": 0,
            "mythos_threats": 0,
            "alerts_sent": 0,
            "start_time": datetime.utcnow()
        }
        
        log.info("Bill Russell Integration System initialized")
        log.info(f"Configuration: {json.dumps(self.config, indent=2)}")
    
    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration from file or use defaults."""
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                log.info(f"Loaded configuration from {config_path}")
                return config
            except Exception as e:
                log.error(f"Error loading config from {config_path}: {e}")
        
        # Use defaults and save
        config = DEFAULT_CONFIG.copy()
        
        if not CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            log.info(f"Created default configuration at {CONFIG_FILE}")
        
        return config
    
    def _init_components(self):
        """Initialize all enabled components."""
        components_config = self.config.get("components", {})
        
        # Data Acquisition
        if components_config.get("data_acquisition", {}).get("enabled", False):
            try:
                self.components["data_acquisition"] = SecurityDatasetScraper()
                log.info("✓ Data Acquisition component initialized")
            except Exception as e:
                log.error(f"✗ Failed to initialize Data Acquisition: {e}")
        
        # Sigma Engine
        if components_config.get("sigma_engine", {}).get("enabled", False):
            try:
                self.components["sigma_engine"] = SigmaEngine()
                log.info("✓ Sigma Engine component initialized")
            except Exception as e:
                log.error(f"✗ Failed to initialize Sigma Engine: {e}")
        
        # ML Pipeline
        if components_config.get("ml_pipeline", {}).get("enabled", False):
            try:
                self.components["ml_pipeline"] = MLTrainingPipeline()
                log.info("✓ ML Pipeline component initialized")
            except Exception as e:
                log.error(f"✗ Failed to initialize ML Pipeline: {e}")
        
        # SIMP Agent (Enhanced)
        if components_config.get("simp_integration", {}).get("enabled", False):
            try:
                simp_config = components_config["simp_integration"]
                self.components["simp_agent"] = EnhancedBillRusselAgent(
                    poll_interval=simp_config.get("poll_interval_seconds", 5),
                    simp_url=simp_config.get("simp_url", "http://127.0.0.1:5555")
                )
                log.info("✓ SIMP Agent component initialized")
            except Exception as e:
                log.error(f"✗ Failed to initialize SIMP Agent: {e}")
        
        log.info(f"Initialized {len(self.components)} components")
    
    def run(self):
        """Run the integration system."""
        self.running = True
        log.info("Bill Russell Integration System starting...")
        
        # Start component threads
        threads = []
        
        # Start log processing thread
        if "sigma_engine" in self.components:
            processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True,
                name="LogProcessing"
            )
            processing_thread.start()
            threads.append(processing_thread)
        
        # Start alert processing thread
        alert_thread = threading.Thread(
            target=self._alert_processing_loop,
            daemon=True,
            name="AlertProcessing"
        )
        alert_thread.start()
        threads.append(alert_thread)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="SystemMonitoring"
        )
        monitor_thread.start()
        threads.append(monitor_thread)
        
        # Start SIMP agent if available
        if "simp_agent" in self.components:
            simp_thread = threading.Thread(
                target=self._run_simp_agent,
                daemon=True,
                name="SIMPIntegration"
            )
            simp_thread.start()
            threads.append(simp_thread)
        
        try:
            # Main loop
            while self.running:
                self._update_status()
                time.sleep(5)  # Main loop sleep
                
        except KeyboardInterrupt:
            log.info("Shutdown signal received")
        except Exception as e:
            log.error(f"Error in main loop: {e}")
        finally:
            self.shutdown()
    
    def _processing_loop(self):
        """Process logs through the detection pipeline."""
        log.info("Log processing loop started")
        
        while self.running:
            try:
                # Check for new logs (simulated for now)
                simulated_logs = self._generate_simulated_logs()
                
                for log_data in simulated_logs:
                    start_time = time.time()
                    
                    # Process through pipeline
                    result = self.process_threat_pipeline(log_data)
                    
                    # Update metrics
                    processing_time = (time.time() - start_time) * 1000  # ms
                    self.metrics.processing_latency_ms = (
                        self.metrics.processing_latency_ms * 0.9 + processing_time * 0.1
                    )
                    
                    # Update statistics
                    self.stats["logs_processed"] += 1
                    
                    if result.sigma_detections or result.ml_predictions:
                        self.stats["threats_detected"] += 1
                        
                        # Check for Mythos threats
                        if self._is_mythos_threat(result):
                            self.stats["mythos_threats"] += 1
                    
                    # Queue for alert processing if needed
                    if self._requires_alert(result):
                        self.alert_queue.put(result)
                
                # Sleep between processing batches
                time.sleep(1)
                
            except Exception as e:
                log.error(f"Error in processing loop: {e}")
                time.sleep(5)
    
    def _alert_processing_loop(self):
        """Process alerts and send notifications."""
        log.info("Alert processing loop started")
        
        while self.running:
            try:
                # Process alerts from queue
                while not self.alert_queue.empty():
                    result = self.alert_queue.get_nowait()
                    self._process_alert(result)
                
                time.sleep(0.1)
                
            except queue.Empty:
                time.sleep(1)
            except Exception as e:
                log.error(f"Error in alert processing loop: {e}")
                time.sleep(5)
    
    def _monitoring_loop(self):
        """Monitor system health and performance."""
        log.info("System monitoring loop started")
        
        while self.running:
            try:
                # Update performance metrics
                self._update_performance_metrics()
                
                # Check component health
                self._check_component_health()
                
                # Log status periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    self._log_system_status()
                
                time.sleep(1)
                
            except Exception as e:
                log.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _run_simp_agent(self):
        """Run the SIMP agent component."""
        log.info("SIMP agent thread started")
        
        try:
            # Run SIMP agent
            self.components["simp_agent"].run()
        except Exception as e:
            log.error(f"Error in SIMP agent: {e}")
    
    def _generate_simulated_logs(self) -> List[Dict]:
        """Generate simulated log data for testing."""
        logs = []
        
        # Generate some normal logs
        for i in range(5):
            logs.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source": "simulated",
                "message": f"Normal system activity {i}",
                "severity": "info"
            })
        
        # Occasionally generate threat logs
        import random
        if random.random() < 0.3:  # 30% chance
            threat_types = [
                ("Failed login attempt from 192.168.1.100", "high"),
                ("Port scan detected from 10.0.0.50", "medium"),
                ("Suspicious process execution: cmd.exe from temp", "critical"),
                ("Zero-day probing detected in web logs", "critical"),
                ("Autonomous attack chain pattern detected", "critical")
            ]
            
            message, severity = random.choice(threat_types)
            logs.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source": "simulated_threat",
                "message": message,
                "severity": severity,
                "source_ip": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}"
            })
        
        return logs
    
    def process_threat_pipeline(self, log_data: Dict) -> ThreatPipelineResult:
        """Process log data through the complete threat detection pipeline."""
        sigma_detections = []
        ml_predictions = []
        
        # Step 1: Sigma Engine detection
        if "sigma_engine" in self.components:
            try:
                # Normalize log
                log_event = self.components["sigma_engine"].normalize_log(log_data, "json")
                
                # Detect threats
                sigma_detections = self.components["sigma_engine"].detect(log_event)
            except Exception as e:
                log.error(f"Error in Sigma Engine processing: {e}")
                log_event = LogEvent(
                    timestamp=log_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                    source="error",
                    event_id="error",
                    event_type="error",
                    severity="low",
                    message=str(log_data),
                    raw_message=json.dumps(log_data)
                )
        else:
            # Create minimal log event
            log_event = LogEvent(
                timestamp=log_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                source=log_data.get("source", "unknown"),
                event_id=hashlib.sha256(json.dumps(log_data).encode()).hexdigest()[:16],
                event_type="generic",
                severity=log_data.get("severity", "low"),
                message=log_data.get("message", str(log_data)),
                raw_message=json.dumps(log_data)
            )
        
        # Step 2: ML Pipeline prediction (if available)
        if "ml_pipeline" in self.components and hasattr(self.components["ml_pipeline"], 'predict'):
            try:
                # Convert log to features for ML
                features = self._extract_ml_features(log_event)
                if features:
                    # Note: In production, would call actual ML model
                    ml_predictions = [{
                        "model": "simulated_ml",
                        "prediction": "threat" if sigma_detections else "benign",
                        "confidence": 0.85 if sigma_detections else 0.95
                    }]
            except Exception as e:
                log.error(f"Error in ML Pipeline prediction: {e}")
        
        # Step 3: Final assessment
        final_assessment = self._assemble_final_assessment(
            log_event, sigma_detections, ml_predictions
        )
        
        # Step 4: Determine actions
        actions_taken = self._determine_actions(final_assessment)
        
        return ThreatPipelineResult(
            log_event=log_event,
            sigma_detections=sigma_detections,
            ml_predictions=ml_predictions,
            final_assessment=final_assessment,
            actions_taken=actions_taken
        )
    
    def _extract_ml_features(self, log_event: LogEvent) -> Optional[List[float]]:
        """Extract features for ML prediction."""
        # Simplified feature extraction
        # In production, would use proper feature engineering
        features = []
        
        # Text features from message
        message = log_event.message.lower()
        
        # Threat keywords
        threat_keywords = ["failed", "error", "attack", "malware", "exploit", 
                          "suspicious", "unauthorized", "breach", "intrusion"]
        
        features.append(sum(1 for kw in threat_keywords if kw in message))
        
        # Severity encoding
        severity_map = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        features.append(severity_map.get(log_event.severity, 0))
        
        # Length features
        features.append(len(message))
        features.append(len(log_event.raw_message))
        
        return features if features else None
    
    def _assemble_final_assessment(self, log_event: LogEvent, 
                                  sigma_detections: List[DetectionResult],
                                  ml_predictions: List[Dict]) -> Dict[str, Any]:
        """Assemble final threat assessment from all detectors."""
        assessment = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "log_event_id": log_event.event_id,
            "sigma_detection_count": len(sigma_detections),
            "ml_prediction_count": len(ml_predictions),
            "overall_confidence": 0.0,
            "threat_level": "low",
            "mythos_relevance": False,
            "recommended_actions": []
        }
        
        # Calculate overall confidence
        confidences = []
        
        for detection in sigma_detections:
            confidences.append(detection.confidence)
        
        for prediction in ml_predictions:
            if "confidence" in prediction:
                confidences.append(prediction["confidence"])
        
        if confidences:
            assessment["overall_confidence"] = max(confidences)
        
        # Determine threat level
        if assessment["overall_confidence"] >= 0.9:
            assessment["threat_level"] = "critical"
        elif assessment["overall_confidence"] >= 0.7:
            assessment["threat_level"] = "high"
        elif assessment["overall_confidence"] >= 0.5:
            assessment["threat_level"] = "medium"
        
        # Check for Mythos relevance
        mythos_patterns = self.config.get("mythos_counter", {}).get("focus_patterns", [])
        for detection in sigma_detections:
            if any(pattern in detection.rule_title.lower() for pattern in ["zero", "autonomous", "cross"]):
                assessment["mythos_relevance"] = True
                break
        
        # Generate recommended actions
        if assessment["threat_level"] in ["high", "critical"]:
            assessment["recommended_actions"].append("Immediate investigation required")
            
            if assessment["mythos_relevance"]:
                assessment["recommended_actions"].append("Mythos-level threat detected - escalate")
            
            if "source_ip" in log_event.normalized_fields:
                assessment["recommended_actions"].append(
                    f"Consider blocking IP: {log_event.normalized_fields['source_ip']}"
                )
        
        return assessment
    
    def _determine_actions(self, assessment: Dict[str, Any]) -> List[str]:
        """Determine actions based on threat assessment."""
        actions = []
        alert_threshold = self.config.get("performance", {}).get("alert_threshold", 0.85)
        
        if assessment["overall_confidence"] >= alert_threshold:
            actions.append("queue_alert")
            
            if assessment["threat_level"] in ["high", "critical"]:
                actions.append("log_critical_event")
                
                if assessment["mythos_relevance"]:
                    actions.append("mythos_counter_protocol")
        
        # Always log for analysis
        actions.append("log_for_analysis")
        
        return actions
    
    def _is_mythos_threat(self, result: ThreatPipelineResult) -> bool:
        """Check if threat is related to Mythos capabilities."""
        for detection in result.sigma_detections:
            rule_title = detection.rule_title.lower()
            if any(keyword in rule_title for keyword in ["zero-day", "autonomous", "cross-domain"]):
                return True
        
        return False
    
    def _requires_alert(self, result: ThreatPipelineResult) -> bool:
        """Check if result requires an alert."""
        alert_threshold = self.config.get("performance", {}).get("alert_threshold", 0.85)
        
        # Check Sigma detections
        for detection in result.sigma_detections:
            if detection.confidence >= alert_threshold:
                return True
        
        # Check ML predictions
        for prediction in result.ml_predictions:
            if prediction.get("confidence", 0) >= alert_threshold:
                return True
        
        return False
    
    def _process_alert(self, result: ThreatPipelineResult):
        """Process an alert."""
        try:
            # Create alert message
            alert_message = self._create_alert_message(result)
            
            # Log alert
            log.warning(f"ALERT: {alert_message}")
            
            # Send to SIMP agent if available
            if "simp_agent" in self.components:
                self._send_to_simp_agent(result)
            
            # TODO: Send Telegram alert if configured
            telegram_config = self.config.get("components", {}).get("telegram_alerts", {})
            if telegram_config.get("enabled", False):
                self._send_telegram_alert(alert_message, telegram_config)
            
            # Update statistics
            self.stats["alerts_sent"] += 1
            
        except Exception as e:
            log.error(f"Error processing alert: {e}")
    
    def _create_alert_message(self, result: ThreatPipelineResult) -> str:
        """Create alert message from detection result."""
        assessment = result.final_assessment
        
        message = f"🚨 THREAT DETECTED\n"
        message += f"Level: {assessment['threat_level'].upper()}\n"
        message += f"Confidence: {assessment['overall_confidence']:.1%}\n"
        
        if assessment['mythos_relevance']:
            message += f"⚠️ MYTHOS-RELATED THREAT\n"
        
        if result.sigma_detections:
            message += f"Rules triggered: {len(result.sigma_detections)}\n"
            for detection in result.sigma_detections[:3]:  # Show first 3
                message += f"  • {detection.rule_title} ({detection.confidence:.1%})\n"
        
        message += f"Log: {result.log_event.message[:100]}..."
        
        return message
    
    def _send_to_simp_agent(self, result: ThreatPipelineResult):
        """Send detection result to SIMP agent."""
        try:
            # Convert to SIMP agent format
            threat_event = EnhancedThreatEvent(
                event_id=result.log_event.event_id,
                timestamp=result.log_event.timestamp,
                source_ip=result.log_event.normalized_fields.get("source_ip", "unknown"),
                threat_type="sigma_detection",  # Would map to actual type
                details=result.to_dict(),
                patterns_detected=[],  # Would extract from detections
                threat_assessment=result.final_assessment,
                confidence=result.final_assessment["overall_confidence"],
                severity=result.final_assessment["threat_level"],
                response_action="alert_only",  # Would determine based on assessment
                mythos_capability_countered="pattern_recognition" if result.final_assessment["mythos_relevance"] else "general"
            )
            
            # In production, would use SIMP agent's internal methods
            # For now, just log
            log.info(f"Would send to SIMP agent: {threat_event.event_id}")
            
        except Exception as e:
            log.error(f"Error sending to SIMP agent: {e}")
    
    def _send_telegram_alert(self, message: str, config: Dict):
        """Send alert to Telegram (placeholder)."""
        # TODO: Implement Telegram bot integration
        log.info(f"Would send Telegram alert: {message[:50]}...")
    
    def _update_performance_metrics(self):
        """Update performance metrics."""
        # Simulated metrics - in production would collect real metrics
        import psutil
        import os
        
        try:
            process = psutil.Process(os.getpid())
            
            self.metrics.memory_usage_mb = process.memory_info().rss / (1024 * 1024)
            self.metrics.cpu_usage_percent = process.cpu_percent(interval=0.1)
            self.metrics.system_uptime_seconds = (datetime.utcnow() - self.stats["start_time"]).total_seconds()
            
            # Simulated accuracy metrics
            if self.stats["logs_processed"] > 0:
                detection_rate = self.stats["threats_detected"] / self.stats["logs_processed"]
                self.metrics.detection_accuracy = min(0.95, detection_rate * 10)  # Simulated
            
        except Exception as e:
            log.error(f"Error updating performance metrics: {e}")
    
    def _check_component_health(self):
        """Check health of all components."""
        health_status = "green"
        
        for name, component in self.components.items():
            # Simple health check - in production would be more sophisticated
            if component is None:
                log.warning(f"Component {name} is None")
                health_status = "yellow"
        
        self.status.system_health = health_status
    
    def _log_system_status(self):
        """Log system status periodically."""
        uptime = (datetime.utcnow() - self.stats["start_time"])
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        log.info(
            f"System Status - Uptime: {uptime_str}, "
            f"Logs: {self.stats['logs_processed']}, "
            f"Threats: {self.stats['threats_detected']} "
            f"(Mythos: {self.stats['mythos_threats']}), "
            f"Alerts: {self.stats['alerts_sent']}, "
            f"Health: {self.status.system_health}"
        )
    
    def _update_status(self):
        """Update integration system status."""
        self.status.timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Update component statuses
        self.status.components = {}
        for name, component in self.components.items():
            self.status.components[name] = {
                "enabled": True,
                "status": "running" if component is not None else "error"
            }
        
        # Update threat statistics
        self.status.threats_detected = {
            "total": self.stats["threats_detected"],
            "mythos": self.stats["mythos_threats"],
            "alerts": self.stats["alerts_sent"]
        }
        
        # Update performance
        self.status.performance = self.metrics.to_dict()
    
    def get_status(self) -> IntegrationStatus:
        """Get current system status."""
        self._update_status()
        return self.status
    
    def shutdown(self):
        """Shutdown the integration system."""
        self.running = False
        log.info("Bill Russell Integration System shutting down...")
        
        # Save final status
        self._update_status()
        status_file = DATA_DIR / "final_status.json"
        with open(status_file, 'w') as f:
            json.dump(self.status.to_dict(), f, indent=2)
        
        log.info(f"Final status saved to {status_file}")
        log.info("Bill Russell Integration System shutdown complete")


# ---------------------------------------------------------------------------
# Command Line Interface
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Bill Russell Protocol - Integration System"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show system status and exit"
    )
    parser.add_argument(
        "--test-pipeline",
        action="store_true",
        help="Test threat detection pipeline with sample data"
    )
    
    args = parser.parse_args()
    
    # Initialize system
    system = BillRussellIntegrationSystem(args.config)
    
    if args.status:
        status = system.get_status()
        
        print("\n" + "=" * 60)
        print("BILL RUSSELL INTEGRATION SYSTEM - STATUS")
        print("=" * 60)
        
        print(f"\nSystem Health: {status.system_health.upper()}")
        print(f"Timestamp: {status.timestamp}")
        
        print(f"\nCOMPONENTS:")
        for name, comp_status in status.components.items():
            print(f"  {name}: {comp_status['status']}")
        
        print(f"\nTHREAT STATISTICS:")
        for name, count in status.threats_detected.items():
            print(f"  {name}: {count}")
        
        print(f"\nPERFORMANCE:")
        for name, value in status.performance.items():
            if isinstance(value, float):
                print(f"  {name}: {value:.2f}")
            else:
                print(f"  {name}: {value}")
        
        print("=" * 60)
        return
    
    if args.test_pipeline:
        print("\nTesting threat detection pipeline...")
        
        # Test with sample log
        sample_log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "test",
            "message": "Zero-day probing detected: fuzzing parameters with unusual headers",
            "severity": "critical",
            "source_ip": "192.168.1.100"
        }
        
        result = system.process_threat_pipeline(sample_log)
        
        print(f"\nPipeline Result:")
        print(f"  Log Event ID: {result.log_event.event_id}")
        print(f"  Sigma Detections: {len(result.sigma_detections)}")
        print(f"  ML Predictions: {len(result.ml_predictions)}")
        print(f"  Final Threat Level: {result.final_assessment['threat_level']}")
        print(f"  Mythos Relevance: {result.final_assessment['mythos_relevance']}")
        print(f"  Actions: {', '.join(result.actions_taken)}")
        
        if result.sigma_detections:
            print(f"\nSigma Detections:")
            for detection in result.sigma_detections:
                print(f"  • {detection.rule_title} ({detection.confidence:.1%})")
        
        return
    
    # Run the system
    print("\n" + "=" * 60)
    print("BILL RUSSELL INTEGRATION SYSTEM")
    print("=" * 60)
    print("\nStarting integrated threat detection system...")
    print("Components initialized:")
    
    for name, component in system.components.items():
        print(f"  ✓ {name}")
    
    print("\nPress Ctrl+C to shutdown")
    print("=" * 60)
    
    try:
        system.run()
    except KeyboardInterrupt:
        print("\nShutdown requested")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()