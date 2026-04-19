#!/usr/bin/env python3
"""
Quantum Mode Schema for Stray Goose

Defines the structured schema for Quantum Mode operation based on the JSON specification.
This enforces retrieval-first behavior, verification requirements, and structured tracing.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum

class TaskType(Enum):
    """Types of quantum tasks."""
    QUANTUM_ALGORITHM = "quantum_algorithm"
    QUANTUM_CIRCUIT = "quantum_circuit"
    QUANTUM_SIMULATION = "quantum_simulation"
    QUANTUM_ERROR_CORRECTION = "quantum_error_correction"
    CONCEPT_EXPLANATION = "concept_explanation"
    CODE_GENERATION = "code_generation"
    CODE_DEBUGGING = "code_debugging"
    VERIFICATION_REQUEST = "verification_request"
    BENCHMARK_EVALUATION = "benchmark_evaluation"
    FRAMEWORK_COMPARISON = "framework_comparison"
    OUT_OF_SCOPE_OR_UNSAFE = "out_of_scope_or_unsafe"

class VerificationStatus(Enum):
    """Verification status labels."""
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"

class QuantumErrorCode(Enum):
    """Quantum mode error codes."""
    QMODE_DETECTION_FALSE_POSITIVE = "QMODE_DETECTION_FALSE_POSITIVE"
    QMODE_RETRIEVAL_EMPTY = "QMODE_RETRIEVAL_EMPTY"
    QMODE_RETRIEVAL_LOW_CONFIDENCE = "QMODE_RETRIEVAL_LOW_CONFIDENCE"
    QMODE_FRAMEWORK_UNSUPPORTED = "QMODE_FRAMEWORK_UNSUPPORTED"
    QMODE_FRAMEWORK_MISMATCH = "QMODE_FRAMEWORK_MISMATCH"
    QMODE_TASK_INVALID = "QMODE_TASK_INVALID"
    QMODE_IMPORT_FAILURE = "QMODE_IMPORT_FAILURE"
    QMODE_SYNTAX_ERROR = "QMODE_SYNTAX_ERROR"
    QMODE_SIMULATOR_FAILURE = "QMODE_SIMULATOR_FAILURE"
    QMODE_LOGIC_FAILURE = "QMODE_LOGIC_FAILURE"
    QMODE_PROBABILISTIC_MISMATCH = "QMODE_PROBABILISTIC_MISMATCH"
    QMODE_UNEXPECTED_ERROR = "QMODE_UNEXPECTED_ERROR"
    QMODE_RESOURCE_LIMIT = "QMODE_RESOURCE_LIMIT"
    QMODE_PROJECTX_BLOCK = "QMODE_PROJECTX_BLOCK"
    QMODE_UNKNOWN = "QMODE_UNKNOWN"

class Severity(Enum):
    """Error severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"

class TraceStep(Enum):
    """Trace steps in quantum mode."""
    DETECTION = "detection"
    CLASSIFICATION = "classification"
    RETRIEVAL = "retrieval"
    PROJECTX_EVAL = "projectx_eval"
    GENERATION = "generation"
    VERIFICATION = "verification"
    REWARD = "reward"
    FINALIZE = "finalize"

