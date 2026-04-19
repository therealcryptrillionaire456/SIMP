# KEEPTHECHANGE.com - Scoring Engine Specification
## Instagram's Crypto Twin

## Overview
This document specifies the scoring engine for KEEPTHECHANGE.com, a sophisticated multi-dimensional scoring system that evaluates users, transactions, merchants, and investment opportunities. The engine powers personalized recommendations, risk assessment, social ranking, and automated decision-making across the platform.

## Scoring Philosophy

### Core Principles
1. **Transparency**: Users understand how scores are calculated
2. **Fairness**: No bias based on protected characteristics
3. **Adaptability**: Scores evolve with user behavior
4. **Privacy**: Personal data protected, aggregated where possible
5. **Utility**: Scores drive tangible user benefits

### Scoring Dimensions
- **User Trust Score**: Overall platform trustworthiness
- **Savings Intelligence Score**: Smart shopping and saving behavior
- **Social Influence Score**: Community engagement and impact
- **Investment Aptitude Score**: Crypto investment sophistication
- **Merchant Quality Score**: Merchant reliability and value
- **Transaction Risk Score**: Fraud and risk assessment

## User Trust Score (UTS)

### Purpose
Evaluate user reliability, activity quality, and platform trustworthiness.

### Components & Weights
```python
class UserTrustScore:
    # Base Components (Total: 100 points)
    VERIFICATION_LEVEL = 20      # KYC, MFA, email/phone verified
    ACCOUNT_AGE = 15            # Account longevity
    ACTIVITY_CONSISTENCY = 20   # Regular, predictable usage
    COMPLIANCE_HISTORY = 25     # No policy violations
    SECURITY_PRACTICES = 20     # Strong password, MFA, device management
    
    # Bonus Components (Up to +50 points)
    REFERRAL_QUALITY = 10       # Quality of referred users
    COMMUNITY_MODERATION = 15   # Helpful reporting, moderation
    BUG_REPORTS = 10            # Quality bug reports
    FEEDBACK_CONTRIBUTION = 15  # Product feedback, surveys
```

### Calculation Algorithm
```python
def calculate_user_trust_score(user):
    base_score = 0
    
    # Verification Level (0-20)
    verification_points = 0
    if user.email_verified: verification_points += 5
    if user.phone_verified: verification_points += 5
    if user.identity_verified: verification_points += 10
    base_score += min(verification_points, 20)
    
    # Account Age (0-15)
    account_age_days = (datetime.now() - user.created_at).days
    age_score = min(account_age_days / 365 * 15, 15)  # Max at 1 year
    base_score += age_score
    
    # Activity Consistency (0-20)
    consistency_score = calculate_activity_consistency(user.activity_history)
    base_score += consistency_score
    
    # Compliance History (0-25)
    violations = user.compliance_violations.count()
    compliance_score = max(25 - (violations * 5), 0)
    base_score += compliance_score
    
    # Security Practices (0-20)
    security_score = 0
    if user.has_strong_password: security_score += 5
    if user.mfa_enabled: security_score += 10
    if user.device_management_enabled: security_score += 5
    base_score += security_score
    
    # Bonus Points (0-50)
    bonus_score = calculate_bonus_points(user)
    
    total_score = min(base_score + bonus_score, 150)  # Cap at 150
    
    return {
        "score": total_score,
        "tier": determine_trust_tier(total_score),
        "breakdown": {
            "base": base_score,
            "bonus": bonus_score,
            "components": {
                "verification": verification_points,
                "account_age": age_score,
                "consistency": consistency_score,
                "compliance": compliance_score,
                "security": security_score
            }
        }
    }
```

