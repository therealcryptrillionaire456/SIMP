#!/usr/bin/env python3.10
"""
Render a compact hot-runtime snapshot for operators.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
LOG_DIR = REPO / "logs"
RUNTIME_LOG_DIR = LOG_DIR / "runtime"
TRADE_LOG = LOG_DIR / "gate4_trades.jsonl"
BRIDGE_LOG = LOG_DIR / "quantum" / "signal_bridge.log"
STATE_FILE = REPO / "data" / "gate4_consumer_state.json"


@dataclass
class EndpointStatus:
    url: str
    ok: bool
    body: dict[str, Any] | None
    error: str | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_json(url: str, timeout: int = 3) -> EndpointStatus:
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - localhost/operator use
            payload = json.loads(response.read().decode("utf-8"))
            return EndpointStatus(url=url, ok=True, body=payload)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return EndpointStatus(url=url, ok=False, body=None, error=str(exc))


def tail_jsonl(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def latest_bridge_line(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if "Signal #" in line or "Signal written" in line or "QIP intent sent" in line:
            return line.strip()
    return None


def process_count(pattern: str) -> int:
    try:
        result = subprocess.run(  # noqa: S603
            ["pgrep", "-f", pattern],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return 0
    if result.returncode != 0:
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def load_gate4_state() -> dict[str, Any] | None:
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def build_snapshot() -> dict[str, Any]:
    broker = fetch_json("http://127.0.0.1:5555/health")
    dashboard = fetch_json("http://127.0.0.1:8050/health")
    projectx = fetch_json("http://127.0.0.1:8771/health")

    snapshot = {
        "timestamp": utc_now_iso(),
        "services": {
            "broker": broker.__dict__,
            "dashboard": dashboard.__dict__,
            "projectx": projectx.__dict__,
        },
        "processes": {
            "projectx_supervisor": process_count("projectx_supervisor.sh"),
            "projectx_guard": process_count("projectx_guard_server.py"),
            "gate4_consumer": process_count("gate4_inbox_consumer.py"),
            "quantum_signal_bridge": process_count("quantum_signal_bridge.py"),
            "quantum_mesh_consumer": process_count("quantum_mesh_consumer.py"),
            "quantum_advisory_broadcaster": process_count("quantum_advisory_broadcaster.py"),
        },
        "gate4": {
            "state": load_gate4_state(),
            "latest_trade": tail_jsonl(TRADE_LOG),
        },
        "bridge": {
            "latest_log_line": latest_bridge_line(BRIDGE_LOG),
        },
    }
    return snapshot


def render_markdown(snapshot: dict[str, Any]) -> str:
    latest_trade = snapshot["gate4"]["latest_trade"] or {}
    trade_result = latest_trade.get("result", "none")
    trade_symbol = latest_trade.get("symbol", "n/a")
    trade_side = latest_trade.get("side", "n/a")
    bridge_line = snapshot["bridge"]["latest_log_line"] or "No recent bridge activity"
    projectx = snapshot["services"]["projectx"]
    projectx_status = "up" if projectx["ok"] else f"down ({projectx['error']})"
    lines = [
        f"# SIMP Hot Runtime Snapshot",
        f"",
        f"- Timestamp: {snapshot['timestamp']}",
        f"- Broker: {'up' if snapshot['services']['broker']['ok'] else 'down'}",
        f"- Dashboard: {'up' if snapshot['services']['dashboard']['ok'] else 'down'}",
        f"- ProjectX: {projectx_status}",
        f"- Gate4 latest trade: {trade_symbol} {trade_side} -> {trade_result}",
        f"- Bridge: {bridge_line}",
        f"",
        f"## Process Counts",
    ]
    for name, count in snapshot["processes"].items():
        lines.append(f"- {name}: {count}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a SIMP hot runtime snapshot")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    snapshot = build_snapshot()
    if args.format == "markdown":
        print(render_markdown(snapshot))
    else:
        print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
