#!/usr/bin/env python3.10
"""
Staking / Yield Opportunity Scanner for QuantumArb.

READ-ONLY — scans and estimates yields from liquid staking protocols
across Solana and Ethereum. Does NOT execute any staking operations.

Provides yield aggregation, best-yield selection, and passive income
estimation for wallet balances.
"""

import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

log = logging.getLogger("StakingEngine")


# ═══════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StakingOpportunity:
    """A staking or yield opportunity from a liquid staking protocol.

    Fields capture all information needed to compare opportunities
    across chains and protocols without executing any stake.
    """
    protocol: str
    asset: str
    apy_pct: float
    min_stake: float
    lockup_days: int
    risk_score: float
    protocol_tvl: float
    timestamp: str
    estimated_daily_yield_usd: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging or display."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StakingOpportunity":
        """Deserialize from a dictionary."""
        return cls(**data)

    def __str__(self) -> str:
        return (
            f"[{self.protocol}] {self.asset} @ {self.apy_pct:.2f}% APY  "
            f"(TVL: ${self.protocol_tvl:,.0f}, "
            f"risk: {self.risk_score:.2f}, "
            f"lockup: {self.lockup_days}d)"
        )


@dataclass
class PoolInfo:
    """Information about a liquidity pool scanned by LiquidityPoolScanner."""

    pool_name: str
    dex: str
    chain: str
    apy_pct: float
    tvl: float
    volume_24h: float
    impermanent_loss_risk: float  # 0 (none) to 1 (extreme)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"[{self.dex}/{self.chain}] {self.pool_name}  "
            f"APY: {self.apy_pct:.2f}%  TVL: ${self.tvl:,.0f}"
        )


# ═══════════════════════════════════════════════════════════════════
# Solana Staking Scanner
# ═══════════════════════════════════════════════════════════════════

class SolanaStakingScanner:
    """Scans Solana liquid staking protocols for yield opportunities.

    Reads hardcoded reference rates for JitoSOL, Marinade mSOL, and
    BlazeSOL. In production, these would be fetched from on-chain
    oracles or DeFi API endpoints.
    """

    # Reference APY estimates (sampled, not live-quoted)
    _REFERENCE_RATES: Dict[str, Dict[str, float]] = {
        "JitoSOL": {
            "apy_pct": 7.5,
            "min_stake": 0.01,
            "lockup_days": 0,
            "risk_score": 0.25,
            "protocol_tvl": 2_350_000_000,
        },
        "Marinade_mSOL": {
            "apy_pct": 7.2,
            "min_stake": 0.01,
            "lockup_days": 0,
            "risk_score": 0.30,
            "protocol_tvl": 1_800_000_000,
        },
        "BlazeSOL": {
            "apy_pct": 8.0,
            "min_stake": 0.001,
            "lockup_days": 0,
            "risk_score": 0.35,
            "protocol_tvl": 450_000_000,
        },
    }

    # Estimated SOL/USD for yield calculation (stub — use API in production)
    _SOL_USD_ESTIMATE: float = 145.0

    def __init__(self, sol_usd_price: Optional[float] = None) -> None:
        self._sol_usd = sol_usd_price if sol_usd_price else self._SOL_USD_ESTIMATE
        self._fetched_at: Optional[str] = None

    def scan_solana_staking(self) -> List[StakingOpportunity]:
        """Return a list of StakingOpportunity for Solana protocols.

        Returns:
            List of StakingOpportunity with estimated APYs.
        """
        self._fetched_at = datetime.now(timezone.utc).isoformat()
        opportunities: List[StakingOpportunity] = []

        for name, data in self._REFERENCE_RATES.items():
            # Calculate estimated daily yield on 1 unit of SOL
            sol_staked = 1.0
            daily_yield = (data["apy_pct"] / 100.0) * sol_staked * self._sol_usd / 365.0
            opportunities.append(
                StakingOpportunity(
                    protocol=name,
                    asset="SOL",
                    apy_pct=data["apy_pct"],
                    min_stake=data["min_stake"],
                    lockup_days=data["lockup_days"],
                    risk_score=data["risk_score"],
                    protocol_tvl=data["protocol_tvl"],
                    timestamp=self._fetched_at,
                    estimated_daily_yield_usd=round(daily_yield, 4),
                )
            )

        log.info(
            "Scanned %d Solana staking protocols at %s",
            len(opportunities),
            self._fetched_at,
        )
        return opportunities

    def fetch_live_rate(self, protocol_name: str) -> Optional[float]:
        """Attempt to fetch a live APY from a public API endpoint.

        This is a best-effort HTTP fetch. Falls back gracefully to
        the reference rate on failure.

        Args:
            protocol_name: The protocol identifier (e.g. 'JitoSOL').

        Returns:
            A live APY percentage, or None if the fetch fails.
        """
        urls = {
            "JitoSOL": "https://api.jito.fi/v1/staking/apy",
            "Marinade_mSOL": "https://api.marinade.finative/v1/apy",
        }
        url = urls.get(protocol_name)
        if not url:
            return None

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SIMP/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    # Expecting {"apy": 7.5} or similar
                    apy = data.get("apy", data.get("apy_pct"))
                    return float(apy) if apy is not None else None
        except Exception:
            log.debug("Live APY fetch failed for %s (using reference)", protocol_name)
        return None