class TraceStatus(Enum):
    """Trace status values."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    BLOCKED = "blocked"

@dataclass
class QuantumTask:
    """A quantum task with classification and requirements."""
    task_id: str
    task_type: str
    query: str = ""
    algorithm_family: Optional[str] = None
    framework_requested: Optional[str] = None
    framework_used: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    
    @classmethod
    def from_query(cls, query: str, classification: Dict) -> 'QuantumTask':
        """Create a QuantumTask from query and classification."""
        import hashlib
        import time
        
        task_id = f"quantum_{hashlib.md5(query.encode()).hexdigest()[:8]}_{int(time.time())}"
        
        return cls(
            task_id=task_id,
            query=query,
            task_type=classification.get('task_type', TaskType.CONCEPT_EXPLANATION.value),
            algorithm_family=classification.get('algorithm_family'),
            framework_requested=classification.get('framework_requested'),
            parameters=classification.get('parameters', {}),
            required_fields=classification.get('required_fields', [])
        )

@dataclass
class RetrievalResult:
    """Result of quantum example retrieval."""
    query: str
    task_type: str
    success: bool = True
    examples: List[Dict[str, Any]] = field(default_factory=list)
    match_scores: List[float] = field(default_factory=list)
    confidence: float = 0.0
    confidence_level: str = "low"
    retrieval_ids: List[str] = field(default_factory=list)
    retrieval_time: str = ""
    latency_ms: float = 0.0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    def has_verified_examples(self) -> bool:
        """Check if any retrieved examples are verified."""
        return any(example.get('verification', {}).get('verified', False) 
                  for example in self.examples)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

@dataclass
class VerificationResult:
    """Result of quantum code verification."""
    retrieval_result: Optional[RetrievalResult] = None
    overall_score: float = 0.0
    verification_status: str = ""  # VERIFIED, PARTIAL, UNVERIFIED, FAILED
    checks: List[Dict[str, Any]] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
    verification_time: str = ""
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    
    def passed(self) -> bool:
        """Check if verification passed."""
        return self.verification_status == VerificationStatus.VERIFIED.value

@dataclass
class ProjectXJudgment:
    """ProjectX safety judgment."""
    recommendation: str  # ALLOW, BLOCK, ESCALATE
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    referenced_rules: List[str] = field(default_factory=list)
    judgment_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')

@dataclass
class QuantumTrace:
    """Structured trace for quantum mode operations."""
    trace_id: str
    parent_trace_id: Optional[str]
    task_id: str
    session_id: Optional[str]
    timestamp: str
    agent: str = "Stray Goose"
    mode: str = "quantum"
    step: str = TraceStep.DETECTION.value
    status: str = TraceStatus.STARTED.value
    algorithm_family: Optional[str] = None
    framework_requested: Optional[str] = None
    framework_used: Optional[str] = None
    retrieval_hits: int = 0
    retrieval_ids: List[str] = field(default_factory=list)
    verification_status: Optional[str] = None
    error_code: Optional[str] = None
    severity: Optional[str] = None
    latency_ms: Optional[float] = None
    reward: Optional[float] = None
    predictive_risk_score: Optional[float] = None
    notes: Optional[str] = None
    
    @classmethod
    def create(cls, task_id: str, step: str, status: str = TraceStatus.STARTED.value,
               parent_trace_id: Optional[str] = None) -> 'QuantumTrace':
        """Create a new trace."""
        import hashlib
        import time
        
        trace_id = f"trace_{hashlib.md5(f'{task_id}_{step}_{time.time()}'.encode()).hexdigest()[:12]}"
        
        return cls(
            trace_id=trace_id,
            parent_trace_id=parent_trace_id,
            task_id=task_id,
            session_id=None,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            step=step,
            status=status
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def update(self, **kwargs):
        """Update trace fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

@dataclass
class LearningSignal:
    """Learning signal for quantum mode."""
    signal_id: str
    task_id: str
    trace_id: str
    signal_type: str  # positive, negative, corrective
    value: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    
    @classmethod
    def positive(cls, task_id: str, trace_id: str, reason: str, value: float = 1.0,
                 metadata: Optional[Dict] = None) -> 'LearningSignal':
        """Create a positive learning signal."""
        import hashlib
        import time
        
        signal_id = f"signal_{hashlib.md5(f'{task_id}_positive_{time.time()}'.encode()).hexdigest()[:8]}"
        
        return cls(
            signal_id=signal_id,
            task_id=task_id,
            trace_id=trace_id,
            signal_type="positive",
            value=value,
            reason=reason,
            metadata=metadata or {}
        )
    
    @classmethod
    def negative(cls, task_id: str, trace_id: str, reason: str, value: float = -1.0,
                 metadata: Optional[Dict] = None) -> 'LearningSignal':
        """Create a negative learning signal."""
        import hashlib
        import time
        
        signal_id = f"signal_{hashlib.md5(f'{task_id}_negative_{time.time()}'.encode()).hexdigest()[:8]}"
        
        return cls(
            signal_id=signal_id,
            task_id=task_id,
            trace_id=trace_id,
            signal_type="negative",
            value=value,
            reason=reason,
            metadata=metadata or {}
        )

