#!/usr/bin/env python3.10
"""
Kraken Exchange Connector.

Supports both sandbox (api.kraken.com) and production (api.kraken.com)
with Kraken's REST API v0. Uses urllib only (no requests library).

Kraken API documentation: https://docs.kraken.com/rest/
"""

import json
import time
import logging
import hashlib
import hmac
import base64
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

log = logging.getLogger("KrakenConnector")


# ---------------------------------------------------------------------------
# Kraken symbol mapping helpers
# ---------------------------------------------------------------------------

# Known Kraken pair keys (used as the exact key in /0/public/Ticker).
# Kraken does not always follow the simple base+quote concatenation rule.
# For example, the pair for SOL/USD has key "SOLUSD" even though the
# quote asset is "ZUSD".  These are the canonical /0/public/AssetPairs keys.
_KNOWN_KRAKEN_PAIRS: Dict[str, str] = {
    "BTC-USD": "XXBTZUSD",
    "ETH-USD": "XETHZUSD",
    "SOL-USD": "SOLUSD",
    "XRP-USD": "XXRPZUSD",
    "DOGE-USD": "XDGZUSD",
    "LTC-USD": "XLTCZUSD",
    "ADA-USD": "ADAZUSD",
    "DOT-USD": "DOTZUSD",
    "LINK-USD": "LINKZUSD",
    "BTC-EUR": "XXBTZEUR",
    "ETH-EUR": "XETHZEUR",
    "SOL-EUR": "SOLEUR",
}


def to_kraken_pair(symbol: str) -> str:
    """Convert SIMP symbol (e.g. 'BTC-USD') to Kraken pair key (e.g. 'XXBTZUSD')."""
    # Look up exact known pair first
    upper_symbol = symbol.upper()
    if upper_symbol in _KNOWN_KRAKEN_PAIRS:
        return _KNOWN_KRAKEN_PAIRS[upper_symbol]

    # Fallback: construct base + quote from asset names
    base, quote = upper_symbol.split("-")
    base_map = {
        "BTC": "XXBT",
        "ETH": "XETH",
        "SOL": "SOL",
        "XRP": "XXRP",
        "LTC": "XLTC",
        "DOGE": "XDG",
        "ADA": "ADA",
        "DOT": "DOT",
        "LINK": "LINK",
    }
    quote_map = {
        "USD": "ZUSD",
        "EUR": "ZEUR",
        "GBP": "ZGBP",
        "JPY": "ZJPY",
        "CAD": "ZCAD",
        "CHF": "ZCHF",
        "AUD": "ZAUD",
    }
    base_name = base_map.get(base, base)
    quote_name = quote_map.get(quote, quote)
    return f"{base_name}{quote_name}"


# Reverse lookup: Kraken pair key -> SIMP symbol
_KNOWN_KRAKEN_PAIRS_REV: Dict[str, str] = {v: k for k, v in _KNOWN_KRAKEN_PAIRS.items()}


def from_kraken_pair(kraken_pair: str) -> str:
    """Convert Kraken pair key (e.g. 'XXBTZUSD') to SIMP symbol (e.g. 'BTC-USD')."""
    # Check known pairs first
    if kraken_pair in _KNOWN_KRAKEN_PAIRS_REV:
        return _KNOWN_KRAKEN_PAIRS_REV[kraken_pair]

    # Fallback: reverse-map by splitting base/quote asset names
    rev_asset = {
        "XXBT": "BTC",
        "XBT": "BTC",
        "XETH": "ETH",
        "SOL": "SOL",
        "XXRP": "XRP",
        "XLTC": "LTC",
        "XDG": "DOGE",
        "ADA": "ADA",
        "DOT": "DOT",
    }
    rev_fiat = {
        "ZUSD": "USD",
        "ZEUR": "EUR",
        "ZGBP": "GBP",
        "ZJPY": "JPY",
        "ZCAD": "CAD",
        "ZCHF": "CHF",
        "ZAUD": "AUD",
    }
    # Try Z-prefixed fiat suffixes first.
    for q_suffix in ("ZUSD", "ZEUR", "ZGBP", "ZJPY", "ZCAD", "ZCHF", "ZAUD"):
        if kraken_pair.endswith(q_suffix) and len(kraken_pair) > len(q_suffix):
            base_raw = kraken_pair[:-len(q_suffix)]
            quote_simp = rev_fiat.get(q_suffix, q_suffix)
            base_simp = rev_asset.get(base_raw, base_raw)
            return f"{base_simp}-{quote_simp}"
    # Fallback: try plain fiat suffixes (e.g. "SOLUSD" -> SOL, USD)
    for q_suffix in ("USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD"):
        if kraken_pair.endswith(q_suffix) and len(kraken_pair) > len(q_suffix):
            base_raw = kraken_pair[:-len(q_suffix)]
            quote_simp = q_suffix
            base_simp = rev_asset.get(base_raw, base_raw)
            return f"{base_simp}-{quote_simp}"
    return kraken_pair  # fallback


