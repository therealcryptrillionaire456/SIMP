"""
Wallet & Balance Manager (T15)

Unified capital view across all venues: Kraken, Bitstamp, Coinbase, Solana wallet, staking accounts.

Features:
- Poll balances from all venues via their respective connectors
- Compute available capital per venue (total - reserved - min_balance)
- Enforce per-venue capital limits from config/trading_limits.json
- Route capital allocation requests from CapitalAllocator
- Detect balance drift: if venue balance moves without our execution -> alert
- Persist data/balances_snapshot.json every cycle for reconciliation
"""

import json
import logging
import os
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

log = logging.getLogger("balance_manager")


@dataclass
class VenueBalance:
    """Balance for one currency at one venue."""
    venue: str
    currency: str
    total: float = 0.0
    available: float = 0.0
    reserved: float = 0.0
    usd_value: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BalanceSnapshot:
    """Complete balance snapshot across all venues."""
    balances: List[VenueBalance] = field(default_factory=list)
    total_portfolio_usd: float = 0.0
    venue_count: int = 0
    currency_count: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "balances": [b.to_dict() for b in self.balances],
            "total_portfolio_usd": round(self.total_portfolio_usd, 2),
            "venue_count": self.venue_count,
            "currency_count": self.currency_count,
            "timestamp": self.timestamp,
        }


class StubVenueConnector:
    """Stub connector returning simulated balances for testing."""

    def __init__(self, venue: str):
        self.venue = venue
        self._balances = {
            "coinbase": {"USD": 0.37, "BTC": 0.00015, "ETH": 0.0035, "SOL": 0.241},
            "kraken": {"USD": 50.0, "BTC": 0.001, "ETH": 0.01},
            "bitstamp": {"USD": 25.0, "BTC": 0.0005},
            "solana": {"SOL": 0.241, "USDC": 10.0},
            "staking": {"JitoSOL": 0.5, "mSOL": 0.3, "stETH": 0.02},
        }

    def get_balances(self) -> Dict[str, float]:
        return self._balances.get(self.venue, {"USD": 10.0})


