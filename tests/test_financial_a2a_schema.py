"""
Tests for A2A/FinancialOps core schemas.

These tests verify that:
- Schemas can be constructed with valid data
- Invalid data is rejected with appropriate errors
- Optional fields default safely
- Serialization/deserialization works correctly
"""

import pytest
from datetime import datetime
from simp.financial.a2a_schema import (
    AgentDecisionSummary,
    PortfolioPosture,
    A2APlan,
    Side,
    RiskPosture,
    ExecutionMode,
    validate_agent_decision_summary,
    validate_portfolio_posture,
    validate_a2a_plan,
)


class TestAgentDecisionSummary:
    """Tests for AgentDecisionSummary schema."""
    
    def test_create_valid_summary(self):
        """Test creating a valid agent decision summary."""
        summary = AgentDecisionSummary(
            agent_name="quantumarb",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=1000.0,
            units="USD",
            confidence=0.85,
            horizon_days=7,
            volatility_posture="high",
            timesfm_used=True,
            rationale="Arbitrage opportunity detected",
        )
        
        assert summary.agent_name == "quantumarb"
        assert summary.instrument == "BTC-USD"
        assert summary.side == Side.BUY
        assert summary.quantity == 1000.0
        assert summary.units == "USD"
        assert summary.confidence == 0.85
        assert summary.horizon_days == 7
        assert summary.volatility_posture == "high"
        assert summary.timesfm_used is True
        assert summary.rationale == "Arbitrage opportunity detected"
        assert isinstance(summary.timestamp, str)
    
    def test_create_minimal_summary(self):
        """Test creating a summary with only required fields."""
        summary = AgentDecisionSummary(
            agent_name="kashclaw",
            instrument="ETH-USD",
            side=Side.SELL,
            quantity=5.0,
            units="ETH",
        )
        
        assert summary.agent_name == "kashclaw"
        assert summary.instrument == "ETH-USD"
        assert summary.side == Side.SELL
        assert summary.quantity == 5.0
        assert summary.units == "ETH"
        assert summary.confidence is None
        assert summary.horizon_days is None
        assert summary.volatility_posture is None
        assert summary.timesfm_used is False
        assert summary.rationale is None
        assert isinstance(summary.timestamp, str)
    
    def test_side_enum_conversion(self):
        """Test that string sides are converted to Side enum."""
        summary = AgentDecisionSummary(
            agent_name="test",
            instrument="BTC-USD",
            side="buy",  # String instead of enum
            quantity=100.0,
            units="USD",
        )
        
        assert summary.side == Side.BUY
    
    def test_invalid_side_rejected(self):
        """Test that invalid side values are rejected."""
        with pytest.raises(ValueError, match="side must be one of"):
            AgentDecisionSummary(
                agent_name="test",
                instrument="BTC-USD",
                side="invalid_side",
                quantity=100.0,
                units="USD",
            )
    
    def test_negative_quantity_rejected(self):
        """Test that negative quantities are rejected."""
        with pytest.raises(ValueError, match="quantity must be non-negative"):
            AgentDecisionSummary(
                agent_name="test",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=-100.0,
                units="USD",
            )
    
    def test_zero_quantity_rejected_for_buy_sell(self):
        """Test that zero quantities are rejected for BUY/SELL decisions."""
        with pytest.raises(ValueError, match="quantity must be positive for BUY/SELL decisions"):
            AgentDecisionSummary(
                agent_name="test",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=0.0,
                units="USD",
            )
    
    def test_invalid_confidence_rejected(self):
        """Test that invalid confidence values are rejected."""
        with pytest.raises(ValueError, match="confidence must be between"):
            AgentDecisionSummary(
                agent_name="test",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
                confidence=1.5,  # > 1.0
            )
    
    def test_serialization_deserialization(self):
        """Test serialization to dict and deserialization from dict."""
        original = AgentDecisionSummary(
            agent_name="kloutbot",
            instrument="AAPL",
            side=Side.HOLD,
            quantity=50.0,
            units="shares",
            confidence=0.6,
            horizon_days=30,
            timesfm_used=False,
            rationale="Market consolidation phase",
        )
        
        # Serialize to dict
        data = original.to_dict()
        
        # Deserialize from dict
        restored = AgentDecisionSummary.from_dict(data)
        
        # Verify equality
        assert restored.agent_name == original.agent_name
        assert restored.instrument == original.instrument
        assert restored.side == original.side
        assert restored.quantity == original.quantity
        assert restored.units == original.units
        assert restored.confidence == original.confidence
        assert restored.horizon_days == original.horizon_days
        assert restored.timesfm_used == original.timesfm_used
        assert restored.rationale == original.rationale
    
    def test_validate_helper_function(self):
        """Test the validate_agent_decision_summary helper function."""
        data = {
            "agent_name": "quantumarb",
            "instrument": "BTC-USD",
            "side": "buy",
            "quantity": 1000.0,
            "units": "USD",
            "confidence": 0.85,
        }
        
        summary = validate_agent_decision_summary(data)
        assert isinstance(summary, AgentDecisionSummary)
        assert summary.agent_name == "quantumarb"
        assert summary.side == Side.BUY