### Trust Tiers
```python
TRUST_TIERS = {
    "PLATINUM": {"min": 120, "benefits": ["Unlimited transactions", "Priority support", "Early access"]},
    "GOLD": {"min": 90, "benefits": ["Higher limits", "Reduced fees", "Premium features"]},
    "SILVER": {"min": 60, "benefits": ["Standard limits", "Basic features"]},
    "BRONZE": {"min": 30, "benefits": ["Reduced limits", "Basic access"]},
    "NEW": {"min": 0, "benefits": ["Introductory limits"]}
}
```

## Savings Intelligence Score (SIS)

### Purpose
Measure user's smart shopping, saving habits, and financial optimization.

### Components & Weights
```python
class SavingsIntelligenceScore:
    # Core Savings Behavior (Total: 60 points)
    ROUNDUP_FREQUENCY = 15      # Regular roundup usage
    SAVINGS_RATE = 20           # Percentage of spending saved
    GOAL_ACHIEVEMENT = 15       # Success in reaching savings goals
    PRICE_COMPARISON = 10       # Using price comparison features
    
    # Advanced Optimization (Total: 40 points)
    COUPON_USAGE = 10           # Digital coupon redemption
    CASHBACK_OPTIMIZATION = 15  # Maximizing cashback offers
    TIMING_INTELLIGENCE = 10    # Buying at optimal times
    BULK_OPTIMIZATION = 5       # Smart bulk purchasing
    
    # Bonus: Challenge Participation (Up to +30 points)
    CHALLENGE_COMPLETION = 15   # Completing savings challenges
    CHALLENGE_PERFORMANCE = 15  # High performance in challenges
```

### Calculation Algorithm
```python
def calculate_savings_intelligence(user, transactions, goals, challenges):
    score = 0
    
    # Roundup Frequency (0-15)
    roundup_transactions = [t for t in transactions if t.has_roundup]
    frequency_score = min(len(roundup_transactions) / 10 * 15, 15)
    score += frequency_score
    
    # Savings Rate (0-20)
    total_spent = sum(t.amount for t in transactions)
    total_saved = sum(t.roundup_amount for t in roundup_transactions)
    savings_rate = (total_saved / total_spent * 100) if total_spent > 0 else 0
    rate_score = min(savings_rate * 0.2, 20)  # 1% = 0.2 points
    score += rate_score
    
    # Goal Achievement (0-15)
    completed_goals = [g for g in goals if g.is_completed]
    achievement_score = min(len(completed_goals) * 3, 15)
    score += achievement_score
    
    # Price Comparison (0-10)
    comparison_usage = user.price_comparison_searches
    comparison_score = min(comparison_usage * 0.5, 10)
    score += comparison_score
    
    # Advanced Optimization (0-40)
    advanced_score = calculate_advanced_optimization(user, transactions)
    score += advanced_score
    
    # Challenge Bonus (0-30)
    challenge_bonus = calculate_challenge_bonus(challenges)
    score += challenge_bonus
    
    total_score = min(score, 130)  # Cap at 130
    
    return {
        "score": total_score,
        "level": determine_savings_level(total_score),
        "monthly_savings": total_saved,
        "savings_rate_percentage": savings_rate
    }
```

### Savings Intelligence Levels
```python
SAVINGS_LEVELS = {
    "SAVINGS_GURU": {"min": 100, "icon": "👑", "badge": "Savings Guru"},
    "SMART_SHOPPER": {"min": 75, "icon": "💡", "badge": "Smart Shopper"},
    "ACTIVE_SAVER": {"min": 50, "icon": "💰", "badge": "Active Saver"},
    "CASUAL_SAVER": {"min": 25, "icon": "🛒", "badge": "Casual Saver"},
    "NEW_SAVER": {"min": 0, "icon": "🌱", "badge": "New Saver"}
}
```

## Social Influence Score (SISocial)

### Purpose
Measure user's social engagement, content quality, and community impact.

