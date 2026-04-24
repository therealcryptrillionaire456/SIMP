"""Entrypoint for running the ProjectX HTTP runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path

from simp.projectx.deployment import ProjectXDeploymentManager
from simp.server.http_server import create_http_server


def build_startup_report(output_path: str = "projectx_logs/runtime_startup_report.json") -> dict:
    report = ProjectXDeploymentManager().readiness_report(fast=True).to_dict()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    host = os.environ.get("PROJECTX_HOST", "127.0.0.1")
    port = int(os.environ.get("PROJECTX_PORT", "5555"))
    build_startup_report()
    server = create_http_server(host=host, port=port, debug=False)
    server.run(host=host, port=port)


if __name__ == "__main__":
    main()
