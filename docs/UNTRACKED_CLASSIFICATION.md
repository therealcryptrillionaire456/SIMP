# Untracked File Classification

Classification date: 2026-04-24

Status update: the relocation and archive pass has now been partially executed. This document still records the original classification decision, but the bucket 2 and 3 files listed below now live under `scripts/bootstrap/`, `scripts/diagnostics/`, `scripts/recovery/`, `scripts/kloutbot/`, `docs/ops/`, `docs/archive/2026-04/`, and `backups/repo_hygiene/archive_data/2026-04/`.

This file classifies the current `git ls-files --others --exclude-standard` set into three buckets:

1. real product code or product assets to keep
2. root-level helper/scratch assets to relocate into `scripts/` or `tools/`
3. historical docs/reports/artifacts to archive out of the repo root

## 1. Keep

These should stay in the repo and be tracked as product code, config, tests, or live docs.

### Product config and deployment

- `.env.example`
- `config/current_trading_config.json`
- `config/kalshi_live_config.json`
- `config/live_production_config.json`
- `config/multi_exchange_live_config.json`
- `config/solana_seeker_config.json`
- `config/trading_hours_test.json`
- `config/universal_exchange_config.json`
- `deployment/projectx/Dockerfile`
- `deployment/projectx/configmap.yaml`
- `deployment/projectx/deployment.yaml`
- `deployment/projectx/hpa.yaml`
- `deployment/projectx/service.yaml`

### Product UI and live docs

- `dashboard/static/trace_compare.html`
- `docs/COMPATIBILITY_PERIMETER.md`
- `docs/REPO_HYGIENE.md`

### Live operational scripts already in the right neighborhood

- `scripts/kalshi_trader.py`
- `scripts/load_env.sh`
- `scripts/quick_test.sh`
- `scripts/quick_universal_test.sh`
- `scripts/repo_hygiene_archive.sh`
- `scripts/run_trader.sh`
- `scripts/setup_multi_exchange.sh`

### Root-level runtime daemons currently wired into startup flows

- `agent_coordination.py`
- `brp_audit_consumer.py`
- `quantum_consensus.py`
- `quantumarb_file_consumer.py`

### Package additions that belong in source control

- `simp/agentic_https.py`
- `simp/brp/__init__.py`
- `simp/brp/detection_benchmark.py`
- `simp/brp/enforcement.py`
- `simp/brp/label_governance.py`
- `simp/brp/quantum_lift_measurement.py`
- `simp/brp/telemetry_ingest.py`
- `simp/compat/projectx_control_plane.py`
- `simp/eval_suite.py`
- `simp/integrations/market_news.py`
- `simp/mcp/__init__.py`
- `simp/mcp/intent_bridge.py`
- `simp/mcp/tool_registry.py`
- `simp/mcp/tool_schema.py`
- `simp/mcp/transport.py`
- `simp/mesh/intent_telemetry.py`
- `simp/native_tools.py`
- `simp/organs/ktc/api/social_store.py`
- `simp/organs/quantumarb/compounding.py`
- `simp/organs/quantumarb/exchange_connectors/coinbase_connector.py`
- `simp/organs/quantumarb/multi_exchange.py`
- `simp/organs/quantumarb/quantum_optimizer.py`
- `simp/post_quantum.py`
- `simp/projectx/agent_spawner.py`
- `simp/projectx/apo_engine.py`
- `simp/projectx/bayesian_optimization.py`
- `simp/projectx/benchmark.py`
- `simp/projectx/cost_tracker.py`
- `simp/projectx/deployment.py`
- `simp/projectx/domain_adapter.py`
- `simp/projectx/evolution_tracker.py`
- `simp/projectx/evolutionary_ai.py`
- `simp/projectx/execution_engine.py`
- `simp/projectx/governance.py`
- `simp/projectx/hardening.py`
- `simp/projectx/intent_adapter.py`
- `simp/projectx/internet.py`
- `simp/projectx/knowledge_distiller.py`
- `simp/projectx/learning_loop.py`
- `simp/projectx/mesh_intelligence.py`
- `simp/projectx/meta_learner.py`
- `simp/projectx/multimodal.py`
- `simp/projectx/orchestrator.py`
- `simp/projectx/parallel_executor.py`
- `simp/projectx/pnl_tracker.py`
- `simp/projectx/rag_memory.py`
- `simp/projectx/resource_monitor.py`
- `simp/projectx/risk_engine.py`
- `simp/projectx/runtime_server.py`
- `simp/projectx/safety_monitor.py`
- `simp/projectx/self_modifier.py`
- `simp/projectx/self_test.py`
- `simp/projectx/skill_engine.py`
- `simp/projectx/subsystems.py`
- `simp/projectx/telemetry.py`
- `simp/projectx/tool_ecology.py`
- `simp/projectx/tool_factory.py`
- `simp/projectx/tool_generator.py`
- `simp/projectx/trace_exporter.py`
- `simp/projectx/validator.py`
- `simp/security/brp/controlled_connector_registry.py`
- `simp/security/brp/delegation_guard.py`
- `simp/security/brp/incident_memory_index.py`
- `simp/security/brp/policy_shadow_trainer.py`
- `simp/security/brp/quantum_advisory_optimizer.py`
- `simp/server/error_taxonomy.py`
- `simp/server/route_contract.py`
- `simp/telemetry/__init__.py`
- `simp/telemetry/path_telemetry.py`
- `simp/transport/noise_wrapper.py`

### Tests that belong in the real test suite

