import sys
import os
sys.path.insert(0, '/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp')

# Set environment variables
os.environ['SIMP_TIMESFM_ENABLED'] = 'true'
os.environ['SIMP_TIMESFM_SHADOW_MODE'] = 'false'

import asyncio
from unittest.mock import Mock, patch, AsyncMock
import pytest

# Import the agent class directly
from simp.agents.kloutbot_agent import KloutbotAgent

async def run_test():
    # Create the agent
    agent = KloutbotAgent(agent_id="test-kloutbot-001")
    
    # Mock TimesFM for long persistence
    with patch('simp.agents.kloutbot_agent.get_timesfm_service') as mock_svc:
        with patch('simp.agents.kloutbot_agent.make_agent_context_for') as mock_ctx:
            with patch('simp.agents.kloutbot_agent.PolicyEngine') as mock_engine:
                # Setup mocks
                mock_service = AsyncMock()
                mock_response = Mock()
                mock_response.available = True
                # Long persistence forecast
                mock_response.point_forecast = [0.8] * 32
                mock_service.forecast.return_value = mock_response
                mock_svc.return_value = mock_service
                
                mock_decision = Mock()
                mock_decision.denied = False
                mock_engine.return_value.evaluate.return_value = mock_decision
                
                # Mock compiler to return a simple tree
                mock_compiler = Mock()
                mock_tree = Mock()
                mock_tree.to_dict.return_value = {"tree": "test"}
                mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
                mock_compiler.get_action_params = Mock(return_value={"action": "test"})
                agent.compiler = mock_compiler
                
                # Fill affinity buffer
                for i in range(20):
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
                    "timestamp": "2026-04-09T05:52:27.731075+00:00",
                })
                
                print(f"Result: {result}")
                print(f"Status: {result.get('status')}")
                print(f"Error code: {result.get('error_code')}")
                print(f"Error message: {result.get('error_message')}")
                
                # Verify TimesFM horizon is reflected in response
                assert result["status"] == "success"
                assert "recommended_horizon" in result
                assert "recommended_horizon_steps" in result
                assert "timesfm_horizon_applied" in result
                assert "timesfm_horizon_rationale" in result
                
                # Verify long horizon was recommended
                assert result["recommended_horizon"] == "long"
                assert result["recommended_horizon_steps"] == 32
                assert result["timesfm_horizon_applied"] is True
                assert "long horizon" in result["timesfm_horizon_rationale"]

if __name__ == "__main__":
    asyncio.run(run_test())