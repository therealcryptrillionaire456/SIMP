#!/bin/bash

# =============================================================================
# MULTI-EXCHANGE TRADING SETUP SCRIPT
# =============================================================================
# This script configures all exchanges for live trading in SIMP
# 
# Usage:
#   ./scripts/setup_multi_exchange.sh [environment]
#
# Environments:
#   sandbox      - Testing with simulated funds (default)
#   microscopic  - Live trading with minimal risk ($0.01-$0.10)
#   small_scale  - Consistent live trading ($1-$10)
#   multi_exchange - Cross-exchange arbitrage
#   full_production - Maximum trading capacity
#
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_DIR/config/multi_exchange_live_config.json"
ENV_FILE="$PROJECT_DIR/.env"

# Parse command line arguments
ENVIRONMENT="${1:-sandbox}"

# Validate environment
case "$ENVIRONMENT" in
    "sandbox"|"microscopic"|"small_scale"|"multi_exchange"|"full_production")
        echo "🎯 Setting up environment: $ENVIRONMENT"
        ;;
    *)
        echo "ERROR: Unknown environment '$ENVIRONMENT'"
        echo "Available environments: sandbox, microscopic, small_scale, multi_exchange, full_production"
        exit 1
        ;;
esac

# Check if required files exist
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Multi-exchange config file not found at $CONFIG_FILE"
    exit 1
fi

# Create backup of current .env file if it exists
if [ -f "$ENV_FILE" ]; then
    echo "📋 Creating backup of current .env file..."
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Copy multi-exchange environment template
echo "📋 Setting up environment variables..."
cp "$PROJECT_DIR/.env.multi_exchange" "$ENV_FILE"

# Update environment variable
sed -i.tmp "s/TRADING_ENVIRONMENT=.*/TRADING_ENVIRONMENT=$ENVIRONMENT/" "$ENV_FILE"
rm -f "$ENV_FILE.tmp"

# Load environment variables
echo "🔐 Loading environment variables..."
source "$SCRIPT_DIR/load_env.sh"

# Validate required environment variables
echo "🔍 Validating configuration..."
python3.10 -c "
import json
import os

# Load configuration
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)

# Check environment configuration
env_config = config['operational_modes']['$ENVIRONMENT']
if not env_config['enabled']:
    print('❌ Environment $ENVIRONMENT is not enabled in configuration')
    exit(1)

print('✅ Environment $ENVIRONMENT is enabled')

# Check exchange configurations
exchanges = env_config['exchanges']
for exchange in exchanges:
    ex_config = config['exchanges'][exchange]
    env = 'production' if '$ENVIRONMENT' in ['microscopic', 'small_scale', 'multi_exchange', 'full_production'] else 'sandbox'
    
    if ex_config['environments'][env]['enabled']:
        print(f'✅ {exchange} ({env}) enabled')
    else:
        print(f'⚠️  {exchange} ({env}) disabled')

print('✅ Configuration validation complete')
"

# Create necessary directories
echo "📁 Creating required directories..."
mkdir -p "$PROJECT_DIR/data/exchange_balances"
mkdir -p "$PROJECT_DIR/data/arbitrage_opportunities"
mkdir -p "$PROJECT_DIR/logs/trading"
mkdir -p "$PROJECT_DIR/logs/monitoring"

# Install required packages
echo "📦 Installing required packages..."
source "$PROJECT_DIR/venv_gate4/bin/activate"

# Check if multi-exchange packages are installed
packages=("coinbase-advanced-py" "krakenex" "python-binance")
for package in "${packages[@]}"; do
    if ! python -c "import $package" 2>/dev/null; then
        echo "Installing $package..."
        pip install "$package"
    else
        echo "✅ $package already installed"
    fi
done

# Create exchange connector modules
echo "🔌 Setting up exchange connectors..."
python3.10 -c "
import os
import json
from pathlib import Path

# Create exchange connectors directory
connectors_dir = Path('$PROJECT_DIR/simp/organs/quantumarb/exchange_connectors')
connectors_dir.mkdir(parents=True, exist_ok=True)

# Create Coinbase connector
connector_code = '''#!/usr/bin/env python3.10
\\\"\\\"\\\"Coinbase Exchange Connector Implementation\\\"\\\"\\\"

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
    \\\"\\\"\\\"Coinbase-specific exchange connector.\\\"\\\"\\\"
    
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
        \\\"\\\"\\\"Get account balance.\\\"\\\"\\\"
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
        \\\"\\\"\\\"Place an order.\\\"\\\"\\\"
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
        \\\"\\\"\\\"Get ticker information.\\\"\\\"\\\"
        try:
            ticker = self.client.get_product_ticker(product_id=symbol)
            return ticker
        except Exception as e:
            logging.error(f'Error getting ticker: {e}')
            return {}
    
    def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        \\\"\\\"\\\"Get order book.\\\"\\\"\\\"
        try:
            orderbook = self.client.get_product_order_book(product_id=symbol, level=2)
            return orderbook
        except Exception as e:
            logging.error(f'Error getting orderbook: {e}')
            return {}
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        \\\"\\\"\\\"Cancel an order.\\\"\\\"\\\"
        try:
            response = self.client.cancel_order(order_id)
            return response
        except Exception as e:
            logging.error(f'Error canceling order: {e}')
            return {'error': str(e)}
'''

