# KEEPTHECHANGE.com - API Contracts
## Instagram's Crypto Twin

## Overview
This document defines the complete API contract for KEEPTHECHANGE.com, detailing all REST endpoints, WebSocket interfaces, GraphQL schemas, and integration points. The API follows RESTful principles with OpenAPI 3.0 specification and supports both traditional REST and real-time WebSocket communication.

## API Design Principles
1. **RESTful Design**: Resource-oriented, stateless, cacheable
2. **Versioning**: URL-based versioning (`/api/v1/`)
3. **Authentication**: JWT tokens with refresh mechanism
4. **Rate Limiting**: Tiered limits based on user type
5. **Idempotency**: All POST/PUT operations support idempotency keys
6. **Pagination**: Cursor-based pagination for all list endpoints
7. **Real-time**: WebSocket support for live updates
8. **Documentation**: OpenAPI 3.0 specification with interactive docs

## Base URL
```
Production: https://api.keepthechange.com/api/v1
Staging: https://api.staging.keepthechange.com/api/v1
Development: http://localhost:8000/api/v1
```

## Authentication

### JWT Authentication
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "device_id": "device_123",
  "mfa_code": "123456"  # Optional
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "user_123",
    "username": "johndoe",
    "email": "user@example.com",
    "profile_image_url": "https://..."
  }
}
```

### Refresh Token
```http
POST /auth/refresh
Content-Type: application/json
Authorization: Bearer <refresh_token>

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}

