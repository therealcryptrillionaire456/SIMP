from __future__ import annotations

from pathlib import Path

import gate4_inbox_consumer as consumer


class _OrderConfiguration:
    def __init__(self, quote_size: str) -> None:
        self.market_market_ioc = {"quote_size": quote_size}


def test_record_trade_serializes_sdk_like_objects(tmp_path: Path, monkeypatch) -> None:
    trade_log = tmp_path / "gate4_trades.jsonl"
    monkeypatch.setattr(consumer, "TRADE_LOG", trade_log)

    consumer.record_trade(
        {
            "result": "rejected_operational",
            "response": {
                "success": False,
                "order_configuration": _OrderConfiguration("3.33"),
            },
        }
    )

    line = trade_log.read_text().strip()
    assert '"result": "rejected_operational"' in line
    assert '"quote_size": "3.33"' in line


def test_insufficient_funds_rejection_does_not_count_as_loss() -> None:
    resp = {
        "success": False,
        "error_response": {
            "error": "INSUFFICIENT_FUND",
            "preview_failure_reason": "PREVIEW_INSUFFICIENT_FUND",
        },
    }

    assert consumer._counts_as_loss(resp) is False


def test_other_rejections_still_count_as_loss() -> None:
    resp = {
        "success": False,
        "error_response": {
            "error": "UNKNOWN_FAILURE",
            "message": "Exchange rejected request",
        },
    }

    assert consumer._counts_as_loss(resp) is True


def test_classify_response_handles_transient_and_insufficient_balance() -> None:
    transient = {
        "success": False,
        "error_response": {"error": "SERVICE_UNAVAILABLE", "message": "temporary upstream failure"},
    }
    insufficient = {
        "success": False,
        "error_response": {"error": "INSUFFICIENT_FUND", "preview_failure_reason": "PREVIEW_INSUFFICIENT_FUND"},
    }

    assert consumer._classify_response(transient)["classification"] == "transient"
    assert consumer._classify_response(insufficient)["result"] == "insufficient_balance"


def test_reset_cooldown_if_expired_clears_consecutive_losses() -> None:
    state = {
        "consecutive_losses": 4,
        "cooldown_until": "2026-04-21T10:00:00+00:00",
        "last_error_classification": "fatal",
    }

    assert consumer.reset_cooldown_if_expired(state) is True
    assert state["consecutive_losses"] == 0
    assert state["cooldown_until"] is None
    assert state["last_error_classification"] is None


def test_pre_fanout_budget_blocks_underfunded_lower_priority_buys(monkeypatch) -> None:
    cfg = {
        "position_sizing": {"min_notional": 1.0, "max_notional": 10.0},
    }
    assets = {
        "BTC-USD": {"action": "buy", "position_usd": 3.0, "weight": 0.6},
        "ETH-USD": {"action": "buy", "position_usd": 2.0, "weight": 0.4},
        "SOL-USD": {"action": "hold", "position_usd": 0.0, "weight": 0.0},
    }
    policies = {"capital_budgeting": {"enabled": True, "min_quote_reserve_usd": 0.0}}

    monkeypatch.setattr(consumer, "_quote_balance_usd", lambda client: 3.0)

    plan = consumer._apply_pre_fanout_budget(assets, cfg, client=object(), policy_state=policies)

    assert plan["decision"] == "capital_budget_applied"
    assert plan["allowed"]["BTC-USD"] == 3.0
    assert plan["blocked"]["ETH-USD"] == "insufficient_quote_budget"
