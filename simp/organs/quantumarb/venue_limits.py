"""
Per-Venue Position Limits & Exposure Caps — T28
================================================
Enforces per-exchange position limits and tracks aggregate exposure
across all venues.

Config: config/venue_limits.json
State: data/venue_positions.json
"""

from __future__ import annotations
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("venue_limits")


@dataclass
class VenueLimitConfig:
    venue: str
    max_position_usd: float = 100.0
    max_daily_volume_usd: float = 500.0
    max_open_positions: int = 3
    max_loss_per_day_usd: float = 20.0
    min_balance_usd: float = 1.0


@dataclass
class OpenPosition:
    position_id: str
    venue: str
    symbol: str
    side: str
    size_usd: float
    entry_price: float
    opened_at: str  # ISO timestamp


@dataclass
class VenueLimitState:
    venue: str
    positions: List[OpenPosition] = field(default_factory=list)
    daily_volume_usd: float = 0.0
    daily_loss_usd: float = 0.0
    last_reset: str = ""  # ISO date YYYY-MM-DD


@dataclass
class TradeCheckResult:
    allowed: bool
    reason: str = ""
    position_remaining_usd: float = 0.0
    volume_remaining_usd: float = 0.0
    positions_remaining: int = 0


_DEFAULT_LIMITS: Dict[str, VenueLimitConfig] = {
    "coinbase": VenueLimitConfig(venue="coinbase", max_position_usd=100.0, max_daily_volume_usd=500.0),
    "kraken": VenueLimitConfig(venue="kraken", max_position_usd=100.0, max_daily_volume_usd=500.0),
    "bitstamp": VenueLimitConfig(venue="bitstamp", max_position_usd=100.0, max_daily_volume_usd=500.0),
    "solana": VenueLimitConfig(venue="solana", max_position_usd=50.0, max_daily_volume_usd=250.0),
    "gemini": VenueLimitConfig(venue="gemini", max_position_usd=100.0, max_daily_volume_usd=500.0),
}


