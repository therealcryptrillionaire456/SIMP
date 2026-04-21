from __future__ import annotations

from simp.exchange.coinbase_client import (
    CoinbaseOperationError,
    ResilientCoinbaseClient,
    classify_coinbase_exception,
)


class _FlakySDK:
    def __init__(self) -> None:
        self.calls = 0

    def get_accounts(self):
        self.calls += 1
        if self.calls < 3:
            raise ConnectionError("temporary dns failure")
        return {"accounts": []}


class _FatalSDK:
    def get_accounts(self):
        raise ValueError("invalid credentials")


def test_retry_wrapper_retries_transient_errors() -> None:
    client = ResilientCoinbaseClient(_FlakySDK(), max_attempts=3, base_delay_seconds=0.0)

    result = client.get_accounts()

    assert result == {"accounts": []}


def test_retry_wrapper_raises_coinbase_operation_error_on_fatal() -> None:
    client = ResilientCoinbaseClient(_FatalSDK(), max_attempts=3, base_delay_seconds=0.0)

    try:
        client.get_accounts()
    except CoinbaseOperationError as exc:
        assert exc.classification == "fatal"
        assert exc.attempts == 1
    else:  # pragma: no cover - defensive
        raise AssertionError("expected CoinbaseOperationError")


def test_exception_classifier_marks_dns_as_transient() -> None:
    assert classify_coinbase_exception(ConnectionError("Failed to resolve api.coinbase.com")) == "transient"
