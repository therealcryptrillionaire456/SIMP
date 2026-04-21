from __future__ import annotations

import sys
from pathlib import Path

from simp.memory.system_memory import Episode, Lesson, PolicyCandidate, SystemMemoryStore
from simp.memory.trade_learning import TradeLearningEngine


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import learn_from_trades  # noqa: E402


def test_system_memory_store_round_trip(tmp_path: Path) -> None:
    store = SystemMemoryStore(db_path=str(tmp_path / "system_memory.sqlite3"))

    episode_id = store.add_episode(
        Episode(
            episode_type="trade_execution",
            source="gate4_trades",
            entity="order-1",
            summary="BTC BUY ok",
            occurred_at="2026-04-21T16:36:53+00:00",
            payload={"symbol": "BTC-USD", "result": "ok"},
            tags=["trade", "BTC-USD"],
        )
    )
    lesson_id = store.upsert_lesson(
        Lesson(
            title="Budget before fan-out",
            summary="Budget capital before placing basket orders.",
            lesson_type="risk_control",
            confidence=0.9,
            evidence={"signals": 2},
            source_episode_ids=[episode_id],
        )
    )
    policy_id = store.upsert_policy_candidate(
        PolicyCandidate(
            title="Run nightly reflection",
            rationale="Promote trade lessons nightly.",
            priority="high",
            payload={"schedule": "nightly"},
            source_lesson_ids=[lesson_id],
        )
    )

    assert episode_id
    assert lesson_id
    assert policy_id
    assert store.list_episodes(limit=1)[0]["entity"] == "order-1"
    assert store.list_lessons(limit=1)[0]["title"] == "Budget before fan-out"
    assert store.list_policy_candidates(limit=1)[0]["title"] == "Run nightly reflection"


def test_trade_learning_detects_capital_gating_need() -> None:
    engine = TradeLearningEngine()
    trades = [
        {
            "ts": "2026-04-21T16:30:38.42+00:00",
            "signal_id": "sig-1",
            "symbol": "BTC-USD",
            "side": "BUY",
            "dry_run": False,
            "result": "insufficient_balance",
        },
        {
            "ts": "2026-04-21T16:30:38.63+00:00",
            "signal_id": "sig-1",
            "symbol": "ETH-USD",
            "side": "BUY",
            "dry_run": False,
            "result": "insufficient_balance",
        },
        {
            "ts": "2026-04-21T16:36:53.05+00:00",
            "signal_id": "sig-2",
            "symbol": "BTC-USD",
            "side": "BUY",
            "dry_run": False,
            "result": "ok",
            "client_order_id": "order-ok",
        },
        {
            "ts": "2026-04-19T14:04:13.87+00:00",
            "signal_id": "sig-old",
            "symbol": "BTC-USD",
            "side": "BUY",
            "dry_run": True,
            "result": "dry_run_ok",
        },
    ]
    pnl = [
        {
            "exec_ts": "2026-04-21T16:36:53.05+00:00",
            "client_order_id": "order-ok",
            "signal_id": "sig-2",
            "symbol": "BTC-USD",
            "side": "BUY",
            "exec_usd": 1.0,
        }
    ]

    report = engine.analyze(trades, pnl)

    titles = {lesson["title"] for lesson in report.lessons}
    policy_titles = {policy["title"] for policy in report.policy_candidates}

    assert "Capital allocation must be gated before multi-asset fan-out" in titles
    assert "Live Gate4 execution path is proven on a constrained notional band" in titles
    assert "Pre-fan-out capital budget check" in policy_titles


def test_build_report_persists_and_renders(tmp_path: Path) -> None:
    trade_log = tmp_path / "gate4_trades.jsonl"
    pnl_ledger = tmp_path / "phase4_pnl_ledger.jsonl"
    db_path = tmp_path / "system_memory.sqlite3"

    trade_log.write_text(
        "\n".join(
            [
                '{"ts":"2026-04-21T16:30:38.42+00:00","signal_id":"sig-1","symbol":"BTC-USD","side":"BUY","dry_run":false,"result":"insufficient_balance"}',
                '{"ts":"2026-04-21T16:30:38.63+00:00","signal_id":"sig-1","symbol":"ETH-USD","side":"BUY","dry_run":false,"result":"insufficient_balance"}',
                '{"ts":"2026-04-21T16:36:53.05+00:00","signal_id":"sig-2","symbol":"BTC-USD","side":"BUY","dry_run":false,"result":"ok","client_order_id":"order-ok"}',
            ]
        )
        + "\n"
    )
    pnl_ledger.write_text(
        '{"exec_ts":"2026-04-21T16:36:53.05+00:00","client_order_id":"order-ok","signal_id":"sig-2","symbol":"BTC-USD","side":"BUY","exec_usd":1.0}\n'
    )

    report = learn_from_trades.build_report(
        trade_log=str(trade_log),
        pnl_ledger=str(pnl_ledger),
        db_path=str(db_path),
        persist=True,
    )

    assert report["stored_counts"]["episodes"] == 4
    assert report["stored_counts"]["lessons"] >= 2
    assert report["stored_counts"]["policy_candidates"] >= 1

    markdown = learn_from_trades.render_markdown(report)
    assert "# Trade Learning Report" in markdown
    assert "Capital allocation must be gated before multi-asset fan-out" in markdown
