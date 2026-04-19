# KEEPTHECHANGE.com - Database Schema
## Instagram's Crypto Twin

## Overview
This document defines the complete database schema for KEEPTHECHANGE.com, detailing all tables, relationships, indexes, and data models required to support the Instagram-inspired social shopping platform.

## Database Technology Stack
- **Primary Database**: PostgreSQL 15+ (relational)
- **Cache Layer**: Redis 7+ (session, feed, real-time)
- **Search Engine**: Elasticsearch 8+ (product search, recommendations)
- **Analytics**: TimescaleDB (time-series for financial data)
- **Message Queue**: Apache Kafka (event streaming)

## Core Schema Design Principles
1. **Instagram Parallel**: User-centric design with social relationships
2. **Financial Integrity**: ACID compliance for all monetary transactions
3. **Scalability**: Shard-ready design for user growth
4. **Real-time Ready**: Optimized for WebSocket and feed updates
5. **Audit Trail**: Complete history for compliance and debugging

## Main Tables

### 1. Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE,
    full_name VARCHAR(100),
    bio TEXT,
    profile_image_url VARCHAR(500),
    cover_image_url VARCHAR(500),
    date_of_birth DATE,
    country_code CHAR(2),
    currency_code CHAR(3) DEFAULT 'USD',
    crypto_wallet_address VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_level SMALLINT DEFAULT 0, -- 0-5
    privacy_settings JSONB DEFAULT '{"profile_public": true, "savings_public": true, "portfolio_public": false}',
    notification_settings JSONB DEFAULT '{"push": true, "email": true, "sms": false}',
    mfa_enabled BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    INDEX idx_users_username (username),
    INDEX idx_users_email (email),
    INDEX idx_users_created_at (created_at)
);
```

### 2. User Authentication
```sql
CREATE TABLE user_auth (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    password_salt VARCHAR(255) NOT NULL,
    totp_secret VARCHAR(255),
    recovery_codes TEXT[],
    failed_attempts SMALLINT DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_password_change TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    device_info JSONB,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_user_sessions_user_id (user_id),
    INDEX idx_user_sessions_expires_at (expires_at)
);
```

### 3. Social Relationships
```sql
CREATE TABLE user_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id UUID REFERENCES users(id) ON DELETE CASCADE,
    following_id UUID REFERENCES users(id) ON DELETE CASCADE,
    relationship_type VARCHAR(20) DEFAULT 'follow', -- follow, close_friend, family
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(follower_id, following_id),
    INDEX idx_user_relationships_follower (follower_id),
    INDEX idx_user_relationships_following (following_id)
);

CREATE TABLE user_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blocker_id UUID REFERENCES users(id) ON DELETE CASCADE,
    blocked_id UUID REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(blocker_id, blocked_id)
);
```

### 4. Shopping Feed (Instagram-style)
```sql
CREATE TABLE shopping_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content_type VARCHAR(20) NOT NULL, -- purchase, savings_goal, investment, story
    title VARCHAR(200),
    description TEXT,
    media_urls TEXT[], -- Array of image/video URLs
    product_info JSONB, -- Product details from receipt
    location JSONB, -- {lat, lng, name, address}
    tags TEXT[], -- Hashtags
    privacy_level VARCHAR(20) DEFAULT 'public', -- public, followers, private
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ, -- For stories (24 hours)
    INDEX idx_shopping_posts_user_id (user_id),
    INDEX idx_shopping_posts_created_at (created_at DESC),
    INDEX idx_shopping_posts_content_type (content_type),
    INDEX idx_shopping_posts_tags (tags) USING GIN
);

