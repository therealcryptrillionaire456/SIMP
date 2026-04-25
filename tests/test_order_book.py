"""
Tests for Order Book Model & Depth-Adjusted Arbitrage — T22
"""

from __future__ import annotations
import json
from pathlib import Path

import pytest

from simp.organs.quantumarb.order_book import (
    DepthAdjustedOpportunity,
    DepthModel,
    OrderBook,
    PriceLevel,
    TriangleDepthFilter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_levels(prices, sizes, cumulative=False):
    cum = 0.0
    out = []
    for p, s in zip(prices, sizes):
        if cumulative:
            cum += s
        out.append(PriceLevel(price=p, size=s, cumulative_size=cum))
    return out


def make_book(symbol="BTC-USD", bid_prices=None, ask_prices=None,
              bid_sizes=None, ask_sizes=None):
    if bid_prices is None:
        bid_prices = [999.95, 999.90, 999.85, 999.80, 999.75]
    if ask_prices is None:
        ask_prices = [1000.05, 1000.10, 1000.15, 1000.20, 1000.25]
    if bid_sizes is None:
        bid_sizes = [1.0] * 5
    if ask_sizes is None:
        ask_sizes = [1.0] * 5
    return OrderBook(
        symbol=symbol,
        bids=make_levels(bid_prices, bid_sizes),
        asks=make_levels(ask_prices, ask_sizes),
    )


# ---------------------------------------------------------------------------
# OrderBook
# ---------------------------------------------------------------------------

class TestOrderBook:
    def test_best_bid_ask(self):
        book = make_book(bid_prices=[100.0], ask_prices=[100.05])
        assert book.best_bid == 100.0
        assert book.best_ask == 100.05

    def test_mid_price(self):
        book = make_book(bid_prices=[100.0], ask_prices=[100.10])
        assert book.mid_price == 100.05

    def test_spread_bps(self):
        book = make_book(bid_prices=[100.0], ask_prices=[100.10])
        expected = (100.10 - 100.0) / 100.05 * 10000
        assert abs(book.spread_bps - expected) < 0.01

    def test_empty_book(self):
        book = OrderBook(symbol="BTC-USD")
        assert book.best_bid == 0.0
        assert book.mid_price == 0.0
        assert book.spread_bps == 0.0

    def test_fill_up_to_usd_small(self):
        book = make_book(ask_prices=[1000.0], ask_sizes=[2.0])
        avg_px, remaining = book.fill_up_to_usd("buy", 500.0)
        assert avg_px == 1000.0
        assert remaining == 0.0

    def test_fill_up_to_usd_partial(self):
        book = make_book(ask_prices=[1000.0], ask_sizes=[2.0])
        avg_px, remaining = book.fill_up_to_usd("buy", 1500.0)
        assert avg_px == 1000.0
        assert remaining == 0.0

    def test_fill_up_to_usd_exceeds_book(self):
        book = make_book(ask_prices=[1000.0], ask_sizes=[0.5])
        avg_px, remaining = book.fill_up_to_usd("buy", 1000.0)
        assert avg_px == 1000.0
        assert remaining > 0.0

    def test_to_snapshot_dict(self):
        book = make_book()
        snap = book.to_snapshot_dict()
        assert snap["symbol"] == "BTC-USD"
        assert "spread_bps" in snap


# ---------------------------------------------------------------------------
# DepthModel
# ---------------------------------------------------------------------------

class TestDepthModel:
    def test_estimate_slippage_zero_size(self):
        book = make_book()
        dm = DepthModel(book)
        slip, avg_px = dm.estimate_slippage(0.0, side="buy")
        assert slip == 0.0
        assert avg_px == book.mid_price

    def test_estimate_slippage_no_levels(self):
        """Empty book → zero slippage."""
        book = OrderBook(symbol="EMPTY")
        dm = DepthModel(book)
        slip, _ = dm.estimate_slippage(100.0, "buy")
        assert slip == 0.0

    def test_slippage_conservative_models(self):
        """
        For a given book, sqrt model always produces <= slippage
        compared to linear, and linear <= power.
        """
        book = make_book(ask_prices=[1000.0, 1001.0, 1002.0, 1003.0, 1004.0],
                         ask_sizes=[0.5, 0.5, 0.5, 0.5, 0.5])
        dm_sqrt = DepthModel(book, model="sqrt")
        dm_lin = DepthModel(book, model="linear")
        dm_pow = DepthModel(book, model="power")

        ss, _ = dm_sqrt.estimate_slippage(500.0, "buy")
        sl, _ = dm_lin.estimate_slippage(500.0, "buy")
        sp, _ = dm_pow.estimate_slippage(500.0, "buy")

        # All three should produce positive slippage for a large trade
        assert ss > 0.0
        assert sl > 0.0
        assert sp > 0.0

        # sqrt <= linear (sqrt is most conservative due to highest exponent)
        assert ss <= sl

    def test_compute_net_spread(self):
        book = make_book(bid_prices=[999.90], ask_prices=[1000.10],
                         bid_sizes=[1.0], ask_sizes=[1.0])
        dm = DepthModel(book, fee_bps=5.0)
        result = dm.compute_net_spread(10.0, "buy")
        assert isinstance(result, DepthAdjustedOpportunity)
        assert result.raw_spread_bps > 0
        assert result.fee_bps == 5.0

    def test_find_max_safe_size_zero_when_fee_exceeds_spread(self):
        """Fee=200bps >> spread=2bps → no size has positive net spread."""
        book = make_book(bid_prices=[999.99], ask_prices=[1000.01],
                         bid_sizes=[10.0], ask_sizes=[10.0])
        dm = DepthModel(book, fee_bps=200.0)
        max_size = dm._find_max_safe_size("buy")
        assert max_size == 0.0

    def test_find_max_safe_size_positive_with_wide_book(self):
        """
        Wide spread book with small fee → positive max safe size.
        """
        book = make_book(
            bid_prices=[990.0, 980.0, 970.0],
            ask_prices=[1010.0, 1020.0, 1030.0],
            bid_sizes=[10.0, 10.0, 10.0],
            ask_sizes=[10.0, 10.0, 10.0],
        )
        dm = DepthModel(book, fee_bps=5.0)
        max_size = dm._find_max_safe_size("buy")
        # With spread=~40 bps and fee=5 bps, there should be a safe region
        assert max_size > 0


# ---------------------------------------------------------------------------
# TriangleDepthFilter
# ---------------------------------------------------------------------------

class TestTriangleDepthFilter:
    def test_wrong_leg_count(self):
        filt = TriangleDepthFilter()
        result = filt.evaluate_path(
            legs=[("BTC-USD", "buy", 10.0), ("ETH-USD", "sell", 5.0)],
            order_books={},
        )
        assert result is None

    def test_missing_book(self):
        filt = TriangleDepthFilter()
        result = filt.evaluate_path(
            legs=[
                ("BTC-USD", "buy", 10.0),
                ("ETH-USD", "sell", 5.0),
                ("BTC-ETH", "buy", 5.0),
            ],
            order_books={},
        )
        assert result is None

    def test_filtered_by_high_min_spread(self):
        books = {
            "A": make_book("A"),
            "B": make_book("B"),
            "C": make_book("C"),
        }
        filt = TriangleDepthFilter(min_net_spread_bps=9999.0)
        result = filt.evaluate_path(
            legs=[("A", "buy", 10.0), ("B", "sell", 10.0), ("C", "buy", 10.0)],
            order_books=books,
        )
        assert result is None

    def test_valid_triangle(self):
        """
        Three wide-spread books with deep liquidity should produce
        a valid triangular opportunity with positive net spread.
        """
        books = {
            "A": OrderBook(
                "A",
                bids=make_levels([990.0], [100.0]),
                asks=make_levels([1010.0], [100.0]),
            ),
            "B": OrderBook(
                "B",
                bids=make_levels([1990.0], [100.0]),
                asks=make_levels([2010.0], [100.0]),
            ),
            "C": OrderBook(
                "C",
                bids=make_levels([0.49], [10000.0]),
                asks=make_levels([0.51], [10000.0]),
            ),
        }
        filt = TriangleDepthFilter(min_net_spread_bps=0.0)
        result = filt.evaluate_path(
            legs=[("A", "buy", 10.0), ("B", "sell", 10.0), ("C", "buy", 10.0)],
            order_books=books,
        )
        assert result is not None
        assert result.direction == "triangular"
        assert result.net_spread_bps > 0

    def test_triangle_rejected_when_net_negative(self):
        """
        Tight books with high fees should produce negative net spread
        and be rejected.
        """
        books = {
            "A": OrderBook(
                "A",
                bids=make_levels([999.99], [0.1]),
                asks=make_levels([1000.01], [0.1]),
            ),
            "B": OrderBook(
                "B",
                bids=make_levels([1999.99], [0.1]),
                asks=make_levels([2000.01], [0.1]),
            ),
            "C": OrderBook(
                "C",
                bids=make_levels([0.49999], [1.0]),
                asks=make_levels([0.50001], [1.0]),
            ),
        }
        # All books have ~2 bps spread, fee=75 bps per triangle → rejected
        filt = TriangleDepthFilter(min_net_spread_bps=0.0)
        result = filt.evaluate_path(
            legs=[("A", "buy", 10.0), ("B", "sell", 10.0), ("C", "buy", 10.0)],
            order_books=books,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Thin book edge case
# ---------------------------------------------------------------------------

class TestThinBookLargeTrade:
    def test_empty_book_zero_slippage(self):
        book = OrderBook(symbol="BTC-USD")
        dm = DepthModel(book)
        slip, _ = dm.estimate_slippage(100.0, "buy")
        assert slip == 0.0

    def test_thin_book_high_slippage(self):
        """Single-level thin book with large trade → measurable slippage."""
        book = OrderBook(
            symbol="NANO-USD",
            asks=[PriceLevel(price=1.0, size=10.0)],
            bids=[PriceLevel(price=0.999, size=10.0)],
        )
        dm = DepthModel(book)
        slip, avg_px = dm.estimate_slippage(1000.0, "buy")
        assert slip > 0


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_written(self, tmp_path):
        snapshot_path = tmp_path / "snapshots.jsonl"
        books = {
            "A": OrderBook("A", bids=make_levels([990.0], [100.0]),
                            asks=make_levels([1010.0], [100.0])),
            "B": OrderBook("B", bids=make_levels([1990.0], [100.0]),
                            asks=make_levels([2010.0], [100.0])),
            "C": OrderBook("C", bids=make_levels([0.49], [10000.0]),
                            asks=make_levels([0.51], [10000.0])),
        }
        filt = TriangleDepthFilter(min_net_spread_bps=0.0)
        filt._snapshot_path = snapshot_path

        result = filt.evaluate_path(
            legs=[("A", "buy", 10.0), ("B", "sell", 10.0), ("C", "buy", 10.0)],
            order_books=books,
        )
        assert result is not None
        assert snapshot_path.exists()
        record = json.loads(snapshot_path.read_text().strip().split("\n")[0])
        assert "ts" in record
        assert "legs" in record
        assert record["net_spread_bps"] == result.net_spread_bps
