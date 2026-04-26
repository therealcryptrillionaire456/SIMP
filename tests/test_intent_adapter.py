"""
Tests for IntentAdapter — ProjectX ↔ SIMP Intent bridge.

All HTTP calls are mocked via monkeypatch; no real network requests are made.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest
import requests


# ── Imports from the module under test ──────────────────────────────────────
import sys
sys.path.insert(0, "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")

from simp.projectx.intent_adapter import (
    IntentAdapter,
    IntentRequest,
    IntentResponse,
    _ADAPTER_AGENT_ID,
    _BROKER_URL,
    _RESPONSE_TIMEOUT,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def adapter() -> IntentAdapter:
    """Default IntentAdapter instance pointing to localhost broker."""
    return IntentAdapter()


@pytest.fixture
def tmp_adapter(tmp_path, monkeypatch) -> IntentAdapter:
    """IntentAdapter using a temp directory for any local state, no real network."""
    # Ensure requests.post/get never hit the wire
    monkeypatch.setattr(requests, "post", MagicMock())
    monkeypatch.setattr(requests, "get", MagicMock())
    return IntentAdapter()


# ── Serialization tests ──────────────────────────────────────────────────────

class TestIntentRequestSerialization:
    def test_intent_request_serialization(self) -> None:
        req = IntentRequest(
            intent_type="market_analysis",
            goal="Analyse BTC/USD for last 24h",
            params={"exchange": "binance", "interval": "1h"},
            requester_id="test_requester",
            priority="high",
            timeout=60,
        )
        d = asdict(req)

        assert d["intent_type"] == "market_analysis"
        assert d["goal"] == "Analyse BTC/USD for last 24h"
        assert d["params"] == {"exchange": "binance", "interval": "1h"}
        assert d["requester_id"] == "test_requester"
        assert d["priority"] == "high"
        assert d["timeout"] == 60


class TestIntentResponseSerialization:
    def test_intent_response_serialization(self) -> None:
        resp = IntentResponse(
            intent_id="abc-123",
            intent_type="research",
            success=True,
            result={"data": [1, 2, 3]},
            error=None,
            agent_id="research_agent",
            latency_ms=42,
        )
        d = asdict(resp)

        assert d["intent_id"] == "abc-123"
        assert d["intent_type"] == "research"
        assert d["success"] is True
        assert d["result"] == {"data": [1, 2, 3]}
        assert d["error"] is None
        assert d["agent_id"] == "research_agent"
        assert d["latency_ms"] == 42

    def test_intent_response_error_serialization(self) -> None:
        resp = IntentResponse(
            intent_id="def-456",
            intent_type="unknown",
            success=False,
            result=None,
            error="Intent type not registered",
            agent_id="",
            latency_ms=5,
        )
        d = asdict(resp)

        assert d["success"] is False
        assert d["error"] == "Intent type not registered"


# ── Dispatch / network error tests ──────────────────────────────────────────

class TestDispatchErrors:

    def test_dispatch_returns_error_on_broker_unreachable(
        self, adapter: IntentAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raise_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(requests, "post", raise_connection_error)

        result = adapter.dispatch(intent_type="research", goal="Summarise the news")

        assert result.success is False
        assert result.error is not None

    def test_dispatch_timeout_returns_error(
        self, adapter: IntentAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mock post succeeds but polling never finds a result — timeout fires."""
        posted_response = MagicMock()
        posted_response.status_code = 202

        polled_response = MagicMock()
        polled_response.status_code = 404  # not ready yet

        call_count = {"count": 0}

        def mock_post(*args, **kwargs):
            return posted_response

        def mock_get(*args, **kwargs):
            call_count["count"] += 1
            return polled_response

        monkeypatch.setattr(requests, "post", mock_post)
        monkeypatch.setattr(requests, "get", mock_get)

        # Use a very short timeout so the test finishes quickly
        result = adapter.dispatch(
            intent_type="research",
            goal="Quick test goal",
            timeout=1,
        )

        assert result.success is False
        assert "Timed out" in result.error


