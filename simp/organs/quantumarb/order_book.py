"""
Order Book Model & Depth-Adjusted Arbitrage — T22
=================================================
Models exchange order book depth and computes depth-adjusted slippage
for triangular and multi-leg arbitrage.
"""

from __future__ import annotations
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("order_book")


@dataclass
class PriceLevel:
    price: float
    size: float
    cumulative_size: float = 0.0

    @classmethod
    def from_raw(cls, price: float, size: float, cum: float = 0.0) -> "PriceLevel":
        return cls(price=price, size=size, cumulative_size=cum)


@dataclass
class OrderBook:
    symbol: str
    bids: List[PriceLevel] = field(default_factory=list)
    asks: List[PriceLevel] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    @property
    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        if mid == 0:
            return 0.0
        return (self.best_ask - self.best_bid) / mid * 10000

    def fill_up_to_usd(self, side: str, usd_amount: float) -> Tuple[float, float]:
        """
        Walk the book cumulatively until we've consumed usd_amount.
        Returns (avg_fill_price, remaining_usd).
        """
        levels = self.asks if side == "buy" else self.bids
        if not levels or usd_amount <= 0:
            return 0.0, usd_amount

        total_cost = 0.0
        remaining = usd_amount
        filled = 0.0

        for level in levels:
            cost = level.price * level.size
            if cost <= remaining:
                total_cost += cost
                remaining -= cost
                filled += level.size
            else:
                partial_size = remaining / level.price
                total_cost += remaining
                remaining = 0.0
                filled += partial_size
                break

        if filled > 0:
            avg_px = total_cost / filled
        else:
            avg_px = 0.0
        return avg_px, remaining

    def to_snapshot_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "spread_bps": round(self.spread_bps, 4),
            "bid_levels": len(self.bids),
            "ask_levels": len(self.asks),
        }


@dataclass
class DepthAdjustedOpportunity:
    raw_spread_bps: float
    estimated_slippage_bps: float
    net_spread_bps: float
    max_safe_size_usd: float
    fee_bps: float
    depth_model: str
    direction: str


class DepthModel:
    """
    Estimates slippage based on order book depth.

    Models (aggressiveness: sqrt < linear < power):
      linear  — multiplier = ratio^0.5  (moderate amplification)
      sqrt    — multiplier = ratio^1.0  (most conservative)
      power   — multiplier = ratio^0.75 (most aggressive for deep fills)

    The ratio = filled_base / total_depth. For a trade that consumes the
    same fraction of the book, sqrt model amplifies the most (since it
    applies exponent 1 > 0.5), while linear is in the middle (exp=0.5).
    """

    def __init__(self, order_book: OrderBook, fee_bps: float = 25.0,
                 model: str = "linear"):
        self.book = order_book
        self.fee_bps = fee_bps
        self.model = model

    def _total_depth(self, side: str) -> float:
        levels = self.book.asks if side == "buy" else self.book.bids
        return sum(level.size for level in levels)

    def _walk_and_measure(
        self, side: str, size: float
    ) -> Tuple[float, float, float]:
        """
        Walk the book and compute (avg_fill_price, filled_base, mid_price).
        """
        levels = self.book.asks if side == "buy" else self.book.bids
        mid = self.book.mid_price
        remaining = size
        filled_cost = 0.0
        filled_base = 0.0

        for level in levels:
            cost = level.price * level.size
            if cost <= remaining:
                filled_cost += cost
                filled_base += level.size
                remaining -= cost
            else:
                partial = remaining / level.price
                filled_cost += remaining
                filled_base += partial
                remaining = 0.0
                break

        avg_px = filled_cost / filled_base if filled_base > 0 else mid
        return avg_px, filled_base, mid

    def _slippage_bps(self, avg_fill: float, mid: float) -> float:
        if mid == 0:
            return 0.0
        return abs(avg_fill - mid) / mid * 10000

    def _model_multiplier(self, filled_base: float, total_depth: float,
                          model: str) -> float:
        """
        Returns a multiplier (0..1] that scales the base slippage.
        For trade consuming a given ratio of total book depth:
          sqrt  (exp=1.0): most conservative → multiplier closer to 0 for small ratios
          linear (exp=0.5): middle ground
          power  (exp=0.75): most aggressive → multiplier closest to 1 for same ratio
        """
        if total_depth <= 0 or filled_base <= 0:
            return 0.0
        ratio = min(filled_base / total_depth, 1.0)
        if model == "sqrt":
            # exp=1.0: multiplier = ratio^1.0 = ratio (most conservative)
            return ratio
        elif model == "power":
            # exp=0.75: multiplier = ratio^0.75 (most aggressive)
            return ratio ** 0.75
        else:  # linear
            # exp=0.5: multiplier = ratio^0.5 (middle)
            return math.sqrt(ratio)

    def estimate_slippage(self, trade_size_usd: float,
                           side: str = "buy") -> Tuple[float, float]:
        if trade_size_usd <= 0:
            return 0.0, self.book.mid_price

        avg_fill, filled_base, mid = self._walk_and_measure(side, trade_size_usd)
        total_depth = self._total_depth(side)
        base_slip = self._slippage_bps(avg_fill, mid)
        multiplier = self._model_multiplier(filled_base, total_depth, self.model)
        slippage = base_slip * multiplier

        return slippage, avg_fill

    def compute_net_spread(self, trade_size_usd: float,
                           side: str = "buy") -> DepthAdjustedOpportunity:
        slippage, _ = self.estimate_slippage(trade_size_usd, side)
        raw_spread = self.book.spread_bps
        net = raw_spread - slippage - self.fee_bps
        max_safe = self._find_max_safe_size(side)

        return DepthAdjustedOpportunity(
            raw_spread_bps=round(raw_spread, 4),
            estimated_slippage_bps=round(slippage, 4),
            net_spread_bps=round(net, 4),
            max_safe_size_usd=round(max_safe, 2),
            fee_bps=self.fee_bps,
            depth_model=self.model,
            direction=side,
        )

    def _find_max_safe_size(self, side: str) -> float:
        """Binary search for largest size with positive net spread."""
        lo, hi = 0.0, 10000.0
        for _ in range(20):
            mid = (lo + hi) / 2
            slip, _ = self.estimate_slippage(mid, side)
            net = self.book.spread_bps - slip - self.fee_bps
            if net > 0:
                lo = mid
            else:
                hi = mid
        return lo


