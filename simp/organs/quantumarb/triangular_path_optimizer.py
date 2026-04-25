"""
Triangular Arb Path Optimizer — T26
=====================================
Pre-compute optimal triangle ordering per venue to minimize legs and
maximize fill rate.

For each venue, identifies all possible triangular arb paths across
available trading pairs and ranks them by:
  - Expected profit (bps)
  - Number of legs (fewer = better fill rate)
  - Composite liquidity score per leg
  - Historical fill rate

Outputs a ranked list of optimal triangles that can be used by
the arb detector and executor.

Usage:
    optimizer = TriangularPathOptimizer()
    optimizer.register_pairs("coinbase", ["BTC-USD", "ETH-USD", "SOL-USD", ...])
    paths = optimizer.find_optimal_paths("coinbase", min_profit_bps=10)
    best = optimizer.best_path("coinbase")
"""

from __future__ import annotations

import itertools
import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger("triangular_path_optimizer")


@dataclass
class TriangularLeg:
    """One leg of a triangular arbitrage path."""
    from_symbol: str
    to_symbol: str
    pair: str           # The actual trading pair on the venue
    side: str           # "buy" or "sell"
    expected_rate: float  # Expected conversion rate

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TriangularPath:
    """A complete triangular arbitrage path."""
    venue: str
    leg_a: TriangularLeg
    leg_b: TriangularLeg
    leg_c: TriangularLeg
    expected_profit_bps: float
    expected_profit_pct: float
    num_legs: int = 3
    composite_liquidity_score: float = 0.0
    fill_probability: float = 0.0
    path_id: str = ""  # Hash of the path for dedup
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.path_id:
            symbols = sorted([self.leg_a.from_symbol, self.leg_b.from_symbol, self.leg_c.from_symbol])
            self.path_id = f"{self.venue}_{'_'.join(symbols)}"

    def to_dict(self) -> dict:
        return {
            "venue": self.venue,
            "leg_a": self.leg_a.to_dict(),
            "leg_b": self.leg_b.to_dict(),
            "leg_c": self.leg_c.to_dict(),
            "expected_profit_bps": self.expected_profit_bps,
            "expected_profit_pct": self.expected_profit_pct,
            "num_legs": self.num_legs,
            "composite_liquidity_score": self.composite_liquidity_score,
            "fill_probability": self.fill_probability,
            "path_id": self.path_id,
            "timestamp": self.timestamp,
        }


