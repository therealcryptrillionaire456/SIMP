from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import learn_from_system  # noqa: E402
from simp.memory.policy_state import POLICY_STATE_PATH, REFLECTION_STATUS_PATH  # noqa: E402
from simp.memory.system_reflection import SystemLearningEngine  # noqa: E402


def test_system_learning_detects_cross_system_policies(tmp_path: Path) -> None:
    trade_log = tmp_path / "gate4_trades.jsonl"
    pnl = tmp_path / "phase4_pnl_ledger.jsonl"
    mesh = tmp_path / "mesh_events.jsonl"
    orchestration = tmp_path / "orchestration_log.jsonl"
    security = tmp_path / "security_audit.jsonl"
    registry = tmp_path / "agent_registry.jsonl"

    trade_log.write_text(
        "\n".join(
            [
                '{"ts":"2026-04-21T16:30:38.42+00:00","signal_id":"sig-1","symbol":"BTC-USD","side":"BUY","dry_run":false,"result":"insufficient_balance"}',
                '{"ts":"2026-04-21T16:36:53.05+00:00","signal_id":"sig-2","symbol":"BTC-USD","side":"BUY","dry_run":false,"result":"ok","client_order_id":"order-ok"}',
            ]
        )
        + "\n"
    )
    pnl.write_text(
        '{"exec_ts":"2026-04-21T16:36:53.05+00:00","client_order_id":"order-ok","signal_id":"sig-2","symbol":"BTC-USD","side":"BUY","exec_usd":1.0}\n'
    )
    mesh.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-21T16:00:00+00:00","event_type":"MESSAGE_DELIVERED","status":"success"}',
                '{"timestamp":"2026-04-21T16:00:01+00:00","event_type":"MESSAGE_DROPPED","status":"error","error_code":"NO_SUBSCRIBERS"}',
            ]
        )
        + "\n"
    )
    orchestration.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-21T16:10:00+00:00","event_kind":"plan_started"}',
                '{"timestamp":"2026-04-21T16:11:00+00:00","event_kind":"plan_completed"}',
            ]
        )
        + "\n"
    )
    security.write_text(
        '{"timestamp":"2026-04-21T16:12:00+00:00","event_type":"validation_error","severity":"low"}\n'
    )
    registry.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-21T16:13:00+00:00","event":"registered"}',
                '{"timestamp":"2026-04-21T16:14:00+00:00","event":"deregistered"}',
            ]
        )
        + "\n"
    )

    engine = SystemLearningEngine(
        trade_log_path=str(trade_log),
        pnl_ledger_path=str(pnl),
        mesh_events_path=str(mesh),
        orchestration_log_path=str(orchestration),
        security_audit_path=str(security),
        agent_registry_path=str(registry),
    )
    report = engine.analyze().to_dict()

    lesson_titles = {lesson["title"] for lesson in report["lessons"]}
    policy_titles = {policy["title"] for policy in report["policy_candidates"]}

    assert "Mesh friction is learnable operational signal, not just transport noise" in lesson_titles
    assert "Revenue learning must join execution outcomes with orchestration intent" in lesson_titles
    assert "Daily mesh hygiene reflection" in policy_titles
    assert "Plan-to-execution lineage capture" in policy_titles


def test_system_learning_script_persists(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "system_memory.sqlite3"
    policy_path = tmp_path / "active_system_policies.json"
    status_path = tmp_path / "reflection_status.json"

    class _FakeReport:
        def to_dict(self):
            return {
                "trade_learning": {
                    "total_trade_records": 1,
                    "live_trade_records": 1,
                    "successful_live_trades": 1,
                    "symbols_with_success": ["BTC-USD"],
                },
                "mesh_summary": {"total_events": 2, "drop_rate": 0.5},
                "orchestration_summary": {
                    "plan_started": 1,
                    "plan_completed": 1,
                    "completion_ratio": 1.0,
                },
                "security_summary": {"total_events": 1},
                "registry_summary": {"total_events": 1, "churn_ratio": 0.0},
                "lessons": [{"title": "L1", "summary": "s", "lesson_type": "x", "confidence": 0.9, "evidence": {}}],
                "policy_candidates": [{"title": "P1", "rationale": "r", "priority": "high", "payload": {}}],
            }

    class _FakeEngine:
        def persist(self, store):
            return _FakeReport()

    monkeypatch.setattr(learn_from_system, "SystemLearningEngine", lambda: _FakeEngine())
    monkeypatch.setattr("simp.memory.policy_state.POLICY_STATE_PATH", policy_path)
    monkeypatch.setattr("simp.memory.policy_state.REFLECTION_STATUS_PATH", status_path)

    report = learn_from_system.build_report(db_path=str(db_path), persist=True)

    assert report["stored_counts"]["episodes"] == 0
    assert report["trade_learning"]["successful_live_trades"] == 1
    assert report["policy_state"]["active_lessons"][0]["title"] == "L1"
    assert policy_path.exists()
    assert status_path.exists()
    assert "# System Learning Report" in learn_from_system.render_markdown(report)
