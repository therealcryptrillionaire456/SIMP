"""Tests for SIMP request guards — input validation layer."""

import pytest
import sys
import os

# Ensure the repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.request_guards import (
    sanitize_agent_id,
    validate_endpoint,
    validate_intent_payload,
    validate_registration_payload,
)


class TestSanitizeAgentId:
    def test_valid_ids(self):
        valid = ["agent:001", "kloutbot", "bullbear_predictor", "claude_cowork", "a.b-c:d_e"]
        for aid in valid:
            ok, err = sanitize_agent_id(aid)
            assert ok, f"{aid} should be valid but got: {err}"

    def test_empty_string(self):
        ok, err = sanitize_agent_id("")
        assert not ok

    def test_too_long(self):
        ok, err = sanitize_agent_id("a" * 65)
        assert not ok

    def test_path_traversal(self):
        ok, err = sanitize_agent_id("../../etc/passwd")
        assert not ok
        assert "path traversal" in err.lower() or "only contain" in err.lower()

    def test_slashes(self):
        ok, err = sanitize_agent_id("agent/sub")
        assert not ok

    def test_non_string(self):
        ok, err = sanitize_agent_id(123)
        assert not ok

    def test_special_chars(self):
        ok, err = sanitize_agent_id("agent;DROP TABLE")
        assert not ok

    def test_unicode(self):
        ok, err = sanitize_agent_id("ag\u00ebnt")
        assert not ok


class TestValidateEndpoint:
    def test_http(self):
        ok, _ = validate_endpoint("http://127.0.0.1:8765")
        assert ok

    def test_https(self):
        ok, _ = validate_endpoint("https://example.com/api")
        assert ok

    def test_empty_for_file_based(self):
        ok, _ = validate_endpoint("")
        assert ok

    def test_localhost(self):
        ok, _ = validate_endpoint("localhost:5555")
        assert ok

    def test_invalid_scheme(self):
        ok, _ = validate_endpoint("ftp://bad.com")
        assert not ok

    def test_too_long(self):
        ok, _ = validate_endpoint("http://example.com/" + "a" * 300)
        assert not ok


class TestValidateIntentPayload:
    def test_valid_minimal(self):
        ok, _ = validate_intent_payload({
            "target_agent": "kloutbot",
            "intent_type": "system_test",
        })
        assert ok

    def test_valid_full(self):
        ok, _ = validate_intent_payload({
            "intent_id": "intent:001",
            "source_agent": "perplexity_research",
            "target_agent": "kloutbot",
            "intent_type": "research_request",
            "params": {"topic": "BTC analysis", "urgency": "medium"},
        })
        assert ok

    def test_missing_target(self):
        ok, err = validate_intent_payload({"intent_type": "test"})
        assert not ok
        assert "target_agent" in err

    def test_bad_target_agent(self):
        ok, _ = validate_intent_payload({
            "target_agent": "../../etc/passwd",
        })
        assert not ok

    def test_oversized_payload(self):
        ok, _ = validate_intent_payload({
            "target_agent": "kloutbot",
            "params": {"big": "x" * 70000},
        })
        assert not ok

    def test_non_dict(self):
        ok, _ = validate_intent_payload("not a dict")
        assert not ok

    def test_params_too_many_keys(self):
        ok, _ = validate_intent_payload({
            "target_agent": "kloutbot",
            "params": {f"key_{i}": i for i in range(51)},
        })
        assert not ok


class TestValidateRegistrationPayload:
    def test_valid(self):
        ok, _ = validate_registration_payload({
            "agent_id": "new_agent",
            "agent_type": "research",
            "endpoint": "http://127.0.0.1:9000",
        })
        assert ok

    def test_valid_file_based(self):
        ok, _ = validate_registration_payload({
            "agent_id": "file_agent",
            "agent_type": "watcher",
            "endpoint": "",
        })
        assert ok

    def test_missing_agent_id(self):
        ok, _ = validate_registration_payload({
            "agent_type": "test",
            "endpoint": "http://localhost:5000",
        })
        assert not ok

    def test_bad_agent_id(self):
        ok, _ = validate_registration_payload({
            "agent_id": "../../../bad",
            "agent_type": "test",
            "endpoint": "",
        })
        assert not ok

    def test_missing_endpoint(self):
        ok, _ = validate_registration_payload({
            "agent_id": "agent_x",
            "agent_type": "test",
        })
        assert not ok


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
