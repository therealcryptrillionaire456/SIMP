"""
Tests for simp.policies.trading_policy — kill switch and risk gate.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from simp.policies.trading_policy import (
    TradingPolicy,
    PolicyViolation,
    check_trade_allowed,
    _LOSS_TRACKER,
)
# Prevent module-level singleton from hitting real exchange APIs during import
os.environ.setdefault("SIMP_STARTING_CAPITAL_USD", "10000")


@pytest.fixture(autouse=True)
def reset_loss_tracker():
    """Reset shared daily loss state between tests."""
    _LOSS_TRACKER.reset()
    yield
    _LOSS_TRACKER.reset()


@pytest.fixture
def policy(tmp_path):
    kill_switch = tmp_path / "KILL_SWITCH"
    # Use explicit starting_capital_usd to avoid hitting real exchange APIs in tests
    return TradingPolicy(kill_switch_path=kill_switch, starting_capital_usd=10_000.0)


# ---------------------------------------------------------------------------
# Kill switch tests
# ---------------------------------------------------------------------------

class TestKillSwitch:
    def test_inactive_by_default(self, policy):
        assert not policy.is_killed()

    def test_activate_creates_file(self, policy, tmp_path):
        policy.activate_kill_switch("test reason")
        kill_path = tmp_path / "KILL_SWITCH"
        assert kill_path.exists()
        data = json.loads(kill_path.read_text())
        assert data["reason"] == "test reason"

    def test_deactivate_removes_file(self, policy, tmp_path):
        policy.activate_kill_switch("test")
        policy.deactivate_kill_switch()
        assert not policy.is_killed()

    def test_active_kill_switch_blocks_all_trades(self, policy):
        policy.activate_kill_switch("emergency stop")
        with pytest.raises(PolicyViolation, match="Kill switch is active"):
            policy.check(exchange="coinbase_paper", size_usd=100.0)

    def test_active_kill_switch_blocks_dry_run_too(self, policy):
        policy.activate_kill_switch("test")
        with pytest.raises(PolicyViolation, match="Kill switch is active"):
            policy.check(exchange="coinbase_paper", size_usd=100.0, dry_run=True)

    def test_kill_switch_info_when_inactive(self, policy):
        assert policy.kill_switch_info() is None

    def test_kill_switch_info_when_active(self, policy):
        policy.activate_kill_switch("reason X")
        info = policy.kill_switch_info()
        assert info is not None
        assert info["reason"] == "reason X"


# ---------------------------------------------------------------------------
# Exchange allowlist tests
# ---------------------------------------------------------------------------

class TestExchangeAllowlist:
    def test_paper_exchange_allowed(self, policy):
        assert policy.check(exchange="coinbase_paper", size_usd=100.0) is True

    def test_alpaca_paper_allowed(self, policy):
        assert policy.check(exchange="alpaca_paper", size_usd=100.0) is True

    def test_unlisted_exchange_blocked(self, policy):
        with pytest.raises(PolicyViolation, match="not in the allowlist"):
            policy.check(exchange="shady_exchange", size_usd=100.0)

    def test_live_exchange_blocked_by_default(self, policy):
        with pytest.raises(PolicyViolation, match="not in the allowlist"):
            policy.check(exchange="coinbase", size_usd=100.0)

    def test_exchange_check_skipped_for_dry_run(self, policy):
        # dry_run skips exchange + size + position checks (but not kill switch)
        assert policy.check(exchange="anywhere", size_usd=999_999.0, dry_run=True) is True


# ---------------------------------------------------------------------------
# Position size tests
# ---------------------------------------------------------------------------

class TestPositionSize:
    # With $10k capital and 5% max position = $500 limit
    def test_within_limit_allowed(self, policy):
        assert policy.check(exchange="coinbase_paper", size_usd=499.0) is True

    def test_at_limit_allowed(self, policy):
        assert policy.check(exchange="coinbase_paper", size_usd=500.0) is True

    def test_over_limit_blocked(self, policy):
        # 5% of $10k = $500; $501 should fail
        with pytest.raises(PolicyViolation, match="exceeds maximum"):
            policy.check(exchange="coinbase_paper", size_usd=501.0)


# ---------------------------------------------------------------------------
# Open positions tests
# ---------------------------------------------------------------------------

class TestOpenPositions:
    def test_under_limit_allowed(self, policy):
        assert policy.check(exchange="coinbase_paper", size_usd=100.0, open_positions=2) is True

    def test_at_limit_blocked(self, policy):
        with pytest.raises(PolicyViolation, match="at maximum"):
            policy.check(exchange="coinbase_paper", size_usd=100.0, open_positions=3)


# ---------------------------------------------------------------------------
# Daily loss limit tests
# ---------------------------------------------------------------------------

class TestDailyLossLimit:
    def test_within_budget_allowed(self, policy):
        policy.record_loss(100.0)  # well under 2% of $10k = $200
        assert policy.check(exchange="coinbase_paper", size_usd=100.0) is True

    def test_loss_exhaustion_activates_kill_switch(self, policy):
        # $10k capital, 2% = $200 limit
        policy.record_loss(201.0)
        assert policy.is_killed()

    def test_budget_exhausted_blocks_trade(self, policy):
        policy.record_loss(200.0)
        # Kill switch triggered; next check fails
        with pytest.raises(PolicyViolation):
            policy.check(exchange="coinbase_paper", size_usd=10.0)

    def test_remaining_budget_decreases(self, policy):
        initial = policy.remaining_daily_loss_budget()
        policy.record_loss(50.0)
        assert policy.remaining_daily_loss_budget() == initial - 50.0

    def test_zero_loss_ignored(self, policy):
        policy.record_loss(0.0)
        assert policy.daily_loss_total() == 0.0

    def test_negative_loss_ignored(self, policy):
        policy.record_loss(-100.0)
        assert policy.daily_loss_total() == 0.0


# ---------------------------------------------------------------------------
# Status report tests
# ---------------------------------------------------------------------------

class TestPolicyStatus:
    def test_status_structure(self, policy):
        status = policy.status()
        assert "kill_switch" in status
        assert "limits" in status
        assert "daily_loss" in status
        assert "exchanges" in status
        assert "system" in status

    def test_status_kill_switch_inactive(self, policy):
        status = policy.status()
        assert status["kill_switch"]["active"] is False
        assert status["kill_switch"]["info"] is None

    def test_status_kill_switch_active(self, policy):
        policy.activate_kill_switch("status test")
        status = policy.status()
        assert status["kill_switch"]["active"] is True
        assert status["kill_switch"]["info"]["reason"] == "status test"

    def test_status_live_trading_disabled_by_default(self, policy):
        assert policy.status()["exchanges"]["live_trading_enabled"] is False

    def test_status_shows_halt_instruction(self, policy):
        status = policy.status()
        assert "touch" in status["system"]["to_halt"]
        assert "rm" in status["system"]["to_resume"]


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

class TestModuleLevelGate:
    def test_check_trade_allowed_paper(self):
        from simp.policies.trading_policy import _DEFAULT_POLICY
        # If no credentials are configured, starting capital is $0 and all trades
        # are correctly blocked. Skip rather than fail — this is expected behaviour
        # when no exchange credentials are loaded.
        if _DEFAULT_POLICY._starting_capital_usd <= 0:
            pytest.skip(
                "No exchange credentials configured: starting capital is $0. "
                "Set COINBASE_API_KEY / ALPACA_API_KEY / SOLANA_WALLET_ADDRESS "
                "or SIMP_STARTING_CAPITAL_USD to test the module-level gate."
            )
        kill_path = Path("data/KILL_SWITCH")
        if kill_path.exists():
            pytest.skip("Kill switch is active on this machine")
        assert check_trade_allowed(exchange="coinbase_paper", size_usd=50.0) is True
