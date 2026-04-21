# SIMP Security Model

This document describes the security architecture added in v0.2, covering all 20 issues identified in the security audit.

---

## 1. Authentication

### HTTP API Keys (issues #10, #13)
All state-modifying endpoints (`/intents/route`, `/control/start`, `/control/stop`, `/agents/register`, `/agents/<id>` DELETE, response/error recording) require a valid API key.

**Supplying the key:**
```
Authorization: Bearer <your-api-key>
# or
X-SIMP-API-Key: <your-api-key>
```

**Configuration:**
```bash
SIMP_REQUIRE_API_KEY=true
SIMP_API_KEYS=key1,key2,key3   # comma-separated; rotate without restart
```

**Rotating keys:** add new key to `SIMP_API_KEYS`, confirm clients are updated, then remove the old key. No restart needed (keys are re-read per request via the env var).

**Dev / local mode:** set `SIMP_REQUIRE_API_KEY=false` to disable auth entirely. Never do this in production.

---

## 2. Cryptographic Intent Signatures (issues #2)

SIMP optionally enforces ed25519 signatures on all inter-agent intents.

**Enable:**
```bash
SIMP_REQUIRE_SIGNATURES=true
```

**How it works:**
1. Each agent generates a key pair at startup.
2. The public key is submitted to the broker at registration time via the `public_key` field.
3. The broker stores public keys in a **secrets store separate from public metadata** — they are never logged or returned by `/agents`.
4. When an intent arrives, the broker verifies the `signature` field against the source agent's registered public key.
5. Intents with missing, invalid, or unverifiable signatures are rejected with a structured error response and an audit log entry.

**Error codes:**
| Code | Meaning |
|---|---|
| `MISSING_SOURCE_AGENT` | No `source_agent` field in intent |
| `UNKNOWN_AGENT` | Source agent not registered |
| `NO_PUBLIC_KEY` | Agent registered without a public key |
| `MISSING_SIGNATURE` | `signature` field absent |
| `SIGNATURE_VERIFICATION_FAILED` | Signature is invalid |
| `CRYPTO_UNAVAILABLE` | `simp.crypto` module not installed |

---

## 3. Transport Security / TLS (issue #8)

Enable TLS for the agent-to-broker socket connection:

```bash
SIMP_ENABLE_TLS=true
SIMP_TLS_CERT=/etc/simp/certs/client.crt   # mTLS client cert (optional)
SIMP_TLS_KEY=/etc/simp/certs/client.key
SIMP_TLS_CA=/etc/simp/certs/ca.crt         # CA bundle for server verification
```

When `SIMP_ENABLE_TLS=false` (default), plain TCP is used. Hostname verification and certificate validation are always on when TLS is enabled.

**Self-signed cert for development:**
```bash
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt \
  -days 365 -nodes -subj '/CN=localhost'
```

---

## 4. Rate Limiting (issue #4)

A pure-Python sliding-window rate limiter protects all HTTP endpoints:

```bash
SIMP_RATE_LIMIT_ROUTE=60 per minute   # /intents/route
SIMP_MAX_PENDING_INTENTS=1000         # queue overflow returns 429
```

Clients that exceed the limit receive `HTTP 429` with `error_code: RATE_LIMITED`.

---

## 5. Input Validation (issue #5)

All intent payloads are validated via a Pydantic schema (`simp/models/intent_schema.py`):

- `intent_id`: alphanumeric + `_-.:/`, 1–256 chars
- `source_agent`, `target_agent`: same pattern, 1–128 chars
- `intent_type`: 1–128 chars
- `params`: serialized size ≤ `SIMP_MAX_PAYLOAD_BYTES` (default 1 MB)
- Extra/unknown fields are rejected (`extra="forbid"`)

Validation errors return `HTTP 400` with a detailed `message` field.

---

## 6. Agent Secrets Storage (issue #3)

Sensitive agent data (public keys, tokens) is stored in a **separate in-memory dict** (`_secrets`) from public metadata (`agents`). The `_secrets` dict:

- Is **never returned** by `list_agents()` or `get_agent()`
- Is **never logged** (not even at DEBUG level)
- Holds only what is needed for signature verification

For production deployments requiring secret persistence, inject secrets at runtime via environment variables or an external secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.).

---

## 7. Logging Obfuscation (issue #14)

All IP addresses and agent endpoints are obfuscated in log output:

- IPv4: `192.168.1.42` → `***.***.***.42`
- Tokens: only first 4 chars shown
- Agent IDs longer than 40 chars are truncated with a hash suffix

Set `SIMP_OBFUSCATE_IPS=false` to disable obfuscation in development.

---

## 8. Code Injection Prevention (issues #1, #12)

`agent_manager.py` previously built Python scripts via f-string interpolation of user-supplied `args`. v0.2 fixes this by:

1. **Validating all args** against a strict allowlist before use (`validate_agent_args()`).
2. **Passing args via `SIMP_AGENT_*` environment variables**, not embedded in script source.
3. **Using `tempfile.mkstemp()`** (mode 700) instead of `/tmp/simp_agent_<name>.py`.
4. **Deriving all paths** from `Path(__file__).resolve().parents[N]` instead of hardcoded `/sessions/…` strings.

---

## 9. Thread Safety (issue #7)

All shared mutable state in the broker uses `threading.RLock()`:

- `_agent_lock` guards `agents` + `_secrets` + `_health_failures`
- `intent_lock` guards `intent_records`
- `stats_lock` guards all counters

Stats increments are atomic under `stats_lock`. TOCTOU races in `route_intent()` are eliminated by holding `_agent_lock` across the read-then-route sequence.

---

## 10. Audit Logging (issue #16)

Every security-relevant event is written to a SQLite audit database:

```bash
SIMP_AUDIT_DB_PATH=/var/log/simp/audit.db   # default: var/simp_audit.db
```

Events logged: `INTENT_ROUTED`, `SIGNATURE_FAILURE`, `AUTH_FAILURE`, `AGENT_REGISTERED`, `AGENT_DEREGISTERED`, `BROKER_START`, `BROKER_STOP`.

Each row includes: timestamp, event_type, agent_id, intent_id, correlation_id, status, sanitized details, obfuscated IP.

Secret values in `details` are automatically redacted (`***REDACTED***`).

---

## Reporting Vulnerabilities

Please report security issues privately via GitHub Security Advisories or email before public disclosure.
