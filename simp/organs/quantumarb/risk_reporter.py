"""
Comprehensive Risk Reporter (T17)

Computes portfolio-level risk metrics for operator visibility.
Reads from PnL ledger, balance snapshots, and execution history.

Metrics:
- Portfolio VaR (95% confidence, 1-day) via historical simulation
- Max drawdown from peak-to-trough
- Exposure by venue and by asset
- Delta sensitivity to ±1% price move
- Fee drag (fees paid vs PnL earned)
- Win rate (24h, 7d, 30d trailing)
- Sharpe ratio (annualized)
"""

import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

log = logging.getLogger("risk_reporter")


@dataclass
class RiskReport:
    """Complete risk report snapshot."""
    portfolio_var_95pct: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate_24h: float = 0.0
    win_rate_7d: float = 0.0
    win_rate_30d: float = 0.0
    exposure_by_venue: Dict[str, float] = field(default_factory=dict)
    exposure_by_asset: Dict[str, float] = field(default_factory=dict)
    delta_usd: float = 0.0
    fee_drag_usd: float = 0.0
    total_pnl_usd: float = 0.0
    total_fees_usd: float = 0.0
    num_trades: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Risk Report ({self.timestamp[:19]})",
            f"  Portfolio VaR (95%): ${self.portfolio_var_95pct:.2f}",
            f"  Max Drawdown:        {self.max_drawdown:.1%}",
            f"  Sharpe Ratio:        {self.sharpe_ratio:.3f}",
            f"  Win Rate (24h):      {self.win_rate_24h:.1%}",
            f"  Win Rate (7d):       {self.win_rate_7d:.1%}",
            f"  Win Rate (30d):      {self.win_rate_30d:.1%}",
            f"  Delta (USD):         ${self.delta_usd:.2f}",
            f"  Fee Drag:            ${self.fee_drag_usd:.2f}",
            f"  Total PnL:           ${self.total_pnl_usd:.2f}",
            f"  Total Fees:          ${self.total_fees_usd:.2f}",
            f"  Trades:              {self.num_trades}",
        ]
        if self.exposure_by_venue:
            lines.append("  Venue Exposure:")
            for v, e in sorted(self.exposure_by_venue.items(), key=lambda x: -x[1]):
                lines.append(f"    {v}: {e:.1%}")
        if self.exposure_by_asset:
            lines.append("  Asset Exposure:")
            for a, e in sorted(self.exposure_by_asset.items(), key=lambda x: -x[1]):
                lines.append(f"    {a}: {e:.1%}")
        return "\n".join(lines)


