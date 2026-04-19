#!/usr/bin/env python3
"""
Quantum Dataset Manager for Stray Goose

Manages retrieval and verification of quantum algorithm examples from dataset.
Implements the retrieval-first approach with multiple verification layers.
"""

import json
import sys
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from quantum_mode_schema import (
    TaskType, VerificationStatus, QuantumErrorCode,
    RetrievalResult, VerificationResult, QuantumModeConfig
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class QuantumDatasetManager:
    """Manages quantum algorithm dataset with retrieval and verification."""
    
    dataset_dir: Optional[Path] = None
    config: Optional[QuantumModeConfig] = None
    cache_size: int = 1000
    
    # Internal state
    _dataset: Dict[str, List[Dict]] = field(default_factory=dict)
    _verification_rules: Dict[str, List[Dict]] = field(default_factory=dict)
    _cache: Dict[str, RetrievalResult] = field(default_factory=dict)
    _cache_keys: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize dataset manager."""
        # Load config if not provided
        if self.config is None:
            self.config = QuantumModeConfig()
        
        # Load dataset
        self._load_dataset()
        
        # Load verification rules
        self._load_verification_rules()
    
    def _load_dataset(self):
        """Load quantum algorithm dataset from directory."""
        if self.dataset_dir is None:
            # Use default dataset path
            self.dataset_dir = Path("data/quantum_dataset")
        
        if not self.dataset_dir.exists():
            logger.warning(f"Dataset directory not found: {self.dataset_dir}")
            self.dataset_dir.mkdir(parents=True, exist_ok=True)
            # Create minimal example dataset
            self._create_example_dataset()
            return
        
        # Load dataset files
        dataset_files = list(self.dataset_dir.glob("*.json"))
        if not dataset_files:
            logger.warning(f"No dataset files found in {self.dataset_dir}")
            self._create_example_dataset()
            return
        
        self._dataset = {}
        for file_path in dataset_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # Validate dataset structure
                if isinstance(data, dict) and "examples" in data:
                    task_type = data.get("task_type", "unknown")
                    if task_type not in self._dataset:
                        self._dataset[task_type] = []
                    
                    for example in data["examples"]:
                        if self._validate_example(example):
                            self._dataset[task_type].append(example)
                    
                    logger.info(f"Loaded {len(data['examples'])} examples from {file_path.name}")
                else:
                    logger.warning(f"Invalid dataset format in {file_path.name}")
                    
            except Exception as e:
                logger.error(f"Error loading dataset file {file_path}: {e}")
        
        # Log summary
        total_examples = sum(len(examples) for examples in self._dataset.values())
        logger.info(f"Loaded dataset with {total_examples} examples across {len(self._dataset)} task types")
    
    def _create_example_dataset(self):
        """Create example dataset if none exists."""
        example_data = {
            "quantum_algorithm": [
                {
                    "id": "example_1",
                    "query": "Implement Grover's search algorithm",
                    "solution": "def grover_search(oracle, n_qubits):\n    # Initialize superposition\n    circuit = QuantumCircuit(n_qubits)\n    circuit.h(range(n_qubits))\n    \n    # Apply Grover iterations\n    for _ in range(int(np.pi/4 * np.sqrt(2**n_qubits))):\n        # Apply oracle\n        circuit.append(oracle, range(n_qubits))\n        \n        # Apply diffusion operator\n        circuit.h(range(n_qubits))\n        circuit.x(range(n_qubits))\n        circuit.h(n_qubits-1)\n        circuit.mcx(list(range(n_qubits-1)), n_qubits-1)\n        circuit.h(n_qubits-1)\n        circuit.x(range(n_qubits))\n        circuit.h(range(n_qubits))\n    \n    return circuit",
                    "framework": "qiskit",
                    "complexity": "intermediate",
                    "verification_status": "verified",
                    "verification_score": 0.95,
                    "safety_checks": ["no_execution", "simulation_only"],
                    "tags": ["search", "amplitude_amplification", "oracle"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "verified_at": "2024-01-02T00:00:00Z"
                }
            ],
            "quantum_circuit": [
                {
                    "id": "example_2",
                    "query": "Create a Bell state circuit",
                    "solution": "from qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2)\nqc.h(0)\nqc.cx(0, 1)\nqc.measure_all()",
                    "framework": "qiskit",
                    "complexity": "beginner",
                    "verification_status": "verified",
                    "verification_score": 0.98,
                    "safety_checks": ["no_execution", "circuit_only"],
                    "tags": ["entanglement", "bell_state", "basic"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "verified_at": "2024-01-02T00:00:00Z"
                }
            ]
        }
        
        # Save example dataset
        for task_type, examples in example_data.items():
            file_path = self.dataset_dir / f"{task_type}_examples.json"
            with open(file_path, 'w') as f:
                json.dump({
                    "task_type": task_type,
                    "examples": examples,
                    "created_at": datetime.now().isoformat()
                }, f, indent=2)
        
        # Load the created dataset
        self._load_dataset()
    
    def _load_verification_rules(self):
        """Load verification rules for different task types."""
        # Default verification rules
        self._verification_rules = {
            "quantum_algorithm": [
                {
                    "name": "framework_check",
                    "description": "Check if framework is supported",
                    "function": self._check_framework,
                    "weight": 0.3
                },
                {
                    "name": "complexity_check",
                    "description": "Check if complexity matches task",
                    "function": self._check_complexity,
                    "weight": 0.2
                },
                {
                    "name": "safety_check",
                    "description": "Check safety constraints",
                    "function": self._check_safety,
                    "weight": 0.3
                },
                {
                    "name": "code_quality_check",
                    "description": "Check code quality indicators",
                    "function": self._check_code_quality,
                    "weight": 0.2
                }
            ],
            "quantum_circuit": [
                {
                    "name": "framework_check",
                    "description": "Check if framework is supported",
                    "function": self._check_framework,
                    "weight": 0.4
                },
                {
                    "name": "safety_check",
                    "description": "Check safety constraints",
                    "function": self._check_safety,
                    "weight": 0.4
                },
                {
                    "name": "circuit_validity_check",
                    "description": "Check circuit structure",
                    "function": self._check_circuit_validity,
                    "weight": 0.2
                }
            ],
            "quantum_simulation": [
                {
                    "name": "framework_check",
                    "description": "Check if framework is supported",
                    "function": self._check_framework,
                    "weight": 0.3
                },
                {
                    "name": "simulation_safety_check",
                    "description": "Check simulation-specific safety",
                    "function": self._check_simulation_safety,
                    "weight": 0.4
                },
                {
                    "name": "resource_check",
                    "description": "Check resource requirements",
                    "function": self._check_resources,
                    "weight": 0.3
                }
            ],
            "quantum_error_correction": [
                {
                    "name": "framework_check",
                    "description": "Check if framework is supported",
                    "function": self._check_framework,
                    "weight": 0.2
                },
                {
                    "name": "error_model_check",
                    "description": "Check error model validity",
                    "function": self._check_error_model,
                    "weight": 0.4
                },
                {
                    "name": "correction_safety_check",
                    "description": "Check correction safety",
                    "function": self._check_correction_safety,
                    "weight": 0.4
                }
            ]
        }
    
    def _validate_example(self, example: Dict) -> bool:
        """Validate a dataset example."""
        required_fields = ["id", "query", "solution", "framework", "verification_status"]
        
        for field in required_fields:
            if field not in example:
                logger.warning(f"Example missing required field: {field}")
                return False
        
        # Check verification status
        if example["verification_status"] not in ["verified", "unverified", "rejected"]:
            logger.warning(f"Invalid verification status: {example['verification_status']}")
            return False
        
        # Check framework
        if not self.config.is_supported_framework(example["framework"]):
            logger.warning(f"Unsupported framework: {example['framework']}")
            return False
        
        return True
    
    def retrieve_examples(self, query: str, task_type: str, 
                         confidence_threshold: str = "medium",
                         max_results: int = 5) -> RetrievalResult:
        """
        Retrieve relevant examples from dataset.
        
        Args:
            query: User query
            task_type: Type of quantum task
            confidence_threshold: Confidence level for filtering
            max_results: Maximum number of examples to return
            
        Returns:
            RetrievalResult with matched examples
        """
        # Generate cache key
        cache_key = hashlib.sha256(f"{query}_{task_type}_{confidence_threshold}".encode()).hexdigest()
        
        # Check cache
        if cache_key in self._cache:
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return self._cache[cache_key]
        
        # Get examples for task type
        examples = self._dataset.get(task_type, [])
        if not examples:
            logger.warning(f"No examples found for task type: {task_type}")
            return RetrievalResult(
                query=query,
                task_type=task_type,
                examples=[],
                match_scores=[],
                confidence_level=confidence_threshold,
                retrieval_time=datetime.now().isoformat()
            )
        
        # Score examples based on similarity
        scored_examples = []
        for example in examples:
            score = self._calculate_similarity_score(query, example["query"])
            
            # Filter by verification status and score
            if (example["verification_status"] == "verified" and 
                score >= self._get_threshold_score(confidence_threshold)):
                scored_examples.append((score, example))
        
        # Sort by score (descending)
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        
        # Take top results
        top_examples = [example for score, example in scored_examples[:max_results]]
        match_scores = [score for score, example in scored_examples[:max_results]]
        
        # Create result
        result = RetrievalResult(
            query=query,
            task_type=task_type,
            examples=top_examples,
            match_scores=match_scores,
            confidence_level=confidence_threshold,
            retrieval_time=datetime.now().isoformat()
        )
        
        # Cache result
        self._cache[cache_key] = result
        self._cache_keys.append(cache_key)
        
        # Manage cache size
        if len(self._cache) > self.cache_size:
            oldest_key = self._cache_keys.pop(0)
            del self._cache[oldest_key]
        
        return result
    
    def _calculate_similarity_score(self, query1: str, query2: str) -> float:
        """Calculate similarity score between two queries."""
        # Simple keyword-based similarity
        words1 = set(re.findall(r'\w+', query1.lower()))
        words2 = set(re.findall(r'\w+', query2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        base_similarity = intersection / union
        
        # Boost for exact matches of key quantum terms
        quantum_terms = ["quantum", "algorithm", "circuit", "gate", "qubit", 
                        "entanglement", "superposition", "grover", "shor",
                        "qiskit", "cirq", "pennylane", "simulation"]
        
        quantum_matches = sum(1 for term in quantum_terms 
                            if term in query1.lower() and term in query2.lower())
        
        boost = min(0.3, quantum_matches * 0.05)
        
        return min(1.0, base_similarity + boost)
    
    def _get_threshold_score(self, confidence_level: str) -> float:
        """Get threshold score for confidence level."""
        thresholds = {
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
            "very_high": 0.9
        }
        return thresholds.get(confidence_level, 0.5)
    
    def verify_examples(self, retrieval_result: RetrievalResult, 
                       task_type: str) -> VerificationResult:
        """
        Verify retrieved examples using multiple checks.
        
        Args:
            retrieval_result: Result from retrieve_examples
            task_type: Type of quantum task
            
        Returns:
            VerificationResult with verification status
        """
        if not retrieval_result.examples:
            return VerificationResult(
                retrieval_result=retrieval_result,
                overall_score=0.0,
                verification_status=VerificationStatus.FAILED.value,
                checks=[],
                failure_reasons=["No examples to verify"],
                verification_time=datetime.now().isoformat()
            )
        
        # Get verification rules for task type
        rules = self._verification_rules.get(task_type, self._verification_rules.get("quantum_algorithm", []))
        
        verification_checks = []
        example_scores = []
        
        for example in retrieval_result.examples:
            example_checks = []
            example_score = 0.0
            total_weight = 0.0
            
            for rule in rules:
                try:
                    check_result = rule["function"](example, task_type)
                    check_result["rule_name"] = rule["name"]
                    check_result["weight"] = rule["weight"]
                    
                    example_checks.append(check_result)
                    
                    if check_result["passed"]:
                        example_score += rule["weight"] * check_result.get("score", 1.0)
                    
                    total_weight += rule["weight"]
                    
                except Exception as e:
                    logger.error(f"Error applying rule {rule['name']}: {e}")
                    example_checks.append({
                        "rule_name": rule["name"],
                        "passed": False,
                        "error": str(e),
                        "weight": rule["weight"]
                    })
            
            # Normalize score
            if total_weight > 0:
                example_score = example_score / total_weight
            
            example_scores.append(example_score)
            verification_checks.append({
                "example_id": example["id"],
                "checks": example_checks,
                "score": example_score
            })
        
        # Calculate overall score (weighted by match scores)
        overall_score = 0.0
        total_weight = 0.0
        
        for i, (example_score, match_score) in enumerate(zip(example_scores, retrieval_result.match_scores)):
            weight = match_score  # Use match score as weight
            overall_score += example_score * weight
            total_weight += weight
        
        if total_weight > 0:
            overall_score = overall_score / total_weight
        
        # Determine verification status
        if overall_score >= 0.8:
            status = VerificationStatus.PASSED.value
        elif overall_score >= 0.5:
            status = VerificationStatus.PARTIAL.value
        else:
            status = VerificationStatus.FAILED.value
        
        return VerificationResult(
            retrieval_result=retrieval_result,
            overall_score=overall_score,
            verification_status=status,
            checks=verification_checks,
            failure_reasons=[] if status != VerificationStatus.FAILED.value else ["Overall score too low"],
            verification_time=datetime.now().isoformat()
        )
    
    # Verification rule functions
    def _check_framework(self, example: Dict, task_type: str) -> Dict:
        """Check if framework is supported."""
        framework = example.get("framework", "")
        is_supported = self.config.is_supported_framework(framework)
        
        return {
            "passed": is_supported,
            "score": 1.0 if is_supported else 0.0,
            "details": f"Framework: {framework}, Supported: {is_supported}"
        }
    
    def _check_complexity(self, example: Dict, task_type: str) -> Dict:
        """Check if complexity matches task."""
        complexity = example.get("complexity", "unknown")
        
        # Simple mapping of complexity levels
        complexity_scores = {
            "beginner": 0.8,
            "intermediate": 1.0,
            "advanced": 0.9,
            "expert": 0.7,
            "unknown": 0.5
        }
        
        score = complexity_scores.get(complexity, 0.5)
        
        return {
            "passed": score >= 0.5,
            "score": score,
            "details": f"Complexity: {complexity}, Score: {score}"
        }
    
    def _check_safety(self, example: Dict, task_type: str) -> Dict:
        """Check safety constraints."""
        safety_checks = example.get("safety_checks", [])
        
        # Check for dangerous patterns
        dangerous_patterns = [
            "real_hardware",
            "live_execution",
            "unrestricted_access",
            "system_call"
        ]
        
        dangerous_found = any(pattern in str(safety_checks).lower() 
                            for pattern in dangerous_patterns)
        
        # Check for safety measures
        safety_measures = [
            "no_execution",
            "simulation_only",
            "sandboxed",
            "validated"
        ]
        
        safety_found = any(measure in str(safety_checks).lower() 
                         for measure in safety_measures)
        
        score = 0.0
        if safety_found and not dangerous_found:
            score = 1.0
        elif not dangerous_found:
            score = 0.5
        # else score remains 0.0
        
        return {
            "passed": score >= 0.5,
            "score": score,
            "details": f"Safety checks: {safety_checks}, Dangerous: {dangerous_found}, Safe: {safety_found}"
        }
    
    def _check_code_quality(self, example: Dict, task_type: str) -> Dict:
        """Check code quality indicators."""
        solution = example.get("solution", "")
        
        # Simple code quality checks
        checks = {
            "has_comments": "def " in solution or "#" in solution,
            "reasonable_length": len(solution) < 1000,  # Not too long
            "no_hardcoded_secrets": "password" not in solution.lower() and 
                                  "secret" not in solution.lower() and
                                  "key" not in solution.lower(),
            "uses_standard_libs": any(lib in solution.lower() 
                                    for lib in ["qiskit", "cirq", "pennylane", "numpy"])
        }
        
        passed_checks = sum(1 for check in checks.values() if check)
        total_checks = len(checks)
        
        score = passed_checks / total_checks if total_checks > 0 else 0.0
        
        return {
            "passed": score >= 0.5,
            "score": score,
            "details": f"Code quality checks: {passed_checks}/{total_checks} passed"
        }
    
    def _check_circuit_validity(self, example: Dict, task_type: str) -> Dict:
        """Check circuit structure validity."""
        solution = example.get("solution", "")
        
        # Check for circuit creation patterns
        circuit_patterns = [
            "QuantumCircuit",
            "circuit =",
            "qc =",
            ".h(",
            ".cx(",
            ".measure"
        ]
        
        pattern_matches = sum(1 for pattern in circuit_patterns 
                            if pattern in solution)
        
        score = min(1.0, pattern_matches / 3)  # At least 3 patterns for good circuit
        
        return {
            "passed": score >= 0.5,
            "score": score,
            "details": f"Circuit patterns matched: {pattern_matches}/{len(circuit_patterns)}"
        }
    
    def _check_simulation_safety(self, example: Dict, task_type: str) -> Dict:
        """Check simulation-specific safety."""
        # Similar to general safety but with simulation focus
        return self._check_safety(example, task_type)
    
    def _check_resources(self, example: Dict, task_type: str) -> Dict:
        """Check resource requirements."""
        # Default implementation - always pass
        return {
            "passed": True,
            "score": 1.0,
            "details": "Resource check passed (default)"
        }
    
    def _check_error_model(self, example: Dict, task_type: str) -> Dict:
        """Check error model validity."""
        solution = example.get("solution", "")
        
        # Check for error correction patterns
        error_patterns = [
            "error",
            "correction",
            "noise",
            "mitigation",
            "code",
            "syndrome"
        ]
        
        pattern_matches = sum(1 for pattern in error_patterns 
                            if pattern in solution.lower())
        
        score = min(1.0, pattern_matches / 3)  # At least 3 patterns
        
        return {
            "passed": score >= 0.5,
            "score": score,
            "details": f"Error correction patterns: {pattern_matches}/{len(error_patterns)}"
        }
    
    def _check_correction_safety(self, example: Dict, task_type: str) -> Dict:
        """Check error correction safety."""
        # Similar to general safety
        return self._check_safety(example, task_type)
    
    def get_stats(self) -> Dict:
        """Get dataset statistics."""
        stats = {
            "total_examples": 0,
            "by_task_type": {},
            "by_framework": {},
            "by_verification_status": {}
        }
        
        for task_type, examples in self._dataset.items():
            stats["by_task_type"][task_type] = len(examples)
            stats["total_examples"] += len(examples)
            
            for example in examples:
                # Count by framework
                framework = example.get("framework", "unknown")
                stats["by_framework"][framework] = stats["by_framework"].get(framework, 0) + 1
                
                # Count by verification status
                status = example.get("verification_status", "unknown")
                stats["by_verification_status"][status] = stats["by_verification_status"].get(status, 0) + 1
        
        return stats
    
    def add_example(self, example: Dict, task_type: str) -> bool:
        """Add a new example to the dataset."""
        if not self._validate_example(example):
            return False
        
        # Add to in-memory dataset
        if task_type not in self._dataset:
            self._dataset[task_type] = []
        
        self._dataset[task_type].append(example)
        
        # Save to file
        file_path = self.dataset_dir / f"{task_type}_examples.json"
        try:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
            else:
                data = {"task_type": task_type, "examples": []}
            
            data["examples"].append(example)
            data["updated_at"] = datetime.now().isoformat()
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Added example {example['id']} to {task_type} dataset")
            return True
            
        except Exception as e:
            logger.error(f"Error saving example to dataset: {e}")
            # Remove from in-memory dataset
            self._dataset[task_type].remove(example)
            return False


def main():
    """Command-line interface for Quantum Dataset Manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quantum Dataset Manager")
    parser.add_argument("--dataset-dir", help="Path to dataset directory")
    parser.add_argument("--stats", action="store_true", help="Show dataset statistics")
    parser.add_argument("--retrieve", help="Query to retrieve examples for")
    parser.add_argument("--task-type", default="quantum_algorithm", help="Task type for retrieval")
    parser.add_argument("--verify", action="store_true", help="Verify retrieved examples")
    
    args = parser.parse_args()
    
    # Initialize manager
    manager = QuantumDatasetManager(
        dataset_dir=Path(args.dataset_dir) if args.dataset_dir else None
    )
    
    if args.stats:
        # Show statistics
        stats = manager.get_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.retrieve:
        # Retrieve examples
        result = manager.retrieve_examples(
            query=args.retrieve,
            task_type=args.task_type
        )
        
        print("Retrieval Result:")
        print(json.dumps(result.to_dict(), indent=2))
        
        if args.verify:
            # Verify examples
            verification = manager.verify_examples(result, args.task_type)
            print("\nVerification Result:")
            print(json.dumps(verification.to_dict(), indent=2))
    
    else:
        parser.print_help()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())