# ═══════════════════════════════════════════════════════════════════
# Ethereum Staking Scanner
# ═══════════════════════════════════════════════════════════════════

class EthereumStakingScanner:
    """Scans Ethereum liquid staking protocols for yield opportunities.

    Covers Lido stETH, Rocket Pool rETH, and Coinbase cbETH.
    """

    _REFERENCE_RATES: Dict[str, Dict[str, float]] = {
        "Lido_stETH": {
            "apy_pct": 3.5,
            "min_stake": 0.01,
            "lockup_days": 0,
            "risk_score": 0.15,
            "protocol_tvl": 28_000_000_000,
        },
        "RocketPool_rETH": {
            "apy_pct": 3.8,
            "min_stake": 0.01,
            "lockup_days": 0,
            "risk_score": 0.20,
            "protocol_tvl": 4_200_000_000,
        },
        "Coinbase_cbETH": {
            "apy_pct": 3.4,
            "min_stake": 0.001,
            "lockup_days": 0,
            "risk_score": 0.10,
            "protocol_tvl": 3_800_000_000,
        },
    }

    _ETH_USD_ESTIMATE: float = 3200.0

    def __init__(self, eth_usd_price: Optional[float] = None) -> None:
        self._eth_usd = eth_usd_price if eth_usd_price else self._ETH_USD_ESTIMATE
        self._fetched_at: Optional[str] = None

    def scan_ethereum_staking(self) -> List[StakingOpportunity]:
        """Return a list of StakingOpportunity for Ethereum protocols.

        Returns:
            List of StakingOpportunity with estimated APYs.
        """
        self._fetched_at = datetime.now(timezone.utc).isoformat()
        opportunities: List[StakingOpportunity] = []

        for name, data in self._REFERENCE_RATES.items():
            eth_staked = 1.0
            daily_yield = (data["apy_pct"] / 100.0) * eth_staked * self._eth_usd / 365.0
            opportunities.append(
                StakingOpportunity(
                    protocol=name,
                    asset="ETH",
                    apy_pct=data["apy_pct"],
                    min_stake=data["min_stake"],
                    lockup_days=data["lockup_days"],
                    risk_score=data["risk_score"],
                    protocol_tvl=data["protocol_tvl"],
                    timestamp=self._fetched_at,
                    estimated_daily_yield_usd=round(daily_yield, 4),
                )
            )

        log.info(
            "Scanned %d Ethereum staking protocols at %s",
            len(opportunities),
            self._fetched_at,
        )
        return opportunities


# ═══════════════════════════════════════════════════════════════════
# Yield Aggregator
# ═══════════════════════════════════════════════════════════════════

