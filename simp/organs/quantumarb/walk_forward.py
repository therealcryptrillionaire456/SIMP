"""
T44 — Walk-Forward Analysis: Overfitting detection & parameter stability.

Provides:
  - WalkForwardOptimizer: IS/OOS split optimization
  - Parameter decay detection across windows
  - Sharpe ratio stability scoring
  - Overfitting likelihood assessment
  - JSONL persistence for audit trail
"""

import json
import math
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable

logger = logging.getLogger(__name__)

# ── Constants ──

DEFAULT_N_WINDOWS = 6
DEFAULT_IS_PCT = 0.70  # 70% in-sample, 30% out-of-sample
DEFAULT_WINDOW_OVERLAP = 0.0  # 0 = no overlap, >0 = rolling windows


@dataclass
class WFConfig:
    """Walk-forward analysis configuration."""
    n_windows: int = DEFAULT_N_WINDOWS
    is_pct: float = DEFAULT_IS_PCT
    window_overlap: float = DEFAULT_WINDOW_OVERLAP
    min_sharpe_stability: float = 0.5   # Min Sharpe ratio across windows
    max_param_decay_pct: float = 0.30   # Max parameter degradation
    confidence_level: float = 0.95

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class WFWindow:
    """Results from a single walk-forward window."""
    window_idx: int
    is_start: int
    is_end: int
    oos_start: int
    oos_end: int
    is_sharpe: float
    oos_sharpe: float
    is_return: float
    oos_return: float
    is_max_dd: float
    oos_max_dd: float
    params: Dict[str, float]          # Optimal params on this window
    is_vol: float = 0.0
    oos_vol: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_idx": self.window_idx,
            "is_start": self.is_start,
            "is_end": self.is_end,
            "oos_start": self.oos_start,
            "oos_end": self.oos_end,
            "is_sharpe": round(self.is_sharpe, 4),
            "oos_sharpe": round(self.oos_sharpe, 4),
            "is_return": round(self.is_return, 6),
            "oos_return": round(self.oos_return, 6),
            "is_max_dd": round(self.is_max_dd, 6),
            "oos_max_dd": round(self.oos_max_dd, 6),
            "params": self.params,
            "is_vol": round(self.is_vol, 6),
            "oos_vol": round(self.oos_vol, 6),
        }


@dataclass
class WFResult:
    """Complete walk-forward analysis result."""
    analysis_id: str
    timestamp: str
    config: WFConfig
    strategy_name: str
    windows: List[WFWindow]
    n_data_points: int

    # Aggregated metrics
    avg_is_sharpe: float = 0.0
    avg_oos_sharpe: float = 0.0
    sharpe_stability: float = 0.0      # Std dev of OOS Sharpe (lower = more stable)
    oos_is_ratio: float = 0.0          # Avg OOS Sharpe / Avg IS Sharpe
    param_stability: float = 0.0       # Avg coefficient of variation of params
    param_decay_pct: float = 0.0       # Avg degradation across windows
    overfitting_likelihood: str = ""   # "low" | "medium" | "high"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "timestamp": self.timestamp,
            "config": self.config.to_dict(),
            "strategy_name": self.strategy_name,
            "n_windows": len(self.windows),
            "n_data_points": self.n_data_points,
            "avg_is_sharpe": round(self.avg_is_sharpe, 4),
            "avg_oos_sharpe": round(self.avg_oos_sharpe, 4),
            "sharpe_stability": round(self.sharpe_stability, 4),
            "oos_is_ratio": round(self.oos_is_ratio, 4),
            "param_stability": round(self.param_stability, 4),
            "param_decay_pct": round(self.param_decay_pct, 4),
            "overfitting_likelihood": self.overfitting_likelihood,
            "windows": [w.to_dict() for w in self.windows],
        }

    def summary_text(self) -> str:
        return (
            f"WF[{self.analysis_id}] {self.strategy_name}: {len(self.windows)} windows\n"
            f"  IS Sharpe:  {self.avg_is_sharpe:.4f}\n"
            f"  OOS Sharpe: {self.avg_oos_sharpe:.4f}\n"
            f"  OOS/IS:     {self.oos_is_ratio:.4f} (target >0.5)\n"
            f"  Stability:  {self.sharpe_stability:.4f} (lower=better)\n"
            f"  Param Decay:{self.param_decay_pct:.2%} (target <30%)\n"
            f"  Verdict:    {self.overfitting_likelihood.upper()} overfitting risk"
        )


