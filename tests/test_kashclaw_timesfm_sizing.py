"""
Tests for KashClaw TimesFM sizing advice integration.

Verifies that TimesFM sizing advice:
- Never blocks execution
- Only adjusts size/slippage
- Is reflected in response fields
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.integrations.kashclaw_shim import KashClawSimpAgent
from simp.organs.spot_trading_organ import SpotTradingOrgan
from simp.integrations.trading_organ import OrganType


class TestKashClawTimesFMSizing:
    """Test TimesFM sizing advice in KashClaw integration"""

    @pytest.fixture
    def agent_with_organ(self):
        """Create a fresh agent with registered organ"""
        agent = KashClawSimpAgent(agent_id="test-agent-001")
        organ = SpotTradingOrgan(organ_id="test:spot:001", initial_balance=5000.0)
        agent.register_organ(organ)
        return agent

    @pytest.mark.asyncio
    async def test_timesfm_sizing_advice_high_volatility(self, agent_with_organ):
        """Test TimesFM sizing advice for high volatility forecast"""
        # Mock TimesFM to return high volatility forecast
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06, 0.065]  # High volatility
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer with enough history
                    for i in range(20):
                        agent_with_organ._record_volatility("BTC/USD:test:spot:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="BTC/USD",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.02,
                    )
                    
                    # Verify TimesFM applied adjustments for high volatility
                    assert advice["timesfm_applied"] is True
                    assert advice["adjusted_quantity"] == 8.0  # 20% reduction
                    assert advice["adjusted_slippage_tolerance"] == 0.025  # 25% increase
                    assert "TimesFM volatility rising" in advice["timesfm_rationale"]
                    assert "forecast_vol=" in advice["timesfm_rationale"]
                    assert "Reduced qty by 20%" in advice["timesfm_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_sizing_advice_normal_volatility(self, agent_with_organ):
        """Test TimesFM sizing advice for normal volatility forecast"""
        # Mock TimesFM to return normal volatility forecast
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.019, 0.02, 0.021, 0.02, 0.019, 0.02, 0.021, 0.02]  # Normal volatility
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer with enough history
                    for i in range(20):
                        agent_with_organ._record_volatility("BTC/USD:test:spot:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="BTC/USD",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.02,
                    )
                    
                    # Verify TimesFM did NOT apply adjustments for normal volatility
                    assert advice["timesfm_applied"] is False
                    assert advice["adjusted_quantity"] == 10.0  # No change
                    assert advice["adjusted_slippage_tolerance"] == 0.02  # No change
                    assert "stable volatility forecast" in advice["timesfm_rationale"]
                    assert "Sizing unchanged" in advice["timesfm_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_sizing_shadow_mode(self, agent_with_organ):
        """Test TimesFM sizing advice in shadow mode"""
        # Mock TimesFM to return shadow mode response
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = False  # Shadow mode
                    mock_response.point_forecast = None
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer with enough history
                    for i in range(20):
                        agent_with_organ._record_volatility("BTC/USD:test:spot:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="BTC/USD",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.02,
                    )
                    
                    # Verify shadow mode behavior
                    assert advice["timesfm_applied"] is False
                    assert advice["adjusted_quantity"] == 10.0  # No change
                    assert advice["adjusted_slippage_tolerance"] == 0.02  # No change
                    assert "shadow mode active" in advice["timesfm_rationale"]
                    assert "sizing unchanged" in advice["timesfm_rationale"].lower()

    @pytest.mark.asyncio
    async def test_timesfm_sizing_policy_denied(self, agent_with_organ):
        """Test TimesFM sizing advice when policy engine denies"""
        # Mock policy engine to deny
        with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
            mock_decision = Mock()
            mock_decision.denied = True
            mock_decision.reason = "Test policy denial"
            mock_engine.return_value.evaluate.return_value = mock_decision
            
            # Fill volatility buffer with enough history
            for i in range(20):
                agent_with_organ._record_volatility("BTC/USD:test:spot:001:volatility", 0.02)
            
            # Get sizing advice
            advice = await agent_with_organ._get_pre_trade_sizing_advice(
                asset_pair="BTC/USD",
                organ_id="test:spot:001",
                quantity=10.0,
                slippage_tolerance=0.02,
            )
            
            # Verify policy denial behavior
            assert advice["timesfm_applied"] is False
            assert advice["adjusted_quantity"] == 10.0  # No change
            assert advice["adjusted_slippage_tolerance"] == 0.02  # No change
            assert "TimesFM policy denied" in advice["timesfm_rationale"]
            assert "Test policy denial" in advice["timesfm_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_sizing_insufficient_history(self, agent_with_organ):
        """Test TimesFM sizing advice with insufficient history"""
        # Don't fill buffer - keep it empty
        
        # Get sizing advice
        advice = await agent_with_organ._get_pre_trade_sizing_advice(
            asset_pair="BTC/USD",
            organ_id="test:spot:001",
            quantity=10.0,
            slippage_tolerance=0.02,
        )
        
        # Verify insufficient history behavior
        assert advice["timesfm_applied"] is False
        assert advice["adjusted_quantity"] == 10.0  # No change
        assert advice["adjusted_slippage_tolerance"] == 0.02  # No change
        assert "insufficient history" in advice["timesfm_rationale"]
        assert "/16 observations" in advice["timesfm_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_sizing_integration_in_trade_execution(self, agent_with_organ):
        """Test that TimesFM sizing advice is integrated into trade execution flow"""
        # Mock TimesFM for high volatility
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06, 0.065]  # High volatility
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.02)
                    
                    # Execute trade
                    result = await agent_with_organ.handle_trade({
                        "organ_id": "test:spot:001",
                        "asset_pair": "SOL/USDC",
                        "side": "BUY",
                        "quantity": 10.0,
                        "price": 150.0,
                        "slippage_tolerance": 0.02,
                    })
                    
                    # Verify TimesFM sizing is reflected in response
                    assert result["status"] == "success"
                    assert "timesfm_sizing" in result
                    assert result["timesfm_sizing"]["applied"] is True
                    assert "TimesFM volatility rising" in result["timesfm_sizing"]["rationale"]
                    
                    # Verify execution succeeded despite TimesFM adjustments
                    assert "execution" in result
                    assert result["execution"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_timesfm_sizing_error_handling(self, agent_with_organ):
        """Test TimesFM sizing advice error handling"""
        # Mock TimesFM to raise exception
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_service.forecast.side_effect = Exception("TimesFM service error")
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("BTC/USD:test:spot:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="BTC/USD",
                        organ_id="test:spot:001",
                        quantity=10.0,
                        slippage_tolerance=0.02,
                    )
                    
                    # Verify error handling
                    assert advice["timesfm_applied"] is False
                    assert advice["adjusted_quantity"] == 10.0  # No change
                    assert advice["adjusted_slippage_tolerance"] == 0.02  # No change
                    assert "TimesFM sizing advice error" in advice["timesfm_rationale"]
                    assert "TimesFM service error" in advice["timesfm_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_sizing_never_blocks_execution(self, agent_with_organ):
        """Test that TimesFM sizing advice never blocks trade execution"""
        # Mock TimesFM to have various issues
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for') as mock_ctx:
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks to simulate TimesFM failure
                    mock_service = AsyncMock()
                    mock_service.forecast.side_effect = Exception("Critical TimesFM failure")
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = True  # Policy denies
                    mock_decision.reason = "Policy failure"
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:001:volatility", 0.02)
                    
                    # Execute trade - should still succeed despite TimesFM issues
                    result = await agent_with_organ.handle_trade({
                        "organ_id": "test:spot:001",
                        "asset_pair": "SOL/USDC",
                        "side": "BUY",
                        "quantity": 10.0,
                        "price": 150.0,
                        "slippage_tolerance": 0.02,
                    })
                    
                    # Verify trade executed successfully
                    assert result["status"] == "success"
                    assert "execution" in result
                    assert result["execution"]["status"] == "completed"
                    
                    # TimesFM sizing should indicate failure but not block
                    assert "timesfm_sizing" in result
                    assert result["timesfm_sizing"]["applied"] is False
                    # Rationale should contain error info but execution proceeded