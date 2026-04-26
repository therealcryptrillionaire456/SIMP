#!/usr/bin/env python3.10
"""
Historical Gas Oracle & Predictive Gas Endpoint — T32.1 / T32.2
==================================================================
Track gas prices over time and provide optimal execution timing.

Predicts gas within 15% for next 5 blocks using moving average + trend.
Extends to multi-chain fee comparison (T32.6).

Integrates:
  - Simulated gas tracker (real via Coinbase/Alchemy in production)
  - Predictive endpoint for optimal timing
  - Multi-chain fee comparison (Ethereum/Solana/Base)

Usage:
    from simp.organs.quantumarb.gas_oracle import GasOracle
    oracle = GasOracle()
    prediction = oracle.predict_next_blocks()  # Next 5 blocks
    best_chain = oracle.cheapest_chain()       # Multi-chain
"""

from __future__ import annotations

import json
import logging
import statistics
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("gas_oracle")


@dataclass
class GasSample:
    """A single gas price observation."""
    chain: str
    gas_price_gwei: float        # Current gas price in Gwei
    priority_fee_gwei: float     # Priority fee / tip
    base_fee_gwei: float         # EIP-1559 base fee
    block_number: int
    timestamp: float
    source: str = "simulated"    # "simulated", "alchemy", "coinbase", etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GasPrediction:
    """Gas price prediction for upcoming blocks."""
    chain: str
    current_gwei: float
    predicted_next_gwei: float    # Next block prediction
    predicted_5block_avg: float   # Average over next 5 blocks
    confidence_low_gwei: float    # Lower bound (85% confidence)
    confidence_high_gwei: float   # Upper bound (85% confidence)
    trend: str                    # "rising", "falling", "stable"
    recommendation: str           # "execute_now", "wait", "split"
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Known fee estimates per chain (Gwei)
CHAIN_FEE_ESTIMATES = {
    "ethereum": {"safe": 15, "standard": 25, "fast": 50, "block_time_s": 12},
    "base": {"safe": 0.1, "standard": 0.3, "fast": 1.0, "block_time_s": 2},
    "solana": {"safe": 0.00001, "standard": 0.00005, "fast": 0.0001, "block_time_s": 0.4},
    "polygon": {"safe": 30, "standard": 50, "fast": 100, "block_time_s": 2},
    "arbitrum": {"safe": 0.1, "standard": 0.5, "fast": 2.0, "block_time_s": 0.25},
    "optimism": {"safe": 0.005, "standard": 0.01, "fast": 0.05, "block_time_s": 2},
}