class TriangularPathOptimizer:
    """
    Pre-computes and ranks optimal triangular arb paths per venue.

    For each venue, given a set of available pairs, computes all
    valid 3-pair cycles and ranks them by profitability, leg count,
    and liquidity.
    """

    def __init__(self, data_dir: str = "data/triangular_paths"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        # venue_pairs[venue] = set of trading pairs
        self._venue_pairs: Dict[str, Set[str]] = {}
        # venue_prices[venue][pair] = current price
        self._venue_prices: Dict[str, Dict[str, float]] = {}
        # cached_paths[venue] = list of TriangularPath
        self._cached_paths: Dict[str, List[TriangularPath]] = {}
        # last scan time per venue
        self._last_scan: Dict[str, float] = {}

        self._load_paths()

        log.info("TriangularPathOptimizer initialized")

    # ── Public API ──────────────────────────────────────────────────────

    def register_pairs(
        self, venue: str, pairs: List[str]
    ) -> None:
        """
        Register the available trading pairs for a venue.

        Args:
            venue: Exchange name
            pairs: List of trading pairs (e.g., ["BTC-USD", "ETH-USD"])
        """
        with self._lock:
            self._venue_pairs[venue] = set(pairs)
        log.info("Registered %d pairs for %s", len(pairs), venue)

    def update_prices(
        self, venue: str, prices: Dict[str, float]
    ) -> None:
        """
        Update current prices for a venue's pairs.

        Args:
            venue: Exchange name
            prices: Dict mapping pair -> price
        """
        with self._lock:
            self._venue_prices[venue] = {**self._venue_prices.get(venue, {}), **prices}

    def find_paths(
        self,
        venue: str,
        min_profit_bps: float = 5.0,
        max_results: int = 20,
    ) -> List[TriangularPath]:
        """
        Find all profitable triangular arbitrage paths for a venue.

        A triangular path involves 3 trades in a cycle:
        A -> B -> C -> A (converting back to the original asset).

        Args:
            venue: Exchange name
            min_profit_bps: Minimum profit in bps to include
            max_results: Maximum paths to return

        Returns:
            List of TriangularPath sorted by profit (descending)
        """
        with self._lock:
            pairs = self._venue_pairs.get(venue, set())
            prices = self._venue_prices.get(venue, {})

        if len(pairs) < 3:
            return []

        # Build symbol -> pairs mapping
        # For each symbol, what pairs does it participate in?
        symbol_pairs: Dict[str, Set[str]] = {}
        for pair in pairs:
            base, quote = self._split_pair(pair)
            symbol_pairs.setdefault(base, set()).add(pair)
            symbol_pairs.setdefault(quote, set()).add(pair)

        # Find all valid triangles (A->B->C->A where all pairs exist)
        symbols = list(symbol_pairs.keys())
        paths: List[TriangularPath] = []

        # Limit symbol combinations to avoid combinatorial explosion
        if len(symbols) > 10:
            # Only use top-traded symbols
            symbols = symbols[:10]

        for sym_a, sym_b, sym_c in itertools.combinations(symbols, 3):
            path = self._evaluate_triangle(
                venue, sym_a, sym_b, sym_c, pairs, prices,
            )
            if path and path.expected_profit_bps >= min_profit_bps:
                # Score the path
                path.composite_liquidity_score = self._score_path(path)
                path.fill_probability = self._estimate_fill_probability(path)
                paths.append(path)

        # Sort by profit (descending), then by liquidity score
        paths.sort(
            key=lambda p: (p.expected_profit_bps, p.composite_liquidity_score),
            reverse=True,
        )

        result = paths[:max_results]

        # Cache
        with self._lock:
            self._cached_paths[venue] = result
            self._last_scan[venue] = time.time()

        # Persist
        self._save_paths(venue, result)

        return result

    def best_path(self, venue: str) -> Optional[TriangularPath]:
        """Get the best triangular path for a venue."""
        with self._lock:
            cached = self._cached_paths.get(venue, [])
        return cached[0] if cached else None

    def get_top_paths(
        self, venue: str, n: int = 5
    ) -> List[TriangularPath]:
        """Get the top N paths for a venue."""
        with self._lock:
            cached = self._cached_paths.get(venue, [])
        return cached[:n]

    def get_all_venues_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of best paths per venue."""
        with self._lock:
            venues = list(self._cached_paths.keys())

        summary: Dict[str, Dict[str, Any]] = {}
        for venue in venues:
            paths = self.get_top_paths(venue, 3)
            if paths:
                summary[venue] = {
                    "best_profit_bps": paths[0].expected_profit_bps,
                    "num_paths_found": len(self._cached_paths.get(venue, [])),
                    "top_paths": [p.to_dict() for p in paths],
                }
        return summary

    def get_path_by_id(self, path_id: str) -> Optional[TriangularPath]:
        """Find a path by its ID across all venues."""
        with self._lock:
            for venue_paths in self._cached_paths.values():
                for path in venue_paths:
                    if path.path_id == path_id:
                        return path
        return None

    # ── Internal ────────────────────────────────────────────────────────

    def _split_pair(self, pair: str) -> Tuple[str, str]:
        """Split a trading pair into base and quote symbols."""
        parts = pair.split("-")
        if len(parts) == 2:
            return parts[0], parts[1]
        return pair, pair  # Fallback

    def _get_price(
        self, prices: Dict[str, float], pair: str
    ) -> float:
        """Get price for a pair, with fallback."""
        return prices.get(pair, 0.0)

    def _evaluate_triangle(
        self,
        venue: str,
        sym_a: str,
        sym_b: str,
        sym_c: str,
        pairs: Set[str],
        prices: Dict[str, float],
    ) -> Optional[TriangularPath]:
        """
        Evaluate a specific triangular cycle A -> B -> C -> A.

        Finds valid pair combinations for each conversion.
        """
        # Find pairs for each conversion
        pairs_ab = self._find_conversion_pairs(sym_a, sym_b, pairs)
        pairs_bc = self._find_conversion_pairs(sym_b, sym_c, pairs)
        pairs_ca = self._find_conversion_pairs(sym_c, sym_a, pairs)

        if not pairs_ab or not pairs_bc or not pairs_ca:
            return None

        # Use the first valid pair for each conversion
        pair_ab, side_ab, rate_ab = pairs_ab[0]
        pair_bc, side_bc, rate_bc = pairs_bc[0]
        pair_ca, side_ca, rate_ca = pairs_ca[0]

        # Get prices for rate calculation
        price_ab = self._get_price(prices, pair_ab)
        price_bc = self._get_price(prices, pair_bc)
        price_ca = self._get_price(prices, pair_ca)

        if price_ab <= 0 or price_bc <= 0 or price_ca <= 0:
            return None

        # Calculate conversion rates based on sides
        if side_ab == "buy":
            rate_ab = price_ab  # How much quote per base (A->B)
        else:
            rate_ab = 1.0 / price_ab  # Inverse

        if side_bc == "buy":
            rate_bc = price_bc
        else:
            rate_bc = 1.0 / price_bc

        if side_ca == "buy":
            rate_ca = price_ca
        else:
            rate_ca = 1.0 / price_ca

        # Calculate round-trip: A -> B -> C -> A
        # Starting with 1 unit of A, how many A do we end with?
        product = rate_ab * rate_bc * rate_ca

        if product <= 0:
            return None

        profit_pct = product - 1.0
        profit_bps = profit_pct * 10000

        if profit_bps <= 0:
            return None

        legs = [
            TriangularLeg(from_symbol=sym_a, to_symbol=sym_b, pair=pair_ab, side=side_ab, expected_rate=rate_ab),
            TriangularLeg(from_symbol=sym_b, to_symbol=sym_c, pair=pair_bc, side=side_bc, expected_rate=rate_bc),
            TriangularLeg(from_symbol=sym_c, to_symbol=sym_a, pair=pair_ca, side=side_ca, expected_rate=rate_ca),
        ]

        # Return the 3-leg path plus the profit
        return TriangularPath(
            venue=venue,
            leg_a=legs[0],
            leg_b=legs[1],
            leg_c=legs[2],
            expected_profit_bps=round(profit_bps, 2),
            expected_profit_pct=round(profit_pct, 6),
            num_legs=3,
        )

    def _find_conversion_pairs(
        self, from_sym: str, to_sym: str, pairs: Set[str],
    ) -> List[Tuple[str, str, float]]:
        """
        Find trading pairs and sides that convert from_sym to to_sym.

        Returns list of (pair, side, implied_rate) tuples.
        """
        results = []
        for pair in pairs:
            base, quote = self._split_pair(pair)
            if base == from_sym and quote == to_sym:
                # Direct: buy from_sym with to_sym -> sell
                results.append((pair, "sell", 0.0))
            elif base == to_sym and quote == from_sym:
                # Inverse: buy to_sym with from_sym -> buy
                results.append((pair, "buy", 0.0))
        return results

    def _score_path(self, path: TriangularPath) -> float:
        """Score a path based on leg count (fewer = better)."""
        return 1.0  # Default — can be enhanced with liquidity data

    def _estimate_fill_probability(self, path: TriangularPath) -> float:
        """Estimate fill probability. Simpler paths have higher prob."""
        # Default: 3-leg paths have ~60% fill probability
        # (can be enhanced with historical data)
        return 0.60

    # ── Persistence ─────────────────────────────────────────────────────

    def _save_paths(self, venue: str, paths: List[TriangularPath]) -> None:
        """Save computed paths to disk."""
        path = self._data_dir / f"{venue}_paths.json"
        data = [p.to_dict() for p in paths]
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.warning("Failed to save paths for %s: %s", venue, e)

    def _load_paths(self) -> None:
        """Load cached paths from disk."""
        if not self._data_dir.exists():
            return
        for fpath in self._data_dir.glob("*_paths.json"):
            venue = fpath.stem.replace("_paths", "")
            try:
                with open(fpath) as f:
                    data = json.load(f)
                paths = []
                for pdata in data:
                    legs = pdata["legs"] if "legs" in pdata else [
                        pdata.get("leg_a", {}),
                        pdata.get("leg_b", {}),
                        pdata.get("leg_c", {}),
                    ]
                    # Rebuild from dict
                    path = TriangularPath(
                        venue=pdata["venue"],
                        leg_a=TriangularLeg(**pdata.get("leg_a", {})),
                        leg_b=TriangularLeg(**pdata.get("leg_b", {})),
                        leg_c=TriangularLeg(**pdata.get("leg_c", {})),
                        expected_profit_bps=pdata.get("expected_profit_bps", 0),
                        expected_profit_pct=pdata.get("expected_profit_pct", 0),
                        num_legs=pdata.get("num_legs", 3),
                        composite_liquidity_score=pdata.get("composite_liquidity_score", 0.0),
                        fill_probability=pdata.get("fill_probability", 0.0),
                        path_id=pdata.get("path_id", ""),
                        timestamp=pdata.get("timestamp", ""),
                    )
                    paths.append(path)
                self._cached_paths[venue] = paths
                log.info("Loaded %d cached paths for %s", len(paths), venue)
            except Exception as e:
                log.warning("Failed to load paths for %s: %s", venue, e)


# ── Module-level singleton ──────────────────────────────────────────────

TRIANGULAR_OPTIMIZER = TriangularPathOptimizer()
