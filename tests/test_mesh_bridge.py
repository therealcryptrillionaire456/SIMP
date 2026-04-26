"""
Tests for ProjectXMeshBridge.

These tests mock all network/broker calls so they run without a live SIMP
installation. Real network calls are never made.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")

from simp.projectx.mesh_bridge import (
    ProjectXMeshBridge,
    ProjectXTask,
    AGENT_ID,
    TASK_CHANNEL,
    RESULT_CHANNEL,
    get_projectx_mesh_bridge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_broker_url():
    return "http://127.0.0.1:5555"


@pytest.fixture
def mock_computer():
    computer = MagicMock()
    computer.max_tier = 2
    computer.log_dir = "/tmp"
    computer._action_count = 0
    computer.safe_execute = MagicMock(return_value={"success": True, "data": {}})
    return computer


@pytest.fixture
def mock_trust_graph():
    graph = MagicMock()
    graph.get_effective_score = MagicMock(return_value=5.0)
    return graph


@pytest.fixture
def mock_mesh_bus():
    bus = MagicMock()
    bus.send = MagicMock(return_value=True)
    bus.subscribe = MagicMock(return_value=True)
    bus.unsubscribe = MagicMock(return_value=True)
    return bus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_task_payload(
    task_id: str = "task-001",
    action: str = "get_screenshot",
    requester_id: str = "remote_agent",
    **kwargs,
) -> dict:
    """Build a minimal packet payload dict for _execute_task."""
    return {
        "task_id": task_id,
        "action": action,
        "params": kwargs.pop("params", {}),
        "requester_id": requester_id,
        "priority": kwargs.pop("priority", "normal"),
        "timeout": kwargs.pop("timeout", 30),
        "trust_required": kwargs.pop("trust_required", 0.0),
        **kwargs,
    }


def make_mock_packet(payload: dict) -> MagicMock:
    """Wrap a payload dict in a mock packet object."""
    pkt = MagicMock()
    pkt.payload = payload
    pkt.channel = TASK_CHANNEL
    return pkt


def make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
    """
    Create a bridge with all external dependencies patched.
    Patches are active for the lifetime of the returned bridge object.
    """
    with patch("simp.projectx.mesh_bridge.requests.post") as mock_post, \
         patch(
             "simp.mesh.enhanced_bus.get_enhanced_mesh_bus",
             return_value=mock_mesh_bus,
         ), \
         patch("simp.mesh.packet.create_event_packet") as mock_create_pkt:

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"agent_id": AGENT_ID})

        br = ProjectXMeshBridge(
            broker_url=mock_broker_url,
            agent_id="test_agent",
            computer=mock_computer,
            trust_graph=mock_trust_graph,
        )
        # Simulate running state without starting the background thread
        br._running = True
        br._registered = True
        yield br, mock_create_pkt
        br._running = False


# ---------------------------------------------------------------------------
# Tests — Initialization
# ---------------------------------------------------------------------------

def test_mesh_bridge_initialization(mock_broker_url, mock_computer, mock_trust_graph):
    """Verify MeshBridge __init__ sets correct defaults and zeroed stats."""
    with patch("simp.projectx.mesh_bridge.requests.post"):
        br = ProjectXMeshBridge(
            broker_url=mock_broker_url,
            agent_id="test_agent",
            computer=mock_computer,
            trust_graph=mock_trust_graph,
        )

    assert br.broker_url == mock_broker_url.rstrip("/")
    assert br.agent_id == "test_agent"
    assert br.computer is mock_computer
    assert br._trust_graph is mock_trust_graph
    assert br._running is False
    assert br._registered is False
    assert br._thread is None

    stats = br._stats
    assert stats["tasks_received"] == 0
    assert stats["tasks_completed"] == 0
    assert stats["tasks_denied"] == 0
    assert stats["tasks_errored"] == 0
    assert stats["heartbeats_sent"] == 0
    assert stats["heartbeat_failures"] == 0


def test_mesh_bridge_initialization_defaults():
    """Verify defaults when no arguments are provided."""
    with patch("simp.projectx.mesh_bridge.requests.post"):
        br = ProjectXMeshBridge()

    assert br.agent_id == AGENT_ID
    assert br.broker_url == "http://127.0.0.1:5555"


# ---------------------------------------------------------------------------
# Tests — connect / start
# ---------------------------------------------------------------------------

def test_mesh_bridge_connect_registers_and_subscribes(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """
    start() registers with the broker and subscribes to mesh channels.
    """
    with patch("simp.projectx.mesh_bridge.requests.post") as mock_post, \
         patch(
             "simp.mesh.enhanced_bus.get_enhanced_mesh_bus",
             return_value=mock_mesh_bus,
         ) as mock_bus_factory, \
         patch("simp.mesh.packet.create_event_packet"):

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"agent_id": "test_agent"})

        br = ProjectXMeshBridge(
            broker_url=mock_broker_url,
            agent_id="test_agent",
            computer=mock_computer,
            trust_graph=mock_trust_graph,
        )
        # Patch the threading module so start() doesn't actually spawn a thread
        with patch("simp.projectx.mesh_bridge.threading.Thread"):
            result = br.start()

    assert result is True
    assert br._running is True
    assert br._registered is True

    # Registration POST was issued
    registration_calls = [
        c for c in mock_post.call_args_list
        if "/agents/register" in c[0][0]
    ]
    assert len(registration_calls) == 1

    # Mesh bus was obtained and subscribed
    mock_bus_factory.assert_called()
    mock_mesh_bus.subscribe.assert_called()


def test_mesh_bridge_start_idempotent(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """Calling start() twice returns True without re-registering."""
    with patch("simp.projectx.mesh_bridge.requests.post") as mock_post, \
         patch("simp.mesh.enhanced_bus.get_enhanced_mesh_bus", return_value=mock_mesh_bus), \
         patch("simp.mesh.packet.create_event_packet"):

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"agent_id": "test_agent"})

        br = ProjectXMeshBridge(
            broker_url=mock_broker_url,
            agent_id="test_agent",
            computer=mock_computer,
            trust_graph=mock_trust_graph,
        )
        with patch("simp.projectx.mesh_bridge.threading.Thread"):
            first = br.start()
            second = br.start()

        assert first is True
        assert second is True
        assert br._running is True


# ---------------------------------------------------------------------------
# Tests — send_message / _send_result
# ---------------------------------------------------------------------------

def test_mesh_bridge_send_message_publishes_result(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """
    _send_result publishes to the mesh bus on RESULT_CHANNEL with correct
    sender_id, recipient_id, and payload fields.
    """
    for br, mock_create_pkt in make_bridge(
        mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus
    ):
        task = ProjectXTask(
            task_id="t-1",
            action="get_screenshot",
            requester_id="requester",
        )
        br._send_result(task, success=True, data={"url": "screenshot.png"})

        mock_create_pkt.assert_called_once()
        _, call_kwargs = mock_create_pkt.call_args
        assert call_kwargs["sender_id"] == br.agent_id
        assert call_kwargs["recipient_id"] == "requester"
        assert call_kwargs["channel"] == RESULT_CHANNEL

        payload = call_kwargs["payload"]
        assert payload["task_id"] == "t-1"
        assert payload["success"] is True
        assert payload["data"]["url"] == "screenshot.png"

        mock_mesh_bus.send.assert_called_once()


def test_mesh_bridge_send_message_failure_payload(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """Error details are included in the failure payload."""
    for br, mock_create_pkt in make_bridge(
        mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus
    ):
        task = ProjectXTask(
            task_id="t-2",
            action="get_screenshot",
            requester_id="requester",
        )
        br._send_result(task, success=False, error="Permission denied")

        _, call_kwargs = mock_create_pkt.call_args
        payload = call_kwargs["payload"]
        assert payload["success"] is False
        assert payload["error"] == "Permission denied"


# ---------------------------------------------------------------------------
# Tests — receive_message / _execute_task
# ---------------------------------------------------------------------------

def test_mesh_bridge_receive_message_allowed_action(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """An inbound task with an allowed action executes and increments stats."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        mock_computer.safe_execute.reset_mock()
        mock_computer.safe_execute.return_value = {"success": True, "data": {"result": 42}}

        pkt = make_mock_packet(make_task_payload(
            task_id="t-3",
            action="get_screenshot",
            requester_id="client",
        ))
        br._execute_task(pkt)

        assert br._stats["tasks_completed"] == 1
        mock_computer.safe_execute.assert_called_once()
        call_step = mock_computer.safe_execute.call_args[0][0]
        assert call_step["action"] == "get_screenshot"


