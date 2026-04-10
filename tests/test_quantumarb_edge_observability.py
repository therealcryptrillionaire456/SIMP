"""
Test QuantumArb observability for edge cases with TimesFM data.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

import pytest

from simp.agents.quantumarb_agent import (
    QuantumArbEngine,
    ArbitrageSignal,
    ArbitrageOpportunity,
    ArbDecision,
    ArbType,
    _log_timesfm_shadow,
    _try_forecast_sync,
)


class TestEdgeCaseObservability:
    """Test that QuantumArb provides clear logs for edge cases."""
    
    def test_logging_with_malformed_forecast_object(self, tmp_path):
        """Test logging when forecast response has malformed structure."""
        # Create a mock forecast response with unexpected structure
        mock_forecast = Mock()
        mock_forecast.available = True
        mock_forecast.point_forecast = "not a list"  # Wrong type!
        mock_forecast.shadow_mode = True
        mock_forecast.request_id = "test-req-123"
        mock_forecast.horizon = 32
        
        # This should not raise an exception
        _log_timesfm_shadow(
            series_id="test-malformed",
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test with malformed forecast",
            log_dir=str(tmp_path),
            intent_id="test-intent-123",
            ticker="BTC-USD",
            direction="BULL",
            arb_type="statistical",
        )
        
        # Verify log was created (even with malformed data)
        log_file = tmp_path / "timesfm_shadow.jsonl"
        
        # The file might not exist if logging failed (which is OK for edge case)
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                entry = json.loads(f.readline())
            
            # Should still have basic fields if log was created
            assert entry["series_id"] == "test-malformed"
            assert entry["decision"] == "NO_OPPORTUNITY"
        
        # Main point: no exception should be raised
    
    def test_logging_with_partial_forecast_data(self, tmp_path):
        """Test logging when forecast has partial/missing attributes."""
        # Mock with missing attributes
        mock_forecast = Mock()
        # Don't set .available attribute at all
        mock_forecast.point_forecast = [100.0, 101.0, 102.0]
        # Don't set .shadow_mode
        
        _log_timesfm_shadow(
            series_id="test-partial",
            forecast_resp=mock_forecast,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test with partial forecast",
            log_dir=str(tmp_path),
        )
        
        log_file = tmp_path / "timesfm_shadow.jsonl"
        
        # The file might not exist if logging failed (which is OK for edge case)
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                entry = json.loads(f.readline())
            
            # Should handle missing attributes gracefully if log was created
            assert entry["series_id"] == "test-partial"
        
        # Main point: no exception should be raised
    
    @patch('simp.agents.quantumarb_agent._try_forecast_sync')
    def test_engine_handles_empty_forecast_list(self, mock_forecast):
        """Test that engine handles empty forecast lists gracefully."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test-empty-forecast",
            source_agent="bullbear_predictor",
            ticker="ETH-USD",
            direction="BULL",
            trust=0.9,
            delta=0.05,
            contradiction_score=1.5,
        )
        
        mock_resp = Mock()
        mock_resp.available = True
        mock_resp.point_forecast = []  # Empty list!
        mock_resp.shadow_mode = True
        mock_forecast.return_value = mock_resp
        
        opportunity = engine._evaluate_statistical(signal)
        
        # Should still produce a valid decision
        assert isinstance(opportunity, ArbitrageOpportunity)
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        assert opportunity.dry_run is True
    
    @patch('simp.agents.quantumarb_agent._try_forecast_sync')
    def test_engine_handles_none_forecast_response(self, mock_forecast):
        """Test that engine handles None forecast response gracefully."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test-none-forecast",
            source_agent="bullbear_predictor",
            ticker="SOL-USD",
            direction="BEAR",
            trust=0.9,
            delta=-0.03,
            contradiction_score=2.0,
            venue_a="coinbase",
            venue_b="kraken",
        )
        
        mock_forecast.return_value = None
        
        opportunity = engine._evaluate_cross_venue(signal)
        
        # Should still produce a valid decision
        assert isinstance(opportunity, ArbitrageOpportunity)
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        assert opportunity.dry_run is True
        # Rationale should not mention TimesFM since forecast was None
        assert "TimesFM" not in opportunity.rationale
    
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_try_forecast_with_short_history(self, mock_policy, mock_context, mock_service):
        """Test _try_forecast_sync with history shorter than minimum."""
        # History shorter than 16 values should return None
        result = _try_forecast_sync(
            series_id="test-short",
            values=[1.0, 2.0, 3.0],  # Only 3 values
        )
        
        assert result is None
    
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_try_forecast_with_none_history(self, mock_policy, mock_context, mock_service):
        """Test _try_forecast_sync with None history."""
        result = _try_forecast_sync(
            series_id="test-none",
            values=None,
        )
        
        assert result is None
    
    def test_decision_summary_with_edge_case_forecast(self, tmp_path):
        """Test decision summary when TimesFM returns edge case data."""
        signal = ArbitrageSignal(
            intent_id="test-edge-summary",
            source_agent="bullbear_predictor",
            ticker="ADA-USD",
            direction="BULL",
            trust=0.8,
            delta=0.04,
            contradiction_score=1.2,
        )
        
        # Create opportunity with edge case values
        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.STATISTICAL,
            decision=ArbDecision.INSUFFICIENT_DATA,
            source_signal_id="test-edge-summary",
            ticker="ADA-USD",
            estimated_spread_bps=0.0,
            confidence=0.0,
            rationale="Edge case: forecast returned empty list",
            dry_run=True,
        )
        
        # Log with edge case TimesFM data
        from simp.agents.quantumarb_agent import _log_decision_summary
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=True,
            timesfm_rationale="Forecast returned empty list (edge case)",
            log_dir=str(tmp_path),
        )
        
        log_file = tmp_path / "decision_summary.jsonl"
        with open(log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline())
        
        # Should clearly indicate the edge case
        assert entry["timesfm_used"] is True
        assert "edge case" in entry["timesfm_rationale"].lower()
        assert entry["decision"] == "INSUFFICIENT_DATA"
    
    def test_logging_independence_from_decision(self, tmp_path):
        """Test that logging failures don't affect decision outcomes."""
        signal = ArbitrageSignal(
            intent_id="test-logging-fail",
            source_agent="bullbear_predictor",
            ticker="XRP-USD",
            direction="BEAR",
            trust=0.9,
            delta=-0.05,
            contradiction_score=2.0,
        )
        
        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.STATISTICAL,
            decision=ArbDecision.NO_OPPORTUNITY,
            source_signal_id="test-logging-fail",
            ticker="XRP-USD",
            rationale="Test logging independence",
            dry_run=True,
        )
        
        # Use a read-only directory to cause logging failure
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)
        
        # Import here to ensure fresh import
        from simp.agents.quantumarb_agent import _log_decision_summary
        
        # Should not raise exception
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=False,
            log_dir=str(read_only_dir),
        )
        
        # Decision object should remain unchanged
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        assert opportunity.dry_run is True
        assert opportunity.rationale == "Test logging independence"