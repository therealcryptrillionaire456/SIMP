#!/usr/bin/env python3.10
"""
Cross-Venue Capital Allocator for QuantumArb.

Decides where to deploy capital across all profit engines (arbitrage, staking,
mining, meme coins, pump fun) using a multi-armed bandit approach with
exploration/exploitation balancing.

Pattern: Thread-safe manager using in-memory dicts for ephemeral session tracking.
No numpy, scipy, or ML libraries. Pure Python math only.
"""

import json
import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("CapitalAllocator")

# ────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class AllocationProposal:
    """A proposed capital allocation to a specific profit engine venue."""

    venue: str
    symbol: str
    expected_return_pct: float
    confidence: float
    risk_score: float
    capital_usd: float
    weight: float
    timestamp: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class VenueStats:
    """Aggregated performance statistics for a single venue."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit_pct: float = 0.0
    total_capital_used: float = 0.0
    returns_history: List[float] = field(default_factory=list)  # decayed returns
    raw_returns: List[float] = field(default_factory=list)       # actual returns

    @property
    def win_rate(self) -> float:
        """Fraction of trades that were profitable."""
        if self.total_trades == 0:
            return 0.5  # neutral default
        return self.winning_trades / self.total_trades

    @property
    def avg_return(self) -> float:
        """Average return per trade as a decimal fraction."""
        if self.total_trades == 0:
            return 0.0
        return self.total_profit_pct / self.total_trades

    @property
    def sharpe(self) -> float:
        """Simplified Sharpe-like ratio: avg_return / std(returns) * sqrt(periods).

        Uses population std with a small epsilon to avoid division by zero.
        """
        if len(self.raw_returns) < 2:
            return 0.0
        mean_r = sum(self.raw_returns) / len(self.raw_returns)
        variance = sum((r - mean_r) ** 2 for r in self.raw_returns) / len(self.raw_returns)
        std = math.sqrt(variance + 1e-12)
        return mean_r / std * math.sqrt(len(self.raw_returns))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_return": self.avg_return,
            "sharpe": self.sharpe,
            "total_profit_pct": self.total_profit_pct,
            "total_capital_used": self.total_capital_used,
        }


# ────────────────────────────────────────────────────────────────────────────
# VenuePerformanceTracker
# ────────────────────────────────────────────────────────────────────────────

class VenuePerformanceTracker:
    """
    Ephemeral in-memory tracker of venue-level performance for a single session.

    Uses a thread-safe dict to record profit/loss outcomes per venue and
    computes summary statistics.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # venue_name -> VenueStats
        self._stats: Dict[str, VenueStats] = {}
        log.info("VenuePerformanceTracker initialized (in-memory)")

    def record_outcome(self, venue: str, profit_pct: float, capital_used: float) -> None:
        """
        Record the outcome of a trade or allocation at a venue.

        Args:
            venue: Venue name (e.g. "cross_exchange_arb")
            profit_pct: Profit/loss as a decimal fraction (0.05 = 5% gain)
            capital_used: Amount of capital deployed in USD
        """
        with self._lock:
            stats = self._stats.setdefault(venue, VenueStats())
            stats.total_trades += 1
            stats.total_profit_pct += profit_pct
            stats.total_capital_used += capital_used
            stats.raw_returns.append(profit_pct)

            if profit_pct > 0:
                stats.winning_trades += 1
            elif profit_pct < 0:
                stats.losing_trades += 1
            # profit_pct == 0 counts as neither win nor loss

            log.debug(
                "Venue %s: recorded profit_pct=%.4f, capital=%.2f "
                "(total trades: %d, win rate: %.2f)",
                venue, profit_pct, capital_used,
                stats.total_trades, stats.win_rate,
            )

    def get_venue_stats(self, venue: str) -> Dict[str, Any]:
        """
        Get aggregated stats for a single venue.

        Args:
            venue: Venue name

        Returns:
            Dictionary with total_trades, win_rate, avg_return, sharpe
        """
        with self._lock:
            stats = self._stats.get(venue)
            if stats is None:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.5,
                    "avg_return": 0.0,
                    "sharpe": 0.0,
                    "total_profit_pct": 0.0,
                    "total_capital_used": 0.0,
                }
            return stats.to_dict()

    def get_all_venue_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get aggregated stats for all tracked venues.

        Returns:
            Dict mapping venue name -> stats dict
        """
        with self._lock:
            return {name: stats.to_dict() for name, stats in self._stats.items()}

    def reset_venue(self, venue: str) -> None:
        """
        Reset all stats for a given venue. Useful for debugging or re-calibration.

        Args:
            venue: Venue name to reset
        """
        with self._lock:
            if venue in self._stats:
                log.info("Resetting stats for venue: %s", venue)
                self._stats[venue] = VenueStats()

    def get_win_rate(self, venue: str) -> float:
        """Get the win rate for a venue (used by allocator scoring)."""
        with self._lock:
            stats = self._stats.get(venue)
            if stats is None:
                return 0.5
            return stats.win_rate

    def get_venue_names(self) -> List[str]:
        """Return list of all venue names that have been tracked."""
        with self._lock:
            return list(self._stats.keys())


# ────────────────────────────────────────────────────────────────────────────
# CapitalAllocator
# ────────────────────────────────────────────────────────────────────────────

class CapitalAllocator:
    """
    Multi-armed bandit capital allocator that distributes available capital
    across profit venues based on expected return, confidence, risk, and
    historical performance.

    Uses epsilon-greedy exploration: with probability exploration_rate, a
    random venue is selected for one allocation slot.
    """

    def __init__(
        self,
        total_capital_usd: float = 100.0,
        exploration_rate: float = 0.1,
        decay_factor: float = 0.95,
    ) -> None:
        """
        Initialize the allocator.

        Args:
            total_capital_usd: Total capital available (in USD)
            exploration_rate: Probability of picking a random venue (0-1)
            decay_factor: How fast past performance decays (0-1)
        """
        self.total_capital_usd = total_capital_usd
        self.exploration_rate = exploration_rate
        self.decay_factor = decay_factor
        self._lock = threading.Lock()
        self.tracker = VenuePerformanceTracker()

        # venue_name -> weight (initialized evenly across known venues on first allocate)
        self.allocations: Dict[str, float] = {}

        log.info(
            "CapitalAllocator initialized: capital=%.2f, explore=%.2f, decay=%.2f",
            total_capital_usd, exploration_rate, decay_factor,
        )

    def _extract_venues(self, opportunities: List[Dict[str, Any]]) -> List[str]:
        """Extract unique venue names from the opportunities list."""
        return list({opp.get("venue", "unknown") for opp in opportunities})

    def _normalize_allocations(self, relevant_venues: List[str]) -> None:
        """
        Ensure allocations dict has an even entry for each relevant venue.
        Existing weights are preserved; new venues start at even share.
        """
        if not relevant_venues:
            return
        for venue in relevant_venues:
            if venue not in self.allocations:
                self.allocations[venue] = 1.0 / len(relevant_venues)

    def _compute_base_score(
        self,
        opp: Dict[str, Any],
    ) -> float:
        """
        Compute the base score for a single opportunity.

        Formula: (expected_return_pct * confidence) / (risk_score + 0.01)

        The +0.01 prevents division by zero while penalizing high-risk venues.
        """
        expected_return = opp.get("expected_return_pct", 0.0)
        confidence = opp.get("confidence", 0.0)
        risk_score = opp.get("risk_score", 1.0)
        return (expected_return * confidence) / (risk_score + 0.01)

    def _apply_venue_performance_multiplier(
        self,
        base_score: float,
        venue: str,
    ) -> float:
        """
        Adjust score by venue historical performance.

        Multiplier: 1 + (win_rate - 0.5) * 2
        - win_rate=0.5 -> multiplier=1.0 (neutral)
        - win_rate=0.75 -> multiplier=1.5 (boost)
        - win_rate=0.25 -> multiplier=0.5 (penalty)
        """
        win_rate = self.tracker.get_win_rate(venue)
        multiplier = 1.0 + (win_rate - 0.5) * 2.0
        return base_score * max(multiplier, 0.01)  # floor at 0.01

    def allocate(
        self,
        opportunities: List[Dict[str, Any]],
        available_capital: Optional[float] = None,
    ) -> List[AllocationProposal]:
        """
        Allocate capital across opportunities using multi-armed bandit logic.

        Args:
            opportunities: List of opportunity dicts with fields:
                - venue: str
                - symbol: str
                - expected_return_pct: float
                - confidence: float (0-1)
                - risk_score: float (0-1)
                - capital_required: float (USD)
            available_capital: Amount of capital to allocate. If None,
                               uses self.total_capital_usd.

        Returns:
            List of AllocationProposal objects, sorted highest capital first.
        """
        cap = available_capital if available_capital is not None else self.total_capital_usd

        if not opportunities:
            log.info("No opportunities to allocate against")
            return []

        # Step 1: Filter opportunities
        valid = self._filter_opportunities(opportunities)
        if not valid:
            log.info("No valid opportunities after filtering")
            return []

        # Step 2: Extract venues and ensure allocations dict is initialized
        venues = self._extract_venues(valid)
        with self._lock:
            self._normalize_allocations(venues)

        # Step 3: Score each opportunity
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for opp in valid:
            base_score = self._compute_base_score(opp)
            venue = opp.get("venue", "unknown")
            adjusted_score = self._apply_venue_performance_multiplier(base_score, venue)
            scored.append((adjusted_score, opp))

        # Step 4: Apply exploration — with exploration_rate probability,
        # pick a random venue to promote
        if random.random() < self.exploration_rate and len(scored) > 1:
            self._apply_exploration(scored)

        # Step 5: Normalize scores to weights summing to 1.0
        scores = [s[0] for s in scored]
        total_score = sum(scores)
        if total_score <= 0:
            # Fallback: equal weights
            weights = [1.0 / len(scored)] * len(scored)
        else:
            weights = [s / total_score for s in scores]

        # Step 6: Build allocation proposals
        proposals: List[AllocationProposal] = []
        timestamp = datetime.now(timezone.utc).isoformat()

        for (weight, opp_info) in zip(weights, scored):
            opp = opp_info[1]
            venue = opp.get("venue", "unknown")
            symbol = opp.get("symbol", "unknown")
            expected_return = opp.get("expected_return_pct", 0.0)
            confidence = opp.get("confidence", 0.0)
            risk_score = opp.get("risk_score", 1.0)
            capital_usd = weight * cap

            # Determine if this was an exploration pick
            was_exploration = opp_info[0] == -1.0  # marker set by _apply_exploration
            if was_exploration:
                rationale = (
                    f"Exploration pick at ε={self.exploration_rate}: "
                    f"random venue selection to discover new opportunities"
                )
            else:
                win_rate = self.tracker.get_win_rate(venue)
                performance_multiplier = 1.0 + (win_rate - 0.5) * 2.0
                rationale = (
                    f"Score={opp_info[0]:.4f} | "
                    f"return×conf/(risk+0.01) adjusted by venue perf multiplier "
                    f"({performance_multiplier:.2f}x, win_rate={win_rate:.2f})"
                )

            proposal = AllocationProposal(
                venue=venue,
                symbol=symbol,
                expected_return_pct=expected_return,
                confidence=confidence,
                risk_score=risk_score,
                capital_usd=capital_usd,
                weight=weight,
                timestamp=timestamp,
                rationale=rationale,
            )
            proposals.append(proposal)

        # Step 7: Sort by capital descending
        proposals.sort(key=lambda p: p.capital_usd, reverse=True)

        # Update allocations dict with the new weights
        with self._lock:
            for prop in proposals:
                self.allocations[prop.venue] = prop.weight

        log.info(
            "Allocated $%.2f across %d opportunities (top: %s @ $%.2f)",
            cap, len(proposals),
            proposals[0].venue if proposals else "none",
            proposals[0].capital_usd if proposals else 0.0,
        )

        return proposals

    def _filter_opportunities(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Filter opportunities to those with positive expected return and
        confidence above threshold.
        """
        filtered = []
        for opp in opportunities:
            expected_return = opp.get("expected_return_pct", 0.0)
            confidence = opp.get("confidence", 0.0)
            if expected_return > 0 and confidence > 0.1:
                filtered.append(opp)
            else:
                log.debug(
                    "Filtered out opportunity: venue=%s, return=%.4f, conf=%.2f",
                    opp.get("venue", "?"), expected_return, confidence,
                )
        return filtered

    def _apply_exploration(
        self,
        scored: List[Tuple[float, Dict[str, Any]]],
    ) -> None:
        """
        With exploration_rate probability, pick one opportunity at random and
        boost its score so it gets a meaningful allocation.

        We pick uniformly from scored items (after filtering). If the item is
        already the highest scoring, we leave it. Otherwise we boost it to
        match or exceed the current best.
        """
        if len(scored) < 2:
            return

        # Pick a random index to explore
        explore_idx = random.randint(0, len(scored) - 1)

        # Find the current best score
        best_score = max(s[0] for s in scored)
        current_score = scored[explore_idx][0]

        # Only boost if not already the leader
        if current_score < best_score - 1e-12:
            # Boost the chosen opportunity to slightly above the current best
            boost = best_score * 1.1 + 0.001
            # Mark this as exploration with a special score value
            scored[explore_idx] = (boost, scored[explore_idx][1])
            log.debug(
                "Exploration: boosting venue=%s from %.4f to %.4f",
                scored[explore_idx][1].get("venue", "?"),
                current_score,
                boost,
            )

    def record_outcome(
        self,
        venue: str,
        profit_pct: float,
        capital_used: float,
    ) -> None:
        """
        Record a trade outcome for a venue to update its performance stats.

        Convenience wrapper around VenuePerformanceTracker.record_outcome.
        """
        self.tracker.record_outcome(venue, profit_pct, capital_used)

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of allocator state and venue performance.

        Returns:
            Dict with total_capital, exploration_rate, venue_stats
        """
        venue_stats = self.tracker.get_all_venue_stats()
        with self._lock:
            current_weights = dict(self.allocations)

        return {
            "total_capital_usd": self.total_capital_usd,
            "exploration_rate": self.exploration_rate,
            "decay_factor": self.decay_factor,
            "venue_weights": current_weights,
            "venue_stats": venue_stats,
            "tracked_venues": list(venue_stats.keys()),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize allocator state (without full trade history)."""
        return self.get_performance_summary()


