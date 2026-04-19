# KEEPTHECHANGE.com - API Specification
## Instagram's Crypto Twin

## Overview
This document specifies the RESTful API endpoints for KEEPTHECHANGE.com, including authentication, request/response formats, and error handling.

## API Versioning
- Base URL: `https://api.keepthechange.com/v1`
- Version header: `X-API-Version: 1.0`
- Content-Type: `application/json`

## Authentication
### OAuth 2.0 Flow
```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&client_id={client_id}
&client_secret={client_secret}
&code={authorization_code}
&redirect_uri={redirect_uri}
```

### Response
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "def50200e3b8c4a4f5a7c8b9d0e1f2g3...",
  "scope": "user:read user:write wallet:read wallet:write social:read social:write"
}
```

### API Key Authentication (for partners)
- Header: `X-API-Key: {partner_api_key}`
- Rate limit: 1000 requests per hour

## Rate Limiting
- Standard users: 100 requests/minute
- Verified creators: 500 requests/minute
- Partners: 1000 requests/minute
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Error Handling
### Standard Error Response
```json
{
  "error": {
    "code": "invalid_request",
    "message": "The request was malformed or missing required parameters.",
    "details": {
      "field": "email",
      "issue": "Email format is invalid"
    },
    "request_id": "req_1234567890abcdef",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### HTTP Status Codes
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 422: Unprocessable Entity
- 429: Too Many Requests
- 500: Internal Server Error

## User Management

### Get Current User
```
GET /users/me
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "user": {
    "id": "user_1234567890",
    "username": "crypto_shopper",
    "email": "user@example.com",
    "display_name": "Crypto Shopper",
    "avatar_url": "https://cdn.keepthechange.com/avatars/user_1234567890.jpg",
    "bio": "Loving crypto shopping!",
    "is_verified": true,
    "is_creator": false,
    "joined_at": "2024-01-01T00:00:00Z",
    "stats": {
      "followers": 1250,
      "following": 350,
      "posts": 42,
      "likes_received": 12500,
      "total_spent": 1250.50,
      "total_earned": 350.25
    },
    "preferences": {
      "currency": "USD",
      "language": "en",
      "notifications": {
        "email": true,
        "push": true,
        "in_app": true
      }
    }
  }
}
```

### Update User Profile
```
PATCH /users/me
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "display_name": "New Display Name",
  "bio": "Updated bio",
  "avatar_url": "https://example.com/new-avatar.jpg",
  "preferences": {
    "currency": "EUR",
    "language": "fr"
  }
}
```

### Search Users
```
GET /users/search?q={query}&limit=20&offset=0
Authorization: Bearer {access_token}
```

## Wallet Management

### Get Wallet Balance
```
GET /wallets/me
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "wallet": {
    "id": "wallet_1234567890",
    "user_id": "user_1234567890",
    "address": "0x742d35Cc6634C0532925a3b844Bc9e...",
    "balances": [
      {
        "currency": "USDC",
        "amount": "1250.50",
        "value_usd": "1250.50"
      },
      {
        "currency": "ETH",
        "amount": "2.5",
        "value_usd": "6250.00"
      },
      {
        "currency": "BTC",
        "amount": "0.1",
        "value_usd": "4500.00"
      }
    ],
    "total_value_usd": "12000.50",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### Get Transaction History
```
GET /wallets/me/transactions?limit=50&offset=0&type={type}
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `type`: `all`, `deposit`, `withdrawal`, `purchase`, `sale`, `reward`, `commission`

**Response:**
```json
{
  "transactions": [
    {
      "id": "tx_1234567890",
      "type": "purchase",
      "status": "completed",
      "amount": "25.50",
      "currency": "USDC",
      "description": "Purchase: Vintage T-Shirt",
      "counterparty": "store_abcdef123456",
      "timestamp": "2024-01-15T10:25:00Z",
      "blockchain_tx_hash": "0xabcdef1234567890...",
      "network_fee": "0.50",
      "network": "polygon"
    }
  ],
  "pagination": {
    "total": 125,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

### Deposit Funds
```
POST /wallets/me/deposit
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "currency": "USDC",
  "amount": "100.00",
  "network": "polygon"
}
```

**Response:**
```json
{
  "deposit": {
    "id": "dep_1234567890",
    "status": "pending",
    "address": "0xDepositAddressForUser...",
    "currency": "USDC",
    "amount": "100.00",
    "network": "polygon",
    "expires_at": "2024-01-15T11:30:00Z",
    "qr_code_url": "https://api.keepthechange.com/qr/dep_1234567890.png"
  }
}
```

### Withdraw Funds
```
POST /wallets/me/withdraw
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "currency": "USDC",
  "amount": "50.00",
  "destination_address": "0xUserExternalWallet...",
  "network": "polygon"
}
```

## Social Features

### Create Post
```
POST /posts
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**Form Data:**
- `caption`: "Check out this amazing product!"
- `product_ids[]`: ["prod_123", "prod_456"]
- `media[]`: [file1.jpg, file2.jpg]
- `tags[]`: ["fashion", "crypto", "shopping"]
- `location`: "New York, NY"
- `is_sponsored`: false

