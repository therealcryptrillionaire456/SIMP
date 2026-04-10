"""
SIMP A2A Compatibility — Sprints 2-6 tests.

Comprehensive tests for task_map (Sprint 2), capability_schema (Sprint 3),
discovery_cache (Sprint 4), lifecycle_map (Sprint 5), and compliance (Sprint 6).
"""

import json
import time
import uuid

import pytest

# Sprint 2
from simp.compat.task_map import (
    A2A_TO_SIMP_INTENT,
    translate_a2a_to_simp,
    validate_a2a_payload,
    simp_state_to_a2a,
    build_a2a_task_status,
    is_a2a_terminal,
)

# Sprint 3
from simp.compat.capability_schema import (
    StructuredCapability,
    normalise_capabilities,
    capabilities_to_a2a_skills,
)

# Sprint 4
from simp.compat.discovery_cache import (
    CardCache,
    CompatError,
    CompatErrorCode,
    validate_agent_card,
)

# Sprint 5
from simp.compat.lifecycle_map import (
    SimpLifecycleState,
    A2ATaskState,
    simp_to_a2a_state,
    is_terminal,
    is_non_terminal,
    build_progress_event,
    build_completion_event,
    build_failure_event,
    events_from_intent_history,
)


# ===================================================================
# Sprint 2 — task_map
# ===================================================================

class TestTaskMap:
    def test_translate_planning(self):
        t, err = translate_a2a_to_simp("planning")
        assert t == "planning"
        assert err is None

    def test_translate_research(self):
        t, err = translate_a2a_to_simp("research")
        assert t == "research"
        assert err is None

    def test_translate_code_task(self):
        t, _ = translate_a2a_to_simp("code_task")
        assert t == "code_task"

    def test_translate_status_check(self):
        t, _ = translate_a2a_to_simp("status_check")
        assert t == "status_check"

    def test_translate_capability_query(self):
        t, _ = translate_a2a_to_simp("capability_query")
        assert t == "capability_query"

    def test_translate_ping(self):
        t, _ = translate_a2a_to_simp("ping")
        assert t == "ping"

    def test_translate_health_check(self):
        t, _ = translate_a2a_to_simp("health_check")
        assert t == "native_agent_health_check"

    def test_translate_task_audit(self):
        t, _ = translate_a2a_to_simp("task_audit")
        assert t == "native_agent_task_audit"

    def test_translate_security_audit(self):
        t, _ = translate_a2a_to_simp("security_audit")
        assert t == "native_agent_security_audit"

    def test_translate_repo_scan(self):
        t, _ = translate_a2a_to_simp("repo_scan")
        assert t == "native_agent_repo_scan"

    def test_translate_alias_plan(self):
        t, _ = translate_a2a_to_simp("plan")
        assert t == "planning"

    def test_translate_alias_analyze(self):
        t, _ = translate_a2a_to_simp("analyze")
        assert t == "research"

    def test_translate_alias_code(self):
        t, _ = translate_a2a_to_simp("code")
        assert t == "code_task"

    def test_translate_alias_health(self):
        t, _ = translate_a2a_to_simp("health")
        assert t == "native_agent_health_check"

    def test_translate_unknown_errors(self):
        t, err = translate_a2a_to_simp("not_a_real_type")
        assert t == ""
        assert err is not None

    def test_validate_payload_valid(self):
        ok, err = validate_a2a_payload({"task_type": "planning"})
        assert ok is True

    def test_validate_payload_missing_type(self):
        ok, err = validate_a2a_payload({"input": {}})
        assert ok is False

    def test_validate_payload_not_dict(self):
        ok, err = validate_a2a_payload("not a dict")
        assert ok is False

    def test_validate_payload_type_not_string(self):
        ok, err = validate_a2a_payload({"task_type": 123})
        assert ok is False

    def test_simp_state_pending(self):
        assert simp_state_to_a2a("pending") == "submitted"

    def test_simp_state_executing(self):
        assert simp_state_to_a2a("executing") == "working"

    def test_simp_state_completed(self):
        assert simp_state_to_a2a("completed") == "completed"

    def test_simp_state_failed(self):
        assert simp_state_to_a2a("failed") == "failed"

    def test_simp_state_unknown(self):
        assert simp_state_to_a2a("xyz") == "unknown"

    def test_build_a2a_task_status(self):
        s = build_a2a_task_status("t1", "pending", intent_type="planning")
        assert s["taskId"] == "t1"
        assert s["state"] == "submitted"
        assert s["terminal"] is False
        assert "x-simp" in s

    def test_is_a2a_terminal(self):
        assert is_a2a_terminal("completed") is True
        assert is_a2a_terminal("failed") is True
        assert is_a2a_terminal("working") is False

    def test_a2a_to_simp_expected_keys(self):
        assert "planning" in A2A_TO_SIMP_INTENT
        assert "health_check" in A2A_TO_SIMP_INTENT


