"""
Tests for A2A/FinancialOps aggregator.

These tests verify that:
- build_a2a_plan correctly aggregates agent decisions
- Aggregate exposure is computed correctly
- Risk posture is classified appropriately
- Safety checks work as expected
- Execution permission is determined correctly
"""

import pytest
from simp.financial.a2a_schema import (
    AgentDecisionSummary,
    PortfolioPosture,
    A2APlan,
    Side,
    RiskPosture,
    ExecutionMode,
)
from simp.financial.a2a_aggregator import (
    build_a2a_plan,
    compute_aggregate_exposure,
    classify_posture,
    filter_decisions_by_confidence,
    group_decisions_by_instrument,
    calculate_net_direction,
    check_agent_consensus,
    check_exposure_concentration,
    check_risk_posture_appropriateness,
    check_confidence_threshold,
    determine_execution_permission,
)


class TestAggregateExposure:
    """Tests for compute_aggregate_exposure function."""
    
    def test_single_buy_decision(self):
        """Test aggregate exposure for a single BUY decision."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
            )
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        
        assert exposure == {"BTC-USD": 1000.0}
    
    def test_single_sell_decision(self):
        """Test aggregate exposure for a single SELL decision."""
        decisions = [
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.SELL,
                quantity=5.0,
                units="ETH",
            )
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        
        assert exposure == {"ETH-USD": -5.0}
    
    def test_single_hold_decision(self):
        """Test aggregate exposure for a single HOLD decision."""
        decisions = [
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="AAPL",
                side=Side.HOLD,
                quantity=0.0,
                units="shares",
            )
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        
        assert exposure == {"AAPL": 0.0}
    
    def test_multiple_decisions_same_instrument(self):
        """Test aggregate exposure for multiple decisions on same instrument."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=500.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=300.0,
                units="USD",
            ),
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        
        # 1000 + 500 - 300 = 1200
        assert exposure == {"BTC-USD": 1200.0}
    
    def test_multiple_instruments(self):
        """Test aggregate exposure for multiple instruments."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.SELL,
                quantity=5.0,
                units="ETH",
            ),
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="AAPL",
                side=Side.HOLD,
                quantity=0.0,
                units="shares",
            ),
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        
        assert exposure == {
            "BTC-USD": 1000.0,
            "ETH-USD": -5.0,
            "AAPL": 0.0,
        }
    
    def test_empty_decisions(self):
        """Test aggregate exposure for empty decisions list."""
        exposure = compute_aggregate_exposure([])
        
        assert exposure == {}


class TestClassifyPosture:
    """Tests for classify_posture function."""
    
    def test_all_hold_conservative(self):
        """Test that all HOLD decisions result in conservative posture."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.HOLD,
                quantity=0.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="ETH-USD",
                side=Side.HOLD,
                quantity=0.0,
                units="USD",
            ),
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        posture = classify_posture(decisions, exposure)
        
        assert posture == RiskPosture.CONSERVATIVE
    
    def test_unanimous_buy_neutral(self):
        """Test that unanimous BUY decisions result in neutral posture."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.7,
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=500.0,
                units="USD",
                confidence=0.6,
            ),
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        posture = classify_posture(decisions, exposure)
        
        # With moderate confidence and not huge exposure, should be neutral
        assert posture == RiskPosture.NEUTRAL
    
    def test_high_confidence_large_exposure_aggressive(self):
        """Test that high confidence with large exposure results in aggressive posture."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=50000.0,  # Large exposure
                units="USD",
                confidence=0.9,  # High confidence
            ),
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        posture = classify_posture(decisions, exposure)
        
        assert posture == RiskPosture.AGGRESSIVE
    
    def test_conflicting_signals_neutral(self):
        """Test that conflicting signals result in neutral posture."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.8,
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=800.0,
                units="USD",
                confidence=0.7,
            ),
        ]
        
        exposure = compute_aggregate_exposure(decisions)
        posture = classify_posture(decisions, exposure)
        
        assert posture == RiskPosture.NEUTRAL
    
    def test_empty_decisions_conservative(self):
        """Test that empty decisions result in conservative posture."""
        posture = classify_posture([], {})
        
        assert posture == RiskPosture.CONSERVATIVE


class TestBuildA2APlan:
    """Tests for the main build_a2a_plan function."""
    
    def test_empty_decisions(self):
        """Test building a plan with empty decisions."""
        plan = build_a2a_plan([])
        
        assert isinstance(plan, A2APlan)
        assert len(plan.decisions) == 0
        assert isinstance(plan.portfolio_posture, PortfolioPosture)
        assert plan.portfolio_posture.risk_posture == RiskPosture.CONSERVATIVE
        assert plan.execution_allowed is False
        assert "No agent decisions" in plan.execution_reason
        assert plan.execution_mode == ExecutionMode.SIMULATED_ONLY
    
    def test_single_agent_plan(self):
        """Test building a plan with a single agent decision."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.8,
            ),
        ]
        
        plan = build_a2a_plan(decisions)
        
        assert isinstance(plan, A2APlan)
        assert len(plan.decisions) == 1
        assert plan.decisions[0].agent_name == "quantumarb"
        assert plan.portfolio_posture.aggregate_exposure["BTC-USD"] == 1000.0
        assert plan.execution_mode == ExecutionMode.SIMULATED_ONLY
        
        # With single agent and good confidence, execution might be allowed
        # but safety checks will determine final outcome
        assert isinstance(plan.execution_allowed, bool)
    
    def test_multi_agent_consensus(self):
        """Test building a plan with multiple agents in consensus."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.85,
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=500.0,
                units="USD",
                confidence=0.75,
            ),
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=300.0,
                units="USD",
                confidence=0.7,
            ),
        ]
        
        plan = build_a2a_plan(decisions)
        
        assert isinstance(plan, A2APlan)
        assert len(plan.decisions) == 3
        assert plan.portfolio_posture.aggregate_exposure["BTC-USD"] == 1800.0
        
        # All agents agree, so agent consensus check should pass
        assert "Agent consensus" in " ".join(plan.safety_checks_passed)
    
    def test_multi_agent_conflict(self):
        """Test building a plan with conflicting agent decisions."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.8,
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=800.0,
                units="USD",
                confidence=0.7,
            ),
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="BTC-USD",
                side=Side.HOLD,
                quantity=0.0,
                units="USD",
                confidence=0.6,
            ),
        ]
        
        plan = build_a2a_plan(decisions)
        
        assert isinstance(plan, A2APlan)
        assert len(plan.decisions) == 3
        assert plan.portfolio_posture.aggregate_exposure["BTC-USD"] == 200.0  # 1000 - 800
        
        # Agents conflict, so agent consensus check should fail
        assert any("conflicting" in check.lower() for check in plan.safety_checks_failed)
        
        # With conflicts, execution should not be allowed
        assert plan.execution_allowed is False
    
    def test_extreme_risk_scenario(self):
        """Test building a plan with extreme risk (very low confidence)."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=50000.0,  # Large exposure
                units="USD",
                confidence=0.1,  # Very low confidence
            ),
        ]
        
        plan = build_a2a_plan(decisions)
        
        assert isinstance(plan, A2APlan)
        
        # With very low confidence, execution should not be allowed
        assert plan.execution_allowed is False
        assert any("Low confidence" in check for check in plan.safety_checks_failed)
    
    def test_normal_safe_scenario(self):
        """Test building a plan with normal, safe parameters."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.8,
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=500.0,
                units="USD",
                confidence=0.7,
            ),
        ]
        
        plan = build_a2a_plan(decisions)
        
        assert isinstance(plan, A2APlan)
        
        # With good confidence, no conflicts, reasonable exposure
        # Execution might be allowed but simulated_only is always True in this phase
        assert plan.execution_mode == ExecutionMode.SIMULATED_ONLY
        
        # Check that safety checks were run
        assert len(plan.safety_checks_passed) + len(plan.safety_checks_failed) > 0


