"""
T43 — Monte Carlo Backtest Engine

Generates 10k+ simulated paths using GBM and jump-diffusion models,
computes confidence intervals (VaR, CVaR, max drawdown), and runs
strategy simulations with JSONL persistence.
"""

import json
import math
import random
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable

logger = logging.getLogger(__name__)

# ── Constants ──

DEFAULT_N_PATHS = 10_000
DEFAULT_DAYS = 252  # Trading days per year
DEFAULT_CONFIDENCE = 0.95


@dataclass
class MCConfig:
    """Monte Carlo simulation configuration."""
    n_paths: int = DEFAULT_N_PATHS
    n_days: int = DEFAULT_DAYS
    annual_return: float = 0.15       # 15% expected annual return
    annual_vol: float = 0.30          # 30% annual volatility
    jump_intensity: float = 0.0       # Poisson jump frequency (0 = no jumps)
    jump_mean: float = -0.02          # Mean jump size
    jump_std: float = 0.05            # Jump size std dev
    seed: Optional[int] = None
    initial_price: float = 100.0
    drift_type: str = "gbm"           # "gbm" | "jump_diffusion" | "mean_reverting"
    mean_reversion_speed: float = 0.1
    mean_reversion_level: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class MCPath:
    """A single simulated price path."""
    path_id: int
    prices: List[float]
    returns: List[float]
    final_price: float
    total_return: float
    max_drawdown: float
    sharpe: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "final_price": round(self.final_price, 4),
            "total_return": round(self.total_return, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "sharpe": round(self.sharpe, 4),
        }


@dataclass
class MCResult:
    """Aggregated Monte Carlo simulation results."""
    config: MCConfig
    timestamp: str
    paths: List[MCPath]
    simulation_id: str

    # Summary stats
    mean_return: float = 0.0
    median_return: float = 0.0
    std_return: float = 0.0
    var_95: float = 0.0           # 95% Value at Risk
    var_99: float = 0.0           # 99% Value at Risk
    cvar_95: float = 0.0          # Conditional VaR (expected shortfall)
    max_drawdown_mean: float = 0.0
    max_drawdown_median: float = 0.0
    max_drawdown_std: float = 0.0
    sharpe_mean: float = 0.0
    sharpe_std: float = 0.0
    prob_positive: float = 0.0    # Probability of positive return
    prob_double: float = 0.0      # Probability of doubling
    prob_ruin: float = 0.0        # Probability of >50% loss

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "timestamp": self.timestamp,
            "config": self.config.to_dict(),
            "n_paths": len(self.paths),
            "mean_return": round(self.mean_return, 6),
            "median_return": round(self.median_return, 6),
            "std_return": round(self.std_return, 6),
            "var_95": round(self.var_95, 6),
            "var_99": round(self.var_99, 6),
            "cvar_95": round(self.cvar_95, 6),
            "max_drawdown_mean": round(self.max_drawdown_mean, 6),
            "max_drawdown_median": round(self.max_drawdown_median, 6),
            "max_drawdown_std": round(self.max_drawdown_std, 6),
            "sharpe_mean": round(self.sharpe_mean, 4),
            "sharpe_std": round(self.sharpe_std, 4),
            "prob_positive": round(self.prob_positive, 4),
            "prob_double": round(self.prob_double, 4),
            "prob_ruin": round(self.prob_ruin, 4),
        }

    def summary_text(self) -> str:
        return (
            f"MC[{self.simulation_id}] {len(self.paths)} paths\n"
            f"  Return:   μ={self.mean_return:.4f}  median={self.median_return:.4f}  σ={self.std_return:.4f}\n"
            f"  VaR(95%): {self.var_95:.4f}  VaR(99%): {self.var_99:.4f}  CVaR(95%): {self.cvar_95:.4f}\n"
            f"  DD:       μ={self.max_drawdown_mean:.4f}  median={self.max_drawdown_median:.4f}  σ={self.max_drawdown_std:.4f}\n"
            f"  Sharpe:   μ={self.sharpe_mean:.4f}  σ={self.sharpe_std:.4f}\n"
            f"  P(>0):    {self.prob_positive:.2%}  P(2x): {self.prob_double:.2%}  P(ruin): {self.prob_ruin:.2%}"
        )


