# Gate 4 Scaled Microscopic Agent

## Overview
The Gate 4 Scaled Microscopic Agent is a production-ready trading agent designed for $1-$10 position sizes with comprehensive risk management, compliance monitoring, and SIMP broker integration.

## Architecture

### Components
1. **Gate4ScaledAgent** (Part 1) - Core infrastructure and market analysis
2. **TradeEngine** (Part 2a) - Trade execution with position sizing
3. **OrderManager** (Part 2b) - Advanced order management and compliance
4. **Gate4ScaledMicroscopicAgent** (Part 3) - Main agent with telemetry and monitoring

### Key Features
- **Scaled Position Sizing**: $1-$10 per trade with dynamic adjustment based on volatility and liquidity
- **Risk Management**: Circuit breakers, Value at Risk (VaR), stress testing scenarios
- **Compliance Monitoring**: Trade surveillance, market abuse detection, best execution policy
- **Real-time Telemetry**: Dashboard integration, performance reporting, alerting
- **Production Ready**: Logging, error handling, graceful shutdown, systemd service

## Configuration

### Configuration File
Located at `config/gate4_scaled_microscopic.json`

Key configuration sections:
- `position_sizing`: Min/max notional, risk per trade, concurrent positions
- `risk_management`: Circuit breakers, position limits, VaR settings
- `monitoring`: Heartbeat intervals, alert thresholds
- `integration`: SIMP broker URL, dashboard settings

### Default Configuration
```json
{
  "mode": "gate_4_scaled_microscopic",
  "exchange": "coinbase",
  "symbols": ["SOL-USD", "BTC-USD", "ETH-USD", "AVAX-USD", "MATIC-USD"],
  "position_sizing": {
    "min_notional": 1.00,
    "max_notional": 10.00,
    "base_allocation_per_symbol": 2.00,
    "max_concurrent_positions": 5,
    "risk_per_trade_percent": 0.75
  }
}
```

## Installation

### Quick Start
```bash
# Run deployment script
./scripts/deploy_gate4.sh

# Start the agent
./scripts/start_gate4.sh

# Monitor the agent
./scripts/monitor_gate4.sh
```

### Manual Installation
```bash
# Create virtual environment
python3.10 -m venv venv_gate4
source venv_gate4/bin/activate

# Install dependencies
pip install numpy pandas scipy aiohttp

# Validate configuration
python3.10 agents/gate4_scaled_microscopic_agent.py --validate

# Run tests
python3.10 -m pytest tests/test_gate4_basic.py -v

# Start agent
python3.10 agents/gate4_scaled_microscopic_agent.py --config config/gate4_scaled_microscopic.json
```

## Usage

### Command Line Options
```bash
# Validate configuration
python3.10 agents/gate4_scaled_microscopic_agent.py --validate

# Check agent status
python3.10 agents/gate4_scaled_microscopic_agent.py --status

# Create default configuration
python3.10 agents/gate4_scaled_microscopic_agent.py --create-config

# Run with custom config
python3.10 agents/gate4_scaled_microscopic_agent.py --config path/to/config.json
```

### Systemd Service
```bash
# Install as systemd service
sudo cp scripts/gate4_agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gate4_agent
sudo systemctl start gate4_agent

# Check status
sudo systemctl status gate4_agent

# View logs
sudo journalctl -u gate4_agent -f
```

## Trading Strategies

### Supported Strategies
1. **Mean Reversion**: Trade when price deviates significantly from mean
2. **Statistical Arbitrage**: Identify and exploit pricing inefficiencies
3. **Pairs Trading**: Trade correlated symbol pairs

### Signal Generation
The agent analyzes:
- Market microstructure (bid-ask spread, order book imbalance)
- Technical indicators (RSI, EMA, Bollinger Bands)
- Volatility metrics
- Liquidity scores

## Risk Management

### Circuit Breakers
- **Warning**: 75% of daily loss limit
- **Critical**: 90% of daily loss limit  
- **Shutdown**: 100% of daily loss limit

### Position Limits
- Max concurrent positions: 5
- Max exposure per symbol: 30%
- Max total exposure: 150%
- Min liquidity threshold: $5M USD

### Value at Risk (VaR)
- Confidence level: 95%
- Lookback period: 30 days
- Max VaR: 2.0%

## Monitoring & Reporting

