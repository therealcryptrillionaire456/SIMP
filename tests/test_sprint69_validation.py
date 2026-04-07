"""
Sprint 69 — Input Validation Tests

Tests for:
- Fixed timestamp regex (now uses datetime.fromisoformat)
- AgentRegistrationRequest Pydantic model
- IntentRouteRequest Pydantic model
- HTTP Content-Type enforcement
- Validation wired into POST /agents/register and POST /intents/route
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from simp.server.validation import (
    ResponseRecording,
    AgentRegistrationRequest,
    IntentRouteRequest,
)
from simp.server.http_server import SimpHttpServer
from simp.server.broker import BrokerConfig


class TestTimestampValidation:
    """Test fixed timestamp validation (was broken regex)."""

    def test_valid_iso_timestamps(self):
        valid = [
            "2024-01-15 12:30:00",
            "2024-01-15T12:30:00",
            "2024-12-31T23:59:59",
            "2024-01-01T00:00:00",
        ]
        for ts in valid:
            rec = ResponseRecording(response_id="r1", content="test", timestamp=ts)
            assert rec.timestamp == ts

    def test_invalid_timestamps_rejected(self):
        invalid = [
            "not-a-date",
            "2024/01/15",
            "15-01-2024",
            "",
            "2024-13-01T00:00:00",  # month 13
        ]
        for ts in invalid:
            with pytest.raises(ValidationError):
                ResponseRecording(response_id="r1", content="test", timestamp=ts)


class TestAgentRegistrationRequest:
    """Test Pydantic model for agent registration."""

    def test_valid_registration(self):
        req = AgentRegistrationRequest(
            agent_id="vision:001",
            agent_type="vision",
            endpoint="localhost:5001",
        )
        assert req.agent_id == "vision:001"

    def test_with_metadata(self):
        req = AgentRegistrationRequest(
            agent_id="grok:001",
            agent_type="grok",
            endpoint="localhost:5002",
            metadata={"version": "2.0"},
        )
        assert req.metadata == {"version": "2.0"}

    def test_empty_agent_id_rejected(self):
        with pytest.raises(ValidationError):
            AgentRegistrationRequest(
                agent_id="",
                agent_type="test",
                endpoint="localhost:5001",
            )

    def test_agent_id_too_long(self):
        with pytest.raises(ValidationError):
            AgentRegistrationRequest(
                agent_id="a" * 129,
                agent_type="test",
                endpoint="localhost:5001",
            )

    def test_agent_type_invalid_chars(self):
        with pytest.raises(ValidationError):
            AgentRegistrationRequest(
                agent_id="test001",
                agent_type="test type!",
                endpoint="localhost:5001",
            )

    def test_endpoint_too_long(self):
        with pytest.raises(ValidationError):
            AgentRegistrationRequest(
                agent_id="test001",
                agent_type="test",
                endpoint="x" * 257,
            )


class TestIntentRouteRequest:
    """Test Pydantic model for intent routing."""

    def test_valid_minimal(self):
        req = IntentRouteRequest(target_agent="grok:001")
        assert req.target_agent == "grok:001"
        assert req.source_agent == "client"

    def test_valid_full(self):
        req = IntentRouteRequest(
            target_agent="grok:001",
            source_agent="vision:001",
            intent_type="generate_strategy",
            intent_id="intent:001",
            params={"market": "SOL/USDC"},
            timestamp="2024-01-15T12:30:00",
        )
        assert req.params == {"market": "SOL/USDC"}

    def test_empty_target_rejected(self):
        with pytest.raises(ValidationError):
            IntentRouteRequest(target_agent="")

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(ValidationError):
            IntentRouteRequest(
                target_agent="test:001",
                timestamp="not-a-date",
            )


class TestHttpContentTypeEnforcement:
    """Test Content-Type checking on POST/PUT endpoints."""

    @pytest.fixture
    def client(self):
        config = BrokerConfig(max_agents=10)
        server = SimpHttpServer(config)
        server.broker.start()
        server.app.config["TESTING"] = True
        return server.app.test_client()

    def test_post_without_json_content_type_returns_415(self, client):
        resp = client.post(
            "/agents/register",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 415

    def test_post_with_json_content_type_accepted(self, client):
        resp = client.post(
            "/agents/register",
            json={"agent_id": "test:001", "agent_type": "test", "endpoint": "localhost:5001"},
            content_type="application/json",
        )
        assert resp.status_code in (201, 400)  # Either success or validation error, not 415

    def test_get_without_content_type_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
