from __future__ import annotations

from pathlib import Path

import quantum_signal_bridge as bridge


def test_register_and_subscribe_tolerates_existing_broker_agent(monkeypatch) -> None:
    calls = []

    def fake_post_result(url, payload, timeout=10):
        calls.append((url, payload))
        return 400, {"status": "error", "error": "duplicate"}, "duplicate"

    monkeypatch.setattr(bridge, "_post_result", fake_post_result)
    monkeypatch.setattr(bridge, "_broker_has_agent", lambda broker, agent_id: True)
    monkeypatch.setattr(bridge, "_bridge_poll_ready", lambda broker: True)

    assert bridge.register_and_subscribe("http://broker") is True
    assert len(calls) == 3


def test_apply_funding_constraints_bootstraps_with_sell(monkeypatch) -> None:
    monkeypatch.setattr(bridge, "_coinbase_client", lambda: object())
    monkeypatch.setattr(bridge, "_account_balances", lambda client: {"ETH": 0.01})
    monkeypatch.setattr(bridge, "_market_price", lambda client, product_id: 2500.0)

    signal = {
        "assets": {
            "BTC-USD": {"weight": 0.4, "position_usd": 4.0, "action": "buy"},
            "ETH-USD": {"weight": 0.25, "position_usd": 2.5, "action": "buy"},
            "SOL-USD": {"weight": 0.35, "position_usd": 3.5, "action": "buy"},
        },
        "metadata": {},
    }

    adjusted = bridge._apply_funding_constraints(signal)

    assert adjusted["assets"] == {
        "ETH-USD": {"weight": 1.0, "position_usd": 6.25, "action": "sell"}
    }
    assert adjusted["metadata"]["funding_mode"] == "bootstrap_sell"


def test_apply_funding_constraints_scales_buys_to_quote_budget(monkeypatch) -> None:
    monkeypatch.setattr(bridge, "_coinbase_client", lambda: object())
    monkeypatch.setattr(bridge, "_account_balances", lambda client: {"USD": 4.5})

    signal = {
        "assets": {
            "BTC-USD": {"weight": 0.6, "position_usd": 6.0, "action": "buy"},
            "ETH-USD": {"weight": 0.4, "position_usd": 4.0, "action": "buy"},
        },
        "metadata": {},
    }

    adjusted = bridge._apply_funding_constraints(signal)

    assert adjusted["metadata"]["funding_mode"] == "quote_funded"
    assert adjusted["metadata"]["quote_budget_usd"] == 4.5
    assert adjusted["assets"]["BTC-USD"]["position_usd"] == 2.7
    assert adjusted["assets"]["ETH-USD"]["position_usd"] == 1.8


def test_parse_qip_response_respects_policy_quality_floor(monkeypatch) -> None:
    qip_payload = {
        "success": True,
        "result": "BTC 60% ETH 40%",
        "metadata": {"quality_score": 0.6, "trace_id": "trace-1"},
    }
    policy_state = {"execution_quality": {"min_quality_score": 0.7}}

    signal = bridge.parse_qip_response(qip_payload, policy_state=policy_state, cycle_id="cycle-1")

    assert signal is None


def test_parse_qip_response_adds_lineage_and_policy_version(monkeypatch) -> None:
    monkeypatch.setattr(bridge, "_coinbase_client", lambda: None)
    qip_payload = {
        "success": True,
        "result": "BTC 60% ETH 40%",
        "metadata": {"quality_score": 0.9, "trace_id": "trace-1", "plan_id": "plan-7"},
        "responding_to": "req-1",
    }
    policy_state = {
        "generated_at": "2026-04-22T00:00:00+00:00",
        "execution_quality": {"min_quality_score": 0.5},
    }

    signal = bridge.parse_qip_response(qip_payload, policy_state=policy_state, cycle_id="cycle-1")

    assert signal is not None
    lineage = signal["metadata"]["lineage"]
    assert lineage["bridge_cycle_id"] == "cycle-1"
    assert lineage["qip_trace_id"] == "trace-1"
    assert lineage["plan_id"] == "plan-7"
    assert signal["metadata"]["policy_state_version"] == "2026-04-22T00:00:00+00:00"
