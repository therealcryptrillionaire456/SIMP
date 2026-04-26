"""
Tests for PnLTracker.

Requirements:
  - test_pnl_tracker_initialization — verify setup
  - test_record_trade — verify PnL updates on buy/sell
  - test_pnl_snapshot — verify serializable output
  - test_pnl_calculation — verify buy low sell high = profit math
  - test_pnl_by_instrument — verify per-symbol breakdown
  - test_pnl_daily_aggregation — verify daily sums (via snapshot fields)
  - test_pnl_reset — verify reset clears state

No network calls. Uses pytest fixtures with tmp_path.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from simp.projectx.pnl_tracker import PnLTracker, PnLSnapshot, TradeRecord


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_snapshot_log(tmp_path: Path) -> Path:
    """Provide a unique snapshot log path per test."""
    return tmp_path / "pnl_snapshots.jsonl"


@pytest.fixture
def tracker(tmp_snapshot_log: Path) -> PnLTracker:
    """Fresh tracker with no trades, isolated temp log."""
    return PnLTracker(
        starting_equity_usd=10_000.0,
        snapshot_log=str(tmp_snapshot_log),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_fill(
    symbol: str,
    side: str,
    exec_usd: float,
    fees_usd: float = 0.0,
    ts_epoch: float | None = None,
    signal_id: str = "",
) -> dict:
    """Build a fill dict matching the execution_engine Fill.to_dict() schema."""
    return {
        "symbol": symbol,
        "side": side,
        "exec_usd": exec_usd,
        "fees_usd": fees_usd,
        "ts_epoch": ts_epoch or time.time(),
        "signal_id": signal_id,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPnlTrackerInitialization:
    """test_pnl_tracker_initialization — verify setup."""

    def test_default_equity(self, tracker: PnLTracker) -> None:
        snap = tracker.snapshot()
        assert snap.equity_usd == pytest.approx(10_000.0)
        assert snap.realised_pnl_usd == 0.0
        assert snap.total_trades == 0
        assert snap.win_rate == 0.0

    def test_custom_starting_equity(self, tmp_snapshot_log: Path) -> None:
        t = PnLTracker(starting_equity_usd=5_000.0, snapshot_log=str(tmp_snapshot_log))
        snap = t.snapshot()
        assert snap.equity_usd == pytest.approx(5_000.0)

    def test_snapshot_log_created(self, tmp_snapshot_log: Path) -> None:
        t = PnLTracker(starting_equity_usd=10_000.0, snapshot_log=str(tmp_snapshot_log))
        t.save_snapshot()
        assert tmp_snapshot_log.exists()

    def test_empty_by_symbol(self, tracker: PnLTracker) -> None:
        snap = tracker.snapshot()
        assert snap.by_symbol == {}
        assert snap.profit_factor == 0.0


class TestRecordTrade:
    """test_record_trade — record a trade, verify PnL updates."""

    def test_buy_sell_cycle_returns_trade_record(self, tracker: PnLTracker) -> None:
        # Open position
        buy = tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0, fees_usd=1.0))
        assert buy is None  # No completed trade yet

        # Close position
        sell = tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_050.0, fees_usd=1.0))
        assert sell is not None
        assert isinstance(sell, TradeRecord)
        assert sell.symbol == "BTC"

    def test_realised_pnl_updated(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("ETH", "BUY", exec_usd=500.0, fees_usd=0.5))
        tracker.record_fill(make_fill("ETH", "SELL", exec_usd=550.0, fees_usd=0.5))

        snap = tracker.snapshot()
        # pnl = close_usd - open_usd - close_fees = 550 - 500 - 0.5 = 49.5
        assert snap.realised_pnl_usd == pytest.approx(49.5)

    def test_fees_accumulated(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("SOL", "BUY", exec_usd=200.0, fees_usd=0.25))
        tracker.record_fill(make_fill("SOL", "SELL", exec_usd=210.0, fees_usd=0.25))

        snap = tracker.snapshot()
        assert snap.total_fees_usd == pytest.approx(0.50)

    def test_winning_trade_flag(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("DOGE", "BUY", exec_usd=100.0, fees_usd=0.0))
        tracker.record_fill(make_fill("DOGE", "SELL", exec_usd=120.0, fees_usd=0.0))

        snap = tracker.snapshot()
        assert snap.winning_trades == 1
        assert snap.losing_trades == 0
        assert snap.realised_pnl_usd > 0

    def test_losing_trade_flag(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("XRP", "BUY", exec_usd=100.0, fees_usd=0.0))
        tracker.record_fill(make_fill("XRP", "SELL", exec_usd=80.0, fees_usd=0.0))

        snap = tracker.snapshot()
        assert snap.winning_trades == 0
        assert snap.losing_trades == 1
        assert snap.realised_pnl_usd < 0

    def test_ignores_invalid_fill(self, tracker: PnLTracker) -> None:
        result = tracker.record_fill({"symbol": "", "side": "BUY", "exec_usd": 100})
        assert result is None

        result = tracker.record_fill({"symbol": "BTC", "side": "INVALID", "exec_usd": 100})
        assert result is None

        snap = tracker.snapshot()
        assert snap.total_trades == 0


class TestPnlSnapshot:
    """test_pnl_snapshot — call snapshot, verify serializable output."""

    def test_snapshot_to_dict_roundtrip(self, tracker: PnLTracker) -> None:
        snap = tracker.snapshot()
        d = snap.to_dict()
        assert isinstance(d, dict)
        assert "realised_pnl_usd" in d
        assert "by_symbol" in d
        assert isinstance(d["by_symbol"], dict)

    def test_snapshot_json_serializable(self, tracker: PnLTracker) -> None:
        snap = tracker.snapshot()
        json_str = json.dumps(snap.to_dict())
        parsed = json.loads(json_str)
        assert parsed["realised_pnl_usd"] == snap.realised_pnl_usd

    def test_snapshot_equity_includes_realised_pnl(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0))

        snap = tracker.snapshot()
        expected_equity = 10_000.0 + snap.realised_pnl_usd
        assert snap.equity_usd == pytest.approx(expected_equity)

    def test_win_rate_calculation(self, tracker: PnLTracker) -> None:
        # 2 wins, 1 loss
        for symbol, exec_open, exec_close in [
            ("A", 100.0, 110.0),
            ("B", 100.0, 115.0),
            ("C", 100.0, 90.0),
        ]:
            tracker.record_fill(make_fill(symbol, "BUY", exec_usd=exec_open))
            tracker.record_fill(make_fill(symbol, "SELL", exec_usd=exec_close))

        snap = tracker.snapshot()
        assert snap.total_trades == 3
        assert snap.winning_trades == 2
        assert snap.losing_trades == 1
        assert snap.win_rate == pytest.approx(2 / 3)


class TestPnlCalculation:
    """test_pnl_calculation — verify PnL math is correct (buy low sell high = profit)."""

    def test_profit_on_rising_price(self, tracker: PnLTracker) -> None:
        """Buy 1000 USD of asset at 50, sell at 55 = profit."""
        # exec_usd is the dollar value of the fill, not the price
        # Buy: spend 1000 USD to open position
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        # Sell: receive 1100 USD when closing
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0))

        snap = tracker.snapshot()
        assert snap.realised_pnl_usd == pytest.approx(100.0)

    def test_loss_on_falling_price(self, tracker: PnLTracker) -> None:
        """Buy 1000 USD of asset at 50, sell at 45 = loss."""
        tracker.record_fill(make_fill("ETH", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("ETH", "SELL", exec_usd=900.0))

        snap = tracker.snapshot()
        assert snap.realised_pnl_usd == pytest.approx(-100.0)

    def test_fees_reduce_profit(self, tracker: PnLTracker) -> None:
        """Buy 1000, sell 1100, fees 5 total = net 95 profit."""
        tracker.record_fill(make_fill("SOL", "BUY", exec_usd=1_000.0, fees_usd=2.0))
        tracker.record_fill(make_fill("SOL", "SELL", exec_usd=1_100.0, fees_usd=3.0))

        snap = tracker.snapshot()
        # pnl = close_usd - open_usd - close_fees = 1100 - 1000 - 3 = 97
        assert snap.realised_pnl_usd == pytest.approx(97.0)
        assert snap.total_fees_usd == pytest.approx(5.0)

    def test_profit_factor_gross_wins_vs_losses(self, tracker: PnLTracker) -> None:
        # Win 1: +100
        tracker.record_fill(make_fill("W1", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("W1", "SELL", exec_usd=200.0))
        # Win 2: +50
        tracker.record_fill(make_fill("W2", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("W2", "SELL", exec_usd=150.0))
        # Loss 1: -25
        tracker.record_fill(make_fill("L1", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("L1", "SELL", exec_usd=75.0))

        snap = tracker.snapshot()
        assert snap.profit_factor == pytest.approx(150.0 / 25.0)  # gross wins / gross losses

    def test_avg_win_and_avg_loss(self, tracker: PnLTracker) -> None:
        # Win 1: +100
        tracker.record_fill(make_fill("W1", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("W1", "SELL", exec_usd=200.0))
        # Loss 1: -20
        tracker.record_fill(make_fill("L1", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("L1", "SELL", exec_usd=80.0))

        snap = tracker.snapshot()
        assert snap.avg_win_usd == pytest.approx(100.0)
        assert snap.avg_loss_usd == pytest.approx(20.0)


class TestPnlByInstrument:
    """test_pnl_by_instrument — verify per-symbol breakdown."""

    def test_by_symbol_accumulates(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0))

        tracker.record_fill(make_fill("ETH", "BUY", exec_usd=500.0))
        tracker.record_fill(make_fill("ETH", "SELL", exec_usd=480.0))

        snap = tracker.snapshot()
        assert snap.by_symbol["BTC"] == pytest.approx(100.0)
        assert snap.by_symbol["ETH"] == pytest.approx(-20.0)
        assert snap.realised_pnl_usd == pytest.approx(80.0)

    def test_by_symbol_multiple_trades_same_symbol(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0))

        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=500.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=450.0))

        snap = tracker.snapshot()
        # +100 - 50 = +50
        assert snap.by_symbol["BTC"] == pytest.approx(50.0)
        assert snap.total_trades == 2

    def test_by_symbol_only_completed_trades(self, tracker: PnLTracker) -> None:
        # BTC completed
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0))

        # ETH open but not closed
        tracker.record_fill(make_fill("ETH", "BUY", exec_usd=500.0))

        snap = tracker.snapshot()
        assert "BTC" in snap.by_symbol
        assert "ETH" not in snap.by_symbol


class TestPnlDailyAggregation:
    """test_pnl_daily_aggregation — verify daily sums via snapshot fields."""

    def test_total_trades_counts_all_completed(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("A", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("A", "SELL", exec_usd=110.0))

        tracker.record_fill(make_fill("B", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("B", "SELL", exec_usd=90.0))

        tracker.record_fill(make_fill("C", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("C", "SELL", exec_usd=105.0))

        snap = tracker.snapshot()
        assert snap.total_trades == 3
        assert snap.winning_trades == 2
        assert snap.losing_trades == 1

    def test_realised_pnl_sums_correctly(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("A", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("A", "SELL", exec_usd=110.0))

        tracker.record_fill(make_fill("B", "BUY", exec_usd=100.0))
        tracker.record_fill(make_fill("B", "SELL", exec_usd=90.0))

        snap = tracker.snapshot()
        # +10 - 10 = 0
        assert snap.realised_pnl_usd == pytest.approx(0.0)

    def test_daily_aggregation_via_multiple_trade_records(self, tracker: PnLTracker) -> None:
        """Simulate multiple daily trades and verify aggregate snapshot."""
        daily_snapshots = []

        for day in range(3):
            tracker.record_fill(make_fill(f"SYM{day}", "BUY", exec_usd=100.0))
            tracker.record_fill(make_fill(f"SYM{day}", "SELL", exec_usd=110.0))
            daily_snapshots.append(tracker.snapshot())

        # Each day adds +10 pnl, accumulated
        assert daily_snapshots[0].realised_pnl_usd == pytest.approx(10.0)
        assert daily_snapshots[1].realised_pnl_usd == pytest.approx(20.0)
        assert daily_snapshots[2].realised_pnl_usd == pytest.approx(30.0)

    def test_equity_grows_with_realised_pnl(self, tracker: PnLTracker) -> None:
        initial_snap = tracker.snapshot()
        assert initial_snap.equity_usd == pytest.approx(10_000.0)

        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_150.0))

        final_snap = tracker.snapshot()
        expected_equity = 10_000.0 + final_snap.realised_pnl_usd
        assert final_snap.equity_usd == pytest.approx(expected_equity)


class TestPnlReset:
    """test_pnl_reset — verify reset clears state."""

    def test_reset_clears_trades(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0))

        # Reset by creating new tracker instance with same equity
        new_tracker = PnLTracker(
            starting_equity_usd=10_000.0,
            snapshot_log=str(tracker._log_path),
        )

        snap = new_tracker.snapshot()
        assert snap.realised_pnl_usd == 0.0
        assert snap.total_trades == 0
        assert snap.by_symbol == {}

    def test_reset_preserves_starting_equity(self, tmp_snapshot_log: Path) -> None:
        t = PnLTracker(starting_equity_usd=7_500.0, snapshot_log=str(tmp_snapshot_log))

        t.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0))
        t.record_fill(make_fill("BTC", "SELL", exec_usd=900.0))  # -100 loss

        # New instance to simulate reset
        t2 = PnLTracker(starting_equity_usd=7_500.0, snapshot_log=str(tmp_snapshot_log))
        assert t2.snapshot().equity_usd == pytest.approx(7_500.0)

    def test_record_pnl_ledger_entry_resets_correctly(
        self, tracker: PnLTracker, tmp_snapshot_log: Path
    ) -> None:
        """Verify ledger-format entry ingestion then reset."""
        tracker.record_pnl_ledger_entry({
            "symbol": "BTC",
            "side": "BUY",
            "exec_usd": 1_000.0,
            "fees_usd": 1.0,
        })
        tracker.record_pnl_ledger_entry({
            "symbol": "BTC",
            "side": "SELL",
            "exec_usd": 1_100.0,
            "fees_usd": 1.0,
        })

        snap = tracker.snapshot()
        assert snap.total_trades == 1
        assert snap.realised_pnl_usd == pytest.approx(99.0)

        # Reset
        tracker2 = PnLTracker(starting_equity_usd=10_000.0, snapshot_log=str(tmp_snapshot_log))
        snap2 = tracker2.snapshot()
        assert snap2.total_trades == 0
        assert snap2.realised_pnl_usd == 0.0


class TestPnlEdgeCases:
    """Additional edge-case coverage for robustness."""

    def test_zero_fees_handled(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0, fees_usd=0.0))
        tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_050.0, fees_usd=0.0))
        snap = tracker.snapshot()
        assert snap.realised_pnl_usd == pytest.approx(50.0)
        assert snap.total_fees_usd == 0.0

    def test_signal_id_preserved(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("BTC", "BUY", exec_usd=1_000.0, signal_id="sig_abc"))
        trade = tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0, signal_id="sig_abc"))
        assert trade is not None
        assert trade.signal_id == "sig_abc"

    def test_trade_record_won_property(self, tracker: PnLTracker) -> None:
        tracker.record_fill(make_fill("W", "BUY", exec_usd=100.0))
        win_trade = tracker.record_fill(make_fill("W", "SELL", exec_usd=120.0))

        tracker.record_fill(make_fill("L", "BUY", exec_usd=100.0))
        loss_trade = tracker.record_fill(make_fill("L", "SELL", exec_usd=80.0))

        assert win_trade is not None and win_trade.won is True
        assert loss_trade is not None and loss_trade.won is False

    def test_snapshot_without_any_trades(self, tracker: PnLTracker) -> None:
        snap = tracker.snapshot()
        assert snap.total_trades == 0
        assert snap.winning_trades == 0
        assert snap.losing_trades == 0
        assert snap.win_rate == 0.0
        assert snap.profit_factor == 0.0
        assert snap.avg_win_usd == 0.0
        assert snap.avg_loss_usd == 0.0

    def test_max_drawdown_tracked(self, tracker: PnLTracker) -> None:
        # Simulate a drawdown sequence
        tracker.record_fill(make_fill("T1", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("T1", "SELL", exec_usd=1_200.0))  # +200

        tracker.record_fill(make_fill("T2", "BUY", exec_usd=1_000.0))
        tracker.record_fill(make_fill("T2", "SELL", exec_usd=800.0))  # -200

        snap = tracker.snapshot()
        assert snap.max_drawdown_usd > 0

    def test_duplicate_sell_without_open_ignored(self, tracker: PnLTracker) -> None:
        # SELL without prior BUY should be ignored (no open position)
        result = tracker.record_fill(make_fill("BTC", "SELL", exec_usd=1_100.0))
        assert result is None
        snap = tracker.snapshot()
        assert snap.total_trades == 0