@dataclass
class PredictiveRiskScore:
    """Predictive risk score for quantum tasks."""
    task_id: str
    trace_id: str
    score: float  # 0.0 to 1.0
    risk_band: str  # low, medium, high, critical
    factors: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    
    @classmethod
    def calculate(cls, task_id: str, trace_id: str, factors: List[Dict[str, Any]]) -> 'PredictiveRiskScore':
        """Calculate predictive risk score from factors."""
        score = 0.0
        
        # Score factors based on specification
        factor_scores = {
            'retrieval_empty': 0.30,
            'retrieval_low_confidence': 0.20,
            'framework_mismatch': 0.20,
            'verification_failed': 0.25,
            'projectx_escalated': 0.15,
            'repeated_failure': 0.20,
            'high_latency': 0.10
        }
        
        for factor in factors:
            factor_type = factor.get('type', '')
            if factor_type in factor_scores:
                score += factor_scores[factor_type]
        
        # Cap at 1.0
        score = min(1.0, score)
        
        # Determine risk band
        if score < 0.3:
            risk_band = "low"
        elif score < 0.6:
            risk_band = "medium"
        elif score < 0.8:
            risk_band = "high"
        else:
            risk_band = "critical"
        
        return cls(
            task_id=task_id,
            trace_id=trace_id,
            score=score,
            risk_band=risk_band,
            factors=factors
        )