class TestPortfolioPosture:
    """Tests for PortfolioPosture schema."""
    
    def test_create_valid_posture(self):
        """Test creating a valid portfolio posture."""
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 5000.0, "ETH-USD": -2000.0},
            risk_posture=RiskPosture.NEUTRAL,
            max_leverage=3.0,
            per_instrument_caps={"BTC-USD": 10000.0, "ETH-USD": 5000.0},
            constraints=["Max daily loss: 5%", "No overnight positions"],
        )
        
        assert posture.aggregate_exposure == {"BTC-USD": 5000.0, "ETH-USD": -2000.0}
        assert posture.risk_posture == RiskPosture.NEUTRAL
        assert posture.max_leverage == 3.0
        assert posture.per_instrument_caps == {"BTC-USD": 10000.0, "ETH-USD": 5000.0}
        assert posture.constraints == ["Max daily loss: 5%", "No overnight positions"]
        assert isinstance(posture.timestamp, str)
    
    def test_create_minimal_posture(self):
        """Test creating a posture with only required fields."""
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 1000.0},
            risk_posture=RiskPosture.CONSERVATIVE,
        )
        
        assert posture.aggregate_exposure == {"BTC-USD": 1000.0}
        assert posture.risk_posture == RiskPosture.CONSERVATIVE
        assert posture.max_leverage is None
        assert posture.per_instrument_caps is None
        assert posture.constraints is None
        assert isinstance(posture.timestamp, str)
    
    def test_risk_posture_enum_conversion(self):
        """Test that string risk postures are converted to RiskPosture enum."""
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 1000.0},
            risk_posture="aggressive",  # String instead of enum
        )
        
        assert posture.risk_posture == RiskPosture.AGGRESSIVE
    
    def test_invalid_risk_posture_rejected(self):
        """Test that invalid risk posture values are rejected."""
        with pytest.raises(ValueError, match="risk_posture must be one of"):
            PortfolioPosture(
                aggregate_exposure={"BTC-USD": 1000.0},
                risk_posture="invalid_posture",
            )
    
    def test_empty_instrument_rejected(self):
        """Test that empty instrument keys are rejected."""
        with pytest.raises(ValueError, match="instrument keys must be non-empty strings"):
            PortfolioPosture(
                aggregate_exposure={"": 1000.0},  # Empty instrument key
                risk_posture=RiskPosture.NEUTRAL,
            )
    
    def test_negative_cap_rejected(self):
        """Test that negative per-instrument caps are rejected."""
        with pytest.raises(ValueError, match="cap values must be positive"):
            PortfolioPosture(
                aggregate_exposure={"BTC-USD": 1000.0},
                risk_posture=RiskPosture.NEUTRAL,
                per_instrument_caps={"BTC-USD": -5000.0},  # Negative cap
            )
    
    def test_serialization_deserialization(self):
        """Test serialization to dict and deserialization from dict."""
        original = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 5000.0, "ETH-USD": -2000.0},
            risk_posture=RiskPosture.AGGRESSIVE,
            max_leverage=5.0,
            per_instrument_caps={"BTC-USD": 20000.0},
            constraints=["High risk tolerance"],
        )
        
        # Serialize to dict
        data = original.to_dict()
        
        # Deserialize from dict
        restored = PortfolioPosture.from_dict(data)
        
        # Verify equality
        assert restored.aggregate_exposure == original.aggregate_exposure
        assert restored.risk_posture == original.risk_posture
        assert restored.max_leverage == original.max_leverage
        assert restored.per_instrument_caps == original.per_instrument_caps
        assert restored.constraints == original.constraints
    
    def test_validate_helper_function(self):
        """Test the validate_portfolio_posture helper function."""
        data = {
            "aggregate_exposure": {"BTC-USD": 1000.0},
            "risk_posture": "conservative",
            "max_leverage": 2.0,
        }
        
        posture = validate_portfolio_posture(data)
        assert isinstance(posture, PortfolioPosture)
        assert posture.risk_posture == RiskPosture.CONSERVATIVE
        assert posture.max_leverage == 2.0


