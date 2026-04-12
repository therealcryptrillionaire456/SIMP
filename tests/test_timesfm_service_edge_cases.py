"""Additional edge case tests for TimesFM service hardening."""

import os
import sys
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.integrations.timesfm_service import (
    ForecastRequest,
    ForecastResponse,
    TimesFMService,
    get_timesfm_service_sync,
    ForecastAuditLog,
)
from simp.integrations.timesfm_policy_engine import (
    PolicyEngine,
    AgentContext,
    make_agent_context_for,
)


class TestAuditLogAppendBehavior:
    """Test audit log append behavior."""
    
    def test_audit_log_actually_writes_to_memory(self):
        """Audit log should store entries in memory."""
        audit_log = ForecastAuditLog()
        
        # Create a mock request and response
        req = ForecastRequest(
            series_id="test:series",
            values=[1.0, 2.0, 3.0] * 10,
            requesting_agent="test",
            horizon=3,
        )
        
        resp = ForecastResponse(
            available=True,
            shadow_mode=False,
            point_forecast=[1.1, 2.1, 3.1],
            lower_bound=[0.6, 1.6, 2.6],
            upper_bound=[1.6, 2.6, 3.6],
            horizon=3,
            series_id="test:series",
            request_id="test-123",
            cached=False,
            latency_ms=10.0,
        )
        
        # Record an entry
        audit_log.record(request=req, response=resp)
        
        # Check entry was stored in memory
        assert len(audit_log._log) == 1
        
        entry = audit_log._log[0]
        assert entry["series_id"] == "test:series"
        assert entry["requesting_agent"] == "test"
        assert entry["available"] is True
        assert entry["validation_errors"] == []
    
    def test_audit_log_includes_validation_errors_when_present(self):
        """Audit log should include validation errors when present."""
        audit_log = ForecastAuditLog()
        
        req = ForecastRequest(
            series_id="bad",  # Missing colon
            values=[1.0],  # Too short
            requesting_agent="test",
            horizon=200,  # Too large
        )
        
        resp = ForecastResponse(
            available=False,
            shadow_mode=False,
            point_forecast=[],
            lower_bound=[],
            upper_bound=[],
            horizon=200,
            series_id="bad",
            request_id="test-123",
            cached=False,
            latency_ms=5.0,
            error="Validation failed",
        )
        
        # Note: ForecastAuditLog.record() calls request.validate() internally
        # So we need a request that will have validation errors
        audit_log.record(request=req, response=resp)
        
        assert len(audit_log._log) == 1
        entry = audit_log._log[0]
        # Should have validation errors from request.validate()
        assert len(entry["validation_errors"]) > 0
        assert entry["available"] is False
        assert "error" in entry
    
    def test_audit_log_includes_cache_hit_field(self):
        """Audit log should include cache_hit field for easier querying."""
        audit_log = ForecastAuditLog()
        
        req = ForecastRequest(
            series_id="test:series",
            values=[1.0, 2.0, 3.0] * 10,
            requesting_agent="test",
            horizon=3,
        )
        
        # Test cached response
        resp_cached = ForecastResponse(
            available=True,
            shadow_mode=False,
            point_forecast=[1.1, 2.1, 3.1],
            lower_bound=[0.6, 1.6, 2.6],
            upper_bound=[1.6, 2.6, 3.6],
            horizon=3,
            series_id="test:series",
            request_id="test-123",
            cached=True,
            latency_ms=2.0,
        )
        
        audit_log.record(request=req, response=resp_cached)
        
        entry = audit_log._log[0]
        assert entry["cache_hit"] is True
        assert entry["cached"] is True
        
        # Test non-cached response
        resp_not_cached = ForecastResponse(
            available=True,
            shadow_mode=False,
            point_forecast=[1.2, 2.2, 3.2],
            lower_bound=[0.7, 1.7, 2.7],
            upper_bound=[1.7, 2.7, 3.7],
            horizon=3,
            series_id="test:series2",
            request_id="test-124",
            cached=False,
            latency_ms=10.0,
        )
        
        audit_log.record(request=req, response=resp_not_cached)
        
        entry2 = audit_log._log[1]
        assert entry2["cache_hit"] is False
        assert entry2["cached"] is False


class TestHealthReportConsistency:
    """Test health report consistency across calls."""
    
    @pytest.mark.asyncio
    async def test_health_report_consistent_across_calls(self):
        """Health report should be consistent and update with statistics."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Get initial health
            health1 = service.health()
            assert health1["total_requests"] == 0
            assert health1["cache_hits"] == 0
            assert health1["errors"] == 0
            
            # Make a request (mocked)
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    resp = await service.forecast(req)
            
            # Get health after request
            health2 = service.health()
            assert health2["total_requests"] == 1
            assert health2["cache_hits"] == 0  # Cache miss
            assert health2["errors"] == 0
            
            # Make same request again (should be cached)
            with patch.object(service, '_get_model', AsyncMock(side_effect=RuntimeError("Should not load model for cache hit"))):
                resp2 = await service.forecast(req)
            
            # Get health after cache hit
            health3 = service.health()
            assert health3["total_requests"] == 2
            assert health3["cache_hits"] == 1  # One cache hit
            assert health3["cache_hit_rate"] > 0.0
    
    @pytest.mark.asyncio
    async def test_health_includes_error_rate_calculation(self):
        """Health report should calculate error rate correctly."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Make several requests with some errors
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            # First request - success
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    await service.forecast(req)
            
            # Second request - error (validation error)
            req_invalid = ForecastRequest(
                series_id="test:series2",
                values=[1.0],  # Too short - will fail validation
                requesting_agent="test",
                horizon=3,
            )
            
            await service.forecast(req_invalid)
            
            # Third request - success
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    await service.forecast(req)
            
            health = service.health()
            assert health["total_requests"] == 3
            assert health["errors"] == 1  # One validation error
            # Error rate should be 1/3 ≈ 0.333
            assert abs(health["error_rate"] - 0.333) < 0.01


