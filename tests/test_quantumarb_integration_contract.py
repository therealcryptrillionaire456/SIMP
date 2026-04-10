"""
Tests for QuantumArb integration contract.

Tests the mapping between QuantumArb decision summaries and
standard AgentDecisionSummary format for A2A compatibility.
"""

import pytest
from datetime import datetime, timezone
from simp.organs.quantumarb import (
    QuantumArbDecisionSummary,
    QuantumArbIntegrationContract,
    CONTRACT,
)


class TestQuantumArbIntegrationContract:
    """Test the QuantumArb integration contract."""
    
    def test_contract_singleton(self):
        """Test that CONTRACT singleton is available."""
        assert CONTRACT is not None
        assert isinstance(CONTRACT, QuantumArbIntegrationContract)
    
    def test_map_to_agent_decision_summary_basic(self):
        """Test basic mapping from QuantumArb summary to AgentDecisionSummary."""
        # Create a QuantumArb decision summary
        quantumarb_summary = QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-001",
            source_agent="bullbear_predictor",
            asset_pair="BTC-USD",
            side="BULL",
            decision="EXECUTE",
            arb_type="statistical",
            dry_run=True,
            confidence=0.75,
            timesfm_used=True,
            timesfm_rationale="Low volatility forecast",
            rationale_preview="Statistical arbitrage opportunity detected",
        )
        
        # Map to AgentDecisionSummary
        result = CONTRACT.map_to_agent_decision_summary(quantumarb_summary)
        
        # Verify required fields
        assert result["agent_name"] == "quantumarb"
        assert result["instrument"] == "BTC-USD"
        assert result["side"] == "buy"  # BULL -> buy
        assert result["quantity"] == 0.0  # Default
        assert result["units"] == "USD"  # Default
        assert result["confidence"] == 0.75
        assert result["horizon_days"] == 1
        assert result["volatility_posture"] == "conservative"  # confidence > 0.7
        assert result["timesfm_used"] is True
        assert result["rationale"] == "Statistical arbitrage opportunity detected"
        assert result["timestamp"] == "2024-04-09T12:34:56.789Z"
        
        # Verify QuantumArb metadata preserved
        assert "x_quantumarb" in result
        assert result["x_quantumarb"]["intent_id"] == "test-001"
        assert result["x_quantumarb"]["source_agent"] == "bullbear_predictor"
        assert result["x_quantumarb"]["decision"] == "EXECUTE"
        assert result["x_quantumarb"]["arb_type"] == "statistical"
        assert result["x_quantumarb"]["dry_run"] is True
        assert result["x_quantumarb"]["timesfm_rationale"] == "Low volatility forecast"
    
    def test_side_mapping(self):
        """Test all side mappings from QuantumArb to standard format."""
        test_cases = [
            ("BULL", "buy"),
            ("BEAR", "sell"),
            ("NOTRADE", "hold"),
            ("bull", "buy"),  # lowercase should work
            ("bear", "sell"),
            ("notrade", "hold"),
        ]
        
        for quantumarb_side, expected_side in test_cases:
            quantumarb_summary = QuantumArbDecisionSummary(
                timestamp="2024-04-09T12:34:56.789Z",
                intent_id="test-side",
                source_agent="test",
                asset_pair="BTC-USD",
                side=quantumarb_side,
                decision="NO_OPPORTUNITY",
                arb_type="statistical",
                dry_run=True,
                confidence=0.5,
                timesfm_used=False,
                timesfm_rationale=None,
                rationale_preview="Test",
            )
            
            result = CONTRACT.map_to_agent_decision_summary(quantumarb_summary)
            assert result["side"] == expected_side, f"Failed for {quantumarb_side}"
    
    def test_volatility_posture_mapping(self):
        """Test volatility posture mapping based on TimesFM usage and confidence."""
        test_cases = [
            # (timesfm_used, confidence, expected_posture)
            (True, 0.8, "conservative"),   # High confidence with TimesFM
            (True, 0.7, "neutral"),        # Exactly 0.7 is neutral
            (True, 0.3, "neutral"),        # Exactly 0.3 is neutral
            (True, 0.2, "aggressive"),     # Low confidence with TimesFM
            (False, 0.9, "neutral"),       # No TimesFM, always neutral
            (False, 0.1, "neutral"),
        ]
        
        for timesfm_used, confidence, expected_posture in test_cases:
            quantumarb_summary = QuantumArbDecisionSummary(
                timestamp="2024-04-09T12:34:56.789Z",
                intent_id="test-posture",
                source_agent="test",
                asset_pair="BTC-USD",
                side="BULL",
                decision="EXECUTE",
                arb_type="statistical",
                dry_run=True,
                confidence=confidence,
                timesfm_used=timesfm_used,
                timesfm_rationale="Test" if timesfm_used else None,
                rationale_preview="Test",
            )
            
            result = CONTRACT.map_to_agent_decision_summary(quantumarb_summary)
            assert result["volatility_posture"] == expected_posture, \
                f"Failed for timesfm_used={timesfm_used}, confidence={confidence}"
    
    def test_optional_fields_preserved(self):
        """Test that optional QuantumArb fields are preserved in metadata."""
        quantumarb_summary = QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-optional",
            source_agent="bullbear_predictor",
            asset_pair="ETH-USD",
            side="BEAR",
            decision="EXECUTE",
            arb_type="cross_venue",
            dry_run=True,
            confidence=0.6,
            timesfm_used=True,
            timesfm_rationale="High volatility expected",
            rationale_preview="Cross-venue spread detected",
            venue_a="coinbase",
            venue_b="kraken",
            estimated_spread_bps=150.5,
        )
        
        result = CONTRACT.map_to_agent_decision_summary(quantumarb_summary)
        
        # Verify optional fields in metadata
        assert result["x_quantumarb"]["venue_a"] == "coinbase"
        assert result["x_quantumarb"]["venue_b"] == "kraken"
        assert result["x_quantumarb"]["estimated_spread_bps"] == 150.5
    
    def test_custom_defaults(self):
        """Test that custom defaults can be provided."""
        quantumarb_summary = QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-defaults",
            source_agent="test",
            asset_pair="SOL-USD",
            side="BULL",
            decision="EXECUTE",
            arb_type="statistical",
            dry_run=True,
            confidence=0.5,
            timesfm_used=False,
            timesfm_rationale=None,
            rationale_preview="Test",
        )
        
        # Provide custom defaults
        result = CONTRACT.map_to_agent_decision_summary(
            quantumarb_summary,
            default_quantity=100.0,
            default_units="SOL"
        )
        
        assert result["quantity"] == 100.0
        assert result["units"] == "SOL"
    
    def test_validate_quantumarb_summary_valid(self):
        """Test validation of a valid QuantumArb summary."""
        valid_summary = {
            "timestamp": "2024-04-09T12:34:56.789Z",
            "intent_id": "test-validate",
            "source_agent": "bullbear_predictor",
            "asset_pair": "BTC-USD",
            "side": "BULL",
            "decision": "EXECUTE",
            "arb_type": "statistical",
            "dry_run": True,
            "confidence": 0.75,
            "timesfm_used": True,
            "timesfm_rationale": "Test",
            "rationale_preview": "Test rationale",
        }
        
        assert CONTRACT.validate_quantumarb_summary(valid_summary) is True
    
    def test_validate_quantumarb_summary_missing_field(self):
        """Test validation fails when required field is missing."""
        invalid_summary = {
            "timestamp": "2024-04-09T12:34:56.789Z",
            "intent_id": "test-validate",
            "source_agent": "bullbear_predictor",
            # Missing asset_pair
            "side": "BULL",
            "decision": "EXECUTE",
            "arb_type": "statistical",
            "dry_run": True,
            "confidence": 0.75,
            "timesfm_used": True,
            "timesfm_rationale": "Test",
            "rationale_preview": "Test rationale",
        }
        
        assert CONTRACT.validate_quantumarb_summary(invalid_summary) is False
    
    def test_validate_quantumarb_summary_invalid_confidence(self):
        """Test validation fails when confidence is out of range."""
        invalid_summary = {
            "timestamp": "2024-04-09T12:34:56.789Z",
            "intent_id": "test-validate",
            "source_agent": "bullbear_predictor",
            "asset_pair": "BTC-USD",
            "side": "BULL",
            "decision": "EXECUTE",
            "arb_type": "statistical",
            "dry_run": True,
            "confidence": 1.5,  # > 1.0
            "timesfm_used": True,
            "timesfm_rationale": "Test",
            "rationale_preview": "Test rationale",
        }
        
        assert CONTRACT.validate_quantumarb_summary(invalid_summary) is False
    
    def test_validate_quantumarb_summary_invalid_timestamp(self):
        """Test validation fails with invalid timestamp."""
        invalid_summary = {
            "timestamp": "not-a-timestamp",
            "intent_id": "test-validate",
            "source_agent": "bullbear_predictor",
            "asset_pair": "BTC-USD",
            "side": "BULL",
            "decision": "EXECUTE",
            "arb_type": "statistical",
            "dry_run": True,
            "confidence": 0.75,
            "timesfm_used": True,
            "timesfm_rationale": "Test",
            "rationale_preview": "Test rationale",
        }
        
        assert CONTRACT.validate_quantumarb_summary(invalid_summary) is False
    
    def test_get_safety_parameters(self):
        """Test that safety parameters are returned."""
        params = CONTRACT.get_safety_parameters()
        
        # Check required parameters
        assert "max_confidence_threshold" in params
        assert "min_confidence_threshold" in params
        assert "required_timesfm_for_live" in params
        assert "max_daily_trades" in params
        assert "position_size_limit_usd" in params
        assert "allowed_arb_types" in params
        assert "blocked_venues" in params
        
        # Check value ranges
        assert 0 <= params["max_confidence_threshold"] <= 1
        assert 0 <= params["min_confidence_threshold"] <= 1
        assert params["max_confidence_threshold"] >= params["min_confidence_threshold"]
        assert params["max_daily_trades"] > 0
        assert params["position_size_limit_usd"] > 0
        
        # Check arb types
        assert "statistical" in params["allowed_arb_types"]
        assert "cross_venue" in params["allowed_arb_types"]
    
    def test_from_dict_conversion(self):
        """Test creating QuantumArbDecisionSummary from dictionary."""
        summary_dict = {
            "timestamp": "2024-04-09T12:34:56.789Z",
            "intent_id": "test-dict",
            "source_agent": "bullbear_predictor",
            "asset_pair": "BTC-USD",
            "side": "BULL",
            "decision": "EXECUTE",
            "arb_type": "statistical",
            "dry_run": True,
            "confidence": 0.75,
            "timesfm_used": True,
            "timesfm_rationale": "Test",
            "rationale_preview": "Test rationale",
            "venue_a": "coinbase",
            "venue_b": "kraken",
            "estimated_spread_bps": 100.0,
        }
        
        # Create from dict using dataclass
        summary = QuantumArbDecisionSummary(**summary_dict)
        
        # Verify all fields
        assert summary.timestamp == summary_dict["timestamp"]
        assert summary.intent_id == summary_dict["intent_id"]
        assert summary.source_agent == summary_dict["source_agent"]
        assert summary.asset_pair == summary_dict["asset_pair"]
        assert summary.side == summary_dict["side"]
        assert summary.decision == summary_dict["decision"]
        assert summary.arb_type == summary_dict["arb_type"]
        assert summary.dry_run == summary_dict["dry_run"]
        assert summary.confidence == summary_dict["confidence"]
        assert summary.timesfm_used == summary_dict["timesfm_used"]
        assert summary.timesfm_rationale == summary_dict["timesfm_rationale"]
        assert summary.rationale_preview == summary_dict["rationale_preview"]
        assert summary.venue_a == summary_dict["venue_a"]
        assert summary.venue_b == summary_dict["venue_b"]
        assert summary.estimated_spread_bps == summary_dict["estimated_spread_bps"]
    
    def test_edge_case_confidence_boundaries(self):
        """Test confidence boundary cases."""
        boundary_cases = [0.0, 0.3, 0.7, 1.0]
        
        for confidence in boundary_cases:
            quantumarb_summary = QuantumArbDecisionSummary(
                timestamp="2024-04-09T12:34:56.789Z",
                intent_id=f"test-boundary-{confidence}",
                source_agent="test",
                asset_pair="BTC-USD",
                side="BULL",
                decision="EXECUTE",
                arb_type="statistical",
                dry_run=True,
                confidence=confidence,
                timesfm_used=True,
                timesfm_rationale="Test",
                rationale_preview="Test",
            )
            
            result = CONTRACT.map_to_agent_decision_summary(quantumarb_summary)
            assert 0 <= result["confidence"] <= 1
    
    def test_null_timesfm_rationale(self):
        """Test handling of None timesfm_rationale."""
        quantumarb_summary = QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-null-rationale",
            source_agent="test",
            asset_pair="BTC-USD",
            side="BULL",
            decision="EXECUTE",
            arb_type="statistical",
            dry_run=True,
            confidence=0.5,
            timesfm_used=False,
            timesfm_rationale=None,  # None value
            rationale_preview="Test",
        )
        
        result = CONTRACT.map_to_agent_decision_summary(quantumarb_summary)
        assert result["x_quantumarb"]["timesfm_rationale"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])