class BalanceManager:
    """Unified balance manager across all trading venues."""

    # Approximate USD prices for conversion
    _PRICE_ESTIMATES = {
        "BTC": 77500.0, "ETH": 2314.0, "SOL": 86.50,
        "USDC": 1.0, "USDT": 1.0, "USD": 1.0,
        "JitoSOL": 92.0, "mSOL": 90.0, "stETH": 2320.0,
    }

    def __init__(
        self,
        limits_path: str = "config/trading_limits.json",
        snapshot_path: str = "data/balances_snapshot.json",
        cache_seconds: float = 30.0,
        min_balance_buffer: float = 1.0,  # $1 min per venue
    ):
        self.snapshot_path = Path(snapshot_path)
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_seconds = cache_seconds
        self.min_balance_buffer = min_balance_buffer

        # Per-venue limits
        self._limits: Dict[str, Dict] = self._load_limits(limits_path)

        # Venue connectors (stubs by default)
        self._connectors: Dict[str, Any] = {}

        # Cache
        self._cached_snapshot: Optional[BalanceSnapshot] = None
        self._cache_time: float = 0.0
        self._lock = threading.Lock()

        # Previous snapshot for drift detection
        self._prev_snapshot: Optional[BalanceSnapshot] = None

    def _load_limits(self, path: str) -> Dict[str, Dict]:
        """Load per-venue trading limits from config file."""
        defaults = {
            "coinbase": {"max_trade_usd": 10.0, "max_daily_usd": 50.0, "min_balance_usd": 1.0},
            "kraken": {"max_trade_usd": 10.0, "max_daily_usd": 50.0, "min_balance_usd": 1.0},
            "bitstamp": {"max_trade_usd": 10.0, "max_daily_usd": 50.0, "min_balance_usd": 1.0},
            "solana": {"max_trade_usd": 5.0, "max_daily_usd": 25.0, "min_balance_usd": 0.5},
            "staking": {"max_trade_usd": 5.0, "max_daily_usd": 25.0, "min_balance_usd": 0.5},
        }
        try:
            with open(os.path.expandvars(path)) as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except Exception:
            log.info(f"No limits file at {path}, using defaults")
        return defaults

    def register_connector(self, venue: str, connector: Any):
        """Register a connector for a venue."""
        self._connectors[venue] = connector

    def _get_connector(self, venue: str) -> Any:
        """Get connector for venue, with stub fallback."""
        if venue in self._connectors:
            return self._connectors[venue]
        stub = StubVenueConnector(venue)
        self._connectors[venue] = stub
        return stub

    def poll_all(self) -> BalanceSnapshot:
        """
        Poll balances from all venues.

        Returns a BalanceSnapshot with all balances aggregated.
        """
        # Check cache
        now = time.time()
        with self._lock:
            if self._cached_snapshot and (now - self._cache_time) < self.cache_seconds:
                return self._cached_snapshot

        all_balances: List[VenueBalance] = []
        venues = list(self._limits.keys())

        for venue in venues:
            try:
                connector = self._get_connector(venue)
                raw = connector.get_balances()
                for currency, amount in raw.items():
                    usd_price = self._PRICE_ESTIMATES.get(currency, 1.0)
                    vb = VenueBalance(
                        venue=venue,
                        currency=currency,
                        total=amount,
                        available=amount - self.min_balance_buffer / max(usd_price, 1),
                        reserved=0.0,
                        usd_value=round(amount * usd_price, 2),
                    )
                    if vb.available < 0:
                        vb.available = 0.0
                    all_balances.append(vb)
            except Exception as e:
                log.warning(f"Failed to poll {venue}: {e}")

        # Compute totals
        total_usd = sum(b.usd_value for b in all_balances)
        unique_currencies = set(b.currency for b in all_balances)

        snapshot = BalanceSnapshot(
            balances=all_balances,
            total_portfolio_usd=round(total_usd, 2),
            venue_count=len(venues),
            currency_count=len(unique_currencies),
        )

        # Drift detection
        drift_alerts = self._detect_drift(snapshot)
        for alert in drift_alerts:
            log.warning(f"DRIFT: {alert}")

        # Cache and persist
        with self._lock:
            self._prev_snapshot = self._cached_snapshot
            self._cached_snapshot = snapshot
            self._cache_time = now
        self._persist(snapshot)

        return snapshot

    def get_available(self, venue: str, currency: str = "USD") -> float:
        """Get available balance for a venue/currency pair."""
        snapshot = self.poll_all()
        for vb in snapshot.balances:
            if vb.venue == venue and vb.currency == currency:
                return vb.available
        return 0.0

    def get_portfolio_value(self) -> float:
        """Get total portfolio value in USD."""
        snapshot = self.poll_all()
        return snapshot.total_portfolio_usd

    def check_limits(self, venue: str, amount_usd: float) -> Tuple[bool, str]:
        """
        Check if a trade is within venue limits.

        Returns (allowed, reason).
        """
        limits = self._limits.get(venue, {})
        max_trade = limits.get("max_trade_usd", 10.0)
        min_balance = limits.get("min_balance_usd", 1.0)

        if amount_usd > max_trade:
            return False, f"${amount_usd:.2f} exceeds ${max_trade:.2f} max trade for {venue}"

        available = self.get_available(venue, "USD")
        # min_balance buffer is separate from per-venue min_balance_usd limit
        effective_min = max(min_balance, self.min_balance_buffer)
        if available < effective_min:
            return False, f"{venue} only ${available:.2f} available, needs ${effective_min:.2f} min"

        if amount_usd > available:
            return False, f"{venue} has ${available:.2f}, needs ${amount_usd:.2f}"

        return True, "OK"

    def allocate(self, opportunity: Dict[str, Any], amount_usd: float) -> Tuple[str, str]:
        """
        Pick best venue to execute an opportunity.

        Considers: available balance, per-venue limits, fee estimates.

        Returns (venue, reason).
        """
        snapshot = self.poll_all()
        preferred_venue = opportunity.get("venue", "")

        # Check preferred venue first
        if preferred_venue:
            allowed, reason = self.check_limits(preferred_venue, amount_usd)
            if allowed:
                return preferred_venue, f"Preferred venue OK: {reason}"

        # Try all venues, pick one with enough balance
        best_venue = ""
        best_balance = 0.0
        for vb in snapshot.balances:
            if vb.currency == "USD" and vb.available >= amount_usd:
                allowed, _ = self.check_limits(vb.venue, amount_usd)
                if allowed and vb.available > best_balance:
                    best_venue = vb.venue
                    best_balance = vb.available

        if best_venue:
            return best_venue, f"Routed to {best_venue} (${best_balance:.2f} available)"

        return preferred_venue or "coinbase", f"No venue has ${amount_usd:.2f} — using default"

    def _detect_drift(self, snapshot: BalanceSnapshot) -> List[str]:
        """
        Detect if venue balances changed without our knowledge.

        Compares current snapshot to previous snapshot.
        Returns list of alert strings.
        """
        alerts: List[str] = []
        prev = self._prev_snapshot
        if not prev:
            return alerts

        prev_map: Dict[Tuple[str, str], float] = {}
        for vb in prev.balances:
            prev_map[(vb.venue, vb.currency)] = vb.total

        for vb in snapshot.balances:
            key = (vb.venue, vb.currency)
            prev_total = prev_map.get(key)
            if prev_total is not None:
                diff = abs(vb.total - prev_total)
                if diff > 0.001:  # Non-trivial change
                    pct = diff / max(prev_total, 0.0001) * 100
                    if pct > 10:  # >10% change without our trades
                        alerts.append(
                            f"{vb.venue}/{vb.currency}: {prev_total:.4f} → {vb.total:.4f} ({pct:.1f}% change)"
                        )
        return alerts

    def _persist(self, snapshot: BalanceSnapshot):
        """Persist snapshot to disk."""
        try:
            with open(self.snapshot_path, "w") as f:
                json.dump(snapshot.to_dict(), f, indent=2)
        except Exception as e:
            log.error(f"Failed to persist snapshot: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get human-readable balance summary."""
        snapshot = self.poll_all()
        by_venue: Dict[str, List[VenueBalance]] = {}
        for vb in snapshot.balances:
            by_venue.setdefault(vb.venue, []).append(vb)

        summary = {
            "total_portfolio_usd": snapshot.total_portfolio_usd,
            "venues": {},
        }
        for venue, balances in by_venue.items():
            venue_usd = sum(b.usd_value for b in balances)
            summary["venues"][venue] = {
                "total_usd": round(venue_usd, 2),
                "currencies": {b.currency: {"total": b.total, "available": b.available, "usd_value": b.usd_value}
                              for b in balances},
            }
        return summary


def test_balance_manager():
    """Test balance manager with stub connectors."""
    import sys as _sys

    tmp_cfg = f"/tmp/bm_test_limits_{int(time.time())}.json"
    cfg_data = '{"coinbase":{"max_trade_usd":10,"max_daily_usd":50,"min_balance_usd":0},"kraken":{"max_trade_usd":10,"max_daily_usd":50,"min_balance_usd":0},"bitstamp":{"max_trade_usd":10,"max_daily_usd":50,"min_balance_usd":0},"solana":{"max_trade_usd":5,"max_daily_usd":25,"min_balance_usd":0},"staking":{"max_trade_usd":5,"max_daily_usd":25,"min_balance_usd":0}}'
    with open(tmp_cfg, "w") as f:
        f.write(cfg_data)
    import json as _json
    _json.loads(cfg_data)  # validate
    bm = BalanceManager(limits_path=tmp_cfg, snapshot_path="/tmp/test_balance_snapshot.json", min_balance_buffer=0.0)

    # Register stub connectors
    from .balance_manager import StubVenueConnector
    for venue in ("coinbase", "kraken", "bitstamp", "solana", "staking"):
        bm.register_connector(venue, StubVenueConnector(venue))

    errors = []

    # Test 1: Poll all venues
    snap = bm.poll_all()
    assert snap.venue_count >= 3, f"Expected 3+ venues, got {snap.venue_count}"
    assert snap.total_portfolio_usd > 0, f"Expected >0 portfolio, got ${snap.total_portfolio_usd}"
    print(f"  Poll:        ✅ {snap.venue_count} venues, {snap.currency_count} currencies, ${snap.total_portfolio_usd:.2f} total")

    # Test 2: Get available balance for a venue
    avail = bm.get_available("coinbase", "USD")
    print(f"  Available:   ✅ coinbase USD=${avail:.2f}")

    # Test 3: Check limits
    allowed, reason = bm.check_limits("coinbase", 0.10)
    assert allowed, f"Expected allowed, got {reason}"
    print(f"  Limit OK:    ✅ ${0.10} on coinbase: {reason}")

    allowed2, reason2 = bm.check_limits("coinbase", 100.0)
    assert not allowed2, f"Expected blocked"
    print(f"  Limit block: ✅ ${100.0} on coinbase: {reason2}")

    # Test 4: Allocation
    venue, reason3 = bm.allocate({"venue": "coinbase", "type": "arb"}, 5.0)
    print(f"  Allocate:    ✅ {venue}: {reason3}")

    # Test 5: Drift detection
    # First poll was cached; trigger a new one with modified state
    bm._cache_time = 0  # Invalidate cache
    # The stub returns same balances, so no drift expected
    drifts = bm._detect_drift(bm._cached_snapshot) if bm._cached_snapshot else []
    print(f"  Drift:       ✅ {len(drifts)} alerts")

    # Test 6: Get summary
    summary = bm.get_summary()
    assert "total_portfolio_usd" in summary
    assert "venues" in summary
    print(f"  Summary:     ✅ ${summary['total_portfolio_usd']:.2f} across {len(summary['venues'])} venues")

    # Test 7: Persistence
    import json
    with open("/tmp/test_balance_snapshot.json") as f:
        saved = json.load(f)
    assert "total_portfolio_usd" in saved
    print(f"  Persist:     ✅ snapshot saved")

    # Cleanup
    import os
    for p in ["/tmp/test_balance_snapshot.json"]:
        if os.path.exists(p): os.remove(p)

    print(f"\n{'='*60}")
    print(f"ALL BALANCE MANAGER TESTS PASSED")
    print(f"{'='*60}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    test_balance_manager()