CREATE TABLE post_engagement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES shopping_posts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    engagement_type VARCHAR(20) NOT NULL, -- like, comment, save, share
    content TEXT, -- For comments
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(post_id, user_id, engagement_type) WHERE engagement_type != 'comment',
    INDEX idx_post_engagement_post_id (post_id),
    INDEX idx_post_engagement_user_id (user_id),
    INDEX idx_post_engagement_type (engagement_type)
);
```

### 5. Financial Transactions
```sql
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    transaction_type VARCHAR(30) NOT NULL, -- purchase, roundup, crypto_buy, crypto_sell, withdrawal, deposit
    amount DECIMAL(20,8) NOT NULL,
    currency_code CHAR(3) NOT NULL,
    crypto_amount DECIMAL(20,8),
    crypto_currency VARCHAR(10), -- BTC, ETH, etc.
    exchange_rate DECIMAL(20,8),
    fee_amount DECIMAL(20,8) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- pending, completed, failed, refunded
    source_type VARCHAR(30), -- card, bank, crypto_wallet
    source_id VARCHAR(255),
    destination_type VARCHAR(30),
    destination_id VARCHAR(255),
    receipt_data JSONB, -- OCR processed receipt data
    merchant_info JSONB,
    location JSONB,
    metadata JSONB,
    blockchain_tx_hash VARCHAR(255),
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_transactions_user_id (user_id),
    INDEX idx_transactions_type (transaction_type),
    INDEX idx_transactions_status (status),
    INDEX idx_transactions_created_at (created_at DESC)
);

CREATE TABLE roundup_pool (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    transaction_id UUID REFERENCES transactions(id) ON DELETE CASCADE,
    original_amount DECIMAL(20,8) NOT NULL,
    roundup_amount DECIMAL(20,8) NOT NULL,
    pool_type VARCHAR(20) DEFAULT 'daily', -- daily, weekly, monthly, custom
    target_amount DECIMAL(20,8),
    investment_strategy VARCHAR(30), -- conservative, balanced, aggressive
    status VARCHAR(20) DEFAULT 'active', -- active, invested, withdrawn
    invested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_roundup_pool_user_id (user_id),
    INDEX idx_roundup_pool_status (status)
);
```

### 6. Crypto Portfolio
```sql
CREATE TABLE crypto_holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    cryptocurrency VARCHAR(10) NOT NULL, -- BTC, ETH, SOL, etc.
    amount DECIMAL(20,8) NOT NULL,
    average_buy_price DECIMAL(20,8),
    current_value DECIMAL(20,8),
    unrealized_pnl DECIMAL(20,8),
    allocation_percentage DECIMAL(5,2),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, cryptocurrency),
    INDEX idx_crypto_holdings_user_id (user_id)
);

CREATE TABLE crypto_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    holding_id UUID REFERENCES crypto_holdings(id) ON DELETE CASCADE,
    transaction_type VARCHAR(20) NOT NULL, -- buy, sell, transfer, reward
    amount DECIMAL(20,8) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    fee DECIMAL(20,8) DEFAULT 0,
    exchange VARCHAR(50),
    wallet_address VARCHAR(255),
    blockchain_tx_hash VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    metadata JSONB,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_crypto_transactions_user_id (user_id),
    INDEX idx_crypto_transactions_type (transaction_type)
);
```

### 7. Savings Goals & Challenges
```sql
CREATE TABLE savings_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    goal_name VARCHAR(100) NOT NULL,
    description TEXT,
    target_amount DECIMAL(20,8) NOT NULL,
    current_amount DECIMAL(20,8) DEFAULT 0,
    currency_code CHAR(3) DEFAULT 'USD',
    deadline_date DATE,
    icon_url VARCHAR(500),
    color_hex CHAR(7) DEFAULT '#FF6B6B',
    privacy_level VARCHAR(20) DEFAULT 'public',
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_savings_goals_user_id (user_id),
    INDEX idx_savings_goals_completed (is_completed)
);

CREATE TABLE savings_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID REFERENCES users(id) ON DELETE CASCADE,
    challenge_name VARCHAR(100) NOT NULL,
    description TEXT,
    challenge_type VARCHAR(30) NOT NULL, -- no_spend, roundup_boost, group_saving
    rules JSONB NOT NULL,
    duration_days INTEGER NOT NULL,
    entry_fee DECIMAL(20,8) DEFAULT 0,
    prize_pool DECIMAL(20,8),
    max_participants INTEGER,
    privacy_level VARCHAR(20) DEFAULT 'public',
    status VARCHAR(20) DEFAULT 'active', -- active, completed, cancelled
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_savings_challenges_creator (creator_id),
    INDEX idx_savings_challenges_status (status)
);

