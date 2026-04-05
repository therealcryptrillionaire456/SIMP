"""
SIMP Request Guards — Input validation for HTTP endpoints.

Validates agent IDs, intent payloads, and request sizes before they reach
the broker core. All guards return (is_valid: bool, error_message: Optional[str]).
"""

import json
import re
from typing import Any, Dict, Optional, Tuple

from simp.models.canonical_intent import INTENT_TYPE_REGISTRY

# -----------------------------------------------------------------------
# Constraints
# -----------------------------------------------------------------------
MAX_AGENT_ID_LENGTH = 64
AGENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-:.]+$")

MAX_INTENT_PAYLOAD_BYTES = 65_536  # 64 KB
MAX_PARAMS_KEYS = 50
MAX_STRING_VALUE_LENGTH = 10_000

# Legacy VALID_INTENT_TYPES removed — use INTENT_TYPE_REGISTRY from
# simp.models.canonical_intent as the single source of truth.


# -----------------------------------------------------------------------
# Guards
# -----------------------------------------------------------------------

def sanitize_agent_id(agent_id: Any) -> Tuple[bool, Optional[str]]:
    """Validate agent_id is safe for file paths and routing.

    Returns (True, None) on success, (False, error_msg) on failure.
    """
    if not isinstance(agent_id, str):
        return False, "agent_id must be a string"
    if not agent_id or len(agent_id) > MAX_AGENT_ID_LENGTH:
        return False, f"agent_id must be 1-{MAX_AGENT_ID_LENGTH} characters"
    if not AGENT_ID_PATTERN.match(agent_id):
        return False, "agent_id may only contain [a-zA-Z0-9_\\-:.]"
    # Path traversal defense
    if ".." in agent_id or "/" in agent_id or "\\" in agent_id:
        return False, "agent_id contains path traversal characters"
    return True, None


def validate_endpoint(endpoint: Any) -> Tuple[bool, Optional[str]]:
    """Validate an agent endpoint string."""
    if not isinstance(endpoint, str):
        return False, "endpoint must be a string"
    if len(endpoint) > 256:
        return False, "endpoint too long (max 256 chars)"
    # Must be http(s) URL, localhost reference, or empty (file-based)
    if endpoint == "":
        return True, None  # file-based agent
    if endpoint.startswith(("http://", "https://")):
        return True, None
    if endpoint.startswith("localhost:") or endpoint.startswith("127.0.0.1:"):
        return True, None
    return False, "endpoint must be http(s) URL, localhost:<port>, or empty string"


def validate_intent_payload(data: Any) -> Tuple[bool, Optional[str]]:
    """Validate an intent routing payload.

    Checks required fields, types, sizes, and intent_type allowlist.
    """
    if not isinstance(data, dict):
        return False, "payload must be a JSON object"

    # Check serialized size
    try:
        raw = json.dumps(data, default=str)
        if len(raw) > MAX_INTENT_PAYLOAD_BYTES:
            return False, f"payload exceeds {MAX_INTENT_PAYLOAD_BYTES} bytes"
    except (TypeError, ValueError):
        return False, "payload is not JSON-serializable"

    # Required field
    target = data.get("target_agent")
    if not target:
        return False, "missing required field: target_agent"

    # Validate target_agent format
    ok, err = sanitize_agent_id(target)
    if not ok:
        return False, f"target_agent invalid: {err}"

    # Validate source_agent if present
    source = data.get("source_agent")
    if source:
        ok, err = sanitize_agent_id(source)
        if not ok:
            return False, f"source_agent invalid: {err}"

    # Validate intent_type if present
    intent_type = data.get("intent_type")
    if intent_type:
        if not isinstance(intent_type, str) or len(intent_type) > 64:
            return False, "intent_type must be a string <= 64 chars"
        if intent_type not in INTENT_TYPE_REGISTRY:
            return False, f"Unknown intent_type: '{intent_type}'"

    # Validate params if present
    params = data.get("params")
    if params is not None:
        if not isinstance(params, dict):
            return False, "params must be a JSON object"
        if len(params) > MAX_PARAMS_KEYS:
            return False, f"params has too many keys (max {MAX_PARAMS_KEYS})"

    return True, None


def validate_registration_payload(data: Any) -> Tuple[bool, Optional[str]]:
    """Validate an agent registration payload."""
    if not isinstance(data, dict):
        return False, "payload must be a JSON object"

    agent_id = data.get("agent_id")
    if not agent_id:
        return False, "missing required field: agent_id"
    ok, err = sanitize_agent_id(agent_id)
    if not ok:
        return False, f"agent_id invalid: {err}"

    agent_type = data.get("agent_type")
    if not agent_type or not isinstance(agent_type, str):
        return False, "missing required field: agent_type"
    if len(agent_type) > 64:
        return False, "agent_type too long (max 64 chars)"

    endpoint = data.get("endpoint")
    if endpoint is None:
        return False, "missing required field: endpoint"
    ok, err = validate_endpoint(endpoint)
    if not ok:
        return False, f"endpoint invalid: {err}"

    # Validate optional public_key
    public_key = data.get("public_key")
    if public_key is not None:
        if not isinstance(public_key, str) or len(public_key) > 4096:
            return False, "public_key must be a string under 4096 chars"

    # Validate metadata size
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        return False, "metadata must be a JSON object"
    try:
        if len(json.dumps(metadata, default=str)) > MAX_INTENT_PAYLOAD_BYTES:
            return False, "metadata too large"
    except (TypeError, ValueError):
        return False, "metadata is not JSON-serializable"

    return True, None
