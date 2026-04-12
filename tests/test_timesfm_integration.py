"""
Integration tests for TimesFM service and policy engine.
Tests the actual integration pattern used by agents.
"""
import asyncio
import numpy as np
from unittest.mock import Mock, patch, AsyncMock
import pytest

from simp.integrations.timesfm_service import (
    TimesFMService,
    ForecastRequest,
    ForecastResponse,
    get_timesfm_service,
)
from simp.integrations.timesfm_policy_engine import (
    AgentContext,
    PolicyDecision,
    PolicyEngine,
    make_agent_context_for,
)


class TestTimesFMIntegration:
    """Integration tests for TimesFM service and policy engine."""
    
    @pytest.mark.asyncio
    async def test_agent_integration_pattern(self):
        """Test the integration pattern used by agents (e.g., quantumarb)."""
        # This test simulates what quantumarb_agent.py does
        
        # 1. Agent creates context using policy engine helper
        context = make_agent_context_for(
            agent_id="quantumarb",
            series_id="btc:usd:coinbase_vs_binance:spread_bps",
            series_length=100,
            requesting_handler="handle_trade",
        )
        
        # 2. Agent evaluates policy
        engine = PolicyEngine()
        policy_decision = engine.evaluate(context)
        
        # Policy should allow quantumarb (has q3_shadow_confirmed=True)
        assert policy_decision.approved is True
        # quantumarb has q3_shadow_confirmed=True in assessments
        
        # 3. Agent calls TimesFM service (in shadow mode)
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            import importlib
            import simp.integrations.timesfm_service as service_module
            importlib.reload(service_module)
            service_module._SERVICE_SINGLETON = None
            
            service = service_module.get_timesfm_service_sync()
            
            # Mock model
            mock_model = Mock()
            # Create realistic numpy arrays that TimesFM would return
            horizon = 7
            point_forecasts = np.random.randn(1, horizon).astype(np.float32)
            quantile_forecasts = np.random.randn(1, horizon, 9).astype(np.float32)
            mock_model.forecast = Mock(return_value=(point_forecasts, quantile_forecasts))
            service._model = mock_model
            
            # 4. Agent creates forecast request
            request = ForecastRequest(
                series_id=context.series_id,
                values=[float(i % 10) for i in range(100)],  # Sample data
                frequency="D",
                horizon=horizon,
                requesting_agent=context.agent_id,
            )
            
            # 5. Agent calls forecast
            response = await service.forecast(request)
            
            # Verify shadow mode behavior
            assert response.shadow_mode is True
            assert response.available is False  # Shadow mode suppresses availability
            assert len(response.point_forecast) == horizon
            assert len(response.lower_bound) == horizon
            assert len(response.upper_bound) == horizon
    
    @pytest.mark.asyncio
    async def test_policy_denial_integration(self):
        """Test integration when policy denies request."""
        # Simulate new agent without shadow confirmation
        context = make_agent_context_for(
            agent_id="new_agent",  # Not in assessments
            series_id="test:series:1",
            series_length=100,
            requesting_handler="handle_trade",
        )
        
        engine = PolicyEngine()
        policy_decision = engine.evaluate(context)
        
        # Policy should deny new_agent (q1_utility_score=1, q3_shadow_confirmed=False)
        assert policy_decision.approved is False
        assert "Q1_UTILITY" in policy_decision.reason or "Q3_SHADOW" in policy_decision.reason
        
        # Agent should not proceed to call TimesFM service when policy denies
    
    @pytest.mark.asyncio
    async def test_shadow_to_live_transition(self):
        """Test the shadow-to-live transition pattern."""
        # Test in shadow mode
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            import importlib
            import simp.integrations.timesfm_service as service_module
            importlib.reload(service_module)
            service_module._SERVICE_SINGLETON = None
            
            service = service_module.get_timesfm_service_sync()
            mock_model = Mock()
            horizon = 7
            point_forecasts = np.random.randn(1, horizon).astype(np.float32)
            quantile_forecasts = np.random.randn(1, horizon, 9).astype(np.float32)
            mock_model.forecast = Mock(return_value=(point_forecasts, quantile_forecasts))
            service._model = mock_model
            
            request = ForecastRequest(
                series_id="test:series:1",
                values=[float(i) for i in range(100)],
                frequency="D",
                horizon=horizon,
                requesting_agent="quantumarb",
            )
            
            shadow_response = await service.forecast(request)
            assert shadow_response.shadow_mode is True
            assert shadow_response.available is False
        
        # Test in live mode (shadow mode disabled)
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            importlib.reload(service_module)
            service_module._SERVICE_SINGLETON = None
            
            service = service_module.get_timesfm_service_sync()
            service._model = mock_model  # Reuse mock
            
            live_response = await service.forecast(request)
            assert live_response.shadow_mode is False
            assert live_response.available is True  # Now available in live mode
    
    @pytest.mark.asyncio
    async def test_cache_integration_pattern(self):
        """Test cache integration as used by agents."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import importlib
            import simp.integrations.timesfm_service as service_module
            importlib.reload(service_module)
            service_module._SERVICE_SINGLETON = None
            
            service = service_module.get_timesfm_service_sync()
            
            # Mock model
            mock_model = Mock()
            horizon = 7
            point_forecasts = np.random.randn(1, horizon).astype(np.float32)
            quantile_forecasts = np.random.randn(1, horizon, 9).astype(np.float32)
            mock_model.forecast = Mock(return_value=(point_forecasts, quantile_forecasts))
            service._model = mock_model
            
            # First request
            request = ForecastRequest(
                series_id="test:series:1",
                values=[float(i) for i in range(100)],
                frequency="D",
                horizon=horizon,
                requesting_agent="quantumarb",
            )
            
            response1 = await service.forecast(request)
            assert response1.cached is False
            
            # Second request with same series_id should be cached
            response2 = await service.forecast(request)
            assert response2.cached is True
            
            # Different series_id should not be cached
            request2 = ForecastRequest(
                series_id="test:series:2",  # Different ID
                values=[float(i) for i in range(100)],
                frequency="D",
                horizon=horizon,
                requesting_agent="quantumarb",
            )
            response3 = await service.forecast(request2)
            assert response3.cached is False
    
    @pytest.mark.asyncio
    async def test_error_handling_integration_pattern(self):
        """Test error handling as experienced by agents."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import importlib
            import simp.integrations.timesfm_service as service_module
            importlib.reload(service_module)
            service_module._SERVICE_SINGLETON = None
            
            service = service_module.get_timesfm_service_sync()
            
            # Mock model to raise error
            mock_model = Mock()
            mock_model.forecast = Mock(side_effect=RuntimeError("Model failed"))
            service._model = mock_model
            
            request = ForecastRequest(
                series_id="test:series:1",
                values=[float(i) for i in range(100)],
                frequency="D",
                horizon=7,
                requesting_agent="quantumarb",
            )
            
            # Agent should get graceful error response
            response = await service.forecast(request)
            assert response.available is False
            assert response.error is not None
            assert "error" in response.error.lower()
            
            # Service health should reflect error
            health = service.health()
            assert health["errors"] >= 1
    
    @pytest.mark.asyncio
    async def test_service_disabled_integration_pattern(self):
        """Test agent experience when service is disabled."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'false',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import importlib
            import simp.integrations.timesfm_service as service_module
            importlib.reload(service_module)
            service_module._SERVICE_SINGLETON = None
            
            service = service_module.get_timesfm_service_sync()
            
            request = ForecastRequest(
                series_id="test:series:1",
                values=[float(i) for i in range(100)],
                frequency="D",
                horizon=7,
                requesting_agent="quantumarb",
            )
            
            # Agent gets immediate unavailable response
            response = await service.forecast(request)
            assert response.available is False
            assert response.error is not None
            assert "SIMP_TIMESFM_ENABLED=false" in response.error
            
            # No model should be loaded
            assert service._model is None