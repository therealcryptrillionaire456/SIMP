"""Comprehensive tests for TimesFM service behavior: cache, policy, unavailable mode, malformed inputs."""

import os
import sys
import asyncio
from unittest.mock import Mock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.integrations.timesfm_service import (
    ForecastRequest,
    ForecastResponse,
    TimesFMService,
    get_timesfm_service,
    get_timesfm_service_sync,
)
from simp.integrations.timesfm_policy_engine import (
    PolicyEngine,
    AgentContext,
    make_agent_context_for,
)


class TestCacheBehavior:
    """Test cache behavior in TimesFM service."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_response(self):
        """Cache hit should return cached response with cached=True."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Create a mock cached response
            cached_resp = ForecastResponse(
                available=True,
                shadow_mode=False,
                point_forecast=[1.0, 2.0, 3.0],
                lower_bound=[0.5, 1.5, 2.5],
                upper_bound=[1.5, 2.5, 3.5],
                horizon=3,
                series_id="test:series",
                request_id="cached-123",
                cached=False,
                latency_ms=10.0,
            )
            
            # Manually add to cache
            await service.cache.put("test:series", cached_resp)
            
            # Make request for same series
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,  # 30 observations
                requesting_agent="test",
                horizon=3,
            )
            
            # Mock model loading to prevent actual model load
            with patch.object(service, '_get_model', AsyncMock(side_effect=RuntimeError("Should not load model for cache hit"))):
                resp = await service.forecast(req)
            
            assert resp.cached
            assert resp.series_id == "test:series"
            assert resp.point_forecast == [1.0, 2.0, 3.0]
            # Should not be shadow mode since we disabled it
            assert not resp.shadow_mode
            assert resp.available
    
    @pytest.mark.asyncio
    async def test_cache_miss_computes_new_forecast(self):
        """Cache miss should compute new forecast."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Make request for new series
            req = ForecastRequest(
                series_id="new:series",
                values=[1.0, 2.0, 3.0] * 10,  # 30 observations
                requesting_agent="test",
                horizon=3,
            )
            
            # Mock model to return predictable forecast
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    resp = await service.forecast(req)
            
            assert not resp.cached
            assert resp.series_id == "new:series"
            assert resp.point_forecast == [1.1, 2.1, 3.1]
            assert resp.available
    
    @pytest.mark.asyncio
    async def test_cache_respects_ttl(self):
        """Cache should respect TTL (simulated by manual invalidation)."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Add to cache
            cached_resp = ForecastResponse(
                available=True,
                shadow_mode=False,
                point_forecast=[1.0, 2.0, 3.0],
                lower_bound=[0.5, 1.5, 2.5],
                upper_bound=[1.5, 2.5, 3.5],
                horizon=3,
                series_id="test:series",
                request_id="cached-123",
                cached=False,
                latency_ms=10.0,
            )
            await service.cache.put("test:series", cached_resp)
            
            # Invalidate cache
            await service.cache.invalidate("test:series")
            
            # Should be cache miss now
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            # Mock model since cache was invalidated
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    resp = await service.forecast(req)
            
            assert not resp.cached  # Should be new computation, not cached


class TestPolicyDenials:
    """Test policy engine denial scenarios."""
    
    def test_policy_denies_low_utility_agent(self):
        """Policy should deny agent with low utility score."""
        ctx = AgentContext(
            agent_id="low_utility_agent",
            series_id="test:series",
            q1_utility_score=2,  # Below threshold of 3
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=20,
            requesting_handler="test",
        )
        
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        
        assert decision.denied
        assert "Q1_UTILITY" in decision.reason
        assert "score=2 < required=3" in decision.reason
    
    def test_policy_denies_unconfirmed_shadow_agent(self):
        """Policy should deny agent not confirmed through shadow mode."""
        ctx = AgentContext(
            agent_id="unconfirmed_agent",
            series_id="test:series",
            q1_utility_score=4,
            q3_shadow_confirmed=False,  # Not confirmed
            q8_nonblocking=True,
            min_series_length=20,
            requesting_handler="test",
        )
        
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        
        assert decision.denied
        assert "Q3_SHADOW" in decision.reason
    
    def test_policy_denies_blocking_agent(self):
        """Policy should deny agent that blocks on forecast."""
        ctx = AgentContext(
            agent_id="blocking_agent",
            series_id="test:series",
            q1_utility_score=4,
            q3_shadow_confirmed=True,
            q8_nonblocking=False,  # Blocks on forecast
            min_series_length=20,
            requesting_handler="test",
        )
        
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        
        assert decision.denied
        assert "Q8_NONBLOCKING" in decision.reason
    
    def test_policy_denies_insufficient_series_length(self):
        """Policy should deny request with insufficient observations."""
        ctx = AgentContext(
            agent_id="quantumarb",
            series_id="test:series",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=10,  # Below minimum of 16
            requesting_handler="test",
        )
        
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        
        assert decision.denied
        assert "MIN_SERIES_LENGTH" in decision.reason
        assert "10 < 16" in decision.reason
    
    def test_policy_approves_valid_request(self):
        """Policy should approve valid request from assessed agent."""
        ctx = AgentContext(
            agent_id="quantumarb",
            series_id="test:series",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=20,
            requesting_handler="test",
        )
        
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        
        assert not decision.denied
        assert decision.approved
        assert decision.reason == "All policy checks passed"


