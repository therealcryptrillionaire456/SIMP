#!/usr/bin/env python3
"""
Quantum Mode Engine for Stray Goose

Main orchestrator that implements the retrieval-first quantum mode workflow:
1. Query classification
2. Dataset retrieval
3. Verification
4. ProjectX judgment (if needed)
5. Execution with safety checks
6. Learning signal generation
"""

import json
import sys
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from quantum_mode_schema import (
    TaskType, VerificationStatus, QuantumErrorCode, Severity,
    TraceStep, TraceStatus, QuantumTask, RetrievalResult,
    VerificationResult, ProjectXJudgment, QuantumTrace,
    LearningSignal, PredictiveRiskScore, QuantumModeConfig
)
from quantum_trace_logger import QuantumTraceLogger
from predictive_risk_scorer import PredictiveRiskScorer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class QuantumModeEngine:
    """Main engine for Quantum Mode operations."""
    
    config_path: Optional[Path] = None
    dataset_dir: Optional[Path] = None
    projectx_endpoint: Optional[str] = None
    enable_learning: bool = True
    enable_risk_scoring: bool = True
    
    # Internal components
    _config: QuantumModeConfig = field(init=False)
    _trace_logger: QuantumTraceLogger = field(init=False)
    _risk_scorer: PredictiveRiskScorer = field(init=False)
    _dataset_manager: Any = field(init=False)  # Will be QuantumDatasetManager
    _executor: Any = field(init=False)  # Will be QuantumExecutor
    _projectx_client: Any = field(init=False)  # Will be ProjectXIntegration
    
    def __post_init__(self):
        """Initialize all components."""
        # Load configuration
        self._config = QuantumModeConfig(self.config_path)
        
        # Initialize trace logger
        log_dir = Path("data/quantum_traces") if self.dataset_dir is None else self.dataset_dir / "traces"
        self._trace_logger = QuantumTraceLogger(log_dir)
        
        # Initialize risk scorer
        self._risk_scorer = PredictiveRiskScorer(self.config_path)
        
        # Initialize dataset manager
        from quantum_dataset_manager import QuantumDatasetManager
        self._dataset_manager = QuantumDatasetManager(
            dataset_dir=self.dataset_dir,
            config=self._config
        )
        
        # Initialize executor
        from quantum_executor import QuantumExecutor
        self._executor = QuantumExecutor(
            config=self._config,
            trace_logger=self._trace_logger
        )
        
        # Initialize ProjectX client if endpoint provided
        if self.projectx_endpoint:
            from projectx_integration import ProjectXIntegration
            self._projectx_client = ProjectXIntegration(self.projectx_endpoint)
        else:
            self._projectx_client = None
    
    def process_query(self, query: str, context: Optional[Dict] = None) -> Dict:
        """
        Main entry point for processing a quantum query.
        
        Args:
            query: User query string
            context: Optional context dictionary
            
        Returns:
            Dictionary with processing results
        """
        # Start trace
        trace = self._trace_logger.start_trace(
            task_id=f"query_{hashlib.sha256(query.encode()).hexdigest()[:16]}",
            step=TraceStep.CLASSIFICATION.value,
            query=query,
            context=context or {},
            source="quantum_mode_engine"
        )
        
        try:
            # Step 1: Classify query
            is_quantum, confidence = self._config.is_quantum_query(query)
            if not is_quantum:
                # Not a quantum query - exit quantum mode
                self._trace_logger.fail_trace(
                    trace_id=trace.trace_id,
                    error_code=QuantumErrorCode.QMODE_DETECTION_FALSE_POSITIVE.value,
                    error_message="Query not quantum-related",
                    severity=Severity.LOW.value,
                    step=TraceStep.CLASSIFICATION.value
                )
                return {
                    "success": False,
                    "error": "Not a quantum query",
                    "error_code": QuantumErrorCode.QMODE_DETECTION_FALSE_POSITIVE.value,
                    "should_exit_quantum_mode": True
                }
            
            # Update trace with classification
            trace.update(
                classification_confidence=confidence,
                task_type=TaskType.QUANTUM_ALGORITHM.value  # Default, will be refined
            )
            
            # Step 2: Create quantum task
            classification = self._classify_task_type(query, confidence)
            task = QuantumTask.from_query(query, classification)
            trace.update(task_id=task.task_id)
            
            # Step 3: Risk assessment
            if self.enable_risk_scoring:
                risk_data = {
                    "query": query,
                    "task_type": task.task_type,
                    "confidence": confidence,
                    "context": context or {},
                    "trace_id": trace.trace_id
                }
                risk_assessment = self._risk_scorer.assess_task_risk(risk_data)
                trace.update(risk_assessment=risk_assessment.to_dict())
                
                # Check if risk is too high
                if risk_assessment.risk_band in ["HIGH", "CRITICAL"]:
                    self._trace_logger.block_trace(
                        trace_id=trace.trace_id,
                        reason=f"High risk detected: {risk_assessment.risk_band}",
                        risk_assessment=risk_assessment.to_dict(),
                        step=TraceStep.RISK_ASSESSMENT.value
                    )
                    return {
                        "success": False,
                        "error": "Task blocked due to high risk",
                        "risk_band": risk_assessment.risk_band,
                        "recommendations": risk_assessment.recommendations
                    }
            
            # Step 4: Dataset retrieval
            retrieval_result = self._dataset_manager.retrieve_examples(
                query=query,
                task_type=task.task_type,
                confidence_threshold=self._config.get_confidence_level(confidence)
            )
            trace.update(retrieval_result=retrieval_result.to_dict())
            
            if not retrieval_result.has_verified_examples():
                # No verified examples found
                self._trace_logger.fail_trace(
                    trace_id=trace.trace_id,
                    error_code=QuantumErrorCode.QMODE_RETRIEVAL_EMPTY.value,
                    error_message="No verified examples found",
                    severity=Severity.MEDIUM.value,
                    step=TraceStep.RETRIEVAL.value,
                    retrieval_result=retrieval_result.to_dict()
                )
                return {
                    "success": False,
                    "error": "No verified examples found",
                    "error_code": QuantumErrorCode.QMODE_RETRIEVAL_EMPTY.value,
                    "retrieval_result": retrieval_result.to_dict()
                }
            
            # Step 5: Verification
            verification_result = self._dataset_manager.verify_examples(
                retrieval_result=retrieval_result,
                task_type=task.task_type
            )
            trace.update(verification_result=verification_result.to_dict())
            
            if not verification_result.passed():
                # Verification failed
                self._trace_logger.escalate_trace(
                    trace_id=trace.trace_id,
                    reason="Verification failed",
                    verification_result=verification_result.to_dict(),
                    step=TraceStep.VERIFICATION.value
                )
                
                # Check if we should consult ProjectX
                if self._projectx_client and verification_result.should_escalate():
                    projectx_result = self._consult_projectx(
                        query=query,
                        task=task,
                        retrieval_result=retrieval_result,
                        verification_result=verification_result,
                        trace_id=trace.trace_id
                    )
                    
                    if projectx_result.get("approved", False):
                        # ProjectX approved - continue with execution
                        trace.update(projectx_judgment=projectx_result)
                    else:
                        # ProjectX rejected - block
                        return {
                            "success": False,
                            "error": "Task rejected by ProjectX",
                            "projectx_result": projectx_result,
                            "should_block": True
                        }
                else:
                    # Block without ProjectX consultation
                    return {
                        "success": False,
                        "error": "Verification failed",
                        "verification_result": verification_result.to_dict(),
                        "should_block": True
                    }
            
            # Step 6: Execution
            execution_result = self._executor.execute(
                task=task,
                retrieval_result=retrieval_result,
                verification_result=verification_result,
                trace_id=trace.trace_id
            )
            trace.update(execution_result=execution_result)
            
            # Step 7: Complete trace
            self._trace_logger.complete_trace(
                trace_id=trace.trace_id,
                success=True,
                execution_result=execution_result,
                step=TraceStep.EXECUTION.value
            )
            
            # Step 8: Generate learning signal
            if self.enable_learning:
                self._generate_learning_signal(
                    task=task,
                    retrieval_result=retrieval_result,
                    verification_result=verification_result,
                    execution_result=execution_result,
                    trace_id=trace.trace_id
                )
            
            return {
                "success": True,
                "task": task.to_dict(),
                "retrieval_result": retrieval_result.to_dict(),
                "verification_result": verification_result.to_dict(),
                "execution_result": execution_result,
                "trace_id": trace.trace_id
            }
            
        except Exception as e:
            # Log unexpected error
            logger.error(f"Error processing quantum query: {e}", exc_info=True)
            self._trace_logger.fail_trace(
                trace_id=trace.trace_id,
                error_code=QuantumErrorCode.QMODE_UNEXPECTED_ERROR.value,
                error_message=str(e),
                severity=Severity.HIGH.value,
                step=TraceStep.UNKNOWN.value
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_code": QuantumErrorCode.QMODE_UNEXPECTED_ERROR.value,
                "should_block": True
            }
    
    def _classify_task_type(self, query: str, confidence: float) -> Dict:
        """Classify the task type from query."""
        # Simple keyword-based classification
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["algorithm", "implementation", "code", "program"]):
            return {
                "task_type": TaskType.QUANTUM_ALGORITHM.value,
                "confidence": confidence,
                "keywords": ["algorithm", "implementation"]
            }
        elif any(word in query_lower for word in ["circuit", "gate", "qasm", "qiskit"]):
            return {
                "task_type": TaskType.QUANTUM_CIRCUIT.value,
                "confidence": confidence,
                "keywords": ["circuit", "gate"]
            }
        elif any(word in query_lower for word in ["simulation", "simulate", "state", "vector"]):
            return {
                "task_type": TaskType.QUANTUM_SIMULATION.value,
                "confidence": confidence,
                "keywords": ["simulation", "simulate"]
            }
        elif any(word in query_lower for word in ["error", "correction", "noise", "mitigation"]):
            return {
                "task_type": TaskType.QUANTUM_ERROR_CORRECTION.value,
                "confidence": confidence,
                "keywords": ["error", "correction"]
            }
        else:
            return {
                "task_type": TaskType.QUANTUM_ALGORITHM.value,  # Default
                "confidence": confidence * 0.8,  # Lower confidence for generic
                "keywords": ["generic"]
            }
    
    def _consult_projectx(self, query: str, task: QuantumTask, 
                         retrieval_result: RetrievalResult,
                         verification_result: VerificationResult,
                         trace_id: str) -> Dict:
        """Consult ProjectX for judgment."""
        if not self._projectx_client:
            return {"approved": False, "reason": "ProjectX not available"}
        
        try:
            judgment = self._projectx_client.request_judgment(
                query=query,
                task=task,
                retrieval_result=retrieval_result,
                verification_result=verification_result,
                trace_id=trace_id
            )
            
            # Log ProjectX consultation
            self._trace_logger.update_trace(
                trace_id=trace_id,
                projectx_consultation=judgment,
                step=TraceStep.PROJECTX_CONSULTATION.value
            )
            
            return judgment
            
        except Exception as e:
            logger.error(f"Error consulting ProjectX: {e}")
            return {
                "approved": False,
                "reason": f"ProjectX consultation failed: {str(e)}"
            }
    
    def _generate_learning_signal(self, task: QuantumTask,
                                 retrieval_result: RetrievalResult,
                                 verification_result: VerificationResult,
                                 execution_result: Dict,
                                 trace_id: str):
        """Generate learning signal for model improvement."""
        try:
            # Determine if this was a positive or negative example
            success = execution_result.get("success", False)
            quality_score = execution_result.get("quality_score", 0.5)
            
            if success and quality_score > 0.7:
                # Positive learning signal
                signal = LearningSignal.positive(
                    task_type=task.task_type,
                    query_hash=hashlib.sha256(task.query.encode()).hexdigest()[:16],
                    retrieval_examples=retrieval_result.examples,
                    verification_score=verification_result.overall_score,
                    execution_quality=quality_score,
                    trace_id=trace_id
                )
            else:
                # Negative learning signal
                signal = LearningSignal.negative(
                    task_type=task.task_type,
                    query_hash=hashlib.sha256(task.query.encode()).hexdigest()[:16],
                    retrieval_examples=retrieval_result.examples,
                    verification_score=verification_result.overall_score,
                    execution_quality=quality_score,
                    trace_id=trace_id
                )
            
            # Log learning signal
            self._trace_logger._log_learning_signal(signal)
            
        except Exception as e:
            logger.error(f"Error generating learning signal: {e}")
    
    def get_metrics(self) -> Dict:
        """Get engine metrics."""
        return {
            "traces": self._trace_logger.get_session_metrics(),
            "risk_profile": self._risk_scorer._get_current_risk_profile(),
            "dataset_stats": self._dataset_manager.get_stats() if hasattr(self._dataset_manager, 'get_stats') else {},
            "config": self._config.load_config(self.config_path) if self.config_path else {}
        }
    
    def export_training_data(self, output_dir: Optional[Path] = None) -> Dict:
        """Export training data for model improvement."""
        trace_data = self._trace_logger.export_training_data(output_dir)
        risk_data = self._risk_scorer.export_risk_data(output_dir)
        
        return {
            "traces": trace_data,
            "risk_assessments": risk_data,
            "timestamp": datetime.now().isoformat()
        }


def main():
    """Command-line interface for Quantum Mode Engine."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quantum Mode Engine for Stray Goose")
    parser.add_argument("query", help="Quantum query to process")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--dataset-dir", help="Path to dataset directory")
    parser.add_argument("--projectx-endpoint", help="ProjectX endpoint URL")
    parser.add_argument("--no-learning", action="store_true", help="Disable learning signals")
    parser.add_argument("--no-risk", action="store_true", help="Disable risk scoring")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize engine
    engine = QuantumModeEngine(
        config_path=Path(args.config) if args.config else None,
        dataset_dir=Path(args.dataset_dir) if args.dataset_dir else None,
        projectx_endpoint=args.projectx_endpoint,
        enable_learning=not args.no_learning,
        enable_risk_scoring=not args.no_risk
    )
    
    # Process query
    result = engine.process_query(args.query)
    
    # Print result
    print(json.dumps(result, indent=2))
    
    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    sys.exit(main())