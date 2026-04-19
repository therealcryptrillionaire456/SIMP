"""
Test isolation for AgentRegistry persistence.

This module demonstrates proper test isolation techniques for AgentRegistry
to prevent tests from interfering with each other due to disk persistence.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from simp.server.agent_registry import AgentRegistry, AgentRegistryConfig


class TestAgentRegistryIsolation:
    """Test isolation patterns for AgentRegistry."""
    
    def test_basic_isolation_with_tempfile(self):
        """Test AgentRegistry with temporary file for isolation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            # Create registry with temporary file
            config = AgentRegistryConfig(path=temp_file)
            registry = AgentRegistry(config=config)
            
            # Register an agent
            registry.register("test_agent", {"endpoint": "http://test", "capabilities": ["test"]})
            
            # Verify agent is registered
            assert "test_agent" in registry
            assert registry.get("test_agent")["endpoint"] == "http://test"
            
            # Verify file was written
            with open(temp_file, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 1
                record = json.loads(lines[0])
                assert record["event"] == "registered"
                assert record["agent_id"] == "test_agent"
        
        finally:
            # Clean up
            os.unlink(temp_file)
    
    def test_multiple_registries_dont_interfere(self):
        """Test that multiple AgentRegistry instances with different files don't interfere."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f1:
            temp_file1 = f1.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f2:
            temp_file2 = f2.name
        
        try:
            # Create two independent registries
            config1 = AgentRegistryConfig(path=temp_file1)
            registry1 = AgentRegistry(config=config1)
            
            config2 = AgentRegistryConfig(path=temp_file2)
            registry2 = AgentRegistry(config=config2)
            
            # Register different agents in each registry
            registry1.register("agent1", {"endpoint": "http://agent1"})
            registry2.register("agent2", {"endpoint": "http://agent2"})
            
            # Verify isolation
            assert "agent1" in registry1
            assert "agent2" not in registry1
            assert "agent2" in registry2
            assert "agent1" not in registry2
            
            # Verify files are separate
            with open(temp_file1, 'r') as f:
                lines1 = f.readlines()
                assert len(lines1) == 1
                record1 = json.loads(lines1[0])
                assert record1["agent_id"] == "agent1"
            
            with open(temp_file2, 'r') as f:
                lines2 = f.readlines()
                assert len(lines2) == 1
                record2 = json.loads(lines2[0])
                assert record2["agent_id"] == "agent2"
        
        finally:
            os.unlink(temp_file1)
            os.unlink(temp_file2)
    
    def test_event_replay_on_load(self):
        """Test that AgentRegistry correctly replays events on load."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            # Create and populate a registry
            config = AgentRegistryConfig(path=temp_file)
            registry1 = AgentRegistry(config=config)
            
            # Register, update, and deregister agents
            registry1.register("agent1", {"endpoint": "http://agent1", "status": "active"})
            registry1.update("agent1", {"status": "inactive"})
            registry1.register("agent2", {"endpoint": "http://agent2"})
            registry1.deregister("agent1")
            
            # Create a new registry instance loading from the same file
            registry2 = AgentRegistry(config=config)
            
            # Verify state was correctly reconstructed
            assert "agent1" not in registry2  # Was deregistered
            assert "agent2" in registry2  # Still registered
            assert registry2.get("agent2")["endpoint"] == "http://agent2"
            
            # Verify count
            assert len(registry2) == 1
        
        finally:
            os.unlink(temp_file)


@pytest.fixture
def temp_agent_registry():
    """Fixture providing an isolated AgentRegistry with temporary file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_file = f.name
    
    try:
        config = AgentRegistryConfig(path=temp_file)
        registry = AgentRegistry(config=config)
        yield registry
    finally:
        os.unlink(temp_file)


class TestAgentRegistryWithFixture:
    """Tests using the temp_agent_registry fixture."""
    
    def test_fixture_isolation(self, temp_agent_registry):
        """Test that fixture provides isolated registry."""
        registry = temp_agent_registry
        
        # Register agent
        registry.register("fixture_agent", {"endpoint": "http://fixture"})
        
        # Verify
        assert "fixture_agent" in registry
        assert registry.get("fixture_agent")["endpoint"] == "http://fixture"
    
    def test_fixture_fresh_for_each_test(self, temp_agent_registry):
        """Test that fixture provides fresh registry for each test."""
        registry = temp_agent_registry
        
        # This test should start with empty registry
        assert len(registry) == 0
        
        # Register agent
        registry.register("test_agent", {"endpoint": "http://test"})
        assert len(registry) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])