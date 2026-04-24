from __future__ import annotations

import json

from simp.projectx.benchmark import BenchmarkRunner


def test_benchmark_history_summary_reads_recent_runs(tmp_path) -> None:
    history_path = tmp_path / "benchmark_history.jsonl"
    rows = [
        {"executor_id": "projx", "overall_score": 0.52},
        {"executor_id": "projx", "overall_score": 0.66},
        {"executor_id": "projx", "overall_score": 0.78},
    ]
    history_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    runner = BenchmarkRunner(history_path=str(history_path), executor_id="projx")
    summary = runner.history_summary(limit=3)

    assert summary.run_count == 3
    assert summary.latest_score == 0.78
    assert summary.best_score == 0.78
    assert summary.trend_ratio == 1.5
    assert len(summary.recent_runs) == 3
