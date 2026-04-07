"""End-to-end task flow test: submit intent -> broker routes -> agent handles -> response recorded."""

import json
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.broker import SimpBroker, BrokerConfig


class MockAgentHandler(BaseHTTPRequestHandler):
    """Minimal mock agent that responds to intents."""
    responses = []

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "agent_id": "mock_agent"})
        else:
            self._respond(404, {})

    def do_POST(self):
        if self.path == "/intents/handle":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            MockAgentHandler.responses.append(body)
            self._respond(200, {
                "type": "response",
                "intent_id": body.get("intent_id", ""),
                "agent_id": "mock_agent",
                "status": "completed",
                "response": {"result": "Mock task completed"},
            })
        else:
            self._respond(404, {})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass  # Suppress output


class TestEndToEndTaskFlow:
    @pytest.fixture
    def mock_agent_server(self):
        """Start a mock agent HTTP server."""
        MockAgentHandler.responses = []
        server = HTTPServer(("127.0.0.1", 0), MockAgentHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield port
        server.shutdown()

    @pytest.fixture
    def broker(self):
        config = BrokerConfig(max_agents=10, health_check_interval=300)
        broker = SimpBroker(config)
        broker.start()
        yield broker
        broker.stop()

    def test_register_agent(self, broker, mock_agent_server):
        """Agent can register with the broker."""
        result = broker.register_agent(
            agent_id="mock_agent",
            agent_type="test",
            endpoint=f"http://127.0.0.1:{mock_agent_server}",
            metadata={"capabilities": ["code_task"]},
        )
        assert "mock_agent" in broker.agents

    def test_full_lifecycle(self, broker, mock_agent_server):
        """Full lifecycle: register -> route intent -> verify delivery."""
        # Register
        broker.register_agent(
            agent_id="mock_agent",
            agent_type="test",
            endpoint=f"http://127.0.0.1:{mock_agent_server}",
            metadata={},
        )

        # Route intent
        import asyncio
        intent = {
            "intent_id": "intent:test:e2e_001",
            "source_agent": "test_client",
            "target_agent": "mock_agent",
            "intent_type": "code_task",
            "params": {"task": "print hello"},
        }

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(broker.route_intent(intent))
        loop.close()

        # Verify intent was delivered
        assert result.get("status") in ("delivered", "completed", "queued", "routed")

    def test_full_lifecycle_delivery_status(self, broker, mock_agent_server):
        """Full lifecycle verifies delivery_status is delivered."""
        broker.register_agent(
            agent_id="mock_agent",
            agent_type="test",
            endpoint=f"http://127.0.0.1:{mock_agent_server}",
            metadata={},
        )

        import asyncio
        intent = {
            "intent_id": "intent:test:e2e_002",
            "source_agent": "test_client",
            "target_agent": "mock_agent",
            "intent_type": "research",
            "params": {"query": "test query"},
        }

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(broker.route_intent(intent))
        loop.close()

        assert result.get("delivery_status") == "delivered"

    def test_route_to_unregistered_agent(self, broker):
        """Routing to an unregistered agent returns an error."""
        import asyncio
        intent = {
            "intent_id": "intent:test:e2e_003",
            "source_agent": "test_client",
            "target_agent": "nonexistent_agent",
            "intent_type": "code_task",
            "params": {"task": "test"},
        }

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(broker.route_intent(intent))
        loop.close()

        assert result.get("status") == "error" or result.get("error_code") == "AGENT_NOT_FOUND"


class TestGemma4AgentAdapter:
    def test_gemma4_agent_importable(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        assert Gemma4Agent is not None

    def test_gemma4_agent_creates(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent(agent_id="test_gemma4")
        assert agent.agent_id == "test_gemma4"

    def test_gemma4_supported_intents(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        assert "research" in Gemma4Agent.SUPPORTED_INTENTS
        assert "code_task" in Gemma4Agent.SUPPORTED_INTENTS

    def test_gemma4_builds_research_prompt(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        prompt = agent._build_prompt("research", {"query": "test topic"})
        assert "test topic" in prompt

    def test_gemma4_builds_planning_prompt(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        prompt = agent._build_prompt("planning", {"goal": "build a house"})
        assert "build a house" in prompt

    def test_gemma4_builds_code_task_prompt(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        prompt = agent._build_prompt("code_task", {"task": "write a function"})
        assert "write a function" in prompt

    def test_gemma4_builds_code_review_prompt(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        prompt = agent._build_prompt("code_review", {"code": "def foo(): pass"})
        assert "def foo(): pass" in prompt

    def test_gemma4_builds_summarization_prompt(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        prompt = agent._build_prompt("summarization", {"text": "long article"})
        assert "long article" in prompt

    def test_gemma4_builds_docs_prompt(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        prompt = agent._build_prompt("docs", {"description": "API reference"})
        assert "API reference" in prompt
        assert "docs" in prompt

    def test_gemma4_builds_fallback_prompt(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        prompt = agent._build_prompt("unknown_type", {"key": "value"})
        assert "unknown_type" in prompt

    def test_gemma4_health_handles_no_server(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent(model_endpoint="http://localhost:99999")
        health = agent.health()
        assert health["status"] == "error"

    def test_gemma4_handle_intent_handles_no_server(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent(model_endpoint="http://localhost:99999")
        response = agent.handle_intent({
            "intent_type": "research",
            "params": {"query": "test"},
        })
        assert response["status"] == "failed"

    def test_gemma4_openai_format(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent(api_format="openai", model_endpoint="http://localhost:99999")
        response = agent.handle_intent({
            "intent_type": "code_task",
            "params": {"task": "hello world"},
        })
        assert response["status"] == "failed"
        assert response["agent_id"] == "gemma4_local"

    def test_gemma4_invalid_api_format(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent(api_format="invalid_format")
        response = agent.handle_intent({
            "intent_type": "research",
            "params": {"query": "test"},
        })
        assert response["status"] == "failed"
        assert "Unknown API format" in response["error"]

    def test_gemma4_close(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        agent.close()  # Should not raise

    def test_gemma4_default_values(self):
        from simp.agents.gemma4_agent import Gemma4Agent
        agent = Gemma4Agent()
        assert agent.agent_id == "gemma4_local"
        assert agent.model_name == "gemma4:e2b"
        assert agent.api_format == "ollama"
        assert agent.max_tokens == 4096
        assert agent.intents_handled == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
