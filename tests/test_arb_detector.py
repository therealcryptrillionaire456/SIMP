import pytest
import time
from unittest.mock import Mock, patch
from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity
from simp.organs.quantumarb.exchange_connector import StubExchangeConnector
import json
import os
import tempfile


def test_calculate_spread_bps():
    """Test that calculate_spread_bps returns the correct spread value."""
    # Create a mock exchange
    mock_exchange = Mock()
    arb = ArbDetector(exchanges={"test_exchange": mock_exchange}, threshold_bps=10.0)
    
    # Test with price_a > price_b
    spread = arb.calculate_spread_bps(100.0, 99.0)
    # (100-99)/99 * 10000 = 101.01 bps
    expected_spread = ((100.0 - 99.0) / 99.0) * 10000
    assert spread == pytest.approx(expected_spread)
    
    # Test with price_b > price_a
    spread = arb.calculate_spread_bps(99.0, 100.0)
    # (100-99)/99 * 10000 = 101.01 bps
    expected_spread = ((100.0 - 99.0) / 99.0) * 10000
    assert spread == pytest.approx(expected_spread)


def test_arb_opportunity_is_profitable():
    """Test that ArbOpportunity.is_profitable returns True when spread > threshold."""
    # Create an opportunity with profitable spread (101.01 bps > 100 bps threshold)
    opportunity = ArbOpportunity(
        exchange_a="exchange_a",
        exchange_b="exchange_b",
        market_a="BTC-USD",
        market_b="BTC-USD",  # Same market on different exchanges
        price_a=100.0,
        price_b=99.0,
        spread_bps=101.01,
        estimated_profit=1.01,
        timestamp=time.time()
    )
    
    # Test with threshold 50 bps (0.5%) and fees 5 bps (0.05%)
    # Net spread = 101.01 - 5 = 96.01 bps > 50 bps threshold
    assert opportunity.is_profitable(threshold_bps=50.0, fees_bps=5.0) is True
    
    # Create an opportunity with unprofitable spread (50.25 bps < 100 bps threshold)
    opportunity = ArbOpportunity(
        exchange_a="exchange_a",
        exchange_b="exchange_b",
        market_a="BTC-USD",
        market_b="BTC-USD",  # Same market on different exchanges
        price_a=100.0,
        price_b=99.5,
        spread_bps=50.25,
        estimated_profit=0.5025,
        timestamp=time.time()
    )
    
    # Test with threshold 100 bps (1%) and fees 5 bps (0.05%)
    assert opportunity.is_profitable(threshold_bps=100.0, fees_bps=5.0) is False


def test_log_opportunity():
    """Test that _log_opportunity writes a record to JSONL and can be parsed back."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock exchange
        mock_exchange = Mock()
        arb = ArbDetector(exchanges={"test_exchange": mock_exchange}, threshold_bps=10.0, log_dir=tmpdir)
        
        opportunity = ArbOpportunity(
            market_a="BTC/USD",
            market_b="ETH/USD",
            exchange_a="exchange_a",
            exchange_b="exchange_b",
            price_a=100.0,
            price_b=99.0,
            spread_bps=101.01,
            estimated_profit=1.01,
            confidence=0.8,
            timestamp=1234567890.0,
        )
        
        arb._log_opportunity(opportunity)
        
        # Check the log file was created
        log_file = os.path.join(tmpdir, "arb_opportunities.jsonl")
        assert os.path.exists(log_file)
        
        # Read and parse the log entry
        with open(log_file, "r") as f:
            record = json.loads(f.readline())
        
        assert record["market_a"] == "BTC/USD"
        assert record["market_b"] == "ETH/USD"
        assert record["price_a"] == 100.0
        assert record["price_b"] == 99.0
        assert record["timestamp"] == 1234567890.0


def test_scan_markets_no_opportunity():
    """Test that scan_markets returns an empty list when all prices are equal."""
    # Create mock exchanges that return the same price
    mock_exchange1 = Mock()
    mock_exchange1.get_ticker.return_value = 100.0
    mock_exchange1.get_fees.return_value = 0.001
    mock_exchange1.name = "exchange1"
    
    mock_exchange2 = Mock()
    mock_exchange2.get_ticker.return_value = 100.0
    mock_exchange2.get_fees.return_value = 0.001
    mock_exchange2.name = "exchange2"
    
    arb = ArbDetector(
        exchanges={"exchange1": mock_exchange1, "exchange2": mock_exchange2},
        threshold_bps=10.0
    )
    
    # Scan markets with equal prices (no arbitrage opportunity)
    markets = ["BTC-USD"]
    exchanges = ["exchange1", "exchange2"]
    opportunities = arb.scan_markets(markets, exchanges)
    
    assert opportunities == []


def test_scan_markets_with_opportunity():
    """Test that scan_markets detects arbitrage opportunities."""
    # Create mock exchanges with different prices
    mock_exchange1 = Mock()
    mock_exchange1.get_ticker.return_value = 100.0
    mock_exchange1.get_fees.return_value = 0.001  # 0.1% fee
    mock_exchange1.name = "exchange1"
    
    mock_exchange2 = Mock()
    mock_exchange2.get_ticker.return_value = 99.0  # Different price creates opportunity
    mock_exchange2.get_fees.return_value = 0.001  # 0.1% fee
    mock_exchange2.name = "exchange2"
    
    arb = ArbDetector(
        exchanges={"exchange1": mock_exchange1, "exchange2": mock_exchange2},
        threshold_bps=10.0
    )
    
    # Scan markets - should detect opportunity between exchanges
    markets = ["BTC-USD"]
    exchanges = ["exchange1", "exchange2"]
    opportunities = arb.scan_markets(markets, exchanges, quantity=1.0)
    
    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity.market_a == "BTC-USD"
    assert opportunity.market_b == "BTC-USD"
    # exchange2 is cheaper (99.0) so it should be exchange_a (buy)
    # exchange1 is more expensive (100.0) so it should be exchange_b (sell)
    assert opportunity.exchange_a == "exchange2"
    assert opportunity.exchange_b == "exchange1"
    assert opportunity.price_a == 99.0  # buy price (cheaper)
    assert opportunity.price_b == 100.0  # sell price (more expensive)
    assert opportunity.spread_bps > 0


def test_exchange_connector_fees():
    """Test that ExchangeConnector returns the expected fee value."""
    # Test StubExchangeConnector
    connector = StubExchangeConnector(prices={"BTC/USD": 100.0})
    assert connector.get_fees() == 0.001  # Default fee in StubExchangeConnector