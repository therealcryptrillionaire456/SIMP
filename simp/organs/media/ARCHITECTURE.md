# KashClaw Media Grid Architecture

## Overview
Autonomous content creation, social media growth, and affiliate monetization pipeline integrated into SIMP/KashClaw ecosystem. 4-layer pipeline: Research → Content Factory → Distribution → Monetization.

## System Architecture

### 1. Agent Cluster (8 Specialized Agents)
```
┌─────────────────────────────────────────────────────────────┐
│                    KashClaw Media Grid                      │
├─────────────────────────────────────────────────────────────┤
│  Research Layer          │  Content Factory Layer          │
│  • Trend Harvester      │  • Script Agent                 │
│  • Offer Intelligence   │  • Asset Agent                  │
│                         │  • Edit/Packaging Agent         │
├─────────────────────────────────────────────────────────────┤
│  Distribution Layer     │  Monetization Layer             │
│  • Publisher Agent      │  • Analytics Agent              │
│                         │  • Landing Page Agent           │
└─────────────────────────────────────────────────────────────┘
```

### 2. Data Flow
```
Trend Research → Offer Scoring → Content Brief → Script Generation
     ↓              ↓                ↓              ↓
Asset Generation → Multi-Format Packaging → Platform Publishing
     ↓              ↓                ↓              ↓
Performance Tracking → Revenue Attribution → Optimization Loop
```

### 3. Integration Points with SIMP
- **Broker Registration**: Each media agent registers as SIMP agent
- **Intent Routing**: Media-specific intent types routed to appropriate agents
- **Dashboard Integration**: Media grid monitoring in SIMP dashboard
- **Data Ledgers**: Append-only JSONL for audit trail (content, publishing, revenue)
- **Orchestration**: n8n workflows trigger agent intents via webhooks

## Agent Specifications

### 1. Trend Harvester Agent
- **Purpose**: Scrape trending topics, affiliate offers, competitor patterns
- **Inputs**: Social platforms, affiliate networks, search trends
- **Outputs**: Content briefs with opportunity scores
- **SIMP Integration**: `media.trend_research` intent type

### 2. Offer Intelligence Agent  
- **Purpose**: Rank affiliate products by payout, conversion, compliance risk
- **Inputs**: Affiliate network APIs, product databases
- **Outputs**: Scored offer recommendations
- **SIMP Integration**: `media.offer_scoring` intent type

### 3. Script Agent
- **Purpose**: Generate hooks, scripts, CTAs, metadata for platforms
- **Inputs**: Content briefs, offer details, brand voice
- **Outputs**: Script packages (10 hooks, 3 scripts, 3 CTA variants)
- **SIMP Integration**: `media.script_generation` intent type

### 4. Asset Agent
- **Purpose**: Generate video/images/audio using AI tools (Higgsfield, Minimax)
- **Inputs**: Scripts, brand guidelines, style preferences
- **Outputs**: Raw media assets with generation metadata
- **SIMP Integration**: `media.asset_generation` intent type

### 5. Edit/Packaging Agent
- **Purpose**: Assemble multi-format versions (9:16, 1:1, 16:9) with subtitles
- **Inputs**: Raw assets, platform specifications
- **Outputs**: Platform-ready content packages
- **SIMP Integration**: `media.content_packaging` intent type

### 6. Publisher Agent
- **Purpose**: Post to social platforms with scheduling and tracking
- **Inputs**: Content packages, platform credentials, posting schedule
- **Outputs**: Published post IDs, URLs, engagement metrics
- **SIMP Integration**: `media.content_publishing` intent type

### 7. Analytics Agent
- **Purpose**: Track performance, CTR, conversions, revenue attribution
- **Inputs**: Platform analytics, affiliate network reports
- **Outputs**: Performance reports, optimization recommendations
- **SIMP Integration**: `media.performance_analytics` intent type

### 8. Landing Page Agent
- **Purpose**: Generate and update presell landing pages for offers
- **Inputs**: Offer details, compliance requirements, branding
- **Outputs**: Landing page HTML/CSS with tracking
- **SIMP Integration**: `media.landing_page_generation` intent type

## Data Models

### Core Entities
1. **Offer**: Affiliate product with payout details, compliance info
2. **ContentBrief**: Research output with topic, angle, target platforms  
3. **ScriptPackage**: Generated scripts with hooks, CTAs, metadata
4. **AssetJob**: Media generation request with tool specifications
5. **ContentPackage**: Platform-ready content with multiple formats
6. **PublishedPost**: Platform posting with tracking IDs
7. **PerformanceMetrics**: Engagement, clicks, conversions, revenue
8. **LandingPage**: Presell page with tracking and compliance

### JSONL Ledgers
- `data/media_offers.jsonl` - Affiliate offers and scoring
- `data/media_content_briefs.jsonl` - Research and planning
- `data/media_scripts.jsonl` - Generated scripts
- `data/media_assets.jsonl` - Asset generation jobs
- `data/media_published.jsonl` - Published posts
- `data/media_performance.jsonl` - Analytics and revenue
- `data/media_landing_pages.jsonl` - Landing pages

## n8n Orchestration

### Workflow Templates
1. **Daily Content Pipeline**: Trigger → Research → Scoring → Generation → Publishing
2. **Offer Discovery**: Affiliate network sync → Scoring → Landing page generation
3. **Performance Optimization**: Analytics → A/B testing → Content iteration
4. **Compliance Check**: Content review → Policy validation → Approval gates

### Webhook Integration
- SIMP broker exposes webhook endpoints for n8n
- n8n workflows trigger agent intents via HTTP POST
- Async callbacks for long-running tasks (video generation)
- Status tracking via intent ledger

## Compliance & Safety

### Platform Policies
- Social media platform terms of service
- Affiliate network disclosure requirements
- FTC guidelines for endorsements
- Platform-specific automation limits

### Safety Measures
- Human approval gates for high-risk content
- Disclosure statements on landing pages
- No fake testimonials or impersonation
- Regular compliance audits
- Account portfolio diversification

## Revenue Model

### Monetization Paths
1. **Direct Affiliate Links**: Commission on sales via social posts
2. **Presell Landing Pages**: Email capture + affiliate forwarding
3. **Sponsored Content**: Brand partnerships (future)
4. **Product Launches**: Affiliate promotions for new tools

### Tracking & Attribution
- UTM parameters for source tracking
- Click-through rate monitoring
- Conversion rate optimization
- Revenue per content asset
- Return on investment calculations

## Implementation Phases

### Phase 1: Foundation (Current)
- Architecture design and data models
- Core agent skeletons
- SIMP integration points
- n8n workflow design

### Phase 2: Core Implementation  
- Trend research and offer scoring
- Script and asset generation
- Basic publishing workflows
- Performance tracking

### Phase 3: Scaling
- Multi-platform publishing
- Advanced analytics
- Landing page system
- Optimization loops

### Phase 4: Automation
- Full pipeline automation
- A/B testing integration
- Revenue maximization
- Compliance automation

## Success Metrics
- Monthly recurring revenue from affiliate commissions
- Cost per published asset vs revenue per asset
- Content decay rate and optimal reposting schedule
- Platform growth and engagement rates
- Return on investment for content production