**Response:**
```json
{
  "post": {
    "id": "post_1234567890",
    "user_id": "user_1234567890",
    "caption": "Check out this amazing product!",
    "media": [
      {
        "id": "media_123",
        "type": "image",
        "url": "https://cdn.keepthechange.com/posts/post_1234567890/media_123.jpg",
        "thumbnail_url": "https://cdn.keepthechange.com/posts/post_1234567890/media_123_thumb.jpg",
        "width": 1080,
        "height": 1350
      }
    ],
    "products": [
      {
        "id": "prod_123",
        "name": "Vintage T-Shirt",
        "price": "25.50",
        "currency": "USDC",
        "store_id": "store_abcdef123456"
      }
    ],
    "tags": ["fashion", "crypto", "shopping"],
    "location": "New York, NY",
    "is_sponsored": false,
    "stats": {
      "likes": 0,
      "comments": 0,
      "shares": 0,
      "clicks": 0,
      "purchases": 0
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### Get Feed
```
GET /feed?limit=20&offset=0
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `algorithm`: `chronological`, `popular`, `personalized` (default)
- `filter`: `following`, `discover`, `shopping`

### Like/Unlike Post
```
POST /posts/{post_id}/like
DELETE /posts/{post_id}/like
Authorization: Bearer {access_token}
```

### Comment on Post
```
POST /posts/{post_id}/comments
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "text": "This looks amazing! Where can I buy it?",
  "parent_comment_id": "comment_123"  // Optional for replies
}
```

### Follow/Unfollow User
```
POST /users/{user_id}/follow
DELETE /users/{user_id}/follow
Authorization: Bearer {access_token}
```

## Marketplace

### Search Products
```
GET /products/search?q={query}&category={category}&min_price={min}&max_price={max}&sort={sort}&limit=20&offset=0
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `category`: `fashion`, `electronics`, `home`, `art`, `collectibles`
- `sort`: `relevance`, `price_asc`, `price_desc`, `newest`, `popular`
- `in_stock_only`: `true`/`false`

### Get Product Details
```
GET /products/{product_id}
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "product": {
    "id": "prod_1234567890",
    "name": "Limited Edition Crypto Hoodie",
    "description": "Exclusive hoodie with blockchain-inspired design",
    "price": "89.99",
    "currency": "USDC",
    "original_price": "119.99",
    "discount_percent": 25,
    "category": "fashion",
    "subcategory": "apparel",
    "tags": ["limited", "crypto", "hoodie", "exclusive"],
    "images": [
      {
        "url": "https://cdn.keepthechange.com/products/prod_1234567890/1.jpg",
        "is_primary": true
      }
    ],
    "inventory": {
      "total": 100,
      "available": 42,
      "reserved": 8
    },
    "store": {
      "id": "store_abcdef123456",
      "name": "Crypto Fashion Co",
      "verified": true,
      "rating": 4.8
    },
    "specifications": {
      "material": "100% Cotton",
      "sizes": ["S", "M", "L", "XL"],
      "colors": ["Black", "White", "Gray"]
    },
    "shipping": {
      "domestic": {
        "cost": "5.00",
        "currency": "USDC",
        "estimated_days": "3-5"
      },
      "international": {
        "cost": "15.00",
        "currency": "USDC",
        "estimated_days": "7-14"
      }
    },
    "stats": {
      "views": 1250,
      "purchases": 89,
      "wishlists": 42,
      "average_rating": 4.7,
      "review_count": 35
    },
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### Create Order
```
POST /orders
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "items": [
    {
      "product_id": "prod_1234567890",
      "quantity": 1,
      "selected_options": {
        "size": "M",
        "color": "Black"
      }
    }
  ],
  "shipping_address": {
    "name": "John Doe",
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "postal_code": "10001",
    "country": "US"
  },
  "payment_method": "wallet",
  "currency": "USDC"
}
```

**Response:**
```json
{
  "order": {
    "id": "order_1234567890",
    "status": "pending_payment",
    "total_amount": "94.99",
    "currency": "USDC",
    "items": [
      {
        "product_id": "prod_1234567890",
        "name": "Limited Edition Crypto Hoodie",
        "quantity": 1,
        "unit_price": "89.99",
        "total_price": "89.99"
      }
    ],
    "shipping_cost": "5.00",
    "tax": "0.00",
    "payment_address": "0xPaymentAddressForOrder...",
    "payment_expires_at": "2024-01-15T11:30:00Z",
    "estimated_delivery": "2024-01-20T00:00:00Z",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### Confirm Payment
```
POST /orders/{order_id}/confirm-payment
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "transaction_hash": "0xabcdef1234567890..."
}
```

## Creator Features

### Get Creator Dashboard
```
GET /creators/me/dashboard
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "dashboard": {
    "overview": {
      "total_earnings": "1250.50",
      "pending_earnings": "250.75",
      "available_balance": "999.75",
      "total_sales": 42,
      "conversion_rate": 3.2,
      "average_order_value": "29.77"
    },
    "recent_activity": [
      {
        "type": "sale",
        "product_name": "Vintage T-Shirt",
        "amount": "25.50",
        "timestamp": "2024-01-15T10:25:00Z"
      }
    ],
    "top_products": [
      {
        "product_id": "prod_1234567890",
        "name": "Limited Edition Crypto Hoodie",
        "sales": 15,
        "revenue": "1349.85"
      }
    ],
    "audience_insights": {
      "total_followers": 1250,
      "new_followers_today": 12,
      "top_locations": ["US", "UK", "DE"],
      "age_distribution": {
        "18-24": 35,
        "25-34": 45,
        "35-44": 15,
        "45+": 5
      }
    }
  }
}
```

### Create Product Listing
```
POST /creators/me/products
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

