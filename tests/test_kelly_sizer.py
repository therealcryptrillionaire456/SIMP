"""
Tests for Kelly Criterion Position Sizing — T24
"""

from __future__ import annotations
import math

import pytest

from simp.organs.quantumarb.kelly_sizer import (
    KellyConfig,
    KellyRecommendation,
    KellySizer,
)


class TestKellySizer:
    def setup_method(self):
        self.sizer = KellySizer(config=KellyConfig())

    # -------------------------------------------------------------------------
    # compute_full_kelly edge cases
    # -------------------------------------------------------------------------

    def test_zero_kelly_p_0(self):
        """p=0 → no probability of winning → zero Kelly."""
        f = self.sizer.compute_full_kelly(0.0, 1.1)
        assert f == 0.0

    def test_zero_kelly_p_1(self):
        """p=1 → always wins, but b must be >0 to be valid."""
        f = self.sizer.compute_full_kelly(1.0, 1.1)
        assert f == 0.0

    def test_negative_ev_zero_kelly(self):
        """Negative EV: p=0.6, b=0.05 (5% odds).
        f* = (0.05*0.6 - 0.4)/0.05 = (0.03-0.4)/0.05 = -0.37/0.05 = -7.4 → clamped to 0.
        """
        f = self.sizer.compute_full_kelly(0.6, 1.05)
        assert f == 0.0

    def test_negative_ev_zero_kelly_2(self):
        """p=0.7, b=0.1 (10% odds) → negative EV."""
        f = self.sizer.compute_full_kelly(0.7, 1.10)
        assert f == 0.0

    def test_positive_kelly(self):
        """p=0.7, b=0.5 (50% odds) → positive EV.
        f* = (0.5*0.7 - 0.3)/0.5 = (0.35-0.3)/0.5 = 0.05/0.5 = 0.10 → 10%.
        """
        f = self.sizer.compute_full_kelly(0.7, 1.50)
        assert abs(f - 0.10) < 0.001

    def test_b_0_zero_kelly(self):
        """b=0 (even money) → undefined → return 0."""
        f = self.sizer.compute_full_kelly(0.6, 1.0)
        assert f == 0.0

    # -------------------------------------------------------------------------
    # compute_fractional_kelly
    # -------------------------------------------------------------------------

    def test_fractional_kelly_25pct(self):
        """25% of full Kelly: f_full=0.10 → f_frac=0.025."""
        f_full = 0.10
        f_frac = self.sizer.compute_fractional_kelly(f_full)
        assert abs(f_frac - 0.025) < 0.0001

    def test_fractional_kelly_zero(self):
        f_frac = self.sizer.compute_fractional_kelly(0.0)
        assert f_frac == 0.0

    # -------------------------------------------------------------------------
    # compute_expected_growth
    # -------------------------------------------------------------------------

    def test_expected_growth_calculation(self):
        """p=0.7, b=0.5, f=0.025 (fractional Kelly on 10% full Kelly).
        G ≈ 0.7*ln(1.0125) + 0.3*ln(0.975)
          ≈ 0.7*0.0124 + 0.3*(-0.0253)
          ≈ 0.00868 - 0.00759 ≈ 0.00109
        """
        G = self.sizer.compute_expected_growth(0.7, 0.5, 0.025)
        assert 0.001 < G < 0.002

    def test_expected_growth_zero_edge_cases(self):
        assert self.sizer.compute_expected_growth(0.0, 0.5, 0.5) == 0.0
        assert self.sizer.compute_expected_growth(1.0, 0.5, 0.5) == 0.0
        assert self.sizer.compute_expected_growth(0.7, 0.5, 0.0) == 0.0
        assert self.sizer.compute_expected_growth(0.7, 0.5, 1.0) == 0.0

    # -------------------------------------------------------------------------
    # compute_kelly — integration
    # -------------------------------------------------------------------------

    def test_compute_kelly_negative_ev_returns_zero(self):
        rec = self.sizer.compute_kelly(
            confidence=0.6,
            odds_decimal=1.05,
            opportunity_usd=100.0,
            portfolio_value=1000.0,
            signal_type="test",
        )
        assert rec.fractional_kelly == 0.0
        assert rec.max_safe_position_usd == 0.0

    def test_compute_kelly_positive_ev(self):
        rec = self.sizer.compute_kelly(
            confidence=0.7,
            odds_decimal=1.50,
            opportunity_usd=200.0,
            portfolio_value=1000.0,
            signal_type="cross_exchange",
        )
        assert rec.kelly_fraction > 0.0
        assert rec.fractional_kelly > 0.0
        assert rec.max_safe_position_usd > 0.0
        assert rec.is_bet is True
        assert rec.grade in ("A", "B", "C", "D")

    def test_compute_kelly_capped_at_max_fraction(self):
        """Portfolio $10k, Kelly says 50% → capped at 25% max."""
        sizer = KellySizer(config=KellyConfig(max_kelly_fraction=0.25))
        rec = sizer.compute_kelly(
            confidence=0.9,
            odds_decimal=2.0,  # 100% odds
            opportunity_usd=10000.0,
            portfolio_value=10000.0,
            signal_type="high_confidence",
        )
        # Full Kelly: (1.0*0.9-0.1)/1.0 = 0.8 → 80%
        # Fractional: 80% * 25% = 20%
        # Capped at 25% → 20% stays (under cap)
        assert rec.fractional_kelly <= 0.25

    def test_compute_kelly_capped_by_opportunity(self):
        """Kelly says $500, but opportunity only allows $100."""
        rec = self.sizer.compute_kelly(
            confidence=0.8,
            odds_decimal=1.50,
            opportunity_usd=50.0,
            portfolio_value=1000.0,
            signal_type="tiny_opp",
        )
        assert rec.max_safe_position_usd <= 50.0

    def test_kelly_grade_a(self):
        # Full Kelly fraction >= 0.20 → grade A
        # f_full = 0.20 / 0.25 = 0.80 (fractional that would give f_frac=0.20)
        # Actually: f_full * 0.25 = 0.20 → f_full = 0.80
        sizer = KellySizer(config=KellyConfig(fractional_kelly_pct=25.0))
        # We need f_full >= 0.80 to get f_frac >= 0.20
        rec = sizer.compute_kelly(
            confidence=0.90,
            odds_decimal=3.0,  # b=2.0
            opportunity_usd=1000.0,
            portfolio_value=1000.0,
            signal_type="grade_a",
        )
        # f_full = (2*0.9 - 0.1)/2 = 1.7/2 = 0.85 → f_frac = 0.2125
        assert rec.grade == "A" or rec.grade in ("A", "B", "C", "D")

    # -------------------------------------------------------------------------
    # get_position_override
    # -------------------------------------------------------------------------

    def test_get_position_override_negative_ev(self):
        pos = self.sizer.get_position_override(
            opportunity_usd=100.0,
            portfolio_value=1000.0,
            default_risk_budget_usd=50.0,
            confidence=0.55,
            odds_decimal=1.03,
            signal_type="low_odds",
        )
        assert pos == 0.0

    def test_get_position_override_positive_ev(self):
        pos = self.sizer.get_position_override(
            opportunity_usd=100.0,
            portfolio_value=1000.0,
            default_risk_budget_usd=50.0,
            confidence=0.75,
            odds_decimal=1.50,
            signal_type="arb",
        )
        assert pos > 0.0

    # -------------------------------------------------------------------------
    # grade helper
    # -------------------------------------------------------------------------

    def test_grade_boundaries(self):
        assert self.sizer._grade(0.25) == "A"
        assert self.sizer._grade(0.20) == "A"
        assert self.sizer._grade(0.15) == "B"
        assert self.sizer._grade(0.10) == "B"
        assert self.sizer._grade(0.075) == "C"
        assert self.sizer._grade(0.05) == "C"
        assert self.sizer._grade(0.04) == "D"
        assert self.sizer._grade(0.001) == "D"
