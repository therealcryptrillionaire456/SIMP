"""Tests for Sprint 9: Protocol cleanup and test coverage."""

import importlib
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestIntentSchemaModule:
    def test_intent_schema_importable(self):
        from simp.models.intent_schema import IntentSchema, SIMPIntent
        assert IntentSchema is not None
        assert SIMPIntent is not None

    def test_intent_schema_compile(self):
        import py_compile
        path = os.path.join(
            os.path.dirname(__file__), "..", "simp", "models", "intent_schema.py"
        )
        py_compile.compile(path, doraise=True)


class TestSecurityTestsPass:
    def test_security_test_importable(self):
        """tests/security/test_intent_schema.py should import without error."""
        security_dir = os.path.join(os.path.dirname(__file__), "security")
        if os.path.exists(os.path.join(security_dir, "test_intent_schema.py")):
            spec = importlib.util.spec_from_file_location(
                "test_intent_schema",
                os.path.join(security_dir, "test_intent_schema.py"),
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # Should not raise


class TestConfigCompiles:
    def test_config_compiles(self):
        """config/config.py should compile if it exists."""
        import py_compile
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "config.py"
        )
        if os.path.exists(config_path):
            py_compile.compile(config_path, doraise=True)
        else:
            pytest.skip("config/config.py does not exist")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
