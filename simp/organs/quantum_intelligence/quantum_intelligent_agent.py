"""
Quantum Intelligent Agent - Tri-Module Integration

This module integrates all three quantum intelligence modules:
1. Quantum Algorithm Designer
2. Quantum State Interpreter  
3. Quantum Skill Evolver

Creates a complete quantum-intelligent agent that can:
- Design and evolve quantum algorithms
- Interpret quantum states and phenomena
- Develop quantum intuition and skills
- Learn and improve over time
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import hashlib

from .quantum_designer import (
    QuantumAlgorithmDesigner,
    QuantumProblemType,
    CircuitDesignStrategy,
    QuantumCircuitDesign
)
from .quantum_interpreter import (
    QuantumStateInterpreter,
    QuantumPhenomenon,
    QuantumAlgorithmInsight,
    QuantumStateAnalysis
)
from .quantum_evolver import (
    QuantumSkillEvolver,
    LearningExperience,
    EvolutionEvent,
    EvolutionTrigger,
    QuantumSkill
)
from . import QuantumIntelligenceLevel, QuantumIntelligenceState


class QuantumIntelligentAgent:
    """A quantum-intelligent agent that integrates all three modules."""
    
    def __init__(self, agent_id: str, initial_level: str = "quantum_aware"):
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"quantum.agent.{agent_id}")
        
        # Initialize the three modules
        self.designer = QuantumAlgorithmDesigner(agent_id)
        self.interpreter = QuantumStateInterpreter(agent_id)
        self.evolver = QuantumSkillEvolver(agent_id)
        
        # Agent state
        self.intelligence_level = QuantumIntelligenceLevel(initial_level)
        self.quantum_intuition: Dict[str, float] = {}
        self.circuit_designs: Dict[str, QuantumCircuitDesign] = {}
        self.insights: Dict[str, QuantumAlgorithmInsight] = {}
        self.skills: Dict[str, QuantumSkill] = {}
        
        # Performance tracking
        self.performance_history: List[Dict[str, Any]] = []
        self.quantum_advantage_history: List[float] = []
        
        self.logger.info(f"Created quantum intelligent agent {agent_id} at level {self.intelligence_level.value}")
    
    def solve_quantum_problem(
        self,
        problem_description: str,
        problem_type: QuantumProblemType,
        qubits: int,
        strategy: CircuitDesignStrategy = CircuitDesignStrategy.HYBRID,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Solve a quantum problem using integrated intelligence."""
        # Coerce string → enum (callers often pass raw strings like "optimization" / "hybrid")
        if isinstance(problem_type, str):
            problem_type = QuantumProblemType(problem_type)
        if isinstance(strategy, str):
            strategy = CircuitDesignStrategy(strategy)
        self.logger.info(f"Solving {problem_type.value} problem: {problem_description[:50]}...")
        
        # Step 1: Get skill recommendation
        problem_complexity = self._estimate_problem_complexity(problem_description, qubits)
        skill_recommendation, skill_details = self.evolver.get_skill_recommendation(
            problem_type, problem_complexity
        )
        
        # Step 2: Design quantum circuit
        circuit_design = self.designer.design_circuit(
            problem_type=problem_type,
            qubits=qubits,
            strategy=strategy,
            constraints=constraints
        )
        
        # Store design
        self.circuit_designs[circuit_design.circuit_id] = circuit_design
        
        # Step 3: Simulate/Execute quantum circuit
        # (In production, this would connect to actual quantum hardware)
        execution_result = self._simulate_quantum_execution(circuit_design, problem_description)
        
        # Step 4: Interpret results
        insights = self.interpreter.interpret_measurement_results(
            measurement_counts=execution_result["measurement_counts"],
            total_shots=execution_result["total_shots"],
            circuit_info={
                "algorithm": circuit_design.problem_type.value,
                "qubits": circuit_design.qubits,
                "depth": circuit_design.depth
            },
            problem_context={
                "problem_type": problem_type,
                "description": problem_description,
                "complexity": problem_complexity
            }
        )
        
        # Store insights
        for insight in insights:
            self.insights[insight.insight_id] = insight
        
        # Step 5: Learn from experience
        learning_experience = self.evolver.learn_from_experience(
            skill_id=skill_details.get("skill_id", "unknown"),
            problem_type=problem_type,
            outcome=execution_result["outcome"],
            performance_score=execution_result["performance_score"],
            quantum_advantage=execution_result["quantum_advantage"],
            insights=[insight.insight_text for insight in insights],
            metadata={
                "circuit_id": circuit_design.circuit_id,
                "problem_description": problem_description,
                "strategy": strategy.value
            }
        )
        
        # Step 6: Update quantum intuition
        state_analysis = QuantumStateAnalysis(
            measurement_results=execution_result["measurement_probabilities"]
        )
        
        intuition_scores = self.interpreter.develop_quantum_intuition(
            state_analysis=state_analysis,
            circuit_executions=[execution_result]
        )
        
        # Update agent's quantum intuition
        for phenomenon, score in intuition_scores.items():
            current_score = self.quantum_intuition.get(phenomenon.value, 0.0)
            new_score = 0.8 * current_score + 0.2 * score
            self.quantum_intuition[phenomenon.value] = new_score
        
        # Step 7: Track performance
        self.performance_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "problem_type": problem_type.value,
            "performance_score": execution_result["performance_score"],
            "quantum_advantage": execution_result["quantum_advantage"],
            "circuit_id": circuit_design.circuit_id,
            "skill_used": skill_details.get("skill_id", "unknown")
        })
        
        self.quantum_advantage_history.append(execution_result["quantum_advantage"])
        
        # Step 8: Check for intelligence level upgrade
        self._check_intelligence_level_upgrade()
        
        # Compile results
        result = {
            "success": execution_result["outcome"] == "success",
            "circuit_design": circuit_design,
            "execution_result": execution_result,
            "insights": insights,
            "learning_experience": learning_experience,
            "quantum_intuition": intuition_scores,
            "skill_recommendation": {
                "recommendation": skill_recommendation,
                "details": skill_details
            },
            "agent_state": self.get_current_state()
        }
        
        self.logger.info(f"Problem solved with performance: {execution_result['performance_score']:.3f}")
        
        return result
    
    def evolve_quantum_algorithm(
        self,
        circuit_id: str,
        target_improvement: float = 0.1,
        evolution_focus: Optional[str] = None
    ) -> Dict[str, Any]:
        """Evolve a quantum algorithm based on past performance."""
        if circuit_id not in self.circuit_designs:
            raise ValueError(f"Circuit {circuit_id} not found")
        
        original_design = self.circuit_designs[circuit_id]
        
        # Get performance feedback from history
        performance_feedback = self._get_circuit_performance_feedback(circuit_id)
        
        # Evolve the circuit
        evolved_design = self.designer.evolve_circuit(
            circuit_id=circuit_id,
            fitness_feedback=performance_feedback,
            evolution_params={
                "mutation_rate": 0.15,
                "crossover_rate": 0.25,
                "focus": evolution_focus
            }
        )
        
        # Store evolved design
        self.circuit_designs[evolved_design.circuit_id] = evolved_design
        
        # Deliberately evolve relevant skills
        evolution_event = self.evolver.evolve_skill_deliberately(
            skill_id=self._get_relevant_skill_id(original_design.problem_type),
            evolution_focus=evolution_focus or "algorithm_evolution",
            resources={"circuit_id": circuit_id, "target_improvement": target_improvement}
        )
        
        # Extract insights about evolution
        evolution_insight = self.interpreter.understand_quantum_phenomenon(
            phenomenon=QuantumPhenomenon.ENTANGLEMENT,
            evidence=[
                {
                    "type": "circuit_evolution",
                    "original_circuit": original_design.circuit_id,
                    "evolved_circuit": evolved_design.circuit_id,
                    "fitness_improvement": evolved_design.fitness_score - original_design.fitness_score
                }
            ],
            context={"evolution_focus": evolution_focus}
        )
        
        self.insights[evolution_insight.insight_id] = evolution_insight
        
        result = {
            "original_design": original_design,
            "evolved_design": evolved_design,
            "fitness_improvement": evolved_design.fitness_score - original_design.fitness_score,
            "evolution_event": evolution_event,
            "evolution_insight": evolution_insight
        }
        
        self.logger.info(f"Evolved circuit {circuit_id} -> {evolved_design.circuit_id}, "
                        f"fitness: {original_design.fitness_score:.3f} -> {evolved_design.fitness_score:.3f}")
        
        return result
    
    def develop_quantum_phenomenon_understanding(
        self,
        phenomenon: QuantumPhenomenon,
        evidence_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Develop deep understanding of a quantum phenomenon."""
        self.logger.info(f"Developing understanding of {phenomenon.value}")
        
        # Interpret phenomenon from evidence
        insight = self.interpreter.understand_quantum_phenomenon(
            phenomenon=phenomenon,
            evidence=evidence_data,
            context={"agent_id": self.agent_id}
        )
        
        # Update quantum intuition
        state_analysis = QuantumStateAnalysis()
        intuition_scores = self.interpreter.develop_quantum_intuition(
            state_analysis=state_analysis,
            circuit_executions=evidence_data
        )
        
        # Update agent's quantum intuition
        if phenomenon.value in intuition_scores:
            current_score = self.quantum_intuition.get(phenomenon.value, 0.0)
            new_score = 0.9 * current_score + 0.1 * intuition_scores[phenomenon.value]
            self.quantum_intuition[phenomenon.value] = new_score
        
        # Learn from this understanding experience
        learning_experience = self.evolver.learn_from_experience(
            skill_id="phenomenon_understanding",
            problem_type=QuantumProblemType.SIMULATION,
            outcome="success",
            performance_score=insight.confidence,
            quantum_advantage=0.6,  # Understanding has inherent quantum advantage
            insights=[insight.insight_text],
            metadata={
                "phenomenon": phenomenon.value,
                "evidence_count": len(evidence_data),
                "insight_id": insight.insight_id
            }
        )
        
        # Store insight
        self.insights[insight.insight_id] = insight
        
        result = {
            "phenomenon": phenomenon.value,
            "insight": insight,
            "quantum_intuition_gain": intuition_scores.get(phenomenon.value, 0.0),
            "learning_experience": learning_experience,
            "current_intuition_score": self.quantum_intuition.get(phenomenon.value, 0.0)
        }
        
        self.logger.info(f"Developed {phenomenon.value} understanding with confidence {insight.confidence:.3f}")
        
        return result
    
    def optimize_quantum_skills(
        self,
        problem_type: QuantumProblemType,
        target_intelligence_level: Optional[QuantumIntelligenceLevel] = None
    ) -> Dict[str, Any]:
        """Optimize quantum skills for a problem type."""
        self.logger.info(f"Optimizing quantum skills for {problem_type.value}")
        
        # Assess current skill gaps
        target_level = target_intelligence_level or self.intelligence_level
        skill_gaps = self.evolver.assess_skill_gaps(target_level, [problem_type])
        
        # Develop pattern recognition
        patterns = self.evolver.develop_pattern_recognition(
            problem_type=problem_type,
            historical_data=self.performance_history,
            pattern_types=["success_patterns", "failure_patterns", "performance_trends"]
        )
        
        # Optimize strategy
        strategy_options = self._generate_strategy_options(problem_type)
        evaluation_metrics = {
            "quantum_advantage_weight": 0.7,
            "success_rate_weight": 0.3
        }
        
        optimized_strategy = self.evolver.optimize_quantum_strategy(
            problem_type=problem_type,
            strategy_options=strategy_options,
            evaluation_metrics=evaluation_metrics
        )
        
        # Create novel algorithm based on optimized strategy
        novel_algorithm = self.designer.create_novel_algorithm(
            problem_description=f"Optimized {problem_type.value} strategy",
            qubits=4,  # Default for strategy optimization
            inspiration=list(self.circuit_designs.values())[:3] if self.circuit_designs else None
        )
        
        # Store novel algorithm
        self.circuit_designs[novel_algorithm.circuit_id] = novel_algorithm
        
        result = {
            "skill_gaps": skill_gaps,
            "patterns_identified": patterns,
            "optimized_strategy": optimized_strategy,
            "novel_algorithm": novel_algorithm,
            "recommendations": skill_gaps.get("recommended_development", [])
        }
        
        self.logger.info(f"Skill optimization complete. Found {len(skill_gaps.get('missing_skills', []))} missing skills")
        
        return result
    
    def get_current_state(self) -> QuantumIntelligenceState:
        """Get current state of quantum intelligence."""
        # Calculate quantum intuition score (average of all phenomena)
        if self.quantum_intuition:
            intuition_score = sum(self.quantum_intuition.values()) / len(self.quantum_intuition)
        else:
            intuition_score = 0.3  # Default
        
        return QuantumIntelligenceState(
            agent_id=self.agent_id,
            intelligence_level=self.intelligence_level,
            quantum_skills=list(self.evolver.skills.values()),
            circuit_designs=list(self.circuit_designs.values()),
            insights=list(self.insights.values()),
            quantum_intuition_score=intuition_score,
            last_updated=datetime.utcnow().isoformat()
        )
    
    def generate_quantum_arb_recommendations(
        self,
        arbitrage_opportunities: List[Dict[str, Any]],
        capital: float,
        risk_tolerance: float = 0.3
    ) -> Dict[str, Any]:
        """Generate quantum-enhanced arbitrage recommendations."""
        self.logger.info(f"Generating quantum arb recommendations for {len(arbitrage_opportunities)} opportunities")
        
        # Convert arbitrage opportunities to quantum optimization problem
        problem_description = f"Optimize arbitrage portfolio with {len(arbitrage_opportunities)} opportunities"
        
        # Solve as quantum optimization problem
        result = self.solve_quantum_problem(
            problem_description=problem_description,
            problem_type=QuantumProblemType.ARBITRAGE,
            qubits=min(len(arbitrage_opportunities), 8),  # Cap at 8 qubits
            strategy=CircuitDesignStrategy.TEMPLATE,
            constraints={
                "max_depth": 15,
                "include_entanglement": True
            }
        )
        
        # Extract portfolio allocation from quantum results
        quantum_allocation = self._extract_arbitrage_allocation(
            result["execution_result"]["measurement_counts"],
            arbitrage_opportunities,
            capital
        )
        
        # Generate quantum insights for arbitrage
        arb_insights = []
        for insight in result["insights"]:
            if "arbitrage" in insight.insight_text.lower() or "portfolio" in insight.insight_text.lower():
                arb_insights.append(insight)
        
        # Calculate quantum advantage for arbitrage
        quantum_advantage = self._calculate_arbitrage_advantage(
            quantum_allocation,
            arbitrage_opportunities,
            result["execution_result"]["quantum_advantage"],
            capital
        )
        
        recommendations = {
            "quantum_allocation": quantum_allocation,
            "quantum_advantage": quantum_advantage,
            "insights": arb_insights,
            "expected_return": self._calculate_expected_return(quantum_allocation, arbitrage_opportunities),
            "risk_assessment": self._assess_arbitrage_risk(quantum_allocation, arbitrage_opportunities, risk_tolerance),
            "agent_confidence": result["agent_state"].quantum_intuition_score
        }
        
        self.logger.info(f"Quantum arb recommendations generated with {quantum_advantage:.3f} quantum advantage")
        
        return recommendations
    
    def _estimate_problem_complexity(
        self,
        problem_description: str,
        qubits: int
    ) -> float:
        """Estimate complexity of a quantum problem."""
        # Simple heuristic based on description length and qubits
        description_complexity = min(1.0, len(problem_description) / 500)  # Normalize to 0-1
        
        # Qubit complexity (exponential in qubits, but capped)
        qubit_complexity = min(1.0, qubits / 10)
        
        # Combined complexity
        complexity = 0.4 * description_complexity + 0.6 * qubit_complexity
        
        return complexity
    
    def _simulate_quantum_execution(
        self,
        circuit_design: QuantumCircuitDesign,
        problem_description: str
    ) -> Dict[str, Any]:
        """Simulate quantum circuit execution (for testing)."""
        # In production, this would connect to actual quantum hardware
        # For now, simulate results
        
        import random
        
        # Generate simulated measurement counts
        num_states = 2 ** circuit_design.qubits
        states = [format(i, f'0{circuit_design.qubits}b') for i in range(num_states)]
        
        # Create biased distribution (simulating algorithm doing something useful)
        if circuit_design.problem_type == QuantumProblemType.OPTIMIZATION:
            # Optimization tends to concentrate on a few states
            focus_states = random.sample(states, min(3, len(states)))
            base_prob = 0.7 / len(focus_states)
            other_prob = 0.3 / (len(states) - len(focus_states))
            
            measurement_counts = {}
            for state in states:
                if state in focus_states:
                    measurement_counts[state] = int(base_prob * 1024)
                else:
                    measurement_counts[state] = int(other_prob * 1024)
        
        elif circuit_design.problem_type == QuantumProblemType.ARBITRAGE:
            # Arbitrage: prefer states with balanced 0s and 1s (diversified portfolio)
            measurement_counts = {}
            for state in states:
                ones_count = state.count('1')
                # Prefer states with ~50% ones (balanced portfolio)
                balance_score = 1.0 - abs(ones_count / circuit_design.qubits - 0.5)
                measurement_counts[state] = int(balance_score * 100)
        
        else:
            # Uniform distribution for other problems
            measurement_counts = {state: 1024 // num_states for state in states}
        
        # Normalize to total shots
        total_shots = 1024
        current_total = sum(measurement_counts.values())
        if current_total != total_shots:
            scale_factor = total_shots / current_total
            measurement_counts = {k: int(v * scale_factor) for k, v in measurement_counts.items()}
        
        # Calculate probabilities
        measurement_probabilities = {k: v / total_shots for k, v in measurement_counts.items()}
        
        # Determine outcome
        max_prob = max(measurement_probabilities.values())
        if max_prob > 0.6:
            outcome = "success"
            performance_score = 0.3 + 0.7 * max_prob  # Scale to 0.3-1.0
        elif max_prob > 0.3:
            outcome = "partial"
            performance_score = 0.2 + 0.5 * max_prob  # Scale to 0.2-0.7
        else:
            outcome = "failure"
            performance_score = 0.1 + 0.3 * max_prob  # Scale to 0.1-0.4
        
        # Simulate quantum advantage
        # More complex circuits and higher qubit counts have higher potential advantage
        quantum_advantage = min(1.0, 0.2 + 0.1 * circuit_design.qubits + 0.05 * circuit_design.depth)
        
        return {
            "measurement_counts": measurement_counts,
            "measurement_probabilities": measurement_probabilities,
            "total_shots": total_shots,
            "outcome": outcome,
            "performance_score": performance_score,
            "quantum_advantage": quantum_advantage,
            "execution_time_ms": random.randint(100, 1000),
            "circuit_id": circuit_design.circuit_id
        }
    
    def _get_circuit_performance_feedback(self, circuit_id: str) -> float:
        """Get performance feedback for a circuit from history."""
        # Look for this circuit in performance history
        circuit_performances = [
            p["performance_score"] for p in self.performance_history
            if p.get("circuit_id") == circuit_id
        ]
        
        if circuit_performances:
            return sum(circuit_performances) / len(circuit_performances)
        
        # Default feedback based on circuit design
        if circuit_id in self.circuit_designs:
            design = self.circuit_designs[circuit_id]
            # Simple heuristic: more qubits and depth = potentially better
            return min(0.7, 0.3 + 0.02 * design.qubits + 0.01 * design.depth)
        
        return 0.5  # Default moderate performance
    
    def _get_relevant_skill_id(self, problem_type: QuantumProblemType) -> str:
        """Get ID of relevant skill for a problem type."""
        for skill in self.evolver.skills.values():
            if problem_type in skill.problem_types:
                return skill.skill_id
        
        # Create new skill if none found
        skill_id = f"{problem_type.value}_skill_{hashlib.md5(str(problem_type).encode()).hexdigest()[:8]}"
        self.evolver._create_new_skill(skill_id, problem_type)
        
        return skill_id
    
    def _check_intelligence_level_upgrade(self):
        """Check if agent should upgrade intelligence level."""
        current_level = self.intelligence_level
        next_level = self._get_next_intelligence_level(current_level)
        
        if next_level is None:
            return  # Already at highest level
        
        # Check upgrade conditions
        upgrade_score = self._calculate_upgrade_score()
        upgrade_threshold = self._get_upgrade_threshold(current_level)
        
        if upgrade_score >= upgrade_threshold:
            old_level = current_level
            self.intelligence_level = next_level
            
            self.logger.info(f"Agent upgraded from {old_level.value} to {next_level.value}")
            
            # Record upgrade in performance history
            self.performance_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "event": "intelligence_upgrade",
                "old_level": old_level.value,
                "new_level": next_level.value,
                "upgrade_score": upgrade_score
            })
    
    def _get_next_intelligence_level(self, current_level: QuantumIntelligenceLevel) -> Optional[QuantumIntelligenceLevel]:
        """Get next intelligence level."""
        levels = list(QuantumIntelligenceLevel)
        current_index = levels.index(current_level)
        
        if current_index < len(levels) - 1:
            return levels[current_index + 1]
        
        return None
    
    def _calculate_upgrade_score(self) -> float:
        """Calculate score for intelligence level upgrade."""
        # Based on quantum intuition, skill levels, and performance
        
        # Quantum intuition score
        if self.quantum_intuition:
            intuition_score = sum(self.quantum_intuition.values()) / len(self.quantum_intuition)
        else:
            intuition_score = 0.0
        
        # Average skill level
        skill_levels = [s.skill_level for s in self.evolver.skills.values()]
        avg_skill_level = sum(skill_levels) / len(skill_levels) / 10.0 if skill_levels else 0.0
        
        # Performance history
        if self.performance_history:
            recent_performances = [p["performance_score"] for p in self.performance_history[-10:]]
            avg_performance = sum(recent_performances) / len(recent_performances)
        else:
            avg_performance = 0.0
        
        # Quantum advantage
        if self.quantum_advantage_history:
            avg_quantum_advantage = sum(self.quantum_advantage_history[-5:]) / len(self.quantum_advantage_history[-5:])
        else:
            avg_quantum_advantage = 0.0
        
        # Combined score
        upgrade_score = (
            0.3 * intuition_score +
            0.25 * avg_skill_level +
            0.25 * avg_performance +
            0.2 * avg_quantum_advantage
        )
        
        return upgrade_score
    
    def _get_upgrade_threshold(self, level: QuantumIntelligenceLevel) -> float:
        """Get upgrade threshold for an intelligence level."""
        thresholds = {
            QuantumIntelligenceLevel.QUANTUM_AWARE: 0.6,
            QuantumIntelligenceLevel.QUANTUM_FLUENT: 0.7,
            QuantumIntelligenceLevel.QUANTUM_INTUITIVE: 0.8,
            QuantumIntelligenceLevel.QUANTUM_CREATIVE: 0.9,
        }
        
        return thresholds.get(level, 1.0)
    
    def _generate_strategy_options(self, problem_type: QuantumProblemType) -> List[Dict[str, Any]]:
        """Generate strategy options for a problem type."""
        base_strategies = []
        
        if problem_type == QuantumProblemType.OPTIMIZATION:
            base_strategies = [
                {
                    "name": "QAOA_Standard",
                    "parameters": {"mixer_strength": 1.0, "cost_strength": 1.0},
                    "description": "Standard QAOA approach"
                },
                {
                    "name": "VQE_Variational",
                    "parameters": {"ansatz_depth": 3, "optimizer": "adam"},
                    "description": "Variational quantum eigensolver"
                }
            ]
        elif problem_type == QuantumProblemType.ARBITRAGE:
            base_strategies = [
                {
                    "name": "Portfolio_QAOA",
                    "parameters": {"risk_weight": 0.3, "return_weight": 0.7},
                    "description": "QAOA for portfolio optimization"
                },
                {
                    "name": "Quantum_Monte_Carlo",
                    "parameters": {"scenarios": 1000, "confidence_level": 0.95},
                    "description": "Quantum Monte Carlo for risk assessment"
                }
            ]
        else:
            base_strategies = [
                {
                    "name": "General_Quantum",
                    "parameters": {"exploration_rate": 0.1, "exploitation_rate": 0.9},
                    "description": "General quantum approach"
                }
            ]
        
        return base_strategies
    
    def _extract_arbitrage_allocation(
        self,
        measurement_counts: Dict[str, int],
        opportunities: List[Dict[str, Any]],
        capital: float
    ) -> List[Dict[str, Any]]:
        """Extract arbitrage allocation from quantum measurement results."""
        if not measurement_counts:
            return []
        
        # Find most probable state (portfolio allocation)
        total_shots = sum(measurement_counts.values())
        if total_shots == 0:
            return []
        
        most_probable_state = max(measurement_counts.items(), key=lambda x: x[1])[0]
        
        # Interpret state as portfolio allocation
        # Each qubit represents whether to include an opportunity
        allocation = []
        
        for i, bit in enumerate(most_probable_state):
            if i < len(opportunities) and bit == '1':
                opportunity = opportunities[i]
                
                # Simple allocation: equal share of capital among selected opportunities
                selected_count = most_probable_state.count('1')
                allocation_amount = capital / selected_count if selected_count > 0 else 0
                
                allocation.append({
                    "opportunity_index": i,
                    "pair": opportunity.get("pair", f"OPP_{i}"),
                    "exchange_a": opportunity.get("exchange_a", "Unknown"),
                    "exchange_b": opportunity.get("exchange_b", "Unknown"),
                    "spread": opportunity.get("spread", 0.0),
                    "allocation_amount": allocation_amount,
                    "expected_return": opportunity.get("spread", 0.0) * 0.8,  # Assume 80% of spread achievable
                    "selection_confidence": measurement_counts[most_probable_state] / total_shots
                })
        
        return allocation
    
    def _calculate_arbitrage_advantage(
        self,
        quantum_allocation: List[Dict[str, Any]],
        opportunities: List[Dict[str, Any]],
        base_quantum_advantage: float,
        capital: float
    ) -> float:
        """Calculate quantum advantage for arbitrage."""
        if not quantum_allocation:
            return 0.0
        
        # Calculate expected return of quantum allocation
        quantum_return = sum(opp["expected_return"] * opp["allocation_amount"] 
                           for opp in quantum_allocation)
        
        # Simple baseline: equal allocation to all opportunities
        baseline_allocation = capital / len(opportunities) if opportunities else 0
        baseline_return = sum(opp.get("spread", 0.0) * 0.8 * baseline_allocation 
                            for opp in opportunities)
        
        if baseline_return > 0:
            advantage_ratio = quantum_return / baseline_return
        else:
            advantage_ratio = 1.0
        
        # Combine with base quantum advantage
        combined_advantage = 0.7 * base_quantum_advantage + 0.3 * min(2.0, advantage_ratio)
        
        return min(1.0, combined_advantage)
    
    def _calculate_expected_return(
        self,
        allocation: List[Dict[str, Any]],
        opportunities: List[Dict[str, Any]]
    ) -> float:
        """Calculate expected return from allocation."""
        if not allocation:
            return 0.0
        
        total_return = 0.0
        total_allocated = 0.0
        
        for alloc in allocation:
            idx = alloc["opportunity_index"]
            if idx < len(opportunities):
                opportunity = opportunities[idx]
                expected_return_rate = opportunity.get("spread", 0.0) * 0.8
                total_return += alloc["allocation_amount"] * expected_return_rate
                total_allocated += alloc["allocation_amount"]
        
        if total_allocated > 0:
            return total_return / total_allocated
        
        return 0.0
    
    def _assess_arbitrage_risk(
        self,
        allocation: List[Dict[str, Any]],
        opportunities: List[Dict[str, Any]],
        risk_tolerance: float
    ) -> Dict[str, Any]:
        """Assess risk of arbitrage allocation."""
        if not allocation:
            return {"risk_score": 1.0, "assessment": "No allocation"}
        
        # Simple risk assessment
        selected_opportunities = len(allocation)
        total_opportunities = len(opportunities)
        
        # Concentration risk (too few opportunities)
        if selected_opportunities < 3:
            concentration_risk = 0.7
        elif selected_opportunities < total_opportunities * 0.3:
            concentration_risk = 0.5
        else:
            concentration_risk = 0.3
        
        # Spread risk (average spread of selected opportunities)
        avg_spread = sum(opp["spread"] for opp in allocation) / selected_opportunities
        if avg_spread < 0.005:  # Less than 0.5%
            spread_risk = 0.6
        elif avg_spread < 0.01:  # Less than 1%
            spread_risk = 0.4
        else:
            spread_risk = 0.2
        
        # Combined risk score
        risk_score = 0.6 * concentration_risk + 0.4 * spread_risk
        
        # Risk assessment
        if risk_score > risk_tolerance * 1.5:
            assessment = "HIGH_RISK"
        elif risk_score > risk_tolerance:
            assessment = "MODERATE_RISK"
        else:
            assessment = "LOW_RISK"
        
        return {
            "risk_score": risk_score,
            "assessment": assessment,
            "concentration_risk": concentration_risk,
            "spread_risk": spread_risk,
            "selected_count": selected_opportunities,
            "average_spread": avg_spread
        }