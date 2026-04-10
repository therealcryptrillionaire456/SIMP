"""
Exchange connector abstraction for QuantumArb organ.

Provides ABC for exchange connectors and implementations for various
exchanges. Supports both real and stub connectors for testing.
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import uuid


class OrderBookSide(str, Enum):
    """Order book side enumeration."""
    BID = "bid"
    ASK = "ask"


@dataclass
class OrderBookLevel:
    """A single level in the order book."""
    price: float
    quantity: float
    exchange_timestamp: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class OrderBook:
    """Complete order book for a market."""
    market: str
    timestamp: float
    bids: List[OrderBookLevel]  # Sorted descending (best bid first)
    asks: List[OrderBookLevel]  # Sorted ascending (best ask first)
    sequence_id: Optional[int] = None
    exchange: Optional[str] = None
    
    def get_best_bid(self) -> Optional[OrderBookLevel]:
        """Get the best (highest) bid."""
        return self.bids[0] if self.bids else None
    
    def get_best_ask(self) -> Optional[OrderBookLevel]:
        """Get the best (lowest) ask."""
        return self.asks[0] if self.asks else None
    
    def get_mid_price(self) -> Optional[float]:
        """Calculate mid price from best bid and ask."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if not best_bid or not best_ask:
            return None
        
        return (best_bid.price + best_ask.price) / 2
    
    def get_spread_bps(self) -> Optional[float]:
        """Calculate spread in basis points."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if not best_bid or not best_ask or best_bid.price <= 0:
            return None
        
        spread = best_ask.price - best_bid.price
        return (spread / best_bid.price) * 10000
    
    def get_depth(self, side: OrderBookSide, levels: int = 10) -> List[OrderBookLevel]:
        """Get order book depth for a given side."""
        if side == OrderBookSide.BID:
            return self.bids[:levels]
        else:
            return self.asks[:levels]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "market": self.market,
            "timestamp": self.timestamp,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
            "sequence_id": self.sequence_id,
            "exchange": self.exchange,
        }


@dataclass
class Ticker:
    """Market ticker information."""
    market: str
    last_price: float
    bid_price: float
    ask_price: float
    volume_24h: float
    timestamp: float
    exchange: Optional[str] = None
    
    def get_spread_bps(self) -> float:
        """Calculate spread in basis points."""
        if self.bid_price <= 0:
            return 0.0
        spread = self.ask_price - self.bid_price
        return (spread / self.bid_price) * 10000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class Trade:
    """A single trade execution."""
    trade_id: str
    market: str
    side: str  # "buy" or "sell"
    price: float
    quantity: float
    timestamp: float
    exchange: Optional[str] = None
    fee: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ExchangeConnector(ABC):
    """
    Abstract base class for exchange connectors.
    
    All exchange connectors must implement these methods.
    """
    
    @abstractmethod
    def get_name(self) -> str:
        """Get exchange name."""
        pass
    
    @abstractmethod
    def get_ticker(self, market: str) -> Ticker:
        """Get ticker information for a market."""
        pass
    
    @abstractmethod
    def get_orderbook(self, market: str, depth: int = 10) -> OrderBook:
        """Get order book for a market."""
        pass
    
    @abstractmethod
    def get_fees(self) -> float:
        """
        Get trading fee rate.
        
        Returns:
            Fee rate as a decimal (e.g., 0.001 for 0.1%)
        """
        pass
    
    @abstractmethod
    def get_balance(self, currency: str) -> float:
        """Get balance for a currency."""
        pass
    
    @abstractmethod
    def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place an order on the exchange.
        
        Args:
            market: Market symbol
            side: "buy" or "sell"
            order_type: "market" or "limit"
            quantity: Order quantity
            price: Limit price (required for limit orders)
            
        Returns:
            Order response dictionary
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status."""
        pass
    
    def get_mid_price(self, market: str) -> Optional[float]:
        """Get mid price for a market."""
        ticker = self.get_ticker(market)
        if ticker.bid_price > 0 and ticker.ask_price > 0:
            return (ticker.bid_price + ticker.ask_price) / 2
        return None
    
    def get_spread_bps(self, market: str) -> float:
        """Get spread in basis points for a market."""
        ticker = self.get_ticker(market)
        return ticker.get_spread_bps()
    
    def is_market_open(self, market: str) -> bool:
        """Check if a market is open for trading."""
        try:
            ticker = self.get_ticker(market)
            return ticker.bid_price > 0 and ticker.ask_price > 0
        except Exception:
            return False