class TestSafetyCheckHelpers:
    """Tests for individual safety check helper functions."""
    
    def test_check_agent_consensus_agreement(self):
        """Test agent consensus check when all agents agree."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=50.0,
                units="USD",
            ),
        ]
        
        assert check_agent_consensus(decisions) is True
    
    def test_check_agent_consensus_conflict(self):
        """Test agent consensus check when agents conflict."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=50.0,
                units="USD",
            ),
        ]
        
        assert check_agent_consensus(decisions) is False
    
    def test_check_agent_consensus_hold_with_other(self):
        """Test agent consensus check when HOLD conflicts with other sides."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="BTC-USD",
                side=Side.HOLD,
                quantity=0.0,
                units="USD",
            ),
        ]
        
        assert check_agent_consensus(decisions) is False
    
    def test_check_exposure_concentration_high(self):
        """Test exposure concentration check with high concentration."""
        exposure = {
            "BTC-USD": 500.0,   # 25% of 2000 (moderate concentration, > 15% but <= 30%)
            "ETH-USD": 700.0,   # 35% of 2000 (high concentration > 30%)
            "AAPL": 800.0,      # 40% of 2000 (high concentration > 30%)
        }
        
        ok, msg = check_exposure_concentration(exposure)
        
        # ETH-USD has 35% concentration which is > 30%, so should fail
        assert ok is False
        assert "High concentration" in msg
        assert "ETH-USD" in msg
    
    def test_check_exposure_concentration_good(self):
        """Test exposure concentration check with good diversification."""
        exposure = {
            "BTC-USD": 400.0,   # 20% of 2000 (moderate concentration)
            "ETH-USD": 600.0,   # 30% of 2000 (at threshold)
            "AAPL": 1000.0,     # 50% of 2000 (high concentration)
        }
        
        ok, msg = check_exposure_concentration(exposure)
        
        # AAPL has 50% concentration which is > 30%, so should fail
        assert ok is False
        assert "High concentration" in msg
        assert "AAPL" in msg
    
    def test_check_exposure_concentration_moderate(self):
        """Test exposure concentration check with moderate concentration."""
        exposure = {
            "BTC-USD": 300.0,   # 15% of 2000 (at moderate threshold)
            "ETH-USD": 700.0,   # 35% of 2000
            "AAPL": 1000.0,     # 50% of 2000
        }
        
        ok, msg = check_exposure_concentration(exposure)
        
        # AAPL has 50% concentration which is > 30%, so should fail
        assert ok is False
        assert "High concentration" in msg
        assert "AAPL" in msg
    
    def test_check_exposure_concentration_actually_good(self):
        """Test exposure concentration check with actually good diversification."""
        exposure = {
            "BTC-USD": 300.0,   # 15% of 2000 (at moderate threshold)
            "ETH-USD": 300.0,   # 15% of 2000
            "AAPL": 400.0,      # 20% of 2000
            "GOOGL": 500.0,     # 25% of 2000
            "MSFT": 500.0,      # 25% of 2000
        }
        
        ok, msg = check_exposure_concentration(exposure)
        
        # Max concentration is 25% which is > 15% but <= 30%, so should pass with moderate
        assert ok is True
        assert "Moderate concentration" in msg
    
    def test_check_exposure_concentration_high(self):
        """Test exposure concentration check with high concentration."""
        exposure = {
            "BTC-USD": 9000.0,  # 90% of total
            "ETH-USD": 500.0,   # 5% of total
            "AAPL": 500.0,      # 5% of total
        }
        
        ok, msg = check_exposure_concentration(exposure)
        
        assert ok is False
        assert "High concentration" in msg
        assert "BTC-USD" in msg
    
    def test_check_risk_posture_appropriateness(self):
        """Test risk posture appropriateness check."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
                confidence=0.9,
            ),
        ]
        
        # Aggressive posture with high confidence is appropriate
        ok, msg = check_risk_posture_appropriateness(decisions, RiskPosture.AGGRESSIVE)
        
        assert ok is True
        assert "appropriate" in msg.lower()
    
    def test_check_confidence_threshold_good(self):
        """Test confidence threshold check with good confidence."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
                confidence=0.8,
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=50.0,
                units="USD",
                confidence=0.7,
            ),
        ]
        
        ok, msg = check_confidence_threshold(decisions)
        
        assert ok is True
        assert "High average confidence" in msg or "Moderate average confidence" in msg
    
    def test_check_confidence_threshold_low(self):
        """Test confidence threshold check with low confidence."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
                confidence=0.2,  # Below threshold
            ),
        ]
        
        ok, msg = check_confidence_threshold(decisions)
        
        assert ok is False
        assert "Low confidence" in msg