### Log Files
- `logs/gate4_agent.log` - Main application log
- `logs/gate4_agent.error.log` - Error log
- `data/gate4_performance.jsonl` - Performance metrics
- `data/gate4_reconciliation.jsonl` - Order reconciliation
- `data/gate4_compliance.jsonl` - Compliance records

### Dashboard Integration
The agent sends real-time telemetry to the SIMP dashboard:
- Current positions and P&L
- Performance metrics
- Risk exposures
- System health
- Alerts and notifications

### Alerts
- **Info**: System status updates
- **Warning**: Risk threshold breaches
- **Error**: System failures
- **Critical**: Circuit breaker triggers

## Testing

### Test Suite
```bash
# Run all tests
python3.10 -m pytest tests/test_gate4_basic.py -v

# Test specific components
python3.10 -m pytest tests/test_gate4_basic.py::TestGate4Basic -v
```

### Test Coverage
- Configuration validation
- Dataclass instantiation
- Enum values
- Decimal and datetime handling
- File I/O operations

## Troubleshooting

### Common Issues

1. **Python 3.10 not found**
   ```bash
   brew install python@3.10
   ```

2. **SIMP broker not running**
   ```bash
   python3.10 -m simp.server.broker
   ```

3. **Configuration validation failed**
   ```bash
   python3.10 agents/gate4_scaled_microscopic_agent.py --create-config
   ```

4. **Import errors**
   ```bash
   source venv_gate4/bin/activate
   pip install -r requirements.txt
   ```

### Log Analysis
Check log files for errors:
```bash
tail -f logs/gate4_agent.log
tail -f logs/gate4_agent.error.log
```

### Performance Monitoring
```bash
./scripts/monitor_gate4.sh
```

## Performance Metrics

### Key Metrics
- **Win Rate**: Percentage of profitable trades
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Maximum peak-to-trough decline
- **Profit Factor**: Gross profits / gross losses
- **Fill Rate**: Percentage of orders filled
- **Avg Slippage**: Average execution slippage

### Optimization
The agent includes:
- Genetic algorithm tuning
- Grid search parameter optimization
- Real-time adaptation
- Bayesian hyperparameter tuning

## Compliance & Security

### Regulatory Compliance
- Trade surveillance
- Market abuse detection
- Best execution policy
- Audit trail (7-year retention)

### Security Features
- API rate limiting
- Input validation
- Error handling
- Secure logging
- Graceful degradation

## Scaling & Production

### Horizontal Scaling
- Max parallel symbols: 20
- Load balancing support
- Fault tolerance with redundant instances
- Auto-failover and state recovery

### Production Readiness
- 99.9% uptime target
- 5-minute mean time to recovery
- Disaster recovery with 15-minute RPO
- Monitoring stack integration (Prometheus, Grafana)

## Development

### Code Structure
```
agents/
├── gate4_scaled_agent_part1.py      # Core infrastructure
├── gate4_scaled_agent_part2a.py     # Trading engine
├── gate4_scaled_agent_part2b.py     # Order management
├── gate4_scaled_agent_part3.py      # Main agent
└── gate4_scaled_microscopic_agent.py # Unified entry point

config/
└── gate4_scaled_microscopic.json    # Configuration

tests/
└── test_gate4_basic.py             # Test suite

scripts/
├── deploy_gate4.sh                 # Deployment script
├── start_gate4.sh                  # Startup script
├── stop_gate4.sh                   # Stop script
└── monitor_gate4.sh                # Monitoring script
```

### Adding New Features
1. Extend existing dataclasses for new data
2. Add new strategies to TradingStrategy enum
3. Implement new analyzers in FeatureEngineeringEngine
4. Add new risk metrics to RiskMetrics
5. Update configuration schema
6. Write corresponding tests

## License & Support

This agent is part of the SIMP (Structured Intent Messaging Protocol) system.

For support:
1. Check the logs: `logs/gate4_agent.log`
2. Review configuration: `config/gate4_scaled_microscopic.json`
3. Run validation: `python3.10 agents/gate4_scaled_microscopic_agent.py --validate`
4. Monitor performance: `./scripts/monitor_gate4.sh`

## Version History

### v1.0.0 (Initial Release)
- Core trading infrastructure
- $1-$10 position sizing
- Risk management with circuit breakers
- SIMP broker integration
- Production deployment scripts
- Comprehensive testing suite