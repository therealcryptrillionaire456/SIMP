# SIMP Sprint Log

## Sprint 1 — Hardening & Security Baseline
**Started:** 2026-04-05T17:07:00Z
**Agent:** perplexity_research (discovery & design), claude_cowork (implementation)
**Branch:** feat/public-readonly-dashboard

### Sprint Goal
Establish security and robustness baseline: validate all broker inputs, wire rate limiting into the actual server, fix broken security modules, and add a SPRINT_LOG + COORDINATION_PROTOCOL for future sprints.

---

### Discovery Summary (2026-04-05T17:07:00Z)

**Architecture:**
- SIMP broker (`SimpHttpServer`) runs Flask on port 5555 with 18 routes
- Dashboard (`FastAPI`) on port 8050 proxies GET-only to broker, redacts sensitive data
- 7 agents: 4 HTTP-based (simp_router, kloutbot, perplexity_research, claude_cowork), 3 file-based (bullbear_predictor, kashclaw, quantumarb)
- Memory layer: 5 modules (conversation_archive, task_memory, knowledge_index, session_bootstrap, hooks)
- Task ledger: JSONL-backed, thread-safe, with failure taxonomy and retry policies

**Security Findings:**
| # | Finding | Severity | Location |
|---|---------|----------|----------|
| S1 | **No input validation on broker endpoints** — `/agents/register` accepts any `agent_id` string (no length/charset check), `/intents/route` accepts unbounded JSON payloads | HIGH | `http_server.py` L76-176 |
| S2 | **Existing validation.py has null bytes** — `simp/server/validation.py` contains `\0` in a regex pattern, won't compile | MEDIUM | `validation.py` L17 |
| S3 | **rate_limiter.py is standalone scaffold** — creates its own Flask app, not wired into `SimpHttpServer` | MEDIUM | `security/rate_limiter.py` |
| S4 | **input_validator.py is standalone scaffold** — has `IntentRequest` model but never imported anywhere | LOW | `security/input_validator.py` |
| S5 | **No request size limit** — Flask default allows unbounded request bodies | MEDIUM | `http_server.py` |
| S6 | **`/control/start` and `/control/stop` have no auth** — anyone on the network can stop the broker | HIGH | `http_server.py` L253-268 |
| S7 | **CORS allows all origins on dashboard** — `allow_origins=["*"]` is fine for GET-only but should be tightened eventually | LOW | `dashboard/server.py` L66-71 |
| S8 | **File-based inbox writes to arbitrary paths** — `_deliver_file_based` uses `agent_id` directly in path construction without sanitizing | MEDIUM | `broker.py` L507-527 |

**Robustness Findings:**
| # | Finding | Severity | Location |
|---|---------|----------|----------|
| R1 | **Tests have hardcoded path** — `sys.path.insert(0, '/sessions/...')` in test_protocol_validation.py | LOW | tests/test_protocol_validation.py L15 |
| R2 | **`route_intent()` creates new event loop per call** — potential resource leak under load | MEDIUM | `http_server.py` L170-176 |
| R3 | **No structured error logging** — errors logged as text, not JSON; harder to parse | LOW | broker.py throughout |
| R4 | **`get_logs()` always returns empty list** — stub method never implemented | LOW | broker.py L733-736 |
| R5 | **`list_agents()` returns dict-of-dicts on broker, dashboard expects list** — already partially fixed but fragile | MEDIUM | multiple files |

---

### Sprint 1 Plan

**Target: 3 changes, all additive, no existing behavior modified.**

#### Change 1: Intent & Registration Input Validation
- **What:** Add `sanitize_agent_id()` and `validate_intent_payload()` to a new `simp/server/request_guards.py` module
- **Why:** S1 is the highest-severity gap — any string can be an agent_id (path traversal via file-based inbox) and intent payloads have no size/structure checks
- **Acceptance:** All current tests pass; new tests in `tests/test_request_guards.py` cover edge cases

