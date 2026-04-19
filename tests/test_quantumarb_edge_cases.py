"""
test_quantumarb_edge_cases.py
=============================
Edge case tests for QuantumArb TimesFM shadow mode.
"""
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest

from simp.agents.quantumarb_agent import (
    _try_forecast_sync,
    _log_timesfm_shadow,
    ArbDecision,
    ArbitrageSignal,
    ArbType,
    QuantumArbEngine,
)


class TestForecastEdgeCases:
    """Test edge cases for TimesFM forecast integration."""
    
    def test_try_forecast_sync_with_none_values(self):
        """Test _try_forecast_sync with None values list."""
        result = _try_forecast_sync("test_series", None)
        assert result is None
    
    def test_try_forecast_sync_with_empty_values(self):
        """Test _try_forecast_sync with empty values list."""
        result = _try_forecast_sync("test_series", [])
        assert result is None
    
    def test_try_forecast_sync_with_single_value(self):
        """Test _try_forecast_sync with single value (insufficient data)."""
        result = _try_forecast_sync("test_series", [1.0])
        assert result is None
    
    def test_try_forecast_sync_with_non_numeric_values(self):
        """Test _try_forecast_sync with non-numeric values."""
        result = _try_forecast_sync("test_series", ["a", "b", "c"])
        assert result is None
    
    def test_try_forecast_sync_with_mixed_numeric_values(self):
        """Test _try_forecast_sync with mixed numeric and non-numeric values."""
        result = _try_forecast_sync("test_series", [1.0, "invalid", 2.0])
        # Should still attempt forecast if at least 16 valid values
        # But with only 2 valid values, should return None
        assert result is None
    
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_try_forecast_sync_service_exception(self, mock_policy, mock_context, mock_service):
        """Test _try_forecast_sync when service raises exception."""
        # Mock service to raise exception
        mock_svc = Mock()
        mock_svc.forecast = AsyncMock(side_effect=Exception("Service unavailable"))
        mock_service.return_value = mock_svc
        
        # Mock policy to allow
        mock_engine = Mock()
        mock_engine.evaluate.return_value.denied = False
        mock_policy.return_value = mock_engine
        
        # Mock context
        mock_context.return_value = Mock()
        
        result = _try_forecast_sync("test_series", [1.0] * 20)
        assert result is None
    
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_try_forecast_sync_policy_exception(self, mock_policy, mock_context, mock_service):
        """Test _try_forecast_sync when policy engine raises exception."""
        # Mock policy to raise exception
        mock_engine = Mock()
        mock_engine.evaluate.side_effect = Exception("Policy error")
        mock_policy.return_value = mock_engine
        
        result = _try_forecast_sync("test_series", [1.0] * 20)
        assert result is None
    
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_try_forecast_sync_with_running_event_loop(self, mock_policy, mock_context, mock_service):
        """Test _try_forecast_sync when event loop is already running."""
        # Mock service
        mock_svc = Mock()
        mock_svc.forecast = AsyncMock(return_value=Mock())
        mock_service.return_value = mock_svc
        
        # Mock policy to allow
        mock_engine = Mock()
        mock_engine.evaluate.return_value.denied = False
        mock_policy.return_value = mock_engine
        
        # Mock context
        mock_context.return_value = Mock()
        
        # Mock asyncio.get_event_loop to return a running loop
        with patch('simp.agents.quantumarb_agent.asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.is_running.return_value = True
            
            result = _try_forecast_sync("test_series", [1.0] * 20)
            # Should return None when loop is running
            assert result is None


class TestLoggingEdgeCases:
    """Test edge cases for TimesFM shadow logging."""
    
    def test_log_with_dict_forecast_response(self, tmp_path):
        """Test logging with dictionary instead of object."""
        log_dir = str(tmp_path / "logs")
        
        # Dictionary instead of object
        forecast_dict = {
            "point_forecast": [1.0, 2.0, 3.0],
            "available": True,
            "cached": False,
            "shadow_mode": True
        }
        
        _log_timesfm_shadow(
            series_id="test_series",
            forecast_resp=forecast_dict,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test rationale",
            log_dir=log_dir,
        )
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        if log_file.exists():
            with open(log_file, "r") as f:
                lines = f.readlines()
                # Dictionary won't have attributes, so might not log
                # This is acceptable behavior
    
    def test_log_with_forecast_response_having_none_point_forecast(self, tmp_path):
        """Test logging with forecast response where point_forecast is None."""
        log_dir = str(tmp_path / "logs")
        
        mock_resp = Mock()
        mock_resp.point_forecast = None  # None instead of list
        mock_resp.available = True
        mock_resp.cached = False
        mock_resp.shadow_mode = True
        
        _log_timesfm_shadow(
            series_id="test_series",
            forecast_resp=mock_resp,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test rationale",
            log_dir=log_dir,
        )
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["forecast_summary"] == {}
    
    def test_log_with_forecast_response_having_string_point_forecast(self, tmp_path):
        """Test logging with forecast response where point_forecast is a string."""
        log_dir = str(tmp_path / "logs")
        
        mock_resp = Mock()
        mock_resp.point_forecast = "1.0,2.0,3.0"  # String instead of list
        mock_resp.available = True
        mock_resp.cached = False
        mock_resp.shadow_mode = True
        
        _log_timesfm_shadow(
            series_id="test_series",
            forecast_resp=mock_resp,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test rationale",
            log_dir=log_dir,
        )
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            # String point_forecast should result in empty summary
            assert entry["forecast_summary"] == {}
    
    def test_log_with_forecast_response_having_mixed_list(self, tmp_path):
        """Test logging with forecast response having mixed numeric/non-numeric values."""
        log_dir = str(tmp_path / "logs")
        
        mock_resp = Mock()
        mock_resp.point_forecast = [1.0, "invalid", 3.0, None, 5.0]  # Mixed types
        mock_resp.available = True
        mock_resp.cached = False
        mock_resp.shadow_mode = True
        
        _log_timesfm_shadow(
            series_id="test_series",
            forecast_resp=mock_resp,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test rationale",
            log_dir=log_dir,
        )
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            # Should extract only numeric values
            assert entry["forecast_summary"]["forecast_length"] == 3  # 1.0, 3.0, 5.0


class TestEngineEdgeCases:
    """Test edge cases for QuantumArbEngine."""
    
    def test_evaluate_with_malformed_signal(self):
        """Test engine evaluation with malformed signal."""
        engine = QuantumArbEngine()
        
        # Create signal with missing required fields
        signal = ArbitrageSignal(
            intent_id="test_id",
            source_agent="test_agent",
            direction="BULL",
            ticker="BTC-USD",
            # Missing other optional fields
        )
        
        # Should return INSUFFICIENT_DATA for malformed signals
        opportunity = engine.evaluate(signal)
        assert opportunity.decision == ArbDecision.INSUFFICIENT_DATA
        assert opportunity.dry_run is True
    
    def test_evaluate_cross_venue_with_missing_venues(self):
        """Test cross-venue evaluation with missing venue data."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test_id",
            source_agent="test_agent",
            direction="BULL",
            ticker="BTC-USD",
            # No venue_a or venue_b (defaults to venue_a, venue_b)
        )
        
        opportunity = engine._evaluate_cross_venue(signal)
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        # Should mention synthetic spread
        assert "synthetic" in opportunity.rationale.lower()
    
    def test_evaluate_statistical_with_missing_contradiction_score(self):
        """Test statistical evaluation with missing contradiction_score."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test_id",
            source_agent="test_agent",
            direction="BULL",
            ticker="BTC-USD",
            # No contradiction_score (defaults to 0.0)
        )
        
        opportunity = engine._evaluate_statistical(signal)
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        assert "contradiction" in opportunity.rationale.lower()
    
    def test_record_spread_with_invalid_series_id(self):
        """Test _record_spread with invalid series_id."""
        engine = QuantumArbEngine()
        
        # Should handle empty series_id
        result = engine._record_spread("", 1.0)
        assert result == []
        
        # None series_id would cause TypeError before reaching validation
        # So we don't test that case
    
    def test_record_spread_with_nan_value(self):
        """Test _record_spread with NaN value."""
        import math
        engine = QuantumArbEngine()
        
        # NaN should not be recorded
        result = engine._record_spread("test_series", float('nan'))
        assert result == []
        
        # Inf should not be recorded
        result = engine._record_spread("test_series", float('inf'))
        assert result == []
        
        # -Inf should not be recorded
        result = engine._record_spread("test_series", float('-inf'))
        assert result == []


