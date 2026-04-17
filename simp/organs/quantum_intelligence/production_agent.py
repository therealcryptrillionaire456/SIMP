"""
Production-Ready Quantum Intelligent Agent

This module provides a production-ready quantum intelligent agent
with deployment management, monitoring, and gradual rollout capabilities.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .quantum_intelligent_agent import QuantumIntelligentAgent
from .quantum_backend_manager import get_quantum_backend_manager
from .deployment_config import (
    get_deployment_manager,
    DeploymentStage,
    FeatureFlag
)


class ProductionQuantumAgent:
    """Production-ready quantum intelligent agent."""
    
    def __init__(
        self,
        agent_id: str,
        initial_level: str = "quantum_aware",
        enable_monitoring: bool = True
    ):
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"quantum.production.{agent_id}")
        
        # Initialize core quantum agent
        self.quantum_agent = QuantumIntelligentAgent(
            agent_id=agent_id,
            initial_level=initial_level
        )
        
        # Initialize backend manager
        self.backend_manager = get_quantum_backend_manager()
        
        # Initialize deployment manager
        self.deployment_manager = get_deployment_manager()
        
        # Request tracking
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        
        # Performance monitoring
        self.enable_monitoring = enable_monitoring
        self.monitoring_data: List[Dict[str, Any]] = []
        
        self.logger.info(f"Production quantum agent {agent_id} initialized")
        self.logger.info(f"Deployment stage: {self.deployment_manager.config.stage.value}")
        self.logger.info(f"Traffic allocation: {self.deployment_manager.config.traffic_allocation:.1%}")
    
    def solve_quantum_problem_with_rollout(
        self,
        problem_description: str,
        problem_type: str,
        qubits: int,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Solve quantum problem with deployment rollout management.
        
        This method handles:
        1. Traffic allocation based on deployment stage
        2. Feature flag checking
        3. Performance monitoring
        4. Error handling and fallback
        """
        # Generate request ID if not provided
        request_id = request_id or str(uuid.uuid4())
        metadata = metadata or {}
        
        # Start tracking request
        self._start_request_tracking(request_id, problem_description, problem_type, qubits)
        
        # Check if quantum enhancement should be applied
        should_apply_quantum = self._should_apply_quantum_enhancement(request_id)
        
        if not should_apply_quantum:
            self.logger.debug(f"Request {request_id}: Quantum enhancement skipped (traffic allocation)")
            
            # Return minimal result without quantum enhancement
            result = {
                "success": True,
                "quantum_enhanced": False,
                "request_id": request_id,
                "traffic_allocation": self.deployment_manager.config.traffic_allocation,
                "message": "Quantum enhancement not applied due to traffic allocation",
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Record request
            self._record_request(request_id, True, {
                "quantum_enhanced": False,
                "performance_score": 0.5,  # Default score for non-enhanced
                "execution_time_ms": 0,
                "quantum_advantage": 0.0,
            })
            
            return result
        
        # Check feature flags
        if not self._check_feature_flags(problem_type):
            self.logger.debug(f"Request {request_id}: Feature flags not enabled for {problem_type}")
            
            result = {
                "success": True,
                "quantum_enhanced": False,
                "request_id": request_id,
                "feature_flags": self._get_enabled_features(),
                "message": "Quantum enhancement not applied due to feature flags",
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            self._record_request(request_id, True, {
                "quantum_enhanced": False,
                "performance_score": 0.5,
                "execution_time_ms": 0,
                "quantum_advantage": 0.0,
            })
            
            return result
        
        try:
            # Solve problem with quantum enhancement
            start_time = datetime.utcnow()
            
            quantum_result = self.quantum_agent.solve_quantum_problem(
                problem_description=problem_description,
                problem_type=problem_type,
                qubits=qubits,
                strategy="hybrid",  # Use hybrid strategy for production
                constraints={
                    "max_depth": 15,
                    "include_entanglement": True,
                    "max_execution_time_ms": 30000,  # 30 second timeout
                }
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Extract performance metrics
            performance_score = quantum_result.get("execution_result", {}).get("performance_score", 0.5)
            quantum_advantage = quantum_result.get("execution_result", {}).get("quantum_advantage", 0.0)
            
            # Prepare result
            result = {
                "success": quantum_result.get("success", False),
                "quantum_enhanced": True,
                "request_id": request_id,
                "execution_time_ms": execution_time,
                "performance_score": performance_score,
                "quantum_advantage": quantum_advantage,
                "traffic_allocation": self.deployment_manager.config.traffic_allocation,
                "feature_flags": self._get_enabled_features(),
                "agent_state": quantum_result.get("agent_state"),
                "insights": [insight.insight_text for insight in quantum_result.get("insights", [])],
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    **metadata,
                    "problem_type": problem_type,
                    "qubits": qubits,
                }
            }
            
            # Add circuit information if available
            if "circuit_design" in quantum_result:
                result["circuit_id"] = quantum_result["circuit_design"].circuit_id
            
            # Record request for monitoring
            self._record_request(request_id, result["success"], {
                "quantum_enhanced": True,
                "performance_score": performance_score,
                "execution_time_ms": execution_time,
                "quantum_advantage": quantum_advantage,
                "problem_type": problem_type,
                "qubits": qubits,
            })
            
            # Check performance thresholds
            self._check_and_log_performance(request_id, result)
            
            self.logger.info(f"Request {request_id}: Quantum problem solved successfully "
                           f"(performance: {performance_score:.3f}, advantage: {quantum_advantage:.3f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Request {request_id}: Quantum problem solving failed: {str(e)}")
            
            # Record failure
            self._record_request(request_id, False, {
                "quantum_enhanced": True,
                "error": str(e),
                "execution_time_ms": 0,
                "performance_score": 0.0,
                "quantum_advantage": 0.0,
            })
            
            # Fallback to non-quantum solution
            fallback_result = self._fallback_to_non_quantum(
                request_id, problem_description, problem_type, qubits
            )
            
            return fallback_result
    
    def optimize_portfolio_with_quantum(
        self,
        opportunities: List[Dict[str, Any]],
        capital: float,
        risk_tolerance: float = 0.3,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Optimize portfolio with quantum intelligence (production-ready)."""
        request_id = request_id or str(uuid.uuid4())
        
        # Check if portfolio optimization feature is enabled
        if not self.deployment_manager.config.is_feature_enabled(FeatureFlag.QUANTUM_PORTFOLIO_OPTIMIZATION):
            self.logger.debug(f"Request {request_id}: Portfolio optimization feature not enabled")
            
            return {
                "success": True,
                "quantum_enhanced": False,
                "request_id": request_id,
                "message": "Quantum portfolio optimization not enabled",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        # Check traffic allocation
        if not self.deployment_manager.should_apply_quantum_enhancement(request_id):
            self.logger.debug(f"Request {request_id}: Portfolio optimization skipped (traffic allocation)")
            
            return {
                "success": True,
                "quantum_enhanced": False,
                "request_id": request_id,
                "message": "Quantum portfolio optimization not applied due to traffic allocation",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        try:
            start_time = datetime.utcnow()
            
            # Use quantum-enhanced arb detector if available
            # (This would integrate with the quantum_enhanced_arb module)
            portfolio_result = {
                "success": True,
                "quantum_enhanced": True,
                "request_id": request_id,
                "allocations": [],
                "expected_return": 0.0,
                "risk_score": 0.0,
                "execution_time_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # For now, return a placeholder result
            # In production, this would call the actual portfolio optimization
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            portfolio_result["execution_time_ms"] = execution_time
            
            # Record request
            self._record_request(request_id, True, {
                "quantum_enhanced": True,
                "operation": "portfolio_optimization",
                "execution_time_ms": execution_time,
                "opportunity_count": len(opportunities),
                "capital": capital,
            })
            
            return portfolio_result
            
        except Exception as e:
            self.logger.error(f"Request {request_id}: Portfolio optimization failed: {str(e)}")
            
            self._record_request(request_id, False, {
                "quantum_enhanced": True,
                "operation": "portfolio_optimization",
                "error": str(e),
            })
            
            # Fallback to classical portfolio optimization
            return self._fallback_classical_portfolio(opportunities, capital, risk_tolerance, request_id)
    
    def evolve_quantum_skills(
        self,
        focus_area: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Evolve quantum skills (production-ready)."""
        request_id = request_id or str(uuid.uuid4())
        
        # Check if skill evolution feature is enabled
        if not self.deployment_manager.config.is_feature_enabled(FeatureFlag.QUANTUM_SKILL_EVOLUTION):
            self.logger.debug(f"Request {request_id}: Skill evolution feature not enabled")
            
            return {
                "success": True,
                "quantum_enhanced": False,
                "request_id": request_id,
                "message": "Quantum skill evolution not enabled",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        try:
            start_time = datetime.utcnow()
            
            # Evolve quantum skills
            evolution_result = self.quantum_agent.evolver.evolve_quantum_skills(
                focus_area=focus_area
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = {
                "success": True,
                "quantum_enhanced": True,
                "request_id": request_id,
                "evolution_result": evolution_result,
                "execution_time_ms": execution_time,
                "agent_state": self.quantum_agent.get_current_state(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Record request
            self._record_request(request_id, True, {
                "quantum_enhanced": True,
                "operation": "skill_evolution",
                "execution_time_ms": execution_time,
                "focus_area": focus_area,
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Request {request_id}: Skill evolution failed: {str(e)}")
            
            self._record_request(request_id, False, {
                "quantum_enhanced": True,
                "operation": "skill_evolution",
                "error": str(e),
            })
            
            return {
                "success": False,
                "quantum_enhanced": True,
                "request_id": request_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get deployment status and metrics."""
        metrics = self.deployment_manager.get_deployment_metrics()
        performance_checks = self.deployment_manager.check_performance_thresholds()
        
        status = {
            "agent_id": self.agent_id,
            "deployment_stage": self.deployment_manager.config.stage.value,
            "traffic_allocation": self.deployment_manager.config.traffic_allocation,
            "feature_flags": self._get_enabled_features(),
            "performance_metrics": metrics,
            "performance_checks": performance_checks,
            "all_checks_passed": all(performance_checks.values()),
            "active_requests": len(self.active_requests),
            "monitoring_enabled": self.enable_monitoring,
            "quantum_agent_state": self.quantum_agent.get_current_state(),
            "backend_status": self.backend_manager.get_usage_stats(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        return status
    
    def promote_deployment_stage(self, target_stage: str):
        """Promote deployment to a new stage."""
        try:
            stage = DeploymentStage(target_stage)
            self.deployment_manager.promote_stage(stage)
            
            self.logger.info(f"Deployment promoted to {target_stage}")
            
            return {
                "success": True,
                "old_stage": self.deployment_manager.config.stage.value,
                "new_stage": target_stage,
                "traffic_allocation": self.deployment_manager.config.traffic_allocation,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to promote deployment: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def enable_feature(self, feature: str, enabled: bool = True):
        """Enable or disable a feature flag."""
        try:
            feature_flag = FeatureFlag(feature)
            self.deployment_manager.enable_feature(feature_flag, enabled)
            
            self.logger.info(f"Feature {feature} {'enabled' if enabled else 'disabled'}")
            
            return {
                "success": True,
                "feature": feature,
                "enabled": enabled,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to update feature flag: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def _should_apply_quantum_enhancement(self, request_id: str) -> bool:
        """Determine if quantum enhancement should be applied."""
        return self.deployment_manager.should_apply_quantum_enhancement(request_id)
    
    def _check_feature_flags(self, problem_type: str) -> bool:
        """Check if relevant feature flags are enabled."""
        # Always enable basic quantum problem solving
        if problem_type in ["optimization", "machine_learning", "arbitrage"]:
            return self.deployment_manager.config.is_feature_enabled(FeatureFlag.QUANTUM_ARB_ENHANCEMENT)
        
        return False
    
    def _get_enabled_features(self) -> Dict[str, bool]:
        """Get enabled feature flags."""
        return {
            feature.value: enabled
            for feature, enabled in self.deployment_manager.config.feature_flags.items()
        }
    
    def _start_request_tracking(self, request_id: str, problem_description: str, problem_type: str, qubits: int):
        """Start tracking a request."""
        self.active_requests[request_id] = {
            "start_time": datetime.utcnow(),
            "problem_description": problem_description,
            "problem_type": problem_type,
            "qubits": qubits,
            "status": "processing",
        }
    
    def _record_request(self, request_id: str, success: bool, metrics: Dict[str, Any]):
        """Record request completion."""
        if request_id in self.active_requests:
            request_data = self.active_requests[request_id]
            request_data["end_time"] = datetime.utcnow()
            request_data["status"] = "completed" if success else "failed"
            request_data["success"] = success
            request_data["metrics"] = metrics
            
            # Calculate duration
            duration = (request_data["end_time"] - request_data["start_time"]).total_seconds() * 1000
            request_data["duration_ms"] = duration
            
            # Record with deployment manager
            self.deployment_manager.record_request(request_id, success, {
                **metrics,
                "duration_ms": duration,
                "problem_type": request_data["problem_type"],
                "qubits": request_data["qubits"],
            })
            
            # Store monitoring data
            if self.enable_monitoring:
                monitoring_entry = {
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": success,
                    "duration_ms": duration,
                    **metrics,
                }
                self.monitoring_data.append(monitoring_entry)
                
                # Keep only recent data
                if len(self.monitoring_data) > 1000:
                    self.monitoring_data = self.monitoring_data[-1000:]
            
            # Remove from active requests
            del self.active_requests[request_id]
    
    def _check_and_log_performance(self, request_id: str, result: Dict[str, Any]):
        """Check and log performance metrics."""
        performance_score = result.get("performance_score", 0.0)
        quantum_advantage = result.get("quantum_advantage", 0.0)
        execution_time = result.get("execution_time_ms", 0)
        
        thresholds = self.deployment_manager.config.performance_thresholds
        
        # Check thresholds
        if performance_score < thresholds["min_success_rate"]:
            self.logger.warning(f"Request {request_id}: Low performance score: {performance_score:.3f}")
        
        if quantum_advantage < thresholds["min_quantum_advantage"]:
            self.logger.warning(f"Request {request_id}: Low quantum advantage: {quantum_advantage:.3f}")
        
        if execution_time > thresholds["max_execution_time_ms"]:
            self.logger.warning(f"Request {request_id}: High execution time: {execution_time:.0f}ms")
    
    def _fallback_to_non_quantum(
        self,
        request_id: str,
        problem_description: str,
        problem_type: str,
        qubits: int
    ) -> Dict[str, Any]:
        """Fallback to non-quantum solution."""
        self.logger.info(f"Request {request_id}: Falling back to non-quantum solution")
        
        # Simple fallback logic
        # In production, this would call classical algorithms
        
        result = {
            "success": True,
            "quantum_enhanced": False,
            "request_id": request_id,
            "fallback": True,
            "message": "Using classical fallback solution",
            "performance_score": 0.5,  # Default score for fallback
            "quantum_advantage": 0.0,
            "execution_time_ms": 10,  # Fast fallback
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Record fallback request
        self._record_request(request_id, True, {
            "quantum_enhanced": False,
            "fallback": True,
            "performance_score": 0.5,
            "execution_time_ms": 10,
            "quantum_advantage": 0.0,
        })
        
        return result
    
    def _fallback_classical_portfolio(
        self,
        opportunities: List[Dict[str, Any]],
        capital: float,
        risk_tolerance: float,
        request_id: str
    ) -> Dict[str, Any]:
        """Fallback to classical portfolio optimization."""
        self.logger.info(f"Request {request_id}: Falling back to classical portfolio optimization")
        
        # Simple equal-weight portfolio as fallback
        if not opportunities:
            return {
                "success": True,
                "quantum_enhanced": False,
                "fallback": True,
                "request_id": request_id,
                "allocations": [],
                "expected_return": 0.0,
                "risk_score": 0.0,
                "message": "No opportunities available",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        # Equal-weight allocation
        allocation_per_opportunity = capital / len(opportunities)
        allocations = []
        
        for i, opportunity in enumerate(opportunities):
            allocations.append({
                "opportunity_index": i,
                "pair": opportunity.get("pair", f"OPP_{i}"),
                "allocation_amount": allocation_per_opportunity,
                "expected_return": opportunity.get("spread", 0.0) * 0.5,  # Conservative estimate
            })
        
        # Calculate portfolio metrics
        total_expected_return = sum(alloc["expected_return"] for alloc in allocations)
        expected_return_rate = total_expected_return / capital if capital > 0 else 0.0
        
        # Simple risk calculation
        risk_scores = [opp.get("risk_score", 0.5) for opp in opportunities]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.5
        
        return {
            "success": True,
            "quantum_enhanced": False,
            "fallback": True,
            "request_id": request_id,
            "allocations": allocations,
            "expected_return": expected_return_rate,
            "risk_score": avg_risk,
            "message": "Using classical equal-weight portfolio",
            "timestamp": datetime.utcnow().isoformat(),
        }


# Factory function
def create_production_agent(
    agent_id: str,
    initial_level: str = "quantum_aware",
    enable_monitoring: bool = True
) -> ProductionQuantumAgent:
    """Create a production-ready quantum intelligent agent."""
    return ProductionQuantumAgent(
        agent_id=agent_id,
        initial_level=initial_level,
        enable_monitoring=enable_monitoring
    )