"""
Tests for TimesFM policy engine.
"""
import pytest
from unittest.mock import Mock, patch

from simp.integrations.timesfm_policy_engine import (
    AgentContext,
    PolicyDecision,
    PolicyEngine,
    make_agent_context_for,
)


class TestTimesFMPolicyEngine:
    """Test TimesFM policy engine functionality."""
    
    def test_agent_context_creation(self):
        """Test AgentContext dataclass."""
        context = AgentContext(
            agent_id="test_agent",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=100,
            requesting_handler="handle_trade",
            extra={"max_horizon": 30},
        )
        assert context.agent_id == "test_agent"
        assert context.series_id == "test:series:1"
        assert context.min_series_length == 100
        assert context.requesting_handler == "handle_trade"
        assert context.q1_utility_score == 5
        assert context.q3_shadow_confirmed is True
        assert context.q8_nonblocking is True
        assert context.extra == {"max_horizon": 30}
    
    def test_policy_decision_denied(self):
        """Test PolicyDecision denied property."""
        # Allowed decision
        allowed = PolicyDecision(
            approved=True,
            reason="All requirements met",
            violations=[],
            agent_id="test_agent",
            series_id="test:series:1",
        )
        assert allowed.denied is False
        
        # Denied decision
        denied = PolicyDecision(
            approved=False,
            reason="Q1 assessment failed",
            violations=["Q1 utility score too low"],
            agent_id="test_agent",
            series_id="test:series:1",
        )
        assert denied.denied is True
        
        # Test string representation
        assert "APPROVED" in str(allowed)
        assert "DENIED" in str(denied)
    
    def test_q1_utility_score_criteria(self):
        """Test Q1 utility score criteria (agent capability)."""
        engine = PolicyEngine()
        
        # Agent with sufficient Q1 score (5 = critical utility)
        context = AgentContext(
            agent_id="quantumarb",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=100,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is True
        assert "All policy checks passed" in decision.reason
        
        # Agent with insufficient Q1 score (1 = minimal utility)
        context = AgentContext(
            agent_id="new_agent",
            series_id="test:series:1",
            q1_utility_score=1,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=100,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is False
        assert "Q1_UTILITY" in decision.reason
        assert "1" in decision.reason  # Score in reason
    
    def test_q3_shadow_requirement(self):
        """Test Q3 shadow mode requirement."""
        engine = PolicyEngine()
        
        # Agent with shadow confirmed
        context = AgentContext(
            agent_id="quantumarb",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,  # Shadow confirmed
            q8_nonblocking=True,
            min_series_length=100,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is True
        
        # Agent without shadow confirmed
        context = AgentContext(
            agent_id="new_agent",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=False,  # No shadow confirmation
            q8_nonblocking=True,
            min_series_length=100,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is False
        assert "Q3_SHADOW" in decision.reason
    
    def test_q8_nonblocking_requirement(self):
        """Test Q8 non-blocking requirement."""
        engine = PolicyEngine()
        
        # Agent with non-blocking confirmed
        context = AgentContext(
            agent_id="quantumarb",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,  # Non-blocking confirmed
            min_series_length=100,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is True
        
        # Agent without non-blocking (should still pass - not a hard requirement)
        context = AgentContext(
            agent_id="new_agent",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=False,  # Blocking agent
            min_series_length=100,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        # Q8 is a hard requirement based on the policy engine
        assert decision.approved is False
        assert "Q8_NONBLOCKING" in decision.reason
    
    def test_min_series_length_requirement(self):
        """Test minimum series length requirement."""
        engine = PolicyEngine()
        
        # Sufficient series length
        context = AgentContext(
            agent_id="quantumarb",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=100,  # Sufficient
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is True
        
        # Insufficient series length
        context = AgentContext(
            agent_id="quantumarb",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=10,  # Too short
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is False
        assert "MIN_SERIES_LENGTH" in decision.reason
    
    def test_policy_engine_evaluation_flow(self):
        """Test complete policy evaluation flow."""
        engine = PolicyEngine()
        
        # Test all checks passing
        context = AgentContext(
            agent_id="quantumarb",
            series_id="btc:usd:spread",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=200,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is True
        assert "All policy checks passed" in decision.reason
        
        # Test multiple failures
        context = AgentContext(
            agent_id="new_agent",
            series_id="btc:usd:spread",
            q1_utility_score=1,
            q3_shadow_confirmed=False,
            q8_nonblocking=False,
            min_series_length=5,
            requesting_handler="handle_trade",
        )
        decision = engine.evaluate(context)
        assert decision.approved is False
        assert len(decision.violations) >= 3  # Q1, Q3, series length
    
    def test_make_agent_context_for_function(self):
        """Test helper function to create agent context."""
        # Mock the assessment data
        mock_assessments = {
            "quantumarb": {
                "q1_utility_score": 5,
                "q3_shadow_confirmed": True,
                "q8_nonblocking": True,
            }
        }
        
        with patch.dict('simp.integrations.timesfm_policy_engine._AGENT_ASSESSMENTS', mock_assessments):
            context = make_agent_context_for(
                agent_id="quantumarb",
                series_id="test:series:1",
                series_length=100,
                requesting_handler="handle_trade",
            )
            
            assert context.agent_id == "quantumarb"
            assert context.series_id == "test:series:1"
            assert context.min_series_length == 100
            assert context.requesting_handler == "handle_trade"
            assert context.q1_utility_score == 5
            assert context.q3_shadow_confirmed is True
            assert context.q8_nonblocking is True
            
            # Test with unknown agent (should get defaults)
            context = make_agent_context_for(
                agent_id="unknown_agent",
                series_id="test:series:1",
                series_length=100,
                requesting_handler="handle_trade",
            )
            assert context.q1_utility_score == 1  # Default
            assert context.q3_shadow_confirmed is False  # Default
            assert context.q8_nonblocking is True  # Default
    
    def test_default_policy_allows_when_requirements_met(self):
        """Test default policy allows when all requirements are met."""
        engine = PolicyEngine()
        
        # Ideal agent context
        context = AgentContext(
            agent_id="quantumarb",
            series_id="test:series:1",
            q1_utility_score=5,
            q3_shadow_confirmed=True,
            q8_nonblocking=True,
            min_series_length=100,
            requesting_handler="handle_trade",
        )
        
        decision = engine.evaluate(context)
        assert decision.approved is True
    
    def test_policy_denial_reasons(self):
        """Test policy denial includes specific reasons."""
        engine = PolicyEngine()
        
        # Test multiple failures
        context = AgentContext(
            agent_id="new_agent",
            series_id="test:series:1",
            q1_utility_score=1,
            q3_shadow_confirmed=False,
            q8_nonblocking=False,
            min_series_length=5,
            requesting_handler="handle_trade",
        )
        
        decision = engine.evaluate(context)
        assert decision.approved is False
        # Should mention failures in violations list
        assert len(decision.violations) > 0
        # Check that violations are included in reason
        for violation in decision.violations:
            assert violation in decision.reason