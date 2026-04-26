"""
T44: Walk-Forward Analysis for Overfit Detection
============================================
Rolling window backtest to detect overfitting.

Walk-forward analysis:
1. Train on in-sample data
2. Test on out-of-sample data
3. Roll window forward
4. Compare performance to detect overfit

Overfit indicators:
- In-sample Sharpe >> Out-of-sample Sharpe (>50% difference)
- Large variance in out-of-sample performance
- Sudden performance collapse in OOS
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("walk_forward")

# ── Constants ───────────────────────────────────────────────────────────

DEFAULT_TRAIN_WINDOW_DAYS = 90
DEFAULT_TEST_WINDOW_DAYS = 30
DEFAULT_ROLLING_STEP_DAYS = 7


@dataclass
class WindowResult:
    """Result for a single walk-forward window."""
    window_id: str
    start_date: str
    end_date: str
    is_train: bool  # True = training, False = test
    
    # Performance metrics
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    
    # Overfit indicators
    vs_prior_is_ratio: float = 0.0  # OOS / IS ratio
    drawdown_vs_is: float = 0.0  # OOS drawdown / IS drawdown

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "is_train": self.is_train,
            "sharpe_ratio": self.sharpe_ratio,
            "total_return": self.total_return,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "num_trades": self.num_trades,
            "vs_prior_is_ratio": self.vs_prior_is_ratio,
            "drawdown_vs_is": self.drawdown_vs_is,
        }


@dataclass
class WalkForwardReport:
    """Report for full walk-forward analysis."""
    strategy_name: str
    train_windows: List[WindowResult]
    test_windows: List[WindowResult]
    
    # Summary statistics
    is_sharpe_mean: float = 0.0
    oos_sharpe_mean: float = 0.0
    sharpe_decay: float = 0.0  # (IS - OOS) / IS
    
    is_return_mean: float = 0.0
    oos_return_mean: float = 0.0
    return_decay: float = 0.0
    
    overfit_detected: bool = False
    overfit_confidence: float = 0.0  # 0-1
    overfit_reasons: List[str] = field(default_factory=list)
    
    # Stability metrics
    oos_sharpe_std: float = 0.0
    oos_return_std: float = 0.0
    stability_score: float = 0.0  # Higher = more stable
    
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "num_train_windows": len(self.train_windows),
            "num_test_windows": len(self.test_windows),
            "is_sharpe_mean": self.is_sharpe_mean,
            "oos_sharpe_mean": self.oos_sharpe_mean,
            "sharpe_decay": self.sharpe_decay,
            "is_return_mean": self.is_return_mean,
            "oos_return_mean": self.oos_return_mean,
            "return_decay": self.return_decay,
            "overfit_detected": self.overfit_detected,
            "overfit_confidence": self.overfit_confidence,
            "overfit_reasons": self.overfit_reasons,
            "oos_sharpe_std": self.oos_sharpe_std,
            "stability_score": self.stability_score,
            "timestamp": self.timestamp,
        }

    def summary(self) -> str:
        overfit_status = "⚠️  OVERFIT DETECTED" if self.overfit_detected else "✅  STABLE"
        return (
            f"Walk-Forward Analysis: {self.strategy_name}\n"
            f"  Status: {overfit_status} (confidence={self.overfit_confidence:.0%})\n"
            f"  IS Sharpe: {self.is_sharpe_mean:.2f}, OOS Sharpe: {self.oos_sharpe_mean:.2f}\n"
            f"  Sharpe Decay: {self.sharpe_decay:.1%}\n"
            f"  OOS Stability: {self.stability_score:.1%}\n"
            f"  Windows: {len(self.train_windows)} train, {len(self.test_windows)} test"
        )


class WalkForwardAnalyzer:
    """
    Walk-forward analysis to detect strategy overfitting.
    
    Process:
    1. Split data into rolling windows
    2. Train strategy parameters on in-sample data
    3. Test on out-of-sample data
    4. Compare performance
    """

    def __init__(
        self,
        train_window_days: int = DEFAULT_TRAIN_WINDOW_DAYS,
        test_window_days: int = DEFAULT_TEST_WINDOW_DAYS,
        rolling_step_days: int = DEFAULT_ROLLING_STEP_DAYS,
    ):
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.rolling_step_days = rolling_step_days

    def analyze(
        self,
        strategy_name: str,
        trades: List[Dict[str, Any]],
        returns: Optional[List[float]] = None,
    ) -> WalkForwardReport:
        """
        Run walk-forward analysis.
        
        Args:
            strategy_name: Name of the strategy
            trades: List of trade records with date, pnl, etc.
            returns: Optional list of returns (alternative to trades)
            
        Returns:
            WalkForwardReport with analysis results
        """
        if not trades and not returns:
            raise ValueError("Must provide either trades or returns")
        
        # Sort by date
        if trades:
            trades = sorted(trades, key=lambda t: t.get("date", ""))
        
        # Generate windows
        train_windows, test_windows = self._generate_windows(trades, returns)
        
        # Calculate statistics
        train_results, test_results = self._calculate_metrics(train_windows, test_windows)
        
        # Detect overfitting
        report = self._detect_overfit(strategy_name, train_results, test_results)
        
        return report

    def _generate_windows(
        self,
        trades: List[Dict[str, Any]],
        returns: Optional[List[float]],
    ) -> Tuple[List[List[Dict]], List[List[Dict]]]:
        """Generate rolling train/test windows."""
        train_windows = []
        test_windows = []
        
        # Simple rolling window generation
        total_days = self.train_window_days + self.test_window_days
        num_windows = max(1, (100 - total_days) // self.rolling_step_days)
        
        for i in range(num_windows):
            train_start = i * self.rolling_step_days
            train_end = train_start + self.train_window_days
            test_start = train_end
            test_end = min(test_start + self.test_window_days, 100)
            
            if test_end <= test_start:
                break
            
            # Extract window data
            train_trades = trades[train_start:train_end] if trades else []
            test_trades = trades[test_start:test_end] if trades else []
            
            train_windows.append(train_trades)
            test_windows.append(test_trades)
        
        return train_windows, test_windows

    def _calculate_metrics(
        self,
        train_windows: List[List[Dict]],
        test_windows: List[List[Dict]],
    ) -> Tuple[List[WindowResult], List[WindowResult]]:
        """Calculate metrics for each window."""
        train_results = []
        test_results = []
        
        for i, (train, test) in enumerate(zip(train_windows, test_windows)):
            # In-sample metrics
            train_result = self._window_metrics(
                f"train_{i}", train, is_train=True
            )
            train_results.append(train_result)
            
            # Out-of-sample metrics
            test_result = self._window_metrics(
                f"test_{i}", test, is_train=False
            )
            
            # Calculate vs IS ratio if we have a prior train window
            if i > 0:
                prev_train = train_results[i-1]
                if prev_train.sharpe_ratio > 0:
                    test_result.vs_prior_is_ratio = test_result.sharpe_ratio / prev_train.sharpe_ratio
                if prev_train.max_drawdown > 0:
                    test_result.drawdown_vs_is = test_result.max_drawdown / prev_train.max_drawdown
            
            test_results.append(test_result)
        
        return train_results, test_results

    def _window_metrics(
        self,
        window_id: str,
        trades: List[Dict],
        is_train: bool,
    ) -> WindowResult:
        """Calculate metrics for a single window."""
        if not trades:
            return WindowResult(
                window_id=window_id,
                start_date="unknown",
                end_date="unknown",
                is_train=is_train,
                sharpe_ratio=0.0,
                total_return=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                num_trades=0,
            )
        
        pnls = [t.get("pnl", 0) for t in trades]
        returns = [t.get("return", 0) for t in trades]
        
        total_return = sum(pnls)
        num_trades = len(trades)
        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / num_trades if num_trades > 0 else 0.0
        
        # Calculate Sharpe (simplified)
        mean_ret = sum(returns) / len(returns) if returns else 0.0
        std_ret = math.sqrt(sum((r - mean_ret)**2 for r in returns) / len(returns)) if returns else 1.0
        sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0
        
        # Calculate max drawdown
        equity = 10000.0  # Starting capital
        peak = equity
        max_dd = 0.0
        for pnl in pnls:
            equity += pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        
        return WindowResult(
            window_id=window_id,
            start_date=trades[0].get("date", "unknown") if trades else "unknown",
            end_date=trades[-1].get("date", "unknown") if trades else "unknown",
            is_train=is_train,
            sharpe_ratio=sharpe,
            total_return=total_return,
            max_drawdown=max_dd,
            win_rate=win_rate,
            num_trades=num_trades,
        )

    def _detect_overfit(
        self,
        strategy_name: str,
        train_results: List[WindowResult],
        test_results: List[WindowResult],
    ) -> WalkForwardReport:
        """Detect overfitting based on IS vs OOS performance."""
        # Calculate mean metrics
        is_sharpe = [r.sharpe_ratio for r in train_results]
        oos_sharpe = [r.sharpe_ratio for r in test_results]
        oos_returns = [r.total_return for r in test_results]
        
        is_sharpe_mean = sum(is_sharpe) / len(is_sharpe) if is_sharpe else 0.0
        oos_sharpe_mean = sum(oos_sharpe) / len(oos_sharpe) if oos_sharpe else 0.0
        oos_sharpe_std = math.sqrt(sum((s - oos_sharpe_mean)**2 for s in oos_sharpe) / len(oos_sharpe)) if oos_sharpe else 0.0
        oos_return_std = math.sqrt(sum((r - sum(oos_returns)/len(oos_returns))**2 for r in oos_returns) / len(oos_returns)) if oos_returns else 0.0
        
        # Sharpe decay
        sharpe_decay = (is_sharpe_mean - oos_sharpe_mean) / is_sharpe_mean if is_sharpe_mean != 0 else 0.0
        
        # Return decay
        is_return_mean = sum(r.total_return for r in train_results) / len(train_results) if train_results else 0.0
        oos_return_mean = sum(oos_returns) / len(oos_returns) if oos_returns else 0.0
        return_decay = (is_return_mean - oos_return_mean) / abs(is_return_mean) if is_return_mean != 0 else 0.0
        
        # Overfit detection
        overfit_reasons = []
        overfit_confidence = 0.0
        
        # Sharpe decay > 30% indicates overfitting
        if sharpe_decay > 0.3:
            overfit_reasons.append(f"Sharpe decay {sharpe_decay:.0%} > 30%")
            overfit_confidence += 0.4
        
        # Sharpe decay > 50% is strong overfit signal
        if sharpe_decay > 0.5:
            overfit_reasons.append(f"Sharpe decay {sharpe_decay:.0%} > 50% (strong overfit)")
            overfit_confidence += 0.3
        
        # High variance in OOS Sharpe
        if oos_sharpe_std > 1.0:
            overfit_reasons.append(f"High OOS variance (std={oos_sharpe_std:.2f})")
            overfit_confidence += 0.2
        
        # OOS Sharpe consistently negative while IS positive
        if is_sharpe_mean > 0.5 and oos_sharpe_mean < 0:
            overfit_reasons.append("OOS Sharpe negative while IS positive")
            overfit_confidence += 0.3
        
        # Stability score
        stability_score = 1.0 - min(1.0, oos_sharpe_std / 2.0) if oos_sharpe_std else 1.0
        
        return WalkForwardReport(
            strategy_name=strategy_name,
            train_windows=train_results,
            test_windows=test_results,
            is_sharpe_mean=is_sharpe_mean,
            oos_sharpe_mean=oos_sharpe_mean,
            sharpe_decay=sharpe_decay,
            is_return_mean=is_return_mean,
            oos_return_mean=oos_return_mean,
            return_decay=return_decay,
            overfit_detected=overfit_confidence >= 0.5,
            overfit_confidence=min(1.0, overfit_confidence),
            overfit_reasons=overfit_reasons,
            oos_sharpe_std=oos_sharpe_std,
            oos_return_std=oos_return_std,
            stability_score=stability_score,
        )


# ── Module-level singleton ──────────────────────────────────────────────

_analyzer: Optional[WalkForwardAnalyzer] = None


def get_walk_forward_analyzer(**kwargs) -> WalkForwardAnalyzer:
    """Get or create the global WalkForwardAnalyzer singleton."""
    global _analyzer
    if _analyzer is None:
        _analyzer = WalkForwardAnalyzer(**kwargs)
    return _analyzer


# ── Demo / Test ─────────────────────────────────────────────────────────

def demo_walk_forward():
    """Demonstrate walk-forward analysis."""
    print("=" * 60)
    print("T44 — Walk-Forward Analysis Demo")
    print("=" * 60)

    analyzer = WalkForwardAnalyzer(
        train_window_days=60,
        test_window_days=20,
        rolling_step_days=10,
    )

    # Generate synthetic trade data
    trades = []
    for i in range(100):
        trades.append({
            "date": f"2024-01-{i+1:02d}",
            "pnl": random.gauss(10, 50),
            "return": random.gauss(0.001, 0.02),
        })

    print(f"\n[1] Generated {len(trades)} synthetic trades")

    print(f"\n[2] Running walk-forward analysis...")
    report = analyzer.analyze("quantumarb", trades)

    print(f"\n[3] Results:")
    print(report.summary())

    if report.overfit_reasons:
        print(f"\n[4] Overfit reasons:")
        for reason in report.overfit_reasons:
            print(f"    ⚠️  {reason}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_walk_forward()