## Webhooks

### Webhook Subscription
```
POST /webhooks
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "url": "https://your-server.com/webhooks/keepthechange",
  "events": [
    "order.created",
    "order.paid",
    "order.shipped",
    "order.delivered",
    "payment.completed",
    "user.registered"
  ],
  "secret": "your_webhook_secret"
}
```

### Webhook Events Payload
```json
{
  "event": "order.paid",
  "data": {
    "order_id": "order_1234567890",
    "user_id": "user_1234567890",
    "total_amount": "94.99",
    "currency": "USDC",
    "paid_at": "2024-01-15T10:35:00Z"
  },
  "timestamp": "2024-01-15T10:35:00Z",
  "webhook_id": "wh_1234567890"
}
```

### Webhook Signature Verification
Header: `X-KTC-Signature: t=timestamp,s=signature`

## Real-time Features (WebSocket)

### Connection
```
wss://api.keepthechange.com/v1/ws
```

**Authentication:**
```json
{
  "type": "auth",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Subscribe to Channels
```json
{
  "type": "subscribe",
  "channels": [
    "user:user_1234567890",
    "notifications",
    "feed_updates"
  ]
}
```

### Real-time Events
```json
{
  "type": "notification",
  "data": {
    "id": "notif_1234567890",
    "type": "like",
    "from_user": {
      "id": "user_abcdef123456",
      "username": "crypto_fan",
      "avatar_url": "..."
    },
    "post_id": "post_1234567890",
    "timestamp": "2024-01-15T10:40:00Z"
  }
}
```

## Security Headers

### Required Headers for All Responses
- `Content-Security-Policy`: "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.keepthechange.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://cdn.keepthechange.com https://*.cloudinary.com;"
- `X-Content-Type-Options`: "nosniff"
- `X-Frame-Options`: "DENY"
- `X-XSS-Protection`: "1; mode=block"
- `Strict-Transport-Security`: "max-age=31536000; includeSubDomains"
- `Referrer-Policy`: "strict-origin-when-cross-origin"

## Data Privacy

### GDPR Compliance Endpoints
```
GET /users/me/data-export
DELETE /users/me
POST /users/me/consent
```

### CCPA Compliance
```
GET /users/me/do-not-sell
POST /users/me/do-not-sell
```

## Testing

### Sandbox Environment
- Base URL: `https://sandbox-api.keepthechange.com/v1`
- Test cards/accounts provided
- No real funds required

### Mock Responses
Add header: `X-Mock-Response: true` to get predictable test data

## Changelog

### Version 1.0 (2024-01-15)
- Initial API release
- User management
- Wallet operations
- Social features
- Marketplace
- Creator tools

### Version 1.1 (Planned)
- Advanced analytics endpoints
- Bulk operations
- Enhanced webhook system
- Multi-currency support