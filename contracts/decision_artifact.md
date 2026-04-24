# Canonical Decision Artifact

This is the one object every live trade must reference. A3 owns the schema; A2 enforces that execution references it; A9 enforces that every fill has one.

## JSON Schema (authoritative)
```json
{
  "$id": "simp/decision.v1",
  "type": "object",
  "required": [
    "decision_id", "created_at", "source_signal_ids", "thesis",
    "confidence", "risk_budget_usd", "venue", "instrument",
    "side", "size", "expected_edge_bps", "policy_result", "mode"
  ],
  "properties": {
    "decision_id":          { "type": "string", "pattern": "^dec_[0-9a-f]{16}$" },
    "created_at":           { "type": "string", "format": "date-time" },
    "source_signal_ids":    { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "thesis":               { "type": "string", "maxLength": 512 },
    "confidence":           { "type": "number", "minimum": 0, "maximum": 1 },
    "risk_budget_usd":      { "type": "number", "minimum": 0 },
    "venue":                { "type": "string", "enum": ["coinbase","kalshi","alpaca","solana","paper"] },
    "instrument":           { "type": "string" },
    "side":                 { "type": "string", "enum": ["buy","sell","long","short"] },
    "size":                 { "type": "number", "exclusiveMinimum": 0 },
    "expected_edge_bps":    { "type": "number" },
    "policy_result":        {
      "type": "object",
      "required": ["status", "evaluated_at"],
      "properties": {
        "status":       { "type": "string", "enum": ["allow","block","shadow"] },
        "reasons":      { "type": "array", "items": { "type": "string" } },
        "evaluated_at": { "type": "string", "format": "date-time" }
      }
    },
    "mode":                 { "type": "string", "enum": ["fully_live","shadow","halt"] },
    "lineage": {
      "type": "object",
      "properties": {
        "scorer":     { "type": "string" },
        "planner":    { "type": "string" },
        "broker_intent_id": { "type": "string" }
      }
    }
  }
}
```

## Contract points
- **Execution MUST reference** `decision_id`. Execution layer receives the full artifact, not a shorthand.
- **`policy_result.status = block`** → execution layer must record the attempt and refuse to send to venue. This is not an error; it is a terminal state `policy_blocked`.
- **`mode = shadow`** → execution uses paper-fill path even if venue is live. Same lineage, same journal.
- **`mode = halt`** → execution rejects immediately with `halted`.
- **Feedback** — after venue response, A2 writes a feedback record keyed by `decision_id` into `state/decision_journal.ndjson`:
```json
{
  "decision_id": "dec_...",
  "executed_at": "...",
  "fill_status": "executed|policy_blocked|exchange_error|strategy_rejected|stale",
  "fill_price": 12345.67,
  "fill_size": 0.5,
  "slippage_bps": -2.1,
  "latency_ms": 180,
  "venue_ref": "..."
}
```

## Enforcement
- `verify_revenue_path.py` asserts: every execution in the last N minutes has a matching decision AND a matching feedback record.
- A9 runs a lineage-completeness probe every cycle.
- Missing lineage = Sev1.