class RiskReporter:
    """Computes and reports portfolio-level risk metrics."""

    PRICE_ESTIMATES = {
        "BTC": 77500.0, "ETH": 2314.0, "SOL": 86.50,
        "USDC": 1.0, "USDT": 1.0, "USD": 1.0,
        "JitoSOL": 92.0, "mSOL": 90.0, "stETH": 2320.0,
    }

    def __init__(
        self,
        pnl_ledger_path: str = "data/pnl_ledger.jsonl",
        snapshot_path: str = "data/balances_snapshot.json",
        risk_free_rate: float = 0.05,
    ):
        self.pnl_ledger_path = Path(pnl_ledger_path)
        self.snapshot_path = Path(snapshot_path)
        self.risk_free_rate = risk_free_rate
        self._lock = threading.Lock()

    def compute(self) -> RiskReport:
        """Compute full risk report from available data."""
        with self._lock:
            # Read PnL ledger
            trades = self._read_pnl_ledger()

            # Read balance snapshot
            snapshot = self._read_balance_snapshot()

            # Compute metrics
            pnl_values = [t.get("pnl_usd", 0.0) for t in trades]
            fees = [t.get("fees_usd", 0.0) for t in trades]
            total_pnl = sum(pnl_values) if pnl_values else 0.0
            total_fees = sum(fees) if fees else 0.0

            # Win rate by time window
            now = time.time()
            win_24h = self._win_rate(trades, now - 86400)
            win_7d = self._win_rate(trades, now - 7 * 86400)
            win_30d = self._win_rate(trades, now - 30 * 86400)

            # VaR (95% confidence, 1-day)
            var_95 = self._compute_var(pnl_values) if pnl_values else 0.0

            # Sharpe ratio
            sharpe = self._compute_sharpe(pnl_values) if pnl_values else 0.0

            # Max drawdown on equity curve
            equity = self._build_equity_curve(pnl_values)
            mdd = self._compute_max_drawdown(equity) if equity else 0.0

            # Exposure from balance snapshot
            exp_venue, exp_asset = self._compute_exposure(snapshot)

            # Delta sensitivity
            delta = self._compute_delta(snapshot)

            # Fee drag
            fee_drag = total_fees - max(total_pnl, 0) if total_fees > max(total_pnl, 0) else 0.0

            return RiskReport(
                portfolio_var_95pct=round(abs(var_95), 2),
                max_drawdown=round(mdd, 4),
                sharpe_ratio=round(sharpe, 4),
                win_rate_24h=round(win_24h, 4),
                win_rate_7d=round(win_7d, 4),
                win_rate_30d=round(win_30d, 4),
                exposure_by_venue=exp_venue,
                exposure_by_asset=exp_asset,
                delta_usd=round(delta, 2),
                fee_drag_usd=round(fee_drag, 2),
                total_pnl_usd=round(total_pnl, 2),
                total_fees_usd=round(total_fees, 2),
                num_trades=len(trades),
            )

    def _read_pnl_ledger(self) -> List[Dict[str, Any]]:
        """Read trades from PnL ledger JSONL."""
        trades = []
        if not self.pnl_ledger_path.exists():
            return trades
        try:
            with open(self.pnl_ledger_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            trades.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            log.warning(f"Failed to read PnL ledger: {e}")
        return trades

    def _read_balance_snapshot(self) -> Dict[str, Any]:
        """Read latest balance snapshot."""
        if not self.snapshot_path.exists():
            return {"balances": [], "total_portfolio_usd": 0.0}
        try:
            with open(self.snapshot_path) as f:
                return json.load(f)
        except Exception:
            return {"balances": [], "total_portfolio_usd": 0.0}

    def _win_rate(self, trades: List[Dict], since: float) -> float:
        """Win rate for trades since timestamp."""
        recent = [t for t in trades if t.get("timestamp", "") and self._ts_to_epoch(t["timestamp"]) >= since]
        if not recent:
            return 0.0
        wins = sum(1 for t in recent if t.get("pnl_usd", 0) > 0)
        return wins / len(recent)

    def _ts_to_epoch(self, ts: str) -> float:
        """Convert ISO timestamp to epoch seconds."""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0.0

    def _compute_var(self, returns: List[float], confidence: float = 0.95) -> float:
        """
        Compute Value at Risk at given confidence level.

        Uses historical simulation: sort returns, pick the (1-confidence)th percentile.
        """
        if not returns:
            return 0.0
        sorted_rets = sorted(returns)
        idx = max(0, int(len(sorted_rets) * (1 - confidence)) - 1)
        return sorted_rets[idx]

    def _compute_sharpe(self, returns: List[float]) -> float:
        """
        Compute annualized Sharpe ratio.

        Assumes daily returns. Annualized = sqrt(365) * mean(returns - rf) / std(returns).
        """
        if len(returns) < 2:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        if variance <= 0:
            return 0.0
        std = math.sqrt(variance)
        daily_rf = self.risk_free_rate / 365.0
        excess = mean_ret - daily_rf
        if std == 0:
            return 0.0
        daily_sharpe = excess / std
        return daily_sharpe * math.sqrt(365)

    def _build_equity_curve(self, pnls: List[float]) -> List[float]:
        """Build cumulative equity curve from PnL values."""
        equity = []
        cum = 0.0
        for p in pnls:
            cum += p
            equity.append(cum)
        return equity

    def _compute_max_drawdown(self, equity: List[float]) -> float:
        """
        Compute maximum drawdown from peak.

        drawdown = (peak - trough) / peak for the worst peak-to-trough.
        """
        if not equity:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for value in equity:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _compute_exposure(
        self, snapshot: Dict[str, Any]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Compute exposure by venue and by asset.

        Returns (exposure_by_venue, exposure_by_asset) as fractions of total.
        """
        balances = snapshot.get("balances", [])
        total = snapshot.get("total_portfolio_usd", 0.0) or 1.0

        by_venue: Dict[str, float] = {}
        by_asset: Dict[str, float] = {}
        for b in balances:
            venue = b.get("venue", "unknown")
            currency = b.get("currency", "unknown")
            usd_value = b.get("usd_value", 0.0)
            by_venue[venue] = by_venue.get(venue, 0.0) + usd_value
            by_asset[currency] = by_asset.get(currency, 0.0) + usd_value

        # Convert to fractions
        exp_venue = {k: round(v / total, 4) for k, v in by_venue.items()}
        exp_asset = {k: round(v / total, 4) for k, v in by_asset.items()}
        return exp_venue, exp_asset

    def _compute_delta(self, snapshot: Dict[str, Any]) -> float:
        """
        Compute portfolio delta: USD change per 1% move in all assets.

        delta = Σ (position_value × 0.01)
        """
        balances = snapshot.get("balances", [])
        delta = 0.0
        for b in balances:
            usd_value = b.get("usd_value", 0.0)
            currency = b.get("currency", "unknown")
            if currency not in ("USD", "USDC", "USDT"):
                delta += usd_value * 0.01
        return delta


def generate_synthetic_pnl(num_trades: int = 100, win_rate: float = 0.6, seed: int = 42) -> List[float]:
    """Generate synthetic PnL values for testing."""
    import random as _r
    _r.seed(seed)
    pnls = []
    for _ in range(num_trades):
        if _r.random() < win_rate:
            pnls.append(round(_r.uniform(0.01, 0.50), 4))
        else:
            pnls.append(round(_r.uniform(-0.50, -0.01), 4))
    return pnls


def test_risk_reporter():
    """Test risk reporter with synthetic data."""
    import sys, tempfile

    # Create synthetic PnL ledger
    tmp_ledger = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    pnls = generate_synthetic_pnl(100, 0.6)
    for i, pnl in enumerate(pnls):
        ts = datetime.now(timezone.utc).isoformat()
        record = {
            "execution_id": f"test_{i}",
            "signal_id": f"sig_{i}",
            "venue": "stub",
            "instrument": "BTC-USD",
            "side": "buy" if pnl < 0 else "sell",
            "size_usd": 1.0,
            "entry_px": 77000.0,
            "exit_px": 77000.0 + pnl * 0.001,
            "pnl_usd": pnl,
            "fees_usd": 0.01,
            "slippage_bps": 5,
            "status": "filled",
            "timestamp": ts,
        }
        tmp_ledger.write(json.dumps(record) + "\n")
    tmp_ledger.close()

    # Create synthetic balance snapshot
    tmp_snap = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    snapshot = {
        "total_portfolio_usd": 405.58,
        "balances": [
            {"venue": "coinbase", "currency": "USD", "total": 0.37, "usd_value": 0.37},
            {"venue": "coinbase", "currency": "BTC", "total": 0.00015, "usd_value": 11.62},
            {"venue": "coinbase", "currency": "ETH", "total": 0.0035, "usd_value": 8.10},
            {"venue": "coinbase", "currency": "SOL", "total": 0.241, "usd_value": 20.85},
            {"venue": "kraken", "currency": "USD", "total": 50.0, "usd_value": 50.0},
            {"venue": "solana", "currency": "SOL", "total": 0.241, "usd_value": 20.85},
            {"venue": "solana", "currency": "USDC", "total": 10.0, "usd_value": 10.0},
            {"venue": "staking", "currency": "JitoSOL", "total": 0.5, "usd_value": 46.0},
            {"venue": "staking", "currency": "stETH", "total": 0.02, "usd_value": 46.4},
        ],
    }
    tmp_snap.write(json.dumps(snapshot))
    tmp_snap.close()

    errors = []

    # Test 1: Create reporter
    reporter = RiskReporter(pnl_ledger_path=tmp_ledger.name, snapshot_path=tmp_snap.name)
    print("  Init:       ✅")

    # Test 2: Compute risk report
    report = reporter.compute()
    print(f"  Compute:    ✅ VaR=${report.portfolio_var_95pct:.2f}, Sharpe={report.sharpe_ratio:.3f}, MDD={report.max_drawdown:.1%}")
    assert report.num_trades == 100, f"Expected 100 trades, got {report.num_trades}"
    assert report.sharpe_ratio > 0.5, f"Expected positive Sharpe, got {report.sharpe_ratio}"
    assert report.win_rate_7d > 0.4, f"Expected win rate > 40%, got {report.win_rate_7d}"

    # Test 3: Venue and asset exposure
    assert len(report.exposure_by_venue) > 0, "Expected venue exposure"
    assert len(report.exposure_by_asset) > 0, "Expected asset exposure"
    print(f"  Exposure:   ✅ {len(report.exposure_by_venue)} venues, {len(report.exposure_by_asset)} assets")

    # Test 4: Delta
    assert report.delta_usd > 0, f"Expected positive delta, got ${report.delta_usd}"
    print(f"  Delta:      ✅ ${report.delta_usd:.2f} per 1% move")

    # Test 5: Fee drag
    assert report.total_fees_usd > 0, "Expected fees > 0"
    print(f"  Fees:       ✅ ${report.total_fees_usd:.2f} total, ${report.fee_drag_usd:.2f} drag")

    # Test 6: Summary string
    summary_str = report.summary()
    assert "VaR" in summary_str and "Sharpe" in summary_str
    print(f"  Summary:    ✅ {len(summary_str)} chars")

    # Test 7: JSON serialization
    as_dict = report.to_dict()
    assert "portfolio_var_95pct" in as_dict
    print(f"  JSON:       ✅ {len(as_dict)} fields")

    # Test 8: Edge case — empty ledger
    empty_reporter = RiskReporter(pnl_ledger_path="/tmp/nonexistent.jsonl", snapshot_path=tmp_snap.name)
    empty_report = empty_reporter.compute()
    assert empty_report.num_trades == 0
    print(f"  Empty:      ✅ empty ledger handled")

    # Test 9: Edge case — all losses
    loss_pnls = generate_synthetic_pnl(20, 0.0, seed=99)
    tmp_loss = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for i, pnl in enumerate(loss_pnls):
        ts = datetime.now(timezone.utc).isoformat()
        tmp_loss.write(json.dumps({"execution_id": f"loss_{i}", "pnl_usd": pnl, "fees_usd": 0.01, "timestamp": ts}) + "\n")
    tmp_loss.close()
    loss_reporter = RiskReporter(pnl_ledger_path=tmp_loss.name, snapshot_path=tmp_snap.name)
    loss_report = loss_reporter.compute()
    assert loss_report.win_rate_7d == 0.0, f"Expected 0% win rate, got {loss_report.win_rate_7d}"
    print(f"  Losses:     ✅ all-losses scenario handled")

    # Cleanup
    for p in [tmp_ledger.name, tmp_snap.name, tmp_loss.name]:
        try:
            os.unlink(p)
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"ALL RISK REPORTER TESTS PASSED")
    print(f"{'='*60}")
    return errors


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    test_risk_reporter()
