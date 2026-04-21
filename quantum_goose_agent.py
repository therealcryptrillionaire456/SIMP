#!/usr/bin/env python3
"""
Quantum Goose SIMP Agent

A SIMP agent that handles quantum computation intents using the Quantum Goose dataset
and verification system. Provides quantum algorithm explanations, code generation,
and verification as first-class SIMP intents.
"""

import json
import sys
import os
import time
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# Add Quantum Goose to path
quantum_goose_path = Path("/Users/kaseymarcelle/Library/Mobile Documents/com~apple~CloudDocs/Desktop/kloutbot_core/quantum_goose")
sys.path.insert(0, str(quantum_goose_path))

# SIMP imports
from simp.agent import SimpAgent
from simp.intent import Intent

@dataclass
class QuantumTask:
    """A quantum computation task."""
    task_id: str
    algorithm: str
    framework: str = "qiskit"
    parameters: Optional[Dict] = None
    expected_output: Optional[Dict] = None
    require_explanation: bool = True
    require_verification: bool = True
    
    @classmethod
    def from_intent(cls, intent: Intent) -> 'QuantumTask':
        """Create a QuantumTask from a SIMP intent."""
        params = intent.parameters or {}
        return cls(
            task_id=intent.intent_id or f"quantum_{int(time.time())}",
            algorithm=params.get('algorithm', ''),
            framework=params.get('framework', 'qiskit'),
            parameters=params.get('parameters', {}),
            expected_output=params.get('expected_output'),
            require_explanation=params.get('require_explanation', True),
            require_verification=params.get('require_verification', True)
        )

@dataclass
class QuantumResult:
    """Result of a quantum computation task."""
    task_id: str
    success: bool
    code: Optional[str] = None
    explanation: Optional[str] = None
    execution_result: Optional[Dict] = None
    verification_result: Optional[Dict] = None
    retrieved_example_id: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    
    def to_simp_response(self) -> Dict:
        """Convert to SIMP response format."""
        response = {
            'status': 'success' if self.success else 'error',
            'task_id': self.task_id,
            'timestamp': self.timestamp,
            'execution_time_ms': self.execution_time_ms,
            'x-simp': {
                'quantum_result': {
                    'success': self.success,
                    'retrieved_example': self.retrieved_example_id,
                    'verification_passed': self.verification_result.get('passed', False) if self.verification_result else False
                }
            }
        }
        
        if self.success:
            response['result'] = {
                'code': self.code,
                'explanation': self.explanation,
                'execution': self.execution_result,
                'verification': self.verification_result
            }
        else:
            response['error'] = self.error_message
            
        return response

