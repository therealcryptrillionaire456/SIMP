"""
Integration scenario tests for QuantumArb.
Tests unusual but valid forecast shapes and cross-agent compatibility.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import pytest

from simp.agents.quantumarb_agent import (
    QuantumArbEngine,
    ArbitrageSignal,
    ArbDecision,
    _try_forecast_sync,
    _log_timesfm_shadow,
)


class TestUnusualForecastShapes:
    """Test QuantumArb handling of unusual but valid forecast shapes."""
    
    @pytest.mark.skip(reason="TimesFM service integration test - outside QuantumArb scope")
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_forecast_with_single_value(self, mock_policy, mock_context, mock_service):
        """Test forecast with single value (valid but unusual)."""
        # Mock service returns forecast with single value
        mock_svc = Mock()
        mock_svc.forecast.return_value = Mock(
            point_forecast=[100.0],  # Single value
            shadow_mode=True,
            available=True,
            cached=False,
        )
        mock_service.return_value = mock_svc
        
        # Mock policy allows
        mock_policy_instance = Mock()
        mock_policy_instance.evaluate.return_value = Mock(
            allowed=True,
            reason="Allowed",
        )
        mock_policy.return_value = mock_policy_instance
        
        # Mock context
        mock_context.return_value = {"agent": "quantumarb"}
        
        result = _try_forecast_sync(
            series_id="test_single_value",
            values=[95.0, 96.0, 97.0, 98.0, 99.0],
        )
        
        assert result is not None
        assert result.point_forecast == [100.0]
        assert result.shadow_mode is True
        assert result.available is True
    
    @pytest.mark.skip(reason="TimesFM service integration test - outside QuantumArb scope")
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_forecast_with_identical_values(self, mock_policy, mock_context, mock_service):
        """Test forecast with identical values (flat forecast)."""
        # Mock service returns flat forecast
        mock_svc = Mock()
        mock_svc.forecast.return_value = Mock(
            point_forecast=[100.0, 100.0, 100.0, 100.0, 100.0],
            shadow_mode=True,
            available=True,
            cached=True,
        )
        mock_service.return_value = mock_svc
        
        # Mock policy allows
        mock_policy_instance = Mock()
        mock_policy_instance.evaluate.return_value = Mock(
            allowed=True,
            reason="Allowed",
        )
        mock_policy.return_value = mock_policy_instance
        
        # Mock context
        mock_context.return_value = {"agent": "quantumarb"}
        
        result = _try_forecast_sync(
            series_id="test_flat_forecast",
            values=[100.0, 100.0, 100.0, 100.0, 100.0],
        )
        
        assert result is not None
        assert len(result.point_forecast) == 5
        assert all(v == 100.0 for v in result.point_forecast)
        assert result.cached is True
    
    @pytest.mark.skip(reason="TimesFM service integration test - outside QuantumArb scope")
    @patch('simp.integrations.timesfm_service.get_timesfm_service_sync')
    @patch('simp.integrations.timesfm_policy_engine.make_agent_context_for')
    @patch('simp.integrations.timesfm_policy_engine.PolicyEngine')
    def test_forecast_with_very_long_history(self, mock_policy, mock_context, mock_service):
        """Test forecast with very long history (simulating accumulated data)."""
        # Create long history (more than typical)
        long_history = [float(i) for i in range(100)]
        
        # Mock service
        mock_svc = Mock()
        mock_svc.forecast.return_value = Mock(
            point_forecast=[float(i) for i in range(100, 110)],
            shadow_mode=True,
            available=True,
            cached=False,
        )
        mock_service.return_value = mock_svc
        
        # Mock policy allows
        mock_policy_instance = Mock()
        mock_policy_instance.evaluate.return_value = Mock(
            allowed=True,
            reason="Allowed",
        )
        mock_policy.return_value = mock_policy_instance
        
        # Mock context
        mock_context.return_value = {"agent": "quantumarb"}
        
        result = _try_forecast_sync(
            series_id="test_long_history",
            values=long_history,
        )
        
        assert result is not None
        assert len(result.point_forecast) == 10
        assert result.point_forecast[0] == 100.0
        assert result.point_forecast[-1] == 109.0
    
    def test_logging_with_unusual_forecast_shapes(self, tmp_path):
        """Test logging handles unusual forecast shapes correctly."""
        log_dir = str(tmp_path / "logs")
        
        # Test 1: Forecast with single value
        mock_resp1 = Mock()
        mock_resp1.point_forecast = [150.0]  # Single value
        mock_resp1.shadow_mode = True
        mock_resp1.available = True
        mock_resp1.cached = False
        
        _log_timesfm_shadow(
            series_id="single_value_forecast",
            forecast_resp=mock_resp1,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Single value forecast test",
            log_dir=log_dir,
        )
        
        # Test 2: Forecast with identical values
        mock_resp2 = Mock()
        mock_resp2.point_forecast = [200.0, 200.0, 200.0]
        mock_resp2.shadow_mode = True
        mock_resp2.available = True
        mock_resp2.cached = True
        
        _log_timesfm_shadow(
            series_id="flat_forecast",
            forecast_resp=mock_resp2,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Flat forecast test",
            log_dir=log_dir,
        )
        
        # Test 3: Forecast with alternating pattern
        mock_resp3 = Mock()
        mock_resp3.point_forecast = [100.0, 101.0, 100.0, 101.0, 100.0]
        mock_resp3.shadow_mode = True
        mock_resp3.available = True
        mock_resp3.cached = False
        
        _log_timesfm_shadow(
            series_id="alternating_forecast",
            forecast_resp=mock_resp3,
            decision=ArbDecision.NO_OPPORTUNITY,
            rationale="Alternating forecast test",
            log_dir=log_dir,
        )
        
        # Verify all logs were written correctly
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        assert log_file.exists()
        
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 3
            
            # Parse all entries
            entries = [json.loads(line) for line in lines]
            
            # Verify each entry has correct forecast summary
            for entry in entries:
                summary = entry["forecast_summary"]
                if entry["series_id"] == "single_value_forecast":
                    assert summary["forecast_length"] == 1
                    assert summary["forecast_mean"] == 150.0
                    assert summary["forecast_min"] == 150.0
                    assert summary["forecast_max"] == 150.0
                    assert summary["forecast_trend"] == "flat"  # Single value = flat
                elif entry["series_id"] == "flat_forecast":
                    assert summary["forecast_length"] == 3
                    assert summary["forecast_mean"] == 200.0
                    assert summary["forecast_min"] == 200.0
                    assert summary["forecast_max"] == 200.0
                    assert summary["forecast_trend"] == "flat"
                elif entry["series_id"] == "alternating_forecast":
                    assert summary["forecast_length"] == 5
                    assert summary["forecast_mean"] == pytest.approx(100.4)
                    assert summary["forecast_min"] == 100.0
                    assert summary["forecast_max"] == 101.0
                    assert summary["forecast_trend"] == "flat"  # first=100.0, last=100.0


class TestCrossAgentCompatibility:
    """Test QuantumArb compatibility with other agent patterns."""
    
    def test_handles_kashclaw_sized_order_context(self, tmp_path):
        """Test QuantumArb handles order sizes typical for KashClaw."""
        log_dir = str(tmp_path / "logs")
        
        # KashClaw typically works with larger quantities
        kashclaw_sized_quantities = [0.1, 0.5, 1.0, 5.0, 10.0]
        
        for i, quantity in enumerate(kashclaw_sized_quantities):
            mock_resp = Mock()
            mock_resp.point_forecast = [100.0 + i, 101.0 + i, 102.0 + i]
            mock_resp.shadow_mode = True
            mock_resp.available = True
            mock_resp.cached = False
            
            _log_timesfm_shadow(
                series_id=f"kashclaw_order_{i}",
                forecast_resp=mock_resp,
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale=f"KashClaw-sized order test: {quantity} units",
                log_dir=log_dir,
                intent_id=f"kashclaw_intent_{i:03d}",
                ticker="BTC-USD",
                direction="BULL",
                quantity=quantity,
                arb_type="cross_venue",
            )
        
        # Verify logs contain KashClaw-sized quantities
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        with open(log_file, "r") as f:
            entries = [json.loads(line) for line in f]
            assert len(entries) == len(kashclaw_sized_quantities)
            
            for i, entry in enumerate(entries):
                assert entry["quantity"] == kashclaw_sized_quantities[i]
                assert entry["intent_id"].startswith("kashclaw_intent_")
                assert entry["ticker"] == "BTC-USD"
                assert entry["direction"] == "BULL"
                assert entry["arb_type"] == "cross_venue"
    
    def test_handles_shared_instrument_ids(self):
        """Test QuantumArb handles instrument IDs that might be shared with other agents."""
        engine = QuantumArbEngine()
        
        # Test with instrument IDs that KashClaw might use
        shared_instruments = [
            "BTC-USD",  # Bitcoin
            "ETH-USD",  # Ethereum
            "SOL-USD",  # Solana
            "SPY",      # S&P 500 ETF (Alpaca)
            "AAPL",     # Apple stock
        ]
        
        for ticker in shared_instruments:
            signal = ArbitrageSignal(
                intent_id=f"shared_instrument_test_{ticker}",
                source_agent="bullbear_predictor",
                direction="BULL",
                ticker=ticker,
                contradiction_score=2.5,
            )
            
            # Should process without errors
            opportunity = engine.evaluate(signal)
            
            assert opportunity.decision in [ArbDecision.NO_OPPORTUNITY, ArbDecision.INSUFFICIENT_DATA]
            assert opportunity.dry_run is True
            # Ticker should be set (may be None for INSUFFICIENT_DATA decisions)
            if opportunity.decision != ArbDecision.INSUFFICIENT_DATA:
                assert opportunity.ticker == ticker
    
    @patch('simp.agents.quantumarb_agent._try_forecast_sync')
    def test_integration_with_bullbear_signals(self, mock_forecast):
        """Test QuantumArb integration with BullBear signal patterns."""
        engine = QuantumArbEngine()
        
        # Mock forecast response
        mock_resp = Mock()
        mock_resp.point_forecast = [105.0, 106.0, 107.0]
        mock_resp.shadow_mode = True
        mock_resp.available = True
        mock_resp.cached = False
        mock_forecast.return_value = mock_resp
        
        # Simulate BullBear signal patterns
        bullbear_signals = [
            {
                "intent_id": "bullbear_signal_001",
                "direction": "BULL",
                "ticker": "BTC-USD",
                "trust": 0.85,
                "contradiction_score": 1.5,
            },
            {
                "intent_id": "bullbear_signal_002",
                "direction": "BEAR",
                "ticker": "ETH-USD",
                "trust": 0.92,
                "contradiction_score": 2.8,
            },
            {
                "intent_id": "bullbear_signal_003",
                "direction": "NOTRADE",
                "ticker": "SOL-USD",
                "trust": 0.45,  # Low trust
                "contradiction_score": 0.5,
            },
        ]
        
        for signal_data in bullbear_signals:
            signal = ArbitrageSignal(
                intent_id=signal_data["intent_id"],
                source_agent="bullbear_predictor",
                direction=signal_data["direction"],
                ticker=signal_data["ticker"],
                trust=signal_data["trust"],
                contradiction_score=signal_data["contradiction_score"],
            )
            
            opportunity = engine.evaluate(signal)
            
            # Verify consistent behavior
            assert opportunity.source_signal_id == signal_data["intent_id"]
            assert opportunity.dry_run is True
            # Ticker should be set (may be None for INSUFFICIENT_DATA decisions)
            if opportunity.decision != ArbDecision.INSUFFICIENT_DATA:
                assert opportunity.ticker == signal_data["ticker"]
            
            # Low trust signals should get INSUFFICIENT_DATA
            if signal_data["trust"] < engine.MIN_TRUST:
                assert opportunity.decision == ArbDecision.INSUFFICIENT_DATA
                assert "trust score" in opportunity.rationale.lower()
            else:
                assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
    
    def test_handles_mixed_agent_contexts(self, tmp_path):
        """Test logging with mixed agent contexts (simulating multi-agent environment)."""
        log_dir = str(tmp_path / "logs")
        
        # Simulate different agent contexts
        agent_contexts = [
            {
                "intent_id": "quantumarb_eval_001",
                "source_agent": "quantumarb",
                "ticker": "BTC-USD",
                "direction": "BULL",
            },
            {
                "intent_id": "kashclaw_order_002",
                "source_agent": "kashclaw",
                "ticker": "ETH-USD",
                "direction": "BEAR",
            },
            {
                "intent_id": "bullbear_signal_003",
                "source_agent": "bullbear_predictor",
                "ticker": "SOL-USD",
                "direction": "NOTRADE",
            },
            {
                "intent_id": "kloutbot_query_004",
                "source_agent": "kloutbot",
                "ticker": "SPY",
                "direction": "BULL",
            },
        ]
        
        for i, context in enumerate(agent_contexts):
            mock_resp = Mock()
            mock_resp.point_forecast = [100.0 + i, 101.0 + i, 102.0 + i]
            mock_resp.shadow_mode = True
            mock_resp.available = True
            mock_resp.cached = (i % 2 == 0)  # Alternate cached status
            
            _log_timesfm_shadow(
                series_id=f"mixed_agent_{i}",
                forecast_resp=mock_resp,
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale=f"Mixed agent context test: {context['source_agent']}",
                log_dir=log_dir,
                intent_id=context["intent_id"],
                ticker=context["ticker"],
                direction=context["direction"],
                arb_type="statistical",
            )
        
        # Verify all contexts were logged correctly
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        with open(log_file, "r") as f:
            entries = [json.loads(line) for line in f]
            assert len(entries) == len(agent_contexts)
            
            for i, entry in enumerate(entries):
                expected = agent_contexts[i]
                assert entry["intent_id"] == expected["intent_id"]
                assert entry["ticker"] == expected["ticker"]
                assert entry["direction"] == expected["direction"]
                assert entry["arb_type"] == "statistical"
                
                # Verify forecast summary
                summary = entry["forecast_summary"]
                assert summary["forecast_length"] == 3
                assert summary["forecast_mean"] == pytest.approx(101.0 + i)
                assert summary["forecast_min"] == 100.0 + i
                assert summary["forecast_max"] == 102.0 + i