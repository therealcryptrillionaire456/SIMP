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
