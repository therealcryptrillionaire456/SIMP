#!/usr/bin/env python3
"""
ProjectX Eval Runner — Tranche 2 Phase 10

Unified entry point for running all eval suites with tracking and gate enforcement.

Usage::

    # Run all suites
    python3 scripts/eval/run_eval.py --all

    # Run specific suite
    python3 scripts/eval/run_eval.py --suite regression --domain coding

    # With gates enforced
    python3 scripts/eval/run_eval.py --all --enforce-gates

    # Establish baselines
    python3 scripts/eval/run_eval.py --establish-baselines
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.eval import (
    RegressionSuite,
    ReplayHarness,
    AdversarialGenerator,
    get_registry,
    ScoreRegistry,
    SuiteType,
    RegressionStatus,
    RegressionError,
)
from scripts.eval.regression_suite import stub_executor, TaskDomain


def run_regression_suite(
    registry: ScoreRegistry,
    domains: Optional[List[TaskDomain]] = None,
    establish_baseline: bool = False,
    enforce_gates: bool = False,
) -> dict:
    """Run regression suite."""
    print("\n" + "=" * 60)
    print("Running Regression Suite")
    print("=" * 60)
    
    suite = RegressionSuite()
    if domains:
        suite = suite.filter_domain(domains[0])
    
    print(f"Tasks: {len(suite)}")
    
    # Run with stub executor (replace with real LLM in production)
    report = suite.run(executor=stub_executor, executor_id="default")
    
    # Print summary
    print(f"\n  Overall Score: {report.overall_score:.1%}")
    print(f"  Pass Rate:     {report.pass_rate:.1%}")
    print(f"  Passed:        {report.passed_count}/{len(report.results)}")
    
    for domain, scores in report.by_domain().items():
        print(f"    {domain:12s}: {scores['score']:.1%}")
    
    # Record in registry
    registry.record_suite_run(
        suite_name="projectx_regression",
        score=report.overall_score,
        suite_type=SuiteType.REGRESSION,
        metadata={
            "executor_id": report.executor_id,
            "run_id": report.run_id,
            "domains": [d.value for d in (domains or [])],
        },
        task_results=[r.to_dict() for r in report.results],
        domain_scores={d: s["score"] for d, s in report.by_domain().items()},
        latency_ms=report.total_ms,
    )
    
    # Check gates
    gate_results = {}
    if enforce_gates:
        gate_results = registry.enforce_all_gates(
            suite_names=["projectx_regression"],
            raise_on_regression=False,
        )
    
    return {
        "suite": "regression",
        "score": report.overall_score,
        "passed": report.passed_count,
        "total": len(report.results),
        "gate_results": gate_results,
    }


def run_replay_suite(
    registry: ScoreRegistry,
    baseline_path: Optional[Path] = None,
    establish_baseline: bool = False,
    enforce_gates: bool = False,
) -> dict:
    """Run replay suite if baseline exists."""
    print("\n" + "=" * 60)
    print("Running Replay Suite")
    print("=" * 60)
    
    harness = ReplayHarness()
    
    # Check for baselines
    baselines = harness.list_baselines()
    if not baselines:
        print("  No baselines found. Skipping replay suite.")
        return {"suite": "replay", "skipped": True}
    
    # Use first baseline or specified
    baseline = harness.load_baseline(baselines[0])
    if not baseline:
        print(f"  Failed to load baseline. Skipping.")
        return {"suite": "replay", "skipped": True}
    
    print(f"  Baseline: {baseline.name}")
    print(f"  Tasks: {baseline.task_count}")
    
    # Replay with stub executor
    results = harness.replay(baseline, stub_executor)
    
    print(f"\n  Overall Score: {results.overall_score:.1%}")
    print(f"  Passed:        {results.passed_count}/{len(results.task_results)}")
    
    # Record in registry
    registry.record_suite_run(
        suite_name="projectx_replay",
        score=results.overall_score,
        suite_type=SuiteType.REPLAY,
        metadata={
            "baseline_name": baseline.name,
            "baseline_id": baseline.run_id,
            "run_id": results.run_id,
        },
        task_results=[r.to_dict() for r in results.task_results],
        latency_ms=results.total_ms,
    )
    
    return {
        "suite": "replay",
        "score": results.overall_score,
        "passed": results.passed_count,
        "total": len(results.task_results),
    }


def run_adversarial_generation(
    registry: ScoreRegistry,
    failures_path: Optional[Path] = None,
    n_cases: int = 5,
) -> dict:
    """Run adversarial generation if failures exist."""
    print("\n" + "=" * 60)
    print("Running Adversarial Generation")
    print("=" * 60)
    
    generator = AdversarialGenerator()
    
    # Generate from failures JSONL if exists
    if failures_path and failures_path.exists():
        cases = generator.generate_from_jsonl(failures_path, n_per_task=n_cases)
    else:
        # Generate targeted cases
        cases = generator.generate_targeted(
            category=AdversarialGenerator.__init__.__code__.co_consts[1] 
            if hasattr(AdversarialGenerator.__init__, "__code__") else None,
            difficulty=Difficulty.MEDIUM,
            n=n_cases,
        )
    
    print(f"  Generated: {len(cases)} cases")
    
    return {
        "suite": "adversarial",
        "generated": len(cases),
    }


def establish_all_baselines(registry: ScoreRegistry) -> None:
    """Establish baselines from current scores."""
    print("\n" + "=" * 60)
    print("Establishing Baselines")
    print("=" * 60)
    
    # Get current scores
    for suite_name in ["projectx_regression", "projectx_replay"]:
        delta = registry.get_delta(suite_name)
        if delta and delta.current_score > 0:
            registry.establish_baseline(
                suite_name=suite_name,
                score=delta.current_score,
                established_by="eval_runner",
            )
            print(f"  {suite_name}: baseline = {delta.current_score:.1%}")
        else:
            print(f"  {suite_name}: no data for baseline")


def print_summary(results: List[dict], registry: ScoreRegistry) -> None:
    """Print final summary."""
    print("\n" + "=" * 60)
    print("Eval Summary")
    print("=" * 60)
    
    for result in results:
        if result.get("skipped"):
            print(f"  {result['suite']:12s}: SKIPPED")
        else:
            score = result.get("score", 0)
            passed = result.get("passed", 0)
            total = result.get("total", 0)
            status = "PASS" if score >= 0.7 else "FAIL"
            print(f"  {result['suite']:12s}: {score:.1%} ({passed}/{total}) [{status}]")
    
    # Check for regressions
    summary = registry.get_summary()
    if summary.regression_alerts:
        print(f"\n  REGRESSION ALERTS:")
        for alert in summary.regression_alerts:
            print(f"    {alert.suite_name}: {alert.absolute_delta:+.3f}")


def main():
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="ProjectX Eval Runner")
    parser.add_argument("--suite", choices=["regression", "replay", "adversarial"], 
                        help="Specific suite to run")
    parser.add_argument("--all", action="store_true", help="Run all suites")
    parser.add_argument("--domain", choices=[d.value for d in TaskDomain], 
                        help="Filter regression suite by domain")
    parser.add_argument("--establish-baselines", action="store_true", 
                        help="Establish baselines from current scores")
    parser.add_argument("--enforce-gates", action="store_true", 
                        help="Enforce regression gates (fail on regression)")
    parser.add_argument("--baseline-path", type=Path, 
                        help="Path to replay baseline")
    parser.add_argument("--failures-path", type=Path, 
                        help="Path to failures JSONL for adversarial generation")
    parser.add_argument("--n-cases", type=int, default=5, 
                        help="Number of adversarial cases to generate")
    parser.add_argument("--output", type=Path, help="Output summary JSON path")
    
    args = parser.parse_args()
    
    registry = get_registry()
    results = []
    
    # Establish baselines if requested
    if args.establish_baselines:
        establish_all_baselines(registry)
        return
    
    # Run suites
    if args.all or args.suite == "regression":
        domains = [TaskDomain(args.domain)] if args.domain else None
        results.append(run_regression_suite(
            registry, domains, enforce_gates=args.enforce_gates
        ))
    
    if args.all or args.suite == "replay":
        results.append(run_replay_suite(
            registry, args.baseline_path, enforce_gates=args.enforce_gates
        ))
    
    if args.all or args.suite == "adversarial":
        results.append(run_adversarial_generation(
            registry, args.failures_path, args.n_cases
        ))
    
    # Print summary
    print_summary(results, registry)
    
    # Export summary if requested
    if args.output:
        data = registry.export_summary(args.output)
        print(f"\nExported to {args.output}")
    
    # Exit with error if gates failed
    if args.enforce_gates:
        for result in results:
            gate_results = result.get("gate_results", {})
            if any(not passed for passed in gate_results.values()):
                print("\nRegression gates FAILED")
                sys.exit(1)
        print("\nRegression gates PASSED")


if __name__ == "__main__":
    main()