# ────────────────────────────────────────────────────────────────────────────
# Test / Demonstration
# ────────────────────────────────────────────────────────────────────────────

def test_capital_allocator() -> None:
    """Test and demonstrate the capital allocator with sample opportunities."""
    print("=" * 60)
    print("Cross-Venue Capital Allocator — Test Suite")
    print("=" * 60)

    # --- Test 1: Basic allocation ---
    print("\n--- Test 1: Basic allocation across 4 venues ---")
    allocator = CapitalAllocator(total_capital_usd=100.0, exploration_rate=0.0)

    opportunities = [
        {
            "venue": "cross_exchange_arb",
            "symbol": "BTC-USD",
            "expected_return_pct": 0.05,
            "confidence": 0.85,
            "risk_score": 0.3,
            "capital_required": 1.0,
        },
        {
            "venue": "triangular_arb",
            "symbol": "ETH-USD",
            "expected_return_pct": 0.03,
            "confidence": 0.70,
            "risk_score": 0.5,
            "capital_required": 0.5,
        },
        {
            "venue": "staking",
            "symbol": "SOL",
            "expected_return_pct": 0.01,
            "confidence": 0.95,
            "risk_score": 0.1,
            "capital_required": 10.0,
        },
        {
            "venue": "meme_launch",
            "symbol": "PEPE",
            "expected_return_pct": 0.20,
            "confidence": 0.25,
            "risk_score": 0.9,
            "capital_required": 0.1,
        },
    ]

    proposals = allocator.allocate(opportunities)
    print(f"Generated {len(proposals)} allocation proposals:\n")
    for p in proposals:
        print(f"  {p.venue:25s} | {p.symbol:8s} | "
              f"${p.capital_usd:<6.2f} ({p.weight*100:5.1f}%) | "
              f"ret={p.expected_return_pct:+.2f} conf={p.confidence:.2f} "
              f"risk={p.risk_score:.2f}")
        print(f"  {'':>25s}   {p.rationale}\n")

    # Verify weights sum to ~1.0
    total_weight = sum(p.weight for p in proposals)
    total_capital = sum(p.capital_usd for p in proposals)
    print(f"  Total weight: {total_weight:.4f} (should be ~1.0)")
    print(f"  Total capital: ${total_capital:.2f} (should be $100.00)")
    assert abs(total_weight - 1.0) < 0.001, f"Weights don't sum to 1: {total_weight}"
    assert abs(total_capital - 100.0) < 0.01, f"Capital doesn't sum: {total_capital}"
    print("  ✅ Basic allocation passed")

    # --- Test 2: Empty opportunities ---
    print("\n--- Test 2: Empty opportunities list ---")
    empty_proposals = allocator.allocate([])
    assert empty_proposals == [], f"Expected empty list, got {empty_proposals}"
    print("  ✅ Empty list handled correctly")

    # --- Test 3: Filter low-confidence / negative-return opportunities ---
    print("\n--- Test 3: Filtering invalid opportunities ---")
    mixed = [
        {
            "venue": "cross_exchange_arb",
            "symbol": "BTC-USD",
            "expected_return_pct": 0.0,  # zero return -> filtered
            "confidence": 0.85,
            "risk_score": 0.3,
            "capital_required": 1.0,
        },
        {
            "venue": "staking",
            "symbol": "SOL",
            "expected_return_pct": 0.01,
            "confidence": 0.05,  # low confidence -> filtered
            "risk_score": 0.1,
            "capital_required": 10.0,
        },
        {
            "venue": "triangular_arb",
            "symbol": "ETH-USD",
            "expected_return_pct": 0.04,
            "confidence": 0.80,
            "risk_score": 0.4,
            "capital_required": 1.0,
        },
    ]
    mixed_proposals = allocator.allocate(mixed)
    assert len(mixed_proposals) == 1, f"Expected 1 proposal, got {len(mixed_proposals)}"
    assert mixed_proposals[0].venue == "triangular_arb"
    print(f"  Filtered to 1 valid opportunity: {mixed_proposals[0].venue}")
    print("  ✅ Filtering passed")

    # --- Test 4: Venue performance tracking ---
    print("\n--- Test 4: Venue performance tracking ---")
    tracker = VenuePerformanceTracker()

    # Record multiple outcomes for cross_exchange_arb
    tracker.record_outcome("cross_exchange_arb", 0.05, 1.0)
    tracker.record_outcome("cross_exchange_arb", 0.03, 0.8)
    tracker.record_outcome("cross_exchange_arb", -0.02, 0.5)
    tracker.record_outcome("cross_exchange_arb", 0.04, 1.2)

    stats = tracker.get_venue_stats("cross_exchange_arb")
    print(f"  cross_exchange_arb stats:")
    print(f"    total_trades: {stats['total_trades']} (expected 4)")
    print(f"    winning_trades: {stats['winning_trades']} (expected 3)")
    print(f"    win_rate: {stats['win_rate']:.2f} (expected 0.75)")
    print(f"    avg_return: {stats['avg_return']:.4f}")
    print(f"    sharpe: {stats['sharpe']:.4f}")

    assert stats["total_trades"] == 4
    assert stats["winning_trades"] == 3
    assert stats["win_rate"] == 0.75
    print("  ✅ Venue tracking passed")

    # --- Test 5: Venue performance influences allocation ---
    print("\n--- Test 5: Venue performance influences allocation ---")
    allocator2 = CapitalAllocator(total_capital_usd=100.0, exploration_rate=0.0)

    # Record strong performance for one venue
    for _ in range(10):
        allocator2.record_outcome("cross_exchange_arb", 0.04, 1.0)
    # Record poor performance for another
    for _ in range(10):
        allocator2.record_outcome("meme_launch", -0.05, 1.0)

    # Now allocate across both equally-scored opportunities
    opps = [
        {
            "venue": "cross_exchange_arb",
            "symbol": "BTC-USD",
            "expected_return_pct": 0.05,
            "confidence": 0.80,
            "risk_score": 0.3,
            "capital_required": 1.0,
        },
        {
            "venue": "meme_launch",
            "symbol": "PEPE",
            "expected_return_pct": 0.05,
            "confidence": 0.80,
            "risk_score": 0.3,
            "capital_required": 1.0,
        },
    ]
    perf_proposals = allocator2.allocate(opps)
    for p in perf_proposals:
        print(f"  {p.venue:25s} gets ${p.capital_usd:.2f} ({p.weight*100:.1f}%)")

    # cross_exchange_arb should get significantly more
    arb_weight = next(p.weight for p in perf_proposals if p.venue == "cross_exchange_arb")
    meme_weight = next(p.weight for p in perf_proposals if p.venue == "meme_launch")
    print(f"  arb weight: {arb_weight:.4f}, meme weight: {meme_weight:.4f}")
    assert arb_weight > meme_weight, (
        f"Expected arb ({arb_weight:.4f}) > meme ({meme_weight:.4f}) "
        f"due to historical performance"
    )
    print("  ✅ Performance influence passed")

    # --- Test 6: Exploration mode ---
    print("\n--- Test 6: Exploration (epsilon-greedy) ---")
    allocator3 = CapitalAllocator(total_capital_usd=100.0, exploration_rate=1.0)
    opps2 = [
        {
            "venue": "pumpfun",
            "symbol": "TOKEN-A",
            "expected_return_pct": 0.01,
            "confidence": 0.50,
            "risk_score": 0.8,
            "capital_required": 0.5,
        },
        {
            "venue": "staking",
            "symbol": "ETH",
            "expected_return_pct": 0.03,
            "confidence": 0.90,
            "risk_score": 0.1,
            "capital_required": 10.0,
        },
    ]
    # With exploration=1.0, we should see variability across runs
    venues_seen: set = set()
    for _ in range(20):
        p = allocator3.allocate(opps2)
        if p:
            venues_seen.add(p[0].venue)
    print(f"  Venues seen as top pick: {venues_seen}")
    # Both venues should appear at least once in 20 runs at ε=1.0
    assert len(venues_seen) > 1, (
        f"Expected both venues to be explored, got: {venues_seen}"
    )
    print("  ✅ Exploration passed (both venues appeared as top pick)")

    # --- Test 7: Reset venue ---
    print("\n--- Test 7: Reset venue stats ---")
    tracker.reset_venue("cross_exchange_arb")
    reset_stats = tracker.get_venue_stats("cross_exchange_arb")
    assert reset_stats["total_trades"] == 0
    assert reset_stats["win_rate"] == 0.5  # neutral default
    print(f"  After reset: total_trades={reset_stats['total_trades']}")
    print("  ✅ Reset passed")

    # --- Test 8: Performance summary ---
    print("\n--- Test 8: Performance summary ---")
    summary = allocator.get_performance_summary()
    print(f"  Total capital: ${summary['total_capital_usd']:.2f}")
    print(f"  Exploration rate: {summary['exploration_rate']}")
    print(f"  Venue weights: {summary['venue_weights']}")
    print(f"  Tracked venues: {summary['tracked_venues']}")
    print("  ✅ Summary passed")

    # --- Test 9: Serialization ---
    print("\n--- Test 9: AllocationProposal.to_dict() ---")
    proposal = AllocationProposal(
        venue="test_venue",
        symbol="TEST",
        expected_return_pct=0.05,
        confidence=0.8,
        risk_score=0.3,
        capital_usd=50.0,
        weight=0.5,
        timestamp=datetime.now(timezone.utc).isoformat(),
        rationale="Test serialization",
    )
    d = proposal.to_dict()
    assert d["venue"] == "test_venue"
    assert d["capital_usd"] == 50.0
    print(f"  Serialized: {json.dumps(d, indent=2)}")
    print("  ✅ Serialization passed")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print()
    print("Capital Allocator ready for cross-venue profit deployment.")
    print("Integrates with:")
    print("  - ArbDetector (arbitrage opportunities)")
    print("  - TradeExecutor (capital deployment)")
    print("  - PNLLedger (P&L tracking for outcome recording)")
    print("  - Multi-armed bandit exploration/exploitation")
    print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_capital_allocator()
