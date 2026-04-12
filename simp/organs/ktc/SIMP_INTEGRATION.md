# KTC - SIMP Integration Design

## Overview
This document outlines how Keep the Change (KTC) integrates with the SIMP (Structured Intent Messaging Protocol) ecosystem.

## Integration Architecture

### 1. KTC Agent Registration
```python
# Agent ID: ktc_agent
# Endpoint: http://localhost:8765 (KTC backend API)
# Capabilities:
#   - receipt_processing
#   - price_comparison  
#   - savings_calculation
#   - crypto_investment
#   - wallet_management
```

### 2. Intent Types

#### 2.1 Receipt Processing Intent
```json
{
  "intent_type": "process_receipt",
  "source_agent": "ktc_frontend",
  "target_agent": "ktc_agent",
  "parameters": {
    "receipt_image": "base64_encoded_image",
    "user_id": "user_123",
    "store_type": "grocery"
  },
  "expected_response": {
    "items": [
      {"name": "item1", "price": 10.99, "quantity": 1},
      {"name": "item2", "price": 5.49, "quantity": 2}
    ],
    "total": 21.97,
    "receipt_id": "rec_123456"
  }
}
```

#### 2.2 Price Comparison Intent
```json
{
  "intent_type": "compare_prices",
  "source_agent": "ktc_agent",
  "target_agent": "ktc_agent",
  "parameters": {
    "items": [
      {"name": "item1", "brand": "BrandA", "size": "16oz"},
      {"name": "item2", "brand": "BrandB", "size": "32oz"}
    ],
    "location": {"zipcode": "90210", "radius_miles": 10}
  },
  "expected_response": {
    "savings_opportunities": [
      {
        "item": "item1",
        "current_price": 10.99,
        "cheaper_price": 8.49,
        "store": "Walmart",
        "savings": 2.50,
        "distance_miles": 2.5
      }
    ],
    "total_potential_savings": 2.50
  }
}
```

#### 2.3 Crypto Investment Intent
```json
{
  "intent_type": "crypto_investment",
  "source_agent": "ktc_agent",
  "target_agent": "quantumarb",
  "parameters": {
    "amount": 2.50,
    "currency": "USD",
    "strategy": "dollar_cost_average",
    "user_wallet": "solana_wallet_address",
    "savings_source": "receipt_123_grocery_savings"
  },
  "expected_response": {
    "trade_confirmation": true,
    "transaction_hash": "0x123...abc",
    "investment_details": {
      "crypto_amount": 0.0015,
      "crypto_asset": "SOL",
      "exchange_rate": 1666.67,
      "timestamp": "2026-04-11T18:30:00Z"
    }
  }
}
```

### 3. Agent Communication Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   KTC Agent │────▶│ SIMP Broker │────▶│ QuantumArb  │
│   (React)   │     │   (Flask)   │     │  (Port 5555)│     │   Agent     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │ 1. Upload receipt │                   │                   │
       │──────────────────▶│                   │                   │
       │                   │ 2. Process receipt│                   │
       │                   │───────────────────┼───────────────────┼───┐
       │                   │                   │ 3. Route to       │   │
       │                   │                   │    quantumarb     │   │
       │                   │                   │──────────────────▶│   │
       │                   │                   │                   │ 4. Execute trade
       │                   │                   │                   │───┘
       │                   │                   │ 5. Return result  │
       │                   │                   │◀──────────────────│
       │                   │ 6. Update ledger  │                   │
       │                   │───────────────────┼───────────────────┼───┐
       │ 7. Show savings   │                   │                   │   │
       │◀──────────────────│                   │                   │   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 4. Financial Operations Integration

#### 4.1 Use SIMP FinancialOps for:
- Transaction tracking in `live_spend_ledger.jsonl`
- Approval queue for large investments (> $50)
- Budget monitoring and alerts
- Reconciliation with crypto exchanges

#### 4.2 FinancialOps Configuration:
```python
FINANCIAL_OPS_CONFIG = {
    "enabled": True,
    "live_mode": False,  # Start in simulation mode
    "budget_limits": {
        "daily_investment_limit": 100.00,
        "weekly_investment_limit": 500.00,
        "monthly_investment_limit": 2000.00
    },
    "approval_thresholds": {
        "auto_approve_max": 50.00,
        "require_approval_above": 50.00
    }
}
```

### 5. Database Schema Integration

