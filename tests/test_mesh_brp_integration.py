import json
import threading

from simp.security.brp_bridge import BRPBridge
from simp.security.brp_models import BRPEventType
from simp.server.mesh_routing import MeshRoutingConfig, MeshRoutingManager, MeshRoutingMode


class _StubMeshRouter:
    def __init__(self, mesh_intent_id: str = "mesh-intent-123"):
        self.mesh_intent_id = mesh_intent_id
        self.calls = []

    def route_intent(self, intent_type, target_agent=None, payload=None, stake_amount=0.0):
        self.calls.append(
            {
                "intent_type": intent_type,
                "target_agent": target_agent,
                "payload": payload,
                "stake_amount": stake_amount,
            }
        )
        return self.mesh_intent_id


def _build_manager(tmp_path, mesh_intent_id: str = "mesh-intent-123"):
    manager = MeshRoutingManager.__new__(MeshRoutingManager)
    manager.broker_id = "simp_broker"
    manager.config = MeshRoutingConfig(mode=MeshRoutingMode.PREFERRED, mesh_stake_amount=25.0)
    manager.brp_bridge = BRPBridge(data_dir=str(tmp_path / "brp"))
    manager.mesh_router = _StubMeshRouter(mesh_intent_id=mesh_intent_id)
    manager.mesh_agents = {
        "quantumarb_test": {
            "capabilities": ["trade_execution"],
            "channel_capacity": 250.0,
            "reputation_score": 0.82,
            "mesh_available": True,
        },
        "kashclaw_test": {
            "capabilities": ["trade_execution"],
            "channel_capacity": 800.0,
            "reputation_score": 0.18,
            "mesh_available": True,
        },
    }
    manager._lock = threading.Lock()
    return manager


def test_route_via_mesh_triggers_brp_event(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path)
    monkeypatch.setattr(manager, "_get_effective_trust_score", lambda agent_id: 1.2 if agent_id == "kashclaw_test" else 3.8)

    payload = {
        "intent_id": "mesh-test-1",
        "params": {"quantity": 5, "action": "BUY"},
        "brp_mode": "shadow",
    }

    result = manager.route_via_mesh(
        source_agent="quantumarb_test",
        target_agent="kashclaw_test",
        intent_type="trade_execution",
        payload=payload,
    )

    assert result["success"] is True
    assert result["mesh_intent_id"] == "mesh-intent-123"
    assert result["brp_evaluation"]["event_type"] == BRPEventType.MESH_INTENT.value
    assert "mesh_intent" in result["brp_evaluation"]["threat_tags"]
    assert "low_mesh_trust" in result["brp_evaluation"]["threat_tags"]
    assert "low_mesh_reputation" in result["brp_evaluation"]["threat_tags"]

    with open(tmp_path / "brp" / "events.jsonl", "r", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle]

    assert len(events) == 1
    assert events[0]["event_type"] == BRPEventType.MESH_INTENT.value
    assert events[0]["context"]["target_agent"] == "kashclaw_test"


def test_route_via_mesh_includes_brp_metadata_on_failure(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path, mesh_intent_id=None)
    monkeypatch.setattr(manager, "_get_effective_trust_score", lambda agent_id: 4.2)

    result = manager.route_via_mesh(
        source_agent="quantumarb_test",
        target_agent="kashclaw_test",
        intent_type="trade_execution",
        payload={"intent_id": "mesh-test-2", "params": {"quantity": 1}},
    )

    assert result["success"] is False
    assert result["brp_evaluation"]["event_type"] == BRPEventType.MESH_INTENT.value
    assert result["brp_evaluation"]["decision"] == "SHADOW_ALLOW"
