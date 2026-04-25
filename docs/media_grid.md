# Media Grid — KashClaw Content Production Pipeline

## Overview

The Media Grid is an autonomous content creation and affiliate monetization pipeline. It discovers trending topics, generates scripts, produces assets, publishes to social platforms, and tracks performance — all routed through the SIMP broker.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    SIMP Broker                        │
│  (intent routing via MEDIA_INTENT_TYPES)              │
└──────────┬────────────────────────────────┬───────────┘
           │                                │
     media.* intents                  agent heartbeats
           │                                │
┌──────────▼────────────────────────────────▼──────────┐
│              MediaGridOrchestrator                    │
│  • Workflow scheduling ──── ──── circuit breaker     │
│  • Error recovery  ──── ──── budget tracking        │
│  • Health monitoring  ── ── metrics collection      │
│  • Graceful shutdown                                │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──┘
   │      │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼
 Trend  Script  Asset  Edit   Publish Analytics LP   Offer
 Agent  Agent   Agent  Agent  Agent   Agent    Agent  Intel
```

## Agents

| Agent | Description | Source |
|-------|-------------|--------|
| TrendHarvester | Scrapes trends from social platforms | `agents/trend_harvester.py` |
| ScriptAgent | Generates video scripts | `agents/script_agent.py` |
| AssetAgent | Creates video/assets via generation tools | `agents/asset_agent.py` |
| EditPackagingAgent | Packages edits for platforms | `agents/edit_packaging_agent.py` |
| PublisherAgent | Publishes to TikTok, YT Shorts, Reels, X | `agents/publisher_agent.py` |
| AnalyticsAgent | Tracks performance metrics | `agents/analytics_agent.py` |
| LandingPageAgent | Builds affiliate landing pages | `agents/landing_page_agent.py` |
| OfferIntelligenceAgent | Scores affiliate offers | `agents/offer_intelligence_agent.py` |
| SimpNewsAgent | Generates news content | `agents/simp_news_agent.py` |

## Intent Types (SIMP Broker)

All intents use the `media.*` namespace:

| Intent | Handler | Returns |
|--------|---------|---------|
| `media.trend_research` | `_execute_trend_research` | TrendBrief |
| `media.create_content` | `_execute_content_creation` | PublicationResult |
| `media.script_generation` | `_execute_script_generation` | Script |
| `media.asset_generation` | `_execute_asset_generation` | GeneratedAsset |
| `media.publish_content` | `_execute_publishing` | PublicationResult |
| `media.performance_analysis` | `_execute_performance_analysis` | PerformanceReport |
| `media.optimization` | `_execute_optimization` | OptimizationSuggestion |
| `media.landing_page_generation` | `_execute_landing_page` | LandingPage |
| `media.news_generation` | `_execute_news_generation` | NewsArticle |
| `media.offer_scoring` | `_execute_offer_scoring` | ScoredOffer |
| `media.content_plan` | `_execute_full_pipeline` | FullPipelineResult |

## Configuration

### Quick Start

```bash
# Copy default config
cp config/media_grid.env.example .env

# Or use all defaults (development mode)
python -m simp.organs.media.orchestration
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDIA_ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `MEDIA_DAILY_BUDGET` | `50.0` | Max daily spend (USD) |
| `MEDIA_MAX_CONTENT_PER_DAY` | `20` | Max content items per day |
| `MEDIA_RATE_LIMIT_CALLS_PER_MINUTE` | `10` | API rate limit per agent |
| `MEDIA_SIMP_BROKER_URL` | `http://127.0.0.1:5555` | SIMP broker endpoint |
| `MEDIA_BUDGET_ALERT_THRESHOLD` | `0.8` | Fire alert at 80% spend |

## Error Handling

### Circuit Breaker
- **State**: CLOSED → OPEN (5 consecutive failures) → HALF_OPEN (after 60s)
- **Reset**: CLOSED on next success in HALF_OPEN state
- **Per-agent**: Each agent has its own circuit breaker instance

### Retry Policy
- Exponential backoff: 1s → 2s → 4s → 8s → 16s (max 5 retries)
- Applied to: `publish_content()`, external API calls
- Configurable via agent constructor

### Health Monitoring
- Heartbeat check every 30 seconds
- Agent marked stale after 5 minutes without heartbeat
- Auto-restart attempts for stale agents
- Full health endpoint: `orchestrator.check_health()`

## Budget & Rate Limiting

### DailyBudgetTracker
- Tracks spend per platform
- Enforces `daily_budget` and `max_cost_per_content`
- `max_content_per_day` limit per platform
- Budget alert at configurable threshold (default 80%)

### RateLimiter (Token Bucket)
- Configurable `max_calls` per `window_seconds`
- Thread-safe with `threading.Lock`
- `@rate_limit` decorator for agent methods
- Example: 10 calls/minute per agent

## Performance

### Async Batching
- `score_batch()` processes offers in parallel with `asyncio.gather`
- Configurable batch size

### LRU Cache
- 5-minute TTL for mock data lookups
- Thread-safe with `threading.Lock`

### Profiling
```bash
python scripts/manual_checks/profile_media.py
```

## Security

### UTM Sanitization
- Allowlist: `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`
- Rejects: `javascript:`, `data:`, `vbscript:` protocols
- Rejects: HTML, control characters, quotes, backticks
- Value length limit: 100 chars

### Affiliate URL Validation
- HTTPS-only (rejects HTTP schemes)
- Max 2000 chars
- Rejects: `javascript:`, `data:`, `vbscript:`

### Input Validation
- ContentBrief title: max 200 chars, no HTML
- ContentBrief description: max 2000 chars, no HTML
- AffiliateOffer: commission 0-100%, HTTPS links only

## Metrics

### Prometheus-Compatible Metrics
```python
media_workflows_total         # Workflow counter
media_content_published_total # Published content counter
media_errors_total            # Error counter
media_agent_uptime_seconds    # Per-agent uptime
media_revenue_cents           # Revenue in cents
```

### Diagnostics Script
```bash
python scripts/diagnostics/media_metrics.py
```

## Testing

```bash
# Run all media tests
python3.10 -m pytest tests/test_media_intent_routing.py tests/test_media_budget_guards.py tests/test_media_security.py -v

# 83 tests total:
# - 12 intent routing
# - 24 budget guards
# - 30 security (UTM, affiliate URLs, validation, fuzzing)
# - 17 existing unit tests
```

## Development

### Adding a New Agent
1. Create agent in `agents/` following `BaseMediaAgent` pattern
2. Add enable flag in `config.py` (bool field)
3. Add to `_compute_enabled_agents()` in `config.py`
4. Add intent handler to `handle_media_intent()` in `orchestration.py`
5. Register in `MEDIA_INTENT_TYPES` in `__init__.py`
6. Add test coverage

### Adding a New Intent
1. Add entry to `MEDIA_INTENT_TYPES` in `__init__.py`
2. Add handler method to `MediaGridOrchestrator`
3. Add route mapping in `handle_media_intent()`
4. Wire through `MediaSignalRouter` if external routing needed

## Data Storage

```
data/media/
├── predictions/     # Engagement score predictions (JSONL)
├── content_log.jsonl       # Published content records
├── spend_ledger.jsonl      # Spend tracking records
├── agent_restarts.jsonl    # Agent recovery log (Tranche 9)
├── metrics.jsonl           # Metrics snapshots
└── recovery_log.jsonl      # Recovery attempts
```
