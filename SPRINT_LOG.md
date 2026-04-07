# SIMP Sprint Log

## Sprint 66 — Crypto Hardening
**Date**: 2026-04-07
**Files changed**: `simp/crypto.py`
**Tests**: `tests/test_sprint66_crypto.py` (15 tests)

**Changes**:
- Added `sign_intent_v2()`: signs without pre-hash (Ed25519 hashes internally), adds `_sig_nonce`, `_sig_exp`, `_sig_iat`, `_sig_kid` security metadata
- Added `verify_signature_v2()`: verifies v2 signatures, checks expiry
- Added `verify_signature_strict()`: full verification with nonce replay detection, key ID matching via `hmac.compare_digest`
- Added `_key_fingerprint()`: SHA-256 fingerprint of public key
- Legacy `sign_intent()` and `verify_signature()` preserved unchanged for backward compatibility

---

## Sprint 67 — Key Storage & Agent Manager Hardening
**Date**: 2026-04-07
**Files changed**: `simp/crypto.py`, `simp/server/agent_manager.py`
**Tests**: `tests/test_sprint67_key_mgmt.py` (11 tests)

**Changes**:
- `private_key_to_pem()` now uses `BestAvailableEncryption` when `SIMP_KEY_PASSPHRASE` env var is set; warns if unset
- `load_private_key()` reads passphrase from env var
- Added `sanitize_agent_id()` validator (1-128 chars, alphanumeric start, restricted charset)
- Replaced predictable `/tmp/simp_agent_{id}_{port}.py` with `tempfile.NamedTemporaryFile`
- Replaced `repr(args)` string injection with JSON temp file approach
- Script files cleaned up after process exits

---

## Sprint 68 — Broker Hardening
**Date**: 2026-04-07
**Files changed**: `simp/server/broker.py`, `simp/server/agent_client.py`, `simp/server/http_server.py`
**Tests**: `tests/test_sprint68_broker_hardening.py` (9 tests)

**Changes**:
- `intent_records` changed from `Dict` to `OrderedDict` with LRU eviction via `_add_intent_record()`
- Added `max_intent_records` config (default 10,000) to `BrokerConfig`
- Agent client: added length-prefixed message framing (4-byte big-endian header)
- Added `_recv_exact()` for reliable socket reads
- Added `_MAX_MESSAGE_SIZE` (16 MB) limit
- Fixed event loop thread safety: `asyncio.run()` per-call instead of shared loop

---

## Sprint 69 — Input Validation
**Date**: 2026-04-07
**Files changed**: `simp/server/validation.py`, `simp/server/http_server.py`
**Tests**: `tests/test_sprint69_validation.py` (15 tests)

**Changes**:
- Fixed broken timestamp regex (`\d{m}` / `\d{d}`) with `datetime.fromisoformat()` validator
- Added `AgentRegistrationRequest` Pydantic model (field limits, pattern validation)
- Added `IntentRouteRequest` Pydantic model (field limits, timestamp validation)
- Wired validation into POST `/agents/register` and POST `/intents/route` — returns 400 on error
- Added `before_request` hook: rejects POST/PUT without `application/json` Content-Type (415)

---

## Sprint 70 — Security Headers & Audit Log
**Date**: 2026-04-07
**Files changed**: `simp/server/http_server.py`, `simp/server/security_audit.py` (new)
**Tests**: `tests/test_sprint70_security_headers.py` (20 tests)
**Docs**: `docs/SECURITY_CHECKLIST.md` (new)

**Changes**:
- Added `after_request` hook with security headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Content-Security-Policy, Cache-Control
- Strips Server and X-Powered-By headers
- Created `SecurityAuditLog` class: append-only JSONL, automatic sensitive field redaction
- Audit hooks: agent_registered, agent_deregistered, validation_error, intent_rejected
- Added GET `/security/audit-log` endpoint with severity/event_type filters
- Created `docs/SECURITY_CHECKLIST.md` documenting security posture
