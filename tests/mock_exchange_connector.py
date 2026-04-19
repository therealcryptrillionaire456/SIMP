from typing import Dict, List, TypedDict

class OrderBook(TypedDict):
    bids: List[List[float]]
    asks: List[List[float]]

class MockExchangeConnector:
    """Mock exchange connector for testing."""

    def __init__(self, fees: float = 0.001):
        self.fees = fees
        self.tickers = {"market1": 100.0, "market2": 101.0, "market3": 100.0}

    def get_ticker(self, market: str) -> float:
        """Return a mock ticker price for the given market."""
        return self.tickers.get(market, 0.0)

    def get_orderbook(self, market: str) -> OrderBook:
        """Return a mock orderbook for the given market."""
        return {"bids": [[self.tickers[market], 1.0]], "asks": [[self.tickers[market], 1.0]]}

    def get_fees(self) -> float:
        """Return the mock fee rate."""
        return self.fees