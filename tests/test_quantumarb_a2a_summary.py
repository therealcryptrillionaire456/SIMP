"""
Test QuantumArb decision summary structure for A2A compatibility.
"""
import json
from pathlib import Path
from datetime import datetime

import pytest

from simp.agents.quantumarb_agent import (
    ArbitrageSignal,
    ArbitrageOpportunity,
    ArbDecision,
    ArbType,
    _log_decision_summary,
)


class TestA2ASummaryStructure:
    """Test that decision summaries have stable structure for A2A consumption."""
    
    def test_summary_has_stable_field_names(self, tmp_path):
        """Test that summary field names don't change unexpectedly."""
        signal = ArbitrageSignal(
            intent_id="test-a2a-1",
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
            source_signal_id="test-a2a-1",
            ticker="BTC-USD",
            estimated_spread_bps=12.5,
            confidence=0.4,
            rationale="Test rationale",
            dry_run=True,
        )
        
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=True,
            timesfm_rationale="Forecast available",
            log_dir=str(tmp_path),
        )
        
        log_file = tmp_path / "decision_summary.jsonl"
        with open(log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline())
        
        # Required fields for A2A consumption
        required_fields = {
            "timestamp": str,           # ISO timestamp
            "intent_id": str,           # Traceability
            "source_agent": str,        # Who sent the signal
            "asset_pair": (str, type(None)),  # Instrument
            "side": str,                # BULL/BEAR/NOTRADE
            "decision": str,            # Uppercase decision
            "arb_type": str,            # Lowercase arb type
            "dry_run": bool,            # Safety flag
            "confidence": (int, float), # 0-1 confidence
            "timesfm_used": bool,       # Whether TimesFM was consulted
            "timesfm_rationale": (str, type(None)),  # TimesFM insight
            "rationale_preview": str,   # Abbreviated rationale
        }
        
        # Verify all required fields exist with correct types
        for field_name, expected_type in required_fields.items():
            assert field_name in entry, f"Missing field: {field_name}"
            
            if isinstance(expected_type, tuple):
                # Multiple allowed types
                assert isinstance(entry[field_name], expected_type), \
                    f"Field {field_name} has wrong type: {type(entry[field_name])}"
            else:
                assert isinstance(entry[field_name], expected_type), \
                    f"Field {field_name} has wrong type: {type(entry[field_name])}"
        
        # Verify specific field constraints
        assert entry["decision"] == "NO_OPPORTUNITY"  # Uppercase
        assert entry["arb_type"] == "statistical"     # Lowercase
        assert entry["dry_run"] is True               # Always True in scaffold
        assert 0 <= entry["confidence"] <= 1          # Valid confidence range
        
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    
    def test_summary_with_venue_fields(self, tmp_path):
        """Test that venue fields are included when present."""
        signal = ArbitrageSignal(
            intent_id="test-a2a-2",
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
            source_signal_id="test-a2a-2",
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
        
        # Optional venue fields should be present
        assert "venue_a" in entry
        assert "venue_b" in entry
        assert "estimated_spread_bps" in entry
        
        assert entry["venue_a"] == "coinbase"
        assert entry["venue_b"] == "kraken"
        assert entry["estimated_spread_bps"] == 8.2
        assert entry["arb_type"] == "cross_venue"
    
    def test_summary_field_consistency_across_decisions(self, tmp_path):
        """Test that field structure is consistent across different decision types."""
        test_cases = [
            (ArbDecision.NO_OPPORTUNITY, "NO_OPPORTUNITY"),
            (ArbDecision.INSUFFICIENT_DATA, "INSUFFICIENT_DATA"),
            (ArbDecision.BLOCKED, "BLOCKED"),
        ]
        
        for decision_enum, expected_decision_str in test_cases:
            signal = ArbitrageSignal(
                intent_id=f"test-{decision_enum.value}",
                source_agent="bullbear_predictor",
                ticker="SOL-USD",
                direction="BULL",
                trust=0.8,
                delta=0.02,
                contradiction_score=1.0,
            )
            
            opportunity = ArbitrageOpportunity(
                arb_type=ArbType.STATISTICAL,
                decision=decision_enum,
                source_signal_id=f"test-{decision_enum.value}",
                ticker="SOL-USD",
                rationale=f"Test {decision_enum.value}",
                dry_run=True,
            )
            
            _log_decision_summary(
                signal=signal,
                opportunity=opportunity,
                timesfm_used=False,
                log_dir=str(tmp_path),
            )
        
        # Read all entries
        log_file = tmp_path / "decision_summary.jsonl"
        with open(log_file, "r", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f]
        
        # All entries should have the same field structure
        field_sets = [set(entry.keys()) for entry in entries]
        first_field_set = field_sets[0]
        
        for field_set in field_sets[1:]:
            assert field_set == first_field_set, "Field structure varies between decisions"
        
        # Verify decision strings are uppercase
        for entry in entries:
            assert entry["decision"].isupper(), f"Decision should be uppercase: {entry['decision']}"
            assert entry["dry_run"] is True, "dry_run should always be True"
    
    def test_summary_rationale_preview_length_limit(self, tmp_path):
        """Test that rationale_preview is truncated appropriately."""
        long_rationale = "A" * 300  # 300 characters
        
        signal = ArbitrageSignal(
            intent_id="test-long-rationale",
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
            source_signal_id="test-long-rationale",
            ticker="ADA-USD",
            rationale=long_rationale,
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
        
        # rationale_preview should be truncated with "..."
        preview = entry["rationale_preview"]
        assert len(preview) <= 203  # 200 chars + "..."
        assert preview.endswith("...")
        assert preview.startswith("A" * 200)
    
    def test_summary_without_timesfm(self, tmp_path):
        """Test summary when TimesFM is not used."""
        signal = ArbitrageSignal(
            intent_id="test-no-timesfm",
            source_agent="bullbear_predictor",
            ticker="XRP-USD",
            direction="BULL",
            trust=0.8,
            delta=0.05,
            contradiction_score=1.5,
        )
        
        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.STATISTICAL,
            decision=ArbDecision.NO_OPPORTUNITY,
            source_signal_id="test-no-timesfm",
            ticker="XRP-USD",
            rationale="No TimesFM used",
            dry_run=True,
        )
        
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=False,
            timesfm_rationale=None,
            log_dir=str(tmp_path),
        )
        
        log_file = tmp_path / "decision_summary.jsonl"
        with open(log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline())
        
        assert entry["timesfm_used"] is False
        assert entry["timesfm_rationale"] is None
        assert entry["confidence"] == 0.0  # Default value