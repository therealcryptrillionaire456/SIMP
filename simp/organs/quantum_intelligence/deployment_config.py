"""
Deployment Configuration for Quantum Intelligence System

This module provides configuration for production deployment of
quantum intelligence with feature flags, monitoring, and rollback capabilities.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeploymentStage(str, Enum):
    """Deployment stages for gradual rollout."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION_PILOT = "production_pilot"  # 5% of traffic
    PRODUCTION_GROWTH = "production_growth"  # 25% of traffic
    PRODUCTION_FULL = "production_full"  # 100% of traffic


class FeatureFlag(str, Enum):
    """Feature flags for quantum intelligence."""
    QUANTUM_ARB_ENHANCEMENT = "quantum_arb_enhancement"
    QUANTUM_PORTFOLIO_OPTIMIZATION = "quantum_portfolio_optimization"
    QUANTUM_SKILL_EVOLUTION = "quantum_skill_evolution"
    REAL_QUANTUM_HARDWARE = "real_quantum_hardware"
    QUANTUM_INTELLIGENCE_DASHBOARD = "quantum_intelligence_dashboard"


@dataclass
class DeploymentConfig:
    """Deployment configuration for quantum intelligence."""
    
    # Deployment stage
    stage: DeploymentStage = DeploymentStage.DEVELOPMENT
    
    # Feature flags
    feature_flags: Dict[FeatureFlag, bool] = field(default_factory=lambda: {
        FeatureFlag.QUANTUM_ARB_ENHANCEMENT: True,
        FeatureFlag.QUANTUM_PORTFOLIO_OPTIMIZATION: True,
        FeatureFlag.QUANTUM_SKILL_EVOLUTION: True,
        FeatureFlag.REAL_QUANTUM_HARDWARE: False,  # Off by default
        FeatureFlag.QUANTUM_INTELLIGENCE_DASHBOARD: True,
    })
    
    # Traffic allocation (0-1)
    traffic_allocation: float = 1.0
    
    # Performance thresholds
    performance_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "min_quantum_advantage": 0.1,  # Minimum quantum advantage to enable
        "max_execution_time_ms": 5000,  # Maximum execution time
        "min_success_rate": 0.7,  # Minimum success rate
        "max_error_rate": 0.1,  # Maximum error rate
    })
    
    # Monitoring configuration
    monitoring: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "metrics_interval_seconds": 60,
        "alert_on_performance_drop": True,
        "alert_on_high_error_rate": True,
        "alert_on_low_quantum_advantage": True,
    })
    
    # Quantum hardware configuration
    quantum_hardware: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "max_cost_per_month": 0.0,  # 0 = free only
        "preferred_backend": "local_simulator",
        "fallback_order": ["local_simulator", "qiskit_aer", "ibm_quantum"],
        "enable_for_traffic_percentage": 0.0,  # Start with 0%
    })
    
    # Rollback configuration
    rollback: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "automatic_on_error_rate": 0.2,  # Auto-rollback if error rate > 20%
        "automatic_on_performance_drop": 0.3,  # Auto-rollback if performance drops > 30%
        "rollback_to_stage": DeploymentStage.DEVELOPMENT,
    })
    
    # Logging configuration
    logging_config: Dict[str, Any] = field(default_factory=lambda: {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/quantum_intelligence.log",
        "max_size_mb": 100,
        "backup_count": 5,
    })
    
    # Data retention
    data_retention: Dict[str, Any] = field(default_factory=lambda: {
        "job_history_days": 30,
        "performance_metrics_days": 90,
        "skill_evolution_history_days": 180,
        "circuit_designs_days": 7,  # Circuit designs can be large
    })
    
    def is_feature_enabled(self, feature: FeatureFlag) -> bool:
        """Check if a feature is enabled."""
        return self.feature_flags.get(feature, False)
    
    def should_apply_quantum_enhancement(self, request_id: str) -> bool:
        """Determine if quantum enhancement should be applied based on traffic allocation."""
        if self.traffic_allocation >= 1.0:
            return True
        
        # Simple deterministic allocation based on request ID hash
        import hashlib
        hash_value = int(hashlib.md5(request_id.encode()).hexdigest(), 16)
        allocation = (hash_value % 100) / 100.0
        
        return allocation < self.traffic_allocation
    
    def get_stage_percentage(self) -> float:
        """Get traffic percentage for current stage."""
        stage_percentages = {
            DeploymentStage.DEVELOPMENT: 0.0,
            DeploymentStage.STAGING: 0.0,  # Staging gets 0% of production traffic
            DeploymentStage.PRODUCTION_PILOT: 0.05,
            DeploymentStage.PRODUCTION_GROWTH: 0.25,
            DeploymentStage.PRODUCTION_FULL: 1.0,
        }
        return stage_percentages.get(self.stage, 0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "stage": self.stage.value,
            "feature_flags": {k.value: v for k, v in self.feature_flags.items()},
            "traffic_allocation": self.traffic_allocation,
            "performance_thresholds": self.performance_thresholds,
            "monitoring": self.monitoring,
            "quantum_hardware": self.quantum_hardware,
            "rollback": {**self.rollback, "rollback_to_stage": self.rollback["rollback_to_stage"].value},
            "logging_config": self.logging_config,
            "data_retention": self.data_retention,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeploymentConfig':
        """Create configuration from dictionary."""
        config = cls()
        
        if "stage" in data:
            config.stage = DeploymentStage(data["stage"])
        
        if "feature_flags" in data:
            config.feature_flags = {
                FeatureFlag(k): v for k, v in data["feature_flags"].items()
            }
        
        if "traffic_allocation" in data:
            config.traffic_allocation = data["traffic_allocation"]
        
        if "performance_thresholds" in data:
            config.performance_thresholds.update(data["performance_thresholds"])
        
        if "monitoring" in data:
            config.monitoring.update(data["monitoring"])
        
        if "quantum_hardware" in data:
            config.quantum_hardware.update(data["quantum_hardware"])
        
        if "rollback" in data:
            rollback_data = data["rollback"].copy()
            if "rollback_to_stage" in rollback_data:
                rollback_data["rollback_to_stage"] = DeploymentStage(rollback_data["rollback_to_stage"])
            config.rollback.update(rollback_data)
        
        if "logging_config" in data:
            config.logging_config.update(data["logging_config"])
        
        if "data_retention" in data:
            config.data_retention.update(data["data_retention"])
        
        return config


class DeploymentManager:
    """Manages deployment of quantum intelligence system."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger("quantum.deployment.manager")
        
        # Configuration path
        self.config_path = config_path or os.path.expanduser("~/.simp/quantum_deployment.json")
        
        # Load configuration
        self.config = self._load_config()
        
        # Deployment state
        self.deployment_start_time = datetime.utcnow()
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.performance_metrics: List[Dict[str, Any]] = []
        
        # Initialize logging
        self._setup_logging()
        
        self.logger.info(f"Deployment manager initialized at stage: {self.config.stage.value}")
    
    def _load_config(self) -> DeploymentConfig:
        """Load deployment configuration."""
        default_config = DeploymentConfig()
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    config = DeploymentConfig.from_dict(data)
                    self.logger.info(f"Loaded deployment configuration from {self.config_path}")
                    return config
            else:
                self.logger.info(f"Deployment configuration not found, using defaults: {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load deployment configuration: {str(e)}")
        
        return default_config
    
    def _setup_logging(self):
        """Setup logging based on configuration."""
        logging_config = self.config.logging_config
        
        # Create log directory if needed
        log_file = logging_config.get("file")
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, logging_config.get("level", "INFO")),
            format=logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            handlers=[
                logging.FileHandler(log_file) if log_file else logging.StreamHandler(),
                logging.StreamHandler()  # Always log to console
            ]
        )
    
    def save_config(self):
        """Save deployment configuration."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            self.logger.info(f"Deployment configuration saved to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save deployment configuration: {str(e)}")
    
    def should_apply_quantum_enhancement(self, request_id: str) -> bool:
        """Delegate to DeploymentConfig — determines if quantum enhancement applies for this request."""
        return self.config.should_apply_quantum_enhancement(request_id)

    def promote_stage(self, new_stage: DeploymentStage):
        """Promote deployment to a new stage."""
        old_stage = self.config.stage
        self.config.stage = new_stage
        
        # Update traffic allocation based on stage
        self.config.traffic_allocation = self.config.get_stage_percentage()
        
        self.logger.info(f"Deployment promoted from {old_stage.value} to {new_stage.value}")
        self.logger.info(f"Traffic allocation: {self.config.traffic_allocation:.1%}")
        
        # Save configuration
        self.save_config()
        
        # Log promotion event
        self._log_deployment_event("stage_promotion", {
            "old_stage": old_stage.value,
            "new_stage": new_stage.value,
            "traffic_allocation": self.config.traffic_allocation,
        })
    
    def enable_feature(self, feature: FeatureFlag, enabled: bool = True):
        """Enable or disable a feature flag."""
        old_value = self.config.feature_flags.get(feature, False)
        self.config.feature_flags[feature] = enabled
        
        self.logger.info(f"Feature {feature.value} {'enabled' if enabled else 'disabled'} "
                        f"(was {'enabled' if old_value else 'disabled'})")
        
        self.save_config()
        
        self._log_deployment_event("feature_flag_change", {
            "feature": feature.value,
            "old_value": old_value,
            "new_value": enabled,
        })
    
    def update_performance_threshold(self, threshold_name: str, value: float):
        """Update a performance threshold."""
        old_value = self.config.performance_thresholds.get(threshold_name)
        self.config.performance_thresholds[threshold_name] = value
        
        self.logger.info(f"Performance threshold {threshold_name} updated: {old_value} -> {value}")
        
        self.save_config()
    
    def record_request(self, request_id: str, success: bool, performance_metrics: Dict[str, Any]):
        """Record a request and its performance metrics."""
        self.request_count += 1
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        # Add timestamp to metrics
        performance_metrics["timestamp"] = datetime.utcnow().isoformat()
        performance_metrics["request_id"] = request_id
        performance_metrics["success"] = success
        
        self.performance_metrics.append(performance_metrics)
        
        # Keep only recent metrics (last 1000)
        if len(self.performance_metrics) > 1000:
            self.performance_metrics = self.performance_metrics[-1000:]
        
        # Check for automatic rollback conditions
        self._check_rollback_conditions()
    
    def _check_rollback_conditions(self):
        """Check if automatic rollback conditions are met."""
        if not self.config.rollback["enabled"]:
            return
        
        if self.request_count < 10:  # Need minimum requests
            return
        
        # Calculate error rate
        error_rate = self.error_count / self.request_count
        
        # Calculate average performance (if we have performance data)
        avg_performance = 0.0
        if self.performance_metrics:
            perf_scores = [m.get("performance_score", 0) for m in self.performance_metrics if "performance_score" in m]
            if perf_scores:
                avg_performance = sum(perf_scores) / len(perf_scores)
        
        # Check rollback conditions
        should_rollback = False
        rollback_reason = ""
        
        if error_rate > self.config.rollback["automatic_on_error_rate"]:
            should_rollback = True
            rollback_reason = f"Error rate {error_rate:.1%} exceeds threshold {self.config.rollback['automatic_on_error_rate']:.1%}"
        
        # Check performance drop (need baseline for comparison)
        # For now, we'll skip this check as we need historical baseline
        
        if should_rollback:
            self.logger.warning(f"Automatic rollback triggered: {rollback_reason}")
            self.rollback_to_stage(self.config.rollback["rollback_to_stage"])
    
    def rollback_to_stage(self, target_stage: DeploymentStage):
        """Rollback deployment to a previous stage."""
        old_stage = self.config.stage
        self.config.stage = target_stage
        
        # Disable all feature flags on rollback
        for feature in self.config.feature_flags:
            self.config.feature_flags[feature] = False
        
        # Set minimal traffic allocation
        self.config.traffic_allocation = 0.0
        
        self.logger.warning(f"Deployment rolled back from {old_stage.value} to {target_stage.value}")
        
        self.save_config()
        
        self._log_deployment_event("rollback", {
            "old_stage": old_stage.value,
            "new_stage": target_stage.value,
            "reason": "automatic_rollback",
        })
    
    def get_deployment_metrics(self) -> Dict[str, Any]:
        """Get deployment metrics."""
        error_rate = self.error_count / self.request_count if self.request_count > 0 else 0.0
        success_rate = self.success_count / self.request_count if self.request_count > 0 else 0.0
        
        # Calculate average quantum advantage
        avg_quantum_advantage = 0.0
        quantum_advantages = [m.get("quantum_advantage", 0) for m in self.performance_metrics if "quantum_advantage" in m]
        if quantum_advantages:
            avg_quantum_advantage = sum(quantum_advantages) / len(quantum_advantages)
        
        # Calculate average execution time
        avg_execution_time = 0.0
        execution_times = [m.get("execution_time_ms", 0) for m in self.performance_metrics if "execution_time_ms" in m]
        if execution_times:
            avg_execution_time = sum(execution_times) / len(execution_times)
        
        return {
            "stage": self.config.stage.value,
            "traffic_allocation": self.config.traffic_allocation,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "error_rate": error_rate,
            "avg_quantum_advantage": avg_quantum_advantage,
            "avg_execution_time_ms": avg_execution_time,
            "deployment_duration_hours": (datetime.utcnow() - self.deployment_start_time).total_seconds() / 3600,
            "feature_flags": {k.value: v for k, v in self.config.feature_flags.items()},
            "performance_metrics_count": len(self.performance_metrics),
        }
    
    def check_performance_thresholds(self) -> Dict[str, bool]:
        """Check if performance meets thresholds."""
        metrics = self.get_deployment_metrics()
        thresholds = self.config.performance_thresholds
        
        checks = {
            "quantum_advantage": metrics["avg_quantum_advantage"] >= thresholds["min_quantum_advantage"],
            "execution_time": metrics["avg_execution_time_ms"] <= thresholds["max_execution_time_ms"],
            "success_rate": metrics["success_rate"] >= thresholds["min_success_rate"],
            "error_rate": metrics["error_rate"] <= thresholds["max_error_rate"],
        }
        
        # Log any failed checks
        for check_name, passed in checks.items():
            if not passed:
                self.logger.warning(f"Performance threshold failed: {check_name}")
        
        return checks
    
    def can_use_real_quantum_hardware(self, request_id: str) -> bool:
        """Check if real quantum hardware can be used for a request."""
        if not self.config.quantum_hardware["enabled"]:
            return False
        
        # Check traffic allocation for quantum hardware
        if self.config.quantum_hardware["enable_for_traffic_percentage"] <= 0:
            return False
        
        # Deterministic allocation based on request ID
        import hashlib
        hash_value = int(hashlib.md5(request_id.encode()).hexdigest(), 16)
        allocation = (hash_value % 100) / 100.0
        
        return allocation < self.config.quantum_hardware["enable_for_traffic_percentage"]
    
    def _log_deployment_event(self, event_type: str, data: Dict[str, Any]):
        """Log a deployment event."""
        event = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
            "deployment_metrics": self.get_deployment_metrics(),
        }
        
        # Log to file
        log_file = self.config.logging_config.get("file")
        if log_file:
            event_log_file = log_file.replace(".log", "_events.log")
            try:
                with open(event_log_file, 'a') as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as e:
                self.logger.error(f"Failed to log deployment event: {str(e)}")
        
        self.logger.info(f"Deployment event: {event_type} - {data}")


# Singleton instance
_deployment_manager = None

def get_deployment_manager(config_path: Optional[str] = None) -> DeploymentManager:
    """Get singleton instance of deployment manager."""
    global _deployment_manager
    if _deployment_manager is None:
        _deployment_manager = DeploymentManager(config_path)
    return _deployment_manager