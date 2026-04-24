from __future__ import annotations

from simp.projectx.apo_engine import APOEngine
from simp.projectx.bayesian_optimization import (
    GaussianProcessOptimizer,
    PromptBayesianOptimizer,
    SearchDimension,
)
from simp.projectx.evolutionary_ai import (
    EvolutionConfig,
    EvolutionaryOptimizer,
    PromptEvolutionEngine,
)


def _quadratic_objective(params: dict[str, float | int]) -> float:
    x = float(params["x"])
    return 1.0 - ((x - 0.72) ** 2)


def test_gaussian_process_optimizer_improves_simple_quadratic() -> None:
    optimizer = GaussianProcessOptimizer(
        [SearchDimension("x", 0.0, 1.0)],
        random_seed=7,
    )

    result = optimizer.optimize(_quadratic_objective, iterations=18, warmup=4)

    assert result.best_score > 0.97
    assert abs(float(result.best_params["x"]) - 0.72) < 0.18
    assert len(result.observations) == 18


def test_prompt_bayesian_optimizer_returns_high_scoring_template() -> None:
    optimizer = PromptBayesianOptimizer(
        [
            SearchDimension("tone", 0.0, 1.0),
            SearchDimension("detail", 0, 4, kind="int"),
        ],
        template_factory=lambda params: (
            f"tone={float(params['tone']):.2f};detail={int(params['detail'])}"
        ),
        random_seed=3,
    )

    def scorer(prompt: str) -> float:
        tone_part, detail_part = prompt.split(";")
        tone = float(tone_part.split("=")[1])
        detail = int(detail_part.split("=")[1])
        return 1.0 - abs(tone - 0.65) - abs(detail - 3) * 0.08

    result = optimizer.optimize(scorer, iterations=16, warmup=4)

    assert result["best_score"] > 0.80
    assert "tone=" in result["best_template"]
    assert result["observation_count"] == 16


def test_evolutionary_optimizer_improves_simple_quadratic() -> None:
    optimizer = EvolutionaryOptimizer(
        [SearchDimension("x", 0.0, 1.0)],
        config=EvolutionConfig(
            population_size=10,
            generations=7,
            mutation_rate=0.30,
            crossover_rate=0.90,
            elite_count=2,
            random_seed=11,
        ),
    )

    result = optimizer.optimize(_quadratic_objective)

    assert result.best_candidate.fitness is not None
    assert result.best_candidate.fitness > 0.95
    assert abs(float(result.best_candidate.genes["x"]) - 0.72) < 0.20
    assert len(result.history) == 7


def test_prompt_evolution_engine_returns_best_template() -> None:
    engine = PromptEvolutionEngine(
        [
            SearchDimension("brevity", 0, 5, kind="int"),
            SearchDimension("certainty", 0.0, 1.0),
        ],
        template_factory=lambda genes: (
            f"brevity={int(genes['brevity'])};certainty={float(genes['certainty']):.2f}"
        ),
        config=EvolutionConfig(
            population_size=12,
            generations=6,
            mutation_rate=0.25,
            crossover_rate=0.85,
            elite_count=2,
            random_seed=21,
        ),
    )

    def scorer(prompt: str) -> float:
        brevity_part, certainty_part = prompt.split(";")
        brevity = int(brevity_part.split("=")[1])
        certainty = float(certainty_part.split("=")[1])
        return 1.0 - abs(brevity - 4) * 0.07 - abs(certainty - 0.8)

    result = engine.optimize(scorer)

    assert result["best_score"] > 0.75
    assert result["generations"] == 6
    assert "brevity=" in result["best_template"]


def test_apo_engine_optimize_prompt_knobs_bayesian_records_backend_report() -> None:
    engine = APOEngine("You are ProjectX.")

    def scorer(prompt: str) -> float:
        score = 0.2
        if "step by step" in prompt.lower():
            score += 0.35
        if "confidence assessment" in prompt.lower():
            score += 0.2
        if "concise" in prompt.lower():
            score += 0.1
        return score

    report = engine.optimize_prompt_knobs(
        scorer,
        backend="bayesian",
        iterations=10,
        random_seed=5,
    )

    assert report["backend"] == "bayesian"
    assert report["best_score"] >= 0.55
    assert report["candidate_id"]
    assert engine.report()["backend_reports"][-1]["backend"] == "bayesian"


def test_apo_engine_optimize_prompt_knobs_evolutionary_records_backend_report() -> None:
    engine = APOEngine("You are ProjectX.")

    def scorer(prompt: str) -> float:
        score = 0.25
        if "compare at least two candidate solutions" in prompt.lower():
            score += 0.35
        if "failure modes and edge cases" in prompt.lower():
            score += 0.25
        if "terse operator-facing format" in prompt.lower():
            score += 0.1
        return score

    report = engine.optimize_prompt_knobs(
        scorer,
        backend="evolutionary",
        iterations=8,
        random_seed=9,
    )

    assert report["backend"] == "evolutionary"
    assert report["best_score"] >= 0.6
    assert report["candidate_id"]
    assert engine.report()["backend_reports"][-1]["backend"] == "evolutionary"
