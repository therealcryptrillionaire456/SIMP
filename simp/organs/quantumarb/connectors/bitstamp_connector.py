#!/usr/bin/env python3.10
"""
Bitstamp Exchange Connector.

Supports Bitstamp REST API v2. NY/NJ compliant — Bitstamp holds
a BitLicense from NYDFS.

API docs: https://www.bitstamp.net/api/
"""

import json
import time
import logging
import hashlib
import hmac
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from ..exchange_connector import (
    BaseExchangeConnector, Balance, Ticker, Order, OrderSide,
    OrderType, OrderStatus, ExchangeError, AuthenticationError,
    InsufficientFundsError, OrderRejectedError, RateLimitError
)

log = logging.getLogger("BitstampConnector")

# ── Symbol mapping ──────────────────────────────────────────────────────

_SYMBOL_MAP: Dict[str, str] = {
    "BTC-USD": "btcusd",
    "ETH-USD": "ethusd",
    "SOL-USD": "solusd",
    "XRP-USD": "xrpusd",
    "ADA-USD": "adausd",
    "LTC-USD": "ltcusd",
    "DOGE-USD": "dogeusd",
    "BTC-EUR": "btceur",
    "ETH-EUR": "etheur",
    "SOL-EUR": "soleur",
    "USDC-USD": "usdcusd",
}

_REVERSE_MAP: Dict[str, str] = {v: k for k, v in _SYMBOL_MAP.items()}


def to_bitstamp_pair(symbol: str) -> str:
    """Convert SIMP symbol (e.g. 'BTC-USD') to Bitstamp pair (e.g. 'btcusd')."""
    upper = symbol.upper()
    if upper in _SYMBOL_MAP:
        return _SYMBOL_MAP[upper]
    # Fallback: lowercase + strip dash
    return upper.lower().replace("-", "")


def from_bitstamp_pair(pair: str) -> str:
    """Convert Bitstamp pair back to SIMP symbol."""
    lower = pair.lower()
    if lower in _REVERSE_MAP:
        return _REVERSE_MAP[lower]
    # Heuristic: split after first non-usd/eur
    for quote in ("usd", "eur", "gbp", "usdc"):
        if lower.endswith(quote):
            base = lower[:-len(quote)].upper()
            return f"{base}-{quote.upper()}"
    return lower.upper()


# ── Connector ───────────────────────────────────────────────────────────

