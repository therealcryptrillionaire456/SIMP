"""
Sprint 55 — Protocol Conformance Tests

~50 tests covering:
- Broker behavior
- Delivery engine
- Routing engine
- Task ledger
- Intent format
- HTTP API
- A2A card invariants
- FinancialOps
- Orchestration
"""

import asyncio
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from simp.server.broker import SimpBroker, BrokerConfig, BrokerState, IntentRecord
from simp.server.delivery import (
    DeliveryConfig,
    DeliveryStatus,
    IntentDeliveryEngine,
)
from simp.server.task_ledger import LedgerConfig, TaskLedger
from simp.server.routing_engine import RoutingEngine, RoutingDecision
from simp.orchestration.orchestration_manager import (
    OrchestrationManager,
    OrchestrationStepStatus,
)
from simp.server.http_server import SimpHttpServer


def _run(coro):
    """Helper to run async coroutines in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =========================================================================
# SECTION 1 — Broker behavior conformance
# =========================================================================


class TestBrokerBehaviorConformance(unittest.TestCase):

    def setUp(self):
        self.broker = SimpBroker(BrokerConfig())

    def test_broker_starts_in_initializing_state(self):
        assert self.broker.state == BrokerState.INITIALIZING

    def test_broker_state_transitions(self):
        self.broker.start()
        assert self.broker.state == BrokerState.RUNNING
        self.broker.pause()
        assert self.broker.state == BrokerState.PAUSED
        self.broker.resume()
        assert self.broker.state == BrokerState.RUNNING
        self.broker.stop()
        assert self.broker.state == BrokerState.STOPPED

    def test_register_agent_returns_bool(self):
        result = self.broker.register_agent("a:001", "test", "http://localhost:5001")
        assert result is True

    def test_register_duplicate_fails(self):
        self.broker.register_agent("a:001", "test", "http://localhost:5001")
        result = self.broker.register_agent("a:001", "test", "http://localhost:5001")
        assert result is False

    def test_deregister_unknown_agent_returns_false(self):
        assert self.broker.deregister_agent("nonexistent") is False

    def test_intent_record_has_delivery_fields(self):
        rec = IntentRecord(
            intent_id="i1", source_agent="s", target_agent="t",
            intent_type="test", timestamp="now", status="pending",
        )
        assert hasattr(rec, "delivery_status")
        assert hasattr(rec, "delivery_attempts")
        assert hasattr(rec, "delivery_elapsed_ms")

    def test_route_intent_unknown_agent_returns_error(self):
        result = _run(self.broker.route_intent({
            "intent_id": "i1",
            "target_agent": "nonexistent",
        }))
        assert result["status"] == "error"
        assert result["error_code"] == "AGENT_NOT_FOUND"


# =========================================================================
# SECTION 2 — Delivery conformance
# =========================================================================


class TestDeliveryConformance(unittest.TestCase):

    def test_file_based_never_gets_http(self):
        engine = IntentDeliveryEngine()
        result = engine.deliver("agent:001 (file-based)", {"intent_id": "i1"})
        assert result.status == DeliveryStatus.FILE_BASED_SKIP
        assert result.attempts == 0

    def test_file_based_skip_is_valid_success(self):
        """FILE_BASED_SKIP is a valid success state, not an error."""
        assert DeliveryStatus.FILE_BASED_SKIP == "file_based_skip"

    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_delivery_posts_to_intent_path(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        engine = IntentDeliveryEngine()
        engine.deliver("http://localhost:5001", {"intent_id": "i1"})

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == "http://localhost:5001/intent"
        assert req.method == "POST"

    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_delivery_sends_json_content_type(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        engine = IntentDeliveryEngine()
        engine.deliver("http://localhost:5001", {"intent_id": "i1"})

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"


# =========================================================================
# SECTION 3 — Routing conformance
# =========================================================================


class TestRoutingConformance(unittest.TestCase):

    def test_explicit_target_always_wins(self):
        engine = RoutingEngine(policy_path="/nonexistent")
        decision = engine.resolve("any_type", "specific:agent", {})
        assert decision.target_agent == "specific:agent"
        assert decision.reason == "explicit"

    def test_auto_target_uses_policy(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "policy.json")
        with open(path, "w") as f:
            json.dump({"rules": [{"intent_type": "ping", "primary_agent": "a:001"}]}, f)
        engine = RoutingEngine(policy_path=path)
        decision = engine.resolve("ping", "auto", {"a:001": {}})
        assert decision.target_agent == "a:001"
        assert decision.reason == "policy_primary"

    def test_none_target_uses_policy(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "policy.json")
        with open(path, "w") as f:
            json.dump({"rules": [{"intent_type": "ping", "primary_agent": "a:001"}]}, f)
        engine = RoutingEngine(policy_path=path)
        decision = engine.resolve("ping", None, {"a:001": {}})
        assert decision.target_agent == "a:001"

    def test_resolution_order(self):
        """Explicit → policy → fallback → capability → none."""
        engine = RoutingEngine(policy_path="/nonexistent")
        # Explicit overrides all
        d = engine.resolve("x", "explicit:001", {"policy:001": {}})
        assert d.reason == "explicit"


# =========================================================================
# SECTION 4 — Task ledger conformance
# =========================================================================


class TestTaskLedgerConformance(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "ledger.jsonl")
        self.ledger = TaskLedger(LedgerConfig(path=self.path))

    def test_append_only(self):
        """Ledger is append-only — records are never modified in place."""
        self.ledger.append({"intent_id": "i1", "status": "pending"})
        self.ledger.append({"intent_id": "i1", "status": "completed"})
        records = self.ledger.load_all()
        assert len(records) == 2  # Both records exist

    def test_append_adds_ledger_ts(self):
        self.ledger.append({"intent_id": "i1"})
        records = self.ledger.load_all()
        assert "ledger_ts" in records[0]

    def test_corrupt_lines_skipped_silently(self):
        with open(self.path, "w") as f:
            f.write("NOT JSON\n")
            f.write('{"intent_id": "i1", "status": "pending"}\n')
        pending = self.ledger.load_pending()
        assert len(pending) == 1


# =========================================================================
# SECTION 5 — Intent format conformance
# =========================================================================


class TestIntentFormatConformance(unittest.TestCase):

    def test_route_intent_returns_intent_id(self):
        broker = SimpBroker()
        broker.register_agent("a:001", "test", "(file-based)")
        result = _run(broker.route_intent({
            "intent_id": "custom-id",
            "target_agent": "a:001",
        }))
        assert result["intent_id"] == "custom-id"

    def test_route_intent_generates_id_if_missing(self):
        broker = SimpBroker()
        broker.register_agent("a:001", "test", "(file-based)")
        result = _run(broker.route_intent({"target_agent": "a:001"}))
        assert "intent_id" in result
        assert len(result["intent_id"]) > 0

    def test_route_intent_has_timestamp(self):
        broker = SimpBroker()
        broker.register_agent("a:001", "test", "(file-based)")
        result = _run(broker.route_intent({
            "intent_id": "i1",
            "target_agent": "a:001",
        }))
        assert "timestamp" in result

    def test_route_intent_has_delivery_status(self):
        broker = SimpBroker()
        broker.register_agent("a:001", "test", "(file-based)")
        result = _run(broker.route_intent({
            "intent_id": "i1",
            "target_agent": "a:001",
        }))
        assert "delivery_status" in result


# =========================================================================
# SECTION 6 — HTTP API conformance
# =========================================================================


class TestHTTPAPIConformance(unittest.TestCase):

    def setUp(self):
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        self.server = SimpHttpServer(BrokerConfig(), debug=False)
        self.client = self.server.app.test_client()

    def test_health_returns_200(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200

    def test_stats_returns_stats(self):
        resp = self.client.get("/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stats" in data
        assert "task_ledger" in data["stats"]

    def test_register_agent_201(self):
        resp = self.client.post("/agents/register", json={
            "agent_id": "t:001",
            "agent_type": "test",
            "endpoint": "http://localhost:9999",
        })
        assert resp.status_code == 201

    def test_routing_policy_endpoint(self):
        resp = self.client.get("/routing-policy")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "routing_policy" in data

    def test_reload_routing_policy_endpoint(self):
        resp = self.client.post("/reload-routing-policy")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "rule_count" in data

    def test_orchestration_create_plan(self):
        resp = self.client.post("/orchestration/plans", json={
            "name": "Test Plan",
            "steps": [{"name": "S1", "intent_type": "ping"}],
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "created"

    def test_orchestration_list_plans(self):
        self.client.post("/orchestration/plans", json={
            "name": "P1",
            "steps": [{"name": "S1"}],
        })
        resp = self.client.get("/orchestration/plans")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] >= 1

    def test_orchestration_maintenance_template(self):
        resp = self.client.post("/orchestration/plans/maintenance")
        assert resp.status_code == 201

    def test_orchestration_demo_template(self):
        resp = self.client.post("/orchestration/plans/demo")
        assert resp.status_code == 201


# =========================================================================
# SECTION 7 — A2A card invariants
# =========================================================================


class TestA2ACardInvariants(unittest.TestCase):

    def setUp(self):
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        self.server = SimpHttpServer(BrokerConfig(), debug=False)
        self.client = self.server.app.test_client()

    def test_well_known_card_returns_json(self):
        resp = self.client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None

    def test_card_has_no_secrets(self):
        resp = self.client.get("/.well-known/agent-card.json")
        card_str = resp.get_data(as_text=True).lower()
        assert "api_key" not in card_str
        assert "secret" not in card_str
        assert "password" not in card_str

    def test_financial_ops_card_exists(self):
        resp = self.client.get("/a2a/agents/financial-ops/agent.json")
        assert resp.status_code == 200


# =========================================================================
# SECTION 8 — FinancialOps conformance
# =========================================================================


class TestFinancialOpsConformance(unittest.TestCase):

    def setUp(self):
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        self.server = SimpHttpServer(BrokerConfig(), debug=False)
        self.client = self.server.app.test_client()

    def test_financial_ops_task_returns_202(self):
        resp = self.client.post("/a2a/agents/financial-ops/tasks", json={
            "op_type": "small_purchase",
            "would_spend": 5.0,
        })
        assert resp.status_code == 202

    def test_financial_ops_no_credentials_exposed(self):
        resp = self.client.post("/a2a/agents/financial-ops/tasks", json={
            "op_type": "small_purchase",
            "would_spend": 5.0,
        })
        text = resp.get_data(as_text=True).lower()
        assert "stripe_key" not in text
        assert "sk_test" not in text

    def test_budget_endpoint_exists(self):
        resp = self.client.get("/a2a/agents/financial-ops/budget")
        assert resp.status_code == 200


# =========================================================================
# SECTION 9 — Orchestration conformance
# =========================================================================


class TestOrchestrationConformance(unittest.TestCase):

    def test_step_status_enum(self):
        assert OrchestrationStepStatus.PENDING.value == "pending"
        assert OrchestrationStepStatus.COMPLETED.value == "completed"
        assert OrchestrationStepStatus.FAILED.value == "failed"

    def test_plan_sequential_execution(self):
        mgr = OrchestrationManager(broker=None)
        plan = mgr.create_plan("Test", "", [
            {"name": "S1", "intent_type": "ping"},
            {"name": "S2", "intent_type": "analysis"},
            {"name": "S3", "intent_type": "research"},
        ])
        result = mgr.execute_plan(plan.plan_id)
        assert result.status == "completed"
        for s in result.steps:
            assert s.status == "completed"

    def test_plan_stops_on_failure(self):
        """When a step fails, subsequent steps should NOT execute."""
        mgr = OrchestrationManager(broker=None)
        plan = mgr.create_plan("Fail Test", "", [
            {"name": "S1"},
            {"name": "S2"},
            {"name": "S3"},
        ])
        # Monkey-patch _execute_step to fail on second step
        original = mgr._execute_step
        call_count = [0]

        def failing_step(step):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Step 2 failed")
            return original(step)

        mgr._execute_step = failing_step
        result = mgr.execute_plan(plan.plan_id)
        assert result.status == "failed"
        assert result.steps[0].status == "completed"
        assert result.steps[1].status == "failed"
        assert result.steps[2].status == "pending"  # Never ran


# =========================================================================
# SECTION 10 — Backward compatibility
# =========================================================================


class TestBackwardCompatibility(unittest.TestCase):
    """Ensure existing broker API is not broken."""

    def test_register_agent_signature_unchanged(self):
        broker = SimpBroker()
        result = broker.register_agent("a:001", "test", "http://localhost:5001", {"version": "1.0"})
        assert result is True

    def test_route_intent_still_async(self):
        broker = SimpBroker()
        broker.register_agent("a:001", "test", "(file-based)")
        # Must be awaitable
        coro = broker.route_intent({"intent_id": "i1", "target_agent": "a:001"})
        assert asyncio.iscoroutine(coro)
        result = _run(coro)
        assert result["status"] == "routed"

    def test_record_response_unchanged(self):
        broker = SimpBroker()
        broker.register_agent("a:001", "test", "(file-based)")
        _run(broker.route_intent({"intent_id": "i1", "target_agent": "a:001"}))
        result = broker.record_response("i1", {"data": "ok"}, 10.0)
        assert result is True

    def test_record_error_unchanged(self):
        broker = SimpBroker()
        broker.register_agent("a:001", "test", "(file-based)")
        _run(broker.route_intent({"intent_id": "i1", "target_agent": "a:001"}))
        result = broker.record_error("i1", "some error", 5.0)
        assert result is True

    def test_get_statistics_still_works(self):
        broker = SimpBroker()
        stats = broker.get_statistics()
        assert "intents_received" in stats
        assert "intents_routed" in stats
        assert "agents_online" in stats

    def test_health_check_still_works(self):
        broker = SimpBroker()
        health = broker.health_check()
        assert "status" in health
        assert "state" in health


if __name__ == "__main__":
    unittest.main()