class WalkForwardOptimizer:
    """Walk-forward analysis engine for strategy parameter stability."""

    def __init__(self, results_dir: Optional[Path] = None):
        self._lock = threading.Lock()
        self._results_dir = results_dir or Path("data/walk_forward")
        self._results_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def _next_id(self) -> str:
        with self._lock:
            self._seq += 1
            return (f"wf-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
                    f"-{self._seq}")

    def run(self, prices: List[float],
            optimize_fn: Callable[[List[float]], Dict[str, float]],
            evaluate_fn: Callable[[List[float], Dict[str, float]], Dict[str, float]],
            config: Optional[WFConfig] = None,
            strategy_name: str = "strategy") -> WFResult:
        """Run walk-forward analysis on a price series.

        Args:
            prices: Historical price data
            optimize_fn: Returns optimal params dict given training data
            evaluate_fn: Returns {'sharpe', 'return', 'max_dd'} given test data + params
            config: Analysis configuration
            strategy_name: Label for the strategy
        """
        cfg = config or WFConfig()
        analysis_id = self._next_id()

        n = len(prices)
        if n < 100:
            raise ValueError(f"Need at least 100 data points, got {n}")

        # Calculate window boundaries
        windows = self._build_windows(n, cfg)
        results: List[WFWindow] = []

        for w_idx, (is_start, is_end, oos_start, oos_end) in enumerate(windows):
            is_data = prices[is_start:is_end]
            oos_data = prices[oos_start:oos_end]

            if len(is_data) < 20 or len(oos_data) < 5:
                logger.warning("Window %d too small (%d IS, %d OOS), skipping",
                               w_idx, len(is_data), len(oos_data))
                continue

            # Optimize on IS
            try:
                optimal_params = optimize_fn(is_data)
            except Exception as e:
                logger.warning("Optimization failed on window %d: %s", w_idx, e)
                continue

            # Evaluate on IS
            try:
                is_metrics = evaluate_fn(is_data, optimal_params)
            except Exception as e:
                logger.warning("IS evaluation failed on window %d: %s", w_idx, e)
                is_metrics = {"sharpe": 0.0, "return": 0.0, "max_dd": 0.0, "vol": 0.0}

            # Evaluate on OOS
            try:
                oos_metrics = evaluate_fn(oos_data, optimal_params)
            except Exception as e:
                logger.warning("OOS evaluation failed on window %d: %s", w_idx, e)
                oos_metrics = {"sharpe": 0.0, "return": 0.0, "max_dd": 0.0, "vol": 0.0}

            window = WFWindow(
                window_idx=w_idx,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                is_sharpe=is_metrics.get("sharpe", 0.0),
                oos_sharpe=oos_metrics.get("sharpe", 0.0),
                is_return=is_metrics.get("return", 0.0),
                oos_return=oos_metrics.get("return", 0.0),
                is_max_dd=is_metrics.get("max_dd", 0.0),
                oos_max_dd=oos_metrics.get("max_dd", 0.0),
                params=optimal_params,
                is_vol=is_metrics.get("vol", 0.0),
                oos_vol=oos_metrics.get("vol", 0.0),
            )
            results.append(window)

        if not results:
            raise ValueError("No valid windows produced")

        # Aggregate
        n_win = len(results)
        is_sharpes = [w.is_sharpe for w in results]
        oos_sharpes = [w.oos_sharpe for w in results]
        avg_is_sharpe = sum(is_sharpes) / n_win
        avg_oos_sharpe = sum(oos_sharpes) / n_win

        # Sharpe stability (std of OOS Sharpe)
        sharpe_stability = math.sqrt(
            sum((s - avg_oos_sharpe) ** 2 for s in oos_sharpes) / n_win
        ) if n_win > 0 else 999.0

        # OOS/IS ratio
        oos_is_ratio = (avg_oos_sharpe / avg_is_sharpe) if avg_is_sharpe > 0 else 0.0

        # Parameter stability (coefficient of variation across windows)
        param_names = list(results[0].params.keys()) if results else []
        param_cvs = []
        for pname in param_names:
            vals = [w.params.get(pname, 0) for w in results]
            mean_val = sum(vals) / len(vals) if vals else 0.0
            if mean_val == 0:
                continue
            std_val = math.sqrt(sum((v - mean_val) ** 2 for v in vals) / len(vals))
            cv = std_val / abs(mean_val)
            param_cvs.append(cv)

        param_stability = sum(param_cvs) / len(param_cvs) if param_cvs else 999.0

        # Parameter decay (degradation in OOS vs IS across windows)
        decays = []
        for w in results:
            if w.is_sharpe > 0:
                decay = (w.is_sharpe - w.oos_sharpe) / w.is_sharpe
                decays.append(max(0.0, decay))
        param_decay_pct = sum(decays) / len(decays) if decays else 1.0

        # Overfitting likelihood
        score = 0
        if avg_oos_sharpe < 0:
            score += 3
        if oos_is_ratio < 0.3:
            score += 2
        elif oos_is_ratio < 0.5:
            score += 1
        if sharpe_stability > 1.0:
            score += 2
        elif sharpe_stability > 0.5:
            score += 1
        if param_stability > 1.0:
            score += 2
        elif param_stability > 0.5:
            score += 1
        if param_decay_pct > cfg.max_param_decay_pct:
            score += 2

        if score >= 6:
            overfitting = "high"
        elif score >= 3:
            overfitting = "medium"
        else:
            overfitting = "low"

        result = WFResult(
            analysis_id=analysis_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            config=cfg,
            strategy_name=strategy_name,
            windows=results,
            n_data_points=n,
            avg_is_sharpe=avg_is_sharpe,
            avg_oos_sharpe=avg_oos_sharpe,
            sharpe_stability=sharpe_stability,
            oos_is_ratio=oos_is_ratio,
            param_stability=param_stability,
            param_decay_pct=param_decay_pct,
            overfitting_likelihood=overfitting,
        )

        self._persist(result)
        return result

    def _build_windows(self, n: int, cfg: WFConfig) -> List[Tuple[int, int, int, int]]:
        """Build IS/OOS window boundaries."""
        windows = []
        is_size = int(n * cfg.is_pct)
        oos_size = n - is_size

        if cfg.window_overlap > 0:
            # Rolling windows with overlap
            stride = max(1, int(oos_size * (1.0 - cfg.window_overlap)))
            for i in range(cfg.n_windows):
                oos_end = n - (cfg.n_windows - 1 - i) * stride
                oos_start = oos_end - oos_size
                is_end = oos_start
                is_start = max(0, is_end - is_size)
                if oos_start < 0 or oos_start >= oos_end or is_start >= is_end:
                    continue
                windows.append((is_start, is_end, oos_start, oos_end))
        else:
            # Sequential non-overlapping windows
            for i in range(cfg.n_windows):
                oos_end = n - i * oos_size
                oos_start = max(0, oos_end - oos_size)
                is_end = oos_start
                is_start = max(0, is_end - is_size)
                if oos_start < 0 or oos_start >= oos_end or is_start >= is_end:
                    continue
                windows.append((is_start, is_end, oos_start, oos_end))

        if not windows:
            # Fallback: single window
            is_start = 0
            is_end = is_size
            windows.append((is_start, is_end, is_end, n))

        return windows[:cfg.n_windows]

    def _persist(self, result: WFResult) -> None:
        """Save analysis result to JSONL."""
        try:
            ledger = self._results_dir / "analyses.jsonl"
            with open(ledger, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except Exception as e:
            logger.error("Failed to persist WF result: %s", e)

    def load_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Load historical walk-forward analyses as dicts."""
        ledger = self._results_dir / "analyses.jsonl"
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
            logger.error("Failed to load WF history: %s", e)

        return results[-limit:]

    def score_strategy(self, prices: List[float],
                       optimize_fn: Callable,
                       evaluate_fn: Callable,
                       strategy_name: str = "strategy") -> Dict[str, Any]:
        """Score a strategy on overfitting risk.

        Returns dict with:
          - 'score': 0-100 (higher = less overfitting risk)
          - 'grade': A/B/C/D/F
          - 'result': WFResult
        """
        config = WFConfig(
            n_windows=6,
            is_pct=0.70,
            min_sharpe_stability=0.5,
            max_param_decay_pct=0.30,
        )
        result = self.run(prices, optimize_fn, evaluate_fn, config, strategy_name)

        # Compute score (0-100)
        score = 50.0  # Start at 50

        # OOS/IS ratio bonus/penalty
        if result.oos_is_ratio >= 0.7:
            score += 20
        elif result.oos_is_ratio >= 0.5:
            score += 10
        elif result.oos_is_ratio >= 0.3:
            score -= 10
        else:
            score -= 20

        # Sharper stability
        if result.sharpe_stability < 0.3:
            score += 15
        elif result.sharpe_stability < 0.6:
            score += 5
        elif result.sharpe_stability > 1.0:
            score -= 15

        # Parameter stability
        if result.param_stability < 0.3:
            score += 15
        elif result.param_stability < 0.6:
            score += 5
        elif result.param_stability > 1.0:
            score -= 15

        avg_oos_sharpe = result.avg_oos_sharpe
        if avg_oos_sharpe > 1.0:
            score += 10
        elif avg_oos_sharpe > 0.5:
            score += 5
        elif avg_oos_sharpe < 0:
            score -= 20

        # Clamp
        score = max(0.0, min(100.0, score))

        if score >= 80:
            grade = "A"
        elif score >= 65:
            grade = "B"
        elif score >= 50:
            grade = "C"
        elif score >= 30:
            grade = "D"
        else:
            grade = "F"

        return {
            "score": round(score, 1),
            "grade": grade,
            "overfitting_likelihood": result.overfitting_likelihood,
            "avg_oos_sharpe": round(result.avg_oos_sharpe, 4),
            "oos_is_ratio": round(result.oos_is_ratio, 4),
            "param_stability": round(result.param_stability, 4),
            "analysis_id": result.analysis_id,
        }


# ── Module Singleton ──

_WFO: Optional[WalkForwardOptimizer] = None
_wfo_lock = threading.Lock()


def get_walk_forward() -> WalkForwardOptimizer:
    global _WFO
    if _WFO is None:
        with _wfo_lock:
            if _WFO is None:
                _WFO = WalkForwardOptimizer()
    return _WFO


# ── Convenience: Default optimize/evaluate for moving average crossover ──

def ma_crossover_optimize(prices: List[float]) -> Dict[str, float]:
    """Find optimal fast/slow MA lookback periods."""
    best_sharpe = -999.0
    best_params = {"fast": 10, "slow": 30}

    for fast in [5, 10, 15, 20]:
        for slow in [20, 30, 50, 100]:
            if slow <= fast:
                continue
            try:
                returns = _simulate_ma_crossover(prices, fast, slow)
                sharpe = _compute_sharpe(returns)
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = {"fast": float(fast), "slow": float(slow)}
            except Exception:
                continue

    return best_params


def ma_crossover_evaluate(prices: List[float],
                          params: Dict[str, float]) -> Dict[str, float]:
    """Evaluate MA crossover with given params."""
    fast = int(params.get("fast", 10))
    slow = int(params.get("slow", 30))
    returns = _simulate_ma_crossover(prices, fast, slow)

    if not returns:
        return {"sharpe": 0.0, "return": 0.0, "max_dd": 0.0, "vol": 0.0}

    sharpe = _compute_sharpe(returns)
    total_return = sum(returns)
    max_dd = _compute_max_dd(returns)
    vol = math.sqrt(sum(r * r for r in returns) / len(returns)) * math.sqrt(252)

    return {
        "sharpe": sharpe,
        "return": total_return,
        "max_dd": max_dd,
        "vol": vol,
    }


def _simulate_ma_crossover(prices: List[float], fast: int, slow: int) -> List[float]:
    """Simulate MA crossover strategy returns."""
    if len(prices) < slow + 1:
        return []

    returns = []
    position = 0  # 0 = flat, 1 = long, -1 = short

    for i in range(slow, len(prices)):
        fast_ma = sum(prices[i - fast:i]) / fast
        slow_ma = sum(prices[i - slow:i]) / slow
        prev_price = prices[i - 1]
        curr_price = prices[i]
        ret = (curr_price - prev_price) / prev_price

        if fast_ma > slow_ma and position <= 0:
            position = 1
        elif fast_ma < slow_ma and position >= 0:
            position = -1

        returns.append(ret * position)

    return returns


def _compute_sharpe(returns: List[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean_r = sum(returns) / len(returns)
    var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
    std_r = math.sqrt(var_r)
    if std_r == 0 or std_r < 1e-12:
        return 0.0
    return (mean_r / std_r) * math.sqrt(252)


def _compute_max_dd(values: List[float]) -> float:
    """Compute max drawdown from a list of values (price levels or cumulative P&L)."""
    if len(values) < 2:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak != 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ── Self-test ──

def test_walk_forward() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        wfo = WalkForwardOptimizer(results_dir=Path(tmpdir))

        # Generate synthetic price data
        import random
        rng = random.Random(42)
        price = 100.0
        prices = [price]
        for _ in range(500):
            ret = rng.gauss(0.0004, 0.015)  # ~10% annual return, 20% vol
            price *= (1.0 + ret)
            prices.append(price)

        # Test 1: Basic run
        result = wfo.run(
            prices,
            ma_crossover_optimize,
            ma_crossover_evaluate,
            strategy_name="ma_crossover",
        )
        assert len(result.windows) > 0
        assert result.analysis_id.startswith("wf-")
        assert result.overfitting_likelihood in ("low", "medium", "high")
        print(f"  ✅ Basic run: {len(result.windows)} windows, "
              f"verdict={result.overfitting_likelihood}")

        # Test 2: Metrics exist
        assert -10.0 <= result.avg_is_sharpe <= 10.0
        assert -10.0 <= result.avg_oos_sharpe <= 10.0
        assert result.oos_is_ratio >= 0.0
        print(f"  ✅ Metrics: IS S={result.avg_is_sharpe:.2f} "
              f"OOS S={result.avg_oos_sharpe:.2f} "
              f"OOS/IS={result.oos_is_ratio:.2f}")

        # Test 3: Strategy scoring
        score = wfo.score_strategy(prices, ma_crossover_optimize,
                                   ma_crossover_evaluate)
        assert 0.0 <= score["score"] <= 100.0
        assert score["grade"] in ("A", "B", "C", "D", "F")
        print(f"  ✅ Strategy scoring: {score['score']:.1f}/100 grade={score['grade']}")

        # Test 4: Persistence
        loaded = wfo.load_history(limit=5)
        assert len(loaded) >= 1, f"Expected >=1, got {len(loaded)}"
        print(f"  ✅ Persistence: {len(loaded)} analyses loaded")

        # Test 5: Empty data protection
        try:
            wfo.run([], ma_crossover_optimize, ma_crossover_evaluate)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Need at least" in str(e)
        print(f"  ✅ Empty data protection")

        # Test 6: Small data
        small_prices = [100.0 + i * 0.1 for i in range(50)]
        try:
            wfo.run(small_prices, ma_crossover_optimize, ma_crossover_evaluate)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Need at least" in str(e)
        print(f"  ✅ Small data protection")

        print(f"\n✅ T44 test_walk_forward: ALL PASSED")


if __name__ == "__main__":
    test_walk_forward()
