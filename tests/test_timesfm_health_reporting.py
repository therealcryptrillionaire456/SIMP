"""Tests for TimesFM service health and policy reporting."""

import os
import sys
from unittest.mock import Mock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.integrations.timesfm_service import (
    TimesFMService,
    get_timesfm_service_sync,
    ForecastRequest,
    ForecastResponse,
)
from simp.integrations.timesfm_policy_engine import PolicyEngine


class TestTimesFMServiceHealthReporting:
    """Test TimesFM service health reporting."""
    
    def test_health_includes_version_and_policy_rules(self):
        """Health report should include version and policy rules."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            health = service.health()
            
            # Check version
            assert "version" in health
            assert health["version"] == "1.0.0"
            
            # Check basic status
            assert "enabled" in health
            assert "shadow_mode" in health
            assert health["enabled"] is True
            assert health["shadow_mode"] is False
            
            # Check policy rules
            assert "policy_rules" in health
            policy_rules = health["policy_rules"]
            assert policy_rules["min_observations"] == 16
            assert policy_rules["max_horizon"] == 128
            assert policy_rules["series_id_format"] == "domain:metric"
            assert policy_rules["q1_utility_threshold"] == 3
            assert policy_rules["q3_shadow_required"] is True
            assert policy_rules["q8_nonblocking_required"] is True
    
    def test_health_includes_last_error_from_audit_log(self):
        """Health report should include last error from audit log if any."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Initially no error
            health1 = service.health()
            assert health1["last_error"] is None
            
            # Simulate an error by adding to audit log
            req = ForecastRequest(
                series_id="test:series",
                values=[1.0, 2.0, 3.0] * 10,
                requesting_agent="test",
                horizon=3,
            )
            
            resp = ForecastResponse(
                available=False,
                shadow_mode=False,
                point_forecast=[],
                lower_bound=[],
                upper_bound=[],
                horizon=3,
                series_id="test:series",
                request_id="test-123",
                cached=False,
                latency_ms=5.0,
                error="Test error message",
            )
            
            service.audit.record(req, resp)
            
            # Now health should show last error
            health2 = service.health()
            assert health2["last_error"] == "Test error message"
    
    def test_health_includes_enhanced_metrics(self):
        """Health report should include enhanced metrics."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            health = service.health()
            
            # Check enhanced metrics are present
            assert "cache_hit_rate" in health
            assert "avg_latency_ms" in health
            assert "error_rate" in health
            assert "shadow_mode_samples" in health
            assert "total_requests" in health
            assert "cache_hits" in health
            assert "errors" in health
            
            # Initial values should be zero
            assert health["total_requests"] == 0
            assert health["cache_hits"] == 0
            assert health["errors"] == 0
            assert health["cache_hit_rate"] == 0.0
            assert health["error_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_health_updates_with_requests(self):
        """Health metrics should update as requests are made."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            
            # Make a request
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
                    await service.forecast(req)
            
            health = service.health()
            assert health["total_requests"] == 1
            assert health["cache_hits"] == 0  # Cache miss
            assert health["errors"] == 0
    
    def test_health_when_service_disabled(self):
        """Health report should reflect disabled service state."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'false',
            'SIMP_TIMESFM_SHADOW_MODE': 'true',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            health = service.health()
            
            assert health["enabled"] is False
            assert health["shadow_mode"] is True
            assert health["model_loaded"] is False  # Model not loaded when disabled


class TestPolicyEngineHealthReporting:
    """Test policy engine health reporting."""
    
    def test_policy_engine_health_includes_configuration(self):
        """Policy engine health should include configuration."""
        engine = PolicyEngine()
        health = engine.health()
        
        # Check version
        assert "version" in health
        assert health["version"] == "1.0.0"
        
        # Check configuration
        assert health["min_observations"] == 16
        assert health["q1_utility_threshold"] == 3
        assert health["q3_shadow_required"] is True
        assert health["q8_nonblocking_required"] is True
        
        # Check policy description
        assert "policy_description" in health
        assert "Q1" in health["policy_description"]
        assert "Q3" in health["policy_description"]
        assert "Q8" in health["policy_description"]
        assert "16 observations" in health["policy_description"]
    
    def test_policy_engine_health_is_pure_python(self):
        """Policy engine health should be pure Python (no network I/O)."""
        engine = PolicyEngine()
        
        # This should not raise any network-related errors
        health = engine.health()
        
        # Should return a dict
        assert isinstance(health, dict)
        
        # Should not have any async methods
        import inspect
        assert not inspect.iscoroutinefunction(engine.health)


class TestHealthFunctionIntegration:
    """Test integration of health functions across service and policy engine."""
    
    def test_health_functions_consistent_with_actual_behavior(self):
        """Health functions should report values consistent with actual service behavior."""
        with patch.dict('os.environ', {
            'SIMP_TIMESFM_ENABLED': 'true',
            'SIMP_TIMESFM_SHADOW_MODE': 'false',
        }):
            import simp.integrations.timesfm_service as module
            module._service_instance = None
            
            service = get_timesfm_service_sync()
            service_health = service.health()
            
            policy_engine = PolicyEngine()
            policy_health = policy_engine.health()
            
            # Check consistency between service and policy engine
            assert service_health["policy_rules"]["min_observations"] == policy_health["min_observations"]
            assert service_health["policy_rules"]["q1_utility_threshold"] == policy_health["q1_utility_threshold"]
            assert service_health["policy_rules"]["q3_shadow_required"] == policy_health["q3_shadow_required"]
            assert service_health["policy_rules"]["q8_nonblocking_required"] == policy_health["q8_nonblocking_required"]
            
            # Service should report additional validation rules
            assert "max_horizon" in service_health["policy_rules"]
            assert "series_id_format" in service_health["policy_rules"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])