- `tests/test_acceptance_matrix.py`
- `tests/test_agent_registry.py`
- `tests/test_agentic_https_surface.py`
- `tests/test_brp_enforcement.py`
- `tests/test_brp_label_governance.py`
- `tests/test_brp_telemetry_ingest.py`
- `tests/test_coinbase_connector_phase4.py`
- `tests/test_detection_benchmark.py`
- `tests/test_error_taxonomy.py`
- `tests/test_intent_mesh_router.py`
- `tests/test_ktc_frontend_api_contract.py`
- `tests/test_mcp_layer.py`
- `tests/test_mesh_dashboard_truth.py`
- `tests/test_mesh_observability.py`
- `tests/test_operator_visibility.py`
- `tests/test_path_telemetry.py`
- `tests/test_profit_seeker.py`
- `tests/test_projectx_benchmark_history.py`
- `tests/test_projectx_deployment.py`
- `tests/test_projectx_governance.py`
- `tests/test_projectx_knowledge_distiller.py`
- `tests/test_projectx_multimodal_runtime.py`
- `tests/test_projectx_optimization.py`
- `tests/test_projectx_orchestrator.py`
- `tests/test_projectx_runtime_endpoints.py`
- `tests/test_projectx_runtime_server.py`
- `tests/test_projectx_tool_ecology.py`
- `tests/test_projectx_tool_factory.py`
- `tests/test_projectx_tool_generator.py`
- `tests/test_quantum_real_traffic.py`
- `tests/test_route_contract.py`

## 2. Relocate Into `scripts/` Or `tools/`

These are useful operational helpers, one-off diagnostics, or sidecar operator assets. They should not stay in the repo root.
Most of this section has already been relocated into the `scripts/` subtree.

### Operator wrappers and restart helpers

- `DEPLOY_FIXES.sh`
- `FIX_AND_VERIFY.command`
- `RUN_FIXES_NOW.sh`
- `START_THE_MACHINE.command`
- `START_THE_MACHINE.sh`
- `launch_goose.sh`
- `launch_horsemen.sh`
- `manual_fix.sh`
- `fix_projectx_heartbeat.sh`

### Diagnostics, probes, and account checks

- `check_all_balances.py`
- `check_real_balances.py`
- `check_wallet_balances.py`
- `verify_api_connections.py`
- `investigate_kalshi.py`
- `get_trust_scores.py`
- `final_status_check.py`

### QIP and mesh incident fixers

- `debug_qip.py`
- `diagnose_qip_pipeline.py`
- `direct_mesh_fix.py`
- `fix_coinbase_key.py`
- `fix_coinbase_pem.py`
- `fix_line_326.py`
- `fix_mesh_subscribe.py`
- `fix_qip.py`
- `fix_qip_mesh_registration.py`
- `fix_qip_poll.py`
- `fix_qip_registration.py`
- `fix_qip_v2.py`
- `force_qip_mesh_registration.py`
- `patch_broker_mesh_registration.py`
- `patch_qip_mesh.py`
- `simple_fix.py`
- `workaround_qip_mesh.py`

### Root-level ad hoc tests and incident smoke checks

These have now been relocated into `scripts/manual_checks/`.

- `scripts/manual_checks/test_all_apis.py`
- `scripts/manual_checks/test_brp_audit.py`
- `scripts/manual_checks/test_coordination_integration.py`
- `scripts/manual_checks/test_kalshi_full.py`
- `scripts/manual_checks/test_other_apis.py`
- `scripts/manual_checks/test_qip_issue.py`
- `scripts/manual_checks/test_qip_live.py`
- `scripts/manual_checks/test_qip_message.py`
- `scripts/manual_checks/test_qip_processing.py`
- `scripts/manual_checks/test_quantum_consensus.py`
- `scripts/manual_checks/test_remaining_apis.py`

### KLOUTBOT / Goose sidecar assets that should live together

- `AUTONOMOUS_SETUP.md`
- `kloutbot_autonomous.py`
- `kloutbot_bridge.py`
- `kloutbot_bridge_fixed.py`
- `send_kloutbot_instruction.py`
- `load_context.py`
- `goose_kloutbot_profile.json`
- `goose_quantum_profile.json`

### Orphaned root modules that should move under a package or tooling area before tracking

- `projectx_self_repair.py`
- `projectx_world_model.py`

## 3. Archive

These are historical narratives, planning artifacts, or generated records. They should move into an archive area instead of staying at the repo root.
Most of this section has already been archived under `docs/archive/2026-04/` or `backups/repo_hygiene/archive_data/2026-04/`.

### Historical top-level docs and reports

- `HARD_MESH_AUDIT.md`
- `LANGSMITH_INTEGRATION_ANALYSIS.md`
- `MORNING_BRIEF_KASEY.md`
- `NEXT_10_STEPS.md`
- `QUANTUM_PERMEATION_ROADMAP.md`
- `V3SP3R_IMMEDIATE_USAGE_DOSSIER.md`
- `V3SP3R_QUICK_START.md`
- `codex_wire_up_prompt.json`

### Generated historical artifacts under `data/`

- `data/hindsight_report.txt`
- `data/quantum_dataset/traces/signal_signal_ceb5e486.json`
- `data/quantum_dataset/traces/trace_trace_8dc4cd19455a.json`
- `data/quantum_integration_logs/interaction_20260419_152133.json`

## Notes

- Category 1 files can be tracked as-is.
- Category 2 files are not being discarded; they belong in `scripts/`, `tools/`, or a dedicated operator subdirectory before tracking.
- Category 3 files belong in an archive area such as `docs/archive/` or `backups/repo_hygiene/archive_data/`.
- The actual relocation and archive pass has now started; use this document as the rationale for the current layout.
