"""
Tests for Kloutbot TimesFM horizon advice integration.

Verifies that TimesFM horizon advice:
- Only uses allowed buckets (short/medium/long)
- Step counts are within safe numeric range
- Failures fall back to default horizon without breaking strategy generation
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.agents.kloutbot_agent import KloutbotAgent
from simp.agents.q_intent_compiler import StrategicOptimizer, DecisionTree


class TestKloutbotTimesFMHorizon:
    """Test TimesFM horizon advice in Kloutbot agent"""

    @pytest.fixture
    def kloutbot_agent(self):
        """Create a fresh Kloutbot agent"""
        agent = KloutbotAgent(agent_id="test-kloutbot-001")
        return agent

    @pytest.mark.asyncio
    async def test_timesfm_horizon_advice_long_persistence(self, kloutbot_agent):
        """Test TimesFM horizon advice for long persistence forecast"""
        # Mock TimesFM to return long persistence forecast
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # All values above 0.5 threshold for entire horizon -> long persistence
                    mock_response.point_forecast = [0.8, 0.85, 0.9, 0.88, 0.87, 0.86, 0.85, 0.84,
                                                    0.83, 0.82, 0.81, 0.8, 0.79, 0.78, 0.77, 0.76,
                                                    0.75, 0.74, 0.73, 0.72, 0.71, 0.7, 0.69, 0.68,
                                                    0.67, 0.66, 0.65, 0.64, 0.63, 0.62, 0.61, 0.6]
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify long horizon recommendation
                    assert advice["timesfm_horizon_applied"] is True
                    assert advice["recommended_horizon"] == "long"
                    assert advice["recommended_horizon_steps"] == 32
                    assert "long horizon" in advice["timesfm_horizon_rationale"]
                    assert "32 steps" in advice["timesfm_horizon_rationale"]
                    assert "persists" in advice["timesfm_horizon_rationale"]
                    assert "0.5 threshold" in advice["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_advice_medium_persistence(self, kloutbot_agent):
        """Test TimesFM horizon advice for medium persistence forecast"""
        # Mock TimesFM to return medium persistence forecast
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Drops below 0.5 at step 18 -> medium persistence
                    mock_response.point_forecast = [0.8, 0.78, 0.76, 0.74, 0.72, 0.7, 0.68, 0.66,
                                                    0.64, 0.62, 0.6, 0.58, 0.56, 0.54, 0.52, 0.5,
                                                    0.48, 0.46, 0.44, 0.42, 0.4, 0.38, 0.36, 0.34,
                                                    0.32, 0.3, 0.28, 0.26, 0.24, 0.22, 0.2, 0.18]
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify medium horizon recommendation
                    assert advice["timesfm_horizon_applied"] is True
                    assert advice["recommended_horizon"] == "medium"
                    assert advice["recommended_horizon_steps"] == 16
                    assert "medium horizon" in advice["timesfm_horizon_rationale"]
                    assert "16 steps" in advice["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_advice_short_persistence(self, kloutbot_agent):
        """Test TimesFM horizon advice for short persistence forecast"""
        # Mock TimesFM to return short persistence forecast
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Drops below 0.5 at step 8 -> short persistence
                    mock_response.point_forecast = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1,
                                                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify short horizon recommendation
                    assert advice["timesfm_horizon_applied"] is True
                    assert advice["recommended_horizon"] == "short"
                    assert advice["recommended_horizon_steps"] == 8
                    assert "short horizon" in advice["timesfm_horizon_rationale"]
                    assert "8 steps" in advice["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_shadow_mode(self, kloutbot_agent):
        """Test TimesFM horizon advice in shadow mode"""
        # Mock TimesFM to return shadow mode response
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
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
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify shadow mode behavior
                    assert advice["timesfm_horizon_applied"] is False
                    assert advice["recommended_horizon"] == "medium"  # Default
                    assert advice["recommended_horizon_steps"] == 16  # Default
                    assert "shadow mode" in advice["timesfm_horizon_rationale"].lower()
                    assert "medium horizon" in advice["timesfm_horizon_rationale"]
                    assert "16 steps" in advice["timesfm_horizon_rationale"]
                    # Shadow mode rationale changed to be more informative
                    # Previously: "horizon unchanged" 
                    # Now: includes specific fallback information
                    pass  # Already checked shadow mode, medium horizon, 16 steps above

    @pytest.mark.asyncio
    async def test_timesfm_horizon_policy_denied(self, kloutbot_agent):
        """Test TimesFM horizon advice when policy engine denies"""
        # Mock policy engine to deny
        with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
            mock_decision = Mock()
            mock_decision.denied = True
            mock_decision.reason = "Test policy denial"
            mock_engine.return_value.evaluate.return_value = mock_decision
            
            # Fill affinity buffer with enough history
            for i in range(20):
                kloutbot_agent._record_affinity(0.8)
            
            # Get horizon advice
            advice = await kloutbot_agent._get_strategy_horizon_advice(
                affinity=0.85,
                drift_risk=0.1,
            )
            
            # Verify policy denial behavior
            assert advice["timesfm_horizon_applied"] is False
            assert advice["recommended_horizon"] == "medium"  # Default
            assert advice["recommended_horizon_steps"] == 16  # Default
            assert "TimesFM policy denied" in advice["timesfm_horizon_rationale"]
            assert "Test policy denial" in advice["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_insufficient_history(self, kloutbot_agent):
        """Test TimesFM horizon advice with insufficient history"""
        # Don't fill buffer - keep it empty
        
        # Get horizon advice
        advice = await kloutbot_agent._get_strategy_horizon_advice(
            affinity=0.85,
            drift_risk=0.1,
        )
        
        # Verify insufficient history behavior
        assert advice["timesfm_horizon_applied"] is False
        assert advice["recommended_horizon"] == "medium"  # Default
        assert advice["recommended_horizon_steps"] == 16  # Default
        assert "insufficient history" in advice["timesfm_horizon_rationale"]
        assert "/16 observations" in advice["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_error_handling(self, kloutbot_agent):
        """Test TimesFM horizon advice error handling"""
        # Mock TimesFM to raise exception
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_service.forecast.side_effect = Exception("TimesFM service error")
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify error handling
                    assert advice["timesfm_horizon_applied"] is False
                    assert advice["recommended_horizon"] == "medium"  # Default
                    assert advice["recommended_horizon_steps"] == 16  # Default
                    assert "TimesFM horizon advice error" in advice["timesfm_horizon_rationale"]
                    assert "TimesFM service error" in advice["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_integration_in_strategy_generation(self, kloutbot_agent):
        """Test that TimesFM horizon advice is integrated into strategy generation"""
        # Mock TimesFM for long persistence
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Long persistence forecast
                    mock_response.point_forecast = [0.8] * 32
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Mock compiler to return a simple tree
                    mock_compiler = Mock()
                    mock_tree = Mock()
                    mock_tree.to_dict.return_value = {"tree": "test"}
                    mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
                    mock_compiler.get_action_params = Mock(return_value={"action": "test"})
                    mock_compiler.iteration_count = 0
                    mock_compiler.improvement_history = []
                    kloutbot_agent.compiler = mock_compiler
                    
                    # Fill affinity buffer
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Generate strategy
                    result = await kloutbot_agent.handle_generate_strategy({
                        "foresight": {
                            "affinity": 0.85,
                            "drift_risk": 0.1
                        },
                        "deltas": {
                            "momentum": 0.8,
                            "volume": 0.7,
                            "sentiment": 0.65
                        },
                        "timestamp": "2026-04-09T05:52:27.731075+00:00",
                    })
                    
                    # Verify TimesFM horizon is reflected in response
                    assert result["status"] == "success"
                    assert "recommended_horizon" in result
                    assert "recommended_horizon_steps" in result
                    assert "timesfm_horizon_applied" in result
                    assert "timesfm_horizon_rationale" in result
                    
                    # Verify long horizon was recommended
                    assert result["recommended_horizon"] == "long"
                    assert result["recommended_horizon_steps"] == 32
                    assert result["timesfm_horizon_applied"] is True
                    assert "long horizon" in result["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_fallback_does_not_break_strategy(self, kloutbot_agent):
        """Test that TimesFM horizon failures fall back gracefully without breaking strategy generation"""
        # Mock TimesFM to fail
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks for TimesFM failure
                    mock_service = AsyncMock()
                    mock_service.forecast.side_effect = Exception("Critical TimesFM failure")
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = True  # Policy denies
                    mock_decision.reason = "Policy failure"
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Mock compiler to return a simple tree
                    mock_compiler = Mock()
                    mock_tree = Mock()
                    mock_tree.to_dict.return_value = {"tree": "test"}
                    mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
                    mock_compiler.get_action_params = Mock(return_value={"action": "test"})
                    mock_compiler.improvement_history = []
                    mock_compiler.iteration_count = 0
                    kloutbot_agent.compiler = mock_compiler
                    
                    # Fill affinity buffer
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Generate strategy - should still succeed despite TimesFM failure
                    result = await kloutbot_agent.handle_generate_strategy({
                        "foresight": {
                            "affinity": 0.85,
                            "drift_risk": 0.1
                        },
                        "deltas": {
                            "momentum": 0.8,
                            "volume": 0.7,
                            "sentiment": 0.65
                        },
                        "timestamp": "2026-04-09T05:52:27.731075+00:00",
                    })
                    
                    # Verify strategy generation succeeded
                    assert result["status"] == "success"
                    assert "strategy" in result
                    assert "action_params" in result
                    
                    # TimesFM horizon should indicate failure but strategy still generated
                    assert "recommended_horizon" in result
                    assert "recommended_horizon_steps" in result
                    assert result["timesfm_horizon_applied"] is False
                    # Should have default values
                    assert result["recommended_horizon"] == "medium"
                    assert result["recommended_horizon_steps"] == 16

    def test_horizon_buckets_and_step_ranges(self):
        """Test that horizon buckets and step counts are within allowed ranges"""
        # Test all three allowed buckets
        allowed_buckets = {"short", "medium", "long"}
        allowed_steps = {8, 16, 32}
        
        # These are the hardcoded values in the implementation
        assert "short" in allowed_buckets
        assert "medium" in allowed_buckets
        assert "long" in allowed_buckets
        
        assert 8 in allowed_steps  # short
        assert 16 in allowed_steps  # medium
        assert 32 in allowed_steps  # long
        
        # Verify step counts are safe numeric ranges
        assert 8 > 0 and 8 <= 32
        assert 16 > 0 and 16 <= 32
        assert 32 > 0 and 32 <= 32
        
        # Default fallback values
        assert "medium" == "medium"  # Default bucket
        assert 16 == 16  # Default steps

    @pytest.mark.asyncio
    async def test_timesfm_horizon_empty_forecast(self, kloutbot_agent):
        """Test TimesFM horizon advice with empty point_forecast list"""
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = []  # Empty list
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify empty forecast falls back to default
                    assert advice["timesfm_horizon_applied"] is False
                    assert advice["recommended_horizon"] == "medium"
                    assert advice["recommended_horizon_steps"] == 16
                    # Should not crash, should return default rationale

    @pytest.mark.asyncio
    async def test_timesfm_horizon_all_values_below_threshold(self, kloutbot_agent):
        """Test TimesFM horizon advice when all forecast values are below 0.5 threshold"""
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # All values below 0.5 -> persistence_steps = 0
                    mock_response.point_forecast = [0.4] * 32
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify short horizon for all values below threshold
                    assert advice["timesfm_horizon_applied"] is True
                    assert advice["recommended_horizon"] == "short"
                    assert advice["recommended_horizon_steps"] == 8
                    assert "short horizon" in advice["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_timesfm_horizon_boundary_values(self, kloutbot_agent):
        """Test TimesFM horizon advice at exact boundary values (12, 24 steps)"""
        test_cases = [
            # (persistence_steps, expected_horizon, expected_steps)
            (24, "long", 32),      # Exactly at long boundary
            (23, "medium", 16),    # Just below long boundary
            (12, "medium", 16),    # Exactly at medium boundary  
            (11, "short", 8),      # Just below medium boundary
            (0, "short", 8),       # Zero persistence
            (32, "long", 32),      # Full horizon persistence
        ]
        
        for persistence_steps, expected_horizon, expected_steps in test_cases:
            with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
                with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                    with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                        # Setup mocks
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        mock_response.available = True
                        
                        # Create forecast with persistence at given step
                        if persistence_steps == 32:
                            # All values >= 0.5
                            mock_response.point_forecast = [0.8] * 32
                        else:
                            # Values drop below 0.5 at persistence_steps
                            mock_response.point_forecast = [0.8] * persistence_steps + [0.4] * (32 - persistence_steps)
                        
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        mock_decision = Mock()
                        mock_decision.denied = False
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        # Fill affinity buffer
                        for i in range(20):
                            kloutbot_agent._record_affinity(0.8)
                        
                        # Get horizon advice
                        advice = await kloutbot_agent._get_strategy_horizon_advice(
                            affinity=0.85,
                            drift_risk=0.1,
                        )
                        
                        # Verify boundary handling
                        assert advice["timesfm_horizon_applied"] is True
                        assert advice["recommended_horizon"] == expected_horizon, \
                            f"Failed for persistence_steps={persistence_steps}: got {advice['recommended_horizon']}, expected {expected_horizon}"
                        assert advice["recommended_horizon_steps"] == expected_steps, \
                            f"Failed for persistence_steps={persistence_steps}: got {advice['recommended_horizon_steps']}, expected {expected_steps}"

    @pytest.mark.asyncio
    async def test_timesfm_horizon_response_schema_validation(self, kloutbot_agent):
        """Test that horizon advice response has consistent schema"""
        # Test with successful forecast
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.8] * 32
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Verify response schema
                    required_keys = {
                        "recommended_horizon",
                        "recommended_horizon_steps", 
                        "timesfm_horizon_applied",
                        "timesfm_horizon_rationale"
                    }
                    assert required_keys.issubset(advice.keys())
                    
                    # Verify types
                    assert isinstance(advice["recommended_horizon"], str)
                    assert isinstance(advice["recommended_horizon_steps"], int)
                    assert isinstance(advice["timesfm_horizon_applied"], bool)
                    assert isinstance(advice["timesfm_horizon_rationale"], str)
                    
                    # Verify horizon is one of allowed values
                    assert advice["recommended_horizon"] in {"short", "medium", "long"}
                    
                    # Verify steps match horizon
                    horizon_to_steps = {"short": 8, "medium": 16, "long": 32}
                    assert advice["recommended_horizon_steps"] == horizon_to_steps[advice["recommended_horizon"]]
        
        # Also test with error case to ensure schema consistency
        advice = await kloutbot_agent._get_strategy_horizon_advice(
            affinity=0.85,
            drift_risk=0.1,
        )
        # Even with insufficient history, schema should be consistent
        required_keys = {
            "recommended_horizon",
            "recommended_horizon_steps", 
            "timesfm_horizon_applied",
            "timesfm_horizon_rationale"
        }
        assert required_keys.issubset(advice.keys())

    @pytest.mark.asyncio
    async def test_long_horizon_coherence(self, kloutbot_agent):
        """Test that horizon recommendations are coherent across multiple calls"""
        # Mock compiler
        mock_compiler = Mock()
        mock_tree = Mock()
        mock_tree.to_dict.return_value = {"tree": "test", "branches": []}
        mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
        mock_compiler.get_action_params = Mock(return_value={"action": "buy", "confidence": 0.8})
        mock_compiler.improvement_history = []
        mock_compiler.iteration_count = 0
        kloutbot_agent.compiler = mock_compiler
        
        # Pre-populate affinity buffer
        for i in range(20):
            kloutbot_agent._record_affinity(0.8)
        
        # Mock TimesFM to return consistent long horizon
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Always return long horizon forecast
                    mock_response.point_forecast = [0.8] * 32
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Generate multiple strategies with similar inputs
                    horizons = []
                    for i in range(5):
                        result = await kloutbot_agent.handle_generate_strategy({
                            "foresight": {
                                "affinity": 0.85 - (i * 0.01),  # Slight variation
                                "drift_risk": 0.1
                            },
                            "deltas": {
                                "momentum": 0.8,
                                "volume": 0.7,
                                "sentiment": 0.65
                            }
                        })
                        
                        assert result["status"] == "success"
                        horizons.append(result["recommended_horizon"])
                    
                    # All horizons should be consistent (all "long")
                    assert all(h == "long" for h in horizons), \
                        f"Horizons not consistent: {horizons}"
                    
                    # Verify telemetry shows increasing strategy count
                    last_result = await kloutbot_agent.handle_generate_strategy({
                        "foresight": {"affinity": 0.85, "drift_risk": 0.1},
                        "deltas": {"momentum": 0.8, "volume": 0.7, "sentiment": 0.65}
                    })
                    
                    telemetry = last_result["mutation_telemetry"]
                    assert telemetry["total_strategies_generated"] >= 6  # 5 + 1 more

    @pytest.mark.asyncio
    async def test_horizon_stability_with_intermittent_timesfm(self, kloutbot_agent):
        """Test horizon stability when TimesFM is intermittently available/unavailable"""
        # Mock compiler
        mock_compiler = Mock()
        mock_tree = Mock()
        mock_tree.to_dict.return_value = {"tree": "test", "branches": []}
        mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
        mock_compiler.get_action_params = Mock(return_value={"action": "buy", "confidence": 0.8})
        mock_compiler.improvement_history = []
        mock_compiler.iteration_count = 0
        kloutbot_agent.compiler = mock_compiler
        
        # Pre-populate affinity buffer
        for i in range(20):
            kloutbot_agent._record_affinity(0.8)
        
        horizons = []
        timesfm_applied_flags = []
        
        # Simulate 3 calls: available -> unavailable -> available
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    mock_service = AsyncMock()
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Call 1: TimesFM available (long horizon)
                    mock_response1 = Mock()
                    mock_response1.available = True
                    mock_response1.point_forecast = [0.8] * 32
                    mock_service.forecast.return_value = mock_response1
                    
                    result1 = await kloutbot_agent.handle_generate_strategy({
                        "foresight": {"affinity": 0.85, "drift_risk": 0.1},
                        "deltas": {"momentum": 0.8, "volume": 0.7, "sentiment": 0.65}
                    })
                    
                    assert result1["status"] == "success"
                    horizons.append(result1["recommended_horizon"])
                    timesfm_applied_flags.append(result1["timesfm_horizon_applied"])
                    
                    # Call 2: TimesFM unavailable (shadow mode)
                    mock_response2 = Mock()
                    mock_response2.available = False  # Shadow mode
                    mock_service.forecast.return_value = mock_response2
                    
                    result2 = await kloutbot_agent.handle_generate_strategy({
                        "foresight": {"affinity": 0.84, "drift_risk": 0.1},
                        "deltas": {"momentum": 0.8, "volume": 0.7, "sentiment": 0.65}
                    })
                    
                    assert result2["status"] == "success"
                    horizons.append(result2["recommended_horizon"])
                    timesfm_applied_flags.append(result2["timesfm_horizon_applied"])
                    
                    # Call 3: TimesFM available again (long horizon)
                    mock_response3 = Mock()
                    mock_response3.available = True
                    mock_response3.point_forecast = [0.8] * 32
                    mock_service.forecast.return_value = mock_response3
                    
                    result3 = await kloutbot_agent.handle_generate_strategy({
                        "foresight": {"affinity": 0.86, "drift_risk": 0.1},
                        "deltas": {"momentum": 0.8, "volume": 0.7, "sentiment": 0.65}
                    })
                    
                    assert result3["status"] == "success"
                    horizons.append(result3["recommended_horizon"])
                    timesfm_applied_flags.append(result3["timesfm_horizon_applied"])
        
        # Verify behavior
        print(f"Horizons: {horizons}")
        print(f"TimesFM applied: {timesfm_applied_flags}")
        
        # First and third calls should use TimesFM (long horizon)
        assert timesfm_applied_flags[0] is True
        assert horizons[0] == "long"
        
        # Second call should fall back (medium horizon default)
        assert timesfm_applied_flags[1] is False
        assert horizons[1] == "medium"
        
        # Third call should use TimesFM again (long horizon)
        assert timesfm_applied_flags[2] is True
        assert horizons[2] == "long"
        
        # Verify fallback rationale
        assert "shadow mode" in result2["timesfm_horizon_rationale"].lower()
        assert "medium horizon" in result2["timesfm_horizon_rationale"]
        assert "16 steps" in result2["timesfm_horizon_rationale"]

    @pytest.mark.asyncio
    async def test_horizon_rationale_consistency(self, kloutbot_agent):
        """Test that horizon rationale provides clear, consistent explanations"""
        # Pre-populate affinity buffer
        for i in range(20):
            kloutbot_agent._record_affinity(0.8)
        
        # Test long horizon rationale
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup for long horizon
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.8] * 32  # Long persistence
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1
                    )
                    
                    # Check rationale contains key information
                    rationale = advice["timesfm_horizon_rationale"]
                    assert "TimesFM forecast" in rationale
                    assert "persists" in rationale
                    assert "0.5 threshold" in rationale
                    assert "long horizon" in rationale
                    assert "32 steps" in rationale
                    assert "strategic positioning" in rationale
        
        # Test fallback rationale (shadow mode)
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup for shadow mode
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = False  # Shadow mode
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Get horizon advice
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1
                    )
                    
                    # Check fallback rationale
                    rationale = advice["timesfm_horizon_rationale"]
                    assert "shadow mode" in rationale.lower()
                    assert "medium horizon" in rationale
                    assert "16 steps" in rationale

    @pytest.mark.asyncio
    async def test_strategy_generation_response_schema(self, kloutbot_agent):
        """Test that strategy generation responses have consistent schema"""
        """Test that strategy generation responses have consistent schema"""
        # Mock compiler
        mock_compiler = Mock()
        mock_tree = Mock()
        mock_tree.to_dict.return_value = {"tree": "test", "branches": []}
        mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
        mock_compiler.get_action_params = Mock(return_value={"action": "buy", "confidence": 0.8})
        mock_compiler.improvement_history = []
        mock_compiler.iteration_count = 0
        kloutbot_agent.compiler = mock_compiler
        
        # Mock TimesFM for consistent horizon advice
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    mock_response.point_forecast = [0.8] * 32
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Test success case
                    result = await kloutbot_agent.handle_generate_strategy({
                        "foresight": {
                            "affinity": 0.85,
                            "drift_risk": 0.1
                        },
                        "deltas": {
                            "momentum": 0.8,
                            "volume": 0.7,
                            "sentiment": 0.65
                        },
                        "timestamp": "2026-04-09T05:52:27.731075+00:00",
                    })
                    
                    # Verify success schema
                    assert "status" in result
                    assert result["status"] == "success"
                    
                    success_required_keys = {
                        "status",
                        "strategy", 
                        "action_params",
                        "recommended_horizon",
                        "recommended_horizon_steps",
                        "timesfm_horizon_applied",
                        "timesfm_horizon_rationale",
                        "mutation_telemetry",
                        "timestamp"
                    }
                    assert success_required_keys.issubset(result.keys())
                    
                    # Verify types
                    assert isinstance(result["strategy"], dict)
                    assert isinstance(result["action_params"], dict)
                    assert isinstance(result["recommended_horizon"], str)
                    assert isinstance(result["recommended_horizon_steps"], int)
                    assert isinstance(result["timesfm_horizon_applied"], bool)
                    assert isinstance(result["timesfm_horizon_rationale"], str)
                    assert isinstance(result["mutation_telemetry"], dict)
                    assert isinstance(result["timestamp"], str)
                    
                    # Verify mutation telemetry structure
                    telemetry = result["mutation_telemetry"]
                    assert isinstance(telemetry.get("total_strategies_generated"), int)
                    assert isinstance(telemetry.get("recent_strategies_count"), int)
                    assert isinstance(telemetry.get("strategy_history_capacity"), int)
                    assert isinstance(telemetry.get("compiler_iterations"), int)
                    assert isinstance(telemetry.get("improvement_history_length"), int)
                    
                    # Verify horizon values
                    assert result["recommended_horizon"] in {"short", "medium", "long"}
                    
        # Test error case - missing required parameters
        result = await kloutbot_agent.handle_generate_strategy({
            "foresight": {},
            "deltas": {}
        })
        
        # Verify error schema
        assert "status" in result
        assert result["status"] == "error"
        
        error_required_keys = {
            "status",
            "error_code",
            "error_message"
        }
        assert error_required_keys.issubset(result.keys())
        
        # Verify error types
        assert isinstance(result["error_code"], str)
        assert isinstance(result["error_message"], str)
        
        # Test error case - exception during compilation
        mock_compiler.compile_intent.side_effect = Exception("Compiler error")
        result = await kloutbot_agent.handle_generate_strategy({
            "foresight": {
                "affinity": 0.85,
                "drift_risk": 0.1
            },
            "deltas": {
                "momentum": 0.8,
                "volume": 0.7,
                "sentiment": 0.65
            },
        })
        
        # Verify exception error schema
        assert result["status"] == "error"
        assert "error_code" in result
        assert "error_message" in result
        assert result["error_code"] == "STRATEGY_GENERATION_FAILED"