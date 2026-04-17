# KEEPTHECHANGE.com - Instagram-Inspired MVP Technical Documentation

## Overview
This document outlines the Minimum Viable Product (MVP) technical implementation for KEEPTHECHANGE.com as "Instagram's Crypto Twin." The MVP focuses on delivering core Instagram-like social shopping experience with basic crypto investment features.

## MVP Vision: Instagram Meets Crypto Shopping

### Core MVP Experience
1. **Instagram-Style Social Feed**: Shopping posts with likes, comments, saves
2. **Basic Social Graph**: Follow friends, see their savings
3. **Simple Shopping**: Price comparison for 5 major retailers
4. **Crypto Integration**: Manual crypto investment of savings
5. **Mobile-First Design**: Instagram-like mobile experience

### Instagram MVP Parallels
- **Feed**: Chronological shopping feed (no algorithm yet)
- **Profile**: User profile with savings stats
- **Explore**: Basic trending products
- **Notifications**: Likes and comments only
- **Camera**: Receipt scanning for price comparison

## MVP Scope

### In Scope (MVP Launch)
1. **User Experience**
   - Instagram-like mobile app (React Native)
   - Basic web interface (Next.js)
   - Warm color palette (#FF6B6B coral, #FFD166 yellow)
   - Smooth animations and transitions

2. **Social Features**
   - User profiles with avatars
   - Follow/unfollow system
   - Shopping posts with images
   - Likes and comments
   - Basic feed (chronological)

3. **Shopping Features**
   - Receipt scanning via camera
   - Price comparison (Walmart, Target, Amazon, Costco, Kroger)
   - Manual purchase confirmation
   - Savings calculation

4. **Crypto Features**
   - Connect crypto wallet (MetaMask/Coinbase)
   - Manual investment of savings
   - Basic portfolio tracking
   - Transaction history

5. **Admin Features**
   - Basic user management
   - Content moderation
   - Analytics dashboard

### Out of Scope (Post-MVP)
1. Advanced feed algorithm
2. Stories and Reels features
3. Group buying and pools
4. Automated crypto investment
5. Advanced SIMP agent integration
6. International retailers
7. Advanced search and discovery
8. Push notifications system
9. WebSocket real-time updates
10. Advanced analytics

## Technical Stack

### Frontend MVP Stack
```
┌─────────────────────────────────────────────────────────┐
│                    Mobile App (MVP)                     │
├─────────────────────────────────────────────────────────┤
│  • React Native with Expo                               │
│  • React Navigation (Stack + Tab)                       │
│  • React Native Paper (UI Components)                   │
│  • React Native Vision Camera (Receipt Scanning)        │
│  • React Native Gesture Handler (Swipe interactions)    │
│  • Zustand (State Management)                           │
│  • React Query (API Calls)                              │
│  • React Hook Form + Zod (Forms)                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    Web App (MVP)                        │
├─────────────────────────────────────────────────────────┤
│  • Next.js 14 (Pages Router - simpler)                  │
│  • Tailwind CSS (Styling)                               │
│  • Shadcn/ui (UI Components)                            │
│  • React Query (API Calls)                              │
│  • Zustand (State Management)                           │
│  • NextAuth.js (Authentication)                         │
└─────────────────────────────────────────────────────────┘
```

### Backend MVP Stack
```
┌─────────────────────────────────────────────────────────┐
│                    Backend Services                     │
├─────────────────────────────────────────────────────────┤
│  • FastAPI (Python 3.10+)                               │
│  • PostgreSQL (Single instance)                         │
│  • Redis (Optional - for caching)                       │
│  • SQLite (Development/fallback)                        │
│  • Docker (Containerization)                            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    External Services                    │
├─────────────────────────────────────────────────────────┤
│  • Supabase (Auth + Database)                           │
│  • Cloudinary (Image hosting)                           │
│  • SendGrid (Email)                                     │
│  • Retailer APIs (5 major retailers)                    │
│  • CoinGecko API (Crypto prices)                        │
└─────────────────────────────────────────────────────────┘
```

## Database Schema (MVP)

### PostgreSQL Tables

```sql
-- Users (Instagram-style profiles)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    profile_picture_url TEXT,
    bio TEXT,
    crypto_wallet_address VARCHAR(255),
    total_savings DECIMAL(10,2) DEFAULT 0,
    total_crypto_invested DECIMAL(18,8) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Social Graph (Instagram follow system)
CREATE TABLE followers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id UUID REFERENCES users(id) ON DELETE CASCADE,
    following_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(follower_id, following_id)
);

-- Shopping Posts (Instagram-style posts)
CREATE TABLE shopping_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200),
    description TEXT,
    images TEXT[] NOT NULL, -- Array of image URLs
    original_price DECIMAL(10,2) NOT NULL,
    saved_price DECIMAL(10,2) NOT NULL,
    savings_amount DECIMAL(10,2) GENERATED ALWAYS AS (original_price - saved_price) STORED,
    crypto_invested DECIMAL(18,8),
    retailer VARCHAR(100),
    location VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Engagement (Instagram-style interactions)
CREATE TABLE likes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES shopping_posts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(post_id, user_id)
);

CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES shopping_posts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Shopping Lists (Basic functionality)
CREATE TABLE shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Price Comparisons (5 retailers)
CREATE TABLE price_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name VARCHAR(255) NOT NULL,
    retailer VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    in_stock BOOLEAN DEFAULT TRUE,
    comparison_date TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_name, retailer)
);

-- Crypto Transactions (Basic)
CREATE TABLE crypto_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    amount_usd DECIMAL(10,2) NOT NULL,
    crypto_amount DECIMAL(18,8) NOT NULL,
    crypto_asset VARCHAR(10) DEFAULT 'BTC',
    exchange_rate DECIMAL(18,8) NOT NULL,
    transaction_hash VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## API Endpoints (MVP)

### Authentication
```
POST   /api/auth/register     # User registration
POST   /api/auth/login        # User login
POST   /api/auth/logout       # User logout
GET    /api/auth/me           # Current user info
POST   /api/auth/refresh      # Refresh token
```

### Users
```
GET    /api/users             # List users (for follow suggestions)
GET    /api/users/:id         # Get user profile
PUT    /api/users/:id         # Update profile
GET    /api/users/:id/posts   # Get user's shopping posts
GET    /api/users/:id/followers   # Get followers
GET    /api/users/:id/following   # Get following
POST   /api/users/:id/follow      # Follow user
DELETE /api/users/:id/follow      # Unfollow user
```

### Shopping Posts (Instagram-style)
```
GET    /api/posts             # Get feed (chronological)
GET    /api/posts/explore     # Explore trending posts
POST   /api/posts             # Create shopping post
GET    /api/posts/:id         # Get single post
PUT    /api/posts/:id         # Update post
DELETE /api/posts/:id         # Delete post
POST   /api/posts/:id/like    # Like post
DELETE /api/posts/:id/like    # Unlike post
GET    /api/posts/:id/likes   # Get post likes
POST   /api/posts/:id/comments    # Add comment
GET    /api/posts/:id/comments    # Get comments
DELETE /api/posts/:id/comments/:comment_id  # Delete comment
```

### Shopping & Price Comparison
```
POST   /api/shopping/scan     # Scan receipt (image upload)
GET    /api/shopping/compare  # Compare prices for product
POST   /api/shopping/lists    # Create shopping list
GET    /api/shopping/lists    # Get user's lists
GET    /api/shopping/lists/:id    # Get list details
POST   /api/shopping/purchase     # Manual purchase confirmation
```

### Crypto Investment
```
GET    /api/crypto/balance    # Get user's crypto balance
POST   /api/crypto/invest     # Manual investment
GET    /api/crypto/transactions   # Transaction history
GET    /api/crypto/prices     # Current crypto prices
POST   /api/crypto/withdraw   # Withdraw crypto (MVP: manual approval)
```

## Frontend Components (MVP)

### Mobile App Screens
1. **Login/Register Screen**
   - Instagram-style login flow
   - Social login options (Google, Apple)
   - Warm color scheme

2. **Main Tab Navigator**
   - **Home Feed**: Chronological shopping posts
   - **Explore**: Trending products and savings
   - **Camera**: Receipt scanning (center tab)
   - **Notifications**: Likes and comments
   - **Profile**: User profile and stats

3. **Home Feed Screen**
   - Instagram-style card layout
   - User avatar, username, location
   - Product images (swipeable)
   - Price comparison display
   - Like, comment, save buttons
   - Savings amount prominently displayed

4. **Camera Screen**
   - Full-screen camera view
   - Receipt scanning mode
   - Flash toggle
   - Gallery upload option
   - Simple OCR preview

5. **Profile Screen**
   - Profile picture and bio
   - Savings statistics
   - Crypto portfolio summary
   - User's shopping posts grid
   - Followers/following counts

### Web App Pages
1. **Landing Page**
   - Value proposition
   - Instagram-style screenshot gallery
   - Call-to-action for app download

2. **Dashboard**
   - Simplified feed view
   - Basic shopping functionality
   - Profile management

3. **Admin Dashboard**
   - User management table
   - Content moderation tools
   - Basic analytics

## Backend Services (MVP)

### 1. Authentication Service
```python
# FastAPI implementation
@app.post("/api/auth/register")
async def register(user_data: UserCreate):
    # Instagram-style username validation
    # Email verification
    # JWT token generation
    pass

@app.post("/api/auth/login")
async def login(credentials: UserLogin):
    # Password validation
    # JWT token generation
    # Session management
    pass
```

### 2. Feed Service
```python
class FeedService:
    def get_feed(self, user_id: str, page: int = 1, limit: int = 20):
        """Get chronological feed for user"""
        # 1. Get users that this user follows
        following = self.get_following(user_id)
        
        # 2. Get their posts (chronological)
        posts = self.get_posts_by_users(following, page, limit)
        
        # 3. Add some explore posts (20% of feed)
        if page == 1:
            explore_posts = self.get_explore_posts(limit=4)
            posts = self.mix_feed(posts, explore_posts)
        
        return posts
```

### 3. Shopping Service
```python
class ShoppingService:
    async def scan_receipt(self, image_file) -> ReceiptScanResult:
        """Scan receipt and extract items"""
        # 1. Upload image to Cloudinary
        # 2. Call OCR service (Tesseract/Google Vision)
        # 3. Parse items and prices
        # 4. Compare prices with retailers
        # 5. Return savings calculation
        pass
    
    async def compare_prices(self, product_name: str) -> List[PriceComparison]:
        """Compare prices across 5 retailers"""
        retailers = ["Walmart", "Target", "Amazon", "Costco", "Kroger"]
        comparisons = []
        
        for retailer in retailers:
            price = await self.get_retailer_price(retailer, product_name)
            comparisons.append(PriceComparison(
                retailer=retailer,
                price=price,
                in_stock=True  # Simplified for MVP
            ))
        
        return sorted(comparisons, key=lambda x: x.price)
```

### 4. Crypto Service
```python
class CryptoService:
    async def invest_savings(self, user_id: str, amount_usd: float) -> InvestmentResult:
        """Manual investment of savings into crypto"""
        # 1. Validate user has sufficient savings
        # 2. Get current crypto price (CoinGecko)
        # 3. Calculate crypto amount
        # 4. Create transaction record
        # 5. Return investment result
        
        # MVP: Manual confirmation required
        return InvestmentResult(
            success=True,
            amount_usd=amount_usd,
            crypto_amount=amount_usd / crypto_price,
            crypto_asset="BTC",
            exchange_rate=crypto_price,
            status="pending_confirmation"
        )
```

## Infrastructure (MVP)

### Deployment Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Production (MVP)                     │
├─────────────────────────────────────────────────────────┤
│  • Frontend: Vercel (Web) + Expo (Mobile)              │
│  • Backend: Railway/Render (FastAPI)                   │
│  • Database: Supabase (PostgreSQL)                     │
│  • Storage: Cloudinary (Images)                        │
│  • Email: SendGrid                                     │
│  • Monitoring: Basic logging to console                │
└─────────────────────────────────────────────────────────┘
```

### Development Environment
```
┌─────────────────────────────────────────────────────────┐
│                    Development                          │
├─────────────────────────────────────────────────────────┤
│  • Local: Docker Compose for services                  │
│  • Database: PostgreSQL in Docker                      │
│  • Redis: Optional, for caching                        │
│  • Testing: pytest for backend, Vitest for frontend    │
│  • CI/CD: GitHub Actions (basic)                       │
└─────────────────────────────────────────────────────────┘
```

## MVP User Flow

### 1. Onboarding Flow
```
Open App → Welcome Screen → Sign Up → Email Verification → 
Profile Setup → Connect Social (optional) → Tutorial → Home Feed
```

### 2. Shopping & Posting Flow
```
Home Feed → Tap Camera → Scan Receipt → View Savings → 
Create Post → Add Caption → Share to Feed → Friends Engage
```

### 3. Investment Flow
```
Profile → View Savings → Tap "Invest" → Enter Amount → 
Confirm Investment → View Transaction → Portfolio Updated
```

### 4. Social Flow
```
Home Feed → See Friend's Post → Like/Comment → 
Visit Profile → Follow → See More Posts
```

## Performance Requirements (MVP)

### Frontend Performance
- **App Launch**: < 3 seconds
- **Feed Load**: < 2 seconds
- **Image Load**: < 1 second (optimized)
- **Camera Open**: < 2 seconds

### Backend Performance
- **API Response**: < 200ms p95
- **Database Queries**: < 50ms
- **OCR Processing**: < 5 seconds
- **Price Comparison**: < 3 seconds

### Scalability (MVP)
- **Concurrent Users**: 1,000
- **Daily Active Users**: 10,000
- **Posts per Day**: 5,000
- **Images per Day**: 10,000

## Security (MVP)

### Authentication
- JWT tokens with 24-hour expiry
- Refresh tokens with 7-day expiry
- Password hashing (bcrypt)
- Email verification required

### Data Protection
- HTTPS everywhere
- Database encryption at rest
- Image uploads sanitized
- SQL injection prevention

### Privacy
- User data not shared with third parties
- Clear privacy policy
- GDPR compliance basics
- User data deletion option

## Testing Strategy (MVP)

### Unit Tests
- Backend: pytest (80% coverage)
- Frontend: Vitest (70% coverage)
- Mobile: Jest (60% coverage)

### Integration Tests
- API endpoints
- Database operations
- External service mocks

### Manual Testing
- User flows
- UI/UX testing
- Cross-device testing
- Performance testing

## Launch Checklist

### Technical Launch
- [ ] Backend deployed and tested
- [ ] Database migrated and seeded
- [ ] Frontend deployed
- [ ] Mobile apps submitted to stores
- [ ] DNS configured
- [ ] SSL certificates installed
- [ ] Monitoring set up
- [ ] Backup system configured

### Content Launch
- [ ] Sample shopping posts created
- [ ] Test users onboarded
- [ ] Tutorial content ready
- [ ] Help documentation written
- [ ] Privacy policy and terms

### Marketing Launch
- [ ] App store listings optimized
- [ ] Social media accounts created
- [ ] Launch announcement prepared
- [ ] Early access program ready
- [ ] Feedback collection system

## Post-MVP Roadmap

### Phase 2 (3-6 months)
1. Advanced feed algorithm
2. Stories feature
3. Group buying
4. Automated crypto investment
5. 10 more retailers

### Phase 3 (6-12 months)
1. SIMP agent integration
2. Advanced social features
3. International expansion
4. Advanced analytics
5. WebSocket real-time

### Phase 4 (12+ months)
1. Full SIMP ecosystem
2. DeFi integration
3. AI personalization
4. Enterprise features
5. Global scale

## Success Metrics (MVP)

### Engagement Metrics
- **DAU/MAU**: > 20%
- **Posts per User**: > 2 per week
- **Likes per Post**: > 3
- **Comments per Post**: > 0.5
- **Follows per User**: > 5

### Business Metrics
- **User Retention**: > 40% Week 1
- **Savings Generated**: > $10 per user
- **Crypto Invested**: > $5 per user
- **App Store Rating**: > 4.0 stars

### Technical Metrics
- **App Crashes**: < 1% of sessions
- **API Uptime**: > 99%
- **Error Rate**: < 1%
- **Load Time**: Meets targets

## Conclusion

The KEEPTHECHANGE.com MVP delivers an Instagram-inspired social shopping experience with basic crypto investment features. By focusing on core functionality with beautiful, intuitive design, we create a foundation for rapid user adoption and future feature expansion.

The warm color palette, smooth animations, and Instagram-like interactions create an engaging experience that makes saving money and investing in crypto feel social, rewarding, and fun.