"""
GEMINI Exchange Connector — T21
===============================
Public price feed and order book from Gemini exchange API.
https://docs.gemini.com/rest-api/

Endpoints used:
  GET /v1/pubticker/{symbol}  — last price + 24h volume + timestamp
  GET /v1/book/{symbol}       — bid/ask ladder
  GET /v1/price/{symbol}      — simple last price

Supports: BTCUSD, ETHUSD, SOLUSD
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

log = logging.getLogger("gemini_connector")


@dataclass
class OrderBook:
    """A single side of an order book (bids or asks)."""
    symbol: str
    bids: List[Tuple[float, float]] = field(default_factory=list)  # (price, size)
    asks: List[Tuple[float, float]] = field(default_factory=list)  # (price, size)
    timestamp: float = field(default_factory=time.time)
    
    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 0.0
    
    @property
    def spread_bps(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        mid = (self.best_bid + self.best_ask) / 2
        if mid == 0:
            return 0.0
        return (self.best_ask - self.best_bid) / mid * 10000


class GeminiConnector:
    BASE_URL = "https://api.gemini.com"
    TIMEOUT_SECONDS = 5
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 1.0
    MAX_PRICE_AGE_SECONDS = 10.0
    
    # Symbol mapping: internal -> Gemini API
    SYMBOL_MAP = {
        "BTC-USD": "btcusd",
        "ETH-USD": "ethusd",
        "SOL-USD": "solusd",
    }
    
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self._session: Optional[aiohttp.ClientSession] = None
        self._price_cache: Dict[str, Tuple[float, float]] = {}  # symbol -> (price, timestamp)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError(
                "aiohttp is not installed. Install it with: pip install aiohttp"
            )
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT_SECONDS)
            )
        return self._session
    
    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _map_symbol(self, symbol: str) -> str:
        """Map internal symbol format to Gemini API format."""
        return self.SYMBOL_MAP.get(symbol, symbol.lower().replace("-", ""))
    
    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request with retry logic."""
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError(
                "aiohttp is not installed. Install it with: pip install aiohttp"
            )
        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"
        for attempt in range(self.MAX_RETRIES):
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status == 429:
                        wait_time = self.RETRY_DELAY_SECONDS * (attempt + 1)
                        log.warning(
                            "Gemini rate limited. Retrying in %.1f seconds (attempt %d/%d)",
                            wait_time, attempt + 1, self.MAX_RETRIES
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"Gemini API error {resp.status}: {text}")
                    return await resp.json()
            except aiohttp.ClientError as e:
                if attempt == self.MAX_RETRIES - 1:
                    log.error("Gemini API request failed after %d attempts: %s", self.MAX_RETRIES, e)
                    raise
                await asyncio.sleep(self.RETRY_DELAY_SECONDS * (attempt + 1))
        return {}
    
    async def get_spot_price(self, symbol: str) -> float:
        """
        Get last traded price for a symbol.
        Returns price as float. Raises RuntimeError on failure.
        """
        if not _AIOHTTP_AVAILABLE:
            log.warning("aiohttp not available, cannot fetch price for %s", symbol)
            return 0.0
        gemini_sym = self._map_symbol(symbol)
        data = await self._get(f"/v1/pubticker/{gemini_sym}")
        price_str = data.get("last", "0")
        try:
            price = float(price_str)
        except (ValueError, TypeError):
            log.warning("Could not parse price for %s: %s", symbol, price_str)
            price = 0.0
        if price > 0:
            self._price_cache[symbol] = (price, time.time())
        return price
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> OrderBook:
        """Get bid/ask ladder for a symbol."""
        if not _AIOHTTP_AVAILABLE:
            log.warning("aiohttp not available, cannot fetch order book for %s", symbol)
            return OrderBook(symbol=symbol)
        gemini_sym = self._map_symbol(symbol)
        params = {"limit_bids": limit, "limit_asks": limit}
        data = await self._get(f"/v1/book/{gemini_sym}", params=params)
        bids = []
        for b in data.get("bids", []):
            try:
                bids.append((float(b["price"]), float(b["amount"])))
            except (ValueError, TypeError, KeyError):
                continue
        asks = []
        for a in data.get("asks", []):
            try:
                asks.append((float(a["price"]), float(a["amount"])))
            except (ValueError, TypeError, KeyError):
                continue
        return OrderBook(symbol=symbol, bids=bids, asks=asks, timestamp=time.time())
    
    async def get_multi_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch multiple prices concurrently."""
        if not _AIOHTTP_AVAILABLE:
            log.warning("aiohttp not available, cannot fetch multiple prices")
            return {sym: 0.0 for sym in symbols}
        tasks = [self.get_spot_price(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        prices = {}
        for sym, result in zip(symbols, results):
            if isinstance(result, Exception):
                log.warning("Failed to fetch %s: %s", sym, result)
                prices[sym] = 0.0
            else:
                prices[sym] = result
        return prices
    
    def is_stale(self, price: float, age_seconds: float = MAX_PRICE_AGE_SECONDS) -> bool:
        """Check if price data is older than max_age_seconds."""
        for sym, (cached_px, cached_ts) in self._price_cache.items():
            if cached_px == price:
                return (time.time() - cached_ts) > age_seconds
        return True
    
    def get_all_prices(self) -> Dict[str, float]:
        """Return all cached prices (for use without async)."""
        return {sym: px for sym, (px, _) in self._price_cache.items()}
    
    def get_price_age(self, symbol: str) -> float:
        """Return the age in seconds of the cached price for a symbol."""
        if symbol not in self._price_cache:
            return float('inf')
        _, timestamp = self._price_cache[symbol]
        return time.time() - timestamp
    
    async def get_ticker_info(self, symbol: str) -> Dict:
        """Get full ticker information including volume and timestamp."""
        if not _AIOHTTP_AVAILABLE:
            log.warning("aiohttp not available, cannot fetch ticker for %s", symbol)
            return {}
        gemini_sym = self._map_symbol(symbol)
        data = await self._get(f"/v1/pubticker/{gemini_sym}")
        return {
            "symbol": symbol,
            "last": float(data.get("last", 0)),
            "bid": float(data.get("bid", 0)),
            "ask": float(data.get("ask", 0)),
            "volume": {
                "base": float(data.get("volume", {}).get("BTC", 0)) if isinstance(data.get("volume"), dict) else 0,
            },
            "timestamp": datetime.fromtimestamp(
                int(data.get("volume.timestamp", 0)) / 1000,
                tz=timezone.utc
            ).isoformat() if data.get("volume.timestamp") else None,
        }