class YieldAggregator:
    """Combined scanner that aggregates yields across all supported chains.

    Provides filtering, ranking, and passive income estimation utilities.
    """

    def __init__(
        self,
        sol_scanner: Optional[SolanaStakingScanner] = None,
        eth_scanner: Optional[EthereumStakingScanner] = None,
    ) -> None:
        self._sol_scanner = sol_scanner or SolanaStakingScanner()
        self._eth_scanner = eth_scanner or EthereumStakingScanner()
        self._cache: List[StakingOpportunity] = []
        self._last_scan: Optional[str] = None

    def scan_all_yields(self) -> List[StakingOpportunity]:
        """Scan all known staking protocols across every supported chain.

        Returns:
            A combined, deduplicated list of StakingOpportunity sorted
            by APY descending.
        """
        results: List[StakingOpportunity] = []
        results.extend(self._sol_scanner.scan_solana_staking())
        results.extend(self._eth_scanner.scan_ethereum_staking())

        # Sort by APY descending
        results.sort(key=lambda o: o.apy_pct, reverse=True)

        self._cache = results
        self._last_scan = datetime.now(timezone.utc).isoformat()

        log.info("Aggregated %d opportunities from all chains", len(results))
        return results

    def best_yield_for_asset(
        self,
        asset: str,
        min_apy: float = 0.0,
    ) -> Optional[StakingOpportunity]:
        """Return the best opportunity for a given asset above a minimum APY.

        Args:
            asset: Asset symbol, e.g. 'SOL', 'ETH'.
            min_apy: Minimum APY threshold (percentage).

        Returns:
            The highest-APY StakingOpportunity for the asset, or None
            if none meet the criteria.
        """
        if not self._cache:
            self.scan_all_yields()

        candidates = [
            o for o in self._cache
            if o.asset.upper() == asset.upper() and o.apy_pct >= min_apy
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda o: o.apy_pct)

    def top_n_opportunities(self, n: int = 5) -> List[StakingOpportunity]:
        """Return the top N opportunities by APY across all chains.

        Args:
            n: Number of opportunities to return (default 5).

        Returns:
            The N highest-APY opportunities.
        """
        if not self._cache:
            self.scan_all_yields()
        return self._cache[:n]

    def estimate_passive_income(
        self,
        wallet_balances: Dict[str, float],
    ) -> Dict[str, float]:
        """Estimate passive income from staking current wallet balances.

        Uses the best available yield for each asset held.

        Args:
            wallet_balances: Mapping of asset → balance. Example:
                {"ETH": 0.0035, "SOL": 0.241, "USDC": 0.0}

        Returns:
            Dictionary with keys:
                - daily_usd: estimated income per day
                - monthly_usd: estimated income per month
                - yearly_usd: estimated income per year
                - effective_apy: weighted average APY across all held assets
        """
        if not self._cache:
            self.scan_all_yields()

        daily_total = 0.0
        total_value = 0.0
        total_apy_weighted = 0.0

        for asset, balance in wallet_balances.items():
            if balance <= 0:
                continue

            best = self.best_yield_for_asset(asset, min_apy=0.0)
            if not best:
                log.debug("No yield opportunity for %s, skipping", asset)
                continue

            # Rough proxy: if we had 1 unit, daily yield = estimated_daily_yield_usd.
            # Scale linearly for the actual balance.
            scaled_daily = best.estimated_daily_yield_usd * balance
            daily_total += scaled_daily

            # Estimate notional value using the yield formula inverted
            if best.apy_pct > 0:
                notional_value = (scaled_daily * 365.0) / (best.apy_pct / 100.0)
            else:
                notional_value = 0.0

            total_value += notional_value
            total_apy_weighted += best.apy_pct * notional_value

        monthly_total = daily_total * 30.0
        yearly_total = daily_total * 365.0

        effective_apy = (
            total_apy_weighted / total_value if total_value > 0 else 0.0
        )

        return {
            "daily_usd": round(daily_total, 2),
            "monthly_usd": round(monthly_total, 2),
            "yearly_usd": round(yearly_total, 2),
            "effective_apy": round(effective_apy, 2),
        }

    def opportunities_to_json(self, opportunities: List[StakingOpportunity]) -> str:
        """Serialize a list of opportunities to a JSON string.

        Args:
            opportunities: The opportunities to serialize.

        Returns:
            Pretty-printed JSON string.
        """
        return json.dumps(
            [o.to_dict() for o in opportunities],
            indent=2,
            default=str,
        )


# ═══════════════════════════════════════════════════════════════════
# Liquidity Pool Scanner
# ═══════════════════════════════════════════════════════════════════