class QuantumGooseAgent(SimpAgent):
    """SIMP agent for quantum computation tasks."""
    
    def __init__(self, agent_id: str = "quantum_goose", config: Optional[Dict] = None):
        super().__init__(agent_id, config)
        
        # Setup Quantum Goose integration
        self.quantum_goose_path = quantum_goose_path
        self.dataset_path = self.quantum_goose_path / 'data' / 'quantum_seed_dataset.jsonl'
        self.verifier_path = self.quantum_goose_path / 'verifier' / 'verify_quantum_dataset.py'
        
        # Load dataset
        self.dataset = self._load_dataset()
        self.dataset_index = self._build_index()
        
        # Initialize quantum frameworks
        self._init_frameworks()
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'retrieval_hits': 0,
            'verification_passes': 0,
            'errors_by_type': {}
        }
        
        # Log file for learning signals
        self.learning_log_path = Path("data/quantum_goose_learning.jsonl")
        self.learning_log_path.parent.mkdir(exist_ok=True)
        
        print(f"Quantum Goose Agent initialized with {len(self.dataset)} examples")
    
    def _load_dataset(self) -> List[Dict]:
        """Load Quantum Goose dataset."""
        examples = []
        if self.dataset_path.exists():
            with open(self.dataset_path, 'r') as f:
                for line in f:
                    if line.strip():
                        examples.append(json.loads(line))
        return examples
    
    def _build_index(self) -> Dict[str, List[Dict]]:
        """Build search index for dataset."""
        index = {
            'by_algorithm': {},
            'by_framework': {'qiskit': [], 'pennylane': []},
            'by_difficulty': {'beginner': [], 'intermediate': [], 'advanced': []},
            'by_category': {}
        }
        
        for example in self.dataset:
            # Index by algorithm name
            algo_name = example['metadata'].get('name', '').lower()
            if algo_name:
                if algo_name not in index['by_algorithm']:
                    index['by_algorithm'][algo_name] = []
                index['by_algorithm'][algo_name].append(example)
            
            # Index by framework
            for framework in example.get('implementations', {}).keys():
                if framework in index['by_framework']:
                    index['by_framework'][framework].append(example)
            
            # Index by difficulty
            difficulty = example['metadata'].get('difficulty', '').lower()
            if difficulty in index['by_difficulty']:
                index['by_difficulty'][difficulty].append(example)
            
            # Index by category
            for category in example['metadata'].get('category', []):
                if category not in index['by_category']:
                    index['by_category'][category] = []
                index['by_category'][category].append(example)
        
        return index
    
    def _init_frameworks(self):
        """Initialize quantum frameworks."""
        try:
            import qiskit
            self.qiskit_available = True
            self.qiskit_version = qiskit.__version__
        except ImportError:
            self.qiskit_available = False
            self.qiskit_version = None
        
        try:
            import pennylane
            self.pennylane_available = True
            self.pennylane_version = pennylane.__version__
        except ImportError:
            self.pennylane_available = False
            self.pennylane_version = None
        
        print(f"Frameworks: Qiskit={self.qiskit_available}({self.qiskit_version}), "
              f"PennyLane={self.pennylane_available}({self.pennylane_version})")
    
    def retrieve_example(self, algorithm: str, framework: str) -> Tuple[Optional[Dict], float]:
        """
        Retrieve relevant example from dataset.
        Returns (example, similarity_score)
        """
        algorithm_lower = algorithm.lower()
        
        # First try exact algorithm name match
        if algorithm_lower in self.dataset_index['by_algorithm']:
            examples = self.dataset_index['by_algorithm'][algorithm_lower]
            # Filter by framework
            framework_examples = [e for e in examples if framework in e.get('implementations', {})]
            if framework_examples:
                # Return first verified example if available
                verified = [e for e in framework_examples if e.get('verification', {}).get('verified', False)]
                if verified:
                    return verified[0], 1.0
                return framework_examples[0], 0.9
        
        # Try category matching
        for example in self.dataset:
            # Check framework support
            if framework not in example.get('implementations', {}):
                continue
            
            # Check description
            description = example['metadata'].get('description', '').lower()
            if algorithm_lower in description:
                return example, 0.7
            
            # Check tags
            tags = [t.lower() for t in example['metadata'].get('tags', [])]
            if algorithm_lower in tags:
                return example, 0.6
        
        return None, 0.0
    
    def generate_code(self, task: QuantumTask, example: Optional[Dict] = None) -> Tuple[str, Optional[str]]:
        """
        Generate quantum code for a task.
        Returns (code, retrieved_example_id)
        """
        if example and task.framework in example.get('implementations', {}):
            # Use example code
            impl = example['implementations'][task.framework]
            code = '\n'.join(impl.get('imports', []) + [impl.get('code', '')])
            
            # Add parameter substitution if needed
            if task.parameters:
                code = self._substitute_parameters(code, task.parameters)
            
            return code, example['id']
        else:
            # Generate simple template
            template = f"""# Quantum task: {task.algorithm}
# Framework: {task.framework}
# Generated by Quantum Goose SIMP Agent

print("Quantum algorithm: {task.algorithm}")
print("Framework: {task.framework}")
print("Parameters: {task.parameters}")

# TODO: Implement {task.algorithm} in {task.framework}
# This is a placeholder - actual implementation would be generated
# based on retrieved examples from the Quantum Goose dataset."""
            
            return template, None
    
    def _substitute_parameters(self, code: str, parameters: Dict) -> str:
        """Substitute parameters in code template."""
        # Simple parameter substitution
        for key, value in parameters.items():
            placeholder = f"{{{key}}}"
            if placeholder in code:
                code = code.replace(placeholder, str(value))
        return code
    
    def execute_code(self, code: str, framework: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Execute quantum code and return results."""
        import time
        start_time = time.time()
        
        try:
            if framework == 'qiskit' and self.qiskit_available:
                result = self._execute_qiskit(code)
            elif framework == 'pennylane' and self.pennylane_available:
                result = self._execute_pennylane(code)
            else:
                return False, None, f"Framework {framework} not available"
            
            execution_time = (time.time() - start_time) * 1000
            result['execution_time_ms'] = execution_time
            
            return True, result, None
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            error_tb = traceback.format_exc()
            
            return False, {
                'execution_time_ms': execution_time,
                'error': error_msg,
                'traceback': error_tb
            }, error_msg
    
    def _execute_qiskit(self, code: str) -> Dict:
        """Execute Qiskit code."""
        import qiskit
        from qiskit import QuantumCircuit
        from qiskit.primitives import StatevectorSampler
        
        namespace = {
            'QuantumCircuit': QuantumCircuit,
            'StatevectorSampler': StatevectorSampler,
            'qiskit': qiskit
        }
        
        exec(code, namespace)
        
        # Find and execute circuit
        circuit = None
        for var_value in namespace.values():
            if isinstance(var_value, QuantumCircuit):
                circuit = var_value
                break
        
        if not circuit:
            return {'error': 'No QuantumCircuit found'}
        
        # Execute
        sampler = StatevectorSampler()
        job = sampler.run([circuit], shots=100)
        result = job.result()
        
        # Extract counts
        pub_result = result[0]
        counts = {}
        try:
            counts = dict(pub_result.data.c.get_counts())
        except AttributeError:
            try:
                counts = pub_result.data.meas.get_counts()
            except AttributeError:
                # Try to find counts in data
                if hasattr(pub_result.data, '__dict__'):
                    for key, value in pub_result.data.__dict__.items():
                        if isinstance(value, dict) and all(isinstance(k, str) for k in value.keys()):
                            counts = value
                            break
        
        return {
            'circuit_info': {
                'qubits': circuit.num_qubits,
                'depth': circuit.depth(),
                'operations': len(circuit.data)
            },
            'counts': counts,
            'shots': 100
        }
    
    def _execute_pennylane(self, code: str) -> Dict:
        """Execute PennyLane code."""
        import pennylane as qml
        import numpy as np
        
        namespace = {
            'qml': qml,
            'np': np
        }
        
        exec(code, namespace)
        
        # Find and execute circuit function
        circuit_func = None
        for var_value in namespace.values():
            if callable(var_value) and hasattr(var_value, '__name__'):
                circuit_func = var_value
                break
        
        if not circuit_func:
            return {'error': 'No circuit function found'}
        
        result = circuit_func()
        
        return {
            'output': str(result),
            'type': type(result).__name__
        }
    
    def verify_result(self, execution_result: Dict, expected_output: Optional[Dict]) -> Dict:
        """Verify execution result against expected output."""
        if not expected_output:
            return {
                'passed': True,
                'score': 1.0,
                'note': 'No expected output provided for verification'
            }
        
        # Simple verification logic
        score = 0.0
        details = {}
        
        if 'counts' in execution_result and 'expected_counts' in expected_output:
            actual_counts = execution_result['counts']
            expected_counts = expected_output['expected_counts']
            
            total_shots = sum(actual_counts.values())
            if total_shots > 0:
                score = 1.0
                for state, expected in expected_counts.items():
                    expected_prob = expected / 100 if isinstance(expected, int) else expected
                    actual_prob = actual_counts.get(state, 0) / total_shots
                    deviation = abs(actual_prob - expected_prob)
                    
                    if deviation > 0.1:  # 10% tolerance
                        penalty = min(1.0, deviation / 0.2)
                        score -= penalty / len(expected_counts)
                
                score = max(0.0, score)
                details['counts_match'] = score >= 0.8
        
        return {
            'passed': score >= 0.8,
            'score': score,
            'details': details
        }
    
    def generate_explanation(self, task: QuantumTask, example: Optional[Dict] = None) -> str:
        """Generate explanation for quantum algorithm."""
        if example:
            # Use example explanation if available
            impl = example['implementations'].get(task.framework, {})
            explanation = impl.get('explanation', '')
            if explanation:
                return explanation
            
            # Fallback to metadata
            return example['metadata'].get('description', '')
        
        # Generate generic explanation
        return f"""Algorithm: {task.algorithm}
Framework: {task.framework}

This quantum algorithm manipulates quantum states to perform computation.
The specific implementation depends on the parameters and framework used.

For detailed explanation, please provide a specific example from the Quantum Goose dataset."""
    
    def log_learning_signal(self, task: QuantumTask, result: QuantumResult):
        """Log learning signal for system improvement."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'task_id': task.task_id,
            'algorithm': task.algorithm,
            'framework': task.framework,
            'retrieved_example': result.retrieved_example_id,
            'success': result.success,
            'verification_passed': result.verification_result.get('passed', False) if result.verification_result else False,
            'execution_time_ms': result.execution_time_ms,
            'stats_snapshot': self.stats.copy()
        }
        
        with open(self.learning_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def handle_quantum_intent(self, intent: Intent) -> Dict:
        """Handle quantum computation intent."""
        self.stats['total_requests'] += 1
        
        try:
            # Parse task from intent
            task = QuantumTask.from_intent(intent)
            
            # Retrieve example
            example, similarity = self.retrieve_example(task.algorithm, task.framework)
            if example:
                self.stats['retrieval_hits'] += 1
            
            # Generate code
            code, retrieved_example_id = self.generate_code(task, example)
            
            # Generate explanation
            explanation = self.generate_explanation(task, example) if task.require_explanation else None
            
            # Execute code
            execution_success, execution_result, error = self.execute_code(code, task.framework)
            
            if not execution_success:
                result = QuantumResult(
                    task_id=task.task_id,
                    success=False,
                    error_message=error,
                    execution_time_ms=execution_result.get('execution_time_ms', 0) if execution_result else 0
                )
                self.stats['errors_by_type'][error.split(':')[0] if error else 'unknown'] = \
                    self.stats['errors_by_type'].get(error.split(':')[0] if error else 'unknown', 0) + 1
            else:
                # Verify if requested
                verification_result = None
                if task.require_verification:
                    verification_result = self.verify_result(execution_result, task.expected_output)
                    if verification_result.get('passed', False):
                        self.stats['verification_passes'] += 1
                
                result = QuantumResult(
                    task_id=task.task_id,
                    success=True,
                    code=code,
                    explanation=explanation,
                    execution_result=execution_result,
                    verification_result=verification_result,
                    retrieved_example_id=retrieved_example_id,
                    execution_time_ms=execution_result.get('execution_time_ms', 0)
                )
                self.stats['successful_requests'] += 1
            
            # Log learning signal
            self.log_learning_signal(task, result)
            
            return result.to_simp_response()
            
        except Exception as e:
            error_msg = f"Quantum Goose agent error: {str(e)}"
            self.stats['errors_by_type']['agent_error'] = self.stats['errors_by_type'].get('agent_error', 0) + 1
            
            return {
                'status': 'error',
                'error': error_msg,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'x-simp': {
                    'quantum_result': {
                        'success': False,
                        'error_type': 'agent_error'
                    }
                }
            }
    
    def get_capabilities(self) -> Dict:
        """Get agent capabilities for A2A card."""
        return {
            'quantum_computation': {
                'description': 'Quantum algorithm explanation and code generation',
                'supported_frameworks': ['qiskit', 'pennylane'],
                'supported_algorithms': list(self.dataset_index['by_algorithm'].keys()),
                'capabilities': [
                    'algorithm_explanation',
                    'code_generation',
                    'execution_verification',
                    'example_retrieval'
                ]
            }
        }
    
    def get_stats(self) -> Dict:
        """Get agent statistics."""
        return {
            'requests': self.stats,
            'dataset': {
                'total_examples': len(self.dataset),
                'verified_examples': len([e for e in self.dataset if e.get('verification', {}).get('verified', False)]),
                'by_framework': {k: len(v) for k, v in self.dataset_index['by_framework'].items()},
                'by_difficulty': {k: len(v) for k, v in self.dataset_index['by_difficulty'].items()}
            },
            'frameworks': {
                'qiskit': {'available': self.qiskit_available, 'version': self.qiskit_version},
                'pennylane': {'available': self.pennylane_available, 'version': self.pennylane_version}
            }
        }

def main():
    """Main entry point for Quantum Goose SIMP agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Quantum Goose SIMP Agent')
    parser.add_argument('--port', type=int, default=8790, help='Port to run agent on')
    parser.add_argument('--broker', type=str, default='http://127.0.0.1:5555', help='SIMP broker URL')
    parser.add_argument('--register', action='store_true', help='Register with SIMP broker')
    
    args = parser.parse_args()
    
    # Create agent
    agent = QuantumGooseAgent()
    
    print(f"Quantum Goose SIMP Agent")
    print(f"  Dataset: {len(agent.dataset)} examples")
    print(f"  Frameworks: Qiskit={agent.qiskit_available}, PennyLane={agent.pennylane_available}")
    print(f"  Listening on port: {args.port}")
    
    if args.register:
        print(f"  Registering with broker: {args.broker}")
        # Registration logic would go here
    
    # Start agent server
    # In a real implementation, this would start a Flask/FastAPI server
    # For now, just demonstrate capability
    print("\nAgent ready to handle quantum intents.")
    print("Example capabilities:")
    for algo in list(agent.dataset_index['by_algorithm'].keys())[:5]:
        print(f"  - {algo}")
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Quantum Goose agent...")
        print(f"Final stats: {agent.stats}")

if __name__ == '__main__':
    main()