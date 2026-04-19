"""Tests for TimesFM service hardening (validation, health, audit)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.integrations.timesfm_service import (
    ForecastRequest,
    ForecastResponse,
    TimesFMService,
    get_timesfm_service_sync,
)
from simp.integrations.timesfm_policy_engine import (
    AgentContext,
    PolicyEngine,
    make_agent_context_for,
)


class TestForecastRequestValidation:
    """Test validation methods added to ForecastRequest."""
    
    def test_forecast_request_validation_passes_good_request(self):
        """Valid request should have no validation errors."""
        req = ForecastRequest(
            series_id="SOL/USDC:spread",
            values=[0.1] * 20,  # 20 observations
            requesting_agent="quantumarb",
            horizon=32,
        )
        errors = req.validate()
        assert errors == [], f"Expected no errors, got: {errors}"
    
    def test_forecast_request_validation_fails_short_series(self):
        """Request with insufficient observations should fail validation."""
        req = ForecastRequest(
            series_id="SOL/USDC:spread",
            values=[0.1] * 10,  # Only 10 observations
            requesting_agent="quantumarb",
            horizon=32,
        )
        errors = req.validate()
        assert any("Need ≥16 observations" in err for err in errors), \
            f"Expected insufficient observations error, got: {errors}"
    
    def test_forecast_request_validation_fails_large_horizon(self):
        """Request with horizon > 128 should fail validation."""
        req = ForecastRequest(
            series_id="SOL/USDC:spread",
            values=[0.1] * 20,
            requesting_agent="quantumarb",
            horizon=256,  # Too large
        )
        errors = req.validate()
        assert any("exceeds safe limit" in err for err in errors), \
            f"Expected horizon limit error, got: {errors}"
    
    def test_forecast_request_validation_fails_bad_series_id(self):
        """Request with malformed series_id should fail validation."""
        req = ForecastRequest(
            series_id="SOLUSDCspread",  # No colon separator
            values=[0.1] * 20,
            requesting_agent="quantumarb",
            horizon=32,
        )
        errors = req.validate()
        assert any("domain:metric" in err for err in errors), \
            f"Expected series_id format error, got: {errors}"
    
    def test_forecast_request_validation_fails_empty_series_id(self):
        """Request with empty series_id should fail validation."""
        req = ForecastRequest(
            series_id="",
            values=[0.1] * 20,
            requesting_agent="quantumarb",
            horizon=32,
        )
        errors = req.validate()
        assert any("series_id should follow" in err for err in errors), \
            f"Expected series_id format error, got: {errors}"


class TestTimesFMServiceHealthReporting:
    """Test enhanced health reporting."""
    
    def test_health_includes_enhanced_metrics(self):
        """Health report should include cache_hit_rate and error_rate."""
        # Mock the service to avoid actual model loading
        import simp.integrations.timesfm_service as tfs
        
        # Temporarily disable TimesFM to avoid model loading
        original_enabled = tfs.TIMESFM_ENABLED
        tfs.TIMESFM_ENABLED = False
        
        try:
            service = TimesFMService()
            health = service.health()
            
            # Check enhanced metrics exist
            assert "cache_hit_rate" in health
            assert "avg_latency_ms" in health
            assert "error_rate" in health
            assert "shadow_mode_samples" in health
            
            # Check types
            assert isinstance(health["cache_hit_rate"], (int, float))
            assert isinstance(health["avg_latency_ms"], (int, float))
            assert isinstance(health["error_rate"], (int, float))
            assert isinstance(health["shadow_mode_samples"], int)
            
            # Initial values should be zero
            assert health["cache_hit_rate"] == 0.0
            assert health["avg_latency_ms"] == 0.0
            assert health["error_rate"] == 0.0
            assert health["shadow_mode_samples"] == 0
            
        finally:
            tfs.TIMESFM_ENABLED = original_enabled
    
    def test_health_includes_basic_fields(self):
        """Health report should still include all basic fields."""
        import simp.integrations.timesfm_service as tfs
        
        original_enabled = tfs.TIMESFM_ENABLED
        tfs.TIMESFM_ENABLED = False
        
        try:
            service = TimesFMService()
            health = service.health()
            
            # Check basic fields still exist
            required_fields = [
                "enabled", "shadow_mode", "model_loaded", "checkpoint",
                "context_len", "default_horizon", "cache_size", "audit_records"
            ]
            
            for field in required_fields:
                assert field in health, f"Missing field in health: {field}"
                
        finally:
            tfs.TIMESFM_ENABLED = original_enabled


class TestAuditLogEnhancements:
    """Test enhanced audit logging."""
    
    def test_audit_log_includes_validation_errors(self):
        """Audit log should include validation errors when present."""
        import simp.integrations.timesfm_service as tfs
        
        # Create a request that will fail validation
        req = ForecastRequest(
            series_id="badid",  # No colon
            values=[0.1] * 10,  # Too short
            requesting_agent="test",
            horizon=256,  # Too large
        )
        
        # Create a mock response
        resp = ForecastResponse.unavailable(
            request_id=req.request_id,
            series_id=req.series_id,
            horizon=req.horizon,
            reason="Test",
            shadow_mode=True,
        )
        
        # Create audit log and record
        audit = tfs.ForecastAuditLog()
        audit.record(req, resp)
        
        # Get recent entries
        entries = audit.recent(1)
        assert len(entries) == 1
        
        entry = entries[0]
        # Check that validation_errors field exists
        assert "validation_errors" in entry
        # Should have 3 validation errors
        assert len(entry["validation_errors"]) >= 2  # At least 2 errors expected
    
    def test_audit_log_preserves_existing_fields(self):
        """Audit log should preserve all existing fields."""
        import simp.integrations.timesfm_service as tfs
        
        req = ForecastRequest(
            series_id="test:metric",
            values=[0.1] * 20,
            requesting_agent="test",
            horizon=32,
        )
        
        resp = ForecastResponse.unavailable(
            request_id=req.request_id,
            series_id=req.series_id,
            horizon=req.horizon,
            reason="Test",
            shadow_mode=True,
        )
        
        audit = tfs.ForecastAuditLog()
        audit.record(req, resp)
        
        entries = audit.recent(1)
        entry = entries[0]
        
        # Check all original fields exist
        original_fields = [
            "ts", "request_id", "series_id", "requesting_agent", "horizon",
            "input_length", "available", "shadow_mode", "cached", 
            "latency_ms", "error"
        ]
        
        for field in original_fields:
            assert field in entry, f"Missing original field: {field}"


class TestPolicyEngineEnhancements:
    """Test policy engine hardening."""
    
    def test_policy_engine_includes_validation_in_decision(self):
        """Policy decision should include validation status."""
        # Create a context that will pass policy but request would fail validation
        ctx = AgentContext(
            agent_id="quantumarb",
            series_id="badid",  # No colon
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=10,  # Too short
            requesting_handler="test",
        )
        
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        
        # Decision should be denied due to min_series_length
        assert decision.denied
        assert "MIN_SERIES_LENGTH" in decision.reason
    
    def test_make_agent_context_handles_edge_cases(self):
        """make_agent_context_for should handle edge cases gracefully."""
        # Test with unregistered agent
        ctx = make_agent_context_for(
            agent_id="unknown_agent",
            series_id="test:metric",
            series_length=20,
            requesting_handler="test",
        )
        
        assert ctx.agent_id == "unknown_agent"
        assert ctx.q1_utility_score == 1  # Default low score
        assert not ctx.q3_shadow_confirmed  # Default false
        assert ctx.q8_nonblocking  # Default true
        
        # Test with agent ID containing colon
        ctx = make_agent_context_for(
            agent_id="quantumarb:instance1",
            series_id="test:metric",
            series_length=20,
            requesting_handler="test",
        )
        
        assert ctx.agent_id == "quantumarb:instance1"
        # Should use base_id "quantumarb" for assessment lookup
        assert ctx.q1_utility_score == 5  # quantumarb assessment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])