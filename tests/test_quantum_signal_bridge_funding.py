from __future__ import annotations

import quantum_signal_bridge as bridge


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
