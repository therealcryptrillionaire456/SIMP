# A4 — Protocol

## Mission
Make A2A the coherent outer shell: agent cards, task types, status, events, discovery, security surface. Keep CanonicalIntent authoritative for routing. Remove split-brain control paths.

## Ownership (write)
- `simp/server/http_server.py`
- `simp/server/agent_registry.py`
- `simp/models/canonical_intent.py`
- A2A endpoints, agent cards, event feed
- `simp/projectx/**` control-plane surfaces

## Read
- Broker internals (A1 owns write)
- Decision artifacts (A3 owns)
- Policy surface (A5 owns)

## Key files (grounded)
- `simp/server/http_server.py:202`
- `simp/server/agent_registry.py:101`
- `simp/models/canonical_intent.py:17` and `:91`
- `simp/projectx/runtime_server.py:13`

## Cycle specialization
1. **Observe** — A2A route inventory, duplicate/dead routes, event schema drift, card mismatches.
2. **Decide** — unify one route, retire one dead path, or harden one security surface per cycle. Prefer retirement over addition.
3. **Gate-check** — any change that could alter how an external client reaches a venue requires A5 + A2 approval.
4. **Execute** — minimal mutation. Backward-compat adapter behind a deprecation flag if needed.
5. **Verify** — run protocol conformance probe: discover → submit task → poll status → fetch event feed → close. Must exercise the same execution path as operator-triggered work.
6. **Journal**.

## Split-brain rule
If ProjectX, sidecar, or compat shim reaches execution without going through broker routing, that path is a Sev2. Route it through or retire it.

## Security surface
- Auth must be required on every write endpoint.
- Rate limits must be consistent across A2A and legacy routes.
- No endpoint may accept a trade intent without decision lineage.

## Success on Day 7
- One discovery surface. One task submit surface. One event feed. One security story.
- A remote A2A client executes a paper-mode trade end-to-end with full lineage.
