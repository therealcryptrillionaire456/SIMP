#!/usr/bin/env python3
"""
Read-only capability audit for the local ProjectX + SIMP workspace.

The goal is to answer a practical operator question:
"What do I already have that is useful for agentic HTTP/HTTPS, offline mesh
communication, Graphify-guided navigation, and the quantum stack, and what is
still disconnected?"
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any


PROJECTX_ROOT = Path("/Users/kaseymarcelle/ProjectX")
SIMP_ROOT = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
GRAPHIFY_ROOT = Path("/Users/kaseymarcelle/Downloads/graphify")


@dataclass
class CapabilityCheck:
    name: str
    status: str
    evidence: List[str]
    notes: List[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def has_any(path: Path, patterns: List[str]) -> bool:
    text = read_text(path)
    return any(pattern in text for pattern in patterns)


def modified_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def audit_http_surface() -> CapabilityCheck:
    guard = PROJECTX_ROOT / "projectx_guard_server.py"
    guard_enhanced = PROJECTX_ROOT / "projectx_guard_server_enhanced.py"
    simp_bridge = PROJECTX_ROOT / "projectx_simp_bridge.py"
    simp_integration = PROJECTX_ROOT / "projectx_simp_integration.py"
    broker = SIMP_ROOT / "simp" / "server" / "broker.py"
    agent_server = SIMP_ROOT / "simp" / "server" / "agent_server.py"
    http_server = SIMP_ROOT / "simp" / "server" / "http_server.py"

    evidence = []
    notes = []

    if has_any(guard, ['if self.path == "/health"', 'if self.path == "/stats"', 'def do_POST']):
        evidence.append(f"{guard}: live ProjectX guard exposes health/stats and intent handling")
    if has_any(guard_enhanced, ["/simp/agent-card", "POST /intents/handle", "A2A"]):
        evidence.append(f"{guard_enhanced}: enhanced A2A/agent-card surface exists")
        notes.append("Enhanced guard server exists, but the default guard entrypoint is still projectx_guard_server.py.")
    if has_any(simp_bridge, ["A2ATask", "handle_a2a_task", "projectx_query"]):
        evidence.append(f"{simp_bridge}: ProjectX A2A bridge exists")
    if has_any(simp_integration, ["register_with_broker", "send_heartbeat", "Get A2A agent card"]):
        evidence.append(f"{simp_integration}: ProjectX SIMP agent registration/integration exists")
    if has_any(broker, ["_deliver_http", "/health", "/intents/handle"]):
        evidence.append(f"{broker}: broker already routes over local HTTP")
    if file_exists(agent_server) and file_exists(http_server):
        evidence.append(f"{agent_server} and {http_server}: SIMP has reusable HTTP agent server surfaces")
    if has_any(simp_integration, [":8080"]) and has_any(simp_bridge, [":5555"]) and has_any(PROJECTX_ROOT / "projectx_mesh_integration.py", [":5555"]):
        evidence.append(
            f"{simp_integration}, {simp_bridge}, and projectx_mesh_integration.py: ProjectX currently assumes both :8080 and :5555 broker ports"
        )
        notes.append("ProjectX is split between SIMP broker defaults on :8080 and :5555; this can quietly break local agent-to-agent flows unless the operator overrides config.")

    status = "healthy" if len(evidence) >= 4 else "partial"
    if has_any(guard_enhanced, ["A2A"]) and not has_any(guard, ["/simp/agent-card"]):
        status = "underutilized"
        notes.append("A2A-friendly endpoints are implemented but not the default operator path.")
    if has_any(simp_bridge, ["def handle_a2a_task", "def _process_intent"]) and has_any(simp_bridge, ["Unsupported intent type", '"validate_code", "check_safety", "ping", "projectx_query"']):
        notes.append("The ProjectX A2A bridge currently translates tasks but then handles only a small local intent set instead of promoting them into the broader broker routing path.")

    return CapabilityCheck(
        name="agentic_http_surface",
        status=status,
        evidence=evidence,
        notes=notes,
    )


def audit_mesh_offline_surface() -> CapabilityCheck:
    projectx_mesh = PROJECTX_ROOT / "projectx_mesh_integration.py"
    mesh_routing = SIMP_ROOT / "simp" / "server" / "mesh_routing.py"
    trust_graph = SIMP_ROOT / "simp" / "mesh" / "trust_graph.py"
    backend_manager = SIMP_ROOT / "simp" / "organs" / "quantum_intelligence" / "quantum_backend_manager.py"

    evidence = []
    notes = []

    if has_any(projectx_mesh, ["refresh_mesh_health", "maintenance_events", "system_heartbeats"]):
        evidence.append(f"{projectx_mesh}: ProjectX mesh monitor can operate from audit logs + mesh channels")
    if has_any(mesh_routing, ["MeshRoutingManager", "route_via_mesh", "MESH_INTENT"]):
        evidence.append(f"{mesh_routing}: broker supports mesh routing with BRP evaluation")
    if file_exists(trust_graph):
        evidence.append(f"{trust_graph}: trust graph exists for peer scoring")
    if has_any(backend_manager, ['"preferred_backend": "local_simulator"', '"enable_real_hardware": False']):
        evidence.append(f"{backend_manager}: quantum stack defaults to local/offline-capable simulators")

    status = "healthy" if len(evidence) >= 3 else "partial"
    notes.append("Local HTTP + mesh can work without internet; they still rely on local networking and power, not cloud connectivity.")
    notes.append("Cloud LLMs, IBM Quantum, Amazon Braket, and Azure Quantum will not work offline unless replaced with local backends/models.")

    return CapabilityCheck(
        name="mesh_offline_surface",
        status=status,
        evidence=evidence,
        notes=notes,
    )


def audit_graphify() -> CapabilityCheck:
    graph_script = SIMP_ROOT / "tools" / "graphify_simp_final.sh"
    graph_data = SIMP_ROOT / ".graphify" / "simp_graph.json"
    graph_analysis = SIMP_ROOT / ".graphify" / "analysis.json"
    graph_helper = SIMP_ROOT / ".graphify" / "agent_helper.py"
    obsidian_log = SIMP_ROOT / "logs" / "obsidian.log"
    broker = SIMP_ROOT / "simp" / "server" / "broker.py"
    projectx_guard = PROJECTX_ROOT / "projectx_guard_server.py"

    evidence = []
    notes = []

    if GRAPHIFY_ROOT.exists():
        evidence.append(f"{GRAPHIFY_ROOT}: Graphify source is installed locally")
    if file_exists(graph_script):
        evidence.append(f"{graph_script}: graph generation pipeline exists")
    if file_exists(graph_data) and file_exists(graph_analysis) and file_exists(graph_helper):
        evidence.append(
            f"{graph_data}: fresh graph data present (updated {modified_iso(graph_data)})"
        )
    if "Synchronization completed successfully" in read_text(obsidian_log):
        evidence.append(f"{obsidian_log}: Obsidian/Graphify sync has succeeded at least once")

    runtime_refs = []
    if has_any(broker, [".graphify", "SIMPGraphAnalyzer", "simp_graph.json"]):
        runtime_refs.append(str(broker))
    if has_any(projectx_guard, [".graphify", "SIMPGraphAnalyzer", "simp_graph.json"]):
        runtime_refs.append(str(projectx_guard))

    if runtime_refs:
        notes.append(f"Runtime graph usage found in: {', '.join(runtime_refs)}")
        status = "healthy"
    else:
        status = "underutilized"
        notes.append("Graphify is real and current, but it is not on the broker/guard critical path.")
        notes.append("Today it behaves like an architecture knowledge asset and helper toolkit, not a latency/throughput accelerator.")
        notes.append("No evidence was found that agents automatically consult Graphify during routing or task execution.")

    return CapabilityCheck(
        name="graphify_status",
        status=status,
        evidence=evidence,
        notes=notes,
    )


def audit_quantum_surface() -> CapabilityCheck:
    production_agent = SIMP_ROOT / "simp" / "organs" / "quantum_intelligence" / "production_agent.py"
    backend_manager = SIMP_ROOT / "simp" / "organs" / "quantum_intelligence" / "quantum_backend_manager.py"
    adapter = SIMP_ROOT / "simp" / "organs" / "quantum" / "quantum_adapter.py"
    quantumarb_quantum = SIMP_ROOT / "simp" / "organs" / "quantumarb" / "quantum_enhanced_arb.py"
    broker = SIMP_ROOT / "simp" / "server" / "broker.py"
    guard = PROJECTX_ROOT / "projectx_guard_server.py"

    evidence = []
    notes = []

    if has_any(production_agent, ["ProductionQuantumAgent", "QuantumIntelligentAgent"]):
        evidence.append(f"{production_agent}: production quantum agent wrapper exists")
    if has_any(backend_manager, ["IBM_QUANTUM", "PENNYLANE", "LOCAL_SIMULATOR", "QISKIT_AER"]):
        evidence.append(f"{backend_manager}: multi-backend quantum manager exists")
    if has_any(adapter, ["IBM Quantum", "PennyLane", "portfolio_optimize", "quantum_ml_inference"]):
        evidence.append(f"{adapter}: quantum adapter surface exists for real and local backends")
    if file_exists(quantumarb_quantum):
        evidence.append(f"{quantumarb_quantum}: quantum-enhanced arbitrage module exists")

    runtime_refs = []
    if has_any(broker, ["ProductionQuantumAgent", "quantum_backend_manager", "quantum_enhanced_arb"]):
        runtime_refs.append(str(broker))
    if has_any(guard, ["ProductionQuantumAgent", "quantum_backend_manager", "quantum_enhanced_arb"]):
        runtime_refs.append(str(guard))

    status = "underutilized"
    if runtime_refs:
        status = "partial"
        notes.append(f"Some runtime references found in: {', '.join(runtime_refs)}")
    else:
        notes.append("Quantum capability surface is broad, but it does not appear to be a default execution path for ProjectX guard or broker operations.")
    notes.append("The local simulator path means some quantum workflows can run without internet, but real hardware integrations remain opt-in and usually cloud-dependent.")

    return CapabilityCheck(
        name="quantum_surface",
        status=status,
        evidence=evidence,
        notes=notes,
    )


def underutilized_opportunities() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Promote A2A-first ProjectX entrypoint",
            "status": "high_value",
            "why": "Enhanced ProjectX guard exposes richer agent-card/A2A semantics than the default guard server.",
            "files": [
                str(PROJECTX_ROOT / "projectx_guard_server.py"),
                str(PROJECTX_ROOT / "projectx_guard_server_enhanced.py"),
                str(PROJECTX_ROOT / "projectx_simp_bridge.py"),
            ],
        },
        {
            "name": "Use Graphify as a pre-read oracle, not just a generated artifact",
            "status": "high_value",
            "why": "Graph data is fresh, but no broker/guard critical-path code appears to consult it before analysis or routing.",
            "files": [
                str(SIMP_ROOT / ".graphify" / "simp_graph.json"),
                str(SIMP_ROOT / ".graphify" / "agent_helper.py"),
                str(SIMP_ROOT / "tools" / "graph_navigator.py"),
            ],
        },
        {
            "name": "Bridge quantum surfaces into operator-facing intents",
            "status": "high_value",
            "why": "Quantum modules exist at production-wrapper depth, but they are not a default ProjectX/SIMP operator workflow.",
            "files": [
                str(SIMP_ROOT / "simp" / "organs" / "quantum_intelligence" / "production_agent.py"),
                str(SIMP_ROOT / "simp" / "organs" / "quantum" / "quantum_adapter.py"),
                str(SIMP_ROOT / "simp" / "agents" / "quantum_mode_agent.py"),
            ],
        },
        {
            "name": "Keep mesh as the offline backbone, HTTP as the local control plane",
            "status": "strategic",
            "why": "You already have both; the missing piece is treating them as one operator-visible transport strategy rather than separate implementations.",
            "files": [
                str(PROJECTX_ROOT / "projectx_mesh_integration.py"),
                str(SIMP_ROOT / "simp" / "server" / "mesh_routing.py"),
                str(SIMP_ROOT / "simp" / "server" / "broker.py"),
            ],
        },
    ]


def build_report() -> Dict[str, Any]:
    checks = [
        audit_http_surface(),
        audit_mesh_offline_surface(),
        audit_graphify(),
        audit_quantum_surface(),
    ]
    return {
        "generated_at": utc_now(),
        "tagline": "test everything, break nothing",
        "paths": {
            "projectx_root": str(PROJECTX_ROOT),
            "simp_root": str(SIMP_ROOT),
            "graphify_root": str(GRAPHIFY_ROOT),
        },
        "checks": [asdict(check) for check in checks],
        "underutilized_opportunities": underutilized_opportunities(),
        "git": {
            "projectx_is_git_repo": (PROJECTX_ROOT / ".git").exists(),
            "simp_is_git_repo": (SIMP_ROOT / ".git").exists(),
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Agentic Capability Audit",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Tagline: `{report['tagline']}`",
        "",
        "## Checks",
    ]
    for check in report["checks"]:
        lines.append(f"### {check['name']}")
        lines.append(f"- Status: `{check['status']}`")
        lines.append("- Evidence:")
        for item in check["evidence"]:
            lines.append(f"  - {item}")
        if check["notes"]:
            lines.append("- Notes:")
            for item in check["notes"]:
                lines.append(f"  - {item}")
        lines.append("")

    lines.append("## Highest-Value Opportunities")
    for item in report["underutilized_opportunities"]:
        lines.append(f"### {item['name']}")
        lines.append(f"- Status: `{item['status']}`")
        lines.append(f"- Why: {item['why']}")
        lines.append("- Files:")
        for file_path in item["files"]:
            lines.append(f"  - {file_path}")
        lines.append("")

    lines.append("## Git Reality")
    lines.append(f"- ProjectX root is a git repo: `{report['git']['projectx_is_git_repo']}`")
    lines.append(f"- SIMP root is a git repo: `{report['git']['simp_is_git_repo']}`")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local agentic capability surface.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    report = build_report()
    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
