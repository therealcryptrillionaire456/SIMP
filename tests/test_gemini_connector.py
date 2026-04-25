import time
"""
Tests for Gemini Exchange Connector — T21
=========================================
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestGeminiConnector:
    """Tests for GeminiConnector class."""

    @pytest.fixture
    def connector(self):
        """Create a GeminiConnector instance for testing."""
        from simp.organs.quantumarb.connectors.gemini_connector import (
            GeminiConnector,
        )
        return GeminiConnector(api_key="test_key", api_secret="test_secret")

    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session."""
        session = AsyncMock()
        session.closed = False
        return session

    def test_symbol_mapping(self, connector):
        """Test internal to Gemini symbol conversion."""
        assert connector._map_symbol("BTC-USD") == "btcusd"
        assert connector._map_symbol("ETH-USD") == "ethusd"
        assert connector._map_symbol("SOL-USD") == "solusd"
        # Test fallback for unknown symbols
        assert connector._map_symbol("UNKNOWN") == "unknown"

    def test_best_bid_ask(self, connector):
        """Test OrderBook best_bid and best_ask properties."""
        from simp.organs.quantumarb.connectors.gemini_connector import OrderBook
        book = OrderBook(
            symbol="BTC-USD",
            bids=[(100.0, 1.0), (99.0, 2.0)],
            asks=[(101.0, 1.5), (102.0, 0.5)],
        )
        assert book.best_bid == 100.0
        assert book.best_ask == 101.0

    def test_spread_bps(self, connector):
        """Test order book spread calculation in basis points."""
        from simp.organs.quantumarb.connectors.gemini_connector import OrderBook
        book = OrderBook(
            symbol="BTC-USD",
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
        )
        expected_spread = (101.0 - 100.0) / 100.5 * 10000
        assert abs(book.spread_bps - expected_spread) < 0.01

    def test_spread_bps_empty(self, connector):
        """Test spread calculation with empty book."""
        from simp.organs.quantumarb.connectors.gemini_connector import OrderBook
        book = OrderBook(symbol="BTC-USD", bids=[], asks=[])
        assert book.spread_bps == 0.0

    @pytest.mark.asyncio
    async def test_get_spot_price_success(self, connector):
        """Test successful price fetching."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"last": "50000.00"})
        
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        with patch.object(
            connector, "_get_session", new_callable=AsyncMock
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_context
            mock_get_session.return_value = mock_session
            
            price = await connector.get_spot_price("BTC-USD")
            assert price == 50000.00
            assert "BTC-USD" in connector._price_cache

    @pytest.mark.asyncio
    async def test_get_spot_price_invalid_response(self, connector):
        """Test price fetching with invalid response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"last": "invalid"})
        
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        with patch.object(
            connector, "_get_session", new_callable=AsyncMock
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_context
            mock_get_session.return_value = mock_session
            
            price = await connector.get_spot_price("BTC-USD")
            assert price == 0.0

    @pytest.mark.asyncio
    async def test_get_order_book_success(self, connector):
        """Test successful order book fetching."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "bids": [
                {"price": "100.0", "amount": "1.0"},
                {"price": "99.0", "amount": "2.0"},
            ],
            "asks": [
                {"price": "101.0", "amount": "1.5"},
            ],
        })
        
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        with patch.object(
            connector, "_get_session", new_callable=AsyncMock
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_context
            mock_get_session.return_value = mock_session
            
            book = await connector.get_order_book("BTC-USD")
            assert book.symbol == "BTC-USD"
            assert len(book.bids) == 2
            assert len(book.asks) == 1
            assert book.bids[0] == (100.0, 1.0)

    @pytest.mark.asyncio
    async def test_get_multi_prices(self, connector):
        """Test fetching multiple prices concurrently."""
        with patch.object(
            connector, "get_spot_price", new_callable=AsyncMock
        ) as mock_price:
            mock_price.side_effect = [50000.0, 3000.0, 100.0]
            
            prices = await connector.get_multi_prices(
                ["BTC-USD", "ETH-USD", "SOL-USD"]
            )
            assert prices["BTC-USD"] == 50000.0
            assert prices["ETH-USD"] == 3000.0
            assert prices["SOL-USD"] == 100.0

    @pytest.mark.asyncio
    async def test_get_multi_prices_with_failures(self, connector):
        """Test fetching multiple prices with some failures."""
        with patch.object(
            connector, "get_spot_price", new_callable=AsyncMock
        ) as mock_price:
            mock_price.side_effect = [
                50000.0,
                RuntimeError("API Error"),
                100.0,
            ]
            
            prices = await connector.get_multi_prices(
                ["BTC-USD", "ETH-USD", "SOL-USD"]
            )
            assert prices["BTC-USD"] == 50000.0
            assert prices["ETH-USD"] == 0.0  # Failed, returns 0
            assert prices["SOL-USD"] == 100.0

    def test_is_stale_fresh(self, connector):
        """Test stale detection for fresh price."""
        connector._price_cache["BTC-USD"] = (50000.0, time.time())
        assert connector.is_stale(50000.0, age_seconds=10.0) is False

    def test_is_stale_old(self, connector):
        """Test stale detection for old price."""
        connector._price_cache["BTC-USD"] = (50000.0, time.time() - 15.0)
        assert connector.is_stale(50000.0, age_seconds=10.0) is True

    def test_get_all_prices(self, connector):
        """Test retrieving all cached prices."""
        connector._price_cache["BTC-USD"] = (50000.0, time.time())
        connector._price_cache["ETH-USD"] = (3000.0, time.time())
        
        prices = connector.get_all_prices()
        assert prices["BTC-USD"] == 50000.0
        assert prices["ETH-USD"] == 3000.0

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, connector):
        """Test rate limit (429) retry logic."""
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                mock_resp = AsyncMock()
                mock_resp.status = 429
                mock_resp.text = AsyncMock(return_value="Rate limited")
                return mock_resp
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"last": "50000.0"})
            return mock_resp
        
        with patch.object(connector, "_get", side_effect=mock_get):
            result = await connector._get("/v1/pubticker/btcusd")
            assert result.get("last") == "50000.0"
            assert call_count >= 3  # Retried at least twice


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