Response:
{
  "access_token": "new_access_token...",
  "refresh_token": "new_refresh_token...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### MFA Setup
```http
POST /auth/mfa/setup
Authorization: Bearer <access_token>

Response:
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code_url": "data:image/png;base64,...",
  "backup_codes": ["12345678", "87654321", ...]
}

POST /auth/mfa/verify
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "code": "123456"
}

Response:
{
  "verified": true,
  "message": "MFA enabled successfully"
}
```

## User Management

### Get Current User
```http
GET /users/me
Authorization: Bearer <access_token>

Response:
{
  "id": "user_123",
  "username": "johndoe",
  "email": "user@example.com",
  "full_name": "John Doe",
  "bio": "Savings enthusiast!",
  "profile_image_url": "https://...",
  "cover_image_url": "https://...",
  "date_of_birth": "1990-01-01",
  "country_code": "US",
  "currency_code": "USD",
  "crypto_wallet_address": "0x123...",
  "is_verified": true,
  "verification_level": 3,
  "privacy_settings": {
    "profile_public": true,
    "savings_public": true,
    "portfolio_public": false
  },
  "notification_settings": {
    "push": true,
    "email": true,
    "sms": false
  },
  "created_at": "2024-01-01T00:00:00Z",
  "stats": {
    "followers_count": 150,
    "following_count": 200,
    "total_savings": 1250.50,
    "crypto_portfolio_value": 3200.75
  }
}
```

### Update User Profile
```http
PATCH /users/me
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "full_name": "John Updated",
  "bio": "New bio text",
  "profile_image_url": "https://new-image.com/profile.jpg",
  "privacy_settings": {
    "portfolio_public": true
  }
}

Response:
{
  "id": "user_123",
  "username": "johndoe",
  "full_name": "John Updated",
  "bio": "New bio text",
  "profile_image_url": "https://new-image.com/profile.jpg",
  "privacy_settings": {
    "profile_public": true,
    "savings_public": true,
    "portfolio_public": true
  },
  "updated_at": "2024-01-02T12:00:00Z"
}
```

### Search Users
```http
GET /users/search?q=john&limit=20&offset=0
Authorization: Bearer <access_token>

Response:
{
  "users": [
    {
      "id": "user_123",
      "username": "johndoe",
      "full_name": "John Doe",
      "profile_image_url": "https://...",
      "is_following": true,
      "follows_you": false
    }
  ],
  "pagination": {
    "total": 45,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

## Social Features

### Follow/Unfollow User
```http
POST /users/{user_id}/follow
Authorization: Bearer <access_token>

Response:
{
  "following": true,
  "relationship": {
    "id": "rel_123",
    "follower_id": "current_user_id",
    "following_id": "user_123",
    "relationship_type": "follow",
    "created_at": "2024-01-01T12:00:00Z"
  }
}

DELETE /users/{user_id}/follow
Authorization: Bearer <access_token>

Response:
{
  "following": false,
  "message": "Unfollowed successfully"
}
```

### Get User Feed (Instagram-style)
```http
GET /feed?limit=20&cursor=<cursor>
Authorization: Bearer <access_token>

Response:
{
  "posts": [
    {
      "id": "post_123",
      "user": {
        "id": "user_123",
        "username": "johndoe",
        "profile_image_url": "https://..."
      },
      "content_type": "purchase",
      "title": "Just saved $15 on groceries!",
      "description": "Found great deals at Whole Foods",
      "media_urls": ["https://.../receipt1.jpg", "https://.../receipt2.jpg"],
      "product_info": {
        "merchant": "Whole Foods",
        "total_amount": 85.50,
        "savings_amount": 15.25,
        "items": [...]
      },
      "location": {
        "name": "Whole Foods Market",
        "address": "123 Main St"
      },
      "tags": ["#groceries", "#savings", "#wholefoods"],
      "engagement": {
        "likes_count": 45,
        "comments_count": 12,
        "saves_count": 8,
        "user_liked": true,
        "user_saved": false
      },
      "created_at": "2024-01-01T10:30:00Z",
      "expires_at": null
    }
  ],
  "pagination": {
    "next_cursor": "cursor_123",
    "has_more": true
  },
  "metadata": {
    "total_posts": 150,
    "new_posts_since_last_visit": 5
  }
}
```

### Create Shopping Post
```http
POST /posts
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

{
  "content_type": "purchase",
  "title": "Great deal at Target!",
  "description": "Saved 30% on household items",
  "media": [file1, file2],  # Receipt images
  "product_info": {
    "merchant": "Target",
    "total_amount": 75.50,
    "savings_amount": 22.65,
    "items": [
      {"name": "Paper Towels", "price": 12.99, "savings": 3.25},
      {"name": "Cleaning Supplies", "price": 24.99, "savings": 7.50}
    ]
  },
  "location": {
    "name": "Target",
    "address": "456 Oak St"
  },
  "tags": ["#target", "#savings", "#household"],
  "privacy_level": "public"
}

Response:
{
  "post": {
    "id": "post_456",
    "user_id": "current_user_id",
    "content_type": "purchase",
    "title": "Great deal at Target!",
    "description": "Saved 30% on household items",
    "media_urls": ["https://.../receipt1.jpg", "https://.../receipt2.jpg"],
    "product_info": {...},
    "location": {...},
    "tags": ["#target", "#savings", "#household"],
    "privacy_level": "public",
    "created_at": "2024-01-01T14:30:00Z"
  },
  "roundup_created": {
    "id": "roundup_123",
    "amount": 0.50,
    "added_to_pool": true
  }
}
```

### Post Engagement
```http
POST /posts/{post_id}/like
Authorization: Bearer <access_token>

Response:
{
  "liked": true,
  "likes_count": 46
}

POST /posts/{post_id}/save
Authorization: Bearer <access_token>

Response:
{
  "saved": true,
  "saves_count": 9
}

POST /posts/{post_id}/comments
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "content": "Great find! Where did you get this deal?"
}

Response:
{
  "comment": {
    "id": "comment_123",
    "user": {
      "id": "current_user_id",
      "username": "current_user",
      "profile_image_url": "https://..."
    },
    "content": "Great find! Where did you get this deal?",
    "created_at": "2024-01-01T15:00:00Z"
  },
  "comments_count": 13
}
```

## Financial Transactions

### Process Receipt (OCR + Roundup)
```http
POST /transactions/receipt
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

{
  "receipt_image": file,
  "merchant_name": "Walmart",  # Optional, auto-detected
  "transaction_date": "2024-01-01",  # Optional
  "roundup_enabled": true,
  "investment_strategy": "balanced"
}

