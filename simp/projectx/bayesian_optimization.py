"""
ProjectX Bayesian Optimization

Pure-Python Bayesian-style optimization utilities for bounded numeric search.
The implementation uses an RBF-kernel surrogate with UCB/EI acquisition so it
works without heavy scientific dependencies while still being reusable.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SearchDimension:
    name: str
    low: float
    high: float
    kind: str = "float"  # float | int

    def clamp(self, value: float) -> float | int:
        clipped = min(max(value, self.low), self.high)
        if self.kind == "int":
            return int(round(clipped))
        return float(clipped)

    def sample(self, rng: random.Random) -> float | int:
        if self.kind == "int":
            return rng.randint(int(math.ceil(self.low)), int(math.floor(self.high)))
        return rng.uniform(self.low, self.high)


@dataclass
class OptimizationObservation:
    params: Dict[str, float | int]
    score: float


@dataclass
class BayesianOptimizationResult:
    best_params: Dict[str, float | int]
    best_score: float
    iterations: int
    observations: List[OptimizationObservation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_params": dict(self.best_params),
            "best_score": self.best_score,
            "iterations": self.iterations,
            "observation_count": len(self.observations),
        }


class GaussianProcessOptimizer:
    """
    Lightweight bounded optimizer with a kernel surrogate.

    This is not a full GP implementation; it is a practical, dependency-light
    surrogate for ProjectX optimization loops where the search space is small.
    """

    def __init__(
        self,
        dimensions: Sequence[SearchDimension],
        *,
        exploration_weight: float = 1.5,
        length_scale: float = 0.20,
        random_seed: Optional[int] = None,
    ) -> None:
        if not dimensions:
            raise ValueError("GaussianProcessOptimizer requires at least one dimension")
        self._dimensions = list(dimensions)
        self._exploration_weight = max(0.0, float(exploration_weight))
        self._length_scale = max(1e-6, float(length_scale))
        self._rng = random.Random(random_seed)
        self._observations: List[OptimizationObservation] = []

    @property
    def observations(self) -> List[OptimizationObservation]:
        return list(self._observations)

    @property
    def best_observation(self) -> Optional[OptimizationObservation]:
        if not self._observations:
            return None
        return max(self._observations, key=lambda obs: obs.score)

    def register(self, params: Dict[str, float | int], score: float) -> OptimizationObservation:
        normalized = self._normalize_params(params)
        observation = OptimizationObservation(params=normalized, score=float(score))
        self._observations.append(observation)
        return observation

    def random_params(self) -> Dict[str, float | int]:
        return {dim.name: dim.sample(self._rng) for dim in self._dimensions}

    def predict(self, params: Dict[str, float | int]) -> Tuple[float, float]:
        """
        Return (mean, variance) from the kernel surrogate at `params`.
        """
        if not self._observations:
            return 0.0, 1.0
        target = self._to_feature_vector(params)
        weights: List[float] = []
        scores: List[float] = []
        for obs in self._observations:
            vec = self._to_feature_vector(obs.params)
            weight = self._rbf(target, vec)
            weights.append(weight)
            scores.append(obs.score)
        weight_sum = sum(weights)
        if weight_sum <= 1e-9:
            mean = statistics.mean(scores)
            variance = statistics.pvariance(scores) if len(scores) > 1 else 1.0
            return mean, max(1e-6, variance)
        mean = sum(weight * score for weight, score in zip(weights, scores)) / weight_sum
        variance = sum(weight * ((score - mean) ** 2) for weight, score in zip(weights, scores)) / weight_sum
        novelty = 1.0 - min(1.0, weight_sum / max(1, len(weights)))
        return mean, max(1e-6, variance + novelty * 0.25)

    def upper_confidence_bound(self, params: Dict[str, float | int]) -> float:
        mean, variance = self.predict(params)
        return mean + self._exploration_weight * math.sqrt(max(0.0, variance))

    def expected_improvement(self, params: Dict[str, float | int]) -> float:
        best = self.best_observation.score if self.best_observation else 0.0
        mean, variance = self.predict(params)
        sigma = math.sqrt(max(1e-9, variance))
        improvement = mean - best
        z = improvement / sigma
        normal_cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        normal_pdf = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
        return improvement * normal_cdf + sigma * normal_pdf

    def suggest(self, candidate_pool: int = 96, acquisition: str = "ucb") -> Dict[str, float | int]:
        if len(self._observations) < max(2, len(self._dimensions)):
            return self.random_params()
        best_params: Optional[Dict[str, float | int]] = None
        best_score = float("-inf")
        for _ in range(max(candidate_pool, 8)):
            params = self.random_params()
            score = (
                self.expected_improvement(params)
                if acquisition == "ei"
                else self.upper_confidence_bound(params)
            )
            if score > best_score:
                best_score = score
                best_params = params
        assert best_params is not None
        return best_params

    def optimize(
        self,
        objective: Callable[[Dict[str, float | int]], float],
        *,
        iterations: int = 20,
        warmup: int = 4,
        acquisition: str = "ucb",
    ) -> BayesianOptimizationResult:
        total = max(1, int(iterations))
        warmup = max(1, min(warmup, total))
        for _ in range(total):
            params = self.random_params() if len(self._observations) < warmup else self.suggest(acquisition=acquisition)
            score = float(objective(dict(params)))
            self.register(params, score)
        best = self.best_observation
        assert best is not None
        return BayesianOptimizationResult(
            best_params=dict(best.params),
            best_score=best.score,
            iterations=total,
            observations=self.observations,
        )

    def _normalize_params(self, params: Dict[str, float | int]) -> Dict[str, float | int]:
        normalized: Dict[str, float | int] = {}
        for dim in self._dimensions:
            if dim.name not in params:
                raise ValueError(f"Missing parameter: {dim.name}")
            normalized[dim.name] = dim.clamp(float(params[dim.name]))
        return normalized

    def _to_feature_vector(self, params: Dict[str, float | int]) -> List[float]:
        normalized = self._normalize_params(params)
        vector: List[float] = []
        for dim in self._dimensions:
            span = max(1e-9, dim.high - dim.low)
            vector.append((float(normalized[dim.name]) - dim.low) / span)
        return vector

    def _rbf(self, a: Sequence[float], b: Sequence[float]) -> float:
        dist_sq = sum((x - y) ** 2 for x, y in zip(a, b))
        return math.exp(-dist_sq / (2.0 * self._length_scale * self._length_scale))


class PromptBayesianOptimizer:
    """
    Optimize a prompt template generated from numeric knobs.

    The caller supplies a `template_factory(params)` that maps numeric values
    to a prompt string. This keeps the optimizer generic and reusable.
    """

    def __init__(
        self,
        dimensions: Sequence[SearchDimension],
        template_factory: Callable[[Dict[str, float | int]], str],
        *,
        random_seed: Optional[int] = None,
    ) -> None:
        self._optimizer = GaussianProcessOptimizer(dimensions, random_seed=random_seed)
        self._template_factory = template_factory

    def optimize(
        self,
        scorer: Callable[[str], float],
        *,
        iterations: int = 20,
        warmup: int = 4,
    ) -> Dict[str, Any]:
        def objective(params: Dict[str, float | int]) -> float:
            return float(scorer(self._template_factory(params)))

        result = self._optimizer.optimize(objective, iterations=iterations, warmup=warmup)
        return {
            "best_params": result.best_params,
            "best_score": result.best_score,
            "best_template": self._template_factory(result.best_params),
            "iterations": result.iterations,
            "observation_count": len(result.observations),
        }
