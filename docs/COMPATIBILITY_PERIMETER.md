# SIMP Compatibility Perimeter

## Summary
Native surfaces are primary; MCP is a compatibility-only facade.

## Stable First-Class Surfaces

- **`/agentic/*`** — agent invocation, routing, and streaming
- **`/native/tools/*`** — tool listing and invocation

**Guarantees for native surfaces:**
- Stable request/response envelopes
- Documented error codes (see [Error Contract](#error-contract))
- Full telemetry blocks attached to every response
- Backward-compatible schema evolution (additive only)

## Compatibility-Only Perimeter (MCP)

- **`/mcp/*`** — MCP facade that mirrors native behavior but identifies as bridged.

**Guaranteed bridge marker fields:**
| Field | Value |
|---|---|
| `source` | `"native_registry"` |
| `bridge_mode` | `"mcp_compat"` |

**NOT guaranteed:**
- Wire format stability beyond the documented bridge mapping
- JSON-RPC shape parity across MCP spec versions
- Telemetry block structure (may differ from native)

## Envelope Field Guarantees

All responses across every surface carry these fields:

| Field | Description |
|---|---|
| `invocation_mode` | How the call was invoked (`native` or `mcp`) |
| `bridge_mode` | Bridge identity (`direct` or `mcp_compat`) |
| `trace_id` | Unique trace identifier for the request lifecycle |
| `correlation_id` | Correlation identifier linking related requests |
| `source` | Originating registry (`"native_registry"`) |

Native-only fields (not guaranteed on MCP facade):

| Field | Description |
|---|---|
| `delivery_status` | Final delivery disposition |
| `delivery_method` | How the intent was delivered to the target agent |
| `delivery_latency_ms` | End-to-end delivery latency in milliseconds |

## Error Contract

All surfaces share the same canonical error family:

| Error Code | Meaning |
|---|---|
| `INVALID_SIGNATURE` | Request signature failed verification |
| `UNAUTHORIZED` | Authentication or authorization failure |
| `NOT_FOUND` | Agent, tool, or resource not found |
| `INVALID_REQUEST` | Malformed or semantically invalid request |
| `TOOL_INVOCATION_FAILED` | Tool execution raised an error |
| `ROUTE_FAILED` | Intent routing could not resolve a target |
| `STREAM_UNAVAILABLE` | Streaming not available for the requested surface |

Error responses always include `error_code`, `message`, and `trace_id`.

## Compatibility Guarantees

- The MCP facade **will not break** existing callers during this phase.
- Changes to the MCP facade will be **additive only** — no removal or renaming of existing fields.
- Future deprecation of the MCP facade will follow a **documented timeline** published at least one full release cycle in advance.

## Migration Note for Internal Callers

**Prefer native surfaces** (`/agentic/*`, `/native/tools/*`) for all internal agent communication. Use the MCP facade only when integrating tools or agents from **non-SIMP ecosystems** (e.g., third-party MCP clients, external agent frameworks).

### When to use native surfaces
- All new agent-to-agent communication
- Internal tool invocation
- Workflows where SIMP owns both ends

### When to use MCP compatibility
- Integrating tools from non-SIMP ecosystems
- Third-party agent interop
- Legacy callers that haven't migrated

### Migration path
1. Identify MCP-dependent internal callers
2. Switch each to the corresponding `/native/tools/*` surface
3. Verify identical behavior with the acceptance test suite
4. Mark the MCP caller as migrated