#### Change 2: Wire Rate Limiting Into HTTP Server
- **What:** Add Flask-Limiter to `SimpHttpServer._setup_routes()` using the limits from the existing `rate_limiter.py` scaffold, then delete the standalone scaffold
- **Why:** S3/S6 — control endpoints and registration are currently unbounded
- **Acceptance:** Rate-limited responses return 429 with proper error JSON

#### Change 3: Fix Broken validation.py + Add SPRINT_LOG.md
- **What:** Rewrite `simp/server/validation.py` to fix null byte, use the Pydantic models from `input_validator.py`, and add this SPRINT_LOG.md
- **Why:** S2 — broken file in the repo is confusing; S4 — consolidate validation into one place
- **Acceptance:** `python3 -m py_compile` passes for all files; SPRINT_LOG.md exists

---

### Design Details

#### Change 1: request_guards.py

```python
# simp/server/request_guards.py
"""Request validation guards for SIMP HTTP server."""
import re
from typing import Any, Dict, Optional, Tuple

# Constraints
MAX_AGENT_ID_LENGTH = 64
MAX_PAYLOAD_SIZE = 65536  # 64KB
AGENT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-:.]+$')
MAX_INTENT_PARAMS_DEPTH = 5

def sanitize_agent_id(agent_id: str) -> Tuple[bool, Optional[str]]:
    """Validate agent_id is safe for use in file paths and routing."""
    if not agent_id or len(agent_id) > MAX_AGENT_ID_LENGTH:
        return False, "agent_id must be 1-64 characters"
    if not AGENT_ID_PATTERN.match(agent_id):
        return False, "agent_id may only contain alphanumeric, underscore, hyphen, colon, dot"
    if ".." in agent_id or "/" in agent_id:
        return False, "agent_id contains path traversal characters"
    return True, None

def validate_intent_payload(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate an intent payload has required fields and acceptable size."""
    # ...
```

**Files touched:** NEW `simp/server/request_guards.py`, NEW `tests/test_request_guards.py`
**Files modified:** `simp/server/http_server.py` (add guard calls at top of each route handler)
**Rollback:** Delete request_guards.py, revert http_server.py import+calls

#### Change 2: Rate Limiting

Wire `flask-limiter` into `SimpHttpServer.__init__()`. Apply per-endpoint limits:
- `/intents/route`: 60/minute
- `/agents/register`: 10/minute
- `/control/*`: 5/minute
- Everything else: 120/minute

**Files touched:** `simp/server/http_server.py` (add Limiter init + decorators)
**Files removed:** `simp/security/rate_limiter.py` (standalone scaffold, replaced)
**Rollback:** Remove Limiter init + decorators from http_server.py, restore rate_limiter.py

#### Change 3: Fix validation.py

Replace null-byte regex with proper ISO 8601 pattern. Consolidate with input_validator.py models.

**Files touched:** `simp/server/validation.py` (rewrite)
**Rollback:** `git checkout -- simp/server/validation.py`

---

### Sprint 1 Results (2026-04-05T17:14:00Z)

**Commit:** `62d9df3` — pushed to `feat/public-readonly-dashboard`

**Completed:**
- [x] Change 1: `simp/server/request_guards.py` — 4 guard functions (sanitize_agent_id, validate_endpoint, validate_intent_payload, validate_registration_payload), wired into all relevant http_server.py handlers
- [x] Change 3: `simp/server/validation.py` — null-byte regex replaced with proper ISO 8601 pattern, Pydantic models updated to v2 syntax
- [x] `tests/test_request_guards.py` — 26 tests, all passing
- [x] `tests/test_protocol_validation.py` — hardcoded sys.path removed
- [x] `COORDINATION_PROTOCOL.md` — agent registry and protocol documentation

**Deferred:**
- [ ] Change 2: Rate limiting — deferred to Sprint 2 (requires flask-limiter dependency, not yet in requirements)

**Pre-existing test failures (NOT regressions):**
- `test_intent_status_tracking` — calls `record_response` on intent never routed (expects `get_intent_status` to find it)
- `test_response_schema_validation` — same root cause, `record_response` returns False for unknown intents

