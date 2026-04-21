#!/usr/bin/env python3.10
"""Generate a current wire-up report for the hot runtime."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
REPORT_PATH = DOCS / "WIRE_UP_REPORT.md"
TRADE_LOG = REPO / "logs" / "gate4_trades.jsonl"
MESH_LOG = REPO / "data" / "mesh_events.jsonl"
REGISTRY_LOG = REPO / "data" / "agent_registry.jsonl"
BROKER_URL = "http://127.0.0.1:5555"
EXPECTED_CHANNELS = {
    "projectx_native": ["system", "safety_alerts", "maintenance_requests", "system_health", "trade_updates"],
    "projectx_quantum_advisor": ["system", "projectx_tasks", "maintenance_requests", "quantum_advisory", "trade_updates", "system_health"],
    "quantum_signal_bridge": ["system", "quantum", "trade_signals"],
    "quantum_advisory_broadcaster": ["system", "quantum_advisory", "trade_updates"],
    "quantum_intelligence_prime": ["system", "quantum"],
    "goose_orchestrator": ["system", "orchestration_commands", "maintenance_requests"],
    "goose_bridge": ["system", "maintenance_requests"],
    "goose_kloutbot_bridge": ["system", "maintenance_requests", "trade_updates"],
    "goose_kloutbot_bridge_test": ["system", "maintenance_requests", "trade_updates"],
    "goose_kloutbot_bridge_test2": ["system", "maintenance_requests", "trade_updates"],
    "kloutbot": ["system", "trade_updates", "maintenance_events"],
    "ktc_agent": ["system", "trade_updates", "maintenance_events"],
    "brp_audit_consumer": ["system", "safety_alerts"],
    "test_goose_bridge": ["system", "maintenance_requests"],
}


def fetch_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost/operator use
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def latest_successful_trade() -> dict[str, Any] | None:
    for row in reversed(load_jsonl(TRADE_LOG)):
        if row.get("result") == "ok":
            return row
    return None


def recent_mesh_activity(window_minutes: int = 10) -> dict[str, list[str]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    activity: dict[str, list[str]] = {}
    for row in load_jsonl(MESH_LOG):
        ts = row.get("timestamp")
        if not ts:
            continue
        try:
            row_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            continue
        if row_dt < cutoff:
            continue
        for agent_key in ("sender_id", "recipient_id"):
            agent_id = row.get(agent_key)
            if not agent_id:
                continue
            activity.setdefault(agent_id, []).append(f"{row.get('event_type')}:{row.get('channel')}")
    return activity


def load_registry_state(window_minutes: int = 30) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    state: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(REGISTRY_LOG):
        agent_id = row.get("agent_id")
        if not agent_id:
            continue
        event = row.get("event")
        if event == "deregistered":
            state.pop(agent_id, None)
            continue
        current = state.setdefault(agent_id, {"agent_id": agent_id})
        if event == "registered":
            current.update(row.get("agent_data") or {})
        elif event == "updated":
            current.update(row.get("updates") or {})
        current["timestamp"] = row.get("timestamp")

    active: list[dict[str, Any]] = []
    for agent in state.values():
        ts_value = agent.get("last_seen") or agent.get("last_heartbeat") or agent.get("timestamp")
        if not ts_value:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts < cutoff:
            continue
        active.append(agent)
    active.sort(key=lambda item: str(item.get("agent_id")))
    return active


def reconcile_channels(agent_channels: dict[str, list[str]]) -> list[str]:
    actions: list[str] = []
    for agent_id, expected in EXPECTED_CHANNELS.items():
        current = set(agent_channels.get(agent_id, []))
        missing = [channel for channel in expected if channel not in current]
        if not missing:
            continue
        for channel in missing:
            response = fetch_json(
                f"{BROKER_URL}/mesh/subscribe",
                method="POST",
                payload={"agent_id": agent_id, "channel": channel},
            )
            if response and response.get("status") == "success":
                actions.append(f"Subscribed {agent_id} -> {channel}")
    return actions


def build_report(reconcile: bool = False) -> str:
    agents_response = fetch_json(f"{BROKER_URL}/agents") or {}
    subscriptions_response = fetch_json(f"{BROKER_URL}/mesh/subscriptions") or {}
    verify_report = fetch_json(f"{BROKER_URL}/health")
    agents = agents_response.get("agents", [])
    agent_channels = subscriptions_response.get("agent_channels", {})
    inventory_source = "broker"

    if not agents:
        agents = load_registry_state()
        inventory_source = "agent_registry"
    if not agent_channels:
        agent_channels = {
            agent_id: list(channels)
            for agent_id, channels in EXPECTED_CHANNELS.items()
            if any(str(agent.get("agent_id")) == agent_id for agent in agents)
        }

    reconcile_actions: list[str] = []
    if reconcile and agent_channels:
        reconcile_actions = reconcile_channels(agent_channels)
        subscriptions_response = fetch_json(f"{BROKER_URL}/mesh/subscriptions") or subscriptions_response
        agent_channels = subscriptions_response.get("agent_channels", agent_channels)

    activity = recent_mesh_activity()
    latest_fill = latest_successful_trade()

    lines = [
        "# Wire-Up Report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Broker URL: {BROKER_URL}",
        f"- Registered agents reported by broker: {len(agents)}",
        f"- Inventory source: {inventory_source}",
        f"- Channel source: {'broker' if subscriptions_response else 'expected_map_fallback'}",
        "",
        "## Edge Inventory",
        "",
        "| Producer | Consumer | Channel | Status |",
        "| --- | --- | --- | --- |",
    ]

    for agent in agents:
        if not isinstance(agent, dict):
            continue
        agent_id = str(agent.get("agent_id") or "")
        channels = agent_channels.get(agent_id, [])
        if not channels:
            lines.append(f"| {agent_id} | _(none)_ | _(none)_ | flagged:no_channels |")
            continue
        for channel in channels:
            recent = "active" if activity.get(agent_id) else "idle"
            lines.append(f"| {agent_id} | * | `{channel}` | {recent} |")

    lines.extend(
        [
            "",
            "## Heartbeats",
            "",
            "| Agent | Last Heartbeat | Stale | Expected Channels Missing | Recent Activity |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for agent in agents:
        if not isinstance(agent, dict):
            continue
        agent_id = str(agent.get("agent_id") or "")
        heartbeat = fetch_json(f"{BROKER_URL}/agents/{agent_id}/heartbeat") or {}
        current_channels = set(agent_channels.get(agent_id, []))
        expected_channels = set(EXPECTED_CHANNELS.get(agent_id, []))
        missing = sorted(expected_channels - current_channels)
        recent = ", ".join(activity.get(agent_id, [])[:3]) or "none"
        lines.append(
            f"| {agent_id} | {heartbeat.get('last_heartbeat', agent.get('last_heartbeat', 'n/a'))} | "
            f"{heartbeat.get('stale', agent.get('stale', 'n/a'))} | "
            f"{', '.join(missing) if missing else 'none'} | {recent} |"
        )

    lines.extend(
        [
            "",
            "## Revenue Path",
            "",
            f"- Latest successful fill: `{json.dumps(latest_fill, default=str) if latest_fill else 'none'}`",
            f"- Broker health surface: `{json.dumps(verify_report, default=str) if verify_report else 'unavailable'}`",
            f"- Mesh activity source: `{'mesh_events.jsonl recent window' if activity else 'registry/expected-map fallback'}`",
        ]
    )

    if reconcile_actions:
        lines.extend(["", "## Reconciliation Actions", ""])
        lines.extend([f"- {item}" for item in reconcile_actions])

    snapshot_start = Path("/tmp/snapshot_start.md")
    verify_start = Path("/tmp/verify_start.json")
    if snapshot_start.exists():
        lines.extend(["", "## Snapshot Start", "", "```markdown", snapshot_start.read_text(encoding="utf-8").rstrip(), "```"])
    if verify_start.exists():
        lines.extend(["", "## Verify Start", "", "```json", verify_start.read_text(encoding="utf-8").rstrip(), "```"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/WIRE_UP_REPORT.md")
    parser.add_argument("--reconcile", action="store_true", help="Re-subscribe missing expected channels before writing the report")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    report = build_report(reconcile=args.reconcile)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
