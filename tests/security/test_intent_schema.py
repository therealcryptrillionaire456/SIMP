"""Security tests for SIMP intent schema validation."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from simp.models.intent_schema import IntentSchema, SIMPIntent


class TestIntentSchemaValidation:
    def test_valid_intent_schema(self):
        """Valid IntentSchema should construct without error."""
        schema = IntentSchema(
            name="test_intent",
            description="A test intent",
            examples=["do something", "perform action"],
        )
        assert schema.name == "test_intent"
        assert len(schema.examples) == 2

    def test_intent_schema_requires_name(self):
        """IntentSchema without name should raise ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            IntentSchema(examples=["test"])

    def test_intent_schema_requires_examples(self):
        """IntentSchema without examples should raise ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            IntentSchema(name="test")

    def test_simp_intent_collection(self):
        """SIMPIntent should hold a list of IntentSchema."""
        intent = SIMPIntent(intents=[
            IntentSchema(name="a", examples=["x"]),
            IntentSchema(name="b", examples=["y"]),
        ])
        assert len(intent.intents) == 2

    def test_simp_intent_empty_list(self):
        """SIMPIntent with empty intents list should be valid (no min constraint)."""
        intent = SIMPIntent(intents=[])
        assert isinstance(intent.intents, list)

    def test_intent_schema_optional_description(self):
        """Description should be optional."""
        schema = IntentSchema(name="test", examples=["x"])
        assert schema.description is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
