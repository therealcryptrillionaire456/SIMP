# SIMP Coordination Protocol

## Overview
The SIMP (Simple Inter-agent Messaging Protocol) broker coordinates communication between autonomous agents in the KashClaw ecosystem.

## Agents
| Agent ID | Type | Transport | Port | Capabilities |
|----------|------|-----------|------|-------------|
| bullbear_predictor | prediction | file-based | — | prediction_signal |
| simp_router | router | HTTP | 5555 | routing, coordination |
| kashclaw | execution | file-based | — | trade_signal, trade_execution |
| kloutbot | orchestration | HTTP | 8765 | orchestration_command, coordination, mcp_bridge |
| perplexity_research | research | HTTP | 8766 | research_request, research_finding, market_intelligence |
| quantumarb | arbitrage | HTTP | 5556 | arbitrage_check, arbitrage, cross_venue, latency_arb |
| claude_cowork | builder | HTTP | 8767 | code_task, code_editing, planning, scaffolding |

## Intent Types
- `prediction_signal`: bullbear_predictor → simp_router
- `trade_signal`: kashclaw → kloutbot
- `arbitrage_check`: kloutbot → quantumarb
- `research_request`: kloutbot → perplexity_research
- `research_finding`: perplexity_research → kloutbot
- `system_test`: any → simp_router
- `orchestration_command`: kloutbot → any

## Security Constraints
1. Dashboard (port 8050) is GET-only — no POST/PUT/PATCH/DELETE
2. All agent_ids validated against `[a-zA-Z0-9_\-:.]+` (max 64 chars)
3. Intent payloads limited to 64KB
4. Sensitive keys redacted from dashboard responses
5. No secrets in logs or public responses

## Sprint Process
See SPRINT_LOG.md for the current sprint state and history.
