"""
Tests for simp.routing.signal_router — multi-platform signal router.
"""
import asyncio
import json
import os
import pytest

os.environ.setdefault("SIMP_STARTING_CAPITAL_USD", "10000")
os.environ.setdefault("SIMP_ROUTER_DRY_RUN", "true")

from simp.routing.signal_router import (
    RouterSignal,
    RouterResult,
    PlatformResult,
    Platform,
    MultiPlatformRouter,
    OrganRegistry,
    CoinbaseLiveOrgan,
    KalshiLiveOrgan,
    AlpacaLiveOrgan,
    route_signal,
)

def _run(coro):
    """Run a coroutine synchronously — avoids pytest-asyncio dependency."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Sample signals
# ---------------------------------------------------------------------------

SAMPLE_SIGNAL = {
    "signal_id": "test-signal-001",
    "source": "quantum_intelligence_prime",
    "signal_type": "portfolio_allocation",
    "assets": {
        "BTC-USD": {"weight": 0.4, "position_usd": 4.0, "action": "buy"},
        "ETH-USD": {"weight": 0.35, "position_usd": 3.5, "action": "buy"},
        "SOL-USD": {"weight": 0.25, "position_usd": 2.5, "action": "buy"},
    },
    "metadata": {"quality_score": 0.8},
}

SELL_SIGNAL = {
    "signal_id": "test-signal-002",
    "source": "quantum_intelligence_prime",
    "signal_type": "portfolio_allocation",
    "assets": {
        "BTC-USD": {"weight": 1.0, "position_usd": 5.0, "action": "sell"},
    },
    "metadata": {"quality_score": 0.75},
}


# ---------------------------------------------------------------------------
# RouterSignal
# ---------------------------------------------------------------------------

class TestRouterSignal:
    def test_from_dict_parses_assets(self):
        sig = RouterSignal.from_dict(SAMPLE_SIGNAL)
        assert sig.signal_id == "test-signal-001"
        assert sig.source == "quantum_intelligence_prime"
        assert "BTC-USD" in sig.assets
        assert sig.assets["BTC-USD"]["position_usd"] == 4.0
        assert sig.quality_score == 0.8

    def test_from_dict_missing_fields_use_defaults(self):
        sig = RouterSignal.from_dict({"assets": {"ETH-USD": {"action": "buy", "position_usd": 1.0}}})
        assert sig.signal_id  # auto-generated UUID
        assert sig.source == "unknown"
        assert sig.quality_score == 0.5

    def test_empty_assets(self):
        sig = RouterSignal.from_dict({"signal_id": "x", "source": "test", "assets": {}})
        assert sig.assets == {}


# ---------------------------------------------------------------------------
# OrganRegistry
# ---------------------------------------------------------------------------

class TestOrganRegistry:
    def test_registry_builds_all_three_organs(self):
        reg = OrganRegistry(dry_run=True)
        assert reg.get(Platform.COINBASE) is not None
        assert reg.get(Platform.KALSHI)   is not None
        assert reg.get(Platform.ALPACA)   is not None

    def test_status_returns_dict(self):
        reg = OrganRegistry(dry_run=True)
        s = reg.status()
        assert "coinbase" in s
        assert "kalshi"   in s
        assert "alpaca"   in s
        for v in s.values():
            assert "available" in v
            assert "dry_run"   in v

    def test_unavailable_without_credentials(self):
        env_backup = {}
        for k in ("KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY",
                   "ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
            env_backup[k] = os.environ.pop(k, None)
        try:
            reg = OrganRegistry(dry_run=True)
            assert not reg.get(Platform.KALSHI).available
            assert not reg.get(Platform.ALPACA).available
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v


# ---------------------------------------------------------------------------
# CoinbaseLiveOrgan (dry-run — no real API calls)
# ---------------------------------------------------------------------------

class TestCoinbaseLiveOrgan:
    @pytest.fixture
    def organ(self):
        return CoinbaseLiveOrgan(dry_run=True)

    def test_execute_returns_platform_result(self, organ):
        sig = RouterSignal.from_dict(SAMPLE_SIGNAL)
        result = _run(organ.execute(sig))
        assert isinstance(result, PlatformResult)
        assert result.platform == Platform.COINBASE

    def test_dry_run_records_executions(self, organ):
        sig = RouterSignal.from_dict(SAMPLE_SIGNAL)
        result = _run(organ.execute(sig))
        for ex in result.executions:
            assert ex["status"] in ("dry_run", "policy_blocked", "ok", "failed", "error")

    def test_empty_assets_returns_skipped(self, organ):
        sig = RouterSignal.from_dict({"signal_id": "x", "source": "t", "assets": {}})
        result = _run(organ.execute(sig))
        assert result.status == "skipped"

    def test_hold_action_skipped(self, organ):
        sig = RouterSignal.from_dict({
            "signal_id": "x", "source": "t",
            "assets": {"BTC-USD": {"action": "hold", "position_usd": 5.0}},
        })
        result = _run(organ.execute(sig))
        assert result.status == "skipped"


# ---------------------------------------------------------------------------
# KalshiLiveOrgan — unavailable without creds
# ---------------------------------------------------------------------------

class TestKalshiLiveOrgan:
    def test_unavailable_without_creds(self):
        for k in ("KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY", "KALSHI_PRODUCTION_PRIVATE_KEY"):
            os.environ.pop(k, None)
        organ = KalshiLiveOrgan(dry_run=True)
        assert not organ.available

    def test_execute_returns_skipped_when_unavailable(self):
        for k in ("KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY", "KALSHI_PRODUCTION_PRIVATE_KEY"):
            os.environ.pop(k, None)
        organ = KalshiLiveOrgan(dry_run=True)
        sig = RouterSignal.from_dict(SAMPLE_SIGNAL)
        result = _run(organ.execute(sig))
        assert result.status == "skipped"
        assert result.platform == Platform.KALSHI


# ---------------------------------------------------------------------------
# AlpacaLiveOrgan — unavailable without creds
# ---------------------------------------------------------------------------

class TestAlpacaLiveOrgan:
    def test_unavailable_without_creds(self):
        for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_LIVE_API_KEY",
                   "ALPACA_LIVE_SECRET_KEY", "APCA_API_KEY", "APCA_API_SECRET_KEY"):
            os.environ.pop(k, None)
        organ = AlpacaLiveOrgan(dry_run=True)
        assert not organ.available

    def test_execute_returns_skipped_when_unavailable(self):
        for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_LIVE_API_KEY",
                   "ALPACA_LIVE_SECRET_KEY", "APCA_API_KEY", "APCA_API_SECRET_KEY"):
            os.environ.pop(k, None)
        organ = AlpacaLiveOrgan(dry_run=True)
        sig = RouterSignal.from_dict(SAMPLE_SIGNAL)
        result = _run(organ.execute(sig))
        assert result.status == "skipped"
        assert result.platform == Platform.ALPACA

    def test_mirror_map_covers_btc_eth_sol(self):
        organ = AlpacaLiveOrgan(dry_run=True)
        assert "BTC" in organ.MIRROR_MAP
        assert "ETH" in organ.MIRROR_MAP
        assert "SOL" in organ.MIRROR_MAP


# ---------------------------------------------------------------------------
# MultiPlatformRouter (full dry-run)
# ---------------------------------------------------------------------------

class TestMultiPlatformRouter:
    @pytest.fixture
    def router(self):
        return MultiPlatformRouter(
            dry_run=True,
            hedge_kalshi=False,
            hedge_alpaca=False,
        )

    def test_route_returns_router_result(self, router):
        result = _run(router.route(SAMPLE_SIGNAL))
        assert isinstance(result, RouterResult)
        assert result.signal_id == "test-signal-001"

    def test_route_has_platform_entries(self, router):
        result = _run(router.route(SAMPLE_SIGNAL))
        platforms = [p.platform for p in result.platforms]
        assert Platform.COINBASE in platforms

    def test_hedge_platforms_absent_when_disabled(self, router):
        result = _run(router.route(SAMPLE_SIGNAL))
        platforms = [p.platform for p in result.platforms]
        assert Platform.KALSHI not in platforms
        assert Platform.ALPACA not in platforms

    def test_hedge_platforms_present_when_enabled(self):
        router = MultiPlatformRouter(dry_run=True, hedge_kalshi=True, hedge_alpaca=True)
        result = _run(router.route(SAMPLE_SIGNAL))
        platforms = [p.platform for p in result.platforms]
        assert Platform.KALSHI in platforms
        assert Platform.ALPACA in platforms

    def test_route_sync_works(self, router):
        result = router.route_sync(SAMPLE_SIGNAL)
        assert isinstance(result, RouterResult)

    def test_status_dict(self, router):
        s = router.status()
        assert "dry_run" in s
        assert "organs"  in s

    def test_sell_signal_routes_correctly(self, router):
        result = _run(router.route(SELL_SIGNAL))
        assert isinstance(result, RouterResult)

    def test_router_result_persisted(self, router, tmp_path, monkeypatch):
        import simp.routing.signal_router as sr
        journal = tmp_path / "router_journal.jsonl"
        monkeypatch.setattr(sr, "ROUTER_JOURNAL", journal)
        _run(router.route(SAMPLE_SIGNAL))
        assert journal.exists()
        lines = [l for l in journal.read_text().splitlines() if l]
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["signal_id"] == "test-signal-001"

    def test_router_result_dry_run_flagged(self, router):
        result = _run(router.route(SAMPLE_SIGNAL))
        assert result.dry_run is True