# ===================================================================
# Sprint 3 — capability_schema
# ===================================================================

class TestCapabilitySchema:
    def test_structured_capability_init(self):
        cap = StructuredCapability(id="planning")
        assert cap.name == "Task Planning"
        assert "plans" in cap.description.lower() or "plan" in cap.description.lower()

    def test_to_a2a_skill(self):
        cap = StructuredCapability(id="planning")
        skill = cap.to_a2a_skill()
        assert skill["id"] == "planning"
        assert skill["name"] == "Task Planning"

    def test_from_dict_roundtrip(self):
        cap = StructuredCapability(id="test", name="Test", description="Desc", tags=["t"])
        d = cap.to_a2a_skill()
        cap2 = StructuredCapability.from_dict(d)
        assert cap2.id == "test"
        assert cap2.name == "Test"

    def test_normalise_none(self):
        assert normalise_capabilities(None) == []

    def test_normalise_empty_list(self):
        assert normalise_capabilities([]) == []

    def test_normalise_csv_string(self):
        caps = normalise_capabilities("code_task,research")
        assert len(caps) == 2
        assert caps[0].id == "code_task"

    def test_normalise_list_of_strings(self):
        caps = normalise_capabilities(["planning", "ping"])
        assert len(caps) == 2

    def test_normalise_list_of_dicts(self):
        caps = normalise_capabilities([{"id": "custom", "name": "Custom"}])
        assert len(caps) == 1
        assert caps[0].name == "Custom"

    def test_well_known_enrichment(self):
        cap = StructuredCapability(id="native_agent_health_check")
        assert cap.name == "Health Check"

    def test_deduplication(self):
        caps = normalise_capabilities(["ping", "ping", "ping"])
        assert len(caps) == 1

    def test_capabilities_to_a2a_skills(self):
        skills = capabilities_to_a2a_skills(["planning", "research"])
        assert len(skills) == 2
        assert all(isinstance(s, dict) for s in skills)


# ===================================================================
# Sprint 4 — discovery_cache
# ===================================================================

class TestDiscoveryCache:
    def test_store_and_retrieve(self):
        cache = CardCache(agent_ttl=60)
        cache.put("a1", {"name": "Agent1"})
        assert cache.get("a1") == {"name": "Agent1"}

    def test_cache_miss(self):
        cache = CardCache()
        assert cache.get("nonexistent") is None

    def test_cache_expiry(self):
        cache = CardCache(agent_ttl=0)
        cache.put("a1", {"name": "Agent1"})
        time.sleep(0.01)
        assert cache.get("a1") is None

    def test_invalidate(self):
        cache = CardCache()
        cache.put("a1", {"name": "Agent1"})
        cache.invalidate("a1")
        assert cache.get("a1") is None

    def test_clear(self):
        cache = CardCache()
        cache.put("a1", {"name": "Agent1"})
        cache.clear()
        assert cache.get("a1") is None

    def test_stats(self):
        cache = CardCache()
        cache.put("a1", {"name": "Agent1"})
        cache.get("a1")
        cache.get("miss")
        s = cache.stats()
        assert s["entries"] == 1
        assert s["hits"] >= 1
        assert s["misses"] >= 1


class TestCompatError:
    def test_http_status_invalid_card(self):
        e = CompatError(CompatErrorCode.INVALID_CARD, "bad card")
        assert e.http_status == 400

    def test_http_status_not_found(self):
        e = CompatError(CompatErrorCode.CARD_NOT_FOUND)
        assert e.http_status == 404

    def test_http_status_rate_limited(self):
        e = CompatError(CompatErrorCode.RATE_LIMITED)
        assert e.http_status == 429

    def test_to_dict(self):
        e = CompatError(CompatErrorCode.VALIDATION_ERROR, "oops")
        d = e.to_dict()
        assert d["error"] is True
        assert d["code"] == "validation_error"
        assert d["message"] == "oops"


class TestValidateAgentCard:
    def test_valid_card(self):
        ok, err = validate_agent_card({"name": "A", "version": "1.0", "url": "http://x"})
        assert ok is True

    def test_missing_name(self):
        ok, err = validate_agent_card({"version": "1.0", "url": "http://x"})
        assert ok is False
        assert "name" in err

    def test_not_dict(self):
        ok, err = validate_agent_card("not a dict")
        assert ok is False

    def test_wrong_type(self):
        ok, err = validate_agent_card({"name": 123, "version": "1.0", "url": "http://x"})
        assert ok is False


