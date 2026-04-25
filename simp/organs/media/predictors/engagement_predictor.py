"""
ContentEngagementPredictor — scores content BEFORE publishing.

Provides an EngagementScore dataclass and a ContentEngagementPredictor class
that takes content features (platform, format, length, topic, day_of_week,
time_of_day, has_cta, has_affiliate) and returns predicted engagement metrics.

Uses a weighted scoring function (stub model) based on known content patterns.
Prediction records are persisted to data/media/predictions/ as append-only JSONL.
"""
import json
import math
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


# =========================================================================
# Data Models
# =========================================================================

@dataclass
class EngagementScore:
    """Predicted engagement score for a piece of content (0-100 scale)."""
    score: float = 0.0                # Overall engagement score 0-100
    confidence: float = 0.0           # Prediction confidence 0-1
    predicted_views: float = 0.0      # Expected view count
    predicted_clicks: float = 0.0     # Expected click count
    predicted_conversions: float = 0.0  # Expected conversions
    estimated_revenue: float = 0.0    # Estimated revenue in USD
    top_factors: List[str] = field(default_factory=list)  # Top contributing factors

    # Internal tracking
    content_id: str = ""
    prediction_id: str = ""
    predicted_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if not result.get("predicted_at"):
            result["predicted_at"] = datetime.utcnow().isoformat()
        return result


# =========================================================================
# Stub Weights — Patterns learned from content engagement research
# =========================================================================

# Platform multipliers (baseline engagement modifier)
_PLATFORM_WEIGHTS = {
    "tiktok": 1.5,
    "youtube_shorts": 1.3,
    "instagram_reels": 1.4,
    "instagram_feed": 0.9,
    "youtube": 1.0,
    "x": 0.7,
    "linkedin": 0.6,
    "facebook": 0.8,
    "pinterest": 0.5,
    "unknown": 0.5,
}

# Content format multipliers
_FORMAT_WEIGHTS = {
    "short_video": 1.4,
    "long_video": 1.0,
    "carousel": 1.2,
    "text_post": 0.6,
    "tutorial": 1.1,
    "review": 1.2,
    "comparison": 1.3,
    "trend_reaction": 1.6,
    "educational_series": 0.9,
    "story": 0.8,
    "unknown": 0.5,
}

# Topic base scores (0-100)
_TOPIC_SCORES = {
    "ai_tools": 85.0,
    "productivity": 75.0,
    "finance": 70.0,
    "health": 65.0,
    "education": 60.0,
    "creator_tools": 80.0,
    "software": 70.0,
    "ecommerce": 65.0,
    "entertainment": 55.0,
    "lifestyle": 50.0,
    "news": 45.0,
    "unknown": 40.0,
}

# Day-of-week multipliers (peak engagement days)
_DAY_WEIGHTS = {
    0: 0.85,  # Monday
    1: 0.90,  # Tuesday
    2: 0.95,  # Wednesday
    3: 1.00,  # Thursday
    4: 1.05,  # Friday
    5: 1.10,  # Saturday
    6: 1.05,  # Sunday
}

# Time-of-day multipliers (peak engagement hours, UTC)
_TIME_WEIGHTS = {
    "morning": (6, 12, 0.90),
    "afternoon": (12, 17, 1.00),
    "evening": (17, 22, 1.10),
    "night": (22, 6, 0.80),
}


def _get_time_slot(hour: int) -> Tuple[float, str]:
    """Get the time-of-day weight and label for a given hour (0-23)."""
    for label, (start, end, weight) in _TIME_WEIGHTS.items():
        if start <= end:
            if start <= hour < end:
                return weight, label
        else:
            # Wraparound (night: 22-6)
            if hour >= start or hour < end:
                return weight, label
    return 1.0, "afternoon"


# =========================================================================
# ContentEngagementPredictor
# =========================================================================

