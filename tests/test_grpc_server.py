"""Test the SIMP gRPC Server.

Runs a minimal broker + gRPC server in-process, then verifies
agent registration, heartbeat, stats, and health via gRPC client.
"""

import sys, os, time

os.environ.setdefault("SIMP_JWT_SECRET", "test-grpc-secret-key-32-chars!!")
os.environ.setdefault("SIMP_WS_DISABLE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grpc

from simp.server.broker import SimpBroker, BrokerConfig
from simp.server.grpc_server import GrpcServer
from simp.server.grpc_proto import simp_pb2, simp_pb2_grpc


def test_grpc_proto():
    """Proto stubs generated and importable."""
    assert hasattr(simp_pb2, "RegisterAgentRequest")
    assert hasattr(simp_pb2, "BrokerStats")
    assert hasattr(simp_pb2_grpc, "SimpServiceStub")
    print("  proto stubs OK")


def test_grpc_server_lifecycle():
    """Start/stop the gRPC server cleanly."""
    cfg = BrokerConfig(max_agents=10)
    broker = SimpBroker(config=cfg)
    broker.start()

    server = GrpcServer(broker=broker, lifecycle_manager=None, ws_bridge=None, port=50001)
    server.start()
    time.sleep(0.5)

    # is_running is a property, not a method
    assert server.is_running is True, "gRPC server should be running"
    assert server.address == "127.0.0.1:50001"

    server.stop()
    time.sleep(0.3)
    broker.stop()
    print("  start/stop OK")


def test_grpc_agent_registration():
    """Register an agent via gRPC and retrieve it."""
    cfg = BrokerConfig(max_agents=10)
    broker = SimpBroker(config=cfg)
    broker.start()

    server = GrpcServer(broker=broker, lifecycle_manager=None, ws_bridge=None, port=50002)
    server.start()
    time.sleep(0.5)

    channel = grpc.insecure_channel("127.0.0.1:50002")
    stub = simp_pb2_grpc.SimpServiceStub(channel)

    resp = stub.RegisterAgent(simp_pb2.RegisterAgentRequest(
        agent_id="grpc-test-agent",
        name="grpc-test-agent",
        agent_type="test",
        endpoint="grpc://localhost",
        capabilities=["test", "grpc"],
    ))
    assert resp.success, f"Registration failed: {resp.message}"
    print(f"  registration OK: {resp.message}")

    list_resp = stub.ListAgents(simp_pb2.ListAgentsRequest(active_only=False))
    agent_ids = [a.agent_id for a in list_resp.agents]
    assert "grpc-test-agent" in agent_ids, f"Agent not found in {agent_ids}"
    print(f"  list agents OK: {agent_ids}")

    get_resp = stub.GetAgent(simp_pb2.GetAgentRequest(agent_id="grpc-test-agent"))
    assert get_resp.agent_id == "grpc-test-agent"
    print(f"  get agent OK: {get_resp.agent_type}")

    channel.close()
    server.stop()
    broker.stop()
    print("  agent lifecycle OK")


def test_grpc_heartbeat():
    """Heartbeat recording via gRPC."""
    cfg = BrokerConfig(max_agents=10)
    broker = SimpBroker(config=cfg)
    broker.start()
    broker.register_agent("heartbeat-agent", "test", "grpc://")

    server = GrpcServer(broker=broker, lifecycle_manager=None, ws_bridge=None, port=50003)
    server.start()
    time.sleep(0.5)

    channel = grpc.insecure_channel("127.0.0.1:50003")
    stub = simp_pb2_grpc.SimpServiceStub(channel)

    resp = stub.Heartbeat(simp_pb2.HeartbeatRequest(agent_id="heartbeat-agent"))
    assert resp.alive, "Heartbeat should succeed for registered agent"
    print(f"  heartbeat OK: count={resp.count}")

    resp2 = stub.Heartbeat(simp_pb2.HeartbeatRequest(agent_id="nobody"))
    assert not resp2.alive, "Heartbeat should fail for unknown agent"
    print("  heartbeat unknown OK")

    channel.close()
    server.stop()
    broker.stop()
    print("  heartbeat OK")


def test_grpc_stats_health():
    """Stats and health endpoints via gRPC."""
    cfg = BrokerConfig(max_agents=10)
    broker = SimpBroker(config=cfg)
    broker.start()
    broker.register_agent("stats-agent", "test", "grpc://")

    server = GrpcServer(broker=broker, lifecycle_manager=None, ws_bridge=None, port=50004)
    server.start()
    time.sleep(0.5)

    channel = grpc.insecure_channel("127.0.0.1:50004")
    stub = simp_pb2_grpc.SimpServiceStub(channel)

    stats = stub.GetStats(simp_pb2.Empty())
    assert stats.agents_registered >= 1
    assert stats.version == "SIMP-1.0"
    print(f"  stats OK: agents={stats.agents_registered}")

    health = stub.Health(simp_pb2.HealthRequest())
    assert health.healthy, f"Broker should be healthy: {health.issues}"
    print(f"  health OK: state={health.state}")

    channel.close()
    server.stop()
    broker.stop()
    print("  stats+health OK")


def test_grpc_intent_submit():
    """Submit an intent via gRPC."""
    cfg = BrokerConfig(max_agents=10)
    broker = SimpBroker(config=cfg)
    broker.start()
    broker.register_agent("intent-agent", "test", "grpc://")

    server = GrpcServer(broker=broker, lifecycle_manager=None, ws_bridge=None, port=50005)
    server.start()
    time.sleep(0.5)

    channel = grpc.insecure_channel("127.0.0.1:50005")
    stub = simp_pb2_grpc.SimpServiceStub(channel)

    resp = stub.SubmitIntent(simp_pb2.SubmitIntentRequest(
        intent=simp_pb2.Intent(
            intent_id="",
            intent_type="test.intent",
            source_agent="intent-agent",
            payload_json='{"test": true}',
            priority="normal",
        )
    ))
    assert resp.accepted, f"Intent should be accepted: {resp.message}"
    assert resp.intent_id, "Intent ID should be returned"
    print(f"  submit intent OK: id={resp.intent_id}")

    status_resp = stub.GetIntentStatus(simp_pb2.GetIntentStatusRequest(intent_id=resp.intent_id))
    assert status_resp.status.intent_id == resp.intent_id
    print(f"  intent status OK: state={status_resp.status.state}")

    channel.close()
    server.stop()
    broker.stop()
    print("  intent submit OK")


if __name__ == "__main__":
    print("=== gRPC Server Tests ===")
    tests = [
        ("proto", test_grpc_proto),
        ("server lifecycle", test_grpc_server_lifecycle),
        ("agent registration", test_grpc_agent_registration),
        ("heartbeat", test_grpc_heartbeat),
        ("stats+health", test_grpc_stats_health),
        ("intent submit", test_grpc_intent_submit),
    ]
    passed = 0
    for name, fn in tests:
        try:
            print(f"\n[{name}]")
            fn()
            print("  PASS")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
    print(f"\n{'='*40}")
    print(f"Result: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
