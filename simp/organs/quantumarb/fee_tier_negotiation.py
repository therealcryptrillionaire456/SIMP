"""
Adaptive Fee Tier Negotiation — T23
====================================
Negotiate tiered maker fees across venues based on 30-day volume.
Directly improves arb gross margin by reducing fee drag.

Each venue offers different maker/taker fee tiers based on 30-day
volume. This module:
  1. Tracks rolling 30-day volume per venue
  2. Maps volume to known fee tiers for each venue
  3. Recommends volume routing to hit the next tier
  4. Calculates fee savings from tier upgrades

Supports: Coinbase, Kraken, Bitstamp, Binance (by pattern)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("fee_tier_negotiation")


@dataclass
class FeeTier:
    """A single fee tier for a venue."""
    venue: str
    tier_name: str
    min_30d_volume_usd: float  # Minimum 30-day volume to qualify
    maker_fee_bps: float       # Maker fee in basis points
    taker_fee_bps: float       # Taker fee in basis points
    rebate_bps: float = 0.0    # Negative fee (rebate) for high-volume makers

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VenueFeeProfile:
    """Current fee situation for a venue."""
    venue: str
    current_tier: Optional[FeeTier]
    next_tier: Optional[FeeTier]
    current_30d_volume_usd: float
    maker_fee_bps: float
    taker_fee_bps: float
    volume_to_next_tier_usd: float
    savings_per_1m_bps: float    # BPS savings if next tier reached
    savings_per_1m_usd: float    # USD savings per $1M at next tier

    def to_dict(self) -> dict:
        return {
            "venue": self.venue,
            "current_tier": self.current_tier.to_dict() if self.current_tier else None,
            "next_tier": self.next_tier.to_dict() if self.next_tier else None,
            "current_30d_volume_usd": self.current_30d_volume_usd,
            "maker_fee_bps": self.maker_fee_bps,
            "taker_fee_bps": self.taker_fee_bps,
            "volume_to_next_tier_usd": self.volume_to_next_tier_usd,
            "savings_per_1m_bps": self.savings_per_1m_bps,
            "savings_per_1m_usd": self.savings_per_1m_usd,
        }


# Default fee tiers for known venues (as of 2025)
DEFAULT_FEE_TIERS: Dict[str, List[FeeTier]] = {
    "coinbase": [
        FeeTier("coinbase", "Free", 0, 60.0, 60.0),          # 0.6% / 0.6%
        FeeTier("coinbase", "Bronze", 10_000, 50.0, 50.0),    # Under $10k
        FeeTier("coinbase", "Silver", 50_000, 40.0, 45.0),
        FeeTier("coinbase", "Gold", 100_000, 30.0, 40.0),
        FeeTier("coinbase", "Platinum", 1_000_000, 20.0, 30.0),
        FeeTier("coinbase", "Diamond", 10_000_000, 10.0, 20.0),
        FeeTier("coinbase", "Elite", 50_000_000, 0.0, 15.0),
    ],
    "kraken": [
        FeeTier("kraken", "Starter", 0, 16.0, 26.0),
        FeeTier("kraken", "Intermediate", 50_000, 14.0, 24.0),
        FeeTier("kraken", "Pro", 100_000, 10.0, 20.0),
        FeeTier("kraken", "VIP 1", 1_000_000, 6.0, 16.0),
        FeeTier("kraken", "VIP 2", 5_000_000, 4.0, 14.0),
        FeeTier("kraken", "VIP 3", 10_000_000, 2.0, 12.0),
        FeeTier("kraken", "VIP 4", 25_000_000, 0.0, 10.0),
        FeeTier("kraken", "VIP 5", 50_000_000, -2.5, 8.0),  # Maker rebate
    ],
    "bitstamp": [
        FeeTier("bitstamp", "Level 1", 0, 30.0, 40.0),
        FeeTier("bitstamp", "Level 2", 20_000, 25.0, 35.0),
        FeeTier("bitstamp", "Level 3", 100_000, 20.0, 30.0),
        FeeTier("bitstamp", "Level 4", 1_000_000, 15.0, 25.0),
        FeeTier("bitstamp", "Level 5", 5_000_000, 10.0, 20.0),
    ],
    "jupiter": [
        FeeTier("jupiter", "Default", 0, 3.0, 5.0),           # DEX — much lower
    ],
}


class FeeTierNegotiator:
    """
    Tracks 30-day volume and negotiates fee tiers.

    Thread-safe. Persists volume history to JSONL for cross-session tracking.
    """

    def __init__(self, data_dir: str = "data/fee_tiers"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        # volume_log[venue] = list of (timestamp, volume_usd) sorted chronologically
        self._volume_log: Dict[str, List[Tuple[float, float]]] = {}
        self._fee_tiers: Dict[str, List[FeeTier]] = {}
        self._load_volume()

        # Load custom tier overrides if file exists
        self._fee_tiers.update(DEFAULT_FEE_TIERS)
        self._load_custom_tiers()

        log.info(
            "FeeTierNegotiator initialized (venues=%s)",
            list(self._fee_tiers.keys()),
        )

    # ── Public API ──────────────────────────────────────────────────────

    def record_volume(self, venue: str, volume_usd: float) -> None:
        """Record a trade volume for a venue (USD notional)."""
        with self._lock:
            self._volume_log.setdefault(venue, []).append((time.time(), volume_usd))

    def get_30d_volume(self, venue: str) -> float:
        """Get the total 30-day trailing volume for a venue."""
        cutoff = time.time() - 30 * 86400
        with self._lock:
            log_entries = self._volume_log.get(venue, [])
            return sum(v for ts, v in log_entries if ts >= cutoff)

    def get_current_tier(self, venue: str) -> Optional[FeeTier]:
        """Get the fee tier the venue qualifies for based on 30d volume."""
        volume_30d = self.get_30d_volume(venue)
        tiers = self._fee_tiers.get(venue, [])
        if not tiers:
            return None

        # Find the highest tier that the volume qualifies for
        current = tiers[0]
        for tier in reversed(tiers):
            if volume_30d >= tier.min_30d_volume_usd:
                current = tier
                break
        return current

    def get_next_tier(self, venue: str) -> Optional[FeeTier]:
        """Get the next fee tier above the current one."""
        volume_30d = self.get_30d_volume(venue)
        tiers = self._fee_tiers.get(venue, [])
        if not tiers:
            return None

        for tier in tiers:
            if tier.min_30d_volume_usd > volume_30d:
                return tier
        return None  # Already at highest tier

    def get_profile(self, venue: str) -> Optional[VenueFeeProfile]:
        """Get the full fee profile for a venue."""
        current = self.get_current_tier(venue)
        next_tier = self.get_next_tier(venue)
        volume_30d = self.get_30d_volume(venue)

        if not current:
            return None

        maker_fee = current.maker_fee_bps
        taker_fee = current.taker_fee_bps

        if next_tier:
            volume_needed = next_tier.min_30d_volume_usd - volume_30d
            savings_bps = max(0, maker_fee - next_tier.maker_fee_bps)
            savings_usd = savings_bps / 10000 * 1_000_000  # per $1M
        else:
            volume_needed = 0.0
            savings_bps = 0.0
            savings_usd = 0.0

        return VenueFeeProfile(
            venue=venue,
            current_tier=current,
            next_tier=next_tier,
            current_30d_volume_usd=round(volume_30d, 2),
            maker_fee_bps=maker_fee,
            taker_fee_bps=taker_fee,
            volume_to_next_tier_usd=round(volume_needed, 2),
            savings_per_1m_bps=round(savings_bps, 2),
            savings_per_1m_usd=round(savings_usd, 2),
        )

    def get_all_profiles(self) -> Dict[str, VenueFeeProfile]:
        """Get fee profiles for all known venues."""
        profiles = {}
        for venue in self._fee_tiers:
            profile = self.get_profile(venue)
            if profile:
                profiles[venue] = profile
        return profiles

    def recommend_volume_routing(
        self, target_venue: str, trade_usd: float
    ) -> Dict[str, Any]:
        """
        Recommend whether to route volume through target_venue to hit next tier.

        Args:
            target_venue: Venue to route to
            trade_usd: Size of the trade in USD

        Returns:
            Dict with routing recommendation and savings analysis
        """
        profile = self.get_profile(target_venue)
        if not profile or not profile.next_tier:
            return {"route_to": target_venue, "reason": "already_at_top_tier"}

        volume_needed = profile.volume_to_next_tier_usd
        if volume_needed <= 0:
            return {"route_to": target_venue, "reason": "already_qualifies"}

        # If this trade gets us closer to next tier, recommend it
        remaining_after_trade = max(0, volume_needed - trade_usd)
        pct_to_next = min(100, (trade_usd / volume_needed) * 100) if volume_needed > 0 else 100

        return {
            "route_to": target_venue,
            "current_volume_30d": profile.current_30d_volume_usd,
            "volume_to_next_tier": volume_needed,
            "trade_usd": trade_usd,
            "remaining_after_trade": remaining_after_trade,
            "pct_to_next_tier": round(pct_to_next, 1),
            "savings_at_next_tier_bps": profile.savings_per_1m_bps,
            "savings_at_next_tier_per_1m_usd": profile.savings_per_1m_usd,
            "reason": "routing_to_hit_next_tier" if pct_to_next > 0 else "minimal_impact",
        }

    def get_fee_savings_summary(self) -> Dict[str, Any]:
        """
        Get a summary of potential fee savings across all venues.

        Returns dict with potential savings if all venues upgraded one tier.
        """
        profiles = self.get_all_profiles()
        total_savings_bps = 0.0
        venues_near_upgrade = 0
        total_volume_to_next = 0.0

        for venue, profile in profiles.items():
            if profile.next_tier:
                total_savings_bps += profile.savings_per_1m_bps
                total_volume_to_next += profile.volume_to_next_tier_usd
                if profile.volume_to_next_tier_usd < 1_000_000:  # <$1M from next tier
                    venues_near_upgrade += 1

        return {
            "total_potential_savings_bps": round(total_savings_bps, 2),
            "total_volume_to_next_tier_usd": round(total_volume_to_next, 2),
            "venues_near_upgrade": venues_near_upgrade,
            "total_venues": len(profiles),
        }

    def set_fee_tiers(self, venue: str, tiers: List[FeeTier]) -> None:
        """Override fee tiers for a venue (for custom negotiation)."""
        with self._lock:
            self._fee_tiers[venue] = tiers
        self._save_custom_tiers()
        log.info("Updated fee tiers for %s: %d tiers", venue, len(tiers))

    def persist(self) -> None:
        """Persist volume log and fee tier data."""
        self._save_volume()
        self._save_custom_tiers()

    # ── Internal: Volume Persistence ────────────────────────────────────

    def _save_volume(self) -> None:
        """Write volume log to JSONL."""
        path = self._data_dir / "volume_log.jsonl"
        with self._lock:
            with open(path, "w") as f:
                for venue, entries in self._volume_log.items():
                    for ts, vol in entries:
                        record = {"venue": venue, "timestamp": ts, "volume_usd": vol}
                        f.write(json.dumps(record) + "\n")
        log.debug("Saved volume log to %s", path)

    def _load_volume(self) -> None:
        """Load volume log from JSONL."""
        path = self._data_dir / "volume_log.jsonl"
        if not path.exists():
            return
        cutoff = time.time() - 30 * 86400  # Only keep last 30 days
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    ts = float(record["timestamp"])
                    if ts >= cutoff:
                        venue = record["venue"]
                        vol = float(record["volume_usd"])
                        self._volume_log.setdefault(venue, []).append((ts, vol))
            log.info("Loaded volume logs for %d venues", len(self._volume_log))
        except Exception as e:
            log.warning("Failed to load volume log: %s", e)

    def _save_custom_tiers(self) -> None:
        """Save custom fee tier overrides to JSON."""
        path = self._data_dir / "custom_tiers.json"
        custom = {v: [t.to_dict() for t in tiers] for v, tiers in self._fee_tiers.items()
                  if v not in DEFAULT_FEE_TIERS or DEFAULT_FEE_TIERS[v] != tiers}
        with open(path, "w") as f:
            json.dump(custom, f, indent=2)

    def _load_custom_tiers(self) -> None:
        """Load custom fee tier overrides from JSON."""
        path = self._data_dir / "custom_tiers.json"
        if not path.exists():
            return
        try:
            with open(path) as f:
                custom = json.load(f)
            for venue, tier_list in custom.items():
                tiers = [FeeTier(**t) for t in tier_list]
                self._fee_tiers[venue] = tiers
            log.info("Loaded custom fee tiers for %d venues", len(custom))
        except Exception as e:
            log.warning("Failed to load custom tiers: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

FEE_NEGOTIATOR = FeeTierNegotiator()
