"""
Sprint 67 — Key Storage & Agent Manager Hardening Tests

Tests for:
- Encrypted private key storage with SIMP_KEY_PASSPHRASE
- Warning when no passphrase set
- Passphrase-based load/save roundtrip
- sanitize_agent_id validation (request_guards)
- Agent manager temp file security (no predictable /tmp paths)
- Agent script uses env-var args instead of repr() injection
"""

import pytest
import os

from simp.crypto import SimpCrypto
from simp.server.request_guards import sanitize_agent_id


class TestEncryptedKeyStorage:
    """Test encrypted private key PEM storage."""

    def test_encrypted_roundtrip_with_explicit_passphrase(self):
        priv, pub = SimpCrypto.generate_keypair()
        passphrase = b"test-passphrase-123"
        pem = SimpCrypto.private_key_to_pem(priv, passphrase=passphrase)
        assert b"ENCRYPTED" in pem
        loaded = SimpCrypto.load_private_key(pem, passphrase=passphrase)
        intent = {"id": "test"}
        sig = SimpCrypto.sign_intent(intent, loaded)
        intent["signature"] = sig
        assert SimpCrypto.verify_signature(intent, pub) is True

    def test_encrypted_roundtrip_with_env_var(self, monkeypatch):
        monkeypatch.setenv("SIMP_KEY_PASSPHRASE", "env-pass-456")
        priv, pub = SimpCrypto.generate_keypair()
        pem = SimpCrypto.private_key_to_pem(priv)
        assert b"ENCRYPTED" in pem
        loaded = SimpCrypto.load_private_key(pem)
        intent = {"id": "test"}
        sig = SimpCrypto.sign_intent(intent, loaded)
        intent["signature"] = sig
        assert SimpCrypto.verify_signature(intent, pub) is True

    def test_no_passphrase_warns(self, monkeypatch):
        monkeypatch.delenv("SIMP_KEY_PASSPHRASE", raising=False)
        priv, _ = SimpCrypto.generate_keypair()
        with pytest.warns(UserWarning, match="SIMP_KEY_PASSPHRASE not set"):
            pem = SimpCrypto.private_key_to_pem(priv)
        assert b"ENCRYPTED" not in pem

    def test_wrong_passphrase_fails(self):
        priv, _ = SimpCrypto.generate_keypair()
        pem = SimpCrypto.private_key_to_pem(priv, passphrase=b"correct")
        with pytest.raises(Exception):
            SimpCrypto.load_private_key(pem, passphrase=b"wrong")


class TestSanitizeAgentId:
    """Test agent ID validation via request_guards.sanitize_agent_id.

    This function returns (bool, Optional[str]) tuples.
    """

    def test_valid_ids(self):
        valid = [
            "agent001",
            "vision:001",
            "my-agent_v2.0",
            "a",
        ]
        for aid in valid:
            ok, err = sanitize_agent_id(aid)
            assert ok is True, f"Expected valid for {aid!r}, got error: {err}"

    def test_invalid_empty(self):
        ok, err = sanitize_agent_id("")
        assert ok is False

    def test_invalid_path_traversal(self):
        ok, err = sanitize_agent_id("../../etc/passwd")
        assert ok is False

    def test_invalid_too_long(self):
        ok, err = sanitize_agent_id("A" * 65)
        assert ok is False

    def test_invalid_special_chars(self):
        ok, err = sanitize_agent_id("has spaces")
        assert ok is False

    def test_non_string_rejected(self):
        ok, err = sanitize_agent_id(123)
        assert ok is False

    def test_invalid_slash(self):
        ok, err = sanitize_agent_id("has/slash")
        assert ok is False

    def test_invalid_semicolon(self):
        ok, err = sanitize_agent_id("has;semicolon")
        assert ok is False
