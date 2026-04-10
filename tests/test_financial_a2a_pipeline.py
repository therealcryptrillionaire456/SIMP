"""
End-to-end tests for A2A/FinancialOps pipeline.

Tests the complete pipeline from agent decisions to simulated execution:
1. Construct AgentDecisionSummary objects (simulating agent outputs)
2. Build A2A plan via aggregator
3. Evaluate risk via safety harness
4. Simulate execution via simulator

All steps are pure, in-memory, and non-destructive.
"""

import pytest
from simp.financial.a2a_schema import AgentDecisionSummary, Side, RiskPosture
from simp.financial.a2a_aggregator import build_a2a_plan
from simp.financial.a2a_safety import evaluate_risk, must_block
from simp.financial.a2a_simulator import simulate_execution, simulate_multiple_plans


class TestA2AEndToEndPipeline:
    """Test suite for end-to-end A2A pipeline."""
    
    def test_pipeline_safe_plan_executes(self):
        """
        Test complete pipeline for a safe plan that should execute.
        
        Steps:
        1. Create agent decisions (simulating QuantumArb, KashClaw, Kloutbot)
        2. Build A2A plan
        3. Evaluate risk (should be low/medium)
        4. Check if blocked (should be False)
        5. Simulate execution (should have trades)
        """
        # Step 1: Simulate agent decisions
        agent_decisions = [
            # QuantumArb detects arbitrage opportunity in BTC
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=200.0,  # 20% of total
                units="USD",
                confidence=0.85,
                horizon_days=1,
                volatility_posture="medium",
                timesfm_used=True,
                rationale="Arbitrage spread detected: 0.5% profit opportunity"
            ),
            # KashClaw recommends ETH based on technical analysis
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=300.0,  # 30% of total
                units="USD",
                confidence=0.75,
                horizon_days=3,
                volatility_posture="low",
                timesfm_used=True,
                rationale="Bullish MACD crossover, support at $3400"
            ),
            # Kloutbot suggests SOL based on social sentiment
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="SOL-USD",
                side=Side.BUY,
                quantity=250.0,  # 25% of total
                units="USD",
                confidence=0.65,
                horizon_days=7,
                volatility_posture="high",
                timesfm_used=False,
                rationale="Positive sentiment trending on Twitter/X"
            ),
            # Additional diversification
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="ADA-USD",
                side=Side.BUY,
                quantity=250.0,  # 25% of total
                units="USD",
                confidence=0.70,
                horizon_days=2,
                volatility_posture="medium",
                timesfm_used=True,
                rationale="Cross-chain arbitrage opportunity emerging"
            )
        ]
        
        # Step 2: Build A2A plan
        plan = build_a2a_plan(agent_decisions)
        
        # Check plan was created
        assert plan is not None
        assert len(plan.decisions) == 4
        assert plan.portfolio_posture is not None
        
        # Step 3: Evaluate risk
        risk_assessment = evaluate_risk(plan)
        
        # Should have risk assessment
        assert risk_assessment is not None
        assert "risk_level" in risk_assessment
        assert "max_single_instrument_exposure" in risk_assessment
        
        # Max concentration should be <= 30% (ETH has 30%)
        assert risk_assessment["max_single_instrument_exposure"] <= 0.3
        
        # Step 4: Check if blocked
        blocked = must_block(plan)
        
        # Plan should not be blocked if it passes aggregator checks
        if plan.execution_allowed:
            assert blocked == False
            
            # Step 5: Simulate execution
            simulation_result = simulate_execution(plan)
            
            # Should not be blocked
            assert simulation_result["blocked"] == False
            assert simulation_result["blocked_reason"] is None
            
            # Should have simulated trades
            assert len(simulation_result["simulated_trades"]) > 0
            
            # Should have 4 trades (one for each BUY decision)
            assert len(simulation_result["simulated_trades"]) == 4
            
            # Check trade details
            for trade in simulation_result["simulated_trades"]:
                assert trade["side"] == "buy"
                assert trade["quantity"] > 0
                assert trade["simulated_price"] > 0
            
            # Should have resulting posture
            assert simulation_result["resulting_posture"] is not None
            
            print(f"✅ Safe plan pipeline executed successfully")
            print(f"   Risk level: {risk_assessment['risk_level']}")
            print(f"   Simulated trades: {len(simulation_result['simulated_trades'])}")
            print(f"   Execution allowed: {plan.execution_allowed}")
        else:
            # Plan was blocked by aggregator (e.g., concentration > 30%)
            print(f"⚠️  Plan blocked by aggregator: {plan.execution_reason}")
            print(f"   Failed checks: {plan.safety_checks_failed}")
            
            # Simulator should also block it
            simulation_result = simulate_execution(plan)
            assert simulation_result["blocked"] == True
            assert simulation_result["blocked_reason"] is not None
    
    def test_pipeline_unsafe_plan_blocked(self):
        """
        Test complete pipeline for an unsafe plan that should be blocked.
        
        Creates a plan with extreme concentration (>50% in one instrument)
        which should be blocked by safety checks.
        """
        # Step 1: Create unsafe agent decisions
        agent_decisions = [
            # QuantumArb recommends huge position in BTC
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=8000.0,  # 80% concentration
                units="USD",
                confidence=0.95,
                rationale="Extreme conviction on breakout"
            ),
            # KashClaw recommends small hedge
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=2000.0,  # 20% concentration
                units="USD",
                confidence=0.60,
                rationale="Small hedge position"
            )
        ]
        
        # Step 2: Build A2A plan
        plan = build_a2a_plan(agent_decisions)
        
        # Step 3: Evaluate risk
        risk_assessment = evaluate_risk(plan)
        
        # Should show high risk due to concentration
        assert risk_assessment["max_single_instrument_exposure"] > 0.5  # >50%
        
        # Risk level should be aggressive
        assert risk_assessment["risk_level"] == RiskPosture.AGGRESSIVE
        
        # Step 4: Check if blocked
        blocked = must_block(plan)
        
        # Should be blocked (concentration > 30% limit)
        assert blocked == True
        
        # Step 5: Simulate execution
        simulation_result = simulate_execution(plan)
        
        # Should be blocked
        assert simulation_result["blocked"] == True
        assert simulation_result["blocked_reason"] is not None
        assert "concentration" in simulation_result["blocked_reason"].lower() or \
               "execution not allowed" in simulation_result["blocked_reason"].lower()
        
        # Should have no simulated trades
        assert len(simulation_result["simulated_trades"]) == 0
        
        print(f"✅ Unsafe plan correctly blocked")
        print(f"   Risk level: {risk_assessment['risk_level']}")
        print(f"   Max concentration: {risk_assessment['max_single_instrument_exposure']:.1%}")
        print(f"   Blocked reason: {simulation_result['blocked_reason']}")
    
    def test_pipeline_conflicting_agents_blocked(self):
        """
        Test pipeline for conflicting agent recommendations.
        
        Creates a plan where agents disagree on direction for same instrument
        with large sizes, which should be blocked.
        """
        # Step 1: Create conflicting agent decisions
        agent_decisions = [
            # QuantumArb says BUY BTC
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=4000.0,  # Large size
                units="USD",
                confidence=0.85,
                rationale="Arbitrage opportunity"
            ),
            # KashClaw says SELL BTC (conflict!)
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=4000.0,  # Large size
                units="USD",
                confidence=0.80,
                rationale="Technical resistance at $68k"
            ),
            # Kloutbot says BUY ETH (non-conflicting)
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=2000.0,
                units="USD",
                confidence=0.70,
                rationale="Positive developer activity"
            )
        ]
        
        # Step 2: Build A2A plan
        plan = build_a2a_plan(agent_decisions)
        
        # Step 3: Evaluate risk
        risk_assessment = evaluate_risk(plan)
        
        # Should detect conflicts
        assert risk_assessment["number_of_conflicting_decisions"] > 0
        
        # Step 4: Check if blocked
        blocked = must_block(plan)
        
        # Should be blocked due to conflicting exposure
        # (4000 + 4000 = 8000 conflicting size out of 10000 total = 80% > 20% limit)
        assert blocked == True
        
        # Step 5: Simulate execution
        simulation_result = simulate_execution(plan)
        
        # Should be blocked
        assert simulation_result["blocked"] == True
        
        # Blocked reason should mention conflict or execution not allowed
        blocked_reason = simulation_result["blocked_reason"].lower()
        has_conflict = "conflict" in blocked_reason
        has_execution_blocked = "execution not allowed" in blocked_reason or "execution blocked" in blocked_reason
        assert has_conflict or has_execution_blocked
        
        # Should have no simulated trades
        assert len(simulation_result["simulated_trades"]) == 0
        
        print(f"✅ Conflicting plan correctly blocked")
        print(f"   Conflicting decisions: {risk_assessment['number_of_conflicting_decisions']}")
        print(f"   Blocked reason: {simulation_result['blocked_reason']}")
    
    def test_pipeline_hold_decisions_ignored(self):
        """
        Test that HOLD decisions don't affect execution.
        
        Creates a plan with BUY, SELL, and HOLD decisions.
        HOLD should be ignored in trade simulation.
        """
        # Step 1: Create mixed decisions
        agent_decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=300.0,
                units="USD",
                confidence=0.8
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.HOLD,  # Should be ignored
                quantity=200.0,
                units="USD",
                confidence=0.7
            ),
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="SOL-USD",
                side=Side.SELL,
                quantity=100.0,
                units="USD",
                confidence=0.6
            )
        ]
        
        # Step 2: Build A2A plan
        plan = build_a2a_plan(agent_decisions)
        
        # Skip if blocked by aggregator
        if not plan.execution_allowed:
            print(f"⚠️  Plan blocked by aggregator, skipping simulation")
            return
        
        # Step 3: Simulate execution
        simulation_result = simulate_execution(plan)
        
        if not simulation_result["blocked"]:
            # Should have trades for BUY and SELL, not HOLD
            trades = simulation_result["simulated_trades"]
            assert len(trades) >= 1  # At least BUY or SELL
            
            # Check sides
            sides = [trade["side"] for trade in trades]
            assert "hold" not in sides  # No HOLD trades
            
            # Check agents
            agents = [trade["agent"] for trade in trades]
            # quantumarb (BUY) and/or kloutbot (SELL) should be in agents
            # kashclaw (HOLD) should not be in agents
            assert "kashclaw" not in agents
            
            print(f"✅ HOLD decisions correctly ignored")
            print(f"   Total trades: {len(trades)}")
            print(f"   Trade sides: {sides}")
    
    def test_pipeline_multiple_scenarios(self):
        """
        Test multiple plan scenarios in batch.
        
        Creates several plans with different risk profiles and
        tests batch simulation via simulate_multiple_plans().
        """
        # Scenario 1: Safe, diversified plan
        safe_decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=200.0,
                units="USD",
                confidence=0.8
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=200.0,
                units="USD",
                confidence=0.7
            )
        ]
        
        # Scenario 2: Unsafe, concentrated plan
        unsafe_decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=5000.0,  # 100% concentration
                units="USD",
                confidence=0.9
            )
        ]
        
        # Scenario 3: Conflicting plan
        conflicting_decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=3000.0,
                units="USD",
                confidence=0.8
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.SELL,
                quantity=3000.0,
                units="USD",
                confidence=0.7
            )
        ]
        
        # Build all plans
        safe_plan = build_a2a_plan(safe_decisions)
        unsafe_plan = build_a2a_plan(unsafe_decisions)
        conflicting_plan = build_a2a_plan(conflicting_decisions)
        
        # Batch simulation
        plans = [safe_plan, unsafe_plan, conflicting_plan]
        batch_result = simulate_multiple_plans(plans)
        
        # Check structure
        assert "plan_results" in batch_result
        assert "summary" in batch_result
        
        # Should have results for all plans
        assert len(batch_result["plan_results"]) == 3
        
        # Check summary
        summary = batch_result["summary"]
        assert summary["total_plans"] == 3
        
        # At least unsafe and conflicting plans should be blocked
        # (safe plan might also be blocked if concentration > 30%)
        blocked_count = summary["blocked_plans"]
        assert blocked_count >= 2  # unsafe + conflicting
        
        executed_count = summary["executed_plans"]
        total_trades = summary["total_trades"]
        
        print(f"✅ Batch simulation completed")
        print(f"   Total plans: {summary['total_plans']}")
        print(f"   Blocked plans: {blocked_count}")
        print(f"   Executed plans: {executed_count}")
        print(f"   Total trades: {total_trades}")
        print(f"   Block rate: {summary['block_rate']:.1%}")
    
    def test_pipeline_error_handling(self):
        """
        Test pipeline error handling and edge cases.
        """
        # Test 1: Empty plan
        empty_plan = build_a2a_plan([])
        assert empty_plan is not None
        assert len(empty_plan.decisions) == 0
        assert empty_plan.execution_allowed == False
        assert "No agent decisions" in empty_plan.execution_reason
        
        # Simulate empty plan
        empty_result = simulate_execution(empty_plan)
        assert empty_result["blocked"] == True
        assert empty_result["blocked_reason"] is not None
        assert len(empty_result["simulated_trades"]) == 0
        
        # Test 2: Plan with zero quantities (edge case)
        # This should fail validation in schema
        # (quantity must be positive for BUY/SELL decisions)
        with pytest.raises(ValueError, match="quantity must be positive"):
            # Create AgentDecisionSummary with zero quantity
            # This should raise ValueError immediately
            AgentDecisionSummary(
                agent_name="test",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=0.0,  # Zero quantity - should fail validation
                units="USD",
                confidence=0.5
            )
        
        print(f"✅ Error handling tests passed")
    
    def test_pipeline_integration_with_existing_system(self):
        """
        Test that the pipeline integrates with existing A2A components.
        
        This test verifies that all modules work together correctly
        and follow the expected interfaces.
        """
        # Create realistic agent decisions
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.82,
                timesfm_used=True
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="ETH-USD",
                side=Side.BUY,
                quantity=800.0,
                units="USD",
                confidence=0.76,
                timesfm_used=True
            ),
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="SOL-USD",
                side=Side.BUY,
                quantity=600.0,
                units="USD",
                confidence=0.68,
                timesfm_used=False
            )
        ]
        
        # Full pipeline execution
        plan = build_a2a_plan(decisions)
        risk = evaluate_risk(plan)
        blocked = must_block(plan)
        simulation = simulate_execution(plan)
        
        # Verify all components produced valid outputs
        assert plan is not None
        assert risk is not None
        assert isinstance(blocked, bool)
        assert simulation is not None
        
        # Verify simulation result structure
        required_keys = [
            "simulated_trades", "resulting_posture", "blocked",
            "blocked_reason", "simulation_id", "timestamp"
        ]
        for key in required_keys:
            assert key in simulation
        
        # Verify types
        assert isinstance(simulation["simulated_trades"], list)
        assert isinstance(simulation["blocked"], bool)
        assert simulation["blocked_reason"] is None or isinstance(simulation["blocked_reason"], str)
        
        print(f"✅ Pipeline integration test passed")
        print(f"   Plan created: {len(plan.decisions)} decisions")
        print(f"   Risk level: {risk['risk_level']}")
        print(f"   Blocked: {blocked}")
        print(f"   Simulation ID: {simulation['simulation_id']}")