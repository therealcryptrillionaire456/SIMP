# Keep the Change (KTC)

**Turn grocery savings into crypto investments**

KTC is a SIMP-integrated application that connects everyday grocery shopping to automated crypto trading. Users scan receipts, the app finds cheaper prices, and the "change" (savings) is automatically reinvested into crypto trading through the SIMP system.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   SIMP Broker   │
│   (React/TS)    │◄──►│   (Flask/Py)    │◄──►│   (Port 5555)   │
│                 │    │                 │    │                 │
│ - Receipt scan  │    │ - OCR processing│    │ - Agent routing │
│ - Dashboard     │    │ - Price compare │    │ - Crypto exec   │
│ - Wallet mgmt   │    │ - SIMP agent    │    │ - Klout feed    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Features

- **Receipt Scanning**: Upload or take photos of grocery receipts
- **Price Comparison**: Find cheaper prices at nearby stores
- **Savings Calculation**: Automatically calculate potential savings
- **Crypto Investment**: Reinvest savings into crypto (SOL, BTC, ETH)
- **SIMP Integration**: Leverage existing SIMP trading infrastructure
- **User Dashboard**: Track savings, investments, and portfolio
- **Web3 Wallet**: Connect Solana wallet for transactions

## Quick Start

### 1. Prerequisites

- Python 3.10+
- SIMP broker running on port 5555
- SQLite (for development) or PostgreSQL (for production)

### 2. Installation

```bash
# Clone SIMP repository (if not already)
# cd /path/to/simp

# Install KTC dependencies
pip install -r simp/organs/ktc/requirements.txt

# Or install from main SIMP requirements
pip install -r requirements.txt
```

### 3. Start KTC System

```bash
# Start SIMP broker first (if not running)
python bin/start_server.py &

# Start KTC system
python simp/organs/ktc/start_ktc.py

# Or with custom options
python simp/organs/ktc/start_ktc.py --port 8765 --debug
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8765/health

# Agent health
curl http://localhost:8765/api/agent/health

# Process a receipt (example)
curl -X POST http://localhost:8765/api/receipts/process \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "store_name": "Whole Foods"}'
```

## Project Structure

```
simp/organs/ktc/
├── agent/
│   └── ktc_agent.py          # SIMP agent implementation
├── api/
│   └── app.py               # Flask API server
├── frontend/                 # (To be developed)
├── models/                   # Database models
├── services/                 # Business logic
├── utils/                    # Utilities
├── tests/
│   └── test_ktc_agent.py    # Test suite
├── start_ktc.py             # Startup script
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── MISSION_BOARD.md        # Project mission and plan
└── SIMP_INTEGRATION.md     # SIMP integration design
```

## SIMP Integration

KTC integrates with the SIMP ecosystem through:

1. **KTC Agent**: Registered as `ktc_agent` with capabilities:
   - `receipt_processing`
   - `price_comparison`
   - `savings_calculation`
   - `crypto_investment`
   - `wallet_management`

2. **Intent Routing**:
   - `process_receipt` → KTC agent
   - `compare_prices` → KTC agent
   - `crypto_investment` → QuantumArb agent
   - `financial_approval` → FinancialOps agent

3. **Financial Operations**:
   - Uses SIMP's `live_spend_ledger.jsonl`
   - Integrates with approval queue
   - Budget monitoring and alerts

## Development

### Running Tests

```bash
# Run agent tests
python simp/organs/ktc/tests/test_ktc_agent.py

# Or use the test-only mode
python simp/organs/ktc/start_ktc.py --test-only
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API health check |
| GET | `/api/agent/health` | KTC agent health |
| POST | `/api/receipts/process` | Process receipt image |
| POST | `/api/prices/compare` | Compare prices for items |
| POST | `/api/investments/create` | Invest savings into crypto |
| GET | `/api/users/<user_id>/stats` | Get user statistics |
| POST | `/api/simp/route` | Route intent through SIMP |

### Database Schema

See `SIMP_INTEGRATION.md` for complete database schema. Main tables:
- `ktc_users` - User accounts and wallets
- `ktc_receipts` - Receipt metadata
- `ktc_receipt_items` - Individual receipt items
- `ktc_price_comparisons` - Price comparison results
- `ktc_investments` - Crypto investment records

## Configuration

Environment variables:

```bash
# KTC Specific
KTC_API_PORT=8765
KTC_DATABASE_URL=sqlite:///data/ktc.db
KTC_SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# SIMP Integration
SIMP_BROKER_URL=http://localhost:5555
SIMP_API_KEY=your_simp_api_key
SIMP_AGENT_ID=ktc_agent

# OCR Services (optional)
GOOGLE_VISION_API_KEY=your_key_here
TESSERACT_PATH=/usr/bin/tesseract
```

## Roadmap

### Phase 1: MVP (Current)
- [x] Agent skeleton and API server
- [x] SIMP integration design
- [x] Mock receipt processing
- [x] Mock price comparison
- [x] Mock crypto investment
- [ ] Basic frontend interface

### Phase 2: Core Features
- [ ] Real OCR integration (Tesseract/Google Vision)
- [ ] Real price comparison APIs (Walmart/Target)
- [ ] Real crypto trading via QuantumArb
- [ ] User authentication
- [ ] Web3 wallet integration

### Phase 3: Advanced Features
- [ ] Machine learning for receipt parsing
- [ ] Predictive price optimization
- [ ] Advanced trading strategies
- [ ] Social features and sharing
- [ ] Mobile app

### Phase 4: Scale & Monetization
- [ ] Multi-chain support
- [ ] DeFi integration
- [ ] Premium features
- [ ] Partnership integrations
- [ ] Enterprise version

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

See `CONTRIBUTING.md` in the main SIMP repository for guidelines.

## License

Part of the SIMP ecosystem. See main repository LICENSE.

## Support

- Issues: [SIMP GitHub Issues](https://github.com/yourorg/simp/issues)
- Documentation: [SIMP Docs](https://docs.simp.protocol)
- Community: [Discord/Slack Channel]

---

*Keep the Change - Making crypto investing accessible through everyday savings.*