# BRP Event Schema Contract

## Overview

The Bill Russell Protocol (BRP) defines four core data models used for security supervision, policy gating, and audit logging across the SIMP agent network.

## Models

### BRPEvent (`brp.event.v1`)

Pre-action event submitted for evaluation before a material action.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| schema_version | str | `brp.event.v1` | Schema identifier |
| event_id | str | uuid4 | Unique event identifier |
| timestamp | str | ISO 8601 UTC | When the event was created |
| source_agent | str | `""` | ID of the emitting agent |
| event_type | str | `generic` | Category (see BRPEventType enum) |
| action | str | `""` | The specific action being evaluated |
| params | dict | `{}` | Action parameters |
| context | dict | `{}` | Additional context |
| mode | str | `shadow` | BRP evaluation mode |
| tags | list[str] | `[]` | Metadata tags |

### BRPPlan (`brp.plan.v1`)

Multi-step plan submitted for review before release by the orchestrator.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| schema_version | str | `brp.plan.v1` | Schema identifier |
| plan_id | str | uuid4 | Unique plan identifier |
| timestamp | str | ISO 8601 UTC | When the plan was created |
| source_agent | str | `""` | ID of the planning agent |
| steps | list[dict] | `[]` | Plan steps, each with at least `action` key |
| context | dict | `{}` | Additional context |
| mode | str | `shadow` | BRP evaluation mode |
| tags | list[str] | `[]` | Metadata tags |

### BRPObservation (`brp.observation.v1`)

Post-action observation submitted after execution completes or fails.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| schema_version | str | `brp.observation.v1` | Schema identifier |
| observation_id | str | uuid4 | Unique observation identifier |
| timestamp | str | ISO 8601 UTC | When observed |
| source_agent | str | `""` | ID of the observing agent |
| event_id | str | `""` | Correlates to pre-action BRPEvent |
| action | str | `""` | The action that was executed |
| outcome | str | `""` | `success`, `failure`, or `partial` |
| result_data | dict | `{}` | Execution results |
| context | dict | `{}` | Additional context |
| mode | str | `shadow` | BRP mode at time of observation |
| tags | list[str] | `[]` | Metadata tags |

### BRPResponse

Evaluation result returned by the BRP bridge.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| response_id | str | uuid4 | Unique response identifier |
| event_id | str | `""` | Correlates to BRPEvent or BRPPlan |
| decision | str | `SHADOW_ALLOW` | See Decisions below |
| mode | str | `shadow` | BRP mode used for evaluation |
| severity | str | `info` | Threat severity level |
| threat_score | float | `0.0` | 0.0 (safe) to 1.0 (critical) |
| confidence | float | `1.0` | Confidence in the assessment |
| threat_tags | list[str] | `[]` | Tags describing threat indicators |
| summary | str | `""` | Human-readable summary |
| timestamp | str | ISO 8601 UTC | When evaluated |
| metadata | dict | `{}` | Additional metadata |

## Enums

### BRPDecision
- `ALLOW` - Action permitted
- `DENY` - Action blocked (enforced mode only)
- `ELEVATE` - Requires elevated review
- `LOG_ONLY` - Logged, no action taken
- `SHADOW_ALLOW` - Allowed in shadow mode (default)

### BRPMode
- `enforced` - Actively blocks restricted actions
- `advisory` - Enriches responses, elevates high threats, never blocks
- `shadow` - Records everything, never blocks (default)
- `disabled` - LOG_ONLY for all events

### BRPSeverity
- `critical` (threat >= 0.8)
- `high` (threat >= 0.6)
- `medium` (threat >= 0.4)
- `low` (threat >= 0.2)
- `info` (threat < 0.2)

### BRPEventType
- `trade_execution`
- `plan_review`
- `withdrawal`
- `admin_action`
- `arbitrage`
- `observation`
- `generic`

## Restricted Actions

These actions trigger threat_score >= 0.8 and ELEVATE/DENY in enforced mode:
- `withdrawal`
- `admin_delete`
- `key_rotation`
- `fund_transfer`
- `permission_escalation`
- `contract_deploy`

## JSONL Persistence

All records are persisted to `data/brp/`:
- `events.jsonl` - Pre-action events
- `plans.jsonl` - Plan reviews
- `observations.jsonl` - Post-action observations
- `responses.jsonl` - BRP evaluation responses
