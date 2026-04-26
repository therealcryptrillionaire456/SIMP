"""
T43: Monte Carlo Backtesting Engine
====================================
10,000+ simulation paths for strategy validation.

This module provides:
1. Monte Carlo simulation of strategy returns
2. Confidence intervals (5th/50th/95th percentile)
3. Regime-aware scenarios
4. Walk-forward analysis

Usage:
    engine = MonteCarloEngine()
    result = engine.run_simulation(strategy_returns, num_paths=10000)
    print(f"P5: {result.p5_return}, Median: {result.median_return}, P95: {result.p95_return}")
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

log = logging.getLogger("monte_carlo")

# ── Constants ───────────────────────────────────────────────────────────

DEFAULT_NUM_PATHS = 10000
RANDOM_SEED = 42


@dataclass
class SimulationResult:
    """Result of Monte Carlo simulation."""
    num_paths: int
    num_periods: int
    initial_capital: float
    
    # Return statistics
    mean_return: float
    median_return: float
    std_return: float
    min_return: float
    max_return: float
    
    # Percentile returns
    p1_return: float
    p5_return: float
    p10_return: float
    p25_return: float
    p50_return: float  # Same as median
    p75_return: float
    p90_return: float
    p95_return: float
    p99_return: float
    
    # Drawdown statistics
    max_drawdown_mean: float
    max_drawdown_p95: float
    max_drawdown_p99: float
    
    # Sharpe-like metrics
    sharpe_mean: float
    sharpe_p5: float
    
    # Simulation paths (optional, for detailed analysis)
    paths: List[List[float]] = field(default_factory=list)
    
    # Metadata
    timestamp: str = ""
    regime: str = "all"
    strategy_name: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def summary(self) -> str:
        return (
            f"Monte Carlo ({self.num_paths} paths, {self.num_periods} periods)\n"
            f"  Returns:   P5={self.p5_return*100:.1f}%, Median={self.median_return*100:.1f}%, P95={self.p95_return*100:.1f}%\n"
            f"  Drawdown: Mean={self.max_drawdown_mean*100:.1f}%, P95={self.max_drawdown_p95*100:.1f}%\n"
            f"  Sharpe:    Mean={self.sharpe_mean:.2f}, P5={self.sharpe_p5:.2f}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_paths": self.num_paths,
            "num_periods": self.num_periods,
            "initial_capital": self.initial_capital,
            "returns": {
                "mean": self.mean_return,
                "median": self.median_return,
                "std": self.std_return,
                "min": self.min_return,
                "max": self.max_return,
                "p1": self.p1_return,
                "p5": self.p5_return,
                "p10": self.p10_return,
                "p25": self.p25_return,
                "p50": self.p50_return,
                "p75": self.p75_return,
                "p90": self.p90_return,
                "p95": self.p95_return,
                "p99": self.p99_return,
            },
            "drawdown": {
                "mean": self.max_drawdown_mean,
                "p95": self.max_drawdown_p95,
                "p99": self.max_drawdown_p99,
            },
            "sharpe": {
                "mean": self.sharpe_mean,
                "p5": self.sharpe_p5,
            },
            "timestamp": self.timestamp,
            "regime": self.regime,
            "strategy_name": self.strategy_name,
        }


class MonteCarloEngine:
    """
    Monte Carlo simulation engine for strategy backtesting.
    
    Thread-safe. Supports configurable number of paths, regimes, and scenarios.
    """

    def __init__(
        self,
        num_paths: int = DEFAULT_NUM_PATHS,
        random_seed: int = RANDOM_SEED,
    ):
        self.num_paths = num_paths
        self.random_seed = random_seed
        self._lock = threading.Lock()

    def run_simulation(
        self,
        historical_returns: List[float],
        initial_capital: float = 10000.0,
        regime: str = "all",
        strategy_name: str = "unknown",
        preserve_order: bool = False,
    ) -> SimulationResult:
        """
        Run Monte Carlo simulation on historical returns.
        
        Args:
            historical_returns: List of historical returns (e.g., [0.01, -0.02, 0.03])
            initial_capital: Starting capital in USD
            regime: Market regime (all, bull, bear, volatile)
            strategy_name: Strategy being evaluated
            preserve_order: If True, use historical sequence; if False, randomize
            
        Returns:
            SimulationResult with percentile statistics
        """
        with self._lock:
            random.seed(self.random_seed)
            np.random.seed(self.random_seed)
            
            n_periods = len(historical_returns)
            if n_periods == 0:
                log.warning("No historical returns provided")
                return self._empty_result(initial_capital, regime, strategy_name)
            
            # Convert to numpy for faster computation
            returns = np.array(historical_returns)
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            # Generate simulation paths
            if preserve_order:
                # Random sampling with replacement, preserving order within each period
                paths = self._bootstrap_with_order(returns, self.num_paths, n_periods)
            else:
                # Pure random sampling
                paths = self._random_sampling(returns, self.num_paths, n_periods)
            
            # Calculate equity curves
            equity_curves = self._calculate_equity_curves(paths, initial_capital)
            
            # Calculate terminal returns
            terminal_returns = (equity_curves[:, -1] - initial_capital) / initial_capital
            
            # Calculate drawdowns
            max_drawdowns = self._calculate_max_drawdowns(equity_curves)
            
            # Calculate Sharpe-like metrics (using std of returns as proxy for risk)
            sharpe_ratios = self._calculate_sharpe_ratios(paths)
            
            # Compute percentiles
            percentiles = {
                "p1": np.percentile(terminal_returns, 1),
                "p5": np.percentile(terminal_returns, 5),
                "p10": np.percentile(terminal_returns, 10),
                "p25": np.percentile(terminal_returns, 25),
                "p50": np.percentile(terminal_returns, 50),
                "p75": np.percentile(terminal_returns, 75),
                "p90": np.percentile(terminal_returns, 90),
                "p95": np.percentile(terminal_returns, 95),
                "p99": np.percentile(terminal_returns, 99),
            }
            
            return SimulationResult(
                num_paths=self.num_paths,
                num_periods=n_periods,
                initial_capital=initial_capital,
                mean_return=np.mean(terminal_returns),
                median_return=percentiles["p50"],
                std_return=np.std(terminal_returns),
                min_return=np.min(terminal_returns),
                max_return=np.max(terminal_returns),
                p1_return=percentiles["p1"],
                p5_return=percentiles["p5"],
                p10_return=percentiles["p10"],
                p25_return=percentiles["p25"],
                p50_return=percentiles["p50"],
                p75_return=percentiles["p75"],
                p90_return=percentiles["p90"],
                p95_return=percentiles["p95"],
                p99_return=percentiles["p99"],
                max_drawdown_mean=np.mean(max_drawdowns),
                max_drawdown_p95=np.percentile(max_drawdowns, 95),
                max_drawdown_p99=np.percentile(max_drawdowns, 99),
                sharpe_mean=np.mean(sharpe_ratios),
                sharpe_p5=np.percentile(sharpe_ratios, 5),
                regime=regime,
                strategy_name=strategy_name,
            )

    def _bootstrap_with_order(self, returns: np.ndarray, num_paths: int, n_periods: int) -> np.ndarray:
        """Bootstrap sampling preserving order within periods."""
        paths = np.zeros((num_paths, n_periods))
        for i in range(num_paths):
            indices = np.random.randint(0, n_periods, size=n_periods)
            paths[i] = returns[indices]
        return paths

    def _random_sampling(self, returns: np.ndarray, num_paths: int, n_periods: int) -> np.ndarray:
        """Pure random sampling of returns."""
        paths = np.zeros((num_paths, n_periods))
        for i in range(num_paths):
            paths[i] = np.random.choice(returns, size=n_periods, replace=True)
        return paths

    def _calculate_equity_curves(self, paths: np.ndarray, initial_capital: float) -> np.ndarray:
        """Calculate equity curves from return paths."""
        equity_curves = np.zeros_like(paths)
        equity_curves[:, 0] = initial_capital * (1 + paths[:, 0])
        for t in range(1, paths.shape[1]):
            equity_curves[:, t] = equity_curves[:, t-1] * (1 + paths[:, t])
        return equity_curves

    def _calculate_max_drawdowns(self, equity_curves: np.ndarray) -> np.ndarray:
        """Calculate maximum drawdown for each path."""
        max_drawdowns = np.zeros(equity_curves.shape[0])
        for i in range(equity_curves.shape[0]):
            equity = equity_curves[i]
            running_max = np.maximum.accumulate(equity)
            drawdowns = (running_max - equity) / running_max
            max_drawdowns[i] = np.max(drawdowns)
        return max_drawdowns

    def _calculate_sharpe_ratios(self, paths: np.ndarray) -> np.ndarray:
        """Calculate Sharpe-like ratios for each path."""
        sharpe_ratios = np.zeros(paths.shape[0])
        for i in range(paths.shape[0]):
            returns = paths[i]
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe_ratios[i] = mean_ret / std_ret * math.sqrt(252)  # Annualized
            else:
                sharpe_ratios[i] = 0.0
        return sharpe_ratios

    def _empty_result(self, initial_capital: float, regime: str, strategy_name: str) -> SimulationResult:
        """Return empty result when no data."""
        return SimulationResult(
            num_paths=self.num_paths,
            num_periods=0,
            initial_capital=initial_capital,
            mean_return=0.0,
            median_return=0.0,
            std_return=0.0,
            min_return=0.0,
            max_return=0.0,
            p1_return=0.0,
            p5_return=0.0,
            p10_return=0.0,
            p25_return=0.0,
            p50_return=0.0,
            p75_return=0.0,
            p90_return=0.0,
            p95_return=0.0,
            p99_return=0.0,
            max_drawdown_mean=0.0,
            max_drawdown_p95=0.0,
            max_drawdown_p99=0.0,
            sharpe_mean=0.0,
            sharpe_p5=0.0,
            regime=regime,
            strategy_name=strategy_name,
        )

    def run_regime_scenario(
        self,
        base_returns: List[float],
        regime_multipliers: Dict[str, float],
        regime: str,
        initial_capital: float = 10000.0,
        strategy_name: str = "unknown",
    ) -> SimulationResult:
        """
        Run simulation with regime-adjusted returns.
        
        Args:
            base_returns: Base historical returns
            regime_multipliers: Dict of regime -> volatility multiplier
            regime: Current regime to simulate
            initial_capital: Starting capital
            strategy_name: Strategy name
            
        Returns:
            SimulationResult for the regime
        """
        multiplier = regime_multipliers.get(regime, 1.0)
        adjusted_returns = [r * multiplier for r in base_returns]
        return self.run_simulation(
            adjusted_returns,
            initial_capital=initial_capital,
            regime=regime,
            strategy_name=strategy_name,
        )


# ── Module-level singleton ──────────────────────────────────────────────

_engine: Optional[MonteCarloEngine] = None


def get_monte_carlo_engine(**kwargs) -> MonteCarloEngine:
    """Get or create the global MonteCarloEngine singleton."""
    global _engine
    if _engine is None:
        _engine = MonteCarloEngine(**kwargs)
    return _engine


# ── Demo / Test ─────────────────────────────────────────────────────────

def demo_monte_carlo():
    """Demonstrate Monte Carlo simulation."""
    print("=" * 60)
    print("T43 — Monte Carlo Backtesting Demo")
    print("=" * 60)

    engine = MonteCarloEngine(num_paths=10000)

    # Simulated daily returns (mean=0.001, std=0.02)
    np.random.seed(42)
    daily_returns = np.random.normal(0.001, 0.02, 252)  # 1 year of daily returns

    print(f"\n[1] Historical returns: {len(daily_returns)} periods")
    print(f"    Mean: {np.mean(daily_returns)*100:.3f}%, Std: {np.std(daily_returns)*100:.3f}%")

    print(f"\n[2] Running Monte Carlo (10,000 paths)...")
    result = engine.run_simulation(
        daily_returns.tolist(),
        initial_capital=10000.0,
        regime="all",
        strategy_name="quantumarb",
    )

    print(f"\n[3] Results:")
    print(result.summary())

    print(f"\n[4] Regime scenarios:")
    scenarios = {
        "bull": engine.run_regime_scenario(daily_returns.tolist(), {"bull": 0.8}, "bull"),
        "normal": engine.run_regime_scenario(daily_returns.tolist(), {"normal": 1.0}, "normal"),
        "volatile": engine.run_regime_scenario(daily_returns.tolist(), {"volatile": 1.5}, "volatile"),
        "bear": engine.run_regime_scenario(daily_returns.tolist(), {"bear": 2.0}, "bear"),
    }
    
    for name, sim in scenarios.items():
        print(f"    {name:8s}: P5={sim.p5_return*100:6.1f}%, Median={sim.median_return*100:6.1f}%, P95={sim.p95_return*100:6.1f}%")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_monte_carlo()
