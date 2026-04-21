# HTTP Delivery Transport

## Status
completed

## Goal
Enable reliable HTTP-based intent delivery between the broker and agents, with health checking and fallback to file-based delivery.

## Current State
Fully implemented. Broker uses httpx for async HTTP delivery with configurable timeouts. Supports health check pinging, automatic fallback to file-based inbox delivery, and retry logic with failure classification.

## Key Decisions
- httpx chosen for async HTTP client (superior to aiohttp for this use case)
- File-based inbox as fallback for agents without HTTP endpoints
- Health check loop runs every 30s in a daemon thread
- Delivery timeout configurable (default 30s)
- Status codes mapped: 200=delivered, 202=queued, 429=rate_limited, 4xx/5xx=failed

## Open Questions
- (none)

## Code Locations
- `simp/server/broker.py` — `_deliver_http()`, `_deliver_file_based()`, `_check_agent_health()`
- `simp/server/agent_http_client.py` — HTTP client for agent-side communication
- `simp/server/agent_server.py` — Agent HTTP server endpoint

## Dependencies
- httpx (optional, graceful degradation if not installed)
- File system for inbox-based delivery (`data/inboxes/`)

## History
- 2025-03-28 — Task created
- 2025-03-29 — Implemented httpx async delivery in broker
- 2025-03-30 — Added health check loop and agent status tracking
- 2025-03-31 — Added file-based inbox delivery fallback
- 2025-04-01 — Completed — all delivery modes working
