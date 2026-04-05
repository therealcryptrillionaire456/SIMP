# Monitoring Dashboard

## Status
active

## Goal
Provide a real-time, read-only monitoring dashboard for the SIMP broker that is safe for public exposure.

## Current State
Built and functional. FastAPI backend proxies broker endpoints with sensitive data redaction. Vanilla JS frontend with dark theme, auto-refresh every 5 seconds. Runs on port 8050.

## Key Decisions
- FastAPI chosen over Flask for async support and automatic OpenAPI docs
- Vanilla JS with no build tools — keeps deployment simple
- All endpoints GET-only for public safety
- Sensitive data (API keys, endpoints, tokens) redacted before exposure
- CORS restricted to GET methods only
- Activity feed uses in-memory ring buffer + JSONL persistence

## Open Questions
- (none yet)

## Code Locations
- `dashboard/server.py` — FastAPI backend with broker proxy
- `dashboard/static/app.js` — Frontend logic (vanilla JS)
- `dashboard/static/index.html` — Dashboard HTML structure
- `dashboard/static/style.css` — Dark theme styling

## Dependencies
- FastAPI + uvicorn
- httpx (for async broker proxying)
- SIMP broker running on port 5555

## History
- 2025-04-01 — Task created
- 2025-04-02 — Built FastAPI backend with all proxy endpoints
- 2025-04-02 — Built vanilla JS frontend with dark theme
- 2025-04-03 — Added activity feed with JSONL persistence
- 2025-04-03 — Added task queue, failure stats, routing policy views
- 2025-04-04 — Added delivery status tracking and topology view
- 2025-04-05 — Added memory section to dashboard
