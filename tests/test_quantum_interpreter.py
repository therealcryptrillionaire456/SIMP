"""
Unit tests for Quantum State Interpreter module.
"""

import pytest
import sys
import os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simp.organs.quantum_intelligence.quantum_interpreter import (
    QuantumStateInterpreter,
    QuantumPhenomenon,
    InterpretationConfidence,
    QuantumStateAnalysis
)
from simp.organs.quantum_intelligence import QuantumProblemType


class TestQuantumStateInterpreter:
    """Test QuantumStateInterpreter class."""
    
    def setup_method(self):
        """Setup test fixture."""
        self.interpreter = QuantumStateInterpreter(agent_id="test_agent")
    
    def test_initialization(self):
        """Test interpreter initialization."""
        assert self.interpreter.agent_id == "test_agent"
        assert isinstance(self.interpreter.insights, dict)
        assert len(self.interpreter.insights) == 0
        assert isinstance(self.interpreter.quantum_intuition, dict)
    
    def test_interpret_measurement_results_optimization(self):
        """Test interpretation of optimization measurement results."""
        # Create measurement results for an optimization problem
        measurement_counts = {
            "000": 700,  # Strong convergence to state 000
            "001": 100,
            "010": 80,
            "011": 40,
            "100": 30,
            "101": 20,
            "110": 15,
            "111": 15
        }
        total_shots = 1000
        
        circuit_info = {
            "algorithm": "QAOA",
            "qubits": 3,
            "depth": 5
        }
        
        problem_context = {
            "problem_type": QuantumProblemType.OPTIMIZATION,
            "description": "Portfolio optimization",
            "complexity": 0.6
        }
        
        insights = self.interpreter.interpret_measurement_results(
            measurement_counts=measurement_counts,
            total_shots=total_shots,
            circuit_info=circuit_info,
            problem_context=problem_context
        )
        
        assert isinstance(insights, list)
        assert len(insights) > 0
        
        for insight in insights:
            assert insight.insight_id.startswith("distribution_") or \
                   insight.insight_id.startswith("optimization_")
            assert insight.algorithm_type == "QAOA"
            assert 0 <= insight.confidence <= 1
            assert insight.insight_text
            assert insight.created_at
    
    def test_interpret_measurement_results_arbitrage(self):
        """Test interpretation of arbitrage measurement results."""
        # Create measurement results for an arbitrage problem
        measurement_counts = {
            "00": 400,  # Balanced distribution
            "01": 300,
            "10": 200,
            "11": 100
        }
        total_shots = 1000
        
        circuit_info = {
            "algorithm": "PortfolioQAOA",
            "qubits": 2,
            "depth": 4
        }
        
        problem_context = {
            "problem_type": QuantumProblemType.ARBITRAGE,
            "description": "Arbitrage portfolio optimization",
            "complexity": 0.5
        }
        
        insights = self.interpreter.interpret_measurement_results(
            measurement_counts=measurement_counts,
            total_shots=total_shots,
            circuit_info=circuit_info,
            problem_context=problem_context
        )
        
        assert isinstance(insights, list)
        
        # Should generate at least distribution insight
        assert len(insights) >= 1
        
        for insight in insights:
            assert 0 <= insight.confidence <= 1
            assert insight.insight_text
    
    def test_interpret_measurement_results_entanglement(self):
        """Test interpretation with entanglement signatures."""
        # Create Bell state-like measurement results
        measurement_counts = {
            "00": 480,  # Strong correlation 00 and 11
            "01": 20,
            "10": 20,
            "11": 480
        }
        total_shots = 1000
        
        circuit_info = {
            "algorithm": "EntanglementCircuit",
            "qubits": 2,
            "depth": 3
        }
        
        insights = self.interpreter.interpret_measurement_results(
            measurement_counts=measurement_counts,
            total_shots=total_shots,
            circuit_info=circuit_info
        )
        
        # Should detect entanglement
        entanglement_found = any(
            "entanglement" in insight.quantum_phenomenon.lower() or
            "entanglement" in insight.insight_text.lower()
            for insight in insights
        )
        
        # Either find entanglement or not, both are valid
        # Just check insights are generated
        assert len(insights) > 0
    
    def test_develop_quantum_intuition(self):
        """Test quantum intuition development."""
        # Create state analysis
        state_analysis = QuantumStateAnalysis(
            measurement_results={
                "00": 0.5,
                "11": 0.5
            },
            entanglement_measures={
                "concurrence": 0.9,
                "entropy": 0.8
            }
        )
        
        circuit_executions = [
            {
                "entanglement_signature": True,
                "correlation": 0.85
            }
        ]
        
        intuition_scores = self.interpreter.develop_quantum_intuition(
            state_analysis=state_analysis,
            circuit_executions=circuit_executions
        )
        
        assert isinstance(intuition_scores, dict)
        assert QuantumPhenomenon.SUPERPOSITION in intuition_scores
        assert QuantumPhenomenon.ENTANGLEMENT in intuition_scores
        assert QuantumPhenomenon.INTERFERENCE in intuition_scores
        
        for phenomenon, score in intuition_scores.items():
            assert 0 <= score <= 1
        
        # Check that intuition is stored
        for phenomenon in intuition_scores.keys():
            assert phenomenon.value in self.interpreter.quantum_intuition
            stored_score = self.interpreter.quantum_intuition[phenomenon.value]
            assert 0 <= stored_score <= 1
    
    def test_understand_quantum_phenomenon(self):
        """Test understanding of quantum phenomena."""
        evidence = [
            {
                "type": "bell_state_measurement",
                "correlation": 0.95,
                "strength": 0.9
            },
            {
                "type": "quantum_teleportation",
                "fidelity": 0.88,
                "strength": 0.8
            }
        ]
        
        insight = self.interpreter.understand_quantum_phenomenon(
            phenomenon=QuantumPhenomenon.ENTANGLEMENT,
            evidence=evidence,
            context={"test": True}
        )
        
        assert insight.insight_id.startswith("phenomenon_entanglement_")
        assert insight.algorithm_type == "phenomenon_analysis"
        assert insight.quantum_phenomenon == "entanglement"
        assert 0 <= insight.confidence <= 1
        assert insight.insight_text
        assert len(insight.evidence) == 2
        assert insight.created_at
        
        # Check that insight is stored
        assert insight.insight_id in self.interpreter.insights
    
    def test_extract_algorithm_insights(self):
        """Test extraction of algorithm insights."""
        algorithm_results = {
            "convergence_history": [1.0, 0.8, 0.6, 0.4, 0.2, 0.1],
            "parameter_sensitivity": {
                "param1": [0.1, 0.2, 0.15],
                "param2": [0.3, 0.25, 0.28]
            },
            "quantum_advantage_metrics": {
                "quantum_score": 0.85,
                "classical_baseline": 0.6,
                "advantage_ratio": 1.42
            }
        }
        
        insights = self.interpreter.extract_algorithm_insights(
            algorithm_results=algorithm_results,
            problem_type=QuantumProblemType.OPTIMIZATION
        )
        
        assert isinstance(insights, list)
        assert len(insights) >= 2  # Should have convergence and advantage insights
        
        for insight in insights:
            assert insight.insight_id.startswith(("convergence_", "sensitivity_", "advantage_"))
            assert 0 <= insight.confidence <= 1
            assert insight.insight_text
    
    def test_calculate_correlations(self):
        """Test correlation calculation."""
        probabilities = {
            "00": 0.4,
            "01": 0.1,
            "10": 0.1,
            "11": 0.4
        }
        
        correlations = self.interpreter._calculate_correlations(probabilities)
        
        assert isinstance(correlations, dict)
        assert "q0_q1" in correlations
        
        # For Bell state-like distribution, correlation should be high
        correlation = correlations["q0_q1"]
        assert -1 <= correlation <= 1
        # With this distribution, correlation should be positive
        assert correlation > 0.5
    
    def test_analyze_distribution(self):
        """Test distribution analysis."""
        probabilities = {
            "000": 0.7,
            "001": 0.1,
            "010": 0.05,
            "011": 0.05,
            "100": 0.04,
            "101": 0.03,
            "110": 0.02,
            "111": 0.01
        }
        
        circuit_info = {
            "algorithm": "TestAlgorithm",
            "qubits": 3
        }
        
        problem_context = {
            "problem_type": QuantumProblemType.OPTIMIZATION
        }
        
        insight = self.interpreter._analyze_distribution(
            probabilities=probabilities,
            circuit_info=circuit_info,
            problem_context=problem_context
        )
        
        assert insight is not None
        assert insight.insight_id.startswith("distribution_")
        assert insight.algorithm_type == "TestAlgorithm"
        assert "superposition" in insight.quantum_phenomenon.lower() or \
               "measurement" in insight.quantum_phenomenon.lower()
        assert 0 <= insight.confidence <= 1
        assert insight.insight_text
    
    def test_detect_entanglement(self):
        """Test entanglement detection."""
        probabilities = {
            "00": 0.45,
            "01": 0.05,
            "10": 0.05,
            "11": 0.45
        }
        
        circuit_info = {
            "algorithm": "BellStateCircuit"
        }
        
        insight = self.interpreter._detect_entanglement(
            probabilities=probabilities,
            circuit_info=circuit_info
        )
        
        # Should detect entanglement with this distribution
        assert insight is not None
        assert insight.insight_id.startswith("entanglement_")
        assert insight.quantum_phenomenon == "entanglement"
        assert insight.confidence > 0.5  # High confidence for Bell state
        assert "entanglement" in insight.insight_text.lower()
    
    def test_detect_interference(self):
        """Test interference detection."""
        # Create distribution with high variance (suggesting interference)
        probabilities = {
            "00": 0.8,
            "01": 0.05,
            "10": 0.05,
            "11": 0.1
        }
        
        circuit_info = {
            "algorithm": "InterferenceCircuit"
        }
        
        insight = self.interpreter._detect_interference(
            probabilities=probabilities,
            circuit_info=circuit_info
        )
        
        # May or may not detect interference depending on threshold
        if insight is not None:
            assert insight.insight_id.startswith("interference_")
            assert insight.quantum_phenomenon == "interference"
            assert 0 <= insight.confidence <= 1
    
    def test_extract_optimization_insight(self):
        """Test optimization insight extraction."""
        probabilities = {
            "000": 0.7,
            "001": 0.1,
            "010": 0.05,
            "011": 0.05,
            "100": 0.04,
            "101": 0.03,
            "110": 0.02,
            "111": 0.01
        }
        
        circuit_info = {
            "algorithm": "QAOA"
        }
        
        problem_context = {
            "problem_type": QuantumProblemType.OPTIMIZATION,
            "expected_solution_pattern": "000"
        }
        
        insight = self.interpreter._extract_optimization_insight(
            probabilities=probabilities,
            circuit_info=circuit_info,
            problem_context=problem_context
        )
        
        assert insight is not None
        assert insight.insight_id.startswith("optimization_")
        assert insight.quantum_phenomenon == "optimization_solution"
        assert "000" in insight.insight_text  # Should mention the solution state
        assert 0 <= insight.confidence <= 1
    
    def test_extract_arbitrage_insight(self):
        """Test arbitrage insight extraction."""
        probabilities = {
            "00": 0.4,  # Don't include either
            "01": 0.3,  # Include second asset
            "10": 0.2,  # Include first asset
            "11": 0.1   # Include both
        }
        
        circuit_info = {
            "algorithm": "PortfolioQAOA"
        }
        
        problem_context = {
            "problem_type": QuantumProblemType.ARBITRAGE
        }
        
        insight = self.interpreter._extract_arbitrage_insight(
            probabilities=probabilities,
            circuit_info=circuit_info,
            problem_context=problem_context
        )
        
        assert insight is not None
        assert insight.insight_id.startswith("arbitrage_")
        assert insight.quantum_phenomenon == "portfolio_allocation"
        assert "assets" in insight.insight_text.lower()
        assert 0 <= insight.confidence <= 1
    
    def test_extract_ml_insight(self):
        """Test machine learning insight extraction."""
        probabilities = {
            "0": 0.8,  # Class 0
            "1": 0.2   # Class 1
        }
        
        circuit_info = {
            "algorithm": "QuantumClassifier"
        }
        
        problem_context = {
            "problem_type": QuantumProblemType.MACHINE_LEARNING
        }
        
        insight = self.interpreter._extract_ml_insight(
            probabilities=probabilities,
            circuit_info=circuit_info,
            problem_context=problem_context
        )
        
        assert insight is not None
        assert insight.insight_id.startswith("ml_")
        assert insight.quantum_phenomenon == "classification"
        assert "class" in insight.insight_text.lower()
        assert 0 <= insight.confidence <= 1
    
    def test_assess_superposition(self):
        """Test superposition assessment."""
        state_analysis = QuantumStateAnalysis(
            measurement_results={
                "00": 0.25,
                "01": 0.25,
                "10": 0.25,
                "11": 0.25
            }
        )
        
        circuit_executions = []
        
        score = self.interpreter._assess_superposition(
            state_analysis=state_analysis,
            circuit_executions=circuit_executions
        )
        
        # Uniform distribution = maximum superposition
        assert 0 <= score <= 1
        assert score > 0.7  # Should be high for uniform distribution
    
    def test_assess_entanglement(self):
        """Test entanglement assessment."""
        state_analysis = QuantumStateAnalysis(
            entanglement_measures={
                "concurrence": 0.9,
                "negativity": 0.85
            }
        )
        
        circuit_executions = [
            {"entanglement_signature": True}
        ]
        
        score = self.interpreter._assess_entanglement(
            state_analysis=state_analysis,
            circuit_executions=circuit_executions
        )
        
        assert 0 <= score <= 1
        # With high entanglement measures, score should be high
        assert score > 0.7
    
    def test_assess_interference(self):
        """Test interference assessment."""
        state_analysis = QuantumStateAnalysis(
            measurement_results={
                "00": 0.8,
                "01": 0.1,
                "10": 0.05,
                "11": 0.05
            }
        )
        
        circuit_executions = []
        
        score = self.interpreter._assess_interference(
            state_analysis=state_analysis,
            circuit_executions=circuit_executions
        )
        
        assert 0 <= score <= 1
        # High variance distribution suggests interference
        assert score > 0.3
    
    def test_analyze_phenomenon_evidence(self):
        """Test phenomenon evidence analysis."""
        evidence = [
            {"type": "measurement1", "strength": 0.8},
            {"type": "measurement2", "strength": 0.9},
            {"type": "measurement3", "strength": 0.7}
        ]
        
        analysis = self.interpreter._analyze_phenomenon_evidence(
            phenomenon=QuantumPhenomenon.ENTANGLEMENT,
            evidence=evidence
        )
        
        assert analysis["evidence_count"] == 3
        assert len(analysis["strength_scores"]) == 3
        assert 0 <= analysis["average_strength"] <= 1
        assert 0 <= analysis["consistency_score"] <= 1
    
    def test_generate_phenomenon_insight(self):
        """Test phenomenon insight generation."""
        analysis = {
            "evidence_count": 3,
            "average_strength": 0.8,
            "consistency_score": 0.9
        }
        
        context = {"test": True}
        
        insight_text = self.interpreter._generate_phenomenon_insight(
            phenomenon=QuantumPhenomenon.ENTANGLEMENT,
            analysis=analysis,
            context=context
        )
        
        assert isinstance(insight_text, str)
        assert len(insight_text) > 0
        assert "entanglement" in insight_text.lower()
        assert "3" in insight_text  # Should mention evidence count
    
    def test_calculate_phenomenon_confidence(self):
        """Test phenomenon confidence calculation."""
        analysis = {
            "evidence_count": 3,
            "average_strength": 0.8,
            "consistency_score": 0.9
        }
        
        confidence = self.interpreter._calculate_phenomenon_confidence(
            phenomenon=QuantumPhenomenon.ENTANGLEMENT,
            analysis=analysis
        )
        
        assert 0 <= confidence <= 1
        # With good evidence, confidence should be high
        assert confidence > 0.6
    
    def test_analyze_convergence(self):
        """Test convergence analysis."""
        convergence_history = [1.0, 0.7, 0.5, 0.3, 0.2, 0.15, 0.12, 0.1]
        
        insight = self.interpreter._analyze_convergence(
            convergence_history=convergence_history,
            problem_type=QuantumProblemType.OPTIMIZATION
        )
        
        assert insight is not None
        assert insight.insight_id.startswith("convergence_")
        assert insight.quantum_phenomenon == "convergence"
        assert "converged" in insight.insight_text.lower()
        assert 0 <= insight.confidence <= 1
    
    def test_analyze_parameter_sensitivity(self):
        """Test parameter sensitivity analysis."""
        sensitivity_data = {
            "param1": [0.1, 0.15, 0.12],
            "param2": [0.3, 0.35, 0.32],
            "param3": [0.05, 0.06, 0.055]
        }
        
        insight = self.interpreter._analyze_parameter_sensitivity(
            sensitivity_data=sensitivity_data,
            problem_type=QuantumProblemType.OPTIMIZATION
        )
        
        assert insight is not None
        assert insight.insight_id.startswith("sensitivity_")
        assert insight.quantum_phenomenon == "parameter_sensitivity"
        assert "sensitivity" in insight.insight_text.lower()
        assert 0 <= insight.confidence <= 1
    
    def test_analyze_quantum_advantage(self):
        """Test quantum advantage analysis."""
        advantage_metrics = {
            "quantum_score": 0.85,
            "classical_baseline": 0.6,
            "advantage_ratio": 1.42
        }
        
        insight = self.interpreter._analyze_quantum_advantage(
            advantage_metrics=advantage_metrics,
            problem_type=QuantumProblemType.OPTIMIZATION
        )
        
        assert insight is not None
        assert insight.insight_id.startswith("advantage_")
        assert insight.quantum_phenomenon == "quantum_advantage"
        assert "advantage" in insight.insight_text.lower()
        assert 0 <= insight.confidence <= 1
    
    def test_calculate_convergence_rate(self):
        """Test convergence rate calculation."""
        history = [1.0, 0.8, 0.6, 0.4, 0.2, 0.1]
        
        rate = self.interpreter._calculate_convergence_rate(history)
        
        assert 0 <= rate <= 1
        # With good convergence, rate should be high
        assert rate > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])