class StubExchangeConnector(ExchangeConnector):
    """
    Stub exchange connector for testing.
    
    Uses predefined prices and order books.
    """
    
    def __init__(
        self,
        name: str = "stub",
        prices: Optional[Dict[str, float]] = None,
        orderbooks: Optional[Dict[str, OrderBook]] = None,
        fee_rate: float = 0.001,
        balances: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize stub exchange connector.
        
        Args:
            name: Exchange name
            prices: Dictionary of market -> price
            orderbooks: Dictionary of market -> OrderBook
            fee_rate: Trading fee rate
            balances: Dictionary of currency -> balance
        """
        self.name = name
        self.prices = prices or {"BTC-USD": 50000.0, "ETH-USD": 3000.0}
        self.orderbooks = orderbooks or {}
        self.fee_rate = fee_rate
        self.balances = balances or {"USD": 100000.0, "BTC": 10.0, "ETH": 100.0}
        
        # Initialize orderbooks if not provided
        for market, price in self.prices.items():
            if market not in self.orderbooks:
                self.orderbooks[market] = self._create_stub_orderbook(market, price)
        
        # Order tracking
        self.orders: Dict[str, Dict[str, Any]] = {}
    
    def _create_stub_orderbook(self, market: str, mid_price: float) -> OrderBook:
        """Create a stub order book."""
        spread = mid_price * 0.001  # 0.1% spread
        
        bids = []
        asks = []
        
        # Create 10 levels on each side
        for i in range(10):
            bid_price = mid_price - (spread * (i + 1) / 10)
            ask_price = mid_price + (spread * (i + 1) / 10)
            
            bids.append(OrderBookLevel(
                price=bid_price,
                quantity=1.0 - (i * 0.1),
                exchange_timestamp=time.time()
            ))
            
            asks.append(OrderBookLevel(
                price=ask_price,
                quantity=1.0 - (i * 0.1),
                exchange_timestamp=time.time()
            ))
        
        return OrderBook(
            market=market,
            timestamp=time.time(),
            bids=bids,
            asks=asks,
            exchange=self.name,
        )
    
    def get_name(self) -> str:
        return self.name
    
    def get_ticker(self, market: str) -> Ticker:
        if market not in self.prices:
            raise ValueError(f"Market not found: {market}")
        
        price = self.prices[market]
        spread = price * 0.001  # 0.1% spread
        
        return Ticker(
            market=market,
            last_price=price,
            bid_price=price - (spread / 2),
            ask_price=price + (spread / 2),
            volume_24h=1000.0,
            timestamp=time.time(),
            exchange=self.name,
        )
    
    def get_orderbook(self, market: str, depth: int = 10) -> OrderBook:
        if market not in self.orderbooks:
            raise ValueError(f"Market not found: {market}")
        
        orderbook = self.orderbooks[market]
        
        # Return limited depth
        return OrderBook(
            market=market,
            timestamp=time.time(),
            bids=orderbook.bids[:depth],
            asks=orderbook.asks[:depth],
            sequence_id=None,
            exchange=self.name,
        )
    
    def get_fees(self) -> float:
        return self.fee_rate
    
    def get_balance(self, currency: str) -> float:
        return self.balances.get(currency.upper(), 0.0)
    
    def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        order_id = f"order-{uuid.uuid4().hex[:8]}"
        
        # Validate market
        if market not in self.prices:
            raise ValueError(f"Market not found: {market}")
        
        # Validate quantity
        if quantity <= 0:
            raise ValueError(f"Invalid quantity: {quantity}")
        
        # For market orders, use current price
        if order_type == "market":
            ticker = self.get_ticker(market)
            if side == "buy":
                price = ticker.ask_price
            else:
                price = ticker.bid_price
        elif order_type == "limit":
            if price is None or price <= 0:
                raise ValueError("Limit price required for limit orders")
        else:
            raise ValueError(f"Unsupported order type: {order_type}")
        
        # Check balance (simplified)
        if side == "buy":
            cost = quantity * price
            usd_balance = self.get_balance("USD")
            if cost > usd_balance:
                raise ValueError(f"Insufficient USD balance: {usd_balance} < {cost}")
        else:  # sell
            # Check if we have the asset
            asset = market.split("-")[0]  # Extract base currency
            asset_balance = self.get_balance(asset)
            if quantity > asset_balance:
                raise ValueError(f"Insufficient {asset} balance: {asset_balance} < {quantity}")
        
        # Create order record
        order = {
            "order_id": order_id,
            "market": market,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "status": "filled" if order_type == "market" else "open",
            "filled_quantity": quantity if order_type == "market" else 0.0,
            "remaining_quantity": 0.0 if order_type == "market" else quantity,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        
        self.orders[order_id] = order
        
        # Update balances for market orders
        if order_type == "market":
            self._update_balances_for_trade(market, side, quantity, price)
        
        return order
    
    def _update_balances_for_trade(
        self,
        market: str,
        side: str,
        quantity: float,
        price: float,
    ) -> None:
        """Update balances after a trade."""
        base_currency, quote_currency = market.split("-")
        
        if side == "buy":
            # Spend quote currency, receive base currency
            cost = quantity * price
            fee = cost * self.fee_rate
            
            self.balances[quote_currency] -= (cost + fee)
            self.balances[base_currency] = self.balances.get(base_currency, 0.0) + quantity
        else:  # sell
            # Spend base currency, receive quote currency
            proceeds = quantity * price
            fee = proceeds * self.fee_rate
            
            self.balances[base_currency] -= quantity
            self.balances[quote_currency] = self.balances.get(quote_currency, 0.0) + (proceeds - fee)
    
    def cancel_order(self, order_id: str) -> bool:
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        if order["status"] == "open":
            order["status"] = "cancelled"
            order["updated_at"] = time.time()
            return True
        
        return False
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        if order_id not in self.orders:
            raise ValueError(f"Order not found: {order_id}")
        
        return self.orders[order_id].copy()
    
    def update_price(self, market: str, price: float) -> None:
        """Update price for a market (for testing)."""
        self.prices[market] = price
        if market in self.orderbooks:
            self.orderbooks[market] = self._create_stub_orderbook(market, price)


# Factory functions for creating connectors
def create_stub_connector(
    name: str = "stub",
    prices: Optional[Dict[str, float]] = None,
    **kwargs
) -> StubExchangeConnector:
    """
    Create a stub exchange connector.
    
    Args:
        name: Exchange name
        prices: Dictionary of market -> price
        **kwargs: Additional arguments for StubExchangeConnector
        
    Returns:
        StubExchangeConnector instance
    """
    return StubExchangeConnector(name=name, prices=prices, **kwargs)


def create_connector_from_config(config: Dict[str, Any]) -> ExchangeConnector:
    """
    Create an exchange connector from configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        ExchangeConnector instance
        
    Raises:
        ValueError: If connector type is not supported
    """
    connector_type = config.get("type", "stub")
    
    if connector_type == "stub":
        return create_stub_connector(
            name=config.get("name", "stub"),
            prices=config.get("prices"),
            fee_rate=config.get("fee_rate", 0.001),
            balances=config.get("balances"),
        )
    else:
        raise ValueError(f"Unsupported connector type: {connector_type}")