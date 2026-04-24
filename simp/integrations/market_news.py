"""
Market News Ingestor + ML Trade Logic Adjuster

Brings the "advanced ML trade logic on market news" from the PDF vision
into SIMP.  Three layers:

  1. NewsAPIIngestor   — pulls from NewsAPI, CryptoPanic, Twitter/X feeds
  2. SentimentAnalyzer — NLP sentiment scoring per token pair
  3. MLTradeLogicAdjuster — adjusts strategy params based on news + trend signals
"""

from __future__ import annotations

import json
import logging
import math
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from urllib.parse import urlencode, quote_plus

log = logging.getLogger("market_news")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NewsArticle:
    """One news article relevant to a trading pair."""
    source: str                       # "newsapi", "cryptopanic", "twitter"
    title: str
    url: str
    published_at: str
    summary: str = ""
    token_pairs: List[str] = field(default_factory=list)
    sentiment_score: float = 0.0      # -1.0 (negative) to +1.0 (positive)
    relevance_score: float = 0.5      # 0.0–1.0 how relevant to trading
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TokenSentiment:
    """Aggregated sentiment for a token pair."""
    pair: str
    avg_sentiment: float
    article_count: int
    recent_trend: str                  # "bullish", "bearish", "neutral"
    volume_24h_change_pct: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyAdjustment:
    """
    Adjustments to trading strategy parameters based on news + sentiment.
    
    These get applied to TradeExecutor and ArbDetector configs.
    """
    timestamp: str
    source: str                       # which news article / signal triggered this
    pair: str
    risk_multiplier: float = 1.0      # <1.0 = reduce risk, >1.0 = increase
    min_spread_adjustment_bps: float = 0.0  # positive = require wider spread
    position_size_multiplier: float = 1.0
    confidence_boost: float = 0.0     # added to arb opportunity confidence
    reason: str = ""


# ---------------------------------------------------------------------------
# NewsAPIIngestor — pull from web APIs
# ---------------------------------------------------------------------------

