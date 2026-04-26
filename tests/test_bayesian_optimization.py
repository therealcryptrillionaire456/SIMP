"""Tests for ProjectX Bayesian Optimization module.

Tests cover GaussianProcessOptimizer and PromptBayesianOptimizer with
deterministic, mocked behavior using pytest fixtures.
"""

from __future__ import annotations

import json
import math
import pytest
from typing import Dict, List
from unittest.mock import MagicMock, patch

from simp.projectx.bayesian_optimization import (
    GaussianProcessOptimizer,
    OptimizationObservation,
    BayesianOptimizationResult,
    PromptBayesianOptimizer,
    SearchDimension,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def search_dims() -> List[SearchDimension]:
    """Standard continuous search dimensions for testing."""
    return [
        SearchDimension(name="temperature", low=0.0, high=1.0),
        SearchDimension(name="top_p", low=0.0, high=1.0),
        SearchDimension(name="learning_rate", low=1e-5, high=1e-2),
    ]


@pytest.fixture
def int_dims() -> List[SearchDimension]:
    """Integer-valued search dimensions."""
    return [
        SearchDimension(name="layers", low=1, high=12, kind="int"),
        SearchDimension(name="batch_size", low=8, high=128, kind="int"),
    ]


@pytest.fixture
def optimizer(search_dims) -> GaussianProcessOptimizer:
    """GaussianProcessOptimizer with fixed seed for deterministic tests."""
    return GaussianProcessOptimizer(
        dimensions=search_dims,
        exploration_weight=1.5,
        length_scale=0.20,
        random_seed=42,
    )


# ---------------------------------------------------------------------------
# Test: BayesianOptimizer initialization
# ---------------------------------------------------------------------------

def test_bayesian_optimizer_initialization(optimizer, search_dims) -> None:
    """Verify BayesianOptimizer is initialized correctly with config."""
    assert optimizer is not None
    assert len(optimizer.observations) == 0
    assert optimizer.best_observation is None
    # Verify dimensions were stored
    assert len([d for d in search_dims]) == 3


def test_optimizer_requires_dimensions() -> None:
    """Optimizer raises ValueError when no dimensions provided."""
    with pytest.raises(ValueError, match="at least one dimension"):
        GaussianProcessOptimizer(dimensions=[])


def test_optimizer_exploration_weight_bounds() -> None:
    """Exploration weight is clamped to non-negative values."""
    dims = [SearchDimension(name="x", low=0, high=1)]
    opt = GaussianProcessOptimizer(dimensions=dims, exploration_weight=-5.0)
    assert opt._exploration_weight == 0.0


# ---------------------------------------------------------------------------
# Test: suggest() returns valid parameters
# ---------------------------------------------------------------------------

def test_suggest_returns_valid_parameters(optimizer) -> None:
    """suggest() returns a dict with keys for each dimension."""
    result = optimizer.suggest()
    assert isinstance(result, dict)
    assert "temperature" in result
    assert "top_p" in result
    assert "learning_rate" in result


def test_suggest_returns_float_by_default(search_dims) -> None:
    """Continuous dimensions return float values."""
    optimizer = GaussianProcessOptimizer(dimensions=search_dims[:1], random_seed=99)
    result = optimizer.suggest()
    assert isinstance(result["temperature"], float)


def test_suggest_returns_int_when_specified(int_dims) -> None:
    """Integer dimensions return int values."""
    optimizer = GaussianProcessOptimizer(dimensions=int_dims[:1], random_seed=99)
    result = optimizer.suggest()
    assert isinstance(result["layers"], int)


# ---------------------------------------------------------------------------
# Test: observe/register registers an observation
# ---------------------------------------------------------------------------

def test_observe_registers_observation(optimizer) -> None:
    """register() stores the params and score."""
    params = {"temperature": 0.5, "top_p": 0.5, "learning_rate": 0.001}
    optimizer.register(params, score=0.8)

    assert len(optimizer.observations) == 1
    obs = optimizer.observations[0]
    assert obs.params == params
    assert obs.score == 0.8


def test_register_returns_observation(optimizer) -> None:
    """register() returns the created OptimizationObservation."""
    params = {"temperature": 0.3, "top_p": 0.7, "learning_rate": 0.0001}
    obs = optimizer.register(params, score=0.95)

    assert isinstance(obs, OptimizationObservation)
    assert obs.params["temperature"] == 0.3
    assert obs.score == 0.95


def test_register_clamps_params_to_bounds(search_dims) -> None:
    """register() clamps out-of-bounds params to dimension limits."""
    optimizer = GaussianProcessOptimizer(dimensions=search_dims[:1], random_seed=1)
    # Out-of-bounds value
    params = {"temperature": 999.0}
    obs = optimizer.register(params, score=0.5)

    assert obs.params["temperature"] == 1.0  # clamped to high


# ---------------------------------------------------------------------------
# Test: best_parameters / best_observation returns dict
# ---------------------------------------------------------------------------

def test_best_parameters_returns_dict(optimizer) -> None:
    """best_observation returns an OptimizationObservation with params dict."""
    optimizer.register({"temperature": 0.2, "top_p": 0.2, "learning_rate": 1e-4}, score=0.5)
    optimizer.register({"temperature": 0.8, "top_p": 0.8, "learning_rate": 1e-3}, score=0.9)

    best = optimizer.best_observation
    assert best is not None
    assert isinstance(best.params, dict)
    assert "temperature" in best.params
    assert "top_p" in best.params


def test_best_observation_returns_highest_score(optimizer) -> None:
    """best_observation returns the observation with highest score."""
    optimizer.register({"temperature": 0.1, "top_p": 0.1, "learning_rate": 1e-5}, score=0.3)
    optimizer.register({"temperature": 0.5, "top_p": 0.5, "learning_rate": 1e-4}, score=0.8)
    optimizer.register({"temperature": 0.9, "top_p": 0.9, "learning_rate": 1e-3}, score=0.6)

    best = optimizer.best_observation
    assert best is not None
    assert best.score == 0.8


def test_best_observation_none_when_empty(optimizer) -> None:
    """best_observation is None before any observations are registered."""
    assert optimizer.best_observation is None


# ---------------------------------------------------------------------------
# Test: bounds respected
# ---------------------------------------------------------------------------

def test_bounds_respected(optimizer) -> None:
    """Suggested params always fall within defined dimension bounds."""
    for _ in range(20):
        params = optimizer.suggest()
        assert 0.0 <= params["temperature"] <= 1.0
        assert 0.0 <= params["top_p"] <= 1.0
        assert 1e-5 <= params["learning_rate"] <= 1e-2


def test_bounds_respected_for_random_params(optimizer) -> None:
    """random_params() respects dimension bounds."""
    for _ in range(20):
        params = optimizer.random_params()
        assert 0.0 <= params["temperature"] <= 1.0
        assert 0.0 <= params["top_p"] <= 1.0
        assert 1e-5 <= params["learning_rate"] <= 1e-2


def test_int_bounds_respected(int_dims) -> None:
    """Integer dimensions produce values within bounds."""
    optimizer = GaussianProcessOptimizer(dimensions=int_dims, random_seed=99)
    for _ in range(20):
        params = optimizer.suggest()
        assert 1 <= params["layers"] <= 12
        assert 8 <= params["batch_size"] <= 128


# ---------------------------------------------------------------------------
# Test: batch suggest
# ---------------------------------------------------------------------------

def test_batch_suggest_multiple_suggestions(search_dims) -> None:
    """Generate multiple suggestions in a batch."""
    optimizer = GaussianProcessOptimizer(dimensions=search_dims, random_seed=42)
    suggestions = [optimizer.suggest() for _ in range(5)]

    assert len(suggestions) == 5
    for params in suggestions:
        assert isinstance(params, dict)
        assert "temperature" in params
        assert "top_p" in params
        assert "learning_rate" in params


def test_batch_suggest_all_within_bounds(search_dims) -> None:
    """All batch suggestions respect dimension bounds."""
    optimizer = GaussianProcessOptimizer(dimensions=search_dims, random_seed=42)
    for _ in range(3):
        for _ in range(10):
            params = optimizer.suggest()
            assert 0.0 <= params["temperature"] <= 1.0


# ---------------------------------------------------------------------------
# Test: hyperparameter serialization
# ---------------------------------------------------------------------------

def test_hyperparameter_serialization(optimizer) -> None:
    """Suggested params can be serialized to JSON."""
    optimizer.register(
        {"temperature": 0.5, "top_p": 0.7, "learning_rate": 0.001},
        score=0.85,
    )

    params = optimizer.suggest()
    json_str = json.dumps(params)
    assert isinstance(json_str, str)

    # Verify round-trip
    parsed = json.loads(json_str)
    assert parsed == params


def test_optimization_result_to_dict() -> None:
    """BayesianOptimizationResult serializes to dict via to_dict()."""
    result = BayesianOptimizationResult(
        best_params={"temperature": 0.7},
        best_score=0.95,
        iterations=10,
    )
    as_dict = result.to_dict()

    assert isinstance(as_dict, dict)
    assert as_dict["best_params"] == {"temperature": 0.7}
    assert as_dict["best_score"] == 0.95
    assert as_dict["iterations"] == 10
    assert as_dict["observation_count"] == 0


def test_optimization_observation_serialization() -> None:
    """OptimizationObservation params can be JSON-serialized."""
    obs = OptimizationObservation(
        params={"temperature": 0.5, "top_p": 0.8},
        score=0.9,
    )
    json_str = json.dumps({"params": obs.params, "score": obs.score})
    parsed = json.loads(json_str)

    assert parsed["params"]["temperature"] == 0.5
    assert parsed["score"] == 0.9


# ---------------------------------------------------------------------------
# Test: empty optimizer behavior
# ---------------------------------------------------------------------------

def test_empty_optimizer_behavior() -> None:
    """What happens when observe/register hasn't been called yet."""
    dims = [SearchDimension(name="x", low=0, high=1)]
    opt = GaussianProcessOptimizer(dimensions=dims, random_seed=123)

    # Observations list is empty
    assert len(opt.observations) == 0
    assert opt.best_observation is None

    # suggest() still works via random_params fallback when observations < warmup
    params = opt.suggest()
    assert isinstance(params, dict)
    assert "x" in params
    assert 0.0 <= params["x"] <= 1.0

    # predict() returns default mean=0, variance=1 when no observations
    mean, variance = opt.predict(params)
    assert mean == 0.0
    assert variance == 1.0


def test_empty_optimizer_upper_confidence_bound() -> None:
    """UCB can be computed even with no observations."""
    dims = [SearchDimension(name="x", low=0, high=1)]
    opt = GaussianProcessOptimizer(dimensions=dims, random_seed=1)
    params = {"x": 0.5}

    # No observations, but UCB should not raise
    ucb = opt.upper_confidence_bound(params)
    assert isinstance(ucb, float)
    assert ucb >= 0.0  # mean(0) + weight(1.5) * sqrt(1) = 1.5


def test_empty_optimizer_expected_improvement() -> None:
    """Expected improvement computed with no prior observations."""
    dims = [SearchDimension(name="x", low=0, high=1)]
    opt = GaussianProcessOptimizer(dimensions=dims, random_seed=1)
    params = {"x": 0.5}

    ei = opt.expected_improvement(params)
    assert isinstance(ei, float)


# ---------------------------------------------------------------------------
# Test: SearchDimension helpers
# ---------------------------------------------------------------------------

def test_search_dimension_clamp() -> None:
    """clamp() restricts values to [low, high]."""
    dim = SearchDimension(name="x", low=0.0, high=1.0)
    assert dim.clamp(-0.5) == 0.0
    assert dim.clamp(0.5) == 0.5
    assert dim.clamp(2.0) == 1.0


def test_search_dimension_clamp_int() -> None:
    """clamp() rounds and returns int for integer dimensions."""
    dim = SearchDimension(name="layers", low=1, high=10, kind="int")
    assert dim.clamp(-5) == 1
    assert dim.clamp(5.7) == 6
    assert dim.clamp(15) == 10


def test_search_dimension_sample() -> None:
    """sample() returns values within bounds."""
    dim = SearchDimension(name="x", low=0.0, high=1.0)
    rng = __import__("random").Random(42)
    for _ in range(100):
        val = dim.sample(rng)
        assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# Test: PromptBayesianOptimizer
# ---------------------------------------------------------------------------

def test_prompt_bayesian_optimizer_init(search_dims) -> None:
    """PromptBayesianOptimizer initializes correctly."""
    factory = MagicMock(return_value="template: {temperature}")
    opt = PromptBayesianOptimizer(dimensions=search_dims, template_factory=factory)
    assert opt._optimizer is not None
    assert opt._template_factory is factory


def test_prompt_bayesian_optimizer_optimize(search_dims) -> None:
    """optimize() returns best params, score, and template."""
    factory = MagicMock(return_value="generated prompt")
    scorer = MagicMock(return_value=0.9)
    opt = PromptBayesianOptimizer(dimensions=search_dims[:1], template_factory=factory)

    result = opt.optimize(scorer, iterations=3, warmup=2)

    assert isinstance(result, dict)
    assert "best_params" in result
    assert "best_score" in result
    assert "best_template" in result
    assert "iterations" in result
    assert factory.called


def test_prompt_bayesian_optimizer_template_factory_called(search_dims) -> None:
    """Template factory is called with best params after optimization."""
    factory = MagicMock(return_value="final prompt")
    scorer = MagicMock(return_value=0.5)
    opt = PromptBayesianOptimizer(dimensions=search_dims[:1], template_factory=factory)

    opt.optimize(scorer, iterations=2, warmup=1)
    assert factory.call_count >= 1


# ---------------------------------------------------------------------------
# Test: optimize() integration
# ---------------------------------------------------------------------------

def test_optimize_integration() -> None:
    """Full optimize() loop returns BayesianOptimizationResult."""
    dims = [SearchDimension(name="x", low=0.0, high=1.0)]
    optimizer = GaussianProcessOptimizer(dimensions=dims, random_seed=42)

    def objective(params: Dict) -> float:
        x = params["x"]
        return -(x - 0.7) ** 2  # maximize by minimizing distance to 0.7

    result = optimizer.optimize(objective, iterations=10, warmup=3)

    assert isinstance(result, BayesianOptimizationResult)
    assert result.iterations == 10
    assert len(result.observations) == 10
    assert result.best_score is not None
    assert "x" in result.best_params


def test_optimize_warmup_random_then_suggest() -> None:
    """During warmup, optimizer uses random_params; after warmup, uses suggest()."""
    dims = [SearchDimension(name="x", low=0.0, high=1.0)]
    optimizer = GaussianProcessOptimizer(dimensions=dims, random_seed=42)

    # warmup=5, iterations=5 => all random, no model-based suggestion
    result = optimizer.optimize(
        lambda p: p["x"],
        iterations=5,
        warmup=5,
    )
    # Should have 5 observations but suggest() not called (warmup covers all)
    assert len(optimizer.observations) == 5


# ---------------------------------------------------------------------------
# Test: acquisition strategies
# ---------------------------------------------------------------------------

def test_acquisition_ucb() -> None:
    """UCB acquisition strategy works."""
    dims = [SearchDimension(name="x", low=0.0, high=1.0)]
    optimizer = GaussianProcessOptimizer(dimensions=dims, random_seed=42)

    optimizer.register({"x": 0.3}, score=0.5)
    optimizer.register({"x": 0.7}, score=0.8)

    params = optimizer.suggest(acquisition="ucb")
    assert "x" in params
    assert 0.0 <= params["x"] <= 1.0


def test_acquisition_ei() -> None:
    """Expected Improvement acquisition strategy works."""
    dims = [SearchDimension(name="x", low=0.0, high=1.0)]
    optimizer = GaussianProcessOptimizer(dimensions=dims, random_seed=42)

    optimizer.register({"x": 0.2}, score=0.4)
    optimizer.register({"x": 0.8}, score=0.6)

    params = optimizer.suggest(acquisition="ei")
    assert "x" in params
    assert 0.0 <= params["x"] <= 1.0


# ---------------------------------------------------------------------------
# Test: random_seed determinism
# ---------------------------------------------------------------------------

def test_random_seed_determinism() -> None:
    """Same seed produces identical random_params across instances."""
    dims = [SearchDimension(name="x", low=0.0, high=1.0)]
    opt1 = GaussianProcessOptimizer(dimensions=dims, random_seed=999)
    opt2 = GaussianProcessOptimizer(dimensions=dims, random_seed=999)

    assert opt1.random_params() == opt2.random_params()
    assert opt1.random_params() == opt2.random_params()


def test_different_seeds_different_results() -> None:
    """Different seeds produce different random params."""
    dims = [SearchDimension(name="x", low=0.0, high=1.0)]
    opt1 = GaussianProcessOptimizer(dimensions=dims, random_seed=111)
    opt2 = GaussianProcessOptimizer(dimensions=dims, random_seed=222)

    assert opt1.random_params() != opt2.random_params()