#### 5.1 KTC Tables:
```sql
-- Users
CREATE TABLE ktc_users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    wallet_address TEXT,
    created_at TIMESTAMP,
    total_savings DECIMAL(10,2),
    total_invested DECIMAL(10,2)
);

-- Receipts
CREATE TABLE ktc_receipts (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES ktc_users(id),
    store_name TEXT,
    total_amount DECIMAL(10,2),
    receipt_date TIMESTAMP,
    image_path TEXT,
    processed BOOLEAN DEFAULT FALSE
);

-- Receipt Items
CREATE TABLE ktc_receipt_items (
    id TEXT PRIMARY KEY,
    receipt_id TEXT REFERENCES ktc_receipts(id),
    item_name TEXT,
    brand TEXT,
    quantity INTEGER,
    price DECIMAL(10,2),
    unit_price DECIMAL(10,2)
);

-- Price Comparisons
CREATE TABLE ktc_price_comparisons (
    id TEXT PRIMARY KEY,
    receipt_item_id TEXT REFERENCES ktc_receipt_items(id),
    alternative_store TEXT,
    alternative_price DECIMAL(10,2),
    savings DECIMAL(10,2),
    distance_miles DECIMAL(5,2),
    comparison_date TIMESTAMP
);

-- Investments
CREATE TABLE ktc_investments (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES ktc_users(id),
    amount DECIMAL(10,2),
    crypto_amount DECIMAL(20,10),
    crypto_asset TEXT,
    exchange_rate DECIMAL(20,10),
    transaction_hash TEXT,
    investment_date TIMESTAMP,
    source_receipt_id TEXT REFERENCES ktc_receipts(id)
);
```

### 6. Security Considerations

#### 6.1 Authentication:
- API key authentication for agent-to-agent communication
- JWT tokens for frontend users
- Wallet signature verification for crypto transactions

#### 6.2 Data Protection:
- Encrypt sensitive user data (emails, wallet addresses)
- Secure receipt image storage
- Audit logging for all financial transactions

#### 6.3 SIMP Security Integration:
- Use SIMP's `security_audit.jsonl` for audit trails
- Integrate with Bill Russell Protocol for threat detection
- Implement rate limiting via SIMP's rate limit module

### 7. Monitoring & Observability

#### 7.1 Metrics to Track:
- Receipt processing success rate
- Average savings per receipt
- Investment execution success rate
- User engagement metrics
- System latency metrics

#### 7.2 Integration with SIMP Dashboard:
- Add KTC section to SIMP dashboard
- Show real-time metrics
- Display recent investments
- Monitor agent health

### 8. Deployment Configuration

#### 8.1 Environment Variables:
```bash
# KTC Specific
KTC_API_PORT=8765
KTC_DATABASE_URL=sqlite:///ktc.db
KTC_SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
KTC_SIMP_BROKER_URL=http://localhost:5555

# SIMP Integration
SIMP_API_KEY=your_simp_api_key
SIMP_AGENT_ID=ktc_agent
SIMP_AGENT_ENDPOINT=http://localhost:8765

# OCR Services
GOOGLE_VISION_API_KEY=your_google_vision_key
TESSERACT_PATH=/usr/bin/tesseract

# Retailer APIs
WALMART_API_KEY=your_walmart_key
TARGET_API_KEY=your_target_key
AMAZON_ASSOCIATE_TAG=your_amazon_tag
```

#### 8.2 Docker Configuration:
```dockerfile
# Dockerfile for KTC Backend
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8765
CMD ["python", "app.py"]
```

### 9. Testing Strategy

#### 9.1 Unit Tests:
- Receipt processing logic
- Price comparison algorithms
- SIMP intent formatting
- Database operations

#### 9.2 Integration Tests:
- SIMP broker communication
- QuantumArb agent integration
- FinancialOps ledger updates
- Web3 wallet interactions

#### 9.3 End-to-End Tests:
- Complete user flow: receipt → savings → investment
- Error handling and recovery
- Performance under load

### 10. Rollout Plan

#### Phase 1: Development & Testing
- Implement core functionality
- Integrate with SIMP in test mode
- Conduct security audit

#### Phase 2: Limited Beta
- Deploy to small user group
- Gather feedback and metrics
- Refine algorithms

#### Phase 3: General Availability
- Full deployment
- Marketing launch
- Continuous monitoring

## Appendix

### A. Existing SIMP Agents to Integrate With

1. **quantumarb** - Crypto trading execution
2. **kloutbot** - User engagement and notifications  
3. **financial_ops** - Transaction tracking and compliance
4. **projectx_native** - System health monitoring
5. **gemma4_local** - User support and assistance

### B. SIMP Endpoints to Use

1. `POST /intents/route` - Route intents to agents
2. `POST /agents/register` - Register KTC agent
3. `GET /stats` - Monitor system health
4. `POST /financial_ops/submit_proposal` - Large investment approvals
5. `GET /dashboard/ui` - Integration with SIMP dashboard

### C. Error Handling

1. **Network Errors**: Retry with exponential backoff
2. **API Errors**: Log and notify operators
3. **Validation Errors**: Return descriptive error messages
4. **Financial Errors**: Rollback transactions and notify users

---

*Last Updated: 2026-04-11*
*Version: 1.0.0*
*Status: Active Development*