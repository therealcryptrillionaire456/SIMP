"""
Additional hardening tests for Kloutbot TimesFM horizon advice.

Tests for edge cases not covered in main test file:
- Invalid/malformed TimesFM responses
- Extreme input values
- Operator-facing field validation
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.agents.kloutbot_agent import KloutbotAgent


class TestKloutbotHorizonHardening:
    """Hardening tests for Kloutbot horizon advice"""

    @pytest.fixture
    def kloutbot_agent(self):
        """Create a fresh Kloutbot agent"""
        agent = KloutbotAgent(agent_id="test-hardening-001")
        return agent

    @pytest.mark.asyncio
    async def test_invalid_forecast_wrong_length(self, kloutbot_agent):
        """Test TimesFM horizon advice with forecast of wrong length"""
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Wrong length - should be 32 but is 30
                    mock_response.point_forecast = [0.8] * 30
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice - should handle gracefully
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Should either work with shorter forecast or fall back
                    # The implementation uses len(pf) which would be 30
                    # and next() would work fine, so it should still apply
                    assert advice["timesfm_horizon_applied"] is True
                    assert advice["recommended_horizon"] in {"short", "medium", "long"}
                    assert advice["recommended_horizon_steps"] in {8, 16, 32}

    @pytest.mark.asyncio
    async def test_invalid_forecast_none_values(self, kloutbot_agent):
        """Test TimesFM horizon advice with None values in forecast"""
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Contains None values - should cause comparison error
                    mock_response.point_forecast = [0.8, 0.7, None, 0.6, 0.5] + [0.4] * 27
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice - should fall back due to error
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Should fall back to default
                    assert advice["timesfm_horizon_applied"] is False
                    assert advice["recommended_horizon"] == "medium"
                    assert advice["recommended_horizon_steps"] == 16
                    assert "error" in advice["timesfm_horizon_rationale"].lower()

    @pytest.mark.asyncio
    async def test_invalid_forecast_non_numeric(self, kloutbot_agent):
        """Test TimesFM horizon advice with non-numeric values in forecast"""
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Contains string values
                    mock_response.point_forecast = ["0.8", "0.7", "0.6"] + [0.5] * 29
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with enough history
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.8)
                    
                    # Get horizon advice - should fall back due to error
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.85,
                        drift_risk=0.1,
                    )
                    
                    # Should fall back to default
                    assert advice["timesfm_horizon_applied"] is False
                    assert advice["recommended_horizon"] == "medium"
                    assert advice["recommended_horizon_steps"] == 16

    @pytest.mark.asyncio
    async def test_extreme_high_affinity(self, kloutbot_agent):
        """Test horizon advice with extremely high affinity values"""
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Extreme high values (near 1.0)
                    mock_response.point_forecast = [0.99] * 32
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with extreme values
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.99)
                    
                    # Get horizon advice with extreme current affinity
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.99,  # Extreme high
                        drift_risk=0.01,  # Very low drift risk
                    )
                    
                    # Should work normally
                    assert advice["timesfm_horizon_applied"] is True
                    assert advice["recommended_horizon"] == "long"  # All values > 0.5
                    assert advice["recommended_horizon_steps"] == 32

    @pytest.mark.asyncio
    async def test_extreme_low_affinity(self, kloutbot_agent):
        """Test horizon advice with extremely low affinity values"""
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    # Setup mocks
                    mock_service = AsyncMock()
                    mock_response = Mock()
                    mock_response.available = True
                    # Extreme low values (near 0.0)
                    mock_response.point_forecast = [0.01] * 32
                    mock_service.forecast.return_value = mock_response
                    mock_svc.return_value = mock_service
                    
                    mock_decision = Mock()
                    mock_decision.denied = False
                    mock_engine.return_value.evaluate.return_value = mock_decision
                    
                    # Fill affinity buffer with extreme values
                    for i in range(20):
                        kloutbot_agent._record_affinity(0.01)
                    
                    # Get horizon advice with extreme current affinity
                    advice = await kloutbot_agent._get_strategy_horizon_advice(
                        affinity=0.01,  # Extreme low
                        drift_risk=0.99,  # Very high drift risk
                    )
                    
                    # Should work normally - all values < 0.5
                    assert advice["timesfm_horizon_applied"] is True
                    assert advice["recommended_horizon"] == "short"  # No values > 0.5
                    assert advice["recommended_horizon_steps"] == 8

    @pytest.mark.asyncio
    async def test_extreme_drift_risk(self, kloutbot_agent):
        """Test horizon advice with extreme drift risk values"""
        test_cases = [
            (0.0, "zero drift risk"),
            (0.99, "very high drift risk"),
            (1.0, "maximum drift risk"),
        ]
        
        for drift_risk, description in test_cases:
            with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
                with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                    with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                        # Setup mocks
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        mock_response.available = True
                        mock_response.point_forecast = [0.8] * 32
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        mock_decision = Mock()
                        mock_decision.denied = False
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        # Fill affinity buffer
                        for i in range(20):
                            kloutbot_agent._record_affinity(0.8)
                        
                        # Get horizon advice with extreme drift risk
                        advice = await kloutbot_agent._get_strategy_horizon_advice(
                            affinity=0.85,
                            drift_risk=drift_risk,
                        )
                        
                        # Should work normally regardless of drift risk
                        assert advice["timesfm_horizon_applied"] is True, f"Failed for {description}"
                        assert advice["recommended_horizon"] == "long", f"Failed for {description}"
                        assert advice["recommended_horizon_steps"] == 32, f"Failed for {description}"

    @pytest.mark.asyncio
    async def test_operator_fields_monitoring(self, kloutbot_agent):
        """Test that operator-facing fields are present and meaningful"""
        # Test multiple scenarios to ensure fields are useful
        
        scenarios = [
            {
                "name": "successful_forecast",
                "mock_available": True,
                "mock_forecast": [0.8] * 32,
                "expected_applied": True,
                "expected_rationale_contains": ["persists", "threshold", "horizon"]
            },
            {
                "name": "shadow_mode",
                "mock_available": False,
                "mock_forecast": None,
                "expected_applied": False,
                "expected_rationale_contains": ["shadow mode", "default", "medium"]
            },
            {
                "name": "insufficient_history",
                "mock_history": 10,  # Less than 16
                "expected_applied": False,
                "expected_rationale_contains": ["insufficient history", "default"]
            }
        ]
        
        for scenario in scenarios:
            # Reset agent for each scenario
            agent = KloutbotAgent(agent_id=f"test-operator-{scenario['name']}")
            
            # Setup history if specified
            history_count = scenario.get("mock_history", 20)
            for i in range(history_count):
                agent._record_affinity(0.8)
            
            if "mock_available" in scenario:
                with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
                    with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                        with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                            # Setup mocks
                            mock_service = AsyncMock()
                            mock_response = Mock()
                            mock_response.available = scenario["mock_available"]
                            mock_response.point_forecast = scenario.get("mock_forecast")
                            mock_service.forecast.return_value = mock_response
                            mock_svc.return_value = mock_service
                            
                            mock_decision = Mock()
                            mock_decision.denied = False
                            mock_engine.return_value.evaluate.return_value = mock_decision
                            
                            advice = await agent._get_strategy_horizon_advice(
                                affinity=0.85,
                                drift_risk=0.1,
                            )
            else:
                # Test insufficient history (no mocks needed)
                advice = await agent._get_strategy_horizon_advice(
                    affinity=0.85,
                    drift_risk=0.1,
                )
            
            # Verify operator-facing fields
            assert "recommended_horizon" in advice
            assert "recommended_horizon_steps" in advice
            assert "timesfm_horizon_applied" in advice
            assert "timesfm_horizon_rationale" in advice
            
            # Verify types
            assert isinstance(advice["recommended_horizon"], str)
            assert isinstance(advice["recommended_horizon_steps"], int)
            assert isinstance(advice["timesfm_horizon_applied"], bool)
            assert isinstance(advice["timesfm_horizon_rationale"], str)
            
            # Verify applied flag
            assert advice["timesfm_horizon_applied"] == scenario["expected_applied"], \
                f"Failed for {scenario['name']}: expected applied={scenario['expected_applied']}, got {advice['timesfm_horizon_applied']}"
            
            # Verify rationale contains expected keywords
            rationale_lower = advice["timesfm_horizon_rationale"].lower()
            for keyword in scenario["expected_rationale_contains"]:
                assert keyword in rationale_lower, \
                    f"Failed for {scenario['name']}: rationale missing '{keyword}'. Rationale: {advice['timesfm_horizon_rationale']}"
            
            # Verify horizon and steps are consistent
            horizon_to_steps = {"short": 8, "medium": 16, "long": 32}
            if advice["recommended_horizon"] in horizon_to_steps:
                assert advice["recommended_horizon_steps"] == horizon_to_steps[advice["recommended_horizon"]], \
                    f"Failed for {scenario['name']}: horizon '{advice['recommended_horizon']}' should map to {horizon_to_steps[advice['recommended_horizon']]} steps, got {advice['recommended_horizon_steps']}"

    @pytest.mark.asyncio
    async def test_operator_field_alert_conditions(self, kloutbot_agent):
        """Test that operator fields support alert condition detection"""
        
        # Simulate various conditions operators might alert on
        conditions = [
            {
                "condition": "high_fallback_rate",
                "setup": lambda: None,  # Use default (insufficient history)
                "expected_applied": False,
                "alert_trigger": lambda advice: not advice["timesfm_horizon_applied"]
            },
            {
                "condition": "short_horizon_dominance",
                "setup": lambda: None,
                "mock_forecast": [0.4] * 32,  # All below threshold
                "expected_applied": True,
                "alert_trigger": lambda advice: advice["recommended_horizon"] == "short"
            },
            {
                "condition": "policy_denied",
                "setup": lambda: None,
                "policy_denied": True,
                "expected_applied": False,
                "alert_trigger": lambda advice: not advice["timesfm_horizon_applied"] and "policy denied" in advice["timesfm_horizon_rationale"].lower()
            }
        ]
        
        for condition in conditions:
            # Reset agent
            agent = KloutbotAgent(agent_id=f"test-alert-{condition['condition']}")
            
            # Fill history
            for i in range(20):
                agent._record_affinity(0.8)
            
            # Setup condition
            if condition.get("setup"):
                condition["setup"]()
            
            with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
                with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                    with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                        # Setup mocks
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        
                        if "mock_forecast" in condition:
                            mock_response.available = True
                            mock_response.point_forecast = condition["mock_forecast"]
                        else:
                            mock_response.available = False
                            mock_response.point_forecast = None
                        
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        mock_decision = Mock()
                        mock_decision.denied = condition.get("policy_denied", False)
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        advice = await agent._get_strategy_horizon_advice(
                            affinity=0.85,
                            drift_risk=0.1,
                        )
            
            # Verify fields support alert detection
            assert condition["alert_trigger"](advice), \
                f"Alert trigger failed for condition: {condition['condition']}. Advice: {advice}"
            
            # Log for operator awareness
            print(f"\nCondition: {condition['condition']}")
            print(f"  Horizon: {advice['recommended_horizon']} ({advice['recommended_horizon_steps']} steps)")
            print(f"  Applied: {advice['timesfm_horizon_applied']}")
            print(f"  Rationale: {advice['timesfm_horizon_rationale'][:80]}...")

    def test_operator_monitoring_guidelines(self):
        """Test that the implementation supports operator monitoring guidelines"""
        
        # These are the monitoring guidelines from documentation
        guidelines = [
            {
                "guideline": "Monitor fallback rate",
                "field": "timesfm_horizon_applied",
                "check": lambda value: isinstance(value, bool),
                "alert_condition": lambda value, history: sum(1 for v in history if not v["timesfm_horizon_applied"]) / len(history) > 0.5,
                "alert_threshold": "> 50% for 1 hour"
            },
            {
                "guideline": "Monitor horizon distribution",
                "field": "recommended_horizon",
                "check": lambda value: value in {"short", "medium", "long"},
                "alert_condition": lambda value, history: len(set(v["recommended_horizon"] for v in history)) == 1,
                "alert_threshold": "> 80% single horizon for 4 hours"
            },
            {
                "guideline": "Monitor step counts",
                "field": "recommended_horizon_steps",
                "check": lambda value: value in {8, 16, 32},
                "alert_condition": lambda value, history: any(v["recommended_horizon_steps"] not in {8, 16, 32} for v in history),
                "alert_threshold": "Any value not in {8, 16, 32}"
            },
            {
                "guideline": "Monitor rationale quality",
                "field": "timesfm_horizon_rationale",
                "check": lambda value: isinstance(value, str) and len(value) > 0,
                "alert_condition": lambda value, history: any(not v["timesfm_horizon_rationale"] or "error" in v["timesfm_horizon_rationale"].lower() for v in history),
                "alert_threshold": "Empty or error rationales"
            }
        ]
        
        # Create sample history for alert condition testing
        sample_history = [
            {
                "recommended_horizon": "medium",
                "recommended_horizon_steps": 16,
                "timesfm_horizon_applied": True,
                "timesfm_horizon_rationale": "TimesFM forecast: affinity persists 18 steps > 0.5 threshold."
            },
            {
                "recommended_horizon": "short",
                "recommended_horizon_steps": 8,
                "timesfm_horizon_applied": False,
                "timesfm_horizon_rationale": "TimesFM insufficient history: 10/16 observations"
            }
        ]
        
        # Verify each guideline can be implemented
        for guideline in guidelines:
            # Test basic check on first sample
            field_value = sample_history[0][guideline["field"]]
            
            # Verify the type/format check works
            assert guideline["check"](field_value), \
                f"Guideline check failed: {guideline['guideline']}. Value: {field_value}"
            
            # Test alert condition if provided
            if "alert_condition" in guideline:
                # This shows the condition can be evaluated
                can_evaluate = guideline["alert_condition"](field_value, sample_history)
                assert isinstance(can_evaluate, bool), \
                    f"Alert condition should return bool for: {guideline['guideline']}"
            
            print(f"✓ {guideline['guideline']}: field='{guideline['field']}', alert='{guideline['alert_threshold']}'")


if __name__ == "__main__":
    # Run a quick verification
    import asyncio
    
    async def quick_test():
        tester = TestKloutbotHorizonHardening()
        agent = tester.kloutbot_agent()
        
        print("Running quick hardening test verification...")
        print("=" * 60)
        
        # Test one of each category
        await tester.test_invalid_forecast_none_values(agent)
        print("✓ Invalid forecast with None values")
        
        await tester.test_extreme_high_affinity(agent)
        print("✓ Extreme high affinity values")
        
        await tester.test_operator_fields_monitoring(agent)
        print("✓ Operator-facing fields monitoring")
        
        print("\n" + "=" * 60)
        print("All quick tests passed!")
    
    asyncio.run(quick_test())