"""
Time-Weighted Position Sizing — T24
====================================
Kelly + exposure limits should decay for stale signals. Add signal age
weighting to confidence scoring.

When a signal is older than the freshness threshold, its Kelly fraction
is decayed exponentially so that stale signals trade smaller sizes
(or not at all).

Features:
  - Signal age tracking per opportunity
  - Exponential decay function (half-life configurable)
  - Integration with Kelly sizer for decayed position sizing
  - Stale signal detection and alerting
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("time_weighted_sizing")


@dataclass
class TimeWeightConfig:
    """Configuration for time-weighted position sizing."""
    signal_freshness_seconds: float = 30.0      # Signal is "fresh" for 30 seconds
    half_life_seconds: float = 15.0              # Confidence halves every 15s after freshness
    max_signal_age_seconds: float = 300.0        # Signal is invalid after 5 minutes
    stale_confidence_multiplier: float = 0.0     # What to multiply confidence by when stale
    decay_min_multiplier: float = 0.05           # Floor on decay multiplier


class TimeWeightedPositionSizer:
    """
    Applies time-based decay to position sizing.

    The core formula:
      if age <= freshness: multiplier = 1.0
      if freshness < age < max_age: multiplier = 0.5 ^ ((age - freshness) / half_life)
      if age >= max_age: multiplier = 0.0

    Usage:
        sizer = TimeWeightedPositionSizer()
        adj_conf = sizer.adjust_confidence(original_confidence, signal_timestamp)
        adj_kelly = sizer.adjust_kelly_fraction(0.25, signal_timestamp)
    """

    def __init__(self, config: Optional[TimeWeightConfig] = None):
        self.config = config or TimeWeightConfig()
        log.info(
            "TimeWeightedPositionSizer initialized (freshness=%.0fs, half_life=%.0fs, max_age=%.0fs)",
            self.config.signal_freshness_seconds,
            self.config.half_life_seconds,
            self.config.max_signal_age_seconds,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def compute_multiplier(self, signal_timestamp: float) -> float:
        """
        Compute the time decay multiplier for a signal.

        Args:
            signal_timestamp: Unix timestamp when the signal was generated

        Returns:
            Multiplier between 0.0 and 1.0
        """
        age = time.time() - signal_timestamp

        if age < 0:
            # Signal from the future — treat as fresh
            return 1.0

        if age <= self.config.signal_freshness_seconds:
            return 1.0

        if age >= self.config.max_signal_age_seconds:
            return 0.0

        # Exponential decay in the stale zone
        elapsed_stale = age - self.config.signal_freshness_seconds
        half_lives = elapsed_stale / self.config.half_life_seconds
        multiplier = 0.5 ** half_lives

        return max(self.config.decay_min_multiplier, multiplier)

    def is_stale(self, signal_timestamp: float) -> bool:
        """Check if a signal has exceeded max age."""
        return (time.time() - signal_timestamp) >= self.config.max_signal_age_seconds

    def is_fresh(self, signal_timestamp: float) -> bool:
        """Check if a signal is still within the freshness window."""
        return (time.time() - signal_timestamp) <= self.config.signal_freshness_seconds

    def adjust_confidence(
        self,
        original_confidence: float,
        signal_timestamp: float,
    ) -> float:
        """
        Adjust confidence score by time multiplier.

        Args:
            original_confidence: Base confidence (0.0 to 1.0)
            signal_timestamp: Unix timestamp of signal

        Returns:
            Adjusted confidence (0.0 to 1.0), may be 0 if stale
        """
        multiplier = self.compute_multiplier(signal_timestamp)
        if multiplier <= 0.0:
            return 0.0
        adjusted = original_confidence * multiplier
        return min(1.0, max(0.0, adjusted))

    def adjust_kelly_fraction(
        self,
        original_kelly: float,
        signal_timestamp: float,
    ) -> float:
        """
        Adjust Kelly fraction by time multiplier.

        Args:
            original_kelly: Base Kelly fraction (0.0 to 1.0)
            signal_timestamp: Unix timestamp of signal

        Returns:
            Adjusted Kelly fraction (may be 0 if stale)
        """
        multiplier = self.compute_multiplier(signal_timestamp)
        if multiplier <= 0.0:
            return 0.0
        return original_kelly * multiplier

    def compute_position_size(
        self,
        kelly_fraction: float,
        confidence: float,
        bankroll_usd: float,
        signal_timestamp: float,
        max_position_usd: float = float("inf"),
    ) -> Tuple[float, float, str]:
        """
        Compute full time-adjusted position size.

        Args:
            kelly_fraction: Optimal Kelly fraction (0.0 to 1.0)
            confidence: Signal confidence (0.0 to 1.0)
            bankroll_usd: Available capital in USD
            signal_timestamp: Unix timestamp of signal
            max_position_usd: Absolute maximum position size

        Returns:
            Tuple of (position_size_usd, effective_kelly, reason)
        """
        age = time.time() - signal_timestamp
        multiplier = self.compute_multiplier(signal_timestamp)

        if multiplier <= 0.0:
            return (0.0, 0.0, f"signal_stale_age={age:.0f}s_exceeds_max={self.config.max_signal_age_seconds:.0f}s")

        adjusted_confidence = confidence * multiplier
        adjusted_kelly = kelly_fraction * multiplier
        raw_position = bankroll_usd * adjusted_kelly * adjusted_confidence
        position = min(raw_position, max_position_usd)

        if multiplier < 1.0:
            reason = (
                f"decayed_multiplier={multiplier:.4f}_age={age:.0f}s_"
                f"freshness={self.config.signal_freshness_seconds:.0f}s"
            )
        else:
            reason = "fresh_signal"

        return (round(position, 2), round(adjusted_kelly, 6), reason)

    def get_signal_age_seconds(self, signal_timestamp: float) -> float:
        """Get the age of a signal in seconds."""
        return max(0.0, time.time() - signal_timestamp)

    def get_signal_status(self, signal_timestamp: float) -> Dict[str, Any]:
        """
        Get the full status of a signal including age and multiplier.

        Returns dict with: age_seconds, freshness_seconds, half_life,
        multiplier, is_fresh, is_stale, max_age_seconds.
        """
        age = self.get_signal_age_seconds(signal_timestamp)
        multiplier = self.compute_multiplier(signal_timestamp)
        return {
            "age_seconds": round(age, 1),
            "freshness_seconds": self.config.signal_freshness_seconds,
            "half_life_seconds": self.config.half_life_seconds,
            "multiplier": round(multiplier, 6),
            "is_fresh": self.is_fresh(signal_timestamp),
            "is_stale": self.is_stale(signal_timestamp),
            "max_age_seconds": self.config.max_signal_age_seconds,
        }


# ── Module-level singleton ──────────────────────────────────────────────

TIME_WEIGHTED_SIZER = TimeWeightedPositionSizer()
