from __future__ import annotations

import json

def test_runtime_startup_report_is_written(monkeypatch, tmp_path) -> None:
    from simp.projectx import runtime_server

    target = tmp_path / "startup_report.json"
    payload = {
        "status": "ready",
        "manifest_validation": {"status": "valid"},
        "benchmark_history": {"run_count": 2},
    }

    monkeypatch.setattr(
        runtime_server,
        "ProjectXDeploymentManager",
        lambda: type(
            "DummyManager",
            (),
            {
                "readiness_report": lambda self, fast=True: type(
                    "Readiness",
                    (),
                    {"to_dict": lambda self: payload},
                )()
            },
        )(),
    )

    result = runtime_server.build_startup_report(str(target))

    assert result["status"] == "ready"
    assert json.loads(target.read_text(encoding="utf-8"))["benchmark_history"]["run_count"] == 2