class LiquidityPoolScanner:
    """Scans known liquidity pools for yield farming opportunities.

    Returns pool metadata including TVL, volume, and an estimate of
    impermanent loss risk.  Uses hardcoded reference data; in production
    this would query The Graph, DeFi Llama, or DEX APIs.
    """

    # Reference pool data — mirrors common pools across major DEXes
    _REFERENCE_POOLS: List[Dict[str, Any]] = [
        {
            "pool_name": "SOL-USDC (Orca)",
            "dex": "Orca",
            "chain": "Solana",
            "apy_pct": 12.5,
            "tvl": 185_000_000,
            "volume_24h": 42_000_000,
            "impermanent_loss_risk": 0.3,
        },
        {
            "pool_name": "mSOL-SOL (Marinade)",
            "dex": "Marinade",
            "chain": "Solana",
            "apy_pct": 6.8,
            "tvl": 320_000_000,
            "volume_24h": 15_000_000,
            "impermanent_loss_risk": 0.1,
        },
        {
            "pool_name": "ETH-USDC (Uniswap V3)",
            "dex": "Uniswap",
            "chain": "Ethereum",
            "apy_pct": 9.2,
            "tvl": 620_000_000,
            "volume_24h": 180_000_000,
            "impermanent_loss_risk": 0.4,
        },
        {
            "pool_name": "stETH-ETH (Curve)",
            "dex": "Curve",
            "chain": "Ethereum",
            "apy_pct": 5.1,
            "tvl": 2_100_000_000,
            "volume_24h": 95_000_000,
            "impermanent_loss_risk": 0.05,
        },
        {
            "pool_name": "rETH-ETH (Balancer)",
            "dex": "Balancer",
            "chain": "Ethereum",
            "apy_pct": 4.8,
            "tvl": 520_000_000,
            "volume_24h": 22_000_000,
            "impermanent_loss_risk": 0.08,
        },
        {
            "pool_name": "JitoSOL-SOL (Meteora)",
            "dex": "Meteora",
            "chain": "Solana",
            "apy_pct": 7.3,
            "tvl": 210_000_000,
            "volume_24h": 38_000_000,
            "impermanent_loss_risk": 0.12,
        },
        {
            "pool_name": "cbETH-ETH (Aerodrome)",
            "dex": "Aerodrome",
            "chain": "Base",
            "apy_pct": 6.9,
            "tvl": 95_000_000,
            "volume_24h": 12_500_000,
            "impermanent_loss_risk": 0.15,
        },
    ]

    def __init__(self) -> None:
        self._fetched_at: Optional[str] = None

    def scan_pools(self, min_tvl: float = 10000) -> List[Dict[str, Any]]:
        """Scan liquidity pools, filtering by minimum TVL.

        Args:
            min_tvl: Minimum total value locked threshold (default 10,000).

        Returns:
            List of pool dictionaries sorted by APY descending.
        """
        self._fetched_at = datetime.now(timezone.utc).isoformat()
        filtered = [
            p for p in self._REFERENCE_POOLS
            if p["tvl"] >= min_tvl
        ]
        filtered.sort(key=lambda p: p["apy_pct"], reverse=True)

        enriched = []
        for pool in filtered:
            entry = {
                **pool,
                "scan_timestamp": self._fetched_at,
            }
            enriched.append(entry)

        log.info(
            "Scanned %d liquidity pools (filtered from %d, min_tvl=%.0f)",
            len(enriched),
            len(self._REFERENCE_POOLS),
            min_tvl,
        )
        return enriched

    def scan_pools_as_objects(self, min_tvl: float = 10000) -> List[PoolInfo]:
        """Same as scan_pools but returns PoolInfo dataclass instances."""
        raw = self.scan_pools(min_tvl=min_tvl)
        return [
            PoolInfo(
                pool_name=p["pool_name"],
                dex=p["dex"],
                chain=p["chain"],
                apy_pct=p["apy_pct"],
                tvl=p["tvl"],
                volume_24h=p["volume_24h"],
                impermanent_loss_risk=p["impermanent_loss_risk"],
            )
            for p in raw
        ]


# ═══════════════════════════════════════════════════════════════════
# Module-Level Convenience
# ═══════════════════════════════════════════════════════════════════

def scan_everything() -> Dict[str, Any]:
    """Convenience function: scan all staking + all liquidity pools.

    Returns:
        Dictionary with keys 'staking' (List[StakingOpportunity]) and
        'pools' (List[PoolInfo]).
    """
    aggregator = YieldAggregator()
    staking = aggregator.scan_all_yields()
    pool_scanner = LiquidityPoolScanner()
    pools = pool_scanner.scan_pools_as_objects()
    return {
        "staking": staking,
        "pools": pools,
        "top_staking": aggregator.top_n_opportunities(3),
    }


# ═══════════════════════════════════════════════════════════════════
# Self-Test
# ═══════════════════════════════════════════════════════════════════

