from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


TRANSIENT_MARKERS = (
    "connectionerror",
    "connecttimeout",
    "readtimeout",
    "timeout",
    "temporarily unavailable",
    "temporary failure",
    "failed to resolve",
    "nameresolutionerror",
    "max retries exceeded",
    "connection reset",
    "connection aborted",
    "remote end closed connection",
    "503",
    "502",
    "504",
    "429",
    "rate limit",
    "too many requests",
    "service unavailable",
)

FATAL_MARKERS = (
    "401",
    "403",
    "permission denied",
    "unauthorized",
    "forbidden",
    "invalid api key",
    "signature",
    "invalid argument",
    "validation",
)


@dataclass
class CoinbaseOperationError(RuntimeError):
    message: str
    classification: str
    attempts: int
    exception_type: str
    last_error: str

    def __str__(self) -> str:
        return self.message


def classify_coinbase_exception(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if isinstance(exc, (TimeoutError, ConnectionError, socket.timeout, socket.gaierror)):
        return "transient"
    if any(marker in text for marker in TRANSIENT_MARKERS):
        return "transient"
    if any(marker in text for marker in FATAL_MARKERS):
        return "fatal"
    return "fatal"


def coinbase_dns_status(host: str = "api.coinbase.com") -> Dict[str, Any]:
    status: Dict[str, Any] = {"host": host, "ok": False, "addresses": [], "error": None}
    try:
        info = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = sorted({item[4][0] for item in info if item and item[4]})
        status["addresses"] = addresses
        status["ok"] = bool(addresses)
    except Exception as exc:  # pragma: no cover - exercised via integration
        status["error"] = f"{type(exc).__name__}: {exc}"

    if status["ok"]:
        return status

    try:  # Optional fallback if dnspython is available in the runtime venv.
        import dns.resolver  # type: ignore

        answers = dns.resolver.resolve(host, "A")
        addresses = sorted({answer.to_text() for answer in answers})
        if addresses:
            status["addresses"] = addresses
            status["ok"] = True
            status["resolver"] = "dnspython"
            status["error"] = None
    except Exception:
        pass
    return status


class ResilientCoinbaseClient:
    """Thin retry/classification wrapper around the Coinbase SDK client."""

    def __init__(
        self,
        sdk_client: Any,
        *,
        logger: Optional[logging.Logger] = None,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 5.0,
    ) -> None:
        self._sdk = sdk_client
        self._logger = logger or logging.getLogger("ResilientCoinbaseClient")
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay_seconds = max(0.0, float(base_delay_seconds))
        self.max_delay_seconds = max(self.base_delay_seconds, float(max_delay_seconds))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sdk, name)

    def call(self, operation: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        last_classification = "fatal"
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                last_classification = classify_coinbase_exception(exc)
                self._logger.warning(
                    "coinbase %s attempt %d/%d classified=%s error=%s",
                    operation,
                    attempt,
                    self.max_attempts,
                    last_classification,
                    exc,
                )
                if last_classification != "transient" or attempt >= self.max_attempts:
                    break
                delay = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1)))
                time.sleep(delay)

        error_text = str(last_exc) if last_exc else f"{operation} failed"
        raise CoinbaseOperationError(
            message=f"{operation} failed after {min(self.max_attempts, attempt)} attempt(s): {error_text}",
            classification=last_classification,
            attempts=min(self.max_attempts, attempt),
            exception_type=type(last_exc).__name__ if last_exc else "CoinbaseError",
            last_error=error_text,
        )

    def get_accounts(self) -> Any:
        return self.call("get_accounts", self._sdk.get_accounts)

    def get_product(self, *, product_id: str) -> Any:
        return self.call("get_product", self._sdk.get_product, product_id=product_id)

    def get_product_ticker(self, *, product_id: str) -> Any:
        return self.call(
            "get_product_ticker",
            self._sdk.get_product_ticker,
            product_id=product_id,
        )

    def market_order_buy(self, **kwargs: Any) -> Any:
        return self.call("market_order_buy", self._sdk.market_order_buy, **kwargs)

    def market_order_sell(self, **kwargs: Any) -> Any:
        return self.call("market_order_sell", self._sdk.market_order_sell, **kwargs)
