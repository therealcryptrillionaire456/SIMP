"""
Content Engagement Predictor for KashClaw Media Grid.

TribeV2-inspired architecture adapted for content engagement prediction.

Architecture pattern (adapted from facebookresearch/tribev2):
  Input Features → Modality Projectors → Combiner → Transformer Encoder
  → Temporal Smoothing → Engagement Head

Instead of predicting fMRI brain activation, this module predicts:
  - Expected view count
  - Expected engagement rate (likes, shares, comments)
  - Predicted click-through rate
  - Content virality score
  - Optimal posting time window

This is a simulation-grade engine. In production it would be trained on
real engagement data via the SIMP TimesFM service or a dedicated model.
"""
import json
import math
import random
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


# =========================================================================
# Data Models
# =========================================================================

@dataclass
class ContentFeatures:
    """Multimodal features extracted from content for engagement prediction."""
    # Text features
    title_length: int = 0
    has_question: bool = False
    has_numbers: bool = False
    has_power_words: bool = False
    sentiment_score: float = 0.0  # -1.0 to 1.0
    readability_score: float = 0.5  # 0.0 to 1.0

    # Visual features (proxy)
    has_thumbnail: bool = False
    thumbnail_quality: float = 0.5  # 0.0 to 1.0
    has_face: bool = False
    color_variance: float = 0.5  # 0.0 to 1.0

    # Audio features (proxy)
    has_music: bool = False
    has_voiceover: bool = False
    audio_quality: float = 0.5  # 0.0 to 1.0
    duration_seconds: float = 60.0

    # Engagement features (historical)
    platform: str = "unknown"
    content_format: str = "unknown"
    target_audience: str = "general"
    posting_hour: int = 12

    def to_vector(self) -> List[float]:
        """Flatten features into a numeric vector for prediction."""
        return [
            self.title_length / 100.0,               # normalize
            1.0 if self.has_question else 0.0,
            1.0 if self.has_numbers else 0.0,
            1.0 if self.has_power_words else 0.0,
            (self.sentiment_score + 1.0) / 2.0,      # shift to 0-1
            self.readability_score,
            1.0 if self.has_thumbnail else 0.0,
            self.thumbnail_quality,
            1.0 if self.has_face else 0.0,
            self.color_variance,
            1.0 if self.has_music else 0.0,
            1.0 if self.has_voiceover else 0.0,
            self.audio_quality,
            min(1.0, self.duration_seconds / 300.0), # normalize to 5 min max
            self.posting_hour / 24.0
        ]

    @classmethod
    def from_content_brief(cls, brief: Dict[str, Any]) -> "ContentFeatures":
        """Extract features from a ContentBrief-like dictionary."""
        title = brief.get("title", "")
        body = brief.get("content", brief.get("brief", ""))
        power_words = [
            "ultimate", "secret", "proven", "guaranteed", "free",
            "instant", "easy", "powerful", "essential", "exclusive",
            "amazing", "incredible", "unbelievable", "shocking", "revealed"
        ]

        return cls(
            title_length=len(title),
            has_question="?" in title,
            has_numbers=any(c.isdigit() for c in title),
            has_power_words=any(w in title.lower() for w in power_words),
            sentiment_score=0.3,  # default slightly positive
            readability_score=0.6,
            has_thumbnail=True,
            thumbnail_quality=0.6,
            has_face=False,
            color_variance=0.5,
            has_music=False,
            has_voiceover=True,
            audio_quality=0.6,
            duration_seconds=brief.get("target_duration_seconds", 60.0),
            platform=brief.get("platform", "tiktok"),
            content_format=brief.get("format", "short_video"),
            target_audience=brief.get("target_audience", "general"),
            posting_hour=datetime.utcnow().hour
        )


@dataclass
class EngagementPrediction:
    """Predicted engagement metrics for a piece of content."""
    content_id: str = ""
    platform: str = "unknown"

    # Core predictions
    predicted_views: float = 0.0
    predicted_likes: float = 0.0
    predicted_shares: float = 0.0
    predicted_comments: float = 0.0
    predicted_ctr: float = 0.0  # click-through rate

    # Composite scores
    virality_score: float = 0.0       # 0.0 to 1.0
    engagement_rate: float = 0.0      # predicted likes+comments / views
    quality_score: float = 0.0        # 0.0 to 1.0
    confidence: float = 0.0           # 0.0 to 1.0

    # Optimization
    optimal_posting_hour: int = 12
    expected_lifetime_views: float = 0.0

    # Metadata
    model_version: str = "tribev2-adapted-v1"
    predicted_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["predicted_at"] = datetime.utcnow().isoformat()
        return result


