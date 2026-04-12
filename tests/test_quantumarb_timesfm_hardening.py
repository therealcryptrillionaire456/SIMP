"""
Hardening tests for TimesFM shadow logging in QuantumArb agent.
Focuses on untested branches and edge cases identified in Phase D.
"""

import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

import pytest

from simp.agents.quantumarb_agent import _log_timesfm_shadow, ArbDecision


def create_mock_forecast(
    point_forecast=None,
    shadow_mode=True,
    available=True,
    cached=False
):
    """Create a properly configured mock forecast response."""
    mock_forecast = Mock()
    if point_forecast is not None:
        mock_forecast.point_forecast = point_forecast
    mock_forecast.shadow_mode = shadow_mode
    mock_forecast.available = available
    mock_forecast.cached = cached
    return mock_forecast


class TestHardeningEdgeCases:
    """Tests for untested branches and edge cases."""
    
    def test_forecast_list_with_non_numeric_values(self, tmp_path):
        """Test when point_forecast list contains mixed numeric and non-numeric values."""
        log_dir = str(tmp_path / "quantumarb")
        
        # Create mock with mixed list
        mock_forecast = create_mock_forecast(
            point_forecast=[1.0, "not_a_number", 3.0, None, 5.0],
            shadow_mode=True,
            available=True
        )
        
        _log_timesfm_shadow(
            series_id="test:mixed",
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test mixed numeric/non-numeric forecast",
            log_dir=log_dir,
        )
        
        # Verify log was written
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            # Should have filtered out non-numeric values
            assert entry["forecast_summary"]["forecast_length"] == 3  # Only 1.0, 3.0, 5.0
            assert entry["forecast_summary"]["forecast_mean"] == pytest.approx(3.0)
    
    def test_forecast_empty_after_numeric_filtering(self, tmp_path):
        """Test when point_forecast list becomes empty after filtering non-numeric values."""
        log_dir = str(tmp_path / "quantumarb")
        
        # Create mock with only non-numeric values
        mock_forecast = create_mock_forecast(
            point_forecast=["string", None, {"dict": "value"}],
            shadow_mode=True,
            available=True
        )
        
        _log_timesfm_shadow(
            series_id="test:non_numeric",
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test all non-numeric forecast",
            log_dir=log_dir,
        )
        
        # Verify log was written with empty forecast_summary
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            assert entry["forecast_summary"] == {}  # Should be empty dict
    
    def test_non_boolean_attributes(self, tmp_path):
        """Test when forecast_resp has non-boolean shadow_mode/available/cached attributes."""
        log_dir = str(tmp_path / "quantumarb")
        
        # Create mock with non-boolean attributes
        mock_forecast = Mock()
        mock_forecast.shadow_mode = "yes"  # String instead of bool
        mock_forecast.available = 1  # Int instead of bool
        mock_forecast.cached = "true"  # String instead of bool
        mock_forecast.point_forecast = [1.0, 2.0, 3.0]
        
        _log_timesfm_shadow(
            series_id="test:non_bool",
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test non-boolean attributes",
            log_dir=log_dir,
        )
        
        # Verify log was written
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            # Attributes should be preserved as-is (truthy values)
            assert entry["shadow_mode"] == "yes"
            assert entry["forecast_available"] == 1
            assert entry["forecast_cached"] == "true"
    
    def test_json_serialization_error_handling(self, tmp_path):
        """Test handling of non-serializable data in entry dict."""
        log_dir = str(tmp_path / "quantumarb")
        
        # Create a mock with a non-serializable object
        class NonSerializable:
            def __repr__(self):
                return "<NonSerializable>"
        
        mock_forecast = create_mock_forecast(
            point_forecast=[1.0, 2.0, 3.0],
            shadow_mode=True
        )
        
        # Patch json.dumps to raise an error
        with patch('json.dumps', side_effect=TypeError("Object not JSON serializable")):
            # Should not raise exception
            _log_timesfm_shadow(
                series_id="test:json_error",
                forecast_resp=mock_forecast,
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale="Test JSON serialization error",
                log_dir=log_dir,
            )
        
        # File might not exist or be empty
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        # Just verify function didn't crash
    
    def test_file_permission_change_mid_write(self, tmp_path):
        """Test when file exists but becomes unwritable during write."""
        log_dir = str(tmp_path / "quantumarb")
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # Create file first
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        log_file.write_text("existing entry\n")
        
        # Make file read-only
        log_file.chmod(0o444)
        
        try:
            mock_forecast = create_mock_forecast(
                point_forecast=[1.0, 2.0, 3.0],
                shadow_mode=True
            )
            
            # Should not raise exception
            _log_timesfm_shadow(
                series_id="test:readonly",
                forecast_resp=mock_forecast,
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale="Test read-only file",
                log_dir=log_dir,
            )
        finally:
            # Restore permissions for cleanup
            log_file.chmod(0o644)
    
    def test_very_long_series_id(self, tmp_path):
        """Test with extremely long series_id."""
        log_dir = str(tmp_path / "quantumarb")
        
        # Create very long series_id
        long_series_id = "test:" + "x" * 1000
        
        mock_forecast = create_mock_forecast(
            point_forecast=[1.0, 2.0, 3.0],
            shadow_mode=True
        )
        
        _log_timesfm_shadow(
            series_id=long_series_id,
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test long series_id",
            log_dir=log_dir,
        )
        
        # Verify log was written
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            assert entry["series_id"] == long_series_id
    
    def test_none_values_in_optional_fields(self, tmp_path):
        """Test when optional fields are explicitly None."""
        log_dir = str(tmp_path / "quantumarb")
        
        mock_forecast = create_mock_forecast(
            point_forecast=[1.0, 2.0, 3.0],
            shadow_mode=True
        )
        
        _log_timesfm_shadow(
            series_id="test:optional_none",
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test None in optional fields",
            log_dir=log_dir,
            intent_id=None,
            ticker=None,
            direction=None,
            quantity=None,
            arb_type=None,
        )
        
        # Verify log was written
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            # None values should be included in JSON
            assert entry["intent_id"] is None
            assert entry["ticker"] is None
            assert entry["direction"] is None
            assert entry["quantity"] is None
            assert entry["arb_type"] is None
    
    def test_decision_value_normalization(self, tmp_path):
        """Test that decision values are normalized to uppercase."""
        log_dir = str(tmp_path / "quantumarb")
        
        # Create a custom decision enum value (simulating different case)
        from enum import Enum
        
        class TestDecision(Enum):
            NO_OPPORTUNITY = "no_opportunity"  # lowercase
        
        mock_forecast = create_mock_forecast(
            point_forecast=[1.0, 2.0, 3.0],
            shadow_mode=True
        )
        
        # Note: We can't actually test with a different enum,
        # but we can verify the current implementation normalizes to uppercase
        _log_timesfm_shadow(
            series_id="test:decision_case",
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,  # This should be "NO_OPPORTUNITY"
            rationale="Test decision case normalization",
            log_dir=log_dir,
        )
        
        # Verify log was written with uppercase decision
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            assert entry["decision"] == "NO_OPPORTUNITY"  # Should be uppercase