**Remaining findings for future sprints:**
- S3: Wire rate limiting (Sprint 2)
- S5: Add Flask `MAX_CONTENT_LENGTH` (Sprint 2)
- S6: Add auth token to `/control/*` endpoints (Sprint 2)
- S8: Sanitize `agent_id` in `_deliver_file_based` using `request_guards.sanitize_agent_id` — now possible since guards exist (Sprint 2)
- R2: Refactor `route_intent()` event loop creation (Sprint 3)
- R3: Structured JSON logging (Sprint 3)
- R4: Implement `get_logs()` (Sprint 3)

---

## Sprint 2 — Rate Limiting, Auth, & Path Safety
**Started:** 2026-04-05T17:22:00Z
**Agent:** perplexity_research (discovery & design), claude_cowork (implementation)
**Branch:** feat/public-readonly-dashboard

### Sprint Goal
Close all remaining HIGH/MEDIUM security findings from Sprint 1: rate limiting, request size caps, control endpoint authentication, and file-based inbox path sanitization.

---

### Sprint 2 Plan

| # | Change | Addresses | Status |
|---|--------|-----------|--------|
| 1 | Lightweight token-bucket rate limiter (no external deps) | S3 | Done |
| 2 | `MAX_CONTENT_LENGTH = 64KB` on Flask app | S5 | Done |
| 3 | Bearer token auth on `/control/*` and `DELETE /agents/<id>` | S6 | Done |
| 4 | Path traversal guard in `_deliver_file_based()` | S8 | Done |
| 5 | Delete old `simp/security/rate_limiter.py` scaffold | S3 cleanup | Done |

### Rate Limits Applied

| Endpoint | Limit |
|----------|-------|
| `/agents/register` | 10/min |
| `/intents/route` | 60/min |
| `/intents/<id>/response` | 60/min |
| `/intents/<id>/error` | 60/min |
| `/control/start` | 5/min |
| `/control/stop` | 5/min |
| `/memory/conversations` POST | 30/min |

### Sprint 2 Results (2026-04-05T17:22:00Z)

**Commit:** `0832e78` — pushed to `feat/public-readonly-dashboard`

**Completed:**
- [x] NEW `simp/server/rate_limit.py` — `TokenBucket` + `RateLimiter` classes, thread-safe, zero external deps
- [x] NEW `simp/server/control_auth.py` — `require_control_auth` decorator, opt-in via `SIMP_CONTROL_TOKEN` env var (backward compatible when unset)
- [x] WIRED rate limits into 7 POST endpoints in `http_server.py`
- [x] WIRED `@require_control_auth` onto `/control/start`, `/control/stop`, `DELETE /agents/<id>`
- [x] SET `MAX_CONTENT_LENGTH = 64KB` in Flask config
- [x] ADDED `sanitize_agent_id()` + path resolve check to `broker._deliver_file_based()`
- [x] DELETED `simp/security/rate_limiter.py` (replaced by `simp/server/rate_limit.py`)
- [x] NEW `tests/test_sprint2_hardening.py` — 10 tests (token bucket, refill, thread safety, cleanup, auth, path safety)

**Test Results:**
- `test_sprint2_hardening.py`: 10/10 passed
- `test_request_guards.py`: 26/26 passed
- `test_protocol_validation.py`: 15/17 passed (same 2 pre-existing failures)

**Security findings status after Sprint 2:**
| # | Finding | Status |
|---|---------|--------|
| S1 | No input validation | **CLOSED** (Sprint 1) |
| S2 | Broken validation.py | **CLOSED** (Sprint 1) |
| S3 | Rate limiter not wired | **CLOSED** (Sprint 2) |
| S4 | input_validator.py scaffold | LOW — still exists, non-blocking |
| S5 | No request size limit | **CLOSED** (Sprint 2) |
| S6 | Control endpoints unauthed | **CLOSED** (Sprint 2) |
| S7 | CORS `*` on dashboard | LOW — acceptable for GET-only |
| S8 | Inbox path traversal | **CLOSED** (Sprint 2) |

