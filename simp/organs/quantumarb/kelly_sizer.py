"""
Kelly Criterion Position Sizing — T24
=====================================
Computes optimal position size using Kelly criterion and fractional Kelly.

Kelly formula: f* = (bp - q) / b
  b = net odds received (decimal - 1)
  p = probability of winning (from ConfidenceCalibrator T12)
  q = 1 - p

Fractional Kelly: 25% of full Kelly for safety.
"""

from __future__ import annotations
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("kelly_sizer")


@dataclass
class KellyRecommendation:
    kelly_fraction: float        # Full Kelly: 0.0 to 1.0+
    fractional_kelly: float     # 25% of full Kelly
    max_safe_position_usd: float
    expected_growth_rate: float  # G per bet (log return)
    confidence: float           # p from calibrator
    odds: float                # b (net decimal - 1)
    signal_type: str
    kelly_grade: str           # "A" (>0.2), "B" (0.1-0.2), "C" (0.05-0.1), "D" (<0.05)

    @property
    def is_bet(self) -> bool:
        return self.fractional_kelly > 0.001 and self.kelly_fraction > 0.0

    @property
    def grade(self) -> str:
        return self.kelly_grade


@dataclass
class KellyConfig:
    fractional_kelly_pct: float = 25.0    # Use 25% of full Kelly
    max_kelly_fraction: float = 0.25        # Cap at 25% of portfolio
    min_kelly_fraction: float = 0.001        # Min 0.1% to avoid dust
    risk_free_rate: float = 0.05             # Annual RF rate for Sharpe


class KellySizer:
    """
    Kelly criterion position sizer.

    Usage:
        sizer = KellySizer(config=KellyConfig())

        rec = sizer.compute_kelly(
            confidence=0.75,
            odds_decimal=1.05,
            opportunity_usd=10.0,
            portfolio_value=100.0,
            signal_type="cross_exchange"
        )
        if rec.is_bet:
            position = sizer.get_position_override(...)
    """

    def __init__(self, config: Optional[KellyConfig] = None, calibrator=None):
        self.config = config or KellyConfig()
        self.calibrator = calibrator
        self._log_path = Path("data/kelly_computations.jsonl")

    def compute_full_kelly(self, p: float, odds_decimal: float) -> float:
        """
        Compute full Kelly fraction: f* = (bp - q) / b

        Returns 0.0 if negative expected value.
        """
        if p <= 0 or p >= 1:
            return 0.0
        b = odds_decimal - 1.0  # net odds
        q = 1.0 - p
        if b <= 0:
            return 0.0  # no odds = no bet (or worse)
        f_star = (b * p - q) / b
        return max(0.0, f_star)

    def compute_fractional_kelly(self, f_full: float) -> float:
        """Apply fractional Kelly (25% default)."""
        frac = self.config.fractional_kelly_pct / 100.0
        return f_full * frac

    def compute_expected_growth(self, p: float, b: float, f: float) -> float:
        """
        Expected log return per bet: G = p*ln(1+b*f) + q*ln(1-f)
        Kelly maximizes this.
        """
        if p <= 0 or p >= 1 or f <= 0 or f >= 1:
            return 0.0
        q = 1.0 - p
        try:
            G = p * math.log(1 + b * f) + q * math.log(1 - f)
            return G
        except (ValueError, OverflowError):
            return 0.0

    def _grade(self, f_frac: float) -> str:
        if f_frac >= 0.20:
            return "A"
        elif f_frac >= 0.10:
            return "B"
        elif f_frac >= 0.05:
            return "C"
        return "D"

    def compute_kelly(
        self,
        confidence: float,
        odds_decimal: float,
        opportunity_usd: float,
        portfolio_value: float,
        signal_type: str = "unknown"
    ) -> KellyRecommendation:
        """
        Compute Kelly recommendation for an opportunity.
        """
        # Step 1: full Kelly
        f_full = self.compute_full_kelly(confidence, odds_decimal)

        # Step 2: fractional Kelly
        f_frac = self.compute_fractional_kelly(f_full)

        # Step 3: cap at max fraction of portfolio
        max_fraction = self.config.max_kelly_fraction
        f_capped = min(f_frac, max_fraction)

        # Step 4: max position in USD
        max_usd = f_capped * portfolio_value
        max_safe = min(max_usd, opportunity_usd)  # never larger than opportunity

        # Step 5: expected growth rate
        b = odds_decimal - 1.0
        growth = self.compute_expected_growth(confidence, b, f_capped)

        # Step 6: clamp to minimum
        if f_capped < self.config.min_kelly_fraction:
            max_safe = 0.0
            f_capped = 0.0

        rec = KellyRecommendation(
            kelly_fraction=round(f_full, 6),
            fractional_kelly=round(f_capped, 6),
            max_safe_position_usd=round(max_safe, 2),
            expected_growth_rate=round(growth, 8),
            confidence=confidence,
            odds=b,
            signal_type=signal_type,
            kelly_grade=self._grade(f_frac),
        )

        self._log(rec)
        return rec

    def get_position_override(
        self,
        opportunity_usd: float,
        portfolio_value: float,
        default_risk_budget_usd: float,
        confidence: float,
        odds_decimal: float,
        signal_type: str
    ) -> float:
        """
        Main entry point for quantum_decision_agent.
        Returns Kelly-adjusted position size in USD.

        Logic:
          - If Kelly says 0 (negative EV): return 0
          - If Kelly < default: use Kelly
          - If Kelly > default: use Kelly (Kelly overrides budget)
          - Cap at opportunity size
        """
        rec = self.compute_kelly(
            confidence=confidence,
            odds_decimal=odds_decimal,
            opportunity_usd=opportunity_usd,
            portfolio_value=portfolio_value,
            signal_type=signal_type,
        )

        if not rec.is_bet:
            return 0.0

        # Use Kelly recommendation but cap at opportunity size
        return max(0.0, min(rec.max_safe_position_usd, opportunity_usd))

    def _log(self, rec: KellyRecommendation) -> None:
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "signal_type": rec.signal_type,
                    "confidence": rec.confidence,
                    "odds": rec.odds,
                    "kelly_fraction": rec.kelly_fraction,
                    "fractional_kelly": rec.fractional_kelly,
                    "max_safe_usd": rec.max_safe_position_usd,
                    "growth_rate": rec.expected_growth_rate,
                    "grade": rec.kelly_grade,
                }) + "\n")
        except Exception as e:
            log.debug(f"Kelly log error: {e}")
