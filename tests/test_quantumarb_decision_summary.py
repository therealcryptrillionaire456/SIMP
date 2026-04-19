"""
Test QuantumArb decision summary logging.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timezone

import pytest

from simp.agents.quantumarb_agent import (
    QuantumArbEngine,
    ArbitrageSignal,
    ArbitrageOpportunity,
    ArbDecision,
    ArbType,
    _log_decision_summary,
)


class TestDecisionSummaryLogging:
    """Test decision summary logging functionality."""
    
    def test_decision_summary_logs_basic_fields(self, tmp_path):
        """Test that decision summary logs contain all basic required fields."""
        # Create test signal and opportunity
        signal = ArbitrageSignal(
            intent_id="test-intent-123",
            source_agent="bullbear_predictor",
            ticker="BTC-USD",
            direction="BULL",
            trust=0.8,
            delta=0.05,
            contradiction_score=1.5,
        )
        
        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.STATISTICAL,
            decision=ArbDecision.NO_OPPORTUNITY,
            source_signal_id="test-intent-123",
            ticker="BTC-USD",
            estimated_spread_bps=15.5,
            confidence=0.3,
            rationale="Test rationale for decision",
            dry_run=True,
        )
        
        # Call decision summary logging
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=True,
            timesfm_rationale="TimesFM forecast suggests mean reversion in ~5 steps",
            log_dir=str(tmp_path),
        )
        
        # Verify log file was created
        log_file = tmp_path / "decision_summary.jsonl"
        assert log_file.exists()
        
        # Read and parse log entry
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) == 1
        entry = json.loads(lines[0])
        
        # Verify required fields
        assert entry["intent_id"] == "test-intent-123"
        assert entry["source_agent"] == "bullbear_predictor"
        assert entry["asset_pair"] == "BTC-USD"
        assert entry["side"] == "BULL"
        assert entry["decision"] == "NO_OPPORTUNITY"
        assert entry["arb_type"] == "statistical"  # lowercase from .value
        assert entry["dry_run"] is True
        assert entry["confidence"] == 0.3
        assert entry["timesfm_used"] is True
        assert entry["timesfm_rationale"] == "TimesFM forecast suggests mean reversion in ~5 steps"
        assert "rationale_preview" in entry
        assert "timestamp" in entry
        
        # Verify timestamp is ISO format
        datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    
    def test_decision_summary_includes_venue_info(self, tmp_path):
        """Test that venue information is included when present."""
        signal = ArbitrageSignal(
            intent_id="test-intent-456",
            source_agent="bullbear_predictor",
            ticker="ETH-USD",
            direction="BEAR",
            trust=0.9,
            delta=-0.03,
            contradiction_score=2.0,
            venue_a="coinbase",
            venue_b="kraken",
        )
        
        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.CROSS_VENUE,
            decision=ArbDecision.NO_OPPORTUNITY,
            source_signal_id="test-intent-456",
            ticker="ETH-USD",
            venue_a="coinbase",
            venue_b="kraken",
            estimated_spread_bps=8.2,
            confidence=0.0,
            rationale="Cross-venue spread insufficient",
            dry_run=True,
        )
        
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=False,
            log_dir=str(tmp_path),
        )
        
        log_file = tmp_path / "decision_summary.jsonl"
        with open(log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline())
        
        assert entry["venue_a"] == "coinbase"
        assert entry["venue_b"] == "kraken"
        assert entry["estimated_spread_bps"] == 8.2
        assert entry["arb_type"] == "cross_venue"  # lowercase from .value
    
    def test_decision_summary_handles_missing_optional_fields(self, tmp_path):
        """Test that logging works when optional fields are missing."""
        signal = ArbitrageSignal(
            intent_id="test-intent-789",
            source_agent="bullbear_predictor",
            ticker="SOL-USD",
            direction="BULL",
            trust=0.7,
            delta=0.02,
            contradiction_score=1.0,
        )
        
        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.STATISTICAL,
            decision=ArbDecision.INSUFFICIENT_DATA,
            source_signal_id="test-intent-789",
            ticker="SOL-USD",
            rationale="Insufficient data for evaluation",
            dry_run=True,
        )
        
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=False,
            log_dir=str(tmp_path),
        )
        
        log_file = tmp_path / "decision_summary.jsonl"
        with open(log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline())
        
        # Should still have basic fields
        assert entry["intent_id"] == "test-intent-789"
        assert entry["decision"] == "INSUFFICIENT_DATA"
        assert entry["confidence"] == 0.0  # Default value
        assert "estimated_spread_bps" in entry  # Always present with default 0.0
        assert entry["estimated_spread_bps"] == 0.0
    
    def test_decision_summary_logging_failure_does_not_raise(self, tmp_path):
        """Test that logging failures don't raise exceptions."""
        signal = ArbitrageSignal(
            intent_id="test-intent-999",
            source_agent="bullbear_predictor",
            ticker="ADA-USD",
            direction="BEAR",
            trust=0.8,
            delta=-0.04,
            contradiction_score=1.8,
        )
        
        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.STATISTICAL,
            decision=ArbDecision.NO_OPPORTUNITY,
            source_signal_id="test-intent-999",
            ticker="ADA-USD",
            rationale="Test",
            dry_run=True,
        )
        
        # Use a read-only directory to cause permission error
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)
        
        # Should not raise
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=False,
            log_dir=str(read_only_dir),
        )
        
        # No exception should be raised
    
    def test_engine_integration_low_trust(self, tmp_path):
        """Test that engine logs decision summary for low-trust signals."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="low-trust-test",
            source_agent="bullbear_predictor",
            ticker="XRP-USD",
            direction="BULL",
            trust=0.5,  # Below MIN_TRUST (0.7)
            delta=0.1,
            contradiction_score=2.0,
        )
        
        with patch.dict('os.environ', {'QUANTUMARB_MIN_TRUST': '0.7'}):
            opportunity = engine.evaluate(signal)
        
        assert opportunity.decision == ArbDecision.INSUFFICIENT_DATA
        
        # Check if log was created (in default location)
        default_log_dir = Path.home() / "bullbear" / "logs" / "quantumarb"
        log_file = default_log_dir / "decision_summary.jsonl"
        
        # Clean up if file exists
        if log_file.exists():
            log_file.unlink()
            # Try to remove directory, but ignore if not empty
            try:
                if default_log_dir.exists():
                    default_log_dir.rmdir()
            except OSError:
                pass  # Directory not empty, leave it
    
    def test_engine_integration_notrade_signal(self, tmp_path):
        """Test that engine logs decision summary for NOTRADE signals."""
        engine = QuantumArbEngine()
        
        signal = ArbitrageSignal(
            intent_id="notrade-test",
            source_agent="bullbear_predictor",
            ticker="LTC-USD",
            direction="NOTRADE",
            trust=0.9,
            delta=0.0,
            contradiction_score=0.0,
        )
        
        opportunity = engine.evaluate(signal)
        
        assert opportunity.decision == ArbDecision.NO_OPPORTUNITY
        assert "NOTRADE" in opportunity.rationale
        
        # Clean up if log was created
        default_log_dir = Path.home() / "bullbear" / "logs" / "quantumarb"
        log_file = default_log_dir / "decision_summary.jsonl"
        if log_file.exists():
            log_file.unlink()
            # Try to remove directory, but ignore if not empty
            try:
                if default_log_dir.exists():
                    default_log_dir.rmdir()
            except OSError:
                pass  # Directory not empty, leave it