class TestA2APlan:
    """Tests for A2APlan schema."""
    
    def test_create_valid_plan(self):
        """Test creating a valid A2A plan."""
        # Create sample decisions
        decision1 = AgentDecisionSummary(
            agent_name="quantumarb",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=1000.0,
            units="USD",
        )
        
        decision2 = AgentDecisionSummary(
            agent_name="kashclaw",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=500.0,
            units="USD",
        )
        
        # Create portfolio posture
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 1500.0},
            risk_posture=RiskPosture.NEUTRAL,
        )
        
        # Create A2A plan
        plan = A2APlan(
            decisions=[decision1, decision2],
            portfolio_posture=posture,
            execution_allowed=False,
            execution_reason="Multiple agents agree, but safety checks pending",
            execution_mode=ExecutionMode.SIMULATED_ONLY,
            safety_checks_passed=["Agent consensus", "Position size within limits"],
            safety_checks_failed=["Risk assessment incomplete"],
        )
        
        assert len(plan.decisions) == 2
        assert plan.portfolio_posture == posture
        assert plan.execution_allowed is False
        assert plan.execution_reason == "Multiple agents agree, but safety checks pending"
        assert plan.execution_mode == ExecutionMode.SIMULATED_ONLY
        assert plan.safety_checks_passed == ["Agent consensus", "Position size within limits"]
        assert plan.safety_checks_failed == ["Risk assessment incomplete"]
        assert isinstance(plan.timestamp, str)
    
    def test_create_minimal_plan(self):
        """Test creating a plan with only required fields."""
        decision = AgentDecisionSummary(
            agent_name="kloutbot",
            instrument="AAPL",
            side=Side.HOLD,
            quantity=0.0,
            units="shares",
        )
        
        posture = PortfolioPosture(
            aggregate_exposure={"AAPL": 0.0},
            risk_posture=RiskPosture.CONSERVATIVE,
        )
        
        plan = A2APlan(
            decisions=[decision],
            portfolio_posture=posture,
        )
        
        assert len(plan.decisions) == 1
        assert plan.portfolio_posture == posture
        assert plan.execution_allowed is False  # Default
        assert plan.execution_reason == "Default: execution disabled in this phase"
        assert plan.execution_mode == ExecutionMode.SIMULATED_ONLY
        assert plan.safety_checks_passed == []
        assert plan.safety_checks_failed == []
    
    def test_execution_mode_enum_conversion(self):
        """Test that string execution modes are converted to ExecutionMode enum."""
        decision = AgentDecisionSummary(
            agent_name="test",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=100.0,
            units="USD",
        )
        
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 100.0},
            risk_posture=RiskPosture.NEUTRAL,
        )
        
        plan = A2APlan(
            decisions=[decision],
            portfolio_posture=posture,
            execution_mode="live_candidate",  # String instead of enum
        )
        
        assert plan.execution_mode == ExecutionMode.LIVE_CANDIDATE
    
    def test_invalid_execution_mode_rejected(self):
        """Test that invalid execution mode values are rejected."""
        decision = AgentDecisionSummary(
            agent_name="test",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=100.0,
            units="USD",
        )
        
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 100.0},
            risk_posture=RiskPosture.NEUTRAL,
        )
        
        with pytest.raises(ValueError, match="execution_mode must be one of"):
            A2APlan(
                decisions=[decision],
                portfolio_posture=posture,
                execution_mode="invalid_mode",
            )
    
    def test_serialization_deserialization(self):
        """Test serialization to dict and deserialization from dict."""
        # Create original plan
        decision = AgentDecisionSummary(
            agent_name="quantumarb",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=1000.0,
            units="USD",
            confidence=0.8,
        )
        
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 1000.0},
            risk_posture=RiskPosture.AGGRESSIVE,
            max_leverage=3.0,
        )
        
        original = A2APlan(
            decisions=[decision],
            portfolio_posture=posture,
            execution_allowed=True,
            execution_reason="All safety checks passed",
            execution_mode=ExecutionMode.SIMULATED_ONLY,
            safety_checks_passed=["Risk assessment", "Position limits", "Agent consensus"],
        )
        
        # Serialize to dict
        data = original.to_dict()
        
        # Deserialize from dict
        restored = A2APlan.from_dict(data)
        
        # Verify equality of key fields
        assert len(restored.decisions) == len(original.decisions)
        assert restored.decisions[0].agent_name == original.decisions[0].agent_name
        assert restored.decisions[0].side == original.decisions[0].side
        assert restored.portfolio_posture.risk_posture == original.portfolio_posture.risk_posture
        assert restored.execution_allowed == original.execution_allowed
        assert restored.execution_reason == original.execution_reason
        assert restored.execution_mode == original.execution_mode
        assert restored.safety_checks_passed == original.safety_checks_passed
    
    def test_validate_helper_function(self):
        """Test the validate_a2a_plan helper function."""
        data = {
            "decisions": [
                {
                    "agent_name": "quantumarb",
                    "instrument": "BTC-USD",
                    "side": "buy",
                    "quantity": 1000.0,
                    "units": "USD",
                }
            ],
            "portfolio_posture": {
                "aggregate_exposure": {"BTC-USD": 1000.0},
                "risk_posture": "neutral",
            },
            "execution_allowed": False,
            "execution_reason": "Test plan",
        }
        
        plan = validate_a2a_plan(data)
        assert isinstance(plan, A2APlan)
        assert len(plan.decisions) == 1
        assert plan.decisions[0].agent_name == "quantumarb"
        assert plan.portfolio_posture.risk_posture == RiskPosture.NEUTRAL
        assert plan.execution_allowed is False


