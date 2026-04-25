"""
Multi-Venue Liquidity Scoring — T21
====================================
Weight signals by depth, spread, slippage history per venue (Kraken, Bitstamp,
Coinbase, Jupiter) to improve arb path quality.

For each venue + symbol, computes:
  - Depth score: order book depth at ±1% from mid
  - Spread score: tighter spread = higher score
  - Slippage history percentile: venues with lower average slippage score higher
  - Composite liquidity score: weighted average of all three

Usage:
    scorer = LiquidityScorer()
    scores = scorer.score_venues("BTC-USD", venues=["coinbase", "kraken"])
    best = scorer.best_venue("BTC-USD")  # returns venue name
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("liquidity_scorer")


@dataclass
class LiquidityScore:
    """Liquidity score for a venue + symbol pair."""
    venue: str
    symbol: str
    depth_score: float        # 0.0 to 1.0
    spread_score: float       # 0.0 to 1.0
    slippage_history_score: float  # 0.0 to 1.0
    composite: float          # weighted average, 0.0 to 1.0
    order_book_bid_depth: float   # USD depth at ±1% on bid side
    order_book_ask_depth: float   # USD depth at ±1% on ask side
    spread_bps: float
    avg_slippage_bps: float
    sample_count: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class LiquidityScorer:
    """
    Scores venue liquidity using depth, spread, and slippage history.

    Thread-safe. Accumulates slippage observations per venue+symbol and
    provides real-time liquidity scores.
    """

    # Weights for composite score
    DEPTH_WEIGHT = 0.40
    SPREAD_WEIGHT = 0.35
    SLIPPAGE_WEIGHT = 0.25

    # Lookback window for slippage history
    MAX_SLIPPAGE_SAMPLES = 100

    def __init__(self, data_dir: str = "data/liquidity"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        # slippage_history[venue][symbol] = list of slippage_bps values
        self._slippage_history: Dict[str, Dict[str, List[float]]] = {}
        self._scores: Dict[str, Dict[str, LiquidityScore]] = {}

        # Load historical scores
        self._load_scores()

        log.info("LiquidityScorer initialized (data_dir=%s)", data_dir)

    # ── Public API ──────────────────────────────────────────────────────

    def record_slippage(
        self, venue: str, symbol: str, slippage_bps: float
    ) -> None:
        """Record a slippage observation for a venue + symbol pair."""
        with self._lock:
            self._slippage_history.setdefault(venue, {}).setdefault(symbol, [])
            hist = self._slippage_history[venue][symbol]
            hist.append(slippage_bps)
            # Trim to max samples
            if len(hist) > self.MAX_SLIPPAGE_SAMPLES:
                self._slippage_history[venue][symbol] = hist[-self.MAX_SLIPPAGE_SAMPLES:]

    def score_venue(
        self,
        symbol: str,
        venue: str,
        bid_depth: float = 0.0,
        ask_depth: float = 0.0,
        spread_bps: float = 0.0,
    ) -> LiquidityScore:
        """
        Compute liquidity score for a single venue + symbol.

        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            venue: Exchange name (e.g., "coinbase", "kraken")
            bid_depth: Order book depth on bid side (USD)
            ask_depth: Order book depth on ask side (USD)
            spread_bps: Current bid-ask spread in basis points

        Returns:
            LiquidityScore with component and composite scores.
        """
        # Depth score: deeper book = higher score
        total_depth = bid_depth + ask_depth
        # Normalize: $1M = score 0.5, $10M = 0.91, $100M+ = 1.0
        depth_score = min(1.0, total_depth / 10_000_000.0) if total_depth > 0 else 0.0

        # Spread score: tighter spread = higher score
        # 1 bps = 1.0, 5 bps = 0.8, 10 bps = 0.5, 50 bps = 0.0
        spread_score = max(0.0, 1.0 - (spread_bps / 50.0)) if spread_bps > 0 else 0.5

        # Slippage history score: lower avg slippage = higher score
        slippage_score = 0.5  # default neutral
        avg_slippage = 0.0
        sample_count = 0
        with self._lock:
            hist = self._slippage_history.get(venue, {}).get(symbol, [])
            sample_count = len(hist)
            if hist:
                avg_slippage = sum(hist) / len(hist)
                # 1 bps avg slippage = 0.95, 5 bps = 0.75, 20 bps = 0.0
                slippage_score = max(0.0, 1.0 - (avg_slippage / 20.0))

        # Composite
        composite = (
            self.DEPTH_WEIGHT * depth_score
            + self.SPREAD_WEIGHT * spread_score
            + self.SLIPPAGE_WEIGHT * slippage_score
        )

        score = LiquidityScore(
            venue=venue,
            symbol=symbol,
            depth_score=round(depth_score, 4),
            spread_score=round(spread_score, 4),
            slippage_history_score=round(slippage_score, 4),
            composite=round(composite, 4),
            order_book_bid_depth=round(bid_depth, 2),
            order_book_ask_depth=round(ask_depth, 2),
            spread_bps=round(spread_bps, 2),
            avg_slippage_bps=round(avg_slippage, 4),
            sample_count=sample_count,
        )

        # Cache
        with self._lock:
            self._scores.setdefault(symbol, {})[venue] = score

        return score

    def score_venues(
        self,
        symbol: str,
        venues: Optional[List[str]] = None,
        depth_map: Optional[Dict[str, Tuple[float, float]]] = None,
        spread_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, LiquidityScore]:
        """
        Score multiple venues for a symbol.

        Args:
            symbol: Trading pair
            venues: List of venue names. If None, returns all cached.
            depth_map: Dict[venue, (bid_depth, ask_depth)]
            spread_map: Dict[venue, spread_bps]

        Returns:
            Dict[venue, LiquidityScore]
        """
        if venues is None:
            with self._lock:
                venues = list(self._scores.get(symbol, {}).keys())
            if not venues:
                return {}

        depth_map = depth_map or {}
        spread_map = spread_map or {}

        results: Dict[str, LiquidityScore] = {}
        for venue in venues:
            bid_d, ask_d = depth_map.get(venue, (0.0, 0.0))
            sp = spread_map.get(venue, 0.0)
            results[venue] = self.score_venue(
                symbol=symbol,
                venue=venue,
                bid_depth=bid_d,
                ask_depth=ask_d,
                spread_bps=sp,
            )
        return results

    def best_venue(
        self,
        symbol: str,
        venues: Optional[List[str]] = None,
        min_composite: float = 0.3,
    ) -> Optional[str]:
        """
        Return the venue with the highest composite score for a symbol.

        Args:
            symbol: Trading pair
            venues: Optional list of venues to consider
            min_composite: Minimum composite score to consider

        Returns:
            Best venue name, or None if none qualify.
        """
        scores = self.score_venues(symbol, venues)
        if not scores:
            return None

        best = max(scores.values(), key=lambda s: s.composite)
        if best.composite < min_composite:
            return None
        return best.venue

    def rank_venues(
        self, symbol: str, venues: Optional[List[str]] = None
    ) -> List[Tuple[str, LiquidityScore]]:
        """Return venues sorted by composite score (descending)."""
        scores = self.score_venues(symbol, venues)
        return sorted(scores.items(), key=lambda x: x[1].composite, reverse=True)

    def get_cached_score(self, venue: str, symbol: str) -> Optional[LiquidityScore]:
        """Get the most recent cached score for a venue + symbol."""
        with self._lock:
            return self._scores.get(symbol, {}).get(venue)

    def persist(self) -> str:
        """Write all cached scores to a JSON file."""
        path = self._data_dir / "liquidity_scores.json"
        with self._lock:
            data = {
                sym: {v: s.to_dict() for v, s in venues.items()}
                for sym, venues in self._scores.items()
            }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("Persisted liquidity scores to %s", path)
        return str(path)

    def _load_scores(self) -> None:
        """Load cached scores from disk."""
        path = self._data_dir / "liquidity_scores.json"
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            with self._lock:
                for sym, venues in data.items():
                    for venue, sdata in venues.items():
                        score = LiquidityScore(**sdata)
                        self._scores.setdefault(sym, {})[venue] = score
            log.info("Loaded %d cached liquidity scores", sum(len(v) for v in data.values()))
        except Exception as e:
            log.warning("Failed to load liquidity scores: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

LIQUIDITY_SCORER = LiquidityScorer()
