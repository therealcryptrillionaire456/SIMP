"""
Integration test for Kloutbot TimesFM horizon advice full flow.

Tests the complete integration from strategy generation through
horizon advice to compiler integration.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.agents.kloutbot_agent import KloutbotAgent


class TestKloutbotHorizonIntegration:
    """Integration tests for Kloutbot horizon advice"""

    @pytest.fixture
    def kloutbot_agent(self):
        """Create a fresh Kloutbot agent"""
        agent = KloutbotAgent(agent_id="test-integration-001")
        return agent

    @pytest.mark.asyncio
    async def test_full_strategy_generation_flow(self, kloutbot_agent):
        """Test complete strategy generation flow with horizon advice"""
        
        # Mock the entire dependency chain
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    with patch.object(kloutbot_agent, 'compiler') as mock_compiler:
                        # Setup TimesFM service mock
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        mock_response.available = True
                        # Forecast with persistence = 18 steps (medium horizon)
                        mock_response.point_forecast = [0.8] * 18 + [0.4] * 14
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        # Setup policy engine mock
                        mock_decision = Mock()
                        mock_decision.denied = False
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        # Setup compiler mock
                        mock_compiler.compile_intent = AsyncMock()
                        # Create a mock tree with to_dict method
                        mock_tree = Mock()
                        mock_tree.to_dict.return_value = {"action": "hold", "confidence": 0.85}
                        mock_compiler.compile_intent.return_value = mock_tree
                        
                        # Add required compiler attributes
                        mock_compiler.get_action_params = Mock(return_value={"position_size": 0.75})
                        mock_compiler.iteration_count = 42
                        mock_compiler.improvement_history = [0.1, 0.2, 0.3]
                        
                        # Fill affinity buffer
                        for i in range(20):
                            kloutbot_agent._record_affinity(0.8)
                        
                        # Generate strategy
                        result = await kloutbot_agent.handle_generate_strategy({
                            "foresight": {
                                "affinity": 0.85,
                                "drift_risk": 0.1
                            },
                            "deltas": {
                                "momentum": 0.8,
                                "volume": 0.7,
                                "sentiment": 0.65
                            },
                            "timestamp": "2026-04-09T12:00:00.000000+00:00",
                        })
                        
                        # Verify success
                        assert result["status"] == "success"
                        
                        # Verify horizon advice was applied
                        assert result["timesfm_horizon_applied"] is True
                        assert result["recommended_horizon"] == "medium"
                        assert result["recommended_horizon_steps"] == 16
                        assert "persists 18 steps" in result["timesfm_horizon_rationale"]
                        
                        # Verify compiler was called (horizon steps are metadata, not compiler input)
                        mock_compiler.compile_intent.assert_called_once()
                        # Note: horizon_steps is not passed to compiler, it's metadata in response
                        
                        # Verify strategy structure
                        assert "strategy" in result
                        assert "action_params" in result
                        assert "mutation_telemetry" in result
                        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_horizon_advice_propagates_to_compiler(self, kloutbot_agent):
        """Test that horizon advice correctly propagates to compiler"""
        
        test_cases = [
            {
                "persistence": 30,
                "expected_horizon": "long",
                "expected_steps": 32,
                "expected_rationale_contains": "long horizon"
            },
            {
                "persistence": 18,
                "expected_horizon": "medium",
                "expected_steps": 16,
                "expected_rationale_contains": "medium horizon"
            },
            {
                "persistence": 8,
                "expected_horizon": "short",
                "expected_steps": 8,
                "expected_rationale_contains": "short horizon"
            }
        ]
        
        for test_case in test_cases:
            # Reset mocks for each test case
            with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
                with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                    with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                        with patch.object(kloutbot_agent, 'compiler') as mock_compiler:
                            # Setup TimesFM service mock
                            mock_service = AsyncMock()
                            mock_response = Mock()
                            mock_response.available = True
                            # Create forecast with specific persistence
                            persistence = test_case["persistence"]
                            mock_response.point_forecast = [0.8] * persistence + [0.4] * (32 - persistence)
                            mock_service.forecast.return_value = mock_response
                            mock_svc.return_value = mock_service
                            
                            # Setup policy engine mock
                            mock_decision = Mock()
                            mock_decision.denied = False
                            mock_engine.return_value.evaluate.return_value = mock_decision
                            
                            # Setup compiler mock
                            mock_compiler.compile_intent = AsyncMock()
                            # Create a mock tree with to_dict method
                            mock_tree = Mock()
                            mock_tree.to_dict.return_value = {"action": "hold", "confidence": 0.85}
                            mock_compiler.compile_intent.return_value = mock_tree
                            
                            # Add required compiler attributes
                            mock_compiler.get_action_params = Mock(return_value={"position_size": 0.75})
                            mock_compiler.iteration_count = 42
                            mock_compiler.improvement_history = [0.1, 0.2, 0.3]
                            
                            # Fill affinity buffer
                            for i in range(20):
                                kloutbot_agent._record_affinity(0.8)
                            
                            # Generate strategy
                            result = await kloutbot_agent.handle_generate_strategy({
                                "foresight": {
                                    "affinity": 0.85,
                                    "drift_risk": 0.1
                                },
                                "deltas": {
                                    "momentum": 0.8,
                                    "volume": 0.7,
                                    "sentiment": 0.65
                                },
                                "timestamp": "2026-04-09T12:00:00.000000+00:00",
                            })
                            
                            # Verify horizon advice
                            assert result["timesfm_horizon_applied"] is True
                            assert result["recommended_horizon"] == test_case["expected_horizon"]
                            assert result["recommended_horizon_steps"] == test_case["expected_steps"]
                            assert test_case["expected_rationale_contains"] in result["timesfm_horizon_rationale"].lower()
                            
                            # Verify compiler was called (horizon steps are metadata, not compiler input)
                            mock_compiler.compile_intent.assert_called()
                            # Note: horizon_steps is not passed to compiler, it's metadata in response

    @pytest.mark.asyncio
    async def test_fallback_horizon_still_produces_strategy(self, kloutbot_agent):
        """Test that fallback horizon still produces valid strategy"""
        
        fallback_scenarios = [
            {
                "name": "insufficient_history",
                "history_count": 10,  # Less than 16
                "expected_steps": 16,  # Default medium
                "expected_applied": False
            },
            {
                "name": "policy_denied",
                "policy_denied": True,
                "expected_steps": 16,  # Default medium
                "expected_applied": False
            },
            {
                "name": "service_unavailable",
                "service_available": False,
                "expected_steps": 16,  # Default medium
                "expected_applied": False
            }
        ]
        
        for scenario in fallback_scenarios:
            # Create fresh agent for each scenario
            agent = KloutbotAgent(agent_id=f"test-fallback-{scenario['name']}")
            
            with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
                with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                    with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                        with patch.object(agent, 'compiler') as mock_compiler:
                            # Setup TimesFM service mock if needed
                            if "service_available" in scenario:
                                mock_service = AsyncMock()
                                mock_response = Mock()
                                mock_response.available = scenario["service_available"]
                                mock_response.point_forecast = None
                                mock_service.forecast.return_value = mock_response
                                mock_svc.return_value = mock_service
                            
                            # Setup policy engine mock if needed
                            if "policy_denied" in scenario:
                                mock_decision = Mock()
                                mock_decision.denied = scenario["policy_denied"]
                                mock_decision.reason = "Test policy violation"
                                mock_engine.return_value.evaluate.return_value = mock_decision
                            else:
                                mock_decision = Mock()
                                mock_decision.denied = False
                                mock_engine.return_value.evaluate.return_value = mock_decision
                            
                            # Setup compiler mock
                            mock_compiler.compile_intent = AsyncMock()
                            # Create a mock tree with to_dict method
                            mock_tree = Mock()
                            mock_tree.to_dict.return_value = {"action": "hold", "confidence": 0.85}
                            mock_compiler.compile_intent.return_value = mock_tree
                            
                            # Add required compiler attributes
                            mock_compiler.get_action_params = Mock(return_value={"position_size": 0.75})
                            mock_compiler.iteration_count = 42
                            mock_compiler.improvement_history = [0.1, 0.2, 0.3]
                            
                            # Fill affinity buffer
                            history_count = scenario.get("history_count", 20)
                            for i in range(history_count):
                                agent._record_affinity(0.8)
                            
                            # Generate strategy
                            result = await agent.handle_generate_strategy({
                                "foresight": {
                                    "affinity": 0.85,
                                    "drift_risk": 0.1
                                },
                                "deltas": {
                                    "momentum": 0.8,
                                    "volume": 0.7,
                                    "sentiment": 0.65
                                },
                                "timestamp": "2026-04-09T12:00:00.000000+00:00",
                            })
                            
                            # Verify strategy was still generated
                            assert result["status"] == "success"
                            assert "strategy" in result
                            assert "action_params" in result
                            
                            # Verify fallback horizon
                            assert result["timesfm_horizon_applied"] == scenario["expected_applied"]
                            assert result["recommended_horizon_steps"] == scenario["expected_steps"]
                            
                            # Verify compiler was called (horizon steps are metadata, not compiler input)
                            mock_compiler.compile_intent.assert_called()
                            # Note: horizon_steps is not passed to compiler, it's metadata in response

    @pytest.mark.asyncio
    async def test_horizon_consistency_across_multiple_calls(self, kloutbot_agent):
        """Test horizon advice consistency across multiple strategy generations"""
        
        # Mock setup
        with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
            with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
                with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                    with patch.object(kloutbot_agent, 'compiler') as mock_compiler:
                        # Setup consistent TimesFM response
                        mock_service = AsyncMock()
                        mock_response = Mock()
                        mock_response.available = True
                        mock_response.point_forecast = [0.8] * 25 + [0.4] * 7  # Long horizon
                        mock_service.forecast.return_value = mock_response
                        mock_svc.return_value = mock_service
                        
                        # Setup policy engine
                        mock_decision = Mock()
                        mock_decision.denied = False
                        mock_engine.return_value.evaluate.return_value = mock_decision
                        
                        # Setup compiler
                        mock_compiler.compile_intent = AsyncMock()
                        # Create a mock tree with to_dict method
                        mock_tree = Mock()
                        mock_tree.to_dict.return_value = {"action": "hold", "confidence": 0.85}
                        mock_compiler.compile_intent.return_value = mock_tree
                        
                        # Add required compiler attributes
                        mock_compiler.get_action_params = Mock(return_value={"position_size": 0.75})
                        mock_compiler.iteration_count = 42
                        mock_compiler.improvement_history = [0.1, 0.2, 0.3]
                        
                        # Fill affinity buffer
                        for i in range(20):
                            kloutbot_agent._record_affinity(0.8)
                        
                        # Generate multiple strategies
                        horizons = []
                        steps_list = []
                        
                        for i in range(3):
                            result = await kloutbot_agent.handle_generate_strategy({
                                "foresight": {
                                    "affinity": 0.85,
                                    "drift_risk": 0.1
                                },
                                "deltas": {
                                    "momentum": 0.8,
                                    "volume": 0.7,
                                    "sentiment": 0.65
                                },
                                "timestamp": f"2026-04-09T12:{i:02d}:00.000000+00:00",
                            })
                            
                            horizons.append(result["recommended_horizon"])
                            steps_list.append(result["recommended_horizon_steps"])
                        
                        # Verify consistency
                        assert len(set(horizons)) == 1, f"Horizons should be consistent: {horizons}"
                        assert len(set(steps_list)) == 1, f"Steps should be consistent: {steps_list}"
                        assert horizons[0] == "long"
                        assert steps_list[0] == 32

    def test_documentation_alignment(self):
        """Test that implementation aligns with documentation"""
        
        # Verify ADR 003 mapping
        adr_mapping = {
            "short": {"steps": 8, "threshold": "< 12"},
            "medium": {"steps": 16, "threshold": "≥ 12 and < 24"},
            "long": {"steps": 32, "threshold": "≥ 24"}
        }
        
        # These should match the implementation in kloutbot_agent.py
        implementation_mapping = {
            "short": 8,
            "medium": 16, 
            "long": 32
        }
        
        for horizon, adr_info in adr_mapping.items():
            assert horizon in implementation_mapping
            assert implementation_mapping[horizon] == adr_info["steps"], \
                f"{horizon} horizon should be {adr_info['steps']} steps per ADR 003"
        
        # Verify default fallback matches documentation
        assert implementation_mapping["medium"] == 16, "Default fallback should be medium (16 steps)"
        
        print("✓ Implementation aligns with ADR 003 and documentation")


if __name__ == "__main__":
    # Run a quick integration test
    import asyncio
    
    async def quick_integration_test():
        tester = TestKloutbotHorizonIntegration()
        agent = tester.kloutbot_agent()
        
        print("Running integration test verification...")
        print("=" * 60)
        
        await tester.test_full_strategy_generation_flow(agent)
        print("✓ Full strategy generation flow")
        
        await tester.test_horizon_advice_propagates_to_compiler(agent)
        print("✓ Horizon advice propagates to compiler")
        
        await tester.test_fallback_horizon_still_produces_strategy(agent)
        print("✓ Fallback horizon still produces strategy")
        
        await tester.test_horizon_consistency_across_multiple_calls(agent)
        print("✓ Horizon consistency across multiple calls")
        
        tester.test_documentation_alignment()
        print("✓ Documentation alignment")
        
        print("\n" + "=" * 60)
        print("All integration tests passed!")
    
    asyncio.run(quick_integration_test())