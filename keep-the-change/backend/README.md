# KEEPTHECHANGE.com Backend

FastAPI backend for the KEEPTHECHANGE.com platform - an AI-powered shopping assistant that turns grocery savings into crypto investments.

## 🚀 Features

- **User Management**: Registration, authentication, profile management
- **Shopping Lists**: Create, manage, and optimize grocery lists
- **Price Comparison**: Find cheapest prices across retailers
- **Automated Purchasing**: One-click buying with saved payment methods
- **Crypto Investment**: Automatically invest savings into cryptocurrency
- **Subscription Tiers**: Free, Basic, Pro, and Elite tiers with different benefits
- **Mobile Integration**: Receipt scanning, barcode scanning, location-based offers
- **Admin Dashboard**: System monitoring, analytics, user management
- **SIMP Integration**: Connect with SIMP agent ecosystem for crypto trading

## 🏗️ Architecture

```
backend/
├── app/
│   ├── api/              # FastAPI routers
│   │   ├── users.py      # User authentication & management
│   │   ├── shopping.py   # Shopping lists & price comparison
│   │   ├── payments.py   # Payment processing
│   │   ├── crypto.py     # Crypto investment & trading
│   │   ├── subscriptions.py # Subscription management
│   │   ├── mobile.py     # Mobile-specific features
│   │   └── admin.py      # Admin endpoints
│   ├── core/            # Core functionality
│   │   ├── config.py    # Configuration settings
│   │   ├── database.py  # Database connection
│   │   ├── security.py  # Authentication & security
│   │   └── logging.py   # Logging configuration
│   ├── models/          # SQLAlchemy models
│   │   ├── user.py      # User models
│   │   ├── shopping.py  # Shopping models
│   │   ├── payment.py   # Payment models
│   │   ├── crypto.py    # Crypto models
│   │   └── subscription.py # Subscription models
│   └── schemas/         # Pydantic schemas
│       ├── user.py      # User schemas
│       ├── shopping.py  # Shopping schemas
│       ├── payment.py   # Payment schemas
│       ├── crypto.py    # Crypto schemas
│       ├── subscription.py # Subscription schemas
│       └── admin.py     # Admin schemas
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose setup
├── start.sh           # Startup script
└── .env.example       # Environment variables template
```

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.10+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (optional)

### Quick Start with Docker

```bash
# Clone the repository
git clone <repository-url>
cd keep-the-change/backend

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start with Docker Compose
docker-compose up -d

# Access the API
curl http://localhost:8000/health
```

### Manual Installation

```bash
# Clone the repository
git clone <repository-url>
cd keep-the-change/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Set up database
createdb keepthechange  # Or use your PostgreSQL client

# Run migrations
alembic upgrade head

# Start the server
./start.sh
```

## 📚 API Documentation

Once the server is running, access the API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 Configuration

### Environment Variables

Key environment variables to configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://user:password@localhost/keepthechange` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `SIMP_BROKER_URL` | SIMP broker URL | `http://localhost:5555` |
| `STRIPE_SECRET_KEY` | Stripe API secret key | (required for payments) |
| `SOLANA_RPC_URL` | Solana RPC endpoint | `https://api.mainnet-beta.solana.com` |
| `ENVIRONMENT` | Environment (development/production) | `development` |

### Database Models

The system uses SQLAlchemy with asyncpg. Key models include:

- **User**: User accounts, authentication, preferences
- **ShoppingList**: Shopping lists with items and optimization
- **Purchase**: Purchase records with savings calculation
- **CryptoInvestment**: Crypto investments from savings
- **Subscription**: User subscriptions with tier management
- **AgentPortfolio**: Agent's crypto portfolio performance

## 🔐 Authentication

The API uses JWT (JSON Web Tokens) for authentication:

1. Register user: `POST /api/v1/users/auth/register`
2. Login: `POST /api/v1/users/auth/login`
3. Use token: `Authorization: Bearer <token>`

Social authentication is supported for:
- Google
- Facebook
- Apple

## 🛒 Shopping Flow

1. **Create Shopping List**: `POST /api/v1/shopping/lists`
2. **Add Items**: `POST /api/v1/shopping/lists/{list_id}/items`
3. **Optimize Prices**: `POST /api/v1/shopping/lists/{list_id}/optimize`
4. **Purchase**: `POST /api/v1/shopping/lists/{list_id}/purchase`
5. **Invest Savings**: `POST /api/v1/crypto/investments/from-purchase/{purchase_id}`

## 💰 Crypto Investment

- **Automatic Investment**: Savings from purchases automatically invested
- **Tip System**: Users can tip agent for share of returns
- **Portfolio Tracking**: Real-time tracking of agent's crypto portfolio
- **Returns Distribution**: Automated distribution of returns to users

## 📱 Mobile Features

- **Receipt Scanning**: OCR processing of grocery receipts
- **Barcode Scanning**: Product lookup via barcode
- **Location-Based Offers**: Nearby deals and discounts
- **Quick Add**: Add products to lists from mobile scans

## 👑 Admin Features

- **User Management**: View and manage all users
- **System Monitoring**: Health checks and performance metrics
- **Financial Reports**: Revenue, savings, and investment reports
- **Audit Logs**: System activity and security logs

## 🔗 SIMP Integration

The backend integrates with the SIMP (Structured Intent Messaging Protocol) ecosystem:

- **Agent Registration**: Registers as `keep_the_change_agent`
- **Intent Routing**: Routes crypto investments to QuantumArb agent
- **Financial Operations**: Uses SIMP's FinancialOps for payment processing

## 🧪 Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=app tests/

# Run specific test module
pytest tests/test_users.py -v
```

## 📊 Monitoring & Logging

- **Logs**: Structured logging to `logs/` directory
- **Metrics**: Performance metrics and business analytics
- **Health Checks**: `/health` endpoint for monitoring
- **Audit Trail**: Comprehensive audit logging of all actions

## 🚀 Deployment

### Production Deployment

1. **Set environment to production**: `ENVIRONMENT=production`
2. **Use secure secret key**: Generate with `openssl rand -hex 32`
3. **Enable HTTPS**: Use reverse proxy (Nginx, Traefik)
4. **Database backups**: Regular PostgreSQL backups
5. **Monitoring**: Set up Prometheus/Grafana for metrics

### Cloud Deployment

```bash
# Deploy to AWS ECS
aws ecs create-service --cli-input-json file://ecs-service.json

# Deploy to Google Cloud Run
gcloud run deploy keep-the-change-backend --source .

# Deploy to Azure Container Instances
az container create --resource-group myResourceGroup --name keep-the-change --image myregistry.azurecr.io/keep-the-change:latest --dns-name-label keep-the-change --ports 8000
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is part of the SIMP ecosystem. See main repository for license details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourorg/keep-the-change/issues)
- **Documentation**: [API Docs](http://localhost:8000/docs)
- **Community**: [Discord/Slack Channel]

---

**KEEPTHECHANGE.com** - Making crypto investing accessible through everyday savings. 🛒➡️💰