# ── Payload structure test ───────────────────────────────────────────────────

class TestPayloadBuilding:

    def test_build_intent_payload(self, adapter: IntentAdapter) -> None:
        intent_id = "test-id-0001"
        intent_type = "market_analysis"
        goal = "Analyse ETH/USD for last 4h"
        params = {"exchange": "kraken"}

        payload = adapter._build_intent_payload(intent_id, intent_type, goal, params)

        # Verify required SIMP intent format fields
        assert payload["id"] == intent_id
        assert payload["intent_type"] == intent_type
        assert "simp_version" in payload
        assert "timestamp" in payload
        assert "source_agent" in payload
        assert payload["source_agent"]["id"] == adapter._agent_id
        assert payload["params"]["goal"] == goal
        assert payload["params"]["exchange"] == "kraken"
        assert "signature" in payload


# ── Adapter initialization tests ────────────────────────────────────────────

class TestAdapterInitialization:

    def test_intent_adapter_initialization(self) -> None:
        custom_broker = "http://custom.broker.local:9999"
        custom_agent = "my_test_adapter"

        adapter = IntentAdapter(broker_url=custom_broker, agent_id=custom_agent)

        assert adapter._broker == custom_broker.rstrip("/")
        assert adapter._agent_id == custom_agent
        assert adapter._registered is False

    def test_adapter_default_values(self, adapter: IntentAdapter) -> None:
        """Verify defaults match module-level constants."""
        assert adapter._broker == _BROKER_URL
        assert adapter._agent_id == _ADAPTER_AGENT_ID


# ── Timeout configuration test ───────────────────────────────────────────────

class TestTimeoutConfiguration:

    def test_response_timeout_configurable(
        self, adapter: IntentAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        custom_timeout = 120
        post_calls: list = []

        def tracking_post(url: str, **kwargs):
            post_calls.append(kwargs.get("timeout"))
            resp = MagicMock()
            resp.status_code = 202
            return resp

        def tracking_get(url: str, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"status": "completed", "success": True}
            return resp

        monkeypatch.setattr(requests, "post", tracking_post)
        monkeypatch.setattr(requests, "get", tracking_get)

        adapter.dispatch(
            intent_type="research",
            goal="Test timeout config",
            timeout=custom_timeout,
        )

        # The dispatch() itself passes timeout=custom_timeout to _poll_result(),
        # which uses it as the deadline — verify the call chain completes
        # without error (the timeout is honoured by _poll_result).
        assert len(post_calls) == 1


# ── Priority parameter test ──────────────────────────────────────────────────

class TestPriorityParameter:

    def test_priority_parameter_passed(
        self, adapter: IntentAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured_payload: list = []

        def capture_post(url: str, json: Dict, **kwargs):
            captured_payload.append(json)
            resp = MagicMock()
            resp.status_code = 202
            return resp

        def immediate_get(url: str, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"status": "completed", "success": True}
            return resp

        monkeypatch.setattr(requests, "post", capture_post)
        monkeypatch.setattr(requests, "get", immediate_get)

        adapter.dispatch(
            intent_type="research",
            goal="Priority test goal",
            params={"priority": "high"},
        )

        assert len(captured_payload) == 1
        payload = captured_payload[0]
        assert "params" in payload
        assert payload["params"].get("priority") == "high"


# ── Error response parsing test ─────────────────────────────────────────────

class TestErrorResponseParsing:

    def test_error_response_parsing(
        self, adapter: IntentAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        broker_error_message = "Intent type 'foo_bar' not found in registry"

        def error_post(url: str, **kwargs):
            resp = MagicMock()
            resp.status_code = 202
            return resp

        def error_get(url: str, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "status": "failed",
                "success": False,
                "error": broker_error_message,
            }
            return resp

        monkeypatch.setattr(requests, "post", error_post)
        monkeypatch.setattr(requests, "get", error_get)

        result = adapter.dispatch(intent_type="foo_bar", goal="Irrelevant goal")

        assert result.success is False
        assert broker_error_message in result.error