class NewsAPIIngestor:
    """
    Fetches market news from multiple sources.

    Supports:
      - NewsAPI     (newsapi.org)
      - CryptoPanic (cryptopanic.com)
      - Twitter/X   (via Nitter RSS as fallback)
    
    Each source can be enabled/disabled independently.
    """

    def __init__(
        self,
        newsapi_key: str = "",
        cryptopanic_key: str = "",
        twitter_bearer_token: str = "",
        cache_dir: str = "data/news_cache",
        cache_ttl_minutes: int = 15,
    ):
        self._newsapi_key = newsapi_key
        self._cryptopanic_key = cryptopanic_key
        self._twitter_token = twitter_bearer_token
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._lock = threading.Lock()
        self._article_cache: Dict[str, List[NewsArticle]] = {}

    # ------------------------------------------------------------------
    # fetch from NewsAPI
    # ------------------------------------------------------------------

    def fetch_newsapi(self, query: str = "cryptocurrency", days_back: int = 1) -> List[NewsArticle]:
        """Fetch news from NewsAPI."""
        if not self._newsapi_key:
            log.debug("NewsAPI key not configured — skipping")
            return []

        cache_key = f"newsapi_{query}_{days_back}"
        cached = self._check_cache(cache_key)
        if cached is not None:
            return cached

        try:
            import requests as req
            from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            url = (
                "https://newsapi.org/v2/everything?"
                + urlencode({"q": query, "from": from_date, "sortBy": "publishedAt", "pageSize": 20})
            )
            resp = req.get(url, headers={"X-Api-Key": self._newsapi_key}, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            articles = []
            for item in data.get("articles", []):
                article = NewsArticle(
                    source="newsapi",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    published_at=item.get("publishedAt", ""),
                    summary=item.get("description", ""),
                    token_pairs=self._extract_pairs(item.get("title", "") + " " + (item.get("description", "") or "")),
                    raw_data=item,
                )
                articles.append(article)

            self._cache_articles(cache_key, articles)
            log.info("NewsAPI: fetched %d articles for query '%s'", len(articles), query)
            return articles

        except Exception as exc:
            log.warning("NewsAPI fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # fetch from CryptoPanic
    # ------------------------------------------------------------------

    def fetch_cryptopanic(self, filter_type: str = "rising", days_back: int = 1) -> List[NewsArticle]:
        """Fetch news from CryptoPanic."""
        if not self._cryptopanic_key:
            log.debug("CryptoPanic key not configured — skipping")
            return []

        cache_key = f"cryptopanic_{filter_type}_{days_back}"
        cached = self._check_cache(cache_key)
        if cached is not None:
            return cached

        try:
            import requests as req
            url = (
                "https://cryptopanic.com/api/v1/posts/?"
                + urlencode({"auth_token": self._cryptopanic_key, "filter": filter_type, "limit": 50})
            )
            resp = req.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            articles = []
            for item in data.get("results", []):
                title = item.get("title", "")
                pairs = []
                for currency in item.get("currencies", []):
                    code = currency.get("code", "")
                    if code:
                        pairs.append(f"{code}/USDT")

                article = NewsArticle(
                    source="cryptopanic",
                    title=title,
                    url=item.get("url", ""),
                    published_at=item.get("published_at", ""),
                    summary=item.get("description", "") or title,
                    token_pairs=pairs,
                    raw_data=item,
                )
                articles.append(article)

            self._cache_articles(cache_key, articles)
            log.info("CryptoPanic: fetched %d articles", len(articles))
            return articles

        except Exception as exc:
            log.warning("CryptoPanic fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # fetch from Twitter/X
    # ------------------------------------------------------------------

    def fetch_twitter(self, query: str = "crypto trading", count: int = 20) -> List[NewsArticle]:
        """Fetch tweets via Twitter API v2."""
        if not self._twitter_token:
            log.debug("Twitter bearer token not configured — skipping")
            return []

        cache_key = f"twitter_{query}_{count}"
        cached = self._check_cache(cache_key)
        if cached is not None:
            return cached

        try:
            import requests as req
            url = "https://api.twitter.com/2/tweets/search/recent"
            params = {
                "query": query,
                "max_results": min(count, 100),
                "tweet.fields": "created_at,public_metrics",
            }
            resp = req.get(url, headers={"Authorization": f"Bearer {self._twitter_token}"}, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            articles = []
            for item in data.get("data", []):
                article = NewsArticle(
                    source="twitter",
                    title=item.get("text", "")[:200],
                    url=f"https://twitter.com/i/web/status/{item['id']}",
                    published_at=item.get("created_at", ""),
                    summary=item.get("text", "")[:500],
                    token_pairs=self._extract_pairs(item.get("text", "")),
                    raw_data=item,
                )
                articles.append(article)

            self._cache_articles(cache_key, articles)
            log.info("Twitter: fetched %d tweets for query '%s'", len(articles), query)
            return articles

        except Exception as exc:
            log.warning("Twitter fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # utility
    # ------------------------------------------------------------------

    def fetch_all(self, crypto_queries: Optional[List[str]] = None) -> List[NewsArticle]:
        """Fetch from all configured sources."""
        queries = crypto_queries or ["bitcoin", "ethereum", "cryptocurrency", "defi", "arbitrage"]
        all_articles = []

        for q in queries:
            all_articles.extend(self.fetch_newsapi(query=q, days_back=1))

        all_articles.extend(self.fetch_cryptopanic())
        all_articles.extend(self.fetch_twitter())

        return all_articles

    def _extract_pairs(self, text: str) -> List[str]:
        """Naively extract token pair mentions from text."""
        known_tokens = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOT", "LINK",
                        "AVAX", "MATIC", "ATOM", "UNI", "AAVE", "CRV", "BNB"]
        found = []
        upper = text.upper()
        for token in known_tokens:
            if token in upper:
                found.append(f"{token}/USDT")
        return found

    def _check_cache(self, key: str) -> Optional[List[NewsArticle]]:
        cache_file = self._cache_dir / f"{key.replace(' ', '_')}.json"
        if cache_file.exists():
            age = datetime.now(timezone.utc) - datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
            if age < self._cache_ttl:
                try:
                    with open(cache_file) as f:
                        data = json.load(f)
                        return [NewsArticle(**a) for a in data]
                except Exception:
                    pass
        return None

    def _cache_articles(self, key: str, articles: List[NewsArticle]) -> None:
        cache_file = self._cache_dir / f"{key.replace(' ', '_')}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump([a.to_dict() for a in articles], f)
        except Exception as exc:
            log.warning("Failed to cache articles: %s", exc)


# ---------------------------------------------------------------------------
# SentimentAnalyzer — simple NLP scoring
# ---------------------------------------------------------------------------

class SentimentAnalyzer:
    """
    Scores news articles and produces aggregated token-level sentiment.

    Uses a simple keyword-based approach (no external NLP dependency).
    For production, swap in VADER (vaderSentiment) or a transformer model.
    """

    def __init__(self):
        # Positive keywords with weights
        self._positive_words: Dict[str, float] = {
            "bullish": 0.8, "surge": 0.7, "rally": 0.8, "moon": 0.6,
            "breakthrough": 0.7, "adoption": 0.6, "partnership": 0.6,
            "launch": 0.4, "upgrade": 0.5, "positive": 0.5,
            "gain": 0.6, "profit": 0.5, "growth": 0.7, "innovation": 0.5,
            "institutional": 0.5, "etf": 0.6, "approval": 0.5,
            "high": 0.3, "rise": 0.5, "increase": 0.4, "opportunity": 0.4,
        }
        # Negative keywords with weights
        self._negative_words: Dict[str, float] = {
            "bearish": -0.8, "crash": -0.9, "plunge": -0.8, "dump": -0.7,
            "hack": -0.9, "scam": -0.9, "fraud": -0.9, "ban": -0.7,
            "regulation": -0.4, "crackdown": -0.7, "fear": -0.6,
            "uncertainty": -0.5, "volatile": -0.3, "decline": -0.5,
            "drop": -0.6, "fall": -0.5, "loss": -0.6, "low": -0.3,
            "risk": -0.4, "warning": -0.5, "sell-off": -0.7,
        }

    def score_article(self, article: NewsArticle) -> float:
        """
        Score a single article. Returns -1.0 (negative) to +1.0 (positive).
        """
        text = f"{article.title} {article.summary}".lower()
        score = 0.0
        match_count = 0

        for word, weight in self._positive_words.items():
            if word in text:
                score += weight
                match_count += 1

        for word, weight in self._negative_words.items():
            if word in text:
                score += weight
                match_count += 1

        if match_count == 0:
            return 0.0

        avg = score / match_count
        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, avg))

    def score_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Score all articles in-place and return them."""
        for article in articles:
            article.sentiment_score = self.score_article(article)
        return articles

    def aggregate_by_pair(self, articles: List[NewsArticle]) -> List[TokenSentiment]:
        """
        Aggregate sentiment scores per trading pair.

        Returns sorted list (most articles first).
        """
        pair_scores: Dict[str, List[float]] = {}

        for article in articles:
            for pair in article.token_pairs:
                if pair not in pair_scores:
                    pair_scores[pair] = []
                pair_scores[pair].append(article.sentiment_score)

        results = []
        for pair, scores in pair_scores.items():
            avg = sum(scores) / len(scores)
            if avg > 0.2:
                trend = "bullish"
            elif avg < -0.2:
                trend = "bearish"
            else:
                trend = "neutral"

            results.append(TokenSentiment(
                pair=pair,
                avg_sentiment=round(avg, 3),
                article_count=len(scores),
                recent_trend=trend,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

        results.sort(key=lambda r: r.article_count, reverse=True)
        return results


# ---------------------------------------------------------------------------
# MLTradeLogicAdjuster — strategy param adaptation
# ---------------------------------------------------------------------------

class MLTradeLogicAdjuster:
    """
    Adjusts trading strategy parameters based on news sentiment and
    market trend data.

    This is the "ML code that makes on-spot adjustments to trade logic"
    from the PDF.  Uses simple heuristics now; swappable for a real ML
    model (XGBoost, Prophet, etc.)
    """

    def __init__(
        self,
        sentiment_analyzer: Optional[SentimentAnalyzer] = None,
        enable_auto_adjust: bool = True,
    ):
        self._sentiment = sentiment_analyzer or SentimentAnalyzer()
        self._enable = enable_auto_adjust
        self._lock = threading.Lock()
        self._adjustment_log: List[StrategyAdjustment] = []
        self._token_cache: Dict[str, TokenSentiment] = {}

    # ------------------------------------------------------------------
    # produce adjustments
    # ------------------------------------------------------------------

    def adjust_for_news(
        self,
        articles: List[NewsArticle],
        target_pairs: Optional[List[str]] = None,
    ) -> Dict[str, StrategyAdjustment]:
        """
        Given a list of news articles, produce StrategyAdjustment objects
        per trading pair.

        Returns dict mapping pair → StrategyAdjustment.
        """
        if not self._enable:
            return {}

        # Score articles
        scored = self._sentiment.score_articles(articles)

        # Aggregate by pair
        sentiments = self._sentiment.aggregate_by_pair(scored)
        for s in sentiments:
            self._token_cache[s.pair] = s

        # Filter to target pairs if specified
        if target_pairs:
            sentiments = [s for s in sentiments if s.pair in target_pairs]

        adjustments: Dict[str, StrategyAdjustment] = {}

        for s in sentiments:
            adj = self._compute_adjustment(s)
            adjustments[s.pair] = adj
            self._adjustment_log.append(adj)

        return adjustments

    def _compute_adjustment(self, sentiment: TokenSentiment) -> StrategyAdjustment:
        """Compute single adjustment from token sentiment."""
        s = sentiment.avg_sentiment
        pair = sentiment.pair

        if s > 0.5:
            # Strongly bullish → increase risk, lower spread threshold
            adjustment = StrategyAdjustment(
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=f"sentiment_{pair}",
                pair=pair,
                risk_multiplier=1.3,
                min_spread_adjustment_bps=-2.0,  # accept smaller spreads
                position_size_multiplier=1.2,
                confidence_boost=0.1,
                reason=f"Bullish sentiment ({s:.2f}) on {pair} from {sentiment.article_count} articles",
            )
        elif s > 0.1:
            # Mildly bullish → slight risk increase
            adjustment = StrategyAdjustment(
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=f"sentiment_{pair}",
                pair=pair,
                risk_multiplier=1.1,
                min_spread_adjustment_bps=-1.0,
                position_size_multiplier=1.05,
                confidence_boost=0.05,
                reason=f"Mildly bullish sentiment ({s:.2f}) on {pair}",
            )
        elif s < -0.5:
            # Strongly bearish → reduce risk significantly
            adjustment = StrategyAdjustment(
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=f"sentiment_{pair}",
                pair=pair,
                risk_multiplier=0.5,
                min_spread_adjustment_bps=5.0,   # require wider spread
                position_size_multiplier=0.5,
                confidence_boost=-0.1,            # reduce confidence
                reason=f"Bearish sentiment ({s:.2f}) on {pair} — reducing exposure",
            )
        elif s < -0.1:
            # Mildly bearish → slight risk reduction
            adjustment = StrategyAdjustment(
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=f"sentiment_{pair}",
                pair=pair,
                risk_multiplier=0.8,
                min_spread_adjustment_bps=2.0,
                position_size_multiplier=0.8,
                confidence_boost=-0.03,
                reason=f"Mildly bearish sentiment ({s:.2f}) on {pair}",
            )
        else:
            # Neutral → no adjustment
            adjustment = StrategyAdjustment(
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=f"sentiment_{pair}",
                pair=pair,
                risk_multiplier=1.0,
                reason=f"Neutral sentiment ({s:.2f}) on {pair} — no adjustment",
            )

        return adjustment

    # ------------------------------------------------------------------
    # apply adjustments to trading params
    # ------------------------------------------------------------------

    def apply_to_params(
        self,
        params: Dict[str, Any],
        pair: str,
        adjustments: Dict[str, StrategyAdjustment],
    ) -> Dict[str, Any]:
        """
        Apply strategy adjustments to a params dict (from GrowthScheduler
        or TradeExecutor config).

        Returns modified copy of params.
        """
        adj = adjustments.get(pair)
        if not adj:
            return dict(params)

        modified = dict(params)

        # Adjust risk per trade
        base_risk = modified.get("risk_per_trade_pct", 0.5)
        modified["risk_per_trade_pct"] = round(base_risk * adj.risk_multiplier, 4)

        # Adjust min spread
        base_spread = modified.get("min_spread_bps", 10.0)
        modified["min_spread_bps"] = max(1.0, base_spread + adj.min_spread_adjustment_bps)

        # Adjust position size
        base_position = modified.get("max_position_pct", 10.0)
        modified["max_position_pct"] = round(base_position * adj.position_size_multiplier, 4)

        # Add confidence boost for rankers
        modified["sentiment_boost"] = adj.confidence_boost
        modified["sentiment_reason"] = adj.reason

        return modified

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------

    def get_adjustment_history(self, limit: int = 20) -> List[StrategyAdjustment]:
        return self._adjustment_log[-limit:]

    def get_token_sentiment(self, pair: str) -> Optional[TokenSentiment]:
        return self._token_cache.get(pair)

    def adjust_strategy(
        self, articles: List[NewsArticle], target_pairs: Optional[List[str]] = None
    ) -> Dict[str, StrategyAdjustment]:
        """Alias for adjust_for_news (semantic clarity)."""
        return self.adjust_for_news(articles, target_pairs)


# ======================================================================
# Quick test
# ======================================================================

if __name__ == "__main__":
    print("Market News Ingestor + ML Trade Logic Adjuster loaded")
    print("Available: NewsAPIIngestor, SentimentAnalyzer, MLTradeLogicAdjuster")