class TestExecutionPermission:
    """Tests for determine_execution_permission function."""
    
    def test_execution_allowed_all_passes(self):
        """Test execution allowed when all checks pass and posture is not aggressive."""
        passed = ["Check 1 passed", "Check 2 passed"]
        failed = []
        
        allowed, reason = determine_execution_permission(passed, failed, RiskPosture.NEUTRAL)
        
        assert allowed is True
        assert "allowed" in reason.lower()
    
    def test_execution_blocked_failed_checks(self):
        """Test execution blocked when checks fail."""
        passed = ["Check 1 passed"]
        failed = ["Check 2 failed"]
        
        allowed, reason = determine_execution_permission(passed, failed, RiskPosture.NEUTRAL)
        
        assert allowed is False
        assert "blocked" in reason.lower()
        assert "failed" in reason.lower()
    
    def test_execution_blocked_aggressive_posture(self):
        """Test execution blocked when posture is aggressive."""
        passed = ["Check 1 passed", "Check 2 passed"]
        failed = []
        
        allowed, reason = determine_execution_permission(passed, failed, RiskPosture.AGGRESSIVE)
        
        assert allowed is False
        assert "Aggressive" in reason
        assert "manual approval" in reason
    
    def test_execution_blocked_no_passed_checks(self):
        """Test execution blocked when no checks passed."""
        passed = []
        failed = []
        
        allowed, reason = determine_execution_permission(passed, failed, RiskPosture.CONSERVATIVE)
        
        assert allowed is False
        assert "No safety checks passed" in reason


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_filter_decisions_by_confidence(self):
        """Test filtering decisions by confidence threshold."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
                confidence=0.8,
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=50.0,
                units="USD",
                confidence=0.4,  # Below 0.5 threshold
            ),
            AgentDecisionSummary(
                agent_name="agent3",
                instrument="AAPL",
                side=Side.BUY,
                quantity=30.0,
                units="USD",
                confidence=None,  # No confidence data
            ),
        ]
        
        filtered = filter_decisions_by_confidence(decisions, min_confidence=0.5)
        
        assert len(filtered) == 1
        assert filtered[0].agent_name == "agent1"
    
    def test_group_decisions_by_instrument(self):
        """Test grouping decisions by instrument."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=50.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent3",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=30.0,
                units="USD",
            ),
        ]
        
        grouped = group_decisions_by_instrument(decisions)
        
        assert set(grouped.keys()) == {"BTC-USD", "ETH-USD"}
        assert len(grouped["BTC-USD"]) == 2
        assert len(grouped["ETH-USD"]) == 1
    
    def test_calculate_net_direction(self):
        """Test calculating net direction for instruments."""
        decisions = [
            AgentDecisionSummary(
                agent_name="agent1",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent2",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=50.0,
                units="USD",
            ),
            AgentDecisionSummary(
                agent_name="agent3",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=30.0,
                units="USD",
            ),
        ]
        
        net_direction = calculate_net_direction(decisions)
        
        assert "BTC-USD" in net_direction
        assert "ETH-USD" in net_direction
        
        btc_analysis = net_direction["BTC-USD"]
        assert btc_analysis["buy_size"] == 100.0
        assert btc_analysis["sell_size"] == 50.0
        assert btc_analysis["net_size"] == 50.0
        assert btc_analysis["direction"] == "buy"
        assert btc_analysis["has_conflict"] is True
        
        eth_analysis = net_direction["ETH-USD"]
        assert eth_analysis["buy_size"] == 30.0
        assert eth_analysis["sell_size"] == 0.0
        assert eth_analysis["net_size"] == 30.0
        assert eth_analysis["direction"] == "buy"
        assert eth_analysis["has_conflict"] is False


