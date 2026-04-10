"""
Tests for KashClaw A2A/FinancialOps integration hooks.

Tests that:
- A2A summary function exists and is callable
- Returns safe, structured data without secrets
- Handles edge cases gracefully
- Provides necessary metadata for A2A pipelines
"""

import pytest
import sys
from datetime import datetime

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.integrations.kashclaw_shim import KashClawSimpAgent


class TestKashClawA2AHooks:
    """Tests for KashClaw A2A integration hooks"""

    @pytest.fixture
    def agent(self):
        """Create a fresh agent"""
        return KashClawSimpAgent(agent_id="test-agent-a2a-001")

    def test_a2a_summary_function_exists(self, agent):
        """Test that prepare_a2a_summary function exists"""
        assert hasattr(agent, 'prepare_a2a_summary')
        assert callable(agent.prepare_a2a_summary)

    def test_a2a_summary_basic_structure(self, agent):
        """Test basic A2A summary structure"""
        # Sample trade result (simplified)
        trade_result = {
            "status": "success",
            "timestamp": "2024-01-15T12:30:45.123456Z",
            "risk_posture": "neutral",
            "timesfm_sizing": {
                "applied": False,
                "rationale": "TimesFM: shadow mode active",
                "risk_posture": "neutral"
            },
            "execution": {
                "trade_id": "trade:abc123",
                "organ_id": "spot:001",
                "organ_type": "spot_trading",
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": 10.0,
                "price": 150.25,
                "fee": 1.50,
                "slippage": 0.5,  # percent
            }
        }
        
        # Sample sizing advice
        sizing_advice = {
            "original_quantity": 10.0,
            "original_slippage_tolerance": 0.01,
            "adjusted_quantity": 10.0,
            "adjusted_slippage_tolerance": 0.01,
            "timesfm_applied": False,
            "timesfm_rationale": "TimesFM: shadow mode active",
            "risk_posture": "neutral"
        }
        
        # Get A2A summary
        summary = agent.prepare_a2a_summary(trade_result, sizing_advice)
        
        # Check required fields
        required_fields = [
            "trade_id", "asset_pair", "side", "quantity", "executed_price",
            "timestamp", "risk_posture", "timesfm_involved", "timesfm_rationale",
            "status", "organ_id", "organ_type", "fee", "slippage_percent",
            "a2a_version", "source_agent", "summary_type"
        ]
        
        for field in required_fields:
            assert field in summary, f"Missing required field: {field}"
        
        # Check values
        assert summary["trade_id"] == "trade:abc123"
        assert summary["asset_pair"] == "SOL/USDC"
        assert summary["side"] == "BUY"
        assert summary["quantity"] == 10.0
        assert summary["executed_price"] == 150.25
        assert summary["risk_posture"] == "neutral"
        assert summary["timesfm_involved"] is False
        assert summary["status"] == "success"
        assert summary["source_agent"] == "test-agent-a2a-001"
        assert summary["a2a_version"] == "0.7.0"

    def test_a2a_summary_with_timesfm_adjustments(self, agent):
        """Test A2A summary when TimesFM adjusted sizing"""
        trade_result = {
            "status": "success",
            "timestamp": "2024-01-15T12:35:00.000000Z",
            "risk_posture": "conservative",
            "timesfm_sizing": {
                "applied": True,
                "rationale": "TimesFM volatility rising: reduced qty by 20%",
                "risk_posture": "conservative"
            },
            "execution": {
                "trade_id": "trade:def456",
                "organ_id": "spot:002",
                "organ_type": "spot_trading",
                "asset_pair": "BTC/USD",
                "side": "SELL",
                "quantity": 8.0,  # Adjusted quantity
                "price": 42000.0,
                "fee": 42.0,
                "slippage": 0.8,
            }
        }
        
        sizing_advice = {
            "original_quantity": 10.0,
            "original_slippage_tolerance": 0.01,
            "adjusted_quantity": 8.0,
            "adjusted_slippage_tolerance": 0.0125,
            "timesfm_applied": True,
            "timesfm_rationale": "TimesFM volatility rising: reduced qty by 20%",
            "risk_posture": "conservative"
        }
        
        summary = agent.prepare_a2a_summary(trade_result, sizing_advice)
        
        # Check TimesFM adjustment fields
        assert summary["timesfm_involved"] is True
        assert "original_quantity" in summary
        assert "adjusted_quantity" in summary
        assert "original_slippage" in summary
        assert "adjusted_slippage" in summary
        assert "sizing_adjustment_percent" in summary
        
        assert summary["original_quantity"] == 10.0
        assert summary["adjusted_quantity"] == 8.0
        assert summary["sizing_adjustment_percent"] == pytest.approx(-20.0, rel=1e-6)  # 20% reduction

    def test_a2a_summary_edge_cases(self, agent):
        """Test A2A summary with edge cases"""
        # Minimal trade result
        trade_result = {
            "status": "error",
            "timestamp": "2024-01-15T12:40:00.000000Z",
        }
        
        # Minimal sizing advice
        sizing_advice = {}
        
        summary = agent.prepare_a2a_summary(trade_result, sizing_advice)
        
        # Should handle missing fields gracefully
        assert summary["trade_id"] == "unknown"
        assert summary["asset_pair"] == "unknown/unknown"
        assert summary["side"] == "unknown"
        assert summary["quantity"] == 0.0
        assert summary["risk_posture"] == "neutral"  # Default
        assert summary["timesfm_involved"] is False
        assert summary["status"] == "error"
        assert summary["source_agent"] == "test-agent-a2a-001"

    def test_a2a_summary_no_secrets_exposed(self, agent):
        """Test that A2A summary doesn't expose secrets or internal state"""
        trade_result = {
            "status": "success",
            "timestamp": "2024-01-15T12:45:00.000000Z",
            "risk_posture": "neutral",
            "timesfm_sizing": {
                "applied": False,
                "rationale": "shadow mode",
                "risk_posture": "neutral"
            },
            "execution": {
                "trade_id": "trade:ghi789",
                "organ_id": "spot:003",
                "organ_type": "spot_trading",
                "asset_pair": "ETH/USD",
                "side": "BUY",
                "quantity": 5.0,
                "price": 2500.0,
                "fee": 2.5,
                "slippage": 0.3,
                # Internal fields that should NOT appear in A2A summary
                "metadata": {"internal": "data"},
                "execution_time": "2024-01-15T12:45:00.000000Z",
                "status": "COMPLETED",  # Internal status enum
                "profit_loss": None,
            }
        }
        
        sizing_advice = {
            "original_quantity": 5.0,
            "original_slippage_tolerance": 0.01,
            "adjusted_quantity": 5.0,
            "adjusted_slippage_tolerance": 0.01,
            "timesfm_applied": False,
            "timesfm_rationale": "shadow mode",
            "risk_posture": "neutral"
        }
        
        summary = agent.prepare_a2a_summary(trade_result, sizing_advice)
        
        # Check that internal fields are not exposed
        internal_fields = ["metadata", "execution_time", "profit_loss"]
        for field in internal_fields:
            assert field not in summary, f"Internal field {field} should not be in A2A summary"
        
        # Check that only safe fields are present
        safe_fields = [
            "trade_id", "asset_pair", "side", "quantity", "executed_price",
            "timestamp", "risk_posture", "timesfm_involved", "timesfm_rationale",
            "status", "organ_id", "organ_type", "fee", "slippage_percent",
            "a2a_version", "source_agent", "summary_type"
        ]
        
        for key in summary.keys():
            assert key in safe_fields or key.startswith(("original_", "adjusted_", "sizing_")), \
                f"Potentially unsafe field in A2A summary: {key}"

    def test_a2a_summary_pure_function(self, agent):
        """Test that prepare_a2a_summary is a pure function (no side effects)"""
        trade_result = {
            "status": "success",
            "timestamp": "2024-01-15T12:50:00.000000Z",
            "risk_posture": "neutral",
            "timesfm_sizing": {"applied": False, "rationale": "test", "risk_posture": "neutral"},
            "execution": {
                "trade_id": "trade:jkl012",
                "organ_id": "spot:004",
                "organ_type": "spot_trading",
                "asset_pair": "XRP/USD",
                "side": "SELL",
                "quantity": 1000.0,
                "price": 0.55,
                "fee": 0.55,
                "slippage": 0.2,
            }
        }
        
        sizing_advice = {
            "original_quantity": 1000.0,
            "original_slippage_tolerance": 0.01,
            "adjusted_quantity": 1000.0,
            "adjusted_slippage_tolerance": 0.01,
            "timesfm_applied": False,
            "timesfm_rationale": "test",
            "risk_posture": "neutral"
        }
        
        # Call multiple times - should return same result
        summary1 = agent.prepare_a2a_summary(trade_result, sizing_advice)
        summary2 = agent.prepare_a2a_summary(trade_result, sizing_advice)
        
        assert summary1 == summary2, "A2A summary should be deterministic"
        
        # Modify input and verify output changes (no caching)
        trade_result2 = trade_result.copy()
        trade_result2["execution"] = trade_result["execution"].copy()
        trade_result2["execution"]["quantity"] = 500.0
        
        summary3 = agent.prepare_a2a_summary(trade_result2, sizing_advice)
        assert summary3["quantity"] == 500.0
        assert summary1["quantity"] == 1000.0  # Original unchanged