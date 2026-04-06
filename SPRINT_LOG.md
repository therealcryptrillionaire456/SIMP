# SIMP Sprint Log

## Sprint 26 — A2A Compatibility Layer: Authentication Mapping (Sprint 1)
- Created `simp/compat/auth_map.py`: Maps SIMP auth mechanisms to A2A securitySchemes declarations.
- Created `simp/compat/agent_card.py`: AgentCardGenerator builds A2A-compatible Agent Cards.
- Created `simp/compat/capability_map.py`: Maps SIMP capabilities to A2A AgentSkill declarations.
- Added `/.well-known/agent-card.json` route to `http_server.py`.

## Sprint 27 — A2A Task Translation (Sprint 2)
- Created `simp/compat/task_map.py`: Allowlist-gated A2A-to-SIMP task translation.
- `translate_a2a_to_simp()` maps 10 task types + aliases to CanonicalIntent types.
- `simp_state_to_a2a()` projects all SIMP lifecycle states to A2A states.
- `build_a2a_task_status()` builds structured A2A TaskStatus responses.
- New routes: POST /a2a/tasks, GET /a2a/tasks/<id>, GET /a2a/tasks/types.

## Sprint 28 — Structured Capability Metadata (Sprint 3)
- Created `simp/compat/capability_schema.py`: StructuredCapability dataclass with A2A AgentSkill alignment.
- `normalise_capabilities()` accepts flat strings, dicts, or mixed lists.
- Well-known capability registry enriches 18 known SIMP capability types.

## Sprint 29 — Discovery Cache + Error Taxonomy (Sprint 4)
- Created `simp/compat/discovery_cache.py`: Thread-safe TTL memoisation (60s agent, 300s broker).
- `CompatError` / `CompatErrorCode`: Typed errors with HTTP status hints.
- `validate_agent_card()`: Validates required A2A AgentCard fields.

## Sprint 30 — Lifecycle State Machine + Event Envelopes (Sprint 5)
- Created `simp/compat/lifecycle_map.py`: Exhaustive state mapping from SIMP to A2A.
- `SimpLifecycleState` + `A2ATaskState` enumerations.
- Event envelope builders: `build_progress_event`, `build_completion_event`, `build_failure_event`.
- `events_from_intent_history()` reconstructs task event sequence from broker records.

## Sprint 31 — Policy-Rich Agent Cards (Sprint S1)
- Created `simp/compat/policy_map.py`: Per-agent-type safety policies, security schemes, and requirements.
- Updated `AgentCardGenerator.build_agent_card()` to include securitySchemes, security, safetyPolicies, resourceLimits.
- Updated `build_broker_card()` with transport security info and autonomous operations policy.
- No file paths or secrets ever appear in card output.

## Sprint 32 — ProjectX Maintenance as A2A Capability (Sprint S2)
- Created `simp/compat/projectx_card.py`: Standalone A2A Agent Card for ProjectX native agent.
- 4 read-only maintenance skills: health_check, audit, security_audit, repo_scan.
- Write operations (code_maintenance, provider_repair) explicitly rejected.
- New routes: GET /a2a/agents/projectx/agent.json, POST /a2a/agents/projectx/tasks.

## Sprint 33 — A2A Events & SIMP Telemetry (Sprint S3)
- Created `simp/compat/event_stream.py`: Converts SIMP ledger records to A2A-compatible task events.
- Sensitive fields redacted, error strings truncated to 200 chars.
- New routes: GET /a2a/events, GET /a2a/events/<intent_id>.

## Sprint 34 — Autonomous Operations Policy Model (Sprint S4)
- Created `simp/compat/ops_policy.py`: Type-safe policy document and validation layer.
- OpsPolicy dataclass with spend limits, approval requirements, logging rules.
- SimulatedSpendLedger: Thread-safe, append-only, simulated-only spend tracking.
- All operations require manual approval. spend_mode always "simulation".