### Components & Weights
```python
class SocialInfluenceScore:
    # Content Quality (Total: 40 points)
    POST_QUALITY = 15           # Engagement rate, completeness
    CONTENT_FREQUENCY = 10      # Regular posting
    CONTENT_VARIETY = 10        # Different content types
    HASHTAG_RELEVANCE = 5       # Relevant hashtag usage
    
    # Engagement Metrics (Total: 35 points)
    FOLLOWER_GROWTH = 10        # Organic follower growth
    ENGAGEMENT_RATE = 15        # Likes, comments, saves per post
    COMMUNITY_INTERACTION = 10  # Commenting on others' posts
    
    # Community Impact (Total: 25 points)
    CHALLENGE_CREATION = 10     # Creating successful challenges
    REFERRAL_IMPACT = 10        # Quality user referrals
    COMMUNITY_HELP = 5          # Helping other users
    
    # Viral Bonus (Up to +20 points)
    VIRAL_POSTS = 10            # High-engagement posts
    FEATURED_CONTENT = 10       # Platform-featured content
```

### Calculation Algorithm
```python
def calculate_social_influence(user, posts, followers, engagement):
    score = 0
    
    # Content Quality (0-40)
    quality_score = calculate_content_quality(posts)
    score += quality_score
    
    # Engagement Metrics (0-35)
    engagement_score = calculate_engagement_metrics(followers, engagement)
    score += engagement_score
    
    # Community Impact (0-25)
    impact_score = calculate_community_impact(user.community_actions)
    score += impact_score
    
    # Viral Bonus (0-20)
    viral_bonus = calculate_viral_bonus(posts)
    score += viral_bonus
    
    total_score = min(score, 120)  # Cap at 120
    
    return {
        "score": total_score,
        "influence_tier": determine_influence_tier(total_score),
        "engagement_rate": calculate_engagement_rate(posts),
        "follower_growth": calculate_growth_rate(followers)
    }
```

### Influence Tiers
```python
INFLUENCE_TIERS = {
    "INFLUENCER": {"min": 90, "badge": "💎 Influencer", "perks": ["Verified badge", "Creator fund"]},
    "TREND_SETTER": {"min": 70, "badge": "🔥 Trend Setter", "perks": ["Early features", "Priority visibility"]},
    "COMMUNITY_LEADER": {"min": 50, "badge": "🌟 Community Leader", "perks": ["Challenge creation", "Moderation tools"]},
    "ACTIVE_MEMBER": {"min": 30, "badge": "👍 Active Member", "perks": ["Standard features"]},
    "NEW_MEMBER": {"min": 0, "badge": "👋 New Member", "perks": ["Basic features"]}
}
```

## Investment Aptitude Score (IAS)

### Purpose
Assess user's crypto investment knowledge, risk management, and portfolio performance.

### Components & Weights
```python
class InvestmentAptitudeScore:
    # Knowledge & Education (Total: 30 points)
    CRYPTO_KNOWLEDGE = 15       # Quiz performance, educational content
    RISK_UNDERSTANDING = 10     # Risk assessment accuracy
    MARKET_AWARENESS = 5        # Following market trends
    
    # Portfolio Management (Total: 40 points)
    DIVERSIFICATION = 15        # Portfolio diversification
    REBALANCING_FREQUENCY = 10  # Regular portfolio rebalancing
    RISK_ADHERENCE = 10         # Adherence to risk profile
    TAX_EFFICIENCY = 5          # Tax-loss harvesting, optimization
    
    # Performance Metrics (Total: 30 points)
    RISK_ADJUSTED_RETURNS = 15  # Sharpe ratio, Sortino ratio
    CONSISTENCY = 10            # Consistent positive returns
    BEHAVIORAL_SCORE = 5        # Avoiding emotional decisions
    
    # Advanced Strategies (Up to +20 points)
    ADVANCED_STRATEGIES = 10    # Using advanced features
    QUANTUMARB_PARTICIPATION = 10 # Participating in QuantumArb
```