# ===================================================================
# Sprint 5 — lifecycle_map
# ===================================================================

class TestLifecycleMap:
    def test_state_constants(self):
        assert SimpLifecycleState.PENDING == "pending"
        assert A2ATaskState.SUBMITTED == "submitted"

    def test_pending_to_submitted(self):
        assert simp_to_a2a_state("pending") == "submitted"

    def test_executing_to_working(self):
        assert simp_to_a2a_state("executing") == "working"

    def test_completed_to_completed(self):
        assert simp_to_a2a_state("completed") == "completed"

    def test_failed_to_failed(self):
        assert simp_to_a2a_state("failed") == "failed"

    def test_queued_to_submitted(self):
        assert simp_to_a2a_state("queued") == "submitted"

    def test_in_progress_to_working(self):
        assert simp_to_a2a_state("in_progress") == "working"

    def test_blocked_to_input_required(self):
        assert simp_to_a2a_state("blocked") == "input-required"

    def test_unknown(self):
        assert simp_to_a2a_state("unknown") == "unknown"

    def test_delivery_status_refinement(self):
        assert simp_to_a2a_state("executing", "delivery_failed") == "failed"

    def test_delivery_no_override_terminal(self):
        # completed should not be overridden by delivery_failed
        assert simp_to_a2a_state("completed", "delivery_failed") == "completed"

    def test_is_terminal(self):
        assert is_terminal("completed") is True
        assert is_terminal("failed") is True
        assert is_terminal("canceled") is True

    def test_is_non_terminal(self):
        assert is_non_terminal("working") is True
        assert is_non_terminal("submitted") is True


class TestEventEnvelopes:
    def test_progress_event_fields(self):
        ev = build_progress_event("t1", "executing", "code_task")
        assert ev["taskId"] == "t1"
        assert ev["state"] == "working"
        assert ev["terminal"] is False
        assert "x-simp" in ev
        assert ev["x-simp"]["simpState"] == "executing"

    def test_progress_event_redacts_sensitive(self):
        ev = build_progress_event("t1", "executing", data={"api_key": "secret123"})
        assert ev["data"]["api_key"] == "[REDACTED]"

    def test_progress_event_truncates(self):
        ev = build_progress_event("t1", "executing", data={"long": "x" * 500})
        assert len(ev["data"]["long"]) < 250

    def test_completion_event(self):
        ev = build_completion_event("t1", result={"ok": True})
        assert ev["state"] == "completed"
        assert ev["terminal"] is True
        assert ev["eventKind"] == "completed"

    def test_failure_event(self):
        ev = build_failure_event("t1", error="boom")
        assert ev["state"] == "failed"
        assert ev["terminal"] is True
        assert ev["eventKind"] == "error"

    def test_failure_event_truncates_error(self):
        ev = build_failure_event("t1", error="E" * 500)
        assert len(ev["error"]) < 250

    def test_events_from_empty_history(self):
        assert events_from_intent_history([]) == []

    def test_events_from_completed(self):
        records = [{"intent_id": "i1", "status": "completed", "intent_type": "ping"}]
        evs = events_from_intent_history(records)
        assert len(evs) == 1
        assert evs[0]["state"] == "completed"

    def test_events_from_failed(self):
        records = [{"intent_id": "i1", "status": "failed", "error": "oops"}]
        evs = events_from_intent_history(records)
        assert evs[0]["state"] == "failed"

    def test_events_from_mixed(self):
        records = [
            {"intent_id": "i1", "status": "pending"},
            {"intent_id": "i2", "status": "completed"},
        ]
        evs = events_from_intent_history(records)
        assert len(evs) == 2


# ===================================================================
# Sprint 6 — compliance
# ===================================================================

class TestComplianceSprint6:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        import os
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_oversized_payload_rejected(self, client):
        big = json.dumps({"task_type": "planning", "data": "x" * 70000})
        resp = client.post(
            "/a2a/tasks",
            data=big,
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_card_output_stability(self, client):
        r1 = client.get("/.well-known/agent-card.json")
        r2 = client.get("/.well-known/agent-card.json")
        d1 = json.loads(r1.data)
        d2 = json.loads(r2.data)
        # Structure should match (timestamps may differ)
        assert d1["name"] == d2["name"]
        assert d1["version"] == d2["version"]

    def test_no_secrets_in_card(self, client):
        resp = client.get("/.well-known/agent-card.json")
        raw = resp.data.decode()
        assert "sk-" not in raw
        assert "password" not in raw.lower() or "noCredentialStorage" in raw
