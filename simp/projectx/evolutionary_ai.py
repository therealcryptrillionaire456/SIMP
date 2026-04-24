"""
ProjectX Evolutionary Optimization

Reusable mutation/crossover/selection utilities for bounded search spaces.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .bayesian_optimization import SearchDimension


@dataclass
class EvolutionConfig:
    population_size: int = 12
    generations: int = 8
    mutation_rate: float = 0.20
    crossover_rate: float = 0.80
    elite_count: int = 2
    tournament_size: int = 3
    random_seed: Optional[int] = None


@dataclass
class GenomeCandidate:
    genes: Dict[str, float | int]
    fitness: Optional[float] = None
    generation: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "genes": dict(self.genes),
            "fitness": self.fitness,
            "generation": self.generation,
            "metadata": dict(self.metadata),
        }


@dataclass
class EvolutionResult:
    best_candidate: GenomeCandidate
    generations: int
    history: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_candidate": self.best_candidate.to_dict(),
            "generations": self.generations,
            "history": list(self.history),
        }


class EvolutionaryOptimizer:
    def __init__(
        self,
        dimensions: Sequence[SearchDimension],
        config: Optional[EvolutionConfig] = None,
    ) -> None:
        if not dimensions:
            raise ValueError("EvolutionaryOptimizer requires at least one dimension")
        self._dimensions = list(dimensions)
        self._config = config or EvolutionConfig()
        self._rng = random.Random(self._config.random_seed)

    def initialize_population(self) -> List[GenomeCandidate]:
        return [
            GenomeCandidate(genes={dim.name: dim.sample(self._rng) for dim in self._dimensions})
            for _ in range(max(2, self._config.population_size))
        ]

    def evaluate_population(
        self,
        population: List[GenomeCandidate],
        objective: Callable[[Dict[str, float | int]], float],
    ) -> None:
        for candidate in population:
            if candidate.fitness is None:
                candidate.fitness = float(objective(dict(candidate.genes)))

    def optimize(
        self,
        objective: Callable[[Dict[str, float | int]], float],
    ) -> EvolutionResult:
        population = self.initialize_population()
        history: List[float] = []
        generations = max(1, self._config.generations)
        for generation in range(generations):
            self.evaluate_population(population, objective)
            population.sort(key=lambda candidate: candidate.fitness or float("-inf"), reverse=True)
            history.append(float(population[0].fitness or 0.0))
            next_population = self._next_generation(population, generation + 1)
            population = next_population
        self.evaluate_population(population, objective)
        population.sort(key=lambda candidate: candidate.fitness or float("-inf"), reverse=True)
        return EvolutionResult(best_candidate=population[0], generations=generations, history=history)

    def mutate(self, candidate: GenomeCandidate, generation: Optional[int] = None) -> GenomeCandidate:
        genes = dict(candidate.genes)
        for dim in self._dimensions:
            if self._rng.random() <= self._config.mutation_rate:
                if dim.kind == "int":
                    step = max(1, int(round((dim.high - dim.low) * 0.15)))
                    delta = self._rng.randint(-step, step)
                    genes[dim.name] = dim.clamp(int(genes[dim.name]) + delta)
                else:
                    step = (dim.high - dim.low) * 0.15
                    delta = self._rng.uniform(-step, step)
                    genes[dim.name] = dim.clamp(float(genes[dim.name]) + delta)
        return GenomeCandidate(
            genes=genes,
            generation=candidate.generation if generation is None else generation,
            metadata={**candidate.metadata, "mutated": True},
        )

    def crossover(
        self,
        left: GenomeCandidate,
        right: GenomeCandidate,
        generation: Optional[int] = None,
    ) -> GenomeCandidate:
        genes: Dict[str, float | int] = {}
        for dim in self._dimensions:
            if self._rng.random() <= self._config.crossover_rate:
                chosen = left.genes[dim.name] if self._rng.random() < 0.5 else right.genes[dim.name]
            else:
                chosen = left.genes[dim.name]
            genes[dim.name] = dim.clamp(float(chosen))
        return GenomeCandidate(
            genes=genes,
            generation=max(left.generation, right.generation) if generation is None else generation,
            metadata={"parents": [left.genes, right.genes]},
        )

    def _next_generation(self, population: List[GenomeCandidate], generation: int) -> List[GenomeCandidate]:
        elite_count = min(max(1, self._config.elite_count), len(population))
        next_population: List[GenomeCandidate] = [
            GenomeCandidate(
                genes=dict(candidate.genes),
                fitness=candidate.fitness,
                generation=generation,
                metadata={**candidate.metadata, "elite": True},
            )
            for candidate in population[:elite_count]
        ]
        while len(next_population) < max(2, self._config.population_size):
            parent_a = self._tournament(population)
            parent_b = self._tournament(population)
            child = self.crossover(parent_a, parent_b, generation=generation)
            child = self.mutate(child, generation=generation)
            next_population.append(child)
        return next_population

    def _tournament(self, population: List[GenomeCandidate]) -> GenomeCandidate:
        contenders = self._rng.sample(
            population,
            min(len(population), max(2, self._config.tournament_size)),
        )
        return max(contenders, key=lambda candidate: candidate.fitness or float("-inf"))


class PromptEvolutionEngine:
    """
    Evolve numeric prompt knobs into higher-scoring templates.
    """

    def __init__(
        self,
        dimensions: Sequence[SearchDimension],
        template_factory: Callable[[Dict[str, float | int]], str],
        config: Optional[EvolutionConfig] = None,
    ) -> None:
        self._optimizer = EvolutionaryOptimizer(dimensions, config=config)
        self._template_factory = template_factory

    def optimize(self, scorer: Callable[[str], float]) -> Dict[str, Any]:
        result = self._optimizer.optimize(
            lambda genes: float(scorer(self._template_factory(genes)))
        )
        return {
            "best_genes": dict(result.best_candidate.genes),
            "best_score": result.best_candidate.fitness,
            "best_template": self._template_factory(result.best_candidate.genes),
            "generations": result.generations,
            "history": list(result.history),
        }