### Calculation Algorithm
```python
def calculate_investment_aptitude(user, portfolio, transactions, quiz_results):
    score = 0
    
    # Knowledge & Education (0-30)
    knowledge_score = calculate_knowledge_score(quiz_results, user.education_completion)
    score += knowledge_score
    
    # Portfolio Management (0-40)
    management_score = calculate_portfolio_management(portfolio, transactions)
    score += management_score
    
    # Performance Metrics (0-30)
    performance_score = calculate_performance_metrics(portfolio.performance)
    score += performance_score
    
    # Advanced Strategies (0-20)
    advanced_score = calculate_advanced_strategies(user.investment_behavior)
    score += advanced_score
    
    total_score = min(score, 120)  # Cap at 120
    
    return {
        "score": total_score,
        "aptitude_level": determine_aptitude_level(total_score),
        "risk_profile": portfolio.risk_profile,
        "performance_metrics": portfolio.performance_metrics
    }
```

### Aptitude Levels
```python
APTITUDE_LEVELS = {
    "CRYPTO_EXPERT": {"min": 90, "badge": "🚀 Crypto Expert", "access": ["Advanced strategies", "QuantumArb priority"]},
    "SOPHISTICATED_INVESTOR": {"min": 70, "badge": "📈 Sophisticated Investor", "access": ["Auto-rebalancing", "Tax optimization"]},
    "GROWING_INVESTOR": {"min": 50, "badge": "🌱 Growing Investor", "access": ["Diversification tools", "Educational content"]},
    "LEARNING_INVESTOR": {"min": 30, "badge": "📚 Learning Investor", "access": ["Basic features", "Risk assessment"]},
    "BEGINNER": {"min": 0, "badge": "🎯 Beginner", "access": ["Introductory features"]}
}
```

## Merchant Quality Score (MQS)

### Purpose
Evaluate merchant reliability, pricing competitiveness, and user satisfaction.

### Components & Weights
```python
class MerchantQualityScore:
    # Reliability (Total: 40 points)
    TRANSACTION_SUCCESS = 15    # Successful transaction rate
    RETURN_RATE = 10            # Low return/refund rate
    FRAUD_INCIDENTS = 15        # Low fraud incidents
    
    # Pricing & Value (Total: 35 points)
    PRICE_COMPETITIVENESS = 15  # Competitive pricing
    DISCOUNT_FREQUENCY = 10     # Regular discounts/sales
    CASHBACK_OFFERS = 10        # Cashback availability
    
    # User Experience (Total: 25 points)
    USER_RATINGS = 15           # Average user rating
    SUPPORT_QUALITY = 10        # Customer support quality
    
    # Partnership Value (Up to +20 points)
    AFFILIATE_PERFORMANCE = 10  # Affiliate program performance
    PLATFORM_INTEGRATION = 10   # Integration quality
```

### Calculation Algorithm
```python
def calculate_merchant_quality(merchant, transactions, reviews):
    score = 0
    
    # Reliability (0-40)
    reliability_score = calculate_reliability_metrics(transactions)
    score += reliability_score
    
    # Pricing & Value (0-35)
    pricing_score = calculate_pricing_metrics(merchant.pricing_data)
    score += pricing_score
    
    # User Experience (0-25)
    experience_score = calculate_experience_metrics(reviews)
    score += experience_score
    
    # Partnership Value (0-20)
    partnership_score = calculate_partnership_value(merchant.affiliate_data)
    score += partnership_score
    
    total_score = min(score, 120)  # Cap at 120
    
    return {
        "score": total_score,
        "quality_tier": determine_quality_tier(total_score),
        "verification_status": merchant.verification_status,
        "user_rating": calculate_average_rating(reviews)
    }
```