class TestRequestValidationIntegration:
    """Test request validation integration with forecast flow."""
    
    @pytest.mark.asyncio
    async def test_validation_errors_return_unavailable_response(self):
        """Requests with validation errors should return unavailable response."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Create request that will fail validation (too short)
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0],  # Only 3 observations, need ≥16
                requesting_agent="test",
                horizon=3,
            )
            
            # Should not try to load model or compute forecast
            with patch.object(service, '_get_model', AsyncMock(side_effect=RuntimeError("Should not be called"))):
                with patch.object(service, '_run_forecast_sync', side_effect=RuntimeError("Should not be called")):
                    resp = await service.forecast(req)
            
            assert not resp.available
            assert "validation" in resp.error.lower()
            # Should still have audit log entry
            assert len(service.audit._log) > 0
    
    @pytest.mark.asyncio
    async def test_validation_passes_for_good_request(self):
        """Requests that pass validation should proceed to forecast."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Create valid request
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,  # 30 observations
                requesting_agent="test",
                horizon=3,
            )
            
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    resp = await service.forecast(req)
            
            assert resp.available
            assert resp.point_forecast == [1.1, 2.1, 3.1]


class TestCacheExpiryBehavior:
    """Test cache expiry behavior."""
    
    @pytest.mark.asyncio
    async def test_cache_manual_invalidation_works(self):
        """Manual cache invalidation should remove entries."""
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
            
            # Verify in cache
            cached = await service.cache.get("test:series")
            assert cached is not None
            
            # Invalidate
            await service.cache.invalidate("test:series")
            
            # Should not be in cache
            cached_after = await service.cache.get("test:series")
            assert cached_after is None
    
    @pytest.mark.asyncio
    async def test_cache_size_limited(self):
        """Cache should respect size limits."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Add many entries (more than default cache size of 100)
            for i in range(150):
                resp = ForecastResponse(
                    available=True,
                    shadow_mode=False,
                    point_forecast=[float(i)],
                    lower_bound=[float(i) - 0.5],
                    upper_bound=[float(i) + 0.5],
                    horizon=1,
                    series_id=f"test:series_{i}",
                    request_id=f"req-{i}",
                    cached=False,
                    latency_ms=10.0,
                )
                await service.cache.put(f"test:series_{i}", resp)
            
            # Cache size should be limited
            assert service.cache.size <= 100  # Default max size


class TestConcurrentAccess:
    """Test concurrent access thread safety."""
    
    @pytest.mark.asyncio
    async def test_concurrent_forecast_requests(self):
        """Multiple concurrent forecast requests should not crash."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Create multiple requests
            requests = []
            for i in range(5):
                req = ForecastRequest(
                    series_id=f"test:series_{i}",
                    values=[1.0, 2.0, 3.0] * 10,
                    requesting_agent="test",
                    horizon=3,
                )
                requests.append(req)
            
            # Mock model for all requests
            mock_model = Mock()
            mock_forecast_result = ([1.1, 2.1, 3.1], [0.6, 1.6, 2.6], [1.6, 2.6, 3.6])
            
            with patch.object(service, '_get_model', AsyncMock(return_value=mock_model)):
                with patch.object(service, '_run_forecast_sync', return_value=mock_forecast_result):
                    # Run forecasts concurrently
                    tasks = [service.forecast(req) for req in requests]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed
            for result in results:
                assert not isinstance(result, Exception)
                assert result.available
                assert result.point_forecast == [1.1, 2.1, 3.1]
            
            # Should have recorded all requests
            health = service.health()
            assert health["total_requests"] == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """Multiple concurrent cache accesses should be thread-safe."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Create a response to cache
            resp = ForecastResponse(
                available=True,
                shadow_mode=False,
                point_forecast=[1.0, 2.0, 3.0],
                lower_bound=[0.5, 1.5, 2.5],
                upper_bound=[1.5, 2.5, 3.5],
                horizon=3,
                series_id="test:series",
                request_id="test-123",
                cached=False,
                latency_ms=10.0,
            )
            
            # Concurrent put and get operations
            async def put_operation():
                await service.cache.put("test:series", resp)
                return "put"
            
            async def get_operation():
                result = await service.cache.get("test:series")
                return "get", result is not None
            
            # Run operations concurrently multiple times
            tasks = []
            for i in range(10):
                if i % 2 == 0:
                    tasks.append(put_operation())
                else:
                    tasks.append(get_operation())
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # No exceptions should occur
            for result in results:
                assert not isinstance(result, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])