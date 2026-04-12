"""
Test structured logging for QuantumArb TimesFM shadow mode.
Verifies that logs contain all necessary context for reconstructing decisions.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

import pytest

from simp.agents.quantumarb_agent import (
    _log_timesfm_shadow,
    ArbitrageSignal,
    QuantumArbEngine,
    ArbDecision,
)


class TestStructuredLogging:
    """Test that QuantumArb logs contain all necessary context."""
    
    def test_log_contains_all_context_fields(self, tmp_path):
        """Test that log entries contain all required context fields."""
        log_dir = str(tmp_path / "logs")
        
        # Create a mock forecast response
        mock_resp = Mock()
        mock_resp.point_forecast = [100.0, 101.0, 102.0]
        mock_resp.shadow_mode = True
        mock_resp.available = True
        mock_resp.cached = False
        
        # Call logging function with all context
        _log_timesfm_shadow(
            series_id="test_series_001",
            forecast_resp=mock_resp,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test rationale for structured logging",
            log_dir=log_dir,
            intent_id="test_intent_123",
            ticker="BTC-USD",
            direction="BULL",
            quantity=1.5,
            arb_type="cross_venue",
        )
        
        # Verify log file exists and contains entry
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            
            # Verify all context fields are present
            assert "timestamp" in entry
            assert entry["series_id"] == "test_series_001"
            assert entry["decision"] == "NO_OPPORTUNITY"
            assert entry["shadow_mode"] is True
            assert entry["forecast_available"] is True
            assert entry["forecast_cached"] is False
            assert "forecast_summary" in entry
            assert "rationale_preview" in entry
            
            # Verify new context fields
            assert entry["intent_id"] == "test_intent_123"
            assert entry["ticker"] == "BTC-USD"
            assert entry["direction"] == "BULL"
            assert entry["quantity"] == 1.5
            assert entry["arb_type"] == "cross_venue"
            
            # Verify forecast summary was calculated
            summary = entry["forecast_summary"]
            assert summary["forecast_length"] == 3
            assert summary["forecast_mean"] == pytest.approx(101.0)
            assert summary["forecast_min"] == 100.0
            assert summary["forecast_max"] == 102.0
            assert summary["forecast_trend"] == "up"
    
    def test_log_with_missing_optional_fields(self, tmp_path):
        """Test logging when optional context fields are None."""
        log_dir = str(tmp_path / "logs")
        
        mock_resp = Mock()
        mock_resp.point_forecast = []
        mock_resp.shadow_mode = True
        mock_resp.available = False
        mock_resp.cached = False
        
        # Call with only required fields
        _log_timesfm_shadow(
            series_id="test_series_002",
            forecast_resp=mock_resp,
            decision=ArbDecision.INSUFFICIENT_DATA,
            rationale="Missing data test",
            log_dir=log_dir,
            # Optional fields omitted (should be None in log)
        )
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, "r") as f:
            entry = json.loads(f.readline())
            
            # Verify optional fields are None
            assert entry["intent_id"] is None
            assert entry["ticker"] is None
            assert entry["direction"] is None
            assert entry["quantity"] is None
            assert entry["arb_type"] is None
            
            # Verify forecast summary is empty
            assert entry["forecast_summary"] == {}
    
    def test_log_format_stability_for_parsing(self, tmp_path):
        """Test that log format is stable enough for downstream parsing."""
        log_dir = str(tmp_path / "logs")
        
        mock_resp = Mock()
        mock_resp.point_forecast = [50.0, 51.0, 52.0, 53.0, 54.0]
        mock_resp.shadow_mode = True
        mock_resp.available = True
        mock_resp.cached = True
        
        # Generate multiple log entries
        for i in range(3):
            _log_timesfm_shadow(
                series_id=f"series_{i}",
                forecast_resp=mock_resp,
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale=f"Test rationale {i}",
                log_dir=log_dir,
                intent_id=f"intent_{i}",
                ticker=f"ASSET-{i}",
                direction="BULL" if i % 2 == 0 else "BEAR",
                quantity=float(i + 1),
                arb_type="statistical" if i % 2 == 0 else "cross_venue",
            )
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        # Verify all entries have consistent structure
        with open(log_file, "r") as f:
            for i, line in enumerate(f):
                entry = json.loads(line)
                
                # All entries should have the same set of keys
                expected_keys = {
                    "timestamp", "series_id", "decision", "shadow_mode",
                    "forecast_available", "forecast_cached", "forecast_summary",
                    "rationale_preview", "intent_id", "ticker", "direction",
                    "quantity", "arb_type"
                }
                assert set(entry.keys()) == expected_keys
                
                # Verify data types are consistent
                assert isinstance(entry["timestamp"], str)
                assert isinstance(entry["series_id"], str)
                assert isinstance(entry["decision"], str)
                assert isinstance(entry["shadow_mode"], bool)
                assert isinstance(entry["forecast_available"], bool)
                assert isinstance(entry["forecast_cached"], bool)
                assert isinstance(entry["forecast_summary"], dict)
                assert isinstance(entry["rationale_preview"], str)
                assert entry["intent_id"] is None or isinstance(entry["intent_id"], str)
                assert entry["ticker"] is None or isinstance(entry["ticker"], str)
                assert entry["direction"] is None or isinstance(entry["direction"], str)
                assert entry["quantity"] is None or isinstance(entry["quantity"], (int, float))
                assert entry["arb_type"] is None or isinstance(entry["arb_type"], str)
    
    def test_log_reconstructs_decision_context(self, tmp_path):
        """Test that logs contain enough information to reconstruct decision context."""
        log_dir = str(tmp_path / "logs")
        
        # Simulate a realistic scenario
        mock_resp = Mock()
        mock_resp.point_forecast = [100.0, 101.0, 102.0, 101.5, 101.0]
        mock_resp.shadow_mode = True
        mock_resp.available = True
        mock_resp.cached = False
        
        _log_timesfm_shadow(
            series_id="BTC-USD_cross_venue_20240320",
            forecast_resp=mock_resp,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Cross-venue spread 2.5 bps insufficient after fees. TimesFM forecast shows mean reversion likely.",
            log_dir=log_dir,
            intent_id="arb_eval_001",
            ticker="BTC-USD",
            direction="BULL",
            quantity=0.5,
            arb_type="cross_venue",
        )
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        with open(log_file, "r") as f:
            entry = json.loads(f.readline())
            
            # Verify we can reconstruct the decision context
            reconstructed_context = {
                "intent": entry["intent_id"],
                "asset": entry["ticker"],
                "side": entry["direction"],
                "size": entry["quantity"],
                "arb_type": entry["arb_type"],
                "decision": entry["decision"],
                "timesfm_available": entry["forecast_available"],
                "timesfm_cached": entry["forecast_cached"],
                "forecast_summary": entry["forecast_summary"],
                "rationale": entry["rationale_preview"],
            }
            
            assert reconstructed_context["intent"] == "arb_eval_001"
            assert reconstructed_context["asset"] == "BTC-USD"
            assert reconstructed_context["side"] == "BULL"
            assert reconstructed_context["size"] == 0.5
            assert reconstructed_context["arb_type"] == "cross_venue"
            assert reconstructed_context["decision"] == "NO_OPPORTUNITY"
            assert reconstructed_context["timesfm_available"] is True
            assert reconstructed_context["timesfm_cached"] is False
            
            # Verify forecast summary provides useful information
            summary = reconstructed_context["forecast_summary"]
            assert summary["forecast_length"] == 5
            assert summary["forecast_trend"] in ["up", "down", "flat"]
            
            # Verify rationale contains key information
            rationale = reconstructed_context["rationale"]
            assert "cross-venue" in rationale.lower()
            assert "bps" in rationale.lower()
            assert "timesfm" in rationale.lower()
    
    @patch('simp.agents.quantumarb_agent._log_timesfm_shadow')
    def test_cross_venue_evaluation_logs_context(self, mock_log, tmp_path):
        """Test that cross-venue evaluation includes context in logs."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test_cross_venue_intent",
            source_agent="test_agent",
            direction="BULL",
            ticker="ETH-USD",
            venue_a="exchange_a",
            venue_b="exchange_b",
            raw_params={"price_a": 100.0, "price_b": 101.0},
        )
        
        # Mock the forecast response
        mock_forecast = Mock()
        mock_forecast.point_forecast = [100.5, 101.0, 101.5]
        mock_forecast.shadow_mode = True
        mock_forecast.available = True
        mock_forecast.cached = False
        
        with patch('simp.agents.quantumarb_agent._try_forecast_sync', return_value=mock_forecast):
            opportunity = engine._evaluate_cross_venue(signal)
        
        # Verify log was called with correct context
        assert mock_log.called
        call_kwargs = mock_log.call_args[1]
        
        assert call_kwargs["intent_id"] == "test_cross_venue_intent"
        assert call_kwargs["ticker"] == "ETH-USD"
        assert call_kwargs["direction"] == "BULL"
        assert call_kwargs["arb_type"] == "cross_venue"
        assert call_kwargs["decision"] == ArbDecision.NO_OPPORTUNITY
    
    @patch('simp.agents.quantumarb_agent._log_timesfm_shadow')
    def test_statistical_evaluation_logs_context(self, mock_log, tmp_path):
        """Test that statistical evaluation includes context in logs."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test_statistical_intent",
            source_agent="test_agent",
            direction="BEAR",
            ticker="SOL-USD",
            contradiction_score=3.5,
        )
        
        # Mock the forecast response
        mock_forecast = Mock()
        mock_forecast.point_forecast = [95.0, 94.0, 93.0]
        mock_forecast.shadow_mode = True
        mock_forecast.available = True
        mock_forecast.cached = True
        
        with patch('simp.agents.quantumarb_agent._try_forecast_sync', return_value=mock_forecast):
            opportunity = engine._evaluate_statistical(signal)
        
        # Verify log was called with correct context
        assert mock_log.called
        call_kwargs = mock_log.call_args[1]
        
        assert call_kwargs["intent_id"] == "test_statistical_intent"
        assert call_kwargs["ticker"] == "SOL-USD"
        assert call_kwargs["direction"] == "BEAR"
        assert call_kwargs["arb_type"] == "statistical"
        assert call_kwargs["decision"] == ArbDecision.NO_OPPORTUNITY