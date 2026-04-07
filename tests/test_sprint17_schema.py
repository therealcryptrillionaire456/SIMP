"""Tests for Sprint 17: Crypto activation, schema unification, config consolidation."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.models.canonical_intent import (
    CanonicalIntent,
    INTENT_TYPE_REGISTRY,
    REQUIRED_FIELDS,
)


class TestCanonicalIntent:
    def test_create_from_broker_dict(self):
        data = {
            "intent_id": "intent:test:123",
            "source_agent": "agent_a",
            "target_agent": "agent_b",
            "intent_type": "code_task",
            "params": {"code": "print('hello')"},
        }
        intent = CanonicalIntent.from_dict(data)
        assert intent.source_agent == "agent_a"
        assert intent.intent_type == "code_task"

    def test_create_from_legacy_intent_dict(self):
        """Handle nested source_agent object from Intent dataclass."""
        data = {
            "simp_version": "1.0",
            "source_agent": {"id": "agent_x", "organization": "acme", "public_key": "abc"},
            "intent": {"type": "research", "params": {"query": "test"}},
            "signature": "deadbeef",
        }
        intent = CanonicalIntent.from_dict(data)
        assert intent.source_agent == "agent_x"
        assert intent.intent_type == "research"
        assert intent.params == {"query": "test"}

    def test_validate_rejects_unknown_type(self):
        intent = CanonicalIntent(
            source_agent="test",
            intent_type="hack_the_planet",
            params={},
        )
        errors = intent.validate()
        assert any("Unknown intent_type" in e for e in errors)

    def test_validate_passes_valid_intent(self):
        intent = CanonicalIntent(
            source_agent="test_agent",
            intent_type="code_task",
            params={"code": "x = 1"},
        )
        errors = intent.validate()
        assert len(errors) == 0

    def test_to_dict_round_trip(self):
        original = CanonicalIntent(
            source_agent="agent_a",
            intent_type="research",
            params={"q": "test"},
        )
        d = original.to_dict()
        restored = CanonicalIntent.from_dict(d)
        assert restored.source_agent == original.source_agent
        assert restored.intent_type == original.intent_type

    def test_get_task_type_mapping(self):
        intent = CanonicalIntent(intent_type="code_task")
        assert intent.get_task_type() == "implementation"
        intent2 = CanonicalIntent(intent_type="research")
        assert intent2.get_task_type() == "research"

    def test_validate_requires_source_agent(self):
        intent = CanonicalIntent(intent_type="code_task", params={})
        errors = intent.validate()
        assert any("source_agent" in e for e in errors)

    def test_priority_validation(self):
        intent = CanonicalIntent(
            source_agent="test",
            intent_type="code_task",
            params={},
            priority="ultra_critical",
        )
        errors = intent.validate()
        assert any("priority" in e for e in errors)


class TestIntentTypeRegistry:
    def test_registry_has_core_types(self):
        core = ["code_task", "research", "planning", "orchestration", "trade_execution"]
        for t in core:
            assert t in INTENT_TYPE_REGISTRY, f"Missing core type: {t}"

    def test_registry_has_computer_use_types(self):
        assert "computer_use" in INTENT_TYPE_REGISTRY
        assert "computer_use_design_review" in INTENT_TYPE_REGISTRY

    def test_registry_has_self_improvement_types(self):
        assert "improve_tree" in INTENT_TYPE_REGISTRY
        assert "native_agent_repo_scan" in INTENT_TYPE_REGISTRY

    def test_all_registry_entries_have_task_type(self):
        for name, entry in INTENT_TYPE_REGISTRY.items():
            assert "task_type" in entry, f"Type '{name}' missing task_type"
            assert "description" in entry, f"Type '{name}' missing description"


class TestCryptoActivation:
    def test_crypto_module_importable(self):
        from simp.crypto import SimpCrypto
        assert hasattr(SimpCrypto, 'verify_signature')
        assert hasattr(SimpCrypto, 'sign_intent')

    def test_sign_verify_round_trip(self):
        from simp.crypto import SimpCrypto
        private_key, public_key = SimpCrypto.generate_keypair()
        payload = {"intent_type": "test", "params": {"x": 1}}
        signature = SimpCrypto.sign_intent(payload, private_key)
        assert isinstance(signature, str)
        assert len(signature) > 0
        # Verify with same key — verify_signature expects signature inside the dict
        signed_payload = {**payload, "signature": signature}
        assert SimpCrypto.verify_signature(signed_payload, public_key)

    def test_verify_rejects_tampered_payload(self):
        from simp.crypto import SimpCrypto
        private_key, public_key = SimpCrypto.generate_keypair()
        payload = {"intent_type": "test", "params": {"x": 1}}
        signature = SimpCrypto.sign_intent(payload, private_key)
        # Tamper with payload
        tampered = {"intent_type": "test", "params": {"x": 999}, "signature": signature}
        assert not SimpCrypto.verify_signature(tampered, public_key)


class TestConfigUnification:
    def test_simp_config_is_canonical(self):
        from config.config import SimpConfig
        config = SimpConfig()
        assert hasattr(config, 'PORT')
        assert hasattr(config, 'HOST')
        assert hasattr(config, 'MAX_AGENTS')
        assert hasattr(config, 'REQUIRE_API_KEY')
        assert hasattr(config, 'REQUIRE_SIGNATURES')

    def test_broker_config_exists(self):
        from simp.server.broker import BrokerConfig
        config = BrokerConfig()
        assert hasattr(config, 'port')
        assert hasattr(config, 'max_agents')

    def test_broker_config_reads_simp_defaults(self):
        from config.config import SimpConfig
        from simp.server.broker import BrokerConfig
        sc = SimpConfig()
        bc = BrokerConfig()
        assert bc.port == sc.PORT
        assert bc.host == sc.HOST
        assert bc.max_agents == sc.MAX_AGENTS

    def test_legacy_config_shim(self):
        from config.config import Config, SimpConfig as SC
        # Config should be aliased to SimpConfig
        assert Config is SC


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