# Write the connector
with open(connectors_dir / 'coinbase_connector.py', 'w') as f:
    f.write(connector_code)

print('✅ Coinbase connector created')
"

# Create trading system configuration
echo "⚙️  Creating trading system configuration..."
python3.10 -c "
import json

# Load configuration
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)

# Update environment-specific settings
env_config = config['operational_modes']['$ENVIRONMENT']
config['current_environment'] = '$ENVIRONMENT'
config['enabled_exchanges'] = env_config['exchanges']
config['position_sizing'] = config['position_sizing']['small'] if '$ENVIRONMENT' in ['small_scale', 'multi_exchange', 'full_production'] else config['position_sizing']['microscopic']

# Save updated configuration
with open('$PROJECT_DIR/config/current_trading_config.json', 'w') as f:
    json.dump(config, f, indent=2)

print('✅ Trading system configuration updated')
"

# Create monitoring dashboard
echo "📊 Setting up monitoring dashboard..."
python3.10 -c "
import json
from pathlib import Path

# Create dashboard config
dashboard_config = {
    'version': '1.0.0',
    'environment': '$ENVIRONMENT',
    'exchanges': [],
    'metrics': {
        'trading': True,
        'risk': True,
        'performance': True,
        'monitoring': True
    },
    'refresh_interval': 5,
    'alert_thresholds': {
        'slippage_pct': 0.10,
        'latency_seconds': 5.0,
        'error_rate_pct': 1.0,
        'balance_alert_pct': 10.0
    }
}

# Save dashboard config
dashboard_path = Path('$PROJECT_DIR/dashboard/config.json')
dashboard_path.parent.mkdir(parents=True, exist_ok=True)
with open(dashboard_path, 'w') as f:
    json.dump(dashboard_config, f, indent=2)

print('✅ Monitoring dashboard configured')
"

# Create test signals for verification
echo "📝 Creating test signals..."
python3.10 -c "
import json
import os
from datetime import datetime
from pathlib import Path

# Create test signal
test_signal = {
    'signal_id': 'test_multi_exchange_' + str(int(datetime.now().timestamp())),
    'signal_type': 'portfolio_allocation',
    'timestamp': datetime.now().isoformat(),
    'assets': {
        'BTC-USD': {
            'action': 'buy',
            'position_usd': 5.00,
            'confidence': 0.8,
            'exchange': 'coinbase'
        },
        'ETH-USD': {
            'action': 'buy',
            'position_usd': 3.00,
            'confidence': 0.7,
            'exchange': 'coinbase'
        }
    }
}

# Save test signal
signal_dir = Path('$PROJECT_DIR/data/inboxes/gate4_real')
signal_dir.mkdir(parents=True, exist_ok=True)
with open(signal_dir / 'test_multi_exchange_signal.json', 'w') as f:
    json.dump(test_signal, f, indent=2)

print('✅ Test signal created')
"

# Final verification
echo "🔍 Running final verification..."
python3.10 -c "
import json
import os

# Check all components
checks = []

# Check configuration file
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    checks.append('✅ Configuration file loaded')
except Exception as e:
    checks.append(f'❌ Configuration file error: {e}')

# Check environment file
try:
    with open('$ENV_FILE', 'r') as f:
        env_vars = f.readlines()
    checks.append(f'✅ Environment file loaded ({len(env_vars)} variables)')
except Exception as e:
    checks.append(f'❌ Environment file error: {e}')

# Check required packages
packages = ['coinbase', 'json', 'pathlib']
for package in packages:
    try:
        __import__(package)
        checks.append(f'✅ {package} available')
    except ImportError:
        checks.append(f'❌ {package} missing')

# Check directories
dirs = ['data', 'config', 'logs', 'scripts']
for dir_name in dirs:
    if os.path.exists(f'$PROJECT_DIR/{dir_name}'):
        checks.append(f'✅ {dir_name} directory exists')
    else:
        checks.append(f'❌ {dir_name} directory missing')

print('\\\\n=== VERIFICATION RESULTS ===')
for check in checks:
    print(check)

# Summary
success_count = sum(1 for check in checks if check.startswith('✅'))
total_count = len(checks)

print(f'\\\\nSummary: {success_count}/{total_count} checks passed')

if success_count == total_count:
    print('🎉 All systems ready for multi-exchange trading!')
else:
    print('⚠️  Some issues detected. Please check the errors above.')
"

echo ""
echo "🎉 Multi-exchange trading setup complete!"
echo ""
echo "=== NEXT STEPS ==="
echo "1. Review your API credentials in $ENV_FILE"
echo "2. Test with dry-run: ./scripts/run_trader.sh dry-run"
echo "3. Start live trading: ./scripts/run_trader.sh once"
echo "4. Monitor with dashboard: python3.10 dashboard_final.py"
echo ""
echo "=== ENVIRONMENT: $ENVIRONMENT ==="
echo "Exchanges: ${exchanges:-coinbase}"
echo "Position Size: $1.00 - $10.00"
echo "Risk Level: Medium"
echo ""