def test_mesh_bridge_receive_message_denied_action(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """An inbound task with a disallowed (tier-3) action is denied."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        pkt = make_mock_packet(make_task_payload(
            task_id="t-4",
            action="run_shell",
            requester_id="client",
        ))
        br._execute_task(pkt)

        assert br._stats["tasks_denied"] == 1
        mock_computer.safe_execute.assert_not_called()


def test_mesh_bridge_receive_message_trust_gate_denied(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """Tier-1 actions are denied when requester trust is below the floor."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        mock_trust_graph.get_effective_score = MagicMock(return_value=1.0)

        pkt = make_mock_packet(make_task_payload(
            task_id="t-5",
            action="click",
            requester_id="low_trust_client",
        ))
        br._execute_task(pkt)

        assert br._stats["tasks_denied"] == 1
        mock_computer.safe_execute.assert_not_called()


def test_mesh_bridge_receive_message_trust_gate_allowed(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """
    Tier-1 actions succeed when requester trust meets the floor.
    sync_knowledge is in REMOTE_ALLOWED_ACTIONS, so we patch ACTION_TIERS
    to give it tier-1 (trust-gated) to exercise the trust gate path.
    """
    import simp.projectx.mesh_bridge as mb_module

    # Patch sync_knowledge → tier-1 so the trust gate is hit
    fake_tiers = dict(mb_module.ACTION_TIERS)
    fake_tiers["sync_knowledge"] = 1

    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        with patch("simp.projectx.mesh_bridge.ACTION_TIERS", fake_tiers):
            mock_computer.safe_execute.return_value = {"success": True}
            mock_trust_graph.get_effective_score = MagicMock(return_value=5.0)

            pkt = make_mock_packet(make_task_payload(
                task_id="t-6",
                action="sync_knowledge",
                requester_id="trusted_client",
            ))
            br._execute_task(pkt)

            assert br._stats["tasks_completed"] == 1
            mock_computer.safe_execute.assert_called_once()


def test_mesh_bridge_receive_message_task_from_dict(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """A task parsed from a dict via ProjectXTask.from_dict works end-to-end."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        mock_computer.safe_execute.return_value = {"success": True, "data": {}}

        pkt = make_mock_packet({
            "task_id": "t-7",
            "action": "get_active_window",
            "params": {},
            "requester_id": "ctrl",
            "priority": "high",
            "timeout": 60,
            "trust_required": 0.0,
        })
        br._execute_task(pkt)

        assert br._stats["tasks_completed"] == 1


# ---------------------------------------------------------------------------
# Tests — Routing
# ---------------------------------------------------------------------------

def test_mesh_bridge_routing_task_to_result_channel(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """_send_result routes results to RESULT_CHANNEL."""
    for br, mock_create_pkt in make_bridge(
        mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus
    ):
        task = ProjectXTask(
            task_id="r-1",
            action="sync_knowledge",
            requester_id="router_test",
        )
        br._send_result(task, success=True, data={})

        _, call_kwargs = mock_create_pkt.call_args
        assert call_kwargs["channel"] == RESULT_CHANNEL


def test_mesh_bridge_routing_broadcast_when_no_requester(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """When requester_id is empty, results are sent to wildcard '*'."""
    for br, mock_create_pkt in make_bridge(
        mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus
    ):
        task = ProjectXTask(
            task_id="r-2",
            action="sync_knowledge",
            requester_id="",
        )
        br._send_result(task, success=True, data={})

        _, call_kwargs = mock_create_pkt.call_args
        assert call_kwargs["recipient_id"] == "*"


def test_mesh_bridge_routing_action_permits_tier0(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """Tier-0 actions (not in ACTION_TIERS) are allowed without a trust check."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        mock_computer.safe_execute.return_value = {"success": True}

        pkt = make_mock_packet(make_task_payload(
            task_id="r-3",
            action="snapshot_state",
            requester_id="anyone",
        ))
        br._execute_task(pkt)

        assert br._stats["tasks_completed"] == 1


def test_mesh_bridge_routing_trust_graph_fallback(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """When trust_graph is None, trust defaults to 1.0 (denies tier-1/2)."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        br._trust_graph = None

        pkt = make_mock_packet(make_task_payload(
            task_id="r-4",
            action="click",
            requester_id="no_graph",
        ))
        br._execute_task(pkt)

        # No trust graph → default 1.0 < TIER1_TRUST_FLOOR 3.0 → denied
        assert br._stats["tasks_denied"] == 1


def test_mesh_bridge_routing_unknown_action_denied(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """Actions not in REMOTE_ALLOWED_ACTIONS are always denied."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        mock_computer.safe_execute.return_value = {"success": True}

        pkt = make_mock_packet(make_task_payload(
            task_id="r-5",
            action="unknown_action",
            requester_id="anyone",
        ))
        br._execute_task(pkt)

        assert br._stats["tasks_denied"] == 1
        mock_computer.safe_execute.assert_not_called()


# ---------------------------------------------------------------------------
# Tests — Disconnect / stop
# ---------------------------------------------------------------------------

def test_mesh_bridge_disconnect_stops_running_flag(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """stop() sets _running to False."""
    with patch("simp.projectx.mesh_bridge.requests.post"), \
         patch("simp.mesh.enhanced_bus.get_enhanced_mesh_bus", return_value=mock_mesh_bus), \
         patch("simp.mesh.packet.create_event_packet"):

        br = ProjectXMeshBridge(
            broker_url=mock_broker_url,
            agent_id="test_agent",
            computer=mock_computer,
            trust_graph=mock_trust_graph,
        )
        br._running = True

        br.stop()
        assert br._running is False


def test_mesh_bridge_disconnect_multiple_calls_safe(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """Calling stop() multiple times does not raise."""
    with patch("simp.projectx.mesh_bridge.requests.post"), \
         patch("simp.mesh.enhanced_bus.get_enhanced_mesh_bus", return_value=mock_mesh_bus), \
         patch("simp.mesh.packet.create_event_packet"):

        br = ProjectXMeshBridge(
            broker_url=mock_broker_url,
            agent_id="test_agent",
            computer=mock_computer,
            trust_graph=mock_trust_graph,
        )
        br._running = True
        br.stop()
        br.stop()  # must not raise
        assert br._running is False


def test_mesh_bridge_disconnect_idempotent(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """stop() is safe to call after the bridge has already stopped."""
    with patch("simp.projectx.mesh_bridge.requests.post"), \
         patch("simp.mesh.enhanced_bus.get_enhanced_mesh_bus", return_value=mock_mesh_bus), \
         patch("simp.mesh.packet.create_event_packet"):

        br = ProjectXMeshBridge(
            broker_url=mock_broker_url,
            agent_id="test_agent",
            computer=mock_computer,
            trust_graph=mock_trust_graph,
        )
        br._running = True
        br.stop()
        br._running = False
        br.stop()  # must not raise


# ---------------------------------------------------------------------------
# Tests — Introspection
# ---------------------------------------------------------------------------

def test_get_status_returns_expected_fields(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """get_status() exposes all expected keys."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        status = br.get_status()

        assert "agent_id" in status
        assert "running" in status
        assert "registered" in status
        assert "broker_url" in status
        assert "stats" in status
        assert "computer" in status
        assert status["agent_id"] == br.agent_id


def test_get_status_reflects_live_stats(
    mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus,
):
    """Stats in get_status() match live _stats after task execution."""
    for br, _ in make_bridge(mock_broker_url, mock_computer, mock_trust_graph, mock_mesh_bus):
        mock_computer.safe_execute.return_value = {"success": True, "data": {}}

        pkt = make_mock_packet(make_task_payload(
            task_id="s-1",
            action="get_screenshot",
            requester_id="client",
        ))
        br._execute_task(pkt)

        status = br.get_status()
        assert status["stats"]["tasks_completed"] == 1


# ---------------------------------------------------------------------------
# Tests — Singleton factory
# ---------------------------------------------------------------------------

def test_singleton_factory_creates_instance(mock_broker_url, mock_trust_graph):
    """get_projectx_mesh_bridge returns a bridge and starts it."""
    import simp.projectx.mesh_bridge as mb_module

    mb_module._bridge_instance = None  # reset between tests

    with patch.object(mb_module, "ProjectXMeshBridge") as MockBridge, \
         patch("simp.projectx.mesh_bridge.requests.post"), \
         patch("simp.mesh.enhanced_bus.get_enhanced_mesh_bus"), \
         patch("simp.mesh.packet.create_event_packet"):

        mock_instance = MagicMock()
        MockBridge.return_value = mock_instance

        bridge = get_projectx_mesh_bridge(
            broker_url=mock_broker_url,
            agent_id="singleton_test",
            trust_graph=mock_trust_graph,
        )

        assert bridge is mock_instance
        mock_instance.start.assert_called_once()

    mb_module._bridge_instance = None


# ---------------------------------------------------------------------------
# Tests — Task dataclass round-trip
# ---------------------------------------------------------------------------

def test_projectx_task_to_dict_roundtrip():
    """ProjectXTask serializes and deserializes without data loss."""
    original = ProjectXTask(
        task_id="roundtrip-1",
        action="update_knowledge",
        params={"key": "value"},
        requester_id="agent_x",
        priority="high",
        timeout=120,
        trust_required=2.5,
    )

    restored = ProjectXTask.from_dict(original.to_dict())

    assert restored.task_id == original.task_id
    assert restored.action == original.action
    assert restored.params == original.params
    assert restored.requester_id == original.requester_id
    assert restored.priority == original.priority
    assert restored.timeout == original.timeout
    assert restored.trust_required == original.trust_required


def test_projectx_task_from_dict_missing_fields_have_defaults():
    """from_dict fills in defaults for missing fields."""
    minimal = ProjectXTask.from_dict({"task_id": "min-1", "action": "log_action"})

    assert minimal.params == {}
    assert minimal.requester_id == ""
    assert minimal.priority == "normal"
    assert minimal.timeout == 30
    assert minimal.trust_required == 0.0