### Merchant Quality Tiers
```python
MERCHANT_TIERS = {
    "PLATINUM_PARTNER": {"min": 90, "badge": "🏆 Platinum Partner", "visibility": ["Featured", "Priority placement"]},
    "GOLD_PARTNER": {"min": 75, "badge": "⭐ Gold Partner", "visibility": ["Highlighted", "Category priority"]},
    "VERIFIED_MERCHANT": {"min": 60, "badge": "✓ Verified", "visibility": ["Standard placement"]},
    "STANDARD_MERCHANT": {"min": 40, "badge": "🛒 Standard", "visibility": ["Basic placement"]},
    "NEW_MERCHANT": {"min": 0, "badge": "🆕 New", "visibility": ["Limited placement"]}
}
```

## Transaction Risk Score (TRS)

### Purpose
Assess transaction risk for fraud detection and security.

### Components & Weights
```python
class TransactionRiskScore:
    # User Behavior (Total: 35 points)
    USER_TRUST_SCORE = 15       # User's overall trust score
    DEVICE_TRUST = 10           # Device reputation
    LOCATION_CONSISTENCY = 10   # Location pattern consistency
    
    # Transaction Patterns (Total: 40 points)
    AMOUNT_ANOMALY = 15         # Unusual transaction amount
    FREQUENCY_ANOMALY = 10      # Unusual transaction frequency
    TIME_ANOMALY = 10           # Unusual transaction time
    MERCHANT_RISK = 5           # Merchant risk profile
    
    # Payment Method (Total: 25 points)
    PAYMENT_METHOD_AGE = 10     # Payment method age
    PAYMENT_SUCCESS_RATE = 10   # Historical success rate
    VERIFICATION_LEVEL = 5      # Payment verification
    
    # Red Flags (Subtract up to -50 points)
    MULTIPLE_FAILURES = -20     # Multiple failed attempts
    SUSPICIOUS_PATTERNS = -20   # Known fraud patterns
    HIGH_RISK_COUNTRY = -10     # High-risk country
```

### Calculation Algorithm
```python
def calculate_transaction_risk(transaction, user, historical_data):
    risk_score = 100  # Start with perfect score
    
    # User Behavior (0-35 impact)
    user_impact = calculate_user_behavior_impact(user, transaction)
    risk_score -= (35 - user_impact)  # Lower impact = higher risk
    
    # Transaction Patterns (0-40 impact)
    pattern_impact = calculate_pattern_impact(transaction, historical_data)
    risk_score -= (40 - pattern_impact)
    
    # Payment Method (0-25 impact)
    payment_impact = calculate_payment_impact(transaction.payment_method)
    risk_score -= (25 - payment_impact)
    
    # Red Flags (up to -50)
    red_flags = detect_red_flags(transaction, user)
    risk_score += red_flags  # Negative values reduce score
    
    # Ensure score is between 0-100
    risk_score = max(0, min(risk_score, 100))
    
    return {
        "score": risk_score,
        "risk_level": determine_risk_level(risk_score),
        "flags": red_flags if red_flags < 0 else [],
        "recommendation": get_risk_recommendation(risk_score)
    }
```

### Risk Levels & Actions
```python
RISK_LEVELS = {
    "LOW": {"min": 80, "action": "Auto-approve", "monitoring": "Standard"},
    "MEDIUM": {"min": 60, "action": "Review recommended", "monitoring": "Enhanced"},
    "HIGH": {"min": 40, "action": "Manual review required", "monitoring": "High"},
    "CRITICAL": {"min": 0, "action": "Block and investigate", "monitoring": "Maximum"}
}
```

## Composite Scoring Engine

### Overall User Score
```python
def calculate_overall_user_score(user_data):
    # Weighted composite of all scores
    weights = {
        "trust": 0.25,      # User Trust Score
        "savings": 0.25,    # Savings Intelligence Score
        "social": 0.20,     # Social Influence Score
        "investment": 0.20, # Investment Aptitude Score
        "risk": 0.10        # Transaction Risk (inverse)
    }
    
    scores = {
        "trust": user_data.trust_score,
        "savings": user_data.savings_score,
        "social": user_data.social_score,
        "investment": user_data.investment_score,
        "risk": 100 - user_data.average_risk_score  # Invert risk
    }
    
    # Calculate weighted average
    weighted_sum = sum(scores[key] * weights[key] for key in weights)
    total_weight = sum(weights.values())
    overall_score = weighted_sum / total_weight
    
    return {
        "overall_score": overall_score,
        "component_scores": scores,
        "weights": weights,
        "tier": determine_overall_tier(overall_score)
    }
```

