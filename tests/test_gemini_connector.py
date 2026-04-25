"""
Tests for Gemini Exchange Connector — T21
=========================================
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
        with patch.object(connector, 'get_spot_price', new_callable=AsyncMock) as mock_price:
            mock_price.return_value = 50000.0
            result = await connector.get_spot_price('BTC-USD')
            assert result == 50000.0

    @pytest.mark.asyncio
    async def test_get_spot_price_invalid_response(self, connector):
        """Test handling of invalid response."""
        with patch.object(connector, '_get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = ValueError('Invalid response')
            with pytest.raises(ValueError):
                await connector.get_spot_price('INVALID')

    @pytest.mark.asyncio
    async def test_get_order_book_success(self, connector):
        """Test successful order book fetching."""
        from simp.organs.quantumarb.connectors.gemini_connector import OrderBook
        with patch.object(connector, 'get_order_book', new_callable=AsyncMock) as mock_book:
            mock_book.return_value = OrderBook(
                symbol='BTC-USD',
                bids=[(100.0, 1.0)],
                asks=[(101.0, 1.5)]
            )
            result = await connector.get_order_book('BTC-USD')
            assert result.best_bid == 100.0
            assert result.best_ask == 101.0