class TestSchemaIntegration:
    """Integration tests for schema validation and error handling."""
    
    def test_all_schemas_together(self):
        """Test creating and validating all schemas together."""
        # Create multiple agent decisions
        decisions = [
            AgentDecisionSummary(
                agent_name="quantumarb",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=1000.0,
                units="USD",
                confidence=0.85,
                timesfm_used=True,
            ),
            AgentDecisionSummary(
                agent_name="kashclaw",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=500.0,
                units="USD",
                confidence=0.7,
                timesfm_used=False,
            ),
            AgentDecisionSummary(
                agent_name="kloutbot",
                instrument="BTC-USD",
                side=Side.HOLD,
                quantity=0.0,
                units="USD",
                confidence=0.5,
                rationale="Market uncertainty",
            ),
        ]
        
        # Create portfolio posture
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 1500.0},
            risk_posture=RiskPosture.NEUTRAL,
            max_leverage=2.0,
            constraints=["Max position: $2000", "Stop loss: 10%"],
        )
        
        # Create A2A plan
        plan = A2APlan(
            decisions=decisions,
            portfolio_posture=posture,
            execution_allowed=False,
            execution_reason="Conflicting agent signals",
            safety_checks_failed=["Agent consensus"],
        )
        
        # Verify the structure
        assert len(plan.decisions) == 3
        assert plan.portfolio_posture.aggregate_exposure["BTC-USD"] == 1500.0
        assert plan.execution_allowed is False
        assert "Agent consensus" in plan.safety_checks_failed
    
    def test_error_messages_clear(self):
        """Test that error messages are clear and actionable."""
        # Test missing required field
        with pytest.raises(TypeError, match="missing.*required"):
            AgentDecisionSummary(
                # Missing agent_name
                instrument="BTC-USD",
                side=Side.BUY,
                quantity=100.0,
                units="USD",
            )
        
        # Test invalid type
        with pytest.raises(ValueError, match="must be a"):
            AgentDecisionSummary(
                agent_name="test",
                instrument="BTC-USD",
                side=Side.BUY,
                quantity="not_a_number",  # Wrong type
                units="USD",
            )