### Overall User Tiers
```python
OVERALL_TIERS = {
    "ELITE": {"min": 85, "badge": "👑 Elite Member", "benefits": ["All premium features", "Personal concierge"]},
    "PREMIUM": {"min": 70, "badge": "💎 Premium", "benefits": ["Most premium features", "Priority support"]},
    "PLUS": {"min": 55, "badge": "⭐ Plus", "benefits": ["Enhanced features", "Reduced fees"]},
    "STANDARD": {"min": 40, "badge": "👍 Standard", "benefits": ["Core features"]},
    "BASIC": {"min": 0, "badge": "👋 Basic", "benefits": ["Essential features"]}
}
```

## Scoring Engine Architecture

### Data Pipeline
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │───▶│  ETL Pipeline   │───▶│ Scoring Models  │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ User Activity   │    │ Data Validation │    │ Trust Scoring   │
│ Transactions    │    │ Feature Extraction│   │ Savings Scoring │
│ Social Posts    │    │ Aggregation     │    │ Social Scoring  │
│ Portfolio Data  │    │ Normalization   │    │ Investment      │
│ Merchant Data   │    │ Enrichment      │    │ Merchant        │
│ Market Data     │    │ Quality Checks  │    │ Risk Scoring    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Real-time     │    │   Batch         │    │   API Layer     │
│   Stream        │    │   Processing    │    │                 │
│   (Kafka)       │    │   (Spark)       │    │  GET /scores/   │
│                 │    │                 │    │  POST /recalc/  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Scoring Models Implementation
```python
class ScoringEngine:
    def __init__(self):
        self.models = {
            'trust': UserTrustModel(),
            'savings': SavingsIntelligenceModel(),
            'social': SocialInfluenceModel(),
            'investment': InvestmentAptitudeModel(),
            'merchant': MerchantQualityModel(),
            'risk': TransactionRiskModel()
        }
        self.cache = RedisCache()
        self.metrics = MetricsCollector()
    
    async def calculate_scores(self, user_id: str, force_recalc: bool = False):
        # Check cache first
        cache_key = f"scores:{user_id}"
        if not force_recalc:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        
        # Fetch user data
        user_data = await self.fetch_user_data(user_id)
        
        # Calculate all scores in parallel
        scores = {}
        tasks = []
        
        for model_name, model in self.models.items():
            task = model.calculate(user_data)
            tasks.append((model_name, task))
        
        # Execute calculations
        for model_name, task in tasks:
            try:
                scores[model_name] = await task
            except Exception as e:
                self.metrics.record_error(model_name, e)
                scores[model_name] = self.get_default_score(model_name)
        
        # Calculate composite score
        composite = self.calculate_composite_score(scores)
        scores['composite'] = composite
        
        # Store in cache
        await self.cache.set(cache_key, scores, ttl=3600)  # 1 hour
        
        # Record metrics
        self.metrics.record_calculation(user_id, scores)
        
        return scores
    
    def calculate_composite_score(self, scores):
        # Weighted average calculation
        weights = self.get_score_weights()
        weighted_sum = 0
        total_weight = 0
        
        for model_name, score_data in scores.items():
            if model_name in weights:
                weight = weights[model_name]
                score = score_data.get('score', 0)
                weighted_sum += score * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0
```