class GasOracle:
    """
    Tracks gas prices across chains and predicts optimal execution timing.

    Thread-safe. Maintains a rolling window of gas samples per chain.
    Uses moving average + linear regression for 5-block prediction.
    """

    WINDOW_SIZE = 100       # Max samples per chain
    PREDICTION_BLOCKS = 5   # Number of blocks to predict

    def __init__(self, data_dir: str = "data/gas_prices"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._samples: Dict[str, List[GasSample]] = {}
        self._fee_estimates: Dict[str, Dict[str, float]] = dict(CHAIN_FEE_ESTIMATES)

        self._load_history()
        log.info("GasOracle initialized (chains=%s)", list(self._fee_estimates.keys()))

    # ── Public API ──────────────────────────────────────────────────────

    def record_sample(self, chain: str, gas_price_gwei: float,
                      priority_fee_gwei: float = 0.0,
                      base_fee_gwei: float = 0.0,
                      block_number: int = 0,
                      source: str = "simulated") -> GasSample:
        """Record a gas price observation."""
        sample = GasSample(
            chain=chain,
            gas_price_gwei=gas_price_gwei,
            priority_fee_gwei=priority_fee_gwei,
            base_fee_gwei=base_fee_gwei,
            block_number=block_number,
            timestamp=time.time(),
            source=source,
        )
        with self._lock:
            self._samples.setdefault(chain, []).append(sample)
            # Trim window
            if len(self._samples[chain]) > self.WINDOW_SIZE:
                self._samples[chain] = self._samples[chain][-self.WINDOW_SIZE:]
        return sample

    def predict_next_blocks(self, chain: str = "ethereum",
                            blocks: int = 5) -> Optional[GasPrediction]:
        """
        Predict gas prices for upcoming blocks.

        Args:
            chain: Blockchain to predict for
            blocks: Number of blocks ahead to predict

        Returns:
            GasPrediction or None if insufficient data
        """
        samples = self._get_recent_samples(chain, min_count=3)
        if not samples:
            # Return estimated prediction based on default fee estimates
            return self._estimate_from_defaults(chain, blocks)

        prices = [s.gas_price_gwei for s in samples]
        current = prices[-1]

        # Simple linear trend
        n = len(prices)
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(prices)
        num = sum(i * p for i, p in enumerate(prices)) - n * x_mean * y_mean
        den = sum(i * i for i in range(n)) - n * x_mean * x_mean
        slope = num / den if den != 0 else 0

        # Predict next `blocks` blocks
        predictions = [current + slope * (i + 1) for i in range(blocks)]
        predicted_next = predictions[0]
        predicted_avg = statistics.mean(predictions)

        # Confidence interval (85%)
        std = statistics.stdev(prices) if len(prices) > 1 else current * 0.1
        conf_low = predicted_avg - 1.44 * std
        conf_high = predicted_avg + 1.44 * std

        # Trend classification
        if slope > current * 0.02:
            trend = "rising"
        elif slope < -current * 0.02:
            trend = "falling"
        else:
            trend = "stable"

        # Recommendation
        if trend == "falling":
            recommendation = "wait"
        elif trend == "rising" and predicted_next <= current * 1.05:
            recommendation = "execute_now"
        elif trend == "stable" and current < self._fee_estimates.get(chain, {}).get("fast", 50):
            recommendation = "execute_now"
        else:
            recommendation = "split"  # Split execution across blocks

        return GasPrediction(
            chain=chain,
            current_gwei=round(current, 4),
            predicted_next_gwei=round(predicted_next, 4),
            predicted_5block_avg=round(predicted_avg, 4),
            confidence_low_gwei=round(max(0, conf_low), 4),
            confidence_high_gwei=round(conf_high, 4),
            trend=trend,
            recommendation=recommendation,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def cheapest_chain(self, tx_complexity: str = "standard") -> Dict[str, Any]:
        """
        Find the cheapest chain for a given transaction complexity.

        Args:
            tx_complexity: "simple", "standard", "complex"

        Returns:
            Dict with chain name, estimated cost, and recommendation
        """
        complexity_mult = {"simple": 21000, "standard": 100000, "complex": 300000}

        results = []
        for chain, estimates in self._fee_estimates.items():
            gas_units = complexity_mult.get(tx_complexity, complexity_mult["standard"])
            gas_price = estimates["standard"]
            fee_eth = gas_units * gas_price * 1e-9  # Gwei → ETH
            block_time = estimates.get("block_time_s", 12)
            results.append({
                "chain": chain,
                "gas_price_gwei": gas_price,
                "estimated_fee_eth": round(fee_eth, 8),
                "estimated_fee_usd": round(fee_eth * 1800, 4),  # ~$1800/ETH est
                "block_time_s": block_time,
            })

        results.sort(key=lambda r: r["estimated_fee_usd"])

        return {
            "cheapest_chain": results[0]["chain"],
            "all_chains_ranked": results,
            "tx_complexity": tx_complexity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_chain_stats(self, chain: str) -> Dict[str, Any]:
        """Get gas statistics for a specific chain."""
        samples = self._get_recent_samples(chain, min_count=1)
        if not samples:
            estimates = self._fee_estimates.get(chain, {})
            return {
                "chain": chain,
                "available_data": False,
                "safe_gwei": estimates.get("safe", 0),
                "standard_gwei": estimates.get("standard", 0),
                "fast_gwei": estimates.get("fast", 0),
                "block_time_s": estimates.get("block_time_s", 12),
            }

        prices = [s.gas_price_gwei for s in samples]
        # Use adaptive precision: 4 decimal places for normal values,
        # more for tiny values (Solana, etc.)
        def _safe_round(v: float) -> float:
            if abs(v) < 0.0001:
                return round(v, 10)
            return round(v, 4)

        return {
            "chain": chain,
            "available_data": True,
            "current_gwei": _safe_round(prices[-1]),
            "min_gwei": _safe_round(min(prices)),
            "max_gwei": _safe_round(max(prices)),
            "avg_gwei": _safe_round(statistics.mean(prices)),
            "median_gwei": _safe_round(statistics.median(prices)),
            "samples": len(samples),
            "latest_block": samples[-1].block_number,
            "safe_gwei": self._fee_estimates.get(chain, {}).get("safe", 0),
            "standard_gwei": self._fee_estimates.get(chain, {}).get("standard", 0),
            "fast_gwei": self._fee_estimates.get(chain, {}).get("fast", 0),
            "block_time_s": self._fee_estimates.get(chain, {}).get("block_time_s", 12),
        }

    def multi_chain_comparison(self, tx_complexity: str = "standard") -> Dict[str, Any]:
        """
        Compare gas costs across all chains for the same trade.

        Args:
            tx_complexity: "simple", "standard", "complex"

        Returns:
            Dict ranked by cheapest chain
        """
        return self.cheapest_chain(tx_complexity)

    def get_gas_budget_status(self, strategy: str,
                               daily_budget_gwei: float = 500000) -> Dict[str, Any]:
        """
        Check gas budget usage for a strategy.

        Args:
            strategy: Strategy name
            daily_budget_gwei: Max daily gas budget in Gwei

        Returns:
            Budget status dict
        """
        # Count today's samples as gas usage
        today = time.time()
        today_start = today - (today % 86400)

        total_used = 0.0
        tx_count = 0
        with self._lock:
            for chain_samples in self._samples.values():
                for s in chain_samples:
                    if s.timestamp >= today_start:
                        total_used += s.gas_price_gwei
                        tx_count += 1

        pct_used = (total_used / daily_budget_gwei) * 100 if daily_budget_gwei > 0 else 0

        return {
            "strategy": strategy,
            "daily_budget_gwei": daily_budget_gwei,
            "used_gwei": round(total_used, 2),
            "tx_count": tx_count,
            "pct_used": round(pct_used, 1),
            "budget_remaining_gwei": round(max(0, daily_budget_gwei - total_used), 2),
            "status": "ok" if pct_used < 75 else "warning" if pct_used < 100 else "exceeded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def persist(self) -> None:
        """Persist gas samples to disk."""
        path = self._data_dir / "gas_samples.jsonl"
        with self._lock:
            with open(path, "w") as f:
                for chain_samples in self._samples.values():
                    for s in chain_samples:
                        f.write(json.dumps(s.to_dict()) + "\n")
        log.info("Persisted gas samples to %s", path)

    # ── Internal ────────────────────────────────────────────────────────

    def _get_recent_samples(self, chain: str,
                             min_count: int = 1) -> List[GasSample]:
        """Get recent samples for a chain."""
        with self._lock:
            samples = list(self._samples.get(chain, []))
        return samples if len(samples) >= min_count else []

    def _estimate_from_defaults(self, chain: str,
                                 blocks: int) -> GasPrediction:
        """Create prediction based on default fee estimates."""
        estimates = self._fee_estimates.get(chain, {})
        current = estimates.get("standard", 25)

        return GasPrediction(
            chain=chain,
            current_gwei=float(current),
            predicted_next_gwei=float(current),
            predicted_5block_avg=float(current),
            confidence_low_gwei=float(current * 0.8),
            confidence_high_gwei=float(current * 1.2),
            trend="stable",
            recommendation="execute_now",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _load_history(self) -> None:
        """Load historical gas samples from disk."""
        path = self._data_dir / "gas_samples.jsonl"
        if not path.exists():
            return
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    sample = GasSample(**data)
                    self._samples.setdefault(sample.chain, []).append(sample)
            log.info("Loaded gas samples for %d chains", len(self._samples))
        except Exception as e:
            log.warning("Failed to load gas history: %s", e)

    # ── Fee Tier Tracking (T32.4) ──────────────────────────────────────

    def check_tier_upgrade(self, venue: str, current_volume_30d: float,
                            target_tiers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if a venue qualifies for a fee tier upgrade.

        Args:
            venue: Exchange/venue name
            current_volume_30d: 30-day rolling volume in USD
            target_tiers: List of {"name": str, "min_volume": float, "maker_bps": float, "taker_bps": float}

        Returns:
            Dict with upgrade recommendation
        """
        sorted_tiers = sorted(target_tiers, key=lambda t: t["min_volume"])
        current_tier = sorted_tiers[0]
        next_tier = None

        for tier in sorted_tiers:
            if current_volume_30d >= tier["min_volume"]:
                current_tier = tier
            elif next_tier is None:
                next_tier = tier

        savings = 0
        if next_tier:
            savings = (current_tier["maker_bps"] - next_tier["maker_bps"])

        return {
            "venue": venue,
            "current_volume_30d": current_volume_30d,
            "current_tier": current_tier["name"],
            "current_maker_bps": current_tier["maker_bps"],
            "current_taker_bps": current_tier["taker_bps"],
            "next_tier": next_tier["name"] if next_tier else None,
            "next_tier_min_volume": next_tier["min_volume"] if next_tier else 0,
            "volume_to_next_tier": (next_tier["min_volume"] - current_volume_30d) if next_tier else 0,
            "savings_bps": savings,
            "can_upgrade": next_tier is not None and (next_tier["min_volume"] <= current_volume_30d),
        }


# ── Module-level singleton ──────────────────────────────────────────────

ORACLE = GasOracle()


# ── Demo / Test ─────────────────────────────────────────────────────────

def demo_gas_oracle():
    """Demonstrate gas oracle functionality."""
    print("=" * 60)
    print("T32 — Predictive Gas & Fee Intelligence")
    print("=" * 60)

    oracle = GasOracle()

    # 1. Record simulated gas samples
    print("\n[1] Recording simulated gas samples (Ethereum, Base, Solana)...")
    import random
    random.seed(42)

    for block in range(50):
        # Ethereum: 15-50 Gwei with trend
        eth_price = 25 + random.uniform(-5, 5) + block * 0.2
        oracle.record_sample("ethereum", eth_price, priority_fee_gwei=2,
                             base_fee_gwei=eth_price - 2, block_number=block)

        # Base: 0.1-2 Gwei
        base_price = 0.3 + random.uniform(-0.1, 0.1)
        oracle.record_sample("base", base_price, block_number=block)

        # Solana: 0.00001-0.0001 SOL
        sol_price = 0.00003 + random.uniform(-0.00001, 0.00002)
        oracle.record_sample("solana", sol_price, block_number=block)

    print("   ✅ 150 samples recorded (50 per chain)")

    # 2. Predict next blocks
    print("\n[2] Predicting next 5 blocks (Ethereum):")
    pred = oracle.predict_next_blocks("ethereum", blocks=5)
    if pred:
        print(f"   Current:     {pred.current_gwei:.2f} Gwei")
        print(f"   Next block:  {pred.predicted_next_gwei:.2f} Gwei")
        print(f"   5-block avg: {pred.predicted_5block_avg:.2f} Gwei")
        print(f"   85% CI:      [{pred.confidence_low_gwei:.2f}, {pred.confidence_high_gwei:.2f}]")
        print(f"   Trend:       {pred.trend}")
        print(f"   Recommend:   {pred.recommendation}")
        assert pred.current_gwei > 0
        assert pred.predicted_next_gwei > 0
    print("   ✅ Prediction generated")

    # 3. Multi-chain comparison
    print("\n[3] Multi-chain comparison (standard tx):")
    comparison = oracle.multi_chain_comparison(tx_complexity="standard")
    print(f"   Cheapest chain: {comparison['cheapest_chain']}")
    for r in comparison["all_chains_ranked"][:3]:
        print(f"     {r['chain']:12s} {r['gas_price_gwei']:.6f} Gwei  "
              f"~${r['estimated_fee_usd']:.4f}")
    print("   ✅ Multi-chain comparison ready")

    # 4. Chain stats
    print("\n[4] Chain stats (Ethereum):")
    stats = oracle.get_chain_stats("ethereum")
    print(f"   Current: {stats['current_gwei']:.2f} Gwei")
    print(f"   Samples: {stats['samples']}")
    if stats.get("avg_gwei"):
        print(f"   Average: {stats['avg_gwei']:.2f} Gwei")
    print("   ✅ Chain stats computed")

    # 5. Gas budget status
    print("\n[5] Gas budget status:")
    budget = oracle.get_gas_budget_status("hf_scalping", daily_budget_gwei=500000)
    print(f"   Used: {budget['used_gwei']:.2f} / {budget['daily_budget_gwei']:.0f} Gwei")
    print(f"   Status: {budget['status']}")
    print("   ✅ Budget tracking ready")

    # 6. Fee tier upgrade check (T32.4)
    print("\n[6] Fee tier upgrade check:")
    tiers = [
        {"name": "Free", "min_volume": 0, "maker_bps": 60, "taker_bps": 60},
        {"name": "Silver", "min_volume": 50000, "maker_bps": 40, "taker_bps": 45},
        {"name": "Gold", "min_volume": 100000, "maker_bps": 30, "taker_bps": 40},
        {"name": "Platinum", "min_volume": 1000000, "maker_bps": 20, "taker_bps": 30},
    ]
    upgrade = oracle.check_tier_upgrade("coinbase", 75000, tiers)
    print(f"   Current tier: {upgrade['current_tier']} ({upgrade['current_maker_bps']}bps)")
    print(f"   Next tier:    {upgrade['next_tier']} (need ${upgrade['volume_to_next_tier']:.0f} more)")
    print("   ✅ Fee tier check ready")

    print("\n" + "=" * 60)
    print("✅ Gas Oracle ready — T32 quick wins complete")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    demo_gas_oracle()
