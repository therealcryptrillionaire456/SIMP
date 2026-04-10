"""
tests/security/test_log_utils.py
──────────────────────────────────
Tests for simp/security/log_utils.py
"""

from simp.security.log_utils import obfuscate_ip, obfuscate_endpoint, redact_token, safe_agent_id


def test_obfuscate_ipv4():
    result = obfuscate_ip("192.168.1.42")
    assert result.endswith(".42")
    assert "192" not in result
    assert "168" not in result


def test_obfuscate_ip_disabled():
    ip = "10.20.30.40"
    assert obfuscate_ip(ip, enabled=False) == ip


def test_obfuscate_none_ip():
    assert obfuscate_ip(None) == "<none>"
    assert obfuscate_ip("") == "<none>"


def test_obfuscate_endpoint_with_port():
    result = obfuscate_endpoint("192.168.1.42:8080")
    assert result.endswith(":8080")
    assert "192" not in result


def test_obfuscate_endpoint_disabled():
    ep = "10.0.0.1:9000"
    assert obfuscate_endpoint(ep, enabled=False) == ep


def test_redact_token_short():
    result = redact_token("abcdefghij")
    assert result.startswith("abcd")
    assert "efghij" not in result


def test_redact_token_none():
    assert redact_token(None) == "<none>"


def test_safe_agent_id_short():
    assert safe_agent_id("my-agent") == "my-agent"


def test_safe_agent_id_long():
    long_id = "a" * 200
    result = safe_agent_id(long_id)
    assert len(result) < len(long_id)
    assert "…" in result


def test_safe_agent_id_none():
    assert safe_agent_id(None) == "<unknown>"
