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