Response:
{
  "transaction": {
    "id": "txn_123",
    "user_id": "current_user_id",
    "transaction_type": "purchase",
    "amount": 65.75,
    "currency_code": "USD",
    "status": "completed",
    "merchant_info": {
      "name": "Walmart",
      "category": "groceries",
      "location": {
        "address": "789 Pine St",
        "city": "San Francisco"
      }
    },
    "receipt_data": {
      "items": [
        {"name": "Milk", "price": 3.99, "quantity": 1},
        {"name": "Bread", "price": 2.49, "quantity": 1}
      ],
      "subtotal": 65.75,
      "tax": 4.12,
      "total": 69.87
    },
    "created_at": "2024-01-01T16:30:00Z"
  },
  "roundup": {
    "id": "roundup_456",
    "original_amount": 65.75,
    "roundup_amount": 0.25,
    "pool_type": "daily",
    "status": "active"
  },
  "savings_post": {
    "id": "post_789",
    "title": "Saved $0.25 at Walmart!",
    "auto_shared": true
  }
}
```

### Get Transaction History
```http
GET /transactions?limit=50&offset=0&start_date=2024-01-01&end_date=2024-01-31
Authorization: Bearer <access_token>

Response:
{
  "transactions": [
    {
      "id": "txn_123",
      "transaction_type": "purchase",
      "amount": 65.75,
      "currency_code": "USD",
      "crypto_amount": null,
      "crypto_currency": null,
      "status": "completed",
      "merchant_info": {
        "name": "Walmart",
        "category": "groceries"
      },
      "location": {
        "name": "Walmart Supercenter",
        "address": "789 Pine St"
      },
      "created_at": "2024-01-01T16:30:00Z"
    }
  ],
  "summary": {
    "total_spent": 1250.50,
    "total_saved": 45.75,
    "total_roundups": 12.25,
    "crypto_invested": 8.50
  },
  "pagination": {
    "total": 150,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

### Initiate Crypto Investment
```http
POST /investments/crypto
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": 50.00,
  "currency_code": "USD",
  "cryptocurrency": "BTC",
  "investment_strategy": "conservative",
  "source": "roundup_pool",  # or "bank_account", "card"
  "auto_reinvest": true
}

Response:
{
  "investment": {
    "id": "inv_123",
    "user_id": "current_user_id",
    "amount": 50.00,
    "currency_code": "USD",
    "cryptocurrency": "BTC",
    "crypto_amount": 0.0012,
    "price_at_purchase": 41666.67,
    "fee": 0.50,
    "status": "pending",
    "estimated_completion": "2024-01-01T17:00:00Z",
    "created_at": "2024-01-01T16:45:00Z"
  },
  "portfolio_update": {
    "total_crypto_value": 3200.75,
    "btc_holdings": 0.0125,
    "unrealized_pnl": 150.25
  }
}
```

## Crypto Portfolio

### Get Portfolio Summary
```http
GET /portfolio
Authorization: Bearer <access_token>

Response:
{
  "summary": {
    "total_value": 3200.75,
    "total_invested": 3050.50,
    "unrealized_pnl": 150.25,
    "pnl_percentage": 4.92,
    "daily_change": 25.50,
    "daily_change_percentage": 0.80
  },
  "holdings": [
    {
      "cryptocurrency": "BTC",
      "amount": 0.0125,
      "current_price": 42000.00,
      "current_value": 525.00,
      "average_buy_price": 41000.00,
      "unrealized_pnl": 12.50,
      "allocation_percentage": 16.4,
      "daily_change": 2.50
    },
    {
      "cryptocurrency": "ETH",
      "amount": 0.85,
      "current_price": 2200.00,
      "current_value": 1870.00,
      "average_buy_price": 2150.00,
      "unrealized_pnl": 42.50,
      "allocation_percentage": 58.4,
      "daily_change": 15.00
    }
  ],
  "performance": {
    "daily": 1.2,
    "weekly": 4.5,
    "monthly": 12.3,
    "yearly": 45.6
  }
}
```

### Get Transaction History
```http
GET /portfolio/transactions?cryptocurrency=BTC&limit=20&offset=0
Authorization: Bearer <access_token>

Response:
{
  "transactions": [
    {
      "id": "crypto_txn_123",
      "transaction_type": "buy",
      "cryptocurrency": "BTC",
      "amount": 0.0012,
      "price": 41666.67,
      "total_value": 50.00,
      "fee": 0.50,
      "exchange": "Coinbase",
      "status": "completed",
      "executed_at": "2024-01-01T17:00:00Z"
    }
  ],
  "pagination": {
    "total": 45,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

## Savings Goals & Challenges

### Create Savings Goal
```http
POST /savings/goals
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "goal_name": "New Laptop",
  "description": "Saving for a new MacBook Pro",
  "target_amount": 2000.00,
  "currency_code": "USD",
  "deadline_date": "2024-06-01",
  "icon_url": "https://.../laptop-icon.png",
  "color_hex": "#06D6A0",
  "privacy_level": "public"
}

Response:
{
  "goal": {
    "id": "goal_123",
    "user_id": "current_user_id",
    "goal_name": "New Laptop",
    "description": "Saving for a new MacBook Pro",
    "target_amount": 2000.00,
    "current_amount": 0.00,
    "currency_code": "USD",
    "deadline_date": "2024-06-01",
    "icon_url": "https://.../laptop-icon.png",
    "color_hex": "#06D6A0",
    "privacy_level": "public",
    "is_completed": false,
    "progress_percentage": 0.0,
    "days_remaining": 152,
    "created_at": "2024-01-01T18:00:00Z"
  }
}
```

### Join Savings Challenge
```http
POST /challenges/{challenge_id}/join
Authorization: Bearer <access_token>

Response:
{
  "participation": {
    "id": "part_123",
    "challenge_id": "challenge_123",
    "user_id": "current_user_id",
    "status": "active",
    "progress_data": {
      "current_savings": 0.00,
      "target_savings": 100.00,
      "days_completed": 0,
      "streak_days": 0
    },
    "joined_at": "2024-01-01T18:30:00Z"
  },
  "challenge": {
    "id": "challenge_123",
    "challenge_name": "30-Day No Spend Challenge",
    "description": "Save $100 in 30 days by cutting unnecessary spending",
    "challenge_type": "no_spend",
    "duration_days": 30,
    "entry_fee": 0.00,
    "prize_pool": 500.00,
    "current_participants": 45,
    "max_participants": 100,
    "status": "active",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z"
  }
}
```

## Real-time WebSocket API

### Connection
```javascript
const ws = new WebSocket('wss://api.keepthechange.com/ws/v1');

// Authentication
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'access_token_here'
  }));
};