CREATE TABLE challenge_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID REFERENCES savings_challenges(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'active', -- active, completed, failed
    progress_data JSONB,
    rank INTEGER,
    prize_won DECIMAL(20,8),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE(challenge_id, user_id)
);
```

### 8. Merchant & Product Catalog
```sql
CREATE TABLE merchants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    website_url VARCHAR(500),
    logo_url VARCHAR(500),
    location JSONB,
    contact_info JSONB,
    is_verified BOOLEAN DEFAULT FALSE,
    affiliate_program JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_merchants_name (name),
    INDEX idx_merchants_category (category)
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID REFERENCES merchants(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    brand VARCHAR(100),
    sku VARCHAR(100),
    upc VARCHAR(50),
    current_price DECIMAL(10,2),
    currency_code CHAR(3) DEFAULT 'USD',
    image_urls TEXT[],
    specifications JSONB,
    affiliate_link VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_products_merchant (merchant_id),
    INDEX idx_products_category (category),
    INDEX idx_products_name (name)
);

CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(10,2) NOT NULL,
    currency_code CHAR(3) DEFAULT 'USD',
    source VARCHAR(100), -- merchant, competitor, user_report
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_price_history_product (product_id),
    INDEX idx_price_history_created_at (created_at DESC)
);
```

### 9. Notifications & Messaging
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL, -- like, comment, follow, transaction, challenge
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    data JSONB, -- Related entity data
    is_read BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_notifications_user_id (user_id),
    INDEX idx_notifications_read (is_read),
    INDEX idx_notifications_created_at (created_at DESC)
);

CREATE TABLE direct_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id UUID REFERENCES users(id) ON DELETE CASCADE,
    receiver_id UUID REFERENCES users(id) ON DELETE CASCADE,
    message_type VARCHAR(20) DEFAULT 'text', -- text, image, video, transaction
    content TEXT,
    media_url VARCHAR(500),
    metadata JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_direct_messages_sender (sender_id),
    INDEX idx_direct_messages_receiver (receiver_id),
    INDEX idx_direct_messages_created_at (created_at DESC)
);
```

### 10. Analytics & Reporting
```sql
CREATE TABLE user_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    metrics JSONB NOT NULL, -- {savings_total, crypto_value, engagement_score, etc.}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date),
    INDEX idx_user_analytics_user_date (user_id, date DESC)
);

CREATE TABLE platform_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20,8) NOT NULL,
    dimension JSONB, -- Breakdown by category, region, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, metric_name, dimension),
    INDEX idx_platform_analytics_date (date DESC)
);
```

