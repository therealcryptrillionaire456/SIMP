"""
ProjectX Evaluation Framework — Tranche 2 Phase 10

A comprehensive eval framework for detecting regressions, replaying SIMP tasks,
and generating adversarial test cases.

Modules:
- score_registry: Track eval scores over time with delta detection and regression gates
- regression_suite: Core task evals for coding, protocol reasoning, and self-checks
- replay_harness: Replay real SIMP tasks and score against baselines
- adversarial_generator: Generate synthetic hard cases from existing failures

Usage::

    from scripts.eval import RegressionSuite, get_registry

    # Run regression suite
    suite = RegressionSuite()
    report = suite.run(executor=my_llm)

    # Track in registry
    registry = get_registry()
    suite.run_with_tracking(executor=my_llm, registry=registry)
"""

from .score_registry import (
    ScoreRegistry,
    EvalScore,
    Baseline,
    DeltaResult,
    RegressionError,
    SuiteType,
    RegressionStatus,
    get_registry,
)

from .regression_suite import (
    RegressionSuite,
    RegressionTask,
    RegressionReport,
    TaskResult,
    TaskDomain,
    SUITE_NAME as REGRESSION_SUITE_NAME,
)

from .replay_harness import (
    ReplayHarness,
    BaselineRun,
    BaselineTask,
    ReplayResults,
    ReplayTaskResult,
    TaskStatus,
    ComparisonMode,
    SUITE_NAME as REPLAY_SUITE_NAME,
)

from .adversarial_generator import (
    AdversarialGenerator,
    AdversarialCase,
    AdversarialCategory,
    Difficulty,
    FailureRecord,
    TransformationStrategy,
    SUITE_NAME as ADVERSARIAL_SUITE_NAME,
)

__all__ = [
    # Score Registry
    "ScoreRegistry",
    "EvalScore",
    "Baseline",
    "DeltaResult",
    "RegressionError",
    "SuiteType",
    "RegressionStatus",
    "get_registry",
    # Regression Suite
    "RegressionSuite",
    "RegressionTask",
    "RegressionReport",
    "TaskResult",
    "TaskDomain",
    "REGRESSION_SUITE_NAME",
    # Replay Harness
    "ReplayHarness",
    "BaselineRun",
    "BaselineTask",
    "ReplayResults",
    "ReplayTaskResult",
    "TaskStatus",
    "ComparisonMode",
    "REPLAY_SUITE_NAME",
    # Adversarial Generator
    "AdversarialGenerator",
    "AdversarialCase",
    "AdversarialCategory",
    "Difficulty",
    "FailureRecord",
    "TransformationStrategy",
    "ADVERSARIAL_SUITE_NAME",
]