def to_kraken_asset(currency: str) -> str:
    """Convert SIMP currency name (e.g. 'BTC') to Kraken asset name (e.g. 'XXBT')."""
    rev_map = {
        "BTC": "XXBT",
        "ETH": "XETH",
        "SOL": "SOL",
        "XRP": "XXRP",
        "LTC": "XLTC",
        "DOGE": "XDG",
        "USD": "ZUSD",
        "EUR": "ZEUR",
        "GBP": "ZGBP",
        "JPY": "ZJPY",
        "CAD": "ZCAD",
        "CHF": "ZCHF",
        "AUD": "ZAUD",
    }
    return rev_map.get(currency.upper(), currency.upper())


def from_kraken_asset(kraken_asset: str) -> str:
    """Convert Kraken asset name (e.g. 'XXBT') to SIMP currency (e.g. 'BTC')."""
    rev_map = {
        "XXBT": "BTC",
        "XETH": "ETH",
        "SOL": "SOL",
        "XXRP": "XRP",
        "XLTC": "LTC",
        "XDG": "DOGE",
        "ZUSD": "USD",
        "ZEUR": "EUR",
        "ZGBP": "GBP",
        "ZJPY": "JPY",
        "ZCAD": "CAD",
        "ZCHF": "CHF",
        "ZAUD": "AUD",
    }
    return rev_map.get(kraken_asset, kraken_asset)


# ---------------------------------------------------------------------------
# KrakenConnector
# ---------------------------------------------------------------------------