## Database Relationships Diagram

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│     users       │      │ shopping_posts   │      │   transactions   │
├─────────────────┤      ├──────────────────┤      ├──────────────────┤
│ id (PK)         │◄─────┤ user_id (FK)     │      │ id (PK)          │
│ username        │      │ id (PK)          │◄─────┤ user_id (FK)     │
│ email           │      │ content_type     │      │ transaction_type │
│ crypto_wallet   │      │ media_urls[]     │      │ amount           │
│ privacy_settings│      │ product_info     │      │ crypto_amount    │
└─────────────────┘      └──────────────────┘      └──────────────────┘
         │                         │                         │
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│user_relationships│      │ post_engagement  │      │  roundup_pool    │
├─────────────────┤      ├──────────────────┤      ├──────────────────┤
│ id (PK)         │      │ id (PK)          │      │ id (PK)          │
│ follower_id (FK)│      │ post_id (FK)     │      │ user_id (FK)     │
│ following_id(FK)│      │ user_id (FK)     │      │ transaction_id(FK)│
└─────────────────┘      │ engagement_type  │      │ roundup_amount   │
         │               └──────────────────┘      └──────────────────┘
         │                         │                         │
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ savings_goals   │      │ crypto_holdings  │      │ savings_challenges│
├─────────────────┤      ├──────────────────┤      ├──────────────────┤
│ id (PK)         │      │ id (PK)          │      │ id (PK)          │
│ user_id (FK)    │      │ user_id (FK)     │      │ creator_id (FK)  │
│ goal_name       │      │ cryptocurrency   │      │ challenge_name   │
│ target_amount   │      │ amount           │      │ challenge_type   │
└─────────────────┘      └──────────────────┘      └──────────────────┘
```

## Indexing Strategy

### Primary Indexes
1. **Users**: `username`, `email`, `created_at`
2. **Shopping Posts**: `user_id`, `created_at DESC`, `content_type`
3. **Transactions**: `user_id`, `created_at DESC`, `status`
4. **Crypto Holdings**: `user_id`, `cryptocurrency`

### Composite Indexes
1. `(user_id, date)` for analytics tables
2. `(post_id, user_id, engagement_type)` for engagement uniqueness
3. `(challenge_id, user_id)` for participant uniqueness

### GIN Indexes (for array/search)
1. `shopping_posts.tags` - For hashtag search
2. `products.specifications` - For product attribute search
3. `transactions.metadata` - For flexible querying

## Partitioning Strategy

### Time-based Partitioning
```sql
-- Partition transactions by month
CREATE TABLE transactions_y2024m01 PARTITION OF transactions
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Partition analytics by day
CREATE TABLE user_analytics_y2024d001 PARTITION OF user_analytics
    FOR VALUES FROM ('2024-01-01') TO ('2024-01-02');
```

### User-based Sharding (Future Scale)
```sql
-- Shard users by hash of user_id
CREATE TABLE users_shard_0 PARTITION OF users
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
```

## Data Retention Policies

1. **User Data**: Indefinite (with soft delete)
2. **Transaction History**: 7 years (compliance)
3. **Analytics Data**: 3 years (raw), 10 years (aggregated)
4. **Notification History**: 90 days
5. **Session Data**: 30 days
6. **Audit Logs**: 10 years

## Backup & Recovery Strategy

### Daily Backups
- Full backup at 02:00 UTC
- Incremental backups every 4 hours
- Point-in-time recovery (PITR) enabled

### Retention
- Daily backups: 30 days
- Weekly backups: 12 weeks
- Monthly backups: 36 months

## Performance Targets

### Query Latency
- User feed: < 100ms (p95)
- Transaction processing: < 50ms (p95)
- Search queries: < 200ms (p95)

### Throughput
- Write capacity: 10,000 TPS
- Read capacity: 100,000 QPS
- Concurrent connections: 10,000

## Security Measures

### Encryption
- Data at rest: AES-256
- Data in transit: TLS 1.3
- Sensitive fields: Application-level encryption

### Access Control
- Row-level security (RLS) for user data
- Principle of least privilege
- Audit logging for all admin actions

### Compliance
- GDPR compliance (right to erasure)
- PCI DSS for payment data
- SOC 2 Type II certification target

## Migration Strategy

### Phase 1: Initial Schema
- Core tables (users, transactions, posts)
- Basic relationships
- MVP functionality

### Phase 2: Scale Preparation
- Partitioning implementation
- Read replicas
- Cache layer integration

### Phase 3: Advanced Features
- TimescaleDB for time-series
- Elasticsearch integration
- Real-time analytics pipeline

## Monitoring & Alerting

### Key Metrics
- Database connections
- Query performance (slow queries > 100ms)
- Replication lag
- Disk usage
- Cache hit ratio

### Alert Thresholds
- Connection pool > 80%
- Replication lag > 5 seconds
- Disk usage > 85%
- Slow queries > 1% of total

This database schema provides a robust foundation for the Instagram-inspired social shopping platform, supporting both the social engagement features and financial transaction requirements while maintaining scalability, security, and performance.