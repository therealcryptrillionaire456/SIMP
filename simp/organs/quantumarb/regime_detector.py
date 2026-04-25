"""
Market Regime Detector — T23
============================
Detects market regime using ADX, Bollinger Bandwidth, ATR, RSI.
Used by quantum_decision_agent to filter signals during dangerous regimes.

Regimes: UNKNOWN | RANGING | TRENDING_UP | TRENDING_DOWN | HIGH_VOL | CRISIS
"""

from __future__ import annotations

import json
import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("regime_detector")


class MarketRegime(Enum):
    """Market regime classification."""
    UNKNOWN = "unknown"
    RANGING = "ranging"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    HIGH_VOL = "high_vol"
    CRISIS = "crisis"


@dataclass
class RegimeConfig:
    """Configuration for regime detection thresholds."""
    adx_trending_threshold: float = 25.0
    adx_strong_threshold: float = 40.0
    bb_bandwidth_multiplier: float = 2.0
    atr_multiplier: float = 2.0
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    lookback_period: int = 200


@dataclass
class RegimeResult:
    """Result of regime detection for a symbol."""
    regime: MarketRegime
    confidence: float
    adx: float
    rsi: float
    atr_ratio: float
    bb_bandwidth_ratio: float
    actions: Dict


class RegimeDetector:
    """
    Detects market regime using technical indicators.
    
    Uses ADX for trend strength, RSI for overbought/oversold,
    ATR for volatility, and Bollinger Bandwidth for range expansion.
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self._prices: Dict[str, List[float]] = {}
        self._highs: Dict[str, List[float]] = {}
        self._lows: Dict[str, List[float]] = {}
        self._history_file = Path("data/regime_history.jsonl")
        self._adx_cache: Dict[str, float] = {}
        self._rsi_cache: Dict[str, float] = {}

    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Add new price observations. Maintains lookback window.
        
        Parameters
        ----------
        prices : Dict[str, float]
            Dictionary mapping symbol to current price.
        """
        for sym, px in prices.items():
            if sym not in self._prices:
                self._prices[sym] = []
                self._highs[sym] = []
                self._lows[sym] = []
            self._prices[sym].append(px)
            self._highs[sym].append(px)
            self._lows[sym].append(px)
            max_keep = self.config.lookback_period
            if len(self._prices[sym]) > max_keep:
                self._prices[sym] = self._prices[sym][-max_keep:]
                self._highs[sym] = self._highs[sym][-max_keep:]
                self._lows[sym] = self._lows[sym][-max_keep:]
            # Invalidate caches when prices update
            self._adx_cache.pop(sym, None)
            self._rsi_cache.pop(sym, None)

    def update_ohlc(
        self,
        symbol: str,
        high: float,
        low: float,
        close: float,
    ) -> None:
        """
        Add OHLC data point for a symbol.
        
        Parameters
        ----------
        symbol : str
            Trading pair symbol (e.g., "BTC-USD").
        high : float
            Period high price.
        low : float
            Period low price.
        close : float
            Period close price.
        """
        if symbol not in self._prices:
            self._prices[symbol] = []
            self._highs[symbol] = []
            self._lows[symbol] = []
        self._highs[symbol].append(high)
        self._lows[symbol].append(low)
        self._prices[symbol].append(close)
        max_keep = self.config.lookback_period
        if len(self._prices[symbol]) > max_keep:
            self._prices[symbol] = self._prices[symbol][-max_keep:]
            self._highs[symbol] = self._highs[symbol][-max_keep:]
            self._lows[symbol] = self._lows[symbol][-max_keep:]
        self._adx_cache.pop(symbol, None)
        self._rsi_cache.pop(symbol, None)

    def _trange(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> List[float]:
        """
        True Range: max of (H-L), |H-PC|, |L-PC|
        
        Parameters
        ----------
        highs : List[float]
            List of high prices.
        lows : List[float]
            List of low prices.
        closes : List[float]
            List of close prices.
            
        Returns
        -------
        List[float]
            List of true range values.
        """
        trs = []
        for i in range(len(highs)):
            h, l = highs[i], lows[i]
            pc = closes[i - 1] if i > 0 else closes[i]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return trs

    def _smooth(self, vals: List[float], period: int) -> List[float]:
        """
        Wilder smoothing (exponential moving average).
        
        Uses alpha = 1/period for Wilder's smoothing method.
        
        Parameters
        ----------
        vals : List[float]
            Values to smooth.
        period : int
            Smoothing period.
            
        Returns
        -------
        List[float]
            Smoothed values.
        """
        if not vals:
            return []
        alpha = 1.0 / period
        smoothed = [vals[0]]
        for v in vals[1:]:
            smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
        return smoothed

    def _compute_adx(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> float:
        """
        Average Directional Index.
        
        Measures trend strength without regard to direction.
        Values above 25 indicate trending market.
        Values above 40 indicate strong trend.
        
        Parameters
        ----------
        highs : List[float]
            List of high prices.
        lows : List[float]
            List of low prices.
        closes : List[float]
            List of close prices.
        period : int
            ADX period (default 14).
            
        Returns
        -------
        float
            ADX value between 0 and 100.
        """
        if len(closes) < period + 1:
            return 0.0

        # Compute +DM, -DM, TR
        trs = self._trange(highs, lows, closes)
        plus_dm: List[float] = []
        minus_dm: List[float] = []

        for i in range(1, len(highs)):
            h_diff = highs[i] - highs[i - 1]
            l_diff = lows[i - 1] - lows[i]
            pdm = h_diff if h_diff > l_diff and h_diff > 0 else 0.0
            mdm = l_diff if l_diff > h_diff and l_diff > 0 else 0.0
            plus_dm.append(pdm)
            minus_dm.append(mdm)

        if not trs[1:]:
            return 0.0

        # Smooth using Wilder's method
        period_tr = self._smooth(trs[1:], period)
        period_plus = self._smooth(plus_dm, period)
        period_minus = self._smooth(minus_dm, period)

        if not period_tr or period_tr[-1] == 0:
            return 0.0

        plus_di = 100 * period_plus[-1] / period_tr[-1]
        minus_di = 100 * period_minus[-1] / period_tr[-1]

        if plus_di + minus_di == 0:
            return 0.0

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # ADX is smoothed DX (use same period)
        adx_vals = self._smooth([dx], period * 3)  # Extra smoothing for ADX
        return adx_vals[-1] if adx_vals else 0.0

    def compute_adx(self, symbol: str, period: int = 14) -> float:
        """
        Compute ADX for a symbol.
        
        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        period : int
            ADX period (default 14).
            
        Returns
        -------
        float
            ADX value.
        """
        if symbol in self._adx_cache:
            return self._adx_cache[symbol]
        adx = self._compute_adx(
            self._highs.get(symbol, []),
            self._lows.get(symbol, []),
            self._prices.get(symbol, []),
            period,
        )
        self._adx_cache[symbol] = adx
        return adx

    def compute_rsi(self, symbol: str, period: int = 14) -> float:
        """
        Compute Relative Strength Index.
        
        RSI above 70 indicates overbought.
        RSI below 30 indicates oversold.
        
        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        period : int
            RSI period (default 14).
            
        Returns
        -------
        float
            RSI value between 0 and 100.
        """
        if symbol in self._rsi_cache:
            return self._rsi_cache[symbol]
        
        prices = self._prices.get(symbol, [])
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d for d in deltas[-period:] if d > 0]
        losses = [-d for d in deltas[-period:] if d < 0]

        avg_gain = statistics.mean(gains) if gains else 0.0
        avg_loss = statistics.mean(losses) if losses else 0.0

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        self._rsi_cache[symbol] = rsi
        return rsi

    def compute_bollinger_bandwidth(self, symbol: str, period: int = 20) -> float:
        """
        Compute Bollinger Bandwidth as percentage.
        
        Bandwidth = (Upper Band - Lower Band) / Middle Band * 100
        
        Higher bandwidth indicates higher volatility.
        
        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        period : int
            Bollinger period (default 20).
            
        Returns
        -------
        float
            Bandwidth as percentage.
        """
        prices = self._prices.get(symbol, [])
        if len(prices) < period:
            return 0.0

        recent = prices[-period:]
        mid = statistics.mean(recent)
        std = statistics.stdev(recent) if len(recent) > 1 else 0

        if mid == 0:
            return 0.0

        # 2 standard deviation bands as percentage of mid
        bandwidth = (2 * 1.96 * std) / mid * 100
        return bandwidth

    def compute_atr_ratio(self, symbol: str, period: int = 14) -> float:
        """
        Compute ATR ratio (current ATR / average ATR).
        
        Ratio above 2.0 indicates elevated volatility (crisis).
        
        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        period : int
            ATR period (default 14).
            
        Returns
        -------
        float
            ATR ratio (current / average).
        """
        highs = self._highs.get(symbol, [])
        lows = self._lows.get(symbol, [])
        closes = self._prices.get(symbol, [])

        if len(closes) < period + 1:
            return 1.0

        trs = self._trange(highs, lows, closes)
        if len(trs) < period:
            return 1.0

        current_atr = statistics.mean(trs[-period:])
        avg_atr = statistics.mean(trs) if trs else 1

        if avg_atr == 0:
            return 1.0

        return current_atr / avg_atr

    def detect_regime(self, symbol: str) -> RegimeResult:
        """
        Classify current market regime for a symbol.
        
        Classification logic:
        - CRISIS: ATR ratio >= atr_multiplier (elevated volatility)
        - HIGH_VOL: Bollinger bandwidth >= bb_bandwidth_multiplier
        - TRENDING: ADX >= adx_strong_threshold (with direction from RSI)
        - RANGING: ADX below trend threshold
        
        Parameters
        ----------
        symbol : str
            Trading pair symbol.
            
        Returns
        -------
        RegimeResult
            Regime classification with confidence and recommended actions.
        """
        if len(self._prices.get(symbol, [])) < 20:
            return RegimeResult(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                adx=0.0,
                rsi=50.0,
                atr_ratio=1.0,
                bb_bandwidth_ratio=0.0,
                actions={
                    "position_reduction_pct": 0.0,
                    "confidence_multiplier": 1.5,
                },
            )

        adx = self.compute_adx(symbol)
        rsi = self.compute_rsi(symbol)
        atr_ratio = self.compute_atr_ratio(symbol)
        bb_ratio = self.compute_bollinger_bandwidth(symbol) / 5.0  # Normalize
        cfg = self.config

        # Classification logic
        if atr_ratio >= cfg.atr_multiplier:
            regime = MarketRegime.CRISIS
        elif bb_ratio >= cfg.bb_bandwidth_multiplier:
            regime = MarketRegime.HIGH_VOL
        elif adx >= cfg.adx_strong_threshold:
            if rsi > 55:
                regime = MarketRegime.TRENDING_UP
            elif rsi < 45:
                regime = MarketRegime.TRENDING_DOWN
            else:
                regime = MarketRegime.TRENDING_UP  # Default to up on strong ADX
        elif adx >= cfg.adx_trending_threshold:
            if rsi > 52:
                regime = MarketRegime.TRENDING_UP
            elif rsi < 48:
                regime = MarketRegime.TRENDING_DOWN
            else:
                regime = MarketRegime.RANGING
        else:
            regime = MarketRegime.RANGING

        actions = self.get_regime_action(regime)
        confidence = min(1.0, adx / 40.0)

        # Write to history
        self._write_history(symbol, regime, adx, rsi, atr_ratio, bb_ratio)

        return RegimeResult(
            regime=regime,
            confidence=confidence,
            adx=adx,
            rsi=rsi,
            atr_ratio=atr_ratio,
            bb_bandwidth_ratio=bb_ratio,
            actions=actions,
        )

    def get_regime_action(self, regime: MarketRegime) -> Dict:
        """
        Get recommended actions for a regime.
        
        Parameters
        ----------
        regime : MarketRegime
            Detected market regime.
            
        Returns
        -------
        Dict
            Action recommendations including position_reduction_pct
            and confidence_multiplier.
        """
        return {
            MarketRegime.TRENDING_UP: {
                "position_reduction_pct": 0.0,
                "confidence_multiplier": 1.0,
            },
            MarketRegime.TRENDING_DOWN: {
                "position_reduction_pct": 0.25,
                "confidence_multiplier": 1.0,
            },
            MarketRegime.RANGING: {
                "position_reduction_pct": 0.0,
                "confidence_multiplier": 1.0,
            },
            MarketRegime.HIGH_VOL: {
                "position_reduction_pct": 0.5,
                "confidence_multiplier": 2.0,
            },
            MarketRegime.CRISIS: {
                "position_reduction_pct": 1.0,
                "confidence_multiplier": 99.0,
            },
            MarketRegime.UNKNOWN: {
                "position_reduction_pct": 0.5,
                "confidence_multiplier": 1.5,
            },
        }.get(
            regime,
            {"position_reduction_pct": 0.0, "confidence_multiplier": 1.0},
        )

    def _write_history(
        self,
        symbol: str,
        regime: MarketRegime,
        adx: float,
        rsi: float,
        atr: float,
        bb: float,
    ) -> None:
        """
        Write regime detection result to history file.
        
        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        regime : MarketRegime
            Detected regime.
        adx : float
            ADX value.
        rsi : float
            RSI value.
        atr : float
            ATR ratio.
        bb : float
            Bollinger bandwidth ratio.
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "regime": regime.value,
            "adx": round(adx, 2),
            "rsi": round(rsi, 2),
            "atr_ratio": round(atr, 4),
            "bb_ratio": round(bb, 4),
        }
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log.debug("Could not write regime history: %s", e)

    def get_regime_summary(self, symbols: List[str]) -> Dict[str, RegimeResult]:
        """
        Get regime classification for multiple symbols.
        
        Parameters
        ----------
        symbols : List[str]
            List of trading pair symbols.
            
        Returns
        -------
        Dict[str, RegimeResult]
            Dictionary mapping symbol to regime result.
        """
        return {sym: self.detect_regime(sym) for sym in symbols}

    def reset(self, symbol: Optional[str] = None) -> None:
        """
        Reset cached data for a symbol or all symbols.
        
        Parameters
        ----------
        symbol : Optional[str]
            Symbol to reset. If None, resets all.
        """
        if symbol:
            self._prices.pop(symbol, None)
            self._highs.pop(symbol, None)
            self._lows.pop(symbol, None)
            self._adx_cache.pop(symbol, None)
            self._rsi_cache.pop(symbol, None)
        else:
            self._prices.clear()
            self._highs.clear()
            self._lows.clear()
            self._adx_cache.clear()
            self._rsi_cache.clear()
