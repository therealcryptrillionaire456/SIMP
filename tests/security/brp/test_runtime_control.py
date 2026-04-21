from pathlib import Path

from simp.security.brp import DeterministicRecurrentController, NamespacedRuntimeCache
from simp.security.brp.atomic_state_checkpointing import (
    load_checkpoint_payload,
    save_checkpoint_payload,
)


def test_deterministic_controller_is_stable_for_same_input():
    controller = DeterministicRecurrentController()
    evidence = {
        "threat_score": 0.58,
        "decision": "ALLOW",
        "predictive_boost": 0.12,
        "multimodal_boost": 0.08,
        "negative_observations": 2,
        "failed_remediations": 1,
        "completed_remediations": 0,
        "related_rules": 2,
        "restricted_action": False,
        "incident_state": "acknowledged",
        "reopen_count": 0,
    }

    first = controller.run(
        namespace="event:projectx_native:run_shell",
        cache_key="evt-1",
        evidence=evidence,
    )
    second = controller.run(
        namespace="event:projectx_native:run_shell",
        cache_key="evt-1",
        evidence=evidence,
    )

    assert first["score_delta"] == second["score_delta"]
    assert first["confidence_delta"] == second["confidence_delta"]
    assert first["terminal_state"] == second["terminal_state"]
    assert first["controller_rounds"] == 3


def test_namespaced_cache_invalidates_without_cross_namespace_leak(tmp_path):
    cache = NamespacedRuntimeCache(checkpoint_path=Path(tmp_path) / "runtime_cache.json")
    cache.set("event:agent_a:run_shell", "evt-1", {"score_delta": 0.1})
    cache.set("plan:agent_a:run_shell", "plan-1", {"score_delta": 0.04})

    assert cache.get("event:agent_a:run_shell", "evt-1") == {"score_delta": 0.1}
    assert cache.get("plan:agent_a:run_shell", "plan-1") == {"score_delta": 0.04}

    cache.invalidate_namespace("event:agent_a:run_shell", reason="observation_update")

    assert cache.get("event:agent_a:run_shell", "evt-1") is None
    assert cache.get("plan:agent_a:run_shell", "plan-1") == {"score_delta": 0.04}


def test_atomic_checkpoint_round_trip_and_kind_validation(tmp_path):
    target = Path(tmp_path) / "incident_state.json"
    payload = {"alert-1": {"state": "open"}}
    save_checkpoint_payload(target, kind="incident_state", payload=payload)

    loaded = load_checkpoint_payload(target, default=None, expected_kind="incident_state")
    wrong_kind = load_checkpoint_payload(target, default={}, expected_kind="adaptive_rules")

    assert loaded == payload
    assert wrong_kind == {}
