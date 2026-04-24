#!/usr/bin/env python3.10
"""Coinbase Exchange Connector Implementation"""

import json
import time
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from coinbase.rest import RESTClient
    from simp.organs.quantumarb.exchange_connector import ExchangeConnector, Order, OrderSide, OrderType, OrderStatus
except ImportError:
    print('Coinbase SDK not installed')
    sys.exit(1)

class CoinbaseConnector(ExchangeConnector):
    """Coinbase-specific exchange connector."""
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str, sandbox: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.sandbox = sandbox
        self.base_url = 'https://api-public.sandbox.pro.coinbase.com' if sandbox else 'https://api.pro.coinbase.com'
        
        # Initialize client
        self.client = RESTClient(
            api_key=api_key,
            api_secret=api_secret,
            timeout=30
        )
        
        super().__init__()
    
    def get_balance(self) -> Dict[str, float]:
        """Get account balance."""
        try:
            accounts = self.client.get_accounts()
            balance = {}
            for account in accounts.get('data', []):
                currency = account['currency']
                available = float(account.get('available', '0'))
                if available > 0:
                    balance[currency] = available
            return balance
        except Exception as e:
            logging.error(f'Error getting balance: {e}')
            return {}
    
    def place_order(self, symbol: str, side: str, size: str, order_type: str = 'market') -> Dict[str, Any]:
        """Place an order."""
        try:
            if side.lower() == 'buy':
                if order_type == 'market':
                    response = self.client.market_order_buy(
                        client_order_id=f'qsig-{int(time.time())}-{symbol[:8]}',
                        product_id=symbol,
                        quote_size=size  # USD amount
                    )
                else:
                    response = self.client.limit_order_buy(
                        client_order_id=f'qsig-{int(time.time())}-{symbol[:8]}',
                        product_id=symbol,
                        quote_size=size,
                        limit_price=size
                    )
            elif side.lower() == 'sell':
                if order_type == 'market':
                    response = self.client.market_order_sell(
                        client_order_id=f'qsig-{int(time.time())}-{symbol[:8]}',
                        product_id=symbol,
                        base_size=size
                    )
                else:
                    response = self.client.limit_order_sell(
                        client_order_id=f'qsig-{int(time.time())}-{symbol[:8]}',
                        product_id=symbol,
                        base_size=size,
                        limit_price=size
                    )
            else:
                raise ValueError(f'Invalid side: {side}')
            
            return response
        except Exception as e:
            logging.error(f'Error placing order: {e}')
            return {'error': str(e)}
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker information."""
        try:
            ticker = self.client.get_product_ticker(product_id=symbol)
            return ticker
        except Exception as e:
            logging.error(f'Error getting ticker: {e}')
            return {}
    
    def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        """Get order book."""
        try:
            orderbook = self.client.get_product_order_book(product_id=symbol, level=2)
            return orderbook
        except Exception as e:
            logging.error(f'Error getting orderbook: {e}')
            return {}
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        try:
            response = self.client.cancel_order(order_id)
            return response
        except Exception as e:
            logging.error(f'Error canceling order: {e}')
            return {'error': str(e)}