# =========================================================================
# Predictor Components
# =========================================================================

class ModalityProjector:
    """
    Maps input feature vectors into a shared embedding space.

    In TribeV2 this would be learned linear projections per modality.
    Here we use sigmoid-weighted combinations as a stand-in.
    """

    def __init__(self, input_dim: int = 15, embed_dim: int = 64):
        self.input_dim = input_dim
        self.embed_dim = embed_dim
        # Mock learned weights
        self._weights = [random.uniform(-0.5, 0.5) for _ in range(input_dim * embed_dim)]
        self._bias = [random.uniform(-0.1, 0.1) for _ in range(embed_dim)]

    def project(self, features: ContentFeatures) -> List[float]:
        """Project content features into embedding space."""
        vec = features.to_vector()
        embedding = []
        for j in range(self.embed_dim):
            val = self._bias[j]
            for i in range(self.input_dim):
                if i < len(vec):
                    val += vec[i] * self._weights[j * self.input_dim + i]
            # Sigmoid-like activation
            val = 1.0 / (1.0 + math.exp(-val))
            embedding.append(val)
        return embedding


class TemporalSmoother:
    """
    Applies temporal smoothing across content sequences.

    TribeV2 applies temporal smoothing to fMRI predictions across time.
    We adapt this to smooth engagement predictions across posting history,
    accounting for audience fatigue and content saturation.
    """

    def __init__(self, window_size: int = 3, decay_factor: float = 0.7):
        self.window_size = window_size
        self.decay_factor = decay_factor
        self._history: List[float] = []

    def smooth(self, raw_score: float) -> float:
        """Apply temporal smoothing to a raw prediction score."""
        self._history.append(raw_score)
        if len(self._history) > self.window_size * 2:
            self._history = self._history[-self.window_size:]

        if len(self._history) <= 1:
            return raw_score

        # Weighted average with recency bias
        weights = [
            self.decay_factor ** (len(self._history) - i - 1)
            for i in range(len(self._history))
        ]
        total_weight = sum(weights)
        smoothed = sum(
            h * w for h, w in zip(self._history, weights)
        ) / total_weight

        return smoothed


class EngagementHead:
    """
    Final prediction layer that maps embeddings to engagement metrics.

    In TribeV2 this is a linear layer + subject-specific mapping.
    Here we use weighted combinations with platform-specific calibrations.
    """

    def __init__(self):
        # Platform base rates (views per hour, normalized)
        self._platform_base_rates = {
            "tiktok": 500.0,
            "youtube": 200.0,
            "instagram": 300.0,
            "x": 100.0,
            "linkedin": 50.0,
            "facebook": 150.0,
            "youtube_shorts": 400.0,
            "instagram_reels": 450.0
        }

        # Engagement multipliers by format
        self._format_multipliers = {
            "short_video": 1.5,
            "long_video": 1.0,
            "carousel": 1.3,
            "text_post": 0.7,
            "tutorial": 1.1,
            "review": 1.2,
            "comparison": 1.4,
            "trend_reaction": 1.8,
            "educational_series": 0.9
        }

    def predict(
        self,
        embedding: List[float],
        features: ContentFeatures,
        temporal_score: float
    ) -> EngagementPrediction:
        """Generate full engagement prediction from processed features."""
        # Base view estimate from platform
        base_views = self._platform_base_rates.get(features.platform, 100.0)

        # Quality multiplier from embedding (mean activation)
        quality = statistics.mean(embedding) if embedding else 0.5
        quality = max(0.1, min(1.0, quality))

        # Format multiplier
        fmt_mult = self._format_multipliers.get(features.content_format, 1.0)

        # Temporal decay
        temporal_factor = temporal_score

        # Calculate predicted views
        predicted_views = base_views * quality * fmt_mult * temporal_factor * 24.0  # daily

        # Derive engagement metrics from views
        like_rate = 0.05 + (quality * 0.10)  # 5-15% like rate
        share_rate = 0.01 + (quality * 0.04)  # 1-5% share rate
        comment_rate = 0.005 + (quality * 0.025)  # 0.5-3% comment rate

        predicted_likes = predicted_views * like_rate
        predicted_shares = predicted_views * share_rate
        predicted_comments = predicted_views * comment_rate

        # CTR: depends on title features
        ctr_base = 0.02  # 2% baseline
        if features.has_question:
            ctr_base += 0.005
        if features.has_numbers:
            ctr_base += 0.003
        if features.has_power_words:
            ctr_base += 0.008
        predicted_ctr = min(0.15, ctr_base * quality)

        # Composite scores
        engagement_rate = (
            (predicted_likes + predicted_comments) / max(1.0, predicted_views)
        )
        virality_score = min(1.0, quality * (1.0 + share_rate * 10) * fmt_mult / 2.0)
        confidence = min(1.0, quality * 0.8 + 0.2)

        # Optimal posting hour (based on platform)
        optimal_hour = self._optimal_posting_hour(features.platform)

        return EngagementPrediction(
            content_id=f"pred-{datetime.utcnow().timestamp():.0f}",
            platform=features.platform,
            predicted_views=round(predicted_views, 0),
            predicted_likes=round(predicted_likes, 0),
            predicted_shares=round(predicted_shares, 0),
            predicted_comments=round(predicted_comments, 0),
            predicted_ctr=round(predicted_ctr, 4),
            virality_score=round(virality_score, 4),
            engagement_rate=round(engagement_rate, 4),
            quality_score=round(quality, 4),
            confidence=round(confidence, 4),
            optimal_posting_hour=optimal_hour,
            expected_lifetime_views=round(predicted_views * 5, 0),  # 5x multiplier for lifetime
        )

    def _optimal_posting_hour(self, platform: str) -> int:
        """Return optimal posting hour (UTC) based on platform."""
        platform_hours = {
            "tiktok": 19,      # 7 PM
            "youtube": 14,     # 2 PM
            "instagram": 11,   # 11 AM
            "x": 8,            # 8 AM
            "linkedin": 7,     # 7 AM
            "facebook": 13,    # 1 PM
            "youtube_shorts": 18,
            "instagram_reels": 20
        }
        return platform_hours.get(platform, 12)


