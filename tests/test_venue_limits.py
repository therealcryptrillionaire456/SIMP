"""
Tests for Per-Venue Position Limits & Exposure Caps — T28
"""

from __future__ import annotations
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from simp.organs.quantumarb.venue_limits import (
    OpenPosition,
    TradeCheckResult,
    VenueLimitConfig,
    VenueLimitManager,
    VenueLimitState,
    _DEFAULT_LIMITS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_manager(state_file: Path) -> VenueLimitManager:
    """Build a VenueLimitManager with clean defaults, no state file load."""
    mgr = object.__new__(VenueLimitManager)
    mgr._limits = {}
    mgr._state = {}
    mgr._lock = threading.RLock()
    mgr._state_file = state_file
    for venue, cfg in _DEFAULT_LIMITS.items():
        mgr._limits[venue] = cfg
        mgr._state[venue] = VenueLimitState(venue=venue)
    return mgr


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_config_overrides_defaults(self, tmp_path):
        path = tmp_path / "venue_limits.json"
        data = {
            "venues": [
                {
                    "venue": "coinbase",
                    "max_position_usd": 200.0,
                    "max_daily_volume_usd": 1000.0,
                    "max_open_positions": 5,
                    "max_loss_per_day_usd": 40.0,
                },
            ]
        }
        with open(path, "w") as f:
            json.dump(data, f)

        mgr = fresh_manager(tmp_path / "state.json")
        mgr.load_config(path)

        assert mgr._limits["coinbase"].max_position_usd == 200.0
        assert mgr._limits["coinbase"].max_open_positions == 5

    def test_load_config_missing_file_no_crash(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        mgr.load_config(tmp_path / "nonexistent.json")  # should warn but not raise


# ---------------------------------------------------------------------------
# Position limit enforcement
# ---------------------------------------------------------------------------

class TestPositionLimits:
    def test_trade_within_limit(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        result = mgr.can_trade("coinbase", 50.0, "BTC", "buy")
        assert result.allowed is True
        # 100 max - 50 used = 50 remaining
        assert result.position_remaining_usd == 50.0

    def test_trade_exceeds_limit(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        result = mgr.can_trade("coinbase", 150.0, "BTC", "buy")
        assert result.allowed is False
        assert "position limit" in result.reason.lower()

    def test_aggregate_over_limit(self, tmp_path):
        """60 USD existing + 50 USD new = 110 > 100 limit → rejected."""
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        # Add one position
        state.positions.append(OpenPosition(
            position_id="pos1", venue="coinbase", symbol="BTC",
            side="buy", size_usd=60.0, entry_price=0.0,
            opened_at=datetime.now(timezone.utc).isoformat(),
        ))
        # Adding another 50 would total 110 > 100 → should fail
        result = mgr.can_trade("coinbase", 50.0, "ETH", "buy")
        assert result.allowed is False
        assert "position limit" in result.reason.lower()

    def test_aggregate_under_limit(self, tmp_path):
        """60 USD existing + 30 USD new = 90 <= 100 limit → allowed."""
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        state.positions.append(OpenPosition(
            position_id="pos1", venue="coinbase", symbol="BTC",
            side="buy", size_usd=60.0, entry_price=0.0,
            opened_at=datetime.now(timezone.utc).isoformat(),
        ))
        result = mgr.can_trade("coinbase", 30.0, "ETH", "buy")
        assert result.allowed is True


# ---------------------------------------------------------------------------
# Daily volume limit
# ---------------------------------------------------------------------------

class TestDailyVolumeLimits:
    def test_trade_exceeds_daily_volume(self, tmp_path):
        """Already at 450 USD volume, trying to add 100 → 550 > 500 limit."""
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        state.daily_volume_usd = 450.0
        state.last_reset = today_str()  # prevent reset on can_trade call

        result = mgr.can_trade("coinbase", 100.0, "BTC", "buy")
        assert result.allowed is False
        assert "volume limit" in result.reason.lower()

    def test_trade_within_volume(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        state.last_reset = today_str()
        result = mgr.can_trade("coinbase", 100.0, "BTC", "buy")
        assert result.allowed is True


# ---------------------------------------------------------------------------
# Max open positions count
# ---------------------------------------------------------------------------

class TestOpenPositionsCount:
    def test_max_open_positions_reached(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        # Fill to max (3 for coinbase)
        for i, sym in enumerate(["BTC", "ETH", "SOL"]):
            state.positions.append(OpenPosition(
                position_id=f"pos{i}", venue="coinbase", symbol=sym,
                side="buy", size_usd=5.0, entry_price=0.0,
                opened_at=datetime.now(timezone.utc).isoformat(),
            ))

        result = mgr.can_trade("coinbase", 5.0, "AVAX", "buy")
        assert result.allowed is False
        assert "max open positions" in result.reason.lower()

    def test_within_open_positions(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        result = mgr.can_trade("coinbase", 5.0, "BTC", "buy")
        assert result.allowed is True


# ---------------------------------------------------------------------------
# Daily loss limit
# ---------------------------------------------------------------------------

class TestDailyLossLimit:
    def test_loss_limit_reached(self, tmp_path):
        """daily_loss = 25 > max_loss_per_day = 20 → trade rejected."""
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        state.daily_loss_usd = 25.0
        state.last_reset = today_str()

        result = mgr.can_trade("coinbase", 10.0, "BTC", "buy")
        assert result.allowed is False
        assert "loss limit" in result.reason.lower()

    def test_loss_limit_not_reached(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        state.daily_loss_usd = 15.0
        state.last_reset = today_str()

        result = mgr.can_trade("coinbase", 10.0, "BTC", "buy")
        assert result.allowed is True


# ---------------------------------------------------------------------------
# Daily reset
# ---------------------------------------------------------------------------

class TestDailyReset:
    def test_reset_clears_volume_and_loss(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        state.daily_volume_usd = 300.0
        state.daily_loss_usd = 15.0
        state.last_reset = "2020-01-01"  # old date, will reset

        result = mgr.can_trade("coinbase", 10.0, "BTC", "buy")
        assert result.allowed is True
        assert state.daily_volume_usd == 0.0
        assert state.daily_loss_usd == 0.0


# ---------------------------------------------------------------------------
# Exposure aggregation
# ---------------------------------------------------------------------------

class TestExposureAggregation:
    def test_exposure_single_venue(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        mgr.record_trade("coinbase", 30.0, "BTC", "buy", pnl_usd=0.0)
        mgr.record_trade("coinbase", 20.0, "ETH", "buy", pnl_usd=0.0)
        exp = mgr.get_total_exposure()
        assert exp["BTC"] == 30.0
        assert exp["ETH"] == 20.0

    def test_exposure_multi_venue(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        mgr.record_trade("coinbase", 30.0, "BTC", "buy", pnl_usd=0.0)
        mgr.record_trade("kraken", 20.0, "BTC", "buy", pnl_usd=0.0)
        exp = mgr.get_total_exposure()
        assert exp["BTC"] == 50.0


# ---------------------------------------------------------------------------
# Venue utilization
# ---------------------------------------------------------------------------

class TestVenueUtilization:
    def test_utilization_zero(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        util = mgr.get_venue_utilization("coinbase")
        assert util["position_pct"] == 0.0
        assert util["volume_pct"] == 0.0
        assert util["loss_pct"] == 0.0
        assert util["positions_active"] == 0

    def test_utilization_partial(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        state = mgr._state["coinbase"]
        state.daily_volume_usd = 250.0
        state.last_reset = today_str()
        mgr.record_trade("coinbase", 25.0, "BTC", "buy", pnl_usd=0.0)
        util = mgr.get_venue_utilization("coinbase")
        assert abs(util["position_pct"] - 0.25) < 0.01
        # 250/500 = 0.5
        assert abs(util["volume_pct"] - 0.55) < 0.01

    def test_utilization_unknown_venue(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        util = mgr.get_venue_utilization("nonexistent")
        assert util == {}


# ---------------------------------------------------------------------------
# Record trade
# ---------------------------------------------------------------------------

class TestRecordTrade:
    def test_record_trade_creates_position(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        mgr.record_trade("coinbase", 20.0, "BTC", "buy", pnl_usd=0.5)
        state = mgr._state["coinbase"]
        assert len(state.positions) == 1
        assert state.positions[0].symbol == "BTC"
        assert state.daily_volume_usd == 20.0
        assert state.daily_loss_usd == 0.0

    def test_record_trade_negative_pnl(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        mgr.record_trade("coinbase", 20.0, "BTC", "buy", pnl_usd=-5.0)
        state = mgr._state["coinbase"]
        assert state.daily_loss_usd == 5.0


# ---------------------------------------------------------------------------
# Close position
# ---------------------------------------------------------------------------

class TestClosePosition:
    def test_close_found(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        mgr.record_trade("coinbase", 20.0, "BTC", "buy", pnl_usd=0.0)
        state = mgr._state["coinbase"]
        pos_id = state.positions[0].position_id

        result = mgr.close_position(pos_id, pnl_usd=1.0)
        assert result is True
        assert len(state.positions) == 0

    def test_close_not_found(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        result = mgr.close_position("nonexistent", pnl_usd=0.0)
        assert result is False

    def test_close_with_loss(self, tmp_path):
        mgr = fresh_manager(tmp_path / "state.json")
        mgr.record_trade("coinbase", 20.0, "BTC", "buy", pnl_usd=0.0)
        state = mgr._state["coinbase"]
        pos_id = state.positions[0].position_id
        mgr.close_position(pos_id, pnl_usd=-3.0)
        assert state.daily_loss_usd == 3.0


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

class TestStatePersistence:
    def test_state_saved_after_trade(self, tmp_path):
        mgr = fresh_manager(tmp_path / "vp.json")
        mgr.record_trade("coinbase", 20.0, "BTC", "buy", pnl_usd=0.0)
        assert tmp_path.joinpath("vp.json").exists()

    def test_state_loaded(self, tmp_path):
        state_path = tmp_path / "vp.json"
        data = {
            "coinbase": {
                "venue": "coinbase",
                "positions": [{
                    "position_id": "abc12345",
                    "venue": "coinbase",
                    "symbol": "BTC",
                    "side": "buy",
                    "size_usd": 50.0,
                    "entry_price": 1000.0,
                    "opened_at": "2024-01-01T00:00:00Z",
                }],
                "daily_volume_usd": 100.0,
                "daily_loss_usd": 5.0,
                "last_reset": "2024-01-01",
            }
        }
        with open(state_path, "w") as f:
            json.dump(data, f)

        mgr = fresh_manager(state_path)
        mgr._load_state()

        assert "coinbase" in mgr._state
        assert len(mgr._state["coinbase"].positions) == 1
        assert mgr._state["coinbase"].daily_volume_usd == 100.0
        assert mgr._state["coinbase"].daily_loss_usd == 5.0
