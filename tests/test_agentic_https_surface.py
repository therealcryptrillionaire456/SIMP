from __future__ import annotations

import asyncio

from simp.agentic_https import AgentIdentity, AgenticIntentRequest, build_contract_description
from simp.crypto import SimpCrypto
from simp.native_tools import NativeToolRegistry, SimpTool
from simp.server.agent_registry import AgentRegistryConfig
from simp.server.broker import BrokerConfig, BrokerState, SimpBroker
from simp.server.http_server import SimpHttpServer


def _server_config(tmp_path):
    registry_cfg = AgentRegistryConfig(persist_path=str(tmp_path / "agent_registry.jsonl"))
    return BrokerConfig(
        inbox_base_dir=str(tmp_path / "inboxes"),
        agent_registry_config=registry_cfg,
    )


def test_native_registry_is_source_of_truth_for_mcp_wrapper():
    agent_id = "native_surface_test"
    registry = NativeToolRegistry.get_registry(agent_id, create=True)
    assert registry is not None

    registry.register(
        SimpTool.from_function(
            lambda target="world": {"hello": target},
            name="hello_tool",
            description="Simple native tool",
            intent_type="status_check",
        )
    )

    from simp.mcp.tool_registry import ToolRegistry

    compat_registry = ToolRegistry.get_registry(agent_id)
    assert compat_registry is registry
    assert compat_registry.get_tool("hello_tool") is not None


def test_build_contract_description_exposes_agentic_https_surface():
    contract = build_contract_description()
    assert contract["protocol"] == "agentic_https"
    assert "intent" in contract["request_fields"]
    assert "/tasks/{task_id}/stream" in contract["streaming"]["task_stream_template"]
    assert "http_native" in contract["invocation_modes"]


def test_agentic_request_to_broker_payload_preserves_native_metadata():
    intent = {
        "source_agent": "planner",
        "target_agent": "executor",
        "intent_type": "health_check",
        "params": {"mode": "quick"},
    }
    request = AgenticIntentRequest.from_dict(
        {
            "intent": intent,
            "transport": "broker_http",
            "invocation_mode": "http_native",
            "ttl_seconds": 45,
            "trace_id": "trace-1",
            "correlation_id": "corr-1",
            "metadata": {"path": "native"},
        }
    )

    payload = request.to_broker_payload()
    assert payload["ttl_seconds"] == 45
    assert payload["trace_id"] == "trace-1"
    assert payload["correlation_id"] == "corr-1"
    assert payload["invocation_mode"] == "http_native"
    assert payload["metadata"]["path"] == "native"
    assert payload["metadata"]["transport"] == "broker_http"


def test_native_http_endpoints_list_and_invoke(tmp_path):
    server = SimpHttpServer(broker_config=_server_config(tmp_path))
    client = server.app.test_client()
    agent_id = "native_http_agent"
    registry = NativeToolRegistry.get_registry(agent_id, create=True)
    assert registry is not None
    registry.register(
        SimpTool.from_function(
            lambda target="mesh": {"pong": target},
            name="native_ping",
            description="Ping natively",
            intent_type="ping",
        )
    )

    list_resp = client.get(f"/native/tools/{agent_id}/list")
    assert list_resp.status_code == 200
    list_body = list_resp.get_json()
    assert list_body["source"] == "native"
    assert list_body["tool_names"] == ["native_ping"]

    invoke_resp = client.post(
        f"/native/tools/{agent_id}/native_ping/invoke",
        json={"arguments": {"target": "executor"}},
    )
    assert invoke_resp.status_code == 200
    invoke_body = invoke_resp.get_json()
    assert invoke_body["invocation_mode"] == "native"
    assert invoke_body["result"] == {"pong": "executor"}

    compat_resp = client.get("/mcp/tools/list")
    assert compat_resp.status_code == 200
    assert compat_resp.get_json()["source"] == "native_via_mcp_compat"


def test_agentic_route_endpoint_returns_uniform_response(tmp_path):
    server = SimpHttpServer(broker_config=_server_config(tmp_path))
    server.broker.state = BrokerState.RUNNING
    assert server.broker.register_agent("executor", "worker", "")
    client = server.app.test_client()

    response = client.post(
        "/agentic/intents/route",
        json={
            "intent": {
                "source_agent": "planner",
                "target_agent": "executor",
                "intent_type": "health_check",
                "params": {"mode": "quick"},
            },
            "invocation_mode": "http_native",
            "trace_id": "trace-agentic-1",
            "correlation_id": "corr-agentic-1",
            "expect_stream": True,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["invocation_mode"] == "http_native"
    assert body["trace_id"] == "trace-agentic-1"
    assert body["correlation_id"] == "corr-agentic-1"
    assert body["stream_endpoint"].startswith("/tasks/")
    assert body["payload"]["delivery_status"] in {"queued_no_endpoint", "queued", "delivered"}


def test_agentic_route_rejects_invalid_signature(tmp_path):
    server = SimpHttpServer(broker_config=_server_config(tmp_path))
    server.broker.state = BrokerState.RUNNING
    assert server.broker.register_agent("executor", "worker", "")
    client = server.app.test_client()

    private_key, public_key = SimpCrypto.generate_keypair()
    intent = {
        "source_agent": "planner",
        "target_agent": "executor",
        "intent_type": "health_check",
        "params": {"mode": "quick"},
    }
    signature = SimpCrypto.sign_intent_v2(intent, private_key)
    intent["signature"] = signature
    intent["params"]["mode"] = "tampered"

    public_pem = SimpCrypto.public_key_to_pem(public_key).decode()
    response = client.post(
        "/agentic/intents/route",
        json={
            "intent": intent,
            "identity": AgentIdentity(agent_id="planner", public_key=public_pem).to_dict(),
            "invocation_mode": "http_native",
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error_code"] == "INVALID_SIGNATURE"


def test_broker_route_agentic_request_supports_signed_happy_path(tmp_path):
    broker = SimpBroker(config=_server_config(tmp_path))
    broker.state = BrokerState.RUNNING
    assert broker.register_agent("executor", "worker", "")

    private_key, public_key = SimpCrypto.generate_keypair()
    intent = {
        "source_agent": "planner",
        "target_agent": "executor",
        "intent_type": "health_check",
        "params": {"mode": "quick"},
    }
    signature = SimpCrypto.sign_intent_v2(intent, private_key)
    intent["signature"] = signature
    public_pem = SimpCrypto.public_key_to_pem(public_key).decode()

    result = asyncio.run(
        broker.route_agentic_request(
            {
                "intent": intent,
                "identity": AgentIdentity(agent_id="planner", public_key=public_pem).to_dict(),
                "invocation_mode": "native",
                "trace_id": "trace-direct-1",
                "correlation_id": "corr-direct-1",
            }
        )
    )

    assert result["success"] is True
    assert result["invocation_mode"] == "native"
    assert result["trace_id"] == "trace-direct-1"
    assert result["correlation_id"] == "corr-direct-1"
