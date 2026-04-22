from __future__ import annotations

import asyncio
import json

import scripts.solana_seeker_integration as seeker


class _DummyMemoryStore:
    def add_episode(self, episode):
        return None


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return _FakeResponse(self.payload)


def _patch_runtime_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(seeker, "STATE_FILE", tmp_path / "solana_state.json")
    monkeypatch.setattr(seeker, "TRADE_LOG", tmp_path / "logs" / "solana_seeker_trades.jsonl")
    monkeypatch.setattr(seeker, "LEDGER", tmp_path / "data" / "solana_seeker_ledger.jsonl")
    monkeypatch.setattr(seeker, "SIGNALS_DIR", tmp_path / "signals")
    monkeypatch.setattr(seeker, "PROCESSED_DIR", tmp_path / "signals" / "processed")
    monkeypatch.setattr(seeker, "FAILED_DIR", tmp_path / "signals" / "failed")
    monkeypatch.setattr(seeker, "SYSTEM_MEMORY_STORE", _DummyMemoryStore())


def test_solana_seeker_api_respects_dry_run_and_live_mode():
    api = seeker.SolanaSeekerAPI({"phone_integration": {"api_endpoint": "https://example.invalid"}})

    dry_result = asyncio.run(
        api.place_order(
            {"symbol": "SOL-USD", "action": "BUY", "notional": 1.0},
            live_mode=False,
        )
    )
    assert dry_result["success"] is True
    assert dry_result["dry_run"] is True
    assert dry_result["order_id"].startswith("dry_run_")

    fake_session = _FakeSession({"success": True, "order_id": "order-123"})
    api.session = fake_session
    live_result = asyncio.run(
        api.place_order(
            {"symbol": "SOL-USD", "action": "BUY", "notional": 1.0},
            live_mode=True,
        )
    )
    assert live_result["success"] is True
    assert live_result["order_id"] == "order-123"
    assert "dry_run" not in live_result
    assert fake_session.calls[0]["url"].endswith("/orders")
    assert fake_session.calls[0]["json"]["client_order_id"].startswith("solana-")


def test_solana_seeker_blocks_low_quality_signals(tmp_path, monkeypatch):
    _patch_runtime_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        seeker,
        "load_active_system_policies",
        lambda: {
            "generated_at": "2026-04-22T00:00:00+00:00",
            "execution_quality": {"min_quality_score": 0.8},
        },
    )

    trader = seeker.SolanaSeekerTrader(
        {
            "phone_integration": {"api_endpoint": "https://example.invalid"},
            "position_sizing": {"microscopic": {"min_usd": 0.01, "max_usd": 10.0}},
        }
    )

    result = asyncio.run(
        trader.process_signal(
            {
                "signal_id": "solana-low-quality",
                "source": "qip",
                "metadata": {
                    "quality_score": 0.2,
                    "lineage": {"bridge_cycle_id": "cycle-2", "qip_trace_id": "trace-2"},
                },
                "assets": {
                    "SOL-USD": {"action": "buy", "position_usd": 1.0},
                },
            },
            live_mode=True,
        )
    )

    assert result["success"] is False
    assert result["errors"] == ["quality_below_threshold:0.8"]
    assert result["lineage"]["bridge_cycle_id"] == "cycle-2"
    assert result["lineage"]["qip_trace_id"] == "trace-2"
    assert result["policy_state_version"] == "2026-04-22T00:00:00+00:00"


def test_solana_seeker_trade_records_include_lineage_and_policy_state_version(
    tmp_path, monkeypatch
):
    _patch_runtime_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        seeker,
        "load_active_system_policies",
        lambda: {
            "generated_at": "2026-04-22T01:02:03+00:00",
            "execution_quality": {"min_quality_score": 0.1},
        },
    )

    trader = seeker.SolanaSeekerTrader(
        {
            "phone_integration": {"api_endpoint": "https://example.invalid"},
            "position_sizing": {"microscopic": {"min_usd": 0.01, "max_usd": 10.0}},
        }
    )

    result = asyncio.run(
        trader.process_signal(
            {
                "signal_id": "solana-lineage",
                "source": "qip",
                "metadata": {
                    "quality_score": 0.9,
                    "lineage": {"bridge_cycle_id": "cycle-9", "plan_id": "plan-11"},
                },
                "assets": {
                    "SOL-USD": {"action": "buy", "position_usd": 1.0},
                },
            },
            live_mode=False,
        )
    )

    assert result["success"] is True
    assert result["positions"][0]["status"] == "executed"
    assert result["lineage"]["bridge_cycle_id"] == "cycle-9"
    assert result["policy_state_version"] == "2026-04-22T01:02:03+00:00"

    trade_log = seeker.TRADE_LOG.read_text(encoding="utf-8").splitlines()
    assert len(trade_log) == 1
    trade_record = json.loads(trade_log[0])
    assert trade_record["dry_run"] is True
    assert trade_record["result"] == "ok"
    assert trade_record["lineage"]["bridge_cycle_id"] == "cycle-9"
    assert trade_record["lineage"]["plan_id"] == "plan-11"
    assert trade_record["policy_state_version"] == "2026-04-22T01:02:03+00:00"
