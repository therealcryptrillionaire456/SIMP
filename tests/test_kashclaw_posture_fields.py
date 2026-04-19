"""
Tests for KashClaw posture fields and A2A readiness.

Tests that KashClaw response structures include:
- advisory risk posture tags
- explicit TimesFM involvement flags
- A2A-ready summary data
"""

import asyncio
import pytest
import sys
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.integrations.kashclaw_shim import KashClawSimpAgent
from simp.organs.spot_trading_organ import SpotTradingOrgan


class TestKashClawPostureFields:
    """Tests for KashClaw posture fields and A2A readiness"""

    @pytest.fixture
    def agent_with_organ(self):
        """Create a fresh agent with registered organ"""
        agent = KashClawSimpAgent(agent_id="test-agent-posture-001")
        organ = SpotTradingOrgan(organ_id="test:spot:posture:001", initial_balance=10000.0)
        agent.register_organ(organ)
        return agent

    @pytest.mark.asyncio
    async def test_response_structure_has_posture_fields(self, agent_with_organ):
        """Test that trade responses include posture fields"""
        # Mock TimesFM for high volatility
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
                        agent_with_organ._record_volatility("SOL/USDC:test:spot:posture:001:volatility", 0.02)
                    
                    # Execute trade
                    result = await agent_with_organ.handle_trade({
                        "organ_id": "test:spot:posture:001",
                        "asset_pair": "SOL/USDC",
                        "side": "BUY",
                        "quantity": 10.0,
                        "price": 150.0,
                        "slippage_tolerance": 0.02,
                    })
                    
                    # Check basic response structure
                    assert result["status"] == "success"
                    assert "execution" in result
                    assert "timestamp" in result
                    assert "timesfm_sizing" in result
                    
                    # Check TimesFM sizing fields
                    timesfm_sizing = result["timesfm_sizing"]
                    assert "applied" in timesfm_sizing
                    assert "rationale" in timesfm_sizing
                    assert "risk_posture" in timesfm_sizing
                    
                    # Check top-level posture fields
                    assert "risk_posture" in result
                    assert result["risk_posture"] in ["conservative", "neutral", "aggressive"]

    @pytest.mark.asyncio
    async def test_sizing_advice_structure(self, agent_with_organ):
        """Test that sizing advice includes all necessary fields"""
        # Mock TimesFM for stable volatility
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.02] * 8  # Stable forecast
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("BTC/USD:test:spot:posture:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="BTC/USD",
                        organ_id="test:spot:posture:001",
                        quantity=5.0,
                        slippage_tolerance=0.01,
                    )
                    
                    # Check required fields exist
                    required_fields = [
                        "original_quantity",
                        "original_slippage_tolerance",
                        "adjusted_quantity",
                        "adjusted_slippage_tolerance", 
                        "timesfm_applied",
                        "timesfm_rationale",
                        "risk_posture"
                    ]
                    
                    for field in required_fields:
                        assert field in advice, f"Missing field: {field}"
                    
                    # Check risk posture is valid
                    assert advice["risk_posture"] in ["conservative", "neutral", "aggressive"]

    @pytest.mark.asyncio
    async def test_shadow_mode_posture_fields(self, agent_with_organ):
        """Test posture fields when TimesFM is in shadow mode"""
        # Mock TimesFM shadow mode
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
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
                    
                    # Fill volatility buffer
                    for i in range(20):
                        agent_with_organ._record_volatility("ETH/USD:test:spot:posture:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="ETH/USD",
                        organ_id="test:spot:posture:001",
                        quantity=3.0,
                        slippage_tolerance=0.015,
                    )
                    
                    # Check shadow mode behavior
                    assert advice["timesfm_applied"] is False
                    assert "shadow mode" in advice["timesfm_rationale"].lower()
                    
                    # Check default posture in shadow mode
                    assert advice["risk_posture"] == "neutral"

    @pytest.mark.asyncio
    async def test_policy_denied_posture_fields(self, agent_with_organ):
        """Test posture fields when TimesFM policy denies sizing"""
        # Mock policy denied
        with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
            mock_decision = Mock()
            mock_decision.denied = True
            mock_decision.reason = "insufficient_trust_score"
            mock_engine.return_value.evaluate.return_value = mock_decision
            
            # Fill volatility buffer
            for i in range(20):
                agent_with_organ._record_volatility("XRP/USD:test:spot:posture:001:volatility", 0.02)
            
            # Get sizing advice
            advice = await agent_with_organ._get_pre_trade_sizing_advice(
                asset_pair="XRP/USD",
                organ_id="test:spot:posture:001",
                quantity=100.0,
                slippage_tolerance=0.02,
            )
            
            # Check policy denied behavior
            assert advice["timesfm_applied"] is False
            assert "policy denied" in advice["timesfm_rationale"].lower()
            
            # Check default posture when policy denied
            assert advice["risk_posture"] == "conservative"

    @pytest.mark.asyncio
    async def test_high_volatility_posture(self, agent_with_organ):
        """Test that high volatility triggers conservative posture"""
        # Mock TimesFM for very high volatility
        with patch('simp.integrations.kashclaw_shim.get_timesfm_service') as mock_svc:
            with patch('simp.integrations.kashclaw_shim.make_agent_context_for'):
                with patch('simp.integrations.kashclaw_shim.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.10] * 8  # Very high volatility
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill volatility buffer with normal volatility
                    for i in range(20):
                        agent_with_organ._record_volatility("DOGE/USD:test:spot:posture:001:volatility", 0.02)
                    
                    # Get sizing advice
                    advice = await agent_with_organ._get_pre_trade_sizing_advice(
                        asset_pair="DOGE/USD",
                        organ_id="test:spot:posture:001",
                        quantity=1000.0,
                        slippage_tolerance=0.02,
                    )
                    
                    # Check high volatility triggers adjustments
                    assert advice["timesfm_applied"] is True
                    assert advice["adjusted_quantity"] < 1000.0  # Quantity reduced
                    assert advice["adjusted_slippage_tolerance"] > 0.02  # Slippage increased
                    
                    # Check that high volatility gets conservative posture
                    assert advice["risk_posture"] == "conservative"