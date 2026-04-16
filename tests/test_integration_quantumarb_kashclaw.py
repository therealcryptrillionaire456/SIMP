"""
Integration test: QuantumArb → KashClaw execution flow.

Tests the complete pipeline:
1. QuantumArb generates AgentDecisionSummary
2. KashClaw execution mapper converts to trade parameters
3. KashClaw shim executes trade (simulated)
4. Verify execution results and metrics
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from simp.financial.a2a_schema import AgentDecisionSummary, Side
from simp.integrations.kashclaw_execution_mapping import (
    KashClawExecutionMapper,
    map_decision_to_trade,
    get_execution_mapper,
)
from simp.integrations.trading_organ import OrganType, OrganExecutionResult, TradeExecution, ExecutionStatus
from simp.organs.quantumarb import QuantumArbIntegrationContract, QuantumArbDecisionSummary
from simp.integrations.kashclaw_shim import KashClawSimpAgent


def create_agent_decision_from_quantumarb(quantumarb_summary, default_quantity=0.0, default_units="USD"):
    """Helper to convert QuantumArbDecisionSummary to AgentDecisionSummary."""
    contract = QuantumArbIntegrationContract()
    agent_decision_dict = contract.map_to_agent_decision_summary(
        quantumarb_summary,
        default_quantity=default_quantity,
        default_units=default_units
    )
    # Remove x_quantumarb field before creating AgentDecisionSummary
    agent_decision_dict_filtered = {k: v for k, v in agent_decision_dict.items() if k != "x_quantumarb"}
    return AgentDecisionSummary(**agent_decision_dict_filtered)


class TestIntegrationQuantumArbKashClaw:
    """Integration tests for QuantumArb → KashClaw execution flow."""
    
    @pytest.fixture
    def quantumarb_decision(self):
        """Create a realistic QuantumArb decision."""
        return AgentDecisionSummary(
            agent_name="quantumarb",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=0.1,
            units="BTC",
            confidence=0.75,
            horizon_days=1,
            volatility_posture="medium",
            timesfm_used=True,
            rationale="Arbitrage opportunity detected between exchanges",
            timestamp="2024-04-09T12:34:56.789Z"
        )
    
    @pytest.fixture
    def quantumarb_decision_summary(self):
        """Create QuantumArb-specific decision summary."""
        return QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-intent-001",
            source_agent="quantumarb",
            asset_pair="BTC-USD",
            side="BULL",  # QuantumArb uses BULL/BEAR/NOTRADE
            decision="BUY",
            arb_type="cross_exchange",
            dry_run=False,
            confidence=0.75,
            timesfm_used=True,
            timesfm_rationale="Volatility within normal range",
            rationale_preview="Arbitrage opportunity detected",
            venue_a="coinbase",
            venue_b="kraken",
            estimated_spread_bps=15.5,
        )
    
    @pytest.fixture
    def execution_mapper(self):
        """Create execution mapper."""
        return get_execution_mapper()
    
    @pytest.fixture
    def mock_kashclaw_agent(self):
        """Create a mock KashClaw agent."""
        agent = Mock(spec=KashClawSimpAgent)
        agent.organs = {
            "spot:001": OrganType.SPOT_TRADING,
            "algo:001": OrganType.ALGORITHMIC,
        }
        
        # Mock handle_trade to return simulated execution
        async def mock_handle_trade(params):
            return {
                "status": "success",
                "execution": {
                    "organ_id": params.get("organ_id", "spot:001"),
                    "organ_type": "spot_trading",
                    "intent_id": params.get("intent_id", "test-intent-001"),
                    "status": "executed",
                    "executions": [
                        {
                            "trade_id": "trade-001",
                            "organ_type": "spot_trading",
                            "asset_pair": params.get("asset_pair", "BTC/USDC"),
                            "side": params.get("side", "BUY"),
                            "quantity": params.get("quantity", 0.1),
                            "price": 65000.0,
                            "execution_time": datetime.utcnow().isoformat(),
                            "status": "executed",
                            "fee": 1.25,
                            "slippage": 0.001,
                            "profit_loss": None,
                            "metadata": {"simulated": True}
                        }
                    ],
                    "total_pnl": 0.0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error_message": None,
                    "gas_used": None,
                    "blockchain": None,
                },
                "timestamp": datetime.utcnow().isoformat(),
                "timesfm_sizing": {
                    "applied": False,
                    "rationale": "No TimesFM adjustment needed",
                    "risk_posture": "neutral",
                },
                "risk_posture": "neutral",
            }
        
        agent.handle_trade = AsyncMock(side_effect=mock_handle_trade)
        return agent
    
    @pytest.mark.asyncio
    async def test_quantumarb_to_kashclaw_mapping(self, quantumarb_decision, execution_mapper):
        """Test mapping QuantumArb decision to KashClaw trade parameters."""
        # Map decision to trade
        mapping_result = execution_mapper.map_decision_to_trade(
            quantumarb_decision,
            available_organs={"spot:001": OrganType.SPOT_TRADING}
        )
        
        # Verify mapping succeeded
        assert mapping_result.success is True
        assert mapping_result.error_message is None
        
        # Verify organ selection
        assert mapping_result.organ_id == "spot:001"
        assert mapping_result.organ_type == OrganType.SPOT_TRADING
        
        # Verify trade parameters
        trade_params = mapping_result.trade_params
        assert trade_params is not None
        assert trade_params["asset_pair"] == "BTC/USDC"
        assert trade_params["side"] == "BUY"
        assert trade_params["quantity"] == 0.1
        assert trade_params["units"] == "BTC"
        assert trade_params["source_agent"] == "quantumarb"
        
        # Verify crypto-specific parameters
        assert trade_params["slippage_tolerance"] == 0.01
        assert trade_params["venue"] == "coinbase"
        assert trade_params["order_type"] == "market"
        
        # Verify optional fields
        assert trade_params["confidence"] == 0.75
        assert "Arbitrage" in trade_params["rationale"]
        assert trade_params["volatility_posture"] == "medium"  # from fixture
        assert trade_params["timesfm_used"] is True
    
    @pytest.mark.asyncio
    async def test_quantumarb_contract_to_agent_decision(self, quantumarb_decision_summary):
        """Test QuantumArb contract conversion to AgentDecisionSummary."""
        # Use the integration contract
        contract = QuantumArbIntegrationContract()
        
        # Convert QuantumArb decision to AgentDecisionSummary dict
        agent_decision_dict = contract.map_to_agent_decision_summary(
            quantumarb_decision_summary,
            default_quantity=0.1,
            default_units="BTC"
        )
        
        # Verify conversion
        assert agent_decision_dict["agent_name"] == "quantumarb"
        assert agent_decision_dict["instrument"] == "BTC-USD"
        assert agent_decision_dict["side"] == "buy"  # BULL maps to buy
        assert agent_decision_dict["quantity"] == 0.1
        assert agent_decision_dict["units"] == "BTC"
        assert agent_decision_dict["confidence"] == 0.75
        assert agent_decision_dict["volatility_posture"] == "conservative"  # confidence > 0.7
        assert agent_decision_dict["timesfm_used"] is True
        assert "Arbitrage" in agent_decision_dict["rationale"]
        
        # Create AgentDecisionSummary object from dict (remove x_quantumarb field)
        agent_decision_dict_filtered = {k: v for k, v in agent_decision_dict.items() if k != "x_quantumarb"}
        agent_decision = AgentDecisionSummary(**agent_decision_dict_filtered)
        assert agent_decision.agent_name == "quantumarb"
        assert agent_decision.instrument == "BTC-USD"
        assert agent_decision.side == Side.BUY
    
    @pytest.mark.asyncio
    async def test_complete_quantumarb_kashclaw_flow(self, quantumarb_decision_summary, mock_kashclaw_agent):
        """Test complete flow: QuantumArb → AgentDecisionSummary → Mapping → Execution."""
        # Step 1: Convert QuantumArb decision to AgentDecisionSummary using helper
        agent_decision = create_agent_decision_from_quantumarb(
            quantumarb_decision_summary,
            default_quantity=0.1,
            default_units="BTC"
        )
        
        # Step 2: Map to trade parameters
        mapper = get_execution_mapper()
        mapping_result = mapper.map_decision_to_trade(
            agent_decision,
            available_organs=mock_kashclaw_agent.organs
        )
        
        assert mapping_result.success is True
        
        # Step 3: Prepare trade parameters for execution
        trade_params = mapping_result.trade_params.copy()
        trade_params["organ_id"] = mapping_result.organ_id
        trade_params["intent_id"] = "test-intent-001"
        
        # Step 4: Execute trade through KashClaw agent
        execution_result = await mock_kashclaw_agent.handle_trade(trade_params)
        
        # Step 5: Verify execution result
        assert execution_result["status"] == "success"
        assert "execution" in execution_result
        
        execution = execution_result["execution"]
        assert execution["organ_id"] == "spot:001"
        assert execution["organ_type"] == "spot_trading"
        assert execution["status"] == "executed"
        
        # Verify trade execution details
        trade_execution = execution["executions"][0]
        assert trade_execution["asset_pair"] == "BTC/USDC"
        assert trade_execution["side"] == "BUY"
        assert trade_execution["quantity"] == 0.1
        assert trade_execution["price"] == 65000.0
        
        # Step 6: Generate execution summary for monitoring
        execution_summary = mapper.get_execution_summary(agent_decision, mapping_result)
        
        assert execution_summary["agent_name"] == "quantumarb"
        assert execution_summary["instrument"] == "BTC-USD"
        assert execution_summary["mapping_success"] is True
        assert execution_summary["mapped_organ_id"] == "spot:001"
        assert execution_summary["mapped_asset_pair"] == "BTC/USDC"
    
    @pytest.mark.asyncio
    async def test_quantumarb_sell_decision_flow(self):
        """Test QuantumArb SELL decision flow."""
        # Create a SELL decision
        quantumarb_sell = QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-intent-002",
            source_agent="quantumarb",
            asset_pair="ETH-USD",
            side="BEAR",  # QuantumArb uses BEAR for sell
            decision="SELL",
            arb_type="cross_exchange",
            dry_run=False,
            confidence=0.68,
            timesfm_used=True,
            timesfm_rationale="High volatility detected",
            rationale_preview="Price divergence detected, taking profit",
            venue_a="coinbase",
            venue_b="binance",
            estimated_spread_bps=8.2,
        )
        
        # Convert to AgentDecisionSummary using helper
        agent_decision = create_agent_decision_from_quantumarb(quantumarb_sell, default_quantity=2.5, default_units="ETH")
        
        # Map to trade parameters
        mapper = get_execution_mapper()
        mapping_result = mapper.map_decision_to_trade(
            agent_decision,
            available_organs={"spot:001": OrganType.SPOT_TRADING}
        )
        
        # Verify SELL side is preserved
        assert mapping_result.success is True
        assert mapping_result.trade_params["side"] == "SELL"
        assert mapping_result.trade_params["asset_pair"] == "ETH/USDC"
        assert mapping_result.trade_params["quantity"] == 2.5
        
        # Verify volatility posture (timesfm_used=False, so neutral regardless of confidence)
        assert mapping_result.trade_params["volatility_posture"] == "neutral"
    
    @pytest.mark.asyncio
    async def test_quantumarb_low_confidence_warning(self):
        """Test that low confidence decisions generate warnings."""
        # Create low confidence decision
        quantumarb_low_conf = QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-intent-003",
            source_agent="quantumarb",
            asset_pair="SOL-USD",
            side="BULL",
            decision="BUY",
            arb_type="cross_exchange",
            dry_run=False,
            confidence=0.25,  # Low confidence
            timesfm_used=False,
            timesfm_rationale=None,
            rationale_preview="Weak arbitrage signal",
            venue_a="coinbase",
            venue_b="kraken",
            estimated_spread_bps=3.5,
        )
        
        # Convert and map using helper
        agent_decision = create_agent_decision_from_quantumarb(quantumarb_low_conf, default_quantity=10.0, default_units="SOL")
        
        mapper = get_execution_mapper()
        mapping_result = mapper.map_decision_to_trade(agent_decision)
        
        # Should succeed but with warnings
        assert mapping_result.success is True
        assert len(mapping_result.warnings) > 0
        assert any("Low confidence" in warning for warning in mapping_result.warnings)
    
    @pytest.mark.asyncio
    async def test_quantumarb_unknown_instrument_warning(self):
        """Test that unknown instruments generate warnings."""
        # Create decision with unknown instrument
        quantumarb_unknown = QuantumArbDecisionSummary(
            timestamp="2024-04-09T12:34:56.789Z",
            intent_id="test-intent-004",
            source_agent="quantumarb",
            asset_pair="XYZ-123",  # Unknown instrument
            side="BULL",
            decision="BUY",
            arb_type="cross_exchange",
            dry_run=False,
            confidence=0.8,
            timesfm_used=False,
            timesfm_rationale=None,
            rationale_preview="Testing unknown instrument",
            venue_a="coinbase",
            venue_b="kraken",
            estimated_spread_bps=10.0,
        )
        
        # Convert and map
        # Convert and map using helper
        agent_decision = create_agent_decision_from_quantumarb(quantumarb_unknown, default_quantity=100.0, default_units="USD")
        
        mapper = get_execution_mapper()
        mapping_result = mapper.map_decision_to_trade(agent_decision)
        
        # Should succeed but with warnings
        assert mapping_result.success is True
        assert len(mapping_result.warnings) > 0
        assert any("Unknown asset class" in warning for warning in mapping_result.warnings)
        
        # Should use default organ for unknown asset class
        assert mapping_result.organ_id == "spot:001"
    
    @pytest.mark.asyncio
    async def test_quantumarb_execution_metrics(self, quantumarb_decision_summary):
        """Test execution metrics collection."""
        # Convert and map
        contract = QuantumArbIntegrationContract()
        agent_decision_dict = contract.map_to_agent_decision_summary(
            quantumarb_decision_summary,
            default_quantity=0.1,
            default_units="BTC"
        )
        # Remove x_quantumarb field before creating AgentDecisionSummary
        agent_decision_dict_filtered = {k: v for k, v in agent_decision_dict.items() if k != "x_quantumarb"}
        agent_decision = AgentDecisionSummary(**agent_decision_dict_filtered)
        
        mapper = get_execution_mapper()
        mapping_result = mapper.map_decision_to_trade(agent_decision)
        
        # Get execution summary
        execution_summary = mapper.get_execution_summary(agent_decision, mapping_result)
        
        # Verify metrics
        assert "timestamp" in execution_summary
        assert execution_summary["agent_name"] == "quantumarb"
        assert execution_summary["instrument"] == "BTC-USD"
        assert execution_summary["original_side"] == "buy"
        assert execution_summary["original_quantity"] == 0.1
        assert execution_summary["original_units"] == "BTC"
        assert execution_summary["mapping_success"] is True
        assert execution_summary["mapped_organ_id"] == "spot:001"
        assert execution_summary["mapped_organ_type"] == "spot_trading"
        assert execution_summary["mapped_asset_pair"] == "BTC/USDC"
        assert execution_summary["mapped_side"] == "BUY"
        assert execution_summary["confidence"] == 0.75
        assert execution_summary["volatility_posture"] == "conservative"
        assert execution_summary["timesfm_used"] is True
        assert execution_summary["warnings"] == []
        
        # Verify rationale preview
        assert "rationale_preview" in execution_summary
        assert "Arbitrage" in execution_summary["rationale_preview"]
    
    @pytest.mark.asyncio
    async def test_quantumarb_multiple_decisions_flow(self):
        """Test flow with multiple QuantumArb decisions."""
        decisions = [
            QuantumArbDecisionSummary(
                timestamp="2024-04-09T12:34:56.789Z",
                intent_id="test-intent-001",
                source_agent="quantumarb",
                asset_pair="BTC-USD",
                side="BULL",
                decision="BUY",
                arb_type="cross_exchange",
                dry_run=False,
                confidence=0.75,
                timesfm_used=True,
                timesfm_rationale="Normal volatility",
                rationale_preview="Decision 1",
                venue_a="coinbase",
                venue_b="kraken",
                estimated_spread_bps=15.5,
            ),
            QuantumArbDecisionSummary(
                timestamp="2024-04-09T12:35:00.000Z",
                intent_id="test-intent-002",
                source_agent="quantumarb",
                asset_pair="ETH-USD",
                side="BEAR",
                decision="SELL",
                arb_type="cross_exchange",
                dry_run=False,
                confidence=0.68,
                timesfm_used=True,
                timesfm_rationale="High volatility",
                rationale_preview="Decision 2",
                venue_a="coinbase",
                venue_b="binance",
                estimated_spread_bps=8.2,
            ),
            QuantumArbDecisionSummary(
                timestamp="2024-04-09T12:36:00.000Z",
                intent_id="test-intent-003",
                source_agent="quantumarb",
                asset_pair="SOL-USD",
                side="BULL",
                decision="BUY",
                arb_type="cross_exchange",
                dry_run=False,
                confidence=0.82,
                timesfm_used=False,
                timesfm_rationale=None,
                rationale_preview="Decision 3",
                venue_a="coinbase",
                venue_b="kraken",
                estimated_spread_bps=12.0,
            ),
        ]
        
        contract = QuantumArbIntegrationContract()
        mapper = get_execution_mapper()
        
        execution_summaries = []
        
        for i, qd in enumerate(decisions):
            # Convert to AgentDecisionSummary using helper with positive quantity
            quantity = 1.0 + i  # Different quantities for each decision
            agent_decision = create_agent_decision_from_quantumarb(qd, default_quantity=quantity, default_units="USD")
            
            # Map to trade parameters
            mapping_result = mapper.map_decision_to_trade(agent_decision)
            
            # Get execution summary
            execution_summary = mapper.get_execution_summary(agent_decision, mapping_result)
            execution_summaries.append(execution_summary)
            
            # Verify each mapping succeeded
            assert mapping_result.success is True
            assert execution_summary["mapping_success"] is True
        
        # Verify we have 3 execution summaries
        assert len(execution_summaries) == 3
        
        # Verify different instruments
        instruments = [es["instrument"] for es in execution_summaries]
        assert "BTC-USD" in instruments
        assert "ETH-USD" in instruments
        assert "SOL-USD" in instruments
        
        # Verify different sides
        sides = [es["original_side"] for es in execution_summaries]
        assert "buy" in sides
        assert "sell" in sides


if __name__ == "__main__":
    pytest.main([__file__, "-v"])