### Real-time Scoring Updates
```python
class RealTimeScoringService:
    def __init__(self):
        self.kafka_consumer = KafkaConsumer('user-events')
        self.scoring_engine = ScoringEngine()
        self.websocket_manager = WebSocketManager()
    
    async def process_event(self, event):
        event_type = event['type']
        user_id = event['user_id']
        
        # Determine which scores need recalculation
        models_to_recalc = self.get_affected_models(event_type)
        
        if models_to_recalc:
            # Trigger recalculation
            scores = await self.scoring_engine.calculate_scores(
                user_id, 
                force_recalc=True
            )
            
            # Notify connected clients
            await self.websocket_manager.broadcast(
                user_id, 
                'score_update', 
                scores
            )
            
            # Update recommendations
            await self.update_recommendations(user_id, scores)
    
    def get_affected_models(self, event_type):
        mapping = {
            'transaction_completed': ['savings', 'risk'],
            'post_created': ['social'],
            'investment_made': ['investment'],
            'goal_achieved': ['savings'],
            'challenge_completed': ['savings', 'social'],
            'verification_updated': ['trust'],
            'device_changed': ['trust', 'risk']
        }
        return mapping.get(event_type, [])
```

## Score Visualization & User Interface

### Score Dashboard Components
```typescript
interface ScoreDashboardProps {
  userId: string;
}

const ScoreDashboard: React.FC<ScoreDashboardProps> = ({ userId }) => {
  const { data: scores, isLoading } = useScores(userId);
  
  if (isLoading) return <LoadingSpinner />;
  
  return (
    <div className="score-dashboard">
      {/* Overall Score Card */}
      <OverallScoreCard 
        score={scores.composite.score}
        tier={scores.composite.tier}
        change={scores.composite.change}
      />
      
      {/* Score Breakdown */}
      <div className="score-breakdown">
        <ScoreRadarChart scores={scores} />
        <ScoreProgressBars scores={scores} />
      </div>
      
      {/* Individual Score Cards */}
      <div className="score-grid">
        <ScoreCard 
          title="Trust Score"
          score={scores.trust.score}
          tier={scores.trust.tier}
          icon="🛡️"
          tips={scores.trust.improvement_tips}
        />
        <ScoreCard 
          title="Savings Intelligence"
          score={scores.savings.score}
          tier={scores.savings.tier}
          icon="💰"
          tips={scores.savings.improvement_tips}
        />
        <ScoreCard 
          title="Social Influence"
          score={scores.social.score}
          tier={scores.social.tier}
          icon="🌟"
          tips={scores.social.improvement_tips}
        />
        <ScoreCard 
          title="Investment Aptitude"
          score={scores.investment.score}
          tier={scores.investment.tier}
          icon="📈"
          tips={scores.investment.improvement_tips}
        />
      </div>
      
      {/* Improvement Recommendations */}
      <ImprovementRecommendations scores={scores} />
      
      {/* Score History */}
      <ScoreHistoryChart userId={userId} />
    </div>
  );
};
```

### Score Improvement Tips
```python
class ImprovementTipsGenerator:
    def generate_tips(self, score_data):
        tips = []
        
        # Trust Score Tips
        if score_data.trust.score < 60:
            tips.append({
                "category": "trust",
                "title": "Boost Your Trust Score",
                "actions": [
                    "Verify your identity (+10 points)",
                    "Enable two-factor authentication (+5 points)",
                    "Add a verified phone number (+5 points)"
                ],
                "priority": "high"
            })
        
        # Savings Score Tips
        if score_data.savings.score < 50:
            tips.append({
                "category": "savings",
                "title": "Improve Your Savings",
                "actions": [
                    "Enable roundups on your next 3 purchases (+5 points)",
                    "Set up a savings goal (+3 points)",
                    "Complete a savings challenge (+10 points)"
                ],
                "priority": "medium"
            })
        
        # Social Score Tips
        if score_data.social.score < 40:
            tips.append({
                "category": "social",
                "title": "Increase Your Social Influence",
                "actions": [
                    "Share your next savings post (+2 points)",
                    "Comment on 3 friends' posts (+3 points)",
                    "Reach 50 followers (+5 points)"
                ],
                "priority": "low"
            })
        
        return sorted(tips, key=lambda x: PRIORITY_ORDER[x["priority"]])
```