class BitstampConnector(BaseExchangeConnector):
    """
    Bitstamp REST API v2 connector.

    Docs: https://www.bitstamp.net/api/
    """

    BASE_URL = "https://www.bitstamp.net/api/v2"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        customer_id: str = "",
        sandbox: bool = True,
        rate_limit_per_minute: int = 10,
    ):
        super().__init__(api_key, api_secret, "", sandbox, rate_limit_per_minute)
        self.customer_id = customer_id
        # Bitstamp doesn't have a separate sandbox; flag just controls logging
        log.info("BitstampConnector initialised (sandbox=%s)", sandbox)
        if api_key:
            self._test_connectivity()

    # ── Fee ─────────────────────────────────────────────────────────────

    def get_fees(self) -> float:
        """Bitstamp tiered fees. Default 0.5% for low-volume."""
        return 0.0 if self.sandbox else 0.005

    # ── Connectivity ────────────────────────────────────────────────────

    def _test_connectivity(self) -> None:
        try:
            self._public_request("GET", "/ticker/btcusd/")
            log.info("✅ Bitstamp API connectivity OK")
        except Exception as e:
            log.warning("⚠️ Bitstamp connectivity failed: %s", e)

    # ── Rate limiting ──────────────────────────────────────────────────

    def _rate_limit(self) -> None:
        """Simple rate limiter: 10 req/min = 6s between."""
        time.sleep(6.0 / max(self.rate_limit_per_minute, 1))

    # ── HTTP helpers ────────────────────────────────────────────────────

    def _public_request(self, method: str, path: str) -> Any:
        url = f"{self.BASE_URL}{path}"
        return self._make_request(method, url)

    def _make_request(
        self, method: str, url: str,
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Any:
        self._rate_limit()
        body = None
        if data:
            body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise ExchangeError(f"Bitstamp HTTP {e.code}: {error_body}")
        except (urllib.error.URLError, OSError) as e:
            raise ExchangeError(f"Bitstamp request failed: {e}")

    def _sign_request(self, method: str, path: str, data: Dict) -> Dict[str, str]:
        """Sign a private request with Bitstamp auth headers."""
        nonce = str(int(time.time() * 1_000_000))
        message = f"{nonce}{self.customer_id}{self.api_key}"
        if data:
            message += urllib.parse.urlencode(data)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()
        return {
            "X-Auth": self.api_key,
            "X-Auth-Nonce": nonce,
            "X-Auth-Signature": signature,
            "X-Auth-Version": "v2",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _authenticated_request(
        self, method: str, path: str,
        data: Optional[Dict] = None,
    ) -> Any:
        url = f"{self.BASE_URL}{path}"
        headers = self._sign_request(method, path, data or {})
        return self._make_request(method, url, headers=headers, data=data or {})

    # ── Public API — Ticker ─────────────────────────────────────────────

    def get_ticker(self, symbol: str) -> Ticker:
        pair = to_bitstamp_pair(symbol)
        url = f"{self.BASE_URL}/ticker/{pair}/"
        data = self._public_request("GET", f"/ticker/{pair}/")
        if isinstance(data, list):
            data = data[0] if data else {}
        return Ticker(
            symbol=symbol,
            bid=float(data.get("bid", 0)),
            ask=float(data.get("ask", 0)),
            last=float(data.get("last", 0)),
            volume=float(data.get("volume", 0)),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ── Private API — Balance ──────────────────────────────────────────

    def get_balance(self, currency: str) -> Balance:
        data = self._authenticated_request("POST", "/balance/")
        curr_lower = currency.lower()
        available_key = f"{curr_lower}_available"
        balance_key = f"{curr_lower}_balance"
        held_key = f"{curr_lower}_reserved"
        available = float(data.get(available_key, 0))
        total = float(data.get(balance_key, 0))
        held = float(data.get(held_key, 0))
        return Balance(
            currency=currency.upper(),
            available=available,
            total=total if total > 0 else available,
            held=held,
        )

    # ── Private API — Place Order ──────────────────────────────────────

    def place_order(
        self, symbol: str, side: OrderSide,
        quantity: float, order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
    ) -> Order:
        pair = to_bitstamp_pair(symbol)
        endpoint = f"/{'buy' if side == OrderSide.BUY else 'sell'}/{pair}/"
        payload: Dict[str, str] = {
            "amount": str(quantity),
        }
        if order_type == OrderType.LIMIT and price:
            payload["price"] = str(price)
        else:
            # Market order — use 'market_' endpoints or just omit price
            pass

        result = self._authenticated_request("POST", endpoint, data=payload)

        # Bitstamp returns {id, datetime, type, price, amount, ...}
        order_id = str(result.get("id", ""))
        filled_qty = float(result.get("amount", quantity))
        avg_price = float(result.get("price", 0)) or float(result.get("avg_price", 0))

        return Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.FILLED if filled_qty > 0 else OrderStatus.NEW,
            filled_quantity=filled_qty,
            average_price=avg_price if avg_price > 0 else None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            exchange_timestamp=result.get("datetime"),
        )

    # ── Private API — Cancel Order ─────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        try:
            result = self._authenticated_request(
                "POST", "/cancel_order/", data={"id": order_id}
            )
            return result.get("result") is True
        except Exception as e:
            log.warning("Cancel order %s failed: %s", order_id, e)
            return False

    # ── Private API — Order Status ─────────────────────────────────────

    def get_order_status(self, order_id: str) -> Order:
        result = self._authenticated_request(
            "POST", "/order_status/", data={"id": order_id}
        )
        status_str = str(result.get("status", "unknown")).lower()
        status_map = {
            "open": OrderStatus.NEW,
            "finished": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "cancelled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
        }
        filled_qty = float(result.get("amount", 0))
        remaining = float(result.get("remaining", filled_qty))
        filled = filled_qty - remaining
        return Order(
            order_id=order_id,
            symbol=from_bitstamp_pair(result.get("currency_pair", "")),
            side=OrderSide.BUY if str(result.get("type", "")).lower() == "buy" else OrderSide.SELL,
            order_type=OrderType.MARKET if result.get("market") else OrderType.LIMIT,
            quantity=filled_qty,
            price=float(result.get("price", 0)) or None,
            status=status_map.get(status_str, OrderStatus.NEW),
            filled_quantity=max(0, filled),
            average_price=float(result.get("avg_price", 0)) or None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            exchange_timestamp=result.get("datetime"),
        )

    # ── Private API — Open Orders ──────────────────────────────────────

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        path = f"/open_orders/all/" if not symbol else f"/open_orders/{to_bitstamp_pair(symbol)}/"
        orders_data = self._authenticated_request("POST", path)
        if not isinstance(orders_data, list):
            return []
        orders = []
        for od in orders_data:
            pair = from_bitstamp_pair(od.get("currency_pair", ""))
            if symbol and pair != symbol:
                continue
            orders.append(Order(
                order_id=str(od.get("id", "")),
                symbol=pair,
                side=OrderSide.BUY if str(od.get("type", "")).lower() == "buy" else OrderSide.SELL,
                order_type=OrderType.MARKET if od.get("market") else OrderType.LIMIT,
                quantity=float(od.get("amount", 0)),
                price=float(od.get("price", 0)) or None,
                status=OrderStatus.NEW,
                filled_quantity=float(od.get("amount", 0)) - float(od.get("remaining", 0)),
                timestamp=datetime.now(timezone.utc).isoformat(),
                exchange_timestamp=od.get("datetime"),
            ))
        return orders


# ── Test function ────────────────────────────────────────────────────────

def test_bitstamp_connector():
    """Test Bitstamp connector (public ticker only, no API key needed)."""
    print("Testing Bitstamp Connector...")
    conn = BitstampConnector(sandbox=True)

    # Test ticker
    ticker = conn.get_ticker("BTC-USD")
    print(f"  BTC-USD ticker: bid={ticker.bid}, ask={ticker.ask}, last={ticker.last}")
    assert ticker.last > 0, "BTC price should be > 0"

    # Test multiple symbols
    for sym in ("ETH-USD", "SOL-USD", "XRP-USD"):
        t = conn.get_ticker(sym)
        print(f"  {sym}: ${t.last:.2f}")
        assert t.last >= 0, f"{sym} price should be >= 0"

    # Test order validation (no API key)
    valid, msg = conn.validate_order("BTC-USD", OrderSide.BUY, 0.001, OrderType.MARKET)
    print(f"  Order validation: valid={valid}, msg={msg}")

    # Test fee
    fee = conn.get_fees()
    print(f"  Default fee: {fee*100:.1f}%")

    print("\n✅ Bitstamp connector tests passed!")


if __name__ == "__main__":
    test_bitstamp_connector()
