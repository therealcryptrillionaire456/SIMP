"""
Edge case tests for KashClaw TimesFM sizing integration.

Tests edge cases not covered in the main test suite:
- Zero slippage tolerance
- Very high original slippage tolerance (>5%)
- Negative quantity (should be clamped)
- Extreme volatility forecasts
- Mixed NaN/inf in forecast arrays
"""

import pytest
import asyncio
import math
from unittest.mock import Mock, AsyncMock, patch
from simp.integrations.kashclaw_shim import KashClawSimpAgent
from simp.integrations.trading_organ import TradingOrgan, OrganType


@pytest.mark.asyncio
class TestKashClawTimesFMEdgeCases:
    """Test edge cases for TimesFM sizing integration."""
    
    @pytest.fixture
    def agent_with_organ(self):
        """Create a KashClaw agent with a spot trading organ."""
        agent = KashClawSimpAgent(agent_id="test-agent")
        
        # Create a mock organ
        organ = Mock(spec=TradingOrgan)
        organ.organ_id = "test:spot:001"
        organ.organ_type = OrganType.SPOT_TRADING
        organ.validate_params = AsyncMock(return_value=True)
        organ.execute = AsyncMock()
        
        # Mock execution result
        execution_result = Mock()
        execution_result.to_dict.return_value = {
            "organ_id": "test:spot:001",
            "status": "completed",
            "executions": []
        }
        organ.execute.return_value = execution_result
        
        # Register organ
        agent.organs[organ.organ_id] = organ
        
        return agent
    
    async def test_zero_slippage_tolerance(self, agent_with_organ):
        """Test TimesFM sizing with zero slippage tolerance."""
        # Mock TimesFM for high volatility
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
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
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.0)
                    
                    # Get sizing advice with zero slippage tolerance
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="SOL/USDC",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.0,  # Zero slippage
                    )
                    
                    # Verify results
                    assert advice["original_slippage_tolerance"] == 0.0
                    assert advice["adjusted_slippage_tolerance"] >= 0.0  # Should be non-negative
                    assert not math.isnan(advice["adjusted_slippage_tolerance"])
                    assert not math.isinf(advice["adjusted_slippage_tolerance"])
                    
                    # Current volatility should use 0.0001 as minimum to avoid division by zero
                    # So forecast_vol (0.03+) > current_vol (0.0001) * 1.5 should trigger adjustment
                    if advice["timesfm_applied"]:
                        assert advice["adjusted_slippage_tolerance"] <= 0.05  # Capped at 5%
    
    async def test_high_original_slippage_tolerance(self, agent_with_organ):
        """Test TimesFM sizing with original slippage tolerance already at or above 5%."""
        # Mock TimesFM for high volatility
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17]  # Very high
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer with high values
                    for i in range(20):
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.06)
                    
                    # Get sizing advice with high original slippage
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="SOL/USDC",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.06,  # Already at 6%
                    )
                    
                    # Verify results
                    assert advice["original_slippage_tolerance"] == 0.06
                    assert advice["adjusted_slippage_tolerance"] <= 0.06  # Should not increase beyond original
                    assert advice["adjusted_slippage_tolerance"] <= 0.05  # Should be capped at 5%
                    
                    # Even with high forecast, slippage should not exceed cap
                    if advice["timesfm_applied"]:
                        assert advice["adjusted_slippage_tolerance"] == 0.05  # Capped at 5%
    
    async def test_negative_quantity_clamping(self, agent_with_organ):
        """Test that negative quantities are clamped to zero."""
        # Mock TimesFM (should not be called due to negative quantity handling)
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.02)
                    
                    # Get sizing advice with negative quantity
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="SOL/USDC",
                        organ_id="test:spot:001",
                        quantity=-5.0,  # Negative quantity
                        slippage_tolerance=0.02,
                    )
                    
                    # Verify clamping
                    assert advice["original_quantity"] == -5.0
                    assert advice["adjusted_quantity"] == 0.0  # Clamped to zero
                    assert advice["adjusted_quantity"] >= 0.0  # Non-negative
    
    async def test_mixed_nan_inf_forecast(self, agent_with_organ):
        """Test TimesFM sizing with forecast containing mixed NaN and inf values."""
        # Mock TimesFM with mixed valid/invalid forecast values
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks with mixed NaN/inf/valid values
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Mix of NaN, inf, and valid values
                    mock_response.point_forecast = [
                        float('nan'), 0.03, float('inf'), 0.04,
                        float('nan'), 0.05, 0.06, float('inf')
                    ]
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="SOL/USDC",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.02,
                    )
                    
                    # Verify handling
                    # Should filter out NaN/inf and use only valid values [0.03, 0.04, 0.05, 0.06]
                    # Average = 0.045, which is > 0.02 * 1.5 = 0.03, so should trigger adjustment
                    if len([f for f in mock_response.point_forecast 
                           if isinstance(f, (int, float)) and not math.isnan(f) and not math.isinf(f)]) > 0:
                        # If there are valid values, TimesFM might be applied
                        # Either applied or not, but should not crash
                        assert "timesfm_rationale" in advice
                        assert advice["adjusted_quantity"] >= 0.0
                        assert advice["adjusted_slippage_tolerance"] >= 0.0
                    else:
                        # No valid values - should fall back
                        assert not advice["timesfm_applied"]
                        assert "invalid values" in advice["timesfm_rationale"].lower() or \
                               "no forecast data" in advice["timesfm_rationale"].lower()
    
    async def test_extreme_volatility_forecast(self, agent_with_organ):
        """Test TimesFM sizing with extremely high volatility forecast."""
        # Mock TimesFM with extreme volatility forecast
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks with extreme volatility
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]  # Extreme
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="SOL/USDC",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.02,
                    )
                    
                    # Verify bounds are respected even with extreme forecast
                    if advice["timesfm_applied"]:
                        # Quantity reduction limited to 20%
                        assert advice["adjusted_quantity"] == 8.0  # 10.0 * 0.8
                        assert advice["adjusted_quantity"] >= 0.0
                        
                        # Slippage widening limited to 25% and capped at 5%
                        expected_slippage = min(0.02 * 1.25, 0.05)
                        assert advice["adjusted_slippage_tolerance"] == pytest.approx(expected_slippage, rel=1e-6)
                        assert advice["adjusted_slippage_tolerance"] <= 0.05
    
    async def test_trade_execution_with_edge_cases(self, agent_with_organ):
        """Test full trade execution with edge case parameters."""
        # Mock TimesFM
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
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
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.0)
                    
                    # Execute trade with edge case parameters
                    result = await agent_with_organ.handle_trade({
                        "organ_id": "test:spot:001",
                        "asset_pair": "SOL/USDC",
                        "side": "BUY",
                        "quantity": 0.001,  # Very small quantity
                        "price": 150.0,
                        "slippage_tolerance": 0.0,  # Zero slippage
                    })
                    
                    # Verify trade executed successfully
                    assert result["status"] == "success"
                    assert "timesfm_sizing" in result
                    assert "rationale" in result["timesfm_sizing"]
                    
                    # TimesFM sizing should be in response regardless of adjustments
                    assert result["timesfm_sizing"]["applied"] in [True, False]
                    
                    # Risk posture should be set
                    assert result["risk_posture"] in ["conservative", "neutral"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])