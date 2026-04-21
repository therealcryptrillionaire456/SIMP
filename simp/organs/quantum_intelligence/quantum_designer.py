"""
Module 1: Quantum Algorithm Designer

This module enables agents to:
1. Design quantum circuits for specific problems
2. Evolve and optimize quantum circuits
3. Create novel quantum algorithms
4. Parameterize quantum circuits
"""

import random
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
from datetime import datetime
from enum import Enum
import hashlib

from . import QuantumProblemType, QuantumCircuitDesign


class QuantumGateType(str, Enum):
    """Types of quantum gates that can be used in circuit design."""
    H = "h"  # Hadamard
    X = "x"  # Pauli-X
    Y = "y"  # Pauli-Y
    Z = "z"  # Pauli-Z
    RX = "rx"  # Rotation X
    RY = "ry"  # Rotation Y
    RZ = "rz"  # Rotation Z
    CNOT = "cnot"  # Controlled NOT
    CZ = "cz"  # Controlled Z
    SWAP = "swap"  # Swap
    TOFFOLI = "toffoli"  # Toffoli (CCNOT)
    MEASURE = "measure"  # Measurement


class CircuitDesignStrategy(str, Enum):
    """Strategies for designing quantum circuits."""
    RANDOM = "random"  # Random circuit generation
    TEMPLATE = "template"  # Use problem-specific templates
    EVOLUTIONARY = "evolutionary"  # Evolve circuits over time
    HYBRID = "hybrid"  # Combine multiple strategies


@dataclass
class QuantumGate:
    """Represents a quantum gate in a circuit."""
    gate_type: QuantumGateType
    qubits: List[int]  # Which qubits the gate acts on
    parameters: List[float] = field(default_factory=list)  # For parameterized gates
    layer: int = 0  # Which layer in the circuit


