# SIMP Security Checklist

## Security Posture (as of Sprints 66-70)

### Fixed Vulnerabilities

#### Sprint 66 — Cryptographic Hardening
- [x] **Double-hashing removed in v2 API**: `sign_intent_v2` signs directly without SHA-256 pre-hash (Ed25519 hashes internally)
- [x] **Signature metadata**: `_sig_nonce` (replay protection), `_sig_exp` (5-min expiry), `_sig_iat` (issuance time), `_sig_kid` (key fingerprint)
- [x] **Strict verification**: `verify_signature_strict()` with nonce tracking, expiry check, key ID validation
- [x] **Timing-safe comparison**: Uses `hmac.compare_digest` for key ID comparison
- [x] **Backward compatibility**: Legacy `sign_intent` and `verify_signature` preserved for existing callers

#### Sprint 67 — Key Storage Hardening
- [x] **Encrypted private keys**: `private_key_to_pem` uses `BestAvailableEncryption` when `SIMP_KEY_PASSPHRASE` env var is set
- [x] **Warning on unencrypted storage**: Emits `UserWarning` when no passphrase is configured
- [x] **Agent ID validation**: `sanitize_agent_id()` rejects path traversal and injection attempts
- [x] **Secure temp files**: Uses `tempfile.NamedTemporaryFile` instead of predictable `/tmp/` paths
- [x] **No repr() injection**: Agent args passed via JSON temp file, not `repr()` string interpolation

#### Sprint 68 — Broker Hardening
- [x] **Bounded intent records**: `OrderedDict` with LRU eviction at configurable `max_intent_records` (default 10,000)
- [x] **Memory exhaustion prevention**: Old records evicted when capacity reached
- [x] **Length-prefixed message framing**: 4-byte big-endian header + payload (replaces fixed 4096-byte `recv`)
- [x] **`_recv_exact()`**: Reads exact byte count from socket, handles partial reads
- [x] **Max message size**: 16 MB limit on incoming messages
- [x] **Event loop thread safety**: `asyncio.run()` per-call instead of shared `_async_loop`

#### Sprint 69 — Input Validation
- [x] **Fixed broken timestamp regex**: Replaced `\d{m}` / `\d{d}` with `datetime.fromisoformat()` validator
- [x] **Pydantic models**: `AgentRegistrationRequest` and `IntentRouteRequest` with field limits and patterns
- [x] **Validation wired into routes**: POST `/agents/register` and POST `/intents/route` return 400 on validation errors
- [x] **Content-Type enforcement**: `before_request` hook rejects POST/PUT without `application/json`

#### Sprint 70 — Security Headers & Audit
- [x] **Security response headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Content-Security-Policy, Cache-Control
- [x] **Server info removed**: `Server` and `X-Powered-By` headers stripped
- [x] **Append-only audit log**: `SecurityAuditLog` writes to `data/security_audit.jsonl`
- [x] **Sensitive field redaction**: API keys, passwords, private keys automatically redacted from log entries
- [x] **Audit events**: auth_failed, rate_limited, agent_registered, agent_deregistered, intent_rejected, validation_error
- [x] **Audit log API**: GET `/security/audit-log` with severity and event_type filters

### Remaining Considerations

- [ ] **TLS/HTTPS**: Broker and agent communication should use TLS in production
- [ ] **Authentication on audit endpoint**: GET `/security/audit-log` should require auth in production
- [ ] **Rate limiting integration with audit**: Audit events should fire on rate limit hits (requires Flask-Limiter hook)
- [ ] **Key rotation**: No automated key rotation mechanism yet
- [ ] **Nonce persistence**: `seen_nonces` set is in-memory only; needs persistence for distributed deployments
- [ ] **Audit log rotation**: No log rotation / size management for `security_audit.jsonl`
- [ ] **CORS policy**: No CORS headers configured; add if browser clients are supported