class TriangleDepthFilter:
    """
    Evaluates 3-leg triangular arbitrage paths using depth-adjusted spreads.
    """

    def __init__(self, fee_per_leg_bps: float = 25.0,
                 slippage_model: str = "linear",
                 min_net_spread_bps: float = 1.0):
        self.fee_per_leg_bps = fee_per_leg_bps
        self.slippage_model = slippage_model
        self.min_net_spread_bps = min_net_spread_bps
        self._snapshot_path = Path("data/order_book_snapshots.jsonl")

    def evaluate_path(
        self,
        legs: List[Tuple[str, str, float]],
        order_books: Dict[str, OrderBook]
    ) -> Optional[DepthAdjustedOpportunity]:
        if len(legs) != 3:
            return None

        total_fee_bps = self.fee_per_leg_bps * 3
        total_slippage_bps = 0.0
        raw_spread_bps = 0.0

        for sym, side, size_usd in legs:
            book = order_books.get(sym)
            if not book or book.mid_price == 0:
                return None
            dm = DepthModel(book, fee_bps=0, model=self.slippage_model)
            slip, _ = dm.estimate_slippage(size_usd, side)
            total_slippage_bps += slip
            raw_spread_bps += book.spread_bps

        net_spread = raw_spread_bps - total_slippage_bps - total_fee_bps

        if net_spread < self.min_net_spread_bps:
            return None

        result = DepthAdjustedOpportunity(
            raw_spread_bps=round(raw_spread_bps, 4),
            estimated_slippage_bps=round(total_slippage_bps, 4),
            net_spread_bps=round(net_spread, 4),
            max_safe_size_usd=1000.0,
            fee_bps=total_fee_bps,
            depth_model=self.slippage_model,
            direction="triangular",
        )

        self._write_snapshot(legs, result, order_books)
        return result

    def _write_snapshot(
        self,
        legs: List[Tuple[str, str, float]],
        result: DepthAdjustedOpportunity,
        order_books: Dict[str, OrderBook]
    ) -> None:
        try:
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "ts": time.time(),
                "legs": [{"sym": l[0], "side": l[1], "size_usd": l[2]} for l in legs],
                "raw_spread_bps": result.raw_spread_bps,
                "slippage_bps": result.estimated_slippage_bps,
                "net_spread_bps": result.net_spread_bps,
                "max_safe_usd": result.max_safe_size_usd,
                "depth_model": result.depth_model,
            }
            with open(self._snapshot_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            log.debug(f"Order book snapshot write error: {e}")
