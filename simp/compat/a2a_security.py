"""
SIMP A2A Security Hardening — Sprint S5 (Sprint 35)

Security scheme declarations, bearer-claim structural validation,
quota checking, and replay-protection posture notes.
"""

from typing import Dict, Any, List, Tuple, Optional


# ---------------------------------------------------------------------------
# Supported schemes
# ---------------------------------------------------------------------------

SUPPORTED_SCHEMES = ["api_key", "oauth2", "mtls"]


# ---------------------------------------------------------------------------
# A2A security-schemes block
# ---------------------------------------------------------------------------

def build_a2a_security_schemes_block() -> Dict[str, Dict[str, Any]]:
    """
    Return A2A-compatible securitySchemes dict.

    NEVER contains actual key values — only type declarations.
    """
    return {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": (
                "Static API key for internal agents and low-privilege A2A calls."
            ),
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "OAuth2/OIDC bearer token for user- or tenant-scoped A2A calls. "
                "Required claims: sub, aud, scope, exp."
            ),
        },
        "MutualTLS": {
            "type": "mutualTLS",
            "description": (
                "Mutual TLS for high-trust agent-to-agent channels. "
                "Enforced at gateway layer. "
                "Required for projectx_native and financial_ops."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Bearer-claim structural validation (no crypto)
# ---------------------------------------------------------------------------

_REQUIRED_CLAIMS = ("sub", "aud", "scope", "exp")


def validate_bearer_claims(
    token_dict: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Validate that *token_dict* contains the required JWT claims.

    This is a STRUCTURAL validator only — it does NOT verify signatures.
    Crypto verification is the gateway's responsibility.
    """
    for claim in _REQUIRED_CLAIMS:
        if claim not in token_dict:
            return False, f"missing claim: {claim}"
    return True, None


# ---------------------------------------------------------------------------
# Quota check (wraps existing rate limiter)
# ---------------------------------------------------------------------------

# A2A endpoints target 30 req/min
A2A_RATE_LIMIT = 30


def check_quota(agent_id: str, endpoint: str, limiter: Any) -> bool:
    """
    Check whether *agent_id* is within its A2A quota for *endpoint*.

    If *limiter* is None or has no per-prefix support, always returns True
    (fail-open for now; enforcement tightened at gateway).
    """
    if limiter is None:
        return True
    # If limiter supports a check method, use it
    if hasattr(limiter, "check"):
        return limiter.check(f"a2a:{agent_id}:{endpoint}", A2A_RATE_LIMIT)
    return True


# ---------------------------------------------------------------------------
# Replay protection posture note
# ---------------------------------------------------------------------------

def build_replay_guard_note() -> Dict[str, Any]:
    """Return a dict describing replay protection posture (card/docs)."""
    return {
        "replay_protection": {
            "status": "planned",
            "mechanisms": ["nonces", "signed_timestamps"],
            "current_enforcement": "none — enforced at gateway layer",
        }
    }