class ContentEngagementPredictor:
    """
    Scores content briefs for expected engagement BEFORE publishing.

    Uses a weighted-scoring model based on known content engagement patterns.
    In production, this would be replaced with a trained ML model from
    TimesFM or similar.

    Thread-safe. Predictions are persisted to a JSONL prediction log.
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        prediction_log: str = "engagement_predictions.jsonl",
        default_threshold: float = 40.0,
    ):
        self._lock = threading.Lock()
        self.default_threshold = default_threshold

        self._data_dir = Path(data_dir) if data_dir else Path("data/media/predictions")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._prediction_log_path = self._data_dir / prediction_log

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, content_brief: Dict[str, Any]) -> EngagementScore:
        """
        Score a single content brief for engagement.

        Args:
            content_brief: A dictionary with ContentBrief-like fields.
                Expected keys: title, platform, format, topic, content,
                has_cta, has_affiliate, target_audience, target_duration_seconds

        Returns:
            EngagementScore with 0-100 score, confidence, and breakdown.
        """
        features = self._extract_features(content_brief)
        score = self._compute_score(features)
        record = self._build_record(score, content_brief, features)
        self._append_prediction(record)
        return score

    def predict_batch(self, briefs: List[Dict[str, Any]]) -> List[EngagementScore]:
        """
        Score multiple content briefs.

        Args:
            briefs: List of content brief dictionaries.

        Returns:
            List of EngagementScore objects in the same order.
        """
        return [self.predict(b) for b in briefs]

    # ------------------------------------------------------------------
    # Feature Extraction
    # ------------------------------------------------------------------

    def _extract_features(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Extract normalized features from a content brief."""
        title = brief.get("title", brief.get("brief", ""))
        content = brief.get("content", "")
        body = content or title

        # Determine day of week and time of day
        now = datetime.utcnow()
        day_of_week = now.weekday()
        hour = now.hour

        time_weight, time_label = _get_time_slot(hour)

        # Determine topic from brief fields
        topic = brief.get("topic", "")
        if not topic:
            topic = brief.get("category", "unknown")

        # Platform
        platform = brief.get("platform", "unknown")
        if isinstance(platform, Enum):
            platform = platform.value

        # Format
        content_format = brief.get("format", "unknown")

        # Length features
        title_length = len(title)
        content_length = len(body)

        # CTA and affiliate flags
        has_cta = brief.get("has_cta", False)
        if not has_cta:
            cta_keywords = ["get started", "sign up", "buy now", "click here",
                            "learn more", "subscribe", "follow", "try now",
                            "download", "claim", "join", "register"]
            has_cta = any(kw in body.lower() for kw in cta_keywords)

        has_affiliate = brief.get("has_affiliate", False)
        if not has_affiliate:
            affiliate_keywords = ["affiliate", "commission", "referral", "partner link",
                                  "sponsored", "promo code", "discount link"]
            has_affiliate = any(kw in body.lower() for kw in affiliate_keywords)

        # Hashtag count (signal of discoverability)
        hashtags = brief.get("hashtags", brief.get("primary_keywords", []))
        hashtag_count = len(hashtags)

        return {
            "title": title,
            "body": body,
            "platform": platform,
            "content_format": content_format,
            "topic": topic,
            "day_of_week": day_of_week,
            "hour": hour,
            "time_label": time_label,
            "time_weight": time_weight,
            "title_length": title_length,
            "content_length": content_length,
            "has_cta": has_cta,
            "has_affiliate": has_affiliate,
            "hashtag_count": hashtag_count,
        }

    # ------------------------------------------------------------------
    # Scoring Engine
    # ------------------------------------------------------------------

    def _compute_score(self, features: Dict[str, Any]) -> EngagementScore:
        """Compute engagement score from extracted features."""
        factors: List[Tuple[str, float]] = []

        # 1. Platform score (0-20 points)
        plat_mult = _PLATFORM_WEIGHTS.get(features["platform"], 0.5)
        platform_score = 10.0 * plat_mult
        platform_score = max(0.0, min(20.0, platform_score))
        factors.append((f"platform({features['platform']})", platform_score))

        # 2. Format score (0-15 points)
        fmt_mult = _FORMAT_WEIGHTS.get(features["content_format"], 0.5)
        format_score = 10.0 * fmt_mult
        format_score = max(0.0, min(15.0, format_score))
        factors.append((f"format({features['content_format']})", format_score))

        # 3. Topic score (0-25 points)
        topic_base = _TOPIC_SCORES.get(features["topic"], 40.0)
        topic_score = topic_base * 0.25  # Scale to 0-25
        topic_score = max(0.0, min(25.0, topic_score))
        factors.append((f"topic({features['topic']})", topic_score))

        # 4. Timing score (0-10 points) — day of week + time of day
        day_mult = _DAY_WEIGHTS.get(features["day_of_week"], 1.0)
        time_mult = features["time_weight"]
        timing_score = 8.0 * day_mult * time_mult
        timing_score = max(0.0, min(10.0, timing_score))
        factors.append((f"timing({features['time_label']})", timing_score))

        # 5. Title quality (0-10 points)
        title_len = features["title_length"]
        if title_len < 10:
            title_score = 3.0  # Too short
        elif title_len < 30:
            title_score = 8.0  # Sweet spot
        elif title_len < 60:
            title_score = 6.0  # OK length
        else:
            title_score = 4.0  # Too long
        factors.append((f"title_length({title_len})", title_score))

        # 6. CTA bonus (0-10 points)
        cta_score = 10.0 if features["has_cta"] else 2.0
        factors.append(("has_cta", cta_score))

        # 7. Affiliate bonus (0-5 points)
        affiliate_bonus = 5.0 if features["has_affiliate"] else 2.0
        factors.append(("has_affiliate", affiliate_bonus))

        # 8. Hashtag bonus (0-5 points)
        htag_count = features["hashtag_count"]
        htag_score = min(5.0, htag_count * 0.5)
        factors.append((f"hashtags({htag_count})", htag_score))

        # Sum raw score (max possible: 100)
        raw_score = sum(s for _, s in factors)
        final_score = max(0.0, min(100.0, raw_score))

        # Confidence — based on how many features were populated
        populated = sum(
            1 for v in features.values()
            if v is not None and v != 0.0 and v != "" and v != "unknown"
        )
        total_checks = max(1, len(features))
        confidence = min(1.0, populated / total_checks)

        # Derived metrics
        base_views = _PLATFORM_WEIGHTS.get(features["platform"], 0.5) * 500.0
        predicted_views = base_views * (1.0 + final_score / 100.0)

        ctr = 0.02 + (final_score / 100.0) * 0.05  # 2-7% CTR
        predicted_clicks = predicted_views * ctr

        conversion_rate = 0.01 + (final_score / 100.0) * 0.04  # 1-5% conversion
        predicted_conversions = predicted_clicks * conversion_rate

        # Revenue: assume avg $25/conversion for affiliate, $5 otherwise
        rev_per_conv = 25.0 if features["has_affiliate"] else 5.0
        estimated_revenue = predicted_conversions * rev_per_conv

        # Top factors (sorted by contribution)
        sorted_factors = sorted(factors, key=lambda x: x[1], reverse=True)
        top_factors = [f"{name}: {val:.1f}" for name, val in sorted_factors[:5]]

        return EngagementScore(
            score=round(final_score, 2),
            confidence=round(confidence, 4),
            predicted_views=round(predicted_views, 0),
            predicted_clicks=round(predicted_clicks, 0),
            predicted_conversions=round(predicted_conversions, 2),
            estimated_revenue=round(estimated_revenue, 2),
            top_factors=top_factors,
        )

    # ------------------------------------------------------------------
    # Record Building & Persistence
    # ------------------------------------------------------------------

    def _build_record(
        self,
        score: EngagementScore,
        brief: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a full prediction record for persistence."""
        now = datetime.utcnow()
        content_id = brief.get("brief_id", brief.get("content_id", f"content_{now.timestamp():.0f}"))
        prediction_id = f"pred_{now.strftime('%Y%m%d_%H%M%S')}_{id(score):x}"

        record = {
            "prediction_id": prediction_id,
            "content_id": content_id,
            "brief_title": brief.get("title", ""),
            "predicted_at": now.isoformat(),
            "score": score.score,
            "confidence": score.confidence,
            "predicted_views": score.predicted_views,
            "predicted_clicks": score.predicted_clicks,
            "predicted_conversions": score.predicted_conversions,
            "estimated_revenue": score.estimated_revenue,
            "top_factors": score.top_factors,
            "brief": {
                k: v for k, v in brief.items()
                if k in ("title", "platform", "format", "topic", "target_audience",
                         "has_cta", "has_affiliate", "category")
            },
            "features": {
                k: v for k, v in features.items()
                if k in ("platform", "content_format", "topic", "day_of_week",
                         "hour", "time_label", "title_length", "content_length",
                         "has_cta", "has_affiliate", "hashtag_count")
            },
        }

        # Attach to score for reference
        score.content_id = content_id
        score.prediction_id = prediction_id
        score.predicted_at = now.isoformat()

        return record

    def _append_prediction(self, record: Dict[str, Any]) -> None:
        """Thread-safe append to the prediction JSONL log."""
        with self._lock:
            with open(self._prediction_log_path, "a") as f:
                f.write(json.dumps(record) + "\n")

    # ------------------------------------------------------------------
    # Log Management
    # ------------------------------------------------------------------

    def load_predictions(self) -> List[Dict[str, Any]]:
        """Load all prediction records from the JSONL log."""
        if not self._prediction_log_path.exists():
            return []
        records = []
        with open(self._prediction_log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate prediction statistics."""
        records = self.load_predictions()
        if not records:
            return {
                "total_predictions": 0,
                "avg_score": 0.0,
                "avg_confidence": 0.0,
                "avg_revenue": 0.0,
            }

        scores = [r["score"] for r in records]
        confs = [r["confidence"] for r in records]
        revs = [r["estimated_revenue"] for r in records]

        return {
            "total_predictions": len(records),
            "avg_score": round(sum(scores) / len(scores), 2),
            "avg_confidence": round(sum(confs) / len(confs), 4),
            "avg_revenue": round(sum(revs) / len(revs), 2),
            "max_score": round(max(scores), 2),
            "min_score": round(min(scores), 2),
        }

    def set_threshold(self, threshold: float) -> None:
        """Set the default engagement score threshold for filtering."""
        self.default_threshold = max(0.0, min(100.0, threshold))