## Sprint 35 — A2A Security Hardening (Sprint S5)
- Created `simp/compat/a2a_security.py`: Security scheme declarations, bearer-claim validation, quota checking.
- `validate_bearer_claims()`: Structural JWT claim validator (no crypto — gateway's job).
- `build_replay_guard_note()`: Replay protection posture (planned).
- New route: GET /a2a/security (unauthenticated).

## Sprint 36 — ProjectX Durability & Recovery (Sprint S6)
- Created `simp/compat/projectx_diagnostics.py`: Read-only diagnostic helpers.
- `check_task_ledger_integrity()`: JSONL integrity check with corrupt-line detection.
- `build_projectx_health_report()`: Aggregated health report (never exposes file paths).
- New route: GET /a2a/agents/projectx/health (unauthenticated).

## Sprint 37 — FinancialOps Agent (Simulated) (Sprint S7)
- Created `simp/compat/financial_ops.py`: Simulated-only financial operations agent.
- 3 capabilities: small_purchase, subscription_management, license_renewal.
- All operations recorded as simulated spend. No real payments ever occur.
- New routes: GET /a2a/agents/financial-ops/agent.json, POST /a2a/agents/financial-ops/tasks.

## Sprint 38 — A2A-Aware Dashboard (Sprint S8)
- Created `dashboard/server.py`: FastAPI dashboard with A2A status endpoint.
- Created `dashboard/index.html`: Collapsible A2A Compatibility panel.
- GET /dashboard/a2a/status returns agent list, enforcement status, quota info.

## Sprint 39 — End-to-End A2A Demo (Sprint S9)
- Created `examples/a2a_demo.py`: Reference A2A client demonstrating full flow.
- Created `docs/A2A_DEMO.md`: Architecture overview, flow diagram, security posture summary.
- Flow: Discover -> Plan -> Maintain -> Simulate Financial Op -> Query Events.

## Sprint 41 — Payment Connector Framework
- Created `simp/compat/payment_connector.py`: PaymentConnector ABC with StubPaymentConnector.
- PaymentConnectorConfig, PaymentResult dataclasses.
- ALLOWED_CONNECTORS allowlist (stripe_small_payments, internal_corp_card_proxy).
- ALLOWED_VENDOR_CATEGORIES, DISALLOWED_PAYMENT_TYPES policy frozensets.
- ConnectorHealthTracker with Gate 1 readiness (7 consecutive OK days).
- build_connector(), validate_payment_request() factory and validation.

## Sprint 42 — Dry-Run Enrichment & Health Tracking
- Extended `simp/compat/ops_policy.py`: Added live payment policy fields to OpsPolicy.
- Added dry_run_result, connector_used, dry_run_reference_id to SpendRecord.
- Added record_with_dry_run() to SimulatedSpendLedger.
- Added get_live_policy_dict() for A2A card serialisation.

## Sprint 43 — Approval Queue & Payment Events
- Created `simp/compat/approval_queue.py`: Append-only JSONL approval queue.
- PaymentProposal state machine: pending -> approved | rejected.
- PolicyChangeQueue with dual-control (two distinct operator approvals).
- Extended `simp/compat/event_stream.py`: Added PAYMENT_EVENT_KINDS frozenset.
- Added build_payment_event() for payment lifecycle A2A events.

## Sprint 44 — Live Execution Pipeline (Feature-Flagged OFF)
- Created `simp/compat/live_ledger.py`: Append-only JSONL live spend ledger.
- Idempotency guard: repeated executions with same proposal_id silently ignored.
- Extended `simp/compat/financial_ops.py`: Added execute_approved_payment().
- 5-gate execution pipeline: feature flag, idempotency, proposal lookup, validation, health.
- FINANCIAL_OPS_LIVE_ENABLED=false by default — no live payments until explicit opt-in.
- Added livePaymentPolicy to financial-ops A2A card x-simp namespace.

## Sprint 45 — Reconciliation, Dashboard & HTTP Routes
- Created `simp/compat/reconciliation.py`: Reconciliation engine comparing live vs simulated ledgers.
- ReconciliationResult with per-vendor breakdowns and discrepancy detection.
- Extended `simp/server/http_server.py`: Added _setup_financial_ops_routes() with 12 new endpoints.
- Routes: connector health, proposals CRUD, approve/reject, execute, policy changes, ledger, export, reconciliation.
- Extended `dashboard/server.py`: Added /dashboard/financial-ops/status, proposals, ledger endpoints.
- Extended `dashboard/index.html`: Added FinancialOps Status, Proposed Payments, Ledger panels.

## Sprint 46 — Rollback System
- Created `simp/compat/rollback.py`: RollbackState (ACTIVE/INACTIVE/NEVER_LIVE), RollbackRecord, RollbackManager.
- JSONL-backed rollback log (append-only). ROLLBACK_MANAGER singleton.
- LedgerFrozenError: LiveSpendLedger.freeze()/unfreeze()/is_frozen() block writes during rollback.
- record_attempt() and record_outcome() raise LedgerFrozenError when frozen.
- execute_approved_payment() checks rollback state before execution.
- Routes: POST /a2a/agents/financial-ops/rollback, GET /rollback/status, GET /rollback/history.
- When FINANCIAL_OPS_LIVE_ENABLED != "true", rollback state is always ACTIVE or NEVER_LIVE.

## Sprint 47 — Graduation Gate Manager
- Created `simp/compat/gate_manager.py`: GateStatus, GateCondition, GateCheckResult, GateManager.
- Two-gate graduation system with automated and manual conditions.
- Gate 1: connector_health_7_days, simulated_payments_20, no_connector_errors (auto), ops_policy_reviewed (manual).
- Gate 2: gate1_signed_off, approval_workflow_tested, live_ledger_validated, reconciliation_run, rollback_system_operational (auto), security_review_signed_off, pilot_limits_set (manual).
- sign_off_gate raises ValueError when automated conditions not met.
- Routes: GET /gates, GET /gates/1, GET /gates/2, POST /gates/1/sign-off, POST /gates/2/sign-off, POST /gates/1/promote, POST /gates/2/promote.

## Sprint 48 — Stripe Test Connector
- Created `simp/compat/stripe_connector.py`: StripeTestConnector(PaymentConnector) using stdlib urllib only.
- Enforces sk_test_ key prefix. NEVER logs full key (only last 4 chars).
- health_check() GET /v1/account. authorize() POST /v1/payment_intents with confirm=false.
- execute_small_payment() and refund() raise RuntimeError in dry_run mode.
- Updated ALLOWED_CONNECTORS: build_connector() uses StripeTestConnector when STRIPE_TEST_SECRET_KEY set, falls back to StubPaymentConnector.

## Sprint 49 — Budget Monitor
- Created `simp/compat/budget_monitor.py`: AlertSeverity, BudgetAlert, BudgetMonitor.
- WARNING at >=75% of limit, CRITICAL at >=100%. Anomaly detection (>2x historical avg).
- BUDGET_MONITOR singleton. CRITICAL task/daily alerts block execute_approved_payment().
- Routes: GET /a2a/agents/financial-ops/budget (public), GET /alerts (auth), POST /alerts/<id>/acknowledge (auth).

## Sprint 50 — Hardening & Release v0.6.0
- Created `tests/test_financial_ops_contracts.py`: 20 invariant/contract tests.
- Ledger append-only, no secrets in cards, idempotency, rollback, gate, A2A card shape.
- Updated `simp/compat/__init__.py`: Exported Sprint 46-49 symbols.
- Bumped _SIMP_VERSION to "0.6.0" in `simp/compat/agent_card.py`.
- Created `docs/FINANCIAL_OPS.md`: 10-section operator guide.