class TestSchemaContracts:
    """Contract tests to prevent schema drift."""
    
    def test_agent_decision_summary_required_fields(self):
        """Test that AgentDecisionSummary has required fields."""
        # Create a valid instance
        decision = AgentDecisionSummary(
            agent_name="test",
            instrument="BTC-USD",
            side=Side.BUY,
            quantity=100.0,
            units="USD"
        )
        
        # Check required fields exist
        assert hasattr(decision, 'agent_name')
        assert hasattr(decision, 'instrument')
        assert hasattr(decision, 'side')
        assert hasattr(decision, 'quantity')
        assert hasattr(decision, 'units')
        
        # Check field types
        assert isinstance(decision.agent_name, str)
        assert isinstance(decision.instrument, str)
        assert isinstance(decision.side, Side)
        assert isinstance(decision.quantity, float)
        assert isinstance(decision.units, str)
        
        # Check optional fields exist (even if None)
        assert hasattr(decision, 'confidence')
        assert hasattr(decision, 'horizon_days')
        assert hasattr(decision, 'volatility_posture')
        assert hasattr(decision, 'timesfm_used')
        assert hasattr(decision, 'rationale')
        assert hasattr(decision, 'timestamp')
    
    def test_portfolio_posture_required_fields(self):
        """Test that PortfolioPosture has required fields."""
        posture = PortfolioPosture(
            aggregate_exposure={"BTC-USD": 100.0},
            risk_posture=RiskPosture.NEUTRAL
        )
        
        # Check required fields
        assert hasattr(posture, 'aggregate_exposure')
        assert hasattr(posture, 'risk_posture')
        
        # Check field types
        assert isinstance(posture.aggregate_exposure, dict)
        assert isinstance(posture.risk_posture, RiskPosture)
        
        # Check optional fields exist
        assert hasattr(posture, 'max_leverage')
        assert hasattr(posture, 'per_instrument_caps')
        assert hasattr(posture, 'constraints')
        assert hasattr(posture, 'timestamp')
    
    def test_a2a_plan_required_fields(self):
        """Test that A2APlan has required fields."""
        plan = A2APlan(
            decisions=[],
            portfolio_posture=PortfolioPosture(
                aggregate_exposure={},
                risk_posture=RiskPosture.CONSERVATIVE
            ),
            execution_allowed=False,
            execution_reason="Test"
        )
        
        # Check required fields
        assert hasattr(plan, 'decisions')
        assert hasattr(plan, 'portfolio_posture')
        assert hasattr(plan, 'execution_allowed')
        assert hasattr(plan, 'execution_reason')
        
        # Check field types
        assert isinstance(plan.decisions, list)
        assert isinstance(plan.portfolio_posture, PortfolioPosture)
        assert isinstance(plan.execution_allowed, bool)
        assert isinstance(plan.execution_reason, str)
        
        # Check optional fields exist (based on actual schema)
        assert hasattr(plan, 'safety_checks_passed')
        assert hasattr(plan, 'safety_checks_failed')
        assert hasattr(plan, 'execution_mode')
        assert hasattr(plan, 'timestamp')
        # Note: plan_id is not a field in the current schema
    
    def test_enum_values_stable(self):
        """Test that enum values remain stable."""
        # Side enum
        assert Side.BUY.value == "buy"
        assert Side.SELL.value == "sell"
        assert Side.HOLD.value == "hold"
        
        # RiskPosture enum
        assert RiskPosture.CONSERVATIVE.value == "conservative"
        assert RiskPosture.NEUTRAL.value == "neutral"
        assert RiskPosture.AGGRESSIVE.value == "aggressive"
        
        # ExecutionMode enum
        assert ExecutionMode.SIMULATED_ONLY.value == "simulated_only"
        assert ExecutionMode.LIVE_CANDIDATE.value == "live_candidate"
    
    def test_aggregator_function_signature(self):
        """Test that build_a2a_plan function signature remains stable."""
        from simp.financial.a2a_aggregator import build_a2a_plan
        import inspect
        
        # Get function signature
        sig = inspect.signature(build_a2a_plan)
        
        # Check it has the right parameter
        assert "agent_decisions" in sig.parameters
        
        # Check return type annotation
        return_annotation = sig.return_annotation
        assert "A2APlan" in str(return_annotation)