// Subscribe to channels
ws.send(JSON.stringify({
  type: 'subscribe',
  channels: ['feed_updates', 'portfolio_updates', 'notifications']
}));
```

### Event Types
```json
{
  "type": "feed_update",
  "data": {
    "event": "new_post",
    "post": {
      "id": "post_123",
      "user_id": "user_456",
      "content_type": "purchase",
      "title": "New savings post!",
      "created_at": "2024-01-01T19:00:00Z"
    }
  }
}

{
  "type": "portfolio_update",
  "data": {
    "event": "price_change",
    "cryptocurrency": "BTC",
    "new_price": 42150.25,
    "change_percentage": 0.36,
    "timestamp": "2024-01-01T19:05:00Z"
  }
}

{
  "type": "notification",
  "data": {
    "id": "notif_123",
    "notification_type": "like",
    "title": "John liked your post",
    "message": "John Doe liked your savings post",
    "data": {
      "post_id": "post_123",
      "user_id": "user_456"
    },
    "created_at": "2024-01-01T19:10:00Z"
  }
}
```

## SIMP Agent Integration API

### KTC Agent Endpoints
```http
POST /agents/ktc/process-receipt
Content-Type: application/json
X-API-Key: <agent_api_key>

{
  "user_id": "user_123",
  "receipt_image_base64": "base64_encoded_image",
  "context": {
    "merchant_hint": "Walmart",
    "location_hint": "San Francisco"
  }
}

