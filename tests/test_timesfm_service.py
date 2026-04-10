"""
Tests for TimesFM service core functionality.
"""
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
import pytest

from simp.integrations.timesfm_service import (
    TimesFMService,
    ForecastRequest,
    ForecastResponse,
    get_timesfm_service,
    get_timesfm_service_sync,
    TIMESFM_ENABLED,
    TIMESFM_SHADOW_MODE,
)


class TestTimesFMService:
    """Test TimesFM service core functionality."""
    
    def test_singleton_pattern(self):
        """Verify singleton pattern returns same instance."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            # Clear any existing singleton
            import simp.integrations.timesfm_service as module
            module._SERVICE_SINGLETON = None
            
            service1 = get_timesfm_service_sync()
            service2 = get_timesfm_service_sync()
            assert service1 is service2
            
            # Async version should return same instance
            service3 = asyncio.run(get_timesfm_service())
            assert service1 is service3
    
    def test_forecast_request_validation(self):
        """Test ForecastRequest dataclass validation."""
        request = ForecastRequest(
            series_id="test:series:1",
            values=[1.0, 2.0, 3.0, 4.0, 5.0],
            frequency="D",
            horizon=7,
            requesting_agent="test_agent",
        )
        assert request.series_id == "test:series:1"
        assert len(request.values) == 5
        assert request.frequency == "D"
        assert request.horizon == 7
        assert request.requesting_agent == "test_agent"
        
        # Test with request_id generation
        assert request.request_id is not None
        assert len(request.request_id) == 36  # UUID length
    
    def test_forecast_response_unavailable(self):
        """Test unavailable response factory method."""
        response = ForecastResponse.unavailable(
            request_id="test-request",
            series_id="test:series:1",
            horizon=7,
            reason="Service disabled",
            shadow_mode=True,
        )
        assert not response.available
        assert response.shadow_mode
        assert response.point_forecast == []
        assert response.lower_bound == []
        assert response.upper_bound == []
        assert response.error == "Service disabled"
        assert not response.cached
    
    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test LRU cache functionality."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            import simp.integrations.timesfm_service as module
            module._SERVICE_SINGLETON = None
            
            service = get_timesfm_service_sync()
            
            # Create a mock response
            request = ForecastRequest(
                series_id="test:series:1",
                values=[1.0] * 100,
                frequency="D",
                horizon=7,
                requesting_agent="test_agent",
            )
            
            response = ForecastResponse(
                available=False,
                shadow_mode=True,
                point_forecast=[1.0] * 7,
                lower_bound=[0.5] * 7,
                upper_bound=[1.5] * 7,
                horizon=7,
                series_id="test:series:1",
                request_id=request.request_id,
                cached=False,
                latency_ms=10.0,
            )
            
            # Put in cache
            await service.cache.put(request.series_id, response)
            assert service.cache.size == 1
            
            # Get from cache - note: cache returns original response without cached flag
            cached = await service.cache.get(request.series_id)
            assert cached is not None
            assert cached.series_id == response.series_id
            # The cache returns the original response, cached flag is set in forecast() method
            
            # Invalidate cache
            await service.cache.invalidate(request.series_id)
            assert service.cache.size == 0
    
    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test audit log records requests and responses."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            import simp.integrations.timesfm_service as module
            module._SERVICE_SINGLETON = None
            
            service = get_timesfm_service_sync()
            
            request = ForecastRequest(
                series_id="test:series:1",
                values=[1.0] * 100,
                frequency="D",
                horizon=7,
                requesting_agent="test_agent",
            )
            
            response = ForecastResponse(
                available=False,
                shadow_mode=True,
                point_forecast=[1.0] * 7,
                lower_bound=[0.5] * 7,
                upper_bound=[1.5] * 7,
                horizon=7,
                series_id="test:series:1",
                request_id=request.request_id,
                cached=False,
                latency_ms=10.0,
            )
            
            # Record in audit log
            service.audit.record(request, response)
            
            # Check recent entries
            recent = service.audit.recent(1)
            assert len(recent) == 1
            assert recent[0]["series_id"] == "test:series:1"
            assert recent[0]["requesting_agent"] == "test_agent"
            
            # Check agent-specific entries
            agent_entries = service.audit.for_agent("test_agent", 1)
            assert len(agent_entries) == 1
    
    def test_health_reporting(self):
        """Test health report includes service status."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            # Clear singleton and re-import to pick up new env vars
            import importlib
            import simp.integrations.timesfm_service as module
            importlib.reload(module)
            module._SERVICE_SINGLETON = None
            
            service = module.get_timesfm_service_sync()
            # Set model directly to simulate loaded state
            service._model = Mock()
            health = service.health()
            
            assert "enabled" in health
            assert "shadow_mode" in health
            assert "cache_size" in health
            assert "audit_records" in health
            assert "model_loaded" in health
            assert health["enabled"] is True, f"enabled should be True, got {health['enabled']}"
            assert health["shadow_mode"] is True, f"shadow_mode should be True, got {health['shadow_mode']}"
            # Model loaded should be True with our mock
            assert health["model_loaded"] is True, f"model_loaded should be True, got {health['model_loaded']}"
    
    def test_shadow_mode_default(self):
        """Verify shadow mode is True by default."""
        # Clear environment to test defaults
        with patch.dict('os.environ', {}, clear=True):
            import simp.integrations.timesfm_service as module
            module._SERVICE_SINGLETON = None
            
            service = get_timesfm_service_sync()
            assert service._shadow_mode is True  # Default should be True
    
    def test_service_disabled_by_default(self):
        """Verify service is disabled by default."""
        # Clear environment to test defaults
        with patch.dict('os.environ', {}, clear=True):
            # Clear singleton and re-import to pick up new env vars
            import importlib
            import simp.integrations.timesfm_service as module
            importlib.reload(module)
            module._SERVICE_SINGLETON = None
            
            service = module.get_timesfm_service_sync()
            assert service._enabled is False, f"Default should be False, got {service._enabled}"  # Default should be False
    
    @pytest.mark.asyncio
    async def test_model_import_error_handling(self):
        """Test error handling when TimesFM package is not installed."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import importlib
            import simp.integrations.timesfm_service as module
            importlib.reload(module)
            module._SERVICE_SINGLETON = None
            
            service = module.get_timesfm_service_sync()
            
            # Mock import error in _get_model
            with patch.object(service, '_get_model', AsyncMock(side_effect=RuntimeError("timesfm package not installed"))):
                request = ForecastRequest(
                    series_id="test:series:1",
                    values=[float(i) for i in range(100)],
                    frequency="D",
                    horizon=7,
                    requesting_agent="quantumarb",
                )
                
                response = await service.forecast(request)
                
                # Should return unavailable response with error
                assert response.available is False
                assert response.error is not None
                assert "timesfm package" in response.error.lower() or "error" in response.error.lower()
                
                # Error should be tracked in statistics
                health = service.health()
                assert health["errors"] >= 1