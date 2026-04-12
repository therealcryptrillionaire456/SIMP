"""
simp/security/log_utils.py
───────────────────────────
Utilities for safe, privacy-preserving logging.

- obfuscate_ip()  : mask all but the last octet of an IPv4 address
- redact_agent_endpoint() : hash the host portion of host:port strings
- safe_agent_id() : truncate/hash long or suspicious agent IDs
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

_IPV4_RE = re.compile(
    r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b"
)
_ENDPOINT_RE = re.compile(r"^(.+):(\d+)$")


def obfuscate_ip(ip: Optional[str], *, enabled: bool = True) -> str:
    """
    Replace octets 1-3 of an IPv4 address with asterisks.

    Example: "192.168.1.42" → "***.***.*.42"
    When *enabled* is False (e.g. in dev mode), return the original value.
    """
    if not ip:
        return "<none>"
    if not enabled:
        return ip

    def _mask(m: re.Match) -> str:
        return f"***.***.***.{m.group(4)}"

    result = _IPV4_RE.sub(_mask, ip)
    # If no IPv4 pattern found, hash the whole value
    if result == ip and "." not in ip:
        return _hash_prefix(ip)
    return result


def obfuscate_endpoint(endpoint: Optional[str], *, enabled: bool = True) -> str:
    """
    Obfuscate the host portion of a "host:port" endpoint string.

    Example: "192.168.1.42:8080" → "***.***.*.42:8080"
             "internal-agent.corp:9000" → "<sha256[:8]>:9000"
    """
    if not endpoint:
        return "<none>"
    if not enabled:
        return endpoint

    m = _ENDPOINT_RE.match(endpoint)
    if m:
        host, port = m.group(1), m.group(2)
        return f"{obfuscate_ip(host, enabled=enabled)}:{port}"
    return obfuscate_ip(endpoint, enabled=enabled)


def safe_agent_id(agent_id: Optional[str], max_len: int = 40) -> str:
    """
    Return a safe representation of an agent ID for log messages.
    Truncates long IDs and adds a hash suffix to detect tampering.
    """
    if not agent_id:
        return "<unknown>"
    if len(agent_id) <= max_len:
        return agent_id
    prefix = agent_id[:max_len]
    suffix = _hash_prefix(agent_id, length=6)
    return f"{prefix}…[{suffix}]"


def redact_token(token: Optional[str]) -> str:
    """Show only first 4 chars of a token/key, mask the rest."""
    if not token:
        return "<none>"
    visible = token[:4]
    return f"{visible}{'*' * min(len(token) - 4, 8)}"


# ── internal ──────────────────────────────────────────────────────────────────

def _hash_prefix(value: str, length: int = 8) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:length]