# =========================================================================
# Main Predictor
# =========================================================================

class ContentEngagementPredictor:
    """
    TribeV2-inspired content engagement prediction engine.

    Architecture:
      ContentFeatures → ModalityProjector → TransformerEncoder (simulated)
      → TemporalSmoother → EngagementHead → EngagementPrediction

    This is a simulation/pattern-matching engine. For real inference,
    weights would be loaded from a trained model via TimesFM or ONNX.
    """

    def __init__(
        self,
        embed_dim: int = 64,
        temporal_window: int = 3,
        model_version: str = "tribev2-adapted-v1",
        data_dir: Optional[str] = None
    ):
        self.embed_dim = embed_dim
        self.model_version = model_version
        self.data_dir = Path(data_dir) if data_dir else Path("data/media/predictions")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Architecture components
        self.projector = ModalityProjector(input_dim=15, embed_dim=embed_dim)
        self.smoother = TemporalSmoother(window_size=temporal_window)
        self.head = EngagementHead()

        # State
        self._prediction_history: List[Dict] = []
        self._calibration_data: Dict[str, Dict] = {}

    def predict(
        self,
        features: ContentFeatures,
        record: bool = True
    ) -> EngagementPrediction:
        """
        Run full prediction pipeline on content features.

        Steps:
        1. Project features into embedding space (ModalityProjector)
        2. Apply temporal smoothing
        3. Generate engagement metrics (EngagementHead)
        """
        # Step 1: Project
        embedding = self.projector.project(features)

        # Step 2: Smooth (extract a scalar confidence from embedding)
        raw_score = statistics.mean(embedding)
        temporal_score = self.smoother.smooth(raw_score)

        # Step 3: Predict
        prediction = self.head.predict(embedding, features, temporal_score)
        prediction.model_version = self.model_version

        # Record
        if record:
            record_data = prediction.to_dict()
            record_data["features"] = asdict(features)
            self._prediction_history.append(record_data)
            self._append_to_ledger(record_data)

        return prediction

    def predict_from_brief(
        self,
        brief: Dict[str, Any],
        record: bool = True
    ) -> EngagementPrediction:
        """Convenience: predict from a content brief dictionary."""
        features = ContentFeatures.from_content_brief(brief)
        return self.predict(features, record=record)

    def batch_predict(
        self,
        features_list: List[ContentFeatures]
    ) -> List[EngagementPrediction]:
        """Run predictions on multiple content items."""
        return [self.predict(f, record=True) for f in features_list]

    def compare(
        self,
        candidate_a: Dict[str, Any],
        candidate_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare two content briefs and return which scores higher."""
        pred_a = self.predict_from_brief(candidate_a)
        pred_b = self.predict_from_brief(candidate_b)

        a_score = pred_a.virality_score * 0.4 + pred_a.engagement_rate * 0.3 + pred_a.quality_score * 0.3
        b_score = pred_b.virality_score * 0.4 + pred_b.engagement_rate * 0.3 + pred_b.quality_score * 0.3

        return {
            "winner": "A" if a_score >= b_score else "B",
            "scores": {
                "A": {"virality": pred_a.virality_score, "engagement": pred_a.engagement_rate, "quality": pred_a.quality_score, "composite": round(a_score, 4)},
                "B": {"virality": pred_b.virality_score, "engagement": pred_b.engagement_rate, "quality": pred_b.quality_score, "composite": round(b_score, 4)}
            },
            "predictions": {
                "A": pred_a.to_dict(),
                "B": pred_b.to_dict()
            }
        }

    def get_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return recent prediction history."""
        return self._prediction_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Return predictor statistics."""
        if not self._prediction_history:
            return {"total_predictions": 0, "avg_virality": 0.0, "avg_confidence": 0.0}

        virality_scores = [
            p.get("virality_score", 0.0) for p in self._prediction_history
        ]
        confidence_scores = [
            p.get("confidence", 0.0) for p in self._prediction_history
        ]

        return {
            "total_predictions": len(self._prediction_history),
            "avg_virality": round(statistics.mean(virality_scores), 4),
            "avg_confidence": round(statistics.mean(confidence_scores), 4),
            "max_virality": round(max(virality_scores), 4),
            "min_virality": round(min(virality_scores), 4),
            "platform_distribution": self._platform_distribution()
        }

    def _platform_distribution(self) -> Dict[str, int]:
        """Count predictions by platform."""
        dist: Dict[str, int] = {}
        for p in self._prediction_history:
            plat = p.get("platform", "unknown")
            dist[plat] = dist.get(plat, 0) + 1
        return dist

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _append_to_ledger(self, record: Dict[str, Any]) -> None:
        """Append a prediction record to the JSONL ledger."""
        ledger_path = self.data_dir / "engagement_predictions.jsonl"
        with open(ledger_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def load_history(self) -> List[Dict[str, Any]]:
        """Load prediction history from the JSONL ledger."""
        ledger_path = self.data_dir / "engagement_predictions.jsonl"
        if not ledger_path.exists():
            return []
        records = []
        with open(ledger_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        self._prediction_history = records
        return records


# =========================================================================
# TribeV2-inspired Simulated Transformer Encoder
# =========================================================================

class SimulatedTransformerEncoder:
    """
    Stand-in for a full TransformerEncoder.

    In TribeV2 this is a multi-layer transformer with self-attention
    over the temporal dimension. Here we provide a simplified version
    that applies attention-like weighting to feature embeddings.

    In production, replace this with a trained TimesFM or transformer model.
    """

    def __init__(self, d_model: int = 64, n_heads: int = 4):
        self.d_model = d_model
        self.n_heads = n_heads
        # Mock attention pattern favoring features correlated with engagement
        self._attention_bias = [
            random.uniform(-0.3, 0.8) for _ in range(d_model)
        ]

    def encode(self, embeddings: List[List[float]]) -> List[List[float]]:
        """
        Apply simulated self-attention to a sequence of embeddings.

        Each embedding gets re-weighted based on its alignment with
        learned engagement-relevant patterns.
        """
        if not embeddings:
            return []

        encoded = []
        for emb in embeddings:
            # Apply attention-like weighting
            weighted = []
            for i, val in enumerate(emb):
                if i < len(self._attention_bias):
                    attention_weight = 1.0 + self._attention_bias[i]
                else:
                    attention_weight = 1.0
                weighted.append(max(0.0, min(1.0, val * attention_weight)))

            # Add residual connection (simplified)
            residual = [(e + w) / 2.0 for e, w in zip(emb, weighted)]
            encoded.append(residual)

        return encoded


# =========================================================================
# Factory
# =========================================================================

def create_content_engagement_predictor(
    embed_dim: int = 64,
    data_dir: Optional[str] = None,
    model_version: str = "tribev2-adapted-v1"
) -> ContentEngagementPredictor:
    """Factory function for ContentEngagementPredictor."""
    return ContentEngagementPredictor(
        embed_dim=embed_dim,
        model_version=model_version,
        data_dir=data_dir
    )