## Performance & Scaling

### Caching Strategy
```python
class ScoreCache:
    def __init__(self):
        self.redis = RedisClient()
        self.local_cache = LRUCache(maxsize=1000)
    
    async def get(self, user_id):
        # Check local cache first
        local_result = self.local_cache.get(user_id)
        if local_result:
            return local_result
        
        # Check Redis
        redis_result = await self.redis.get(f"scores:{user_id}")
        if redis_result:
            # Store in local cache
            self.local_cache[user_id] = redis_result
            return redis_result
        
        return None
    
    async def set(self, user_id, scores, ttl=3600):
        # Store in Redis
        await self.redis.setex(
            f"scores:{user_id}",
            ttl,
            json.dumps(scores)
        )
        
        # Store in local cache
        self.local_cache[user_id] = scores
```

### Performance Targets
- **Score Calculation**: < 500ms (p95)
- **Cache Hit Rate**: > 90%
- **Concurrent Calculations**: 1000/sec
- **Data Freshness**: Scores updated within 5 minutes of relevant events

## Monitoring & Analytics

### Key Metrics
```python
SCORING_METRICS = {
    "calculation_latency": "Histogram of calculation times",
    "cache_hit_rate": "Percentage of cache hits",
    "score_distribution": "Distribution of scores by tier",
    "recalculation_triggers": "Events triggering recalculations",
    "error_rate": "Calculation error rate",
    "model_performance": "Individual model performance"
}
```

### Alerting Rules
- **High Latency**: Calculation > 1s for > 5% of requests
- **Low Cache Hit**: Hit rate < 80% for 5 minutes
- **High Error Rate**: > 2% error rate for any model
- **Score Anomalies**: Unexpected score distribution changes

## Security & Privacy

### Data Protection
- **Personal Data**: Never stored in scoring models
- **Aggregation**: Scores based on aggregated, anonymized patterns
- **Access Control**: Strict RBAC for score data access
- **Audit Logging**: All score calculations logged

### Compliance
- **GDPR**: Right to explanation for automated decisions
- **Fairness**: Regular bias testing and mitigation
- **Transparency**: Clear documentation of scoring methodology

## Testing & Validation

### Test Suite
```python
class TestScoringEngine:
    def test_user_trust_scoring(self):
        user = create_test_user()
        scores = engine.calculate_scores(user.id)
        assert 0 <= scores.trust.score <= 150
        assert scores.trust.tier in TRUST_TIERS
    
    def test_savings_intelligence(self):
        user = create_user_with_transactions()
        scores = engine.calculate_scores(user.id)
        assert scores.savings.savings_rate >= 0
    
    def test_score_consistency(self):
        # Same input should produce same output
        user = create_test_user()
        scores1 = engine.calculate_scores(user.id)
        scores2 = engine.calculate_scores(user.id)
        assert scores1 == scores2
    
    def test_performance(self):
        start = time.time()
        for _ in range(100):
            engine.calculate_scores(test_user_id)
        duration = time.time() - start
        assert duration < 10  # 100 calculations in < 10 seconds
```

### Validation Pipeline
1. **Unit Tests**: Individual scoring models
2. **Integration Tests**: Full scoring pipeline
3. **Performance Tests**: Load and stress testing
4. **Fairness Tests**: Bias detection and mitigation
5. **A/B Testing**: Score impact on user behavior

This comprehensive scoring engine specification provides a robust foundation for evaluating and rewarding user behavior on the KEEPTHECHANGE.com platform, driving engagement, trust, and financial optimization through transparent, fair, and adaptive scoring mechanisms.