**Remaining for Sprint 3:**
- R2: Refactor `route_intent()` event loop creation (resource leak under load)
- R3: Structured JSON logging for machine-parseable error tracking
- R4: Implement `get_logs()` (currently returns empty list)
- R5: Harden agent list format consistency between broker and dashboard
- Fix 2 pre-existing test failures (`test_intent_status_tracking`, `test_response_schema_validation`)

---

## Sprint 3 — Robustness & Observability
**Started:** 2026-04-05T17:42:00Z
**Agent:** perplexity_research (task authoring & design), claude_cowork (implementation)
**Branch:** feat/public-readonly-dashboard

### Sprint Goal
Close remaining robustness findings (R2-R5), fix pre-existing test failures, and adopt formal task protocol with SPRINT<NN>-KP-<NNN> IDs.

---

## Task SPRINT03-KP-001
- Title: Refactor route_intent() event loop to reuse a single loop
- Author: perplexity_research
- Owner: claude_cowork
- Status: DONE
- Related Files: [simp/server/http_server.py]
- Created At: 2026-04-05T17:42:00Z
- Last Updated: 2026-04-05T18:00:00Z
- Description:
  The `/intents/route` handler in `http_server.py` (lines 203-209) creates a new
  `asyncio.new_event_loop()` on every request and closes it after. Under load this
  causes resource churn and potential event-loop leaks. Refactor to create one event
  loop at server init time (stored as `self._async_loop` + background thread), then
  use `asyncio.run_coroutine_threadsafe()` to submit work to it from Flask handlers.
- Acceptance Criteria:
  - A single asyncio event loop is created in `SimpHttpServer.__init__()` and runs in a daemon thread
  - `route_intent()` handler uses `asyncio.run_coroutine_threadsafe(coro, self._async_loop).result(timeout=30)` instead of creating a new loop
  - Existing tests in `test_protocol_validation.py` still pass (15/17, same 2 pre-existing failures)
  - `python3 -m py_compile simp/server/http_server.py` passes
- Notes:
  - The loop thread should be daemon so it doesn't block shutdown
  - Add `self._async_loop` and `self._loop_thread` to `__init__`
  - The health check loop in `broker.start_health_checks()` already runs its own thread; this is separate
- Outcome: Refactored route_intent() to use a shared asyncio event loop created at init time. The loop runs in a daemon thread (SIMP-AsyncLoop). Handler now uses run_coroutine_threadsafe() with 30s timeout, plus proper TimeoutError and Exception handling returning 504/500 respectively. All compile checks and tests pass.

---

## Task SPRINT03-KP-002
- Title: Add structured JSON logging with ring buffer
- Author: perplexity_research
- Owner: claude_cowork
- Status: DONE
- Related Files: [simp/server/broker.py]
- Created At: 2026-04-05T17:42:00Z
- Last Updated: 2026-04-05T18:00:00Z
- Description:
  Currently all broker logging goes through Python's `logging` module with text format.
  The `get_logs()` method (line 756) is a stub that returns `[]`. Implement a structured
  JSON log ring buffer inside the broker that captures key events (agent registered,
  intent routed, intent failed, response recorded, health change) and serves them
  through `get_logs()`. This also enables the dashboard to show a real event feed.
- Acceptance Criteria:
  - New `_log_event()` method on `SimpBroker` that appends structured events to a `collections.deque` ring buffer (max 500 entries)
  - Each event is a dict with keys: `timestamp`, `event_type`, `agent_id`, `intent_id` (optional), `message`, `level` (info/warning/error)
  - `_log_event()` is called at key points: `register_agent`, `deregister_agent`, `route_intent` (success/fail), `record_response`, `record_error`, `_check_agent_health` (status change)
  - `get_logs(limit)` returns the most recent `limit` entries from the ring buffer as a list of dicts
  - Existing Python `logging` calls are NOT removed (dual output: text logs + structured buffer)
  - `python3 -m py_compile simp/server/broker.py` passes
  - New test in `tests/test_sprint3_observability.py` verifies `get_logs()` returns events after operations
