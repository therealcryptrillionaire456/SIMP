import json
from pathlib import Path

from quantum_advisory_broadcaster import QuantumAdvisoryBroadcaster


def test_collects_recommendations_from_broker_and_file(tmp_path):
    broadcaster = QuantumAdvisoryBroadcaster(
        inbox_dir=tmp_path / "inbox",
        processed_dir=tmp_path / "processed",
        receipts_path=tmp_path / "receipts.jsonl",
        registry_path=tmp_path / "agent_registry.jsonl",
        dry_run=True,
    )
    broadcaster.ensure_registered = lambda: True
    broadcaster._get_json = lambda url, **kwargs: {
        "status": "success",
        "messages": [{"payload": {"recommendation": {"recommendation_id": "broker-rec"}}}],
    }

    (broadcaster.inbox_dir / "file_rec.json").write_text(
        json.dumps({"recommendation_id": "file-rec"})
    )

    broker_recs = broadcaster.collect_from_broker()
    file_recs = broadcaster.collect_from_inbox()

    assert broker_recs[0]["recommendation_id"] == "broker-rec"
    assert file_recs[0]["recommendation_id"] == "file-rec"
    assert (broadcaster.processed_dir / "file_rec.json").exists()


def test_resolve_targets_by_capability():
    broadcaster = QuantumAdvisoryBroadcaster(dry_run=True)
    agents = [
        {"agent_id": "projectx_native", "capabilities": ["code_review", "maintenance"]},
        {"agent_id": "bullbear_predictor", "capabilities": ["prediction_signal"]},
    ]
    targets = broadcaster.resolve_targets({"target_capabilities": ["prediction_signal"]}, agents)
    assert [agent["agent_id"] for agent in targets] == ["bullbear_predictor"]


def test_dry_run_delivery_does_not_write_agent_inbox(tmp_path):
    broadcaster = QuantumAdvisoryBroadcaster(
        inbox_dir=tmp_path / "inbox",
        processed_dir=tmp_path / "processed",
        receipts_path=tmp_path / "receipts.jsonl",
        registry_path=tmp_path / "agent_registry.jsonl",
        dry_run=True,
    )
    receipt = broadcaster.deliver(
        {"recommendation_id": "rec-1"},
        {"agent_id": "gate4_real", "metadata": {"transport": "file", "inbox": str(tmp_path / "gate4")}},
    )
    assert receipt["status"] == "dry_run"
    assert not (tmp_path / "gate4").exists()


def test_delivery_retries_transient_broker_failure(tmp_path):
    broadcaster = QuantumAdvisoryBroadcaster(
        inbox_dir=tmp_path / "inbox",
        processed_dir=tmp_path / "processed",
        receipts_path=tmp_path / "receipts.jsonl",
        registry_path=tmp_path / "agent_registry.jsonl",
        dry_run=False,
        retry_attempts=2,
    )
    calls = {"count": 0}

    def fake_post(url, payload, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return {"status": "success", "message_id": "mesh-1"}

    broadcaster._post_json = fake_post
    receipt = broadcaster.deliver({"recommendation_id": "rec-2"}, {"agent_id": "mesh_agent", "endpoint": "http://mesh"})
    assert receipt["status"] == "delivered"
    assert receipt["attempts"] == 2


def test_registry_fallback_when_broker_unavailable(tmp_path):
    registry = tmp_path / "agent_registry.jsonl"
    registry.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "registered",
                        "agent_id": "bullbear_predictor",
                        "capabilities": ["prediction_signal"],
                        "metadata": {"transport": "file", "inbox": str(tmp_path / "bullbear")},
                    }
                ),
                json.dumps(
                    {
                        "event": "registered",
                        "agent_id": "projectx_native",
                        "capabilities": ["code_review"],
                        "endpoint": "http://127.0.0.1:8771",
                    }
                ),
            ]
        )
    )
    broadcaster = QuantumAdvisoryBroadcaster(
        inbox_dir=tmp_path / "inbox",
        processed_dir=tmp_path / "processed",
        receipts_path=tmp_path / "receipts.jsonl",
        registry_path=registry,
        dry_run=True,
    )
    broadcaster._get_json = lambda url, **kwargs: None
    agents = broadcaster.load_agents()
    assert {agent["agent_id"] for agent in agents} == {"bullbear_predictor", "projectx_native"}
