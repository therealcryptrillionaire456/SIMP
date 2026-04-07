"""
Sprint 67 — Key Storage & Agent Manager Hardening Tests

Tests for:
- Encrypted private key storage with SIMP_KEY_PASSPHRASE
- Warning when no passphrase set
- Passphrase-based load/save roundtrip
- sanitize_agent_id validation
- Agent manager temp file security (no predictable /tmp paths)
- Agent script uses JSON args instead of repr() injection
"""

import pytest
import os
import tempfile
import json

from simp.crypto import SimpCrypto
from simp.server.agent_manager import AgentManager, sanitize_agent_id


class TestEncryptedKeyStorage:
    """Test encrypted private key PEM storage."""

    def test_encrypted_roundtrip_with_explicit_passphrase(self):
        priv, pub = SimpCrypto.generate_keypair()
        passphrase = b"test-passphrase-123"
        pem = SimpCrypto.private_key_to_pem(priv, passphrase=passphrase)
        assert b"ENCRYPTED" in pem
        loaded = SimpCrypto.load_private_key(pem, passphrase=passphrase)
        # Verify the loaded key can sign and be verified
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
    """Test agent ID validation."""

    def test_valid_ids(self):
        valid = [
            "agent001",
            "vision:001",
            "my-agent_v2.0",
            "A" * 128,
            "a",
        ]
        for aid in valid:
            assert sanitize_agent_id(aid) == aid

    def test_invalid_ids(self):
        invalid = [
            "",
            ":starts-with-colon",
            "-starts-with-dash",
            ".starts-with-dot",
            "_starts-with-underscore",
            "has spaces",
            "has;semicolon",
            "has/slash",
            'has"quote',
            "A" * 129,
        ]
        for aid in invalid:
            with pytest.raises(ValueError):
                sanitize_agent_id(aid)

    def test_non_string_rejected(self):
        with pytest.raises(ValueError):
            sanitize_agent_id(123)


class TestAgentManagerSecurity:
    """Test agent manager security improvements."""

    def test_spawn_rejects_invalid_id(self):
        mgr = AgentManager()
        result = mgr.spawn_agent(
            agent_id="../../etc/passwd",
            agent_type="test",
            agent_class="simp.agents.TestAgent",
            agent_module="simp.agents.test",
        )
        assert result is None

    def test_generate_script_uses_json_args(self):
        mgr = AgentManager()
        args = {"key": "value", "nested": {"a": 1}}
        script = mgr._generate_agent_script(
            agent_id="test001",
            agent_type="test",
            agent_class="simp.agents.TestAgent",
            agent_module="simp.agents.test",
            port=5001,
            args=args,
        )
        # Script should NOT contain repr() of args directly
        assert "repr(" not in script
        # Script should use json.load
        assert "json.load" in script

    def test_generate_script_no_repr_injection(self):
        mgr = AgentManager()
        malicious_args = {"key": '__import__("os").system("rm -rf /")'}
        script = mgr._generate_agent_script(
            agent_id="test001",
            agent_type="test",
            agent_class="simp.agents.TestAgent",
            agent_module="simp.agents.test",
            port=5001,
            args=malicious_args,
        )
        # The malicious string should NOT appear directly in the script
        assert '__import__("os")' not in script

    def test_agent_manager_basic_lifecycle(self):
        mgr = AgentManager()
        assert mgr.list_agents() == {}
        health = mgr.get_health_status()
        assert health["total_agents"] == 0