- Notes:
  - Use `collections.deque(maxlen=500)` for automatic eviction
  - Thread-safe via the existing `self.intent_lock` or a new dedicated `self._log_lock`
  - Do NOT change the existing logging format or remove any existing log lines
- Outcome: Added _log_event() method and deque(maxlen=500) ring buffer with dedicated _event_log_lock. Events logged at 7 key points: agent_registered, agent_deregistered, intent_routed, intent_failed, response_recorded, intent_error, health_change. get_logs() returns most-recent-first with configurable limit (1-500). All existing logging calls preserved. 9 new tests in test_sprint3_observability.py all pass.

---

## Task SPRINT03-KP-003
- Title: Wire get_logs() to HTTP server and dashboard
- Author: perplexity_research
- Owner: claude_cowork
- Status: DONE
- Related Files: [simp/server/http_server.py, dashboard/server.py]
- Created At: 2026-04-05T17:42:00Z
- Last Updated: 2026-04-05T18:00:00Z
- Description:
  Once SPRINT03-KP-002 implements `get_logs()` on the broker, wire it through:
  1. Add `/logs` GET endpoint in `http_server.py` that returns `broker.get_logs(limit)` where limit comes from `?limit=N` query param (default 100, max 500)
  2. Add `/api/logs` GET endpoint in `dashboard/server.py` that proxies to broker `/logs`, redacts sensitive data
  The dashboard frontend already has an activity feed; this gives it real structured data.
- Acceptance Criteria:
  - `GET /logs?limit=50` on broker returns JSON `{"status": "success", "count": N, "logs": [...]}`
  - `GET /api/logs?limit=50` on dashboard returns the same but redacted
  - Both are GET-only (read-safe)
  - `python3 -m py_compile` passes for both files
- Notes:
  - Depends on SPRINT03-KP-002 being done first
  - The dashboard `/api/activity` endpoint already exists and uses a polling-based ring buffer; `/api/logs` is complementary (broker-side structured events vs dashboard-side diff events)
- Outcome: Added GET /logs endpoint on broker (http_server.py) with ?limit query param (default 100, clamped 1-500). Added GET /api/logs on dashboard (server.py) using FastAPI query parameter with _redact() applied. Both compile and are GET-only read-safe.

---

## Task SPRINT03-KP-004
- Title: Fix 2 pre-existing test failures in test_protocol_validation.py
- Author: perplexity_research
- Owner: claude_cowork
- Status: DONE
- Related Files: [tests/test_protocol_validation.py]
- Created At: 2026-04-05T17:42:00Z
- Last Updated: 2026-04-05T18:00:00Z
- Description:
  Two tests have been failing since before Sprint 1:
  1. `test_intent_status_tracking` (line 151): Calls `record_response(intent_id, ...)` on an
     intent_id that was never routed, so `get_intent_status()` returns None.
  2. `test_response_schema_validation` (line 195): Same root cause — calls `record_response("intent:001", ...)`
     without first routing an intent with that ID.
  Fix: update both tests to first route the intent via `broker.route_intent()` (async),
  then call `record_response()`. The target agent must be pre-registered in the fixture.
- Acceptance Criteria:
  - Both tests pass (17/17 total)
  - No changes to broker code — only test code changes
  - `python3 -m py_compile tests/test_protocol_validation.py` passes
- Notes:
  - `test_intent_status_tracking` uses `broker_with_agents` fixture which has vision:001, grok:001, trusty:001
  - `test_response_schema_validation` uses `broker` fixture with no agents — will need to register one first
  - Route intent needs `asyncio.run()` or `loop.run_until_complete()` since tests aren't async
  - The target agents have `localhost:XXXX` endpoints which will fail HTTP delivery, but the intent record will still be created with status "failed" — so `record_response()` should work on that record. Or use a file-based endpoint (empty string) to get "queued_no_endpoint".
- Outcome: Fixed both tests. test_intent_status_tracking now routes intent via loop.run_until_complete() before calling record_response(). test_response_schema_validation now registers a file-based agent and routes an intent first. All 17/17 protocol tests pass.

---