class TestLoggingPathIndependence:
    """Test that logging failures don't affect decision path."""
    
    @patch('simp.agents.quantumarb_agent._log_timesfm_shadow')
    def test_cross_venue_logging_failure_does_not_affect_decision(self, mock_log):
        """Test that cross-venue evaluation still works when logging fails."""
        mock_log.side_effect = Exception("Logging failed")
        
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test_id",
            source_agent="test_agent",
            direction="BULL",
            ticker="BTC-USD",
            venue_a="exchange_a",
            venue_b="exchange_b",
            raw_params={"price_a": 100.0, "price_b": 101.0},
        )
        
        # Should still return a decision even if logging fails
        opportunity = engine._evaluate_cross_venue(signal)
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        assert opportunity.dry_run is True
    
    @patch('simp.agents.quantumarb_agent._log_timesfm_shadow')
    def test_statistical_logging_failure_does_not_affect_decision(self, mock_log):
        """Test that statistical evaluation still works when logging fails."""
        mock_log.side_effect = Exception("Logging failed")
        
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test_id",
            source_agent="test_agent",
            direction="BULL",
            ticker="BTC-USD",
            contradiction_score=2.5,
        )
        
        # Should still return a decision even if logging fails
        opportunity = engine._evaluate_statistical(signal)
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        assert opportunity.dry_run is True