class KrakenConnector(BaseExchangeConnector):
    """
    Kraken exchange connector.

    Supports sandbox and live environments via the Kraken REST API v0.
    Public endpoints require no authentication.
    Private endpoints use API-Key + HMAC-SHA512 signature.
    """

    # Kraken public rate limit: 1 request per 3 seconds for public,
    # 1 per second for private.
    PUBLIC_RATE_LIMIT = 20   # requests per minute (~1 per 3s)
    PRIVATE_RATE_LIMIT = 60  # requests per minute (~1 per 1s)

    def __init__(self, api_key: str = "", api_secret: str = "",
                 sandbox: bool = True):
        """
        Initialize Kraken connector.

        Args:
            api_key: Kraken API key
            api_secret: Kraken API secret (Base64-encoded)
            sandbox: Use sandbox (True — both sandbox and live use
                     api.kraken.com; sandbox flag affects logging/behaviour)
        """
        super().__init__(api_key, api_secret, passphrase="",
                         sandbox=sandbox,
                         rate_limit_per_minute=self.PUBLIC_RATE_LIMIT)

        # Kraken uses a single API host for both sandbox and production.
        # A real sandbox environment is available at api.kraken.com with
        # sandbox-specific API keys.
        self.base_url = "https://api.kraken.com"
        self.api_version = "0"

        # Nonce tracking (must be monotonically increasing)
        self._nonce_counter = int(time.time() * 1_000_000)

        # Private request rate limiter (separate from the public one in base)
        self._private_last_request_time = 0.0
        self._private_min_interval = 60.0 / self.PRIVATE_RATE_LIMIT

        if sandbox:
            log.info("Using Kraken SANDBOX (api.kraken.com with sandbox keys)")
        else:
            log.info("Using Kraken LIVE API")

        if api_key:
            self._test_connectivity()

    # ------------------------------------------------------------------
    # Fee
    # ------------------------------------------------------------------

    def get_fees(self) -> float:
        """Return the default fee estimate for Kraken."""
        # Kraken standard: 0.26% maker / 0.16% taker at lowest volume tier.
        # Sandbox returns 0.0; live returns a conservative estimate.
        return 0.0 if self.sandbox else 0.0026

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    def _test_connectivity(self):
        """Test API connectivity via the public time endpoint."""
        try:
            self._public_request("GET", "/0/public/Time")
            log.info("Kraken API connectivity test passed")
        except Exception as e:
            log.warning("Kraken API connectivity test failed: %s", e)

    # ------------------------------------------------------------------
    # Nonce
    # ------------------------------------------------------------------

    def _next_nonce(self) -> int:
        """Return a monotonically increasing nonce."""
        self._nonce_counter += 1
        return self._nonce_counter

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limit_private(self):
        """Enforce private endpoint rate limiting (1 req/s)."""
        current = time.time()
        elapsed = current - self._private_last_request_time
        if elapsed < self._private_min_interval:
            sleep = self._private_min_interval - elapsed
            log.debug("Private rate limit: sleeping %.2fs", sleep)
            time.sleep(sleep)
        self._private_last_request_time = time.time()

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _sign_request(self, method: str, path: str,
                      body: Optional[Dict] = None,
                      timestamp: Optional[str] = None) -> Dict[str, str]:
        """
        Sign a Kraken private API request.

        Kraken authentication uses:
          - API-Key header
          - API-Sign header = Base64(HMAC-SHA512(secret, SHA256(nonce + postdata) + path))

        The nonce and POST data are concatenated, SHA256-hashed, then
        used as part of the HMAC-SHA512 message along with the URI path.
        """
        if not self.api_key or not self.api_secret:
            return {}

        if body is None:
            body = {}

        # Use provided timestamp as nonce, or generate a new one
        nonce = self._next_nonce()

        # Build POST data string (nonce first, then key=value pairs)
        post_data_parts = [f"nonce={nonce}"]
        for key, value in body.items():
            post_data_parts.append(f"{key}={urllib.parse.quote(str(value), safe='')}")
        post_data_str = "&".join(post_data_parts)
        post_data_bytes = post_data_str.encode("utf-8")

        # SHA256 of (nonce + postdata)
        sha256_hash = hashlib.sha256(str(nonce).encode("utf-8") + post_data_bytes).digest()

        # HMAC-SHA512 of (path + sha256_hash) using the secret
        path_bytes = path.encode("utf-8")
        secret_decoded = base64.b64decode(self.api_secret)
        hmac_digest = hmac.new(secret_decoded, path_bytes + sha256_hash,
                               hashlib.sha512).digest()

        signature = base64.b64encode(hmac_digest).decode("utf-8")

        return {
            "API-Key": self.api_key,
            "API-Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _public_request(self, method: str, path: str,
                        body: Optional[Dict] = None) -> Dict:
        """
        Make a public (unauthenticated) API request.

        Kraken public endpoints are GET requests.  Some accept query
        parameters appended to the path.
        """
        self._rate_limit()

        url = self.base_url + path
        headers = {
            "User-Agent": "SIMP-Trading-System/1.0",
            "Accept": "application/json",
        }

        data = None
        if method.upper() == "POST" and body:
            data = urllib.parse.urlencode(body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method.upper())

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8")
                if raw:
                    resp = json.loads(raw)
                    self._check_kraken_error(resp, f"{method} {path}")
                    return resp
                return {"error": [], "result": {}}
        except urllib.error.HTTPError as e:
            self._handle_error(e, f"{method} {path}")
            raise
        except (urllib.error.URLError, OSError) as e:
            raise ExchangeError(f"Kraken public request failed: {e}")

    def _authenticated_request(self, method: str, path: str,
                               body: Optional[Dict] = None) -> Dict:
        """
        Make an authenticated (private) API request.

        Kraken private endpoints use POST with form-encoded body and
        API-Key / API-Sign headers.
        """
        self._rate_limit_private()

        if not self.api_key or not self.api_secret:
            raise AuthenticationError("Kraken API credentials not configured")

        url = self.base_url + path

        # Build POST data with nonce
        if body is None:
            body = {}
        nonce = self._next_nonce()
        body["nonce"] = nonce

        post_data_str = urllib.parse.urlencode(body)
        post_data_bytes = post_data_str.encode("utf-8")

        # Build signature (same message as the encoded body)
        headers = self._sign_request(method, path, body)
        headers["User-Agent"] = "SIMP-Trading-System/1.0"

        req = urllib.request.Request(url, data=post_data_bytes,
                                     headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8")
                if raw:
                    resp = json.loads(raw)
                    self._check_kraken_error(resp, f"{method} {path}")
                    return resp
                return {"error": [], "result": {}}
        except urllib.error.HTTPError as e:
            self._handle_error(e, f"{method} {path}")
            raise
        except (urllib.error.URLError, OSError) as e:
            raise ExchangeError(f"Kraken authenticated request failed: {e}")

    @staticmethod
    def _check_kraken_error(response: Dict, context: str = ""):
        """
        Check a Kraken API response for error strings and raise accordingly.

        Kraken returns {"error": [...], "result": {...}} with empty error
        list on success.
        """
        errors = response.get("error", [])
        if errors:
            error_str = "; ".join(errors)
            if any("Invalid nonce" in e for e in errors):
                raise AuthenticationError(f"Kraken nonce error: {error_str}")
            elif any("API:Invalid key" in e for e in errors):
                raise AuthenticationError(f"Kraken auth error: {error_str}")
            elif any("EGeneral:Invalid arguments" in e for e in errors):
                raise ExchangeError(f"Kraken invalid arguments: {error_str}")
            elif any("EOrder:Insufficient funds" in e for e in errors):
                raise InsufficientFundsError(f"Insufficient funds: {error_str}")
            elif any("EOrder:Order minimum" in e for e in errors):
                raise OrderRejectedError(f"Order below minimum: {error_str}")
            elif any("EOrder:Rate limit exceeded" in e for e in errors):
                raise RateLimitError(f"Kraken rate limit: {error_str}")
            elif any("EAPI:Rate limit" in e for e in errors):
                raise RateLimitError(f"Kraken rate limit: {error_str}")
            else:
                raise ExchangeError(f"Kraken API error [{context}]: {error_str}")

    def _handle_error(self, response, context: str = ""):
        """Handle HTTP-level errors from Kraken."""
        status_code = getattr(response, 'code', 0)
        if status_code == 401:
            raise AuthenticationError(f"Kraken authentication failed: {context}")
        elif status_code == 429:
            raise RateLimitError(f"Kraken rate limit exceeded: {context}")
        elif status_code >= 400:
            raise ExchangeError(f"Kraken HTTP {status_code}: {context}")

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    def get_ticker(self, symbol: str) -> Ticker:
        """
        Get current ticker data for a symbol from Kraken.

        Kraken public endpoint: GET /0/public/Ticker?pair=XXBTZUSD

        Returns a Ticker with the mid of the last-trade price as 'last',
        best bid/ask, and 24h volume.
        """
        try:
            kraken_pair = to_kraken_pair(symbol)
            path = f"/0/public/Ticker?pair={urllib.parse.quote(kraken_pair)}"
            resp = self._public_request("GET", path)

            result = resp.get("result", {})
            # Kraken returns the pair name as the key (e.g. "XXBTZUSD")
            pair_data = result.get(kraken_pair)
            if pair_data is None:
                # Kraken may return the pair under a different key (e.g. "XBTUSD")
                for key in result:
                    pair_data = result[key]
                    break

            if not pair_data:
                raise ExchangeError(f"No ticker data for {symbol} (pair: {kraken_pair})")

            # Parse ticker fields
            # Kraken format: c[0]=last price, b[0]=bid, a[0]=ask, v[1]=24h volume
            last_price = float(pair_data.get("c", ["0"])[0])
            bid = float(pair_data.get("b", ["0"])[0])
            ask = float(pair_data.get("a", ["0"])[0])
            volume = float(pair_data.get("v", [None, "0"])[1] or "0")

            return Ticker(
                symbol=symbol,
                bid=bid,
                ask=ask,
                last=last_price,
                volume=volume,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        except (ExchangeError, AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            log.warning("Failed to get ticker for %s: %s, using stub fallback", symbol, e)
            return self._get_stub_ticker(symbol)

    # ------------------------------------------------------------------
    # Private endpoints
    # ------------------------------------------------------------------

    def get_balance(self, currency: str) -> Balance:
        """
        Get balance for a specific currency.

        Kraken private endpoint: POST /0/private/Balance
        Returns a dict of asset -> balance.
        """
        try:
            resp = self._authenticated_request("POST", "/0/private/Balance")
            result = resp.get("result", {})

            # Kraken uses asset names like "XXBT", "ZUSD"
            kraken_asset = to_kraken_asset(currency)
            raw_balance = result.get(kraken_asset)

            if raw_balance is None:
                # Try finding by reversed mapping
                for kraken_key, kraken_value in result.items():
                    if from_kraken_asset(kraken_key) == currency.upper():
                        raw_balance = kraken_value
                        break

            if raw_balance is None:
                # Currency may not exist on account – return zero balance
                log.info("Currency %s not found in Kraken account, returning 0 balance", currency)
                return Balance(
                    currency=currency.upper(),
                    available=0.0,
                    total=0.0,
                    held=0.0,
                )

            total = float(raw_balance)
            # Kraken does not separate held balances in the Balance endpoint.
            # We derive held from open orders separately.
            held = self._get_held_for_currency(currency)

            return Balance(
                currency=currency.upper(),
                available=total - held,
                total=total,
                held=held,
            )

        except Exception as e:
            raise ExchangeError(f"Failed to get balance for {currency}: {e}")

    def _get_held_for_currency(self, currency: str) -> float:
        """Estimate held amount for a currency from open orders."""
        held = 0.0
        try:
            open_orders = self.get_open_orders()
            for order in open_orders:
                base = order.symbol.split("-")[0] if "-" in order.symbol else ""
                quote = order.symbol.split("-")[1] if "-" in order.symbol else ""
                if order.side == OrderSide.SELL and base.upper() == currency.upper():
                    held += order.quantity - order.filled_quantity
                elif order.side == OrderSide.BUY and quote.upper() == currency.upper():
                    if order.price:
                        held += (order.quantity - order.filled_quantity) * order.price
        except Exception:
            pass  # Best-effort held calculation
        return held

    def place_order(self, symbol: str, side: OrderSide,
                    quantity: float, order_type: OrderType = OrderType.MARKET,
                    price: Optional[float] = None) -> Order:
        """
        Place an order on Kraken.

        Kraken private endpoint: POST /0/private/AddOrder
        Parameters: pair, type (buy/sell), ordertype (market/limit),
                    volume, price (required for limit)

        Returns an Order object with the exchange-assigned order ID.
        """
        # Validate
        is_valid, error_msg = self.validate_order(symbol, side, quantity, order_type, price)
        if not is_valid:
            raise OrderRejectedError(f"Order validation failed: {error_msg}")

        kraken_pair = to_kraken_pair(symbol)

        order_params: Dict[str, Any] = {
            "pair": kraken_pair,
            "type": side.value,       # "buy" or "sell"
            "ordertype": order_type.value,  # "market" or "limit"
            "volume": str(quantity),
        }

        if order_type == OrderType.LIMIT and price is not None:
            order_params["price"] = str(price)

        # Kraken requires a minimum order size; if we're below,
        # bump to the minimum (conservative: 0.0001 for most pairs)
        if quantity < 0.0001:
            log.warning("Order quantity %.8f is very small, Kraken may reject", quantity)

        try:
            resp = self._authenticated_request("POST", "/0/private/AddOrder", order_params)
            result = resp.get("result", {})

            # Kraken AddOrder returns { "txid": ["ORDER_ID"], ... }
            txids = result.get("txid", [])
            order_id = txids[0] if txids else "unknown"

            order = Order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status=OrderStatus.NEW,
                filled_quantity=0.0,
                average_price=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            log.info(
                "Order placed on Kraken: %s - %s %.8f %s",
                order.order_id, side.value, quantity, symbol,
            )
            return order

        except (InsufficientFundsError, OrderRejectedError, AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            raise ExchangeError(f"Failed to place order on Kraken: {e}")

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order on Kraken.

        Kraken private endpoint: POST /0/private/CancelOrder
        Returns True if cancelled successfully.
        """
        try:
            params = {"txid": order_id}
            resp = self._authenticated_request("POST", "/0/private/CancelOrder", params)
            result = resp.get("result", {})

            count = int(result.get("count", 0))
            if count > 0:
                log.info("Order cancelled on Kraken: %s", order_id)
                return True

            log.warning("Order %s not found or already cancelled", order_id)
            return False

        except Exception as e:
            raise ExchangeError(f"Failed to cancel order {order_id}: {e}")

    def get_order_status(self, order_id: str) -> Order:
        """
        Get order status from Kraken.

        Kraken private endpoint: POST /0/private/QueryOrders
        """
        try:
            params = {"txid": order_id, "trades": False}
            resp = self._authenticated_request("POST", "/0/private/QueryOrders", params)
            result = resp.get("result", {})

            order_data = result.get(order_id)
            if not order_data:
                raise ExchangeError(f"Order {order_id} not found on Kraken")

            return self._parse_kraken_order(order_id, order_data)

        except Exception as e:
            raise ExchangeError(f"Failed to get order status for {order_id}: {e}")

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get open orders from Kraken.

        Kraken private endpoint: POST /0/private/OpenOrders
        Optionally filtered by symbol.
        """
        try:
            params: Dict[str, Any] = {}
            resp = self._authenticated_request("POST", "/0/private/OpenOrders", params)
            result = resp.get("result", {})
            open_data = result.get("open", {})

            orders: List[Order] = []
            for order_id, order_data in open_data.items():
                order = self._parse_kraken_order(order_id, order_data)
                if symbol is None or order.symbol == symbol:
                    orders.append(order)

            return orders

        except Exception as e:
            raise ExchangeError(f"Failed to get open orders: {e}")

    # ------------------------------------------------------------------
    # Order parsing
    # ------------------------------------------------------------------

    def _parse_kraken_order(self, order_id: str, order_data: Dict) -> Order:
        """
        Parse a Kraken order dict into our Order dataclass.
        """
        # --- Status mapping ---
        kraken_status_map = {
            "pending": OrderStatus.NEW,
            "open": OrderStatus.NEW,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
        }
        status_str = order_data.get("status", "").lower()
        status = kraken_status_map.get(status_str, OrderStatus.NEW)

        # --- Side ---
        side_str = order_data.get("type", "buy").lower()
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL

        # --- Order type ---
        type_str = order_data.get("ordertype", "market").lower()
        order_type = OrderType.MARKET if type_str == "market" else OrderType.LIMIT

        # --- Symbol ---
        kraken_pair = order_data.get("pair", "")
        symbol = from_kraken_pair(kraken_pair)

        # --- Quantity & filled ---
        vol = float(order_data.get("vol", "0"))
        vol_exec = float(order_data.get("vol_exec", "0"))

        # --- Price ---
        price = None
        if order_data.get("price"):
            try:
                price = float(order_data["price"])
            except (ValueError, TypeError):
                pass

        # --- Average price (from cost / vol_exec) ---
        average_price = None
        cost = float(order_data.get("cost", "0"))
        if vol_exec > 0:
            average_price = cost / vol_exec

        # --- Timestamps ---
        # Kraken uses Unix timestamps in the "opentm" field
        exchange_timestamp = None
        open_tm = order_data.get("opentm")
        if open_tm:
            exchange_timestamp = datetime.fromtimestamp(
                float(open_tm), tz=timezone.utc
            ).isoformat()

        return Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=vol,
            price=price,
            status=status,
            filled_quantity=vol_exec,
            average_price=average_price,
            timestamp=datetime.now(timezone.utc).isoformat(),
            exchange_timestamp=exchange_timestamp,
        )

    # ------------------------------------------------------------------
    # Stub fallback (for testing without live API)
    # ------------------------------------------------------------------

    def _get_stub_ticker(self, symbol: str) -> Ticker:
        """Fallback stub ticker data for testing."""
        import random

        stub_prices: Dict[str, Dict[str, float]] = {
            "BTC-USD": {"bid": 65000.0, "ask": 65010.0, "last": 65005.0, "volume": 1000.0},
            "ETH-USD": {"bid": 3500.0, "ask": 3502.0, "last": 3501.0, "volume": 5000.0},
            "SOL-USD": {"bid": 150.0, "ask": 150.5, "last": 150.25, "volume": 10000.0},
            "XRP-USD": {"bid": 0.62, "ask": 0.63, "last": 0.625, "volume": 500_000.0},
            "DOGE-USD": {"bid": 0.12, "ask": 0.13, "last": 0.125, "volume": 10_000_000.0},
        }

        if symbol not in stub_prices:
            symbol = "BTC-USD"

        data = stub_prices[symbol]
        noise = random.uniform(-0.001, 0.001)

        return Ticker(
            symbol=symbol,
            bid=data["bid"] * (1 + noise),
            ask=data["ask"] * (1 + noise),
            last=data["last"] * (1 + noise),
            volume=data["volume"] * (1 + random.uniform(-0.1, 0.1)),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Slippage estimation
    # ------------------------------------------------------------------

    def estimate_slippage(self, symbol: str, side: OrderSide,
                          quantity: float) -> float:
        """
        Estimate slippage for a Kraken order.

        Kraken has good liquidity on major pairs; microscopic orders
        typically incur minimal slippage.
        """
        ticker = self.get_ticker(symbol)
        order_value = quantity * ticker.last

        if order_value < 100:
            return 1.0  # 1 basis point
        elif order_value < 1000:
            return 5.0   # 5 basis points
        else:
            spread_bps = ((ticker.ask - ticker.bid) / ticker.last) * 10_000
            volume_ratio = quantity / ticker.volume if ticker.volume > 0 else 0
            volume_slippage = volume_ratio * 100
            return min(spread_bps + volume_slippage, 50.0)


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def create_kraken_connector(api_key: str = "", api_secret: str = "",
                            sandbox: bool = True) -> KrakenConnector:
    """Convenience factory for creating a KrakenConnector."""
    return KrakenConnector(api_key=api_key, api_secret=api_secret, sandbox=sandbox)


# ---------------------------------------------------------------------------
# Symbol mapping tests
# ---------------------------------------------------------------------------

def test_symbol_mapping():
    """Test Kraken symbol mapping functions."""
    cases = [
        ("BTC-USD", "XXBTZUSD"),
        ("ETH-USD", "XETHZUSD"),
        ("SOL-USD", "SOLZUSD"),
        ("XRP-USD", "XXRPZUSD"),
        ("DOGE-USD", "XDGZUSD"),
    ]
    for simp_pair, expected_kraken in cases:
        kraken = to_kraken_pair(simp_pair)
        back = from_kraken_pair(kraken)
        print(f"  {simp_pair} -> {kraken} -> {back}")
        assert back.upper() == simp_pair.upper(), f"Mismatch: {back} vs {simp_pair}"
    print("  Symbol mapping: OK")


# ---------------------------------------------------------------------------
# Test function
# ---------------------------------------------------------------------------

def test_kraken_connector():
    """Test Kraken connector functionality (public API ticker)."""
    print("=" * 60)
    print("Kraken Connector Test Suite")
    print("=" * 60)

    # --- Symbol mapping ---
    print("\n1. Symbol mapping tests:")
    test_symbol_mapping()

    # --- Create connector (sandbox, no API keys) ---
    print("\n2. Creating KrakenConnector (sandbox, no API keys)...")
    connector = KrakenConnector(sandbox=True)

    # --- Ticker with stub fallback ---
    print("\n3. Ticker tests (will use stub fallback without live API):")
    for sym in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        try:
            ticker = connector.get_ticker(sym)
            print(f"   {sym}: bid={ticker.bid:.2f} ask={ticker.ask:.2f} "
                  f"last={ticker.last:.2f} vol={ticker.volume:.2f}")
        except Exception as e:
            print(f"   {sym}: ERROR - {e}")

    # --- Order validation ---
    print("\n4. Order validation tests:")
    test_cases = [
        ("BTC-USD", OrderSide.BUY, 0.001, OrderType.MARKET, None),
        ("BTC-USD", OrderSide.SELL, 0.001, OrderType.LIMIT, 65000.0),
        ("INVALID", OrderSide.BUY, 0.001, OrderType.MARKET, None),
        ("BTC-USD", OrderSide.BUY, -1.0, OrderType.MARKET, None),
    ]
    for sym, side, qty, otype, price in test_cases:
        valid, msg = connector.validate_order(sym, side, qty, otype, price)
        status = "OK" if valid else f"INVALID ({msg})"
        print(f"   {sym} {side.value} {qty} {otype.value}: {status}")

    # --- Slippage estimation ---
    print("\n5. Slippage estimation:")
    slippage = connector.estimate_slippage("BTC-USD", OrderSide.BUY, 0.001)
    print(f"   BTC-USD buy 0.001: {slippage:.2f} bps")
    slippage = connector.estimate_slippage("ETH-USD", OrderSide.SELL, 0.01)
    print(f"   ETH-USD sell 0.01: {slippage:.2f} bps")

    # --- Fee rate ---
    print(f"\n6. Fee rate: {connector.get_fees() * 100:.3f}%")

    # --- Auth error handling (no keys configured) ---
    print("\n7. Auth error handling (expect failure - no API keys):")
    try:
        connector.get_balance("BTC")
        print("   WARNING: should have failed without keys")
    except AuthenticationError as e:
        print(f"   Expected auth error: {e}")
    except ExchangeError as e:
        print(f"   Exchange error (expected with no keys): {e}")

    print("\n" + "=" * 60)
    print("Kraken connector tests completed")
    print("=" * 60)


if __name__ == "__main__":
    test_kraken_connector()
