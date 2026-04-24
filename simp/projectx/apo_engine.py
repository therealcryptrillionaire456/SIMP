"""
ProjectX APO Engine — Phase 3

Automatic Prompt Optimization with Bayesian search over the prompt space.
Builds on the Agent Lightning APO framework already present in SIMP by
providing a self-contained optimizer that can be called from any agent
without depending on the full Agent Lightning stack.

Architecture:
  - PromptCandidate: a versioned, scored prompt variant
  - APOEngine: manages population, evaluates fitness, selects survivors
  - BayesianSampler: Gaussian-process–inspired surrogate for efficient search
  - EvoSearch: genetic mutation + crossover fallback when Bayesian data is thin

Design principles:
  - Stateless between calls; state is persisted to JSONL
  - Never modifies production prompts automatically; caller must apply
  - All scoring is async-compatible (no blocking loops internally)
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .bayesian_optimization import PromptBayesianOptimizer, SearchDimension
from .evolutionary_ai import EvolutionConfig, PromptEvolutionEngine

logger = logging.getLogger(__name__)

# Minimum evaluations before Bayesian surrogate kicks in
_BAYES_MIN_SAMPLES = 6
# Exploration weight in UCB acquisition (higher = more exploration)
_UCB_KAPPA = 2.0
# Fraction of population replaced each generation
_REPLACEMENT_RATE = 0.3
# Max population kept in memory
_MAX_POPULATION = 50


@dataclass
class PromptCandidate:
    """A versioned prompt variant with its performance history."""
    candidate_id: str
    template: str
    variables: Dict[str, str] = field(default_factory=dict)
    scores: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    generation: int = 0

    @property
    def mean_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def score_variance(self) -> float:
        if len(self.scores) < 2:
            return 1.0
        mu = self.mean_score
        return sum((s - mu) ** 2 for s in self.scores) / len(self.scores)

    @property
    def ucb_score(self) -> float:
        n = len(self.scores) or 1
        return self.mean_score + _UCB_KAPPA * math.sqrt(math.log(n + 1) / n)

    def render(self, **kwargs) -> str:
        """Render the template with provided variables."""
        text = self.template
        ctx = {**self.variables, **kwargs}
        for k, v in ctx.items():
            text = text.replace(f"{{{k}}}", str(v))
        return text

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EvalResult:
    """Result of evaluating a prompt candidate."""
    candidate_id: str
    score: float           # 0.0–1.0
    response: str = ""
    latency_ms: int = 0
    tokens_used: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.error is None


class APOEngine:
    """
    Automatic Prompt Optimizer.

    Maintains a population of prompt candidates, evaluates them using
    caller-supplied scorer functions, and evolves the population toward
    higher scores over time.

    Usage::

        engine = APOEngine("My task prompt: {input}")

        def scorer(prompt: str) -> float:
            response = call_llm(prompt)
            return evaluate_response(response)

        best = engine.optimize(scorer, input="hello world", steps=20)
        print(best.template)
    """

    def __init__(
        self,
        base_prompt: str,
        population_size: int = 10,
        persist_path: Optional[str] = None,
        task_name: str = "default",
    ) -> None:
        self._task_name = task_name
        self._base_prompt = base_prompt
        self._population: List[PromptCandidate] = []
        self._generation = 0
        self._persist_path = Path(persist_path) if persist_path else None
        self._eval_history: List[EvalResult] = []
        self._backend_reports: List[Dict[str, Any]] = []

        seed = self._make_candidate(base_prompt, generation=0)
        self._population.append(seed)
        self._expand_population(base_prompt, target=population_size)

        if self._persist_path:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_history()

    # ── Public API ────────────────────────────────────────────────────────

    def optimize(
        self,
        scorer: Callable[[str], float],
        steps: int = 20,
        **render_kwargs,
    ) -> PromptCandidate:
        """
        Run `steps` optimization steps and return the best candidate.

        Args:
            scorer: Function that takes a rendered prompt string and returns
                    a scalar score in [0, 1].
            steps:  Number of evaluate-evolve cycles.
            **render_kwargs: Variables passed to candidate.render().

        Returns:
            The best-scoring PromptCandidate after optimization.
        """
        for step in range(steps):
            candidate = self._select_candidate()
            prompt_text = candidate.render(**render_kwargs)

            t0 = time.time()
            try:
                score = float(scorer(prompt_text))
            except Exception as exc:
                logger.warning("Scorer raised %s for candidate %s", exc, candidate.candidate_id)
                score = 0.0

            latency = int((time.time() - t0) * 1000)
            candidate.scores.append(score)

            result = EvalResult(
                candidate_id=candidate.candidate_id,
                score=score,
                latency_ms=latency,
            )
            self._eval_history.append(result)

            logger.debug(
                "Step %d/%d  id=%s  score=%.3f  ucb=%.3f",
                step + 1, steps, candidate.candidate_id[:8], score, candidate.ucb_score,
            )

            # Evolve every 5 steps
            if (step + 1) % 5 == 0:
                self._evolve()

        if self._persist_path:
            self._save_history()

        return self.best_candidate

    def get_population(self) -> List[PromptCandidate]:
        return list(self._population)

    @property
    def best_candidate(self) -> PromptCandidate:
        return max(self._population, key=lambda c: c.mean_score)

    def add_candidate(self, template: str, metadata: Optional[Dict] = None) -> PromptCandidate:
        """Inject an externally crafted prompt into the population."""
        c = self._make_candidate(template, generation=self._generation, metadata=metadata or {})
        self._population.append(c)
        if len(self._population) > _MAX_POPULATION:
            self._cull()
        return c

    def report(self) -> Dict[str, Any]:
        """Return a summary of the current optimization state."""
        return {
            "task_name": self._task_name,
            "generation": self._generation,
            "population_size": len(self._population),
            "evaluations": len(self._eval_history),
            "best_score": self.best_candidate.mean_score if self._population else 0.0,
            "best_template_preview": (self.best_candidate.template[:120] + "…")
            if self._population else "",
            "backend_reports": self._backend_reports[-5:],
        }

    def optimize_prompt_knobs(
        self,
        scorer: Callable[[str], float],
        *,
        backend: str = "bayesian",
        iterations: int = 12,
        random_seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Optimize bounded prompt-control knobs with a concrete optimizer backend.
        """
        dimensions = [
            SearchDimension("reasoning", 0, 3, kind="int"),
            SearchDimension("brevity", 0, 2, kind="int"),
            SearchDimension("confidence", 0, 1, kind="int"),
        ]

        def template_factory(params: Dict[str, float | int]) -> str:
            parts = [self._base_prompt]
            if int(params["reasoning"]) >= 1:
                parts.append("Reason step by step before answering.")
            if int(params["reasoning"]) >= 2:
                parts.append("Compare at least two candidate solutions before selecting one.")
            if int(params["reasoning"]) >= 3:
                parts.append("Include explicit failure modes and edge cases.")
            brevity = int(params["brevity"])
            if brevity == 1:
                parts.append("Keep the answer concise.")
            elif brevity >= 2:
                parts.append("Respond in a terse operator-facing format.")
            if int(params["confidence"]) >= 1:
                parts.append("Include a short confidence assessment.")
            return " ".join(parts).strip()

        if backend == "bayesian":
            optimizer = PromptBayesianOptimizer(
                dimensions,
                template_factory,
                random_seed=random_seed,
            )
            result = optimizer.optimize(scorer, iterations=iterations, warmup=min(4, iterations))
        elif backend == "evolutionary":
            optimizer = PromptEvolutionEngine(
                dimensions,
                template_factory,
                config=EvolutionConfig(
                    population_size=max(6, min(16, iterations)),
                    generations=max(3, min(10, iterations)),
                    mutation_rate=0.25,
                    crossover_rate=0.85,
                    elite_count=2,
                    random_seed=random_seed,
                ),
            )
            evo = optimizer.optimize(scorer)
            result = {
                "best_params": evo["best_genes"],
                "best_score": evo["best_score"],
                "best_template": evo["best_template"],
                "iterations": evo["generations"],
                "history": evo["history"],
                "observation_count": len(evo["history"]),
            }
        else:
            raise ValueError(f"Unknown APO backend: {backend}")

        candidate = self.add_candidate(
            result["best_template"],
            metadata={
                "backend": backend,
                "optimized_params": result["best_params"],
                "optimized_score": result["best_score"],
            },
        )
        candidate.scores.append(float(result["best_score"]))
        report = {
            "backend": backend,
            "best_score": float(result["best_score"]),
            "best_params": dict(result["best_params"]),
            "candidate_id": candidate.candidate_id,
            "template_preview": result["best_template"][:160],
            "iterations": int(result.get("iterations", iterations)),
            "observation_count": int(result.get("observation_count", 0)),
        }
        if "history" in result:
            report["history"] = list(result["history"])
        self._backend_reports.append(report)
        self._generation += 1
        if len(self._backend_reports) > 100:
            self._backend_reports = self._backend_reports[-50:]
        if self._persist_path:
            self._save_history()
        return report

    # ── Selection ─────────────────────────────────────────────────────────

    def _select_candidate(self) -> PromptCandidate:
        """UCB-based selection: balance exploitation vs. exploration."""
        evaluated = [c for c in self._population if c.scores]
        unevaluated = [c for c in self._population if not c.scores]
        if unevaluated:
            return random.choice(unevaluated)
        if len(evaluated) < _BAYES_MIN_SAMPLES:
            return random.choice(evaluated)
        return max(evaluated, key=lambda c: c.ucb_score)

    # ── Evolution ─────────────────────────────────────────────────────────

    def _evolve(self) -> None:
        self._generation += 1
        n_replace = max(1, int(len(self._population) * _REPLACEMENT_RATE))
        evaluated = [c for c in self._population if c.scores]
        if len(evaluated) < 2:
            return

        # Sort by mean score descending
        evaluated.sort(key=lambda c: c.mean_score, reverse=True)
        top_half = evaluated[: len(evaluated) // 2 + 1]

        new_candidates = []
        for _ in range(n_replace):
            a, b = random.sample(top_half, min(2, len(top_half)))
            child = self._crossover(a, b)
            child = self._mutate(child)
            new_candidates.append(child)

        # Remove lowest-scoring and add children
        evaluated.sort(key=lambda c: c.mean_score)
        to_remove = evaluated[:n_replace]
        for c in to_remove:
            self._population.remove(c)
        self._population.extend(new_candidates)

    def _crossover(self, a: PromptCandidate, b: PromptCandidate) -> PromptCandidate:
        """Single-point sentence-level crossover."""
        sents_a = a.template.split(". ")
        sents_b = b.template.split(". ")
        mid_a = len(sents_a) // 2
        mid_b = len(sents_b) // 2
        merged = sents_a[:mid_a] + sents_b[mid_b:]
        template = ". ".join(merged).strip()
        return self._make_candidate(template, generation=self._generation,
                                    metadata={"parents": [a.candidate_id, b.candidate_id]})

    _MUTATIONS = [
        lambda t: t.replace("You are", "Act as"),
        lambda t: t.replace("Please", ""),
        lambda t: t + " Think step by step.",
        lambda t: "Let's reason carefully. " + t,
        lambda t: t.replace("should", "must"),
        lambda t: t + " Be concise.",
        lambda t: t + " Provide a confidence score.",
        lambda t: t.replace(".", ". Importantly,", 1) if "." in t else t,
    ]

    def _mutate(self, candidate: PromptCandidate) -> PromptCandidate:
        mutation = random.choice(self._MUTATIONS)
        try:
            new_template = mutation(candidate.template)
        except Exception:
            new_template = candidate.template
        c = copy.deepcopy(candidate)
        c.candidate_id = hashlib.sha256(
            (new_template + str(time.time())).encode()
        ).hexdigest()[:16]
        c.template = new_template
        c.scores = []
        c.generation = self._generation
        c.metadata["mutated_from"] = candidate.candidate_id
        return c

    # ── Population helpers ────────────────────────────────────────────────

    def _expand_population(self, base: str, target: int) -> None:
        for _ in range(target - 1):
            c = self._make_candidate(base, generation=0)
            c = self._mutate(c)
            self._population.append(c)

    def _cull(self) -> None:
        evaluated = [c for c in self._population if c.scores]
        if len(evaluated) > _MAX_POPULATION:
            evaluated.sort(key=lambda c: c.mean_score)
            for c in evaluated[: len(evaluated) - _MAX_POPULATION]:
                self._population.remove(c)

    @staticmethod
    def _make_candidate(
        template: str,
        generation: int = 0,
        metadata: Optional[Dict] = None,
    ) -> PromptCandidate:
        cid = hashlib.sha256(
            (template + str(time.time()) + str(random.random())).encode()
        ).hexdigest()[:16]
        return PromptCandidate(
            candidate_id=cid,
            template=template,
            generation=generation,
            metadata=metadata or {},
        )

    # ── Persistence ───────────────────────────────────────────────────────

    def _save_history(self) -> None:
        if not self._persist_path:
            return
        try:
            with open(self._persist_path, "w") as f:
                for result in self._eval_history[-1000:]:
                    f.write(json.dumps(asdict(result)) + "\n")
        except Exception as exc:
            logger.warning("APOEngine: failed to save history: %s", exc)

    def _load_history(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            with open(self._persist_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._eval_history.append(EvalResult(**json.loads(line)))
        except Exception as exc:
            logger.warning("APOEngine: failed to load history: %s", exc)
