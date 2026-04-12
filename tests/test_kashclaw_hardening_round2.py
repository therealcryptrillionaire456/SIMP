"""
Round 2 hardening tests for KashClaw TimesFM integration.

Tests for:
- Non-mutation of caller-supplied params
- Repeated trades with history rollover
- Volatility buffer cap behavior
- Malformed forecast payloads
- Zero / tiny quantity edge cases
- Extreme slippage inputs
- Shadow mode and policy denied response consistency
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import uuid
from datetime import datetime
import copy

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.integrations.kashclaw_shim import KashClawSimpAgent
from simp.organs.spot_trading_organ import SpotTradingOrgan
from simp.integrations.trading_organ import OrganType


class TestKashClawHardeningRound2:
    """Round 2 hardening tests for KashClaw TimesFM integration"""

    @pytest.fixture
    def agent_with_organ(self):
        """Create a fresh agent with registered organ"""
        agent = KashClawSimpAgent(agent_id="test-agent-hardening-001")
        organ = SpotTradingOrgan(organ_id="test:spot:hardening:001", initial_balance=10000.0)
        agent.register_organ(organ)
        return agent

    @pytest.mark.asyncio
    async def test_non_mutation_of_caller_params(self, agent_with_organ):
        """Test that caller-supplied params are not mutated"""
        # Create original params that we'll pass
        original_params = {
            "organ_id": "test:spot:hardening:001",
            "asset_pair": "SOL/USDC",
            "side": "BUY",
            "quantity": 10.0,
            "price": 150.0,
            "slippage_tolerance": 0.02,
            "strategy_params": {"test": "value"}
        }
        
        # Make a deep copy to compare later
        params_copy = copy.deepcopy(original_params)
        
        # Mock TimesFM for high volatility to trigger adjustments
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06, 0.065]
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:hardening:001:volatility", 0.02)
                    
                    # Execute trade
                    result = await agent_with_organ.handle_trade(params_copy)
                    
                    # Verify original params were not mutated
                    assert params_copy == original_params, "Caller params were mutated!"
                    
                    # Verify trade executed successfully
                    assert result["status"] == "success"
                    assert "timesfm_sizing" in result
                    assert result["timesfm_sizing"]["applied"] is True

    @pytest.mark.asyncio
    async def test_repeated_trades_with_history_rollover(self, agent_with_organ):
        """Test repeated trades maintain consistent volatility history"""
        # Mock TimesFM for consistent responses
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.025] * 8  # Consistent forecast
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    series_id = "SOL/USDC:test:spot:hardening:001:volatility"
                    
                    # Execute multiple trades
                    all_advice = []
                    for trade_num in range(5):
                        # Get sizing advice
                        advice = await agent_with_organ._get_pre_trade_sizing_advice(
                            asset_pair="SOL/USDC",
                            organ_id="test:spot:hardening:001",
                            quantity=10.0 + trade_num,  # Varying quantity
                            slippage_tolerance=0.02 + (trade_num * 0.001),
                        )
                        all_advice.append(advice)
                        
                        # Check volatility buffer is growing
                        if series_id in agent_with_organ._volatility_buffers:
                            buffer_len = len(agent_with_organ._volatility_buffers[series_id])
                            assert buffer_len == trade_num + 1, f"Buffer length mismatch at trade {trade_num}"
                    
                    # Verify consistent behavior across trades
                    for i, advice in enumerate(all_advice):
                        assert "timesfm_applied" in advice
                        assert "timesfm_rationale" in advice

    @pytest.mark.asyncio
    async def test_volatility_buffer_cap_behavior(self, agent_with_organ):
        """Test that volatility buffer respects capacity limit"""
        series_id = "BTC/USD:test:spot:hardening:001:volatility"
        
        # Fill buffer beyond capacity
        for i in range(300):  # More than _VOLATILITY_BUFFER_CAP (256)
            agent_with_organ._record_volatility(series_id, 0.01 + (i * 0.0001))
        
        # Check buffer length is capped
        assert series_id in agent_with_organ._volatility_buffers
        buffer = agent_with_organ._volatility_buffers[series_id]
        assert len(buffer) <= 256, f"Buffer exceeded cap: {len(buffer)}"
        
        # Check oldest values were dropped (should have most recent 256)
        expected_min = 0.01 + (300 - 256) * 0.0001  # First value after dropping oldest
        assert buffer[0] == pytest.approx(expected_min, rel=1e-6), "Oldest values not properly dropped"

    @pytest.mark.asyncio
    async def test_malformed_forecast_payloads(self, agent_with_organ):
        """Test handling of various malformed forecast payloads"""
        test_cases = [
            {"available": True, "point_forecast": [None, 0.02, 0.03]},  # Mixed types
            {"available": True, "point_forecast": ["not_a_number", 0.02]},  # Strings
            {"available": True, "point_forecast": [{}]},  # Dict instead of number
            {"available": True, "point_forecast": [[]]},  # List instead of number
        ]
        
        for i, test_case in enumerate(test_cases):
            with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
                with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
                    with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                        # Setup mocks
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        mock_response.available = test_case["available"]
                        mock_response.point_forecast = test_case["point_forecast"]
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        mock_decision = Mock()
                        mock_decision.denied = False
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        # Fill fresh buffer for each test
                        fresh_agent = KashClawSimpAgent(agent_id=f"test-malformed-{i}")
                        fresh_organ = SpotTradingOrgan(organ_id=f"test:spot:malformed:{i}", initial_balance=5000.0)
                        fresh_agent.register_organ(fresh_organ)
                        
                        for j in range(20):
                            fresh_agent._record_volatility(f"BTC/USD:test:spot:malformed:{i}:volatility", 0.02)
                        
                        # Get sizing advice - should not crash
                        advice = await fresh_agent._get_pre_trade_sizing_advice(
                            asset_pair="BTC/USD",
                            organ_id=f"test:spot:malformed:{i}",
                            quantity=10.0,
                            slippage_tolerance=0.02,
                        )
                        
                        # Should handle gracefully
                        assert "timesfm_applied" in advice
                        assert "adjusted_quantity" in advice
                        assert "adjusted_slippage_tolerance" in advice
                        assert advice["adjusted_quantity"] == 10.0  # Fallback to original

    @pytest.mark.asyncio
    async def test_zero_and_tiny_quantity_edge_cases(self, agent_with_organ):
        """Test edge cases with zero and very small quantities"""
        test_cases = [
            (0.0, "zero quantity"),
            (0.00000001, "tiny quantity"),
            (1e-10, "extremely tiny quantity"),
            (-5.0, "negative quantity"),
        ]
        
        for quantity, description in test_cases:
            # Get sizing advice
            advice = await agent_with_organ._get_pre_trade_sizing_advice(
                asset_pair="BTC/USD",
                organ_id="test:spot:hardening:001",
                quantity=quantity,
                slippage_tolerance=0.02,
            )
            
            # Should handle without crashing
            assert "timesfm_applied" in advice, f"Failed for {description}"
            assert "adjusted_quantity" in advice, f"Failed for {description}"
            assert "adjusted_slippage_tolerance" in advice, f"Failed for {description}"
            
            # For negative quantities, should be clamped to non-negative
            if quantity < 0:
                assert advice["adjusted_quantity"] >= 0, f"Negative quantity not clamped: {description}"

    @pytest.mark.asyncio
    async def test_extreme_slippage_inputs(self, agent_with_organ):
        """Test handling of extreme slippage tolerance values"""
        test_cases = [
            (0.0, "zero slippage"),
            (0.5, "50% slippage"),
            (1.0, "100% slippage"),
            (10.0, "1000% slippage (extreme)"),
            (-0.1, "negative slippage"),
        ]
        
        for slippage, description in test_cases:
            # Mock TimesFM for consistent test
            with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
                with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
                    with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                        # Setup mocks
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        mock_response.available = True
                        mock_response.point_forecast = [0.03] * 8
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        mock_decision = Mock()
                        mock_decision.denied = False
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        # Fill buffer
                        fresh_agent = KashClawSimpAgent(agent_id=f"test-extreme-{hash(description)}")
                        fresh_organ = SpotTradingOrgan(organ_id=f"test:spot:extreme:{hash(description)}", initial_balance=5000.0)
                        fresh_agent.register_organ(fresh_organ)
                        
                        for i in range(20):
                            fresh_agent._record_volatility(f"BTC/USD:test:spot:extreme:{hash(description)}:volatility", abs(slippage))
                        
                        # Get sizing advice
                        advice = await fresh_agent._get_pre_trade_sizing_advice(
                            asset_pair="BTC/USD",
                            organ_id=f"test:spot:extreme:{hash(description)}",
                            quantity=10.0,
                            slippage_tolerance=slippage,
                        )
                        
                        # Should handle without crashing
                        assert "timesfm_applied" in advice, f"Failed for {description}"
                        assert "adjusted_slippage_tolerance" in advice, f"Failed for {description}"
                        
                        # Adjusted slippage should be bounded
                        if advice["timesfm_applied"]:
                            assert 0 <= advice["adjusted_slippage_tolerance"] <= 0.05, \
                                f"Slippage not bounded for {description}: {advice['adjusted_slippage_tolerance']}"

    @pytest.mark.asyncio
    async def test_shadow_mode_response_consistency(self, agent_with_organ):
        """Test that shadow mode responses are consistent"""
        # Test multiple shadow mode calls
        all_advice = []
        for i in range(3):
            with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
                with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
                    with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                        # Setup shadow mode mocks
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        mock_response.available = False  # Shadow mode
                        mock_response.point_forecast = None
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        mock_decision = Mock()
                        mock_decision.denied = False
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        # Fill buffer
                        fresh_agent = KashClawSimpAgent(agent_id=f"test-shadow-{i}")
                        fresh_organ = SpotTradingOrgan(organ_id=f"test:spot:shadow:{i}", initial_balance=5000.0)
                        fresh_agent.register_organ(fresh_organ)
                        
                        for j in range(20):
                            fresh_agent._record_volatility(f"BTC/USD:test:spot:shadow:{i}:volatility", 0.02)
                        
                        # Get sizing advice
                        advice = await fresh_agent._get_pre_trade_sizing_advice(
                            asset_pair="BTC/USD",
                            organ_id=f"test:spot:shadow:{i}",
                            quantity=10.0 + i,
                            slippage_tolerance=0.02,
                        )
                        
                        all_advice.append(advice)
        
        # Verify consistent shadow mode behavior
        for advice in all_advice:
            assert advice["timesfm_applied"] is False
            assert "shadow mode" in advice["timesfm_rationale"].lower()
            assert advice["adjusted_quantity"] > 0  # Should preserve original quantity

    @pytest.mark.asyncio
    async def test_policy_denied_response_consistency(self, agent_with_organ):
        """Test that policy denied responses are consistent"""
        # Test multiple policy denied calls with different reasons
        denial_reasons = [
            "insufficient_trust_score",
            "rate_limit_exceeded",
            "volatility_too_high",
        ]
        
        all_advice = []
        for reason in denial_reasons:
            with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                mock_decision = Mock()
                mock_decision.denied = True
                mock_decision.reason = reason
                mock_engine.return_value.evaluate.return_value = mock_decision
                
                # Fill buffer
                fresh_agent = KashClawSimpAgent(agent_id=f"test-deny-{reason}")
                fresh_organ = SpotTradingOrgan(organ_id=f"test:spot:deny:{reason}", initial_balance=5000.0)
                fresh_agent.register_organ(fresh_organ)
                
                for i in range(20):
                    fresh_agent._record_volatility(f"BTC/USD:test:spot:deny:{reason}:volatility", 0.02)
                
                # Get sizing advice
                advice = await fresh_agent._get_pre_trade_sizing_advice(
                    asset_pair="BTC/USD",
                    organ_id=f"test:spot:deny:{reason}",
                    quantity=10.0,
                    slippage_tolerance=0.02,
                )
                
                all_advice.append(advice)
        
        # Verify consistent policy denied behavior
        for advice, reason in zip(all_advice, denial_reasons):
            assert advice["timesfm_applied"] is False
            assert "policy denied" in advice["timesfm_rationale"].lower()
            assert reason in advice["timesfm_rationale"]
            assert advice["adjusted_quantity"] == 10.0  # Should preserve original