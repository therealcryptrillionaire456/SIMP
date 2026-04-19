# Agentic Capability Audit

Generated from the local workspace using:

```bash
python3 tools/agentic_capability_audit.py --format markdown
```

This audit is intentionally practical. It is not asking "what code exists?" only.
It is asking:

1. What already works for agentic HTTP/HTTPS?
2. What already works offline with only local power/network?
3. What exists but is disconnected from the default execution path?
4. Is Graphify actually helping runtime behavior?

## Current State

### 1. Agentic HTTP/HTTPS is present, but underutilized

The stack already contains:

- A live ProjectX guard server with `/health`, `/stats`, and intent handling.
- An enhanced ProjectX guard server with richer A2A-style surfaces.
- A ProjectX A2A/SIMP bridge.
- A SIMP broker that already routes over local HTTP.
- Reusable HTTP agent server surfaces in SIMP.

The main underuse is not missing code. It is path selection:

- The default operator entrypoint is still the simpler `projectx_guard_server.py`.
- The richer A2A-first surfaces exist, but are not the default control plane.
- ProjectX currently assumes both `:8080` and `:5555` for the SIMP broker in different files, which can quietly break local HTTP/A2A flows.
- The ProjectX A2A bridge translates tasks, but then handles only a small local intent set instead of sending the wider task surface into the broker's routing path.

### 2. Offline communication is real

The codebase already supports a meaningful "electricity only" mode for local operation:

- Local HTTP control plane over `127.0.0.1`.
- Mesh routing with BRP evaluation.
- Trust graph support for peer scoring.
- ProjectX mesh health monitoring.
- Quantum backends defaulting to local simulators.

Important boundary:

- This supports operation without internet.
- It still depends on local networking and power.
- Cloud services remain optional but not offline-safe by default.

### 3. Graphify is real, but not a runtime accelerator

Graphify is not fake or abandoned:

- The Graphify repo is installed locally.
- The `.graphify/` outputs are fresh.
- Obsidian + Graphify sync has succeeded.
- Agent helper and graph navigation tooling exist.

But Graphify is not currently part of the broker or ProjectX critical path:

- No evidence shows the broker consulting Graphify before routing.
- No evidence shows ProjectX guard consulting Graphify before analysis or execution.
- Today it behaves as an architecture knowledge asset and helper toolkit.

That means the "3D map around the system" idea is only partially true.

What is true:

- It gives a large architecture graph and can help humans/agents navigate the repo.

What is not true today:

- It does not automatically reduce routing latency.
- It does not automatically increase throughput.
- It is not acting as a live spatial runtime map used by all agents.
- It is not currently giving agents a live 3D runtime map around the system.

### 4. Quantum surface is broad, but not the default operator workflow

The codebase already includes:

- A production quantum agent wrapper.
- A multi-backend quantum backend manager.
- IBM Quantum and PennyLane adapter surfaces.
- Local simulator and Qiskit Aer defaults.
- Quantum-enhanced arbitrage modules.

The current gap is activation and integration:

- These modules do not appear to be the default path for ProjectX guard or broker operations.
- Real hardware integrations remain opt-in and usually cloud-dependent.
- Local simulation is available immediately, but operator-facing workflows do not prioritize it.

## Highest-Value Integration Moves

### Promote the A2A-first ProjectX path

This is the fastest way to get more out of what already exists for agentic HTTP/HTTPS.

Before doing that, unify the ProjectX broker port defaults so the same local broker
address is used by registration, bridge routing, and mesh monitoring.

Primary files:

- `projectx_guard_server.py`
- `projectx_guard_server_enhanced.py`
- `projectx_simp_bridge.py`

### Treat mesh as the offline backbone and HTTP as the control plane

You already have both transports. The next step is making that dual-path strategy
explicit and operator-visible rather than leaving it implicit in separate modules.

Primary files:

- `projectx_mesh_integration.py`
- `simp/server/mesh_routing.py`
- `simp/server/broker.py`

### Start using Graphify as a pre-read oracle

Graphify should help before deep scans, not only after documentation generation.

Primary files:

- `.graphify/simp_graph.json`
- `.graphify/agent_helper.py`
- `tools/graph_navigator.py`

### Bridge quantum surfaces into operator-facing intents

The quantum stack should become a callable system capability, not just a library surface.

Primary files:

- `simp/organs/quantum_intelligence/production_agent.py`
- `simp/organs/quantum/quantum_adapter.py`
- `simp/agents/quantum_mode_agent.py`

## Git Reality

- `ProjectX` root is not currently a git repository.
- `SIMP` root is a git repository and can be safely used for committed audit/tooling work.

That means:

- We can commit and push audit tooling and SIMP-side integration work now.
- To get the same safety net for `ProjectX`, that directory needs its own repository or to be brought under an existing repo intentionally.