class TestAggregatorEdgeCases:
    """Test edge cases and robustness of the aggregator."""
    
    def test_absurd_quantity_values(self):
        """Test that absurdly large quantities are handled gracefully."""
        # Test with extremely large quantity (1 trillion USD)
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1_000_000_000_000.0,  # 1 trillion USD
                units="USD",
                confidence=0.8
            )
        ]
        
        plan = build_a2a_plan(decisions)
        
        # Plan should still be created
        assert plan is not None
        assert len(plan.decisions) == 1
        
        # Should have the absurdly large exposure
        assert plan.portfolio_posture.aggregate_exposure["BTC-USD"] == 1_000_000_000_000.0
        
        # Execution should be blocked due to concentration > 30%
        assert plan.execution_allowed == False
        # Check that concentration check failed
        concentration_failed = any("concentration" in check.lower() for check in plan.safety_checks_failed)
        assert concentration_failed, f"Expected concentration check to fail, but got: {plan.safety_checks_failed}"
        
        # Test with extremely small but positive quantity
        decisions_small = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=0.000001,  # Very small but positive
                units="USD",
                confidence=0.8
            )
        ]
        
        plan_small = build_a2a_plan(decisions_small)
        assert plan_small is not None
        # Single instrument with small quantity still has 100% concentration
        # so execution should be blocked
        assert plan_small.execution_allowed == False
        concentration_failed_small = any("concentration" in check.lower() for check in plan_small.safety_checks_failed)
        assert concentration_failed_small
    
    def test_missing_optional_fields(self):
        """Test that missing optional fields don't break the aggregator."""
        # Decisions without confidence, horizon_days, etc.
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                # confidence=None (default)
                # horizon_days=None (default)
                # rationale=None (default)
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=500.0,
                units="USD",
                confidence=0.7,  # Only one has confidence
            )
        ]
        
        plan = build_a2a_plan(decisions)
        
        # Plan should be created successfully
        assert plan is not None
        assert len(plan.decisions) == 2
        
        # Should have exposures for both instruments
        assert "BTC-USD" in plan.portfolio_posture.aggregate_exposure
        assert "ETH-USD" in plan.portfolio_posture.aggregate_exposure
        
        # Average confidence calculation should handle None values
        # (implementation should filter out None values)
    
    def test_mixed_units_handling(self):
        """Test that mixed units are handled (though not ideal)."""
        # Note: In real system, units should be normalized, but test that it doesn't crash
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1.5,  # BTC units
                units="BTC",
                confidence=0.8
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=30000.0,  # USD units - mixed units!
                units="USD",
                confidence=0.7
            )
        ]
        
        plan = build_a2a_plan(decisions)
        
        # Plan should still be created (though units are mixed)
        assert plan is not None
        
        # Aggregate exposure should sum them (even though units differ)
        # This is a limitation but shouldn't crash
        btc_exposure = plan.portfolio_posture.aggregate_exposure.get("BTC-USD", 0)
        assert btc_exposure == 1.5 + 30000.0  # Mixed units summed
    
    def test_duplicate_agent_decisions(self):
        """Test handling of duplicate agent decisions for same instrument."""
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",  # Same agent
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.8
            ),
            AgentDecisionSummary(
                agent_name="quantumarb",  # Same agent again (duplicate)
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=500.0,  # Additional quantity
                units="USD",
                confidence=0.8
            )
        ]
        
        plan = build_a2a_plan(decisions)
        
        # Plan should be created
        assert plan is not None
        assert len(plan.decisions) == 2  # Both decisions included
        
        # Exposure should be sum of both quantities
        assert plan.portfolio_posture.aggregate_exposure["BTC-USD"] == 1500.0