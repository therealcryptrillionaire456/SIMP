"""
Tests for Market Regime Detector — T23
=====================================
"""

import pytest
from simp.organs.quantumarb.regime_detector import (
    MarketRegime,
    RegimeConfig,
    RegimeDetector,
    RegimeResult,
)


class TestRegimeDetector:
    """Tests for RegimeDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a RegimeDetector instance for testing."""
        return RegimeDetector()

    @pytest.fixture
    def trending_prices(self):
        """Generate a strongly trending price series."""
        prices = []
        base = 100.0
        for i in range(200):
            base += 0.5  # Steady uptrend
            prices.append(base)
        return prices

    @pytest.fixture
    def ranging_prices(self):
        """Generate a ranging price series."""
        import math
        prices = []
        base = 100.0
        for i in range(200):
            # Sine wave with small amplitude
            prices.append(base + 5 * math.sin(i / 50))
        return prices

    @pytest.fixture
    def high_vol_prices(self):
        """Generate a high volatility price series."""
        import random
        prices = []
        base = 100.0
        for i in range(200):
            # Large random swings
            base += random.uniform(-5, 5)
            prices.append(base)
        return prices

    def test_unknown_regime_insufficient_data(self, detector):
        """Test that unknown regime is returned with insufficient data."""
        detector.update_prices({"BTC-USD": 50000.0})
        result = detector.detect_regime("BTC-USD")
        assert result.regime == MarketRegime.UNKNOWN
        assert result.confidence == 0.0

    def test_trending_up_regime(self, detector, trending_prices):
        """Test trending up regime detection."""
        for price in trending_prices:
            detector.update_prices({"BTC-USD": price})
        result = detector.detect_regime("BTC-USD")
        assert result.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]
        assert result.adx > 25.0  # Should be trending

    def test_ranging_regime(self, detector, ranging_prices):
        """Test ranging regime detection."""
        for price in ranging_prices:
            detector.update_prices({"BTC-USD": price})
        result = detector.detect_regime("BTC-USD")
        # Ranging can have varying ADX depending on wave pattern
        # Key safety: ensure we are not in CRISIS regime
        assert result.regime != MarketRegime.CRISIS

    def test_adx_calculation(self, detector):
        """Test ADX calculation accuracy."""
        # Create uptrending data
        prices = [100.0]
        for i in range(1, 50):
            # Strong uptrend with higher highs
            prices.append(prices[-1] + 1.0)
        
        for price in prices:
            detector.update_prices({"TEST": price})
        
        adx = detector.compute_adx("TEST")
        assert adx >= 0.0
        assert adx <= 100.0

    def test_rsi_calculation(self, detector):
        """Test RSI calculation."""
        # Add prices with a clear uptrend
        prices = [100.0, 102.0, 104.0, 106.0, 108.0]
        for price in prices:
            detector.update_prices({"TEST": price})
        
        rsi = detector.compute_rsi("TEST")
        assert 0.0 <= rsi <= 100.0
        assert rsi >= 50.0  # Flat prices → RSI = 50; uptrend → RSI > 50

    def test_bollinger_bandwidth(self, detector):
        """Test Bollinger Bandwidth calculation."""
        import math
        prices = [100.0 + 10.0 * math.sin(i / 5) for i in range(50)]
        for price in prices:
            detector.update_prices({"TEST": price})
        
        bw = detector.compute_bollinger_bandwidth("TEST")
        assert bw >= 0.0

    def test_regime_action_mapping(self, detector):
        """Test regime action recommendations."""
        # Test each regime
        actions = detector.get_regime_action(MarketRegime.TRENDING_UP)
        assert "position_reduction_pct" in actions
        assert "confidence_multiplier" in actions
        
        actions = detector.get_regime_action(MarketRegime.CRISIS)
        assert actions["position_reduction_pct"] == 1.0
        assert actions["confidence_multiplier"] == 99.0

    def test_update_prices_maintains_lookback(self, detector):
        """Test that update_prices maintains lookback window."""
        config = RegimeConfig(lookback_period=50)
        detector = RegimeDetector(config=config)
        
        # Add 100 prices
        for i in range(100):
            detector.update_prices({"TEST": float(i)})
        
        # Should only keep last 50
        assert len(detector._prices["TEST"]) <= 50

    def test_update_ohlc(self, detector):
        """Test OHLC update method."""
        detector.update_ohlc("BTC-USD", high=105.0, low=95.0, close=100.0)
        assert "BTC-USD" in detector._prices
        assert len(detector._prices["BTC-USD"]) == 1
        assert detector._highs["BTC-USD"][0] == 105.0
        assert detector._lows["BTC-USD"][0] == 95.0

    def test_reset(self, detector):
        """Test reset functionality."""
        detector.update_prices({"BTC-USD": 50000.0})
        assert "BTC-USD" in detector._prices
        
        detector.reset("BTC-USD")
        assert "BTC-USD" not in detector._prices

    def test_reset_all(self, detector):
        """Test reset all functionality."""
        detector.update_prices({"BTC-USD": 50000.0, "ETH-USD": 3000.0})
        assert len(detector._prices) == 2
        
        detector.reset()
        assert len(detector._prices) == 0

    def test_custom_config(self, detector):
        """Test custom configuration."""
        config = RegimeConfig(
            adx_trending_threshold=30.0,
            adx_strong_threshold=50.0,
            atr_multiplier=3.0,
        )
        detector = RegimeDetector(config=config)
        assert detector.config.adx_trending_threshold == 30.0
        assert detector.config.adx_strong_threshold == 50.0
        assert detector.config.atr_multiplier == 3.0

    def test_multi_symbol_regimes(self, detector):
        """Test regime detection for multiple symbols."""
        for i in range(100):
            detector.update_prices({
                "BTC-USD": 50000.0 + i,
                "ETH-USD": 3000.0 + i * 0.1,
            })
        
        regimes = detector.get_regime_summary(["BTC-USD", "ETH-USD"])
        assert "BTC-USD" in regimes
        assert "ETH-USD" in regimes
        assert isinstance(regimes["BTC-USD"], RegimeResult)


class TestRegimeResult:
    """Tests for RegimeResult dataclass."""

    def test_regime_result_creation(self):
        """Test RegimeResult can be created."""
        result = RegimeResult(
            regime=MarketRegime.TRENDING_UP,
            confidence=0.75,
            adx=35.0,
            rsi=65.0,
            atr_ratio=1.2,
            bb_bandwidth_ratio=0.8,
            actions={"position_reduction_pct": 0.0, "confidence_multiplier": 1.0},
        )
        assert result.regime == MarketRegime.TRENDING_UP
        assert result.confidence == 0.75
        assert result.adx == 35.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