Response:
{
  "processed": true,
  "transaction_data": {
    "merchant": "Walmart",
    "total_amount": 65.75,
    "items": [...],
    "savings_opportunities": [
      {
        "item": "Milk",
        "competitor_price": 3.49,
        "potential_savings": 0.50,
        "competitor": "Target"
      }
    ]
  },
  "roundup_recommendation": {
    "amount": 0.25,
    "rationale": "Standard roundup to nearest dollar"
  }
}
```

### QuantumArb Integration
```http
POST /agents/quantumarb/invest
Content-Type: application/json
X-API-Key: <agent_api_key>

{
  "user_id": "user_123",
  "amount": 50.00,
  "currency": "USD",
  "risk_profile": "conservative",
  "time_horizon": "short_term"
}

Response:
{
  "investment_decision": {
    "cryptocurrency": "BTC",
    "amount_to_invest": 50.00,
    "expected_apy": 8.5,
    "risk_score": 0.2,
    "rationale": "Current market conditions favorable for BTC accumulation",
    "execution_plan": {
      "exchange": "Coinbase",
      "estimated_price": 41666.67,
      "estimated_fee": 0.50,
      "estimated_completion": "2024-01-01T20:00:00Z"
    }
  }
}
```

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "email": "Must be a valid email address"
    },
    "request_id": "req_123456789",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

### Common Error Codes
- `AUTH_REQUIRED`: Authentication required
- `INVALID_TOKEN`: Invalid or expired token
- `PERMISSION_DENIED`: Insufficient permissions
- `VALIDATION_ERROR`: Invalid input parameters
- `RESOURCE_NOT_FOUND`: Requested resource not found
- `RATE_LIMITED`: Rate limit exceeded
- `INTERNAL_ERROR`: Internal server error

## Rate Limiting

### Default Limits
- **Unauthenticated**: 100 requests/hour
- **Authenticated Users**: 1000 requests/hour
- **Premium Users**: 5000 requests/hour
- **Agents/Partners**: 10000 requests/hour

### Headers
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1704110400
```

## Webhook System

### Webhook Events
```http
POST /webhooks/merchant
Content-Type: application/json
X-Webhook-Signature: <signature>

{
  "event": "price_change",
  "data": {
    "product_id": "prod_123",
    "merchant_id": "merchant_456",
    "old_price": 29.99,
    "new_price": 24.99,
    "change_percentage": -16.67,
    "effective_from": "2024-01-01T00:00:00Z"
  },
  "timestamp": "2024-01-01T21:00:00Z"
}
```

### Supported Webhook Events
1. `price_change` - Product price changes
2. `new_product` - New products added
3. `stock_update` - Product stock changes
4. `merchant_verification` - Merchant verification status
5. `affiliate_payout` - Affiliate commission payout

## API Versioning Policy

### Version Support
- **Current**: v1 (stable)
- **Previous**: v0 (deprecated, 6-month sunset)
- **Beta**: v2-beta (experimental features)

### Deprecation Timeline
1. **Announcement**: 3 months before deprecation
2. **Deprecation**: Marked as deprecated, still functional
3. **Sunset**: 6 months after deprecation, returns 410 Gone

## Security Headers

### Required Headers
- `Content-Type: application/json` for JSON requests
- `Authorization: Bearer <token>` for authenticated requests
- `X-Request-ID` for request tracing (optional but recommended)

### Response Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`

## Testing Endpoints

### Health Check
```http
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2024-01-01T22:00:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "elasticsearch": "healthy",
    "kafka": "healthy"
  },
  "version": "1.0.0",
  "uptime": "7d 12h 30m"
}
```

### Metrics
```http
GET /metrics

Response (Prometheus format):
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET", endpoint="/health", status="200"} 12345
```

This comprehensive API contract provides all the endpoints needed to build the Instagram-inspired social shopping platform, supporting both user-facing features and backend agent integrations.