class TestUnavailableMode:
    """Test service behavior when unavailable (disabled or error)."""
    
    @pytest.mark.asyncio
    async def test_service_disabled_returns_unavailable(self):
        """When service is disabled, should return unavailable response."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'false',  # Disabled
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            # Clear the singleton to force creation of new service with new environment
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Use unique series ID to avoid cache hits from other tests
            req = ForecastRequest(
                series_id="disabled_test:unique_series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            resp = await service.forecast(req)
            
            assert not resp.available
            assert resp.error == "SIMP_TIMESFM_ENABLED=false"
            # Should still have latency measurement
            assert resp.latency_ms > 0
    
    @pytest.mark.asyncio
    async def test_model_load_error_returns_unavailable(self):
        """When model fails to load, should return unavailable."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Use unique series ID to avoid cache hits from other tests
            req = ForecastRequest(
                series_id="model_error_test:unique_series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            # Mock model loading to raise exception
            with patch.object(service, '_get_model', AsyncMock(side_effect=RuntimeError("Model load failed"))):
                resp = await service.forecast(req)
            
            assert not resp.available
            assert "Forecast error:" in resp.error
            assert "Model load failed" in resp.error
    
    @pytest.mark.asyncio
    async def test_forecast_computation_error_returns_unavailable(self):
        """When forecast computation fails, should return unavailable."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Use unique series ID to avoid cache hits from other tests
            req = ForecastRequest(
                series_id="forecast_error_test:unique_series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            # Mock model to load successfully but forecast to fail
            mock_model = Mock()
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', side_effect=ValueError("Forecast computation error")):
                    resp = await service.forecast(req)
            
            assert not resp.available
            assert "Forecast error:" in resp.error
            assert "Forecast computation error" in resp.error


class TestMalformedInputs:
    """Test service handling of malformed inputs."""
    
    @pytest.mark.asyncio
    async def test_nan_values_in_request(self):
        """Request with NaN values should fail validation."""
        import math
        
        req = ForecastRequest(
            series_id="test:series",
            values=[1.0, 2.0, float('nan'), 4.0] * 5,  # Contains NaN
            requesting_agent="test",
            horizon=3,
        )
        
        errors = req.validate()
        assert any("not finite" in err for err in errors)
    
    @pytest.mark.asyncio
    async def test_inf_values_in_request(self):
        """Request with Inf values should fail validation."""
        req = ForecastRequest(
            series_id="test:series",
            values=[1.0, 2.0, float('inf'), 4.0] * 5,  # Contains Inf
            requesting_agent="test",
            horizon=3,
        )
        
        errors = req.validate()
        assert any("not finite" in err for err in errors)
    
    @pytest.mark.asyncio
    async def test_non_numeric_values_in_request(self):
        """Request with non-numeric values should fail validation."""
        req = ForecastRequest(
            series_id="test:series",
            values=[1.0, 2.0, "not-a-number", 4.0] * 5,  # Contains string
            requesting_agent="test",
            horizon=3,
        )
        
        errors = req.validate()
        assert any("not a number" in err for err in errors)
    
    @pytest.mark.asyncio
    async def test_empty_values_list(self):
        """Request with empty values list should fail validation."""
        req = ForecastRequest(
            series_id="test:series",
            values=[],  # Empty list
            requesting_agent="test",
            horizon=3,
        )
        
        errors = req.validate()
        assert any("Need ≥16 observations" in err for err in errors)
    
    def test_make_agent_context_for_unregistered_agent(self):
        """make_agent_context_for should handle unregistered agents with defaults."""
        ctx = make_agent_context_for(
            agent_id="unknown_agent_123",
            series_id="test:series",
            series_length=20,
            requesting_handler="test",
        )
        
        # Should use default assessment (low utility, not shadow confirmed)
        assert ctx.q1_utility_score == 1  # Default low score
        assert not ctx.q3_shadow_confirmed  # Default false
        assert ctx.q8_nonblocking  # Default true
        assert ctx.agent_id == "unknown_agent_123"


class TestShadowModeBehavior:
    """Test shadow mode behavior."""
    
    @pytest.mark.asyncio
    async def test_shadow_mode_computes_but_suppresses(self):
        """In shadow mode, forecast should be computed but available=False."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',  # Shadow mode enabled
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Use unique series ID to avoid cache hits from other tests
            req = ForecastRequest(
                series_id="shadow_mode_test:unique_series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            # Mock model
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    resp = await service.forecast(req)
            
            # In shadow mode, forecast is computed but not available
            assert resp.shadow_mode
            assert not resp.available
            # But forecast data should still be present
            assert resp.point_forecast == [1.1, 2.1, 3.1]
    
    @pytest.mark.asyncio  
    async def test_shadow_mode_still_caches(self):
        """In shadow mode, forecasts should still be cached."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            # Mock model
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    # First request - should compute
                    resp1 = await service.forecast(req)
            
            # Second request - should be cached
            req2 = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
                request_id="different-request-id",
            )
            
            with patch.object(service, '_get_model', AsyncMock(side_effect=RuntimeError("Should not load model for cache hit"))):
                resp2 = await service.forecast(req2)
            
            assert resp2.cached
            assert resp2.point_forecast == [1.1, 2.1, 3.1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])