class VenueLimitManager:
    """
    Manages per-venue position limits.

    Usage:
        manager = VenueLimitManager()
        manager.load_config(Path("config/venue_limits.json"))

        # Before every trade:
        result = manager.can_trade(venue="coinbase", size_usd=10.0, symbol="BTC")
        if not result.allowed:
            log.warning(f"Venue limit reached: {result.reason}")

        # After trade fills:
        manager.record_trade(venue="coinbase", size_usd=10.0, symbol="BTC",
                            side="buy", pnl_usd=0.50)
    """

    def __init__(self):
        self._limits: Dict[str, VenueLimitConfig] = {}
        self._state: Dict[str, VenueLimitState] = {}
        self._lock = threading.RLock()
        self._state_file = Path("data/venue_positions.json")
        self._load_state()
        # Initialize default limits
        for venue, cfg in _DEFAULT_LIMITS.items():
            self._limits[venue] = cfg
            if venue not in self._state:
                self._state[venue] = VenueLimitState(venue=venue)

    def load_config(self, config_path: Path) -> None:
        if not config_path.exists():
            log.warning(f"Venue limits config not found: {config_path}, using defaults")
            return
        try:
            with open(config_path) as f:
                data = json.load(f)
            for item in data.get("venues", []):
                cfg = VenueLimitConfig(**item)
                self._limits[cfg.venue] = cfg
            log.info(f"Loaded venue limits for {len(self._limits)} venues")
        except Exception as e:
            log.error(f"Failed to load venue limits: {e}")

    def _check_daily_reset(self, venue: str) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        state = self._state.get(venue)
        if state and state.last_reset != today:
            state.daily_volume_usd = 0.0
            state.daily_loss_usd = 0.0
            state.last_reset = today

    def can_trade(self, venue: str, size_usd: float,
                  symbol: str, side: str = "buy") -> TradeCheckResult:
        """Check if a trade is allowed under venue limits."""
        with self._lock:
            self._check_daily_reset(venue)

            cfg = self._limits.get(venue)
            if not cfg:
                return TradeCheckResult(allowed=False, reason=f"unknown venue: {venue}")

            state = self._state.get(venue)
            if not state:
                state = VenueLimitState(venue=venue)
                self._state[venue] = state

            # Check: size <= max position
            current_pos = sum(p.size_usd for p in state.positions)
            position_remaining = max(0.0, cfg.max_position_usd - current_pos)
            if size_usd > position_remaining:
                return TradeCheckResult(
                    allowed=False,
                    reason=f"position limit: {current_pos:.2f}/{cfg.max_position_usd} USD",
                    position_remaining_usd=position_remaining,
                    positions_remaining=cfg.max_open_positions - len(state.positions),
                )

            # Check: daily volume
            if state.daily_volume_usd + size_usd > cfg.max_daily_volume_usd:
                return TradeCheckResult(
                    allowed=False,
                    reason=f"daily volume limit: {state.daily_volume_usd:.2f}/{cfg.max_daily_volume_usd} USD",
                    position_remaining_usd=position_remaining,
                    volume_remaining_usd=max(0.0, cfg.max_daily_volume_usd - state.daily_volume_usd),
                    positions_remaining=cfg.max_open_positions - len(state.positions),
                )

            # Check: open positions count
            if len(state.positions) >= cfg.max_open_positions:
                return TradeCheckResult(
                    allowed=False,
                    reason=f"max open positions: {len(state.positions)}/{cfg.max_open_positions}",
                    position_remaining_usd=position_remaining,
                    positions_remaining=0,
                )

            # Check: loss limit
            if state.daily_loss_usd >= cfg.max_loss_per_day_usd:
                return TradeCheckResult(
                    allowed=False,
                    reason=f"daily loss limit reached: {state.daily_loss_usd:.2f}/{cfg.max_loss_per_day_usd} USD",
                    position_remaining_usd=position_remaining,
                    positions_remaining=cfg.max_open_positions - len(state.positions),
                )

            return TradeCheckResult(
                allowed=True,
                position_remaining_usd=position_remaining - size_usd,
                volume_remaining_usd=cfg.max_daily_volume_usd - state.daily_volume_usd - size_usd,
                positions_remaining=cfg.max_open_positions - len(state.positions),
            )

    def record_trade(self, venue: str, size_usd: float, symbol: str,
                     side: str, pnl_usd: float = 0.0) -> None:
        """Record a completed trade and update position state."""
        with self._lock:
            self._check_daily_reset(venue)
            state = self._state.get(venue)
            if not state:
                state = VenueLimitState(venue=venue)
                self._state[venue] = state

            # Add open position
            pos = OpenPosition(
                position_id=str(uuid.uuid4())[:8],
                venue=venue,
                symbol=symbol,
                side=side,
                size_usd=size_usd,
                entry_price=0.0,  # TODO: fill from execution
                opened_at=datetime.now(timezone.utc).isoformat(),
            )
            state.positions.append(pos)

            # Update volume
            state.daily_volume_usd += size_usd

            # Update loss
            if pnl_usd < 0:
                state.daily_loss_usd += abs(pnl_usd)

            self._save_state()

    def close_position(self, position_id: str, pnl_usd: float) -> bool:
        """Close an open position by ID. Returns True if found and closed."""
        with self._lock:
            for venue, state in self._state.items():
                for i, pos in enumerate(state.positions):
                    if pos.position_id == position_id:
                        state.positions.pop(i)
                        if pnl_usd < 0:
                            state.daily_loss_usd += abs(pnl_usd)
                        self._save_state()
                        return True
            return False

    def get_total_exposure(self) -> Dict[str, float]:
        """Aggregate exposure by asset across all venues."""
        exposure: Dict[str, float] = {}
        with self._lock:
            for state in self._state.values():
                for pos in state.positions:
                    exposure[pos.symbol] = exposure.get(pos.symbol, 0.0) + pos.size_usd
        return exposure

    def get_venue_utilization(self, venue: str) -> Dict[str, float]:
        """Venue utilization percentages."""
        with self._lock:
            cfg = self._limits.get(venue)
            state = self._state.get(venue)
            if not cfg or not state:
                return {}
            current_pos = sum(p.size_usd for p in state.positions)
            return {
                "position_pct": round(current_pos / max(cfg.max_position_usd, 1), 4),
                "volume_pct": round(state.daily_volume_usd / max(cfg.max_daily_volume_usd, 1), 4),
                "loss_pct": round(state.daily_loss_usd / max(cfg.max_loss_per_day_usd, 1), 4),
                "positions_active": len(state.positions),
            }

    def _save_state(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                venue: {
                    "venue": s.venue,
                    "positions": [asdict(p) for p in s.positions],
                    "daily_volume_usd": s.daily_volume_usd,
                    "daily_loss_usd": s.daily_loss_usd,
                    "last_reset": s.last_reset,
                }
                for venue, s in self._state.items()
            }
            with open(self._state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.warning(f"Could not save venue state: {e}")

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file) as f:
                data = json.load(f)
            for venue, item in data.items():
                state = VenueLimitState(
                    venue=item["venue"],
                    positions=[OpenPosition(**p) for p in item.get("positions", [])],
                    daily_volume_usd=item.get("daily_volume_usd", 0.0),
                    daily_loss_usd=item.get("daily_loss_usd", 0.0),
                    last_reset=item.get("last_reset", ""),
                )
                self._state[venue] = state
        except Exception as e:
            log.warning(f"Could not load venue state: {e}")
