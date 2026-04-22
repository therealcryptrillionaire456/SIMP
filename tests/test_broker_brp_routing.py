import asyncio

from simp.security.brp_bridge import BRPBridge
from simp.security.brp_models import BRPMode


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _StubMeshRouting:
    def __init__(self, mode: str = "preferred"):
        self.config = type(
            "Config",
            (),
            {"mode": type("Mode", (), {"value": mode})()},
        )()
        self.route_calls = 0

    def can_route_via_mesh(self, source_agent, target_agent, intent_type):
        return True, None

    def route_via_mesh(self, source_agent, target_agent, intent_type, payload):
        self.route_calls += 1
        return {
            "success": True,
            "mesh_routed": True,
            "mesh_intent_id": "mesh-intent-1",
        }


def test_route_intent_surfaces_brp_review_and_skips_mesh_when_elevated(broker, tmp_path):
    broker.resume()
    broker.config.inbox_base_dir = str(tmp_path / "inboxes")
    broker.brp_bridge = BRPBridge(
        data_dir=str(tmp_path / "brp"),
        default_mode=BRPMode.ADVISORY.value,
    )
    broker.mesh_routing = _StubMeshRouting(mode="preferred")
    broker.register_agent("ops_agent", "test", "(file-based)")

    result = _run(
        broker.route_intent(
            {
                "intent_id": "intent-brp-elevate-1",
                "source_agent": "projectx_native",
                "target_agent": "ops_agent",
                "intent_type": "planning",
                "params": {"steps": [{"action": "trade_buy"}, {"action": "withdrawal"}]},
            }
        )
    )

    assert result["status"] == "routed"
    assert result["delivery_status"] == "queued_no_endpoint"
    assert result["brp_plan_review"]["decision"] == "ELEVATE"
    assert result["brp_plan_review_required"] is True
    assert result["mesh_routing"]["brp_blocked"] is True
    assert result["mesh_routing"]["review_required"] is True
    assert result["mesh_routing"]["error_code"] == "BRP_REVIEW_REQUIRED"
    assert broker.mesh_routing.route_calls == 0


def test_route_intent_returns_policy_error_when_brp_requires_review(broker, tmp_path):
    class _StubProjectX:
        def safe_execute(self, step):
            return {"success": True, "step": step}

    broker.resume()
    broker.config.inbox_base_dir = str(tmp_path / "inboxes")
    broker.brp_bridge = BRPBridge(
        data_dir=str(tmp_path / "brp"),
        default_mode=BRPMode.ENFORCED.value,
    )
    broker.mesh_routing = None
    broker._projectx = _StubProjectX()

    result = _run(
        broker.route_intent(
            {
                "intent_id": "intent-brp-deny-1",
                "source_agent": "projectx_native",
                "target_agent": "projectx_native",
                "intent_type": "computer_use",
                "params": {"steps": [{"action": "withdrawal"}]},
            }
        )
    )

    assert result["status"] == "error"
    assert result["error_code"] == "BRP_REVIEW_REQUIRED"
    assert result["brp_plan_review"]["decision"] == "ELEVATE"
    assert not (tmp_path / "inboxes" / "ops_agent").exists()


def test_route_intent_includes_brp_plan_review_for_multi_step_intent(broker, tmp_path):
    broker.resume()
    broker.config.inbox_base_dir = str(tmp_path / "inboxes")
    broker.brp_bridge = BRPBridge(
        data_dir=str(tmp_path / "brp"),
        default_mode=BRPMode.ADVISORY.value,
    )
    broker.mesh_routing = None
    broker.register_agent("ops_agent", "test", "(file-based)")

    result = _run(
        broker.route_intent(
            {
                "intent_id": "intent-brp-plan-1",
                "source_agent": "mother_goose",
                "target_agent": "ops_agent",
                "intent_type": "planning",
                "params": {"steps": [{"action": "trade_buy"}, {"action": "withdrawal"}]},
            }
        )
    )

    assert result["status"] == "routed"
    assert result["brp_plan_review"]["decision"] == "ELEVATE"
    assert result["brp_plan_review_required"] is True
    assert result["brp_plan_review"]["incident"]["incident_state"] in {"open", "reopened"}


def test_computer_use_review_required_blocks_projectx_execution(broker, tmp_path):
    class _StubProjectX:
        def __init__(self):
            self.calls = 0

        def safe_execute(self, step):
            self.calls += 1
            return {"success": True, "step": step}

    broker.resume()
    broker.config.inbox_base_dir = str(tmp_path / "inboxes")
    broker.brp_bridge = BRPBridge(
        data_dir=str(tmp_path / "brp"),
        default_mode=BRPMode.ADVISORY.value,
    )
    broker.mesh_routing = None
    broker._projectx = _StubProjectX()

    result = _run(
        broker.route_intent(
            {
                "intent_id": "intent-brp-computer-1",
                "source_agent": "projectx_native",
                "target_agent": "projectx_native",
                "intent_type": "computer_use",
                "params": {"steps": [{"action": "withdrawal"}]},
            }
        )
    )

    assert result["status"] == "error"
    assert result["error_code"] == "BRP_REVIEW_REQUIRED"
    assert result["brp_plan_review_required"] is True
    assert broker._projectx.calls == 0
