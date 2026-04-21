"""
Fixed version of test_sprint18_scalability.py with proper test isolation.
"""

import asyncio
import pytest
import tempfile
import os
from pathlib import Path
from simp.server.broker import SimpBroker, BrokerConfig
from simp.server.agent_registry import AgentRegistryConfig


class TestDeadAgentCleanupFixed:
    """Fixed tests with proper AgentRegistry isolation."""
    
    @pytest.fixture
    def broker(self):
        """Create broker with isolated AgentRegistry using temporary file."""
        # Create temporary directory for test data
        temp_dir = tempfile.mkdtemp(prefix="simp_test_")
        temp_registry_file = os.path.join(temp_dir, "agent_registry.jsonl")
        
        # Create broker config
        config = BrokerConfig(max_agents=100, health_check_interval=60)
        
        # Create broker
        broker = SimpBroker(config)
        
        # Replace the AgentRegistry with one using temporary file
        # Note: This is a hack because broker doesn't expose AgentRegistry config
        # In production, we should modify broker to accept AgentRegistry config
        from simp.server.agent_registry import AgentRegistry
        registry_config = AgentRegistryConfig(path=temp_registry_file)
        broker.agent_registry = AgentRegistry(config=registry_config)
        broker.agents = broker.agent_registry  # Maintain backward compatibility
        
        yield broker
        
        # Cleanup
        broker.stop()
        # Remove temporary directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_agent_info_has_failure_counter(self, broker):
        """Registered agents should track health check failures."""
        broker.start()
        try:
            broker.register_agent(
                agent_id="test_agent_cleanup",
                agent_type="test",
                endpoint="http://localhost:9999",
                metadata={},
            )
            agent_info = broker.agents.get("test_agent_cleanup", {})
            assert "health_check_failures" in agent_info
            assert agent_info["health_check_failures"] == 0
        finally:
            broker.stop()
    
    def test_failure_counter_increments(self, broker):
        """Health check failure counter should increment."""
        broker.start()
        try:
            broker.register_agent(
                agent_id="test_fail_agent",
                agent_type="test",
                endpoint="http://localhost:9999",
                metadata={},
            )
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(broker._record_health_failure("test_fail_agent"))
                assert broker.agents["test_fail_agent"]["health_check_failures"] == 1
                assert broker.agents["test_fail_agent"]["status"] == "unreachable"
            finally:
                loop.close()
        finally:
            broker.stop()
    
    def test_auto_deregister_after_threshold(self, broker):
        """Agent should be auto-deregistered after 3 consecutive failures."""
        broker.start()
        try:
            broker.register_agent(
                agent_id="test_dead_agent",
                agent_type="test",
                endpoint="http://localhost:9999",
                metadata={},
            )
            loop = asyncio.new_event_loop()
            try:
                for _ in range(3):
                    loop.run_until_complete(broker._record_health_failure("test_dead_agent"))
                # Agent should be deregistered
                assert "test_dead_agent" not in broker.agents
            finally:
                loop.close()
        finally:
            broker.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])