def test_staking_engine() -> None:
    """Run all internal tests. Callable directly or via pytest."""
    print("=== StakingEngine Self-Test ===")

    # 1. Solana scanner
    sol_scanner = SolanaStakingScanner(sol_usd_price=145.0)
    sol_ops = sol_scanner.scan_solana_staking()
    assert len(sol_ops) == 3, f"Expected 3 Solana protocols, got {len(sol_ops)}"
    for op in sol_ops:
        assert op.asset == "SOL"
        assert 0 < op.risk_score <= 1
        assert op.apy_pct > 0
        assert op.estimated_daily_yield_usd > 0
    print(f"  Solana: {len(sol_ops)} opportunities")
    for op in sol_ops:
        print(f"    {op}")

    # 2. Ethereum scanner
    eth_scanner = EthereumStakingScanner(eth_usd_price=3200.0)
    eth_ops = eth_scanner.scan_ethereum_staking()
    assert len(eth_ops) == 3, f"Expected 3 Ethereum protocols, got {len(eth_ops)}"
    for op in eth_ops:
        assert op.asset == "ETH"
        assert 0 < op.risk_score <= 1
    print(f"  Ethereum: {len(eth_ops)} opportunities")
    for op in eth_ops:
        print(f"    {op}")

    # 3. YieldAggregator
    aggregator = YieldAggregator(sol_scanner=sol_scanner, eth_scanner=eth_scanner)
    all_ops = aggregator.scan_all_yields()
    assert len(all_ops) == 6
    # Top 3 should be SOL protocols (higher APY)
    top3 = aggregator.top_n_opportunities(3)
    assert len(top3) == 3
    print(f"  Top 3: {[o.protocol for o in top3]}")

    # 4. Best yield for asset
    best_sol = aggregator.best_yield_for_asset("SOL")
    assert best_sol is not None
    assert best_sol.asset == "SOL"
    best_eth = aggregator.best_yield_for_asset("ETH")
    assert best_eth is not None
    assert best_eth.asset == "ETH"
    print(f"  Best SOL: {best_sol.protocol} @ {best_sol.apy_pct}%")
    print(f"  Best ETH: {best_eth.protocol} @ {best_eth.apy_pct}%")

    # 5. Passive income estimate
    wallet = {"ETH": 1.0, "SOL": 10.0, "USDC": 5000.0}
    income = aggregator.estimate_passive_income(wallet)
    assert "daily_usd" in income
    assert "monthly_usd" in income
    assert "yearly_usd" in income
    assert income["daily_usd"] > 0
    assert income["monthly_usd"] > income["daily_usd"]
    assert income["yearly_usd"] > income["monthly_usd"]
    print(f"  Passive income (1 ETH + 10 SOL):")
    print(f"    Daily:   ${income['daily_usd']:.2f}")
    print(f"    Monthly: ${income['monthly_usd']:.2f}")
    print(f"    Yearly:  ${income['yearly_usd']:.2f}")
    print(f"    Eff APY: {income['effective_apy']:.2f}%")

    # 6. Empty wallet
    empty = aggregator.estimate_passive_income({"ETH": 0.0, "SOL": 0.0})
    assert empty["daily_usd"] == 0.0
    assert empty["effective_apy"] == 0.0
    print(f"  Empty wallet: ${empty['daily_usd']:.2f}/day")

    # 7. LiquidityPoolScanner
    pool_scanner = LiquidityPoolScanner()
    pools = pool_scanner.scan_pools(min_tvl=10000)
    assert len(pools) == 7
    for p in pools:
        assert "scan_timestamp" in p
    print(f"  Liquidity pools: {len(pools)} pools scanned")

    pools_obj = pool_scanner.scan_pools_as_objects(min_tvl=100_000_000)
    assert len(pools_obj) < 7  # filtered by higher min_tvl
    for po in pools_obj:
        assert isinstance(po, PoolInfo)
    print(f"  Pools >$100M TVL: {len(pools_obj)}")

    # 8. Serialization round-trip
    if all_ops:
        first = all_ops[0]
        d = first.to_dict()
        restored = StakingOpportunity.from_dict(d)
        assert restored.protocol == first.protocol
        assert restored.apy_pct == first.apy_pct
        print(f"  Serialization: OK ({first.protocol} round-trips)")

    # 9. scan_everything convenience
    everything = scan_everything()
    assert "staking" in everything
    assert "pools" in everything
    assert "top_staking" in everything
    assert len(everything["pools"]) == 7
    print(f"  scan_everything: {len(everything['staking'])} staking + "
          f"{len(everything['pools'])} pools")

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_staking_engine()
