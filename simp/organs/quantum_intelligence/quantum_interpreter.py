"""
Module 2: Quantum State Interpreter

This module enables agents to:
1. Interpret quantum measurement results
2. Develop quantum intuition about states
3. Understand quantum phenomena (entanglement, superposition)
4. Extract insights from quantum computations
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime
import random
from enum import Enum
from dataclasses import dataclass, field

from . import QuantumProblemType, QuantumAlgorithmInsight


class QuantumPhenomenon(str, Enum):
    """Quantum phenomena that can be interpreted."""
    SUPERPOSITION = "superposition"
    ENTANGLEMENT = "entanglement"
    INTERFERENCE = "interference"
    MEASUREMENT = "measurement"
    DECOHERENCE = "decoherence"
    TUNNELING = "tunneling"
    TELEPORTATION = "teleportation"


class InterpretationConfidence(str, Enum):
    """Confidence levels for quantum interpretations."""
    SPECULATIVE = "speculative"  # 0-0.3 confidence
    PLAUSIBLE = "plausible"      # 0.3-0.7 confidence  
    CONFIDENT = "confident"      # 0.7-0.9 confidence
    CERTAIN = "certain"          # 0.9-1.0 confidence


@dataclass
class QuantumStateAnalysis:
    """Analysis of a quantum state."""
    state_vector: Optional[np.ndarray] = None
    density_matrix: Optional[np.ndarray] = None
    measurement_results: Dict[str, float] = field(default_factory=dict)
    entanglement_measures: Dict[str, float] = field(default_factory=dict)
    superposition_measures: Dict[str, float] = field(default_factory=dict)
    classical_correlations: Dict[str, float] = field(default_factory=dict)


class QuantumStateInterpreter:
    """Interprets quantum states and extracts insights."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"quantum.interpreter.{agent_id}")
        self.insights: Dict[str, QuantumAlgorithmInsight] = {}
        self.quantum_intuition: Dict[str, float] = {}  # Intuition scores for different phenomena
        
    def interpret_measurement_results(
        self,
        measurement_counts: Dict[str, int],
        total_shots: int,
        circuit_info: Dict[str, Any],
        problem_context: Optional[Dict[str, Any]] = None
    ) -> List[QuantumAlgorithmInsight]:
        """Interpret quantum measurement results."""
        insights = []
        problem_context = problem_context or {}
        
        # Convert counts to probabilities
        probabilities = {state: count / total_shots for state, count in measurement_counts.items()}
        
        # Analyze distribution
        distribution_insight = self._analyze_distribution(probabilities, circuit_info, problem_context)
        if distribution_insight:
            insights.append(distribution_insight)
        
        # Look for entanglement signatures
        entanglement_insight = self._detect_entanglement(probabilities, circuit_info)
        if entanglement_insight:
            insights.append(entanglement_insight)
        
        # Look for interference patterns
        interference_insight = self._detect_interference(probabilities, circuit_info)
        if interference_insight:
            insights.append(interference_insight)
        
        # Extract problem-specific insights
        problem_insight = self._extract_problem_insight(probabilities, circuit_info, problem_context)
        if problem_insight:
            insights.append(problem_insight)
        
        # Store insights
        for insight in insights:
            self.insights[insight.insight_id] = insight
        
        self.logger.info(f"Extracted {len(insights)} insights from measurement results")
        return insights
    
    def develop_quantum_intuition(
        self,
        state_analysis: QuantumStateAnalysis,
        circuit_executions: List[Dict[str, Any]]
    ) -> Dict[QuantumPhenomenon, float]:
        """Develop quantum intuition from state analyses."""
        intuition_scores = {}
        
        # Analyze superposition
        superposition_score = self._assess_superposition(state_analysis, circuit_executions)
        intuition_scores[QuantumPhenomenon.SUPERPOSITION] = superposition_score
        
        # Analyze entanglement
        entanglement_score = self._assess_entanglement(state_analysis, circuit_executions)
        intuition_scores[QuantumPhenomenon.ENTANGLEMENT] = entanglement_score
        
        # Analyze interference
        interference_score = self._assess_interference(state_analysis, circuit_executions)
        intuition_scores[QuantumPhenomenon.INTERFERENCE] = interference_score
        
        # Update agent's quantum intuition
        for phenomenon, score in intuition_scores.items():
            current_score = self.quantum_intuition.get(phenomenon.value, 0.0)
            # Moving average update
            new_score = 0.7 * current_score + 0.3 * score
            self.quantum_intuition[phenomenon.value] = new_score
        
        self.logger.info(f"Developed quantum intuition: {intuition_scores}")
        return intuition_scores
    
    def understand_quantum_phenomenon(
        self,
        phenomenon: QuantumPhenomenon,
        evidence: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> QuantumAlgorithmInsight:
        """Develop understanding of a specific quantum phenomenon."""
        context = context or {}
        
        # Analyze evidence
        analysis = self._analyze_phenomenon_evidence(phenomenon, evidence)
        
        # Generate insight
        insight_text = self._generate_phenomenon_insight(phenomenon, analysis, context)
        confidence = self._calculate_phenomenon_confidence(phenomenon, analysis)
        
        insight_id = f"phenomenon_{phenomenon.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        insight = QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type="phenomenon_analysis",
            quantum_phenomenon=phenomenon.value,
            insight_text=insight_text,
            confidence=confidence,
            evidence=evidence,
            created_at=datetime.utcnow().isoformat()
        )
        
        self.insights[insight_id] = insight
        self.logger.info(f"Developed understanding of {phenomenon.value}: {insight_text[:50]}...")
        
        return insight
    
    def extract_algorithm_insights(
        self,
        algorithm_results: Dict[str, Any],
        problem_type: QuantumProblemType
    ) -> List[QuantumAlgorithmInsight]:
        """Extract insights from algorithm execution results."""
        insights = []
        
        # Analyze convergence (for variational algorithms)
        if "convergence_history" in algorithm_results:
            convergence_insight = self._analyze_convergence(
                algorithm_results["convergence_history"],
                problem_type
            )
            if convergence_insight:
                insights.append(convergence_insight)
        
        # Analyze parameter sensitivity
        if "parameter_sensitivity" in algorithm_results:
            sensitivity_insight = self._analyze_parameter_sensitivity(
                algorithm_results["parameter_sensitivity"],
                problem_type
            )
            if sensitivity_insight:
                insights.append(sensitivity_insight)
        
        # Analyze quantum advantage
        if "quantum_advantage_metrics" in algorithm_results:
            advantage_insight = self._analyze_quantum_advantage(
                algorithm_results["quantum_advantage_metrics"],
                problem_type
            )
            if advantage_insight:
                insights.append(advantage_insight)
        
        # Store insights
        for insight in insights:
            self.insights[insight.insight_id] = insight
        
        return insights
    
    def _analyze_distribution(
        self,
        probabilities: Dict[str, float],
        circuit_info: Dict[str, Any],
        problem_context: Dict[str, Any]
    ) -> Optional[QuantumAlgorithmInsight]:
        """Analyze probability distribution of measurement results."""
        if not probabilities:
            return None
        
        states = list(probabilities.keys())
        probs = list(probabilities.values())
        
        # Calculate entropy of distribution
        entropy = -sum(p * np.log2(p) for p in probs if p > 0)
        max_entropy = np.log2(len(probs))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        # Find most probable states
        sorted_indices = np.argsort(probs)[::-1]
        top_states = [states[i] for i in sorted_indices[:3]]
        top_probs = [probs[i] for i in sorted_indices[:3]]
        
        # Generate insight based on distribution
        if normalized_entropy > 0.8:
            insight_text = "Measurement results show high entropy, suggesting the circuit explores many states."
            phenomenon = QuantumPhenomenon.SUPERPOSITION
            confidence = min(0.7, normalized_entropy)
        elif top_probs[0] > 0.7:
            insight_text = f"Strong convergence to state '{top_states[0]}' with probability {top_probs[0]:.2f}."
            phenomenon = QuantumPhenomenon.MEASUREMENT
            confidence = top_probs[0]
        else:
            insight_text = f"Distributed results with top states: {', '.join(top_states[:2])}"
            phenomenon = QuantumPhenomenon.SUPERPOSITION
            confidence = 0.5
        
        # Add problem context
        if problem_context.get("problem_type") == QuantumProblemType.OPTIMIZATION:
            if top_probs[0] > 0.6:
                insight_text += " This suggests a good solution to the optimization problem."
            else:
                insight_text += " The optimization landscape may have multiple good solutions."
        
        insight_id = f"distribution_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type=circuit_info.get("algorithm", "unknown"),
            quantum_phenomenon=phenomenon.value,
            insight_text=insight_text,
            confidence=confidence,
            evidence=[
                {"type": "probability_distribution", "entropy": float(entropy), 
                 "top_states": top_states[:3], "top_probabilities": [float(p) for p in top_probs[:3]]}
            ],
            created_at=datetime.utcnow().isoformat()
        )
    
    def _detect_entanglement(
        self,
        probabilities: Dict[str, float],
        circuit_info: Dict[str, Any]
    ) -> Optional[QuantumAlgorithmInsight]:
        """Detect entanglement signatures in measurement results."""
        if len(probabilities) < 4:  # Need at least 2 qubits for entanglement
            return None
        
        # Check for Bell state signatures
        bell_state_patterns = {
            "00": "Φ+", "11": "Φ+",  # |00⟩ + |11⟩
            "01": "Ψ+", "10": "Ψ+",  # |01⟩ + |10⟩
            "00_11": "Φ+",  # Both |00⟩ and |11⟩ present
            "01_10": "Ψ+",  # Both |01⟩ and |10⟩ present
        }
        
        # Simple entanglement detection
        states = list(probabilities.keys())
        qubit_count = len(states[0]) if states else 0
        
        if qubit_count >= 2:
            # Check for correlated measurements
            correlations = self._calculate_correlations(probabilities)
            
            if any(abs(corr) > 0.7 for corr in correlations.values()):
                insight_text = "Strong correlations detected between qubits, suggesting entanglement."
                confidence = max(abs(corr) for corr in correlations.values())
                
                insight_id = f"entanglement_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                
                return QuantumAlgorithmInsight(
                    insight_id=insight_id,
                    algorithm_type=circuit_info.get("algorithm", "unknown"),
                    quantum_phenomenon=QuantumPhenomenon.ENTANGLEMENT.value,
                    insight_text=insight_text,
                    confidence=confidence,
                    evidence=[
                        {"type": "correlation_analysis", "correlations": correlations}
                    ],
                    created_at=datetime.utcnow().isoformat()
                )
        
        return None
    
    def _detect_interference(
        self,
        probabilities: Dict[str, float],
        circuit_info: Dict[str, Any]
    ) -> Optional[QuantumAlgorithmInsight]:
        """Detect interference patterns in measurement results."""
        if len(probabilities) < 3:
            return None
        
        # Look for patterns that suggest constructive/destructive interference
        probs = list(probabilities.values())
        
        # Calculate variance - high variance might indicate interference
        variance = np.var(probs)
        mean_prob = np.mean(probs)
        
        # Normalize variance
        max_variance = mean_prob * (1 - mean_prob) if 0 < mean_prob < 1 else 0.25
        normalized_variance = variance / max_variance if max_variance > 0 else 0
        
        if normalized_variance > 0.6:
            insight_text = "High variance in probabilities suggests quantum interference effects."
            confidence = min(0.8, normalized_variance)
            
            insight_id = f"interference_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            return QuantumAlgorithmInsight(
                insight_id=insight_id,
                algorithm_type=circuit_info.get("algorithm", "unknown"),
                quantum_phenomenon=QuantumPhenomenon.INTERFERENCE.value,
                insight_text=insight_text,
                confidence=confidence,
                evidence=[
                    {"type": "variance_analysis", "variance": float(variance), 
                     "normalized_variance": float(normalized_variance)}
                ],
                created_at=datetime.utcnow().isoformat()
            )
        
        return None
    
    def _extract_problem_insight(
        self,
        probabilities: Dict[str, float],
        circuit_info: Dict[str, Any],
        problem_context: Dict[str, Any]
    ) -> Optional[QuantumAlgorithmInsight]:
        """Extract problem-specific insights."""
        problem_type = problem_context.get("problem_type")
        
        if problem_type == QuantumProblemType.OPTIMIZATION:
            return self._extract_optimization_insight(probabilities, circuit_info, problem_context)
        elif problem_type == QuantumProblemType.ARBITRAGE:
            return self._extract_arbitrage_insight(probabilities, circuit_info, problem_context)
        elif problem_type == QuantumProblemType.MACHINE_LEARNING:
            return self._extract_ml_insight(probabilities, circuit_info, problem_context)
        
        return None
    
    def _extract_optimization_insight(
        self,
        probabilities: Dict[str, float],
        circuit_info: Dict[str, Any],
        problem_context: Dict[str, Any]
    ) -> Optional[QuantumAlgorithmInsight]:
        """Extract insights for optimization problems."""
        # Find the state with highest probability (assumed to be solution)
        if not probabilities:
            return None
        
        best_state = max(probabilities.items(), key=lambda x: x[1])
        
        insight_text = f"Optimization suggests solution state '{best_state[0]}' with confidence {best_state[1]:.2f}."
        
        # Check if solution makes sense in context
        if problem_context.get("expected_solution_pattern"):
            expected_pattern = problem_context["expected_solution_pattern"]
            if best_state[0].startswith(expected_pattern):
                insight_text += " This matches the expected solution pattern."
                confidence = best_state[1] * 1.1
            else:
                insight_text += " This differs from the expected pattern."
                confidence = best_state[1] * 0.8
        else:
            confidence = best_state[1]
        
        insight_id = f"optimization_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type=circuit_info.get("algorithm", "unknown"),
            quantum_phenomenon="optimization_solution",
            insight_text=insight_text,
            confidence=min(1.0, confidence),
            evidence=[
                {"type": "optimization_result", "best_state": best_state[0], 
                 "probability": float(best_state[1])}
            ],
            created_at=datetime.utcnow().isoformat()
        )
    
    def _extract_arbitrage_insight(
        self,
        probabilities: Dict[str, float],
        circuit_info: Dict[str, Any],
        problem_context: Dict[str, Any]
    ) -> Optional[QuantumAlgorithmInsight]:
        """Extract insights for arbitrage problems."""
        # For arbitrage, we're looking for portfolio allocations
        # Each qubit might represent whether to include an asset
        
        if not probabilities:
            return None
        
        # Find most probable allocation
        best_allocation = max(probabilities.items(), key=lambda x: x[1])
        
        # Interpret allocation
        allocation_bits = best_allocation[0]
        included_assets = [i for i, bit in enumerate(allocation_bits) if bit == '1']
        
        insight_text = f"Quantum arbitrage suggests including assets {included_assets} "
        insight_text += f"with confidence {best_allocation[1]:.2f}."
        
        # Check if this is a diverse portfolio
        asset_count = len(included_assets)
        total_assets = len(allocation_bits)
        
        if 0.3 <= asset_count / total_assets <= 0.7:
            insight_text += " This represents a balanced portfolio."
            confidence = best_allocation[1] * 1.1
        else:
            insight_text += " Portfolio concentration may need review."
            confidence = best_allocation[1] * 0.9
        
        insight_id = f"arbitrage_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type=circuit_info.get("algorithm", "unknown"),
            quantum_phenomenon="portfolio_allocation",
            insight_text=insight_text,
            confidence=min(1.0, confidence),
            evidence=[
                {"type": "arbitrage_allocation", "allocation": best_allocation[0],
                 "included_assets": included_assets, "probability": float(best_allocation[1])}
            ],
            created_at=datetime.utcnow().isoformat()
        )
    
    def _extract_ml_insight(
        self,
        probabilities: Dict[str, float],
        circuit_info: Dict[str, Any],
        problem_context: Dict[str, Any]
    ) -> Optional[QuantumAlgorithmInsight]:
        """Extract insights for machine learning problems."""
        # For ML, probabilities might represent class predictions
        
        if not probabilities:
            return None
        
        # Find most probable class
        best_prediction = max(probabilities.items(), key=lambda x: x[1])
        
        insight_text = f"Quantum ML predicts class '{best_prediction[0]}' "
        insight_text += f"with confidence {best_prediction[1]:.2f}."
        
        # Check confidence level
        if best_prediction[1] > 0.8:
            insight_text += " High confidence prediction."
            confidence = best_prediction[1]
        elif best_prediction[1] > 0.6:
            insight_text += " Moderate confidence prediction."
            confidence = best_prediction[1]
        else:
            insight_text += " Low confidence, model may need more training."
            confidence = best_prediction[1] * 0.8
        
        insight_id = f"ml_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type=circuit_info.get("algorithm", "unknown"),
            quantum_phenomenon="classification",
            insight_text=insight_text,
            confidence=min(1.0, confidence),
            evidence=[
                {"type": "ml_prediction", "predicted_class": best_prediction[0],
                 "confidence": float(best_prediction[1])}
            ],
            created_at=datetime.utcnow().isoformat()
        )
    
    def _calculate_correlations(self, probabilities: Dict[str, float]) -> Dict[str, float]:
        """Calculate correlations between qubits in measurement results."""
        correlations = {}
        
        if not probabilities:
            return correlations
        
        states = list(probabilities.keys())
        if not states:
            return correlations
        
        qubit_count = len(states[0])
        
        # Calculate pairwise correlations
        for i in range(qubit_count):
            for j in range(i + 1, qubit_count):
                # Calculate correlation between qubit i and j
                exp_ij = 0.0
                exp_i = 0.0
                exp_j = 0.0
                
                for state, prob in probabilities.items():
                    bit_i = 1 if state[i] == '1' else -1  # Map to ±1
                    bit_j = 1 if state[j] == '1' else -1
                    
                    exp_ij += prob * bit_i * bit_j
                    exp_i += prob * bit_i
                    exp_j += prob * bit_j
                
                # Correlation
                var_i = 1.0 - exp_i**2  # For ±1 variables, variance = 1 - mean²
                var_j = 1.0 - exp_j**2
                
                if var_i > 0 and var_j > 0:
                    correlation = (exp_ij - exp_i * exp_j) / np.sqrt(var_i * var_j)
                    correlations[f"q{i}_q{j}"] = correlation
        
        return correlations
    
    def _assess_superposition(
        self,
        state_analysis: QuantumStateAnalysis,
        circuit_executions: List[Dict[str, Any]]
    ) -> float:
        """Assess superposition in quantum states."""
        if state_analysis.measurement_results:
            # Use measurement results to assess superposition
            probs = list(state_analysis.measurement_results.values())
            if probs:
                entropy = -sum(p * np.log2(p) for p in probs if p > 0)
                max_entropy = np.log2(len(probs))
                if max_entropy > 0:
                    return entropy / max_entropy
        
        # Default moderate superposition
        return 0.5
    
    def _assess_entanglement(
        self,
        state_analysis: QuantumStateAnalysis,
        circuit_executions: List[Dict[str, Any]]
    ) -> float:
        """Assess entanglement in quantum states."""
        if state_analysis.entanglement_measures:
            # Use provided entanglement measures
            avg_entanglement = np.mean(list(state_analysis.entanglement_measures.values()))
            return min(1.0, avg_entanglement)
        
        # Check circuit executions for entanglement signatures
        entanglement_evidence = 0
        for execution in circuit_executions:
            if execution.get("entanglement_signature", False):
                entanglement_evidence += 0.2
        
        return min(1.0, entanglement_evidence)
    
    def _assess_interference(
        self,
        state_analysis: QuantumStateAnalysis,
        circuit_executions: List[Dict[str, Any]]
    ) -> float:
        """Assess interference in quantum states."""
        if state_analysis.measurement_results:
            # Look for interference patterns in measurements
            probs = list(state_analysis.measurement_results.values())
            if len(probs) >= 3:
                variance = np.var(probs)
                max_variance = 0.25  # Maximum variance for probabilities
                return min(1.0, variance / max_variance)
        
        return 0.3  # Default moderate interference
    
    def _analyze_phenomenon_evidence(
        self,
        phenomenon: QuantumPhenomenon,
        evidence: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze evidence for a quantum phenomenon."""
        analysis = {
            "evidence_count": len(evidence),
            "strength_scores": [],
            "consistency_score": 0.0,
        }
        
        if not evidence:
            return analysis
        
        # Calculate strength scores from evidence
        strength_scores = []
        for item in evidence:
            strength = item.get("strength", 0.5)
            strength_scores.append(strength)
        
        analysis["strength_scores"] = strength_scores
        analysis["average_strength"] = np.mean(strength_scores) if strength_scores else 0.0
        
        # Check consistency
        if len(evidence) > 1:
            # Simple consistency check
            consistency = 1.0 - np.std(strength_scores)
            analysis["consistency_score"] = max(0.0, consistency)
        
        return analysis
    
    def _generate_phenomenon_insight(
        self,
        phenomenon: QuantumPhenomenon,
        analysis: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Generate insight text about a quantum phenomenon."""
        strength = analysis.get("average_strength", 0.5)
        evidence_count = analysis.get("evidence_count", 0)
        
        if phenomenon == QuantumPhenomenon.ENTANGLEMENT:
            if strength > 0.7:
                return f"Strong evidence of quantum entanglement ({evidence_count} observations). Entanglement is being effectively utilized."
            elif strength > 0.4:
                return f"Moderate evidence of quantum entanglement ({evidence_count} observations). Entanglement may be present but not dominant."
            else:
                return f"Weak evidence of quantum entanglement ({evidence_count} observations). Circuit may not be leveraging entanglement effectively."
        
        elif phenomenon == QuantumPhenomenon.SUPERPOSITION:
            if strength > 0.7:
                return f"Strong superposition effects observed ({evidence_count} observations). Quantum parallelism is being exploited."
            elif strength > 0.4:
                return f"Moderate superposition observed ({evidence_count} observations). Some quantum advantage may be present."
            else:
                return f"Limited superposition observed ({evidence_count} observations). Circuit may be mostly classical."
        
        elif phenomenon == QuantumPhenomenon.INTERFERENCE:
            if strength > 0.7:
                return f"Strong quantum interference patterns ({evidence_count} observations). Constructive/destructive interference is shaping results."
            elif strength > 0.4:
                return f"Moderate interference effects ({evidence_count} observations). Some quantum phase effects present."
            else:
                return f"Limited interference observed ({evidence_count} observations). Classical behavior may dominate."
        
        else:
            return f"Observed {phenomenon.value} with strength {strength:.2f} ({evidence_count} observations)."
    
    def _calculate_phenomenon_confidence(
        self,
        phenomenon: QuantumPhenomenon,
        analysis: Dict[str, Any]
    ) -> float:
        """Calculate confidence in phenomenon understanding."""
        strength = analysis.get("average_strength", 0.5)
        consistency = analysis.get("consistency_score", 0.5)
        evidence_count = analysis.get("evidence_count", 0)
        
        # Base confidence on strength and consistency
        base_confidence = (strength + consistency) / 2
        
        # Adjust for evidence count
        evidence_factor = min(1.0, evidence_count / 5)  # Cap at 5 pieces of evidence
        
        confidence = 0.7 * base_confidence + 0.3 * evidence_factor
        
        return min(1.0, max(0.0, confidence))
    
    def _analyze_convergence(
        self,
        convergence_history: List[float],
        problem_type: QuantumProblemType
    ) -> Optional[QuantumAlgorithmInsight]:
        """Analyze convergence of variational algorithm."""
        if len(convergence_history) < 2:
            return None
        
        # Calculate convergence metrics
        final_value = convergence_history[-1]
        initial_value = convergence_history[0]
        improvement = initial_value - final_value  # Assuming minimization
        
        convergence_rate = self._calculate_convergence_rate(convergence_history)
        
        # Generate insight
        if convergence_rate > 0.8:
            insight_text = f"Algorithm converged rapidly with {improvement:.3f} improvement."
            confidence = 0.8
        elif convergence_rate > 0.5:
            insight_text = f"Moderate convergence with {improvement:.3f} improvement."
            confidence = 0.6
        else:
            insight_text = f"Slow convergence, only {improvement:.3f} improvement."
            confidence = 0.4
        
        # Add problem-specific context
        if problem_type == QuantumProblemType.OPTIMIZATION:
            insight_text += " The optimization found a good solution."
        
        insight_id = f"convergence_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type="variational",
            quantum_phenomenon="convergence",
            insight_text=insight_text,
            confidence=confidence,
            evidence=[
                {"type": "convergence_analysis", "initial_value": float(initial_value),
                 "final_value": float(final_value), "improvement": float(improvement),
                 "convergence_rate": float(convergence_rate)}
            ],
            created_at=datetime.utcnow().isoformat()
        )
    
    def _analyze_parameter_sensitivity(
        self,
        sensitivity_data: Dict[str, List[float]],
        problem_type: QuantumProblemType
    ) -> Optional[QuantumAlgorithmInsight]:
        """Analyze parameter sensitivity of quantum circuit."""
        if not sensitivity_data:
            return None
        
        # Calculate average sensitivity
        all_sensitivities = []
        for param, sensitivities in sensitivity_data.items():
            all_sensitivities.extend(sensitivities)
        
        avg_sensitivity = np.mean(all_sensitivities) if all_sensitivities else 0.0
        max_sensitivity = np.max(all_sensitivities) if all_sensitivities else 0.0
        
        # Generate insight
        if max_sensitivity > 0.5:
            insight_text = f"High parameter sensitivity detected (max: {max_sensitivity:.3f}). Circuit is highly tunable."
            confidence = 0.7
        elif avg_sensitivity > 0.2:
            insight_text = f"Moderate parameter sensitivity (avg: {avg_sensitivity:.3f}). Circuit responds to tuning."
            confidence = 0.6
        else:
            insight_text = f"Low parameter sensitivity (avg: {avg_sensitivity:.3f}). Circuit is robust but less tunable."
            confidence = 0.5
        
        insight_id = f"sensitivity_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type="parameterized",
            quantum_phenomenon="parameter_sensitivity",
            insight_text=insight_text,
            confidence=confidence,
            evidence=[
                {"type": "sensitivity_analysis", "average_sensitivity": float(avg_sensitivity),
                 "max_sensitivity": float(max_sensitivity), "parameter_count": len(sensitivity_data)}
            ],
            created_at=datetime.utcnow().isoformat()
        )
    
    def _analyze_quantum_advantage(
        self,
        advantage_metrics: Dict[str, float],
        problem_type: QuantumProblemType
    ) -> Optional[QuantumAlgorithmInsight]:
        """Analyze quantum advantage metrics."""
        if not advantage_metrics:
            return None
        
        quantum_score = advantage_metrics.get("quantum_score", 0.0)
        classical_baseline = advantage_metrics.get("classical_baseline", 0.0)
        
        advantage_ratio = quantum_score / classical_baseline if classical_baseline > 0 else 0.0
        
        # Generate insight
        if advantage_ratio > 1.5:
            insight_text = f"Strong quantum advantage: {advantage_ratio:.2f}x better than classical."
            confidence = 0.8
        elif advantage_ratio > 1.1:
            insight_text = f"Moderate quantum advantage: {advantage_ratio:.2f}x better than classical."
            confidence = 0.6
        elif advantage_ratio > 0.9:
            insight_text = f"Parity with classical: {advantage_ratio:.2f}x of classical performance."
            confidence = 0.5
        else:
            insight_text = f"Classical advantage: quantum performs at {advantage_ratio:.2f}x of classical."
            confidence = 0.4
        
        insight_id = f"advantage_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return QuantumAlgorithmInsight(
            insight_id=insight_id,
            algorithm_type="comparative",
            quantum_phenomenon="quantum_advantage",
            insight_text=insight_text,
            confidence=confidence,
            evidence=[
                {"type": "advantage_analysis", "quantum_score": float(quantum_score),
                 "classical_baseline": float(classical_baseline), "advantage_ratio": float(advantage_ratio)}
            ],
            created_at=datetime.utcnow().isoformat()
        )
    
    def _calculate_convergence_rate(self, history: List[float]) -> float:
        """Calculate convergence rate from history."""
        if len(history) < 3:
            return 0.5  # Default moderate convergence
        
        # Calculate improvement per iteration
        improvements = []
        for i in range(1, len(history)):
            improvement = history[i-1] - history[i]  # Assuming minimization
            if history[i-1] != 0:
                relative_improvement = improvement / abs(history[i-1])
                improvements.append(relative_improvement)
        
        if not improvements:
            return 0.5
        
        # Average improvement rate
        avg_improvement = np.mean(improvements)
        
        # Convert to 0-1 scale
        convergence_rate = min(1.0, avg_improvement * 10)  # Scale factor
        
        return max(0.0, convergence_rate)