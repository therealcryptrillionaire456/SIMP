"""
Regime-Aware Strategy Switching — T27
=======================================
Use regime_detector to auto-switch between high-frequency scalping
(trending) and wide-spread harvesting (ranging).

When the market is trending:
  → High-frequency scalping: tighter spreads, faster entries, smaller
     position sizes, quick exits.

When the market is ranging:
  → Wide-spread harvesting: capture larger spreads, fewer trades,
     wider stop-losses, higher position sizes.

When volatility is high / crisis:
  → Defensive mode: reduce or halt trading.

Integrates:
  - RegimeDetector for real-time regime classification
  - TimeWeightedPositionSizer for adjusted sizing
  - TradeExecutor for strategy parameter overrides

Usage:
    switcher = StrategySwitcher(regime_detector=detector)
    strategy = switcher.get_current_strategy()  # Returns strategy config
    params = switcher.get_execution_params("BTC-USD")  # Returns execution overrides
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("strategy_switcher")


class StrategyMode:
    """Strategy mode identifiers."""
    HF_SCALPING = "hf_scalping"            # Trending market
    WIDE_SPREAD_HARVEST = "wide_spread_harvest"  # Ranging market
    BALANCED = "balanced"                  # Default / moderate
    DEFENSIVE = "defensive"                # High volatility / crisis
    PAUSED = "paused"                      # No trading


@dataclass
class StrategyConfig:
    """Full configuration for a strategy mode."""
    mode: str
    min_spread_bps: float                 # Minimum spread to trigger
    max_position_pct: float               # Max position as % of capital
    max_position_usd: float
    position_kelly_multiplier: float      # Kelly fraction multiplier
    max_trades_per_minute: int
    min_trade_interval_seconds: float     # Gap between trades
    stop_loss_bps: float
    take_profit_bps: float
    max_slippage_bps: float
    confidence_threshold: float           # Min confidence to trade
    signal_freshness_seconds: float       # Max age of signal
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Default strategy configurations per regime
DEFAULT_STRATEGIES: Dict[str, StrategyConfig] = {
    StrategyMode.HF_SCALPING: StrategyConfig(
        mode=StrategyMode.HF_SCALPING,
        min_spread_bps=5.0,
        max_position_pct=0.05,
        max_position_usd=50.0,
        position_kelly_multiplier=1.0,
        max_trades_per_minute=6,
        min_trade_interval_seconds=10.0,
        stop_loss_bps=20.0,
        take_profit_bps=30.0,
        max_slippage_bps=10.0,
        confidence_threshold=0.65,
        signal_freshness_seconds=15.0,
        description="High-frequency scalping for trending markets",
    ),
    StrategyMode.WIDE_SPREAD_HARVEST: StrategyConfig(
        mode=StrategyMode.WIDE_SPREAD_HARVEST,
        min_spread_bps=20.0,
        max_position_pct=0.15,
        max_position_usd=150.0,
        position_kelly_multiplier=0.8,
        max_trades_per_minute=2,
        min_trade_interval_seconds=30.0,
        stop_loss_bps=50.0,
        take_profit_bps=100.0,
        max_slippage_bps=20.0,
        confidence_threshold=0.75,
        signal_freshness_seconds=60.0,
        description="Wide-spread harvesting for ranging markets",
    ),
    StrategyMode.BALANCED: StrategyConfig(
        mode=StrategyMode.BALANCED,
        min_spread_bps=10.0,
        max_position_pct=0.10,
        max_position_usd=100.0,
        position_kelly_multiplier=0.9,
        max_trades_per_minute=3,
        min_trade_interval_seconds=20.0,
        stop_loss_bps=30.0,
        take_profit_bps=60.0,
        max_slippage_bps=15.0,
        confidence_threshold=0.70,
        signal_freshness_seconds=30.0,
        description="Balanced default strategy",
    ),
    StrategyMode.DEFENSIVE: StrategyConfig(
        mode=StrategyMode.DEFENSIVE,
        min_spread_bps=50.0,
        max_position_pct=0.02,
        max_position_usd=20.0,
        position_kelly_multiplier=0.2,
        max_trades_per_minute=1,
        min_trade_interval_seconds=120.0,
        stop_loss_bps=15.0,
        take_profit_bps=30.0,
        max_slippage_bps=5.0,
        confidence_threshold=0.90,
        signal_freshness_seconds=10.0,
        description="Defensive: minimal trading, tight stops",
    ),
    StrategyMode.PAUSED: StrategyConfig(
        mode=StrategyMode.PAUSED,
        min_spread_bps=999.0,
        max_position_pct=0.0,
        max_position_usd=0.0,
        position_kelly_multiplier=0.0,
        max_trades_per_minute=0,
        min_trade_interval_seconds=999.0,
        stop_loss_bps=0.0,
        take_profit_bps=0.0,
        max_slippage_bps=0.0,
        confidence_threshold=1.0,
        signal_freshness_seconds=0.0,
        description="PAUSED: no trading allowed",
    ),
}


class StrategySwitcher:
    """
    Switches strategy based on detected market regime.

    Thread-safe. Persists strategy switch events to JSONL.
    """

    def __init__(
        self,
        regime_detector: Any,  # RegimeDetector instance
        strategies: Optional[Dict[str, StrategyConfig]] = None,
        log_dir: str = "data/strategy_switches",
    ):
        self._regime_detector = regime_detector
        self._strategies = strategies or dict(DEFAULT_STRATEGIES)
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._current_mode: str = StrategyMode.BALANCED
        self._switch_history: List[Dict[str, Any]] = []
        self._last_switch_time: float = 0.0
        self._manual_override: Optional[str] = None
        self._override_until: float = 0.0

        self._load_history()

        log.info(
            "StrategySwitcher initialized (strategies=%s)",
            list(self._strategies.keys()),
        )

    # ── Public API ──────────────────────────────────────────────────────

    def evaluate_and_switch(
        self, symbol: str = "BTC-USD"
    ) -> Tuple[str, StrategyConfig]:
        """
        Evaluate the current market regime and switch strategy if needed.

        Args:
            symbol: Symbol to use for regime detection

        Returns:
            Tuple of (mode_name, StrategyConfig)
        """
        # Check manual override
        if self._manual_override and time.time() < self._override_until:
            mode = self._manual_override
            config = self._strategies.get(mode, DEFAULT_STRATEGIES[StrategyMode.BALANCED])
            return mode, config

        # Get regime from detector
        try:
            regime_result = self._regime_detector.detect_regime(symbol)
            regime = regime_result.regime.value
        except Exception as e:
            log.warning("Regime detection failed: %s", e)
            return self._current_mode, self._strategies.get(
                self._current_mode, DEFAULT_STRATEGIES[StrategyMode.BALANCED]
            )

        # Map regime to strategy mode
        new_mode = self._map_regime_to_mode(regime)
        config = self._strategies.get(new_mode, DEFAULT_STRATEGIES[StrategyMode.BALANCED])

        # Switch if changed
        if new_mode != self._current_mode:
            self._switch_mode(new_mode, regime, symbol)

        return new_mode, config

    def get_current_strategy(self) -> StrategyConfig:
        """Get the current strategy config."""
        return self._strategies.get(
            self._current_mode, DEFAULT_STRATEGIES[StrategyMode.BALANCED]
        )

    def get_execution_params(
        self, symbol: str = "BTC-USD"
    ) -> Dict[str, Any]:
        """
        Get execution parameter overrides based on current strategy.

        Returns a dict that can be used to override TradeExecutor params.
        """
        strat = self.get_current_strategy()

        return {
            "max_position_size_usd": strat.max_position_usd,
            "max_slippage_bps": strat.max_slippage_bps,
            "max_trades_per_minute": strat.max_trades_per_minute,
            "min_spread_bps": strat.min_spread_bps,
            "position_kelly_multiplier": strat.position_kelly_multiplier,
            "stop_loss_bps": strat.stop_loss_bps,
            "take_profit_bps": strat.take_profit_bps,
            "confidence_threshold": strat.confidence_threshold,
            "signal_freshness_seconds": strat.signal_freshness_seconds,
            "min_trade_interval_seconds": strat.min_trade_interval_seconds,
        }

    def set_manual_override(
        self, mode: str, duration_seconds: float = 300.0
    ) -> None:
        """
        Manually override the strategy mode for a duration.

        Args:
            mode: Strategy mode to force
            duration_seconds: How long the override lasts
        """
        if mode not in self._strategies:
            raise ValueError(f"Unknown strategy mode: {mode}")
        self._manual_override = mode
        self._override_until = time.time() + duration_seconds
        log.warning("Manual strategy override: %s for %.0fs", mode, duration_seconds)

    def clear_manual_override(self) -> None:
        """Clear any manual override and return to regime-based switching."""
        self._manual_override = None
        self._override_until = 0.0
        log.info("Manual strategy override cleared")

    def get_switch_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent strategy switch history."""
        with self._lock:
            return list(reversed(self._switch_history[-limit:]))

    def get_status(self) -> Dict[str, Any]:
        """Get full strategy switcher status."""
        manual_active = (
            self._manual_override is not None
            and time.time() < self._override_until
        )
        return {
            "current_mode": self._current_mode,
            "manual_override": self._manual_override if manual_active else None,
            "override_remaining_seconds": max(0, self._override_until - time.time()) if manual_active else 0,
            "available_modes": list(self._strategies.keys()),
            "total_switches": len(self._switch_history),
            "last_switch": self._switch_history[-1] if self._switch_history else None,
        }

    def get_strategies(self) -> Dict[str, StrategyConfig]:
        """Get all strategy configs."""
        return dict(self._strategies)

    def set_strategy(self, mode: str, config: StrategyConfig) -> None:
        """Override a strategy config for a mode."""
        self._strategies[mode] = config
        log.info("Updated strategy config for mode: %s", mode)

    # ── Internal ────────────────────────────────────────────────────────

    def _map_regime_to_mode(self, regime: str) -> str:
        """Map market regime to strategy mode."""
        # From regime_detector: unknown, ranging, trending_up, trending_down, high_vol, crisis
        regime_map = {
            "trending_up": StrategyMode.HF_SCALPING,
            "trending_down": StrategyMode.HF_SCALPING,
            "ranging": StrategyMode.WIDE_SPREAD_HARVEST,
            "unknown": StrategyMode.BALANCED,
            "high_vol": StrategyMode.DEFENSIVE,
            "crisis": StrategyMode.PAUSED,
        }
        return regime_map.get(regime, StrategyMode.BALANCED)

    def _switch_mode(
        self, new_mode: str, regime: str, symbol: str
    ) -> None:
        """Execute a strategy mode switch."""
        old_mode = self._current_mode
        self._current_mode = new_mode
        self._last_switch_time = time.time()

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_mode": old_mode,
            "new_mode": new_mode,
            "regime": regime,
            "symbol": symbol,
        }

        with self._lock:
            self._switch_history.append(event)
            # Persist
            log_path = self._log_dir / "strategy_switches.jsonl"
            with open(log_path, "a") as f:
                f.write(json.dumps(event) + "\n")

        log.warning(
            "Strategy switched: %s -> %s (regime=%s, symbol=%s)",
            old_mode, new_mode, regime, symbol,
        )

    def _load_history(self) -> None:
        """Load switch history from disk."""
        log_path = self._log_dir / "strategy_switches.jsonl"
        if not log_path.exists():
            return
        try:
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    self._switch_history.append(json.loads(line))
            log.info("Loaded %d strategy switch events", len(self._switch_history))
        except Exception as e:
            log.warning("Failed to load strategy switch history: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

STRATEGY_SWITCHER: Optional[StrategySwitcher] = None


def get_strategy_switcher(regime_detector: Any = None) -> StrategySwitcher:
    """Get or create the global StrategySwitcher singleton."""
    global STRATEGY_SWITCHER
    if STRATEGY_SWITCHER is None:
        if regime_detector is None:
            from .regime_detector import RegimeDetector
            regime_detector = RegimeDetector()
        STRATEGY_SWITCHER = StrategySwitcher(regime_detector=regime_detector)
    return STRATEGY_SWITCHER
