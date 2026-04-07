"""
SIMP Control Auth — Simple bearer token authentication for control endpoints.

Protects /control/* endpoints with an optional bearer token.
When SIMP_CONTROL_TOKEN env var is set, requests must include it.
When not set, control endpoints are open (backward compatible).
"""

import hmac
import os
from functools import wraps
from flask import request, jsonify


# Read token from environment; empty/missing = auth disabled
CONTROL_TOKEN = os.environ.get("SIMP_CONTROL_TOKEN", "").strip()


def require_control_auth(f):
    """Decorator that enforces bearer token auth on control endpoints.

    If SIMP_CONTROL_TOKEN is not set, all requests pass through (no-op).
    If set, the request must have: Authorization: Bearer <token>
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not CONTROL_TOKEN:
            # No token configured — allow all (backward compatible)
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "status": "error",
                "error_code": "AUTH_REQUIRED",
                "error": "Missing Authorization: Bearer <token> header",
            }), 401

        provided_token = auth_header[7:].strip()  # Strip "Bearer "
        if not hmac.compare_digest(provided_token, CONTROL_TOKEN):
            return jsonify({
                "status": "error",
                "error_code": "AUTH_FAILED",
                "error": "Invalid control token",
            }), 403

        return f(*args, **kwargs)
    return wrapper