class QuantumModeConfig:
    """Configuration for Quantum Mode."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self.load_config(config_path)
        
        # Activation rules
        self.quantum_keywords = [
            'quantum', 'qubit', 'superposition', 'entanglement', 'bell state',
            'grover', 'qft', 'quantum fourier', 'deutsch', 'bernstein-vazirani',
            'teleportation', 'vqe', 'qaoa', 'oracle', 'amplitude amplification',
            'phase estimation', 'qiskit', 'pennylane', 'cirq', 'quantum circuit',
            'quantum algorithm', 'quantum simulator', 'quantum framework'
        ]
        
        # Task types requiring retrieval
        self.retrieval_required_for = [
            TaskType.CONCEPT_EXPLANATION.value,
            TaskType.CODE_GENERATION.value,
            TaskType.CODE_DEBUGGING.value,
            TaskType.VERIFICATION_REQUEST.value,
            TaskType.BENCHMARK_EVALUATION.value
        ]
        
        # Task types requiring verification
        self.verification_required_for = [
            TaskType.CODE_GENERATION.value,
            TaskType.CODE_DEBUGGING.value,
            TaskType.VERIFICATION_REQUEST.value,
            TaskType.BENCHMARK_EVALUATION.value
        ]
        
        # Supported frameworks
        self.supported_frameworks = ['qiskit', 'pennylane']
        self.primary_framework = 'qiskit'
        
        # Confidence thresholds
        self.confidence_thresholds = {
            'low': 0.35,
            'medium': 0.6,
            'high': 0.8
        }
        
        # Retry policy
        self.max_retries = 2
        self.retryable_errors = [
            QuantumErrorCode.QMODE_RETRIEVAL_LOW_CONFIDENCE.value,
            QuantumErrorCode.QMODE_FRAMEWORK_MISMATCH.value,
            QuantumErrorCode.QMODE_SYNTAX_ERROR.value,
            QuantumErrorCode.QMODE_PROBABILISTIC_MISMATCH.value
        ]
        
        # Reward values
        self.reward_values = {
            'verified_success': 1.0,
            'partial_success': 0.4,
            'safe_escalation': 0.2,
            'verification_failure': -0.8,
            'unsafe_attempt_without_retrieval': -1.0,
            'projectx_block_respected': 0.1,
            'projectx_block_ignored': -1.0
        }
    
    def load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration from file or use defaults."""
        default_config = {
            'mode_id': 'stray_goose_quantum_mode_v1',
            'mode_name': 'Quantum Mode',
            'safety_posture': 'conservative',
            'trace_sampling_rate': 1.0,  # 100% for quantum mode
            'resource_limits': {
                'max_qubits': 10,
                'max_circuit_depth': 100,
                'max_execution_time_ms': 30000
            }
        }
        
        if config_path and config_path.exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def is_quantum_query(self, query: str) -> Tuple[bool, float]:
        """Check if query is quantum-related and return confidence."""
        query_lower = query.lower()
        
        # Count keyword matches
        matches = 0
        for keyword in self.quantum_keywords:
            if keyword in query_lower:
                matches += 1
        
        if matches == 0:
            return False, 0.0
        
        # Calculate confidence based on matches
        confidence = min(1.0, matches / 3)  # Cap at 1.0
        
        return True, confidence
    
    def requires_retrieval(self, task_type: str) -> bool:
        """Check if task type requires retrieval."""
        return task_type in self.retrieval_required_for
    
    def requires_verification(self, task_type: str) -> bool:
        """Check if task type requires verification."""
        return task_type in self.verification_required_for
    
    def is_supported_framework(self, framework: str) -> bool:
        """Check if framework is supported."""
        return framework.lower() in self.supported_frameworks
    
    def get_confidence_level(self, confidence: float) -> str:
        """Get confidence level name from score."""
        if confidence >= self.confidence_thresholds['high']:
            return 'high'
        elif confidence >= self.confidence_thresholds['medium']:
            return 'medium'
        elif confidence >= self.confidence_thresholds['low']:
            return 'low'
        else:
            return 'very_low'
    
    def is_retryable_error(self, error_code: str) -> bool:
        """Check if error is retryable."""
        return error_code in self.retryable_errors
    
    def get_reward_value(self, reward_type: str) -> float:
        """Get reward value for reward type."""
        return self.reward_values.get(reward_type, 0.0)

def main():
    """Test the quantum mode schema."""
    config = QuantumModeConfig()
    
    # Test quantum query detection
    test_queries = [
        "How do I create a Bell state in Qiskit?",
        "What is the weather today?",
        "Explain quantum teleportation with PennyLane",
        "Implement Grover's search algorithm"
    ]
    
    print("Quantum Mode Schema Test")
    print("="*60)
    
    for query in test_queries:
        is_quantum, confidence = config.is_quantum_query(query)
        confidence_level = config.get_confidence_level(confidence)
        
        print(f"Query: '{query[:30]}...'")
        print(f"  Is quantum: {is_quantum}")
        print(f"  Confidence: {confidence:.2f} ({confidence_level})")
        print()
    
    # Test task creation
    classification = {
        'task_type': TaskType.CODE_GENERATION.value,
        'algorithm_family': 'bell_state',
        'framework_requested': 'qiskit',
        'parameters': {'qubits': 2},
        'required_fields': ['algorithm', 'framework']
    }
    
    task = QuantumTask.from_query("Create Bell state", classification)
    print(f"Task created: {task.task_id}")
    print(f"  Type: {task.task_type}")
    print(f"  Requires retrieval: {config.requires_retrieval(task.task_type)}")
    print(f"  Requires verification: {config.requires_verification(task.task_type)}")
    
    # Test trace creation
    trace = QuantumTrace.create(task.task_id, TraceStep.DETECTION.value)
    print(f"\nTrace created: {trace.trace_id}")
    print(f"  Step: {trace.step}")
    print(f"  Status: {trace.status}")

if __name__ == '__main__':
    main()