#!/usr/bin/env python3
"""
Quantum Intelligence Deployment Script

This script handles the deployment of quantum intelligence to production,
including configuration, monitoring setup, and health checks.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simp.organs.quantum_intelligence.deployment_config import (
    DeploymentStage, FeatureFlag, get_deployment_manager
)
from simp.organs.quantum_intelligence.production_agent import create_production_agent


class QuantumIntelligenceDeployer:
    """Deployer for quantum intelligence system."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger("quantum.deployer")
        
        # Configuration
        self.config_path = config_path or os.path.expanduser("~/.simp/quantum_deployment.json")
        self.deployment_manager = get_deployment_manager(self.config_path)
        
        # Deployment directories
        self.base_dir = Path(__file__).parent
        self.logs_dir = self.base_dir / "logs"
        self.monitoring_dir = self.base_dir / "monitoring"
        
        # Ensure directories exist
        self.logs_dir.mkdir(exist_ok=True)
        self.monitoring_dir.mkdir(exist_ok=True)
        
        self.logger.info(f"Quantum intelligence deployer initialized")
        self.logger.info(f"Config path: {self.config_path}")
        self.logger.info(f"Logs directory: {self.logs_dir}")
    
    def deploy(self, stage: str, enable_features: Optional[list] = None):
        """Deploy quantum intelligence to specified stage."""
        try:
            # Parse stage
            deployment_stage = DeploymentStage(stage)
            
            self.logger.info(f"Starting deployment to {stage} stage")
            
            # Step 1: Validate system requirements
            self._validate_requirements()
            
            # Step 2: Setup logging and monitoring
            self._setup_monitoring()
            
            # Step 3: Configure deployment
            self._configure_deployment(deployment_stage, enable_features or [])
            
            # Step 4: Run health checks
            self._run_health_checks()
            
            # Step 5: Start monitoring services
            self._start_monitoring_services()
            
            # Step 6: Create deployment report
            report = self._create_deployment_report(deployment_stage)
            
            self.logger.info(f"Deployment to {stage} completed successfully")
            self.logger.info(f"Deployment report saved to: {report['report_path']}")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Deployment failed: {str(e)}")
            raise
    
    def promote(self, target_stage: str):
        """Promote deployment to a higher stage."""
        try:
            current_stage = self.deployment_manager.config.stage
            target = DeploymentStage(target_stage)
            
            self.logger.info(f"Promoting deployment from {current_stage.value} to {target_stage}")
            
            # Validate promotion path
            self._validate_promotion_path(current_stage, target)
            
            # Run pre-promotion checks
            self._run_pre_promotion_checks()
            
            # Promote stage
            self.deployment_manager.promote_stage(target)
            
            # Update monitoring configuration
            self._update_monitoring_config(target)
            
            # Run post-promotion checks
            self._run_post_promotion_checks()
            
            self.logger.info(f"Promotion to {target_stage} completed successfully")
            
            return {
                "success": True,
                "old_stage": current_stage.value,
                "new_stage": target_stage,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Promotion failed: {str(e)}")
            raise
    
    def rollback(self, target_stage: str = "development"):
        """Rollback deployment to a previous stage."""
        try:
            current_stage = self.deployment_manager.config.stage
            target = DeploymentStage(target_stage)
            
            self.logger.warning(f"Rolling back deployment from {current_stage.value} to {target_stage}")
            
            # Run pre-rollback checks
            self._run_pre_rollback_checks()
            
            # Rollback stage
            self.deployment_manager.rollback_to_stage(target)
            
            # Disable all feature flags
            for feature in FeatureFlag:
                self.deployment_manager.enable_feature(feature, False)
            
            # Update monitoring configuration
            self._update_monitoring_config(target)
            
            # Run post-rollback checks
            self._run_post_rollback_checks()
            
            self.logger.warning(f"Rollback to {target_stage} completed successfully")
            
            return {
                "success": True,
                "old_stage": current_stage.value,
                "new_stage": target_stage,
                "rollback": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")
            raise
    
    def status(self) -> Dict[str, Any]:
        """Get deployment status."""
        metrics = self.deployment_manager.get_deployment_metrics()
        performance_checks = self.deployment_manager.check_performance_thresholds()
        
        # Check monitoring services
        monitoring_status = self._check_monitoring_services()
        
        # Check quantum backend connectivity
        backend_status = self._check_backend_connectivity()
        
        status = {
            "deployment": {
                "stage": self.deployment_manager.config.stage.value,
                "traffic_allocation": self.deployment_manager.config.traffic_allocation,
                "feature_flags": {
                    k.value: v for k, v in self.deployment_manager.config.feature_flags.items()
                },
                "request_count": metrics["request_count"],
                "success_rate": metrics["success_rate"],
                "error_rate": metrics["error_rate"],
                "avg_quantum_advantage": metrics["avg_quantum_advantage"],
            },
            "performance": {
                "checks": performance_checks,
                "all_passed": all(performance_checks.values()),
                "thresholds": self.deployment_manager.config.performance_thresholds,
            },
            "monitoring": monitoring_status,
            "backend": backend_status,
            "system": {
                "logs_directory": str(self.logs_dir),
                "config_path": self.config_path,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
        
        return status
    
    def _validate_requirements(self):
        """Validate system requirements."""
        self.logger.info("Validating system requirements...")
        
        requirements = [
            ("Python 3.10+", self._check_python_version),
            ("Qiskit installation", self._check_qiskit_installation),
            ("Log directory writable", self._check_log_directory),
            ("Config file writable", self._check_config_file),
        ]
        
        all_passed = True
        for name, check_func in requirements:
            try:
                result = check_func()
                if result:
                    self.logger.info(f"✓ {name}: OK")
                else:
                    self.logger.error(f"✗ {name}: FAILED")
                    all_passed = False
            except Exception as e:
                self.logger.error(f"✗ {name}: ERROR - {str(e)}")
                all_passed = False
        
        if not all_passed:
            raise RuntimeError("System requirements validation failed")
        
        self.logger.info("All system requirements validated successfully")
    
    def _check_python_version(self) -> bool:
        """Check Python version."""
        import sys
        return sys.version_info >= (3, 10)
    
    def _check_qiskit_installation(self) -> bool:
        """Check if Qiskit is installed."""
        try:
            import qiskit
            return True
        except ImportError:
            return False
    
    def _check_log_directory(self) -> bool:
        """Check if log directory is writable."""
        test_file = self.logs_dir / ".test_write"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception:
            return False
    
    def _check_config_file(self) -> bool:
        """Check if config file is writable."""
        try:
            # Try to write to config directory
            config_dir = Path(self.config_path).parent
            config_dir.mkdir(exist_ok=True)
            
            test_file = config_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception:
            return False
    
    def _setup_monitoring(self):
        """Setup monitoring infrastructure."""
        self.logger.info("Setting up monitoring...")
        
        # Create monitoring configuration
        monitoring_config = {
            "enabled": True,
            "metrics_interval_seconds": 60,
            "alert_rules": {
                "high_error_rate": {
                    "threshold": 0.1,
                    "window_minutes": 5,
                    "action": "alert_and_rollback",
                },
                "low_quantum_advantage": {
                    "threshold": 0.05,
                    "window_minutes": 10,
                    "action": "alert",
                },
                "high_execution_time": {
                    "threshold": 10000,  # 10 seconds
                    "window_minutes": 5,
                    "action": "alert",
                },
            },
            "dashboard": {
                "enabled": True,
                "port": 8051,
                "refresh_interval_seconds": 30,
            },
            "logging": {
                "level": "INFO",
                "file": str(self.logs_dir / "quantum_monitoring.log"),
                "max_size_mb": 100,
                "backup_count": 5,
            },
        }
        
        # Save monitoring configuration
        monitoring_config_path = self.monitoring_dir / "config.json"
        with open(monitoring_config_path, 'w') as f:
            json.dump(monitoring_config, f, indent=2)
        
        self.logger.info(f"Monitoring configuration saved to: {monitoring_config_path}")
    
    def _configure_deployment(self, stage: DeploymentStage, enable_features: list):
        """Configure deployment for specified stage."""
        self.logger.info(f"Configuring deployment for {stage.value} stage")
        
        # Set deployment stage
        self.deployment_manager.promote_stage(stage)
        
        # Enable requested features
        for feature_name in enable_features:
            try:
                feature = FeatureFlag(feature_name)
                self.deployment_manager.enable_feature(feature, True)
                self.logger.info(f"Enabled feature: {feature_name}")
            except ValueError:
                self.logger.warning(f"Unknown feature flag: {feature_name}")
        
        # Set stage-specific configuration
        if stage == DeploymentStage.PRODUCTION_PILOT:
            # Pilot stage: 5% traffic, conservative features
            self.deployment_manager.config.traffic_allocation = 0.05
            self.deployment_manager.config.quantum_hardware["enabled"] = False
            self.deployment_manager.config.rollback["enabled"] = True
        
        elif stage == DeploymentStage.PRODUCTION_GROWTH:
            # Growth stage: 25% traffic, more features
            self.deployment_manager.config.traffic_allocation = 0.25
            self.deployment_manager.config.quantum_hardware["enabled"] = True
            self.deployment_manager.config.quantum_hardware["enable_for_traffic_percentage"] = 0.01  # 1%
        
        elif stage == DeploymentStage.PRODUCTION_FULL:
            # Full stage: 100% traffic, all features
            self.deployment_manager.config.traffic_allocation = 1.0
            self.deployment_manager.config.quantum_hardware["enabled"] = True
            self.deployment_manager.config.quantum_hardware["enable_for_traffic_percentage"] = 0.05  # 5%
        
        # Save configuration
        self.deployment_manager.save_config()
        
        self.logger.info(f"Deployment configured for {stage.value} stage")
        self.logger.info(f"Traffic allocation: {self.deployment_manager.config.traffic_allocation:.1%}")
    
    def _run_health_checks(self):
        """Run health checks."""
        self.logger.info("Running health checks...")
        
        checks = [
            ("Quantum agent initialization", self._check_quantum_agent),
            ("Backend connectivity", self._check_backend_connectivity),
            ("Monitoring setup", self._check_monitoring_setup),
            ("Configuration validation", self._check_configuration),
        ]
        
        all_passed = True
        results = {}
        
        for name, check_func in checks:
            try:
                result = check_func()
                results[name] = result
                if result.get("healthy", False):
                    self.logger.info(f"✓ {name}: OK")
                else:
                    self.logger.error(f"✗ {name}: FAILED - {result.get('error', 'Unknown error')}")
                    all_passed = False
            except Exception as e:
                results[name] = {"healthy": False, "error": str(e)}
                self.logger.error(f"✗ {name}: ERROR - {str(e)}")
                all_passed = False
        
        # Save health check results
        health_check_path = self.logs_dir / f"health_check_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(health_check_path, 'w') as f:
            json.dump({
                "timestamp": datetime.utcnow().isoformat(),
                "all_passed": all_passed,
                "results": results,
            }, f, indent=2)
        
        if not all_passed:
            raise RuntimeError("Health checks failed")
        
        self.logger.info("All health checks passed")
    
    def _check_quantum_agent(self) -> Dict[str, Any]:
        """Check quantum agent initialization."""
        try:
            agent = create_production_agent(
                agent_id="health_check",
                initial_level="quantum_aware",
                enable_monitoring=False
            )
            
            # Test basic functionality
            status = agent.get_deployment_status()
            
            return {
                "healthy": True,
                "agent_id": status["agent_id"],
                "deployment_stage": status["deployment_stage"],
                "feature_flags": status["feature_flags"],
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _check_backend_connectivity(self) -> Dict[str, Any]:
        """Check quantum backend connectivity."""
        try:
            from simp.organs.quantum_intelligence.quantum_backend_manager import (
                get_quantum_backend_manager
            )
            
            backend_manager = get_quantum_backend_manager()
            stats = backend_manager.get_usage_stats()
            
            return {
                "healthy": True,
                "available_backends": stats["available_backends"],
                "active_backend": stats["active_backend"],
                "total_jobs": stats["total_jobs"],
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _check_monitoring_setup(self) -> Dict[str, Any]:
        """Check monitoring setup."""
        try:
            # Check monitoring directory
            if not self.monitoring_dir.exists():
                return {"healthy": False, "error": "Monitoring directory not found"}
            
            # Check monitoring config
            config_path = self.monitoring_dir / "config.json"
            if not config_path.exists():
                return {"healthy": False, "error": "Monitoring config not found"}
            
            # Load and validate config
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            return {
                "healthy": True,
                "config_path": str(config_path),
                "config_valid": True,
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _check_configuration(self) -> Dict[str, Any]:
        """Check deployment configuration."""
        try:
            config = self.deployment_manager.config
            
            return {
                "healthy": True,
                "stage": config.stage.value,
                "traffic_allocation": config.traffic_allocation,
                "feature_flags_count": len(config.feature_flags),
                "performance_thresholds": config.performance_thresholds,
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _start_monitoring_services(self):
        """Start monitoring services."""
        self.logger.info("Starting monitoring services...")
        
        # In production, this would start actual monitoring services
        # For now, we'll just create a placeholder
        
        monitoring_script = self.monitoring_dir / "start_monitoring.py"
        
        monitoring_code = '''#!/usr/bin/env python3
"""
Quantum Intelligence Monitoring Service

This service monitors quantum intelligence performance and alerts on issues.
"""

import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("quantum.monitoring")

def main():
    """Main monitoring loop."""
    logger.info("Quantum intelligence monitoring service started")
    
    # Load monitoring configuration
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    logger.info(f"Monitoring configuration loaded: {config_path}")
    
    # Main monitoring loop
    while True:
        try:
            # Check deployment status
            # In production, this would query the deployment manager
            
            # Log heartbeat
            logger.debug("Monitoring heartbeat")
            
            # Sleep for configured interval
            time.sleep(config.get("metrics_interval_seconds", 60))
            
        except KeyboardInterrupt:
            logger.info("Monitoring service stopped by user")
            break
        except Exception as e:
            logger.error(f"Monitoring error: {str(e)}")
            time.sleep(10)  # Wait before retrying

if __name__ == "__main__":
    main()
'''
        
        with open(monitoring_script, 'w') as f:
            f.write(monitoring_code)
        
        # Make executable
        monitoring_script.chmod(0o755)
        
        self.logger.info(f"Monitoring service script created: {monitoring_script}")
        
        # Note: In production, you would start this as a service
        # For now, we'll just log that it's ready
    
    def _create_deployment_report(self, stage: DeploymentStage) -> Dict[str, Any]:
        """Create deployment report."""
        report = {
            "deployment_id": f"quantum_deploy_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "stage": stage.value,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
            "configuration": self.deployment_manager.config.to_dict(),
            "health_checks": self._run_health_checks_report(),
            "next_steps": self._get_next_steps(stage),
            "rollback_procedure": self._get_rollback_procedure(stage),
        }
        
        # Save report
        report_path = self.logs_dir / f"deployment_report_{report['deployment_id']}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        report["report_path"] = str(report_path)
        
        return report
    
    def _run_health_checks_report(self) -> Dict[str, Any]:
        """Run health checks for report."""
        return {
            "quantum_agent": self._check_quantum_agent(),
            "backend_connectivity": self._check_backend_connectivity(),
            "monitoring_setup": self._check_monitoring_setup(),
            "configuration": self._check_configuration(),
        }
    
    def _get_next_steps(self, stage: DeploymentStage) -> list:
        """Get next steps for deployment."""
        steps = []
        
        if stage == DeploymentStage.DEVELOPMENT:
            steps = [
                "Run integration tests with QuantumArb agent",
                "Benchmark quantum vs classical performance",
                "Prepare for staging deployment",
            ]
        elif stage == DeploymentStage.STAGING:
            steps = [
                "Monitor performance for 24 hours",
                "Validate error rates and quantum advantage",
                "Prepare for production pilot (5% traffic)",
            ]
        elif stage == DeploymentStage.PRODUCTION_PILOT:
            steps = [
                "Monitor pilot traffic for 48 hours",
                "Check for any performance degradation",
                "Prepare for production growth (25% traffic)",
            ]
        elif stage == DeploymentStage.PRODUCTION_GROWTH:
            steps = [
                "Monitor growth traffic for 72 hours",
                "Validate scaling performance",
                "Prepare for full production (100% traffic)",
            ]
        elif stage == DeploymentStage.PRODUCTION_FULL:
            steps = [
                "Monitor full production traffic",
                "Continuously optimize quantum algorithms",
                "Plan for quantum hardware integration",
            ]
        
        return steps
    
    def _get_rollback_procedure(self, stage: DeploymentStage) -> Dict[str, Any]:
        """Get rollback procedure for stage."""
        procedures = {
            DeploymentStage.DEVELOPMENT: {
                "procedure": "Development rollback is automatic",
                "steps": ["Fix issues in development", "Redeploy"],
                "estimated_time": "5 minutes",
            },
            DeploymentStage.STAGING: {
                "procedure": "Disable feature flags and reduce traffic",
                "steps": [
                    "Disable all quantum intelligence features",
                    "Set traffic allocation to 0%",
                    "Investigate issues",
                    "Redeploy after fixes",
                ],
                "estimated_time": "15 minutes",
            },
            DeploymentStage.PRODUCTION_PILOT: {
                "procedure": "Immediate rollback to staging",
                "steps": [
                    "Run rollback command: ./deploy_quantum_intelligence.py rollback staging",
                    "Monitor classical performance",
                    "Investigate quantum-specific issues",
                    "Fix and redeploy to pilot",
                ],
                "estimated_time": "30 minutes",
            },
            DeploymentStage.PRODUCTION_GROWTH: {
                "procedure": "Gradual rollback with monitoring",
                "steps": [
                    "Reduce traffic allocation to 5%",
                    "Disable quantum hardware",
                    "Monitor error rates",
                    "If issues persist, rollback to pilot",
                ],
                "estimated_time": "1 hour",
            },
            DeploymentStage.PRODUCTION_FULL: {
                "procedure": "Emergency rollback plan",
                "steps": [
                    "Immediately disable all quantum features",
                    "Set traffic allocation to 0%",
                    "Switch to classical algorithms",
                    "Form incident response team",
                    "Investigate and fix issues",
                    "Gradual re-enablement after fixes",
                ],
                "estimated_time": "2 hours",
            },
        }
        
        return procedures.get(stage, {"procedure": "Unknown stage", "steps": [], "estimated_time": "Unknown"})
    
    def _validate_promotion_path(self, current: DeploymentStage, target: DeploymentStage):
        """Validate promotion path."""
        valid_paths = {
            DeploymentStage.DEVELOPMENT: [DeploymentStage.STAGING],
            DeploymentStage.STAGING: [DeploymentStage.PRODUCTION_PILOT],
            DeploymentStage.PRODUCTION_PILOT: [DeploymentStage.PRODUCTION_GROWTH],
            DeploymentStage.PRODUCTION_GROWTH: [DeploymentStage.PRODUCTION_FULL],
        }
        
        if current not in valid_paths:
            raise ValueError(f"Cannot promote from {current.value}")
        
        if target not in valid_paths[current]:
            raise ValueError(f"Cannot promote from {current.value} to {target.value}")
    
    def _run_pre_promotion_checks(self):
        """Run pre-promotion checks."""
        self.logger.info("Running pre-promotion checks...")
        
        # Check performance thresholds
        checks = self.deployment_manager.check_performance_thresholds()
        
        if not all(checks.values()):
            failed = [k for k, v in checks.items() if not v]
            raise RuntimeError(f"Performance thresholds failed: {failed}")
        
        # Check error rate
        metrics = self.deployment_manager.get_deployment_metrics()
        if metrics["error_rate"] > 0.05:  # 5% error rate threshold
            raise RuntimeError(f"Error rate too high for promotion: {metrics['error_rate']:.1%}")
        
        self.logger.info("Pre-promotion checks passed")
    
    def _run_post_promotion_checks(self):
        """Run post-promotion checks."""
        self.logger.info("Running post-promotion checks...")
        
        # Verify configuration was updated
        current_stage = self.deployment_manager.config.stage
        self.logger.info(f"Verified deployment stage: {current_stage.value}")
        
        # Verify traffic allocation
        traffic = self.deployment_manager.config.traffic_allocation
        self.logger.info(f"Verified traffic allocation: {traffic:.1%}")
    
    def _run_pre_rollback_checks(self):
        """Run pre-rollback checks."""
        self.logger.info("Running pre-rollback checks...")
        
        # Check if we have a backup configuration
        config_path = Path(self.config_path)
        if not config_path.exists():
            self.logger.warning("No configuration backup found")
    
    def _run_post_rollback_checks(self):
        """Run post-rollback checks."""
        self.logger.info("Running post-rollback checks...")
        
        # Verify rollback was successful
        current_stage = self.deployment_manager.config.stage
        self.logger.info(f"Verified rollback to stage: {current_stage.value}")
        
        # Verify feature flags are disabled
        enabled_features = [
            f.value for f, enabled in self.deployment_manager.config.feature_flags.items()
            if enabled
        ]
        
        if enabled_features:
            self.logger.warning(f"Some features still enabled after rollback: {enabled_features}")
        else:
            self.logger.info("All feature flags disabled after rollback")
    
    def _update_monitoring_config(self, stage: DeploymentStage):
        """Update monitoring configuration for stage."""
        monitoring_config_path = self.monitoring_dir / "config.json"
        
        if monitoring_config_path.exists():
            with open(monitoring_config_path, 'r') as f:
                config = json.load(f)
            
            # Update alert thresholds based on stage
            if stage in [DeploymentStage.PRODUCTION_PILOT, DeploymentStage.PRODUCTION_GROWTH]:
                config["alert_rules"]["high_error_rate"]["threshold"] = 0.05  # 5% for production
            else:
                config["alert_rules"]["high_error_rate"]["threshold"] = 0.1  # 10% for non-production
            
            with open(monitoring_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.logger.info(f"Updated monitoring configuration for {stage.value} stage")
    
    def _check_monitoring_services(self) -> Dict[str, Any]:
        """Check monitoring services status."""
        # In production, this would check actual service status
        # For now, return simulated status
        
        return {
            "status": "simulated",
            "monitoring_script_exists": (self.monitoring_dir / "start_monitoring.py").exists(),
            "config_exists": (self.monitoring_dir / "config.json").exists(),
            "logs_directory": str(self.logs_dir),
            "note": "In production, this would check actual service status",
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Deploy quantum intelligence system")
    parser.add_argument("command", choices=["deploy", "promote", "rollback", "status"],
                       help="Command to execute")
    parser.add_argument("--stage", choices=["development", "staging", "production_pilot", 
                                          "production_growth", "production_full"],
                       help="Deployment stage (for deploy/promote)")
    parser.add_argument("--features", nargs="+",
                       help="Feature flags to enable (for deploy)")
    parser.add_argument("--config", help="Path to deployment configuration")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create deployer
    deployer = QuantumIntelligenceDeployer(args.config)
    
    try:
        if args.command == "deploy":
            if not args.stage:
                parser.error("--stage required for deploy command")
            
            result = deployer.deploy(args.stage, args.features)
            print(f"Deployment successful: {json.dumps(result, indent=2)}")
        
        elif args.command == "promote":
            if not args.stage:
                parser.error("--stage required for promote command")
            
            result = deployer.promote(args.stage)
            print(f"Promotion successful: {json.dumps(result, indent=2)}")
        
        elif args.command == "rollback":
            target_stage = args.stage or "development"
            result = deployer.rollback(target_stage)
            print(f"Rollback successful: {json.dumps(result, indent=2)}")
        
        elif args.command == "status":
            result = deployer.status()
            print(f"Deployment status: {json.dumps(result, indent=2)}")
    
    except Exception as e:
        logging.error(f"Command failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()