class QuantumAlgorithmDesigner:
    """Designs and evolves quantum algorithms."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"quantum.designer.{agent_id}")
        self.designs: Dict[str, QuantumCircuitDesign] = {}
        self.templates: Dict[QuantumProblemType, List[List[QuantumGate]]] = self._initialize_templates()
        
    def _initialize_templates(self) -> Dict[QuantumProblemType, List[List[QuantumGate]]]:
        """Initialize problem-specific circuit templates."""
        templates = {}
        
        # Optimization templates (QAOA-like)
        templates[QuantumProblemType.OPTIMIZATION] = [
            # Template 1: Basic QAOA
            [
                QuantumGate(QuantumGateType.H, [0]),
                QuantumGate(QuantumGateType.H, [1]),
                QuantumGate(QuantumGateType.RZ, [0], [0.5]),
                QuantumGate(QuantumGateType.RZ, [1], [0.5]),
                QuantumGate(QuantumGateType.CNOT, [0, 1]),
                QuantumGate(QuantumGateType.RZ, [1], [1.0]),
                QuantumGate(QuantumGateType.CNOT, [0, 1]),
            ],
            # Template 2: Variational circuit
            [
                QuantumGate(QuantumGateType.RY, [0], [0.3]),
                QuantumGate(QuantumGateType.RY, [1], [0.3]),
                QuantumGate(QuantumGateType.CZ, [0, 1]),
                QuantumGate(QuantumGateType.RY, [0], [0.7]),
                QuantumGate(QuantumGateType.RY, [1], [0.7]),
            ]
        ]
        
        # Machine learning templates
        templates[QuantumProblemType.MACHINE_LEARNING] = [
            # Template 1: Quantum neural network layer
            [
                QuantumGate(QuantumGateType.RY, [0], [0.2]),
                QuantumGate(QuantumGateType.RZ, [0], [0.3]),
                QuantumGate(QuantumGateType.RY, [1], [0.2]),
                QuantumGate(QuantumGateType.RZ, [1], [0.3]),
                QuantumGate(QuantumGateType.CNOT, [0, 1]),
                QuantumGate(QuantumGateType.RY, [1], [0.4]),
            ]
        ]
        
        # Arbitrage optimization templates
        templates[QuantumProblemType.ARBITRAGE] = [
            # Template for portfolio optimization
            [
                QuantumGate(QuantumGateType.H, [0]),
                QuantumGate(QuantumGateType.H, [1]),
                QuantumGate(QuantumGateType.H, [2]),
                QuantumGate(QuantumGateType.RZ, [0], [0.1]),  # Asset 1 weight
                QuantumGate(QuantumGateType.RZ, [1], [0.2]),  # Asset 2 weight  
                QuantumGate(QuantumGateType.RZ, [2], [0.3]),  # Asset 3 weight
                QuantumGate(QuantumGateType.CNOT, [0, 1]),  # Correlation 1-2
                QuantumGate(QuantumGateType.CNOT, [1, 2]),  # Correlation 2-3
                QuantumGate(QuantumGateType.RZ, [1], [0.4]),  # Risk factor
            ]
        ]
        
        return templates
    
    def design_circuit(
        self,
        problem_type: QuantumProblemType,
        qubits: int,
        strategy: CircuitDesignStrategy = CircuitDesignStrategy.HYBRID,
        constraints: Optional[Dict[str, Any]] = None
    ) -> QuantumCircuitDesign:
        """Design a quantum circuit for a specific problem."""
        constraints = constraints or {}
        max_depth = constraints.get("max_depth", 10)
        
        circuit_id = self._generate_circuit_id(problem_type, qubits)
        
        if strategy == CircuitDesignStrategy.RANDOM:
            gates = self._design_random_circuit(qubits, max_depth)
        elif strategy == CircuitDesignStrategy.TEMPLATE:
            gates = self._design_from_template(problem_type, qubits, max_depth)
        elif strategy == CircuitDesignStrategy.EVOLUTIONARY:
            gates = self._design_evolutionary(problem_type, qubits, max_depth)
        else:  # HYBRID
            gates = self._design_hybrid(problem_type, qubits, max_depth)
        
        # Parameterize the circuit
        parameters = self._parameterize_circuit(gates)
        
        # Create circuit design
        design = QuantumCircuitDesign(
            circuit_id=circuit_id,
            problem_type=problem_type,
            qubits=qubits,
            depth=len(gates),
            gates=[self._gate_to_dict(g) for g in gates],
            parameters=parameters,
            fitness_score=0.5,  # Initial score
            created_at=datetime.utcnow().isoformat(),
            metadata={
                "strategy": strategy.value,
                "constraints": constraints,
                "designer": self.agent_id
            }
        )
        
        self.designs[circuit_id] = design
        self.logger.info(f"Designed circuit {circuit_id} for {problem_type.value} with {qubits} qubits")
        
        return design
    
    def evolve_circuit(
        self,
        circuit_id: str,
        fitness_feedback: float,
        evolution_params: Optional[Dict[str, Any]] = None
    ) -> QuantumCircuitDesign:
        """Evolve a circuit based on fitness feedback."""
        if circuit_id not in self.designs:
            raise ValueError(f"Circuit not found: {circuit_id}")
        
        original = self.designs[circuit_id]
        evolution_params = evolution_params or {}
        mutation_rate = evolution_params.get("mutation_rate", 0.1)
        crossover_rate = evolution_params.get("crossover_rate", 0.3)
        
        # Update fitness score
        original.fitness_score = fitness_feedback
        
        # Create evolved version
        evolved_gates = self._evolve_gates(
            [self._dict_to_gate(g) for g in original.gates],
            mutation_rate,
            crossover_rate
        )
        
        # Update parameters
        evolved_parameters = self._parameterize_circuit(evolved_gates)
        
        # Create evolved design
        evolved_id = f"{circuit_id}_evolved_{hashlib.md5(str(evolved_gates).encode()).hexdigest()[:8]}"
        
        evolved = QuantumCircuitDesign(
            circuit_id=evolved_id,
            problem_type=original.problem_type,
            qubits=original.qubits,
            depth=len(evolved_gates),
            gates=[self._gate_to_dict(g) for g in evolved_gates],
            parameters=evolved_parameters,
            fitness_score=fitness_feedback * 1.1,  # Assume evolution improves fitness
            created_at=datetime.utcnow().isoformat(),
            metadata={
                **original.metadata,
                "parent_circuit": circuit_id,
                "evolution_params": evolution_params,
                "original_fitness": original.fitness_score,
            }
        )
        
        self.designs[evolved_id] = evolved
        self.logger.info(f"Evolved circuit {circuit_id} -> {evolved_id}, fitness: {fitness_feedback:.3f}")
        
        return evolved
    
    def create_novel_algorithm(
        self,
        problem_description: str,
        qubits: int,
        inspiration: Optional[List[QuantumCircuitDesign]] = None
    ) -> QuantumCircuitDesign:
        """Create a novel quantum algorithm from problem description."""
        # Analyze problem description to determine problem type
        problem_type = self._classify_problem(problem_description)
        
        # Generate novel circuit structure
        novel_gates = self._generate_novel_structure(problem_type, qubits, inspiration)
        
        circuit_id = f"novel_{hashlib.md5(problem_description.encode()).hexdigest()[:8]}"
        
        design = QuantumCircuitDesign(
            circuit_id=circuit_id,
            problem_type=problem_type,
            qubits=qubits,
            depth=len(novel_gates),
            gates=[self._gate_to_dict(g) for g in novel_gates],
            parameters=self._parameterize_circuit(novel_gates),
            fitness_score=0.3,  # Novel algorithms start with lower fitness
            created_at=datetime.utcnow().isoformat(),
            metadata={
                "problem_description": problem_description,
                "inspiration": [d.circuit_id for d in inspiration] if inspiration else [],
                "novelty_score": self._calculate_novelty_score(novel_gates, inspiration),
            }
        )
        
        self.designs[circuit_id] = design
        self.logger.info(f"Created novel algorithm {circuit_id} for: {problem_description[:50]}...")
        
        return design
    
    def _design_random_circuit(self, qubits: int, max_depth: int) -> List[QuantumGate]:
        """Design a random quantum circuit."""
        gates = []
        gate_types = list(QuantumGateType)
        
        for layer in range(max_depth):
            # Randomly decide how many gates in this layer
            gates_in_layer = random.randint(1, max(2, qubits // 2))
            
            for _ in range(gates_in_layer):
                gate_type = random.choice(gate_types)
                
                if gate_type in [QuantumGateType.CNOT, QuantumGateType.CZ, QuantumGateType.SWAP]:
                    # Two-qubit gates
                    if qubits >= 2:
                        q1, q2 = random.sample(range(qubits), 2)
                        qubit_list = [q1, q2]
                    else:
                        continue  # Skip two-qubit gates if not enough qubits
                else:
                    # Single-qubit gates
                    qubit_list = [random.randint(0, qubits - 1)]
                
                # Add parameters for parameterized gates
                parameters = []
                if gate_type in [QuantumGateType.RX, QuantumGateType.RY, QuantumGateType.RZ]:
                    parameters = [random.uniform(0, 2 * np.pi)]
                
                gates.append(QuantumGate(gate_type, qubit_list, parameters, layer))
        
        return gates
    
    def _design_from_template(
        self,
        problem_type: QuantumProblemType,
        qubits: int,
        max_depth: int
    ) -> List[QuantumGate]:
        """Design circuit from problem-specific templates."""
        if problem_type not in self.templates or not self.templates[problem_type]:
            self.logger.warning(f"No templates for {problem_type}, using random design")
            return self._design_random_circuit(qubits, max_depth)
        
        # Select and adapt a template
        template = random.choice(self.templates[problem_type])
        
        # Adapt template to requested qubit count
        adapted_gates = []
        for gate in template:
            # Scale qubit indices if needed
            if max(gate.qubits) >= qubits:
                # Remap qubits to fit within available qubits
                mapped_qubits = [q % qubits for q in gate.qubits]
            else:
                mapped_qubits = gate.qubits
            
            adapted_gates.append(QuantumGate(
                gate.gate_type,
                mapped_qubits,
                gate.parameters.copy(),
                gate.layer
            ))
        
        return adapted_gates
    
    def _design_evolutionary(
        self,
        problem_type: QuantumProblemType,
        qubits: int,
        max_depth: int
    ) -> List[QuantumGate]:
        """Design circuit using evolutionary approach."""
        # Start with population of random circuits
        population_size = 10
        population = [self._design_random_circuit(qubits, max_depth) for _ in range(population_size)]
        
        # Simple evolutionary loop
        for generation in range(5):  # Few generations for design phase
            # Evaluate fitness (simplified)
            fitness_scores = [self._evaluate_circuit_fitness(circuit, problem_type) for circuit in population]
            
            # Select parents
            parents = self._select_parents(population, fitness_scores)
            
            # Create new generation
            new_population = []
            for _ in range(population_size):
                if random.random() < 0.7 and len(parents) >= 2:
                    # Crossover
                    parent1, parent2 = random.sample(parents, 2)
                    child = self._crossover_circuits(parent1, parent2)
                else:
                    # Mutation or new random
                    parent = random.choice(parents) if parents else []
                    child = self._mutate_circuit(parent, qubits)
                
                new_population.append(child)
            
            population = new_population
        
        # Return best circuit from final population
        fitness_scores = [self._evaluate_circuit_fitness(circuit, problem_type) for circuit in population]
        best_idx = np.argmax(fitness_scores)
        
        return population[best_idx]
    
    def _design_hybrid(
        self,
        problem_type: QuantumProblemType,
        qubits: int,
        max_depth: int
    ) -> List[QuantumGate]:
        """Design circuit using hybrid strategy."""
        # 50% template, 50% evolutionary
        if random.random() < 0.5:
            template_circuit = self._design_from_template(problem_type, qubits, max_depth)
            # Add some random gates for exploration
            extra_gates = self._design_random_circuit(qubits, max_depth // 2)
            return template_circuit + extra_gates
        else:
            return self._design_evolutionary(problem_type, qubits, max_depth)
    
    def _evolve_gates(
        self,
        gates: List[QuantumGate],
        mutation_rate: float,
        crossover_rate: float
    ) -> List[QuantumGate]:
        """Evolve a list of quantum gates."""
        evolved = gates.copy()
        
        # Apply mutations
        for i, gate in enumerate(evolved):
            if random.random() < mutation_rate:
                evolved[i] = self._mutate_gate(gate)
        
        # Occasionally add or remove gates
        if random.random() < mutation_rate:
            if random.random() < 0.5 and len(evolved) > 1:
                # Remove a gate
                evolved.pop(random.randint(0, len(evolved) - 1))
            else:
                # Add a random gate
                new_gate = self._create_random_gate(max([g.qubits for g in evolved if g.qubits] + [0]))
                evolved.insert(random.randint(0, len(evolved)), new_gate)
        
        return evolved
    
    def _mutate_gate(self, gate: QuantumGate) -> QuantumGate:
        """Mutate a single quantum gate."""
        mutation_type = random.choice(["parameter", "type", "qubits"])
        
        if mutation_type == "parameter" and gate.parameters:
            # Mutate parameters
            new_params = [p + random.uniform(-0.5, 0.5) for p in gate.parameters]
            return QuantumGate(gate.gate_type, gate.qubits, new_params, gate.layer)
        
        elif mutation_type == "type":
            # Change gate type (keeping same number of qubits)
            new_type = random.choice(list(QuantumGateType))
            return QuantumGate(new_type, gate.qubits, gate.parameters, gate.layer)
        
        else:  # "qubits"
            # Change qubit indices
            new_qubits = [q + random.randint(-1, 1) for q in gate.qubits]
            new_qubits = [max(0, q) for q in new_qubits]  # Ensure non-negative
            return QuantumGate(gate.gate_type, new_qubits, gate.parameters, gate.layer)
    
    def _create_random_gate(self, max_qubit: int) -> QuantumGate:
        """Create a random quantum gate."""
        gate_type = random.choice(list(QuantumGateType))
        
        if gate_type in [QuantumGateType.CNOT, QuantumGateType.CZ, QuantumGateType.SWAP]:
            qubits = random.sample(range(max_qubit + 1), 2)
        else:
            qubits = [random.randint(0, max_qubit)]
        
        parameters = []
        if gate_type in [QuantumGateType.RX, QuantumGateType.RY, QuantumGateType.RZ]:
            parameters = [random.uniform(0, 2 * np.pi)]
        
        return QuantumGate(gate_type, qubits, parameters, 0)
    
    def _parameterize_circuit(self, gates: List[QuantumGate]) -> Dict[str, float]:
        """Extract parameters from a circuit."""
        parameters = {}
        
        for i, gate in enumerate(gates):
            if gate.parameters:
                param_name = f"gate_{i}_{gate.gate_type.value}"
                parameters[param_name] = gate.parameters[0]
        
        return parameters
    
    def _gate_to_dict(self, gate: QuantumGate) -> Dict[str, Any]:
        """Convert QuantumGate to dictionary."""
        return {
            "type": gate.gate_type.value,
            "qubits": gate.qubits,
            "parameters": gate.parameters,
            "layer": gate.layer
        }
    
    def _dict_to_gate(self, gate_dict: Dict[str, Any]) -> QuantumGate:
        """Convert dictionary to QuantumGate."""
        return QuantumGate(
            QuantumGateType(gate_dict["type"]),
            gate_dict["qubits"],
            gate_dict.get("parameters", []),
            gate_dict.get("layer", 0)
        )
    
    def _generate_circuit_id(self, problem_type: QuantumProblemType, qubits: int) -> str:
        """Generate unique circuit ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"circuit_{problem_type.value}_{qubits}q_{timestamp}"
    
    def _classify_problem(self, description: str) -> QuantumProblemType:
        """Classify problem from description."""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ["optimize", "maximize", "minimize", "best"]):
            return QuantumProblemType.OPTIMIZATION
        elif any(word in description_lower for word in ["learn", "predict", "classify", "model"]):
            return QuantumProblemType.MACHINE_LEARNING
        elif any(word in description_lower for word in ["search", "find", "locate"]):
            return QuantumProblemType.SEARCH
        elif any(word in description_lower for word in ["arbitrage", "trade", "profit", "spread"]):
            return QuantumProblemType.ARBITRAGE
        elif any(word in description_lower for word in ["finance", "portfolio", "risk"]):
            return QuantumProblemType.FINANCE
        else:
            return QuantumProblemType.OPTIMIZATION  # Default
    
    def _generate_novel_structure(
        self,
        problem_type: QuantumProblemType,
        qubits: int,
        inspiration: Optional[List[QuantumCircuitDesign]] = None
    ) -> List[QuantumGate]:
        """Generate novel circuit structure."""
        # Combine elements from inspiration circuits
        novel_gates = []
        
        if inspiration:
            # Take gates from inspiration circuits
            for design in inspiration:
                if design.gates:
                    # Take a subset of gates
                    take_count = min(3, len(design.gates))
                    for gate_dict in design.gates[:take_count]:
                        gate = self._dict_to_gate(gate_dict)
                        # Modify slightly for novelty
                        if random.random() < 0.3:
                            gate = self._mutate_gate(gate)
                        novel_gates.append(gate)
        
        # Add some completely new gates
        new_gate_count = max(5, qubits * 2)
        for _ in range(new_gate_count):
            novel_gates.append(self._create_random_gate(qubits - 1))
        
        return novel_gates
    
    def _calculate_novelty_score(
        self,
        gates: List[QuantumGate],
        inspiration: Optional[List[QuantumCircuitDesign]] = None
    ) -> float:
        """Calculate how novel a circuit is compared to inspiration."""
        if not inspiration:
            return 1.0  # Completely novel without inspiration
        
        # Simplified novelty calculation
        total_inspiration_gates = sum(len(design.gates) for design in inspiration)
        if total_inspiration_gates == 0:
            return 1.0
        
        # Count how many gates are similar to inspiration
        similar_count = 0
        for gate in gates:
            for design in inspiration:
                for insp_gate_dict in design.gates:
                    insp_gate = self._dict_to_gate(insp_gate_dict)
                    if (gate.gate_type == insp_gate.gate_type and 
                        gate.qubits == insp_gate.qubits):
                        similar_count += 1
                        break
        
        novelty = 1.0 - (similar_count / len(gates))
        return max(0.0, min(1.0, novelty))
    
    def _evaluate_circuit_fitness(
        self,
        circuit: List[QuantumGate],
        problem_type: QuantumProblemType
    ) -> float:
        """Evaluate fitness of a circuit (simplified)."""
        # Simplified fitness evaluation
        # In production, would execute circuit and evaluate results
        
        score = 0.0
        
        # Diversity of gates (encourage variety)
        gate_types = set(g.gate_type for g in circuit)
        score += len(gate_types) * 0.1
        
        # Appropriate depth (not too shallow, not too deep)
        depth = len(circuit)
        if 5 <= depth <= 20:
            score += 0.3
        elif depth > 0:
            score += 0.1
        
        # Problem-specific heuristics
        if problem_type == QuantumProblemType.OPTIMIZATION:
            # Optimization circuits benefit from entanglement
            two_qubit_gates = sum(1 for g in circuit if g.gate_type in [QuantumGateType.CNOT, QuantumGateType.CZ])
            score += min(two_qubit_gates * 0.05, 0.3)
        
        return min(1.0, score)
    
    def _select_parents(
        self,
        population: List[List[QuantumGate]],
        fitness_scores: List[float]
    ) -> List[List[QuantumGate]]:
        """Select parents for evolution."""
        if not population:
            return []
        
        # Tournament selection
        tournament_size = 3
        parents = []
        
        for _ in range(len(population)):
            # Random tournament
            tournament_indices = random.sample(range(len(population)), 
                                             min(tournament_size, len(population)))
            tournament_fitness = [fitness_scores[i] for i in tournament_indices]
            winner_idx = tournament_indices[np.argmax(tournament_fitness)]
            parents.append(population[winner_idx])
        
        return parents
    
    def _crossover_circuits(
        self,
        parent1: List[QuantumGate],
        parent2: List[QuantumGate]
    ) -> List[QuantumGate]:
        """Crossover two circuits."""
        if not parent1 or not parent2:
            return parent1 or parent2 or []
        
        # Single-point crossover
        crossover_point = random.randint(1, min(len(parent1), len(parent2)) - 1)
        
        child = parent1[:crossover_point] + parent2[crossover_point:]
        
        return child
    
    def _mutate_circuit(
        self,
        circuit: List[QuantumGate],
        qubits: int
    ) -> List[QuantumGate]:
        """Mutate a circuit."""
        if not circuit:
            return self._design_random_circuit(qubits, 10)
        
        mutated = circuit.copy()
        
        # Apply random mutations
        for i in range(len(mutated)):
            if random.random() < 0.1:
                mutated[i] = self._mutate_gate(mutated[i])
        
        # Possibly add or remove gates
        if random.random() < 0.2:
            if random.random() < 0.5 and len(mutated) > 1:
                mutated.pop(random.randint(0, len(mutated) - 1))
            else:
                mutated.insert(random.randint(0, len(mutated)), 
                             self._create_random_gate(qubits - 1))
        
        return mutated