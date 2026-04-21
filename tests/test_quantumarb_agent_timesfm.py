"""
Tests for QuantumArb TimesFM shadow mode integration.
Verifies that TimesFM usage is shadow-only and doesn't change decisions.
"""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
from pathlib import Path

from simp.agents.quantumarb_agent import (
    QuantumArbEngine,
    ArbitrageSignal,
    ArbDecision,
    ArbType,
    _try_forecast_sync,
    AGENT_ID,
)


class TestTimesFMShadowMode:
    """Test TimesFM integration in QuantumArb agent."""
    
    def test_timesfm_shadow_mode_does_not_change_decisions(self):
        """Verify that TimesFM forecasts (even if available) don't change ArbDecision."""
        engine = QuantumArbEngine()
        
        # Create a test signal
        signal = ArbitrageSignal(
            intent_id="test-123",
            source_agent="bullbear_predictor",
            direction="BULL",
            delta=0.05,
            trust=0.8,
            contradiction_score=0.3,
            ticker="BTC/USD",
            venue_a="coinbase",
            venue_b="binance",
        )
        
        # Mock _try_forecast_sync to return a forecast response
        with patch('simp.agents.quantumarb_agent._try_forecast_sync') as mock_forecast:
            with patch('simp.agents.quantumarb_agent._log_timesfm_shadow') as mock_log:
                # Create a mock forecast response - in shadow mode, available should be False
                mock_response = Mock()
                mock_response.available = False  # Shadow mode makes available=False
                mock_response.shadow_mode = True  # Shadow mode active
                mock_response.point_forecast = [0.06, 0.07, 0.08, 0.09]
                mock_response.cached = False
                mock_forecast.return_value = mock_response
                
                # Evaluate the signal
                opportunity = engine.evaluate(signal)
                
                # Verify decision is still NO_OPPORTUNITY (not changed by TimesFM)
                assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
                assert opportunity.dry_run is True  # Always True
                
                # Verify TimesFM rationale is included
                assert "TimesFM" in opportunity.rationale
                assert "shadow mode" in opportunity.rationale.lower()
                
                # Verify logging was called (for cross-venue evaluation)
                assert mock_log.called
    
    def test_timesfm_unavailable_fallback(self):
        """Verify that when TimesFM is unavailable, evaluation still works."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test-456",
            source_agent="bullbear_predictor",
            direction="BEAR",
            delta=-0.03,
            trust=0.9,
            contradiction_score=0.4,
            ticker="ETH/USD",
        )
        
        # Mock _try_forecast_sync to return None (unavailable)
        with patch('simp.agents.quantumarb_agent._try_forecast_sync', return_value=None):
            opportunity = engine.evaluate(signal)
            
            # Should still work without TimesFM
            assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
            assert opportunity.dry_run is True
            assert "TimesFM" not in opportunity.rationale
    
    def test_try_forecast_sync_with_insufficient_data(self):
        """Test _try_forecast_sync with insufficient historical data."""
        # With less than 16 values, should return None
        result = _try_forecast_sync(
            series_id="test:series",
            values=[1.0, 2.0, 3.0],  # Only 3 values
            agent_id=AGENT_ID,
            horizon=16,
        )
        assert result is None
    
    def test_try_forecast_sync_policy_denied(self):
        """Test _try_forecast_sync when policy engine denies."""
        # Mock the imports inside _try_forecast_sync
        with patch('simp.integrations.timesfm_service.get_timesfm_service_sync') as mock_svc:
            with patch('simp.integrations.timesfm_policy_engine.PolicyEngine') as mock_engine:
                with patch('simp.integrations.timesfm_policy_engine.make_agent_context_for') as mock_context:
                    # Mock policy engine to deny
                    mock_decision = Mock()
                    mock_decision.denied = True
                    mock_decision.reason = "Test policy denial"
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    result = _try_forecast_sync(
                        series_id="test:series",
                        values=[1.0] * 20,  # Enough values
                        agent_id=AGENT_ID,
                        horizon=16,
                    )
                    
                    # Should return None when policy denies
                    assert result is None
    
    def test_cross_venue_timesfm_integration(self, tmp_path):
        """Test cross-venue evaluation with TimesFM integration."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test-789",
            source_agent="bullbear_predictor",
            direction="BULL",
            delta=0.05,
            trust=0.85,
            contradiction_score=0.2,
            ticker="SOL/USD",
            venue_a="kraken",
            venue_b="ftx",
        )
        
        with patch('simp.agents.quantumarb_agent._try_forecast_sync') as mock_forecast:
            with patch('simp.agents.quantumarb_agent._log_timesfm_shadow') as mock_log:
                mock_response = Mock()
                mock_response.available = False  # Shadow mode makes available=False
                mock_response.shadow_mode = True
                mock_response.point_forecast = [0.06, 0.07]
                mock_response.cached = False
                mock_forecast.return_value = mock_response
                
                opportunity = engine._evaluate_cross_venue(signal)
                
                # Verify core properties
                assert opportunity.arb_type == ArbType.CROSS_VENUE
                assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
                assert opportunity.dry_run is True
                assert opportunity.ticker == "SOL/USD"
                assert opportunity.venue_a == "kraken"
                assert opportunity.venue_b == "ftx"
                
                # TimesFM should be mentioned in rationale
                assert "TimesFM" in opportunity.rationale
                
                # Verify logging was called
                mock_log.assert_called_once()
                call_args = mock_log.call_args[1]
                assert call_args["series_id"] == "SOL/USD:kraken_vs_ftx:spread_bps"
                assert call_args["decision"] == ArbDecision.NO_OPPORTUNITY
                assert call_args["forecast_resp"] == mock_response
    
    def test_statistical_arb_timesfm_integration(self):
        """Test statistical arb evaluation with TimesFM integration."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="test-101",
            source_agent="bullbear_predictor",
            direction="BEAR",
            delta=-0.02,
            trust=0.75,
            contradiction_score=0.6,  # High contradiction
            ticker="ADA/USD",
        )
        
        with patch('simp.agents.quantumarb_agent._try_forecast_sync') as mock_forecast:
            with patch('simp.agents.quantumarb_agent._log_timesfm_shadow') as mock_log:
                mock_response = Mock()
                mock_response.available = False  # Shadow mode
                mock_response.shadow_mode = True
                mock_response.point_forecast = [-0.01, 0.0, 0.01, 0.02]  # Sign flip
                mock_response.cached = False
                mock_forecast.return_value = mock_response
                
                opportunity = engine._evaluate_statistical(signal)
                
                # Verify core properties
                assert opportunity.arb_type == ArbType.STATISTICAL
                assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
                assert opportunity.dry_run is True
                assert opportunity.ticker == "ADA/USD"
                
                # TimesFM should be mentioned
                assert "TimesFM" in opportunity.rationale
                
                # Verify logging was called
                mock_log.assert_called_once()
                call_args = mock_log.call_args[1]
                assert call_args["series_id"] == "ADA/USD:stat_delta"
                assert call_args["decision"] == ArbDecision.NO_OPPORTUNITY
                assert call_args["forecast_resp"] == mock_response


class TestTimesFMShadowLog:
    """Test the dedicated TimesFM shadow logging."""
    
    def test_timesfm_shadow_log_creation(self, tmp_path):
        """Test that TimesFM shadow logs are created."""
        from simp.agents.quantumarb_agent import _log_timesfm_shadow
        
        # Create a mock forecast response
        mock_response = Mock()
        mock_response.shadow_mode = True
        mock_response.available = False
        mock_response.cached = False
        mock_response.point_forecast = [1.0, 2.0, 3.0]
        
        # Call logging function
        _log_timesfm_shadow(
            series_id="test:series",
            forecast_resp=mock_response,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Test rationale",
            log_dir=str(tmp_path),
        )
        
        # Check log file was created
        log_file = tmp_path / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        # Read and parse log entry
        with open(log_file, "r") as f:
            entry = json.loads(f.readline())
        
        # Verify entry structure
        assert entry["series_id"] == "test:series"
        assert entry["decision"] == "NO_OPPORTUNITY"
        assert entry["shadow_mode"] is True
        assert entry["forecast_available"] is False
        assert entry["forecast_cached"] is False
        assert "forecast_summary" in entry
        assert "rationale_preview" in entry
    
    def test_log_format_with_forecast_data(self, tmp_path):
        """Test log format with actual forecast data."""
        from simp.agents.quantumarb_agent import _log_timesfm_shadow
        
        # Create a mock forecast response with point forecast
        mock_response = Mock()
        mock_response.shadow_mode = True
        mock_response.available = True  # Available in shadow mode (for testing)
        mock_response.cached = False
        mock_response.point_forecast = [1.0, 2.0, 3.0, 4.0, 5.0]  # Upward trend
        
        _log_timesfm_shadow(
            series_id="BTC/USD:coinbase_vs_binance:spread_bps",
            forecast_resp=mock_response,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Cross-venue spread analysis with TimesFM forecast",
            log_dir=str(tmp_path),
        )
        
        log_file = tmp_path / "timesfm_shadow_log.jsonl"
        with open(log_file, "r") as f:
            entry = json.loads(f.readline())
        
        # Verify forecast summary
        summary = entry["forecast_summary"]
        assert summary["forecast_length"] == 5
        assert summary["forecast_mean"] == 3.0  # (1+2+3+4+5)/5
        assert summary["forecast_min"] == 1.0
        assert summary["forecast_max"] == 5.0
        assert summary["forecast_trend"] == "up"  # 5.0 > 1.0
    
    def test_logging_exception_handling(self):
        """Test that logging exceptions don't break the agent."""
        from simp.agents.quantumarb_agent import _log_timesfm_shadow
        
        # Mock Path to raise exception
        with patch('simp.agents.quantumarb_agent.Path') as mock_path:
            mock_path.return_value.mkdir.side_effect = Exception("Test error")
            
            # Should not raise
            _log_timesfm_shadow(
                series_id="test:series",
                forecast_resp=Mock(),
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale="Test",
            )
            
            # Exception should be caught and logged (we can't easily test the log call)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])