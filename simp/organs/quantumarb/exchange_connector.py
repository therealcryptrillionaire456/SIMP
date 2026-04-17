#!/usr/bin/env python3.10
"""
Exchange Connector Abstract Base Class and Base Implementation.

This module provides:
1. ExchangeConnector ABC - Abstract interface for all exchange connectors
2. StubExchangeConnector - For testing and sandbox mode
3. BaseExchangeConnector - Common functionality for real exchanges
"""

import json
import time
import logging
import hashlib
import hmac
import base64
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

# Configure logging
log = logging.getLogger("ExchangeConnector")
log.setLevel(logging.INFO)

class OrderSide(Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"

class OrderStatus(Enum):
    """Order status."""
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

@dataclass
class Order:
    """Order representation."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0.0
    average_price: Optional[float] = None
    timestamp: str = ""
    exchange_timestamp: Optional[str] = None

@dataclass
class Balance:
    """Account balance for a currency."""
    currency: str
    available: float
    total: float
    held: float = 0.0

@dataclass
class Ticker:
    """Market ticker data."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: str

class ExchangeError(Exception):
    """Base exception for exchange errors."""
    pass

class AuthenticationError(ExchangeError):
    """Authentication failed."""
    pass

class InsufficientFundsError(ExchangeError):
    """Insufficient funds for order."""
    pass

class OrderRejectedError(ExchangeError):
    """Order was rejected by exchange."""
    pass

class RateLimitError(ExchangeError):
    """Rate limit exceeded."""
    pass


class ExchangeConnector(ABC):
    """
    Abstract Base Class for exchange connectors.
    
    All exchange connectors must implement these methods.
    """
    
    @abstractmethod
    def get_balance(self, currency: str) -> Balance:
        """
        Get balance for a specific currency.
        
        Args:
            currency: Currency symbol (e.g., "USD", "BTC")
            
        Returns:
            Balance object
            
        Raises:
            ExchangeError: If balance cannot be retrieved
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """
        Get current ticker data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTC-USD")
            
        Returns:
            Ticker object
            
        Raises:
            ExchangeError: If ticker cannot be retrieved
        """
        pass
    
    @abstractmethod
    def place_order(self, symbol: str, side: OrderSide, 
                   quantity: float, order_type: OrderType = OrderType.MARKET,
                   price: Optional[float] = None) -> Order:
        """
        Place an order on the exchange.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            order_type: Market or limit
            price: Required for limit orders
            
        Returns:
            Order object with order_id
            
        Raises:
            InsufficientFundsError: If insufficient balance
            OrderRejectedError: If order is rejected
            ExchangeError: For other exchange errors
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
            
        Raises:
            ExchangeError: If order cannot be cancelled
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Order:
        """
        Get current status of an order.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Order object with current status
            
        Raises:
            ExchangeError: If order status cannot be retrieved
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get list of open orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of open Order objects
            
        Raises:
            ExchangeError: If orders cannot be retrieved
        """
        pass
    
    @abstractmethod
    def get_fees(self) -> float:
        """
        Get the fee rate for the exchange.
        
        Returns:
            Fee rate as a decimal (e.g., 0.001 for 0.1% fee)
            
        Raises:
            ExchangeError: If fee information cannot be retrieved
        """
        pass
    
    def get_mid_price(self, symbol: str) -> float:
        """
        Get mid price (average of bid and ask).
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Mid price
        """
        ticker = self.get_ticker(symbol)
        return (ticker.bid + ticker.ask) / 2
    
    def estimate_slippage(self, symbol: str, side: OrderSide, 
                         quantity: float) -> float:
        """
        Estimate slippage for an order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            
        Returns:
            Estimated slippage in basis points
        """
        ticker = self.get_ticker(symbol)
        if side == OrderSide.BUY:
            # Buying at ask price
            return 0.0  # Base implementation - override for real estimates
        else:
            # Selling at bid price
            return 0.0
    
    def validate_order(self, symbol: str, side: OrderSide,
                      quantity: float, order_type: OrderType,
                      price: Optional[float] = None) -> Tuple[bool, str]:
        """
        Validate order parameters before placing.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            order_type: Market or limit
            price: Required for limit orders
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if order_type == OrderType.LIMIT and price is None:
            return False, "Price required for limit orders"
        
        if order_type == OrderType.LIMIT and price <= 0:
            return False, "Price must be positive"
        
        # Check symbol format (basic validation)
        if "-" not in symbol:
            return False, "Symbol must be in format BASE-QUOTE"
        
        return True, ""


class BaseExchangeConnector(ExchangeConnector):
    """
    Base implementation with common functionality for real exchanges.
    
    Provides:
    - Rate limiting
    - Request signing
    - Error handling
    - Retry logic
    """
    
    def __init__(self, api_key: str = "", api_secret: str = "",
                 passphrase: str = "", sandbox: bool = True,
                 rate_limit_per_minute: int = 60):
        """
        Initialize base exchange connector.
        
        Args:
            api_key: Exchange API key
            api_secret: Exchange API secret
            passphrase: Exchange API passphrase (if required)
            sandbox: Whether to use sandbox/testnet
            rate_limit_per_minute: API rate limit
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.sandbox = sandbox
        self.rate_limit_per_minute = rate_limit_per_minute
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 60.0 / rate_limit_per_minute
        
        # Session management
        self._session = None
        
        log.info(f"Initialized {self.__class__.__name__} "
                f"(sandbox: {sandbox}, rate limit: {rate_limit_per_minute}/min)")
    
    def get_fees(self) -> float:
        """
        Get the fee rate for the exchange.
        
        Returns:
            Fee rate as a decimal (e.g., 0.001 for 0.1% fee)
            
        Raises:
            NotImplementedError: Base implementation - must be overridden
        """
        raise NotImplementedError("get_fees must be implemented by subclass")
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            log.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _sign_request(self, method: str, path: str, 
                     body: Optional[Dict] = None,
                     timestamp: Optional[str] = None) -> Dict[str, str]:
        """
        Sign request for authenticated API calls.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            body: Request body
            timestamp: Timestamp for signature
            
        Returns:
            Dictionary of headers to add to request
        """
        # Base implementation - override for specific exchange
        return {}
    
    def _handle_error(self, response, context: str = ""):
        """
        Handle API error response.
        
        Args:
            response: Response object
            context: Context for error message
            
        Raises:
            Appropriate ExchangeError subclass
        """
        status_code = getattr(response, 'status_code', 0)
        
        if status_code == 401:
            raise AuthenticationError(f"Authentication failed: {context}")
        elif status_code == 429:
            raise RateLimitError(f"Rate limit exceeded: {context}")
        elif status_code >= 400:
            raise ExchangeError(f"API error {status_code}: {context}")
    
    def _create_order_object(self, order_data: Dict) -> Order:
        """
        Create Order object from exchange response.
        
        Args:
            order_data: Order data from exchange
            
        Returns:
            Order object
        """
        # Base implementation - override for specific exchange format
        return Order(
            order_id=order_data.get("id", ""),
            symbol=order_data.get("symbol", ""),
            side=OrderSide(order_data.get("side", "buy")),
            order_type=OrderType(order_data.get("type", "market")),
            quantity=float(order_data.get("size", 0)),
            price=float(order_data.get("price", 0)) if order_data.get("price") else None,
            status=OrderStatus(order_data.get("status", "new")),
            filled_quantity=float(order_data.get("filled_size", 0)),
            average_price=float(order_data.get("executed_value", 0)) / float(order_data.get("filled_size", 1)) if order_data.get("filled_size", 0) > 0 else None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            exchange_timestamp=order_data.get("created_at")
        )


class StubExchangeConnector(BaseExchangeConnector):
    """
    Stub exchange connector for testing and sandbox mode.
    
    Simulates exchange behavior without real API calls.
    """
    
    def __init__(self, initial_balances: Optional[Dict[str, float]] = None,
                 simulated_latency_ms: int = 100, **kwargs):
        """
        Initialize stub exchange connector.
        
        Args:
            initial_balances: Initial account balances
            simulated_latency_ms: Simulated network latency
            **kwargs: Passed to parent
        """
        super().__init__(**kwargs)
        
        # Simulated balances
        self.balances = initial_balances or {
            "USD": 10000.0,
            "BTC": 1.0,
            "ETH": 10.0
        }
        
        # Simulated orders
        self.orders = {}
        self.order_counter = 0
        
        # Simulated market data
        self.market_data = {
            "BTC-USD": {"bid": 65000.0, "ask": 65010.0, "last": 65005.0, "volume": 1000.0},
            "ETH-USD": {"bid": 3500.0, "ask": 3502.0, "last": 3501.0, "volume": 5000.0},
            "SOL-USD": {"bid": 150.0, "ask": 150.5, "last": 150.25, "volume": 10000.0}
        }
        
        self.simulated_latency_ms = simulated_latency_ms
        
        log.info(f"Stub exchange initialized with balances: {self.balances}")
    
    def _simulate_latency(self):
        """Simulate network latency."""
        if self.simulated_latency_ms > 0:
            time.sleep(self.simulated_latency_ms / 1000.0)
    
    def get_fees(self) -> float:
        """
        Get the fee rate for the stub exchange.
        
        Returns:
            Fee rate as a decimal (0.001 for 0.1% fee)
        """
        return 0.001  # 0.1% fee for stub exchange
    
    def get_balance(self, currency: str) -> Balance:
        self._rate_limit()
        self._simulate_latency()
        
        if currency not in self.balances:
            raise ExchangeError(f"Currency not found: {currency}")
        
        total = self.balances[currency]
        held = sum(order.quantity for order in self.orders.values() 
                  if order.status in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED])
        available = total - held
        
        return Balance(
            currency=currency,
            available=available,
            total=total,
            held=held
        )
    
    def get_ticker(self, symbol: str) -> Ticker:
        self._rate_limit()
        self._simulate_latency()
        
        if symbol not in self.market_data:
            raise ExchangeError(f"Symbol not found: {symbol}")
        
        data = self.market_data[symbol]
        
        # Add some random noise to simulate market movement
        import random
        noise = random.uniform(-0.001, 0.001)  # ±0.1%
        
        return Ticker(
            symbol=symbol,
            bid=data["bid"] * (1 + noise),
            ask=data["ask"] * (1 + noise),
            last=data["last"] * (1 + noise),
            volume=data["volume"] * (1 + random.uniform(-0.1, 0.1)),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def place_order(self, symbol: str, side: OrderSide, 
                   quantity: float, order_type: OrderType = OrderType.MARKET,
                   price: Optional[float] = None) -> Order:
        self._rate_limit()
        self._simulate_latency()
        
        # Validate
        is_valid, error_msg = self.validate_order(symbol, side, quantity, order_type, price)
        if not is_valid:
            raise OrderRejectedError(f"Order validation failed: {error_msg}")
        
        # Check balance for buy orders
        if side == OrderSide.BUY:
            quote_currency = symbol.split("-")[1]
            ticker = self.get_ticker(symbol)
            cost = quantity * ticker.ask  # Buying at ask price
            
            balance = self.get_balance(quote_currency)
            if cost > balance.available:
                raise InsufficientFundsError(
                    f"Insufficient {quote_currency}: need {cost:.2f}, have {balance.available:.2f}"
                )
        
        # Create order
        self.order_counter += 1
        order_id = f"stub_order_{self.order_counter}"
        
        ticker = self.get_ticker(symbol)
        order_price = price if price else (ticker.ask if side == OrderSide.BUY else ticker.bid)
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=order_price,
            status=OrderStatus.NEW,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        # Store order
        self.orders[order_id] = order
        
        # Simulate immediate fill for market orders
        if order_type == OrderType.MARKET:
            time.sleep(0.1)  # Simulate processing time
            order.status = OrderStatus.FILLED
            order.filled_quantity = quantity
            order.average_price = order_price
            
            # Update balances
            base_currency = symbol.split("-")[0]
            quote_currency = symbol.split("-")[1]
            
            if side == OrderSide.BUY:
                # Buy base with quote
                self.balances[base_currency] = self.balances.get(base_currency, 0) + quantity
                self.balances[quote_currency] = self.balances.get(quote_currency, 0) - (quantity * order_price)
            else:
                # Sell base for quote
                self.balances[base_currency] = self.balances.get(base_currency, 0) - quantity
                self.balances[quote_currency] = self.balances.get(quote_currency, 0) + (quantity * order_price)
        
        log.info(f"Placed {order_type.value} order {order_id}: {side.value} {quantity} {symbol} "
                f"at {order_price:.2f}")
        
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        self._rate_limit()
        self._simulate_latency()
        
        if order_id not in self.orders:
            raise ExchangeError(f"Order not found: {order_id}")
        
        order = self.orders[order_id]
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            raise ExchangeError(f"Cannot cancel order in status: {order.status.value}")
        
        order.status = OrderStatus.CANCELLED
        log.info(f"Cancelled order {order_id}")
        
        return True
    
    def get_order_status(self, order_id: str) -> Order:
        self._rate_limit()
        self._simulate_latency()
        
        if order_id not in self.orders:
            raise ExchangeError(f"Order not found: {order_id}")
        
        return self.orders[order_id]
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        self._rate_limit()
        self._simulate_latency()
        
        open_orders = []
        for order in self.orders.values():
            if order.status in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                if symbol is None or order.symbol == symbol:
                    open_orders.append(order)
        
        return open_orders
    
    def estimate_slippage(self, symbol: str, side: OrderSide, 
                         quantity: float) -> float:
        """Estimate slippage for stub exchange."""
        # Simple linear slippage model
        ticker = self.get_ticker(symbol)
        spread = ticker.ask - ticker.bid
        
        # Slippage increases with order size relative to volume
        volume_ratio = quantity / ticker.volume
        slippage_bps = volume_ratio * 100  # 1% slippage at volume equal to daily volume
        
        # Add spread component
        spread_bps = (spread / ticker.last) * 10000
        
        return min(slippage_bps + spread_bps, 50.0)  # Cap at 50 bps


# Factory function for creating connectors
def create_exchange_connector(exchange_name: str, **kwargs) -> ExchangeConnector:
    """
    Factory function to create exchange connectors.
    
    Args:
        exchange_name: Name of exchange ("coinbase", "binance", "kraken", "stub")
        **kwargs: Connector-specific arguments
        
    Returns:
        ExchangeConnector instance
        
    Raises:
        ValueError: If exchange name not recognized
    """
    exchange_name = exchange_name.lower()
    
    if exchange_name == "stub":
        return StubExchangeConnector(**kwargs)
    elif exchange_name == "coinbase":
        # Import here to avoid circular dependencies
        try:
            from .coinbase_connector import CoinbaseConnector
            return CoinbaseConnector(**kwargs)
        except ImportError:
            log.warning("Coinbase connector not available, using stub")
            return StubExchangeConnector(**kwargs)
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}")