@dataclass
class StrategySimResult:
    """Result of running a strategy over simulated paths."""
    strategy_name: str
    simulation_id: str
    path_results: List[Dict[str, Any]]
    mean_pnl: float = 0.0
    median_pnl: float = 0.0
    std_pnl: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0
    var_95_pnl: float = 0.0
    max_drawdown: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "simulation_id": self.simulation_id,
            "n_paths": len(self.path_results),
            "mean_pnl": round(self.mean_pnl, 4),
            "median_pnl": round(self.median_pnl, 4),
            "std_pnl": round(self.std_pnl, 4),
            "win_rate": round(self.win_rate, 4),
            "sharpe": round(self.sharpe, 4),
            "var_95_pnl": round(self.var_95_pnl, 4),
            "max_drawdown": round(self.max_drawdown, 4),
        }


class MonteCarloEngine:
    """Monte Carlo simulation engine for price paths and strategies."""

    def __init__(self, results_dir: Optional[Path] = None):
        self._lock = threading.Lock()
        self._results_dir = results_dir or Path("data/monte_carlo")
        self._results_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def _next_id(self) -> str:
        with self._lock:
            self._seq += 1
            return f"mc-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{self._seq}"

    def simulate(self, config: MCConfig) -> MCResult:
        """Run a full Monte Carlo simulation with n_paths."""
        sim_id = self._next_id()
        rng = random.Random(config.seed) if config.seed else random

        dt = 1.0 / 252.0  # Daily timestep
        mu = config.annual_return
        sigma = config.annual_vol

        paths: List[MCPath] = []

        for i in range(config.n_paths):
            prices = [config.initial_price]
            returns = []
            peak = config.initial_price
            max_dd = 0.0

            for day in range(config.n_days):
                # Drift
                if config.drift_type == "mean_reverting":
                    drift = config.mean_reversion_speed * (
                        config.mean_reversion_level - prices[-1]
                    ) / prices[-1] * dt
                else:
                    drift = (mu - 0.5 * sigma * sigma) * dt

                # Random shock
                shock = sigma * math.sqrt(dt) * rng.gauss(0, 1)

                # Jump component
                jump = 0.0
                if config.jump_intensity > 0 and rng.random() < config.jump_intensity * dt:
                    jump = rng.gauss(config.jump_mean, config.jump_std)

                ret = drift + shock + jump
                returns.append(ret)
                new_price = prices[-1] * math.exp(ret)
                prices.append(new_price)

                # Track drawdown
                if new_price > peak:
                    peak = new_price
                dd = (peak - new_price) / peak
                if dd > max_dd:
                    max_dd = dd

            final_price = prices[-1]
            total_return = (final_price / config.initial_price) - 1.0

            # Sharpe ratio (annualized)
            mean_ret = sum(returns) / len(returns) if returns else 0.0
            std_ret = math.sqrt(
                sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            ) if returns else 0.0
            sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0

            paths.append(MCPath(
                path_id=i,
                prices=prices,
                returns=returns,
                final_price=final_price,
                total_return=total_return,
                max_drawdown=max_dd,
                sharpe=sharpe,
            ))

        # Compute summary stats
        returns_list = [p.total_return for p in paths]
        dd_list = [p.max_drawdown for p in paths]
        sharpe_list = [p.sharpe for p in paths]
        sorted_returns = sorted(returns_list)

        n = len(returns_list)
        mean_r = sum(returns_list) / n if n > 0 else 0.0
        median_r = sorted_returns[n // 2] if n > 0 else 0.0
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns_list) / n) if n > 0 else 0.0

        # VaR at 95% and 99%
        var_95_idx = int(n * (1 - DEFAULT_CONFIDENCE))
        var_99_idx = int(n * 0.01)
        var_95 = sorted_returns[var_95_idx] if var_95_idx < n and n > 0 else 0.0
        var_99 = sorted_returns[var_99_idx] if var_99_idx < n and n > 0 else 0.0

        # CVaR (expected shortfall) at 95%
        tail = sorted_returns[:var_95_idx + 1]
        cvar_95 = sum(tail) / len(tail) if tail else 0.0

        max_dd_mean = sum(dd_list) / n if n > 0 else 0.0
        max_dd_median = sorted(dd_list)[n // 2] if n > 0 else 0.0
        max_dd_std = math.sqrt(
            sum((d - max_dd_mean) ** 2 for d in dd_list) / n
        ) if n > 0 else 0.0

        sharpe_mean = sum(sharpe_list) / n if n > 0 else 0.0
        sharpe_std = math.sqrt(
            sum((s - sharpe_mean) ** 2 for s in sharpe_list) / n
        ) if n > 0 else 0.0

        prob_positive = sum(1 for r in returns_list if r > 0) / n if n > 0 else 0.0
        prob_double = sum(1 for r in returns_list if r > 1.0) / n if n > 0 else 0.0
        prob_ruin = sum(1 for r in returns_list if r < -0.5) / n if n > 0 else 0.0

        result = MCResult(
            config=config,
            timestamp=datetime.now(timezone.utc).isoformat(),
            paths=paths,
            simulation_id=sim_id,
            mean_return=mean_r,
            median_return=median_r,
            std_return=std_r,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            max_drawdown_mean=max_dd_mean,
            max_drawdown_median=max_dd_median,
            max_drawdown_std=max_dd_std,
            sharpe_mean=sharpe_mean,
            sharpe_std=sharpe_std,
            prob_positive=prob_positive,
            prob_double=prob_double,
            prob_ruin=prob_ruin,
        )

        self._persist(result)
        return result

    def simulate_strategy(self, strategy_fn: Callable[[List[float]], float],
                          config: MCConfig,
                          strategy_name: str = "custom") -> StrategySimResult:
        """Run a strategy function over all simulated paths.

        The strategy_fn receives a price series and returns total PnL.
        """
        sim_id = self._next_id()
        result = self.simulate(config)

        path_results = []
        pnls = []

        for path in result.paths:
            try:
                pnl = strategy_fn(path.prices)
            except Exception as e:
                logger.warning("Strategy failed on path %d: %s", path.path_id, e)
                pnl = 0.0

            pnls.append(pnl)
            path_results.append({
                "path_id": path.path_id,
                "pnl": round(pnl, 4),
                "total_return": round(path.total_return, 6),
            })

        n = len(pnls)
        mean_pnl = sum(pnls) / n if n > 0 else 0.0
        sorted_pnls = sorted(pnls)
        median_pnl = sorted_pnls[n // 2] if n > 0 else 0.0
        std_pnl = math.sqrt(sum((p - mean_pnl) ** 2 for p in pnls) / n) if n > 0 else 0.0
        win_rate = sum(1 for p in pnls if p > 0) / n if n > 0 else 0.0

        var_95_idx = int(n * 0.05)
        var_95_pnl = sorted_pnls[var_95_idx] if var_95_idx < n else (sorted_pnls[0] if sorted_pnls else 0.0)

        sharpe = (mean_pnl / std_pnl * math.sqrt(252)) if std_pnl > 0 else 0.0

        result = StrategySimResult(
            strategy_name=strategy_name,
            simulation_id=sim_id,
            path_results=path_results,
            mean_pnl=mean_pnl,
            median_pnl=median_pnl,
            std_pnl=std_pnl,
            win_rate=win_rate,
            sharpe=sharpe,
            var_95_pnl=var_95_pnl,
            max_drawdown=result.max_drawdown_mean,
        )
        return result

    def compare_strategies(self, strategies: Dict[str, Callable[[List[float]], float]],
                           config: MCConfig) -> List[StrategySimResult]:
        """Compare multiple strategies on the same simulation."""
        base = self.simulate(config)
        results = []
        for name, fn in strategies.items():
            # Re-use the base simulation paths
            sim_result = StrategySimResult(
                strategy_name=name,
                simulation_id=base.simulation_id,
                path_results=[],
            )

            pnls = []
            for path in base.paths:
                try:
                    pnl = fn(path.prices)
                except Exception:
                    pnl = 0.0
                pnls.append(pnl)
                sim_result.path_results.append({
                    "path_id": path.path_id,
                    "pnl": round(pnl, 4),
                })

            n = len(pnls)
            mean_pnl = sum(pnls) / n if n > 0 else 0.0
            sorted_pnls = sorted(pnls)
            median_pnl = sorted_pnls[n // 2] if n > 0 else 0.0
            std_pnl = math.sqrt(sum((p - mean_pnl) ** 2 for p in pnls) / n) if n > 0 else 0.0
            win_rate = sum(1 for p in pnls if p > 0) / n if n > 0 else 0.0
            var_95_idx = int(n * 0.05)
            var_95_pnl = sorted_pnls[var_95_idx] if var_95_idx < n else (sorted_pnls[0] if sorted_pnls else 0.0)
            sharpe = (mean_pnl / std_pnl * math.sqrt(252)) if std_pnl > 0 else 0.0

            sim_result.mean_pnl = mean_pnl
            sim_result.median_pnl = median_pnl
            sim_result.std_pnl = std_pnl
            sim_result.win_rate = win_rate
            sim_result.sharpe = sharpe
            sim_result.var_95_pnl = var_95_pnl
            sim_result.max_drawdown = base.max_drawdown_mean
            results.append(sim_result)

        results.sort(key=lambda r: -r.sharpe)
        return results

    def _persist(self, result: MCResult) -> None:
        """Save simulation result to JSONL."""
        try:
            ledger = self._results_dir / "simulations.jsonl"
            with open(ledger, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except Exception as e:
            logger.error("Failed to persist MC result: %s", e)

    def load_history(self, limit: int = 50) -> List[MCResult]:
        """Load historical simulation results."""
        ledger = self._results_dir / "simulations.jsonl"
        if not ledger.exists():
            return []
        results = []
        try:
            with open(ledger) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        results.append(data)
                    except Exception:
                        continue
        except Exception as e:
            logger.error("Failed to load history: %s", e)

        return results[-limit:]

    def compute_kelly_optimal(self, win_rate: float, avg_win: float,
                              avg_loss: float) -> float:
        """Compute Kelly Criterion optimal fraction."""
        if avg_loss == 0:
            return 0.0
        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1.0 - p
        kelly = (b * p - q) / b
        return max(0.0, min(kelly, 1.0))  # Clamp to [0, 1]


# ── Module Singleton ──

_MC: Optional[MonteCarloEngine] = None
_mc_lock = threading.Lock()


def get_monte_carlo() -> MonteCarloEngine:
    global _MC
    if _MC is None:
        with _mc_lock:
            if _MC is None:
                _MC = MonteCarloEngine()
    return _MC


# ── Helper: Example strategy functions ──

def momentum_strategy(prices: List[float], lookback: int = 20) -> float:
    """Simple momentum: buy if price > SMA(lookback), else short."""
    if len(prices) < lookback + 1:
        return 0.0
    sma = sum(prices[-lookback-1:-1]) / lookback
    entry = prices[-lookback-1]
    exit_price = prices[-1]

    if entry > sma:
        return (exit_price / entry - 1.0) * 0.01  # 1x leverage
    else:
        return -(exit_price / entry - 1.0) * 0.01


def mean_reversion_strategy(prices: List[float], lookback: int = 20,
                            entry_z: float = 2.0) -> float:
    """Mean reversion: buy oversold, sell overbought."""
    if len(prices) < lookback + 1:
        return 0.0
    recent = prices[-lookback-1:-1]
    mean = sum(recent) / len(recent)
    std = math.sqrt(sum((p - mean) ** 2 for p in recent) / len(recent))
    if std == 0:
        return 0.0

    entry = prices[-lookback-1]
    z = (entry - mean) / std
    exit_price = prices[-1]

    if z < -entry_z:
        return (exit_price / entry - 1.0) * 0.01  # Buy
    elif z > entry_z:
        return -(exit_price / entry - 1.0) * 0.01  # Short
    return 0.0


def buy_and_hold_strategy(prices: List[float]) -> float:
    """Benchmark: buy and hold."""
    if len(prices) < 2:
        return 0.0
    return (prices[-1] / prices[0]) - 1.0


# ── Self-test ──

def test_monte_carlo() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = MonteCarloEngine(results_dir=Path(tmpdir))

        # Test 1: Basic simulation
        config = MCConfig(
            n_paths=1000,
            n_days=252,
            annual_return=0.10,
            annual_vol=0.20,
            seed=42,
        )
        result = engine.simulate(config)
        assert len(result.paths) == 1000
        assert result.simulation_id.startswith("mc-")
        print(f"  ✅ Basic simulation: {len(result.paths)} paths")

        # Test 2: Stats make sense
        assert result.mean_return > -0.5  # Not absurdly negative
        assert result.mean_return < 1.0   # Not absurdly positive
        assert result.var_95 < 0.0        # VaR should be negative
        assert result.var_99 <= result.var_95  # 99% VaR is more extreme
        assert 0.0 <= result.prob_positive <= 1.0
        print(f"  ✅ Stats: μ={result.mean_return:.4f} VaR95={result.var_95:.4f} "
              f"CVaR95={result.cvar_95:.4f} P(+)={result.prob_positive:.2%}")

        # Test 3: Jump diffusion
        jump_config = MCConfig(
            n_paths=500,
            n_days=252,
            annual_return=0.10,
            annual_vol=0.20,
            jump_intensity=10.0,
            jump_mean=-0.03,
            jump_std=0.06,
            seed=42,
        )
        jump_result = engine.simulate(jump_config)
        assert len(jump_result.paths) == 500
        print(f"  ✅ Jump diffusion: {len(jump_result.paths)} paths")

        # Test 4: Mean reverting
        mr_config = MCConfig(
            n_paths=500,
            n_days=252,
            drift_type="mean_reverting",
            mean_reversion_speed=0.5,
            mean_reversion_level=100.0,
            annual_vol=0.15,
            seed=42,
        )
        mr_result = engine.simulate(mr_config)
        assert len(mr_result.paths) == 500
        print(f"  ✅ Mean reverting: {len(mr_result.paths)} paths")

        # Test 5: Strategy comparison
        strategies = {
            "momentum": lambda p: momentum_strategy(p, lookback=20),
            "buy_hold": buy_and_hold_strategy,
            "mean_rev": lambda p: mean_reversion_strategy(p, lookback=20),
        }
        comp_config = MCConfig(n_paths=200, n_days=63, seed=42)  # 63 trading days
        results = engine.compare_strategies(strategies, comp_config)
        assert len(results) == 3
        # Sorted by Sharpe descending
        assert results[0].sharpe >= results[-1].sharpe
        print(f"  ✅ Strategy comparison: 3 strategies ranked by Sharpe")

        # Test 6: Persistence
        loaded = engine.load_history(limit=10)
        assert len(loaded) >= 3
        print(f"  ✅ Persistence: {len(loaded)} historical simulations")

        # Test 7: Kelly criterion
        kelly = engine.compute_kelly_optimal(0.6, 100, 50)
        assert 0.0 < kelly < 1.0
        print(f"  ✅ Kelly: {kelly:.4f}")

        print(f"\n✅ T43 test_monte_carlo: ALL PASSED")


if __name__ == "__main__":
    test_monte_carlo()
